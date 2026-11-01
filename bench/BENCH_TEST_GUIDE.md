# BESS-Twin bench test guide: one day, two to four cells, low voltage

This is how to replace the model's main assumptions with measurements. Plan on one working day. Every test runs on a single cell at 5 A or less (one test briefly reaches 10 A, through a busbar strip only), so nothing here needs more than a bench supply, a load and a logger.

The flow is:

```
bench logs (CSV)  ->  python3 calibrate.py data/  ->  calib.json  ->  python3 bess_platform.py calib.json
                       (fit + replay + pass/fail)                     (results tagged "calibrated")
```

`calibrate.py` only writes a value to `calib.json` if the replay of its own test meets the pass criterion. Everything else keeps its ASM tag.

## 1. Safety first

- Use only 1 cell at a time for T1–T4, at most 5 A. Never short a cell or a busbar.
- Work in a fire-resistant tray (a metal tray with sand). Keep an ABC dry-powder extinguisher within reach.
- Fit an in-line fuse (10 A for T1–T4, 15 A for the T5 busbar test) and a thermal cut-out or a logger alarm at 60 °C.
- Stop at 4.25 V per cell on charge, 2.5 V on discharge, or 60 °C. Never leave a test running unattended.
- Use cells with no dents or torn sleeves, and charge them on a proper CC-CV Li-ion charger.

## 2. Kit

| Item | Use | Notes |
|---|---|---|
| 2–4 Molicel P28A cells (more for T5) | device under test | about ₹460–530 each in Indian retail listings |
| Single 18650 holder with thick leads, or spot-welded nickel tabs | contact | spring holders add tens of mΩ; prefer welded tabs |
| Programmable DC electronic load (0–10 A), or power resistors with a MOSFET switch | discharge | a 0.68 Ω, 50 W resistor gives about 5 A at 3.6 V |
| Bench supply with current limit | charge, T5 busbar test | |
| Current and voltage logger at 10 samples/s or faster | V and I | ready-made: `logger/bess_logger.ino` (ESP32 + INA226 + two NTCs + safety relay) and `logger/serial_to_csv.py`; wiring and parts in `logger/WIRING.md` |
| 10 kΩ NTC thermistor or K-type thermocouple, taped to the middle of the cell can | temperature | add a second one for the air temperature in T2 |
| Kitchen scale (0.1 g) | cell mass | |
| Multimeter with mV range | T5 busbar drop | |
| Cardboard box with a small heater and a thermometer, or a warm room | T3 at about 35 °C | **never an oven** |

## 3. File format

Comma-separated, one header row, lines starting with `#` are ignored. Discharge current is positive.

```
t_s,V,I_A,T_C
0.0,4.182,0.000,25.1
0.1,4.181,0.000,25.1
```

`T2_heating.csv` adds one column, `Tamb_C`. `T5_cells.csv` has columns `cell_id,R_mOhm`. `T5_busbar.csv` has columns `branch,busbar,I_A,drop_mV`, where busbar is `Ni` or `CuNi`.

## 4. The tests

Put the files for one cell in one folder, named exactly as below.

| Test | Do this | File | Calibrates | Pass criterion |
|---|---|---|---|---|
| T1 capacity and OCV | Full CC-CV charge, rest 1 h, then discharge at 0.56 A (0.2C) to 2.5 V. Log at 1 s. | `T1_capacity.csv` | Q_cell, OCV table | capacity within ±5 % of 2.8 Ah |
| T4 pulses | Bring the cell to 100 %, 50 %, 20 % and 10 % SOC (discharge at 1 A for the right time, then rest 30 min). At each SOC: rest 30 s, then **three times** 5 A for 30 s followed by 150 s rest, then once 2 A for 30 s and 150 s rest. Log at 10 samples/s. | `T4_soc100.csv`, `T4_soc50.csv`, `T4_soc20.csv`, `T4_soc10.csv` | R25, R_p, tau_p, soc_gain | voltage replay within 20 mV during every rest |
| T3 ambient | Repeat the 50 % SOC pulse file with the cell soaked for 1 h in the warm box (35 °C or more; a larger gap gives a better slope). | `T4_soc50_35C.csv` (use the real temperature in the name) | R_T_slope | uncertainty under 30 % of the value |
| T2 heating | Full cell in still air at room temperature: 5 A for 10 min, then 10 min rest. Log cell and air temperature at 1 s. | `T2_heating.csv` | cp_cell (and G of one cell, for reference) | replay within ±2 K at every point |
| T5 cell spread | Measure the DC resistance of every cell in the batch with the T4 method (one 5 A step at 50 % SOC). | `T5_cells.csv` | cell_sigma | at least 30 cells for the spread to be written |
| T5 busbar | Pass 10 A from the bench supply through each branch strip and read the mV drop across it. | `T5_busbar.csv` | R_ic_Ni or R_ic_CuNi | within ±20 % between branches |
| T6 charge | Log one full CC-CV charge at 1C. | (compare by hand with section 4.7) | CC fraction, CV taper | charge time within ±20 % |
| T7 sensor fault | During a T2 run, unplug the thermistor or shunt it with a resistor. | (logger alarm) | checker C7 | flagged within 15 s |

Repeat T1, T2 and T4 three times if time allows. `calibrate.py` reports the spread.

## 5. Run the calibration

```
python3 calibrate.py data/cell1 --out calib.json        # writes calib.json and calib_report.md
python3 ../bess_platform.py calib.json                  # all results now use the measured values
```

To see the effect in the browser, open `bess_dashboard.html#checker` and load `calib.json` under *Parameters and calibration*. Every result and the 3D module colours switch to the measured values.

Check `calib_report.md` first. Every fitted value is listed with the test it came from, whether it passed, and the replay error. In `results.json` the measured parameters are tagged `calibrated`, and the traceability table shows which requirements now rest on measurements.

## 6. Check the method before you have data

`make_synthetic.py` writes files in exactly this format from a single-cell model whose "true" values are hidden in `TRUE_VALUES_hidden.json`, with logger-like noise (2 mV, 10 mA, 0.2 K). Running `calibrate.py synthetic/` recovers them. Result of that check (synthetic, not a measurement):

| Parameter | True | Fitted | Error |
|---|---|---|---|
| Q_cell | 2.72 Ah | 2.720 Ah | 0.0 % |
| R25 | 21.5 mΩ | 21.7 mΩ | +1.1 % |
| R_p | 6.5 mΩ | 6.47 mΩ | −0.5 % |
| tau_p | 24 s | 23.8 s | −0.7 % |
| soc_gain | 0.45 | 0.433 | −3.7 % |
| cp_cell | 1020 J/kg·K | 1021 J/kg·K | +0.1 % |
| R_T_slope | 0.012 /K | 0.0134 /K | +11.5 % (±0.0009 from a 10 K gap) |
| R_ic_Ni | 2.6 mΩ | 2.26 mΩ | −13 % (4 branches) |
| cell_sigma | 6 % | 5.9 % | −1 %, but not written: 16 cells give ±18 % |
| OCV table | | | at most 2 mV at the 10 points |

What this taught us about the procedure: the first version of the script overestimated tau_p by 38 %, because a fit on the logarithm of a noisy decay is biased. It also overestimated soc_gain by 33 %, because the state of charge falls during the 10 % SOC pulses. Both are fixed. Use pulses repeated three times, a wide temperature gap for T3, and 30 or more cells for the spread.

What this check does **not** show: that the model structure fits a real P28A. Only the real test can show that.
