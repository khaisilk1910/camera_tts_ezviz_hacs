"""Shared entity helpers for Camera TTS EZVIZ."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CameraTTSCoordinator


class CameraTTSEntity(CoordinatorEntity[CameraTTSCoordinator]):
    """Base entity linked to one Docker camera and one HA device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: CameraTTSCoordinator, entry: ConfigEntry, camera_id: str) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._camera_id = camera_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}:{camera_id}")},
            name=f"Camera TTS {camera_id}",
            manufacturer="EZVIZ / Hikvision",
            model="HCNetSDK speaker",
        )

    @property
    def camera_data(self):
        """Return coordinator data without doing I/O in an entity property."""
        return (self.coordinator.data or {}).get(self._camera_id)

    @property
    def available(self) -> bool:
        """Return backend/camera availability."""
        return self.coordinator.last_update_success and self.camera_data is not None
