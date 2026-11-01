#!/usr/bin/env python3
"""
Generate SYNTHETIC bench-test files in the exact CSV format of BENCH_TEST_GUIDE.md.

These files are NOT measurements. They come from a single-cell model with hidden "true" values
that differ from the platform's assumptions, plus sensor noise. Their only purpose is to prove that
calibrate.py recovers known values from data that looks like a real bench log, before real data exists.

    python3 make_synthetic.py synthetic/        writes T1, T2, T4 (three SOCs, two ambients), T5 files
"""
import csv, math, os, random, sys, json

TRUE = dict(Q_cell=2.72, R25=0.0215, R_p=0.0065, tau_p=24.0, cp_cell=1020.0, R_T_slope=0.012,
            soc_gain=0.45, soc_width=0.08, G_single=0.060, m_cell=0.046,
            cell_sigma=0.06, R_ic_Ni=0.0026)
OCV_TRUE = [(0.0, 3.02), (0.05, 3.27), (0.10, 3.40), (0.20, 3.52), (0.40, 3.65),
            (0.50, 3.71), (0.60, 3.79), (0.80, 3.98), (0.90, 4.08), (1.0, 4.19)]
NOISE = dict(V=0.002, I=0.010, T=0.2)
rnd = random.Random(42)

def ocv(s):
    s = min(max(s, 0.0), 1.0)
    for (s0, v0), (s1, v1) in zip(OCV_TRUE, OCV_TRUE[1:]):
        if s <= s1: return v0 + (v1 - v0) * (s - s0) / (s1 - s0)
    return OCV_TRUE[-1][1]

class Cell:
    def __init__(self, soc=1.0, Tamb=25.0):
        self.soc, self.vp, self.T, self.Tamb = soc, 0.0, Tamb, Tamb
    def R0(self):
        return (TRUE["R25"] * math.exp(-TRUE["R_T_slope"] * (self.T - 25.0))
                * (1 + TRUE["soc_gain"] * math.exp(-self.soc / TRUE["soc_width"])))
    def step(self, I, dt):
        V = ocv(self.soc) - I * self.R0() - self.vp
        q = I * I * self.R0() + self.vp ** 2 / TRUE["R_p"]
        C = TRUE["m_cell"] * TRUE["cp_cell"]
        self.T += dt * (q - TRUE["G_single"] * (self.T - self.Tamb)) / C
        self.vp += dt * (I * TRUE["R_p"] - self.vp) / TRUE["tau_p"]
        self.soc -= I * dt / 3600 / TRUE["Q_cell"]
        return V

def write(path, rows, header):
    with open(path, "w", newline="") as f:
        f.write("# SYNTHETIC DATA from make_synthetic.py - not a measurement\n")
        w = csv.writer(f); w.writerow(header); w.writerows(rows)

def run(cell, segments, rate):
    """segments: list of (current A, duration s). Logs t, V, I, T with noise at `rate` Hz."""
    dt_log, dt_sim = 1.0 / rate, 0.02
    rows, t, nxt = [], 0.0, 0.0
    for I, dur in segments:
        end = t + dur
        while t < end - 1e-9:
            V = cell.step(I, dt_sim); t += dt_sim
            if t >= nxt - 1e-9:
                rows.append((round(t, 3), round(V + rnd.gauss(0, NOISE["V"]), 4),
                             round(I + rnd.gauss(0, NOISE["I"]), 3), round(cell.T + rnd.gauss(0, NOISE["T"]), 2)))
                nxt += dt_log
            if V < 2.5 or cell.soc <= 0: return rows   # cutoff (generic OCV has no knee below 0 %)
    return rows

def main(out):
    os.makedirs(out, exist_ok=True)
    H = ["t_s", "V", "I_A", "T_C"]
    # T1: 0.2C discharge from full to 2.5 V, 1 Hz
    write(f"{out}/T1_capacity.csv", run(Cell(), [(0.56, 6 * 3600)], 1), H)
    # T4: pulses at three SOCs (25 C) and at 50 % SOC in a 35 C ambient (that pair is test T3), 10 Hz
    pulses = [(0.0, 30)] + [(5.0, 30), (0.0, 150)] * 3 + [(2.0, 30), (0.0, 150)]   # 5 A pulse three times
    for soc, Tamb in ((1.0, 25.0), (0.5, 25.0), (0.2, 25.0), (0.1, 25.0), (0.5, 35.0)):
        tag = f"T4_soc{int(soc*100)}" + ("" if Tamb == 25.0 else f"_{int(Tamb)}C")
        write(f"{out}/{tag}.csv", run(Cell(soc, Tamb), pulses, 10), H)
    # T2: 5 A for 600 s in free air, then 600 s rest, 1 Hz
    rows = run(Cell(), [(5.0, 600), (0.0, 600)], 1)
    write(f"{out}/T2_heating.csv", [r + (25.0,) for r in rows], H + ["Tamb_C"])
    # T5: DC resistance of 16 cells, and millivolt drop across 4 nickel-strip branches at 10 A
    cells = [(i + 1, round(TRUE["R25"] * 1000 * (1 + rnd.gauss(0, TRUE["cell_sigma"])), 2)) for i in range(16)]
    write(f"{out}/T5_cells.csv", cells, ["cell_id", "R_mOhm"])
    strips = [(i + 1, "Ni", 10.0, round(10.0 * TRUE["R_ic_Ni"] * 1000 * (1 + rnd.gauss(0, 0.10)), 2)) for i in range(4)]
    write(f"{out}/T5_busbar.csv", strips, ["branch", "busbar", "I_A", "drop_mV"])
    json.dump(dict(TRUE, OCV=OCV_TRUE), open(f"{out}/TRUE_VALUES_hidden.json", "w"), indent=1)
    print("wrote synthetic files to", out)

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "synthetic")
