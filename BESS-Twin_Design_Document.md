# BESS-Twin: checking a battery module design before building it

TELIPORT Season 4, Case Study 2. Version 3.0.

Worked example: a burst-power module of Molicel P28A cells for a heavy-lift drone or a hybrid-vehicle auxiliary supply.

Files that go with this document:

| File | What it is |
|---|---|
| `bess_platform.py` | The engine: electro-thermal model, cell-variation Monte Carlo, end-of-life scenario, geometry, bill of materials, checker, traceability and sensitivity sweeps. Runs any design given as JSON. Pure Python, no packages, about 8 s for five designs. |
| `bess_dashboard.html` | The same engine in the browser, as one offline file with two pages. **Home** shows a rotating 3D model of the recommended module, with its cells coloured by simulated temperature as a 40 °C mission plays back, plus the key results and how the platform works. **Module checker** configures two designs (cell, series and parallel counts, busbar, cooling, balancing, BMS) and the mission. It compares curves, rule checks, 3D module views, traceability and bill of materials, searches all 480 designs, runs the uncertainty study and loads a calibration file. |
| `web/engine.js`, `web/test_parity.js` | The dashboard engine and a test that runs it against the Python engine. On 10 designs, 202 numbers agree to within 0.05 %, and all verdicts match. The uncertainty study and the 480-design search give identical results in both engines. |
| `configs/*.json` | Design files: the design-space exploration and the final candidates. |
| `reproduce.py` | Re-runs the five studies behind sections 5 and 9.5, the 480-design search and the uncertainty study, and the browser parity test, and compares each with the committed results. Exit code 0 means everything reproduced. |
| `bench/calibrate.py`, `bench/BENCH_TEST_GUIDE.md`, `bench/make_synthetic.py` | The bench-to-model loop. CSV logs go in, `calib.json` comes out, and the platform tags the replaced values as calibrated. |
| `bench/logger/` | ESP32 + INA226 logger firmware that writes those CSV files at 10 samples/s and opens a relay at 4.25 V, 2.5 V or 60 °C, with a serial-to-CSV script and the wiring. Not yet tested on hardware. |
| `INTERVIEW_KIT.md` | Script, timed tasks and pricing questions to test desirability and willingness to pay. |
| Pitch deck (published separately) | 14 slides for the judges: problem, scope, platform, models, what the checker found, search, recommendation, confidence, evidence, prototype, validation, business, limits and next steps. Speaker notes map each slide to the evaluation criteria. |
| `results*.json`, `*tables*.md` | Output of the runs quoted here. Every number in sections 5, 6 and 9.5 is in these files. |

Each number carries a tag. **DS** means it is from a datasheet, **CALC** means we calculated it, and **ASM** means it is our assumption and nobody has measured it yet. Results that rest on ASM values are good for ranking designs against each other. They do not predict real temperatures until the bench tests in section 9 have run. **None of those tests has been run yet.** The calibration pipeline that will absorb them has been built and checked on synthetic data (section 9.3).

---

## 1. Summary

When you change one thing in a battery module, several others move. More current changes temperature, voltage sag, ageing and cost. More parallel cells change mass, size and cost. A different cooling method changes all of them, plus the space inside the enclosure. The information needed to judge this is spread over cell datasheets, a thermal estimate, a BMS datasheet, a CAD sketch and a price list, and small teams usually keep these in separate spreadsheets.

BESS-Twin puts them into one tagged parameter set. That set feeds these models:

- electrical
- thermal
- cell-variation
- end-of-life
- protection
- balancing
- geometry
- mass and cost

A checker then compares the results with 12 requirements and 12 rules. It says which ones fail and why, and traces every result back to a requirement, a component, an assumption, a model and the test that would confirm it. The checker is also what drives the design. In this study it led us through five steps:

1. **The v2 reference design did not survive its own checker.** v2 recommended 4S4P with liquid cooling and no PCM. It finishes the 25 °C mission with 143 Wh, but the v3 checks show three problems:
   - It fails R4, stopping at 310 s on a 40 °C day.
   - It fails the new end-of-life requirement R11: at 80 % capacity and 1.5 times the resistance, it runs 472 s against 480 s.
   - It carries two interface warnings: the worst parallel branch takes 40.7 A against a 35 A rating (C2), and the BMS dissipates 29 W (C4).
2. **Mechanical checks found a conflict we had missed.** The 100 g of PCM in Option 2 needs 130 cm³ once molten, but the foam between 16 cells holds only 124 cm³ (C12).
3. **Exploring the design space took six runs from one JSON file.** The cell library and the NS/NP inputs let us try a 21700 cell and other cells on the same mission:
   - Molicel P42A fails its 45 °C charge limit on a 40 °C day (C5), and the 4S4P version exceeds 1.5 kg.
   - Samsung 30Q is a 15 A cell, so it cannot carry the burst current (C2 FAIL).
   - A fifth parallel P28A fixes R11 and C2 together.
4. **One last rule took one more change.** A low-loss BMS power path closes C4. Its cost is covered by dropping active balancing, which no requirement depends on.
5. **Recommended design (R-B):** 4S5P P28A, nickel-clad copper busbar, liquid cold plates, low-loss BMS, passive balancing.
   - Rating: 14.4 V, 14.0 Ah, 202 Wh.
   - Checks: every requirement and every rule is met, with no FAIL and no WARN. One MARGINAL remains: on a 40 °C day the hot cell peaks at 58.2 °C, inside the 3 K uncertainty band. The derate rule covers it.
   - At 25 °C: 187 Wh over the 760 s mission.
   - At end of life: 142 Wh.
   - Module: 1434 g, ₹18,216, 0.84 L.
   - The result needs the coolant to return within 5 K of ambient. That becomes the radiator specification.

Three further checks back the recommendation:

- **Automatic search:** of all 480 combinations of cell, parallel count, busbar, cooling, balancing and BMS at 4S, only 7 meet every requirement. All 7 are 4S5P P28A with liquid cooling. R-B sits on the cost, mass and hot-day-margin trade-off front (5.8).
- **Uncertainty:** every assumption was drawn across its plausible range, 300 times. R-B meets R3, R5 and R11 in 100 % of samples and finishes the 40 °C mission in 79 %. The v2 pick meets all four in 0.7 %. The cheaper nickel-busbar point on the front (R-C, ₹17,148) finishes the 40 °C mission in only 64 %. The search and uncertainty study also rank which tests matter most: coolant offset, cooling strength and cell spread drive the hot-day risk (5.9).
- **External evidence:** the model predicts 2.80 Ah at 0.56 A. An independent test measured 2.745–2.787 Ah on four cells, so the model is within 2 %. The model does not lose capacity at high current, so we re-ran R-B with only the manufacturer's guaranteed minimum of 2.50 Ah per cell. It still meets R5 and R11, with 167 Wh and 128 Wh (9.5).

We do not claim liquid cooling, PCM or active balancing as new ideas. What is new is the workflow around them:
- shared tagged parameters
- an automatic checker that steers the design
- traceability from requirement to evidence
- ablation and sensitivity runs that show which part does the work
- one engine running in Python and in the browser, with a parity test
- a calibration loop that turns a day of low-current bench tests into calibrated results
- a search that checks every combination, and an uncertainty study that turns "it passes" into "it passes with this probability"

---

## 2. Application, scope and requirements

### 2.1 Application

Short, high-power bursts on top of a moderate base load, for example a heavy-lift drone or an auxiliary supply in a hybrid vehicle. 11.2 Ah at 140 A lasts 11.2 / 140 = 0.08 h, about 4.8 minutes (CALC), so what matters is the temperature at the end of a mission, not a steady state.

Reference mission M1: 60 A base load, with 140 A for 20 s at the start of every 300 s, until a limit trips. Mean current is (140 × 20 + 60 × 280) / 300 = 65.3 A (CALC). Stress test P1: 140 A constant until a limit trips.

### 2.2 Scope

| In scope | Out of scope |
|---|---|
| One module (3 to 15 cells in series, any parallel count), busbars, sensing, balancing, cooling, envelope | Full pack (for example 96S), high-voltage isolation |
| Lumped electro-thermal model with calibration from bench data | CFD, electrochemical (P2D) models |
| Datasheet comparison and low-current bench tests | Abuse testing, thermal-runaway propagation |
| Prototype-quantity cost, mass and envelope | Production cost, crash and vibration |

### 2.3 Requirements

| ID | Requirement | Limit | Basis |
|---|---|---|---|
| R1 | Nominal voltage and capacity | 14.4 V, at least 11.2 Ah | 4 × 3.6 V, 4 × 2.8 Ah (DS) |
| R2 | Peak current | 140 A for at least 20 s, within the cell rating per branch | P28A maximum discharge 35 A (DS) |
| R3 | Hot-cell temperature, 25 °C ambient | below 60 °C through M1 | cell limit (DS) |
| R4 | Hot-cell temperature, 40 °C ambient | below 60 °C through M1, or a stated derated mission | ASM |
| R5 | Mission energy and length at 25 °C | at least 100 Wh and 480 s | ASM |
| R6 | Module mass, pump and radiator excluded | at most 1.5 kg | ASM |
| R7 | Module cost, pump and radiator excluded | at most ₹19,000 | ASM ($200 at ₹95/USD) |
| R8 | Charge time at 1C | at most 1.5 h | ASM |
| R9 | Hardware protection | OV, UV, OC, short circuit, over-temperature | cell limits (DS) |
| R10 | Failed thermistor detected | within 15 s | ASM |
| R11 | **R5 still met at end of life** | 80 % capacity, 1.5 times resistance | ASM, a common end-of-life definition |
| R12 | **Module envelope** | at most 1.0 L | ASM |

