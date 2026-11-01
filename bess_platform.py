#!/usr/bin/env python3
"""
BESS-Twin engine, v3.0
Configurable cell-to-module design checker: coupled electro-thermal model, cell-variation
Monte Carlo, end-of-life scenario, geometry and volume, BOM roll-up, requirement / conflict
checker, traceability table and sensitivity sweeps.

    python3 bess_platform.py                              5 reference designs, writes results.json
    python3 bess_platform.py calib.json                   same, measured values override assumptions
    python3 bess_platform.py --config my_design.json      your own designs (see configs/)
    python3 bess_platform.py --fast                       skip sweeps (a few seconds)

Every value carries a tag: DS = datasheet, ASM = assumption (not yet measured),
calibrated = replaced by a bench measurement through calib.json (see calibrate.py).
The browser dashboard (bess_dashboard.html) runs the same equations; test_parity.js checks it.
"""
import json, math, sys, argparse

# ---- cell library -----------------------------------------------------------------------
# Values from manufacturer data sheets (DS) unless the cell's "asm" list says otherwise.
CELLS = {
    "Molicel P28A": dict(fmt="18650", Q=2.8, Vnom=3.6, Vmax=4.2, Vmin=2.5, R25=0.020, Imax=35.0,
                         Ichg_max=6.0, m=0.046, D=18.6, H=65.2, Tchg=[0, 60], Tdis=[-40, 60], usd=4.5,
                         asm=["usd"],
                         src="Molicel INR-18650-P28A data sheet. DC resistance 20 mOhm at 10 A / 1 s. "
                             "One revision lists 8.4 A max charge; the lower 6 A is used."),
    "Molicel P42A": dict(fmt="21700", Q=4.2, Vnom=3.6, Vmax=4.2, Vmin=2.5, R25=0.016, Imax=45.0,
                         Ichg_max=4.2, m=0.070, D=21.7, H=70.2, Tchg=[0, 45], Tdis=[-40, 60], usd=5.0,
                         asm=["usd", "Ichg_max"],
                         src="Molicel INR-21700-P42A data sheet. DC 16 mOhm at 10 A / 1 s; 70 g max. "
                             "4.2 A is the standard charge current; a higher max was not confirmed."),
    "Samsung 30Q":  dict(fmt="18650", Q=3.0, Vnom=3.6, Vmax=4.2, Vmin=2.5, R25=0.026, Imax=15.0,
                         Ichg_max=4.0, m=0.048, D=18.4, H=65.0, Tchg=[0, 50], Tdis=[-20, 75], usd=5.0,
                         asm=["usd", "R25"],
                         src="Samsung SDI INR18650-30Q spec v1.0. 26 mOhm is the AC 1 kHz maximum; "
                             "no DC value is given, so it is used as an assumption."),
}

# ---- model parameters: value, tag ----------------------------------------------------------
PARAMS = {
    "cp_cell":    (950.0,  "ASM"),   # J/kg/K
    "R_T_slope":  (0.015,  "ASM"),   # 1/K, resistance falls as the cell warms
    "R_floor":    (0.008,  "ASM"),   # ohm
    "soc_gain":   (0.6,    "ASM"),   # resistance rise near empty: 1 + gain*exp(-soc/width)
    "soc_width":  (0.08,   "ASM"),
    "R_p":        (0.008,  "ASM"),   # polarization branch, ohm
    "tau_p":      (30.0,   "ASM"),   # s
    "R_ic_Ni":    (0.0030, "ASM"),   # interconnect resistance per parallel branch, ohm
    "R_ic_CuNi":  (0.0008, "ASM"),
    "sink_offset_liquid": (5.0, "ASM"),   # coolant return above ambient, K
    "R_shunt":    (0.0005, "ASM"),   # BQ769x0 current-sense resistor, ohm
    "R_fet":      (0.0010, "ASM"),   # charge + discharge FET on-resistance, ohm
    "cell_sigma": (0.08,   "ASM"),   # cell-to-cell DC resistance spread (1 sigma)
    "branch_sigma": (0.15, "ASM"),   # spread of busbar resistance between parallel branches
    "maldist":    (None,   "ASM"),   # None = take the 95th percentile of the Monte Carlo per design
    "eol_cap":    (0.80,   "ASM"),   # end of life: 80 % capacity ...
    "eol_res":    (1.50,   "ASM"),   # ... and 1.5x resistance (common EOL definition)
    "pitch_gap":  (1.5,    "ASM"),   # mm between cells (holder or foam web)
    "pcm_rho":    (0.77,   "ASM"),   # g/cm3, paraffin when molten (largest volume)
    "foam_porosity": (0.90, "ASM"),
    "cool_scale": (1.0,    "ASM"),   # multiplier on every thermal conductance (used by the uncertainty study)
    "usd_inr":    (95.0,   "ASM"),   # planning exchange rate; part prices are small-quantity USD list prices converted to INR
}
CELL_KEYS = ("Q_cell", "R25")        # cell values a calibration file may override
CALIB_CELL = "Molicel P28A"          # the cell the bench tests are run on
P = {k: v[0] for k, v in PARAMS.items()}
CALIB = {}

def load_calibration(path):
    for k, v in json.load(open(path)).items():
        if k in P or k in CELL_KEYS or k == "OCV":
            CALIB[k] = v
            if k in P: P[k] = v
    if "OCV" in CALIB:
        global OCV
        OCV = [tuple(x) for x in CALIB["OCV"]]

T_DERATE_BELOW = 5.0       # derate when the hot cell is within 5 K of the limit
MARGIN_K = 3.0
T_DESIGN_HOT = 40.0
BQ_OCD_MAX_V = 0.100       # BQ769x0 data sheet: highest OCD threshold across the sense resistor
BQ_SCALE_ERR = 0.10        # +-10 % scale error, +2.5 mV offset

OCV = [(0.0, 3.00), (0.05, 3.25), (0.10, 3.38), (0.20, 3.50), (0.40, 3.64),
       (0.50, 3.70), (0.60, 3.78), (0.80, 3.97), (0.90, 4.07), (1.0, 4.20)]  # generic NMC, ASM

def ocv(s):
    s = min(max(s, 0.0), 1.0)
    for (s0, v0), (s1, v1) in zip(OCV, OCV[1:]):
        if s <= s1:
            return v0 + (v1 - v0) * (s - s0) / (s1 - s0)
    return OCV[-1][1]

# ---- cooling options, per 16 cells; scaled with cell count (all ASM) --------------------------
COOL = {
    "air":     dict(G_ca=0.29),
    "pcm":     dict(G_cp=3.1, G_pa=0.30, m=0.150, Ts=34.0, Tl=36.0, L=240e3, block=True),
    "liquid":  dict(G_ca=10.0, sink=True),
    "hbtms":   dict(G_cp=60.0, G_pa=12.0, m=0.100, Ts=34.0, Tl=36.0, L=240e3, sink=True, foam=True),
    "hbtms47": dict(G_cp=60.0, G_pa=12.0, m=0.100, Ts=45.0, Tl=47.0, L=170e3, sink=True, foam=True),
    "single_air": dict(G_ca=0.06 * 16),   # one cell alone in still air, 0.06 W/K (ASM); used for datasheet checks
}
COOL_LABEL = {"air": "natural air", "pcm": "PCM block (35 C)", "liquid": "liquid cold plates",
              "hbtms": "liquid + foam + PCM (35 C)", "hbtms47": "liquid + foam + PCM (47 C)",
              "single_air": "single cell in still air"}
