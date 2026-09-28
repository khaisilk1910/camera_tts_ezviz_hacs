"""Data coordinator for Camera TTS EZVIZ."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import CameraTTSAPI, CameraTTSAPIError
from .const import DOMAIN


class CameraTTSCoordinator(DataUpdateCoordinator[dict[str, dict]]):
    """Poll camera playback state from the Docker service."""

    def __init__(self, hass: HomeAssistant, api: CameraTTSAPI) -> None:
        super().__init__(
            hass,
            logger=__import__("logging").getLogger(__name__),
            name=DOMAIN,
            update_interval=timedelta(seconds=2),
        )
        self.api = api

    async def _async_update_data(self) -> dict[str, dict]:
        try:
            cameras = await self.api.async_cameras()
        except CameraTTSAPIError as exc:
            raise UpdateFailed(str(exc)) from exc
        return {str(item["id"]): item for item in cameras}
