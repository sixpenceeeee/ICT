"""Independent reference for a real quadratic polynomial."""

import math


def solve_quadratic(request):
    if not isinstance(request, dict):
        raise ValueError("需要二次函数参数对象")
    a, b, c = (request.get(key) for key in ("a", "b", "c"))
    if any(type(value) not in (int, float) or not abs(value) <= 1e6 for value in (a, b, c)):
        raise ValueError("a、b、c 必须是绝对值不超过 1000000 的有限数字")
    if abs(a) < 1e-6:
        raise ValueError("二次项系数的绝对值必须至少为 0.000001")

    squared_b, product = b * b, 4 * a * c
    delta = squared_b - product
    if abs(delta) <= 1e-14 * max(squared_b, abs(product)):
        delta = 0
    x = -b / (2 * a)
    if delta < 0:
        roots = []
    elif delta == 0:
        roots = [x]
    else:
        q = -0.5 * (b + math.copysign(math.sqrt(delta), b))
        roots = sorted([q / a, c / q])
    return {
        "version": 1, "a": a, "b": b, "c": c,
        "vertex_x": x, "vertex_y": -delta / (4 * a), "axis_x": x,
        "discriminant": delta, "roots": roots, "y_intercept": c,
        "opening": "开口向上" if a > 0 else "开口向下",
    }
