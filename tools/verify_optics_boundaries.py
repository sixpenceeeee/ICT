"""Browser benchmark for the 3D optics boundary checker and its memory."""

from contextlib import contextmanager
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import statistics
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "04_review_agent")]
import optics_resources
import shell
from reviewer import run_review
import optics_boundary


@contextmanager
def isolated_memory(database):
    previous = os.environ.get("ICT_TEACHING_MEMORY")
    os.environ["ICT_TEACHING_MEMORY"] = str(database)
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("ICT_TEACHING_MEMORY", None)
        else:
            os.environ["ICT_TEACHING_MEMORY"] = previous


def fixture(directory, name, focus, distance=None, fault=None):
    folder = directory / name
    folder.mkdir()
    model = optics_resources.resolve_model({"f": focus})
    html = shell.render(optics_resources.TITLE, optics_resources.render_sections(model), name)
    if fault:
        hook, change = fault
        if html.count(hook) != 1:
            raise RuntimeError(f"{name} 插入对照故障的位置不唯一")
        html = html.replace(hook, hook + f"\n      if (model.u === {distance:g}) {{ {change} }}", 1)
    page = folder / "lens.html"
    page.write_text(html, encoding="utf-8")
    for asset in ("logo.png", "frame.css", "exp.css"):
        shutil.copy2(ROOT / "frame" / asset, folder / asset)
    return page


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def review(directory, label, page, req, mode, database):
    for attempt in range(3):
        start = perf_counter()
        with isolated_memory(database):
            report = run_review(str(page), str(req), verbose=False, optics_mode=mode)
        seconds = round(perf_counter() - start, 3)
        load = next((row for row in report["检查项"] if row["check_id"] == "G4-01"), {})
        if "Target page, context or browser has been closed" not in load.get("actual", ""):
            break
        dump(directory / f"{label}-browser-retry-{attempt + 1}.json", report)
    dump(directory / f"{label}.json", report)
    trace = report.get("凸透镜边界回归")
    if report["动态验证"] != "已执行" or not trace or not trace["采样"]:
        raise RuntimeError(f"{label} 缺少真实浏览器采样，见详细报告。")
    runtime = next((check for check in report["检查项"] if check["check_id"] == "G4-02"), {})
    if runtime.get("status") != "pass":
        raise RuntimeError(f"{label} 浏览器运行异常，见详细报告。")
    if trace["记忆"].get("storage_error"):
        raise RuntimeError(trace["记忆"]["storage_error"])
    check = next(row for row in report["检查项"] if row["check_id"] == optics_boundary.RULE)
    print(f"{label}: {check['status']} · {len(trace['采样'])} 点 · {seconds:.3f}s", flush=True)
    return {"status": check["status"], "seconds": seconds, "trace": trace}


def run(directory):
    req = directory / "需求.json"
    dump(req, {"需求": optics_resources.template_requirement("探究凸透镜成像规律", "3d")})
    solver = "lastResult = global.OPTICS.solve(model);"
    display = "var bound = global.OPTICS.bindReadouts(lastResult, domRoot);"
    normal = {"clean-f10": fixture(directory, "clean-f10", 10),
              "clean-f20": fixture(directory, "clean-f20", 20)}
    mutants = {
        "focal": fixture(directory, "focal", 10, 10, (solver, "lastResult.v = 1;")),
        "virtual-side": fixture(directory, "virtual-side", 10, 9, (display,
            "domRoot.querySelector('[data-optics-readout=\"kind\"]').textContent = '倒立·放大·实像';")),
        "double-focus-side": fixture(directory, "double-focus-side", 10, 21,
            (solver, "lastResult.uClass = 'u=2f';")),
        "local-recurrence": fixture(directory, "local-recurrence", 10, 12, (display,
            "domRoot.querySelector('[data-optics-readout=\"v\"]').textContent = '0 cm';")),
        "cross-focus-recurrence": fixture(directory, "cross-focus-recurrence", 20, 24,
            (solver, "lastResult.kindText = '正立·放大·虚像';")),
        "held-out-point": fixture(directory, "held-out-point", 10, 13, (solver, "lastResult.v = 1;")),
    }
    train = fixture(directory, "train", 10, 12, (solver, "lastResult.m = 0;"))
    coarse = fixture(directory, "coarse-grid", 10.5)
    learned = directory / "learned.sqlite3"
    first = review(directory, "training-discovery", train, req, "deep", learned)
    assert first["status"] == "fail" and first["trace"]["记忆"]["recorded"] == [12], first
    pending = review(directory, "pending-does-not-transfer", mutants["cross-focus-recurrence"],
                     req, "active", learned)
    assert pending["status"] == "pass" and 24 not in [p["u"] for p in pending["trace"]["采样"]]
    repaired = review(directory, "training-confirmation", normal["clean-f10"], req, "active", learned)
    assert repaired["status"] == "pass" and repaired["trace"]["记忆"]["confirmed"] == [12], repaired
    grid = review(directory, "unreachable-grid", coarse, req, "active", directory / "grid.sqlite3")
    assert grid["status"] == "review" and any(
        point["target"] == 10.5 for point in grid["trace"]["未覆盖"]), grid

    matrix = {}
    for group in ("baseline", "active", "history"):
        matrix[group] = {}
        for name, page in {**normal, **mutants}.items():
            label = f"{group}-{name}"
            # A new database per page prevents another benchmark page from changing its input plan.
            database = directory / f"{label}.sqlite3"
            if group == "history":
                shutil.copy2(learned, database)
            outcome = review(directory, label, page, req, "baseline" if group == "baseline" else "active",
                             database)
            matrix[group][name] = outcome

    target_detection = {
        "baseline": {"focal"},
        "active": {"focal", "virtual-side", "double-focus-side"},
        "history": set(mutants) - {"held-out-point"},
    }
    summary = {}
    for group, outputs in matrix.items():
        detected = {name for name in mutants if outputs[name]["status"] == "fail"}
        wrong = {name for name in normal if outputs[name]["status"] != "pass"}
        summary[group] = dict(detected=sorted(detected), faults=len(mutants), false_positives=sorted(wrong),
                              clean_pages=len(normal), median_seconds=statistics.median(
                                  result["seconds"] for result in outputs.values()))
    dump(directory / "benchmark-summary.json", summary)
    for group, row in summary.items():
        print(f"{group}: 检出 {len(row['detected'])}/{row['faults']}，"
              f"误报 {len(row['false_positives'])}/{row['clean_pages']}，"
              f"单页中位 {row['median_seconds']:.3f}s", flush=True)
        assert set(row["detected"]) == target_detection[group] and not row["false_positives"], row
    for name, point, source in (("local-recurrence", 12, "历史"), ("cross-focus-recurrence", 24, "迁移")):
        assert any(row["u"] == point and row["source"] == source and row["errors"]
                   for row in matrix["history"][name]["trace"]["采样"]), name


if __name__ == "__main__":
    output = ROOT / "runs" / ("optics-boundary-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
    output.mkdir(parents=True)
    print(f"报告目录 {output}", flush=True)
    run(output)
    print("凸透镜边界对照验证通过。")
