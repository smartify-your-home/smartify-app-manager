"""Smartify App Manager: administrator catalog with periodic GitHub synchronisation."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import hashlib
import hmac
import os
from pathlib import Path
import time

import probatio
from homeassistant.components import frontend, panel_custom, websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store

from .catalog_sync import async_sync_catalog, current_catalog
from .const import DOMAIN, PANEL_PATH, STORAGE_KEY, STORAGE_VERSION
from .kubi_source import KubiError, download_release, fetch_latest, validate_server_url


def _hash_pin(pin: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, 310000).hex()


def _pin_valid(settings: dict, pin: str) -> bool:
    if not settings.get("pin_hash") or not settings.get("pin_salt"):
        return False
    return hmac.compare_digest(
        settings["pin_hash"], _hash_pin(pin, bytes.fromhex(settings["pin_salt"]))
    )


def _check_pin(state: dict, pin: str) -> bool:
    now = time.monotonic()
    if now < state["blocked_until"]:
        return False
    if _pin_valid(state["settings"], pin):
        state["failed_attempts"] = 0
        return True
    state["failed_attempts"] += 1
    if state["failed_attempts"] >= 5:
        state["blocked_until"] = now + 300
        state["failed_attempts"] = 0
    return False


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): f"{DOMAIN}/catalog"})
@callback
def websocket_catalog(hass, connection, msg) -> None:
    state = hass.data.get(DOMAIN)
    if state is None:
        connection.send_error(msg["id"], "not_loaded", "Smartify Manager nicht geladen")
        return
    settings = state["settings"]
    connection.send_result(msg["id"], {
        "apps": current_catalog(settings),
        "pin_configured": bool(settings.get("pin_hash")),
        "trial_enabled": False,
        "last_synced": settings.get("last_synced"),
        "sync_error": state.get("sync_error"),
        "catalog_source": "GitHub + lokaler Fallback",
    })


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): f"{DOMAIN}/refresh"})
@websocket_api.async_response
async def websocket_refresh(hass, connection, msg) -> None:
    state = hass.data.get(DOMAIN)
    if state is None:
        connection.send_error(msg["id"], "not_loaded", "Smartify Manager nicht geladen")
        return
    updated = await async_sync_catalog(hass, state, force=True)
    connection.send_result(msg["id"], {
        "updated": updated,
        "last_synced": state["settings"].get("last_synced"),
        "sync_error": state.get("sync_error"),
    })


@websocket_api.require_admin
@websocket_api.websocket_command({
    probatio.Required("type"): f"{DOMAIN}/set_pin",
    probatio.Required("new_pin"): str,
    probatio.Optional("old_pin", default=""): str,
})
@websocket_api.async_response
async def websocket_set_pin(hass, connection, msg) -> None:
    state = hass.data.get(DOMAIN)
    if state is None:
        connection.send_error(msg["id"], "not_loaded", "Smartify Manager nicht geladen")
        return
    settings = state["settings"]
    if not 6 <= len(msg["new_pin"]) <= 32:
        connection.send_error(msg["id"], "invalid_format", "PIN muss 6 bis 32 Zeichen haben")
        return
    if settings.get("pin_hash") and not _check_pin(state, msg["old_pin"]):
        connection.send_error(msg["id"], "invalid_pin", "Bisherige PIN ungültig")
        return
    salt = os.urandom(16)
    settings["pin_salt"] = salt.hex()
    settings["pin_hash"] = _hash_pin(msg["new_pin"], salt)
    await state["store"].async_save(settings)
    connection.send_result(msg["id"], {"success": True})


@websocket_api.require_admin
@websocket_api.websocket_command({
    probatio.Required("type"): f"{DOMAIN}/set_lock",
    probatio.Required("app_id"): str,
    probatio.Required("locked"): bool,
    probatio.Required("pin"): str,
})
@websocket_api.async_response
async def websocket_set_lock(hass, connection, msg) -> None:
    state = hass.data.get(DOMAIN)
    if state is None:
        connection.send_error(msg["id"], "not_loaded", "Smartify Manager nicht geladen")
        return
    settings = state["settings"]
    valid_ids = {app["id"] for app in current_catalog(settings)}
    if msg["app_id"] not in valid_ids:
        connection.send_error(msg["id"], "unknown_app", "Unbekanntes Modul")
        return
    if not settings.get("pin_hash"):
        connection.send_error(msg["id"], "pin_required", "Bitte zuerst Administrator-PIN einrichten")
        return
    if not _check_pin(state, msg["pin"]):
        connection.send_error(msg["id"], "invalid_pin", "PIN ungültig")
        return
    settings.setdefault("locks", {})[msg["app_id"]] = msg["locked"]
    await state["store"].async_save(settings)
    connection.send_result(msg["id"], {"success": True})


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): f"{DOMAIN}/kubi_status"})
@websocket_api.async_response
async def websocket_kubi_status(hass, connection, msg) -> None:
    """Fetch the local Kubi metadata via HA, never from the browser."""
    state = hass.data.get(DOMAIN)
    if state is None:
        connection.send_error(msg["id"], "not_loaded", "Smartify Manager nicht geladen")
        return
    url = state["settings"].get("kubi_url", "")
    if not url:
        connection.send_result(msg["id"], {
            "configured": False, "connected": False, "url": "",
        })
        return
    try:
        meta = await fetch_latest(hass, url)
        connection.send_result(msg["id"], {
            "configured": True, "connected": True, "url": url, **meta,
        })
    except (KubiError, OSError) as err:
        connection.send_result(msg["id"], {
            "configured": True, "connected": False, "url": url, "error": str(err),
        })


@websocket_api.require_admin
@websocket_api.websocket_command({
    probatio.Required("type"): f"{DOMAIN}/kubi_set_url",
    probatio.Required("url"): str,
})
@websocket_api.async_response
async def websocket_kubi_set_url(hass, connection, msg) -> None:
    """Save a LAN-only IPv4 package source; empty disables it."""
    state = hass.data.get(DOMAIN)
    if state is None:
        connection.send_error(msg["id"], "not_loaded", "Smartify Manager nicht geladen")
        return
    try:
        url = validate_server_url(msg["url"])
    except KubiError as err:
        connection.send_error(msg["id"], "invalid_server_url", str(err))
        return
    state["settings"]["kubi_url"] = url
    await state["store"].async_save(state["settings"])
    connection.send_result(msg["id"], {"success": True, "url": url})


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): f"{DOMAIN}/kubi_download"})
@websocket_api.async_response
async def websocket_kubi_download(hass, connection, msg) -> None:
    """Save only a validated SEP ZIP to /config; never install it automatically."""
    state = hass.data.get(DOMAIN)
    if state is None:
        connection.send_error(msg["id"], "not_loaded", "Smartify Manager nicht geladen")
        return
    url = state["settings"].get("kubi_url", "")
    if not url:
        connection.send_error(msg["id"], "not_configured", "Bitte Kubi-Adresse speichern")
        return
    async with state["kubi_download_lock"]:
        try:
            meta = await fetch_latest(hass, url)
            result = await download_release(hass, url, meta)
            connection.send_result(msg["id"], result)
        except (KubiError, OSError) as err:
            connection.send_error(msg["id"], "kubi_download_failed", str(err))


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register WebSocket handlers once, so reloading the entry is safe."""
    for handler in (
        websocket_catalog, websocket_refresh, websocket_set_pin, websocket_set_lock,
        websocket_kubi_status, websocket_kubi_set_url, websocket_kubi_download,
    ):
        websocket_api.async_register_command(hass, handler)
    await hass.http.async_register_static_paths([
        StaticPathConfig(f"/{DOMAIN}_assets", str(Path(__file__).parent / "frontend"), False)
    ])
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Load persistent settings, register panel and start periodic catalog sync."""
    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    settings = await store.async_load() or {}
    settings.setdefault("locks", {})
    state = {
        "store": store,
        "settings": settings,
        "failed_attempts": 0,
        "blocked_until": 0.0,
        "sync_attempt": 0.0,
        "sync_lock": asyncio.Lock(),
        "kubi_download_lock": asyncio.Lock(),
        "sync_error": None,
    }
    hass.data[DOMAIN] = state

    await panel_custom.async_register_panel(
        hass,
        webcomponent_name="smartify-app-manager-panel",
        frontend_url_path=PANEL_PATH,
        sidebar_title="Smartify",
        sidebar_icon="mdi:apps",
        module_url=f"/{DOMAIN}_assets/panel.js?v=0.3.0",
        require_admin=True,
    )

    @callback
    def _scheduled_catalog_sync(_now):
        hass.async_create_background_task(
            async_sync_catalog(hass, state), "Smartify catalog sync"
        )

    entry.async_on_unload(
        async_track_time_interval(hass, _scheduled_catalog_sync, timedelta(hours=6))
    )
    hass.async_create_background_task(
        async_sync_catalog(hass, state), "Smartify initial catalog sync"
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Remove the panel and cancel the periodic callback on reload."""
    entry.async_unload()
    frontend.async_remove_panel(hass, PANEL_PATH)
    hass.data.pop(DOMAIN, None)
    return True