Datasheet operating window for the P28A (DS): charge 0 to 60 °C, discharge −40 to 60 °C. R4 to R8, R11, R12 and the mission are our own choices for a representative duty cycle; a real customer would replace them. They live in the config file, not in the code.

---

## 3. The platform

### 3.1 How the parts exchange data

```
 Requirements R1..R12 --->  Parameter store  <--- cell library (DS), assumptions (ASM),
 (config file)              (value + tag)         bench calibration (calibrated)
                                  |
   +-----------+----------+-------+-------+-----------+----------+-----------+
 Electrical  Thermal  Cell-variation  End of life  Protection  Balancing  Geometry + BOM
   +-----+-----+----------+---------------+-----------+----------+-----------+
         |                                    |
  Results per design                    Conflict checker (12 R + 12 C rules)
         +------------------+-----------------+
                Traceability, sensitivity, recommendation
                            |
              change the design (JSON or dashboard), run again
```

| Producer | Passes | Consumer |
|---|---|---|
| Cell library | capacity, resistance, current and temperature limits, mass, size, price | every model, rules C2, C5, C6 |
| Electrical | heat per cell, including the polarization branch | Thermal |
| Thermal | cell temperature | Electrical (resistance falls as the cell warms), Protection |
| Cell-variation Monte Carlo | worst-cell current factor for this cell, busbar and parallel count | hot-cell estimate, rule C2 |
| Busbar choice | interconnect resistance | Electrical, Monte Carlo |
| Cooling choice | coupling, PCM mass and melt window, cold-plate size | Thermal, BOM, Geometry, rules C9 and C12 |
| NS, NP | cell count | everything; BMS chip choice (C8), cooling scaled with cell count |
| BMS option | shunt and FET resistance, cost | rules C4 and C11, BOM |
| Geometry | envelope, gaps between cells | R12, rule C12 |

### 3.2 Three ways to use it

1. **Browser.** Open `bess_dashboard.html`, with no install and no network. It has two pages.
   - **Overview** (`#home`): a 3D model of the recommended module in a CAD-style viewport rotates while a 40 °C mission plays back. Cells are coloured by temperature, the hot cell and the rest are labelled, and an instrument strip shows time, hot-cell temperature and module voltage. Drag to rotate. Below it, laid out as a test report:
     - a datasheet table for R-B, computed live by the page
     - the search and confidence figures
     - a log of what the checker caught, with each row re-run live by the page using the same rules as the Python engine
     - a block diagram of how the platform works, including the bench-calibration loop
     - the package contents and where the evidence stands
   - **Module checker** (`#checker`): design A and design B each have a preset menu plus every design choice, and a 3D view of the module (cells, busbars, cold plates or PCM, BMS board) coloured by temperature at the peak of the curves shown. Drag it to rotate. The mission strip sets burst and base current, timing, coolant offset and the current factor. Curves switch between 25 °C, 40 °C and end of life. Every rule is shown for both designs with its reason. One button copies a full design review (A against B, every rule with its reason, and the traceability table) as Markdown, ready to paste into a report. The page also shows the traceability and bill-of-materials tables for design A, and a parameter table with its DS, ASM or calibrated tags. Loading `calib.json` switches results to calibrated values. One button copies a design as JSON for the Python engine. Both designs recompute in about 0.25 s. Two more panels:
   - **Search every design:** runs all 480 combinations in about 2 s and plots cost against mass, coloured by verdict, with the R6 and R7 limits drawn. It lists the trade-off front and how many designs each rule rules out. Clicking any dot loads that design.
   - **How sure are we?:** runs 300 samples of design A across all assumption ranges in about 2 s. It shows the pass probability of each requirement, a histogram of the 40 °C peak, and which assumptions move it most.
2. **Script.** `python3 bess_platform.py --config configs/my_design.json` runs any set of designs, writes `results.json` with the full traceability per design, and writes a markdown table file.
3. **Calibration.** `python3 bench/calibrate.py data/` turns bench logs into `calib.json`, which both of the above accept (section 9).

### 3.3 Who it is for

| User | Problem today | What they get |
|---|---|---|
| Student EV, eBAJA or drone team | No licensed multi-physics software, and separate spreadsheets | A model that runs in a browser in seconds, with every assumption visible and a one-day route to calibrate it |
| Early-stage battery or drone engineer | Cell, cooling, busbar and BMS decided separately | One coupled model to screen options before building anything |
| Reviewer, judge or customer | Cannot see why a design was chosen | A trace from each requirement to its evidence, with the evidence still missing marked |

---

## 4. Models

### 4.1 Cell library

| | Molicel P28A | Molicel P42A | Samsung 30Q |
|---|---|---|---|
| Format | 18650 | 21700 | 18650 |
| Capacity (typ.) | 2.8 Ah | 4.2 Ah | 3.0 Ah |
| Max continuous discharge | 35 A | 45 A | 15 A |
| DC resistance used | 20 mΩ (10 A, 1 s) | 16 mΩ (10 A, 1 s) | 26 mΩ (AC 1 kHz max; **ASM** as DC) |
| Max charge current used | 6.0 A | 4.2 A (standard; **ASM** as max) | 4.0 A |
| Charge window | 0–60 °C | 0–45 °C | 0–50 °C |
| Mass | 46 g | 70 g (max) | 48 g (max) |
| Size (max) | 18.6 × 65.2 mm | 21.7 × 70.2 mm | 18.4 × 65.0 mm |
| Price used | ₹428 ($4.50, **ASM**) | ₹475 ($5.00, **ASM**) | ₹475 ($5.00, **ASM**) |

The values come from the manufacturers' data sheets (sources 1–3). Revisions of the P28A sheet disagree on maximum charge current (6 A or 8.4 A), so we use the lower figure. Retail listings in India price the P28A at about ₹460–530 per cell.

Module R-B: 4 × 3.6 = 14.4 V; 5 × 2.8 = 14.0 Ah; 14.4 × 14.0 = 201.6 Wh (CALC).

### 4.2 Electrical model

Cell terminal voltage: `V = OCV(SOC) − I_cell × R_eff − v_p`, with `R_eff = R(T) × f(SOC) + R_interconnect`.

- `R(T) = R25 × exp(−0.015 (T − 25))`, floor 8 mΩ (ASM).
- `f(SOC) = 1 + 0.6 × exp(−SOC / 0.08)` (ASM), so resistance rises near empty.
- `v_p` is the polarization voltage on one RC branch, `dv_p/dt = (I_cell × R_p − v_p) / τ`, with R_p = 8 mΩ and τ = 30 s (ASM). The heat in that branch, `v_p² / R_p`, is counted.
- OCV is a generic NMC table (ASM). Test T1 replaces it.
- Interconnect resistance per branch (ASM): nickel strip 3.0 mΩ, nickel-clad copper 0.8 mΩ.
- End of life: capacity × 0.80, R25 × 1.5 (ASM).

Ohmic heat at 35 A per cell, by hand (CALC):

| Case | R_total | Heat per cell | 16-cell heat |
|---|---|---|---|
| Cell only | 20 mΩ | 24.5 W | 392 W |
| Nickel busbar | 23 mΩ | 28.2 W | 451 W |
| Nickel-clad copper busbar | 20.8 mΩ | 25.5 W | 408 W |

With five parallel cells (R-B), each cell carries 28 A: 28² × 0.0208 = 16.3 W, and 20 cells give 326 W. That is 20 % less module heat than 4S4P at the same 140 A, spread over 25 % more thermal mass (CALC).

### 4.3 Thermal model

Three nodes: the cells, a PCM block (enthalpy method) and a sink.

`C_c × dT_c/dt = q − G_cp (T_c − T_pcm) − G_ca (T_c − T_sink)`, with C_c = N × m_cell × 950 J/kg·K (ASM). For 16 P28A cells, C_c = 699 J/K (CALC).

- The PCM starts at the ambient temperature. If the ambient is above the melt window, the PCM starts fully molten and has no latent buffer left.
- The sink is the ambient for air and PCM-only designs, and ambient plus 5 K for the liquid designs (ASM).
- All conductances and the PCM mass are given for 16 cells and scaled with cell count (ASM: the cold plate grows with the module).

| Cooling (per 16 cells) | Coupling (all ASM) |
|---|---|
| Air | G_ca = 0.29 W/K |
| PCM block | 150 g, melts 34–36 °C, 240 kJ/kg, G_cp = 3.1, G_pa = 0.30 W/K |
| Liquid | G_ca = 10 W/K, loop at ambient + 5 K |
| Liquid + foam + PCM (Option 2) | 100 g PCM, 34–36 °C, 240 kJ/kg, G_cp = 60, G_pa = 12 W/K |
| As above with a 47 °C PCM (Option 2b) | melts 45–47 °C, 170 kJ/kg (our guess, pending the supplier datasheet) |

**Hot-cell estimate.** The worst parallel cell carries f times the mean current, so it makes f² times the heat. Its extra rise is (f² − 1) times the module's rise above the sink it rejects heat to:

