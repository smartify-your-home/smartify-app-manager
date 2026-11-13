"""LAN-only SEP release metadata and verified archive download for HA admins.

SHA-256 verifies the downloaded ZIP against Kubi's metadata, but does not
authenticate the server. A secured HTTPS portal is required for customers.
"""
from __future__ import annotations

import asyncio
from hashlib import sha256
from io import BytesIO
import ipaddress
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
from urllib.parse import urlsplit
import zipfile

from aiohttp import ClientError, ClientTimeout
from homeassistant.helpers.aiohttp_client import async_get_clientsession

MODULE = "smartify-energy-pro"
COMPONENT = "custom_components/smartify_energy"
VERSION = re.compile(r"^\d+\.\d+\.\d+$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")
MAX_ARCHIVE_BYTES = 30 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 80 * 1024 * 1024
MAX_METADATA_BYTES = 16 * 1024
PRIVATE_NETWORKS = tuple(ipaddress.ip_network(net) for net in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"
))


class KubiError(ValueError):
    """A configuration, network or package integrity failure."""


def validate_server_url(raw: str) -> str:
    """Accept only HTTP to literal RFC1918 IPv4 addresses; no DNS or redirects."""
    if not isinstance(raw, str) or len(raw) > 120:
        raise KubiError("Ungültige Serveradresse")
    raw = raw.strip().rstrip("/")
    if not raw:
        return ""
    try:
        parts = urlsplit(raw)
        port = parts.port
        address = ipaddress.IPv4Address(parts.hostname or "")
    except (ValueError, TypeError) as err:
        raise KubiError("Bitte eine lokale IPv4-Adresse eingeben") from err
    if (parts.scheme != "http" or parts.username or parts.password
            or parts.path or parts.query or parts.fragment
            or not any(address in network for network in PRIVATE_NETWORKS)):
        raise KubiError("Nur HTTP-Adressen in privaten IPv4-Netzen erlaubt")
    if port is None:
        port = 80
    return f"http://{address}:{port}"


def validate_metadata(payload: object) -> dict:
    """Reject all URLs and file names other than the immutable SEP layout."""
    if not isinstance(payload, dict):
        raise KubiError("latest.json ist kein JSON-Objekt")
    version = payload.get("version")
    if not isinstance(version, str) or not VERSION.fullmatch(version):
        raise KubiError("Ungültige SEP-Versionsnummer")
    if (payload.get("module") != MODULE
            or payload.get("archive") != f"{MODULE}-{version}.zip"
            or payload.get("release_notes") != f"{MODULE}-{version}-release-notes.md"
            or payload.get("tag") not in (version, f"v{version}")
            or payload.get("verified_published_release") is not True
            or not isinstance(payload.get("sha256"), str)
            or not SHA256.fullmatch(payload["sha256"])
            or not isinstance(payload.get("source_commit"), str)
            or not COMMIT.fullmatch(payload["source_commit"])):
        raise KubiError("Metadaten passen nicht zu einem geprüften SEP-Release")
    return {
        "module": MODULE, "version": version, "archive": payload["archive"],
        "sha256": payload["sha256"], "source_commit": payload["source_commit"],
        "release_notes": payload["release_notes"],
    }


async def fetch_latest(hass, server_url: str) -> dict:
    base = validate_server_url(server_url)
    if not base:
        raise KubiError("Noch keine Kubi-Serveradresse hinterlegt")
    session = async_get_clientsession(hass)
    try:
        async with session.get(
            f"{base}/sep/latest.json", allow_redirects=False,
            timeout=ClientTimeout(total=10, sock_connect=5)
        ) as response:
            if response.status != 200:
                raise KubiError(f"Kubi latest.json: HTTP {response.status}")
            raw = await response.content.read(MAX_METADATA_BYTES + 1)
    except (ClientError, asyncio.TimeoutError) as err:
        raise KubiError(f"Kubi nicht erreichbar: {err}") from err
    if len(raw) > MAX_METADATA_BYTES:
        raise KubiError("Kubi-Metadaten sind zu groß")
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as err:
        raise KubiError("Kubi liefert ungültiges JSON") from err
    return validate_metadata(data)


