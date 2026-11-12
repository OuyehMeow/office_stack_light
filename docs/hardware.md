# Hardware: electronics selection, wiring, enclosure brief

Status: v0.1 selection, ready for enclosure design. Prices are approximate (USD, late 2026) and vary by vendor.

## 1. Architecture

```
 USB-C 5V ──► XIAO nRF52840 ──(on-board BQ25101 charger)──► BAT+/BAT- pads
                   │                                           │
                   │ D0 ──330R──► LED DIN                      │
                   │ D1 ◄── tact switch ── GND                 │
                   │                                           │
 LiPo 1S 1000 mAh ─┴── JST-PH ── slide switch ── BAT+ node ────┴──► LED PWR (VBAT, 3.4-4.2 V)
```

- MCU + BLE + charger: Seeed Studio XIAO nRF52840 (one board does BLE 5, USB-C, LiPo charging, battery voltage sense).
- Light: Adafruit NeoPixel Jewel 7 (7x WS2812B-class 5050 RGB on a 23 mm round PCB), driven as one light, all pixels the same colour.
- Power: single-cell LiPo with protection circuit, hard power switch in the battery line.
- Input: one tactile button for manual state change without the computer.

## 2. Why these parts

MCU: XIAO nRF52840 (chosen)
- BLE connected idle about 1 mA or less with the Adafruit/Seeed core (FreeRTOS tickless idle), vs tens of mA for an ESP32-C3 under Arduino unless light-sleep is configured by hand.
- On-board battery voltage divider (P0.31, enable P0.14), so the battery percentage needs no extra parts.
- 21 x 17.8 mm, fits easily in a palm-size capsule.
- Trade-off: charger is only 50 / 100 mA (firmware selects 100 mA). A 1000 mAh cell needs about 10-12 h, i.e. overnight.

Alternative considered: XIAO ESP32-C3
- Cheaper (about $5) and Seeed lists about 380 mA fast charge (2.5-3 h for 1000 mAh).
- No on-board battery divider (need 2 resistors), higher BLE idle current, firmware would need porting (NimBLE).
- Pick this only if charge time matters more than run time.

Light: NeoPixel Jewel 7 (chosen)
- 7 LEDs spread across 23 mm give an even glow in the dome at low per-LED brightness; one LED makes a hot spot.
- Any RGB colour, so the custom slot is pure software.
- Runs directly from the LiPo. WS2812B is specified from about 3.5 V; firmware turns the LEDs off below 3.4 V.
- Trade-off: about 0.5-1 mA quiescent per LED (3.5-7 mA total) even when black. That is why there is a hard power switch.

Alternative: single LED (Adafruit NeoPixel Mini PCB, PID 1612). Set `LED_COUNT 1` in firmware. Lower quiescent current, dimmer, more hot-spotting.

## 3. Bill of materials (per unit)

1. Seeed Studio XIAO nRF52840, non-Sense, SKU 102010448. Qty 1. About $10. Buy without pre-soldered headers.
2. Adafruit NeoPixel Jewel 7, PID 2226. Qty 1. About $6.
3. LiPo 3.7 V 1000 mAh, size 803040 (8 x 30 x 40 mm), with protection PCM, JST-PH 2.0 mm 2-pin lead. Qty 1. About $7. Any 800-1200 mAh cell that fits the enclosure works.
4. JST-PH 2.0 2-pin pigtail matching the battery. Qty 1. About $0.50. Check polarity against the battery: JST-PH polarity is not standardised between vendors.
5. Mini slide switch SS12D00G3 (SPDT, 2.54 mm pitch, body about 8.6 x 3.6 x 3.5 mm). Qty 1. About $0.20.
6. Tactile switch 6 x 6 mm, through-hole, 7 mm or 9.5 mm height. Qty 1. About $0.10.
7. Resistor 330 ohm 1/4 W (LED data line series resistor). Qty 1.
8. Capacitor 100 uF 6.3-10 V electrolytic (or 10-22 uF ceramic) across LED PWR/GND. Qty 1.
9. Neodymium disc magnets N52, 10 x 3 mm. Qty 6 (4 bottom, 2 side). About $3 per pack of 20.
10. Silicone wire 28 AWG, red / black / one signal colour. About 30 cm total.
11. Heat-shrink 1.5-3 mm, Kapton tape, double-sided foam tape.
12. If the enclosure halves are screwed: M2 x 6 screws + M2 brass heat-set inserts, qty 2-3.
13. Filament: opaque PLA/PETG for the base, translucent "natural" PETG or frosted PLA for the dome.

Total electronics + hardware: about $30 per unit (excluding filament and tools).

Tools: fine-tip soldering iron, flush cutters, multimeter (to check battery polarity before connecting), hot glue or CA glue for magnets.

## 3a. As ordered (2026-11) and still missing

Ordered
- Amazon: Seeed XIAO nRF52840 pre-soldered x2, 100 uF 35 V radial capacitors x15, 330 ohm 1/2 W resistors x100.
- Adafruit: NeoPixel Jewel 7 (2226) x1, SPDT slide switch (805) x1, tactile switches 6 mm tall (1490) x10.

