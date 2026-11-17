# -*- coding: utf-8 -*-
"""Triangular-prism adapter for the convex polyhedron section kernel."""
import math
from polyhedron_section_solver import solve_plane_section


PRISM_EDGES = ((0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3), (0, 3), (1, 4), (2, 5))
PRISM_FACES = ((0, 2, 1), (3, 4, 5), (0, 1, 4, 3), (1, 2, 5, 4), (2, 0, 3, 5))


def solve_triangular_prism_cut(base=3.0, triangle_height=2.0, length=4.0,
                               n=(1.0, 1.0, 1.0), offset=0.0, eps=1e-9):
    """Cut a right triangular prism with an isosceles triangular end face.

    Coordinates are centered at the solid's centroid. The end triangle has
    base ``base`` and altitude ``triangle_height``; the prism
    extends ``length`` along z. Arbitrary triangular ends are not yet supported.
    """
    base, triangle_height, length = map(float, (base, triangle_height, length))
    if any(not math.isfinite(v) or v <= 0 for v in (base, triangle_height, length)):
        raise ValueError("三棱柱底边、底面高和棱柱长必须为有限正数")
    x, y, z = base / 2.0, triangle_height / 3.0, length / 2.0
    vertices = [(-x, -y, -z), (x, -y, -z), (0.0, 2 * y, -z),
                (-x, -y, z), (x, -y, z), (0.0, 2 * y, z)]
    result = solve_plane_section(vertices, PRISM_EDGES, PRISM_FACES, n, offset, eps=eps)
    result.update({"solid": "triangular_prism", "dimensions": [base, triangle_height, length],
                   "size_label": "底边 %.3g × 底面高 %.3g × 棱柱长 %.3g" %
                                 (base, triangle_height, length),
                   "volume": base * triangle_height * length / 2.0,
                   "vertex_labels": ["A", "B", "C", "A1", "B1", "C1"], "base_face": 0})
    return result
