"""Privacy-aware diagnostics for Camera TTS (no network I/O)."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .api import _safe_error
from .const import CONF_API_KEY, CONF_BASE_URL
from .coordinator import CameraTTSCoordinator

# Do not export backend objects wholesale: mic/RTSP URLs, transport errors and
# vendor-specific fields can contain tokens or camera credentials.
_CAMERA_FIELDS = (
    "vendor", "state", "queued", "current_kind", "gain_db",
    "volume_level", "volume_backend", "ptz_protocol",
)


def _camera_diagnostics(data: dict[str, Any]) -> dict[str, Any]:
    """Allowlist state and capability flags only; exclude raw stream URLs."""
    result = {key: data.get(key) for key in _CAMERA_FIELDS if key in data}
    capabilities = data.get("capabilities")
    if isinstance(capabilities, dict):
        result["capabilities"] = {
            key: value for key, value in capabilities.items()
            if isinstance(value, bool) and key in (
                "ptz", "assist_mic", "media_volume", "audio_upload", "intercom_exec"
            )
        }
    sender = data.get("sender")
    if isinstance(sender, dict):
        result["sender"] = {key: sender.get(key) for key in ("alive", "connected") if key in sender}
    return result


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Provide lightweight support diagnostics without exposing credentials."""
    coordinator: CameraTTSCoordinator = entry.runtime_data
    return {
        "entry": {
            "base_url": _safe_error(entry.data.get(CONF_BASE_URL, "")),
            "api_key_configured": bool(entry.data.get(CONF_API_KEY)),
        },
        "options": dict(entry.options),
        "last_update_success": coordinator.last_update_success,
        "last_successful_update": (
            coordinator.last_update_success_time.isoformat()
            if coordinator.last_update_success_time else None
        ),
        "backend_version": coordinator.api.backend_version,
        "backend_features": sorted(coordinator.api.features),
        "update_interval_seconds": (
            coordinator.update_interval.total_seconds()
            if coordinator.update_interval is not None else None
        ),
        "cameras": {
            camera_id: _camera_diagnostics(data)
            for camera_id, data in (coordinator.data or {}).items()
        },
    }
