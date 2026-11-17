"""Independent references for interactive mathematics lessons."""

import math
from statistics import mean, pvariance


def numbers(request, *fields):
    if not isinstance(request, dict):
        raise ValueError("需要结构化数学参数")
    values = [request.get(field) for field in fields]
    if any(type(value) not in (int, float) or abs(value) > 1e6
           or not math.isfinite(value) or (value != 0 and abs(value) < 1e-9)
           for value in values):
        raise ValueError("参数须为 0 或绝对值在 1e-9 到 1e6 内的有限数")
    return values


def solve_linear_system(request):
    """Classify the intersection of two lines in slope-intercept form."""
    k1, b1, k2, b2 = numbers(request, "k1", "b1", "k2", "b2")
    if k1 == k2:
        return {"status": "重合" if b1 == b2 else "平行", "x": None, "y": None}
    x = (b2 - b1) / (k1 - k2)
    y = (k1 * b2 - k2 * b1) / (k1 - k2)
    return {"status": "唯一交点", "x": x, "y": y}


def solve_right_triangle(request):
    opposite, adjacent = numbers(request, "opposite", "adjacent")
    if min(opposite, adjacent) <= 0:
        raise ValueError("两条直角边必须大于零")
    hypotenuse = math.hypot(opposite, adjacent)
    return {"hypotenuse": hypotenuse, "angle_deg": math.degrees(math.atan2(opposite, adjacent)),
            "sine": opposite / hypotenuse, "cosine": adjacent / hypotenuse,
            "tangent": opposite / adjacent, "area": opposite * adjacent / 2}


def solve_descriptive_stats(request):
    values = numbers(request, "x1", "x2", "x3", "x4", "x5")
    return {"mean": float(mean(values)), "variance": float(pvariance(values)), "values": values}


def solve_sequences(request):
    first, difference, ratio, count = numbers(request, "first", "difference", "ratio", "count")
    if int(count) != count or not 1 <= count <= 20 or abs(ratio) > 5:
        raise ValueError("项数须为 1–20 的整数，公比绝对值至多为 5")
    count = int(count)
    arithmetic = [first + i * difference for i in range(count)]
    geometric = [first * ratio ** i for i in range(count)]
    return {"arithmetic_term": arithmetic[-1], "arithmetic_sum": math.fsum(arithmetic),
            "geometric_term": geometric[-1], "geometric_sum": math.fsum(geometric),
            "arithmetic": arithmetic, "geometric": geometric}


def solve_reciprocal(request):
    k, x = numbers(request, "k", "x")
    if k == 0 or x == 0:
        raise ValueError("反比例系数和取样横坐标必须非零")
    return {"y": k / x, "product": k, "quadrants": "第一、三象限" if k > 0 else "第二、四象限"}


def solve_sinusoid(request):
    amplitude, omega, phase, x = numbers(request, "amplitude", "omega", "phase", "x")
    if amplitude == 0 or omega == 0:
        raise ValueError("振幅系数与角频率必须非零")
    magnitude = abs(amplitude)
    return {"y": amplitude * math.sin(omega * x + phase), "period": math.tau / abs(omega),
            "magnitude": magnitude, "minimum": -magnitude, "maximum": magnitude,
            "shift": -phase / omega}


def solve_exp_log(request):
    base, x = numbers(request, "base", "x")
    if not 0.1 <= base <= 10 or base == 1 or not 0 < x <= 10:
        raise ValueError("底数须在 0.1–10 内且不等于 1，取样数须在 (0, 10] 内")
    exponential = base ** x
    return {"exponential": exponential, "logarithm": math.log(x, base),
            "inverse": x, "trend": "递增" if base > 1 else "递减"}


def solve_function_transform(request):
    a, h, k, x = numbers(request, "a", "h", "k", "x")
    if a == 0:
        raise ValueError("纵向伸缩系数必须非零")
    family = request.get("family")
    if family not in ("quadratic", "absolute"):
        raise ValueError("请选择平方函数或绝对值函数")
    value = (x - h) ** 2 if family == "quadratic" else abs(x - h)
    return {"y": a * value + k, "vertex_x": h, "vertex_y": k,
            "orientation": "向上" if a > 0 else "向下"}


def solve_derivative(request):
    a, b, c, x = numbers(request, "a", "b", "c", "x")
    value = a * x * x + b * x + c
    slope = 2 * a * x + b
    return {"y": value, "slope": slope, "intercept": c - a * x * x,
            "direction": "上升" if slope > 0 else "下降" if slope < 0 else "水平"}


