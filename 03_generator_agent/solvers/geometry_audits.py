# -*- coding: utf-8 -*-
"""几何、二次函数与凸透镜的第一层自检。"""

import math

from solver_contract import Audit, register

SECTION_APIS = (
    "solveCubeCut", "solveCuboidCut", "solveTriangularPrismCut", "solveSquarePyramidCut",
)
CURVED_SECTION_APIS = ("solveCylinderCut", "solveConeCut", "solveSphereCut")


def _audit_finite_vertices(audit, vertices):
    for index, point in enumerate(vertices or []):
        audit.need("vertex_%d_size" % index, isinstance(point, (list, tuple)) and len(point) == 3)
        if isinstance(point, (list, tuple)) and len(point) == 3:
            audit.need("vertex_%d_finite" % index,
                       all(isinstance(value, (int, float)) and math.isfinite(value) for value in point))


def _audit_common_section(api, request, result):
    audit = Audit(api)
    dimensions = result.get("dimensions") or []
    scale = max([abs(value) for value in dimensions if isinstance(value, (int, float))] or [1.0])
    audit.positive("area", result.get("area"))
    audit.nonnegative("volume", result.get("volume"))
    residual = result.get("plane_residual")
    if residual is not None:
        audit.need("vertices_on_plane", abs(residual) <= 1e-6 * max(1.0, scale), repr(residual))
    _audit_finite_vertices(audit, result.get("vertices"))
    sides = result.get("sides")
    if sides is not None:
        audit.need("sides_range", 3 <= sides <= 8, repr(sides))
        audit.same("sides_match_vertices", sides, len(result.get("vertices") or []))
    return audit


@register(*SECTION_APIS)
def audit_polyhedron_section(request, result):
    audit = _audit_common_section("polyhedron-section", request, result)
    audit.need("shape_present", isinstance(result.get("shape"), str) and bool(result.get("shape")))
    return audit.result()


CURVED_BY_SOLID = {"sphere": "solveSphereCut", "cylinder": "solveCylinderCut",
                   "cone": "solveConeCut"}


@register(*CURVED_SECTION_APIS)
def audit_curved_section(request, result):
    audit = Audit(CURVED_BY_SOLID.get(result.get("solid"), "curved-section"))
    audit.positive("area", result.get("area"))
    audit.nonnegative("volume", result.get("volume"))
    boundary = result.get("boundary")
    if boundary is not None:
        audit.need("boundary_points_present", len(boundary) >= 3, str(len(boundary)))
    count = result.get("boundary_samples")
    if count is not None:
        audit.need("boundary_samples_positive", isinstance(count, int) and count >= 3, repr(count))
        if isinstance(count, int) and boundary is not None:
            audit.same("boundary_matches_samples", len(boundary), count)
    radius = result.get("section_radius")
    if radius is not None:
        audit.nonnegative("section_radius", radius)
    audit.need("shape_present", isinstance(result.get("shape"), str) and bool(result.get("shape")))
    return audit.result()


@register("solveSolidVolume")
def audit_solid_volume(request, result):
    audit = Audit("solveSolidVolume")
    audit.positive("volume", result.get("volume"))
    checks = result.get("checks") or {}
    audit.need("solver_checks_finite", checks.get("finite") is not False)
    audit.need("solver_checks_positive", checks.get("positive") is not False)
    return audit.result()


@register("solveSpatialMetrics")
def audit_spatial_metrics(request, result):
    audit = Audit("solveSpatialMetrics")
    value = result.get("value")
    audit.need("value_finite", isinstance(value, (int, float)) and math.isfinite(value), repr(value))
    audit.need("value_nonnegative", isinstance(value, (int, float)) and value >= -1e-12, repr(value))
    audit.need("unit_present", isinstance(result.get("unit"), str) and bool(result.get("unit")))
    return audit.result()


@register("solveQuadratic")
def audit_quadratic(request, result):
    audit = Audit("solveQuadratic")
    a, b, c = request.get("a"), request.get("b"), request.get("c")
    audit.need("a_nonzero", a not in (0, None), repr(a))
    vertex_x = -b / (2 * a) if a else None
    audit.same("vertex_x", result.get("vertex_x"), vertex_x)
    audit.same("axis_x", result.get("axis_x"), vertex_x)
    audit.same("vertex_y", result.get("vertex_y"),
               a * vertex_x ** 2 + b * vertex_x + c if a else None)
    discriminant = b * b - 4 * a * c
    audit.same("discriminant", result.get("discriminant"), discriminant)
    audit.same("y_intercept", result.get("y_intercept"), c)
    audit.one_of("opening", result.get("opening"), {"开口向上", "开口向下"})
    audit.need("opening_matches_sign", (result.get("opening") == "开口向上") == (a > 0))
    roots = result.get("roots") or []
    expected_count = 2 if discriminant > 1e-14 else 1 if abs(discriminant) <= 1e-14 else 0
    audit.same("root_count", len(roots), expected_count)
    for root in roots:
        audit.same("root_on_curve_%r" % root, a * root * root + b * root + c, 0, abs_tol=1e-9)
    return audit.result()


@register("solveThinLens")
def audit_thin_lens(request, result):
    audit = Audit("solveThinLens")
    u, f = request.get("u"), request.get("f")
    distance = result.get("image_distance_cm")
    if u == f:
        audit.need("no_finite_image", distance is None and result.get("magnification") is None)
        audit.one_of("state", result.get("state"), {"无有限像"})
        return audit.result()
    expected_distance = u * f / (u - f)
    audit.same("image_distance", distance, expected_distance, rel=1e-9)
    audit.same("magnification", result.get("magnification"), -f / (u - f), rel=1e-9)
    audit.same("lens_equation", 1 / f, 1 / u + 1 / (distance or 1), rel=1e-9)
    audit.same("magnification_from_distance", result.get("magnification"),
               -(distance or 0) / u, rel=1e-9)
    expected_state = ("正立放大的虚像" if u < f
                      else "倒立放大的实像" if u < 2 * f
                      else "倒立等大的实像" if u == 2 * f else "倒立缩小的实像")
    audit.one_of("state", result.get("state"), {expected_state})
    return audit.result()
