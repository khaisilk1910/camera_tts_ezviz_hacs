"""On-demand PTZ buttons for cameras that advertise PTZ capability."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import CameraTTSAPIError
from .coordinator import CameraTTSCoordinator
from .entity import CameraTTSEntity

_BUTTONS = {
    "left": "PTZ left",
    "right": "PTZ right",
    "up": "PTZ up",
    "down": "PTZ down",
    "zoom_in": "PTZ zoom in",
    "zoom_out": "PTZ zoom out",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator: CameraTTSCoordinator = entry.runtime_data
    ptz_known: set[str] = set()
    stop_known: set[str] = set()

    @callback
    def add_new_entities() -> None:
        current = set(coordinator.data or {})
        entities: list[ButtonEntity] = []

        new_stop = sorted(current - stop_known)
        stop_known.update(new_stop)
        entities.extend(CameraTTSStopButton(coordinator, entry, camera_id) for camera_id in new_stop)

        ptz_ids = {
            camera_id
            for camera_id, data in (coordinator.data or {}).items()
            if (data.get("capabilities") or {}).get("ptz")
        }
        new_ptz = sorted(ptz_ids - ptz_known)
        ptz_known.update(new_ptz)
        entities.extend(
            CameraTTSPTZButton(coordinator, entry, camera_id, direction, name)
            for camera_id in new_ptz
            for direction, name in _BUTTONS.items()
        )
        if entities:
            async_add_entities(entities)

    add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(add_new_entities))


class CameraTTSStopButton(CameraTTSEntity, ButtonEntity):
    """Dedicated emergency stop button for one camera speaker."""

    _attr_translation_key = "stop_playback"
    _attr_icon = "mdi:stop-circle-outline"

    def __init__(self, coordinator: CameraTTSCoordinator, entry: ConfigEntry, camera_id: str) -> None:
        super().__init__(coordinator, entry, camera_id)
        self._attr_unique_id = f"{entry.entry_id}_{camera_id}_stop"

    async def async_press(self) -> None:
        try:
            await self.coordinator.api.async_stop(self._camera_id)
        except CameraTTSAPIError as exc:
            raise HomeAssistantError(
                f"Stop playback failed for {self._camera_id}: {exc}"
            ) from exc
        self.coordinator.async_mark_stopped(self._camera_id)


class CameraTTSPTZButton(CameraTTSEntity, ButtonEntity):
    def __init__(
        self,
        coordinator: CameraTTSCoordinator,
        entry: ConfigEntry,
        camera_id: str,
        direction: str,
        name: str,
    ) -> None:
        super().__init__(coordinator, entry, camera_id)
        self._direction = direction
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{camera_id}_ptz_{direction}"

    async def async_press(self) -> None:
        try:
            await self.coordinator.api.async_ptz(self._camera_id, self._direction)
        except CameraTTSAPIError as exc:
            raise HomeAssistantError(
                f"PTZ {self._direction} failed for {self._camera_id}: {exc}"
            ) from exc
