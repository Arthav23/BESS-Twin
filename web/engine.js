/* BESS-Twin engine v3.0, JavaScript port of bess_platform.py (same equations, same order).
   test_parity.js runs both and compares. Works in the browser (window.BESS) and in node (require). */
(function (root) {
"use strict";
const CELLS = {
  "Molicel P28A": {fmt:"18650", Q:2.8, Vnom:3.6, Vmax:4.2, Vmin:2.5, R25:0.020, Imax:35.0, Ichg_max:6.0, m:0.046, D:18.6, H:65.2, Tchg:[0,60], Tdis:[-40,60], usd:4.5, asm:["usd"]},
  "Molicel P42A": {fmt:"21700", Q:4.2, Vnom:3.6, Vmax:4.2, Vmin:2.5, R25:0.016, Imax:45.0, Ichg_max:4.2, m:0.070, D:21.7, H:70.2, Tchg:[0,45], Tdis:[-40,60], usd:5.0, asm:["usd","Ichg_max"]},
  "Samsung 30Q":  {fmt:"18650", Q:3.0, Vnom:3.6, Vmax:4.2, Vmin:2.5, R25:0.026, Imax:15.0, Ichg_max:4.0, m:0.048, D:18.4, H:65.0, Tchg:[0,50], Tdis:[-20,75], usd:5.0, asm:["usd","R25"]},
};
const PARAMS = {
  cp_cell:[950.0,"ASM"], R_T_slope:[0.015,"ASM"], R_floor:[0.008,"ASM"], soc_gain:[0.6,"ASM"], soc_width:[0.08,"ASM"],
  R_p:[0.008,"ASM"], tau_p:[30.0,"ASM"], R_ic_Ni:[0.0030,"ASM"], R_ic_CuNi:[0.0008,"ASM"], sink_offset_liquid:[5.0,"ASM"],
  R_shunt:[0.0005,"ASM"], R_fet:[0.0010,"ASM"], cell_sigma:[0.08,"ASM"], branch_sigma:[0.15,"ASM"], maldist:[null,"ASM"],
  eol_cap:[0.80,"ASM"], eol_res:[1.50,"ASM"], pitch_gap:[1.5,"ASM"], pcm_rho:[0.77,"ASM"], foam_porosity:[0.90,"ASM"],
  cool_scale:[1.0,"ASM"], usd_inr:[95.0,"ASM"],
};
const CALIB_CELL = "Molicel P28A";
const P = {}; for (const k in PARAMS) P[k] = PARAMS[k][0];
let CALIB = {};
const OCV0 = [[0.0,3.00],[0.05,3.25],[0.10,3.38],[0.20,3.50],[0.40,3.64],[0.50,3.70],[0.60,3.78],[0.80,3.97],[0.90,4.07],[1.0,4.20]];
let OCV = OCV0.slice();

function loadCalibration(obj) {
  CALIB = {};
  for (const k in PARAMS) P[k] = PARAMS[k][0];
  OCV = OCV0.slice();
  for (const k in obj) {
    if (k in P || k === "Q_cell" || k === "R25" || k === "OCV") {
      CALIB[k] = obj[k];
      if (k in P) P[k] = obj[k];
    }
  }
  if (CALIB.OCV) OCV = CALIB.OCV.map(x => [x[0], x[1]]);
  MC_CACHE.clear();
}

const T_DERATE_BELOW = 5.0, MARGIN_K = 3.0, T_DESIGN_HOT = 40.0, BQ_OCD_MAX_V = 0.100, BQ_SCALE_ERR = 0.10;

function ocv(s) {
  s = Math.min(Math.max(s, 0.0), 1.0);
  for (let i = 0; i < OCV.length - 1; i++) {
    const [s0, v0] = OCV[i], [s1, v1] = OCV[i + 1];
    if (s <= s1) return v0 + (v1 - v0) * (s - s0) / (s1 - s0);
  }
  return OCV[OCV.length - 1][1];
}

const COOL = {
  air:     {G_ca:0.29},
  pcm:     {G_cp:3.1, G_pa:0.30, m:0.150, Ts:34.0, Tl:36.0, L:240e3, block:true},
  liquid:  {G_ca:10.0, sink:true},
  hbtms:   {G_cp:60.0, G_pa:12.0, m:0.100, Ts:34.0, Tl:36.0, L:240e3, sink:true, foam:true},
  hbtms47: {G_cp:60.0, G_pa:12.0, m:0.100, Ts:45.0, Tl:47.0, L:170e3, sink:true, foam:true},
  single_air: {G_ca:0.06 * 16},
};
const COOL_LABEL = {air:"natural air", pcm:"PCM block (35 C)", liquid:"liquid cold plates", hbtms:"liquid + foam + PCM (35 C)", hbtms47:"liquid + foam + PCM (47 C)"};
const CP_PCM = 2000.0;
const DEFAULT_MISSION = {burst:140.0, base:60.0, burst_s:20.0, period_s:300.0};
const DEFAULT_REQ = {R5_s:480, R5_Wh:100.0, R6_kg:1.5, R7_inr:19000.0, R8_h:1.5, R12_L:1.0};
const REFERENCE = {
  "Baseline":    {cell:"Molicel P28A", NS:4, NP:4, busbar:"Ni",   cooling:"air",     bal:"passive"},
  "Option 1":    {cell:"Molicel P28A", NS:4, NP:4, busbar:"Ni",   cooling:"pcm",     bal:"passive"},
  "Option 2":    {cell:"Molicel P28A", NS:4, NP:4, busbar:"CuNi", cooling:"hbtms",   bal:"active"},
  "Option 2b":   {cell:"Molicel P28A", NS:4, NP:4, busbar:"CuNi", cooling:"hbtms47", bal:"active"},
  "Ablation 2a": {cell:"Molicel P28A", NS:4, NP:4, busbar:"CuNi", cooling:"liquid",  bal:"active"},
  "R-A 4S5P":    {cell:"Molicel P28A", NS:4, NP:5, busbar:"CuNi", cooling:"liquid",  bal:"active"},
  "R-B 4S5P low-loss": {cell:"Molicel P28A", NS:4, NP:5, busbar:"CuNi", cooling:"liquid", bal:"passive", bms:"lowloss"},
};
const BMS_OPT = {standard:{R_shunt:null, R_fet:null, g:0, usd:0.0}, lowloss:{R_shunt:0.00025, R_fet:0.0005, g:10, usd:8.0}};

function mulberry32(a) {
  return function () {
    a |= 0; a = a + 0x6D2B79F5 | 0;
    let t = Math.imul(a ^ a >>> 15, 1 | a);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}
function gaussFactory(rnd) {
  return function () { const u1 = rnd() || 1e-12, u2 = rnd(); return Math.sqrt(-2.0 * Math.log(u1)) * Math.cos(2.0 * Math.PI * u2); };
}
const MC_CACHE = new Map();
let MC_N = 20000;
function currentShareMC(R25, R_ic, NP, n, seed = 1) {
  n = n || MC_N;
  if (NP < 2) return {mean:1.0, p95:1.0, p99:1.0, n};
  const key = [R25, R_ic, NP, P.cell_sigma, P.branch_sigma, n, seed].join("|");
  if (MC_CACHE.has(key)) return MC_CACHE.get(key);
  const g = gaussFactory(mulberry32(seed));
  const worst = new Float64Array(n);
  for (let i = 0; i < n; i++) {
    let sum = 0, mx = 0;
    for (let j = 0; j < NP; j++) {
      const r = R25 * (1 + P.cell_sigma * g()) + R_ic * (1 + P.branch_sigma * g());
      const c = 1.0 / r; sum += c; if (c > mx) mx = c;
    }
    worst[i] = mx / (sum / NP);
  }
  worst.sort();
  let s = 0; for (let i = 0; i < n; i++) s += worst[i];
  const out = {mean: s / n, p95: worst[Math.floor(0.95 * n)], p99: worst[Math.floor(0.99 * n)], n};
  MC_CACHE.set(key, out);
  return out;
}

function build(cfg, mission) {
  const c = Object.assign({}, CELLS[cfg.cell]);
  if (cfg.cell === CALIB_CELL) { if ("Q_cell" in CALIB) c.Q = CALIB.Q_cell; if ("R25" in CALIB) c.R25 = CALIB.R25; }
  const NS = cfg.NS | 0, NP = cfg.NP | 0, N = NS * NP, s = N / 16.0;
  const cool = Object.assign({}, COOL[cfg.cooling]);
  for (const k of ["G_ca", "G_cp", "G_pa", "m"]) if (k in cool) cool[k] *= s;
  for (const k of ["G_ca", "G_cp", "G_pa"]) if (k in cool) cool[k] *= P.cool_scale;
  const ric = P["R_ic_" + cfg.busbar];
  const mc = currentShareMC(c.R25, ric, NP);
  const f = P.maldist !== null && P.maldist !== undefined ? P.maldist : mc.p95;
  const bo = BMS_OPT[cfg.bms || "standard"];
  const d = {cfg, cell:c, NS, NP, N, cool, ric, mc, f, R_shunt: bo.R_shunt || P.R_shunt, R_fet: bo.R_fet || P.R_fet,
             mission: Object.assign({}, mission || DEFAULT_MISSION), T_MAX: Math.min(60.0, c.Tdis[1])};
  d.T_DERATE = d.T_MAX - T_DERATE_BELOW;
  return d;
}

class Thermal {
  constructor(d, Tamb) {
    const c = d.cool; this.c = c;
    this.Cc = d.N * d.cell.m * P.cp_cell;
    this.Tsink = Tamb + (c.sink ? P.sink_offset_liquid : 0.0);
    this.Tc = Tamb;
    this.m = c.m || 0.0;
    if (this.m) {
      const Ts = c.Ts, Tl = c.Tl, L = c.L;
      if (Tamb <= Ts) this.H = this.m * CP_PCM * (Tamb - Ts);
      else if (Tamb < Tl) this.H = this.m * L * (Tamb - Ts) / (Tl - Ts);
      else this.H = this.m * L + this.m * CP_PCM * (Tamb - Tl);
    }
  }
  Tp() {
    const c = this.c, m = this.m;
    if (this.H <= 0) return c.Ts + this.H / (m * CP_PCM);
    if (this.H < m * c.L) return c.Ts + (c.Tl - c.Ts) * this.H / (m * c.L);
    return c.Tl + (this.H - m * c.L) / (m * CP_PCM);
  }
  step(q, dt) {
    const c = this.c;
    const qca = (c.G_ca || 0.0) * (this.Tc - this.Tsink);
    let qcp = 0.0;
    if (this.m) {
      const tp = this.Tp();
      qcp = c.G_cp * (this.Tc - tp);
      this.H += dt * (qcp - c.G_pa * (tp - this.Tsink));
    }
    this.Tc += dt * (q - qcp - qca) / this.Cc;
  }
}
function hot(Tc, Tsink, f) { return Tc + (f * f - 1.0) * Math.max(0.0, Tc - Tsink); }

function sim(d, profile, Tamb = 25.0, opt = {}) {
  const t_limit = opt.t_limit || 7200.0, dt = opt.dt || 0.25, trace = !!opt.trace, eol = !!opt.eol, tempStop = opt.temp_stop !== false;
  const th = new Thermal(d, Tamb);
  const c = d.cell, NS = d.NS, NP = d.NP, N = d.N, f = d.f;
  const Q = c.Q * (eol ? P.eol_cap : 1.0), R25 = c.R25 * (eol ? P.eol_res : 1.0);
  const ric = d.ric, T_MAX = d.T_MAX, T_DER = d.T_DERATE;
  let soc = 1.0, vp = 0.0, t = 0.0, Ah = 0, Wh = 0, Qloss = 0, Tint = 0, I2 = 0, Eoc = 0;
  let Tmax = Tamb, Thmax = Tamb, Vmin = 99.0, t55 = null, t60 = null, reason = "profile complete";
  const curve = [];
  while (t < t_limit) {
    const I = profile(t);
    if (I === null) break;
    const Ic = I / NP;
    let R = Math.max(R25 * Math.exp(-P.R_T_slope * (th.Tc - 25.0)), P.R_floor);
    R *= 1.0 + P.soc_gain * Math.exp(-soc / P.soc_width);
    const Reff = R + ric;
    const Vc = ocv(soc) - Ic * Reff - vp;
    if (Vc < c.Vmin) { reason = "undervoltage cutoff"; break; }
    if (soc <= 0.0) { reason = "capacity exhausted"; break; }
    const q = N * (Ic * Ic * Reff + vp * vp / P.R_p);
    Eoc += NS * ocv(soc) * I * dt / 3600;
    Wh += NS * Vc * I * dt / 3600; Ah += I * dt / 3600;
    Qloss += q * dt; I2 += I * I * dt; Tint += th.Tc * dt;
    th.step(q, dt);
    vp += dt * (Ic * P.R_p - vp) / P.tau_p;
    soc -= Ic * dt / 3600 / Q;
    Vmin = Math.min(Vmin, NS * Vc);
    t += dt;
    const Th = hot(th.Tc, th.Tsink, f);
    Tmax = Math.max(Tmax, th.Tc); Thmax = Math.max(Thmax, Th);
    if (trace && Math.round(t / dt) % 4 === 0) curve.push([t, Th, NS * Vc]);
    if (t55 === null && Th >= T_DER) t55 = t;
    if (Th >= T_MAX && t60 === null) { t60 = t; if (tempStop) { reason = "hot-cell limit"; break; } }
  }
  const out = {t, reason, Ah, Wh, Eoc_Wh:Eoc, Qloss_kJ:Qloss / 1e3, Tavg_max:Tmax, Thot_max:Thmax, t55, t60, Vmin,
               Tmean: Tint / Math.max(t, 1e-9), Irms: Math.sqrt(I2 / Math.max(t, 1e-9))};
  if (trace) out.curve = curve;
  return out;
}

function missionProfile(m, k = 1.0) { return t => k * ((t % m.period_s) < m.burst_s ? m.burst : m.base); }
const CONST = I => (t => I);

function maxConstCurrent(d, Tamb) {
  const top = d.mission.burst;
  const ok = I => sim(d, CONST(I), Tamb, {dt:0.5}).t60 === null;
  if (ok(top)) return top;
  let lo = 1.0, hi = top;
  for (let i = 0; i < 12; i++) { const mid = (lo + hi) / 2; if (ok(mid)) lo = mid; else hi = mid; }
  return lo;
}
function maxDerate(d, Tamb, margin = 0.0) {
  const ok = k => sim(d, missionProfile(d.mission, k), Tamb, {dt:0.5}).Thot_max <= d.T_MAX - margin;
  let lo = 0.05, hi = 1.0;
  if (ok(hi)) return 1.0;
  for (let i = 0; i < 12; i++) { const mid = (lo + hi) / 2; if (ok(mid)) lo = mid; else hi = mid; }
  return lo;
}
function charge(d, crate = 1.0, Tamb = 25.0) {
  const c = d.cell, Q = d.NP * c.Q, I_mod = crate * Q, f_cc = 0.80, t_cv = 0.5;
  const t_cc = f_cc / crate * 3600;
  const th = new Thermal(d, Tamb), Ic = I_mod / d.NP;
  const q = d.N * Ic * Ic * (c.R25 + d.ric);
  let t = 0.0;
  while (t < t_cc) { th.step(q, 0.5); t += 0.5; }
  return {hours: t_cc / 3600 + t_cv, dT_cc: th.Tc - Tamb, heat_W: q, I_cell: Ic, Thot_end: hot(th.Tc, th.Tsink, d.f)};
}

function bmsChip(NS) {
  if (NS >= 3 && NS <= 5) return ["BQ76920", 45, 18.0];
  if (NS >= 6 && NS <= 10) return ["BQ76930", 55, 24.0];
  if (NS >= 9 && NS <= 15) return ["BQ76940", 65, 30.0];
  return [null, 45, 18.0];
}
function bom(d) {
  const cfg = d.cfg, N = d.N, NS = d.NS, s = N / 16.0, c = d.cell;
  const liq = ["liquid", "hbtms", "hbtms47"].includes(cfg.cooling);
  let [chip, g_bms, usd_bms] = bmsChip(NS);
  const bo = BMS_OPT[cfg.bms || "standard"]; g_bms += bo.g; usd_bms += bo.usd;
  const items = [[`${N} x ${cfg.cell} cells`, N * c.m * 1000, N * c.usd, false],
                 ["wiring and connector", 90, 12.0, false],
                 [`BMS (${chip || "no BQ769x0 fits"}, ${cfg.bms || "standard"} FETs and shunt)`, g_bms, usd_bms, false]];
  if (!liq) items.push(["cell holders", 60 * s, 4.0 * s, false]);
  items.push(cfg.busbar === "Ni" ? ["busbar, Ni strip", 30 * s, 5.0 * s, false] : ["busbar, Cu-Ni clad", 55 * s, 14.0 * s, false]);
  if (cfg.cooling === "pcm") items.push(["PCM block + container", 200 * s, 10.0 * s, false]);
  if (cfg.cooling === "hbtms" || cfg.cooling === "hbtms47") { items.push(["PCM", 100 * s, 3.0 * s, false]); items.push(["Al foam", 23 * s, 12.0 * s, false]); }
  if (cfg.bal === "active") items.push([`ETA3000 x${NS - 1} + inductors`, 5 * (NS - 1), 13.0 / 3 * (NS - 1), false]);
  if (liq) items.push(["cold plates x2", 120 * s, 24.0 * s, false], ["coolant, tubing, fittings", 100, 10.0, false],
                      ["enclosure and seals", 40 * s, 5.0 * s, false], ["pump (vehicle side)", 60, 15.0, true], ["radiator + reservoir", 250, 20.0, true]);
  let gm = 0, um = 0, gs = 0, us = 0;
  for (const [, g, u, loop] of items) { gs += g; us += u; if (!loop) { gm += g; um += u; } }
  const r0 = x => Math.floor(x + 0.5), fx = P.usd_inr;          // costs are reported in INR
  return {items: items.map(([item, g, usd, l]) => ({item, g: Math.floor(g * 10 + 0.5) / 10, inr: r0(usd * fx), vehicle_side: l})),
          mass_module: r0(gm), inr_module: r0(um * fx), mass_system: r0(gs), inr_system: r0(us * fx), chip};
}
function geometry(d) {
  const c = d.cell, N = d.N, cfg = d.cfg;
  const pitch = c.D + P.pitch_gap;
  const cols = Math.ceil(Math.sqrt(N)), rows = Math.ceil(N / cols);
  const bx = cols * pitch, by = rows * pitch, bh = c.H;
  const liq = ["liquid", "hbtms", "hbtms47"].includes(cfg.cooling);
  const wall = liq ? 2.0 : 1.5;
  let L = bx + 2 * wall + (liq ? 2 * 6.0 : 0.0), W = by + 2 * wall, H = bh + 2 * 4.0 + 12.0;
  const pcm = {needed_cm3:0.0, gap_cm3:0.0, overflow_cm3:0.0};
  const m_pcm = (d.cool.m || 0.0) * 1000;
  if (cfg.cooling === "pcm") { const vol = m_pcm / P.pcm_rho * 1.2; L += vol * 1000 / (W * H); pcm.needed_cm3 = m_pcm / P.pcm_rho; }
  if (d.cool.foam) {
    const gap = (bx * by * bh - N * Math.PI * (c.D / 2) ** 2 * bh) / 1000 * P.foam_porosity;
    const need = m_pcm / P.pcm_rho, over = Math.max(0.0, need - gap);
    H += over * 1000 / (bx * by);
    Object.assign(pcm, {needed_cm3: need, gap_cm3: gap, overflow_cm3: over});
  }
  const vol_L = L * W * H / 1e6, E = d.NS * d.NP * c.Q * c.Vnom;
  return {L_mm: L, W_mm: W, H_mm: H, volume_L: vol_L, Wh_per_L: E / vol_L, E_nom_Wh: E, grid: `${cols} x ${rows}`, cols, rows, pitch, pcm};
}
function balancing(d, imbalance = 0.05) {
  const q = imbalance * d.NP * d.cell.Q;
  if (d.cfg.bal === "passive") { const i = 0.075; return {hours: q / i, heat_W: i * 4.1, waste_Wh: q * 3.9}; }
  const i = 1.0; return {hours: q / i, heat_W: i * 3.9 * 0.08, waste_Wh: q * 3.9 * 0.08};
}

function thermalVerdict(run, T_MAX) {
  if (run.t60 !== null) return "FAIL";
  return (T_MAX - run.Thot_max < MARGIN_K) ? "MARGINAL" : "PASS";
}
const f0 = (x, n = 0) => Number(x).toFixed(n);
const inr = x => Math.round(x).toLocaleString("en-IN");
function verdicts(d, r, REQ) {
  const c = d.cell, m = d.mission, m25 = r.mission25, m40 = r.mission40, eol = r.mission25_eol, b = r.bom, g = r.geom, TM = d.T_MAX;
  const v = [];
  v.push(["R3 / C1", `hot cell < ${f0(TM)} C, mission at 25 C`, thermalVerdict(m25, TM), `Thot ${f0(m25.Thot_max,1)} C, ran ${f0(m25.t)} s (${m25.reason})`]);
  v.push(["R4 / C1", `hot cell < ${f0(TM)} C, mission at 40 C`, thermalVerdict(m40, TM),
          `Thot ${f0(m40.Thot_max,1)} C, ran ${f0(m40.t)} s (${m40.reason}); derated mission k = ${f0(r.derate40_3K,2)} passes with 3 K margin`]);
  const ok5 = x => x.t >= REQ.R5_s && x.Wh >= REQ.R5_Wh;
  v.push(["R5", `>= ${REQ.R5_s} s and >= ${f0(REQ.R5_Wh)} Wh at 25 C`, ok5(m25) ? "PASS" : "FAIL", `${f0(m25.t)} s, ${f0(m25.Wh)} Wh`]);
  v.push(["R11", "R5 still met at end of life (80 % capacity, 1.5x resistance)", (ok5(eol) && eol.t60 === null) ? "PASS" : "FAIL",
          `${f0(eol.t)} s, ${f0(eol.Wh)} Wh, Thot ${f0(eol.Thot_max,1)} C (${eol.reason})`]);
  const worst = m.burst / d.NP * d.f;
  v.push(["C2", `worst branch current <= ${f0(c.Imax)} A at ${f0(m.burst)} A burst`,
          m.burst / d.NP > c.Imax ? "FAIL" : (worst > c.Imax ? "WARN" : "PASS"),
          `mean ${f0(m.burst / d.NP,1)} A, worst ${f0(worst,1)} A (factor ${f0(d.f,3)}, 95th pct)`]);
  const pf = m.burst ** 2 * (d.R_shunt + d.R_fet);
  v.push(["C4", "BMS FET + shunt dissipation <= 15 W", pf > 15 ? "WARN" : "PASS", `${f0(pf)} W at ${f0(m.burst)} A`]);
  const v_ocd = m.burst * (1 + BQ_SCALE_ERR) * d.R_shunt + 0.0025;
  v.push(["C11", "BQ769x0 OCD threshold (max 100 mV) above burst + 10 % error", v_ocd <= BQ_OCD_MAX_V ? "PASS" : "FAIL",
          `needs ${f0(v_ocd * 1e3)} mV across ${f0(d.R_shunt * 1e3,2)} mOhm shunt`]);
  const cool = COOL[d.cfg.cooling];
  if (cool.m) v.push(["C9", `PCM melt window above ${f0(T_DESIGN_HOT)} C design ambient`, cool.Tl > T_DESIGN_HOT ? "PASS" : "FAIL", `melts ${f0(cool.Ts)}-${f0(cool.Tl)} C`]);
  if (cool.foam) { const p = g.pcm;
    v.push(["C12", "PCM fits in the foam between the cells", p.overflow_cm3 <= 0 ? "PASS" : "WARN",
            `needs ${f0(p.needed_cm3)} cm3 molten, gaps hold ${f0(p.gap_cm3)} cm3; ${f0(p.overflow_cm3)} cm3 overflows into a top layer`]); }
  const ch = r.charge1c, chh = r.charge1c_hot;
  v.push(["C5", `cell inside its charge window (${c.Tchg[0]}-${c.Tchg[1]} C), 1C charge at 40 C`,
          chh.Thot_end > c.Tchg[1] ? "FAIL" : (c.Tchg[1] - chh.Thot_end < MARGIN_K ? "MARGINAL" : "PASS"), `hot cell ${f0(chh.Thot_end,1)} C at end of CC phase`]);
  v.push(["C6", `charge current <= ${f0(c.Ichg_max,1)} A per cell at 1C`, ch.I_cell <= c.Ichg_max ? "PASS" : "FAIL", `${f0(ch.I_cell,1)} A per cell`]);
  v.push(["C8", "a BQ769x0 front end covers NS", b.chip ? "PASS" : "FAIL", `NS = ${d.NS} -> ${b.chip || "none (needs 3-15 cells)"}`]);
  v.push(["R6", `module mass <= ${REQ.R6_kg} kg`, b.mass_module / 1000 <= REQ.R6_kg ? "PASS" : "FAIL", `${b.mass_module} g (+${b.mass_system - b.mass_module} g vehicle-side loop)`]);
  v.push(["R7", `module BOM <= ₹${inr(REQ.R7_inr)}`, b.inr_module <= REQ.R7_inr ? "PASS" : "FAIL", `₹${inr(b.inr_module)} (+₹${inr(b.inr_system - b.inr_module)} loop)`]);
  v.push(["R8", `charge at 1C <= ${REQ.R8_h} h`, ch.hours <= REQ.R8_h ? "PASS" : "FAIL", `${f0(ch.hours,2)} h, CC rise ${f0(ch.dT_cc,1)} K`]);
  v.push(["R12", `module envelope <= ${REQ.R12_L} L`, Math.round(g.volume_L * 1000) / 1000 <= REQ.R12_L ? "PASS" : "FAIL",
          `${f0(g.L_mm)} x ${f0(g.W_mm)} x ${f0(g.H_mm)} mm = ${f0(g.volume_L,2)} L, ${f0(g.Wh_per_L)} Wh/L`]);
  const fails = v.filter(x => x[2] === "FAIL").map(x => x[0]);
  v.push(["C10", "all requirements and hard rules met", fails.length ? "FAIL" : "PASS", fails.length ? "fails: " + fails.join(", ") : "no FAIL"]);
  return v;
}
function trace(d, r) {
  const m25 = r.mission25, m40 = r.mission40, eol = r.mission25_eol, cfg = d.cfg;
  const tag = (...ks) => ks.every(k => k in CALIB) ? "calibrated" : "uncalibrated (ASM)";
  return [
    ["R1", `${d.N} x ${cfg.cell}, ${d.NS}S${d.NP}P`, "datasheet capacity at 25 C", "hand calculation",
     `${f0(d.NS * d.cell.Vnom,1)} V, ${f0(d.NP * d.cell.Q,1)} Ah, ${f0(r.geom.E_nom_Wh)} Wh`, "datasheet; test T1", "Q_cell" in CALIB ? "calibrated" : "datasheet"],
    ["R2 / C2", "busbar, parallel branches", `cell spread ${f0(P.cell_sigma*100)}%, branch spread ${f0(P.branch_sigma*100)}%`, "Monte Carlo + checker C2",
     `factor ${f0(d.f,3)}, worst branch ${f0(d.mission.burst / d.NP * d.f,1)} A`, "pulse-rating check; test T5", tag("cell_sigma", "branch_sigma")],
    ["R3", COOL_LABEL[cfg.cooling], "G values, sink offset, hot-cell factor", "thermal node model", `${f0(m25.Thot_max,1)} C hot cell, ${thermalVerdict(m25, d.T_MAX)}`, "heating test T2", tag("cp_cell")],
    ["R4", "cooling + derating rule", `sink at ambient + ${f0(P.sink_offset_liquid)} K`, "thermal model, derate sweep",
     `${thermalVerdict(m40, d.T_MAX)}; derate k = ${f0(r.derate40_3K,2)} with 3 K margin`, "warm-ambient test T3; radiator test", tag("sink_offset_liquid")],
    ["R5", "cells, busbar", "R(T, SOC), polarization, OCV table", "electrical model", `${f0(m25.Wh)} Wh in ${f0(m25.t)} s`, "tests T1, T4", tag("R_p", "tau_p", "R25")],
    ["R11", "cells at end of life", "80 % capacity, 1.5x resistance", "electrical + thermal model", `${f0(eol.Wh)} Wh in ${f0(eol.t)} s`, "cycling data or aged-cell test", tag("eol_cap", "eol_res")],
    ["R6", "BOM", "part masses", "roll-up", `${r.bom.mass_module} g`, "weighing the mock-up", "uncalibrated (ASM)"],
    ["R7", "BOM", "retail prices +-30 %", "roll-up", `₹${inr(r.bom.inr_module)}`, "vendor quotes", "uncalibrated (ASM)"],
    ["R8", "CC-CV charger", "CC to 80 %, 0.5 h CV", "charge model", `${f0(r.charge1c.hours,2)} h`, "test T6", "uncalibrated (ASM)"],
    ["R12", "layout, cold plates, enclosure", "1.5 mm pitch gap, 6 mm plates, 2 mm walls", "geometry roll-up",
     `${f0(r.geom.volume_L,2)} L, ${f0(r.geom.Wh_per_L)} Wh/L`, "measuring the mock-up", "uncalibrated (ASM)"],
  ];
}
function label(cfg) {
  return `${cfg.NS}S${cfg.NP}P ${cfg.cell}, ${cfg.busbar === "CuNi" ? "Cu-Ni" : "Ni"} busbar, ${cfg.bal} balancing, ${COOL_LABEL[cfg.cooling]}` + (cfg.bms === "lowloss" ? ", low-loss BMS" : "");
}
function evaluate(cfg, mission, REQ, opts = {}) {
  REQ = REQ || DEFAULT_REQ;
  const d = build(cfg, mission), mp = missionProfile(d.mission);
  const r = {config: cfg, label: label(cfg)};
  r.peak25 = sim(d, CONST(d.mission.burst), 25.0);
  r.mission25 = sim(d, mp, 25.0, {trace:true});
  r.mission40 = sim(d, mp, 40.0, {trace:true});
  r.mission25_eol = sim(d, mp, 25.0, {eol:true, trace: !!opts.traceEol});
  r.imax25 = maxConstCurrent(d, 25.0); r.imax40 = maxConstCurrent(d, 40.0);
  r.derate40 = maxDerate(d, 40.0); r.derate40_3K = maxDerate(d, 40.0, MARGIN_K);
  r.charge1c = charge(d, 1.0); r.charge2c = charge(d, 2.0); r.charge1c_hot = charge(d, 1.0, T_DESIGN_HOT);
  r.bom = bom(d); r.geom = geometry(d); r.bal = balancing(d);
  r.Wh_per_kg = r.geom.E_nom_Wh / (r.bom.mass_module / 1000);
  r.current_factor = d.f; r.mc = d.mc; r.T_MAX = d.T_MAX; r.T_DERATE = d.T_DERATE;
  r.ageing_index = 2 ** ((r.mission25.Tmean - 25) / 10);
  r.ageing_comparable = ["undervoltage cutoff", "capacity exhausted"].includes(r.mission25.reason);
  r.verdicts = verdicts(d, r, REQ);
  r.trace = trace(d, r);
  return r;
}


// ---- uncertainty propagation (same sampling order and seed as bess_platform.py) ----
const UQ_RANGES = {cp_cell:[850.0,1050.0], R_T_slope:[0.010,0.020], soc_gain:[0.3,0.9], R_p:[0.005,0.011], tau_p:[20.0,40.0],
  R_ic_CuNi:[0.0005,0.0012], R_ic_Ni:[0.002,0.004], sink_offset_liquid:[3.0,7.0], cell_sigma:[0.05,0.11], cool_scale:[0.75,1.25], R25_scale:[0.9,1.1]};
function uncertainty(cfg, n = 300, seed = 7, mission) {
  const rnd = mulberry32(seed), keep = Object.assign({}, P), keepR = CELLS[cfg.cell].R25, mcn = MC_N; MC_N = 4000;
  const out = [];
  const ok5 = z => z.t >= DEFAULT_REQ.R5_s && z.Wh >= DEFAULT_REQ.R5_Wh;
  try {
    for (let i = 0; i < n; i++) {
      const x = {}; for (const k in UQ_RANGES) { const [lo, hi] = UQ_RANGES[k]; x[k] = lo + (hi - lo) * rnd(); }
      for (const k in x) if (k in P) P[k] = x[k];
      CELLS[cfg.cell].R25 = keepR * x.R25_scale;
      const d = build(cfg, mission), mp = missionProfile(d.mission);
      const a = sim(d, mp, 25.0, {dt:0.5}), b = sim(d, mp, 40.0, {dt:0.5}), e = sim(d, mp, 25.0, {dt:0.5, eol:true});
      out.push({R3: a.t60 === null, R4: b.t60 === null, R4m: b.t60 === null && d.T_MAX - b.Thot_max >= MARGIN_K, R5: ok5(a),
                R11: ok5(e) && e.t60 === null, T25: a.Thot_max, T40: b.Thot_max, Wh25: a.Wh, x});
    }
  } finally { Object.assign(P, keep); CELLS[cfg.cell].R25 = keepR; MC_N = mcn; MC_CACHE.clear(); }
  const pr = k => out.filter(o => o[k]).length / n;
  const q = (k, f) => out.map(o => o[k]).sort((a, b) => a - b)[Math.floor(f * (n - 1))];
  const corr = k => { const xs = out.map(o => o.x[k]), ys = out.map(o => o.T40); const mx = xs.reduce((a, b) => a + b) / n, my = ys.reduce((a, b) => a + b) / n;
    let sxy = 0, sxx = 0, syy = 0; for (let i = 0; i < n; i++) { sxy += (xs[i] - mx) * (ys[i] - my); sxx += (xs[i] - mx) ** 2; syy += (ys[i] - my) ** 2; }
    return sxx && syy ? sxy / Math.sqrt(sxx * syy) : 0; };
  const drivers = Object.keys(UQ_RANGES).map(k => [k, corr(k)]).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1])).slice(0, 5);
  return {n, p_R3: pr("R3"), p_R4: pr("R4"), p_R4_margin: pr("R4m"), p_R5: pr("R5"), p_R11: pr("R11"),
          p_all: out.filter(o => o.R3 && o.R4 && o.R5 && o.R11).length / n,
          T25_p5_p50_p95: [q("T25", .05), q("T25", .5), q("T25", .95)], T40_p5_p50_p95: [q("T40", .05), q("T40", .5), q("T40", .95)],
          Wh25_p5_p50_p95: [q("Wh25", .05), q("Wh25", .5), q("Wh25", .95)], drivers_T40: drivers, T40_all: out.map(o => o.T40)};
}

