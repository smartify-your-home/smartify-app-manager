"""Offline verification for private-release Cubi app packages, no network."""
import hashlib
from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cubi"))
import build_catalog
import fetch_releases
import package_policy


class CubiPrivateDistributionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.policy = ROOT / "cubi/package-policy.example.json"
        self.recipes = ROOT / "cubi/app-recipes.json"
        self.checkouts = self.work / "checkouts"
        self.out = self.work / "staging"
        self.src = (
            self.checkouts / "smartify-energy-pro" / "src"
            / "custom_components" / "smartify_energy"
        )
        self.src.mkdir(parents=True)
        (self.src / "manifest.json").write_text(json.dumps({
            "domain": "smartify_energy", "version": "0.3.87"
        }))
        (self.src / "__init__.py").write_text("# offline test")
        (self.src / "brand").mkdir()
        (self.src / "brand" / "icon.png").write_bytes(b"test icon")
        receipt = self.checkouts / "smartify-energy-pro" / "cubi-release.json"
        receipt.write_text(json.dumps({
            "tag": "0.3.87",
            "published_release": True,
            "published_at": "2026-11-13T11:00:00Z",
        }))

    def test_build_only_approved_app_with_manifest_and_icon(self):
        result = build_catalog.build_staging(
            self.policy, self.recipes, self.checkouts, self.out
        )
        self.assertEqual(len(result["apps"]), 1)
        app = result["apps"][0]
        self.assertEqual(app["id"], "energy-pro")
        self.assertEqual(app["version"], "0.3.87")
        self.assertEqual(app["kind"], "integration")
        path = self.out / "energy-pro" / "energy-pro-0.3.87.zip"
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), app["sha256"])
        with ZipFile(path) as zipfile:
            names = set(zipfile.namelist())
        self.assertIn("custom_components/smartify_energy/manifest.json", names)
        self.assertIn("custom_components/smartify_energy/__init__.py", names)
        self.assertNotIn("cubi-release.json", names)
        self.assertTrue((self.out / "energy-pro" / "icon-0.3.87.png").exists())
        self.assertNotIn("smartify-tailnet-viewer", json.dumps(result))

    def test_mismatched_release_fails_closed(self):
        (self.src / "manifest.json").write_text(json.dumps({
            "domain": "smartify_energy", "version": "0.3.86"
        }))
        with self.assertRaises(build_catalog.BuildError):
            build_catalog.build_staging(
                self.policy, self.recipes, self.checkouts, self.out
            )

    def test_bad_or_unknown_app_recipe_fails(self):
        data = json.loads(self.recipes.read_text(encoding="utf-8"))
        data["apps"]["smartify-energy-pro"]["destination"] = "../config"
        dest = self.work / "bad-recipes.json"
        dest.write_text(json.dumps(data))
        with self.assertRaises(build_catalog.BuildError):
            build_catalog.load_recipes(dest)

    def test_reject_unsafe_source_symlinks(self):
        (self.src / "unsafe").symlink_to(self.src / "__init__.py")
        with self.assertRaises(build_catalog.BuildError):
            build_catalog.build_staging(
                self.policy, self.recipes, self.checkouts, self.out
            )

    def test_public_release_falls_back_without_private_repo_token(self):
        url = "https://api.github.com/repos/smartify-your-home/smartify-energy-pro/releases/latest"
        requests = []

        def open_stub(request, timeout):
            authorized = request.get_header("Authorization") is not None
            requests.append(authorized)
            if authorized:
                raise HTTPError(url, 404, "Not Found", {}, None)
            return BytesIO(json.dumps({
                "tag_name": "0.3.89", "draft": False,
                "prerelease": False, "published_at": "2026-11-14T10:35:14Z",
            }).encode())

        with patch.object(fetch_releases.NO_REDIRECT, "open", side_effect=open_stub):
            release, authenticated = fetch_releases.github_request_json(url, "scoped-token")
        self.assertEqual(release["tag_name"], "0.3.89")
        self.assertFalse(authenticated)
        self.assertEqual(requests, [True, False])

    def test_private_repository_auth_not_silently_bypassed(self):
        url = "https://api.github.com/repos/smartify-your-home/smartify-raffstore/releases/latest"
        requests = []

        def open_stub(request, timeout):
            requests.append(request.get_header("Authorization") is not None)
            raise HTTPError(url, 404, "Not Found", {}, None)

        with patch.object(fetch_releases.NO_REDIRECT, "open", side_effect=open_stub):
            with self.assertRaisesRegex(fetch_releases.FetchError, "permissions"):
                fetch_releases.github_request_json(url, "wrong-token")
        self.assertEqual(requests, [True, False])

    def test_public_tarball_fetch_has_no_bearer_header(self):
        url = "https://api.github.com/repos/smartify-your-home/smartify-energy-pro/tarball/0.3.89"
        def open_stub(request, timeout):
            self.assertIsNone(request.get_header("Authorization"))
            return BytesIO(b"tar-test")
        with patch.object(fetch_releases.NO_REDIRECT, "open", side_effect=open_stub):
            self.assertEqual(fetch_releases.fetch_private_tarball(url, None), b"tar-test")

    def test_non_404_auth_error_does_not_retry_anonymously(self):
        url = "https://api.github.com/repos/smartify-your-home/smartify-energy-pro/releases/latest"
        calls = []
        def open_stub(request, timeout):
            calls.append(1)
            raise HTTPError(url, 401, "Unauthorized", {}, None)
        with patch.object(fetch_releases.NO_REDIRECT, "open", side_effect=open_stub):
            with self.assertRaisesRegex(fetch_releases.FetchError, "401"):
                fetch_releases.github_request_json(url, "bad-token")
        self.assertEqual(len(calls), 1)

    def test_protected_token_and_invalid_redirect_helpers(self):
        token_file = self.work / "github-token"
        token_file.write_text("example-token\n")
        token_file.chmod(0o600)
        self.assertEqual(fetch_releases.token_from_file(token_file), "example-token")
        token_file.chmod(0o644)
        with self.assertRaises(fetch_releases.FetchError):
            fetch_releases.token_from_file(token_file)


if __name__ == "__main__":
    unittest.main()
