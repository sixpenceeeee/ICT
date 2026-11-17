import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import reviewer


class SolverPageMetamorphicReviewTests(unittest.TestCase):
    def test_circuit_page_requires_input_and_result_to_change(self):
        page = {
            "circuit": {"initial": {"model": {"components": []}, "result": {}}},
            "metamorphic": {"samples": [{
                "inputChanged": True,
                "changedInputs": ["__CIRCUIT_MODEL__"],
                "changedResponses": ["__CIRCUIT_RESULT__"],
            }]},
        }
        result = reviewer.verify_solver_page_metamorphic(page)
        self.assertTrue(result["ok"], result["actual"])
        page["metamorphic"]["samples"][0]["changedResponses"] = []
        self.assertFalse(reviewer.verify_solver_page_metamorphic(page)["ok"])

    def test_math_page_requires_real_parameter_mutation(self):
        page = {
            "spatialMetric": {"initial": {"request": {}, "result": {}}},
            "metamorphic": {"samples": [{
                "inputChanged": True,
                "changedInputs": ["__MATH_SPATIAL_REQUEST__"],
                "changedResponses": ["__MATH_SPATIAL_RESULT__"],
            }]},
        }
        self.assertTrue(reviewer.verify_solver_page_metamorphic(page)["ok"])
        page["metamorphic"]["samples"][0]["changedInputs"] = []
        self.assertFalse(reviewer.verify_solver_page_metamorphic(page)["ok"])

    def test_chemistry_page_requires_transformed_requests(self):
        page = {
            "machine": {
                "CHEM_STOICH_REQUEST": {"initial_amounts_mol": [1, 2]},
                "CHEM_STOICH_SAMPLES": [{"request": {"initial_amounts_mol": [1.1, 2]}}],
            },
        }
        self.assertTrue(reviewer.verify_solver_page_metamorphic(page)["ok"])
        page["machine"]["CHEM_STOICH_SAMPLES"] = []
        result = reviewer.verify_solver_page_metamorphic(page)
        self.assertFalse(result["ok"])
        self.assertIn("化学反应计量", result["missing"])

    def test_equation_balance_requires_browser_bundle_transformations(self):
        kinds = ["uniform-formula-scaling", "unicode-subscript-equivalence", "species-reordering"]
        page = {"machine": {
            "CHEM_BALANCE_REQUEST": {"reactants": ["H2"], "products": ["H2"]},
            "CHEM_BALANCE_SAMPLES": [{"kind": kind} for kind in kinds],
        }}
        self.assertTrue(reviewer.verify_solver_page_metamorphic(
            page, "CHEMSOLVER.balanceEquation")["ok"])

    def test_registered_solver_scene_fails_if_page_exposes_no_solver_state(self):
        result = reviewer.verify_solver_page_metamorphic({}, "MATH.solveSphereCut")
        self.assertTrue(result["checked"])
        self.assertFalse(result["ok"])
        self.assertIn("球体截面", result["missing"])

    def test_page_topic_solver_wins_over_legacy_scene_metadata(self):
        api = reviewer.expected_solver_api_for_page(
            "平面截正方体与空间想象", "数学", {}, {"solver_api": "CIRCUIT.solve"})
        self.assertEqual(api, "MATH.solveCubeCut")

    def test_solver_api_can_be_resolved_from_registered_page_scene(self):
        api = reviewer.expected_solver_api_for_page(
            "交互主图", "数学", {"scene_id": "math-cube-cut-3d"})
        self.assertEqual(api, "MATH.solveCubeCut")

    def test_every_math_solver_family_requires_a_changed_page_response(self):
        cases = [
            ("MATH.solveCubeCut", "cubeCut", "__GEO__", "__MATH_CUBE_RESULT__"),
            ("MATH.solveCuboidCut", "cubeCut", "__GEO__", "__MATH_POLYHEDRON_RESULT__"),
            ("MATH.solveTriangularPrismCut", "cubeCut", "__GEO__", "__MATH_POLYHEDRON_RESULT__"),
            ("MATH.solveSquarePyramidCut", "cubeCut", "__GEO__", "__MATH_POLYHEDRON_RESULT__"),
            ("MATH.solveCylinderCut", "cylinderCut", "__GEO__", "__MATH_CYLINDER_RESULT__"),
            ("MATH.solveConeCut", "coneCut", "__GEO__", "__MATH_CONE_RESULT__"),
            ("MATH.solveSphereCut", "sphereCut", "__GEO__", "__MATH_SPHERE_RESULT__"),
            ("MATH.solveSpatialMetrics", "spatialMetric", "__MATH_SPATIAL_REQUEST__", "__MATH_SPATIAL_RESULT__"),
            ("MATH.solveSolidVolume", "solidVolume", "__MATH_VOLUME_REQUEST__", "__MATH_VOLUME_RESULT__"),
            ("MATH.solveCubeNet", "cubeNet", "__MATH_CUBE_NET_REQUEST__", "__MATH_CUBE_NET_RESULT__"),
            ("MATH.solveCuboidNet", "cuboidNet", "__MATH_CUBOID_NET_REQUEST__", "__MATH_CUBOID_NET_RESULT__"),
            ("MATH.solveCylinderNet", "cylinderNet", "__MATH_CYLINDER_NET_REQUEST__", "__MATH_CYLINDER_NET_RESULT__"),
            ("MATH.solveConeNet", "coneNet", "__MATH_CONE_NET_REQUEST__", "__MATH_CONE_NET_RESULT__"),
        ]
        for api, browser_key, changed_input, changed_response in cases:
            with self.subTest(api=api):
                page = {
                    browser_key: {"initial": {"request": {"side": 1}, "result": {"side": 1}}},
                    "metamorphic": {"samples": [{
                        "inputChanged": True,
                        "changedInputs": [changed_input],
                        "changedResponses": [changed_response],
                    }]},
                }
                self.assertTrue(reviewer.verify_solver_page_metamorphic(page, api)["ok"])
                page["metamorphic"]["samples"][0]["changedResponses"] = []
                self.assertFalse(reviewer.verify_solver_page_metamorphic(page, api)["ok"])

    def test_registered_chemistry_reaction_solvers_require_base_and_changed_request(self):
        cases = [
            ("CHEMSOLVER.solveStoichiometry", "CHEM_STOICH_REQUEST", "CHEM_STOICH_SAMPLES"),
            ("CHEMSOLVER.solveSolutionMixing", "CHEM_MIX_REQUEST", "CHEM_MIX_SAMPLES"),
        ]
        for api, request_key, samples_key in cases:
            with self.subTest(api=api):
                page = {"machine": {
                    request_key: {"amount": 1},
                    samples_key: [{"request": {"amount": 2}}],
                }}
                self.assertTrue(reviewer.verify_solver_page_metamorphic(page, api)["ok"])
                page["machine"].pop(request_key)
                result = reviewer.verify_solver_page_metamorphic(page, api)
                self.assertFalse(result["ok"])


if __name__ == "__main__":
    unittest.main()
