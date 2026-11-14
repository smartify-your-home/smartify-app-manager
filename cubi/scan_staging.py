#!/usr/bin/env python3
"""Mandatory fail-closed ClamAV gate for a *private staged* Cubi release.

Do not call publish_staging.py unless this process returns zero. Scan both
the package ZIPs/icons in the staging snapshot and the exact published
GitHub source trees before replacing /srv/smartify/releases/v1.

Uses clamscan (no clamd daemon required). A missing binary, outdated
signatures, scan timeout, unreadable files or malware always block publication.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from build_catalog import BuildError, load_recipes
from package_policy import load_policy, is_allowed
from publish_staging import audit_staging

SCANNER = "/usr/bin/clamscan"
MAX_SIGNATURE_AGE_DAYS = 7
SCAN_TIMEOUT_SECONDS = 140
SCANNED = re.compile(r"(?m)^\s*Scanned files:\s*(\d+)\s*$")
INFECTED = re.compile(r"(?m)^\s*Infected files:\s*(\d+)\s*$")
ERRORS = re.compile(r"(?m)^\s*Total errors:\s*(\d+)\s*$")


class ScanRejected(RuntimeError):
    """ClamAV did not completely clear the candidate release."""


def _validate_source_tree(checkouts: Path, repository: str) -> Path:
    """Reject symlinks; ClamAV must never leave its checked release source."""
    base = checkouts.resolve()
    root = checkouts / repository
    path = root / "src"
    if root.is_symlink() or path.is_symlink() or not path.is_dir():
        raise ScanRejected(f"Missing or symlinked release source: {repository}")
    if not path.resolve().is_relative_to(base):
        raise ScanRejected(f"Release source escapes private checkouts: {repository}")
    count = 0
    for member in path.rglob("*"):
        if member.is_symlink():
            raise ScanRejected(f"Symlink in {repository}: {member.relative_to(path)}")
        if member.is_file():
            count += 1
            if not member.resolve().is_relative_to(path.resolve()):
                raise ScanRejected(f"Escaping file in {repository}")
    if not count:
        raise ScanRejected(f"Empty release source: {repository}")
    return path


def _report(report_dir: Path, result: dict) -> Path:
    if report_dir.is_symlink() or report_dir.parent.is_symlink():
        raise ScanRejected("Unsafe ClamAV report directory")
    report_dir.mkdir(parents=True, exist_ok=True)
    name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = report_dir / f"clamav-{name}-{os.getpid()}.json"
    # Atomic creation with private permissions, never in the served /v1 tree.
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=report_dir, prefix=".clamav-",
        delete=False,
    ) as temp:
        os.fchmod(temp.fileno(), 0o600)
        json.dump(result, temp, indent=2, ensure_ascii=False)
        temp.write("\n")
        tempname = Path(temp.name)
    os.replace(tempname, output)
    return output


def scan_staging(
    staging: Path,
    checkouts: Path,
    policy_file: Path,
    recipes_file: Path,
    report_dir: Path,
    *,
    scanner: str = SCANNER,
    runner=subprocess.run,
) -> dict:
    """Return an audit result on success; raise ScanRejected on any failure.

    runner can be injected for offline regression tests. On the real Cubi LXC
    this always calls the installed /usr/bin/clamscan with no shell involved.
    """
    if not staging.is_dir() or staging.is_symlink():
        raise ScanRejected("Staged Cubi package folder missing/unsafe")
    if report_dir.resolve().is_relative_to(staging.resolve()):
        raise ScanRejected("ClamAV report folder must remain outside public staging")
    policy = load_policy(policy_file)
    recipes = load_recipes(recipes_file)
    catalog = audit_staging(staging, policy_file, recipes_file)
    inputs = [str(staging.resolve())]
    repositories = []
    for item in catalog["apps"]:
        repo = next(
            (name for name, recipe in recipes.items() if recipe["id"] == item["id"]),
            None,
        )
        if not repo or not is_allowed(policy, repo, "publish"):
            raise ScanRejected(f"Publication not approved: {item['id']}")
        inputs.append(str(_validate_source_tree(checkouts, repo)))
        repositories.append(repo)
    # Must verify scan succeeded and actually touched files, not just exit 0.
    command = [
        scanner,
        "--recursive=yes",
        "--infected",
        "--scan-archive=yes",
        "--alert-exceeds-max=yes",
        "--fail-if-cvd-older-than=7",
        "--follow-dir-symlinks=0",
        "--follow-file-symlinks=0",
        "--max-filesize=32M",
        "--max-scansize=512M",
        "--max-files=5000",
        "--max-recursion=20",
        "--max-scantime=110000",
        *inputs,
    ]
    result = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "engine": "clamscan",
        "max_signature_age_days": MAX_SIGNATURE_AGE_DAYS,
        "apps": [{"id": item["id"], "version": item["version"]}
                 for item in catalog["apps"]],
        "repositories": repositories,
        "status": "BLOCKED",
    }
    try:
        completed = runner(
            command, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, timeout=SCAN_TIMEOUT_SECONDS,
            check=False,
        )
        output = completed.stdout or ""
        result["exit_code"] = completed.returncode
        result["scanner_output"] = output[-12000:]
        infected_match = INFECTED.search(output)
        scanned_match = SCANNED.search(output)
        errors_match = ERRORS.search(output)
        if (completed.returncode != 0 or infected_match is None
                or scanned_match is None or int(scanned_match.group(1)) < 1
                or int(infected_match.group(1)) != 0
                or (errors_match and int(errors_match.group(1)) != 0)):
            result["error"] = (
                f"ClamAV did not clear the release "
                f"(exit={completed.returncode}; "
                f"scanned={scanned_match.group(1) if scanned_match else '?'}; "
                f"infected={infected_match.group(1) if infected_match else '?'})."
            )
            raise ScanRejected(result["error"])
        result["scanned_files"] = int(scanned_match.group(1))
        result["infected_files"] = 0
        result["status"] = "CLEAN"
    except subprocess.TimeoutExpired as error:
        result["error"] = f"ClamAV timeout after {SCAN_TIMEOUT_SECONDS}s"
        raise ScanRejected(result["error"]) from error
    except (OSError, ValueError) as error:
        result["error"] = f"ClamAV execution failed: {type(error).__name__}: {error}"
        raise ScanRejected(result["error"]) from error
    finally:
        path = _report(report_dir, result)
        print(
            f"Cubi ClamAV {result['status']}: "
            f"apps={len(result['apps'])}, "
            f"scanned={result.get('scanned_files', '?')}, "
            f"report={path}",
            flush=True,
        )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--checkouts", required=True)
    parser.add_argument("--policy", default="/etc/smartify/package-policy.json")
    parser.add_argument("--recipes", default=str(Path(__file__).with_name("app-recipes.json")))
    parser.add_argument("--report-dir", default="/srv/smartify/private-state/clamav-reports")
    args = parser.parse_args(argv)
    try:
        scan_staging(
            Path(args.stage),
            Path(args.checkouts),
            Path(args.policy),
            Path(args.recipes),
            Path(args.report_dir),
        )
    except (ScanRejected, BuildError, OSError, ValueError) as error:
        print(f"BLOCKED: Cubi will retain previous catalog. {error}", flush=True)
        return 1
    print("CLEAN: All approved source trees, ZIP packages and icons passed ClamAV.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