`T_hot = T_avg + (f² − 1) × max(0, T_avg − T_sink)`

v2 measured the rise from ambient instead of from the sink. For liquid designs, whose sink sits 5 K above ambient, that also multiplied the coolant offset by f², about 1.6 K too conservative. For air and PCM designs the two formulas are identical. The correction moves Option 2b at 40 °C from a 317 s stop to a marginal finish. Section 5.2 shows that this result is fragile.

### 4.4 Cell-to-cell variation, per design

Parallel cells share one voltage, so each carries a current proportional to 1/R. For each design the platform draws every branch resistance 20 000 times. Each draw combines the cell's own resistance with an 8 % spread (ASM) and that design's busbar resistance with a 15 % spread between branches (ASM). The worst-cell factor f is the 95th percentile. The random generator is seeded and identical in Python and JavaScript, so both engines get the same f.

| Cell, busbar, NP | Mean | p95 (used) | p99 |
|---|---|---|---|
| P28A, nickel, 4P | 1.078 | 1.151 | 1.195 |
| P28A, Cu-Ni, 4P | 1.083 | 1.163 | 1.211 |
| P28A, Cu-Ni, 5P | 1.095 | 1.178 | 1.229 |

Two findings went against our intuition:
- The low-resistance copper busbar slightly *worsens* current sharing. With less busbar resistance in series, the cell-to-cell spread dominates.
- More parallel cells also raise f: there are more chances for one strong cell.

Even so, adding a fifth cell lowers the worst-branch current from 40.7 A to 140 / 5 × 1.178 = 33.0 A, below the 35 A rating (CALC).

### 4.5 Protection and sensing

- Front end: TI BQ769x0 family, chosen by series count (C8): BQ76920 for 3–5 cells, BQ76930 for 6–10, BQ76940 for 9–15 (DS). Hardware OV, UV, OCD and SCD protection with programmable delays.
- Overcurrent threshold (C11). The highest OCD threshold is 100 mV across the sense resistor, with ±10 % scale error and 2.5 mV offset (DS). The check is `peak × 1.1 × R_shunt + 2.5 mV ≤ 100 mV`:
  - Standard 0.5 mΩ shunt: 80 mV, which fits.
  - Low-loss 0.25 mΩ shunt: 41 mV, which fits.
  - A 1.5 mΩ shunt would need 234 mV, so the chip would trip on an ordinary burst (a v2 finding).
- Dissipation at 140 A (C4):
  - Standard path, 0.5 mΩ shunt plus 1.0 mΩ FETs: 140² × 0.0015 = 29.4 W. This fails the 15 W budget.
  - Low-loss path, four parallel FETs per direction plus a 0.25 mΩ shunt (0.75 mΩ in total, ASM): 140² × 0.00075 = 14.7 W. This passes, but only just. It adds 10 g and ₹760 (ASM).

### 4.6 Balancing

For a 5 % imbalance in one series group (0.05 × NP × Q):

| Method | Current | 4P time | 5P time | Heat | Energy dissipated (4P) |
|---|---|---|---|---|---|
| Passive bleed | 75 mA (50–100 mA range, ASM) | 7.5 h | 9.3 h | 0.31 W | 2.2 Wh |
| Active inductive (ETA3000) | 1 A planning value (2 A vendor peak) | 0.56 h | 0.70 h | 0.31 W | 0.17 Wh |

v2's table listed the active balancer's heat as 0.17 W. That figure was the energy column; the heat is 1 A × 3.9 V × 8 % loss = 0.31 W. No requirement depends on balancing time, which is why R-B can drop active balancing to pay for the low-loss BMS. A drone module that is balanced overnight loses nothing.

### 4.7 Charging

Constant current to 80 %, then a 0.5 h constant-voltage taper (ASM, ±20 %). At 1C that is 0.8 h + 0.5 h = 1.30 h for every design. Cooling matters at fast charge: during the 2C constant-current phase the baseline rises 17.9 K, the PCM block 12.5 K, and the liquid designs 6.0 K.

Rule C5 checks the hot cell at the end of a 1C charge on a 40 °C day against the cell's own charge window. For the P28A (limit 60 °C) every design passes with 45–49 °C. For the P42A (limit 45 °C) the liquid designs reach 45.6 °C, so it fails. That is a cell-specific conflict that a single-cell spreadsheet would not show.

### 4.8 Geometry

Cells stand in the squarest grid that fits N (4 × 4 for 16, 5 × 4 for 20). The cell pitch is the diameter plus 1.5 mm (ASM). Layers on top of the cells: 4 mm busbar and holder at each end, plus a 12 mm BMS board (ASM). Liquid designs add two 6 mm cold plates and 2 mm walls; air designs have 1.5 mm holder rims. The PCM block of Option 1 sits on one side, sized at 0.77 g/cm³ (molten paraffin) plus a 20 % container (ASM). For foam and PCM between the cells, the free volume is the grid volume minus the cells, times 90 % foam porosity (ASM). Anything that does not fit becomes a layer on top, and C12 warns.

Check by hand for 16 P28A cells: the grid is 4 × 20.1 mm by 4 × 20.1 mm by 65.2 mm, which is 421.5 cm³. The cells take 16 × π × 0.93² × 6.52 = 283.4 cm³. The gaps are therefore 138.1 cm³, and 90 % of that is 124.3 cm³. 100 g of molten PCM needs 100 / 0.77 = 129.9 cm³, so 5.6 cm³ does not fit (CALC).

### 4.9 Mass and cost

Small-quantity list prices in US dollars, converted at ₹95 per USD (both ASM, ±30 %); the rate is close to the mid-2026 market rate of about ₹95–96.5. Costs are reported in rupees. Items that scale with cell count (holders, busbar, cold plates, enclosure, PCM, foam) are given per 16 cells. Pump, radiator and reservoir (310 g, ₹3,325) belong to the vehicle and are shown separately.

| Item | Baseline | Opt 1 | Opt 2 / 2b | Abl 2a | R-B |
|---|---|---|---|---|---|
| Cells | 736 g, ₹6,840 | 736 g, ₹6,840 | 736 g, ₹6,840 | 736 g, ₹6,840 | 920 g, ₹8,550 |
| Holders | 60 g, ₹380 | 60 g, ₹380 | | | |
| Busbar | Ni 30 g, ₹475 | Ni 30 g, ₹475 | Cu-Ni 55 g, ₹1,330 | Cu-Ni 55 g, ₹1,330 | Cu-Ni 69 g, ₹1,663 |
| Wiring and connector | 90 g, ₹1,140 | 90 g, ₹1,140 | 90 g, ₹1,140 | 90 g, ₹1,140 | 90 g, ₹1,140 |
| BMS | 45 g, ₹1,710 | 45 g, ₹1,710 | 45 g, ₹1,710 | 45 g, ₹1,710 | low-loss 55 g, ₹2,470 |
| PCM (+ container / foam) | | 200 g, ₹950 | 123 g, ₹1,425 | | |
| ETA3000 × 3 | | | 15 g, ₹1,235 | 15 g, ₹1,235 | |
| Cold plates, coolant, enclosure | | | 260 g, ₹3,705 | 260 g, ₹3,705 | 300 g, ₹4,394 |
| **Module** | **961 g, ₹10,545** | **1161 g, ₹11,495** | **1324 g, ₹17,385** | **1201 g, ₹15,960** | **1434 g, ₹18,216** |

Each item is rounded to the rupee; the module total is rounded once from the exact sum. That is why the R-B column adds up to ₹18,217 against a total of ₹18,216.

---

## 5. Results

Every number here comes from `bess_platform.py` v3.0. The files are `results.json` for the five reference designs, `results_design_space.json` for section 5.5 and `results_recommended.json` for 5.6 and 5.7.

### 5.1 Reference designs (all 4S4P P28A)

| | Baseline | Option 1 | Option 2 | Option 2b | Ablation 2a |
|---|---|---|---|---|---|
| Busbar | nickel | nickel | nickel-clad Cu | nickel-clad Cu | nickel-clad Cu |
| Cooling | natural air | 150 g PCM (35 °C) | liquid + foam + 100 g PCM (35 °C) | as Option 2, 47 °C PCM | liquid only |
| Balancing | passive | passive | active | active | active |

### 5.2 Mission M1

| | Baseline | Option 1 | Option 2 | Option 2b | Ablation 2a |
|---|---|---|---|---|---|
| 25 °C: run time | 130 s | 203 s | 600 s | 600 s | 600 s |
| Stopped by | 60 °C | 60 °C | low voltage | low voltage | low voltage |
| Energy delivered | 37 Wh | 54 Wh | 143 Wh | 143 Wh | 143 Wh |
| Hot cell, maximum | 60.0 °C | 60.0 °C | 44.4 °C | 50.4 °C | 51.7 °C |
| 40 °C: run time | 58 s | 77 s | 312 s | 600 s | 310 s |
| 40 °C: energy | 20 Wh | 25 Wh | 83 Wh | 145 Wh | 83 Wh |
| 40 °C: stopped by | 60 °C | 60 °C | 60 °C | low voltage (59.96 °C peak) | 60 °C |
| End of life, 25 °C: run time | 78 s | 115 s | 471 s | 472 s | 472 s |
| End of life: energy | 23 Wh | 32 Wh | 109 Wh | 110 Wh | 110 Wh |

