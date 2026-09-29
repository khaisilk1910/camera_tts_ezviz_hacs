"""Shared entity helpers for Camera TTS multi-vendor cameras."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CameraTTSCoordinator

_VENDOR_INFO = {
    "ezviz": ("EZVIZ / Hikvision", "Local camera audio (HCNetSDK)"),
    "imou": ("Imou", "Local camera audio (Imou/Dahua talk)"),
    "dahua": ("Dahua", "Local camera audio (Dahua talk)"),
}


class CameraTTSEntity(CoordinatorEntity[CameraTTSCoordinator]):
    """Base entity linked to one Docker camera and one HA device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: CameraTTSCoordinator, entry: ConfigEntry, camera_id: str) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._camera_id = camera_id
        data = (coordinator.data or {}).get(camera_id) or {}
        vendor = str(data.get("vendor") or "ezviz").lower()
        manufacturer, model = _VENDOR_INFO.get(vendor, (vendor.upper(), "Local camera audio"))
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}:{camera_id}")},
            name=f"Camera {camera_id}",
            manufacturer=manufacturer,
            model=model,
        )

    @property
    def camera_data(self) -> dict[str, Any] | None:
        """Return coordinator data without doing I/O in an entity property."""
        return (self.coordinator.data or {}).get(self._camera_id)

    @property
    def available(self) -> bool:
        """Return backend/camera availability."""
        return self.coordinator.last_update_success and self.camera_data is not None
