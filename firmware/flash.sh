#!/usr/bin/env bash
# Build and flash the StackLight firmware to a Seeed XIAO nRF52840 (macOS / Linux).
# Usage: firmware/flash.sh [serial-port]     e.g. /dev/ttyACM0 or /dev/cu.usbmodem1101
set -euo pipefail

FQBN="Seeeduino:nrf52:xiaonRF52840"
CORE="Seeeduino:nrf52@1.1.13"   # version verified in CI
BOARDS_URL="https://files.seeedstudio.com/arduino/package_seeeduino_boards_index.json"
cd "$(dirname "$0")"

need() { command -v "$1" >/dev/null 2>&1 || { echo "Missing $1. $2" >&2; exit 1; }; }
need arduino-cli "Install: macOS 'brew install arduino-cli', Linux see https://arduino.github.io/arduino-cli/latest/installation/"
need adafruit-nrfutil "Install: pip3 install --user adafruit-nrfutil (the Seeed core calls it after linking)"

echo "== 1/4 board package + library"
arduino-cli core update-index --additional-urls "$BOARDS_URL" >/dev/null
arduino-cli core list | grep -q "^Seeeduino:nrf52 " || arduino-cli core install "$CORE" --additional-urls "$BOARDS_URL"
arduino-cli lib list | grep -q "^Adafruit_NeoPixel\|^Adafruit NeoPixel" || arduino-cli lib install "Adafruit NeoPixel"

echo "== 2/4 compile"
arduino-cli compile --fqbn "$FQBN" --output-dir build stacklight

echo "== 3/4 find board"
PORT="${1:-}"
if [ -z "$PORT" ]; then
  PORT=$(arduino-cli board list | awk 'NR>1 && /XIAO|nRF52840|ttyACM|usbmodem/ {print $1; exit}')
fi
if [ -z "$PORT" ]; then
  echo "No board found. Check the USB cable carries data, or double-tap the reset button and run again." >&2
  arduino-cli board list >&2
  exit 1
fi
echo "   port: $PORT"

echo "== 4/4 upload"
arduino-cli upload --fqbn "$FQBN" -p "$PORT" --input-dir build stacklight
echo "Done. Verify: stacklight scan   (should list 'StackLight')"