What this table shows:

- At 25 °C the liquid designs meet R3 and R5. The 143 Wh is 89 % of the 161 Wh nominal; the rest is lost as voltage sag. All three stop at exactly 600 s because the third burst starts then and pulls the voltage below 2.5 V per cell. The mission is defined as "until a limit trips", so this is the mission's length for this pack, not a fixed target.
- At 40 °C, Option 2 and 2a stop at the limit around 310 s. Option 2b's 47 °C PCM still has latent capacity when the 35 °C PCM is already molten, and it finishes. But the hot cell peaks 0.04 K below the limit. The checker therefore reports MARGINAL: inside the 3 K model uncertainty, never shown as PASS. Its 170 kJ/kg latent heat is our own guess. We do not rely on this result.
- **At end of life every 4S4P design fails R11.** The liquid designs run 471–472 s against the 480 s requirement: 20 % less capacity runs out just before the third burst. v2 did not check end of life, so it recommended a module that would stop meeting its own requirement as it aged.

### 5.3 Derating, constant current, ageing

Largest scale k on the whole mission (burst 140·k, base 60·k) that keeps the hot cell below the limit at 40 °C:

| | Baseline | Option 1 | Option 2 | Option 2b | Ablation 2a |
|---|---|---|---|---|---|
| k, below 60 °C | 0.24 | 0.27 | 0.88 | 1.00 | 0.86 |
| k, with 3 K margin | 0.21 | 0.24 | 0.79 | 0.80 | 0.77 |
| Max constant current, 25 °C | 23 A | 44 A | 98 A | 109 A | 96 A |
| Max constant current, 40 °C | 16 A | 19 A | 68 A | 68 A | 67 A |
| P1, 140 A constant | 44 s / 23 Wh | 47 s / 24 Wh | 132 s / 65 Wh | 96 s / 48 Wh | 66 s / 34 Wh |

Ageing index: mean cell temperature, doubling per 10 K, relative to 25 °C (ASM). It is only comparable between designs that finish the mission:

| Option 2 | Option 2b | Ablation 2a | R-B (4S5P) |
|---|---|---|---|
| 2.23 | 2.69 | 2.75 | 2.25 |

The fifth parallel cell lowers the index about as much as adding the PCM does. It is a relative figure, not a life prediction.

### 5.4 Charging, balancing, mass, cost, size

| | Baseline | Option 1 | Option 2 | Ablation 2a |
|---|---|---|---|---|
| Charge time at 1C | 1.30 h | 1.30 h | 1.30 h | 1.30 h |
| Rise during 2C CC phase | 17.9 K | 12.5 K | 6.0 K | 6.0 K |
| Time to balance 5 % | 7.5 h | 7.5 h | 0.56 h | 0.56 h |
| Module mass | 961 g | 1161 g | 1324 g | 1201 g |
| Module cost | ₹10,545 | ₹11,495 | ₹17,385 | ₹15,960 |
| Envelope | 83 × 83 × 85 mm | 116 × 83 × 85 mm | 96 × 84 × 86 mm | 96 × 84 × 85 mm |
| Volume | 0.59 L | 0.83 L | 0.70 L | 0.69 L |
| Nominal Wh/kg, Wh/L | 168, 272 | 139, 195 | 122, 230 | 134, 233 |

The PCM block costs Option 1 39 % more volume than the baseline and buys 17 Wh of mission energy. Liquid cooling costs 17 % more volume and buys 106 Wh.

### 5.5 Design-space exploration: what the checker led us to

All of these use nickel-clad copper busbars, liquid cooling, active balancing and the standard BMS. The only changes are the cell and the parallel count (`configs/design_space.json`):

| | 4S4P P28A | **4S5P P28A** | 4S5P P28A + 47 °C PCM | 4S3P P42A | 4S4P P42A | 4S5P 30Q |
|---|---|---|---|---|---|---|
| 25 °C: energy, run time | 143 Wh, 600 s | 187 Wh, 760 s | 187 Wh, 760 s | 148 Wh, 612 s | 219 Wh, 900 s | 196 Wh, 819 s |
| 40 °C: run time | 310 s | 760 s | 760 s | 297 s | 900 s | 619 s |
| End of life: energy, time | 110 Wh, 472 s | 142 Wh, 600 s | 142 Wh, 600 s | 78 Wh, 314 s | 171 Wh, 719 s | 139 Wh, 600 s |
| k at 40 °C, 3 K margin | 0.77 | 0.96 | 0.99 | 0.67 | 0.88 | 0.88 |
| Mass, cost, volume | 1201 g, ₹15,960, 0.69 L | 1439 g, ₹18,691, 0.84 L | 1592 g, ₹20,473, 0.85 L | 1251 g, ₹13,799, 0.72 L | 1585 g, ₹16,720, 0.95 L | 1479 g, ₹19,641, 0.82 L |
| What fails | R4, R11 | nothing | R6, R7 | R4, R11, C2, C5 | C5, R6 | R4, C2, R7 |

What we learned:

- **A fifth P28A in parallel (R-A) passes every requirement.** It also clears C2, because the worst branch falls to 33.0 A. It adds 238 g and ₹2,731 to design 2a, and it stays under the 1.5 kg and ₹19,000 limits, though only just.
- **The P42A has more energy per cell but is the wrong cell for a 40 °C day.** Its 45 °C charge limit fails C5. As 4S3P it carries 46.7 A per branch against a 45 A rating. As 4S4P it is 85 g over the mass limit.
- **The 30Q is a 15 A cell.** At 140 A over five branches each carries 28 A, so C2 fails outright. This is the kind of mistake the checker exists to catch before anyone orders cells.
- Adding the 47 °C PCM to 4S5P buys almost nothing (k 0.96 to 0.99) and breaks R6 and R7. This repeats v2's ablation lesson: find out which part is doing the work before you pay for it.

### 5.6 Recommended design (R-B)

R-A still carries the C4 warning: 29 W in the BMS at 140 A. R-B swaps in the low-loss power path (+₹760, +10 g) and drops active balancing (−₹1,235, −15 g), which no requirement needs (`configs/recommended.json`):

| | v2 pick (2a, 4S4P) | R-A (4S5P) | **R-B (4S5P, low-loss BMS, passive balancing)** |
|---|---|---|---|
| Nominal | 14.4 V, 11.2 Ah, 161 Wh | 14.4 V, 14.0 Ah, 202 Wh | 14.4 V, 14.0 Ah, 202 Wh |
| 25 °C mission | 600 s, 143 Wh, hot cell 51.7 °C | 760 s, 187 Wh, 45.4 °C | 760 s, 187 Wh, 45.4 °C |
| 40 °C mission | stops at 310 s | finishes, 58.2 °C peak | finishes, 58.2 °C peak (MARGINAL) |
| End of life | 472 s, 110 Wh (FAIL) | 600 s, 142 Wh | 600 s, 142 Wh, 49.8 °C |
| Worst branch at 140 A | 40.7 A (WARN) | 33.0 A | 33.0 A |
| BMS dissipation | 29 W (WARN) | 29 W (WARN) | 14.7 W |
| P1, 140 A constant | 66 s | 120 s | 120 s |
| Balance 5 % | 0.56 h | 0.70 h | 9.3 h |
| Mass, cost (module) | 1201 g, ₹15,960 | 1439 g, ₹18,691 | 1434 g, ₹18,216 |
| Envelope | 0.69 L, 233 Wh/L | 0.84 L, 241 Wh/L | 0.84 L, 241 Wh/L (116 × 84 × 85 mm) |
| Checker | 2 FAIL, 2 WARN | 0 FAIL, 1 WARN, 1 MARGINAL | **0 FAIL, 0 WARN, 1 MARGINAL** |

**Recommendation: build R-B,** on these conditions:

1. **Keep the hot-day derate rule.** At 40 °C the hot cell peaks at 58.2 °C, 1.8 K below the limit. That is inside model uncertainty, so the BMS cuts the burst when the hot-cell estimate passes 55 °C. With a 3 K margin the module still serves 96 % of M1 (k = 0.96).
2. **Specify the radiator from this model.** The average heat on a 40 °C mission is 64.9 kJ over 760 s, which is 85 W (CALC from the run). R-B finishes the 40 °C mission as long as the coolant returns within 5 K of ambient (section 5.7). The vehicle-side loop therefore needs about 85 / 5 = 17 W/K from coolant to air. That is the first item to agree with the vehicle side.
3. **Confirm the low-loss power path on the bench.** It has 14.7 W against a 15 W budget, which is the tightest PASS in the design. Measure the FET and shunt drop at 10–20 A and scale by I².
4. **Close the remaining ASM values with the one-day bench plan (section 9), in the order the uncertainty study gives (5.9):** the radiator offset, then T2 (heating), T5 (cell spread on 30+ cells) and T4 (pulses). Only the hot-day verdict is uncertain, and these four inputs drive it.
5. **Add active balancing back as an option** if the module will be cycled several times a day, so that the 9.3 h passive balance never catches up. The cost is ₹1,235 and 15 g.
6. Do not use air cooling, the PCM block, the P42A in a 40 °C application, or any 15 A cell for this mission.

### 5.7 How much the conclusions depend on the two riskiest assumptions

Coolant return above ambient (all other values at their base):

