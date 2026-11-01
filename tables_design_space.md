| | 2a 4S4P P28A | 2a 4S5P P28A | 2b 4S5P P28A | 2a 4S3P P42A | 2a 4S4P P42A | 2a 4S5P 30Q |
|---|---|---|---|---|---|---|
| 25 C: run time | 600 s | 760 s | 760 s | 612 s | 900 s | 819 s |
| Stopped by | undervoltage cutoff | capacity exhausted | capacity exhausted | undervoltage cutoff | undervoltage cutoff | undervoltage cutoff |
| Energy delivered | 143 Wh | 187 Wh | 187 Wh | 148 Wh | 219 Wh | 196 Wh |
| Hot cell, maximum | 51.7 C | 45.4 C | 44.6 C | 55.9 C | 46.7 C | 48.0 C |
| First above derate line | never | never | never | 318 s | never | never |
| 40 C: run time | 310 s | 760 s | 760 s | 297 s | 900 s | 619 s |
| 40 C: energy | 83 Wh | 190 Wh | 189 Wh | 76 Wh | 222 Wh | 160 Wh |
| 40 C: stopped by | hot-cell limit | capacity exhausted | capacity exhausted | hot-cell limit | undervoltage cutoff | hot-cell limit |
| End of life, 25 C: run time | 472 s | 600 s | 600 s | 314 s | 719 s | 600 s |
| End of life: energy | 110 Wh | 142 Wh | 142 Wh | 78 Wh | 171 Wh | 139 Wh |
| End of life: hot cell | 58.6 C | 49.8 C | 48.6 C | 60.1 C | 52.4 C | 53.7 C |
| k at 40 C, below limit | 0.86 | 1.00 | 1.00 | 0.78 | 1.00 | 0.99 |
| k at 40 C, 3 K margin | 0.77 | 0.96 | 0.99 | 0.67 | 0.88 | 0.88 |
| Max constant current 25 C | 96 A | 118 A | 134 A | 79 A | 103 A | 108 A |
| Max constant current 40 C | 67 A | 83 A | 84 A | 55 A | 72 A | 76 A |
| P1 140 A: time / energy | 66 s / 34 Wh | 120 s / 63 Wh | 305 s / 150 Wh | 62 s / 31 Wh | 113 s / 59 Wh | 91 s / 47 Wh |
| Current factor (p95) | 1.163 | 1.178 | 1.178 | 1.140 | 1.162 | 1.180 |
| Charge 1C | 1.30 h | 1.30 h | 1.30 h | 1.30 h | 1.30 h | 1.30 h |
| 2C CC rise | 6.0 K | 6.0 K | 6.0 K | 6.9 K | 6.9 K | 6.5 K |
| Hot cell end of 1C CC at 40 C | 45.4 C | 45.4 C | 45.4 C | 45.6 C | 45.6 C | 45.5 C |
| Balance 5 % | 0.56 h | 0.70 h | 0.70 h | 0.63 h | 0.84 h | 0.75 h |
| Module mass | 1201 g | 1439 g | 1593 g | 1251 g | 1585 g | 1479 g |
| Module cost | ₹15,960 | ₹18,691 | ₹20,473 | ₹13,799 | ₹16,720 | ₹19,641 |
| Envelope | 96x84x85 mm | 116x84x85 mm | 116x84x86 mm | 109x74x90 mm | 109x97x90 mm | 116x84x85 mm |
| Volume | 0.69 L | 0.84 L | 0.85 L | 0.72 L | 0.95 L | 0.82 L |
| Wh/kg, Wh/L (nominal) | 134, 233 | 140, 241 | 127, 238 | 145, 251 | 153, 255 | 146, 263 |
| Ageing index | 2.75 | 2.25 | 2.21 | 3.57 | 2.52 | 2.46 |

Verdicts

| Check | 2a 4S4P P28A | 2a 4S5P P28A | 2b 4S5P P28A | 2a 4S3P P42A | 2a 4S4P P42A | 2a 4S5P 30Q |
|---|---|---|---|---|---|---|
| R3 / C1 | PASS | PASS | PASS | PASS | PASS | PASS |
| R4 / C1 | FAIL | MARGINAL | MARGINAL | FAIL | MARGINAL | FAIL |
| R5 | PASS | PASS | PASS | PASS | PASS | PASS |
| R11 | FAIL | PASS | PASS | FAIL | PASS | PASS |
| C2 | WARN | PASS | PASS | FAIL | PASS | FAIL |
| C4 | WARN | WARN | WARN | WARN | WARN | WARN |
| C11 | PASS | PASS | PASS | PASS | PASS | PASS |
| C5 | PASS | PASS | PASS | FAIL | FAIL | PASS |
| C6 | PASS | PASS | PASS | PASS | PASS | PASS |
| C8 | PASS | PASS | PASS | PASS | PASS | PASS |
| R6 | PASS | PASS | FAIL | PASS | FAIL | PASS |
| R7 | PASS | PASS | FAIL | PASS | PASS | FAIL |
| R8 | PASS | PASS | PASS | PASS | PASS | PASS |
| R12 | PASS | PASS | PASS | PASS | PASS | PASS |
| C10 | FAIL | PASS | FAIL | FAIL | FAIL | FAIL |
| C9 | n/a | n/a | PASS | n/a | n/a | n/a |
| C12 | n/a | n/a | WARN | n/a | n/a | n/a |

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
 }
}
```
