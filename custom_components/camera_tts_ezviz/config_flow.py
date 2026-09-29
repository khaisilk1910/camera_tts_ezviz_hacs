"""Config flow for Camera TTS Multi-Vendor."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CameraTTSAPI, CameraTTSAPIError, CameraTTSAuthError
from .const import CONF_API_KEY, CONF_BASE_URL, DEFAULT_BASE_URL, DOMAIN


def _normalize_url(value: str) -> str:
    """Validate and normalize a Docker API URL."""
    value = value.strip().rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("invalid_url")
    return value


async def _async_validate_connection(
    hass,
    base_url: str,
    api_key: str,
) -> None:
    """Validate authentication and API reachability."""
    api = CameraTTSAPI(async_get_clientsession(hass), base_url, api_key)
    # An empty camera list is valid. Cameras may be added later in Docker and
    # the integration will create entities dynamically.
    await api.async_cameras()


class CameraTTSEzvizConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle Camera TTS Multi-Vendor config and reauthentication flows."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Configure a new Docker API connection."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                base_url = _normalize_url(user_input[CONF_BASE_URL])
                api_key = str(user_input[CONF_API_KEY]).strip()
                await _async_validate_connection(self.hass, base_url, api_key)
            except ValueError:
                errors[CONF_BASE_URL] = "invalid_url"
            except CameraTTSAuthError:
                errors[CONF_API_KEY] = "invalid_auth"
            except CameraTTSAPIError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(base_url.lower())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Camera TTS Multi-Vendor",
                    data={CONF_BASE_URL: base_url, CONF_API_KEY: api_key},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_BASE_URL, default=DEFAULT_BASE_URL): str,
                    vol.Required(CONF_API_KEY): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]):
        """Start reauthentication when Docker rejects the API key."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ):
        """Validate and replace the API key."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        base_url = entry.data[CONF_BASE_URL]

        if user_input is not None:
            api_key = str(user_input[CONF_API_KEY]).strip()
            try:
                await _async_validate_connection(self.hass, base_url, api_key)
            except CameraTTSAuthError:
                errors[CONF_API_KEY] = "invalid_auth"
            except CameraTTSAPIError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(str(entry.unique_id or base_url.lower()))
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={CONF_API_KEY: api_key},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ):
        """Change Docker URL/API key without deleting entities or the config entry."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            try:
                base_url = _normalize_url(user_input[CONF_BASE_URL])
                api_key = str(user_input.get(CONF_API_KEY) or entry.data[CONF_API_KEY]).strip()
                await _async_validate_connection(self.hass, base_url, api_key)
            except ValueError:
                errors[CONF_BASE_URL] = "invalid_url"
            except CameraTTSAuthError:
                errors[CONF_API_KEY] = "invalid_auth"
            except CameraTTSAPIError:
                errors["base"] = "cannot_connect"
            else:
                unique_id = base_url.lower()
                if unique_id != entry.unique_id:
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()
                return self.async_update_reload_and_abort(
                    entry,
                    unique_id=unique_id,
                    data_updates={CONF_BASE_URL: base_url, CONF_API_KEY: api_key},
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_BASE_URL, default=entry.data[CONF_BASE_URL]): str,
                    vol.Optional(CONF_API_KEY, default=""): str,
                }
            ),
            errors=errors,
        )