CP_PCM = 2000.0

DEFAULT_MISSION = dict(burst=140.0, base=60.0, burst_s=20.0, period_s=300.0)
DEFAULT_REQ = dict(R5_s=480, R5_Wh=100.0, R6_kg=1.5, R7_inr=19000.0, R8_h=1.5, R12_L=1.0)

REFERENCE = {
    "Baseline":    dict(cell="Molicel P28A", NS=4, NP=4, busbar="Ni",   cooling="air",     bal="passive"),
    "Option 1":    dict(cell="Molicel P28A", NS=4, NP=4, busbar="Ni",   cooling="pcm",     bal="passive"),
    "Option 2":    dict(cell="Molicel P28A", NS=4, NP=4, busbar="CuNi", cooling="hbtms",   bal="active"),
    "Option 2b":   dict(cell="Molicel P28A", NS=4, NP=4, busbar="CuNi", cooling="hbtms47", bal="active"),
    "Ablation 2a": dict(cell="Molicel P28A", NS=4, NP=4, busbar="CuNi", cooling="liquid",  bal="active"),
}

# ---- seeded random numbers, identical in Python and in the dashboard's JavaScript ------------
M32 = 0xFFFFFFFF
def _imul(a, b): return (a * b) & M32
def mulberry32(seed):
    st = [seed & M32]
    def rnd():
        st[0] = (st[0] + 0x6D2B79F5) & M32
        a = st[0]
        t = _imul(a ^ (a >> 15), 1 | a)
        t = ((t + _imul(t ^ (t >> 7), 61 | t)) & M32) ^ t
        return ((t ^ (t >> 14)) & M32) / 4294967296.0
    return rnd
def gauss_factory(rnd):
    def g():
        u1 = rnd() or 1e-12
        u2 = rnd()
        return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)
    return g

MC_N = 20000
def current_share_mc(R25, R_ic, NP, n=None, seed=1):
    """Parallel cells share one voltage, so current goes as 1/R. Draw each branch resistance from the
    cell spread plus the busbar-branch spread; report how much the worst cell carries vs the mean."""
    n = n or MC_N
    if NP < 2: return dict(mean=1.0, p95=1.0, p99=1.0, n=n)
    key = (R25, R_ic, NP, P["cell_sigma"], P["branch_sigma"], n, seed)
    if key in _MC_CACHE: return _MC_CACHE[key]
    g = gauss_factory(mulberry32(seed))
    worst = []
    for _ in range(n):
        cond = []
        for _ in range(NP):
            r = R25 * (1 + P["cell_sigma"] * g()) + R_ic * (1 + P["branch_sigma"] * g())
            cond.append(1.0 / r)
        worst.append(max(cond) / (sum(cond) / NP))
    worst.sort()
    out = dict(mean=sum(worst) / n, p95=worst[int(.95 * n)], p99=worst[int(.99 * n)], n=n)
    _MC_CACHE[key] = out
    return out
_MC_CACHE = {}

# ---- build a design from a configuration ---------------------------------------------------
def build(cfg, mission=None):
    c = dict(CELLS[cfg["cell"]])
    if cfg["cell"] == CALIB_CELL:
        if "Q_cell" in CALIB: c["Q"] = CALIB["Q_cell"]
        if "R25" in CALIB: c["R25"] = CALIB["R25"]
    NS, NP = int(cfg["NS"]), int(cfg["NP"])
    N = NS * NP
    s = N / 16.0
    cool = dict(COOL[cfg["cooling"]])
    for k in ("G_ca", "G_cp", "G_pa", "m"):
        if k in cool: cool[k] *= s
    for k in ("G_ca", "G_cp", "G_pa"):
        if k in cool: cool[k] *= P["cool_scale"]
    ric = P["R_ic_" + cfg["busbar"]]
    mc = current_share_mc(c["R25"], ric, NP)
    f = P["maldist"] if P["maldist"] is not None else mc["p95"]
    bo = BMS_OPT[cfg.get("bms", "standard")]
    d = dict(cfg=cfg, cell=c, NS=NS, NP=NP, N=N, cool=cool, ric=ric, mc=mc, f=f,
             R_shunt=bo["R_shunt"] or P["R_shunt"], R_fet=bo["R_fet"] or P["R_fet"],
             mission=dict(mission or DEFAULT_MISSION),
             T_MAX=min(60.0, c["Tdis"][1]))
    d["T_DERATE"] = d["T_MAX"] - T_DERATE_BELOW
    return d

class Thermal:
    """One lumped cell node, an optional PCM node (enthalpy method) and a sink."""
    def __init__(self, d, Tamb):
        c = d["cool"]; self.c = c
        self.Cc = d["N"] * d["cell"]["m"] * P["cp_cell"]
        self.Tsink = Tamb + (P["sink_offset_liquid"] if c.get("sink") else 0.0)
        self.Tc = Tamb
        self.m = c.get("m", 0.0)
        if self.m:   # PCM starts at ambient; above the melt window it is already molten (rule C9)
            Ts, Tl, L = c["Ts"], c["Tl"], c["L"]
            if Tamb <= Ts:   self.H = self.m * CP_PCM * (Tamb - Ts)
            elif Tamb < Tl:  self.H = self.m * L * (Tamb - Ts) / (Tl - Ts)
            else:            self.H = self.m * L + self.m * CP_PCM * (Tamb - Tl)
    def Tp(self):
        c, m = self.c, self.m
        if self.H <= 0:           return c["Ts"] + self.H / (m * CP_PCM)
        if self.H < m * c["L"]:   return c["Ts"] + (c["Tl"] - c["Ts"]) * self.H / (m * c["L"])
        return c["Tl"] + (self.H - m * c["L"]) / (m * CP_PCM)
    def step(self, q, dt):
        c = self.c
        qca = c.get("G_ca", 0.0) * (self.Tc - self.Tsink)
        qcp = 0.0
        if self.m:
            tp = self.Tp()
            qcp = c["G_cp"] * (self.Tc - tp)
            self.H += dt * (qcp - c["G_pa"] * (tp - self.Tsink))
        self.Tc += dt * (q - qcp - qca) / self.Cc

def hot(Tc, Tsink, f):
    """Hot-cell estimate. The worst parallel cell carries f times the mean current, so it makes f^2 the
    heat; its extra rise is (f^2-1) times the module's rise above the sink it rejects heat to."""
    return Tc + (f * f - 1.0) * max(0.0, Tc - Tsink)

