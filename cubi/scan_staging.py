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
import hashlib
import time
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
MAX_RESCAN_HOURS = 12
SIGNATURE_DIR = Path('/var/lib/clamav')
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


def _digest_sources(directories: list[str]) -> str:
    """Hash exact package/source bytes, so changed files force a new scan."""
    digest = hashlib.sha256()
    for directory in sorted(directories):
        root = Path(directory)
        for item in sorted(root.rglob("*")):
            if item.is_symlink():
                raise ScanRejected(f"Symlink in scan input: {item}")
            if not item.is_file():
                continue
            digest.update(str(item.relative_to(root)).encode("utf-8"))
            with item.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
    return digest.hexdigest()


def _signature_fingerprint(database_dir: Path) -> str:
    """Require recent ClamAV signatures, including for cached clean scans."""
    if database_dir.is_symlink() or not database_dir.is_dir():
        raise ScanRejected("ClamAV signature directory missing or unsafe")
    definitions = sorted(
        file for file in database_dir.iterdir()
        if file.suffix in {".cvd", ".cld", ".cud"}
        and file.name.split(".")[0] in {"main", "daily", "bytecode"}
        and file.is_file() and not file.is_symlink()
    )
    if not definitions:
        raise ScanRejected("ClamAV signature files not installed (freshclam)")
    newest = max(file.stat().st_mtime for file in definitions)
    if time.time() - newest > MAX_SIGNATURE_AGE_DAYS * 86400:
        raise ScanRejected("ClamAV signature files older than 7 days")
    summary = [(file.name, file.stat().st_size, file.stat().st_mtime_ns)
               for file in definitions]
    return hashlib.sha256(json.dumps(summary).encode("utf-8")).hexdigest()


def _read_cache(filename: Path) -> dict | None:
    if filename.is_symlink() or not filename.is_file():
        return None
    try:
        data = json.loads(filename.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return None
    return data if isinstance(data, dict) else None


def _write_cache(filename: Path, payload: dict) -> None:
    if filename.is_symlink() or filename.parent.is_symlink():
        raise ScanRejected("Unsafe ClamAV clean-cache location")
    filename.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=filename.parent,
        prefix=".clamav-clean-", delete=False,
    ) as tmp:
        os.fchmod(tmp.fileno(), 0o600)
        json.dump(payload, tmp, ensure_ascii=False, indent=2)
        tmp.write("\n")
        tmpname = Path(tmp.name)
    os.replace(tmpname, filename)


def scan_staging(
    staging: Path,
    checkouts: Path,
    policy_file: Path,
    recipes_file: Path,
    report_dir: Path,
    *,
    scanner: str = SCANNER,
    runner=subprocess.run,
    cache_enabled: bool = False,
    signatures_dir: Path = SIGNATURE_DIR,
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
    # The two-minute timer must not reload ClamAV's sizeable database on
    # every unchanged catalog. Cache only the latest *verified* clean scan,
    # bound to exact source/package bytes and current database signatures.
    scan_fingerprint = None
    signature_fingerprint = None
    cache_file = report_dir.parent / "clamav-last-clean.json"
    if cache_enabled:
        if not Path(scanner).is_file():
            raise ScanRejected("ClamAV scanner executable missing")
        signature_fingerprint = _signature_fingerprint(signatures_dir)
        scan_fingerprint = _digest_sources(inputs)
        cached = _read_cache(cache_file)
        now = time.time()
        if (cached is not None
                and cached.get("status") == "CLEAN"
                and cached.get("scan_digest") == scan_fingerprint
                and cached.get("signature_digest") == signature_fingerprint
                and isinstance(cached.get("completed_epoch"), (int, float))
                and 0 <= now - cached["completed_epoch"] < MAX_RESCAN_HOURS * 3600):
            print("Cubi ClamAV CACHED_CLEAN: unchanged releases and signatures")
            return {"status": "CLEAN", "cached": True,
                    "apps": [{"id": x["id"], "version": x["version"]}
                             for x in catalog["apps"]]}

    # Must verify scan succeeded and actually touched files, not just exit 0.
    command = [
        scanner,
        "--recursive",
        "--infected",
        "--alert-encrypted-archive=yes",
        "--scan-archive=yes",
        "--alert-exceeds-max=yes",
        "--fail-if-cvd-older-than=7",
        "--follow-dir-symlinks=0",
        "--follow-file-symlinks=0",
        "--max-filesize=32M",
        "--max-scansize=512M",
        "--max-files=5000",
        "--max-recursion=20",
        "--max-scantime=0",
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
    if cache_enabled:
        _write_cache(cache_file, {
            "status": "CLEAN",
            "completed_epoch": time.time(),
            "scan_digest": scan_fingerprint,
            "signature_digest": signature_fingerprint,
        })
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
            cache_enabled=True,
        )
    except (ScanRejected, BuildError, OSError, ValueError) as error:
        print(f"BLOCKED: Cubi will retain previous catalog. {error}", flush=True)
        return 1
    print("CLEAN: All approved source trees, ZIP packages and icons passed ClamAV.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
