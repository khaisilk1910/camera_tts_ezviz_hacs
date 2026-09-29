"""Diagnostics support for Camera TTS EZVIZ."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_API_KEY
from .coordinator import CameraTTSCoordinator

TO_REDACT = {CONF_API_KEY, "mic_url"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return non-sensitive diagnostics for troubleshooting."""
    coordinator: CameraTTSCoordinator = entry.runtime_data
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "last_update_success": coordinator.last_update_success,
        "backend_version": coordinator.api.backend_version,
        "backend_features": sorted(coordinator.api.features),
        "update_interval_seconds": (
            coordinator.update_interval.total_seconds()
            if coordinator.update_interval is not None
            else None
        ),
        "cameras": async_redact_data(coordinator.data or {}, TO_REDACT),
    }
