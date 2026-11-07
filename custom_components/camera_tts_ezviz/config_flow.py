"""Config flow for Camera TTS Multi-Vendor."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.core import callback

from .api import CameraTTSAPI, CameraTTSAPIError, CameraTTSAuthError
from .const import (
    CONF_API_KEY,
    CONF_ASSIST_AUTO_LISTEN,
    CONF_BASE_URL,
    CONF_POLL_INTERVAL,
    DEFAULT_ASSIST_AUTO_LISTEN,
    DEFAULT_BASE_URL,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
)


def _normalize_url(value: str) -> str:
    """Reject credentials, query strings, fragments, and invalid API URLs."""
    value = value.strip().rstrip("/")
    if any(ch in value for ch in ("\n", "\r", "\t", "\\")):
        raise ValueError("invalid_url")
    try:
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or any(char.isspace() for char in parsed.hostname)
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or parsed.port == 0
            or ".." in parsed.path.split("/")
        ):
            raise ValueError("invalid_url")
    except ValueError as exc:
        raise ValueError("invalid_url") from exc
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, "", ""))


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

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> CameraTTSOptionsFlow:
        """Return the standard options dialog from the integration card."""
        return CameraTTSOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Configure a new Docker API connection."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                base_url = _normalize_url(user_input[CONF_BASE_URL])
                api_key = str(user_input.get(CONF_API_KEY, "")).strip()
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
                    vol.Optional(CONF_API_KEY, default=""): str,
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



class CameraTTSOptionsFlow(config_entries.OptionsFlowWithReload):
    """User-configurable polling and Assist startup behavior."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Show safe, bounded options in the native Home Assistant UI."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        options = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_POLL_INTERVAL,
                        default=options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
                    ): vol.All(vol.Coerce(int), vol.Range(min=10, max=120)),
                    vol.Required(
                        CONF_ASSIST_AUTO_LISTEN,
                        default=options.get(CONF_ASSIST_AUTO_LISTEN, DEFAULT_ASSIST_AUTO_LISTEN),
                    ): bool,
                }
            ),
        )
