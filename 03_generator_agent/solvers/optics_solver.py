# -*- coding: utf-8 -*-
"""Independent thin-lens oracle for the 3D optics page.

This mirrors ``frame/optics_solver.js`` line for line, but is written and run
separately so the reviewer can compare two implementations instead of trusting
the page's own numbers.

Conventions: centimetres; lens at x=0, object at x=-u, screen at x=+s; object
height h>0 (upright). Gaussian thin-lens: 1/f = 1/u + 1/v => v = uf/(u-f),
magnification m = -v/u (negative => inverted).
"""

import math

REL_TOL = 1e-6      # u=f / u=2f classification threshold (relative to f)
CHECK_TOL = 1e-12   # gauss / magnification self-check


class OpticsError(ValueError):
    """Invalid or non-finite optics model."""


def _finite(model, name, fallback=None):
    value = model.get(name, fallback)
    if value is None:
        raise OpticsError("%s 缺失" % name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OpticsError("%s 必须是数字" % name)
    value = float(value)
    if not math.isfinite(value):
        raise OpticsError("%s 必须是有限数" % name)
    return value


def _screen(model):
    screen = model.get("screen")
    if isinstance(screen, dict):
        return _finite(screen, "s")
    return _finite(model, "screen", 0.0)


def classify(u, f):
    tol = REL_TOL * max(1.0, f)
    if abs(u - f) <= tol:
        return "u=f"
    if abs(u - 2 * f) <= tol:
        return "u=2f"
    if u > 2 * f:
        return "u>2f"
    if u > f:
        return "f<u<2f"
    return "u<f"


def kind_text(kind, m):
    if kind == "none":
        return "不成像"
    if abs(m) > 1.0005:
        size = "放大"
    elif abs(m) < 0.9995:
        size = "缩小"
    else:
        size = "等大"
    pose = "倒立" if m < 0 else "正立"
    return pose + "·" + size + "·" + ("实像" if kind == "real" else "虚像")


def _build_rays(f, u, h, v, m, x_right):
    rays = []

    def point(x, y):
        return [x, y, 0.0]

    # ① parallel ray -> passes through F'(f, 0)
    rays.append({
        "id": "parallel",
        "solid": [point(-u, h), point(0, h), point(x_right, h - h * x_right / f)],
        "dashed": [],
    })
    # ② centre ray -> straight through the optical centre
    rays.append({
        "id": "center",
        "solid": [point(-u, h), point(0, 0), point(x_right, -h * x_right / u)],
        "dashed": [],
    })
    # ③ focal ray -> emerges parallel to the axis (degenerate at u=f)
    if abs(u - f) > REL_TOL * max(1.0, f):
        y_c = -h * f / (u - f)
        rays.append({
            "id": "focus",
            "solid": [point(-u, h), point(0, y_c), point(x_right, y_c)],
            "dashed": [],
        })
    if v is not None and v < 0:
        image = [v, m * h]
        for ray in rays:
            ray["dashed"] = [list(ray["solid"][1]), point(image[0], image[1])]
    return rays


def solve_optics(model):
    if not isinstance(model, dict):
        raise OpticsError("模型必须是对象")
    f = _finite(model, "f")
    u = _finite(model, "u")
    h = _finite(model, "h", 2.0)
    s = _screen(model)
    if f <= 0:
        raise OpticsError("f 必须大于 0")
    if u <= 0:
        raise OpticsError("u 必须大于 0")
    if h <= 0:
        raise OpticsError("h 必须大于 0")
    if s < 0:
        raise OpticsError("screen.s 不能为负")

    u_class = classify(u, f)
    x_right = min(400.0, max(s, 2 * f, 40.0) + 10.0)
    result = {
        "schema_version": 1,
        "scene_id": "lens_imaging",
        "f": f, "u": u, "h": h, "s": s,
        "kind": "none", "uClass": u_class,
        "v": None, "m": None, "kindText": "不成像",
        "image": None,
        "onScreen": {"s": s, "sharp": False, "blur": None, "reason": ""},
        "rays": [],
        "checks": {"gauss": None, "magnification": None, "ok": False},
    }

    if u_class == "u=f":
        result["onScreen"]["reason"] = "u=f：折射光平行射出，不成像"
        result["rays"] = _build_rays(f, u, h, None, None, x_right)
        result["checks"] = {"gauss": 0.0, "magnification": 0.0, "ok": True}
        return result

    v = u * f / (u - f)
    m = -v / u
    result["v"] = v
    result["m"] = m
    result["kind"] = "real" if v > 0 else "virtual"
    result["kindText"] = kind_text(result["kind"], m)
    result["image"] = {
        "x": v,
        "y": m * h,
        "h": abs(m * h),
        "inverted": m < 0,
        "offscene": abs(v) > x_right,
    }

    if result["kind"] == "real":
        blur = abs(s - v)
        sharp_tol = max(0.5, 0.01 * abs(v))
        result["onScreen"]["blur"] = blur
        result["onScreen"]["sharp"] = blur <= sharp_tol
        result["onScreen"]["reason"] = (
            "光屏在像距处，像清晰" if blur <= sharp_tol
            else "光屏偏离像距 %.2f cm，像模糊" % blur
        )
    else:
        result["onScreen"]["reason"] = "虚像：光屏上接不到，需从透镜另一侧观察"

    gauss_residual = abs(1 / v - (1 / f - 1 / u)) * abs(f)
    mag_residual = abs(m + v / u)
    result["checks"] = {
        "gauss": gauss_residual,
        "magnification": mag_residual,
        "ok": gauss_residual <= CHECK_TOL and mag_residual <= CHECK_TOL,
    }
    result["rays"] = _build_rays(f, u, h, v, m, x_right)
    return result


def signature(model):
    return "|".join(str(x) for x in (
        "lens_imaging", model.get("f"), model.get("u"),
        model.get("h", 2), _screen(model),
    ))
