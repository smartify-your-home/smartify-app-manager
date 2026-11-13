"""Smartify App Manager: local catalog and optional administrative PIN."""
from __future__ import annotations

import hashlib
import hmac
import os
import time
from pathlib import Path

import voluptuous as vol
from homeassistant.components import frontend, panel_custom, websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.config_entries import ConfigEntry

from .const import APPS, DOMAIN, GITHUB_OWNER, PANEL_PATH, STORAGE_KEY, STORAGE_VERSION


def _hash_pin(pin: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, 310000).hex()


def _pin_valid(settings: dict, pin: str) -> bool:
    if not settings.get("pin_hash") or not settings.get("pin_salt"):
        return False
    return hmac.compare_digest(settings["pin_hash"], _hash_pin(pin, bytes.fromhex(settings["pin_salt"])))


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up initial integration domain."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    settings = await store.async_load() or {"locks": {}, "pin_hash": None, "pin_salt": None}
    hass.data[DOMAIN] = {"store": store, "settings": settings, "failed_attempts": 0, "blocked_until": 0.0}

    def check_pin(pin: str) -> bool:
        state = hass.data[DOMAIN]
        now = time.monotonic()
        if now < state["blocked_until"]:
            return False
        if _pin_valid(settings, pin):
            state["failed_attempts"] = 0
            return True
        state["failed_attempts"] += 1
        if state["failed_attempts"] >= 5:
            state["blocked_until"] = now + 300
            state["failed_attempts"] = 0
        return False

    @websocket_api.require_admin
    @websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/catalog"})
    @callback
    def catalog(hass, connection, msg):
        locks = settings.get("locks", {})
        apps = [{"id": key, "name": name, "repo": repo, "category": category,
                 "icon": icon, "locked": bool(locks.get(key, False)),
                 "url": f"https://github.com/{GITHUB_OWNER}/{repo}"}
                for key, name, repo, category, icon in APPS]
        connection.send_result(msg["id"], {"apps": apps, "pin_configured": bool(settings.get("pin_hash")),
                                          "trial_enabled": False})

    @websocket_api.require_admin
    @websocket_api.async_response
    @websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/set_pin",
                                       vol.Required("new_pin"): vol.All(str, vol.Length(min=6, max=32)),
                                       vol.Optional("old_pin", default=""): str})
    async def set_pin(hass, connection, msg):
        if settings.get("pin_hash") and not check_pin(msg["old_pin"]):
            connection.send_error(msg["id"], "invalid_pin", "Bisherige PIN ist ungültig")
            return
        salt = os.urandom(16)
        settings["pin_salt"] = salt.hex()
        settings["pin_hash"] = _hash_pin(msg["new_pin"], salt)
        await store.async_save(settings)
        connection.send_result(msg["id"], {"success": True})

    @websocket_api.require_admin
    @websocket_api.async_response
    @websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/set_lock",
                                       vol.Required("app_id"): str,
                                       vol.Required("locked"): bool,
                                       vol.Required("pin"): str})
    async def set_lock(hass, connection, msg):
        if msg["app_id"] not in {a[0] for a in APPS}:
            connection.send_error(msg["id"], "unknown_app", "Unbekanntes Modul")
            return
        if not settings.get("pin_hash"):
            connection.send_error(msg["id"], "pin_required", "Bitte zuerst Administrator-PIN einrichten")
            return
        if not check_pin(msg["pin"]):
            connection.send_error(msg["id"], "invalid_pin", "PIN ungültig")
            return
        settings.setdefault("locks", {})[msg["app_id"]] = msg["locked"]
        await store.async_save(settings)
        connection.send_result(msg["id"], {"success": True})

    for handler in (catalog, set_pin, set_lock):
        websocket_api.async_register_command(hass, handler)

    await hass.http.async_register_static_paths([
        StaticPathConfig(f"/{DOMAIN}_assets", str(Path(__file__).parent / "frontend"), False)
    ])
    await panel_custom.async_register_panel(
        hass, webcomponent_name="smartify-app-manager-panel",
        frontend_url_path=PANEL_PATH, sidebar_title="Smartify",
        sidebar_icon="mdi:apps", module_url=f"/{DOMAIN}_assets/panel.js?v=0.1.0",
        require_admin=True,
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    frontend.async_remove_panel(hass, PANEL_PATH)
    hass.data.pop(DOMAIN, None)
    return True
