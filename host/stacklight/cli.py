"""Command line interface.

    stacklight scan
    stacklight available | busy | meeting | custom | off
    stacklight color ff8800            (sets custom slot colour and switches to it)
    stacklight brightness 40%
    stacklight effect breathe
    stacklight status
    stacklight daemon [--port 8765] [--off-on-exit]

If the daemon is running, commands go through it (instant). Otherwise the CLI
connects over BLE directly (1-5 s).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import urllib.error
import urllib.request

from . import protocol as p
from .daemon import DEFAULT_PORT

STATE_CMDS = ["available", "busy", "meeting", "custom", "off"]


def _via_daemon(port: int, method: str, path: str) -> dict | None:
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = json.loads(e.read() or b"{}")
        raise SystemExit(f"error: {body.get('error', e)}")
    except (urllib.error.URLError, ConnectionError, TimeoutError):
        return None  # daemon not running


async def _direct(cmd: str, arg: str | None, address: str | None) -> dict:
    from .device import StackLight

    async with StackLight(address) as sl:
        if cmd in STATE_CMDS:
            await sl.set_state(p.parse_state(cmd))
        elif cmd == "color":
            await sl.set_custom_color(p.parse_color(arg))
            await sl.set_state(p.State.CUSTOM)
        elif cmd == "brightness":
            await sl.set_brightness(p.parse_brightness(arg))
        elif cmd == "effect":
            await sl.set_effect(p.parse_effect(arg))
        return await sl.status()


async def _scan() -> None:
    from .device import scan

    found = await scan()
    if not found:
        print("no StackLight found")
    for dev, rssi in found:
        print(f"{dev.address}  {dev.name}  RSSI {rssi} dBm")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="stacklight", description="Control the Office Stack Light over BLE.")
    ap.add_argument("--address", help="BLE address (or macOS UUID). Default: cached / auto-discover")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT, help="daemon port (default %(default)s)")
    ap.add_argument("--direct", action="store_true", help="bypass the daemon even if it is running")
    ap.add_argument("-v", "--verbose", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for s in STATE_CMDS:
        sub.add_parser(s, help=f"set state: {s}")
    sub.add_parser("color", help="set custom slot colour and switch to it").add_argument("value", help="RRGGBB or r,g,b")
    sub.add_parser("brightness", help="0-255 or NN%%").add_argument("value")
    sub.add_parser("effect", help="solid | breathe | blink").add_argument("value")
    sub.add_parser("status", help="show device status")
    sub.add_parser("scan", help="list nearby StackLights")
    d = sub.add_parser("daemon", help="run background daemon with localhost HTTP API")
    d.add_argument("--off-on-exit", action="store_true", help="turn the light off when the daemon stops")
    d.add_argument("--initial", help="state to apply on first connect, e.g. available")

    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO if a.verbose or a.cmd == "daemon" else logging.WARNING,
                        format="%(asctime)s %(levelname)s %(message)s")

    if a.cmd == "scan":
        asyncio.run(_scan())
        return
    if a.cmd == "daemon":
        from .daemon import run
        initial = p.parse_state(a.initial) if a.initial else None
        try:
            asyncio.run(run(a.port, a.address, a.off_on_exit, initial))
        except KeyboardInterrupt:
            pass
        return

    arg = getattr(a, "value", None)
    # Validate locally first so typos never touch the device.
    try:
        if a.cmd == "color":
            p.parse_color(arg)
        elif a.cmd == "brightness":
            p.parse_brightness(arg)
        elif a.cmd == "effect":
            p.parse_effect(arg)
    except ValueError as e:
        raise SystemExit(f"error: {e}")

    result = None
    if not a.direct:
        if a.cmd in STATE_CMDS:
            result = _via_daemon(a.port, "POST", f"/state/{a.cmd}")
        elif a.cmd == "color":
            result = _via_daemon(a.port, "POST", f"/color/{p.color_hex(p.parse_color(arg))}")
            if result is not None:
                result = _via_daemon(a.port, "POST", "/state/custom")
        elif a.cmd in ("brightness", "effect"):
            result = _via_daemon(a.port, "POST", f"/{a.cmd}/{arg.replace('%', '%25')}")
        elif a.cmd == "status":
            result = _via_daemon(a.port, "GET", "/status")

    if result is None:
        try:
            result = asyncio.run(_direct(a.cmd, arg, a.address))
        except Exception as e:
            raise SystemExit(f"error: {e}")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main(sys.argv[1:])