Still needed per unit
1. LiPo 1S 1000 mAh with protection PCM, 803040 size preferred. Check the connector is JST-PH 2.0 mm (many listings use 1.25 mm or bare wires).
2. Matching JST-PH 2-pin female pigtail from the same vendor (polarity is vendor-specific), or skip the connector and solder the battery leads to the switch.
3. N52 disc magnets 10 x 3 mm, 6 per unit.
4. 26-28 AWG silicone wire, heat-shrink, Kapton tape.
5. If screw-joined: M2 x 6 screws + M2 heat-set inserts.

Quantity check for two prototypes: 2 XIAO ordered, but only 1 Jewel and 1 slide switch. Add 1 Jewel (2226) and 1-2 slide switches (805) for unit 2.

## 4. Wiring

XIAO nRF52840 pin use
- D0 (P0.02): LED data, through 330 ohm to Jewel DIN.
- D1 (P0.03): button to GND (internal pull-up).
- BAT+ / BAT- pads (underside of XIAO): battery, after the slide switch.
- USB-C: charging and firmware upload.
- All other pins unused, free for later (e.g. a vibration sensor, a second button).

Connections
1. Battery red -> JST -> slide switch common pin. Slide switch one outer pin -> "BAT+ node".
2. BAT+ node -> XIAO BAT+ pad, and -> Jewel PWR (5V/PWR pad).
3. Battery black -> XIAO BAT- pad, and -> Jewel GND, and -> one side of button.
4. XIAO D0 -> 330 ohm -> Jewel DIN. Place the resistor near the Jewel.
5. XIAO D1 -> other side of button.
6. 100 uF across Jewel PWR / GND, at the Jewel, observe polarity.

Notes
- The switch disconnects the battery from everything, including the charger. The switch must be ON to charge. Switch OFF at night/weekends: zero drain.
- With USB connected and the switch OFF, the XIAO still runs from USB but the LEDs have no power.
- Do not power the LEDs from the XIAO 3V3 pin (regulator too small) or the 5V pin (only live on USB).
- Keep the LED data wire short (< 10 cm).
- Check battery polarity with a multimeter before plugging in. Reversed polarity will destroy the XIAO charger.

## 5. Power budget (estimates, to be measured on the prototype)

Running (state set, solid colour, default brightness 48/255):
- nRF52840 + BLE connected: about 1 mA
- Jewel quiescent: about 4-7 mA
- Jewel single colour at brightness 48: 7 x about 15 mA x 48/255 = about 20 mA
- Total: about 25 mA

Run time on 1000 mAh (about 900 mAh usable above 3.4 V): about 36 h, about 4 working days of 9 h.
Charge time at 100 mA: about 10-12 h (overnight).
Peak current: firmware caps brightness at 160/255; worst case single colour about 90 mA, white is not used.

## 5a. Charging (how it works)

Path: USB-C 5 V (VBUS) -> BQ25101 linear Li-ion charger on the XIAO -> BAT+ pad -> slide switch -> cell. No extra parts needed.

- Profile: standard CC/CV. Constant current until the cell reaches 4.2 V, then constant voltage while the current tapers; the charger stops when the current falls to a small fraction of the set value.
- Current: set by a resistor on the charger's ISET pin. A second resistor can be switched in parallel by P0.13: floating = 50 mA (default, e.g. in the bootloader), driven LOW = 100 mA. The firmware drives it LOW at boot.
- Indicator: the charger's status output drives the XIAO's charge LED next to the USB-C port: on while charging, off when done or with no battery.
- Board power: with USB plugged in, the XIAO's 3.3 V regulator is fed from USB; unplugged, from the battery. Check the exact power path in Seeed's schematic (Seeed-Studio-XIAO-nRF52840-Sense-v1.1.pdf) before relying on details.
- Our wiring: the LEDs hang on the BAT+ node, so while lit on USB they take part of the 100 mA (about 25 mA). Net charge current is about 75 mA, so a full charge takes longer (about 13-15 h from empty with the light on, 10-12 h with the light off).
- Side effect of that load: the charger measures total current out of BAT+, so with the LEDs drawing more than its termination threshold it may never report "done" and holds the cell at 4.2 V. Safe (the charger still regulates 4.2 V and the cell has its own protection board), but a cell kept at 100 % ages faster. If the light lives on USB permanently, consider a lower brightness or turning the light off at night.
- Switch must be ON to charge (it is in the battery line).
- Safety: the cell's own PCM handles over-charge, over-discharge and short circuit as a second layer; the charger is the first. Do not charge a swollen or damaged cell.
- Chargers: any 5 V USB port or adapter. If a USB-C-to-C charger gives nothing, try a USB-A-to-C cable (some C chargers only output power after USB-C negotiation).

## 6. Enclosure design brief (for your CAD)

