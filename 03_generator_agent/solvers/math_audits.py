# -*- coding: utf-8 -*-
"""数学教学模型的第一层自检。

每条检查都用“另一条等价路径”复核求解器输出：三角恒等式、面积/周长缩放、
概率归一、点积与夹角互算、回归的离差公式等。自检不过说明求解器内部矛盾。
"""

import math
from fractions import Fraction
from statistics import mean, pvariance

from solver_contract import Audit, register


@register("solveLinearSystem")
def audit_linear_system(request, result):
    audit = Audit("solveLinearSystem")
    k1, b1, k2, b2 = (request.get("k1"), request.get("b1"),
                      request.get("k2"), request.get("b2"))
    status = result.get("status")
    if k1 == k2:
        audit.one_of("status", status, {"平行", "重合"})
        audit.need("status_matches_intercepts",
                   (status == "重合") == (b1 == b2), status)
        audit.need("no_solution_point", result.get("x") is None and result.get("y") is None)
    else:
        audit.one_of("status", status, {"唯一交点"})
        x = (b2 - b1) / (k1 - k2)
        audit.same("x", result.get("x"), x)
        audit.same("y_matches_first_line", result.get("y"), k1 * x + b1)
        audit.same("y_matches_second_line", result.get("y"), k2 * x + b2)
    return audit.result()


@register("solveRightTriangle")
def audit_right_triangle(request, result):
    audit = Audit("solveRightTriangle")
    opposite, adjacent = request.get("opposite"), request.get("adjacent")
    hypotenuse = math.hypot(opposite, adjacent)
    audit.same("hypotenuse", result.get("hypotenuse"), hypotenuse)
    sine, cosine = opposite / hypotenuse, adjacent / hypotenuse
    audit.same("sine", result.get("sine"), sine)
    audit.same("cosine", result.get("cosine"), cosine)
    audit.same("pythagoras", sine ** 2 + cosine ** 2, 1)
    audit.same("tangent", result.get("tangent"), opposite / adjacent)
    audit.same("angle_deg", result.get("angle_deg"), math.degrees(math.atan2(opposite, adjacent)))
    audit.same("area", result.get("area"), opposite * adjacent / 2)
    return audit.result()


@register("solveDescriptiveStats")
def audit_descriptive_stats(request, result):
    audit = Audit("solveDescriptiveStats")
    values = [request.get("x%d" % index) for index in range(1, 6)]
    audit.same("mean", result.get("mean"), float(mean(values)))
    audit.same("variance", result.get("variance"), float(pvariance(values)))
    audit.same("sum_matches_mean", sum(values), (result.get("mean") or 0) * len(values))
    audit.same("values_preserved", result.get("values"), values)
    return audit.result()


@register("solveSequences")
def audit_sequences(request, result):
    audit = Audit("solveSequences")
    first = request.get("first", 0)
    difference = request.get("difference", 0)
    ratio = request.get("ratio", 1)
    count = int(request.get("count", 0))
    arithmetic = [first + index * difference for index in range(count)]
    geometric = [first * ratio ** index for index in range(count)]
    audit.same("arithmetic_term", result.get("arithmetic_term"), arithmetic[-1])
    audit.same("arithmetic_sum", result.get("arithmetic_sum"), math.fsum(arithmetic))
    audit.same("geometric_term", result.get("geometric_term"), geometric[-1])
    audit.same("geometric_sum", result.get("geometric_sum"), math.fsum(geometric))
    audit.same("arithmetic_series", result.get("arithmetic"), arithmetic)
    audit.same("geometric_series", result.get("geometric"), geometric)
    return audit.result()


@register("solveReciprocal")
def audit_reciprocal(request, result):
    audit = Audit("solveReciprocal")
    coefficient, x = request.get("k"), request.get("x")
    audit.same("y", result.get("y"), coefficient / x)
    audit.same("product", result.get("product"), coefficient)
    audit.same("y_times_x", (result.get("y") or 0) * x, coefficient)
    audit.one_of("quadrants", result.get("quadrants"),
                 {"第一、三象限", "第二、四象限"})
    return audit.result()


@register("solveSinusoid")
def audit_sinusoid(request, result):
    audit = Audit("solveSinusoid")
    amplitude, omega = request.get("amplitude"), request.get("omega")
    phase, x = request.get("phase"), request.get("x")
    audit.same("y", result.get("y"), amplitude * math.sin(omega * x + phase))
    audit.same("period", result.get("period"), math.tau / abs(omega))
    audit.same("magnitude", result.get("magnitude"), abs(amplitude))
    audit.same("minimum", result.get("minimum"), -abs(amplitude))
    audit.same("maximum", result.get("maximum"), abs(amplitude))
    audit.same("shift", result.get("shift"), -phase / omega)
    audit.same("range", (result.get("maximum") or 0) - (result.get("minimum") or 0), 2 * abs(amplitude))
    return audit.result()


