"""Validate optics boundary samples with the independent Python solver."""

import math

from optics_solver import solve_optics
from physics.thin_lens_solver import solve_thin_lens

RULE = "J3-OPTICS-EDGE"


def same(expected, actual, tolerance=1e-9):
    if type(expected) in (float, int):
        return type(actual) in (float, int) and math.isclose(
            expected, actual, rel_tol=1e-10, abs_tol=tolerance)
    return expected == actual


def readout_matches(expected, text, suffix, tolerance):
    if expected is None:
        return text == "—"
    if not text.endswith(suffix):
        return False
    try:
        value = float(text.removesuffix(suffix).strip().replace("−", "-"))
    except ValueError:
        return False
    return math.isfinite(value) and abs(expected - value) <= tolerance


def solver_errors(model, sample, legacy):
    result = sample.get("result")
    if not isinstance(result, dict):
        return ["缺少求解结果对象"]
    fields = sample["fields"]
    expected = (solve_thin_lens if legacy else solve_optics)(model)
    keys = ("u", "f", "image_distance_cm", "magnification", "state") if legacy else (
        "u", "f", "v", "m", "kind", "kindText", "uClass")
    errors = [f"求解结果 {key} 与独立复算不符" for key in keys
              if key not in result or not same(expected[key], result[key])]
    numeric = (("image_distance_cm", ""), ("magnification", "")) if legacy else (("v", " cm"), ("m", "×"))
    for key, suffix in numeric:
        values = fields.get(key) or []
        tolerance = abs(expected[key] or 0) * 1e-6 if legacy else 0.005000001
        if not values or not all(readout_matches(expected[key], value, suffix, tolerance) for value in values):
            errors.append(f"页面读数 {key} 与独立复算不符")
    kind = fields.get("state" if legacy else "kind") or []
    if not kind or any(value != expected["state" if legacy else "kindText"] for value in kind):
        errors.append("页面成像性质与独立复算不符")
    if not legacy:
        u_class = fields.get("uClass") or []
        if not u_class or any(f'（{expected["uClass"]}）' not in value for value in u_class):
            errors.append("页面物距区间与独立复算不符")
        sharp = fields.get("sharp") or []
        sharp_expected = "清晰" if expected["onScreen"]["sharp"] else "不清晰"
        screen = result.get("onScreen")
        if (not sharp or any(value != sharp_expected for value in sharp)
                or not isinstance(screen, dict) or screen.get("sharp") is not expected["onScreen"]["sharp"]):
            errors.append("光屏清晰度与独立复算不符")
    return errors


def assess(trace):
    model = trace.get("model")
    rows, failed, verified = [], set(), set()
    legacy = trace.get("legacy")
    for sample in trace.get("samples", []):
        point = sample["target"]
        current = sample.get("model") or {}
        reached = (sample.get("valid") and same(point, sample.get("actual"))
                   and same(point, current.get("u"))
                   and same(model["f"], current.get("f"))
                   and (legacy or (same(model.get("h"), current.get("h"))
                                   and model.get("screen") == current.get("screen"))))
        errors = []
        if not reached:
            errors.append("滑块未把目标物距传入求解器，或其他参数意外改变")
        else:
            try:
                errors.extend(solver_errors(dict(model, u=point), sample, legacy))
            except ValueError as error:
                rows.append(dict(u=point, source=sample["source"], errors=[f"参考模型无法复算：{error}"]))
                continue
            (failed if errors else verified).add(point)
        rows.append(dict(u=point, source=sample["source"], errors=errors))
    return {"焦距": model.get("f") if model else None, "采样": rows,
            "未覆盖": trace.get("skipped", [])}, failed, verified
