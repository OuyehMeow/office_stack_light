// Office Stack Light firmware
// Target: Seeed Studio XIAO nRF52840 (non-Sense), "Seeed nRF52 Boards" core (NOT the mbed core)
// LED:    WS2812B / SK6812 addressable LEDs (default: Adafruit NeoPixel Jewel 7)
//
// BLE GATT protocol: see docs/protocol.md. Keep UUIDs in sync with host/stacklight/protocol.py.

#include <bluefruit.h>
#include <Adafruit_NeoPixel.h>
#include <Adafruit_LittleFS.h>
#include <InternalFileSystem.h>

using namespace Adafruit_LittleFS_Namespace;

// ---------------------------------------------------------------- config
#define DEVICE_NAME            "StackLight"
#define FW_VERSION             "0.1.0"

#define LED_PIN                D0        // -> 330R -> LED DIN
#define LED_COUNT              7         // Jewel 7. Set to 1 for a single LED.
#define BUTTON_PIN             D1        // tactile switch to GND, internal pull-up

#define DEFAULT_BRIGHTNESS     48        // 0..255, ~19 %
#define MAX_BRIGHTNESS         160       // hard cap: current + heat inside the capsule
#define DISCONNECT_TIMEOUT_MS  (60UL * 60UL * 1000UL)  // no host for 60 min -> OFF. 0 = never
#define BATTERY_POLL_MS        30000UL
#define LOW_BATT_MV            3500      // warn below this
#define CUTOFF_BATT_MV         3400      // LEDs out of spec below ~3.5 V; shut LED off, keep BLE
#define LONG_PRESS_MS          1500

// XIAO nRF52840 battery / charger pins (defined by the Seeed non-mbed variant; fallbacks below)
#ifndef PIN_VBAT
#define PIN_VBAT               32        // P0.31, divider 1M / 510k
#endif
#ifndef VBAT_ENABLE
#define VBAT_ENABLE            14        // P0.14, LOW enables the divider. NEVER drive HIGH.
#endif
#ifndef PIN_CHARGING_CURRENT
#define PIN_CHARGING_CURRENT   22        // P0.13, LOW = 100 mA, floating = 50 mA
#endif

// ---------------------------------------------------------------- protocol
enum State : uint8_t { ST_OFF = 0, ST_AVAILABLE = 1, ST_BUSY = 2, ST_MEETING = 3, ST_CUSTOM = 4, ST_COUNT };
enum Effect : uint8_t { FX_SOLID = 0, FX_BREATHE = 1, FX_BLINK = 2, FX_COUNT };

// 128-bit UUIDs, little-endian byte order (Bluefruit convention)
// service 7f3a1000-8c2e-4d5b-9e61-3a2f5c7b9d01, chars ...1001..1004
#define UUID_BYTES(lo) { 0x01, 0x9D, 0x7B, 0x5C, 0x2F, 0x3A, 0x61, 0x9E, \
                         0x5B, 0x4D, 0x2E, 0x8C, (lo), 0x10, 0x3A, 0x7F }
const uint8_t UUID_SVC[16]    = UUID_BYTES(0x00);
const uint8_t UUID_STATE[16]  = UUID_BYTES(0x01);
const uint8_t UUID_COLOR[16]  = UUID_BYTES(0x02);
const uint8_t UUID_BRIGHT[16] = UUID_BYTES(0x03);
const uint8_t UUID_EFFECT[16] = UUID_BYTES(0x04);

BLEService        svc(UUID_SVC);
BLECharacteristic chrState(UUID_STATE);
BLECharacteristic chrColor(UUID_COLOR);
BLECharacteristic chrBright(UUID_BRIGHT);
BLECharacteristic chrEffect(UUID_EFFECT);
BLEBas            bas;
BLEDis            dis;

Adafruit_NeoPixel strip(LED_COUNT, LED_PIN, NEO_GRB + NEO_KHZ800);

