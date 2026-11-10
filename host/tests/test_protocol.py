import pytest

from stacklight import protocol as p


def test_state_aliases():
    assert p.parse_state("Busy") is p.State.BUSY
    assert p.parse_state("meeting") is p.State.MEETING
    assert p.parse_state("2") is p.State.BUSY
    with pytest.raises(ValueError):
        p.parse_state("lunch")
    with pytest.raises(ValueError):
        p.parse_state("9")


def test_color_formats():
    assert p.parse_color("ff8800") == (255, 136, 0)
    assert p.parse_color("#00FF00") == (0, 255, 0)
    assert p.parse_color("1,2,3") == (1, 2, 3)
    for bad in ("fff", "zzzzzz", "1,2", "256,0,0"):
        with pytest.raises(ValueError):
            p.parse_color(bad)


def test_brightness():
    assert p.parse_brightness("40") == 40
    assert p.parse_brightness("255") == p.MAX_BRIGHTNESS
    assert p.parse_brightness("100%") == p.MAX_BRIGHTNESS
    assert p.parse_brightness("50%") == 80
    with pytest.raises(ValueError):
        p.parse_brightness("-1")


def test_encoding_roundtrip():
    assert p.encode_state(p.State.MEETING) == b"\x03"
    assert p.decode_state(b"\x03") is p.State.MEETING
    assert p.decode_color(p.encode_color((1, 2, 3))) == (1, 2, 3)
    assert p.color_hex((255, 136, 0)) == "ff8800"


def test_uuids_match_firmware():
    """Byte arrays in the .ino are little-endian; check they decode to protocol.py UUIDs."""
    import pathlib
    import re
    import uuid

    ino = (pathlib.Path(__file__).parents[2] / "firmware" / "stacklight" / "stacklight.ino").read_text()
    m = re.search(r"#define UUID_BYTES\(lo\) \{(.*?)\}", ino, re.S)
    raw = [t.strip() for t in m.group(1).replace("\\", "").split(",")]
    for lo, expected in [(0, p.SERVICE_UUID), (1, p.STATE_UUID), (2, p.COLOR_UUID),
                         (3, p.BRIGHTNESS_UUID), (4, p.EFFECT_UUID)]:
        b = bytes(lo if t == "(lo)" else int(t, 16) for t in raw)
        assert str(uuid.UUID(bytes=b[::-1])) == expected
