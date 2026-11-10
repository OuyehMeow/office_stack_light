"""Background daemon: keeps one BLE connection open and exposes a localhost HTTP API.

Why: a BLE connect takes 1-5 s. Hotkeys, scripts, Stream Deck, macOS Shortcuts etc.
should switch the light instantly, so they talk to this daemon instead.

API (127.0.0.1 only, JSON responses):
    GET  /status
    POST /state/<off|available|busy|meeting|custom>
    POST /color/<RRGGBB>          custom slot colour
    POST /brightness/<0-255|NN%>
    POST /effect/<solid|breathe|blink>
"""

from __future__ import annotations

import asyncio
import json
import logging
import signal
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import unquote

from . import protocol as p

log = logging.getLogger("stacklight.daemon")

DEFAULT_PORT = 8765


@dataclass
class Desired:
    """Host-side source of truth, re-applied after every reconnect."""
    state: Optional[p.State] = None
    color: Optional[tuple[int, int, int]] = None
    brightness: Optional[int] = None
    effect: Optional[p.Effect] = None
    extra: dict = field(default_factory=dict)


class Controller:
    def __init__(self, light):
        self.light = light
        self.desired = Desired()
        self.light.on_state = self._on_device_state
        self._lock = asyncio.Lock()

    def _on_device_state(self, s: p.State) -> None:
        # Button pressed on the device: adopt it as the new desired state.
        log.info("device reported state %s", s.name)
        self.desired.state = s

    async def _apply(self, coro_factory) -> None:
        async with self._lock:
            if self.light.connected:
                await coro_factory()

    async def set_state(self, s: p.State) -> None:
        self.desired.state = s
        await self._apply(lambda: self.light.set_state(s))

    async def set_color(self, rgb: tuple[int, int, int]) -> None:
        self.desired.color = rgb
        await self._apply(lambda: self.light.set_custom_color(rgb))

    async def set_brightness(self, v: int) -> None:
        self.desired.brightness = v
        await self._apply(lambda: self.light.set_brightness(v))

    async def set_effect(self, e: p.Effect) -> None:
        self.desired.effect = e
        await self._apply(lambda: self.light.set_effect(e))

    async def resync(self) -> None:
        """Push desired settings after (re)connect. State last so colour is right first."""
        d = self.desired
        if d.color is not None:
            await self.light.set_custom_color(d.color)
        if d.brightness is not None:
            await self.light.set_brightness(d.brightness)
        if d.effect is not None:
            await self.light.set_effect(d.effect)
        if d.state is not None:
            await self.light.set_state(d.state)

    async def status(self) -> dict:
        if not self.light.connected:
            return {"connected": False,
                    "desired_state": self.desired.state.name.lower() if self.desired.state is not None else None}
        async with self._lock:
            return await self.light.status()


async def route(ctrl: Controller, method: str, path: str) -> tuple[int, dict]:
    parts = [unquote(x) for x in path.split("?")[0].strip("/").split("/") if x]
    try:
        if method == "GET" and parts == ["status"]:
            return 200, await ctrl.status()
        if method != "POST" or len(parts) != 2:
            return 404, {"error": "not found", "usage": __doc__}
        kind, arg = parts
        if kind == "state":
            s = p.parse_state(arg)
            await ctrl.set_state(s)
            return 200, {"ok": True, "state": s.name.lower(), "applied": ctrl.light.connected}
        if kind == "color":
            rgb = p.parse_color(arg)
            await ctrl.set_color(rgb)
            return 200, {"ok": True, "custom_color": p.color_hex(rgb), "applied": ctrl.light.connected}
        if kind == "brightness":
            v = p.parse_brightness(arg)
            await ctrl.set_brightness(v)
            return 200, {"ok": True, "brightness": v, "applied": ctrl.light.connected}
        if kind == "effect":
            e = p.parse_effect(arg)
            await ctrl.set_effect(e)
            return 200, {"ok": True, "effect": e.name.lower(), "applied": ctrl.light.connected}
        return 404, {"error": "not found"}
    except ValueError as e:
        return 400, {"error": str(e)}
    except Exception as e:  # BLE write failure etc.
        log.warning("request failed: %s", e)
        return 503, {"error": f"device error: {e}"}


_REASONS = {200: "OK", 400: "Bad Request", 404: "Not Found", 503: "Service Unavailable"}


async def _serve_client(ctrl: Controller, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        line = (await asyncio.wait_for(reader.readline(), 5)).decode("latin-1").strip()
        while (await asyncio.wait_for(reader.readline(), 5)) not in (b"\r\n", b"\n", b""):
            pass  # skip headers; no request bodies are used
        method, path, *_ = line.split(" ") + ["", ""]
        code, body = await route(ctrl, method.upper(), path or "/")
        payload = json.dumps(body).encode()
        writer.write(
            f"HTTP/1.1 {code} {_REASONS.get(code, '')}\r\n"
            f"Content-Type: application/json\r\nContent-Length: {len(payload)}\r\n"
            f"Connection: close\r\n\r\n".encode() + payload
        )
        await writer.drain()
    except (asyncio.TimeoutError, ConnectionError):
        pass
    finally:
        writer.close()


async def _connection_loop(ctrl: Controller, stop: asyncio.Event) -> None:
    backoff = 2.0
    while not stop.is_set():
        if not ctrl.light.connected:
            try:
                await ctrl.light.connect()
                log.info("connected to %s", ctrl.light.address)
                await ctrl.resync()
                backoff = 2.0
            except Exception as e:
                log.info("connect failed (%s); retry in %.0fs", e, backoff)
                try:
                    await asyncio.wait_for(stop.wait(), backoff)
                except asyncio.TimeoutError:
                    pass
                backoff = min(backoff * 2, 60.0)
                continue
        try:
            await asyncio.wait_for(stop.wait(), 2.0)
        except asyncio.TimeoutError:
            pass


async def run(port: int = DEFAULT_PORT, address: Optional[str] = None,
              off_on_exit: bool = False, initial: Optional[p.State] = None) -> None:
    from .device import StackLight

    light = StackLight(address)
    ctrl = Controller(light)
    if initial is not None:
        ctrl.desired.state = initial

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except (NotImplementedError, RuntimeError):
            pass  # Windows: Ctrl+C raises KeyboardInterrupt instead

    server = await asyncio.start_server(lambda r, w: _serve_client(ctrl, r, w), "127.0.0.1", port)
    log.info("listening on http://127.0.0.1:%d", port)
    conn_task = asyncio.create_task(_connection_loop(ctrl, stop))
    try:
        async with server:
            await stop.wait()
    finally:
        conn_task.cancel()
        if off_on_exit and light.connected:
            try:
                await light.set_state(p.State.OFF)
            except Exception:
                pass
        await light.disconnect()
