"""Turn a camera microphone/speaker pair into a Home Assistant Assist satellite.

Microphone audio stays local: ffmpeg reads the configured camera/go2rtc URL and
feeds PCM16 mono 16 kHz into Home Assistant's native Assist pipeline. Replies
are uploaded to the local Docker backend, which selects the correct vendor talk
transport. The listener is started only after the entity is added, so config
entry setup never waits for a camera media stream.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import math
import struct
import time
from typing import Any

from homeassistant.components import media_source, tts
from homeassistant.components.assist_pipeline import PipelineEvent, PipelineEventType, PipelineStage
from homeassistant.components.assist_satellite import (
    AssistSatelliteAnnouncement,
    AssistSatelliteConfiguration,
    AssistSatelliteEntity,
    AssistSatelliteEntityFeature,
)
from homeassistant.components.ffmpeg import get_ffmpeg_manager
from homeassistant.components.media_player.browse_media import async_process_play_media_url
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import CameraTTSAPIError
from .const import DOMAIN, MIC_CHUNK, MIC_RATE
from .coordinator import CameraTTSCoordinator
from .entity import CameraTTSEntity
from .select import selector_scope

_LOGGER = logging.getLogger(__name__)

_TTS_COLLECT_TIMEOUT = 30.0
_ANNOUNCE_TIMEOUT = 300.0
_WAKE_SOUND_TIMEOUT = 8.0
_WAKE_ECHO_GUARD = 0.4
_MIN_PIPELINE_INTERVAL = 1.0
_MAX_ERROR_BACKOFF = 60.0
_FAST_FAILURE_SECONDS = 3.0
_SELECTOR_READY_TIMEOUT = 30.0
_MIC_STALL_TIMEOUT = 10.0


def _wake_tone(sample_rate: int = MIC_RATE) -> bytes:
    """Generate a short two-note PCM16 mono wake acknowledgement."""
    out = bytearray()
    for hz, seconds in ((1047.0, 0.12), (1568.0, 0.18)):
        count = int(sample_rate * seconds)
        fade = max(1, int(sample_rate * 0.01))
        for index in range(count):
            envelope = min(1.0, index / fade, (count - 1 - index) / fade)
            out += struct.pack(
                "<h",
                int(0.35 * 32767 * envelope * math.sin(2 * math.pi * hz * index / sample_rate)),
            )
    return bytes(out)


def _wav_pcm16_mono(pcm: bytes, sample_rate: int) -> bytes:
    """Wrap raw PCM16 mono in a small WAV header without external dependencies."""
    data_len = len(pcm)
    byte_rate = sample_rate * 2
    return (
        b"RIFF"
        + struct.pack("<I", 36 + data_len)
        + b"WAVEfmt "
        + struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, byte_rate, 2, 16)
        + b"data"
        + struct.pack("<I", data_len)
        + pcm
    )


def _mic_filter(gain_db: float) -> str:
    """Remove DC/rumble before optional mic gain and peak limiting."""
    value = "highpass=f=80"
    if gain_db > 0:
        value += f",volume={gain_db:g}dB,alimiter=limit=0.9:attack=5:release=50:level=false"
    return value


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
        async_add_entities(
            CameraTTSAssistSatellite(coordinator, entry, camera_id)
            for camera_id in new_ids
        )

    add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(add_new_entities))


class CameraTTSAssistSatellite(CameraTTSEntity, AssistSatelliteEntity):
    """Native Assist satellite backed by a camera microphone and Docker speaker."""

    _attr_name = "Assist satellite"
    _attr_supported_features = (
        AssistSatelliteEntityFeature.ANNOUNCE
        | AssistSatelliteEntityFeature.START_CONVERSATION
    )

    def __init__(self, coordinator: CameraTTSCoordinator, entry: ConfigEntry, camera_id: str) -> None:
        super().__init__(coordinator, entry, camera_id)
        self._attr_unique_id = f"{entry.entry_id}_{camera_id}_satellite"
        self._audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=64)
        self._speaking = False
        self._block_wake_tone = False
        self._tts_done = asyncio.Event()
        self._has_tts = False
        self._continue_conversation = False
        self._runner: asyncio.Task | None = None
        self._mic_proc: asyncio.subprocess.Process | None = None
        self._restart_mic = False
        self._pipeline_error: str | None = None
        self._may_listen = asyncio.Event()
        self._may_listen.set()

    @property
    def _voice_state(self):
        return self.coordinator.voice_states[self._camera_id]

    @property
    def _mic_url(self) -> str:
        return str((self.camera_data or {}).get("mic_url") or "")

    def _selector_entity(self, key: str) -> str | None:
        unique_id = f"{selector_scope(self._entry, self._camera_id)}-{key}"
        entity_id = er.async_get(self.hass).async_get_entity_id("select", DOMAIN, unique_id)
        state = self.hass.states.get(entity_id) if entity_id else None
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return None
        return entity_id

    @property
    def pipeline_entity_id(self) -> str | None:
        return self._selector_entity("pipeline")

    @property
    def vad_sensitivity_entity_id(self) -> str | None:
        return self._selector_entity("vad_sensitivity")

    @property
    def tts_options(self) -> dict[str, Any] | None:
        return {
            tts.ATTR_PREFERRED_FORMAT: "wav",
            tts.ATTR_PREFERRED_SAMPLE_RATE: MIC_RATE,
            tts.ATTR_PREFERRED_SAMPLE_CHANNELS: 1,
            tts.ATTR_PREFERRED_SAMPLE_BYTES: 2,
        }

    @callback
    def async_get_configuration(self) -> AssistSatelliteConfiguration:
        raise NotImplementedError

    async def async_set_configuration(self, config: AssistSatelliteConfiguration) -> None:
        raise NotImplementedError

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if self._mic_url:
            self._runner = self._entry.async_create_background_task(
                self.hass,
                self._run(),
                f"{self.entity_id} camera assist listener",
            )
        self.async_on_remove(self._voice_state.listen_mute(self._on_mute))
        self.async_on_remove(self._voice_state.listen_gain(self._on_gain))

    async def async_will_remove_from_hass(self) -> None:
        if self._runner is not None:
            self._runner.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._runner
        self._kill_mic()
        await super().async_will_remove_from_hass()

    @callback
    def _on_mute(self, muted: bool) -> None:
        if muted:
            self._end_current_audio_turn()

    @callback
    def _on_gain(self, _gain: float) -> None:
        if self._mic_proc is not None and self._mic_proc.returncode is None:
            self._restart_mic = True
            self._mic_proc.kill()

    @callback
    def _kill_mic(self) -> None:
        if self._mic_proc is not None and self._mic_proc.returncode is None:
            self._mic_proc.kill()

    @callback
    def _pause_mic(self) -> None:
        self._may_listen.clear()
        if self._mic_proc is not None and self._mic_proc.returncode is None:
            self._restart_mic = True
            self._mic_proc.kill()

    @callback
    def _end_current_audio_turn(self) -> None:
        while not self._audio_queue.empty():
            self._audio_queue.get_nowait()
        with contextlib.suppress(asyncio.QueueFull):
            self._audio_queue.put_nowait(None)

    async def _wait_selectors(self) -> None:
        deadline = self.hass.loop.time() + _SELECTOR_READY_TIMEOUT
        while self.hass.loop.time() < deadline and (
            self.pipeline_entity_id is None or self.vad_sensitivity_entity_id is None
        ):
            await asyncio.sleep(0.1)

    async def _run(self) -> None:
        await self._wait_selectors()
        mic_task = self._entry.async_create_background_task(
            self.hass,
            self._read_mic_loop(),
            f"{self.entity_id} microphone",
        )
        error_backoff = 0.0
        last_logged_error: str | None = None
        try:
            while True:
                if self._voice_state.mic_muted:
                    await asyncio.sleep(1.0)
                    continue

                start_stage = (
                    PipelineStage.STT if self._continue_conversation else PipelineStage.WAKE_WORD
                )
                self._continue_conversation = False
                self._has_tts = False
                self._pipeline_error = None
                self._tts_done.clear()
                started = self.hass.loop.time()
                try:
                    await self.async_accept_pipeline_from_satellite(
                        audio_stream=self._audio_stream(),
                        start_stage=start_stage,
                    )
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # one bad Assist turn must not kill the entity
                    _LOGGER.debug("%s: Assist pipeline failed", self.entity_id, exc_info=True)
                    self._pipeline_error = str(exc) or type(exc).__name__

                if self._has_tts and self._pipeline_error is None:
                    await self._tts_done.wait()
                if not self._speaking and self.state == "responding":
                    self.tts_response_finished()

                if self._continue_conversation:
                    error_backoff = 0.0
                    continue

                elapsed = self.hass.loop.time() - started
                if self._pipeline_error is not None and elapsed >= _FAST_FAILURE_SECONDS:
                    _LOGGER.debug(
                        "%s: Assist turn failed after listening (%s); listening again",
                        self.entity_id,
                        self._pipeline_error,
                    )
                    self._pipeline_error = None

                if self._pipeline_error is not None:
                    error_backoff = min(_MAX_ERROR_BACKOFF, max(5.0, error_backoff * 2))
                    if self._pipeline_error != last_logged_error:
                        last_logged_error = self._pipeline_error
                        _LOGGER.warning(
                            "%s: Assist pipeline error (%s); retrying in %.0f s",
                            self.entity_id,
                            self._pipeline_error,
                            error_backoff,
                        )
                    self._pause_mic()
                    try:
                        await asyncio.sleep(error_backoff)
                    finally:
                        self._may_listen.set()
                    continue

                error_backoff = 0.0
                last_logged_error = None
                remaining = _MIN_PIPELINE_INTERVAL - (self.hass.loop.time() - started)
                if remaining > 0:
                    await asyncio.sleep(remaining)
        finally:
            mic_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await mic_task

    async def _audio_stream(self):
        while not self._audio_queue.empty():
            self._audio_queue.get_nowait()
        while (chunk := await self._audio_queue.get()) is not None:
            yield chunk

    async def _read_mic_loop(self) -> None:
        while True:
            try:
                await self._read_mic_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                _LOGGER.exception("%s: microphone reader failed; reopening", self.entity_id)
                await asyncio.sleep(2.0)

    async def _read_mic_once(self) -> None:
        await self._may_listen.wait()
        mic_url = self._mic_url
        if not mic_url:
            await asyncio.sleep(5.0)
            return

        command = [
            get_ffmpeg_manager(self.hass).binary,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
        ]
        if mic_url.lower().startswith("rtsp://"):
            command += ["-rtsp_transport", "tcp"]
        command += [
            "-i",
            mic_url,
            "-vn",
            "-af",
            _mic_filter(self._voice_state.mic_gain_db),
            "-ac",
            "1",
            "-ar",
            str(MIC_RATE),
            "-f",
            "s16le",
            "pipe:",
        ]
        proc = self._mic_proc = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        assert proc.stdout is not None
        try:
            while True:
                try:
                    chunk = await asyncio.wait_for(
                        proc.stdout.readexactly(MIC_CHUNK),
                        _MIC_STALL_TIMEOUT,
                    )
                except TimeoutError:
                    _LOGGER.warning(
                        "%s: no microphone audio for %.0f s; reopening",
                        self.entity_id,
                        _MIC_STALL_TIMEOUT,
                    )
                    break
                if self._speaking or self._block_wake_tone or self._voice_state.mic_muted:
                    continue
                if self._audio_queue.full():
                    self._audio_queue.get_nowait()
                self._audio_queue.put_nowait(chunk)
        except asyncio.IncompleteReadError:
            if not self._restart_mic:
                _LOGGER.warning("%s: microphone stream ended; reopening", self.entity_id)
        finally:
            if proc.returncode is None:
                proc.kill()
            await proc.wait()
            if self._mic_proc is proc:
                self._mic_proc = None

        if self._restart_mic:
            self._restart_mic = False
        else:
            await asyncio.sleep(2.0)

    def on_pipeline_event(self, event: PipelineEvent) -> None:
        if event.type is PipelineEventType.WAKE_WORD_END:
            if (event.data or {}).get("wake_word_output") and self._voice_state.wake_sound:
                self._block_wake_tone = True
                self._entry.async_create_background_task(
                    self.hass,
                    self._play_wake_tone(),
                    f"{self.entity_id} wake sound",
                )
        elif event.type is PipelineEventType.INTENT_END:
            output = (event.data or {}).get("intent_output") or {}
            self._continue_conversation = bool(output.get("continue_conversation"))
        elif event.type is PipelineEventType.TTS_END:
            output = (event.data or {}).get("tts_output") or {}
            stream = tts.async_get_stream(self.hass, output["token"]) if output.get("token") else None
            if stream is None:
                self._tts_done.set()
                return
            self._has_tts = True
            self._entry.async_create_background_task(
                self.hass,
                self._play_tts(stream),
                f"{self.entity_id} TTS reply",
            )
        elif event.type is PipelineEventType.ERROR:
            data = event.data or {}
            self._pipeline_error = str(data.get("message") or data.get("code") or "error")
            self._tts_done.set()

    @staticmethod
    def _job_id(payload: dict[str, Any]) -> str:
        jobs = payload.get("jobs")
        if not isinstance(jobs, list) or not jobs or not isinstance(jobs[0], dict) or not jobs[0].get("id"):
            raise CameraTTSAPIError("Docker did not return a playback job id")
        return str(jobs[0]["id"])

    async def _play_wav(self, wav: bytes, *, title: str, timeout: float = 90.0) -> None:
        payload = await self.coordinator.api.async_upload_audio(
            self._camera_id,
            wav,
            title=title,
            queue_mode="play",
        )
        await self.coordinator.api.async_wait_job(self._job_id(payload), timeout=timeout)

    async def _play_wake_tone(self) -> None:
        try:
            wav = _wav_pcm16_mono(_wake_tone(), MIC_RATE)
            async with asyncio.timeout(_WAKE_SOUND_TIMEOUT):
                await self._play_wav(wav, title="Assist wake sound", timeout=_WAKE_SOUND_TIMEOUT)
            await asyncio.sleep(_WAKE_ECHO_GUARD)
        except (CameraTTSAPIError, OSError, TimeoutError) as exc:
            _LOGGER.debug("%s: cannot play wake sound: %s", self.entity_id, exc)
        finally:
            self._block_wake_tone = False

    async def _play_tts(self, stream: tts.ResultStream) -> None:
        self._speaking = True
        try:
            async with asyncio.timeout(_TTS_COLLECT_TIMEOUT):
                wav = b"".join([chunk async for chunk in stream.async_stream_result()])
            timeout = min(300.0, max(30.0, len(wav) / 32000.0 + 30.0))
            await self._play_wav(wav, title="Assist reply", timeout=timeout)
        except (CameraTTSAPIError, OSError, TimeoutError) as exc:
            _LOGGER.warning("%s: cannot play Assist reply: %s", self.entity_id, exc)
        finally:
            self._speaking = False
            self.tts_response_finished()
            self._tts_done.set()

    async def async_announce(self, announcement: AssistSatelliteAnnouncement) -> None:
        self._speaking = True
        try:
            if announcement.tts_token and (
                stream := tts.async_get_stream(self.hass, announcement.tts_token)
            ):
                async with asyncio.timeout(_TTS_COLLECT_TIMEOUT):
                    wav = b"".join([chunk async for chunk in stream.async_stream_result()])
                timeout = min(300.0, max(30.0, len(wav) / 32000.0 + 30.0))
                await self._play_wav(wav, title="Assist announcement", timeout=timeout)
            else:
                media_id = announcement.media_id
                if media_source.is_media_source_id(media_id):
                    resolved = await media_source.async_resolve_media(
                        self.hass, media_id, self.entity_id
                    )
                    media_id = resolved.url
                media_id = async_process_play_media_url(self.hass, media_id)
                payload = await self.coordinator.api.async_play_media(
                    self._camera_id,
                    media_id,
                    title="Assist announcement",
                    queue_mode="play",
                )
                async with asyncio.timeout(_ANNOUNCE_TIMEOUT):
                    await self.coordinator.api.async_wait_job(
                        self._job_id(payload),
                        timeout=_ANNOUNCE_TIMEOUT,
                    )
        except (CameraTTSAPIError, HomeAssistantError, OSError, TimeoutError) as exc:
            _LOGGER.warning("%s: cannot play announcement: %s", self.entity_id, exc)
        finally:
            self._speaking = False

    async def async_start_conversation(
        self,
        start_announcement: AssistSatelliteAnnouncement,
    ) -> None:
        await self.async_announce(start_announcement)
        self._continue_conversation = True
        self._end_current_audio_turn()
