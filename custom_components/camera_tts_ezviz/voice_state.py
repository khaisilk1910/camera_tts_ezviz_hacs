"""Runtime-only Assist microphone state shared by camera entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from homeassistant.core import callback


@dataclass
class CameraVoiceState:
    """Small in-memory state object; no network I/O is performed here."""

    mic_muted: bool = False
    mic_gain_db: float = 0.0
    wake_sound: bool = True
    _mute_listeners: list[Callable[[bool], None]] = field(default_factory=list)
    _gain_listeners: list[Callable[[float], None]] = field(default_factory=list)

    @callback
    def set_mic_muted(self, value: bool) -> None:
        value = bool(value)
        if value == self.mic_muted:
            return
        self.mic_muted = value
        for listener in list(self._mute_listeners):
            listener(value)

    @callback
    def listen_mute(self, listener: Callable[[bool], None]) -> Callable[[], None]:
        self._mute_listeners.append(listener)
        return lambda: self._mute_listeners.remove(listener)

    @callback
    def set_mic_gain(self, value: float) -> None:
        value = float(value)
        if value == self.mic_gain_db:
            return
        self.mic_gain_db = value
        for listener in list(self._gain_listeners):
            listener(value)

    @callback
    def listen_gain(self, listener: Callable[[float], None]) -> Callable[[], None]:
        self._gain_listeners.append(listener)
        return lambda: self._gain_listeners.remove(listener)
