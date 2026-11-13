import copy
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "../../../../../"))
sys.path.insert(0, PROJECT)
sys.path.insert(0, os.path.join(PROJECT, "03_generator_agent"))
sys.path.insert(0, os.path.join(PROJECT, "03_generator_agent", "solvers"))
sys.path.insert(0, os.path.join(PROJECT, "04_review_agent"))

import generator_agent
import judges
import scene_registry
import shell
from chemistry.reactions.solution_mixing_solver import solve_solution_mixing


class SolutionMixingPipelineIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.request = {
            "reactants": ["BaCl2", "Na2SO4"], "products": ["BaSO4", "NaCl"],
            "solutions": [
                {"concentration_mol_L": 0.2, "volume": 50, "volume_unit": "mL"},
                {"concentration_mol_L": 0.15, "volume": 100, "volume_unit": "mL"},
            ],
            "progress": 0.5,
        }
        self.result = solve_solution_mixing(self.request)
        self.sample_request = copy.deepcopy(self.request)
        self.sample_request["solutions"][0].update({"volume": 0.05, "volume_unit": "L"})
        self.sample_result = solve_solution_mixing(self.sample_request)
        self.sample = {
            "kind": "equivalent-volume-unit",
            "request": self.sample_request,
            "result": self.sample_result,
            "controls": {
                "concentration_indices": [0, 1], "concentrations_mol_L": [0.2, 0.15],
                "volume_indices": [0, 1], "volumes": [0.05, 100],
                "unit_indices": [0, 1], "volume_units": ["L", "mL"], "progress": 0.5,
            },
            "displayed_equation": self.sample_result["equation"],
        }
        self.sample_oracles = [{"sample": self.sample, "oracle": {"result": self.sample_result}}]

    def _context(self, request=None, result=None, controls=None, displayed=None, samples=None):
        request = request or self.request
        result = result or solve_solution_mixing(request)
        if controls is None:
            controls = {
                "concentration_indices": [0, 1], "concentrations_mol_L": [0.2, 0.15],
                "volume_indices": [0, 1], "volumes": [50, 100],
                "unit_indices": [0, 1], "volume_units": ["mL", "mL"], "progress": 0.5,
            }
        return {
            "machine": {
                "CHEM_MIX_REQUEST": request, "CHEM_MIX_RESULT": result,
                "CHEM_MIX_CONTROLS": controls,
                "CHEM_MIX_DISPLAYED_EQUATION": displayed if displayed is not None else result["equation"],
            },
            "text": "溶液混合与限量试剂", "topic": "溶液混合与限量试剂",
            "chem_mix_oracle": {"result": solve_solution_mixing(request)},
            "chem_mix_sample_oracles": self.sample_oracles if samples is None else samples,
        }

    def test_scene_selection_and_generation_guard(self):
        req = {"学科": "化学", "实验主题": "混合两种溶液，探究浓度和体积对限量试剂的影响"}
        skeleton = scene_registry.select_page_skeleton(req)
        self.assertEqual(skeleton["id"], "chemistry-solution-mixing-stoichiometry")
        self.assertEqual(skeleton["solver_api"], "CHEMSOLVER.solveSolutionMixing")

        sections = {key: "占位" for key in ("1", "2", "3", "4", "5", "6")}
        sections["2"] = '<svg data-visual-type="apparatus"><text data-chem-mix-equation></text></svg>'
        sections["3"] = ('<div class="exp-field">'
                          '<input data-chem-mix-concentration-index="0">'
                          '<input data-chem-mix-volume-index="0">'
                          '<select data-chem-mix-unit-index="0"></select>'
                          '<input data-chem-mix-concentration-index="1">'
                          '<input data-chem-mix-volume-index="1">'
                          '<select data-chem-mix-unit-index="1"></select>'
                          '<input data-chem-mix-progress></div>')
        sections["4"] = '<div class="exp-formula"></div>'
        sections["5"] = '<table class="exp-table"></table>'
        sections["js"] = "CHEMSOLVER.solveSolutionMixing(request);"
        problems = generator_agent.hard_validate(sections, req)
        self.assertTrue(any("__CHEM_MIX_REQUEST__" in problem for problem in problems))

        sections["js"] = """
          var result = CHEMSOLVER.solveSolutionMixing(request);
          window.__CHEM_MIX_REQUEST__ = request;
          window.__CHEM_MIX_RESULT__ = result;
          window.__DATA__ = {};
          equation.textContent = result.equation;
          reading.textContent = result.solution_inputs + result.initial_amounts_mol +
            result.limiting_reactants + result.max_extent_mol + result.remaining_mol +
            result.produced_mol + result.element_balance.ok + result.checks.ok;
        """
        problems = generator_agent.hard_validate(sections, req)
        self.assertFalse(any("溶液混合" in problem or "CHEMSOLVER.solveSolutionMixing" in problem
                             for problem in problems), problems)

    def test_shell_inlines_solution_mixing_solver(self):
        page_js = "var result = CHEMSOLVER.solveSolutionMixing(request);"
        assembled = shell._with_libs(page_js)
        self.assertIn("solveSolutionMixing", assembled)
        self.assertTrue(assembled.endswith(page_js))
        self.assertNotIn("<script src=", assembled)

    def test_independent_reviewer_passes_unit_equivalence_and_catches_tampering(self):
        check = next(item for item in judges.j3_conservation(self._context())
                     if item["check_id"] == "J3-08")
        self.assertEqual(check["status"], "pass")

        sample = copy.deepcopy(self.sample)
        sample["result"]["initial_amounts_mol"][0] += 0.001
        sample_oracles = [{"sample": sample, "oracle": {"result": self.sample_result}}]
        check = next(item for item in judges.j3_conservation(self._context(samples=sample_oracles))
                     if item["check_id"] == "J3-08")
        self.assertEqual(check["status"], "fail")

    def test_reviewer_detects_control_mismatch_and_wrong_display(self):
        controls = {
            "concentration_indices": [0, 1], "concentrations_mol_L": [0.2, 0.15],
            "volume_indices": [0, 1], "volumes": [50, 120],
            "unit_indices": [0, 1], "volume_units": ["mL", "mL"], "progress": 0.5,
        }
        check = next(item for item in judges.j3_conservation(
            self._context(controls=controls, displayed="BaCl2 + Na2SO4 → NaCl"))
                     if item["check_id"] == "J3-08")
        self.assertEqual(check["status"], "fail")


if __name__ == "__main__":
    unittest.main()
