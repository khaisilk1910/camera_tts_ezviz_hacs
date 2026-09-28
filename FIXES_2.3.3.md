# Camera TTS EZVIZ HACS 2.3.3

- Backend timeout messages now identify HTTP method, endpoint, timeout/status and backend URL context.
- Action errors identify camera and whether the failing path is direct text TTS, media URL playback, or stop.
- `media_player.play_media` with `media_content_type: tts` and Home Assistant `tts.speak` remain supported.
- Uses Home Assistant shared aiohttp session and coordinator polling; entity properties perform no network I/O.
