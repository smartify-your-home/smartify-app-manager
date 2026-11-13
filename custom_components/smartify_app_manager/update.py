"""Official Home Assistant update entity for Smartify Energy Pro on Cubi."""
from __future__ import annotations

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .sep_update import CubiSEPUpdateCoordinator, is_newer_release
from .cubi_catalog import CubiCatalogCoordinator, newer
from .cubi_installer import install_cubi_app
from homeassistant.exceptions import HomeAssistantError

SEP_ICON = (
    "https://raw.githubusercontent.com/smartify-your-home/"
    "smartify-energy-pro/main/custom_components/smartify_energy/brand/icon.png"
)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Register the native update indication, without an install action."""
    coordinator = hass.data[DOMAIN]["sep_update_coordinator"]
    async_add_entities([CubiSEPUpdateEntity(coordinator)])
    catalog = hass.data[DOMAIN]["cubi_catalog_coordinator"]
    added = set()

    def sync_new_entities() -> None:
        for app in (catalog.data or {}).get("apps", []):
            if app["id"] == "energy-pro":
                continue  # existing SEP entity retains its stable unique_id
            if not app.get("install_supported") or app["id"] in added:
                continue
            added.add(app["id"])
            async_add_entities([CubiAppUpdateEntity(catalog, app["id"])])

    sync_new_entities()
    entry.async_on_unload(catalog.async_add_listener(sync_new_entities))


class CubiSEPUpdateEntity(CoordinatorEntity[CubiSEPUpdateCoordinator], UpdateEntity):
    """An update is reported, never auto-installed or silently downloaded."""

    _attr_name = "Smartify Energy Pro (Cubi)"
    _attr_title = "Smartify Energy Pro"
    _attr_unique_id = "smartify_app_manager_cubi_sep_update"
    _attr_icon = "mdi:update"
    _attr_supported_features = UpdateEntityFeature.INSTALL
    _attr_restart_required = True
    _attr_device_info = DeviceInfo(
        identifiers={(DOMAIN, "cubi_sep")},
        name="Smartify Energy Pro – Cubi",
        manufacturer="Smartify",
        model="SEP Paketquelle",
    )

    def __init__(self, coordinator: CubiSEPUpdateCoordinator) -> None:
        super().__init__(coordinator)

    @property
    def available(self) -> bool:
        data = self.coordinator.data or {}
        return (
            self.coordinator.last_update_success
            and bool(data.get("configured"))
            and bool(data.get("installed_version"))
        )

    @property
    def installed_version(self) -> str | None:
        return (self.coordinator.data or {}).get("installed_version")

    @property
    def latest_version(self) -> str | None:
        return (self.coordinator.data or {}).get("latest_version")

    @property
    def release_url(self) -> str | None:
        # Customers need no direct private GitHub access.
        return None

    @property
    def release_summary(self) -> str | None:
        if not self.available or not self.latest_version:
            return None
        return (
            f"SEP {self.latest_version} ist auf Cubi verfügbar. "
            "Details und geprüfter ZIP-Download im Smartify App Manager. "
            "Keine automatische Installation."
        )

    @property
    def entity_picture(self) -> str | None:
        catalog = self.hass.data.get(DOMAIN, {}).get("cubi_catalog_coordinator")
        apps = (catalog.data or {}).get("apps", []) if catalog else []
        app = next((item for item in apps if item["id"] == "energy-pro"), None)
        return app.get("local_icon_url") if app else None

    def version_is_newer(self, latest_version: str, installed_version: str) -> bool:
        """Avoid a false notification when Cubi has an older package."""
        return is_newer_release(installed_version, latest_version)

    async def async_install(self, version: str | None, backup: bool, **kwargs) -> None:
        """Apply only an explicitly approved Cubi package after user action."""
        state = self.hass.data[DOMAIN]
        catalog = state["cubi_catalog_coordinator"]
        app = next((x for x in (catalog.data or {}).get("apps", [])
                    if x["id"] == "energy-pro"), None)
        if app is None:
            raise HomeAssistantError("Cubi-App-Katalog noch nicht aktiviert")
        if version is not None and version != app["version"]:
            raise HomeAssistantError("Nur die freigegebene aktuelle Cubi-Version installierbar")
        async with state["cubi_install_lock"]:
            try:
                await install_cubi_app(self.hass, state["settings"]["kubi_url"], app)
            except (OSError, ValueError) as err:
                raise HomeAssistantError(f"Smartify-Installation fehlgeschlagen: {err}") from err
            await catalog.async_request_refresh()
            await self.coordinator.async_request_refresh()


class CubiAppUpdateEntity(CoordinatorEntity[CubiCatalogCoordinator], UpdateEntity):
    """Native, individually installable Cubi update for an approved Smartify app."""

    _attr_supported_features = UpdateEntityFeature.INSTALL
    _attr_auto_update = False

    def __init__(self, coordinator: CubiCatalogCoordinator, app_id: str) -> None:
        super().__init__(coordinator)
        self.app_id = app_id
        self._attr_unique_id = f"smartify_app_manager_{app_id}_update"
        self._attr_name = f"Smartify {app_id} (Cubi)"

    @property
    def _app(self) -> dict | None:
        return next((x for x in (self.coordinator.data or {}).get("apps", [])
                     if x["id"] == self.app_id), None)

    @property
    def available(self) -> bool:
        app = self._app
        return bool(
            self.coordinator.last_update_success
            and app and app["installed_version"] is not None
        )

    @property
    def title(self) -> str | None:
        app = self._app
        return app["name"] if app else None

    @property
    def installed_version(self) -> str | None:
        app = self._app
        return app["installed_version"] if app else None

    @property
    def latest_version(self) -> str | None:
        app = self._app
        return app["version"] if app else None

    @property
    def entity_picture(self) -> str | None:
        app = self._app
        return app.get("local_icon_url") if app else None

    @property
    def restart_required(self) -> bool:
        app = self._app
        return bool(app and app.get("restart_required"))

    @property
    def release_summary(self) -> str | None:
        app = self._app
        if not app:
            return None
        return f"{app['name']} {app['version']} auf Cubi verfügbar. " \
               "Installation erfolgt nur nach Bestätigung."

    def version_is_newer(self, latest_version: str, installed_version: str) -> bool:
        return newer(installed_version, latest_version)

    async def async_install(self, version: str | None, backup: bool, **kwargs) -> None:
        """Explicit update.install: no implicit polling side effects."""
        app = self._app
        if app is None:
            raise HomeAssistantError("App auf Cubi nicht mehr freigegeben")
        if version is not None and version != app["version"]:
            raise HomeAssistantError("Nur die freigegebene aktuelle Cubi-Version installierbar")
        state = self.hass.data[DOMAIN]
        async with state["cubi_install_lock"]:
            try:
                await install_cubi_app(self.hass, state["settings"]["kubi_url"], app)
                settings = state["settings"]
                settings.setdefault("cubi_managed_versions", {})[self.app_id] = app["version"]
                await state["store"].async_save(settings)
            except (OSError, ValueError) as err:
                raise HomeAssistantError(f"Smartify-Update fehlgeschlagen: {err}") from err
            await self.coordinator.async_request_refresh()