@register("solveExpLog")
def audit_exp_log(request, result):
    audit = Audit("solveExpLog")
    base, x = request.get("base"), request.get("x")
    audit.same("exponential", result.get("exponential"), base ** x, rel=1e-12)
    audit.same("logarithm", result.get("logarithm"), math.log(x, base), rel=1e-12)
    audit.same("inverse", result.get("inverse"), x)
    audit.same("exp_of_log", base ** (result.get("logarithm") or 0), x, rel=1e-9)
    audit.one_of("trend", result.get("trend"), {"递增", "递减"})
    audit.need("trend_matches_base", (result.get("trend") == "递增") == (base > 1))
    return audit.result()


@register("solveFunctionTransform")
def audit_function_transform(request, result):
    audit = Audit("solveFunctionTransform")
    a, h, k, x = request.get("a"), request.get("h"), request.get("k"), request.get("x")
    base = (x - h) ** 2 if request.get("family") == "quadratic" else abs(x - h)
    audit.same("y", result.get("y"), a * base + k)
    audit.same("vertex_x", result.get("vertex_x"), h)
    audit.same("vertex_y", result.get("vertex_y"), k)
    audit.one_of("orientation", result.get("orientation"), {"向上", "向下"})
    audit.need("orientation_matches_sign", (result.get("orientation") == "向上") == (a > 0))
    return audit.result()


@register("solveDerivative")
def audit_derivative(request, result):
    audit = Audit("solveDerivative")
    a, b, c, x = request.get("a"), request.get("b"), request.get("c"), request.get("x")
    audit.same("y", result.get("y"), a * x * x + b * x + c)
    audit.same("slope", result.get("slope"), 2 * a * x + b)
    audit.same("intercept", result.get("intercept"), c - a * x * x)
    audit.same("tangent_value_at_x", (result.get("slope") or 0) * x + (result.get("intercept") or 0),
               result.get("y"))
    slope = result.get("slope") or 0
    expected = "上升" if slope > 0 else "下降" if slope < 0 else "水平"
    audit.one_of("direction", result.get("direction"), {expected})
    return audit.result()


@register("solveSimilarTriangles")
def audit_similar_triangles(request, result):
    audit = Audit("solveSimilarTriangles")
    a, b, c, scale = (request.get("a"), request.get("b"), request.get("c"),
                      request.get("scale"))
    audit.same("a2", result.get("a2"), a * scale)
    audit.same("b2", result.get("b2"), b * scale)
    audit.same("c2", result.get("c2"), c * scale)
    audit.same("perimeter", result.get("perimeter"), (a + b + c) * scale)
    audit.same("perimeter_ratio", result.get("perimeter_ratio"), scale)
    audit.same("area_ratio", result.get("area_ratio"), scale ** 2)
    # 海伦公式独立复算面积
    shortest, middle, longest = sorted((a, b, c))
    gap = shortest - (longest - middle)
    area = math.sqrt((longest + middle + shortest) * gap
                     * (shortest + longest - middle)
                     * (longest + middle - shortest)) / 4
    audit.same("area", result.get("area"), area * scale ** 2)
    return audit.result()


@register("solveCircle")
def audit_circle(request, result):
    audit = Audit("solveCircle")
    radius, offset = request.get("radius"), request.get("offset")
    audit.same("circumference", result.get("circumference"), math.tau * radius)
    audit.same("area", result.get("area"), math.pi * radius * radius)
    half = math.sqrt((radius - offset) * (radius + offset))
    audit.same("half_chord", result.get("half_chord"), half)
    audit.same("chord", result.get("chord"), 2 * half)
    audit.same("pythagoras", half ** 2 + offset ** 2, radius ** 2)
    angle = math.degrees(math.atan2(half, offset))
    audit.same("central_angle", result.get("central_angle"), 2 * angle)
    audit.same("inscribed_angle", result.get("inscribed_angle"), angle)
    audit.same("central_is_twice_inscribed", result.get("central_angle"),
               2 * (result.get("inscribed_angle") or 0))
    return audit.result()


