# BLE protocol

Device name: `StackLight`. Advertises the custom service UUID, so hosts can filter by it.

Custom service `7f3a1000-8c2e-4d5b-9e61-3a2f5c7b9d01`

- State `7f3a1001-...`: 1 byte, read / write / notify.
  0 off, 1 available (green), 2 busy (red), 3 meeting (blue), 4 custom (custom colour).
  Invalid values are rejected. Notifies when changed by the button on the device.
- Custom colour `7f3a1002-...`: 3 bytes R, G, B, read / write. Used by state 4. Persisted in flash.
- Brightness `7f3a1003-...`: 1 byte 0-255, read / write. Clamped to 160 by firmware. Persisted.
- Effect `7f3a1004-...`: 1 byte, read / write. 0 solid, 1 breathe (4 s), 2 blink (1 Hz). Persisted.

Standard services
- Battery Service 0x180F, Battery Level 0x2A19 (percent, notify every 30 s while connected).
- Device Information 0x180A (manufacturer, model, firmware revision).

Device behaviour
- Boots into state 1 (available).
- Button: short press cycles available -> busy -> meeting -> custom -> available. Long press (1.5 s) -> off.
- No host connected for 60 min after a disconnect -> off (DISCONNECT_TIMEOUT_MS).
- Battery < 3.5 V: light dips briefly every 10 s. < 3.4 V: LEDs off, BLE stays up so the host can read the battery level.

Security
- v0.1 characteristics are open (no pairing). Anyone within BLE range (~10 m) with a BLE app can change the light.
- To require bonding: change `SECMODE_OPEN` to `SECMODE_ENC_NO_MITM` in `setupChr()`. The OS will pair on first write (macOS automatic, Windows/Linux may prompt).

Host -> device examples (any BLE tool, e.g. nRF Connect app)
- Busy: write `02` to State.
- Custom purple: write `80 00 FF` to Custom colour, then `04` to State.
