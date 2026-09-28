"""Media player entities for Camera TTS EZVIZ."""

from __future__ import annotations

import logging
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
)
from homeassistant.components.media_player.browse_media import async_process_play_media_url
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import CameraTTSAPIError, CameraTTSAuthError
from .coordinator import CameraTTSCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Entities do no per-entity polling; all state is shared by one coordinator.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create one media_player entity for every camera returned by Docker."""
    coordinator: CameraTTSCoordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def add_new_entities() -> None:
        current = set(coordinator.data or {})
        new_ids = sorted(current - known)
        if not new_ids:
            return
        known.update(new_ids)
        async_add_entities(
            CameraTTSMediaPlayer(coordinator, entry, camera_id)
            for camera_id in new_ids
        )

    add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(add_new_entities))


class CameraTTSMediaPlayer(CoordinatorEntity[CameraTTSCoordinator], MediaPlayerEntity):
    """Expose one camera speaker as a Home Assistant media_player."""

    _attr_device_class = MediaPlayerDeviceClass.SPEAKER
    _attr_has_entity_name = True
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
        self._entry = entry
        self._camera_id = camera_id
        # One media_player per device, so the entity itself does not need a
        # duplicated name. Existing entity IDs stay tied to the unique ID.
        self._attr_name = None
        self._attr_unique_id = f"{entry.entry_id}_{camera_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}:{camera_id}")},
            name=f"Camera TTS {camera_id}",
            manufacturer="EZVIZ / Hikvision",
            model="HCNetSDK speaker",
        )

    @property
    def camera_data(self) -> dict[str, Any] | None:
        """Return cached camera data; never perform I/O from an entity property."""
        return (self.coordinator.data or {}).get(self._camera_id)

    @property
    def available(self) -> bool:
        """Return whether Docker and this camera are available."""
        return self.coordinator.last_update_success and self.camera_data is not None

    @property
    def state(self) -> MediaPlayerState:
        """Return cached media player state."""
        raw = (self.camera_data or {}).get("state")
        if raw == "playing":
            return MediaPlayerState.PLAYING
        if raw == "buffering":
            return MediaPlayerState.BUFFERING
        return MediaPlayerState.IDLE

    @property
    def media_title(self) -> str | None:
        """Return current media title or TTS text."""
        return (self.camera_data or {}).get("media_title")

    @property
    def media_content_type(self) -> MediaType | str | None:
        """Return current content type."""
        kind = (self.camera_data or {}).get("current_kind")
        if kind == "media":
            return MediaType.MUSIC
        if kind == "tts":
            return "tts"
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose lightweight diagnostics already present in coordinator data."""
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
        """Route the media browser to Home Assistant Media Sources."""

        def audio_filter(item) -> bool:
            content_type = str(item.media_content_type or "")
            return (
                not content_type
                or content_type.startswith("audio/")
                or content_type in {"music", "playlist"}
            )

        return await media_source.async_browse_media(
            self.hass,
            media_content_id,
            content_filter=audio_filter,
        )

    def _raise_api_error(self, exc: CameraTTSAPIError, *, action: str) -> None:
        """Convert backend failures to one clear HA action error."""
        if isinstance(exc, CameraTTSAuthError):
            self._entry.async_start_reauth(self.hass)
        _LOGGER.error(
            "Camera TTS action failed: camera=%s action=%s backend=%s error=%s",
            self._camera_id,
            action,
            self.coordinator.api.base_url,
            exc,
        )
        raise HomeAssistantError(
            f"Camera TTS failed: camera={self._camera_id}, action={action}: {exc}"
        ) from exc

    async def async_play_media(
        self,
        media_type: str,
        media_id: str,
        enqueue: MediaPlayerEnqueue | None = None,
        announce: bool | None = None,
        **kwargs: Any,
    ) -> None:
        """Play TTS text or an HTTP/Home Assistant media source."""
        media_type_text = str(media_type).lower()

        if media_type_text in {"tts", "text", DOMAIN}:
            text = str(media_id)
            try:
                await self.coordinator.api.async_say(self._camera_id, text)
            except CameraTTSAPIError as exc:
                self._raise_api_error(exc, action="tts_text")
            self.coordinator.async_mark_started(
                self._camera_id,
                kind="tts",
                title=text,
            )
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
            resolved_type = str(play_item.mime_type or MediaType.MUSIC)

        media_url = str(media_id)
        parsed = urlparse(media_url)
        if parsed.scheme not in {"http", "https"}:
            raise HomeAssistantError(
                "Camera TTS EZVIZ requires an HTTP/HTTPS media URL or Home Assistant Media Source"
            )

        title = None
        extra = kwargs.get("extra")
        if isinstance(extra, dict):
            title = extra.get("title") or extra.get("name")
        if not title:
            title = PurePosixPath(parsed.path).name or "Media"

        # ADD/NEXT append. PLAY/REPLACE starts now and clears the old queue.
        replace = enqueue not in {MediaPlayerEnqueue.ADD, MediaPlayerEnqueue.NEXT}
        try:
            await self.coordinator.api.async_play_media(
                self._camera_id,
                media_url,
                title=str(title),
                content_type=str(resolved_type),
                cache_key=original_id,
                replace=replace,
            )
        except CameraTTSAPIError as exc:
            self._raise_api_error(exc, action="play_media_url")

        self.coordinator.async_mark_started(
            self._camera_id,
            kind="media",
            title=str(title),
        )

    async def async_media_stop(self) -> None:
        """Stop current playback and clear this camera's queued jobs."""
        try:
            await self.coordinator.api.async_stop(self._camera_id)
        except CameraTTSAPIError as exc:
            self._raise_api_error(exc, action="stop")
        self.coordinator.async_mark_stopped(self._camera_id)