// ---------------------------------------------------------------- persisted settings
struct Settings {
  uint32_t magic;
  uint8_t  custom[3];
  uint8_t  brightness;
  uint8_t  effect;
  uint8_t  reserved[3];
};
const uint32_t SETTINGS_MAGIC = 0x534C3031;  // "SL01"
const char*    SETTINGS_FILE  = "/settings.bin";

Settings cfg = { SETTINGS_MAGIC, {255, 120, 0}, DEFAULT_BRIGHTNESS, FX_SOLID, {0, 0, 0} };
volatile bool cfgDirty = false;
uint32_t cfgDirtyAt = 0;

// ---------------------------------------------------------------- runtime state
volatile uint8_t state = ST_AVAILABLE;
volatile bool    stateChangedLocal = false;  // set by button, needs notify
uint32_t lastDisconnectAt = 0;
bool     everConnected = false;
uint16_t battMv = 4000;
uint32_t lastBattPoll = 0;

// ---------------------------------------------------------------- helpers
static void baseColor(uint8_t s, uint8_t& r, uint8_t& g, uint8_t& b) {
  switch (s) {
    case ST_AVAILABLE: r = 0;   g = 255; b = 0;   break;
    case ST_BUSY:      r = 255; g = 0;   b = 0;   break;
    case ST_MEETING:   r = 0;   g = 0;   b = 255; break;
    case ST_CUSTOM:    r = cfg.custom[0]; g = cfg.custom[1]; b = cfg.custom[2]; break;
    default:           r = 0;   g = 0;   b = 0;   break;
  }
}

static void loadSettings() {
  File f(InternalFS);
  if (f.open(SETTINGS_FILE, FILE_O_READ)) {
    Settings tmp;
    if (f.read(&tmp, sizeof(tmp)) == sizeof(tmp) && tmp.magic == SETTINGS_MAGIC) {
      cfg = tmp;
      if (cfg.effect >= FX_COUNT) cfg.effect = FX_SOLID;
      if (cfg.brightness > MAX_BRIGHTNESS) cfg.brightness = MAX_BRIGHTNESS;
    }
    f.close();
  }
}

static void saveSettings() {
  InternalFS.remove(SETTINGS_FILE);
  File f(InternalFS);
  if (f.open(SETTINGS_FILE, FILE_O_WRITE)) {
    f.write((const uint8_t*)&cfg, sizeof(cfg));
    f.close();
  }
}

// Debounce flash writes: BLE callbacks only mark dirty, loop() saves after 2 s quiet.
static void markDirty() { cfgDirty = true; cfgDirtyAt = millis(); }

static uint16_t readBatteryMv() {
  // 12-bit, 2.4 V internal reference; divider ratio (1000k + 510k) / 510k
  uint32_t acc = 0;
  for (int i = 0; i < 8; i++) acc += analogRead(PIN_VBAT);
  float mv = (acc / 8.0f) * 2400.0f / 4096.0f * (1510.0f / 510.0f);
  return (uint16_t)mv;
}

static uint8_t mvToPercent(uint16_t mv) {
  // Rough LiPo discharge curve at light load
  static const uint16_t pts[][2] = {
    {4150, 100}, {4050, 90}, {3970, 80}, {3900, 70}, {3840, 60}, {3790, 50},
    {3750, 40}, {3710, 30}, {3670, 20}, {3600, 10}, {3500, 5}, {3400, 0}
  };
  if (mv >= pts[0][0]) return 100;
  for (size_t i = 1; i < sizeof(pts) / sizeof(pts[0]); i++) {
    if (mv >= pts[i][0]) {
      uint16_t v0 = pts[i][0], v1 = pts[i - 1][0];
      uint8_t  p0 = pts[i][1], p1 = pts[i - 1][1];
      return p0 + (uint32_t)(mv - v0) * (p1 - p0) / (v1 - v0);
    }
  }
  return 0;
}