@register("solvePolygonArea")
def audit_polygon_area(request, result):
    audit = Audit("solvePolygonArea")
    bottom, top, height = request.get("bottom"), request.get("top"), request.get("height")
    audit.same("area", result.get("area"), (bottom + top) * height / 2)
    audit.same("equivalent_base", result.get("equivalent_base"), (bottom + top) / 2)
    audit.same("area_from_equivalent_base", result.get("area"),
               (result.get("equivalent_base") or 0) * height)
    expected = "三角形" if top == 0 else "平行四边形" if top == bottom else "梯形"
    audit.one_of("shape", result.get("shape"), {expected})
    return audit.result()


@register("solveConstructions")
def audit_constructions(request, result):
    audit = Audit("solveConstructions")
    length, angle = request.get("length"), request.get("angle")
    audit.same("midpoint", result.get("midpoint"), length / 2)
    audit.same("perpendicular", result.get("perpendicular"), 90)
    audit.same("bisector", result.get("bisector"), angle / 2)
    audit.same("bisector_double", (result.get("bisector") or 0) * 2, angle)
    return audit.result()


@register("solveEllipse")
def audit_ellipse(request, result):
    audit = Audit("solveEllipse")
    a, b = request.get("a"), request.get("b")
    focus = math.sqrt((a - b) * (a + b))
    audit.same("focus", result.get("focus"), focus)
    audit.same("focus_relation", (result.get("focus") or 0) ** 2, a ** 2 - b ** 2)
    audit.same("eccentricity", result.get("eccentricity"), focus / a)
    audit.same("distance_sum", result.get("distance_sum"), 2 * a)
    audit.same("area", result.get("area"), math.pi * a * b)
    return audit.result()


@register("solveSampling")
def audit_sampling(request, result):
    audit = Audit("solveSampling")
    good, bad = request.get("good"), request.get("bad")
    draws, hits = int(request.get("draws")), int(request.get("hits"))
    total = good + bad
    probabilities = result.get("probabilities") or []
    audit.need("probability_vector_size", len(probabilities) == draws + 1, str(len(probabilities)))
    audit.same("probabilities_sum", math.fsum(probabilities), 1)
    if 0 <= hits < len(probabilities):
        audit.same("probability", result.get("probability"), probabilities[hits])
    audit.same("expected", result.get("expected"), draws * good / total)
    audit.need("probabilities_in_range", all(-1e-12 <= value <= 1 + 1e-12 for value in probabilities))
    return audit.result()


@register("solveBinomial")
def audit_binomial(request, result):
    audit = Audit("solveBinomial")
    trials, hits = int(request.get("trials")), int(request.get("hits"))
    probability = request.get("p")
    probabilities = result.get("probabilities") or []
    audit.same("probabilities_sum", math.fsum(probabilities), 1, rel=1e-9, abs_tol=1e-9)
    if 0 <= hits < len(probabilities):
        audit.same("probability", result.get("probability"), probabilities[hits])
    audit.same("mean", result.get("mean"), trials * probability)
    audit.same("variance", result.get("variance"), trials * probability * (1 - probability))
    return audit.result()


@register("solveRegression")
def audit_regression(request, result):
    audit = Audit("solveRegression")
    x = [request.get("x%d" % index) for index in range(1, 4)]
    y = [request.get("y%d" % index) for index in range(1, 4)]
    x_bar, y_bar = mean(x), mean(y)
    denominator = math.fsum((value - x_bar) ** 2 for value in x)
    numerator = math.fsum((x[i] - x_bar) * (y[i] - y_bar) for i in range(3))
    slope = numerator / denominator
    audit.same("slope", result.get("slope"), slope)
    audit.same("intercept", result.get("intercept"), y_bar - slope * x_bar)
    audit.same("passes_through_centroid",
               (result.get("slope") or 0) * x_bar + (result.get("intercept") or 0), y_bar)
    return audit.result()


@register("solveDotProduct")
def audit_dot_product(request, result):
    audit = Audit("solveDotProduct")
    ax, ay, bx, by = (request.get("ax"), request.get("ay"),
                      request.get("bx"), request.get("by"))
    dot = ax * bx + ay * by
    audit.same("dot", result.get("dot"), dot)
    if result.get("angle") is None:
        audit.one_of("state", result.get("state"), {"含零向量"})
    else:
        cross = abs(ax * by - ay * bx)
        audit.same("angle", result.get("angle"), math.degrees(math.atan2(cross, dot)))
        audit.same("cosine_relation", math.cos(math.radians(result.get("angle"))),
                   dot / (math.hypot(ax, ay) * math.hypot(bx, by)))
    return audit.result()