def sim(d, profile, Tamb=25.0, t_limit=7200.0, dt=0.25, trace=False, eol=False, temp_stop=True):
    th = Thermal(d, Tamb)
    c = d["cell"]; NS, NP, N, f = d["NS"], d["NP"], d["N"], d["f"]
    Q = c["Q"] * (P["eol_cap"] if eol else 1.0)
    R25 = c["R25"] * (P["eol_res"] if eol else 1.0)
    ric = d["ric"]; T_MAX, T_DER = d["T_MAX"], d["T_DERATE"]
    soc, vp, t = 1.0, 0.0, 0.0
    Ah = Wh = Qloss = Tint = I2 = Eoc = 0.0
    Tmax = Thmax = Tamb
    Vmin = 99.0
    t55 = t60 = None
    reason = "profile complete"
    curve = []
    while t < t_limit:
        I = profile(t)
        if I is None: break
        Ic = I / NP
        R = max(R25 * math.exp(-P["R_T_slope"] * (th.Tc - 25.0)), P["R_floor"])
        R *= 1.0 + P["soc_gain"] * math.exp(-soc / P["soc_width"])
        Reff = R + ric
        Vc = ocv(soc) - Ic * Reff - vp
        if Vc < c["Vmin"]: reason = "undervoltage cutoff"; break
        if soc <= 0.0: reason = "capacity exhausted"; break
        q = N * (Ic * Ic * Reff + vp * vp / P["R_p"])
        Eoc += NS * ocv(soc) * I * dt / 3600
        Wh += NS * Vc * I * dt / 3600; Ah += I * dt / 3600
        Qloss += q * dt; I2 += I * I * dt; Tint += th.Tc * dt
        th.step(q, dt)
        vp += dt * (Ic * P["R_p"] - vp) / P["tau_p"]
        soc -= Ic * dt / 3600 / Q
        Vmin = min(Vmin, NS * Vc)
        t += dt
        Th = hot(th.Tc, th.Tsink, f)
        Tmax = max(Tmax, th.Tc); Thmax = max(Thmax, Th)
        if trace and int(round(t / dt)) % 4 == 0:
            curve.append((round(t, 2), round(Th, 2), round(NS * Vc, 3)))
        if t55 is None and Th >= T_DER: t55 = t
        if Th >= T_MAX and t60 is None:
            t60 = t
            if temp_stop: reason = "hot-cell limit"; break
    out = dict(t=t, reason=reason, Ah=Ah, Wh=Wh, Eoc_Wh=Eoc, Qloss_kJ=Qloss / 1e3, Tavg_max=Tmax,
               Thot_max=Thmax, t55=t55, t60=t60, Vmin=Vmin,
               Tmean=Tint / max(t, 1e-9), Irms=math.sqrt(I2 / max(t, 1e-9)))
    if trace: out["curve"] = curve
    return out

def mission_profile(m, k=1.0):
    b, B, bs, ps = m["burst"], m["base"], m["burst_s"], m["period_s"]
    return lambda t: k * (b if (t % ps) < bs else B)
CONST = lambda I: (lambda t: I)

def max_const_current(d, Tamb):
    top = d["mission"]["burst"]
    ok = lambda I: sim(d, CONST(I), Tamb, dt=0.5)["t60"] is None
    if ok(top): return top
    lo, hi = 1.0, top
    for _ in range(12):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if ok(mid) else (lo, mid)
    return lo

def max_derate(d, Tamb, margin=0.0):
    """Largest scale k on the whole mission so the hot cell stays below the limit minus margin."""
    ok = lambda k: sim(d, mission_profile(d["mission"], k), Tamb, dt=0.5)["Thot_max"] <= d["T_MAX"] - margin
    lo, hi = 0.05, 1.0
    if ok(hi): return 1.0
    for _ in range(12):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if ok(mid) else (lo, mid)
    return lo

def charge(d, crate=1.0, Tamb=25.0):
    """CC to 80 %, then a 0.5 h CV taper (both ASM, +-20 %). Returns time and hot-cell temperature."""
    c = d["cell"]; Q = d["NP"] * c["Q"]; I_mod = crate * Q
    f_cc, t_cv = 0.80, 0.5
    t_cc = f_cc / crate * 3600
    th = Thermal(d, Tamb); Ic = I_mod / d["NP"]
    q = d["N"] * Ic * Ic * (c["R25"] + d["ric"])
    t = 0.0
    while t < t_cc:
        th.step(q, 0.5); t += 0.5
    return dict(hours=t_cc / 3600 + t_cv, dT_cc=th.Tc - Tamb, heat_W=q, I_cell=Ic,
                Thot_end=hot(th.Tc, th.Tsink, d["f"]))

# ---- bill of materials (g, USD; small-quantity retail, +-30 %, ASM) ------------------------------
BMS_OPT = {   # sense resistor and FET path (both ASM); low-loss = 4 parallel FETs per direction, 0.25 mOhm shunt
    "standard": dict(R_shunt=None, R_fet=None, g=0, usd=0.0),
    "lowloss":  dict(R_shunt=0.00025, R_fet=0.0005, g=10, usd=8.0),
}

def bms_chip(NS):
    if 3 <= NS <= 5:   return "BQ76920", 45, 18.0
    if 6 <= NS <= 10:  return "BQ76930", 55, 24.0
    if 9 <= NS <= 15:  return "BQ76940", 65, 30.0
    return None, 45, 18.0

def bom(d):
    cfg, N, NS = d["cfg"], d["N"], d["NS"]; s = N / 16.0; c = d["cell"]
    liq = cfg["cooling"] in ("liquid", "hbtms", "hbtms47")
    chip, g_bms, usd_bms = bms_chip(NS)
    bo = BMS_OPT[cfg.get("bms", "standard")]; g_bms += bo["g"]; usd_bms += bo["usd"]
    items = [(f"{N} x {cfg['cell']} cells", N * c["m"] * 1000, N * c["usd"], False),
             ("wiring and connector", 90, 12.0, False),
             (f"BMS ({chip or 'no BQ769x0 fits'}, {cfg.get('bms','standard')} FETs and shunt)", g_bms, usd_bms, False)]
    if not liq:
        items.append(("cell holders", 60 * s, 4.0 * s, False))
    items.append(("busbar, Ni strip", 30 * s, 5.0 * s, False) if cfg["busbar"] == "Ni"
                 else ("busbar, Cu-Ni clad", 55 * s, 14.0 * s, False))
    if cfg["cooling"] == "pcm":
        items.append(("PCM block + container", 200 * s, 10.0 * s, False))
    if cfg["cooling"] in ("hbtms", "hbtms47"):
        items += [("PCM", 100 * s, 3.0 * s, False), ("Al foam", 23 * s, 12.0 * s, False)]
    if cfg["bal"] == "active":
        items.append((f"ETA3000 x{NS-1} + inductors", 5 * (NS - 1), 13.0 / 3 * (NS - 1), False))
    if liq:
        items += [("cold plates x2", 120 * s, 24.0 * s, False), ("coolant, tubing, fittings", 100, 10.0, False),
                  ("enclosure and seals", 40 * s, 5.0 * s, False),
                  ("pump (vehicle side)", 60, 15.0, True), ("radiator + reservoir", 250, 20.0, True)]
    mod = [(g, u) for _, g, u, loop in items if not loop]
    r0 = lambda x: int(math.floor(x + 0.5))                     # round half up, as the dashboard does
    r1 = lambda x: math.floor(x * 10 + 0.5) / 10
    r2 = lambda x: math.floor(x * 100 + 0.5) / 100
    fx = P["usd_inr"]                                           # costs are reported in INR
    return dict(items=[dict(item=i, g=r1(g), inr=r0(u * fx), vehicle_side=l) for i, g, u, l in items],
                mass_module=r0(sum(g for g, _ in mod)), inr_module=r0(sum(u for _, u in mod) * fx),
                mass_system=r0(sum(g for _, g, _, _ in items)), inr_system=r0(sum(u for _, _, u, _ in items) * fx),
                chip=chip)

