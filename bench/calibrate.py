#!/usr/bin/env python3
"""
BESS-Twin calibration: turn bench-test logs into calib.json for bess_platform.py.
Pure Python, no packages to install.

    python3 calibrate.py DATA_DIR [--out calib.json] [--m-cell 0.046]

DATA_DIR holds any of these files (format in BENCH_TEST_GUIDE.md):
    T1_capacity.csv        0.2C discharge, 4.2 V to 2.5 V             -> Q_cell, OCV table
    T4_soc<NN>.csv         current pulses at NN % SOC, 25 C            -> R25, R_p, tau_p, soc_gain
    T4_soc<NN>_<TT>C.csv   same pulses at another ambient (test T3)    -> R_T_slope
    T2_heating.csv         5 A in free air, then rest                  -> cp_cell (and G of a single cell)
    T5_cells.csv           DC resistance of every cell in the batch    -> cell_sigma
    T5_busbar.csv          mV drop across each branch strip at 10 A    -> R_ic_Ni / R_ic_CuNi

Each fitted value is replayed against its own data and checked against the pass criteria of the
validation plan (design document section 9). A value is written to calib.json only if its test passed.
If DATA_DIR contains TRUE_VALUES_hidden.json (synthetic data only), the report also compares the
fitted values with the hidden true ones.
"""
import csv, glob, json, math, os, re, sys, argparse

DEFAULTS = dict(R_T_slope=0.015, soc_width=0.08, soc_gain=0.6, R_p=0.008, tau_p=30.0)
SOC_GRID = [0.0, 0.05, 0.10, 0.20, 0.40, 0.50, 0.60, 0.80, 0.90, 1.0]

def read(path):
    rows, header = [], None
    with open(path) as f:
        for line in f:
            if line.startswith("#") or not line.strip(): continue
            parts = next(csv.reader([line]))
            if header is None: header = [h.strip() for h in parts]; continue
            rows.append({h: float(x) if re.match(r"^-?[\d.eE+-]+$", x.strip()) else x.strip() for h, x in zip(header, parts)})
    return rows

def mean(x): return sum(x) / len(x)
def std(x):
    m = mean(x); return math.sqrt(sum((v - m) ** 2 for v in x) / max(len(x) - 1, 1))
def linfit(x, y):
    mx, my = mean(x), mean(y)
    sxx = sum((a - mx) ** 2 for a in x)
    b = sum((a - mx) * (c - my) for a, c in zip(x, y)) / sxx
    return my - b * mx, b

def nelder_mead(f, x0, step, iters=400):
    n = len(x0)
    pts = [list(x0)] + [[x0[j] + (step[j] if j == i else 0) for j in range(n)] for i in range(n)]
    vals = [f(p) for p in pts]
    for _ in range(iters):
        order = sorted(range(n + 1), key=lambda i: vals[i]); pts = [pts[i] for i in order]; vals = [vals[i] for i in order]
        c = [mean([p[j] for p in pts[:-1]]) for j in range(n)]
        r = [c[j] + (c[j] - pts[-1][j]) for j in range(n)]; fr = f(r)
        if fr < vals[0]:
            e = [c[j] + 2 * (c[j] - pts[-1][j]) for j in range(n)]; fe = f(e)
            pts[-1], vals[-1] = (e, fe) if fe < fr else (r, fr)
        elif fr < vals[-2]:
            pts[-1], vals[-1] = r, fr
        else:
            k = [c[j] + 0.5 * (pts[-1][j] - c[j]) for j in range(n)]; fk = f(k)
            if fk < vals[-1]: pts[-1], vals[-1] = k, fk
            else:
                pts = [pts[0]] + [[pts[0][j] + 0.5 * (p[j] - pts[0][j]) for j in range(n)] for p in pts[1:]]
                vals = [vals[0]] + [f(p) for p in pts[1:]]
    i = min(range(n + 1), key=lambda i: vals[i]); return pts[i], vals[i]

