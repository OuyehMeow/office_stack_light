"""Background daemon: keeps one BLE connection open, serves the web UI and a localhost HTTP API.

Why: a BLE connect takes 1-5 s. The UI, hotkeys, scripts, Stream Deck, macOS Shortcuts
etc. should switch the light instantly, so they talk to this daemon instead.

UI:  GET /            phone-sized control page (stacklight/ui/index.html)

API (127.0.0.1 only, JSON; the /api prefix is optional):
    GET  /api/status
    POST /api/state/<off|available|busy|meeting|custom>
    POST /api/color/<RRGGBB>          custom slot colour
    POST /api/brightness/<0-255|NN%>
    POST /api/effect/<solid|breathe|blink>   custom slot effect
    POST /api/sync/<on|off>           follow the presence provider (Teams)
"""

from __future__ import annotations

import asyncio
import json
import logging
import signal
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import unquote

from . import protocol as p
from .presence import Presence, PresenceProvider, map_teams

log = logging.getLogger("stacklight.daemon")

DEFAULT_PORT = 8765
UI_DIR = Path(__file__).parent / "ui"


@dataclass
class Desired:
    """Host-side source of truth, re-applied after every reconnect."""
    state: Optional[p.State] = None
    color: Optional[tuple[int, int, int]] = None
    brightness: Optional[int] = None
    effect: Optional[p.Effect] = None
    extra: dict = field(default_factory=dict)


class Controller:
    def __init__(self, light, provider: Optional[PresenceProvider] = None):
        self.light = light
        self.desired = Desired()
        self.light.on_state = self._on_device_state
        self._lock = asyncio.Lock()
        self.source = "manual"          # who set the current state: manual | device | <provider name>
        self.since = time.time()
        self.provider = provider
        self.sync = provider is not None
        self.presence: Optional[Presence] = None
        self.presence_error: Optional[str] = None

    def _mark(self, source: str) -> None:
        self.source = source
        self.since = time.time()

    def _on_device_state(self, s: p.State) -> None:
        # Button pressed on the device: adopt it, and stop following Teams.
        log.info("device reported state %s", s.name)
        self.desired.state = s
        self.sync = False
        self._mark("device")

    async def _apply(self, coro_factory) -> None:
        async with self._lock:
            if self.light.connected:
                await coro_factory()

    async def set_state(self, s: p.State, source: str = "manual") -> None:
        if source == "manual":
            self.sync = False  # a manual choice overrides auto-sync
        changed = s != self.desired.state
        self.desired.state = s
        if changed or source == "manual":
            self._mark(source)
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

    async def set_sync(self, on: bool) -> None:
        if on and self.provider is None:
            raise ValueError("no presence provider configured (start with --presence teams)")
        self.sync = on
        if on:
            await self.poll_presence()

    async def poll_presence(self) -> None:
        if self.provider is None:
            return
        try:
            pr = await self.provider.get()
            self.presence_error = None
        except Exception as e:
            self.presence_error = str(e)
            log.warning("presence poll failed: %s", e)
            return
        if pr is None:
            return
        self.presence = pr
        target = map_teams(pr)
        if self.sync and target is not None:
            await self.set_state(target, source=self.provider.name)

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

    def _meta(self) -> dict:
        return {
            "source": self.source,
            "since": round(self.since),
            "sync": {
                "available": self.provider is not None,
                "enabled": self.sync,
                "provider": self.provider.name if self.provider else None,
                "presence": self.presence.label() if self.presence else None,
                "error": self.presence_error,
            },
        }

    async def status(self) -> dict:
        if not self.light.connected:
            st = self.desired.state.name.lower() if self.desired.state is not None else None
            return {"connected": False, "desired_state": st, **self._meta()}
        async with self._lock:
            dev = await self.light.status()
        return {**dev, **self._meta()}