Component envelopes (add 0.3-0.5 mm clearance per side; vendor dimensions vary)
- XIAO nRF52840, no headers (enclosure build): 21.0 x 17.8 mm PCB, about 4.5 mm tall including the USB-C receptacle (on top side), plus about 1 mm for wires on BAT pads below. USB-C receptacle is centred on one short edge and sits flush with the PCB edge.
- XIAO nRF52840, pre-soldered headers (as ordered on Amazon): same PCB, but the pin rows add about 2.5 mm plastic + 6 mm pins below the board (about 13 mm total height) and partly block the BAT pads. Use these for breadboard bring-up; for the enclosure either use an unsoldered board or clip the pins flush and design for a 4.5 mm board + about 3 mm of header plastic.
- Jewel 7 (Adafruit 2226, as ordered): 23 mm diameter, about 4 mm thick, solder pads on the back; leave 4 mm behind it for wires.
- Capacitor (as ordered: 100 uF 35 V radial, 6 mm dia x 12 mm + leads): too tall to stand behind the Jewel. Lay it flat (needs a 6.5 mm x 14 mm slot) beside the XIAO sled, or bend it sideways behind the Jewel and reserve 7 mm depth there.
- Resistor (as ordered: 330 ohm 1/2 W axial, body about 3.5 mm dia x 9 mm): in-line on the data wire under heat-shrink, no pocket needed.
- Battery 803040 (not yet ordered): 8 x 30 x 40 mm plus about 3 mm PCM/lead at one end. Design the pocket 9 x 32 x 45 mm and plan for swelling: do not clamp it tight. A common 1000 mAh 503450/603450-class cell (about 6 x 34 x 51 mm) will not lie flat inside a 50-56 mm capsule: either grow the capsule to about 60 mm or stand the cell on edge.
- Slide switch (as ordered: Adafruit 805, E-Switch EG1218 type): 3 pins at 2.54 mm, slide travel 3 mm. Body is larger than the SS12D00G3 originally listed; I could not confirm exact body dimensions, so reserve about 13 x 5 x 6 mm and measure on arrival. Wall slot = actuator width + 0.5 mm by actuator length + 3 mm travel + 0.5 mm.
- Tactile switch (as ordered: Adafruit 1490, Omron B3F-40xx footprint): 6.1 x 6.1 mm base, about 4 mm body. Vendor listings disagree on height (6 mm nominal vs about 12 mm button top above PCB); reserve 12 mm and measure on arrival. Mount it on a printed bracket so the button pushes through a 4 mm hole, or add a printed plunger.
- Magnets: pockets 10.2 mm dia x 3.2 mm deep, glue in. Leave 0.6-0.8 mm plastic skin to the outside (more skin = much weaker hold).

Suggested overall size
- Capsule about 50-56 mm diameter, 85-100 mm tall. Fits a palm and holds the battery flat across the base.
- Lower opaque section about 30-35 mm tall: battery flat at the bottom, XIAO on a sled above it, Jewel on top facing up.
- Upper translucent dome about 50-60 mm tall.

Must-haves
1. USB-C port flush with the outer wall (opening about 9.5 x 3.6 mm, chamfered), XIAO held by a sled or slot so plugging in does not push it inward. A cable must reach the receptacle: plug overmolds are about 12 x 7 mm, so the wall around the opening must be thin or recessed.
2. Flat bottom face with the 4 magnets. Capsule round side will not hold on steel: add a flat face (about 20 x 40 mm) on one side for the 2 side magnets.
3. Magnets and steel surfaces at least 5 mm from the XIAO antenna end (the short edge opposite the USB-C port). Orient the antenna end up/towards the dome, not towards the mounting faces.
4. Distance from Jewel LEDs to the dome inner surface at least 15-20 mm for even diffusion. Translucent PETG 1.2-2 mm wall, or add a frosted inner diffuser disc/cone. Test print a dome sample first.
5. Opaque base section must actually block light (PLA in black/white, 2+ walls), so electronics do not glow.
6. Access to the slide switch and button from outside. Put them where a hand naturally lands; keep them away from the magnet faces.
7. Openable joint (bayonet, thread, or M2 screws into heat-set inserts) for battery service. No glued shut prototypes.
8. Small hole or light pipe for the XIAO charge LED (next to the USB-C port), or accept that it glows through.

Nice-to-have
- Internal light-blocking ring between base and dome so the dome lights evenly without a bright band at the joint.
- Cable strain relief / wire channel between base and Jewel platform.
- Weight: total about 50-60 g; 6 magnets hold this easily on steel, not on painted aluminium or wood (magnets need ferrous metal; for other surfaces add a stick-on steel disc).

## 7. Bring-up order

1. Flash firmware to the bare XIAO over USB (see firmware/README.md, "Flash process"). Check it advertises as "StackLight" (`stacklight scan`).
2. Wire the Jewel + resistor + capacitor. The LEDs are powered from the battery node only, so connect the battery (switch ON) to test colours: `stacklight busy`, `stacklight meeting`, button presses.
3. Check battery polarity, connect battery through the switch, confirm charging (XIAO charge LED on with USB).
4. Measure current with the switch replaced by a multimeter in series: running about 25 mA expected.
5. Install in the enclosure.
