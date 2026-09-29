"""Assist microphone switches for Camera TTS."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

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
                    CameraTTSMuteSwitch(coordinator, entry, camera_id),
                    CameraTTSWakeSoundSwitch(coordinator, entry, camera_id),
                )
            )
        async_add_entities(entities)

    add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(add_new_entities))


class _VoiceSwitch(CameraTTSEntity, SwitchEntity, RestoreEntity):
    @property
    def _voice_state(self):
        return self.coordinator.voice_states[self._camera_id]


class CameraTTSMuteSwitch(_VoiceSwitch):
    _attr_translation_key = "mute_mic"

    def __init__(self, coordinator: CameraTTSCoordinator, entry: ConfigEntry, camera_id: str) -> None:
        super().__init__(coordinator, entry, camera_id)
        self._attr_unique_id = f"{entry.entry_id}_{camera_id}_mute_mic"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        previous = await self.async_get_last_state()
        self._voice_state.set_mic_muted(previous is not None and previous.state == STATE_ON)

    @property
    def is_on(self) -> bool:
        return self._voice_state.mic_muted

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._voice_state.set_mic_muted(True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._voice_state.set_mic_muted(False)
        self.async_write_ha_state()


class CameraTTSWakeSoundSwitch(_VoiceSwitch):
    _attr_translation_key = "wake_sound"

    def __init__(self, coordinator: CameraTTSCoordinator, entry: ConfigEntry, camera_id: str) -> None:
        super().__init__(coordinator, entry, camera_id)
        self._attr_unique_id = f"{entry.entry_id}_{camera_id}_wake_sound"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        previous = await self.async_get_last_state()
        self._voice_state.wake_sound = previous is None or previous.state != "off"

    @property
    def is_on(self) -> bool:
        return self._voice_state.wake_sound

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._voice_state.wake_sound = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._voice_state.wake_sound = False
        self.async_write_ha_state()
