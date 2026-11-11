# Office Stack Light

A palm-size, battery-powered BLE status light for the desk: green available, red busy, blue in a meeting, plus one custom colour slot. Controlled from the computer; magnets on the bottom and side.

## Layout

- `docs/hardware.md`: board and part selection, BOM, wiring, power budget, enclosure design brief.
- `docs/protocol.md`: BLE GATT protocol.
- `firmware/`: Arduino firmware for the Seeed XIAO nRF52840.
- `host/`: Python CLI, background daemon and phone-sized web UI (Windows / macOS / Linux), with a mock device and Teams presence sync.
- `docs/folder_structure.txt`: annotated folder tree.

## Workflow

1. Software + electronics selection (this repo, v0.1).
2. Enclosure design from `docs/hardware.md` section 6.
3. Design review and revisions.
4. Prototypes.

## Quick start

1. Buy the parts in `docs/hardware.md` section 3.
2. Flash the firmware: `firmware/README.md`.
3. `pip install -e host`, then `stacklight scan` and `stacklight busy`.

No hardware yet: `pip install -e host && stacklight ui --mock --presence mock`.
