"""Camera TTS EZVIZ integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CameraTTSAPI
from .const import CONF_API_KEY, CONF_BASE_URL, DOMAIN, PLATFORMS
from .coordinator import CameraTTSCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Camera TTS EZVIZ from a config entry."""
    session = async_get_clientsession(hass)
    api = CameraTTSAPI(session, entry.data[CONF_BASE_URL], entry.data[CONF_API_KEY])
    coordinator = CameraTTSCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
    }
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded
