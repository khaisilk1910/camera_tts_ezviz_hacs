"""Static regression checks for HA compatibility and deferred initialization."""
from __future__ import annotations

import ast
import json
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "custom_components" / "camera_tts_ezviz"


def _url_normalizer():
    tree = ast.parse((SOURCE / "config_flow.py").read_text())
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_normalize_url")
    namespace = {"urlsplit": urlsplit, "urlunsplit": urlunsplit}
    exec(compile(ast.Module(body=[function], type_ignores=[]), "config_flow.py", "exec"), namespace)
    return namespace["_normalize_url"]


@pytest.mark.parametrize("value", [
    "ftp://camera.local", "localhost:8124", "http://", "http://name:password@camera:8124",
    "https://cam:8124/path?q=secret", "http://cam:8124/path#fragment",
    "http://cam:8124/a/../b", "http://bad host:8124", "http://cam:0",
    "http://cam:99999", "http://cam:8124\\evil", "http://cam:8124\nHeader:broken",
])
def test_url_rejects_bad_inputs(value):
    with pytest.raises(ValueError, match="invalid_url"):
        _url_normalizer()(value)


def test_url_accepts_lan_names_and_ipv6():
    f = _url_normalizer()
    assert f(" HTTP://camera.local:8124/ ") == "http://camera.local:8124"
    assert f("http://[::1]:8124/") == "http://[::1]:8124"
    assert f("https://my-server:9443/api/v1/") == "https://my-server:9443/api/v1"


def test_ha_platform_init_does_not_poll_network():
    tree = ast.parse((SOURCE / "__init__.py").read_text())
    setup = next(item for item in tree.body if isinstance(item, ast.AsyncFunctionDef) and item.name == "async_setup_entry")
    # Initial refresh must be nested inside @callback registered with
    # async_at_started: the setup coroutine itself never awaits backend I/O.
    awaited = [ast.unparse(n.value) for n in ast.walk(setup) if isinstance(n, ast.Await)]
    assert all("async_refresh" not in text and "async_cameras" not in text for text in awaited)
    assert "async_at_started" in ast.unparse(setup)


def test_vad_select_2026_11_two_argument_constructor():
    tree = ast.parse((SOURCE / "select.py").read_text())
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and ast.unparse(n.func).endswith("VadSensitivitySelect.__init__")]
    assert len(calls) == 1
    # HA Core 2026.11: __init__(self, hass, unique_id_prefix)
    assert len(calls[0].args) == 3


def test_json_and_manifest_consistent():
    manifest = json.loads((SOURCE / "manifest.json").read_text())
    hacs = json.loads((SOURCE.parents[1] / "hacs.json").read_text())
    assert manifest["domain"] == "camera_tts_ezviz"
    assert manifest["version"] == "2.7.0"
    assert manifest["config_flow"] is True
    assert manifest["issue_tracker"].startswith("https://")
    assert hacs["homeassistant"] == "2026.11.0"
    for lang in ("strings", "translations/en", "translations/vi"):
        resource = json.loads((SOURCE / f"{lang}.json").read_text())
        assert "config" in resource and "options" in resource
        assert "entity" in resource and "button" in resource["entity"]
