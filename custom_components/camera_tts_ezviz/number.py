"""Speaker and microphone gain controls for Camera TTS."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode, RestoreNumber
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfSoundPressure
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import CameraTTSAPIError
from .const import MIC_GAIN_MAX
from .coordinator import CameraTTSCoordinator
from .entity import CameraTTSEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create gain entities as Docker cameras/capabilities appear."""
    coordinator: CameraTTSCoordinator = entry.runtime_data
    speaker_known: set[str] = set()
    mic_known: set[str] = set()

    @callback
    def add_new_entities() -> None:
        current = set(coordinator.data or {})
        entities = []
        if "runtime_gain" in coordinator.api.features:
            new_speakers = sorted(current - speaker_known)
            speaker_known.update(new_speakers)
            entities.extend(CameraTTSGainNumber(coordinator, entry, camera_id) for camera_id in new_speakers)

        mic_ids = {
            camera_id
            for camera_id, data in (coordinator.data or {}).items()
            if (data.get("capabilities") or {}).get("assist_mic") or data.get("mic_url")
        }
        new_mics = sorted(mic_ids - mic_known)
        mic_known.update(new_mics)
        entities.extend(CameraTTSMicGainNumber(coordinator, entry, camera_id) for camera_id in new_mics)
        if entities:
            async_add_entities(entities)

    add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(add_new_entities))


class CameraTTSGainNumber(CameraTTSEntity, NumberEntity):
    """Persisted output gain applied by Docker before camera playback."""

    _attr_translation_key = "speaker_gain"
    _attr_native_min_value = -20.0
    _attr_native_max_value = 12.0
    _attr_native_step = 0.5
    _attr_native_unit_of_measurement = UnitOfSoundPressure.DECIBEL
    _attr_mode = NumberMode.SLIDER
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: CameraTTSCoordinator, entry: ConfigEntry, camera_id: str) -> None:
        super().__init__(coordinator, entry, camera_id)
        self._attr_unique_id = f"{entry.entry_id}_{camera_id}_speaker_gain"

    @property
    def available(self) -> bool:
        return super().available and "runtime_gain" in self.coordinator.api.features

    @property
    def native_value(self) -> float | None:
        value = (self.camera_data or {}).get("gain_db")
        return float(value) if value is not None else None

    async def async_set_native_value(self, value: float) -> None:
        try:
            payload = await self.coordinator.api.async_set_gain(self._camera_id, float(value))
        except CameraTTSAPIError as exc:
            raise HomeAssistantError(
                f"Unable to set speaker gain for {self._camera_id}: {exc}"
            ) from exc
        self.coordinator.async_mark_gain(
            self._camera_id,
            float(payload.get("gain_db", value)),
        )


class CameraTTSMicGainNumber(CameraTTSEntity, RestoreNumber):
    """Microphone gain used by the ffmpeg Assist capture path."""

    _attr_translation_key = "mic_gain"
    _attr_native_min_value = 0.0
    _attr_native_max_value = MIC_GAIN_MAX
    _attr_native_step = 1.0
    _attr_native_unit_of_measurement = UnitOfSoundPressure.DECIBEL
    _attr_mode = NumberMode.SLIDER
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: CameraTTSCoordinator, entry: ConfigEntry, camera_id: str) -> None:
        super().__init__(coordinator, entry, camera_id)
        self._attr_unique_id = f"{entry.entry_id}_{camera_id}_mic_gain"

    @property
    def _voice_state(self):
        return self.coordinator.voice_states[self._camera_id]

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        previous = await self.async_get_last_number_data()
        if previous is not None and previous.native_value is not None:
            self._voice_state.set_mic_gain(float(previous.native_value))

    @property
    def native_value(self) -> float:
        return self._voice_state.mic_gain_db

    async def async_set_native_value(self, value: float) -> None:
        self._voice_state.set_mic_gain(float(value))
        self.async_write_ha_state()