# ---- geometry: envelope, volume, PCM fit (all dimensions ASM except the cell size) ------------
def geometry(d):
    c, N, cfg = d["cell"], d["N"], d["cfg"]
    pitch = c["D"] + P["pitch_gap"]
    cols = math.ceil(math.sqrt(N)); rows = math.ceil(N / cols)
    bx, by, bh = cols * pitch, rows * pitch, c["H"]                 # cell block, mm
    liq = cfg["cooling"] in ("liquid", "hbtms", "hbtms47")
    wall = 2.0 if liq else 1.5                                       # enclosure wall or holder rim
    L = bx + 2 * wall + (2 * 6.0 if liq else 0.0)                   # two 6 mm cold plates
    W = by + 2 * wall
    H = bh + 2 * 4.0 + 12.0                                          # busbar + holder layers, BMS board
    pcm = dict(needed_cm3=0.0, gap_cm3=0.0, overflow_cm3=0.0)
    m_pcm = d["cool"].get("m", 0.0) * 1000                          # g
    if cfg["cooling"] == "pcm":                                      # separate block on one side
        vol = m_pcm / P["pcm_rho"] * 1.2                             # +20 % container
        L += vol * 1000 / (W * H)
        pcm["needed_cm3"] = m_pcm / P["pcm_rho"]
    if d["cool"].get("foam"):                                        # PCM in foam between the cells
        gap = (bx * by * bh - N * math.pi * (c["D"] / 2) ** 2 * bh) / 1000 * P["foam_porosity"]
        need = m_pcm / P["pcm_rho"]
        over = max(0.0, need - gap)
        H += over * 1000 / (bx * by)                                  # overflow sits as a layer on top
        pcm.update(needed_cm3=need, gap_cm3=gap, overflow_cm3=over)
    vol_L = L * W * H / 1e6
    E = d["NS"] * d["NP"] * c["Q"] * c["Vnom"]
    return dict(L_mm=round(L, 1), W_mm=round(W, 1), H_mm=round(H, 1), volume_L=round(vol_L, 3),
                Wh_per_L=round(E / vol_L, 1), E_nom_Wh=round(E, 1), grid=f"{cols} x {rows}", pcm=pcm)

def balancing(d, imbalance=0.05):
    q = imbalance * d["NP"] * d["cell"]["Q"]                          # Ah to move in one series group
    if d["cfg"]["bal"] == "passive":
        i = 0.075                                                     # 50-100 mA bleed, ASM
        return dict(hours=q / i, heat_W=i * 4.1, waste_Wh=q * 3.9)
    i = 1.0                                                           # 1 A planning value, 2 A vendor peak
    return dict(hours=q / i, heat_W=i * 3.9 * 0.08, waste_Wh=q * 3.9 * 0.08)

# ---- requirements and checker ---------------------------------------------------------------------
def thermal_verdict(run, T_MAX):
    if run["t60"] is not None: return "FAIL"
    return "MARGINAL" if T_MAX - run["Thot_max"] < MARGIN_K else "PASS"

def verdicts(d, r, REQ):
    c, m = d["cell"], d["mission"]; m25, m40, eol = r["mission25"], r["mission40"], r["mission25_eol"]
    b, g = r["bom"], r["geom"]; TM = d["T_MAX"]
    v = []
    v.append(("R3 / C1", f"hot cell < {TM:.0f} C, mission at 25 C", thermal_verdict(m25, TM),
              f"Thot {m25['Thot_max']:.1f} C, ran {m25['t']:.0f} s ({m25['reason']})"))
    v.append(("R4 / C1", f"hot cell < {TM:.0f} C, mission at 40 C", thermal_verdict(m40, TM),
              f"Thot {m40['Thot_max']:.1f} C, ran {m40['t']:.0f} s ({m40['reason']}); "
              f"derated mission k = {r['derate40_3K']:.2f} passes with 3 K margin"))
    ok5 = lambda x: x["t"] >= REQ["R5_s"] and x["Wh"] >= REQ["R5_Wh"]
    v.append(("R5", f">= {REQ['R5_s']} s and >= {REQ['R5_Wh']:.0f} Wh at 25 C", "PASS" if ok5(m25) else "FAIL",
              f"{m25['t']:.0f} s, {m25['Wh']:.0f} Wh"))
    v.append(("R11", "R5 still met at end of life (80 % capacity, 1.5x resistance)",
              "PASS" if ok5(eol) and eol["t60"] is None else "FAIL",
              f"{eol['t']:.0f} s, {eol['Wh']:.0f} Wh, Thot {eol['Thot_max']:.1f} C ({eol['reason']})"))
    worst = m["burst"] / d["NP"] * d["f"]
    v.append(("C2", f"worst branch current <= {c['Imax']:.0f} A at {m['burst']:.0f} A burst",
              "FAIL" if m["burst"] / d["NP"] > c["Imax"] else ("WARN" if worst > c["Imax"] else "PASS"),
              f"mean {m['burst']/d['NP']:.1f} A, worst {worst:.1f} A (factor {d['f']:.3f}, 95th pct)"))
    pf = m["burst"] ** 2 * (d["R_shunt"] + d["R_fet"])
    v.append(("C4", "BMS FET + shunt dissipation <= 15 W", "WARN" if pf > 15 else "PASS",
              f"{pf:.0f} W at {m['burst']:.0f} A"))
    v_ocd = m["burst"] * (1 + BQ_SCALE_ERR) * d["R_shunt"] + 0.0025
    v.append(("C11", "BQ769x0 OCD threshold (max 100 mV) above burst + 10 % error",
              "PASS" if v_ocd <= BQ_OCD_MAX_V else "FAIL",
              f"needs {v_ocd*1e3:.0f} mV across {d['R_shunt']*1e3:.2f} mOhm shunt"))
    cool = COOL[d["cfg"]["cooling"]]
    if cool.get("m"):
        v.append(("C9", f"PCM melt window above {T_DESIGN_HOT:.0f} C design ambient",
                  "PASS" if cool["Tl"] > T_DESIGN_HOT else "FAIL", f"melts {cool['Ts']:.0f}-{cool['Tl']:.0f} C"))
    if cool.get("foam"):
        p = g["pcm"]
        v.append(("C12", "PCM fits in the foam between the cells", "PASS" if p["overflow_cm3"] <= 0 else "WARN",
                  f"needs {p['needed_cm3']:.0f} cm3 molten, gaps hold {p['gap_cm3']:.0f} cm3; "
                  f"{p['overflow_cm3']:.0f} cm3 overflows into a top layer"))
    ch = r["charge1c"]; chh = r["charge1c_hot"]
    v.append(("C5", f"cell inside its charge window ({c['Tchg'][0]}-{c['Tchg'][1]} C), 1C charge at 40 C",
              "FAIL" if chh["Thot_end"] > c["Tchg"][1] else ("MARGINAL" if c["Tchg"][1] - chh["Thot_end"] < MARGIN_K else "PASS"),
              f"hot cell {chh['Thot_end']:.1f} C at end of CC phase"))
    v.append(("C6", f"charge current <= {c['Ichg_max']:.1f} A per cell at 1C", "PASS" if ch["I_cell"] <= c["Ichg_max"] else "FAIL",
              f"{ch['I_cell']:.1f} A per cell"))
    v.append(("C8", "a BQ769x0 front end covers NS", "PASS" if b["chip"] else "FAIL",
              f"NS = {d['NS']} -> {b['chip'] or 'none (needs 3-15 cells)'}"))
    v.append(("R6", f"module mass <= {REQ['R6_kg']} kg", "PASS" if b["mass_module"] / 1000 <= REQ["R6_kg"] else "FAIL",
              f"{b['mass_module']} g (+{b['mass_system']-b['mass_module']} g vehicle-side loop)"))
    v.append(("R7", f"module BOM <= ₹{REQ['R7_inr']:,.0f}", "PASS" if b["inr_module"] <= REQ["R7_inr"] else "FAIL",
              f"₹{b['inr_module']:,} (+₹{b['inr_system']-b['inr_module']:,} loop)"))
    v.append(("R8", f"charge at 1C <= {REQ['R8_h']} h", "PASS" if ch["hours"] <= REQ["R8_h"] else "FAIL",
              f"{ch['hours']:.2f} h, CC rise {ch['dT_cc']:.1f} K"))
    v.append(("R12", f"module envelope <= {REQ['R12_L']} L", "PASS" if g["volume_L"] <= REQ["R12_L"] else "FAIL",
              f"{g['L_mm']:.0f} x {g['W_mm']:.0f} x {g['H_mm']:.0f} mm = {g['volume_L']:.2f} L, {g['Wh_per_L']:.0f} Wh/L"))
    fails = [x[0] for x in v if x[2] == "FAIL"]
    v.append(("C10", "all requirements and hard rules met", "FAIL" if fails else "PASS",
              ("fails: " + ", ".join(fails)) if fails else "no FAIL"))
    return v

