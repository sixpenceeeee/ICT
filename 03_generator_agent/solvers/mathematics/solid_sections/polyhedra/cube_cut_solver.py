# -*- coding: utf-8 -*-
"""Cube adapter for the shared convex-polyhedron plane-section kernel."""
import math
from polyhedron_section_solver import solve_plane_section


CUBE_EDGES = ((0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4),
              (0, 4), (1, 5), (2, 6), (3, 7))
CUBE_FACES = ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (3, 7, 6, 2),
              (0, 4, 7, 3), (1, 2, 6, 5))


def solve_cube_cut(a=2.0, n=(1.0, 1.0, 1.0), offset=0.0, eps=1e-9):
    """Intersect a centered axis-aligned cube of edge length ``a`` by a plane."""
    a = float(a)
    if not math.isfinite(a) or a <= 0:
        raise ValueError("棱长 a 必须为有限正数")
    h = a / 2.0
    vertices = [(-h, -h, -h), (h, -h, -h), (h, h, -h), (-h, h, -h),
                (-h, -h, h), (h, -h, h), (h, h, h), (-h, h, h)]
    result = solve_plane_section(vertices, CUBE_EDGES, CUBE_FACES, n, offset, eps=eps)
    result.update({"a": a, "solid": "cube", "dimensions": [a, a, a], "volume": a ** 3})
    return result
