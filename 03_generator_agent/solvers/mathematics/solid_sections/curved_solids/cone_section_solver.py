# -*- coding: utf-8 -*-
"""Plane-section solver for a right circular cone with axis along z."""
import math


def solve_cone_cut(radius=1.0, height=2.0, n=(0.0, 0.0, 1.0), offset=0.0,
                   samples=720, eps=1e-9):
    radius, height = float(radius), float(height)
    try:
        normal = tuple(float(v) for v in n)
        offset = float(offset)
    except (TypeError, ValueError) as exc:
        raise ValueError("截平面参数格式无效") from exc
    if not math.isfinite(radius) or radius <= 0 or not math.isfinite(height) or height <= 0:
        raise ValueError("圆锥底面半径和高必须为有限正数")
    if len(normal) != 3 or not all(math.isfinite(v) for v in normal) or not math.isfinite(offset):
        raise ValueError("平面必须由三个有限法向量分量和有限偏移量定义")
    norm = math.hypot(*normal)
    if norm <= eps:
        raise ValueError("平面法向量不能为零")
    normal = tuple(v / norm for v in normal)
    offset /= norm
    nx, ny, nz = normal
    horizontal = math.hypot(nx, ny)
    half = height / 2
    tolerance = eps * max(1.0, radius, height)
    if horizontal <= eps:
        z = offset / nz
        if z < -half-tolerance or z > half+tolerance:
            return _empty(radius, height, normal, offset)
        z = min(half, max(-half, z))
        section_radius = radius * max(0.0, (half-z)/height)
        if section_radius <= tolerance:
            return _result(radius, height, normal, offset, "tangent", 0.0, [], {"z_min": z, "z_max": z})
        boundary = [[section_radius*math.cos(2*math.pi*i/samples),
                     section_radius*math.sin(2*math.pi*i/samples), z] for i in range(samples)]
        return _result(radius, height, normal, offset, "circle", math.pi*section_radius**2,
                       boundary, {"z_min": z, "z_max": z})

    ux, uy = nx/horizontal, ny/horizontal
    vx, vy = -uy, ux
    # At height z, the plane fixes u and the cone leaves a chord in v.
    # Both inequalities r(z)-u(z)>=0 and r(z)+u(z)>=0 are linear in z,
    # so they clip the finite cone's z interval exactly.
    lo, hi = -half, half
    linear_constraints = ((radius/2-offset/horizontal, -radius/height+nz/horizontal),
                          (radius/2+offset/horizontal, -radius/height-nz/horizontal))
    for intercept, slope in linear_constraints:
        if abs(slope) <= eps:
            if intercept < -tolerance:
                return _empty(radius, height, normal, offset)
        elif slope > 0:
            lo = max(lo, -intercept/slope)
        else:
            hi = min(hi, -intercept/slope)
    lo, hi = max(lo, -half), min(hi, half)
    if hi < lo-tolerance:
        return _empty(radius, height, normal, offset)
    lo, hi = min(lo, hi), max(lo, hi)

    def chord(z):
        u = (offset-nz*z)/horizontal
        rz = radius*max(0.0, (half-z)/height)
        return math.sqrt(max(0.0, rz*rz-u*u))

    count = max(32768, int(samples)//2*2)
    dz = (hi-lo)/count
    total = chord(lo)+chord(hi)
    total += 4*sum(chord(lo+i*dz) for i in range(1, count, 2))
    total += 2*sum(chord(lo+i*dz) for i in range(2, count, 2))
    area = (2/horizontal)*total*dz/3
    half_samples = max(32, min(360, count//2))
    upper, lower = [], []
    for i in range(half_samples+1):
        z = lo+(hi-lo)*i/half_samples
        u = (offset-nz*z)/horizontal
        v = chord(z)
        upper.append(_xyz(u, v, z, ux, uy, vx, vy))
        lower.append(_xyz(u, -v, z, ux, uy, vx, vy))
    boundary = upper+list(reversed(lower))
    apex_on_plane = abs(nz*half-offset) <= tolerance
    base_chord = chord(-half)
    shape = "triangle" if apex_on_plane and base_chord > tolerance else (
        "tangent" if area <= tolerance*tolerance else
        "ellipse" if lo > -half+tolerance and hi < half-tolerance else "conic_segment")
    if area <= tolerance*tolerance:
        area, boundary, shape = 0.0, [], "tangent"
    return _result(radius, height, normal, offset, shape, area, boundary, {"z_min": lo, "z_max": hi})


def _xyz(u, v, z, ux, uy, vx, vy):
    return [u*ux+v*vx, u*uy+v*vy, z]


def _result(radius, height, normal, offset, shape, area, boundary, interval):
    return {"solid": "cone", "dimensions": [radius, height], "radius": radius,
            "height": height, "normal": list(normal), "offset": offset, "shape": shape,
            "area": area, "boundary": boundary, "boundary_samples": len(boundary),
            "z_interval": interval, "volume": math.pi*radius*radius*height/3}


def _empty(radius, height, normal, offset):
    return _result(radius, height, normal, offset, "empty", 0.0, [], {"z_min": None, "z_max": None})
