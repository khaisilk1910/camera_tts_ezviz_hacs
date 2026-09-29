"""Data coordinator for Camera TTS EZVIZ."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import CameraTTSAPI, CameraTTSAPIError, CameraTTSAuthError
from .const import (
    ACTIVE_UPDATE_INTERVAL,
    DOMAIN,
    IDLE_UPDATE_INTERVAL,
    OFFLINE_UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

CameraData = dict[str, dict[str, Any]]


class CameraTTSCoordinator(DataUpdateCoordinator[CameraData]):
    """Poll lightweight camera state from the local Docker service."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: CameraTTSAPI,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=IDLE_UPDATE_INTERVAL,
            # Camera data is a normal dict and supports equality. Do not wake
            # every entity when the Docker response has not changed.
            always_update=False,
        )
        self.api = api

    @staticmethod
    def _has_active_playback(data: CameraData) -> bool:
        return any(
            camera.get("state") in {"playing", "buffering"}
            for camera in data.values()
        )

    async def _async_update_data(self) -> CameraData:
        """Fetch state without blocking Home Assistant's event loop."""
        try:
            cameras = await self.api.async_cameras()
        except CameraTTSAuthError as exc:
            raise ConfigEntryAuthFailed("Camera TTS API authentication failed") from exc
        except CameraTTSAPIError as exc:
            # Back off while Docker is unavailable so a failed backend cannot
            # generate excessive work/log noise in Home Assistant.
            self.update_interval = OFFLINE_UPDATE_INTERVAL
            raise UpdateFailed(f"Camera TTS API unavailable: {exc}") from exc

        data: CameraData = {str(item["id"]): item for item in cameras}
        self.update_interval = (
            ACTIVE_UPDATE_INTERVAL if self._has_active_playback(data) else IDLE_UPDATE_INTERVAL
        )
        return data

    @callback
    def async_mark_started(
        self,
        camera_id: str,
        *,
        kind: str,
        title: str,
    ) -> None:
        """Optimistically update one entity after Docker accepts an action."""
        if camera_id not in (self.data or {}):
            return

        data: CameraData = dict(self.data or {})
        camera = dict(data[camera_id])
        camera["state"] = "buffering"
        camera["current_kind"] = kind
        camera["media_title"] = title
        camera["queued"] = max(1, int(camera.get("queued") or 0))
        data[camera_id] = camera

        self.update_interval = ACTIVE_UPDATE_INTERVAL
        self.async_set_updated_data(data)

    @callback
    def async_mark_gain(self, camera_id: str, gain_db: float) -> None:
        """Update cached gain after Docker persists a runtime setting."""
        if camera_id not in (self.data or {}):
            return
        data: CameraData = dict(self.data or {})
        camera = dict(data[camera_id])
        camera["gain_db"] = float(gain_db)
        data[camera_id] = camera
        self.async_set_updated_data(data)

    @callback
    def async_mark_stopped(self, camera_id: str) -> None:
        """Optimistically show a stopped camera without another API round trip."""
        if camera_id not in (self.data or {}):
            return

        data: CameraData = dict(self.data or {})
        camera = dict(data[camera_id])
        camera["state"] = "idle"
        camera["current_kind"] = None
        camera["media_title"] = None
        camera["queued"] = 0
        data[camera_id] = camera

        self.update_interval = IDLE_UPDATE_INTERVAL
        self.async_set_updated_data(data)
