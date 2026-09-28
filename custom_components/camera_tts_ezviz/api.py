"""Async HTTP client for Camera TTS EZVIZ."""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

from .const import (
    ACTION_REQUEST_TIMEOUT,
    CAMERAS_REQUEST_TIMEOUT,
    MEDIA_REQUEST_TIMEOUT,
)


class CameraTTSAPIError(Exception):
    """Base API error."""


class CameraTTSAuthError(CameraTTSAPIError):
    """Authentication error."""


class CameraTTSAPI:
    """Small non-blocking client for the Camera TTS Docker API."""

    def __init__(self, session: aiohttp.ClientSession, base_url: str, api_key: str) -> None:
        self._session = session
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    @staticmethod
    def _timeout(total: float) -> aiohttp.ClientTimeout:
        """Return a bounded LAN-friendly timeout."""
        connect = min(2.0, total)
        return aiohttp.ClientTimeout(
            total=total,
            connect=connect,
            sock_connect=connect,
            sock_read=total,
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        timeout_seconds: float,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Perform one asynchronous API request."""
        headers = dict(kwargs.pop("headers", {}))
        if self.api_key:
            headers["X-API-Key"] = self.api_key

        try:
            async with self._session.request(
                method,
                f"{self.base_url}{path}",
                headers=headers,
                timeout=self._timeout(timeout_seconds),
                **kwargs,
            ) as response:
                if response.status in {401, 403}:
                    raise CameraTTSAuthError("Invalid API key")

                if response.status == 204:
                    return {}

                try:
                    payload = await response.json(content_type=None)
                except (aiohttp.ContentTypeError, ValueError):
                    payload = {"error": (await response.text())[:512]}

                if response.status >= 400:
                    message = payload.get("error") if isinstance(payload, dict) else None
                    raise CameraTTSAPIError(message or f"HTTP {response.status}")

                if not isinstance(payload, dict):
                    raise CameraTTSAPIError("Unexpected API response")
                return payload

        except (CameraTTSAuthError, CameraTTSAPIError):
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            raise CameraTTSAPIError(str(exc) or exc.__class__.__name__) from exc

    async def async_cameras(self) -> list[dict[str, Any]]:
        """Return configured cameras and lightweight playback state."""
        data = await self._request(
            "GET",
            "/cameras",
            timeout_seconds=CAMERAS_REQUEST_TIMEOUT,
        )
        cameras = data.get("cameras", [])
        if not isinstance(cameras, list):
            raise CameraTTSAPIError("Invalid cameras response")
        return [item for item in cameras if isinstance(item, dict) and item.get("id")]

    async def async_say(self, camera_id: str, text: str) -> dict[str, Any]:
        """Queue a TTS message."""
        return await self._request(
            "POST",
            f"/say/{camera_id}",
            json={"text": text},
            timeout_seconds=ACTION_REQUEST_TIMEOUT,
        )

    async def async_play_media(
        self,
        camera_id: str,
        url: str,
        *,
        title: str | None = None,
        content_type: str | None = None,
        cache_key: str | None = None,
        replace: bool = True,
    ) -> dict[str, Any]:
        """Queue a media URL for playback."""
        body: dict[str, Any] = {"url": url, "replace": replace}
        if title:
            body["title"] = title
        if content_type:
            body["content_type"] = content_type
        if cache_key:
            body["cache_key"] = cache_key

        return await self._request(
            "POST",
            f"/media/{camera_id}",
            json=body,
            timeout_seconds=MEDIA_REQUEST_TIMEOUT,
        )

    async def async_stop(self, camera_id: str) -> dict[str, Any]:
        """Stop playback and clear the camera queue."""
        return await self._request(
            "POST",
            f"/stop/{camera_id}",
            json={},
            timeout_seconds=ACTION_REQUEST_TIMEOUT,
        )
