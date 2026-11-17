# -*- coding: utf-8 -*-
"""Analytic/numerical section solver for a right circular cylinder.

Cylinder axis is z, centered at the origin. The plane is n·x=offset.
For oblique/vertical planes, area is integrated over z with adaptive-free
composite Simpson quadrature; the boundary is returned as a sampled 3D loop.
"""
import math


def solve_cylinder_cut(radius=1.0, height=2.0, n=(0.0, 0.0, 1.0), offset=0.0,
                       samples=720, eps=1e-9):
    radius, height = float(radius), float(height)
    try:
        normal = tuple(float(v) for v in n)
        offset = float(offset)
    except (TypeError, ValueError) as exc:
        raise ValueError("截平面参数格式无效") from exc
    if not math.isfinite(radius) or radius <= 0 or not math.isfinite(height) or height <= 0:
        raise ValueError("圆柱半径和高必须为有限正数")
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
    boundary = []

    if horizontal <= eps:
        z = offset / nz
        if abs(z) > half + tolerance:
            return _empty(radius, height, normal, offset)
        z = min(half, max(-half, z))
        boundary = [[radius * math.cos(2*math.pi*i/samples),
                     radius * math.sin(2*math.pi*i/samples), z] for i in range(samples)]
        return _result(radius, height, normal, offset, "circle", math.pi*radius**2, boundary,
                       {"z_min": z, "z_max": z})

    # u points along the horizontal projection of n; v is the perpendicular
    # horizontal direction. At each z, the plane fixes u and the cylinder
    # leaves a chord of length 2*sqrt(r²-u²) in v.
    ux, uy = nx / horizontal, ny / horizontal
    vx, vy = -uy, ux
    zlo, zhi = -half, half
    if abs(nz) <= eps:
        u = offset / horizontal
        if abs(u) > radius + tolerance:
            return _empty(radius, height, normal, offset)
        u = min(radius, max(-radius, u))
        vlim = math.sqrt(max(0.0, radius*radius-u*u))
        boundary = [_xyz(u, -vlim, zlo, ux, uy, vx, vy),
                    _xyz(u, vlim, zlo, ux, uy, vx, vy),
                    _xyz(u, vlim, zhi, ux, uy, vx, vy),
                    _xyz(u, -vlim, zhi, ux, uy, vx, vy)]
        typ = "rectangle" if vlim > tolerance else "tangent"
        area = 2*vlim*height
        return _result(radius, height, normal, offset, typ, area, boundary,
                       {"z_min": zlo, "z_max": zhi})

    # u(z) = (d - nz*z)/|n_xy|; clip z to the cylinder's finite height and
    # to the range where the horizontal chord exists.
    z_at_minus_r = (offset + horizontal*radius) / nz
    z_at_plus_r = (offset - horizontal*radius) / nz
    zlo = max(zlo, min(z_at_minus_r, z_at_plus_r))
    zhi = min(zhi, max(z_at_minus_r, z_at_plus_r))
    if zhi < zlo - tolerance:
        return _empty(radius, height, normal, offset)
    zlo, zhi = max(-half, zlo), min(half, zhi)

    def chord(z):
        u = (offset - nz*z) / horizontal
        return math.sqrt(max(0.0, radius*radius-u*u))

    # Simpson integration of the section in plane coordinates (z,v).
    count = max(32768, int(samples) // 2 * 2)
    dz = (zhi-zlo)/count
    total = chord(zlo) + chord(zhi)
    total += 4*sum(chord(zlo+i*dz) for i in range(1, count, 2))
    total += 2*sum(chord(zlo+i*dz) for i in range(2, count, 2))
    area = (2 / horizontal) * total * dz / 3

    # Polygonal boundary approximation for rendering; area remains the
    # numerical integral above, not the polygon's shoelace approximation.
    half_samples = max(32, min(360, count // 2))
    upper = []
    lower = []
    for i in range(half_samples + 1):
        z = zlo + (zhi-zlo)*i/half_samples
        v = chord(z)
        u = (offset - nz*z) / horizontal
        upper.append(_xyz(u, v, z, ux, uy, vx, vy))
        lower.append(_xyz(u, -v, z, ux, uy, vx, vy))
    boundary = upper + list(reversed(lower))
    shape = "ellipse" if zlo > -half+tolerance and zhi < half-tolerance else "elliptical_segment"
    return _result(radius, height, normal, offset, shape, area, boundary,
                   {"z_min": zlo, "z_max": zhi})


def _xyz(u, v, z, ux, uy, vx, vy):
    return [u*ux+v*vx, u*uy+v*vy, z]


def _result(radius, height, normal, offset, shape, area, boundary, interval):
    return {"solid": "cylinder", "dimensions": [radius, height], "radius": radius,
            "height": height, "normal": list(normal), "offset": offset,
            "shape": shape, "area": area, "boundary": boundary,
            "boundary_samples": len(boundary), "z_interval": interval,
            "volume": math.pi*radius*radius*height}


def _empty(radius, height, normal, offset):
    return _result(radius, height, normal, offset, "empty", 0.0, [], {"z_min": None, "z_max": None})
