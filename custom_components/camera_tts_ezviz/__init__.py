"""Camera TTS EZVIZ integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CameraTTSAPI
from .const import CONF_API_KEY, CONF_BASE_URL, DOMAIN, PLATFORMS
from .coordinator import CameraTTSCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Camera TTS EZVIZ from a config entry."""
    api = CameraTTSAPI(
        async_get_clientsession(hass),
        entry.data[CONF_BASE_URL],
        entry.data[CONF_API_KEY],
    )
    coordinator = CameraTTSCoordinator(hass, entry, api)

    # This is async network I/O using HA's shared aiohttp session. It does not
    # block the event loop. The API timeout is deliberately short; if Docker is
    # unavailable Home Assistant marks the entry not ready and retries later.
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry cleanly."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    entry: ConfigEntry,
    device_entry: dr.DeviceEntry,
) -> bool:
    """Allow removal of a stale camera device no longer returned by Docker."""
    coordinator: CameraTTSCoordinator = entry.runtime_data
    active_identifiers = {
        (DOMAIN, f"{entry.entry_id}:{camera_id}")
        for camera_id in (coordinator.data or {})
    }
    return not bool(device_entry.identifiers & active_identifiers)