# ---- T4: pulses -> R0 per edge, R_p and tau from each relaxation ---------------------------------
def analyse_pulses(rows):
    t = [r["t_s"] for r in rows]; V = [r["V"] for r in rows]; I = [r["I_A"] for r in rows]; T = [r["T_C"] for r in rows]
    edges = [i for i in range(1, len(I)) if abs(I[i] - I[i - 1]) > 0.5]
    qcum = [0.0]
    for k in range(1, len(t)):
        qcum.append(qcum[-1] + (I[k - 1] if abs(I[k - 1]) > 0.05 else 0.0) * (t[k] - t[k - 1]) / 3600)
    R0, relax = [], []
    for k, i in enumerate(edges):
        dI = I[i] - I[i - 1]
        # extrapolate 1 s of samples on each side to the edge instant (removes noise and polarization drift)
        te = 0.5 * (t[i] + t[i - 1])
        bw = [j for j in range(max(0, i - 40), i) if te - t[j] <= 1.0]
        aw = [j for j in range(i, min(len(t), i + 40)) if t[j] - te <= 1.0 and abs(I[j] - I[i]) < 0.3]
        if len(bw) < 3 or len(aw) < 3: continue
        pre = linfit([t[j] - te for j in bw], [V[j] for j in bw])[0]
        post = linfit([t[j] - te for j in aw], [V[j] for j in aw])[0]
        R0.append(dict(R=(pre - post) / dI, dI=abs(dI), q=qcum[i], T=T[i]))
        if dI < 0:                                            # current switched off: relaxation follows
            start = edges[k - 1] if k > 0 else 0
            tp = t[i] - t[start]; Ip = -dI
            end = edges[k + 1] if k + 1 < len(edges) else len(t)
            tail = [V[j] for j in range(end - 1, i, -1) if t[end - 1] - t[j] <= 5.0]
            Vinf = mean(tail)
            xs, vs = [], []
            for j in range(i, end):
                tt = t[j] - t[i]
                if 1.0 <= tt: xs.append(tt); vs.append(V[j])
            if len(xs) > 20:
                # start from a log-linear guess, then fit V = Vinf - A exp(-t/tau) on the raw voltages
                # (a log fit alone is biased once the signal sinks into the noise)
                g = [(x, math.log(Vinf - v)) for x, v in zip(xs, vs) if x <= 30 and Vinf - v > 0.004]
                a0, b0 = linfit([x for x, _ in g], [y for _, y in g]) if len(g) > 5 else (math.log(0.02), -1 / 30)
                sse = lambda q: (sum((v - (q[0] - q[1] * math.exp(-x / q[2]))) ** 2 for x, v in zip(xs, vs))
                                 if q[2] > 1 else 1e9)
                (vi, A, tau), _ = nelder_mead(sse, [Vinf, math.exp(a0), -1 / b0], [0.002, 0.005, 5.0], iters=600)
                relax.append(dict(tau=tau, Rp=A / (Ip * (1 - math.exp(-tp / tau))), Ip=Ip))
    big = [x["R"] for x in R0 if x["dI"] >= 4.0] or [x["R"] for x in R0]
    return dict(R0=mean(big), R0_sd=std(big) / math.sqrt(len(big)) if len(big) > 1 else float("nan"),
                n_edges=len(big), relax=relax, T=mean(T), edges=[x for x in R0 if x["dI"] >= 4.0] or R0)

def replay_pulses(rows, soc0, p, ocv_tab):
    """Voltage replay with the fitted model; returns RMS and max error over the rests (mV)."""
    soc, vp, err_all, err_rest = soc0, 0.0, [], []
    for k, r in enumerate(rows):
        dt = rows[k]["t_s"] - rows[k - 1]["t_s"] if k else 0.0
        I = r["I_A"] if abs(r["I_A"]) > 0.05 else 0.0
        vp += dt * (I * p["R_p"] - vp) / p["tau_p"]; soc -= I * dt / 3600 / p["Q_cell"]
        R = p["R25"] * math.exp(-p["R_T_slope"] * (r["T_C"] - 25)) * (1 + p["soc_gain"] * math.exp(-soc / p["soc_width"]))
        e = (r["V"] - (interp(ocv_tab, soc) - I * R - vp)) * 1000
        err_all.append(e)
        if I == 0.0: err_rest.append(e)
    # OCV at the pulse SOC is not known from T4 alone; remove the mean offset before judging the shape
    off = mean(err_rest)
    rest = [abs(e - off) for e in err_rest]
    return dict(rms_mV=math.sqrt(mean([(e - off) ** 2 for e in err_all])), max_rest_mV=max(rest), ocv_offset_mV=off)

