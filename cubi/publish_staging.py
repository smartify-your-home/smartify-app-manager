#!/usr/bin/env python3
"""Atomically publish an audited private staged Cubi catalog to Tailscale Serve.

The staging and private backup directories MUST reside outside the served root
and on the same filesystem. A revoked app cannot remain in the new v1 set.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile

from package_policy import load_policy, is_allowed
from build_catalog import load_recipes, BuildError

VERSION = re.compile(r"^\d+\.\d+\.\d+$")


def audit_staging(staging: Path, policy_file: Path, recipes_file: Path) -> dict:
    if staging.is_symlink() or not staging.is_dir():
        raise BuildError("Staging directory missing or symlinked")
    policy = load_policy(policy_file)
    recipes = load_recipes(recipes_file)
    catalog_file = staging / "catalog.json"
    if catalog_file.is_symlink() or not catalog_file.is_file():
        raise BuildError("Missing catalog.json")
    catalog = json.loads(catalog_file.read_text(encoding="utf-8"))
    if (catalog.get("schema_version") != 1 or catalog.get("source") != "Cubi"
            or not isinstance(catalog.get("apps"), list)):
        raise BuildError("Invalid Cubi catalog")
    expected_dirs = set()
    for item in catalog["apps"]:
        ident = item.get("id")
        version = item.get("version")
        if not isinstance(version, str) or not VERSION.fullmatch(version):
            raise BuildError("Invalid release version")
        repo = next((name for name, recipe in recipes.items()
                     if recipe["id"] == ident), None)
        if not repo or not is_allowed(policy, repo, "publish"):
            raise BuildError(f"Unapproved package in catalog: {ident}")
        expected_dirs.add(ident)
        folder = staging / ident
        if folder.is_symlink() or not folder.is_dir():
            raise BuildError(f"Missing package directory: {ident}")
        zipname = f"{ident}-{version}.zip"
        zipfile = folder / zipname
        if zipfile.is_symlink() or not zipfile.is_file():
            raise BuildError(f"Missing zip file: {ident}")
        if hashlib.sha256(zipfile.read_bytes()).hexdigest() != item["sha256"]:
            raise BuildError(f"Invalid ZIP checksum: {ident}")
        expected_files = {zipname}
        if item.get("icon"):
            expected_files.add(f"icon-{version}.png")
        actual_files = {p.name for p in folder.iterdir()}
        if actual_files != expected_files or any(p.is_symlink() for p in folder.iterdir()):
            raise BuildError(f"Unexpected files in {ident} package")
    actual_dirs = {p.name for p in staging.iterdir() if p.name != "catalog.json"}
    if actual_dirs != expected_dirs:
        raise BuildError("Unapproved, stale or extra files in staging root")
    return catalog


def _same_snapshot(stage: Path, published: Path) -> bool:
    """Avoid changing published assets or creating backups when files match."""
    if not published.is_dir() or published.is_symlink():
        return False

    def contents(root: Path) -> dict[str, str] | None:
        files = {}
        for item in root.rglob("*"):
            if item.is_symlink():
                return None
            if item.is_file():
                relative = item.relative_to(root).as_posix()
                with item.open("rb") as stream:
                    digest = hashlib.sha256()
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
                files[relative] = digest.hexdigest()
        return files

    return contents(stage) == contents(published)


def publish(
    staging: Path, live_release_root: Path, backup_parent: Path,
    policy_file: Path, recipes_file: Path,
) -> dict:
    """Move complete staging snapshot to public /v1 with rollback."""
    catalog = audit_staging(staging, policy_file, recipes_file)
    root = live_release_root
    old = root / "v1"
    if (root.is_symlink() or old.is_symlink() or backup_parent.is_symlink()
            or not root.is_dir()):
        raise BuildError("Unsafe public release directory")
    backup_parent.mkdir(parents=True, exist_ok=True)
    if backup_parent.resolve().is_relative_to(root.resolve()):
        raise BuildError("Backups must not be in public directory")
    if staging.resolve().is_relative_to(root.resolve()):
        raise BuildError("Staging must not be in public directory")
    if staging.stat().st_dev != root.stat().st_dev:
        raise BuildError("Staging and public directory must share filesystem")
    if _same_snapshot(staging, old):
        return {"apps": len(catalog["apps"]), "backup": "", "changed": False}
    moved_old = None
    if old.exists():
        moved_old = Path(tempfile.mkdtemp(prefix="cubi-v1-old-", dir=backup_parent))
        moved_old.rmdir()
        os.replace(old, moved_old)
    try:
        os.replace(staging, old)
    except Exception:
        if moved_old is not None and moved_old.exists() and not old.exists():
            os.replace(moved_old, old)
        raise
    # Backups are intentionally retained privately for manual rollback.
    return {"apps": len(catalog["apps"]), "backup": str(moved_old) if moved_old else "", "changed": True}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", default="/etc/smartify/package-policy.json")
    parser.add_argument("--recipes", default=str(Path(__file__).with_name("app-recipes.json")))
    parser.add_argument("--stage", required=True)
    parser.add_argument("--serve-root", default="/srv/smartify/releases")
    parser.add_argument("--private-backups", default="/srv/smartify/private-backups")
    args = parser.parse_args(argv)
    result = publish(
        Path(args.stage), Path(args.serve_root), Path(args.private_backups),
        Path(args.policy), Path(args.recipes)
    )
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
