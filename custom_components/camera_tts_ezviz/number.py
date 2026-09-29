"""Speaker gain control for Camera TTS EZVIZ."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfSoundPressure
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import CameraTTSAPIError
from .coordinator import CameraTTSCoordinator
from .entity import CameraTTSEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create one gain entity per camera, including cameras added later."""
    coordinator: CameraTTSCoordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def add_new_entities() -> None:
        # Do not create a permanently unavailable gain control against legacy
        # backends. If Docker is upgraded later, the next coordinator refresh
        # sees runtime_gain and creates the entities automatically.
        if "runtime_gain" not in coordinator.api.features:
            return
        current = set(coordinator.data or {})
        new_ids = sorted(current - known)
        if not new_ids:
            return
        known.update(new_ids)
        async_add_entities(
            CameraTTSGainNumber(coordinator, entry, camera_id)
            for camera_id in new_ids
        )

    add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(add_new_entities))


class CameraTTSGainNumber(CameraTTSEntity, NumberEntity):
    """Persisted output gain applied by Docker before HCNetSDK playback."""

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
        """Expose gain control only on backends that can persist it."""
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