static void setState(uint8_t s, bool fromLocal) {
  if (s >= ST_COUNT) return;
  state = s;
  chrState.write8(s);
  if (fromLocal) stateChangedLocal = true;
}

// ---------------------------------------------------------------- BLE callbacks
void onStateWrite(uint16_t, BLECharacteristic*, uint8_t* data, uint16_t len) {
  if (len >= 1 && data[0] < ST_COUNT) state = data[0];
  else chrState.write8(state);  // reject: restore readable value
}

void onColorWrite(uint16_t, BLECharacteristic*, uint8_t* data, uint16_t len) {
  if (len != 3) { chrColor.write(cfg.custom, 3); return; }
  memcpy(cfg.custom, data, 3);
  markDirty();
}

void onBrightWrite(uint16_t, BLECharacteristic*, uint8_t* data, uint16_t len) {
  if (len < 1) return;
  cfg.brightness = data[0] > MAX_BRIGHTNESS ? MAX_BRIGHTNESS : data[0];
  chrBright.write8(cfg.brightness);
  markDirty();
}

void onEffectWrite(uint16_t, BLECharacteristic*, uint8_t* data, uint16_t len) {
  if (len >= 1 && data[0] < FX_COUNT) { cfg.effect = data[0]; markDirty(); }
  else chrEffect.write8(cfg.effect);
}

void onConnect(uint16_t) { everConnected = true; lastDisconnectAt = 0; }
void onDisconnect(uint16_t, uint8_t) {
  uint32_t t = millis();
  lastDisconnectAt = t ? t : 1;  // 0 means "connected / not timing"
}

static void setupChr(BLECharacteristic& c, uint8_t props, int len, BLECharacteristic::write_cb_t cb) {
  c.setProperties(props);
  c.setPermission(SECMODE_OPEN, SECMODE_OPEN);  // see docs/protocol.md "Security"
  c.setFixedLen(len);
  c.setWriteCallback(cb);
  c.begin();
}

static void setupBle() {
  Bluefruit.begin();
  Bluefruit.setTxPower(0);  // dBm; desk range, saves power
  Bluefruit.setName(DEVICE_NAME);
  Bluefruit.autoConnLed(false);
  Bluefruit.Periph.setConnectCallback(onConnect);
  Bluefruit.Periph.setDisconnectCallback(onDisconnect);
  Bluefruit.Periph.setConnInterval(80, 160);  // 100..200 ms, units of 1.25 ms

  dis.setManufacturer("DIY");
  dis.setModel("Office Stack Light");
  dis.setFirmwareRev(FW_VERSION);
  dis.begin();

  bas.begin();
  bas.write(mvToPercent(battMv));

  svc.begin();
  setupChr(chrState,  CHR_PROPS_READ | CHR_PROPS_WRITE | CHR_PROPS_NOTIFY, 1, onStateWrite);
  setupChr(chrColor,  CHR_PROPS_READ | CHR_PROPS_WRITE, 3, onColorWrite);
  setupChr(chrBright, CHR_PROPS_READ | CHR_PROPS_WRITE, 1, onBrightWrite);
  setupChr(chrEffect, CHR_PROPS_READ | CHR_PROPS_WRITE, 1, onEffectWrite);
  chrState.write8(state);
  chrColor.write(cfg.custom, 3);
  chrBright.write8(cfg.brightness);
  chrEffect.write8(cfg.effect);

  Bluefruit.Advertising.addFlags(BLE_GAP_ADV_FLAGS_LE_ONLY_GENERAL_DISC_MODE);
  Bluefruit.Advertising.addTxPower();
  Bluefruit.Advertising.addService(svc);
  Bluefruit.ScanResponse.addName();
  Bluefruit.Advertising.restartOnDisconnect(true);
  Bluefruit.Advertising.setInterval(160, 1600);  // fast 100 ms, slow 1 s
  Bluefruit.Advertising.setFastTimeout(30);
  Bluefruit.Advertising.start(0);
}