@register("solveFractions")
def audit_fractions(request, result):
    audit = Audit("solveFractions")
    n1, d1, n2, d2 = (int(request.get("n1")), int(request.get("d1")),
                      int(request.get("n2")), int(request.get("d2")))
    common = math.lcm(d1, d2)
    audit.same("common", result.get("common"), common)
    audit.same("left", result.get("left"), n1 * (common // d1))
    audit.same("right", result.get("right"), n2 * (common // d2))
    sign = -1 if request.get("mode") == "subtract" else 1
    expected = Fraction(n1, d1) + sign * Fraction(n2, d2)
    audit.same("numerator", result.get("numerator"), expected.numerator)
    audit.same("denominator", result.get("denominator"), expected.denominator)
    audit.need("denominator_positive", (result.get("denominator") or 0) > 0)
    audit.same("value", Fraction(int(result.get("numerator")), int(result.get("denominator"))),
               expected)
    return audit.result()


@register("solveAmgm")
def audit_amgm(request, result):
    audit = Audit("solveAmgm")
    a, b = request.get("a"), request.get("b")
    audit.same("arithmetic", result.get("arithmetic"), (a + b) / 2)
    audit.same("geometric", result.get("geometric"), math.sqrt(a * b))
    audit.need("am_gm_order", (result.get("arithmetic") or 0) + 1e-12 >= (result.get("geometric") or 0))
    expected = "取等" if a == b else "严格大于"
    audit.one_of("state", result.get("state"), {expected})
    audit.need("gap_positive", (result.get("gap") or 0) >= 0)
    return audit.result()


@register("solveOrthographic")
def audit_orthographic(request, result):
    audit = Audit("solveOrthographic")
    width, depth, height = (int(request.get("width")), int(request.get("depth")),
                            int(request.get("height")))
    step_width, rise = int(request.get("step_width")), int(request.get("rise"))
    front = width * height + step_width * rise
    audit.same("front", result.get("front"), front)
    audit.same("side", result.get("side"), depth * (height + rise))
    audit.same("top", result.get("top"), width * depth)
    audit.same("volume", result.get("volume"), depth * front)
    return audit.result()


@register("solveSphereContact")
def audit_sphere_contact(request, result):
    audit = Audit("solveSphereContact")
    a, b, c = request.get("a"), request.get("b"), request.get("c")
    smallest = min(a, b, c)
    audit.same("inside_radius", result.get("inside_radius"), smallest / 2)
    audit.same("outside_radius", result.get("outside_radius"), math.hypot(a, b, c) / 2)
    audit.same("contact_faces", result.get("contact_faces"),
               2 * sum(edge == smallest for edge in (a, b, c)))
    audit.need("outside_larger", (result.get("outside_radius") or 0) >= (result.get("inside_radius") or 0))
    return audit.result()


@register("solveSurfacePath")
def audit_surface_path(request, result):
    audit = Audit("solveSurfacePath")
    a, b, c = request.get("a"), request.get("b"), request.get("c")
    paths = [math.hypot(a + b, c), math.hypot(a + c, b), math.hypot(b + c, a)]
    audit.same("ab", result.get("ab"), paths[0])
    audit.same("ac", result.get("ac"), paths[1])
    audit.same("bc", result.get("bc"), paths[2])
    audit.same("shortest", result.get("shortest"), min(paths))
    return audit.result()


@register("solveCavalieri")
def audit_cavalieri(request, result):
    audit = Audit("solveCavalieri")
    width, depth, height = (request.get("width"), request.get("depth"),
                            request.get("height"))
    section = width * depth
    audit.same("section", result.get("section"), section)
    audit.same("straight", result.get("straight"), section * height)
    audit.same("slanted", result.get("slanted"), section * height)
    audit.same("shear_preserves_volume", result.get("straight"), result.get("slanted"))
    return audit.result()


@register("solveTravel")
def audit_travel(request, result):
    audit = Audit("solveTravel")
    gap, v1, v2 = request.get("gap"), request.get("v1"), request.get("v2")
    closing = v1 - v2
    audit.same("closing", result.get("closing"), closing)
    time = result.get("time")
    if gap == 0:
        audit.one_of("state", result.get("state"), {"起点相同"})
        audit.same("time", time, 0)
    elif closing <= 0:
        audit.one_of("state", result.get("state"), {"不相遇"})
        audit.need("no_meeting_time", time is None, repr(time))
    else:
        audit.same("time", time, gap / closing)
        audit.same("position", result.get("position"), v1 * time)
        audit.same("meeting_condition",
                   (result.get("position") or 0) - gap, (v2 * (time or 0)))
    return audit.result()
