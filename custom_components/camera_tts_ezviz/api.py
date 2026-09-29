"""Async HTTP client for Camera TTS EZVIZ."""

from __future__ import annotations

import asyncio
import time
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
        self.backend_version: str | None = None
        self.features: frozenset[str] = frozenset()

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

        url = f"{self.base_url}{path}"
        started = time.monotonic()
        try:
            async with self._session.request(
                method,
                url,
                headers=headers,
                timeout=self._timeout(timeout_seconds),
                **kwargs,
            ) as response:
                elapsed = time.monotonic() - started
                if response.status in {401, 403}:
                    raise CameraTTSAuthError(
                        f"{method} {path}: authentication rejected (HTTP {response.status})"
                    )

                if response.status == 204:
                    return {}

                try:
                    payload = await response.json(content_type=None)
                except (aiohttp.ContentTypeError, ValueError):
                    payload = {"error": (await response.text())[:512]}

                if response.status >= 400:
                    message = payload.get("error") if isinstance(payload, dict) else None
                    raise CameraTTSAPIError(
                        f"{method} {path}: backend HTTP {response.status} after "
                        f"{elapsed:.2f}s: {message or 'request failed'}"
                    )

                if not isinstance(payload, dict):
                    raise CameraTTSAPIError(
                        f"{method} {path}: invalid non-object JSON response"
                    )
                return payload

        except (CameraTTSAuthError, CameraTTSAPIError):
            raise
        except aiohttp.ServerTimeoutError as exc:
            elapsed = time.monotonic() - started
            raise CameraTTSAPIError(
                f"{method} {path}: backend connected but did not return data within "
                f"{timeout_seconds:.1f}s (elapsed={elapsed:.2f}s)"
            ) from exc
        except aiohttp.ClientConnectorError as exc:
            raise CameraTTSAPIError(
                f"{method} {path}: cannot connect to backend {self.base_url}: {exc.os_error or exc}"
            ) from exc
        except asyncio.TimeoutError as exc:
            elapsed = time.monotonic() - started
            raise CameraTTSAPIError(
                f"{method} {path}: request timed out after {elapsed:.2f}s "
                f"(limit={timeout_seconds:.1f}s)"
            ) from exc
        except aiohttp.ClientError as exc:
            raise CameraTTSAPIError(
                f"{method} {path}: HTTP client error: {exc.__class__.__name__}: {exc}"
            ) from exc

    async def async_cameras(self) -> list[dict[str, Any]]:
        """Return configured cameras and lightweight playback state."""
        data = await self._request(
            "GET",
            "/cameras",
            timeout_seconds=CAMERAS_REQUEST_TIMEOUT,
        )
        version = data.get("version")
        self.backend_version = str(version) if version not in (None, "") else None
        features = data.get("features", [])
        self.features = frozenset(str(item) for item in features) if isinstance(features, list) else frozenset()
        cameras = data.get("cameras", [])
        if not isinstance(cameras, list):
            raise CameraTTSAPIError("Invalid cameras response")
        return [item for item in cameras if isinstance(item, dict) and item.get("id")]

    async def async_say(
        self,
        camera_id: str,
        text: str,
        *,
        queue_mode: str = "add",
    ) -> dict[str, Any]:
        """Queue a TTS message."""
        return await self._request(
            "POST",
            f"/say/{camera_id}",
            json={"text": text, "queue_mode": queue_mode},
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
        queue_mode: str = "replace",
    ) -> dict[str, Any]:
        """Queue a media URL for playback."""
        body: dict[str, Any] = {"url": url, "queue_mode": queue_mode}
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

    async def async_set_gain(self, camera_id: str, gain_db: float) -> dict[str, Any]:
        """Set and persist the runtime speaker gain for one camera."""
        return await self._request(
            "PATCH",
            f"/cameras/{camera_id}/settings",
            json={"gain_db": gain_db},
            timeout_seconds=ACTION_REQUEST_TIMEOUT,
        )

    async def async_stop(self, camera_id: str) -> dict[str, Any]:
        """Stop playback and clear the camera queue."""
        return await self._request(
            "POST",
            f"/stop/{camera_id}",
            json={},
            timeout_seconds=ACTION_REQUEST_TIMEOUT,
        )
