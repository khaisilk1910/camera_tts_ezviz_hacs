"""Regression tests for the Docker HTTP contract and privacy-safe logging."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import aiohttp
from aiohttp import web
import pytest


@asynccontextmanager
async def backend(handler):
    app = web.Application()
    app.router.add_route("*", "/{path:.*}", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    host, port = site._server.sockets[0].getsockname()[:2]
    try:
        yield f"http://{host}:{port}"
    finally:
        await runner.cleanup()


@pytest.mark.asyncio
async def test_successful_inventory_and_feature_change(api_module):
    current = {"version": "2.6.0", "features": ["ptz"], "cameras": [{"id": "gate", "state": "idle"}]}

    async def handler(req):
        assert req.headers["X-API-Key"] == "my-test-key"
        return web.json_response(current)

    async with backend(handler) as url, aiohttp.ClientSession() as session:
        api = api_module.CameraTTSAPI(session, url, "my-test-key")
        cameras = await api.async_cameras()
        assert cameras == [{"id": "gate", "state": "idle", "capabilities": {}}]
        assert api.features == frozenset({"ptz"})
        assert api.backend_version == "2.6.0"
        current.update(version="2.7.0", features=["runtime_gain", "ptz"], cameras=[])
        assert await api.async_cameras() == []
        assert api.backend_version == "2.7.0"
        assert api.features == {"runtime_gain", "ptz"}


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [
    {},
    {"cameras": None},
    {"cameras": {}},
    {"cameras": [None]},
    {"cameras": [{}]},
    {"cameras": [{"id": " "}]},
    {"cameras": [{"id": True}]},
    {"cameras": [{"id": "x"}, {"id": "x"}]},
    {"cameras": [{"id": "x", "capabilities": ["ptz"]}]},
    {"cameras": [], "features": "ptz"},
    {"cameras": [], "features": [True]},
])
async def test_malformed_inventory_rejected_without_corrupting_features(api_module, payload):
    current = {"cameras": [], "features": ["ptz"], "version": "original"}

    async def handler(_):
        return web.json_response(current)

    async with backend(handler) as url, aiohttp.ClientSession() as session:
        api = api_module.CameraTTSAPI(session, url, "")
        await api.async_cameras()
        current.clear()
        current.update(payload)
        with pytest.raises(api_module.CameraTTSAPIError):
            await api.async_cameras()
        assert api.features == {"ptz"}
        assert api.backend_version == "original"


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 403])
async def test_auth_failure_recognized(api_module, status):
    async def handler(_):
        return web.Response(status=status, text="authentication rejected")

    async with backend(handler) as url, aiohttp.ClientSession() as session:
        api = api_module.CameraTTSAPI(session, url, "wrong")
        with pytest.raises(api_module.CameraTTSAuthError, match="authentication rejected"):
            await api.async_cameras()


@pytest.mark.asyncio
async def test_camera_id_path_segment_is_escaped(api_module):
    seen = []

    async def handler(req):
        seen.append(req.raw_path)
        return web.json_response({})

    async with backend(handler) as url, aiohttp.ClientSession() as session:
        api = api_module.CameraTTSAPI(session, url, "")
        await api.async_stop("a/b?x#@ ö")
        assert seen == ["/stop/a%2Fb%3Fx%23@%20%C3%B6"]


@pytest.mark.asyncio
async def test_invalid_payload_does_not_become_success(api_module):
    async def handler(_):
        return web.json_response(["not", "a", "dict"])

    async with backend(handler) as url, aiohttp.ClientSession() as session:
        api = api_module.CameraTTSAPI(session, url, "")
        with pytest.raises(api_module.CameraTTSAPIError, match="non-object"):
            await api.async_cameras()


@pytest.mark.asyncio
async def test_backend_error_sanitizes_credentials(api_module):
    async def handler(_):
        return web.json_response({"error": "password=abc123 secret:topsecret rtsp://admin:pass@local/cam"}, status=500)

    async with backend(handler) as url, aiohttp.ClientSession() as session:
        api = api_module.CameraTTSAPI(session, url, "")
        with pytest.raises(api_module.CameraTTSAPIError) as err:
            await api.async_cameras()
        message = str(err.value)
        assert "abc123" not in message
        assert "topsecret" not in message
        assert "admin:pass" not in message
        assert "HTTP 500" in message


@pytest.mark.asyncio
async def test_backend_200_but_missing_cameras_is_error(api_module):
    async def handler(_):
        return web.json_response({"ok": True})

    async with backend(handler) as url, aiohttp.ClientSession() as session:
        api = api_module.CameraTTSAPI(session, url, "")
        with pytest.raises(api_module.CameraTTSAPIError, match="cameras"):
            await api.async_cameras()


@pytest.mark.asyncio
async def test_timeout_is_bounded(api_module):
    async def handler(_):
        await asyncio.sleep(0.3)
        return web.json_response({"cameras": []})

    async with backend(handler) as url, aiohttp.ClientSession() as session:
        api = api_module.CameraTTSAPI(session, url, "")
        with pytest.raises(api_module.CameraTTSAPIError, match="timed out|did not return"):
            await api._request("GET", "/cameras", timeout_seconds=0.05)


def test_safe_error_redaction(api_module):
    safe = api_module._safe_error("\n token=abcdef password:1234 http://admin:pwd@camera/path\n")
    assert "abcdef" not in safe
    assert "1234" not in safe
    assert "admin:pwd" not in safe
    assert "\n" not in safe