| Offset | 0 K | 2 K | 3 K | 5 K (base) | 8 K |
|---|---|---|---|---|---|
| v2 pick 2a: 40 °C run time | 600 s | 317 s | 315 s | 310 s | 304 s |
| v2 pick 2a: k with 3 K margin | 0.88 | 0.85 | 0.82 | 0.77 | 0.63 |
| **R-B: 40 °C run time** | 760 s | 760 s | 760 s | 760 s | **319 s** |
| R-B: k with 3 K margin | 1.00 | 1.00 | 1.00 | 0.96 | 0.84 |

Worst-cell current factor:

| Factor | 1.00 | 1.10 | 1.15 | 1.20 |
|---|---|---|---|---|
| 2a: 25 °C hot cell | 46.0 °C | 49.4 °C | 51.2 °C | 53.1 °C |
| 2a: k with 3 K margin | 0.88 | 0.82 | 0.78 | 0.75 |
| R-B: 25 °C hot cell | 41.1 °C | 43.4 °C | 44.7 °C | 46.0 °C |
| R-B: k with 3 K margin | 1.00 | 1.00 | 0.98 | 0.94 |

R-B's 25 °C verdict and its end-of-life verdict hold across both sweeps. Its 40 °C verdict holds up to a 5 K coolant offset and fails at 8 K. That is why the radiator specification is condition 2. The current factor matters less for R-B than for 2a, because the fifth cell lowers every branch current.

### 5.8 Automatic design search

`python3 bess_platform.py --search` (or the dashboard panel) checks every combination at 4S: 3 cells × 4 parallel counts (3–6) × 2 busbars × 5 cooling options × 2 balancing methods × 2 BMS power paths, which is 480 designs. Each one runs the mission at 25 °C, at 40 °C and at end of life, plus every rule.

| Rule | Designs it rules out (of 480) |
|---|---|
| R4, hot day | 336 |
| R11, end of life | 308 |
| C2, branch current | 240 |
| C5, charge window at 40 °C | 224 |
| R3, 25 °C temperature | 216 |
| R6, mass | 210 |
| R5, mission energy | 200 |
| C9, PCM melt point | 192 |
| R12, volume | 168 |
| R7, cost | 129 |

**7 designs meet every requirement, and all 7 are 4S5P P28A with liquid cooling.** They differ only in busbar, balancing and BMS path. Four of them carry the C4 warning (standard BMS), which leaves three clean designs. Two of those form the trade-off front on cost, mass and 40 °C margin:

| Front design | Cost | Mass | 40 °C margin |
|---|---|---|---|
| R-C: 4S5P P28A, **nickel** busbar, liquid, passive balancing, low-loss BMS | ₹17,148 | 1403 g | 0.8 K |
| **R-B**: 4S5P P28A, **Cu-Ni** busbar, liquid, passive balancing, low-loss BMS | ₹18,216 | 1434 g | 1.8 K |

The third clean design (Ni, active balancing) costs more than R-C with the same margin, so it is dominated. The search therefore confirms that the choice we reached by hand in 5.5–5.6 is one of only two efficient designs. It also leaves one question open: is R-B's extra 1 K of margin worth ₹1,068? Section 5.9 answers it.

### 5.9 How sure are we? Uncertainty propagation

A single run says pass or fail at the base assumptions. To see how robust that is, `--uq` draws all eleven uncertain inputs at random, uniformly within these ranges:
- coolant offset 3–7 K
- conductance scale 0.75–1.25
- cell resistance ±10 %
- temperature slope 0.010–0.020 /K
- soc_gain 0.3–0.9
- R_p 5–11 mΩ
- τ 20–40 s
- heat capacity 850–1050 J/kg·K
- busbar resistance: Cu-Ni 0.5–1.2 mΩ, nickel 2–4 mΩ
- cell spread 5–11 %

It then re-runs the mission at 25 °C, at 40 °C and at end of life, 300 times. The sampling is seeded, so the results repeat, and they are identical in the dashboard.

| Probability of passing | v2 pick (2a, 4S4P) | R-C (Ni, front) | **R-B (Cu-Ni, front)** |
|---|---|---|---|
| R3, 25 °C | 99 % | 100 % | 100 % |
| R5, energy | 99 % | 100 % | 100 % |
| R11, end of life | 3 % | 100 % | 100 % |
| R4, finishes the 40 °C mission | 7 % | 64 % | **79 %** |
| R4 with 3 K margin | 0 % | 13 % | 32 % |
| All four | 0.7 % | 64 % | **79 %** |

For R-B, the 40 °C hot-cell peak is 54.8 / 58.1 / 60.1 °C at the 5th / 50th / 95th percentile. The 25 °C mission energy is 184–189 Wh (5th–95th percentile).

What the study adds:
- **The copper busbar buys 15 percentage points of hot-day confidence for ₹1,068.** That decides between the two front designs, and it is why R-B stays the recommendation.
- **Only the hot-day result is genuinely uncertain.** The 25 °C, energy and end-of-life verdicts hold in every sample.
- **It ranks the tests by how much they would tell us.** The inputs most correlated with the 40 °C peak are coolant offset (+0.53), cooling conductance (−0.47), cell spread (+0.45), polarization resistance (+0.37) and temperature slope (−0.33). So the first evidence to collect is the radiator test, then T2 (heating), T5 (cell spread, 30+ cells) and T4 (pulses). Section 9 orders the bench day accordingly.

---

## 6. Conflict and limit checker

The checker runs after every simulation and every dashboard change.

| ID | Rule | Limit | Level |
|---|---|---|---|
| C1 | Hot-cell temperature during the mission (R3, R4) | below the cell limit (60 °C here) | FAIL |
| C1a | Hot cell within 5 K of the limit | derate | shown as the derate line and t55 |
| C1b | Margin to the limit below 3 K | inside model uncertainty | MARGINAL, never shown as PASS |
| C2 | Branch current at the burst | mean above rating: FAIL; worst (p95) above rating: WARN | FAIL or WARN |
| C3 | Cell voltage inside the window | 2.5–4.2 V | enforced as the cutoff |
| C4 | BMS FET and shunt dissipation | at most 15 W | WARN |
| C5 | Cell inside its datasheet charge window, 1C charge on a 40 °C day | per cell | FAIL or MARGINAL |
| C6 | Charge current above the cell maximum | per cell | FAIL |
| C7 | Model and thermistor disagree | over 5 K for 10 s | FAIL (sensor fault), self-test |
| C8 | A BQ769x0 variant covers NS | 3–15 cells | FAIL |
| C9 | PCM melt window above the design ambient | upper melt point above 40 °C | FAIL |
| C10 | Overall: every requirement and hard rule met | no FAIL anywhere | FAIL / PASS |
| C11 | Sense-resistor voltage at peak against the OCD range | peak × 1.1 × R + 2.5 mV ≤ 100 mV | FAIL |
| C12 | PCM fits in the foam between the cells | molten volume ≤ free volume | WARN |

v3 codes everything except C7. C7 is exercised by the self-test in 6.2 because it needs a live sensor.

### 6.1 Verdicts

| Check | Baseline | Option 1 | Option 2 | Option 2b | Ablation 2a | **R-B** |
|---|---|---|---|---|---|---|
| R3, 25 °C | FAIL | FAIL | PASS | PASS | PASS | PASS |
| R4, 40 °C | FAIL | FAIL | FAIL | MARGINAL | FAIL | MARGINAL |
| R5 | FAIL | FAIL | PASS | PASS | PASS | PASS |
| R11, end of life | FAIL | FAIL | FAIL | FAIL | FAIL | PASS |
| C2, branch current | WARN | WARN | WARN | WARN | WARN | PASS |
| C4, BMS heat | WARN | WARN | WARN | WARN | WARN | PASS |
| C5, charge window at 40 °C | PASS | PASS | PASS | PASS | PASS | PASS |
| C9, PCM above 40 °C | n/a | FAIL | FAIL | PASS | n/a | n/a |
| C12, PCM fits | n/a | n/a | WARN | WARN | n/a | n/a |
| C6, C8, C11, R6, R7, R8, R12 | PASS | PASS | PASS | PASS | PASS | PASS |
| **C10 overall** | FAIL | FAIL | FAIL | FAIL | FAIL | **PASS** |

The checker finds four kinds of problem:
- **Requirements that a design misses:** R4, R11.
- **Conflicts between assumptions inside one subsystem:** a 35 °C PCM at a 40 °C ambient (C9), and a cell's charge window against the climate (C5).
- **Interface conflicts:** cells against busbar against BMS (C2, C4, C11).
- **Mechanical conflicts:** PCM volume against the free space between cells (C12).

### 6.2 Sensor-fault self-test

A thermistor reading 12 K low is injected at 100 s into a simulated Option 2 run. The plausibility check flags it at 109 s, inside the 15 s target of R10. This tests the checker logic only. Until test T2 gives the real model error, a model-against-sensor check could give false alarms, so the first line of detection is a comparison of the two thermistors on each cell group. The model check is a second layer.

### 6.3 Model self-checks

`verify()` runs these on every run. None of them needs bench data.