def _validate_zip(data: bytes, version: str) -> None:
    """Reject traversal, bombs, symlinks, wrong component and mismatched version."""
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            infos = archive.infolist()
            if not infos or len(infos) > 200:
                raise KubiError("ZIP enthält unerwartet viele oder keine Dateien")
            if sum(item.file_size for item in infos) > MAX_UNCOMPRESSED_BYTES:
                raise KubiError("ZIP überschreitet die erlaubte entpackte Größe")
            names = set()
            for item in infos:
                name = item.filename
                path = PurePosixPath(name)
                if (name in names or name.startswith("/") or "\\" in name
                        or ".." in path.parts or path.is_absolute()
                        or ((item.external_attr >> 16) & 0o170000) == 0o120000):
                    raise KubiError("ZIP enthält unsichere Dateipfade")
                if not (name == "INSTALLATION.txt" or name.startswith(f"{COMPONENT}/")):
                    raise KubiError("ZIP enthält Dateien außerhalb der SEP-Integration")
                names.add(name)
            manifest = f"{COMPONENT}/manifest.json"
            if manifest not in names or f"{COMPONENT}/__init__.py" not in names:
                raise KubiError("ZIP enthält keine vollständige SEP-Integration")
            if archive.getinfo(manifest).file_size > 16384:
                raise KubiError("SEP-Manifest zu groß")
            info = json.loads(archive.read(manifest))
            if info.get("domain") != "smartify_energy" or info.get("version") != version:
                raise KubiError("ZIP und veröffentlichte Version stimmen nicht überein")
            if archive.testzip() is not None:
                raise KubiError("ZIP hat eine ungültige CRC-Prüfsumme")
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, UnicodeDecodeError) as err:
        raise KubiError(f"Ungültiges SEP-ZIP: {err}") from err


def _store_verified(hass_config_dir: str, filename: str, data: bytes, digest: str) -> str:
    directory = Path(hass_config_dir) / "smartify-downloads" / "sep"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    if path.is_symlink():
        raise KubiError("Unsicherer symbolischer Link am Zieldateipfad")
    if path.exists():
        if not path.is_file() or sha256(path.read_bytes()).hexdigest() != digest:
            raise KubiError("Vorhandenes Versionspaket ist unterschiedlich – nicht überschrieben")
        return str(path)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=directory, prefix=".sep-", suffix=".tmp", delete=False
        ) as file:
            temp = Path(file.name)
            file.write(data)
        os.chmod(temp, 0o600)
        os.replace(temp, path)
        return str(path)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


async def download_release(hass, server_url: str, meta: dict) -> dict:
    """Download ZIP into HA /config only after SHA and full ZIP validation."""
    base = validate_server_url(server_url)
    # Metadata is already validated by fetch_latest; validate once more defensively.
    meta = validate_metadata({
        **meta, "tag": meta["version"], "verified_published_release": True
    })
    session = async_get_clientsession(hass)
    try:
        async with session.get(
            f"{base}/sep/{meta['archive']}", allow_redirects=False,
            timeout=ClientTimeout(total=90, sock_connect=5, sock_read=30)
        ) as response:
            if response.status != 200:
                raise KubiError(f"Kubi ZIP: HTTP {response.status}")
            if response.content_length and response.content_length > MAX_ARCHIVE_BYTES:
                raise KubiError("SEP-ZIP ist zu groß")
            buffer = bytearray()
            async for chunk in response.content.iter_chunked(65536):
                buffer.extend(chunk)
                if len(buffer) > MAX_ARCHIVE_BYTES:
                    raise KubiError("SEP-ZIP überschreitet 30 MiB")
    except (ClientError, asyncio.TimeoutError) as err:
        raise KubiError(f"Download fehlgeschlagen: {err}") from err
    data = bytes(buffer)
    if sha256(data).hexdigest() != meta["sha256"]:
        raise KubiError("SHA-256-Prüfsumme falsch – ZIP nicht gespeichert")
    await hass.async_add_executor_job(_validate_zip, data, meta["version"])
    destination = await hass.async_add_executor_job(
        _store_verified, hass.config.config_dir, meta["archive"], data, meta["sha256"]
    )
    return {"version": meta["version"], "filename": meta["archive"],
            "destination": destination, "bytes": len(data), "sha256": meta["sha256"]}
