"""In-memory stand-in for the BLE device, same interface as device.StackLight.

Used by `stacklight ui --mock` / `stacklight daemon --mock` to develop and test
the host software and UI without hardware.
"""

from __future__ import annotations

import asyncio
import time
from typing import Callable, Optional

from . import protocol as p


class MockLight:
    def __init__(self, connect_delay: float = 0.3, battery_start: float = 87.0):
        self._connected = False
        self._delay = connect_delay
        self._t0 = time.monotonic()
        self._batt0 = battery_start
        self.address = "MOCK-00:00:00:00:00:00"
        self.on_state: Optional[Callable[[p.State], None]] = None
        self.state = p.State.AVAILABLE
        self.color = (255, 120, 0)
        self.brightness = 48
        self.effect = p.Effect.SOLID
        self.log: list[tuple[str, object]] = []

    @property
    def connected(self) -> bool:
        return self._connected

    async def connect(self, timeout: float = 10.0) -> None:
        await asyncio.sleep(self._delay)
        self._connected = True

    async def disconnect(self) -> None:
        self._connected = False

    def press_button(self) -> None:
        """Simulate a short press on the device button (cycles states)."""
        order = [p.State.AVAILABLE, p.State.BUSY, p.State.MEETING, p.State.CUSTOM]
        self.state = order[(order.index(self.state) + 1) % len(order)] if self.state in order else p.State.AVAILABLE
        if self.on_state:
            self.on_state(self.state)

    def _check(self) -> None:
        if not self._connected:
            raise RuntimeError("not connected")

    async def set_state(self, s: p.State) -> None:
        self._check()
        self.state = s
        self.log.append(("state", s))

    async def set_custom_color(self, rgb: tuple[int, int, int]) -> None:
        self._check()
        self.color = rgb
        self.log.append(("color", rgb))

    async def set_brightness(self, v: int) -> None:
        self._check()
        self.brightness = min(v, p.MAX_BRIGHTNESS)
        self.log.append(("brightness", v))

    async def set_effect(self, e: p.Effect) -> None:
        self._check()
        self.effect = e
        self.log.append(("effect", e))

    def battery_percent(self) -> int:
        # Drain ~1 % per 20 min so the UI shows something moving over a long session.
        hours = (time.monotonic() - self._t0) / 3600
        return max(0, round(self._batt0 - hours * 3))

    async def status(self) -> dict:
        self._check()
        return {
            "connected": True,
            "mock": True,
            "address": self.address,
            "state": self.state.name.lower(),
            "custom_color": p.color_hex(self.color),
            "brightness": self.brightness,
            "effect": self.effect.name.lower(),
            "battery_percent": self.battery_percent(),
        }
