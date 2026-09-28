"""HTTP client for Camera TTS EZVIZ."""
from __future__ import annotations

from typing import Any

import aiohttp


class CameraTTSAPIError(Exception):
    """Base API error."""


class CameraTTSAuthError(CameraTTSAPIError):
    """Authentication error."""


class CameraTTSAPI:
    """Small async client for the Docker API."""

    def __init__(self, session: aiohttp.ClientSession, base_url: str, api_key: str) -> None:
        self._session = session
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        headers = dict(kwargs.pop("headers", {}))
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        timeout = kwargs.pop("timeout", aiohttp.ClientTimeout(total=15))
        try:
            async with self._session.request(
                method,
                f"{self.base_url}{path}",
                headers=headers,
                timeout=timeout,
                **kwargs,
            ) as response:
                if response.status == 401:
                    raise CameraTTSAuthError("Invalid API key")
                try:
                    payload = await response.json(content_type=None)
                except Exception:
                    payload = {"error": await response.text()}
                if response.status >= 400:
                    message = payload.get("error") if isinstance(payload, dict) else None
                    raise CameraTTSAPIError(message or f"HTTP {response.status}")
                if not isinstance(payload, dict):
                    raise CameraTTSAPIError("Unexpected API response")
                return payload
        except CameraTTSAPIError:
            raise
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise CameraTTSAPIError(str(exc)) from exc

    async def async_cameras(self) -> list[dict[str, Any]]:
        data = await self._request("GET", "/cameras")
        cameras = data.get("cameras", [])
        if not isinstance(cameras, list):
            raise CameraTTSAPIError("Invalid cameras response")
        return [item for item in cameras if isinstance(item, dict) and item.get("id")]

    async def async_say(self, camera_id: str, text: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/say/{camera_id}",
            json={"text": text},
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
        body: dict[str, Any] = {
            "url": url,
            "replace": replace,
        }
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
            timeout=aiohttp.ClientTimeout(total=20),
        )

    async def async_stop(self, camera_id: str) -> dict[str, Any]:
        return await self._request("POST", f"/stop/{camera_id}", json={})
