"""Metamorphic relations for solver families that need cross-cutting coverage.

Domain-specific tests still live beside their solvers. This file is the
coverage backstop for the currently registered math/physics/chemistry APIs.
"""
import copy
import math
import os
import sys
import unittest

SOLVER_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, SOLVER_ROOT)
for current, _, files in os.walk(SOLVER_ROOT):
    if any(name.endswith(".py") and name != "__init__.py" for name in files):
        sys.path.insert(0, current)

from physics.electric_circuits.circuit_solver import solve_circuit
from mathematics.spatial_geometry.distance_angles.spatial_metrics_solver import solve_spatial_metrics
from mathematics.solid_sections.polyhedra.cube_cut_solver import solve_cube_cut
from mathematics.solid_sections.polyhedra.cuboid_cut_solver import solve_cuboid_cut
from mathematics.solid_sections.polyhedra.triangular_prism_cut_solver import solve_triangular_prism_cut
from mathematics.solid_sections.polyhedra.square_pyramid_cut_solver import solve_square_pyramid_cut
from mathematics.solid_sections.curved_solids.cylinder_section_solver import solve_cylinder_cut
from mathematics.solid_sections.curved_solids.cone_section_solver import solve_cone_cut
from mathematics.solid_sections.curved_solids.sphere_section_solver import solve_sphere_cut
from mathematics.solid_geometry.volume.solid_volume_solver import (
    solve_solid_volume, solve_composite_volume, check_volume_partition,
)
from chemistry.reactions.stoichiometry_solver import solve_stoichiometry
from chemistry.reactions.solution_mixing_solver import solve_solution_mixing


class PolyhedronSectionMetamorphicTests(unittest.TestCase):
    def assert_same_section(self, solve, args):
        base = solve(*args)
        scaled = list(args)
        scaled[-2] = tuple(7 * x for x in args[-2])
        scaled[-1] = 7 * args[-1]
        multiplied = solve(*scaled)
        reversed_plane = list(args)
        reversed_plane[-2] = tuple(-x for x in args[-2])
        reversed_plane[-1] = -args[-1]
        flipped = solve(*reversed_plane)
        for result in (multiplied, flipped):
            self.assertEqual(result["sides"], base["sides"])
            self.assertEqual(result["shape"], base["shape"])
            self.assertAlmostEqual(result["area"], base["area"], places=8)
            self.assertEqual(len(result["vertices"]), len(base["vertices"]))
            for point in result["vertices"]:
                self.assertLess(min(math.dist(point, candidate) for candidate in base["vertices"]), 1e-7)

    def test_plane_equation_scale_and_sign_for_every_polyhedron_adapter(self):
        self.assert_same_section(solve_cube_cut, (2, (1, 2, 3), 0.4))
        self.assert_same_section(solve_cuboid_cut, (4, 2, 1, (1, 2, 3), 0.1))
        self.assert_same_section(solve_triangular_prism_cut, (3, 2, 4, (1, 1, 2), 0.15))
        self.assert_same_section(solve_square_pyramid_cut, (2, 3, (1, 1, 2), 0.1))


class CurvedSectionMetamorphicTests(unittest.TestCase):
    def test_plane_normal_scaling_and_reversal_preserve_curved_sections(self):
        cases = (
            (solve_cylinder_cut, (1.5, 3.0, (1, 2, 3), 0.2)),
            (solve_cone_cut, (1.5, 3.0, (1, 2, 3), 0.2)),
            (solve_sphere_cut, (2.5, (1, 2, 3), 0.2)),
        )
        for solve, args in cases:
            with self.subTest(solver=solve.__name__):
                base = solve(*args)
                for factor in (5, -3):
                    transformed = list(args)
                    normal_index = 2 if solve is not solve_sphere_cut else 1
                    offset_index = normal_index + 1
                    transformed[normal_index] = tuple(factor * x for x in args[normal_index])
                    transformed[offset_index] = factor * args[offset_index]
                    actual = solve(*transformed)
                    self.assertEqual(actual["shape"], base["shape"])
                    self.assertAlmostEqual(actual["area"], base["area"], places=8)
                    if base.get("section_radius") is not None:
                        self.assertAlmostEqual(actual["section_radius"], base["section_radius"], places=8)


