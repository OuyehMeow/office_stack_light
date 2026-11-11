# CAD

Reference 3D models of purchased parts, for enclosure design. Enclosure source files go in `cad/enclosure/` when ready.

## vendor/adafruit-neopixel-jewel-7/
- `adafruit-2226-neopixel-jewel-7.step`: Adafruit NeoPixel Jewel 7 (PID 2226).
- Source: github.com/adafruit/Adafruit_CAD_Parts, folder "2226 NeoPixel Jewel" (also has a Fusion 360 .f3d).
- License: MIT, Copyright (c) 2016 Adafruit Industries (LICENSE in the folder).
- Model extent: about 23 mm diameter, 3.5 mm overall height (PCB + LEDs), origin at PCB underside.

## Seeed XIAO nRF52840 (not included, download manually)
Seeed's official files (linked from the XIAO nRF52840 wiki "Resources" section):
- STEP 3D model (Sense variant): grabcad.com/library/seeed-studio-xiao-nrf52840-sense-1 (free GrabCAD account needed).
  Same PCB outline, USB-C position and pads as the non-Sense board; the Sense adds an IMU and microphone on top. Fine for enclosure fit.
- 2D dimension drawing (non-Sense, DXF): files.seeedstudio.com/wiki/XIAO-BLE/XIAO-nRF52840-DXF.zip
- Not suitable: "XIAO nRF52840 Plus" models (different board, extra pads).

Save the STEP as `cad/vendor/seeed-xiao-nrf52840/xiao-nrf52840-sense.step` if you want it in the repo (check the GrabCAD license first).

## Still to verify with calipers on the real parts
- XIAO PCB thickness, USB-C overhang past the board edge, reset button and charge LED positions.
- Battery actual size (vendors vary +/- 1 mm).