// ---- automatic design search (same space and rules as bess_platform.py) ----
const SEARCH_SPACE = {cell: Object.keys(CELLS), NP: [3, 4, 5, 6], busbar: ["Ni", "CuNi"], cooling: ["air", "pcm", "liquid", "hbtms", "hbtms47"],
                      bal: ["passive", "active"], bms: ["standard", "lowloss"]};
function quickEval(cfg, mission, REQ) {
  REQ = REQ || DEFAULT_REQ;
  const d = build(cfg, mission), mp = missionProfile(d.mission);
  const r = {config: cfg, label: label(cfg)};
  r.mission25 = sim(d, mp, 25.0, {dt:0.5}); r.mission40 = sim(d, mp, 40.0, {dt:0.5}); r.mission25_eol = sim(d, mp, 25.0, {dt:0.5, eol:true});
  r.derate40_3K = NaN; r.charge1c = charge(d, 1.0); r.charge1c_hot = charge(d, 1.0, T_DESIGN_HOT);
  r.bom = bom(d); r.geom = geometry(d); r.verdicts = verdicts(d, r, REQ);
  r.margin40 = r.mission40.t60 === null ? d.T_MAX - r.mission40.Thot_max : 0.0;
  return r;
}
function designSearch(NS = 4, mission) {
  const S = SEARCH_SPACE, rows = [];
  for (const cell of S.cell) for (const NP of S.NP) for (const busbar of S.busbar) for (const cooling of S.cooling) for (const bal of S.bal) for (const bms of S.bms) {
    const cfg = {cell, NS, NP, busbar, cooling, bal, bms}, r = quickEval(cfg, mission);
    rows.push({cfg, fails: r.verdicts.filter(v => v[2] === "FAIL" && v[0] !== "C10").map(v => v[0]), warns: r.verdicts.filter(v => v[2] === "WARN").map(v => v[0]),
               mass: r.bom.mass_module, inr: r.bom.inr_module, vol: r.geom.volume_L, Wh25: r.mission25.Wh, margin40: r.margin40, eolWh: r.mission25_eol.Wh});
  }
  const ok = rows.filter(x => !x.fails.length), clean = ok.filter(x => !x.warns.length);
  const dominated = (a, pool) => pool.some(b => b !== a && b.inr <= a.inr && b.mass <= a.mass && b.margin40 >= a.margin40 &&
                                                (b.inr < a.inr || b.mass < a.mass || b.margin40 > a.margin40));
  const front = clean.filter(x => !dominated(x, clean)).sort((a, b) => a.inr - b.inr);
  const fail_count = {}; for (const x of rows) for (const f of x.fails) fail_count[f] = (fail_count[f] || 0) + 1;
  return {n: rows.length, n_pass: ok.length, n_clean: clean.length, front, fail_count, rows};
}

const API = {CELLS, PARAMS, P, COOL, COOL_LABEL, REFERENCE, BMS_OPT, DEFAULT_MISSION, DEFAULT_REQ, MARGIN_K,
             get CALIB() { return CALIB; }, get OCV() { return OCV; },
             loadCalibration, mulberry32, currentShareMC, build, sim, missionProfile, maxDerate, maxConstCurrent,
             charge, bom, geometry, inr, balancing, verdicts, trace, evaluate, label, uncertainty, designSearch, quickEval, UQ_RANGES, SEARCH_SPACE};
if (typeof module !== "undefined" && module.exports) module.exports = API; else root.BESS = API;
})(typeof window !== "undefined" ? window : this);
