#!/usr/bin/env python3
"""
Re-run every published result and compare it with the committed file.

    python3 reproduce.py            all studies (about 1.5 minutes)
    python3 reproduce.py --quick    skip the 480-design search and the uncertainty study (about 30 s)

Each study is run into a temporary folder. Strings, booleans and integers must match exactly; floats must
agree to a relative 1e-9 (the last digits can differ between machines because the maths library differs).
The Monte Carlo and uncertainty studies use a fixed seed, so they repeat. Exit code 0 = everything reproduced.
Also runs the browser-against-Python parity test when node is installed.
"""
import json, math, os, shutil, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
STUDIES = [  # (what, committed file, engine arguments, slow?)
    ("five reference designs (section 5.2-5.4)", "results.json", [], False),
    ("design-space exploration (5.5)", "results_design_space.json", ["--config", "configs/design_space.json"], False),
    ("recommended candidates (5.6, 5.7)", "results_recommended.json", ["--config", "configs/recommended.json"], False),
    ("model against published P28A data (9.5)", "results_evidence.json", ["--evidence"], False),
    ("480-design search (5.8)", "results_search.json", ["--search"], True),
    ("uncertainty study, R-B, 300 samples (5.9)", "results_uq_RB.json",
     ["--config", "configs/recommended.json", "--uq", "R-B 4S5P low-loss"], True),
]

def same(a, b, path="", tol=1e-9):
    """Return the first difference between two parsed JSON values, or None."""
    if isinstance(a, dict) and isinstance(b, dict):
        if a.keys() != b.keys(): return f"{path}: keys differ"
        for k in a:
            d = same(a[k], b[k], f"{path}/{k}", tol)
            if d: return d
        return None
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b): return f"{path}: length {len(a)} vs {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            d = same(x, y, f"{path}[{i}]", tol)
            if d: return d
        return None
    if isinstance(a, float) or isinstance(b, float):
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            if math.isnan(a) and math.isnan(b): return None
            return None if abs(a - b) <= tol * max(1.0, abs(a), abs(b)) else f"{path}: {a} vs {b}"
        return f"{path}: type differs"
    return None if a == b else f"{path}: {a!r} vs {b!r}"

def main():
    quick = "--quick" in sys.argv
    tmp = tempfile.mkdtemp(prefix="bess-repro-")
    ok_all, t_all = True, time.time()
    try:
        for what, committed, args, slow in STUDIES:
            if quick and slow:
                print(f"SKIP   {what}"); continue
            out = os.path.join(tmp, committed)
            t0 = time.time()
            r = subprocess.run([sys.executable, os.path.join(HERE, "bess_platform.py"), *args, "--out", out,
                                "--tables", os.path.join(tmp, "tables.md")], cwd=HERE, capture_output=True, text=True)
            if r.returncode:
                print(f"ERROR  {what}\n{r.stderr[-400:]}"); ok_all = False; continue
            diff = same(json.load(open(out)), json.load(open(os.path.join(HERE, committed))))
            print(f"{'PASS ' if not diff else 'FAIL '}  {what}  [{time.time()-t0:.1f} s]" + (f"\n         first difference {diff}" if diff else ""))
            ok_all &= diff is None
        node = shutil.which("node")
        if node:
            r = subprocess.run([node, os.path.join(HERE, "web", "test_parity.js")], cwd=HERE, capture_output=True, text=True)
            print(f"{'PASS ' if r.returncode == 0 else 'FAIL '}  browser engine against Python engine\n         " + r.stdout.strip().splitlines()[-1])
            ok_all &= r.returncode == 0
        else:
            print("SKIP   browser parity test (node not installed)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n{'ALL RESULTS REPRODUCED' if ok_all else 'SOMETHING DID NOT REPRODUCE'} in {time.time()-t_all:.0f} s")
    sys.exit(0 if ok_all else 1)

if __name__ == "__main__":
    main()
