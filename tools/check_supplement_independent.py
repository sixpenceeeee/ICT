"""跨语言独立复算：比较页面使用的 JS 求解器与 Python 参考公式。"""
from __future__ import annotations

import json
import math
import os
import shutil
import subprocess


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(ROOT, "frame", "supplement_solver.js")


CASES = [
    ("biology-enzyme", "BIOSOLVER.solveEnzyme", {"substrate": 50, "temperature": 37, "ph": 7}),
    ("biology-respiration", "BIOSOLVER.solveRespiration", {"tidal_volume_l": 0.5, "respiratory_rate": 16}),
    ("biology-ecosystem-foodweb", "BIOSOLVER.solveFoodWeb", {"producer_energy": 1000, "transfer_efficiency": 0.1, "levels": 4}),
    ("geography-scale-distance", "GEOSOLVER.solveScaleDistance", {"map_distance_cm": 3, "scale_denominator": 100000}),
    ("geography-climate-reading", "GEOSOLVER.solveClimate", {"temp_shift": 0, "rain_scale": 1, "monthly_temps": [4, 6, 10, 15, 20, 24, 27, 26, 21, 15, 9, 5], "monthly_rain": [30] * 12}),
    ("geography-population-resources", "GEOSOLVER.solvePopulationDensity", {"population": 200000, "area_km2": 500}),
    ("informatics-binary-representation", "CSSOLVER.solveBinary", {"bits": "1011"}),
    ("informatics-data-visualization", "CSSOLVER.solveStatistics", {"values": [2, 4, 6]}),
    ("informatics-sensor-control", "CSSOLVER.solveSensor", {"period_s": 0.5, "threshold": 50, "value": 60}),
]


def expected(scene, req):
    if scene == "biology-enzyme":
        substrate = req["substrate"] / (40 + req["substrate"])
        temp = max(0.0, 1 - ((req["temperature"] - 37) / 30) ** 2)
        ph = max(0.0, 1 - ((req["ph"] - 7) / 5) ** 2)
        return {"rate": substrate * temp * ph}
    if scene == "biology-respiration":
        return {"minute_ventilation_l_min": req["tidal_volume_l"] * req["respiratory_rate"]}
    if scene == "biology-ecosystem-foodweb":
        return {"energies": [req["producer_energy"] * req["transfer_efficiency"] ** i for i in range(req["levels"])]}
    if scene == "geography-scale-distance":
        return {"actual_distance_km": req["map_distance_cm"] * req["scale_denominator"] / 100000}
    if scene == "geography-climate-reading":
        temps = req["monthly_temps"]
        return {"annual_temperature_range": max(temps) - min(temps), "annual_precipitation": sum(req["monthly_rain"])}
    if scene == "geography-population-resources":
        return {"density_per_km2": req["population"] / req["area_km2"]}
    if scene == "informatics-binary-representation":
        return {"decimal": int(req["bits"], 2), "bit_count": len(req["bits"])}
    if scene == "informatics-data-visualization":
        values = sorted(req["values"])
        return {"mean": sum(values) / len(values), "median": values[len(values) // 2]}
    if scene == "informatics-sensor-control":
        return {"frequency_hz": 1 / req["period_s"], "state": "触发" if req["value"] >= req["threshold"] else "未触发"}
    raise KeyError(scene)


def main():
    node = shutil.which("node")
    if not node:
        raise SystemExit("node not found")
    payload = json.dumps(CASES, ensure_ascii=False)
    js = f"""
const fs=require('fs'), vm=require('vm'); globalThis.window=globalThis; vm.runInThisContext(fs.readFileSync({json.dumps(JS_PATH)},'utf8'));
const cases={payload}; const out=[];
for (const [scene, api, req] of cases) {{
  const p=api.split('.'); const fn=globalThis[p[0]][p[1]]; out.push({{scene, result:fn(req)}});
}}
process.stdout.write(JSON.stringify(out));
"""
    script = os.path.join(ROOT, "runs", "supplement_batch", "_independent_check.js")
    with open(script, "w", encoding="utf-8") as f:
        f.write(js)
    raw = subprocess.check_output([node, script], text=True, encoding="utf-8")
    actual = {row["scene"]: row["result"] for row in json.loads(raw)}
    rows = []
    all_ok = True
    for scene, _api, req in CASES:
        exp = expected(scene, req)
        got = actual[scene]
        checks = {}
        for key, value in exp.items():
            actual_value = got.get(key)
            if isinstance(value, list):
                ok = len(value) == len(actual_value or []) and all(math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9) for a, b in zip(value, actual_value))
            elif isinstance(value, (int, float)):
                ok = math.isclose(float(value), float(actual_value), rel_tol=1e-9, abs_tol=1e-9)
            else:
                ok = value == actual_value
            checks[key] = ok
        row_ok = bool(got.get("checks", {}).get("ok")) and all(checks.values())
        rows.append({"scene": scene, "ok": row_ok, "checks": checks})
        all_ok = all_ok and row_ok
    print(json.dumps({"ok": all_ok, "cases": rows}, ensure_ascii=False, indent=2))
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
