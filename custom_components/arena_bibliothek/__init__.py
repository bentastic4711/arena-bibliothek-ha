"""Arena Bibliothek - Ausleihen eines Axiell-Arena-Kontos in Home Assistant."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant

from .api import ArenaClient
from .const import CONF_BASE_URL, CONF_SCAN_HOURS, DEFAULT_SCAN_HOURS, PLATFORMS
from .coordinator import ArenaCoordinator

_PLATFORMS = [Platform(platform) for platform in PLATFORMS]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Einen konfigurierten Bibliotheksausweis einrichten."""
    client = ArenaClient(
        entry.data[CONF_BASE_URL],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )
    scan_hours = entry.options.get(
        CONF_SCAN_HOURS, entry.data.get(CONF_SCAN_HOURS, DEFAULT_SCAN_HOURS)
    )
    coordinator = ArenaCoordinator(hass, entry, client, timedelta(hours=scan_hours))

    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Eintrag wieder abbauen."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Nach Aenderung der Optionen neu laden."""
    await hass.config_entries.async_reload(entry.entry_id)
