# -*- coding: utf-8 -*-
import math
import os
import sys
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from cube_cut_solver import solve_cube_cut
from cuboid_cut_solver import solve_cuboid_cut
from triangular_prism_cut_solver import solve_triangular_prism_cut
from square_pyramid_cut_solver import solve_square_pyramid_cut
from polyhedron_volume_oracle import split_polyhedron_volumes


class PolyhedronSectionRegressionTests(unittest.TestCase):
    def assert_close(self, actual, expected, tol=1e-7):
        self.assertLessEqual(abs(actual - expected), tol * max(1.0, abs(expected)))

    def test_cube_known_sections(self):
        cases = [
            (solve_cube_cut(2, (0, 0, 1), 0), 4, 4.0),
            (solve_cube_cut(2, (1, 1, 1), 0), 6, 3 * math.sqrt(3)),
            (solve_cube_cut(2, (0, 0, 1), 1), 4, 4.0),  # coincident with a face
            (solve_cube_cut(2, (1, 1, 0), 0), 4, 4 * math.sqrt(2)),  # plane through edges
        ]
        for result, sides, area in cases:
            with self.subTest(sides=sides, area=area):
                self.assertEqual(result["sides"], sides)
                self.assert_close(result["area"], area)
                self.assertLessEqual(result["plane_residual"], 1e-8)

    def test_tangency_and_empty_sections(self):
        tangent_vertex = solve_cube_cut(2, (1, 1, 1), 3)
        outside = solve_cube_cut(2, (0, 0, 1), 1.01)
        self.assertEqual(tangent_vertex["sides"], 0)
        self.assertEqual(tangent_vertex["area"], 0)
        self.assertEqual(outside["sides"], 0)
        self.assertEqual(outside["vertices"], [])

    def test_plane_scale_and_sign_invariance(self):
        base = solve_cube_cut(2, (1, 2, 3), 0.4)
        scaled = solve_cube_cut(2, (7, 14, 21), 2.8)
        flipped = solve_cube_cut(2, (-1, -2, -3), -0.4)
        for result in (scaled, flipped):
            self.assertEqual(result["sides"], base["sides"])
            self.assert_close(result["area"], base["area"])
            self.assertEqual(len(result["vertices"]), len(base["vertices"]))
            for p in result["vertices"]:
                self.assertLess(min(math.dist(p, q) for q in base["vertices"]), 1e-7)

    def test_other_solid_baselines(self):
        cuboid = solve_cuboid_cut(4, 2, 1, n=(0, 0, 1), offset=0)
        prism = solve_triangular_prism_cut(3, 2, 4, n=(0, 0, 1), offset=0)
        pyramid = solve_square_pyramid_cut(2, 3, n=(0, 0, 1), offset=0)
        self.assertEqual((cuboid["sides"], prism["sides"], pyramid["sides"]), (4, 3, 4))
        self.assert_close(cuboid["area"], 8)
        self.assert_close(prism["area"], 3)
        self.assert_close(pyramid["area"], 1)

    def test_split_volume_oracle_invariants(self):
        cases = [
            solve_cube_cut(2, (1, 1, 1), 0),
            solve_cuboid_cut(4, 2, 1, n=(1, 2, 3), offset=0.1),
            solve_triangular_prism_cut(3, 2, 4, n=(1, 1, 1), offset=0),
            solve_square_pyramid_cut(2, 3, n=(1, 1, 1), offset=0),
            solve_cube_cut(2, (0, 0, 1), 1),
            solve_cube_cut(2, (0, 0, 1), 1.01),
        ]
        for result in cases:
            volumes = split_polyhedron_volumes(result["solid_vertices"], result["faces"],
                                               result["normal"], result["offset"])
            with self.subTest(solid=result["solid"], sides=result["sides"]):
                self.assert_close(volumes["negative"] + volumes["positive"], result["volume"])
                self.assertGreaterEqual(volumes["negative"], 0)
                self.assertGreaterEqual(volumes["positive"], 0)

    def test_bad_dimensions_and_zero_normal_are_rejected(self):
        for call in (lambda: solve_cube_cut(0), lambda: solve_cuboid_cut(1, math.nan, 2),
                     lambda: solve_triangular_prism_cut(1, 2, math.inf),
                     lambda: solve_square_pyramid_cut(2, 0)):
            with self.subTest(call=call), self.assertRaises(ValueError):
                call()
        with self.assertRaises(ValueError):
            solve_cube_cut(2, (0, 0, 0), 0)


if __name__ == "__main__":
    unittest.main()