def plausibility(Tmodel, Tsensor, thr=5.0, hold=10, dt=1.0):
    run = 0
    for i, (a, b) in enumerate(zip(Tmodel, Tsensor)):
        run = run + 1 if abs(a - b) > thr else 0
        if run * dt >= hold: return i * dt
    return None

def sensor_selftest():
    """Thermistor reads 12 K low from t = 100 s. Tests the checker logic, not the model."""
    d = build(REFERENCE["Option 2"]); th = Thermal(d, 25.0); f = mission_profile(d["mission"])
    Tm, Ts = [], []
    for k in range(600):
        for j in range(4):
            Ic = f(k + j * 0.25) / d["NP"]
            th.step(d["N"] * Ic * Ic * (d["cell"]["R25"] + d["ric"]), 0.25)
        Tm.append(th.Tc); Ts.append(th.Tc - (12 if k >= 100 else 0))
    return plausibility(Tm, Ts)

# ---- traceability: requirement -> component -> assumption -> model -> result -> evidence -> status ---
def trace(d, r):
    m25, m40, eol = r["mission25"], r["mission40"], r["mission25_eol"]
    def tag(*ks):
        return "calibrated" if all(k in CALIB for k in ks) else "uncalibrated (ASM)"
    cfg = d["cfg"]
    return [
        ("R1", f"{d['N']} x {cfg['cell']}, {d['NS']}S{d['NP']}P", "datasheet capacity at 25 C", "hand calculation",
         f"{d['NS']*d['cell']['Vnom']:.1f} V, {d['NP']*d['cell']['Q']:.1f} Ah, {r['geom']['E_nom_Wh']:.0f} Wh",
         "datasheet; test T1", "calibrated" if "Q_cell" in CALIB else "datasheet"),
        ("R2 / C2", "busbar, parallel branches", f"cell spread {P['cell_sigma']:.0%}, branch spread {P['branch_sigma']:.0%}",
         "Monte Carlo + checker C2", f"factor {d['f']:.3f}, worst branch {d['mission']['burst']/d['NP']*d['f']:.1f} A",
         "pulse-rating check; test T5", tag("cell_sigma", "branch_sigma")),
        ("R3", COOL_LABEL[cfg["cooling"]], "G values, sink offset, hot-cell factor", "thermal node model",
         f"{m25['Thot_max']:.1f} C hot cell, {thermal_verdict(m25, d['T_MAX'])}", "heating test T2", tag("cp_cell")),
        ("R4", "cooling + derating rule", f"sink at ambient + {P['sink_offset_liquid']:.0f} K", "thermal model, derate sweep",
         f"{thermal_verdict(m40, d['T_MAX'])}; derate k = {r['derate40_3K']:.2f} with 3 K margin",
         "warm-ambient test T3; radiator test", tag("sink_offset_liquid")),
        ("R5", "cells, busbar", "R(T, SOC), polarization, OCV table", "electrical model",
         f"{m25['Wh']:.0f} Wh in {m25['t']:.0f} s", "tests T1, T4", tag("R_p", "tau_p", "R25")),
        ("R11", "cells at end of life", "80 % capacity, 1.5x resistance", "electrical + thermal model",
         f"{eol['Wh']:.0f} Wh in {eol['t']:.0f} s", "cycling data or aged-cell test", tag("eol_cap", "eol_res")),
        ("R6", "BOM", "part masses", "roll-up", f"{r['bom']['mass_module']} g", "weighing the mock-up", "uncalibrated (ASM)"),
        ("R7", "BOM", "retail prices +-30 %", "roll-up", f"₹{r['bom']['inr_module']:,}", "vendor quotes", "uncalibrated (ASM)"),
        ("R8", "CC-CV charger", "CC to 80 %, 0.5 h CV", "charge model", f"{r['charge1c']['hours']:.2f} h", "test T6", "uncalibrated (ASM)"),
        ("R12", "layout, cold plates, enclosure", "1.5 mm pitch gap, 6 mm plates, 2 mm walls", "geometry roll-up",
         f"{r['geom']['volume_L']:.2f} L, {r['geom']['Wh_per_L']:.0f} Wh/L", "measuring the mock-up", "uncalibrated (ASM)"),
    ]

# ---- one design, end to end -----------------------------------------------------------------------
def evaluate(name, cfg, mission=None, REQ=None, fast=False):
    REQ = REQ or DEFAULT_REQ
    d = build(cfg, mission)
    mp = mission_profile(d["mission"])
    r = dict(config=cfg, label=label(cfg))
    r["peak25"] = sim(d, CONST(d["mission"]["burst"]), 25.0)
    r["mission25"] = sim(d, mp, 25.0, trace=True)
    r["mission40"] = sim(d, mp, 40.0, trace=True)
    r["mission25_eol"] = sim(d, mp, 25.0, eol=True)
    if fast:
        r["imax25"] = r["imax40"] = r["derate40"] = float("nan"); r["derate40_3K"] = float("nan")
    else:
        r["imax25"], r["imax40"] = max_const_current(d, 25.0), max_const_current(d, 40.0)
        r["derate40"], r["derate40_3K"] = max_derate(d, 40.0), max_derate(d, 40.0, MARGIN_K)
    r["charge1c"], r["charge2c"] = charge(d, 1.0), charge(d, 2.0)
    r["charge1c_hot"] = charge(d, 1.0, T_DESIGN_HOT)
    r["bom"], r["geom"], r["bal"] = bom(d), geometry(d), balancing(d)
    r["Wh_per_kg"] = r["geom"]["E_nom_Wh"] / (r["bom"]["mass_module"] / 1000)
    r["current_factor"] = d["f"]; r["mc"] = d["mc"]; r["T_MAX"] = d["T_MAX"]
    r["ageing_index"] = 2 ** ((r["mission25"]["Tmean"] - 25) / 10)
    r["ageing_comparable"] = r["mission25"]["reason"] in ("undervoltage cutoff", "capacity exhausted")
    r["verdicts"] = verdicts(d, r, REQ)
    r["trace"] = trace(d, r)
    return r