| Check | Result |
|---|---|
| Thermal node against its closed-form solution (100 W into one conductance) | 41.7432 °C against 41.7424 °C, difference 0.001 K |
| Time step 0.25 s against 0.05 s, design 2a at 25 °C | 143.42 against 143.41 Wh; 51.65 against 51.64 °C |
| Energy balance, 2a: OCV energy minus delivered, against heat | 19.05 against 18.93 Wh, residual 0.12 Wh (the energy still in the polarization branch) |
| Scaling: 4S8P against 4S4P on the same mission | more energy (308 against 143 Wh) and cooler (36.6 against 51.7 °C), as it must be |
| Same inputs twice | identical outputs |
| Python engine against browser engine, 10 designs | 202 numbers within 0.05 % (the remaining difference is the 1 mL rounding of volume), all verdicts identical |
| Same, uncertainty study and 480-design search | identical probabilities, percentiles, pass counts and front |

These show the equations are solved correctly and consistently. Whether they match a real cell is what section 9 is for.

---

## 7. Traceability (recommended design R-B)

| Requirement | Component | Assumption | Model | Result | Evidence still needed |
|---|---|---|---|---|---|
| R1 14.4 V, ≥ 11.2 Ah | 20 × P28A, 4S5P | datasheet capacity | hand calculation | 14.4 V, 14.0 Ah, 202 Wh | datasheet; T1 |
| R2, C2 140 A peak | Cu-Ni busbar, 5 branches | 8 % cell spread, 15 % branch spread | Monte Carlo, C2 | factor 1.178, worst 33.0 A, PASS | T5 on 30+ cells |
| R3 < 60 °C at 25 °C | liquid cold plates | G, sink + 5 K, factor | thermal model | 45.4 °C, PASS | T2 |
| R4 < 60 °C at 40 °C | liquid loop, derate rule | sink at ambient + 5 K | thermal model, derate sweep | 58.2 °C, MARGINAL; k = 0.96 with 3 K margin | T3; radiator test at 85 W |
| R5 ≥ 100 Wh, 480 s | cells, busbar | R(T, SOC), polarization, OCV | electrical model | 187 Wh, 760 s | T1, T4 |
| R11 end of life | cells | 80 % capacity, 1.5 × R | electrical + thermal | 142 Wh, 600 s | cycling data or an aged cell |
| R6 ≤ 1.5 kg | BOM | part masses | roll-up | 1434 g | weigh the mock-up |
| R7 ≤ ₹19,000 | BOM | list prices at ₹95/USD, ±30 % | roll-up | ₹18,216 | vendor quotes in rupees |
| R8 ≤ 1.5 h | CC-CV charger | CC to 80 %, 0.5 h CV | charge model | 1.30 h | T6 |
| R9 protection | BQ76920, low-loss FETs, 0.25 mΩ shunt | thresholds in hardware | C4, C11 | 41 mV at peak, 14.7 W | trip-point and FET-drop bench check |
| R10 sensor fault | dual thermistors, model cross-check | 5 K, 10 s | C7 | flagged at 109 s | T7 |
| R12 ≤ 1.0 L | 5 × 4 grid, cold plates, enclosure | 1.5 mm gap, 6 mm plates, 2 mm walls | geometry | 0.84 L, 116 × 84 × 85 mm | measure the mock-up |

`results*.json` hold this table for every design, with each line marked `datasheet`, `uncalibrated (ASM)` or `calibrated`. The dashboard shows it live for design A.

---

## 8. Safety approach

This is a design aid and a checklist, not a certification claim.

Hazards covered: over-temperature (a hot cell above 60 °C speeds ageing and cuts margin), over-current, over- and under-voltage, charging outside the cell's window, and sensor failure. Thermal runaway is not simulated. Self-heating in NMC cells can start somewhere between roughly 80 and 130 °C depending on the cell and its state of charge, so 60 °C is a limit for ageing and margin in this model, not a runaway threshold. We have not reviewed the P28A abuse data.

ISO 26262 and UAV airworthiness practice are used only for vocabulary. No ASIL is claimed, and the BQ76920 is a commercial part. The module is 14.4 V, so the safe state is open charge and discharge FETs.

| Mechanism | Implementation | Requirement |
|---|---|---|
| Hardware OV, UV, OC, short circuit | BQ76920 thresholds with FET drive; C11 confirms the OCD range | R9 |
| Over-temperature disconnect | two thermistors per cell group, trip at 60 °C, hard limit 65 °C | C1 |
| Derating | cut the burst when the hot-cell estimate passes 55 °C, by the k in 5.6 | C1a |
| Charge inhibit | no charge outside the cell's charge window (0–60 °C for the P28A) | C5 |
| Sensor plausibility | thermistor against thermistor first, model against thermistor second | C7 |
| Safe state | FETs open, latched until manual reset | R9 |

A simulation can raise a warning or ask for derating. The independent hardware protection is the safety layer. Bench safety is in `bench/BENCH_TEST_GUIDE.md`: one cell at a time, at most 5 A, fire-resistant tray, fuse, thermal cut-out, never unattended.

---

## 9. Validation and calibration

### 9.1 Plan

The model is only as good as its calibration. None of these tests has been run yet. All of them use one cell at a time at 5 A or less, plus 10 A through a busbar strip only.

| Test | Procedure | Calibrates | Pass criterion |
|---|---|---|---|
| T1 Capacity and OCV | 0.2C discharge, 4.2 to 2.5 V | Q_cell, OCV table | Ah within ±5 % of datasheet |
| T2 Heating | 5 A for 10 min in still air, then 10 min rest | cp_cell (G of one cell for reference) | replay within ±2 K |
| T3 Ambient | T4 at 50 % SOC after a 1 h soak at ≥ 35 °C | R_T_slope | uncertainty under 30 % |
| T4 Pulses | three 5 A × 30 s pulses and one 2 A pulse, at 100, 50, 20 and 10 % SOC, 10 samples/s | R25, R_p, τ, soc_gain | voltage replay within 20 mV during rests |
| T5 Spread and busbar | DC resistance of every cell; mV drop of each branch strip at 10 A | cell_sigma, R_ic | 30+ cells; ±20 % between branches |
| T6 Charge | one CC-CV log at 1C | CC fraction, CV taper | within ±20 % |
| T7 Sensor fault | unplug or bias a thermistor during T2 | C7 | flagged within 15 s |

Heat scales with I²R, so a 5 A test makes about 2 % of the heat of a 35 A one. The tests calibrate the model's structure (R, C, R_p, τ), and the calibrated values are then used at full current. That extrapolation is a stated limitation.

### 9.2 Pipeline

`calibrate.py` reads the CSV logs (format in the guide) and fits each parameter from its test. Then it **replays each test with the fitted model** and checks the pass criterion. Only parameters that pass, and whose statistical uncertainty is acceptable, are written to `calib.json`. Passing that file to `bess_platform.py` or loading it in the dashboard replaces those values, and every result and trace line that depends on them changes from "uncalibrated (ASM)" to "calibrated".

The estimators:
- **R0:** extrapolate one second of samples on each side of every current step to the step instant.
- **R_p and τ:** a three-parameter least-squares fit of each relaxation.
- **soc_gain:** from the low-SOC pulses, using the SOC at each step.
- **Temperature slope:** the ratio of R0 at the two ambients.
- **Heat capacity:** a Nelder–Mead fit of the heating-and-cooling curve.
- **OCV:** V + I·(R0 + R_p) along the 0.2C discharge, as a local straight-line fit at each table point.

### 9.3 Checking the pipeline before real data exists

`make_synthetic.py` writes bench files in the exact format from a single-cell model whose "true" values are hidden and differ from our assumptions, with logger-like noise (2 mV, 10 mA, 0.2 K). **These are synthetic files, not measurements.** `calibrate.py` recovered:

| Parameter | True | Fitted | Error |
|---|---|---|---|
| Q_cell | 2.72 Ah | 2.720 Ah | 0.0 % |
| R25 | 21.5 mΩ | 21.7 mΩ | +1.1 % |
| R_p | 6.5 mΩ | 6.47 mΩ | −0.5 % |
| τ | 24 s | 23.8 s | −0.7 % |
| soc_gain | 0.45 | 0.433 | −3.7 % |
| cp_cell | 1020 J/kg·K | 1021 J/kg·K | +0.1 % |
| R_T_slope | 0.012 /K | 0.0134 /K | +11.5 % (±0.0009 from a 10 K gap) |
| R_ic, nickel | 2.6 mΩ | 2.26 mΩ | −13 % (4 branches) |
| cell_sigma | 6 % | 5.9 % | −1 %, but held back: 16 cells give ±18 % |
| OCV table | | | at most 2 mV at 10 points |

The check paid for itself. The first version of the script overestimated τ by 38 %, because a fit on the logarithm of a noisy decay is biased. It also overestimated soc_gain by 33 %, because SOC falls during the 10 % SOC pulses. Both are fixed. The check also set the procedure: repeat each pulse three times, use a wide temperature gap for T3, and measure 30 or more cells for the spread. What it cannot show is that the model structure fits a real P28A. Only the bench day can show that.

### 9.4 Minimum evidence before any test

Compare the model's discharge voltage with the P28A datasheet curves at 1C, 10 A and 30 A. A non-live mock-up with inert cells (5 × 4 grid, two cold plates, BMS position) checks the 116 × 84 × 85 mm envelope and the mass roll-up. It shows geometry only.

### 9.5 External evidence: the model against published P28A data

This is not our own measurement. It is the best evidence available before the bench day, and it compares the model with published numbers that we did not tune to. `python3 bess_platform.py --evidence` runs it: a single bare cell in still air (G = 0.06 W/K, ASM), discharged at constant current to 2.5 V.

