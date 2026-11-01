| | Baseline | Option 1 | Option 2 | Option 2b | Ablation 2a |
|---|---|---|---|---|---|
| 25 C: run time | 130 s | 203 s | 600 s | 600 s | 600 s |
| Stopped by | hot-cell limit | hot-cell limit | undervoltage cutoff | undervoltage cutoff | undervoltage cutoff |
| Energy delivered | 37 Wh | 54 Wh | 143 Wh | 143 Wh | 143 Wh |
| Hot cell, maximum | 60.0 C | 60.0 C | 44.4 C | 50.4 C | 51.7 C |
| First above derate line | 98 s | 140 s | never | never | never |
| 40 C: run time | 58 s | 77 s | 312 s | 600 s | 310 s |
| 40 C: energy | 20 Wh | 25 Wh | 83 Wh | 145 Wh | 83 Wh |
| 40 C: stopped by | hot-cell limit | hot-cell limit | hot-cell limit | undervoltage cutoff | hot-cell limit |
| End of life, 25 C: run time | 78 s | 115 s | 471 s | 472 s | 472 s |
| End of life: energy | 23 Wh | 32 Wh | 109 Wh | 110 Wh | 110 Wh |
| End of life: hot cell | 60.0 C | 60.0 C | 48.2 C | 56.8 C | 58.6 C |
| k at 40 C, below limit | 0.24 | 0.27 | 0.88 | 1.00 | 0.86 |
| k at 40 C, 3 K margin | 0.21 | 0.24 | 0.79 | 0.80 | 0.77 |
| Max constant current 25 C | 23 A | 44 A | 98 A | 109 A | 96 A |
| Max constant current 40 C | 16 A | 19 A | 68 A | 68 A | 67 A |
| P1 140 A: time / energy | 44 s / 23 Wh | 47 s / 24 Wh | 132 s / 65 Wh | 96 s / 48 Wh | 66 s / 34 Wh |
| Current factor (p95) | 1.151 | 1.151 | 1.163 | 1.163 | 1.163 |
| Charge 1C | 1.30 h | 1.30 h | 1.30 h | 1.30 h | 1.30 h |
| 2C CC rise | 17.9 K | 12.5 K | 6.0 K | 6.0 K | 6.0 K |
| Hot cell end of 1C CC at 40 C | 49.2 C | 47.9 C | 45.4 C | 45.3 C | 45.4 C |
| Balance 5 % | 7.47 h | 7.47 h | 0.56 h | 0.56 h | 0.56 h |
| Module mass | 961 g | 1161 g | 1324 g | 1324 g | 1201 g |
| Module cost | ₹10,545 | ₹11,495 | ₹17,385 | ₹17,385 | ₹15,960 |
| Envelope | 83x83x85 mm | 116x83x85 mm | 96x84x86 mm | 96x84x86 mm | 96x84x85 mm |
| Volume | 0.59 L | 0.83 L | 0.70 L | 0.70 L | 0.69 L |
| Wh/kg, Wh/L (nominal) | 168, 272 | 139, 195 | 122, 230 | 122, 230 | 134, 233 |
| Ageing index | 3.38* | 3.64* | 2.23 | 2.69 | 2.75 |

Verdicts

| Check | Baseline | Option 1 | Option 2 | Option 2b | Ablation 2a |
|---|---|---|---|---|---|
| R3 / C1 | FAIL | FAIL | PASS | PASS | PASS |
| R4 / C1 | FAIL | FAIL | FAIL | MARGINAL | FAIL |
| R5 | FAIL | FAIL | PASS | PASS | PASS |
| R11 | FAIL | FAIL | FAIL | FAIL | FAIL |
| C2 | WARN | WARN | WARN | WARN | WARN |
| C4 | WARN | WARN | WARN | WARN | WARN |
| C11 | PASS | PASS | PASS | PASS | PASS |
| C5 | PASS | PASS | PASS | PASS | PASS |
| C6 | PASS | PASS | PASS | PASS | PASS |
| C8 | PASS | PASS | PASS | PASS | PASS |
| R6 | PASS | PASS | PASS | PASS | PASS |
| R7 | PASS | PASS | PASS | PASS | PASS |
| R8 | PASS | PASS | PASS | PASS | PASS |
| R12 | PASS | PASS | PASS | PASS | PASS |
| C10 | FAIL | FAIL | FAIL | FAIL | FAIL |
| C9 | n/a | FAIL | FAIL | PASS | n/a |
| C12 | n/a | n/a | WARN | WARN | n/a |

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
  "design": "Ablation 2a",
  "sink_offset": [
   {
    "offset_K": 0.0,
    "t40": 600.0,
    "Wh40": 145.23378992060128,
    "reason": "undervoltage cutoff",
    "k3": 0.88287353515625
   },
   {
    "offset_K": 2.0,
    "t40": 316.75,
    "Wh40": 85.33435257125869,
    "reason": "hot-cell limit",
    "k3": 0.84599609375
   },
   {
    "offset_K": 3.0,
    "t40": 314.75,
    "Wh40": 84.45778473856109,
    "reason": "hot-cell limit",
    "k3": 0.8244262695312499
   },
   {
    "offset_K": 5.0,
    "t40": 310.5,
    "Wh40": 82.56652176715156,
    "reason": "hot-cell limit",
    "k3": 0.7740966796875001
   },
   {
    "offset_K": 8.0,
    "t40": 304.25,
    "Wh40": 79.73483185160586,
    "reason": "hot-cell limit",
    "k3": 0.63145751953125
   }
  ],
  "current_factor": [
   {
    "f": 1.0,
    "Thot25": 46.007480929150375,
    "k3": 0.88426513671875
   },
   {
    "f": 1.1,
    "Thot25": 49.36905192427196,
    "k3": 0.8158447265624998
   },
   {
    "f": 1.15,
    "Thot25": 51.16989352880137,
    "k3": 0.7826782226562499
   },
   {
    "f": 1.2,
    "Thot25": 53.05077253797654,
    "k3": 0.7506713867187498
   }
  ]
 }
}
```