def label(cfg):
    return (f"{cfg['NS']}S{cfg['NP']}P {cfg['cell']}, {'Cu-Ni' if cfg['busbar']=='CuNi' else 'Ni'} busbar, "
            f"{cfg['bal']} balancing, {COOL_LABEL[cfg['cooling']]}" + (", low-loss BMS" if cfg.get("bms") == "lowloss" else ""))

# ---- sensitivity of the recommended design to the two assumptions that matter most -------------------
def sensitivity(cfg, mission=None):
    out = dict(sink_offset=[], current_factor=[])
    keep_s, keep_f = P["sink_offset_liquid"], P["maldist"]
    for s in (0.0, 2.0, 3.0, 5.0, 8.0):
        P["sink_offset_liquid"] = s
        d = build(cfg, mission); m = sim(d, mission_profile(d["mission"]), 40.0)
        out["sink_offset"].append(dict(offset_K=s, t40=m["t"], Wh40=m["Wh"], reason=m["reason"],
                                       k3=max_derate(d, 40.0, MARGIN_K)))
    P["sink_offset_liquid"] = keep_s
    for f in (1.00, 1.10, 1.15, 1.20):
        P["maldist"] = f
        d = build(cfg, mission)
        out["current_factor"].append(dict(f=f, Thot25=sim(d, mission_profile(d["mission"]), 25.0)["Thot_max"],
                                          k3=max_derate(d, 40.0, MARGIN_K)))
    P["maldist"] = keep_f
    return out

# ---- model self-checks (no bench data needed) ----------------------------------------------------------
def verify():
    out = {}
    q, G, t_end = 100.0, 0.29, 120.0
    d = build(REFERENCE["Baseline"]); th = Thermal(d, 25.0)
    for _ in range(int(t_end / 0.25)): th.step(q, 0.25)
    exact = 25.0 + q / G * (1 - math.exp(-G * t_end / th.Cc))
    out["thermal_vs_closed_form"] = dict(model=th.Tc, exact=exact, err_K=th.Tc - exact)
    d = build(REFERENCE["Ablation 2a"]); mp = mission_profile(d["mission"])
    a, b = sim(d, mp, 25.0, dt=0.25), sim(d, mp, 25.0, dt=0.05)
    out["dt_convergence_2a"] = dict(Wh_025=a["Wh"], Wh_005=b["Wh"], Thot_025=a["Thot_max"], Thot_005=b["Thot_max"])
    lost = a["Eoc_Wh"] - a["Wh"]; heat = a["Qloss_kJ"] * 1e3 / 3600
    out["energy_balance_2a"] = dict(Eoc_minus_delivered_Wh=lost, heat_Wh=heat, residual_Wh=lost - heat)
    d2 = build(REFERENCE["Option 2"]); mp2 = mission_profile(d2["mission"])
    out["repeatable"] = sim(d2, mp2, 25.0)["Wh"] == sim(d2, mp2, 25.0)["Wh"]
    # scaling check: 4S8P with twice the cells, cooling and capacity should run the same mission at half
    # the per-cell current, so it must deliver more energy and run cooler than 4S4P
    d8 = build(dict(REFERENCE["Ablation 2a"], NP=8)); m8 = sim(d8, mission_profile(d8["mission"]), 25.0)
    out["scaling_4s8p_vs_4s4p"] = dict(Wh_4s4p=a["Wh"], Wh_4s8p=m8["Wh"], Thot_4s4p=a["Thot_max"],
                                       Thot_4s8p=m8["Thot_max"], ok=m8["Wh"] > a["Wh"] and m8["Thot_max"] < a["Thot_max"])
    return out


# ---- external evidence: model against the manufacturer's specification and independent tests ------------
# Molicel INR-18650-P28A product specification, section 5.2: minimum capacity to 2.5 V after a standard
# charge, single cell at 23 C (and at 2.8 A for 45 C and 0 C). Independent test (Battery Mooch): four cells
# delivered 2.745-2.787 Ah at 0.56 A. These are real published numbers, not our assumptions.
SPEC_MIN = [(0.56, 23.0, 2.70), (2.8, 23.0, 2.60), (10.0, 23.0, 2.55), (15.0, 23.0, 2.50), (20.0, 23.0, 2.50),
            (2.8, 45.0, 2.60), (2.8, 0.0, 2.10)]
INDEP_056 = (2.745, 2.787)

def datasheet_check():
    cfg = dict(cell="Molicel P28A", NS=1, NP=1, busbar="CuNi", cooling="single_air", bal="passive")
    keep = P["R_ic_CuNi"]; P["R_ic_CuNi"] = 0.0                  # bare cell, no busbar
    d = build(cfg)
    rows = []
    for I, T, mn in SPEC_MIN:
        r = sim(d, CONST(I), T, dt=0.5 if I < 3 else 0.25, t_limit=8 * 3600, temp_stop=False)
        rows.append(dict(I_A=I, Tamb_C=T, spec_min_Ah=mn, model_Ah=r["Ah"], Tmax_C=r["Tavg_max"],
                         verdict="model >= spec minimum" if r["Ah"] >= mn else "model BELOW spec minimum"))
    r25 = sim(d, CONST(25.0), 23.0, temp_stop=False)
    P["R_ic_CuNi"] = keep
    # the model keeps the full 2.8 Ah at any current, the specification guarantees only 2.50 Ah at 15-20 A.
    # So re-run the finalists with a cell that has only the guaranteed minimum capacity.
    worst = {}
    keepQ = CELLS["Molicel P28A"]["Q"]; CELLS["Molicel P28A"]["Q"] = 2.50
    for name, cfg in (("Ablation 2a", REFERENCE["Ablation 2a"]),
                      ("R-B", dict(cell="Molicel P28A", NS=4, NP=5, busbar="CuNi", cooling="liquid", bal="passive", bms="lowloss"))):
        dd = build(cfg); mp = mission_profile(dd["mission"])
        a, b, e = sim(dd, mp, 25.0), sim(dd, mp, 40.0), sim(dd, mp, 25.0, eol=True)
        worst[name] = dict(t25=a["t"], Wh25=a["Wh"], T25=a["Thot_max"], t40=b["t"], Wh40=b["Wh"], T40=b["Thot_max"], r40=b["reason"],
                           t_eol=e["t"], Wh_eol=e["Wh"], R5=a["t"] >= 480 and a["Wh"] >= 100, R11=e["t"] >= 480 and e["Wh"] >= 100 and e["t60"] is None)
    CELLS["Molicel P28A"]["Q"] = keepQ
    return dict(spec=rows, indep_056=dict(measured_Ah=INDEP_056, model_Ah=rows[0]["model_Ah"]),
                at_25A=dict(Ah=r25["Ah"], Tmax_C=r25["Tavg_max"], t_s=r25["t"]), spec_min_capacity_runs=worst,
                cycle_life="spec: >= 80 % capacity after 500 cycles at 10 A, 23 C; review of the spec: 400 cycles to 80 % at 20 A")