class SolidVolumeMetamorphicTests(unittest.TestCase):
    def test_uniform_length_scaling_cubes_volume_for_every_supported_solid(self):
        requests = [
            {"solid": "cube", "edge": 2},
            {"solid": "cuboid", "length": 2, "width": 3, "height": 4},
            {"solid": "triangular_prism", "base": 3, "triangle_height": 2, "length": 4},
            {"solid": "square_pyramid", "base": 2, "height": 3},
            {"solid": "cylinder", "radius": 2, "height": 3},
            {"solid": "cone", "radius": 2, "height": 3},
            {"solid": "sphere", "radius": 3},
        ]
        factor = 2.5
        for request in requests:
            with self.subTest(solid=request["solid"]):
                transformed = {key: (value * factor if key != "solid" else value)
                               for key, value in request.items()}
                before = solve_solid_volume(request)["volume"]
                after = solve_solid_volume(transformed)["volume"]
                self.assertAlmostEqual(after, before * factor ** 3, places=7)

    def test_composite_sum_and_partition_check_are_homogeneous(self):
        parts = [{"solid": "cube", "edge": 1}, {"solid": "sphere", "radius": 1}]
        original = solve_composite_volume(parts)
        factor = 3
        scaled_parts = [{key: (value * factor if key != "solid" else value)
                         for key, value in part.items()} for part in parts]
        scaled = solve_composite_volume(scaled_parts)
        self.assertAlmostEqual(scaled["volume"], original["volume"] * factor ** 3, places=8)
        base_check = check_volume_partition(10, [4, 6])
        scaled_check = check_volume_partition(10 * factor ** 3, [4 * factor ** 3, 6 * factor ** 3])
        self.assertTrue(base_check["ok"])
        self.assertTrue(scaled_check["ok"])
        self.assertAlmostEqual(scaled_check["relative_error"], base_check["relative_error"], places=12)


class SpatialMetricsMetamorphicTests(unittest.TestCase):
    DISTANCE_CASES = [
        {"operation": "point_point_distance", "p": [1, 2, 3], "q": [4, 6, 8]},
        {"operation": "point_line_distance", "point": [1, 2, 3], "line_point": [0, 0, 0], "line_direction": [1, 2, 0]},
        {"operation": "point_plane_distance", "point": [1, 2, 3], "plane_normal": [1, 2, 3], "plane_offset": 2},
        {"operation": "line_line_distance", "line1_point": [0, 0, 0], "line1_direction": [1, 0, 0],
         "line2_point": [0, 2, 1], "line2_direction": [0, 0, 1]},
        {"operation": "line_plane_distance", "line_point": [0, 0, 4], "line_direction": [1, 0, 0],
         "plane_normal": [0, 0, 1], "plane_offset": 1},
        {"operation": "plane_plane_distance", "plane1_normal": [0, 0, 1], "plane1_offset": 2,
         "plane2_normal": [0, 0, -3], "plane2_offset": -12},
    ]

    ANGLE_CASES = [
        {"operation": "line_line_angle", "line1_point": [1, 2, 3], "line1_direction": [1, 2, 0],
         "line2_point": [-1, 0, 4], "line2_direction": [1, -1, 2]},
        {"operation": "line_plane_angle", "line_point": [1, 2, 3], "line_direction": [1, 2, 3],
         "plane_normal": [1, 0, 0], "plane_offset": 0},
        {"operation": "plane_plane_angle", "plane1_normal": [1, 2, 3], "plane1_offset": 4,
         "plane2_normal": [2, -1, 1], "plane2_offset": -2},
    ]

    def test_coordinate_homothety_scales_distances_and_preserves_angles(self):
        for request in self.DISTANCE_CASES:
            transformed = copy.deepcopy(request)
            for key, value in list(transformed.items()):
                if isinstance(value, list) and key not in ("plane_normal", "plane1_normal", "plane2_normal"):
                    transformed[key] = [2.75 * item for item in value]
                elif key.endswith("offset"):
                    transformed[key] = 2.75 * value
            with self.subTest(operation=request["operation"]):
                before = solve_spatial_metrics(request)["value"]
                after = solve_spatial_metrics(transformed)["value"]
                self.assertAlmostEqual(after, 2.75 * before, places=8)

        for request in self.ANGLE_CASES:
            transformed = copy.deepcopy(request)
            for key, value in list(transformed.items()):
                if isinstance(value, list):
                    transformed[key] = [2.75 * item for item in value]
                elif key.endswith("offset"):
                    transformed[key] = 2.75 * value
            with self.subTest(operation=request["operation"]):
                self.assertAlmostEqual(solve_spatial_metrics(transformed)["value"],
                                       solve_spatial_metrics(request)["value"], places=8)

    def test_direction_vector_and_plane_equation_rescaling_preserves_metrics(self):
        for request in self.DISTANCE_CASES + self.ANGLE_CASES:
            transformed = copy.deepcopy(request)
            for key in ("line_direction", "line1_direction", "line2_direction"):
                if key in transformed:
                    transformed[key] = [-4 * item for item in transformed[key]]
            for key, offset_key in (("plane_normal", "plane_offset"),
                                    ("plane1_normal", "plane1_offset"),
                                    ("plane2_normal", "plane2_offset")):
                if key in transformed:
                    transformed[key] = [6 * item for item in transformed[key]]
                    transformed[offset_key] *= 6
            with self.subTest(operation=request["operation"]):
                self.assertAlmostEqual(solve_spatial_metrics(transformed)["value"],
                                       solve_spatial_metrics(request)["value"], places=8)