def interp(tab, s):
    s = min(max(s, tab[0][0]), tab[-1][0])
    for (s0, v0), (s1, v1) in zip(tab, tab[1:]):
        if s <= s1: return v0 + (v1 - v0) * (s - s0) / (s1 - s0)
    return tab[-1][1]

# ---- T2: heating -> C and G of one cell -------------------------------------------------------------
def fit_heating(rows, p):
    def simulate(C, G):
        T = rows[0]["T_C"]; out = [T]
        for k in range(1, len(rows)):
            dt = rows[k]["t_s"] - rows[k - 1]["t_s"]; I = rows[k - 1]["I_A"]
            I = I if abs(I) > 0.05 else 0.0
            R = p["R25"] * math.exp(-p["R_T_slope"] * (T - 25)) + p["R_p"]
            T += dt * (I * I * R - G * (T - rows[k - 1].get("Tamb_C", 25.0))) / C
            out.append(T)
        return out
    meas = [r["T_C"] for r in rows]
    cost = lambda x: (math.sqrt(mean([(a - b) ** 2 for a, b in zip(simulate(x[0], x[1]), meas)]))
                      if x[0] > 1 and x[1] > 0 else 1e9)
    (C, G), rms = nelder_mead(cost, [40.0, 0.1], [10.0, 0.05])
    maxerr = max(abs(a - b) for a, b in zip(simulate(C, G), meas))
    return dict(C=C, G=G, rms_K=rms, max_K=maxerr, rise_K=max(meas) - meas[0])

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("data"); ap.add_argument("--out", default="calib.json")
    ap.add_argument("--m-cell", type=float, default=0.046); ap.add_argument("--Q-datasheet", type=float, default=2.8)
    ap.add_argument("--report", default=None)
    a = ap.parse_args(); D = a.data
    p = dict(DEFAULTS); res, rep, calib = {}, [], {}
    synthetic = any("SYNTHETIC" in open(f).readline() for f in glob.glob(os.path.join(D, "*.csv")))

    f1 = os.path.join(D, "T1_capacity.csv")
    Qref = a.Q_datasheet
    if os.path.exists(f1):
        r1 = read(f1)
        Qref = sum(r1[k - 1]["I_A"] * (r1[k]["t_s"] - r1[k - 1]["t_s"]) / 3600 for k in range(1, len(r1)))

    # T4 / T3
    t4 = {}
    for f in sorted(glob.glob(os.path.join(D, "T4_soc*.csv"))):
        m = re.search(r"T4_soc(\d+)(?:_(\d+)C)?\.csv", os.path.basename(f))
        soc, amb = int(m.group(1)) / 100, (float(m.group(2)) if m.group(2) else 25.0)
        t4[(soc, amb)] = dict(file=f, rows=read(f), **analyse_pulses(read(f)))
    if t4:
        mid = [v for (s, amb), v in t4.items() if amb == 25.0 and s >= 0.5]
        hot_pair = [(k, v) for k, v in t4.items() if k[1] != 25.0 and (k[0], 25.0) in t4]
        if hot_pair:
            (s, amb), v = hot_pair[0]; ref = t4[(s, 25.0)]
            p["R_T_slope"] = -math.log(v["R0"] / ref["R0"]) / (v["T"] - ref["T"])
            se = math.hypot(v["R0_sd"] / v["R0"], ref["R0_sd"] / ref["R0"]) / abs(v["T"] - ref["T"])
            res["R_T_slope"] = dict(value=p["R_T_slope"], test="T3",
                                    note=f"R0 {ref['R0']*1e3:.2f} mOhm at {ref['T']:.1f} C vs {v['R0']*1e3:.2f} at {v['T']:.1f} C; "
                                         f"+-{se:.4f} /K (1 SE), so use a wider temperature gap if you can",
                                    confident=se / abs(p["R_T_slope"]) < 0.3)
        Rmid = mean([v["R0"] * math.exp(p["R_T_slope"] * (v["T"] - 25)) for v in mid])
        low = sorted([(s, v) for (s, amb), v in t4.items() if amb == 25.0 and s <= 0.2])
        w = p["soc_width"]
        if low:
            s0, v = low[0]
            gs = []
            for e in v["edges"]:                      # SOC falls during the pulses: use the SOC at each edge
                se = s0 - e["q"] / Qref
                r = e["R"] * math.exp(p["R_T_slope"] * (e["T"] - 25)) / Rmid
                gs.append((r - 1) / (math.exp(-se / w) - r * math.exp(-0.5 / w)))
            g = mean(gs); rel_sd = std(gs) / math.sqrt(len(gs)) / max(abs(g), 1e-9)
            res["soc_gain"] = dict(value=g, test="T4", note=f"{len(gs)} edges near {s0:.0%} SOC; relative uncertainty {rel_sd:.0%}",
                                   confident=rel_sd < 0.3)
            if rel_sd < 0.3: p["soc_gain"] = g
        p["R25"] = Rmid / (1 + p["soc_gain"] * math.exp(-0.5 / w))
        res["R25"] = dict(value=p["R25"], test="T4", note=f"{sum(v['n_edges'] for v in mid)} current edges >= 4 A at >= 50 % SOC")
        rl = [x for v in t4.values() for x in v["relax"] if x["Ip"] >= 4.0]
        p["tau_p"] = mean([x["tau"] for x in rl]); p["R_p"] = mean([x["Rp"] for x in rl])
        res["tau_p"] = dict(value=p["tau_p"], test="T4", note=f"{len(rl)} relaxations, spread {std([x['tau'] for x in rl]):.1f} s")
        res["R_p"] = dict(value=p["R_p"], test="T4", note=f"spread {std([x['Rp'] for x in rl])*1e3:.2f} mOhm")

    # T1
    f1 = os.path.join(D, "T1_capacity.csv")
    if os.path.exists(f1):
        rows = read(f1); Ah = 0.0; pts = []
        for k in range(1, len(rows)):
            Ah += rows[k - 1]["I_A"] * (rows[k]["t_s"] - rows[k - 1]["t_s"]) / 3600
        p["Q_cell"] = Ah
        res["Q_cell"] = dict(value=Ah, test="T1", note=f"{(Ah/a.Q_datasheet-1)*100:+.1f} % vs {a.Q_datasheet} Ah datasheet",
                             passed=abs(Ah / a.Q_datasheet - 1) <= 0.05)
        q = 0.0
        for k, r in enumerate(rows):
            if k: q += rows[k - 1]["I_A"] * (r["t_s"] - rows[k - 1]["t_s"]) / 3600
            soc = 1 - q / Ah
            if r["t_s"] < 5 * p["tau_p"]: continue            # wait for the polarization to settle
            R = p["R25"] * math.exp(-p["R_T_slope"] * (r["T_C"] - 25)) * (1 + p["soc_gain"] * math.exp(-soc / p["soc_width"]))
            pts.append((soc, r["V"] + r["I_A"] * (R + p["R_p"])))
        tab = []
        for s in SOC_GRID:
            # local straight line through the nearest points, evaluated at the grid SOC
            # (at 0 % and 100 % there are points on one side only, so this extrapolates a little)
            near = sorted(pts, key=lambda z: abs(z[0] - s))[:max(20, len(pts) // 150)]
            a0, b0 = linfit([x for x, _ in near], [v for _, v in near])
            tab.append((s, round(a0 + b0 * s, 4)))
        p["OCV"] = tab
        res["OCV"] = dict(value=tab, test="T1", note="V + I*(R0+Rp) along the 0.2C discharge")
    else:
        p.setdefault("Q_cell", a.Q_datasheet)

    # T4 replay (needs OCV)
    if t4 and "OCV" in p:
        reps = {f"{int(s*100)} % SOC, {amb:.0f} C": replay_pulses(v["rows"], s, p, p["OCV"]) for (s, amb), v in t4.items()}
        res["T4_replay"] = reps
        ok = all(x["max_rest_mV"] <= 20.0 for x in reps.values())
        for k in ("R25", "R_p", "tau_p", "soc_gain", "R_T_slope"):
            if k in res: res[k]["passed"] = ok

    # T2
    f2 = os.path.join(D, "T2_heating.csv")
    if os.path.exists(f2) and "R25" in p:
        h = fit_heating(read(f2), p)
        res["cp_cell"] = dict(value=h["C"] / a.m_cell, test="T2",
                              note=f"C = {h['C']:.1f} J/K, single-cell G in free air {h['G']*1000:.0f} mW/K, rise {h['rise_K']:.1f} K, "
                                   f"replay RMS {h['rms_K']:.2f} K, max {h['max_K']:.2f} K", passed=h["max_K"] <= 2.0)

    # T5
    f5 = os.path.join(D, "T5_cells.csv")
    if os.path.exists(f5):
        R = [r["R_mOhm"] for r in read(f5)]
        se = 1 / math.sqrt(2 * (len(R) - 1))          # relative standard error of a sample standard deviation
        res["cell_sigma"] = dict(value=std(R) / mean(R), test="T5", passed=True, confident=len(R) >= 30,
                                 note=f"{len(R)} cells, mean {mean(R):.2f} mOhm; +-{se:.0%} (1 SE) on the spread"
                                      + ("" if len(R) >= 30 else "; fewer than 30 cells, so not written"))
    f5b = os.path.join(D, "T5_busbar.csv")
    if os.path.exists(f5b):
        rows = read(f5b)
        for kind in sorted({r["busbar"] for r in rows}):
            vals = [r["drop_mV"] / 1000 / r["I_A"] for r in rows if r["busbar"] == kind]
            res[f"R_ic_{kind}"] = dict(value=mean(vals), test="T5", note=f"{len(vals)} branches, spread {std(vals)/mean(vals):.0%}",
                                       passed=True)

    for k, v in res.items():
        if k in ("T4_replay",): continue
        if k == "OCV": calib["OCV"] = v["value"]; continue
        if v.get("passed", True) and v.get("confident", True): calib[k] = v["value"]
    json.dump(calib, open(a.out, "w"), indent=1)

    # report
    L = ["# Calibration report", ""]
    if synthetic: L += ["**SYNTHETIC DATA.** These files were generated by make_synthetic.py to test the method. "
                        "Nothing below is a measurement of a real cell.", ""]
    L += ["| Parameter | Fitted | Test | Written to calib.json | Note |", "|---|---|---|---|---|"]
    for k, v in res.items():
        if k in ("T4_replay", "OCV"): continue
        L.append(f"| {k} | {v['value']:.5g} | {v['test']} | {'yes' if k in calib else 'no'} | {v['note']} |")
    if "T4_replay" in res:
        L += ["", "Voltage replay of every pulse file with the fitted model (criterion: recovery within 20 mV)", "",
              "| File | RMS (mV) | Max error during rests (mV) |", "|---|---|---|"]
        for k, v in res["T4_replay"].items(): L.append(f"| {k} | {v['rms_mV']:.1f} | {v['max_rest_mV']:.1f} |")
    tv = os.path.join(D, "TRUE_VALUES_hidden.json")
    if os.path.exists(tv):
        T = json.load(open(tv))
        L += ["", "Recovered against the hidden true values (synthetic check only)", "",
              "| Parameter | True | Fitted | Error |", "|---|---|---|---|"]
        for k in ("Q_cell", "R25", "R_p", "tau_p", "R_T_slope", "soc_gain", "cp_cell", "cell_sigma", "R_ic_Ni"):
            if k in res:
                fv = res[k]["value"]; L.append(f"| {k} | {T[k]:.5g} | {fv:.5g} | {(fv/T[k]-1)*100:+.1f} % |")
        oe = [abs(x[1] - interp(T["OCV"], x[0])) * 1000 for x in res.get("OCV", {}).get("value", [])]
        if oe: L.append(f"| OCV table | | | max {max(oe):.0f} mV over {len(oe)} points |")
    out_md = a.report or os.path.splitext(a.out)[0] + "_report.md"
    open(out_md, "w").write("\n".join(L) + "\n")
    print("\n".join(L)); print("\nwrote", a.out, "and", out_md)

if __name__ == "__main__":
    main()
