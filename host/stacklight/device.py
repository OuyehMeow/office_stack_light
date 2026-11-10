"""BLE client for the Office Stack Light (bleak; Windows / macOS / Linux)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Callable, Optional

from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice

from . import protocol as p

CONFIG_DIR = Path(os.environ.get("STACKLIGHT_CONFIG_DIR", Path.home() / ".config" / "stacklight"))
CONFIG_FILE = CONFIG_DIR / "config.json"


def load_config() -> dict:
    try:
        return json.loads(CONFIG_FILE.read_text())
    except (OSError, ValueError):
        return {}


def save_config(cfg: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))


def _matches(dev: BLEDevice, adv) -> bool:
    uuids = [u.lower() for u in (adv.service_uuids or [])]
    return p.SERVICE_UUID in uuids or (dev.name or adv.local_name or "").startswith(p.DEVICE_NAME)


async def scan(timeout: float = 5.0) -> list[tuple[BLEDevice, int]]:
    found = await BleakScanner.discover(timeout=timeout, return_adv=True)
    return [(d, adv.rssi) for d, adv in found.values() if _matches(d, adv)]


async def find(address: Optional[str] = None, timeout: float = 10.0) -> BLEDevice:
    address = address or os.environ.get("STACKLIGHT_ADDRESS") or load_config().get("address")
    dev = None
    if address:
        dev = await BleakScanner.find_device_by_address(address, timeout=timeout)
    if dev is None:
        dev = await BleakScanner.find_device_by_filter(_matches, timeout=timeout)
    if dev is None:
        raise RuntimeError("StackLight not found. Is it switched on and in range?")
    return dev


class StackLight:
    """Thin async wrapper. Use as `async with StackLight() as sl: await sl.set_state(...)`."""

    def __init__(self, address: Optional[str] = None,
                 on_disconnect: Optional[Callable[["StackLight"], None]] = None):
        self._address = address
        self._client: Optional[BleakClient] = None
        self._on_disconnect = on_disconnect
        self.on_state: Optional[Callable[[p.State], None]] = None

    @property
    def connected(self) -> bool:
        return self._client is not None and self._client.is_connected

    @property
    def address(self) -> Optional[str]:
        return self._client.address if self._client else self._address

    async def connect(self, timeout: float = 10.0) -> None:
        dev = await find(self._address, timeout)
        self._client = BleakClient(dev, disconnected_callback=self._handle_disconnect)
        await self._client.connect(timeout=timeout)
        cfg = load_config()
        if cfg.get("address") != dev.address:
            cfg["address"] = dev.address
            save_config(cfg)
        await self._client.start_notify(p.STATE_UUID, self._handle_state_notify)

    async def disconnect(self) -> None:
        if self._client:
            await self._client.disconnect()

    async def __aenter__(self) -> "StackLight":
        await self.connect()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.disconnect()

    def _handle_disconnect(self, _client: BleakClient) -> None:
        if self._on_disconnect:
            self._on_disconnect(self)

    def _handle_state_notify(self, _char, data: bytearray) -> None:
        if self.on_state and data:
            try:
                self.on_state(p.decode_state(data))
            except ValueError:
                pass

    def _c(self) -> BleakClient:
        if not self.connected:
            raise RuntimeError("not connected")
        return self._client  # type: ignore[return-value]

    async def set_state(self, s: p.State) -> None:
        await self._c().write_gatt_char(p.STATE_UUID, p.encode_state(s), response=True)

    async def set_custom_color(self, rgb: tuple[int, int, int]) -> None:
        await self._c().write_gatt_char(p.COLOR_UUID, p.encode_color(rgb), response=True)

    async def set_brightness(self, v: int) -> None:
        await self._c().write_gatt_char(p.BRIGHTNESS_UUID, p.encode_u8(v), response=True)

    async def set_effect(self, e: p.Effect) -> None:
        await self._c().write_gatt_char(p.EFFECT_UUID, p.encode_u8(int(e)), response=True)

    async def status(self) -> dict:
        c = self._c()
        # Sequential reads: some backends (BlueZ, WinRT) dislike concurrent GATT ops.
        state = await c.read_gatt_char(p.STATE_UUID)
        color = await c.read_gatt_char(p.COLOR_UUID)
        bright = await c.read_gatt_char(p.BRIGHTNESS_UUID)
        effect = await c.read_gatt_char(p.EFFECT_UUID)
        batt = await c.read_gatt_char(p.BATTERY_LEVEL_UUID)
        return {
            "connected": True,
            "address": c.address,
            "state": p.decode_state(state).name.lower(),
            "custom_color": p.color_hex(p.decode_color(color)),
            "brightness": bright[0],
            "effect": p.Effect(effect[0]).name.lower(),
            "battery_percent": batt[0],
        }
