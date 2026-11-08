"""Gemeinsame Basis der Entities."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ArenaCoordinator


class ArenaEntity(CoordinatorEntity[ArenaCoordinator]):
    """Haengt alle Entities an ein Geraet pro Bibliotheksausweis."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ArenaCoordinator, entry: ConfigEntry, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Axiell",
            model="Arena",
            configuration_url=entry.data["base_url"].rstrip("/")
            + "/protected/my-account/overview",
        )
        self._username = entry.data[CONF_USERNAME]