async def route(ctrl: Controller, method: str, path: str) -> tuple[int, dict]:
    parts = [unquote(x) for x in path.split("?")[0].strip("/").split("/") if x]
    if parts[:1] == ["api"]:
        parts = parts[1:]
    try:
        if method == "GET" and parts == ["status"]:
            return 200, await ctrl.status()
        if method != "POST" or len(parts) != 2:
            return 404, {"error": "not found", "usage": __doc__}
        kind, arg = parts
        applied = lambda: ctrl.light.connected  # noqa: E731
        if kind == "state":
            s = p.parse_state(arg)
            await ctrl.set_state(s)
            return 200, {"ok": True, "state": s.name.lower(), "applied": applied()}
        if kind == "color":
            rgb = p.parse_color(arg)
            await ctrl.set_color(rgb)
            return 200, {"ok": True, "custom_color": p.color_hex(rgb), "applied": applied()}
        if kind == "brightness":
            v = p.parse_brightness(arg)
            await ctrl.set_brightness(v)
            return 200, {"ok": True, "brightness": v, "applied": applied()}
        if kind == "effect":
            e = p.parse_effect(arg)
            await ctrl.set_effect(e)
            return 200, {"ok": True, "effect": e.name.lower(), "applied": applied()}
        if kind == "sync":
            if arg not in ("on", "off"):
                raise ValueError("use /sync/on or /sync/off")
            await ctrl.set_sync(arg == "on")
            return 200, {"ok": True, "sync": ctrl.sync}
        return 404, {"error": "not found"}
    except ValueError as e:
        return 400, {"error": str(e)}
    except Exception as e:  # BLE write failure etc.
        log.warning("request failed: %s", e)
        return 503, {"error": f"device error: {e}"}


_REASONS = {200: "OK", 400: "Bad Request", 404: "Not Found", 503: "Service Unavailable"}


def _static(path: str) -> Optional[tuple[bytes, str]]:
    if path.split("?")[0] in ("/", "/index.html"):
        f = UI_DIR / "index.html"
        if f.exists():
            return f.read_bytes(), "text/html; charset=utf-8"
    return None


async def _serve_client(ctrl: Controller, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        line = (await asyncio.wait_for(reader.readline(), 5)).decode("latin-1").strip()
        while (await asyncio.wait_for(reader.readline(), 5)) not in (b"\r\n", b"\n", b""):
            pass  # skip headers; no request bodies are used
        method, path, *_ = line.split(" ") + ["", ""]
        method = method.upper()
        static = _static(path) if method == "GET" else None
        if static:
            code, payload, ctype = 200, static[0], static[1]
        else:
            code, body = await route(ctrl, method, path or "/")
            payload, ctype = json.dumps(body).encode(), "application/json"
        writer.write(
            f"HTTP/1.1 {code} {_REASONS.get(code, '')}\r\n"
            f"Content-Type: {ctype}\r\nContent-Length: {len(payload)}\r\n"
            f"Cache-Control: no-store\r\nConnection: close\r\n\r\n".encode() + payload
        )
        await writer.drain()
    except (asyncio.TimeoutError, ConnectionError):
        pass
    finally:
        writer.close()


async def _sleep_or_stop(stop: asyncio.Event, seconds: float) -> None:
    try:
        await asyncio.wait_for(stop.wait(), seconds)
    except asyncio.TimeoutError:
        pass


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
                await _sleep_or_stop(stop, backoff)
                backoff = min(backoff * 2, 60.0)
                continue
        await _sleep_or_stop(stop, 2.0)


async def _presence_loop(ctrl: Controller, stop: asyncio.Event) -> None:
    while not stop.is_set():
        if ctrl.sync:
            await ctrl.poll_presence()
        await _sleep_or_stop(stop, ctrl.provider.interval)


async def run(port: int = DEFAULT_PORT, address: Optional[str] = None,
              off_on_exit: bool = False, initial: Optional[p.State] = None,
              mock: bool = False, presence: Optional[str] = None,
              on_ready=None) -> None:
    from .device import load_config
    from .presence import build_provider

    if mock:
        from .mock import MockLight
        light = MockLight()
    else:
        from .device import StackLight
        light = StackLight(address)

    ctrl = Controller(light, build_provider(presence, load_config()))
    ctrl.desired.state = initial if initial is not None else p.State.AVAILABLE

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except (NotImplementedError, RuntimeError):
            pass  # Windows: Ctrl+C raises KeyboardInterrupt instead

    server = await asyncio.start_server(lambda r, w: _serve_client(ctrl, r, w), "127.0.0.1", port)
    log.info("UI and API on http://127.0.0.1:%d%s", port, "  (mock device)" if mock else "")
    tasks = [asyncio.create_task(_connection_loop(ctrl, stop))]
    if ctrl.provider:
        tasks.append(asyncio.create_task(_presence_loop(ctrl, stop)))
    if on_ready:
        on_ready(f"http://127.0.0.1:{port}/")
    try:
        async with server:
            await stop.wait()
    finally:
        for t in tasks:
            t.cancel()
        if off_on_exit and light.connected:
            try:
                await light.set_state(p.State.OFF)
            except Exception:
                pass
        await light.disconnect()
