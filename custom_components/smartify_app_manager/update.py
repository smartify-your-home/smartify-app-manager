"""Official Home Assistant update entity for Smartify Energy Pro on Cubi."""
from __future__ import annotations

from homeassistant.components.update import UpdateEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .sep_update import CubiSEPUpdateCoordinator, is_newer_release

SEP_ICON = (
    "https://raw.githubusercontent.com/smartify-your-home/"
    "smartify-energy-pro/main/custom_components/smartify_energy/brand/icon.png"
)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Register the native update indication, without an install action."""
    coordinator = hass.data[DOMAIN]["sep_update_coordinator"]
    async_add_entities([CubiSEPUpdateEntity(coordinator)])


class CubiSEPUpdateEntity(CoordinatorEntity[CubiSEPUpdateCoordinator], UpdateEntity):
    """An update is reported, never auto-installed or silently downloaded."""

    _attr_name = "Smartify Energy Pro (Cubi)"
    _attr_title = "Smartify Energy Pro"
    _attr_unique_id = "smartify_app_manager_cubi_sep_update"
    _attr_icon = "mdi:update"
    _attr_supported_features = 0
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
        version = self.latest_version
        if version is None:
            return None
        return (
            "https://github.com/smartify-your-home/"
            f"smartify-energy-pro/releases/tag/{version}"
        )

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
    def entity_picture(self) -> str:
        return SEP_ICON

    def version_is_newer(self, latest_version: str, installed_version: str) -> bool:
        """Avoid a false notification when Cubi has an older package."""
        return is_newer_release(installed_version, latest_version)
