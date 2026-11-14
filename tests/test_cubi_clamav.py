"""Offline regression tests for mandatory ClamAV gate before Cubi /v1 publish."""
from pathlib import Path
import json
import os
import time
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cubi"))

import build_catalog
import scan_staging


class CubiClamavGateTests(unittest.TestCase):
    def setUp(self):
        self.working = tempfile.TemporaryDirectory()
        self.addCleanup(self.working.cleanup)
        base = Path(self.working.name)
        self.policy = ROOT / "cubi" / "package-policy.example.json"
        self.recipes = ROOT / "cubi" / "app-recipes.json"
        self.checkouts = base / "checkouts"
        src = self.checkouts / "smartify-energy-pro" / "src"
        target = src / "custom_components" / "smartify_energy"
        target.mkdir(parents=True)
        (target / "manifest.json").write_text(json.dumps({
            "domain": "smartify_energy", "version": "0.3.87",
        }))
        (target / "__init__.py").write_text("# test")
        (target / "brand").mkdir()
        (target / "brand" / "icon.png").write_bytes(b"icon")
        (self.checkouts / "smartify-energy-pro" / "cubi-release.json").write_text(
            json.dumps({"tag": "0.3.87", "published_release": True})
        )
        self.stage = base / "candidate"
        build_catalog.build_staging(self.policy, self.recipes, self.checkouts, self.stage)
        self.reports = base / "private" / "clamav-reports"

    def scan(self, runner):
        return scan_staging.scan_staging(
            self.stage, self.checkouts, self.policy, self.recipes,
            self.reports, runner=runner,
        )

    def assert_report(self, status):
        reports = list(self.reports.glob("clamav-*.json"))
        self.assertEqual(len(reports), 1)
        document = json.loads(reports[0].read_text())
        self.assertEqual(document["status"], status)
        self.assertEqual(document["apps"][0]["id"], "energy-pro")
        self.assertEqual(document["apps"][0]["version"], "0.3.87")
        return document

    def test_refresh_script_enforces_clamav_before_publish(self):
        pipeline = (ROOT / "cubi" / "refresh.sh").read_text()
        self.assertLess(pipeline.index("build_catalog.py"),
                        pipeline.index("scan_staging.py"))
        self.assertLess(pipeline.index("scan_staging.py"),
                        pipeline.index("publish_staging.py"))
        self.assertIn("set -euo pipefail", pipeline)

    def test_scan_covers_source_and_zip_before_publication(self):
        def fake(command, **kwargs):
            self.assertEqual(command[0], "/usr/bin/clamscan")
            self.assertIn("--recursive", command)
            self.assertIn("--scan-archive=yes", command)
            self.assertIn("--fail-if-cvd-older-than=7", command)
            self.assertIn("--alert-exceeds-max=yes", command)
            self.assertIn(str(self.stage.resolve()), command)
            self.assertIn(
                str((self.checkouts / "smartify-energy-pro" / "src").resolve()),
                command,
            )
            self.assertNotIn("publish_staging.py", command)
            return SimpleNamespace(
                returncode=0,
                stdout="----------- SCAN SUMMARY -----------\n"
                       "Scanned files: 7\nInfected files: 0\n",
            )
        result = self.scan(fake)
        self.assertEqual(result["scanned_files"], 7)
        self.assert_report("CLEAN")

    def test_clean_cache_skips_unchanged_packages_and_rechecks_changes(self):
        database = self.reports.parent / "db"
        database.mkdir(parents=True)
        (database / "daily.cvd").write_bytes(b"test definitions")
        scanner_file = self.reports.parent / "clamscan"
        scanner_file.write_text("#!/bin/sh\\n")
        invocations = []

        def runner(command, **kwargs):
            invocations.append(command)
            return SimpleNamespace(
                returncode=0, stdout="Scanned files: 7\\nInfected files: 0\\n",
            )

        def scan_cached():
            return scan_staging.scan_staging(
                self.stage, self.checkouts, self.policy, self.recipes,
                self.reports, scanner=str(scanner_file), runner=runner,
                cache_enabled=True, signatures_dir=database,
            )

        first = scan_cached()
        self.assertEqual(first["status"], "CLEAN")
        self.assertEqual(len(invocations), 1)
        second = scan_cached()
        self.assertTrue(second["cached"])
        self.assertEqual(len(invocations), 1)
        source_file = (self.checkouts / "smartify-energy-pro" / "src"
                       / "custom_components" / "smartify_energy" / "__init__.py")
        source_file.write_text("# changed source")
        third = scan_cached()
        self.assertEqual(third["status"], "CLEAN")
        self.assertEqual(len(invocations), 2)
        # New signatures require a new scan even when ZIP/source are the same.
        (database / "daily.cvd").write_bytes(b"new definitions")
        fourth = scan_cached()
        self.assertEqual(len(invocations), 3)

    def test_signature_database_missing_or_stale_blocks_cached_result(self):
        database = self.reports.parent / "db"
        database.mkdir(parents=True)
        with self.assertRaisesRegex(scan_staging.ScanRejected, "signature"):
            scan_staging._signature_fingerprint(database)
        old = database / "daily.cvd"
        old.write_text("stale signatures")
        age = time.time() - 9 * 86400
        os.utime(old, (age, age))
        with self.assertRaisesRegex(scan_staging.ScanRejected, "older than"):
            scan_staging._signature_fingerprint(database)

    def test_infected_archive_denied(self):
        def virus(command, **kwargs):
            return SimpleNamespace(
                returncode=1, stdout="Eicar-Test-Signature FOUND\n"
                "Scanned files: 5\nInfected files: 1\n"
            )
        with self.assertRaises(scan_staging.ScanRejected):
            self.scan(virus)
        self.assert_report("BLOCKED")

    def test_scanner_failure_denied(self):
        for returncode, output in [
            (2, "ERROR: virus database unavailable"),
            (0, "Scanned files: 0\nInfected files: 0\n"),
            (0, "Scanned files: 3\nInfected files: 0\nTotal errors: 1\n"),
            (0, "Scan was skipped, no summary"),
        ]:
            with self.subTest(returncode=returncode, output=output):
                for path in self.reports.glob("clamav-*.json"):
                    path.unlink()
                def fail(command, **kwargs):
                    return SimpleNamespace(returncode=returncode, stdout=output)
                with self.assertRaises(scan_staging.ScanRejected):
                    self.scan(fail)
                self.assert_report("BLOCKED")

    def test_timeout_or_missing_clamscan_denied(self):
        def timeout(command, **kwargs):
            raise subprocess.TimeoutExpired(command, 140)
        with self.assertRaises(scan_staging.ScanRejected):
            self.scan(timeout)
        self.assert_report("BLOCKED")

        for path in self.reports.glob("clamav-*.json"):
            path.unlink()
        def missing(command, **kwargs):
            raise FileNotFoundError("/usr/bin/clamscan")
        with self.assertRaises(scan_staging.ScanRejected):
            self.scan(missing)
        self.assert_report("BLOCKED")

    def test_unsafe_source_symlink_rejected_without_scan(self):
        source = self.checkouts / "smartify-energy-pro" / "src"
        (source / "bad-link").symlink_to("/etc/passwd")
        def must_not_run(command, **kwargs):
            self.fail("Never scan an unsafe source tree")
        with self.assertRaises(scan_staging.ScanRejected):
            self.scan(must_not_run)

    def test_invalid_staging_denied_before_scanner(self):
        (self.stage / "unexpected-binary").write_text("unapproved")
        def must_not_run(command, **kwargs):
            self.fail("Invalid catalog was allowed through to scanner")
        with self.assertRaises(build_catalog.BuildError):
            self.scan(must_not_run)


if __name__ == "__main__":
    unittest.main()
