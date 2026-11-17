# -*- coding: utf-8 -*-
"""Exact plane-section solver for a sphere centered at the origin."""
import math


def solve_sphere_cut(radius=1.0, n=(0.0, 0.0, 1.0), offset=0.0, samples=720, eps=1e-9):
    radius = float(radius)
    try:
        normal = tuple(float(v) for v in n)
        offset = float(offset)
    except (TypeError, ValueError) as exc:
        raise ValueError("截平面参数格式无效") from exc
    if not math.isfinite(radius) or radius <= 0:
        raise ValueError("球半径必须为有限正数")
    if len(normal) != 3 or not all(math.isfinite(v) for v in normal) or not math.isfinite(offset):
        raise ValueError("平面必须由三个有限法向量分量和有限偏移量定义")
    magnitude = math.hypot(*normal)
    if magnitude <= eps:
        raise ValueError("平面法向量不能为零")
    normal = tuple(v/magnitude for v in normal)
    offset /= magnitude
    tolerance = eps * max(1.0, radius)
    if abs(offset) > radius+tolerance:
        shape, area, boundary, center, section_radius = "empty", 0.0, [], None, 0.0
    else:
        offset = max(-radius, min(radius, offset))
        center = [offset*v for v in normal]
        section_radius = math.sqrt(max(0.0, radius*radius-offset*offset))
        if section_radius <= tolerance:
            shape, area, boundary, section_radius = "tangent", 0.0, [], 0.0
        else:
            ref = (1.0, 0.0, 0.0) if abs(normal[0]) < .9 else (0.0, 1.0, 0.0)
            u = (normal[1]*ref[2]-normal[2]*ref[1], normal[2]*ref[0]-normal[0]*ref[2],
                 normal[0]*ref[1]-normal[1]*ref[0])
            ul = math.sqrt(sum(v*v for v in u))
            u = tuple(v/ul for v in u)
            v = (normal[1]*u[2]-normal[2]*u[1], normal[2]*u[0]-normal[0]*u[2],
                 normal[0]*u[1]-normal[1]*u[0])
            boundary = [[center[k]+section_radius*(u[k]*math.cos(2*math.pi*i/samples)
                                                   +v[k]*math.sin(2*math.pi*i/samples))
                         for k in range(3)] for i in range(samples)]
            shape, area = "circle", math.pi*section_radius**2
    return {"solid": "sphere", "radius": radius, "dimensions": [radius],
            "normal": list(normal), "offset": offset, "shape": shape,
            "center": center, "section_radius": section_radius, "area": area,
            "boundary": boundary, "boundary_samples": len(boundary),
            "volume": 4*math.pi*radius**3/3}
