# -*- coding: utf-8 -*-
"""Volume formulas and conservation checks for supported school solids."""
import math


def _positive(request, key, label):
    try:
        value = float(request[key])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(label + "必须提供有限正数") from exc
    if not math.isfinite(value) or value <= 0:
        raise ValueError(label + "必须提供有限正数")
    return value


def solve_solid_volume(request):
    if not isinstance(request, dict):
        raise ValueError("立体体积请求必须是对象")
    solid = str(request.get("solid", ""))
    if solid == "cube":
        a = _positive(request, "edge", "棱长")
        value, dims = a**3, {"edge": a}
    elif solid == "cuboid":
        l, w, h = (_positive(request, k, label) for k, label in
                   (("length", "长"), ("width", "宽"), ("height", "高")))
        value, dims = l*w*h, {"length": l, "width": w, "height": h}
    elif solid == "triangular_prism":
        b, th, length = (_positive(request, k, label) for k, label in
                         (("base", "三角形底边"), ("triangle_height", "三角形高"), ("length", "棱柱长")))
        value, dims = b*th*length/2, {"base": b, "triangle_height": th, "length": length}
    elif solid == "square_pyramid":
        b, h = _positive(request, "base", "底面边长"), _positive(request, "height", "高")
        value, dims = b*b*h/3, {"base": b, "height": h}
    elif solid in ("cylinder", "cone"):
        r, h = _positive(request, "radius", "底面半径"), _positive(request, "height", "高")
        value = math.pi*r*r*h*(1 if solid == "cylinder" else 1/3)
        dims = {"radius": r, "height": h}
    elif solid == "sphere":
        r = _positive(request, "radius", "球半径")
        value, dims = 4*math.pi*r**3/3, {"radius": r}
    else:
        raise ValueError("不支持的立体类型：%s" % solid)
    return {"solid": solid, "dimensions": dims, "volume": value,
            "unit": "unit^3", "checks": {"finite": math.isfinite(value), "positive": value > 0}}


def solve_composite_volume(components):
    if not isinstance(components, list) or not components:
        raise ValueError("组合体至少需要一个有明确定义的组成部分")
    results = [solve_solid_volume(item) for item in components]
    total = sum(item["volume"] for item in results)
    if not math.isfinite(total):
        raise ValueError("组合体总体积超出有限范围")
    return {"operation": "sum_disjoint_components", "components": results,
            "volume": total, "unit": "unit^3",
            "checks": {"finite": True, "positive": total > 0}}


def check_volume_partition(original, parts, relative_tolerance=1e-8):
    try:
        total = float(original)
        pieces = [float(x) for x in parts]
        tolerance = float(relative_tolerance)
    except (TypeError, ValueError) as exc:
        raise ValueError("体积分割检查参数无效") from exc
    if (not math.isfinite(total) or total <= 0 or not pieces or
            any(not math.isfinite(x) or x < 0 for x in pieces) or
            not math.isfinite(tolerance) or tolerance < 0):
        raise ValueError("原体积须为正，分割体积须有限且非负")
    summed = sum(pieces)
    error = abs(summed-total)
    allowed = max(1e-12, abs(total)*tolerance)
    return {"original": total, "parts": pieces, "sum": summed, "absolute_error": error,
            "relative_error": error/total, "ok": error <= allowed, "unit": "unit^3"}
