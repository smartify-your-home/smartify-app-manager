#!/usr/bin/env python3
"""Build a sanitized Cubi customer catalog from already fetched GitHub release trees.

Only the *server-side* global publish allowlist authorizes catalog entries.
The script writes into a private staging directory, NEVER directly into the
live Tailscale Serve root. Deployment must replace the customer-visible set
and revoke removed files before switching the catalog.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile

from package_policy import PolicyError, load_policy, is_allowed

VERSION = re.compile(r"^v?(\d+\.\d+\.\d+)$")
SAFE_ID = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")
MAX_ZIP_FILE = 16 * 1024 * 1024
MAX_APP_UNCOMPRESSED = 64 * 1024 * 1024
MAX_FILES = 500
MODES = {"integration", "dashboard", "theme", "supervisor", "external"}


class BuildError(ValueError):
    pass


def load_recipes(filename: str | Path) -> dict:
    content = json.loads(Path(filename).read_text(encoding="utf-8"))
    if type(content) is not dict or set(content) != {"schema_version", "apps"}:
        raise BuildError("Invalid recipes document")
    if type(content["schema_version"]) is not int or content["schema_version"] != 1:
        raise BuildError("Unsupported recipe format")
    if type(content["apps"]) is not dict:
        raise BuildError("Invalid apps mapping")
    seen_ids = set()
    for repo, entry in content["apps"].items():
        if not isinstance(entry, dict) or set(entry) != {
            "id", "name", "kind", "source", "destination", "icon"
        }:
            raise BuildError(f"Incomplete recipe: {repo}")
        if not SAFE_ID.fullmatch(entry["id"]) or entry["id"] in seen_ids:
            raise BuildError(f"Invalid or duplicate app id: {repo}")
        seen_ids.add(entry["id"])
        if entry["kind"] not in MODES:
            raise BuildError(f"Invalid install kind: {repo}")
        for field in ("source", "destination", "icon"):
            value = entry[field]
            if value is None:
                continue
            if not isinstance(value, str) or not value or "\\" in value:
                raise BuildError(f"Invalid {field}: {repo}")
            p = PurePosixPath(value)
            if p.is_absolute() or ".." in p.parts or "." in p.parts:
                raise BuildError(f"Unsafe {field} path: {repo}")
        if entry["kind"] == "external" and entry["source"] is not None:
            raise BuildError(f"External apps cannot be packaged for HA: {repo}")
    return content["apps"]


def _files_under_root(source_tree: Path, source: str, destination: str) -> list[tuple[Path, str]]:
    """Only follow exact trusted recipe paths; reject symlinks and oversized trees."""
    src = source_tree / source
    if src.is_symlink() or not src.exists():
        raise BuildError(f"Missing or symlink source: {source}")
    if not src.resolve().is_relative_to(source_tree.resolve()):
        raise BuildError("Source escapes checkout")
    entries = []
    candidates = [src] if src.is_file() else sorted(src.rglob("*"))
    base = src.parent if src.is_file() else src
    for path in candidates:
        if path.is_symlink():
            raise BuildError(f"Symlink in package: {path}")
        if not path.is_file():
            continue
        if not path.resolve().is_relative_to(source_tree.resolve()):
            raise BuildError("Package member escapes checkout")
        if path.stat().st_size > MAX_ZIP_FILE:
            raise BuildError(f"File too big: {path}")
        relative = path.relative_to(base).as_posix()
        dest = str(PurePosixPath(destination) / relative)
        if ".." in PurePosixPath(dest).parts or dest.startswith("/"):
            raise BuildError("Unsafe destination")
        entries.append((path, dest))
    if not entries or len(entries) > MAX_FILES:
        raise BuildError("Invalid file count")
    if sum(path.stat().st_size for path, _ in entries) > MAX_APP_UNCOMPRESSED:
        raise BuildError("App too large")
    return entries


def prepare_app(source_tree: Path, recipe: dict, version: str) -> tuple[bytes, bytes | None]:
    """Generate a deterministic ZIP containing only approved HA installation files."""
    from io import BytesIO
    if recipe["kind"] == "external":
        raise BuildError("External desktop app cannot be installed on a HA host")
    source = recipe["source"]
    destination = recipe["destination"]
    if not source or (not destination and recipe["kind"] != "supervisor"):
        raise BuildError("Missing source or destination")
    if recipe["kind"] == "supervisor":
        # Add-on repository export is a separate deployment flow; do not promise
        # supervisor installation until its exact API and Git repo are integrated.
        destination = f"supervisor/{recipe['id']}"
    entries = _files_under_root(source_tree, source, destination)
    if recipe["kind"] == "integration":
        manifest = source_tree / source / "manifest.json"
        if not manifest.is_file():
            raise BuildError("Integration manifest.json missing")
        data = json.loads(manifest.read_text(encoding="utf-8"))
        if data.get("version") != version:
            raise BuildError(f"Manifest version {data.get('version')} does not match release {version}")
    icon = None
    if recipe["icon"]:
        iconfile = source_tree / recipe["icon"]
        if iconfile.is_symlink():
            raise BuildError("Icon is a symlink")
        if iconfile.is_file():
            if iconfile.stat().st_size > 2 * 1024 * 1024:
                raise BuildError("Icon too large")
            icon = iconfile.read_bytes()
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED, compresslevel=8) as archive:
        for file, dest in entries:
            archive.write(file, arcname=dest)
    return buffer.getvalue(), icon


def build_staging(policy_file: Path, recipes_file: Path, checkouts: Path, output: Path) -> dict:
    """Write a full new catalog into a *private empty* directory."""
    policy = load_policy(policy_file)
    recipes = load_recipes(recipes_file)
    if output.exists() and any(output.iterdir()):
        raise BuildError("Staging output must be empty; never reuse a live public directory")
    output.mkdir(parents=True, exist_ok=True)
    catalog = {
        "schema_version": 1,
        "source": "Cubi",
        "apps": [],
    }
    for repo in sorted(policy["apps"]):
        if not is_allowed(policy, repo, "publish"):
            continue
        recipe = recipes.get(repo)
        if not recipe:
            raise BuildError(f"Published app has no audited recipe: {repo}")
        if recipe["kind"] == "external":
            raise BuildError(f"Desktop-only app cannot be published to HA: {repo}")
        checkout = checkouts / repo
        if checkout.is_symlink() or not checkout.is_dir():
            raise BuildError(f"No downloaded release tree for {repo}")
        receipt = checkout / "cubi-release.json"
        if not receipt.is_file() or receipt.is_symlink():
            raise BuildError(f"Missing release receipt for {repo}")
        release = json.loads(receipt.read_text(encoding="utf-8"))
        tag = release.get("tag")
        if not isinstance(tag, str) or not VERSION.fullmatch(tag):
            raise BuildError(f"Invalid official release tag: {repo}")
        if release.get("published_release") is not True:
            raise BuildError(f"Release not verified as published: {repo}")
        version = VERSION.fullmatch(tag).group(1)
        root = checkout / "src"
        if root.is_symlink() or not root.is_dir():
            raise BuildError(f"Missing release snapshot: {repo}")
        package, icon = prepare_app(root, recipe, version)
        folder = output / recipe["id"]
        folder.mkdir()
        zipname = f"{recipe['id']}-{version}.zip"
        (folder / zipname).write_bytes(package)
        icon_url = None
        if icon is not None:
            iconname = f"icon-{version}.png"
            (folder / iconname).write_bytes(icon)
            icon_url = f"/v1/{recipe['id']}/{iconname}"
        catalog["apps"].append({
            "id": recipe["id"],
            "name": recipe["name"],
            "kind": recipe["kind"],
            "version": version,
            "zip": f"/v1/{recipe['id']}/{zipname}",
            "sha256": hashlib.sha256(package).hexdigest(),
            "icon": icon_url,
            "installed_destination": recipe["destination"],
            "install_supported": recipe["kind"] in {"integration", "dashboard", "theme"},
            "restart_required": recipe["kind"] == "integration",
        })
    (output / "catalog.json").write_text(
        json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return catalog


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", default="/etc/smartify/package-policy.json")
    parser.add_argument("--recipes", default=str(Path(__file__).with_name("app-recipes.json")))
    parser.add_argument("--checkouts", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    catalog = build_staging(
        Path(args.policy), Path(args.recipes), Path(args.checkouts), Path(args.output)
    )
    print(f"Built {len(catalog['apps'])} globally approved Smartify packages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
