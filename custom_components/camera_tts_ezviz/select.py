"""Assist pipeline and VAD selectors for camera satellites."""

from __future__ import annotations

from homeassistant.components.assist_pipeline import AssistPipelineSelect, VadSensitivitySelect
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import CameraTTSCoordinator
from .entity import CameraTTSEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator: CameraTTSCoordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def add_new_entities() -> None:
        mic_ids = {
            camera_id
            for camera_id, data in (coordinator.data or {}).items()
            if (data.get("capabilities") or {}).get("assist_mic") or data.get("mic_url")
        }
        new_ids = sorted(mic_ids - known)
        if not new_ids:
            return
        known.update(new_ids)
        entities = []
        for camera_id in new_ids:
            entities.extend(
                (
                    CameraTTSPipelineSelect(hass, coordinator, entry, camera_id),
                    CameraTTSVadSelect(hass, coordinator, entry, camera_id),
                )
            )
        async_add_entities(entities)

    add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(add_new_entities))


def selector_scope(entry: ConfigEntry, camera_id: str) -> str:
    return f"{entry.entry_id}_{camera_id}"


class CameraTTSPipelineSelect(CameraTTSEntity, AssistPipelineSelect):
    def __init__(self, hass: HomeAssistant, coordinator: CameraTTSCoordinator, entry: ConfigEntry, camera_id: str) -> None:
        CameraTTSEntity.__init__(self, coordinator, entry, camera_id)
        AssistPipelineSelect.__init__(self, hass, DOMAIN, selector_scope(entry, camera_id))


class CameraTTSVadSelect(CameraTTSEntity, VadSensitivitySelect):
    def __init__(self, hass: HomeAssistant, coordinator: CameraTTSCoordinator, entry: ConfigEntry, camera_id: str) -> None:
        CameraTTSEntity.__init__(self, coordinator, entry, camera_id)
        VadSensitivitySelect.__init__(self, hass, selector_scope(entry, camera_id))