def solve_similar_triangles(request):
    a, b, c, scale = numbers(request, "a", "b", "c", "scale")
    shortest, middle, longest = sorted((a, b, c))
    gap = shortest - (longest - middle)
    if shortest <= 0 or gap <= 0 or scale <= 0:
        raise ValueError("边长须组成非退化三角形，相似比须为正")
    area = math.sqrt((longest + (middle + shortest)) * gap
                     * (shortest + (longest - middle)) * (longest + (middle - shortest))) / 4
    return {"a2": a * scale, "b2": b * scale, "c2": c * scale,
            "perimeter": (a + b + c) * scale, "area": area * scale ** 2,
            "perimeter_ratio": scale, "area_ratio": scale ** 2}


def solve_circle(request):
    radius, offset = numbers(request, "radius", "offset")
    if radius <= 0 or not 0 <= offset < radius:
        raise ValueError("半径须为正，圆心到弦的距离须小于半径")
    half_chord = math.sqrt((radius - offset) * (radius + offset))
    angle = math.degrees(math.atan2(half_chord, offset))
    return {"circumference": math.tau * radius, "area": math.pi * radius * radius,
            "half_chord": half_chord, "chord": 2 * half_chord,
            "central_angle": 2 * angle, "inscribed_angle": angle}


def solve_polygon_area(request):
    bottom, top, height = numbers(request, "bottom", "top", "height")
    if bottom <= 0 or height <= 0 or top < 0:
        raise ValueError("下底和高须为正，上底须为非负")
    return {"area": (bottom + top) * height / 2, "equivalent_base": (bottom + top) / 2,
            "shape": "三角形" if top == 0 else "平行四边形" if top == bottom else "梯形"}


def solve_constructions(request):
    length, angle = numbers(request, "length", "angle")
    if length <= 0 or not 0 < angle < 180:
        raise ValueError("线段长度须为正，角须在 0° 与 180° 之间")
    return {"midpoint": length / 2, "perpendicular": 90, "bisector": angle / 2}


def solve_ellipse(request):
    a, b = numbers(request, "a", "b")
    if not 0 < b <= a:
        raise ValueError("半轴须满足 0 < b ≤ a")
    focus = math.sqrt((a - b) * (a + b))
    return {"focus": focus, "eccentricity": focus / a, "distance_sum": 2 * a,
            "area": math.pi * a * b}


def integers(request, *fields):
    values = numbers(request, *fields)
    if any(int(value) != value for value in values):
        raise ValueError("指定的计数和分数项须为整数")
    return tuple(int(value) for value in values)


def solve_sampling(request):
    good, bad, draws, hits = integers(request, "good", "bad", "draws", "hits")
    mode = request.get("mode")
    total = good + bad
    if (min(good, bad) < 0 or not 1 <= total <= 100 or not 1 <= draws <= 8 or not 0 <= hits <= draws
            or mode not in ("with", "without") or (mode == "without" and draws > total)):
        raise ValueError("抽样数量或方式超出范围")
    if mode == "with":
        denominator = total ** draws
        weights = [math.comb(draws, i) * good ** i * bad ** (draws - i) for i in range(draws + 1)]
    else:
        denominator = math.comb(total, draws)
        weights = [math.comb(good, i) * math.comb(bad, draws - i) for i in range(draws + 1)]
    probabilities = [weight / denominator for weight in weights]
    return {"probability": probabilities[hits], "expected": draws * good / total, "probabilities": probabilities}


def solve_binomial(request):
    trials, hits = integers(request, "trials", "hits")
    probability, = numbers(request, "p")
    if not 1 <= trials <= 50 or not 0 <= hits <= trials or not 0 <= probability <= 1:
        raise ValueError("试验次数、成功次数或成功概率超出范围")
    probabilities = [math.comb(trials, i) * probability ** i * (1 - probability) ** (trials - i)
                     for i in range(trials + 1)]
    return {"probability": probabilities[hits], "mean": trials * probability,
            "variance": trials * probability * (1 - probability), "probabilities": probabilities}


def solve_regression(request):
    x = numbers(request, "x1", "x2", "x3")
    y = numbers(request, "y1", "y2", "y3")
    if x[0] == x[1] == x[2]:
        raise ValueError("横坐标不能全部相同")
    slope, intercept = _linear_regression(x, y)
    return {"slope": slope, "intercept": intercept}


def _linear_regression(x, y):
    # Pairwise differences eliminate the means from the covariance and variance.
    pairs = ((0, 1), (0, 2), (1, 2))
    squared = math.fsum((x[i] - x[j]) ** 2 for i, j in pairs)
    products = math.fsum((x[i] - x[j]) * (y[i] - y[j]) for i, j in pairs)
    slope = products / squared
    return slope, (math.fsum(y) - slope * math.fsum(x)) / len(x)


def solve_dot_product(request):
    ax, ay, bx, by = numbers(request, "ax", "ay", "bx", "by")
    value = ax * bx + ay * by
    if math.hypot(ax, ay) == 0 or math.hypot(bx, by) == 0:
        return {"dot": value, "angle": None, "state": "含零向量"}
    cross = abs(ax * by - ay * bx)
    angle = math.degrees(math.atan2(cross, value))
    state = "锐角方向" if value > 0 else "钝角方向" if value < 0 else "垂直"
    if cross == 0:
        state = "同向" if value > 0 else "反向"
    return {"dot": value, "angle": angle, "state": state}