# ---- uncertainty propagation: how likely is each verdict, given the ranges of all assumptions? -------------
UQ_RANGES = {   # (low, high), uniform; spreads chosen to cover typical datasheet-to-cell and model-form error
    "cp_cell": (850.0, 1050.0), "R_T_slope": (0.010, 0.020), "soc_gain": (0.3, 0.9), "R_p": (0.005, 0.011),
    "tau_p": (20.0, 40.0), "R_ic_CuNi": (0.0005, 0.0012), "R_ic_Ni": (0.002, 0.004),
    "sink_offset_liquid": (3.0, 7.0), "cell_sigma": (0.05, 0.11), "cool_scale": (0.75, 1.25), "R25_scale": (0.9, 1.1),
}
def uncertainty(cfg, n=300, seed=7, mission=None):
    rnd = mulberry32(seed); keep = dict(P); keepR = CELLS[cfg["cell"]]["R25"]
    global MC_N; mcn = MC_N; MC_N = 4000
    out = []
    for _ in range(n):
        x = {k: lo + (hi - lo) * rnd() for k, (lo, hi) in UQ_RANGES.items()}
        for k, v in x.items():
            if k in P: P[k] = v
        CELLS[cfg["cell"]]["R25"] = keepR * x["R25_scale"]
        d = build(cfg, mission); mp = mission_profile(d["mission"])
        a, b, e = sim(d, mp, 25.0, dt=0.5), sim(d, mp, 40.0, dt=0.5), sim(d, mp, 25.0, dt=0.5, eol=True)
        ok5 = lambda z: z["t"] >= DEFAULT_REQ["R5_s"] and z["Wh"] >= DEFAULT_REQ["R5_Wh"]
        out.append(dict(R3=a["t60"] is None, R4=b["t60"] is None, R4m=b["t60"] is None and d["T_MAX"] - b["Thot_max"] >= MARGIN_K,
                        R5=ok5(a), R11=ok5(e) and e["t60"] is None, T25=a["Thot_max"], T40=b["Thot_max"], Wh25=a["Wh"], x=x))
    P.clear(); P.update(keep); CELLS[cfg["cell"]]["R25"] = keepR; MC_N = mcn; _MC_CACHE.clear()
    pr = lambda k: sum(o[k] for o in out) / n
    q = lambda k, f: sorted(o[k] for o in out)[int(f * (n - 1))]
    # which assumption drives the hot-day temperature? rank by correlation with T40
    def corr(k):
        xs = [o["x"][k] for o in out]; ys = [o["T40"] for o in out]
        mx, my = sum(xs) / n, sum(ys) / n
        sxy = sum((a - mx) * (b - my) for a, b in zip(xs, ys)); sxx = sum((a - mx) ** 2 for a in xs); syy = sum((b - my) ** 2 for b in ys)
        return sxy / math.sqrt(sxx * syy) if sxx and syy else 0.0
    drivers = sorted(((k, corr(k)) for k in UQ_RANGES), key=lambda z: -abs(z[1]))
    return dict(n=n, p_R3=pr("R3"), p_R4=pr("R4"), p_R4_margin=pr("R4m"), p_R5=pr("R5"), p_R11=pr("R11"),
                p_all=sum(o["R3"] and o["R4"] and o["R5"] and o["R11"] for o in out) / n,
                T25_p5_p50_p95=(q("T25", .05), q("T25", .5), q("T25", .95)), T40_p5_p50_p95=(q("T40", .05), q("T40", .5), q("T40", .95)),
                Wh25_p5_p50_p95=(q("Wh25", .05), q("Wh25", .5), q("Wh25", .95)), drivers_T40=drivers[:5])

# ---- automatic design search: every combination, then the trade-off front --------------------------------
SEARCH_SPACE = dict(cell=list(CELLS), NP=[3, 4, 5, 6], busbar=["Ni", "CuNi"], cooling=["air", "pcm", "liquid", "hbtms", "hbtms47"],
                    bal=["passive", "active"], bms=["standard", "lowloss"])
def quick_eval(cfg, mission=None, REQ=None):
    REQ = REQ or DEFAULT_REQ
    d = build(cfg, mission); mp = mission_profile(d["mission"])
    r = dict(config=cfg, label=label(cfg))
    r["mission25"], r["mission40"] = sim(d, mp, 25.0, dt=0.5), sim(d, mp, 40.0, dt=0.5)
    r["mission25_eol"] = sim(d, mp, 25.0, dt=0.5, eol=True)
    r["derate40_3K"] = float("nan")
    r["charge1c"], r["charge1c_hot"] = charge(d, 1.0), charge(d, 1.0, T_DESIGN_HOT)
    r["bom"], r["geom"] = bom(d), geometry(d)
    r["verdicts"] = verdicts(d, r, REQ)
    lv = {v[0]: v[2] for v in r["verdicts"]}
    r["n_fail"] = sum(1 for k, v in lv.items() if v == "FAIL" and k != "C10")
    r["n_warn"] = sum(1 for v in lv.values() if v == "WARN")
    r["margin40"] = d["T_MAX"] - r["mission40"]["Thot_max"] if r["mission40"]["t60"] is None else 0.0
    return r

def design_search(NS=4, mission=None):
    import itertools
    S = SEARCH_SPACE; rows = []
    for cell, NP, bus, cool, bal, bms in itertools.product(S["cell"], S["NP"], S["busbar"], S["cooling"], S["bal"], S["bms"]):
        cfg = dict(cell=cell, NS=NS, NP=NP, busbar=bus, cooling=cool, bal=bal, bms=bms)
        r = quick_eval(cfg, mission)
        rows.append(dict(cfg=cfg, fails=[v[0] for v in r["verdicts"] if v[2] == "FAIL" and v[0] != "C10"],
                         warns=[v[0] for v in r["verdicts"] if v[2] == "WARN"], mass=r["bom"]["mass_module"], inr=r["bom"]["inr_module"],
                         vol=r["geom"]["volume_L"], Wh25=r["mission25"]["Wh"], margin40=r["margin40"], eolWh=r["mission25_eol"]["Wh"]))
    ok = [x for x in rows if not x["fails"]]
    clean = [x for x in ok if not x["warns"]]
    def dominated(a, pool):   # lower cost, lower mass, higher hot-day margin are all better
        return any(b is not a and b["inr"] <= a["inr"] and b["mass"] <= a["mass"] and b["margin40"] >= a["margin40"]
                   and (b["inr"] < a["inr"] or b["mass"] < a["mass"] or b["margin40"] > a["margin40"]) for b in pool)
    front = sorted([x for x in clean if not dominated(x, clean)], key=lambda z: z["inr"])
    fail_count = {}
    for x in rows:
        for f in x["fails"]: fail_count[f] = fail_count.get(f, 0) + 1
    return dict(n=len(rows), n_pass=len(ok), n_clean=len(clean), front=front, fail_count=fail_count, rows=rows)

