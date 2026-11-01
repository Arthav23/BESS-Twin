# Bench logger: parts and wiring

This logger produces the CSV files that `calibrate.py` reads, at 10 samples per second, and opens a relay if the cell goes above 4.25 V, below 2.5 V or above 60 °C. **The firmware has not yet been tested on hardware.** Check the voltage, current and temperature readings against a multimeter and a thermometer before the first real test.

## Parts (approximate Indian retail; check local listings)

| Part | Note |
|---|---|
| ESP32 dev board (DevKit V1 or similar) | any ESP32 with GPIO21/22/26/34/35 |
| INA226 breakout module | **replace its 0.1 Ω (R100) shunt with 10 mΩ, 1 %, 2 W.** The stock shunt saturates at about 0.8 A |
| 2 × 10 kΩ NTC thermistor, B = 3950, plus 2 × 10 kΩ 1 % resistors | one taped to the middle of the cell can, one in the air |
| 1-channel relay module (or a MOSFET switch) rated 10 A | in series with the load, closed only while the logger says OK |
| 10 A fuse and holder, 18650 holder with thick leads or welded tabs, 1.5 mm² wire | |
| Electronic load, or a 0.68 Ω 50 W resistor for 5 A | |

## Wiring

```
 cell + ──[10 A fuse]──┬── INA226 IN+        INA226 IN- ── relay COM, relay NO ── load + 
                       └── INA226 VBUS
 cell - ───────────────┬── load -
                       └── ESP32 GND ── INA226 GND

 INA226  VCC → ESP32 3V3   SDA → GPIO21   SCL → GPIO22   (A0, A1 to GND: address 0x40)
 NTC cell:  3V3 ── 10 kΩ ── GPIO34 ── NTC ── GND
 NTC air:   3V3 ── 10 kΩ ── GPIO35 ── NTC ── GND
 Relay   IN → GPIO26, VCC → 5V (VIN), GND → GND
```

For charging (T6), connect the charger where the load is. The current then reads negative, which is correct (discharge is positive).

## Use

1. Open `bess_logger.ino` in the Arduino IDE with the ESP32 board package and upload it. Set `R_SHUNT` to your shunt's measured value.
2. Check with no load: V should match a multimeter within 5 mV, I should read under 0.01 A, and both temperatures should read room temperature within 1 K.
3. Check with a known load: I should match a clamp meter or the electronic load within 2 %. If discharge reads negative, set `I_SIGN = -1.0`.
4. For each test in `BENCH_TEST_GUIDE.md`: `python3 serial_to_csv.py <port> data/cell1/<file name>.csv`, run the test, then Ctrl+C.
5. Run `python3 ../calibrate.py data/cell1 --out calib.json`.

Sending `s` in the serial monitor opens the relay immediately. The relay also opens on reset and stays open for the first 3 s, so the load is never connected while the logger is not running.
