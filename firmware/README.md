# Firmware

Target: Seeed Studio XIAO nRF52840 with the "Seeed nRF52 Boards" Arduino core, version 1.1.13 (the non-mbed core; the mbed core lacks the Bluefruit library). Board ID (FQBN): `Seeeduino:nrf52:xiaonRF52840`.

The XIAO ships with a USB bootloader, so no programmer (J-Link etc.) is needed. A failed upload cannot brick it: the bootloader can always be entered by double-tapping reset.

## Flash process

Do this on the bare board first, before soldering anything. Battery not needed.

### Before you start
- USB-C cable that carries data. Many cheap cables are charge-only: if no port or drive ever appears, swap the cable first.
- Know the bootloader trick: double-tap the tiny reset button next to the USB-C port (two presses within about half a second). The board shows up as a USB drive (usually named XIAO-SENSE, also on the non-Sense board) and its LED pulses. Unplug or tap reset once to leave.

### Method A: drag and drop (no software install)
1. GitHub -> Actions -> latest green "ci" run -> Artifacts -> download `stacklight-firmware`, unzip. It contains `stacklight.uf2`.
2. Plug in the XIAO, double-tap reset. The USB drive appears.
3. Copy `stacklight.uf2` onto the drive. The board reboots by itself and the drive disappears (some systems warn "disk not ejected properly": ignore).
4. Go to "Verify".

### Method B: script (builds from source)
One-time installs:
- arduino-cli: macOS `brew install arduino-cli`, Windows `winget install ArduinoSA.CLI`, Linux see arduino.github.io/arduino-cli.
- adafruit-nrfutil (the core calls it after linking; on macOS/Linux it must be on PATH): `pip3 install --user adafruit-nrfutil`.

Then from the repo root:

```bash
firmware/flash.sh
```

Windows PowerShell:

```powershell
.\firmware\flash.ps1
```

The script installs the board package and NeoPixel library on first run, compiles, finds the board and uploads. If it cannot find the board, double-tap reset and run again, or pass the port: `firmware/flash.sh /dev/cu.usbmodem1101` / `.\firmware\flash.ps1 -Port COM5`.

Linux only: if upload fails with a permission error on /dev/ttyACM0, add yourself to the `dialout` group (`sudo usermod -aG dialout $USER`, then log out and in).

### Method C: Arduino IDE 2
1. Preferences -> Additional boards manager URLs: `https://files.seeedstudio.com/arduino/package_seeeduino_boards_index.json`
2. Boards Manager: install "Seeed nRF52 Boards" 1.1.13. Do not use "Seeed nRF52 mbed-enabled Boards".
3. Library Manager: install "Adafruit NeoPixel".
4. macOS/Linux: `pip3 install --user adafruit-nrfutil` (Windows: bundled).
5. Tools -> Board -> Seeed nRF52 Boards -> "Seeed XIAO nRF52840". Tools -> Port -> the XIAO.
6. Open `firmware/stacklight/stacklight.ino`, Upload.

### Verify
1. On the computer: `stacklight scan` lists `StackLight` with an RSSI value. (macOS: allow Bluetooth access for the terminal when asked.)
2. Optional, phone: nRF Connect app -> scan -> "StackLight" -> connect -> custom service `7f3a1000-...` and Battery Service visible.
3. `stacklight status` returns state "available" and a battery value. With no battery connected the battery reading is meaningless.
4. The LEDs only light once the battery is connected through the switch (they are powered from the battery node, not from USB). Colour tests come after wiring.

### Troubleshooting
- No port / no drive: charge-only cable, or a USB hub; try a direct port and another cable.
- `adafruit-nrfutil: executable file not found`: install it (see above) and make sure `~/.local/bin` (Linux) or the Python user bin folder (macOS) is on PATH.
- Upload starts then times out: double-tap reset, then upload again within a few seconds.
- Board compiled for the wrong core (errors about `bluefruit.h` missing): you selected the mbed board; pick "Seeed XIAO nRF52840" under "Seeed nRF52 Boards".
- `stacklight scan` finds nothing: Bluetooth off on the computer, or the firmware did not start; tap reset once and scan again.

### Updating later
Same steps. Settings saved on the device (custom colour, brightness, effect) normally survive a firmware update.

## Tunables (top of stacklight.ino)

- `LED_COUNT`: 7 for Jewel 7, 1 for a single LED.
- `DEFAULT_BRIGHTNESS`, `MAX_BRIGHTNESS`: light output vs battery life and heat.
- `DISCONNECT_TIMEOUT_MS`: auto-off when the computer is gone. 0 disables.
- `LOW_BATT_MV`, `CUTOFF_BATT_MV`: battery warning / LED cutoff.
- Base colours for each state: `baseColor()`. Effect per state: `effectFor()`.

Protocol details: `docs/protocol.md`. UUIDs must match `host/stacklight/protocol.py` (a host unit test checks this).
