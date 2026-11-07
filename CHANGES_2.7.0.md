# Camera TTS v2.7.0 — Home Assistant Marketplace / 2026.11

## Compatibility

- Updated `manifest.json` to 2.7.0, declared valid HA integration categories, preserved original domain and all existing entity unique IDs.
- Added Marketplace metadata and native options form (interval 10–120 seconds, Assist auto-listen).
- Updated Vietnamese/English translations for flow, entities, and services, including 6 PTZ controls and pipeline selectors.
- Corrected Home Assistant 2026.11 `VadSensitivitySelect` API: `__init__(self, hass, unique_id_prefix)` (removed obsolete domain argument).
- Options inherit `OptionsFlowWithReload`; do **not** separately register a reload listener, which can cause duplicate reloads.
- Maintained config-entry reauthentication, reconfiguration, device registry and native actions.

## Startup, API, log and data correctness

- Zero Docker/RTSP requests during `async_setup_entry`; initial HTTP poll scheduled after Home Assistant has fully started, or in the background after adding the integration during runtime.
- Shares Home Assistant aiohttp session; valid 4s poll deadline; polls idle 20s (user-adjustable), active playback 3s, offline 60s.
- Ensures invalid camera inventory does not turn into `[]`. Reject missing/malformed list, bad IDs, duplicates, invalid capabilities/features; backend feature changes trigger entity creation.
- Improved HTTP exceptions with method/path/status/timing and secret redaction; auth failures initiate native reauth; backend error recovery handled by coordinator.
- Protected diagnostics with strict allowlist: no raw RTSP/mic URL, token, arbitrary vendor data or raw sender error.
- Guarded NaN/nonfinite volume/gain and invalid queued payloads; encoded camera path segments.
- Mute mic halts the stream; disabled auto-listening prevents FFmpeg/RTSP launch, removes Start conversation capability while retaining Announce.
- Reduced brand icon PNG to 256px, added 512px high-DPI icon to reduce repository size.

## QA

- 36 isolated pytest cases with local aiohttp mock backend, plus static Home Assistant API/translation and deferred-start checks.
- Python 3.13 `compileall`, JSON translations parse and match, and CI workflow for HACS action, hassfest and pytest.
- End-to-end Home Assistant, Docker and physical camera validation **not possible in this build environment**; should be exercised on the actual target installation.