// ---------------------------------------------------------------- rendering
static void render(uint32_t now) {
  uint8_t r, g, b;
  baseColor(state, r, g, b);
  uint16_t level = cfg.brightness;  // 0..255

  if (battMv < CUTOFF_BATT_MV) {
    level = 0;
  } else if (state != ST_OFF) {
    switch (cfg.effect) {
      case FX_BREATHE: {
        // 4 s triangle wave, 20 %..100 %
        uint32_t t = now % 4000;
        uint32_t tri = t < 2000 ? t : 4000 - t;           // 0..2000
        level = level * (200 + tri * 800 / 2000) / 1000;
        break;
      }
      case FX_BLINK:
        if ((now % 1000) >= 500) level = 0;
        break;
      default: break;
    }
    // Low battery: brief dip every 10 s
    if (battMv < LOW_BATT_MV && (now % 10000) < 150) level = 0;
  }

  strip.setBrightness(level);
  uint32_t c = strip.Color(r, g, b);
  for (int i = 0; i < LED_COUNT; i++) strip.setPixelColor(i, c);
  strip.show();
}

// ---------------------------------------------------------------- button
static void pollButton(uint32_t now) {
  static bool     last = HIGH;
  static uint32_t downAt = 0;
  static bool     longFired = false;
  bool cur = digitalRead(BUTTON_PIN);

  if (cur == LOW && last == HIGH) { downAt = now; longFired = false; }
  if (cur == LOW && !longFired && now - downAt > LONG_PRESS_MS) {
    setState(ST_OFF, true);   // long press: off
    longFired = true;
  }
  if (cur == HIGH && last == LOW && !longFired && now - downAt > 30) {
    // short press: cycle available -> busy -> meeting -> custom -> available
    uint8_t s = state;
    s = (s == ST_OFF || s >= ST_CUSTOM) ? ST_AVAILABLE : s + 1;
    setState(s, true);
  }
  last = cur;
}

// ---------------------------------------------------------------- setup / loop
void setup() {
  pinMode(VBAT_ENABLE, OUTPUT);
  digitalWrite(VBAT_ENABLE, LOW);           // keep divider enabled; HIGH can damage P0.31
  pinMode(PIN_CHARGING_CURRENT, OUTPUT);
  digitalWrite(PIN_CHARGING_CURRENT, LOW);  // 100 mA charge
  pinMode(BUTTON_PIN, INPUT_PULLUP);

  analogReference(AR_INTERNAL_2_4);
  analogReadResolution(12);
  battMv = readBatteryMv();

  InternalFS.begin();
  loadSettings();

  strip.begin();
  strip.clear();
  strip.show();

  setupBle();
}

void loop() {
  uint32_t now = millis();

  pollButton(now);

  if (stateChangedLocal) {
    stateChangedLocal = false;
    if (Bluefruit.connected()) chrState.notify8(state);
  }

  if (DISCONNECT_TIMEOUT_MS && everConnected && lastDisconnectAt &&
      !Bluefruit.connected() && now - lastDisconnectAt > DISCONNECT_TIMEOUT_MS) {
    setState(ST_OFF, false);
    lastDisconnectAt = 0;
  }

  if (now - lastBattPoll > BATTERY_POLL_MS) {
    lastBattPoll = now;
    battMv = readBatteryMv();
    uint8_t pct = mvToPercent(battMv);
    if (Bluefruit.connected()) bas.notify(pct); else bas.write(pct);
  }

  if (cfgDirty && now - cfgDirtyAt > 2000) {
    cfgDirty = false;
    saveSettings();
  }

  render(now);

  // Solid colour needs no refresh; animate at 40 Hz only when needed.
  bool animating = state != ST_OFF && cfg.effect != FX_SOLID;
  delay(animating ? 25 : 100);  // FreeRTOS tickless idle: CPU sleeps here
}