def solve_fractions(request):
    from fractions import Fraction

    n1, d1, n2, d2 = integers(request, "n1", "d1", "n2", "d2")
    mode = request.get("mode")
    if d1 <= 0 or d2 <= 0 or mode not in ("add", "subtract"):
        raise ValueError("分母须为正整数，运算须为加法或减法")
    common = math.lcm(d1, d2)
    value = Fraction(n1, d1) + (-1 if mode == "subtract" else 1) * Fraction(n2, d2)
    return {"common": common, "left": n1 * (common // d1), "right": n2 * (common // d2),
            "numerator": value.numerator, "denominator": value.denominator}


def solve_amgm(request):
    a, b = numbers(request, "a", "b")
    if min(a, b) < 0:
        raise ValueError("算术–几何平均不等式要求两个输入非负")
    root_sum = math.sqrt(a) + math.sqrt(b)
    gap = ((a - b) / root_sum) ** 2 / 2 if root_sum else 0
    return {"arithmetic": (a + b) / 2, "geometric": math.sqrt(a * b),
            "gap": gap, "state": "取等" if a == b else "严格大于"}


def solve_orthographic(request):
    width, depth, height, step_width, rise = integers(
        request, "width", "depth", "height", "step_width", "rise")
    if (not all(1 <= value <= 12 for value in (width, depth, height))
            or not 1 <= step_width <= width or not 0 <= rise <= 12):
        raise ValueError("底座尺寸须为 1–12 的整数，台阶尺寸超出范围")
    return {"front": width * height + step_width * rise, "side": depth * (height + rise),
            "top": width * depth, "volume": depth * (width * height + step_width * rise)}


def solve_sphere_contact(request):
    a, b, c = numbers(request, "a", "b", "c")
    smallest = min(a, b, c)
    if smallest <= 0:
        raise ValueError("长方体三边须为正")
    return {"inside_radius": smallest / 2, "outside_radius": math.hypot(a, b, c) / 2,
            "contact_faces": 2 * sum(edge == smallest for edge in (a, b, c))}


def solve_surface_path(request):
    a, b, c = numbers(request, "a", "b", "c")
    if min(a, b, c) <= 0:
        raise ValueError("长方体三边须为正")
    paths = [math.hypot(a + b, c), math.hypot(a + c, b), math.hypot(b + c, a)]
    return {"ab": paths[0], "ac": paths[1], "bc": paths[2], "shortest": min(paths)}


def solve_cavalieri(request):
    width, depth, height, shear = numbers(request, "width", "depth", "height", "shear")
    if min(width, depth, height) <= 0 or abs(shear) > 3 * width:
        raise ValueError("底面尺寸和高度须为正，剪切位移绝对值至多为底宽的三倍")
    section = width * depth
    return {"section": section, "straight": section * height, "slanted": section * height}


def solve_travel(request):
    gap, v1, v2 = numbers(request, "gap", "v1", "v2")
    if gap < 0:
        raise ValueError("初始间距须为非负")
    closing = v1 - v2
    if gap == 0:
        return {"closing": closing, "time": 0, "position": 0, "state": "起点相同"}
    if closing <= 0:
        return {"closing": closing, "time": None, "position": None, "state": "不相遇"}
    time = gap / closing
    state = "相向而行" if v1 > 0 > v2 else "相遇静止对象" if v1 == 0 or v2 == 0 else "同向追及"
    return {"closing": closing, "time": time, "position": v1 * time, "state": state}


SOLVERS = {
    "solveLinearSystem": solve_linear_system,
    "solveRightTriangle": solve_right_triangle,
    "solveDescriptiveStats": solve_descriptive_stats,
    "solveSequences": solve_sequences,
    "solveReciprocal": solve_reciprocal,
    "solveSinusoid": solve_sinusoid,
    "solveExpLog": solve_exp_log,
    "solveFunctionTransform": solve_function_transform,
    "solveDerivative": solve_derivative,
    "solveSimilarTriangles": solve_similar_triangles,
    "solveCircle": solve_circle,
    "solvePolygonArea": solve_polygon_area,
    "solveConstructions": solve_constructions,
    "solveEllipse": solve_ellipse,
    "solveSampling": solve_sampling,
    "solveBinomial": solve_binomial,
    "solveRegression": solve_regression,
    "solveDotProduct": solve_dot_product,
    "solveFractions": solve_fractions,
    "solveAmgm": solve_amgm,
    "solveOrthographic": solve_orthographic,
    "solveSphereContact": solve_sphere_contact,
    "solveSurfacePath": solve_surface_path,
    "solveCavalieri": solve_cavalieri,
    "solveTravel": solve_travel,
}
