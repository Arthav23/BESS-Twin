| | 2a 4S4P (v2 pick) | R-A 4S5P | R-B 4S5P low-loss | R-C 4S5P Ni low-loss |
|---|---|---|---|---|
| 25 C: run time | 600 s | 760 s | 760 s | 760 s |
| Stopped by | undervoltage cutoff | capacity exhausted | capacity exhausted | capacity exhausted |
| Energy delivered | 143 Wh | 187 Wh | 187 Wh | 185 Wh |
| Hot cell, maximum | 51.7 C | 45.4 C | 45.4 C | 46.4 C |
| First above derate line | never | never | never | never |
| 40 C: run time | 310 s | 760 s | 760 s | 760 s |
| 40 C: energy | 83 Wh | 190 Wh | 190 Wh | 188 Wh |
| 40 C: stopped by | hot-cell limit | capacity exhausted | capacity exhausted | capacity exhausted |
| End of life, 25 C: run time | 472 s | 600 s | 600 s | 600 s |
| End of life: energy | 110 Wh | 142 Wh | 142 Wh | 141 Wh |
| End of life: hot cell | 58.6 C | 49.8 C | 49.8 C | 50.7 C |
| k at 40 C, below limit | 0.86 | 1.00 | 1.00 | 1.00 |
| k at 40 C, 3 K margin | 0.77 | 0.96 | 0.96 | 0.92 |
| Max constant current 25 C | 96 A | 118 A | 118 A | 115 A |
| Max constant current 40 C | 67 A | 83 A | 83 A | 80 A |
| P1 140 A: time / energy | 66 s / 34 Wh | 120 s / 63 Wh | 120 s / 63 Wh | 106 s / 55 Wh |
| Current factor (p95) | 1.163 | 1.178 | 1.178 | 1.164 |
| Charge 1C | 1.30 h | 1.30 h | 1.30 h | 1.30 h |
| 2C CC rise | 6.0 K | 6.0 K | 6.0 K | 6.2 K |
| Hot cell end of 1C CC at 40 C | 45.4 C | 45.4 C | 45.4 C | 45.4 C |
| Balance 5 % | 0.56 h | 0.70 h | 9.33 h | 9.33 h |
| Module mass | 1201 g | 1439 g | 1434 g | 1403 g |
| Module cost | ₹15,960 | ₹18,691 | ₹18,216 | ₹17,148 |
| Envelope | 96x84x85 mm | 116x84x85 mm | 116x84x85 mm | 116x84x85 mm |
| Volume | 0.69 L | 0.84 L | 0.84 L | 0.84 L |
| Wh/kg, Wh/L (nominal) | 134, 233 | 140, 241 | 141, 241 | 144, 241 |
| Ageing index | 2.75 | 2.25 | 2.25 | 2.34 |

Verdicts

| Check | 2a 4S4P (v2 pick) | R-A 4S5P | R-B 4S5P low-loss | R-C 4S5P Ni low-loss |
|---|---|---|---|---|
| R3 / C1 | PASS | PASS | PASS | PASS |
| R4 / C1 | FAIL | MARGINAL | MARGINAL | MARGINAL |
| R5 | PASS | PASS | PASS | PASS |
| R11 | FAIL | PASS | PASS | PASS |
| C2 | WARN | PASS | PASS | PASS |
| C4 | WARN | WARN | PASS | PASS |
| C11 | PASS | PASS | PASS | PASS |
| C5 | PASS | PASS | PASS | PASS |
| C6 | PASS | PASS | PASS | PASS |
| C8 | PASS | PASS | PASS | PASS |
| R6 | PASS | PASS | PASS | PASS |
| R7 | PASS | PASS | PASS | PASS |
| R8 | PASS | PASS | PASS | PASS |
| R12 | PASS | PASS | PASS | PASS |
| C10 | FAIL | PASS | PASS | PASS |

```
{
 "sensor_fault_detect_s": 109.0,
 "verify": {
  "thermal_vs_closed_form": {
   "model": 41.74321835199264,
   "exact": 41.74237170857401,
   "err_K": 0.0008466434186260585
  },
  "dt_convergence_2a": {
   "Wh_025": 143.42009222124184,
   "Wh_005": 143.41138606790352,
   "Thot_025": 51.65141504736616,
   "Thot_005": 51.64000235184218
  },
  "energy_balance_2a": {
   "Eoc_minus_delivered_Wh": 19.04569230118841,
   "heat_Wh": 18.928576939267668,
   "residual_Wh": 0.11711536192074234
  },
  "repeatable": true,
  "scaling_4s8p_vs_4s4p": {
   "Wh_4s4p": 143.42009222124184,
   "Wh_4s8p": 308.13830402922804,
   "Thot_4s4p": 51.65141504736616,
   "Thot_4s8p": 36.56159583330181,
   "ok": true
  }
 },
 "sensitivity": {
  "design": "R-B 4S5P low-loss",
  "sink_offset": [
   {
    "offset_K": 0.0,
    "t40": 760.25,
    "Wh40": 189.06015665731434,
    "reason": "capacity exhausted",
    "k3": 1.0
   },
   {
    "offset_K": 2.0,
    "t40": 760.25,
    "Wh40": 189.35658781421049,
    "reason": "capacity exhausted",
    "k3": 1.0
   },
   {
    "offset_K": 3.0,
    "t40": 760.25,
    "Wh40": 189.50202820067412,
    "reason": "capacity exhausted",
    "k3": 1.0
   },
   {
    "offset_K": 5.0,
    "t40": 760.25,
    "Wh40": 189.78746178669311,
    "reason": "capacity exhausted",
    "k3": 0.9554687500000001
   },
   {
    "offset_K": 8.0,
    "t40": 319.0,
    "Wh40": 89.77657168336394,
    "reason": "hot-cell limit",
    "k3": 0.8392700195312499
   }
  ],
  "current_factor": [
   {
    "f": 1.0,
    "Thot25": 41.079227435222975,
    "k3": 1.0
   },
   {
    "f": 1.1,
    "Thot25": 43.4058651966198,
    "k3": 1.0
   },
   {
    "f": 1.15,
    "Thot25": 44.65227828308238,
    "k3": 0.9781982421875001
   },
   {
    "f": 1.2,
    "Thot25": 45.95408750672108,
    "k3": 0.93853759765625
   }
  ]
 }
}
```
