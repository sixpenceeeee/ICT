# -*- coding: utf-8 -*-
"""Regular square-pyramid adapter for the convex polyhedron section kernel."""
import math
from polyhedron_section_solver import solve_plane_section


PYRAMID_EDGES = ((0, 1), (1, 2), (2, 3), (3, 0), (0, 4), (1, 4), (2, 4), (3, 4))
PYRAMID_FACES = ((0, 3, 2, 1), (0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4))


def solve_square_pyramid_cut(base=2.0, height=3.0, n=(1.0, 1.0, 1.0), offset=0.0, eps=1e-9):
    """Cut a regular square pyramid centered on the z axis by n·x=offset."""
    base, height = float(base), float(height)
    if not (math.isfinite(base) and math.isfinite(height) and base > 0 and height > 0):
        raise ValueError("正四棱锥底面边长和高必须为有限正数")
    x, z = base / 2.0, height / 2.0
    vertices = [(-x, -x, -z), (x, -x, -z), (x, x, -z), (-x, x, -z), (0.0, 0.0, z)]
    result = solve_plane_section(vertices, PYRAMID_EDGES, PYRAMID_FACES, n, offset, eps=eps)
    result.update({"solid": "square_pyramid", "dimensions": [base, height],
                   "size_label": "底面边长 %.3g × 高 %.3g" % (base, height),
                   "volume": base * base * height / 3.0,
                   "vertex_labels": ["A", "B", "C", "D", "S"], "base_face": 0})
    return result
