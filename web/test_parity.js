// Parity test: the dashboard engine (engine.js) against bess_platform.py, design by design.
//   node web/test_parity.js        (run from the repository folder; needs python3 on the path)
const { execFileSync } = require("child_process");
const path = require("path");
const B = require("./engine.js");

const root = path.resolve(__dirname, "..");
const designs = Object.assign({}, B.REFERENCE, {
  "P42A 4S4P liquid": {cell:"Molicel P42A", NS:4, NP:4, busbar:"CuNi", cooling:"liquid", bal:"active"},
  "30Q 4S5P liquid":  {cell:"Samsung 30Q",  NS:4, NP:5, busbar:"CuNi", cooling:"liquid", bal:"active"},
  "P28A 6S3P air":    {cell:"Molicel P28A", NS:6, NP:3, busbar:"Ni",   cooling:"air",    bal:"passive"},
});
const py = `
import json, sys
sys.path.insert(0, ${JSON.stringify(root)})
import bess_platform as bp
designs = json.loads(sys.stdin.read())
print(json.dumps({n: bp.evaluate(n, c) for n, c in designs.items()}, default=lambda o: None))`;
const pyRes = JSON.parse(execFileSync("python3", ["-c", py], {input: JSON.stringify(designs), maxBuffer: 1 << 28}).toString());

const fields = [
  ["mission25.t"], ["mission25.Wh"], ["mission25.Thot_max"], ["mission40.t"], ["mission40.Wh"], ["mission40.Thot_max"],
  ["mission25_eol.t"], ["mission25_eol.Wh"], ["peak25.t"], ["derate40"], ["derate40_3K"], ["imax25"], ["imax40"],
  ["bom.mass_module"], ["bom.inr_module"], ["geom.volume_L"], ["current_factor"], ["charge1c.hours"], ["charge1c_hot.Thot_end"],
];
const get = (o, p) => p.split(".").reduce((a, k) => a[k], o);
let worst = 0, n = 0, verdictMismatch = 0;
for (const [name, cfg] of Object.entries(designs)) {
  const js = B.evaluate(cfg), p = pyRes[name];
  for (const [f] of fields) {
    const a = get(js, f), b = get(p, f);
    const tol = f === "geom.volume_L" ? 1e-3 : 1e-6;   // the Python file rounds volume to 1 mL
    const err = Math.abs(a - b) / Math.max(1, Math.abs(b));
    n++; worst = Math.max(worst, err);
    if (err > tol) console.log(`MISMATCH ${name} ${f}: js ${a} py ${b}`);
  }
  const jl = js.verdicts.map(v => v[0] + "=" + v[2]).join(" "), pl = p.verdicts.map(v => v[0] + "=" + v[2]).join(" ");
  if (jl !== pl) { verdictMismatch++; console.log(`VERDICT MISMATCH ${name}\n js ${jl}\n py ${pl}`); }
}
// uncertainty propagation and design search must give the same answers too
const RB = B.REFERENCE["R-B 4S5P low-loss"];
const pyX = JSON.parse(execFileSync("python3", ["-c", `
import json, sys
sys.path.insert(0, ${JSON.stringify(root)})
import bess_platform as bp
cfg = json.loads(sys.stdin.read())
u = bp.uncertainty(cfg, n=60)
s = bp.design_search()
print(json.dumps(dict(u={k: v for k, v in u.items() if k.startswith("p_") or k.startswith("T")}, s=dict(n=s["n"], n_pass=s["n_pass"], n_clean=s["n_clean"], front=[[x["inr"], x["mass"], x["margin40"]] for x in s["front"]]))))`],
  {input: JSON.stringify(RB), maxBuffer: 1 << 28}).toString());
const ju = B.uncertainty(RB, 60), js_s = B.designSearch();
for (const k of ["p_R3", "p_R4", "p_R4_margin", "p_R5", "p_R11", "p_all"]) {
  n++; const err = Math.abs(ju[k] - pyX.u[k]); worst = Math.max(worst, err); if (err > 1e-9) console.log(`MISMATCH uncertainty ${k}: js ${ju[k]} py ${pyX.u[k]}`); }
for (const k of ["T40_p5_p50_p95", "T25_p5_p50_p95"]) ju[k].forEach((v, i) => { n++; const err = Math.abs(v - pyX.u[k][i]) / Math.abs(v); worst = Math.max(worst, err); if (err > 1e-6) console.log(`MISMATCH ${k}[${i}]`); });
const sameSearch = js_s.n === pyX.s.n && js_s.n_pass === pyX.s.n_pass && js_s.n_clean === pyX.s.n_clean &&
  JSON.stringify(js_s.front.map(x => [x.inr, x.mass, +x.margin40.toFixed(6)])) === JSON.stringify(pyX.s.front.map(x => [x[0], x[1], +x[2].toFixed(6)]));
if (!sameSearch) { verdictMismatch++; console.log("SEARCH MISMATCH", js_s.n, js_s.n_pass, js_s.n_clean, pyX.s); }
console.log(`uncertainty (60 samples) and design search (${js_s.n} designs, ${js_s.n_pass} pass, ${js_s.n_clean} clean) ${sameSearch ? "identical" : "DIFFER"}`);
console.log(`${Object.keys(designs).length} designs, ${n} numeric comparisons, largest relative difference ${worst.toExponential(2)}, verdict mismatches ${verdictMismatch}`);
process.exit(worst > 1e-3 || verdictMismatch ? 1 : 0);
