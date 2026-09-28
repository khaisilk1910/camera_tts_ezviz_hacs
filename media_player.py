"""Media player entities for Camera TTS EZVIZ."""
from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlparse

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEnqueue,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    async_process_play_media_url,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CameraTTSCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create one media_player entity for every configured camera."""
    runtime = hass.data[DOMAIN][entry.entry_id]
    coordinator: CameraTTSCoordinator = runtime["coordinator"]
    known: set[str] = set()

    @callback
    def add_new_entities() -> None:
        new_ids = [camera_id for camera_id in coordinator.data if camera_id not in known]
        if not new_ids:
            return
        known.update(new_ids)
        async_add_entities(
            [CameraTTSMediaPlayer(coordinator, entry, camera_id) for camera_id in new_ids]
        )

    add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(add_new_entities))


class CameraTTSMediaPlayer(CoordinatorEntity[CameraTTSCoordinator], MediaPlayerEntity):
    """Camera speaker exposed as a Home Assistant media player."""

    _attr_device_class = MediaPlayerDeviceClass.SPEAKER
    _attr_supported_features = (
        MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.BROWSE_MEDIA
    )

    def __init__(
        self,
        coordinator: CameraTTSCoordinator,
        entry: ConfigEntry,
        camera_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._camera_id = camera_id
        self._attr_name = f"Camera TTS {camera_id}"
        self._attr_unique_id = f"{entry.entry_id}_{camera_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}:{camera_id}")},
            name=f"Camera TTS {camera_id}",
            manufacturer="EZVIZ / Hikvision",
            model="HCNetSDK speaker",
        )

    @property
    def camera_data(self) -> dict[str, Any] | None:
        return self.coordinator.data.get(self._camera_id)

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self.camera_data is not None

    @property
    def state(self) -> MediaPlayerState:
        data = self.camera_data or {}
        raw = data.get("state")
        if raw == "playing":
            return MediaPlayerState.PLAYING
        if raw == "buffering":
            return MediaPlayerState.BUFFERING
        return MediaPlayerState.IDLE

    @property
    def media_title(self) -> str | None:
        data = self.camera_data or {}
        return data.get("media_title")

    @property
    def media_content_type(self) -> MediaType | str | None:
        data = self.camera_data or {}
        if data.get("current_kind") == "media":
            return MediaType.MUSIC
        if data.get("current_kind") == "tts":
            return "tts"
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.camera_data or {}
        sender = data.get("sender") or {}
        return {
            "camera_id": self._camera_id,
            "queued": data.get("queued", 0),
            "gain_db": data.get("gain_db"),
            "sdk_worker_alive": sender.get("alive"),
            "sdk_last_error": sender.get("last_error"),
        }

    async def async_browse_media(
        self,
        media_content_type: str | None = None,
        media_content_id: str | None = None,
    ):
        """Expose Home Assistant Media Sources in the media browser."""
        return await media_source.async_browse_media(
            self.hass,
            media_content_id,
        )

    async def async_play_media(
        self,
        media_type: str,
        media_id: str,
        enqueue: MediaPlayerEnqueue | None = None,
        announce: bool | None = None,
        **kwargs: Any,
    ) -> None:
        """Play TTS text or an audio/media source on the camera speaker."""
        media_type_text = str(media_type).lower()
        if media_type_text in {"tts", "text", "camera_tts_ezviz"}:
            await self.coordinator.api.async_say(self._camera_id, str(media_id))
            await self.coordinator.async_request_refresh()
            return

        original_id = str(media_id)
        resolved_type = media_type_text
        if media_source.is_media_source_id(original_id):
            play_item = await media_source.async_resolve_media(
                self.hass,
                original_id,
                self.entity_id,
            )
            media_id = async_process_play_media_url(self.hass, play_item.url)
            resolved_type = getattr(play_item, "mime_type", None) or MediaType.MUSIC

        parsed = urlparse(str(media_id))
        title = None
        extra = kwargs.get("extra")
        if isinstance(extra, dict):
            title = extra.get("title") or extra.get("name")
        if not title:
            title = PurePosixPath(parsed.path).name or "Media"

        replace = enqueue not in {MediaPlayerEnqueue.ADD, MediaPlayerEnqueue.NEXT}
        await self.coordinator.api.async_play_media(
            self._camera_id,
            str(media_id),
            title=str(title),
            content_type=str(resolved_type),
            cache_key=original_id,
            replace=replace,
        )
        await self.coordinator.async_request_refresh()

    async def async_media_stop(self) -> None:
        """Stop current playback and clear this camera's queue."""
        await self.coordinator.api.async_stop(self._camera_id)
        await self.coordinator.async_request_refresh()
