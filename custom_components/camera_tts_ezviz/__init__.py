"""Camera TTS multi-vendor integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CameraTTSAPI, CameraTTSAPIError
from .const import CONF_API_KEY, CONF_BASE_URL, DOMAIN, PLATFORMS, PTZ_DIRECTIONS
from .coordinator import CameraTTSCoordinator


def _resolve_camera(hass: HomeAssistant, entity_id: str) -> tuple[CameraTTSCoordinator, str]:
    record = er.async_get(hass).async_get(entity_id)
    if record is None or not record.config_entry_id:
        raise ServiceValidationError(f"Unknown entity: {entity_id}")
    entry = hass.config_entries.async_get_entry(record.config_entry_id)
    if entry is None or entry.domain != DOMAIN:
        raise ServiceValidationError(f"{entity_id} is not a Camera TTS entity")
    coordinator: CameraTTSCoordinator = entry.runtime_data
    prefix = f"{entry.entry_id}_"
    unique_id = str(record.unique_id)
    if not unique_id.startswith(prefix):
        raise ServiceValidationError(f"Cannot resolve camera from {entity_id}")
    camera_id = unique_id[len(prefix):]
    # Services are documented against media_player entities whose unique id is
    # exactly <entry_id>_<camera_id>. Reject platform-specific entity suffixes.
    if camera_id not in (coordinator.data or {}):
        raise ServiceValidationError(
            f"Use the camera media_player entity for this service, not {entity_id}"
        )
    return coordinator, camera_id


async def async_setup(hass: HomeAssistant, _config: dict) -> bool:
    """Register lightweight domain services without performing any network I/O."""

    async def async_ptz_service(call: ServiceCall) -> None:
        coordinator, camera_id = _resolve_camera(hass, call.data["entity_id"])
        try:
            await coordinator.api.async_ptz(
                camera_id,
                call.data["direction"],
                speed=call.data.get("speed"),
                duration=call.data.get("duration", 0.35),
            )
        except CameraTTSAPIError as exc:
            raise ServiceValidationError(f"PTZ failed for {camera_id}: {exc}") from exc

    async def async_intercom_source_service(call: ServiceCall) -> ServiceResponse:
        coordinator, camera_id = _resolve_camera(hass, call.data["entity_id"])
        try:
            return await coordinator.api.async_intercom_source(
                camera_id,
                host=call.data.get("docker_host"),
            )
        except CameraTTSAPIError as exc:
            raise ServiceValidationError(
                f"Cannot generate intercom source for {camera_id}: {exc}"
            ) from exc

    hass.services.async_register(
        DOMAIN,
        "ptz",
        async_ptz_service,
        schema=vol.Schema(
            {
                vol.Required("entity_id"): cv.entity_id,
                vol.Required("direction"): vol.In(PTZ_DIRECTIONS),
                vol.Optional("speed"): vol.All(vol.Coerce(float), vol.Range(min=1, max=100)),
                vol.Optional("duration", default=0.35): vol.All(
                    vol.Coerce(float), vol.Range(min=0.05, max=10.0)
                ),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        "get_intercom_source",
        async_intercom_source_service,
        schema=vol.Schema(
            {
                vol.Required("entity_id"): cv.entity_id,
                vol.Optional("docker_host"): vol.All(
                    str,
                    vol.Match(
                        r"^[A-Za-z0-9_.:-]+$",
                        msg="docker_host must be a hostname or IP address without a URL path",
                    ),
                ),
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Camera TTS from a config entry."""
    api = CameraTTSAPI(
        async_get_clientsession(hass),
        entry.data[CONF_BASE_URL],
        entry.data[CONF_API_KEY],
    )
    coordinator = CameraTTSCoordinator(hass, entry, api)

    # One short asynchronous LAN request establishes the dynamic camera list.
    # No camera SDK/RTSP/PTZ probe runs in Home Assistant during startup.
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
