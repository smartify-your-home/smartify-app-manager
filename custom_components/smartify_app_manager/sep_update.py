"""Two-minute Cubi SEP release monitor for the native Home Assistant update entity.

The manager only checks for and announces updates. It never installs or
replaces the running SEP integration.
"""
from __future__ import annotations

from datetime import timedelta
import json
import logging
from pathlib import Path

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .kubi_source import KubiError, VERSION, fetch_latest

_LOGGER = logging.getLogger(__name__)
UPDATE_INTERVAL = timedelta(minutes=2)
SEP_MANIFEST = ("custom_components", "smartify_energy", "manifest.json")


def read_installed_sep_version(manifest_path: str) -> str | None:
    """Read the actual on-disk SEP manifest; never infer it from a download."""
    try:
        payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("domain") != "smartify_energy":
        return None
    version = payload.get("version")
    return version if isinstance(version, str) and VERSION.fullmatch(version) else None


def is_newer_release(installed: str | None, latest: str | None) -> bool:
    """Compare the constrained numeric SEP release versions."""
    if not installed or not latest:
        return False
    if not VERSION.fullmatch(installed) or not VERSION.fullmatch(latest):
        return False
    return tuple(map(int, latest.split("."))) > tuple(map(int, installed.split(".")))


class CubiSEPUpdateCoordinator(DataUpdateCoordinator[dict]):
    """Fetch Cubi metadata every two minutes independently of GitHub sync."""

    def __init__(self, hass, entry, settings: dict) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name="Cubi Smartify Energy Pro update",
            update_interval=UPDATE_INTERVAL,
        )
        self.settings = settings

    async def _async_update_data(self) -> dict:
        installed = await self.hass.async_add_executor_job(
            read_installed_sep_version, self.hass.config.path(*SEP_MANIFEST)
        )
        url = self.settings.get("kubi_url") or ""
        if not url:
            return {
                "configured": False,
                "installed_version": installed,
                "latest_version": None,
            }
        try:
            latest = await fetch_latest(self.hass, url)
        except (KubiError, OSError) as err:
            raise UpdateFailed(f"Cubi-Paketserver nicht erreichbar: {err}") from err
        return {
            "configured": True,
            "installed_version": installed,
            "latest_version": latest["version"],
            "source_commit": latest["source_commit"],
            "sha256": latest["sha256"],
            "archive": latest["archive"],
            "update_available": is_newer_release(installed, latest["version"]),
        }
