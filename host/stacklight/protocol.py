"""BLE GATT protocol for the Office Stack Light.

Keep in sync with firmware/stacklight/stacklight.ino and docs/protocol.md.
Pure functions only, no BLE dependency, so it is unit-testable.
"""

from __future__ import annotations

from enum import IntEnum

DEVICE_NAME = "StackLight"

SERVICE_UUID = "7f3a1000-8c2e-4d5b-9e61-3a2f5c7b9d01"
STATE_UUID = "7f3a1001-8c2e-4d5b-9e61-3a2f5c7b9d01"
COLOR_UUID = "7f3a1002-8c2e-4d5b-9e61-3a2f5c7b9d01"
BRIGHTNESS_UUID = "7f3a1003-8c2e-4d5b-9e61-3a2f5c7b9d01"
EFFECT_UUID = "7f3a1004-8c2e-4d5b-9e61-3a2f5c7b9d01"
BATTERY_LEVEL_UUID = "00002a19-0000-1000-8000-00805f9b34fb"

MAX_BRIGHTNESS = 160  # firmware clamps above this


class State(IntEnum):
    OFF = 0
    AVAILABLE = 1
    BUSY = 2
    MEETING = 3
    CUSTOM = 4


class Effect(IntEnum):
    SOLID = 0
    BREATHE = 1
    BLINK = 2


STATE_ALIASES = {
    "off": State.OFF,
    "available": State.AVAILABLE,
    "free": State.AVAILABLE,
    "green": State.AVAILABLE,
    "busy": State.BUSY,
    "dnd": State.BUSY,
    "red": State.BUSY,
    "meeting": State.MEETING,
    "call": State.MEETING,
    "blue": State.MEETING,
    "custom": State.CUSTOM,
}


def parse_state(text: str) -> State:
    key = text.strip().lower()
    if key in STATE_ALIASES:
        return STATE_ALIASES[key]
    if key.isdigit() and int(key) in State._value2member_map_:
        return State(int(key))
    raise ValueError(f"unknown state {text!r}; use one of {', '.join(s.name.lower() for s in State)}")


def parse_effect(text: str) -> Effect:
    key = text.strip().upper()
    if key in Effect.__members__:
        return Effect[key]
    raise ValueError(f"unknown effect {text!r}; use one of {', '.join(e.name.lower() for e in Effect)}")


def parse_color(text: str) -> tuple[int, int, int]:
    """Accept 'ff8800', '#ff8800', or '255,136,0'."""
    t = text.strip().lstrip("#")
    if "," in t:
        parts = [int(p) for p in t.split(",")]
        if len(parts) != 3 or not all(0 <= p <= 255 for p in parts):
            raise ValueError(f"bad color {text!r}")
        return parts[0], parts[1], parts[2]
    if len(t) != 6:
        raise ValueError(f"bad color {text!r}; expected RRGGBB")
    try:
        v = int(t, 16)
    except ValueError as e:
        raise ValueError(f"bad color {text!r}") from e
    return (v >> 16) & 0xFF, (v >> 8) & 0xFF, v & 0xFF


def parse_brightness(text: str) -> int:
    """Accept '0'..'255' or a percentage like '40%' (percent of MAX_BRIGHTNESS)."""
    t = text.strip()
    if t.endswith("%"):
        pct = float(t[:-1])
        if not 0 <= pct <= 100:
            raise ValueError(f"bad brightness {text!r}")
        return round(MAX_BRIGHTNESS * pct / 100)
    v = int(t)
    if not 0 <= v <= 255:
        raise ValueError(f"bad brightness {text!r}")
    return min(v, MAX_BRIGHTNESS)


def encode_state(s: State) -> bytes:
    return bytes([int(s)])


def encode_color(rgb: tuple[int, int, int]) -> bytes:
    return bytes(rgb)


def encode_u8(v: int) -> bytes:
    if not 0 <= v <= 255:
        raise ValueError(v)
    return bytes([v])


def decode_state(data: bytes | bytearray) -> State:
    return State(data[0])


def decode_color(data: bytes | bytearray) -> tuple[int, int, int]:
    return data[0], data[1], data[2]


def color_hex(rgb: tuple[int, int, int]) -> str:
    return "%02x%02x%02x" % rgb
