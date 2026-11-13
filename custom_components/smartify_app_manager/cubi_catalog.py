"""Read and validate the Cubi multi-app customer catalog via Home Assistant.

No GitHub requests are made from a customer Home Assistant. Catalog entries
come only from the allowlisted HTTPS Cubi server and are checked against the
Manager's locally audited installation paths.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path, PurePosixPath
import re

from aiohttp import ClientError, ClientTimeout
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .kubi_source import KubiError, validate_server_url

CATALOG_SCHEMA = 1
MAX_CATALOG_BYTES = 128 * 1024
VERSION = re.compile(r"^\d+\.\d+\.\d+$")
DIGEST = re.compile(r"^[a-f0-9]{64}$")
SAFE_ID = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")

# Audit this map before adding a new app. No server-supplied path can install
# arbitrary files in Home Assistant. Supervisor apps are handled separately.
APP_TARGETS = {
    "energy-pro": ("integration", "custom_components/smartify_energy"),
    "flow-card": ("integration", "custom_components/smartify_flow_card"),
    "floorplan3d": ("integration", "custom_components/smartify_floorplan3d"),
    "heating": ("integration", "custom_components/smartify_heating"),
    "row-card": ("integration", "custom_components/smartify_energy_row_card"),
    "weather-card": ("dashboard", "www/smartify/weather-card/smartify-weather-chart.js"),
    "raffstore": ("dashboard", "www/smartify/raffstore"),
    "tabbar": ("dashboard", "www/smartify/tabbar"),
    "themes": ("theme", "themes/smartify"),
    "person-detection": ("supervisor", None),
    "sip-manager": ("supervisor", None),
}


def validate_catalog(payload: object) -> dict:
    if (not isinstance(payload, dict)
            or payload.get("schema_version") != CATALOG_SCHEMA
            or payload.get("source") != "Cubi"):
        raise KubiError("Ungültiger Cubi-App-Katalog")
    apps = payload.get("apps")
    if not isinstance(apps, list) or len(apps) > len(APP_TARGETS):
        raise KubiError("Ungültige App-Anzahl im Cubi-Katalog")
    seen = set()
    clean = []
    for raw in apps:
        if not isinstance(raw, dict):
            raise KubiError("Ungültiger Cubi-App-Eintrag")
        ident = raw.get("id")
        if not isinstance(ident, str) or not SAFE_ID.fullmatch(ident):
            raise KubiError("Ungültige Cubi-App-ID")
        if ident not in APP_TARGETS:
            raise KubiError("Unbekannte Cubi-App – Manager muss aktualisiert werden")
        if ident in seen:
            raise KubiError("Doppelte Cubi-App-ID")
        seen.add(ident)
        kind, target = APP_TARGETS[ident]
        version = raw.get("version")
        digest = raw.get("sha256")
        archive = raw.get("zip")
        title = raw.get("name")
        if (raw.get("kind") != kind
                or raw.get("installed_destination") != target
                or not isinstance(version, str) or not VERSION.fullmatch(version)
                or not isinstance(digest, str) or not DIGEST.fullmatch(digest)
                or not isinstance(title, str) or not 1 <= len(title) <= 90
                or not isinstance(archive, str)
                or archive != f"/v1/{ident}/{ident}-{version}.zip"):
            raise KubiError(f"Ungültige Freigabe-/Paketdaten für {ident}")
        icon = raw.get("icon")
        if icon is not None and icon != f"/v1/{ident}/icon-{version}.png":
            raise KubiError(f"Ungültiger Icon-Pfad für {ident}")
        clean.append({
            "id": ident,
            "name": title,
            "kind": kind,
            "version": version,
            "sha256": digest,
            "zip": archive,
            "icon": icon,
            "target": target,
            "install_supported": kind in {"integration", "dashboard", "theme"},
            "restart_required": kind == "integration",
        })
    return {"schema_version": 1, "source": "Cubi", "apps": clean}


async def fetch_catalog(hass, server_url: str) -> dict:
    base = validate_server_url(server_url)
    if not base:
        raise KubiError("Kein Cubi-Paketserver eingerichtet")
    session = async_get_clientsession(hass)
    try:
        async with session.get(
            f"{base}/v1/catalog.json",
            allow_redirects=False,
            timeout=ClientTimeout(total=15, sock_connect=6),
        ) as response:
            if response.status != 200:
                raise KubiError(f"Cubi-Katalog HTTP {response.status}")
            raw = await response.content.read(MAX_CATALOG_BYTES + 1)
    except (ClientError, asyncio.TimeoutError) as err:
        raise KubiError(f"Cubi-Katalog nicht erreichbar: {err}") from err
    if len(raw) > MAX_CATALOG_BYTES:
        raise KubiError("Cubi-Katalog ist zu groß")
    try:
        return validate_catalog(json.loads(raw))
    except (ValueError, UnicodeDecodeError) as err:
        raise KubiError("Cubi-Katalog enthält ungültige Daten") from err


def installed_version(hass_config: str, app: dict, receipts: dict | None = None) -> str | None:
    """Use actual integration manifest; otherwise a manager-owned receipt."""
    target = app["target"]
    if target is None:
        return None
    root = Path(hass_config)
    if app["kind"] == "integration":
        manifest = root / target / "manifest.json"
        try:
            value = json.loads(manifest.read_text(encoding="utf-8")).get("version")
        except (OSError, ValueError, UnicodeError):
            return None
        return value if isinstance(value, str) and VERSION.fullmatch(value) else None
    value = (receipts or {}).get(app["id"])
    return value if isinstance(value, str) and VERSION.fullmatch(value) else None


def newer(installed: str | None, available: str) -> bool:
    if not installed:
        return False
    return tuple(int(p) for p in available.split(".")) > tuple(int(p) for p in installed.split("."))