| Condition | Published | Model | Reading |
|---|---|---|---|
| 0.56 A, 23 °C | **2.745–2.787 Ah measured on four cells** (independent test, source 19); spec minimum 2.70 Ah | 2.800 Ah | within 0.5–2 % of measurement |
| 2.8 A, 23 °C | spec minimum 2.60 Ah | 2.800 Ah | above minimum |
| 10 A, 23 °C | spec minimum 2.55 Ah | 2.800 Ah | above minimum; **no rate-capacity loss in the model** |
| 15 A / 20 A, 23 °C | spec minimum 2.50 Ah | 2.800 Ah | as above |
| 2.8 A, 45 °C | spec minimum 2.60 Ah | 2.800 Ah | above minimum |
| 2.8 A, 0 °C | spec minimum 2.10 Ah | 2.800 Ah | **the model has no cold-capacity loss: do not use it below about 15 °C until calibrated** |
| 30 A, still air | an independent reviewer stopped his test because the cell got hot (source 20) | the cell passes 100 °C | qualitatively consistent; T2 sets the number |

The comparison exposes two real gaps:
- The generic OCV table has no knee below 0 % SOC, so the model gives the full rated capacity at any current.
- It has no low-temperature capacity loss.

Neither is visible from inside the model, and both are what T1 and T4 calibrate. In the meantime we bound the first gap with the manufacturer's own guarantee: we re-ran the finalists with every cell at the **specified minimum of 2.50 Ah** instead of 2.8 Ah.

| Cells at 2.50 Ah (spec minimum) | 25 °C mission | 40 °C mission | End of life | R5 | R11 |
|---|---|---|---|---|---|
| v2 pick (2a, 4S4P) | 546 s, 131 Wh | stops at 311 s | 416 s, 98 Wh | PASS | **FAIL** |
| **R-B (4S5P)** | 670 s, 167 Wh | finishes, 59.0 °C peak | 541 s, 128 Wh | PASS | **PASS** |

The recommendation survives the manufacturer's worst-case capacity. The hot-day margin shrinks to 1 K, which is why the radiator specification and the derate rule are conditions.

Ageing anchor: the specification guarantees at least 80 % capacity after 500 cycles at 10 A and 23 °C, and a review of the spec quotes 400 cycles to 80 % at 20 A (source 18). The R11 end-of-life scenario (80 % capacity) therefore corresponds to roughly 400–500 such cycles. R-B still meets R5 there; the v2 pick does not.

---

## 10. User value and business viability

### 10.1 What the user gets

- **Mistakes caught before parts are ordered.** In this study alone the checker found:
  - a reference design that fails at end of life (R11)
  - a PCM that does not fit the space it was drawn into (C12)
  - a cell whose charge window cannot handle a 40 °C day (C5)
  - a 15 A cell proposed for a 28 A branch (C2)
  - a BMS power path that cooks itself at 29 W (C4)
  - a shunt that would have defeated the BMS overcurrent range (C11, from v2)

  Building and testing one wrong module costs its bill of materials (₹10,545–₹20,473 here) plus days of build and test. Discovering R11 after the cells have aged costs a redesign.
- **Exploring the design space in seconds.** Six cell and layout variants ran from one 20-line JSON file in about 10 s. All 480 combinations run in about 14 s in Python and about 2 s in the browser. In the browser, both designs recompute in about 0.25 s.
- **Confidence, not just pass or fail.** The uncertainty study says how likely each verdict is, and which test would most reduce the doubt. A team can spend its one bench day where it matters.
- **Reviewable decisions.** Every number traces to a requirement, an assumption and the test that would confirm it, and each is tagged DS, ASM or calibrated.
- **A path from assumption to evidence for about one day of bench work** with student-lab equipment (section 9).

### 10.2 Market context

These figures are context, not our addressable market:
- India's battery management system market was about USD 278–282 million in 2024. Forecasts put growth at about 18–20 % a year, reaching about USD 700 million by 2029 (sources 10, 11).
- India is the third-largest EV ecosystem by number of companies, after the US and China (source 12).
- Student EV design is growing fast. The 2026 eBAJA physical round had 90 electric teams, up from 8 in its first year (sources 13, 14).

The comparable commercial tool is MATLAB with Simscape Battery. Its academic annual licence lists MATLAB at USD 330 and Simscape Battery at USD 330 (about ₹31,350 each at ₹95/USD), and Simscape Battery also needs Simulink and Simscape (sources 15, 16). Open-source solvers such as PyBaMM are free. So paid value has to come from the workflow (checker, traceability, calibration, browser access), not from the solver.

### 10.3 Offer

| Tier | Who | What | Price |
|---|---|---|---|
| Free | students, teaching | engine, dashboard, cell library, configs, calibration scripts | free, open source |
| Team | student and research teams | saved projects, PDF design-review export, shared assumption libraries | hypothesis: ₹10,000–20,000 per team per year |
| Start-up seat | early-stage battery, drone, EV firms | the above plus extended cell library and pack-level models (next step) | hypothesis: ₹28,500–57,000 (USD 300–600) per seat per year, under one academic MATLAB + Simscape Battery seat |
| Calibration service | anyone | customer sends cells or logs, we return a calibrated model and a report | hypothesis: ₹25,000 per cell type |

Costs are low: a static web page with no server compute, and Python that runs on the user's laptop. The prices above are **hypotheses to test, not findings.** `INTERVIEW_KIT.md` holds the Van Westendorp questions that will test them.

### 10.4 How we will test the idea

| Step | Method | Proceed if |
|---|---|---|
| 1. Problem | 10–15 interviews with student teams and start-up engineers (`INTERVIEW_KIT.md` part 1) | at least 6 describe the separate-spreadsheet, found-out-too-late problem unprompted |
| 2. Usability | 5 users, five timed tasks on the dashboard (part 2) | median under 15 minutes to a passing design, without help |
| 3. Willingness to pay | Van Westendorp with the interviewees (part 3) | the acceptable range overlaps the hypothesis in 10.3 |
| 4. Calibration pilot | one team runs the bench day and `calibrate.py` | every written parameter meets its section 9 criterion |

**Status: not started.** We report only real counts when it is done.

### 10.5 Cost against performance

| Against the baseline | Cost | Mass | Volume | 25 °C mission energy | Hot day | End of life |
|---|---|---|---|---|---|---|
| R-B | +73 % | +49 % | +41 % | 5.1 × (187 against 37 Wh) | finishes (MARGINAL) | passes |

The baseline cannot finish the mission at all, so the extra cost buys the ability to do the job, including on a hot day and at end of life. Against the v2 pick (2a), R-B costs ₹2,256 and 233 g more, and it is the first design that passes every requirement.

### 10.6 Scaling

1. **Module to pack.** NS up to 15 already selects the right BQ769x0. A 96S pack needs isolation, creepage and contactor models, which this version does not have.
2. **New cells.** A new cell is one entry in the library: datasheet values with tags and a source.
3. **Thermal detail.** The model can go from lumped to per-cell nodes, which would let the Monte Carlo place the hot cell on the plate.
4. **Integration.** Today it exports JSON and markdown. FMU export for co-simulation is a later step.

---

## 11. Limitations, risks, next steps

Limitations:

1. The thermal model is lumped. Temperature differences between cells come from the Monte Carlo current factor, not from geometry.
2. Resistance, polarization, heat capacity, PCM data, convection, coolant coupling and the end-of-life factors are all ASM until section 9 is done. Absolute temperatures may be off by several kelvin. Rankings and trends are more reliable than absolute values, and the MARGINAL band exists for this reason.
3. The 40 °C conclusion depends on the coolant offset (section 5.7). No radiator has been sized; 5.6 states the needed 17 W/K.
4. Low-current tests calibrate the structure, and the jump to 28–35 A per cell relies on I²R scaling.
5. Geometry is an envelope estimate. Cold plates on two faces may not reach the inner cells as the lumped model assumes. The 3D views draw that geometry. The colours show the lumped model's two temperatures, the hot cell and the module average. They are not a per-cell thermal map, and which cell is drawn as the hot one is illustrative.
6. Costs are small-quantity retail, ±30 %. Two cell prices and the low-loss BMS cost are assumptions.
7. The ageing index is relative and temperature-only. End of life is a fixed 80 % / 1.5 × scenario, not a degradation model.
8. The 47 °C PCM latent heat (170 kJ/kg) is a guess. PCM leakage, foam compatibility and pump reliability are not modelled.
9. The mission and R4–R8, R11, R12 are our assumptions.
10. The generic OCV table has no knee below 0 % SOC, and the model has no low-temperature capacity loss, so it gives full capacity at any current and temperature (found in 9.5). The finalists are re-checked at the specification's minimum capacity, but below about 15 °C the model should not be used until T1 and T4 are done.
11. Every result is simulated, synthetic, or checked against published data only. No bench measurement of our own and no user interview has been made yet.

