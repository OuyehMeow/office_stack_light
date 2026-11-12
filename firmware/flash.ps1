# Build and flash the StackLight firmware to a Seeed XIAO nRF52840 (Windows PowerShell).
# Usage: .\firmware\flash.ps1 [-Port COM5]
param([string]$Port = "")
$ErrorActionPreference = "Stop"

$FQBN = "Seeeduino:nrf52:xiaonRF52840"
$CORE = "Seeeduino:nrf52@1.1.13"   # version verified in CI
$BOARDS_URL = "https://files.seeedstudio.com/arduino/package_seeeduino_boards_index.json"
Set-Location $PSScriptRoot

if (-not (Get-Command arduino-cli -ErrorAction SilentlyContinue)) {
  Write-Error "Missing arduino-cli. Install: winget install ArduinoSA.CLI"
}

Write-Host "== 1/4 board package + library"
arduino-cli core update-index --additional-urls $BOARDS_URL | Out-Null
if (-not (arduino-cli core list | Select-String "^Seeeduino:nrf52 ")) {
  arduino-cli core install $CORE --additional-urls $BOARDS_URL
}
if (-not (arduino-cli lib list | Select-String "NeoPixel")) { arduino-cli lib install "Adafruit NeoPixel" }

Write-Host "== 2/4 compile"
arduino-cli compile --fqbn $FQBN --output-dir build stacklight
if ($LASTEXITCODE -ne 0) {
  Write-Host "If the error mentions adafruit-nrfutil: pip install adafruit-nrfutil, then run again."
  exit 1
}

Write-Host "== 3/4 find board"
if (-not $Port) {
  $line = arduino-cli board list | Select-String "XIAO|nRF52840" | Select-Object -First 1
  if ($line) { $Port = ($line.ToString() -split "\s+")[0] }
}
if (-not $Port) {
  Write-Host "No board found. Check the USB cable carries data, or double-tap reset and run again. Ports:"
  arduino-cli board list
  exit 1
}
Write-Host "   port: $Port"

Write-Host "== 4/4 upload"
arduino-cli upload --fqbn $FQBN -p $Port --input-dir build stacklight
Write-Host "Done. Verify: stacklight scan   (should list 'StackLight')"
