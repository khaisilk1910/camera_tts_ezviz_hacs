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
    known: set[str] = set()

    @callback
    def add_new_entities() -> None:
        ids = {
            camera_id
            for camera_id, data in (coordinator.data or {}).items()
            if (data.get("capabilities") or {}).get("ptz")
        }
        new_ids = sorted(ids - known)
        if not new_ids:
            return
        known.update(new_ids)
        async_add_entities(
            CameraTTSPTZButton(coordinator, entry, camera_id, direction, name)
            for camera_id in new_ids
            for direction, name in _BUTTONS.items()
        )

    add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(add_new_entities))


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