| Risk | Impact | Mitigation |
|---|---|---|
| Hot-day margin is only 1.8 K | mission derated on hot days | derate rule at 55 °C; radiator spec of 17 W/K at ≤ 5 K offset; T3 |
| Coolant offset above 5 K | mission stops at about 320 s at 40 °C | radiator test before release; the checker re-runs with the measured offset |
| Low-loss BMS path at 14.7 W against 15 W | FET overheating | bench FET-drop check; heat-sink the FETs to the cold plate |
| Mass 1434 g against 1.5 kg | no headroom for added parts | weigh the mock-up early; the BOM roll-up flags any addition |
| Model assumptions wrong | false confidence | calibration pipeline, uncalibrated flags, MARGINAL band, parity test |
| Model-based sensor check false alarms | nuisance disconnects | two-thermistor comparison first; set the model threshold from T2 error |

Next steps, in order:
1. Run T1, T2 and T4 on one P28A (one day) and recalibrate.
2. Weigh and measure a mock-up.
3. Run the five interviews and five usability sessions.
4. Agree the 17 W/K radiator specification with the vehicle side.
5. Bench-check the low-loss FET drop.

Later: per-cell thermal nodes, a PyBaMM cross-check of the electrical model, and pack-level isolation models.

---

## 12. Sources

Check each against the current manufacturer document before quoting.

1. Molicel, INR-18650-P28A product data sheet (revisions differ on max charge current: 6 A and 8.4 A).
2. Molicel, INR-21700-P42A product data sheet (4.2 Ah, 45 A, 16 mΩ DC at 10 A / 1 s, 70 g max, charge 0–45 °C).
3. Samsung SDI, INR18650-30Q specification v1.0 (15 A, ≤ 26 mΩ AC 1 kHz, 48 g max, max rapid charge 4 A).
4. Texas Instruments, BQ76920/BQ76930/BQ76940 datasheet, SLUSBK2.
5. ETA Solution, ETA3000 inductive active balancer datasheet (vendor claims).
6. Paraffin PCM supplier datasheets, 35 °C and 47 °C classes.
7. Literature on hybrid PCM, metal-foam and liquid battery cooling; passive and active balancing; Bernardi heat generation; lumped thermal models (context).
8. ISO 26262 (vocabulary only).
9. TELIPORT Season 4, Case Study 2.
10. [IMARC Group, India Battery Management System Market](https://www.imarcgroup.com/india-battery-management-system-market): USD 278 million in 2024.
11. [MarketsandMarkets, India Battery Management System Market](https://www.marketsandmarkets.com/Market-Reports/geography/battery-management-bms-market/India): USD 281.6 million in 2024, USD 699.6 million by 2029.
12. [Business Today, citing Tracxn](https://www.businesstoday.in/amp/entrepreneurship/news/story/ev-start-ups-in-india-record-highest-funding-in-a-decade-sees-a-jump-of-117-369210-2023-02-06): India third by number of EV companies.
13. [Entrepreneur India, BAJA SAEINDIA 2026](https://www.entrepreneurindia.com/blog/en/news/baja-saeindia-2026-begins-at-natrax-with-ev-and-hydrogen-teams.58718): 90 electric teams.
14. [Autocar Professional, eBAJA SAEINDIA 2025](https://autocarpro.in/news/ebaja-saeindia-2025-launches-at-bv-raju-institute-with-record-participation-125051): eight teams when eBAJA started in 2015.
15. [MathWorks store, academic annual licence](https://www.mathworks.com/store/products/academic/annual/ML): MATLAB USD 330, Simscape Battery USD 330.
16. [Humusoft MATLAB price list](https://www.humusoft.cz/docs/cs/matlab-cenik.pdf): Simscape Battery requires Simulink and Simscape.
17. Indian retail listings for the P28A (for example robu.in, hubtronics.in): about ₹460–530 per cell.
18. [Molicel INR-18650-P28A product specification](https://www.nkon.nl/amfile/file/download/file/121/product/3518), section 5.2: minimum capacity 2.70 Ah at 0.56 A, 2.60 at 2.8 A, 2.55 at 10 A, 2.50 at 15 and 20 A; 2.60 Ah at 45 °C and 2.10 Ah at 0 °C (2.8 A); at least 80 % after 500 cycles at 10 A.
19. [Battery Mooch's test, quoted on Budget Light Forum](https://budgetlightforum.com/t/great-promotion-for-vapcell-batteries/56625): four P28A cells delivered 2745–2787 mAh at 560 mA to 2.5 V.
20. [HKJ, Test/review of Molicel INR18650-P28A](https://lygte-info.dk/review/batteries2012/Molicel%20INR18650-P28A%202800mAh%20(Gray)%20UK.html): at 30 A the cell got hot and the test was stopped early; cycle life quoted as 400 cycles to 80 % at 20 A.

---

## Appendix A. Coverage of the case-study key points and criteria

| Key point or criterion | Where |
|---|---|
| Manageable scope | 2.2 |
| Application, requirements, operating conditions | 2.1–2.3 |
| Cells, connections, temperature control, sensing, protection, controls | 4, 6, 8 |
| Mechanical: size, layout, fit | 4.8, R12, C12, dashboard 3D module view |
| Datasheets, calculations, simulation, low-voltage tests | 4, 6.3, 9 (pipeline built and checked; bench day not yet run) |
| At least two options against a baseline | 5.1–5.6 (five references, six variants, two finalists) |
| Indicators: energy, temperature, charge time, mass, size, cost | 5.2–5.6 |
| Cell variation, ageing, operating conditions | 4.4, 5.2 (end of life), 5.7 |
| Assumptions, sources, safety, results, limitations | tags throughout, 8, 11, 12 |
| Prototype or visual demonstration, next step | 3.2, `bess_dashboard.html` (home page with 3D module and mission playback, module checker), 5.6, 11 |
| Configure, visualise, analyse, compare | 3.2, dashboard |
| Parameters shared between subsystem models | 3.1 |
| Interface conflicts, incompatible assumptions, limit violations | 6 |
| Traceability | 7, `results*.json`, dashboard |
| Repeatable results | 6.3, parity test, seeded Monte Carlo, `configs/` |
| Recommending a balanced design with risks stated | 5.6, 5.8 (search and front), 5.9 (probabilities), 9.5 (worst-case capacity) |

## Appendix B. Reproducing the numbers

```
python3 bess_platform.py                                       # five reference designs -> results.json, results_tables.md
python3 bess_platform.py --config configs/design_space.json    # section 5.5
python3 bess_platform.py --config configs/recommended.json     # sections 5.6, 5.7
python3 bess_platform.py calib.json                            # any of the above, with bench values
python3 bess_platform.py --search                              # section 5.8: all 480 combinations
python3 bess_platform.py --config configs/recommended.json --uq "R-B 4S5P low-loss"   # section 5.9
python3 bess_platform.py --evidence                            # section 9.5: model against published P28A data
python3 reproduce.py                                           # re-run every study and compare with the committed results (--quick skips the slow two)
node web/test_parity.js                                        # browser engine against Python engine
python3 web/build_dashboard.py                                 # rebuild bess_dashboard.html from web/
cd bench && python3 make_synthetic.py synthetic && python3 calibrate.py synthetic --out synthetic_calib.json
```

Open `bess_dashboard.html` in any browser. It opens on the home page; `bess_dashboard.html#checker` opens the module checker directly. To rebuild it after changing `web/engine.js` or `web/dashboard_src.html`, run `python3 web/build_dashboard.py`.

## Appendix C. What changed from v2 and why

| Change | Why | Effect |
|---|---|---|
| Hot-cell estimate measured from the sink, not the ambient | v2 multiplied the 5 K coolant offset by 1.32 | liquid designs about 1.3 K cooler; 2b reaches MARGINAL at 40 °C |
| Current factor from a Monte Carlo per design | v2 used one nickel-busbar value (1.15) for every design | Cu-Ni 4P: 1.163; Cu-Ni 5P: 1.178 |
| End-of-life requirement R11 | the brief asks how ageing propagates to the system | every 4S4P design fails |
| Geometry, R12 and C12 | the brief lists size and mechanical | Option 2's PCM does not fit |
| Cell library, NS/NP and config files | the brief asks for a reusable platform | design-space exploration in 5.5 |
| C2 FAIL level, C5, C8 chip selection, C10 coded | rules that v2 described but did not code | the 30Q and P42A conflicts are caught |
| Low-loss BMS option | C4 had no fix in v2 | R-B clears every WARN |
| Active balancer heat corrected to 0.31 W | v2's table quoted the energy figure as heat | table 4.6 |
| Sensitivity sweep coded | v2's section 5.6 numbers were not produced by the script | `sensitivity()` in the engine |
| Dashboard rebuilt as a configurable tool, with a parity test | v2's dashboard had five fixed presets | 3.2, 6.3 |
| Home page and 3D module views | to show the module and its thermal behaviour the way an engineer pictures it | 3.2 |
| Costs in rupees (₹95/USD, ASM); R7 restated as ₹19,000 | the target users and suppliers are in India | 2.3, 4.9; every verdict unchanged |
| Calibration pipeline with a synthetic check | v2 had a test plan but no way to use the data | section 9 |
| Automatic search of 480 designs, with trade-off front | to show the recommendation is not just the best of the few we thought of | 5.8: all 7 passing designs are 4S5P P28A liquid |
| Uncertainty propagation, 300 samples | to turn pass or fail into a probability and to rank the tests | 5.9: R-B 79 % on the hot day, v2 pick 0.7 % overall |
| Comparison with published P28A data | the best external evidence available before our own bench day | 9.5: found two model gaps; R-B still passes at the specified minimum capacity |
