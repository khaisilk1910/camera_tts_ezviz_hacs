"""Small HTTP-contract test harness that does not need a running HA instance.

Home Assistant is a large runtime dependency. These tests load only the pure
Python aiohttp client; HA-specific platform checks run in hassfest and HA itself.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "camera_tts_ezviz"


@pytest.fixture
def api_module(monkeypatch):
    root = "camera_tts_contract_test"
    package = ModuleType(root)
    package.__path__ = [str(ROOT)]
    monkeypatch.setitem(sys.modules, root, package)

    const = ModuleType(f"{root}.const")
    values = {
        "ACTION_REQUEST_TIMEOUT": 6.0,
        "AUDIO_UPLOAD_TIMEOUT": 15.0,
        "CAMERAS_REQUEST_TIMEOUT": 4.0,
        "JOB_REQUEST_TIMEOUT": 4.0,
        "MEDIA_REQUEST_TIMEOUT": 10.0,
        "PTZ_REQUEST_TIMEOUT": 8.0,
    }
    for key, value in values.items():
        setattr(const, key, value)
    monkeypatch.setitem(sys.modules, f"{root}.const", const)

    spec = importlib.util.spec_from_file_location(f"{root}.api", ROOT / "api.py")
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module
