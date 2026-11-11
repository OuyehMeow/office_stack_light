from stacklight import protocol as p
from stacklight.daemon import Controller, route


class FakeLight:
    def __init__(self, connected=True):
        self.connected = connected
        self.address = "AA:BB"
        self.on_state = None
        self.calls = []

    async def set_state(self, s):
        self.calls.append(("state", s))

    async def set_custom_color(self, rgb):
        self.calls.append(("color", rgb))

    async def set_brightness(self, v):
        self.calls.append(("brightness", v))

    async def set_effect(self, e):
        self.calls.append(("effect", e))

    async def status(self):
        return {"connected": True}


async def test_routes_apply_when_connected():
    light = FakeLight()
    c = Controller(light)
    assert (await route(c, "POST", "/state/busy"))[0] == 200
    assert (await route(c, "POST", "/color/ff8800"))[0] == 200
    assert (await route(c, "POST", "/brightness/50%25"))[0] == 200
    assert (await route(c, "POST", "/effect/breathe"))[0] == 200
    assert light.calls == [("state", p.State.BUSY), ("color", (255, 136, 0)),
                           ("brightness", 80), ("effect", p.Effect.BREATHE)]


async def test_bad_input_and_unknown_route():
    c = Controller(FakeLight())
    assert (await route(c, "POST", "/state/lunch"))[0] == 400
    assert (await route(c, "GET", "/state/busy"))[0] == 404
    assert (await route(c, "GET", "/nope"))[0] == 404


async def test_offline_then_resync():
    light = FakeLight(connected=False)
    c = Controller(light)
    code, body = await route(c, "POST", "/state/meeting")
    assert code == 200 and body["applied"] is False
    await route(c, "POST", "/color/010203")
    assert light.calls == []
    st = (await route(c, "GET", "/status"))[1]
    assert st["connected"] is False and st["desired_state"] == "meeting" and st["source"] == "manual"
    light.connected = True
    await c.resync()
    assert light.calls == [("color", (1, 2, 3)), ("state", p.State.MEETING)]


async def test_device_button_updates_desired():
    light = FakeLight()
    c = Controller(light)
    light.on_state(p.State.AVAILABLE)
    assert c.desired.state is p.State.AVAILABLE


async def test_api_prefix_and_static_ui():
    from stacklight.daemon import _static

    c = Controller(FakeLight())
    assert (await route(c, "POST", "/api/state/meeting"))[0] == 200
    html, ctype = _static("/")
    assert ctype.startswith("text/html") and b"Stack Light" in html
    assert _static("/etc/passwd") is None
