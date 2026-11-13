# -*- coding: utf-8 -*-
"""Axis-aligned rectangular-prism adapter for the convex section kernel."""
import math
from polyhedron_section_solver import solve_plane_section


CUBOID_EDGES = ((0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4),
                (0, 4), (1, 5), (2, 6), (3, 7))
CUBOID_FACES = ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (3, 7, 6, 2),
                (0, 4, 7, 3), (1, 2, 6, 5))


def solve_cuboid_cut(length=3.0, width=2.0, height=1.0, n=(1.0, 1.0, 1.0), offset=0.0, eps=1e-9):
    """Intersect a centered axis-aligned cuboid by n·x=offset."""
    dims = tuple(float(v) for v in (length, width, height))
    if any(not math.isfinite(v) or v <= 0 for v in dims):
        raise ValueError("长方体长、宽、高必须为有限正数")
    hx, hy, hz = (v / 2.0 for v in dims)
    vertices = [(-hx, -hy, -hz), (hx, -hy, -hz), (hx, hy, -hz), (-hx, hy, -hz),
                (-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz)]
    result = solve_plane_section(vertices, CUBOID_EDGES, CUBOID_FACES, n, offset, eps=eps)
    result.update({"solid": "cuboid", "dimensions": list(dims), "volume": dims[0] * dims[1] * dims[2]})
    return result