# ---- markdown tables for the design document ----------------------------------------------------------
def tables_md(res, extra):
    n = list(res)
    L = []
    row = lambda name, f: L.append(f"| {name} | " + " | ".join(f(res[k]) for k in n) + " |")
    L.append("| | " + " | ".join(n) + " |"); L.append("|---" * (len(n) + 1) + "|")
    row("25 C: run time", lambda r: f"{r['mission25']['t']:.0f} s")
    row("Stopped by", lambda r: r["mission25"]["reason"])
    row("Energy delivered", lambda r: f"{r['mission25']['Wh']:.0f} Wh")
    row("Hot cell, maximum", lambda r: f"{r['mission25']['Thot_max']:.1f} C")
    row("First above derate line", lambda r: f"{r['mission25']['t55']:.0f} s" if r['mission25']['t55'] else "never")
    row("40 C: run time", lambda r: f"{r['mission40']['t']:.0f} s")
    row("40 C: energy", lambda r: f"{r['mission40']['Wh']:.0f} Wh")
    row("40 C: stopped by", lambda r: r["mission40"]["reason"])
    row("End of life, 25 C: run time", lambda r: f"{r['mission25_eol']['t']:.0f} s")
    row("End of life: energy", lambda r: f"{r['mission25_eol']['Wh']:.0f} Wh")
    row("End of life: hot cell", lambda r: f"{r['mission25_eol']['Thot_max']:.1f} C")
    row("k at 40 C, below limit", lambda r: f"{r['derate40']:.2f}")
    row("k at 40 C, 3 K margin", lambda r: f"{r['derate40_3K']:.2f}")
    row("Max constant current 25 C", lambda r: f"{r['imax25']:.0f} A")
    row("Max constant current 40 C", lambda r: f"{r['imax40']:.0f} A")
    row("P1 140 A: time / energy", lambda r: f"{r['peak25']['t']:.0f} s / {r['peak25']['Wh']:.0f} Wh")
    row("Current factor (p95)", lambda r: f"{r['current_factor']:.3f}")
    row("Charge 1C", lambda r: f"{r['charge1c']['hours']:.2f} h")
    row("2C CC rise", lambda r: f"{r['charge2c']['dT_cc']:.1f} K")
    row("Hot cell end of 1C CC at 40 C", lambda r: f"{r['charge1c_hot']['Thot_end']:.1f} C")
    row("Balance 5 %", lambda r: f"{r['bal']['hours']:.2f} h")
    row("Module mass", lambda r: f"{r['bom']['mass_module']} g")
    row("Module cost", lambda r: f"₹{r['bom']['inr_module']:,}")
    row("Envelope", lambda r: f"{r['geom']['L_mm']:.0f}x{r['geom']['W_mm']:.0f}x{r['geom']['H_mm']:.0f} mm")
    row("Volume", lambda r: f"{r['geom']['volume_L']:.2f} L")
    row("Wh/kg, Wh/L (nominal)", lambda r: f"{r['Wh_per_kg']:.0f}, {r['geom']['Wh_per_L']:.0f}")
    row("Ageing index", lambda r: f"{r['ageing_index']:.2f}" + ("" if r["ageing_comparable"] else "*"))
    L.append("\nVerdicts\n")
    ids = [v[0] for v in res[n[0]]["verdicts"]]
    allids = []
    for k in n:
        for v in res[k]["verdicts"]:
            if v[0] not in allids: allids.append(v[0])
    L.append("| Check | " + " | ".join(n) + " |"); L.append("|---" * (len(n) + 1) + "|")
    for i in allids:
        cells = []
        for k in n:
            m = [v for v in res[k]["verdicts"] if v[0] == i]
            cells.append(m[0][2] if m else "n/a")
        L.append(f"| {i} | " + " | ".join(cells) + " |")
    return "\n".join(L) + "\n\n```\n" + json.dumps(extra, indent=1) + "\n```\n"

def main():
    ap = argparse.ArgumentParser(description="BESS-Twin engine")
    ap.add_argument("calib", nargs="?", help="calibration JSON from calibrate.py")
    ap.add_argument("--config", help="design file: {mission, requirements, designs: {name: cfg}}")
    ap.add_argument("--out", default="results.json")
    ap.add_argument("--tables", default="results_tables.md")
    ap.add_argument("--fast", action="store_true", help="skip derate, constant-current and sensitivity sweeps")
    ap.add_argument("--evidence", action="store_true", help="model against the P28A specification and independent tests")
    ap.add_argument("--uq", metavar="DESIGN", help="uncertainty propagation for one design name (300 samples)")
    ap.add_argument("--search", action="store_true", help="search every cell x NP x busbar x cooling x balancing x BMS combination")
    a = ap.parse_args()
    if a.calib: load_calibration(a.calib)
    if a.evidence or a.uq or a.search:
        extra_designs = dict(REFERENCE)
        if a.config: extra_designs.update(json.load(open(a.config))["designs"])
        out = {}
        if a.evidence: out["evidence"] = datasheet_check(); print(json.dumps(out["evidence"], indent=1))
        if a.uq:
            out["uncertainty"] = {a.uq: uncertainty(extra_designs[a.uq])}
            print(json.dumps(out["uncertainty"], indent=1))
        if a.search:
            s_ = design_search(); out["search"] = {k: v for k, v in s_.items() if k != "rows"}
            out["search"]["all"] = s_["rows"]
            print(json.dumps({k: v for k, v in s_.items() if k not in ("rows",)}, indent=1))
        json.dump(out, open(a.out if a.out != "results.json" else "results_extra.json", "w"), indent=1)
        return
    designs, mission, REQ, sens_for = REFERENCE, None, dict(DEFAULT_REQ), "Ablation 2a"
    if a.config:
        spec = json.load(open(a.config))
        designs = spec["designs"]; mission = spec.get("mission"); REQ.update(spec.get("requirements", {}))
        sens_for = spec.get("sensitivity_for")
    res = {name: evaluate(name, cfg, mission, REQ, a.fast) for name, cfg in designs.items()}
    out = {"version": "3.0",
           "parameters": {k: dict(value=P[k], tag=("calibrated" if k in CALIB else PARAMS[k][1])) for k in P},
           "cells": CELLS, "calibrated": sorted(CALIB), "mission": mission or DEFAULT_MISSION,
           "requirements": REQ, "designs": res}
    out["sensor_fault_detect_s"] = sensor_selftest()
    out["verify"] = verify()
    if sens_for and not a.fast:
        out["sensitivity"] = {"design": sens_for, **sensitivity(designs[sens_for], mission)}
    json.dump(out, open(a.out, "w"), indent=1)
    extra = {k: out[k] for k in ("sensor_fault_detect_s", "verify") }
    if "sensitivity" in out: extra["sensitivity"] = out["sensitivity"]
    open(a.tables, "w").write(tables_md(res, extra))

    print("design         t25   Wh25  Thot25 | t40   Wh40 | EOL t Wh  | k40   k3K  | Imax25 Imax40 | g     Rs     L     | f")
    for n, r in res.items():
        x, y, e = r["mission25"], r["mission40"], r["mission25_eol"]
        print(f"{n:<13} {x['t']:5.0f} {x['Wh']:6.1f} {x['Thot_max']:6.1f} | {y['t']:5.0f} {y['Wh']:5.1f} | "
              f"{e['t']:4.0f} {e['Wh']:5.1f} | {r['derate40']:.2f}  {r['derate40_3K']:.2f} | {r['imax25']:5.0f}  {r['imax40']:5.0f}  | "
              f"{r['bom']['mass_module']:4d} {r['bom']['inr_module']:6d} {r['geom']['volume_L']:.2f} | {r['current_factor']:.3f}")
    for n, r in res.items():
        print("\n" + n + ": " + r["label"])
        for rid, rule, lvl, why in r["verdicts"]: print(f"  {rid:<8}{lvl:<9}{rule}: {why}")
    print("\nverify:", json.dumps(out["verify"], indent=1))
    print("sensor fault flagged at", out["sensor_fault_detect_s"], "s (injected at 100 s)")
    if "sensitivity" in out: print("sensitivity:", json.dumps(out["sensitivity"], indent=1))

if __name__ == "__main__":
    main()
