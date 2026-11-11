import pytest

from stacklight import protocol as p
from stacklight.daemon import Controller, route
from stacklight.mock import MockLight
from stacklight.presence import MockPresenceProvider, Presence, build_provider, map_teams


@pytest.mark.parametrize("avail,act,expected", [
    ("Available", "Available", p.State.AVAILABLE),
    ("AvailableIdle", "Available", p.State.AVAILABLE),
    ("Busy", "Busy", p.State.BUSY),
    ("Busy", "InACall", p.State.MEETING),
    ("Busy", "InAMeeting", p.State.MEETING),
    ("DoNotDisturb", "Presenting", p.State.MEETING),
    ("DoNotDisturb", "DoNotDisturb", p.State.BUSY),
    ("Away", "Away", p.State.OFF),
    ("Offline", "OffWork", p.State.OFF),
    ("PresenceUnknown", "PresenceUnknown", None),
])
def test_map_teams(avail, act, expected):
    assert map_teams(Presence(avail, act)) == expected


def test_build_provider():
    assert build_provider(None, {}) is None
    assert build_provider("mock", {}).name == "mock-teams"
    with pytest.raises(RuntimeError):
        build_provider("teams", {})
    with pytest.raises(ValueError):
        build_provider("slack", {})


async def _ctrl(script):
    light = MockLight(connect_delay=0)
    await light.connect()
    return light, Controller(light, MockPresenceProvider(script=script))


async def test_sync_drives_state_and_manual_overrides():
    light, c = await _ctrl([Presence("Busy", "InACall"), Presence("Available", "Available")])
    assert c.sync is True
    await c.poll_presence()
    assert light.state is p.State.MEETING and c.source == "mock-teams"

    await route(c, "POST", "/api/state/busy")          # manual press
    assert c.sync is False and c.source == "manual"
    await c.poll_presence()                             # presence still read, not applied
    assert light.state is p.State.BUSY
    assert (await c.status())["sync"]["presence"] == "Available"

    code, _ = await route(c, "POST", "/api/sync/on")    # re-enable: applies immediately
    assert code == 200 and c.sync is True


async def test_sync_without_provider_rejected():
    light = MockLight(connect_delay=0)
    await light.connect()
    c = Controller(light)
    assert (await route(c, "POST", "/api/sync/on"))[0] == 400
    assert (await c.status())["sync"]["available"] is False


async def test_device_button_stops_sync():
    light, c = await _ctrl(None)
    light.press_button()
    assert c.sync is False and c.source == "device"
    assert c.desired.state is p.State.BUSY


async def test_mock_status_shape():
    light, c = await _ctrl(None)
    s = await c.status()
    assert s["connected"] and s["mock"] and s["state"] == "available"
    assert 0 <= s["battery_percent"] <= 100
