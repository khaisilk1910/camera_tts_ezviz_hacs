# QA — Camera TTS Multi-Vendor 2.7.0 / HA 2026.11

**Status:** Code QA completed; end-to-end verification on a running Home Assistant and real camera pending.

## Verification performed

- 14 Python integration modules compiled successfully on Python 3.13.
- 36/36 tests passed (`python -m pytest -q tests`): API contract, auth rejection, invalid data and duplicate IDs, feature snapshot consistency, timeout, HTTP path ID escaping, redaction of credentials, URL validation, startup network deferral, manifest/translation structure, and HA 2026.11 VAD selector signature.
- 5 JSON files (including `hacs.json`) parsed successfully; services YAML parsed successfully.
- `brand/icon.png`: 256x256; `brand/icon@2x.png`: 512x512.
- No blocking Docker HTTP request is made inside `async_setup_entry` on HA startup: initial refresh is scheduled with `async_at_started`.
- `OptionsFlowWithReload`, reauth, reconfigure, native service selectors and UI translations reviewed.
- Validated `hacs.json` location, `manifest.json` version `2.7.0`, integration domain, categories, issue tracker and repo structure against official Home Assistant Marketplace docs as of 2026-11-07.

## Limitations

- HA Core, hassfest and HACS/Marketplace validators were not executable inside this offline code environment. GitHub Actions workflows are included and **must run on GitHub** to validate these checks before release.
- Audio playback, FFmpeg, go2rtc, Assist pipeline, vendor SDK, physical camera transport and actual install/update in Marketplace are **not end-to-end tested**.
- Release the source on a public GitHub repository, keeping `hacs.json` and `custom_components/camera_tts_ezviz` at the root; publish a GitHub release/tag matching `2.7.0` and check the action status.

## Reference specifications

- https://www.home-assistant.io/blog/2026/11/04/release-202611
- https://www.home-assistant.io/integrations/marketplace
- https://contributors.home-assistant.io/marketplace/guides/integrations/
- https://contributors.home-assistant.io/marketplace/reference/hacs-json/
- https://github.com/home-assistant/core/blob/dev/homeassistant/components/assist_pipeline/select.py
