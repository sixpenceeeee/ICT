# -*- coding: utf-8 -*-
"""Coordinate/vector solver for common 3D distances and acute angles.

Lines use point + direction; planes use n·x=offset. All angles returned are
the conventional smaller (0..90 degree) angles used for line/plane pairs.
"""
import math


def _vec(value, name):
    try:
        v = tuple(float(x) for x in value)
    except (TypeError, ValueError) as exc:
        raise ValueError(name + "必须是三个有限数") from exc
    if len(v) != 3 or not all(math.isfinite(x) for x in v):
        raise ValueError(name + "必须是三个有限数")
    return v


def _norm(v):
    return math.sqrt(sum(x*x for x in v))


def _unit(v, name):
    size = _norm(v)
    if size <= 1e-12:
        raise ValueError(name + "不能为零向量")
    return tuple(x/size for x in v)


def _dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def _sub(a, b):
    return tuple(x-y for x, y in zip(a, b))


def _cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def _angle_degrees(cosine):
    return math.degrees(math.acos(max(-1.0, min(1.0, abs(cosine)))))


def _scalar(value, name):
    try:
        value = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(name + "必须是有限数") from exc
    if not math.isfinite(value):
        raise ValueError(name + "必须是有限数")
    return value


def solve_spatial_metrics(request):
    """Solve one named metric request; see README for request schemas."""
    if not isinstance(request, dict):
        raise ValueError("请求必须是对象")
    op = str(request.get("operation", ""))
    if op == "point_point_distance":
        p, q = _vec(request.get("p"), "点 p"), _vec(request.get("q"), "点 q")
        value = _norm(_sub(p, q))
    elif op == "point_line_distance":
        p = _vec(request.get("point"), "点")
        a = _vec(request.get("line_point"), "直线上一点")
        u = _unit(_vec(request.get("line_direction"), "直线方向向量"), "直线方向向量")
        delta = _sub(p, a)
        value = _norm(_cross(delta, u))
    elif op == "point_plane_distance":
        p = _vec(request.get("point"), "点")
        n = _unit(_vec(request.get("plane_normal"), "平面法向量"), "平面法向量")
        d = _scalar(request.get("plane_offset"), "平面偏移量")
        value = abs(_dot(n, p)-d/_norm(_vec(request.get("plane_normal"), "平面法向量")))
    elif op in ("line_line_distance", "line_line_angle"):
        p1, p2 = _vec(request.get("line1_point"), "直线1上的点"), _vec(request.get("line2_point"), "直线2上的点")
        u = _unit(_vec(request.get("line1_direction"), "直线1方向向量"), "直线1方向向量")
        v = _unit(_vec(request.get("line2_direction"), "直线2方向向量"), "直线2方向向量")
        cross = _cross(u, v)
        cn = _norm(cross)
        if op == "line_line_angle":
            value = _angle_degrees(_dot(u, v))
        elif cn <= 1e-12:
            value = _norm(_cross(_sub(p2, p1), u))
        else:
            value = abs(_dot(_sub(p2, p1), cross))/cn
    elif op in ("line_plane_distance", "line_plane_angle"):
        p = _vec(request.get("line_point"), "直线上一点")
        u = _unit(_vec(request.get("line_direction"), "直线方向向量"), "直线方向向量")
        raw_n = _vec(request.get("plane_normal"), "平面法向量")
        nn = _norm(raw_n)
        n = _unit(raw_n, "平面法向量")
        d = _scalar(request.get("plane_offset"), "平面偏移量")
        if op == "line_plane_distance":
            value = 0.0 if abs(_dot(n, u)) > 1e-12 else abs(_dot(n, p)-d/nn)
        else:
            value = math.degrees(math.asin(max(-1.0, min(1.0, abs(_dot(n, u))))))
    elif op in ("plane_plane_distance", "plane_plane_angle"):
        raw_a = _vec(request.get("plane1_normal"), "平面1法向量")
        raw_b = _vec(request.get("plane2_normal"), "平面2法向量")
        na, nb = _unit(raw_a, "平面1法向量"), _unit(raw_b, "平面2法向量")
        da = _scalar(request.get("plane1_offset"), "平面1偏移量")
        db = _scalar(request.get("plane2_offset"), "平面2偏移量")
        if op == "plane_plane_angle":
            value = _angle_degrees(_dot(na, nb))
        elif _norm(_cross(na, nb)) > 1e-12:
            value = 0.0
        else:
            orientation = 1.0 if _dot(na, nb) >= 0 else -1.0
            value = abs(da/_norm(raw_a)-orientation*db/_norm(raw_b))
    else:
        raise ValueError("不支持的运算类型：%s" % op)
    return {"operation": op, "value": value,
            "unit": "degree" if op.endswith("angle") else "length",
            "checks": {"finite": math.isfinite(value), "non_negative": value >= -1e-12,
                       "angle_in_range": not op.endswith("angle") or 0 <= value <= 90}}
