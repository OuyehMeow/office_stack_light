# Firmware

Target: Seeed Studio XIAO nRF52840 with the "Seeed nRF52 Boards" Arduino core (the non-mbed core; the mbed core lacks the Bluefruit library).

## Build and flash (Arduino IDE 2)

1. Preferences -> Additional boards manager URLs, add:
   `https://files.seeedstudio.com/arduino/package_seeeduino_boards_index.json`
2. Boards Manager: install "Seeed nRF52 Boards".
3. Library Manager: install "Adafruit NeoPixel".
4. Tools -> Board -> "Seeed XIAO nRF52840" (not "... mbed-enabled").
5. Open `stacklight/stacklight.ino`, Upload.
   If upload fails: double-tap the reset button to enter the bootloader (XIAO shows up as a USB drive), then upload again.

## arduino-cli

```bash
arduino-cli core install Seeeduino:nrf52 --additional-urls https://files.seeedstudio.com/arduino/package_seeeduino_boards_index.json
```

```bash
arduino-cli lib install "Adafruit NeoPixel"
```

```bash
arduino-cli compile --fqbn Seeeduino:nrf52:xiaonRF52840 firmware/stacklight
```

```bash
arduino-cli upload --fqbn Seeeduino:nrf52:xiaonRF52840 -p /dev/ttyACM0 firmware/stacklight
```

## Tunables (top of stacklight.ino)

- `LED_COUNT`: 7 for Jewel 7, 1 for a single LED.
- `DEFAULT_BRIGHTNESS`, `MAX_BRIGHTNESS`: light output vs battery life and heat.
- `DISCONNECT_TIMEOUT_MS`: auto-off when the computer is gone. 0 disables.
- `LOW_BATT_MV`, `CUTOFF_BATT_MV`: battery warning / LED cutoff.
- Base colours for each state: `baseColor()`.

Protocol details: `docs/protocol.md`. UUIDs must match `host/stacklight/protocol.py` (a host unit test checks this).