class CircuitSolverMetamorphicTests(unittest.TestCase):
    @staticmethod
    def model(volts=12.0, resistance=6.0):
        return {"ground": "0", "components": [
            {"id": "V1", "type": "voltage_source", "positive": "n1", "negative": "0", "volts": volts},
            {"id": "R1", "type": "resistor", "from": "n1", "to": "0", "ohms": resistance},
        ]}

    def test_source_voltage_scaling_scales_voltage_and_current_linearly(self):
        base = solve_circuit(self.model(volts=12, resistance=6))
        doubled = solve_circuit(self.model(volts=24, resistance=6))
        self.assertAlmostEqual(doubled["nodes"]["n1"], 2 * base["nodes"]["n1"], places=9)
        self.assertAlmostEqual(doubled["branches"]["R1"]["voltage"], 2 * base["branches"]["R1"]["voltage"], places=9)
        self.assertAlmostEqual(doubled["branches"]["R1"]["current"], 2 * base["branches"]["R1"]["current"], places=9)
        self.assertAlmostEqual(doubled["branches"]["R1"]["power"], 4 * base["branches"]["R1"]["power"], places=9)
        self.assertTrue(base["checks"]["ok"] and doubled["checks"]["ok"])

    def test_resistance_scaling_preserves_voltage_and_inverts_current(self):
        base = solve_circuit(self.model(volts=12, resistance=6))
        quadrupled = solve_circuit(self.model(volts=12, resistance=24))
        self.assertAlmostEqual(quadrupled["branches"]["R1"]["voltage"], base["branches"]["R1"]["voltage"], places=9)
        self.assertAlmostEqual(quadrupled["branches"]["R1"]["current"], base["branches"]["R1"]["current"] / 4, places=9)
        self.assertAlmostEqual(quadrupled["branches"]["R1"]["power"], base["branches"]["R1"]["power"] / 4, places=9)
        self.assertTrue(quadrupled["checks"]["ok"])


class ChemistryReactionMetamorphicTests(unittest.TestCase):
    def test_stoichiometry_extent_is_linear_in_reaction_progress(self):
        template = {"reactants": ["Fe", "CuSO4"], "products": ["FeSO4", "Cu"],
                    "initial_amounts_mol": [0.3, 0.18]}
        low = solve_stoichiometry({**template, "progress": 0.2})
        high = solve_stoichiometry({**template, "progress": 0.8})
        self.assertAlmostEqual(high["extent_mol"], 4 * low["extent_mol"], places=10)
        for before, after in zip(low["products"], high["products"]):
            self.assertAlmostEqual(after["produced_mol"], 4 * before["produced_mol"], places=10)

    def test_solution_mixing_equivalent_concentrations_and_volume_scaling(self):
        request = {"reactants": ["BaCl2", "Na2SO4"], "products": ["BaSO4", "NaCl"],
                   "solutions": [{"concentration_mol_L": 0.2, "volume": 50, "volume_unit": "mL"},
                                 {"concentration_mol_L": 0.15, "volume": 100, "volume_unit": "mL"}],
                   "progress": 0.4}
        base = solve_solution_mixing(request)
        equivalent = copy.deepcopy(request)
        equivalent["solutions"][0] = {"concentration_mol_L": 0.2, "volume": 0.05, "volume_unit": "L"}
        equivalent["solutions"][1] = {"concentration_mol_L": 0.15, "volume": 0.1, "volume_unit": "L"}
        same = solve_solution_mixing(equivalent)
        self.assertEqual(base["initial_amounts_mol"], same["initial_amounts_mol"])
        self.assertEqual(base["products"], same["products"])

        scaled = copy.deepcopy(request)
        for solution in scaled["solutions"]:
            solution["volume"] *= 2
        larger = solve_solution_mixing(scaled)
        self.assertEqual(base["limiting_reactants"], larger["limiting_reactants"])
        self.assertAlmostEqual(larger["extent_mol"], 2 * base["extent_mol"], places=10)
        for before, after in zip(base["products"], larger["products"]):
            self.assertAlmostEqual(after["produced_mol"], 2 * before["produced_mol"], places=10)


if __name__ == "__main__":
    unittest.main()
