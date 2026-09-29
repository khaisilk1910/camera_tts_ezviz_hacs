"""Constants for Camera TTS multi-vendor integration."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "camera_tts_ezviz"
PLATFORMS = [
    Platform.ASSIST_SATELLITE,
    Platform.BUTTON,
    Platform.MEDIA_PLAYER,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SWITCH,
]

CONF_BASE_URL = "base_url"
CONF_API_KEY = "api_key"
DEFAULT_BASE_URL = "http://127.0.0.1:8124"

# Keep idle polling light. Playback actions update the entity optimistically and
# active playback is polled more frequently for responsive state changes.
ACTIVE_UPDATE_INTERVAL = timedelta(seconds=3)
IDLE_UPDATE_INTERVAL = timedelta(seconds=20)
OFFLINE_UPDATE_INTERVAL = timedelta(seconds=60)

# The Docker API is normally on the local LAN. Short timeouts prevent an
# unavailable backend from delaying config-entry setup or service actions.
CAMERAS_REQUEST_TIMEOUT = 4.0
ACTION_REQUEST_TIMEOUT = 6.0
MEDIA_REQUEST_TIMEOUT = 10.0
AUDIO_UPLOAD_TIMEOUT = 15.0
JOB_REQUEST_TIMEOUT = 4.0

MIC_RATE = 16000
MIC_CHUNK = 2048
MIC_GAIN_MAX = 30.0
PTZ_DIRECTIONS = (
    "left",
    "right",
    "up",
    "down",
    "up_left",
    "up_right",
    "down_left",
    "down_right",
    "zoom_in",
    "zoom_out",
)
