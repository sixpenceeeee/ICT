import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from solvers.rule_state import solve_cell_division, solve_display_scene, solve_optics  # noqa: E402
from solvers.law_layers import contract_for, solve_law, LAW_CONTRACTS, LAW, NUMERIC, RULE  # noqa: E402
import scene_registry  # noqa: E402


class RuleStateSolverTests(unittest.TestCase):
    def test_phase_order_and_required_objects(self):
        results = [solve_cell_division(i, 50) for i in range(5)]
        self.assertEqual([r["phase"] for r in results], list(range(5)))
        self.assertTrue(all(r["checks"]["ok"] for r in results))
        self.assertEqual(results[2]["state"], "中期")
        self.assertIn("赤道板", results[2]["visible_objects"])

    def test_metamorphic_emphasis_does_not_change_phase(self):
        low = solve_cell_division(3, 20)
        high = solve_cell_division(3, 80)
        self.assertEqual(low["state"], high["state"])
        self.assertEqual(low["chromosome_state"], high["chromosome_state"])
        self.assertLess(low["signal"], high["signal"])

    def test_all_display_scene_rule_packs(self):
        display_scenes = [s for s in scene_registry.SCENE_SKELETONS if not s.get("solver_api")]
        self.assertGreaterEqual(len(display_scenes), 60)
        for scene in display_scenes:
            result = solve_display_scene(scene, phase=2, emphasis=60)
            self.assertTrue(result["checks"]["ok"], scene["id"])
            self.assertEqual(result["phase"], 2)
            self.assertNotEqual(result["rule_id"], "display_generic", scene["id"])
            self.assertTrue(result["checks"]["semantic_invariants_valid"], scene["id"])
            self.assertTrue(result.get("semantic") or result.get("evidence"), scene["id"])
            self.assertTrue(result["visible_objects"], scene["id"])

    def test_optics_law_and_total_internal_reflection(self):
        normal = solve_optics(30, 1.0, 1.5)
        self.assertTrue(normal["checks"]["ok"])
        self.assertAlmostEqual(normal["reflection_angle_deg"], 30.0)
        self.assertAlmostEqual(normal["snell_residual"], 0.0, places=10)
        tir = solve_optics(60, 1.5, 1.0)
        self.assertTrue(tir["total_internal_reflection"])
        self.assertIsNone(tir["refraction_angle_deg"])
        self.assertTrue(tir["checks"]["tir_condition"])

    def test_all_registered_scenes_have_solver_layer_contract(self):
        for scene in scene_registry.SCENE_SKELETONS:
            contract = contract_for(scene["id"], scene.get("solver_api"), scene.get("mode"))
            self.assertIn(contract.layer, {LAW, NUMERIC, RULE}, scene["id"])
            self.assertTrue(contract.contract_id, scene["id"])

    def test_all_law_oracles_return_verified_evidence(self):
        cases = {
            "physics-optics-bench": {"incident_angle_deg": 30, "n1": 1, "n2": 1.5},
            "biology-ecosystem-energy": {},
            "geography-solar-altitude": {},
            "informatics-binary-search": {},
            "chemistry-molecular-model": {},
            "math-spatial-geometry": {},
        }
        for scene_id, inputs in cases.items():
            result = solve_law(scene_id, **inputs).as_dict()
            self.assertEqual(result["layer"], LAW, scene_id)
            self.assertTrue(result["checks"]["ok"], scene_id)
            self.assertTrue(result["evidence"]["contract_id"], scene_id)

    def test_reference_law_profiles_have_recomputable_defaults(self):
        profiles = [c for c in LAW_CONTRACTS.values() if c.oracle == "solve_reference"]
        self.assertGreaterEqual(len(profiles), 10)
        for contract in profiles:
            result = solve_law(contract.scene_id).as_dict()
            self.assertTrue(result["checks"]["ok"], contract.scene_id)
            self.assertTrue(result["checks"]["reference_recomputed"], contract.scene_id)


if __name__ == "__main__":
    unittest.main()
