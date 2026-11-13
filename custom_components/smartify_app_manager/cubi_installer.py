"""Staged, checksum-verified Cubi package install for supported HA app types.

No PIN in this development mode. Only a Home Assistant administrator can
invoke installs. A backup is retained and existing installations are never
modified by polling.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
from zipfile import ZipFile, BadZipFile

from aiohttp import ClientError, ClientTimeout
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .cubi_catalog import APP_TARGETS
from .kubi_source import KubiError, validate_server_url

MAX_ARCHIVE = 40 * 1024 * 1024
MAX_EXTRACTED = 80 * 1024 * 1024
MAX_MEMBERS = 500
INSTALLABLE = {"integration", "dashboard", "theme"}


def _safe_parts(dest: str) -> tuple[str, ...]:
    pure = PurePosixPath(dest)
    if pure.is_absolute() or ".." in pure.parts or "\\" in dest:
        raise KubiError("Unsicherer Installationspfad")
    return pure.parts


def _install_verified_archive(
    config_path: str, app: dict, archive: bytes
) -> str:
    """Validate whole package, then atomically replace one owned target.

    The app and exact destination must match the audited Manager allowlist.
    Existing data are moved to a dated backup; on failure restore the old
    installation. Never delete or overwrite unrelated configuration paths.
    """
    app_id = app["id"]
    kind, expected_dest = APP_TARGETS.get(app_id, (None, None))
    if (kind not in INSTALLABLE or app["kind"] != kind
            or expected_dest != app["target"]):
        raise KubiError("Dieser App-Typ ist noch nicht für direkte HA-Installation freigegeben")
    if sha256(archive).hexdigest() != app["sha256"]:
        raise KubiError("Cubi-Paket SHA-256 stimmt nicht überein")
    dest_parts = _safe_parts(expected_dest)
    config = Path(config_path)
    target = config.joinpath(*dest_parts)
    if not config.is_dir():
        raise KubiError("Home-Assistant-Konfigurationsverzeichnis fehlt")
    current = config
    for part in dest_parts:
        current = current / part
        if current.is_symlink():
            raise KubiError("Unsicherer symbolischer Link im Installationspfad")
    if not target.resolve().is_relative_to(config.resolve()):
        raise KubiError("Installationspfad verlässt die HA-Konfiguration")
    try:
        with ZipFile(BytesIO(archive), "r") as z:
            infos = z.infolist()
            if not infos or len(infos) > MAX_MEMBERS:
                raise KubiError("Unzulässiger Paketumfang")
            total = 0
            names = set()
            expected_prefix = expected_dest + "/"
            for item in infos:
                name = item.filename
                path = PurePosixPath(name)
                if (name in names or path.is_absolute() or "\\" in name
                        or ".." in path.parts or item.is_dir()
                        or stat.S_IFMT(item.external_attr >> 16) == stat.S_IFLNK):
                    raise KubiError("Unsichere oder doppelte Paketpfade")
                names.add(name)
                if kind == "dashboard" and expected_dest.endswith(".js"):
                    if name != expected_dest:
                        raise KubiError("Paket versucht fremde Dateien zu überschreiben")
                elif not name.startswith(expected_prefix):
                    raise KubiError("Paket außerhalb des freigegebenen App-Verzeichnisses")
                total += item.file_size
            if total > MAX_EXTRACTED:
                raise KubiError("Entpackte Paketgröße zu groß")
            if kind == "integration":
                manifest = f"{expected_dest}/manifest.json"
                init_file = f"{expected_dest}/__init__.py"
                if manifest not in names or init_file not in names:
                    raise KubiError("Integration benötigt manifest.json und __init__.py")
                data = json.loads(z.read(manifest))
                if (data.get("domain") != dest_parts[-1]
                        or data.get("version") != app["version"]):
                    raise KubiError("Integration und Release-Version stimmen nicht überein")
            if z.testzip() is not None:
                raise KubiError("CRC-Fehler im Download")

            parent = target.parent
            parent.mkdir(parents=True, exist_ok=True)
            work = Path(tempfile.mkdtemp(prefix=".cubi-install-", dir=parent))
            staged = work / ("new.js" if target.suffix == ".js" else "new")
            if target.suffix != ".js":
                staged.mkdir()
            try:
                for item in infos:
                    rel = item.filename[len(expected_prefix):] if target.suffix != ".js" else ""
                    staged_file = staged / rel if rel else staged
                    staged_file.parent.mkdir(parents=True, exist_ok=True)
                    # Recheck file sizes at extraction time.
                    with z.open(item, "r") as source, staged_file.open("wb") as output:
                        left = item.file_size
                        while left:
                            chunk = source.read(min(65536, left))
                            if not chunk:
                                raise KubiError("Unvollständiges ZIP")
                            output.write(chunk)
                            left -= len(chunk)
                backup = None
                if target.exists():
                    backups = config / "smartify-manager-backups" / app_id
                    if backups.is_symlink() or backups.parent.is_symlink():
                        raise KubiError("Unsicherer Backup-Pfad")
                    backups.mkdir(parents=True, exist_ok=True)
                    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
                    backup = backups / stamp
                    os.replace(target, backup)
                try:
                    os.replace(staged, target)
                except Exception:
                    if backup is not None and backup.exists() and not target.exists():
                        os.replace(backup, target)
                    raise
                return str(backup) if backup else ""
            finally:
                shutil.rmtree(work, ignore_errors=True)
    except (OSError, BadZipFile, json.JSONDecodeError, UnicodeDecodeError) as err:
        raise KubiError(f"Paketinstallation fehlgeschlagen: {err}") from err


async def install_cubi_app(hass, base_url: str, app: dict) -> dict:
    """Download one validated zip, then run the blocking filesystem work."""
    base = validate_server_url(base_url)
    if not base:
        raise KubiError("Cubi-Paketserver nicht konfiguriert")
    if not app.get("install_supported"):
        raise KubiError("Installation dieses App-Typs wird noch nicht unterstützt")
    url = base + app["zip"]
    session = async_get_clientsession(hass)
    try:
        async with session.get(
            url, allow_redirects=False,
            timeout=ClientTimeout(total=90, sock_connect=8, sock_read=30),
        ) as response:
            if response.status != 200:
                raise KubiError(f"Cubi-Download HTTP {response.status}")
            if response.content_length and response.content_length > MAX_ARCHIVE:
                raise KubiError("App-Paket zu groß")
            buffer = bytearray()
            async for chunk in response.content.iter_chunked(65536):
                buffer.extend(chunk)
                if len(buffer) > MAX_ARCHIVE:
                    raise KubiError("App-Paket überschreitet Größenlimit")
    except (ClientError, asyncio.TimeoutError) as err:
        raise KubiError(f"Cubi-Download fehlgeschlagen: {err}") from err
    data = bytes(buffer)
    if sha256(data).hexdigest() != app["sha256"]:
        raise KubiError("SHA-256-Sicherheitsprüfung fehlgeschlagen")
    backup = await hass.async_add_executor_job(
        _install_verified_archive, hass.config.config_dir, app, data
    )
    return {
        "id": app["id"], "version": app["version"], "backup": backup,
        "restart_required": app["restart_required"],
    }
