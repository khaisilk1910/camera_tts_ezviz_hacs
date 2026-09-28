"""Config flow for Camera TTS EZVIZ."""
from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import urlparse

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CameraTTSAPI, CameraTTSAPIError, CameraTTSAuthError
from .const import CONF_API_KEY, CONF_BASE_URL, DEFAULT_BASE_URL, DOMAIN


def _normalize_url(value: str) -> str:
    value = value.strip().rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("invalid_url")
    return value


class CameraTTSEzvizConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                base_url = _normalize_url(user_input[CONF_BASE_URL])
                api_key = str(user_input[CONF_API_KEY]).strip()
                api = CameraTTSAPI(async_get_clientsession(self.hass), base_url, api_key)
                cameras = await api.async_cameras()
                if not cameras:
                    errors["base"] = "no_cameras"
                else:
                    await self.async_set_unique_id(base_url.lower())
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title="Camera TTS EZVIZ",
                        data={CONF_BASE_URL: base_url, CONF_API_KEY: api_key},
                    )
            except ValueError:
                errors[CONF_BASE_URL] = "invalid_url"
            except CameraTTSAuthError:
                errors[CONF_API_KEY] = "invalid_auth"
            except (CameraTTSAPIError, aiohttp.ClientError, asyncio.TimeoutError):
                errors["base"] = "cannot_connect"

        schema = vol.Schema(
            {
                vol.Required(CONF_BASE_URL, default=DEFAULT_BASE_URL): str,
                vol.Required(CONF_API_KEY): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
