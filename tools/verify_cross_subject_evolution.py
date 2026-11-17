"""Compare the same non-optics pages with and without saved interaction counterexamples."""

from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import statistics
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "04_review_agent"))
from reviewer import run_review

SOURCES = {
    "math": ("教学资源_二次函数图像.html", "const result = MATH.solveQuadratic(request);"),
    "physics": ("教学资源_浮力与浮沉.html", "const result = PHYS.solveBuoyancy(request);"),
}


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def fixture(output, label, family, condition=None, error=None):
    name, hook = SOURCES[family]
    source_dir = ROOT / "03_generator_agent" / "output"
    html = (source_dir / name).read_text(encoding="utf-8")
    folder = output / label
    folder.mkdir()
    if condition:
        if html.count(hook) != 1:
            raise RuntimeError(f"无法定位 {name} 的故障注入点")
        html = html.replace(hook, hook + f" if ({condition}) {{ {error} }}", 1)
    for file in ("frame.css", "exp.css", "logo.png"):
        shutil.copy2(source_dir / file, folder / file)
    for bundle in source_dir.glob(name.removeprefix("教学资源_").removesuffix(".html") + ".zip"):
        shutil.copy2(bundle, folder / bundle.name)
    result = folder / name
    result.write_text(html, encoding="utf-8")
    return result


def check(output, name, html, database, mode="active"):
    old = os.environ.get("ICT_TEACHING_MEMORY")
    os.environ["ICT_TEACHING_MEMORY"] = str(database)
    try:
        for attempt in range(3):
            start = perf_counter()
            report = run_review(str(html), None, verbose=False, interaction_mode=mode)
            duration = perf_counter() - start
            evolution = report["实验自进化"]
            trace = evolution["浏览器"]
            if trace.get("samples"):
                break
            save(output / f"{name}-retry-{attempt + 1}.json", report)
    finally:
        if old is None:
            os.environ.pop("ICT_TEACHING_MEMORY", None)
        else:
            os.environ["ICT_TEACHING_MEMORY"] = old
    save(output / f"{name}.json", report)
    if not trace.get("samples") or trace.get("error") or evolution["记忆"].get("storage_error"):
        raise RuntimeError(f"{name} 缺少有效浏览器或记忆证据，详见报告")
    failed = [row for row in trace["samples"] if row["errors"]]
    print(f"{name}: {len(failed)} 个异常，{len(trace['samples'])} 个采样，{duration:.2f}s", flush=True)
    return {"failed": failed, "duration": duration, "memory": evolution["记忆"]}


def run(output):
    normal = {f"{f}-clean": fixture(output, f"{f}-clean", f) for f in SOURCES}
    expected_cases = [
        ("math-active", "math", "request.b === -5", "result.vertex_x += 1;"),
        ("math-replay", "math", "request.b === 3", "result.vertex_x += 2;"),
        ("math-unseen", "math", "request.b === 8", "result.vertex_x += 1;"),
        ("physics-active", "physics", "Math.abs(request.fraction - 0.3) < 1e-8", "result.buoyancy += 1;"),
        ("physics-replay", "physics", "Math.abs(request.fraction - 0.6) < 1e-8", "result.buoyancy += 1;"),
        ("physics-unseen", "physics", "Math.abs(request.fraction - 0.7) < 1e-8", "result.buoyancy += 1;"),
    ]
    faults = {name: fixture(output, name, family, trigger, error)
              for name, family, trigger, error in expected_cases}
    learned = output / "learned.sqlite3"
    for family, trigger, error, expected in [
        ("math", "request.b === 3", "result.vertex_y += 1;", {"control": "b", "value": "3"}),
        ("physics", "Math.abs(request.fraction - 0.6) < 1e-8",
         "result.tension += 1;", {"control": "fraction", "value": "0.6"}),
    ]:
        training = fixture(output, f"{family}-training", family, trigger, error)
        discovery = check(output, f"{family}-discovery", training, learned, "deep")
        assert expected in discovery["memory"]["recorded"], discovery
        repaired = check(output, f"{family}-confirmation", normal[f"{family}-clean"], learned)
        assert expected in repaired["memory"]["confirmed"] and not repaired["failed"], repaired

    summary = {}
    for group in ("empty", "history"):
        detected, false_positives, elapsed = [], [], []
        for name, html in {**normal, **faults}.items():
            database = output / f"{group}-{name}.sqlite3"
            if group == "history":
                shutil.copy2(learned, database)
            result = check(output, f"{group}-{name}", html, database)
            elapsed.append(result["duration"])
            if result["failed"]:
                (detected if name in faults else false_positives).append(name)
            if group == "history" and name.endswith("-replay"):
                assert any(row["source"] == "历史" for row in result["failed"]), result
        summary[group] = dict(detected=detected, total_faults=len(faults),
                              false_positives=false_positives, normal_pages=len(normal),
                              median_seconds=round(statistics.median(elapsed), 3))
    save(output / "benchmark-summary.json", summary)
    assert summary["empty"]["detected"] == ["math-active", "physics-active"], summary
    assert summary["history"]["detected"] == ["math-active", "math-replay", "physics-active", "physics-replay"], summary
    assert not any(item["false_positives"] for item in summary.values()), summary
    for group, item in summary.items():
        print(f"{group}: 检出 {len(item['detected'])}/{item['total_faults']}，误报 "
              f"{len(item['false_positives'])}/{item['normal_pages']}，"
              f"耗时中位数 {item['median_seconds']:.2f}s", flush=True)


if __name__ == "__main__":
    directory = ROOT / "runs" / ("cross-subject-evolution-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
    directory.mkdir(parents=True)
    print(f"报告目录 {directory}", flush=True)
    run(directory)
    print("跨学科自进化浏览器对照通过。")
