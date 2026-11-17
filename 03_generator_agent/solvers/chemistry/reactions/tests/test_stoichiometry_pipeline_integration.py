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
from chemistry.reactions.stoichiometry_solver import solve_stoichiometry


class StoichiometryPipelineIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.request = {
            "reactants": ["Fe", "CuSO4"], "products": ["FeSO4", "Cu"],
            "initial_amounts_mol": [0.1, 0.06], "progress": 0.5,
        }
        self.result = solve_stoichiometry(self.request)
        def sample(amounts, progress, kind, **extra):
            request = {**self.request, "initial_amounts_mol": amounts, "progress": progress}
            result = solve_stoichiometry(request)
            return {
                "kind": kind, "request": request, "result": result,
                "controls": {"indices": [0, 1], "initial_amounts_mol": amounts,
                             "amount_min": [0, 0], "amount_max": [1, 1], "progress": progress},
                "displayed_equation": result["equation"], **extra,
            }
        self.samples = [
            sample([0.12, 0.06], 0.73, "amount-change"),
            sample([0.2, 0.12], 0.5, "common-scaling", scale_factor=2),
            sample([0.1, 0.06], 0, "progress-zero"),
            sample([0.1, 0.06], 0.5, "progress-half"),
            sample([0.1, 0.06], 1, "progress-complete"),
            sample([0.0588, 0.06], 0.5, "limiting-threshold-below", threshold_index=0, threshold_mol=0.06),
            sample([0.06, 0.06], 0.5, "limiting-threshold-at", threshold_index=0, threshold_mol=0.06),
            sample([0.0612, 0.06], 0.5, "limiting-threshold-above", threshold_index=0, threshold_mol=0.06),
        ]
        self.sample = self.samples[0]
        self.sample_oracles = [{"sample": item, "oracle": {"result": item["result"]}}
                               for item in self.samples]

    def test_scene_selection_and_generator_guard(self):
        request = {"学科": "化学", "实验主题": "限量试剂与理论产量"}
        skeleton = scene_registry.select_page_skeleton(request)
        self.assertEqual(skeleton["id"], "chemistry-stoichiometry-limiting-reagent")
        self.assertEqual(skeleton["solver_api"], "CHEMSOLVER.solveStoichiometry")

        sections = {key: "占位" for key in ("1", "2", "3", "4", "5", "6")}
        sections["2"] = '<svg data-visual-type="apparatus"><text data-chem-stoich-equation></text></svg>'
        sections["3"] = ('<div class="exp-field">'
                          '<input data-chem-stoich-amount-index="0">'
                          '<input data-chem-stoich-amount-index="1">'
                          '<input type="range" min="0" max="1" step="0.01" data-chem-stoich-progress></div>')
        sections["4"] = '<div class="exp-formula"></div>'
        sections["5"] = '<table class="exp-table"></table>'
        sections["js"] = "CHEMSOLVER.solveStoichiometry(request);"
        problems = generator_agent.hard_validate(sections, request)
        self.assertTrue(any("__CHEM_STOICH_REQUEST__" in problem for problem in problems))
        sections["3"] = '<div class="exp-field"></div>'
        problems = generator_agent.hard_validate(sections, request)
        self.assertTrue(any("可见物质的量与反应进度控件" in problem for problem in problems))

        sections["3"] = ('<div class="exp-field">'
                          '<input data-chem-stoich-amount-index="0">'
                          '<input data-chem-stoich-amount-index="1">'
                          '<input type="range" min="0" max="1" step="0.01" data-chem-stoich-progress></div>')
        sections["js"] = """
          var result = CHEMSOLVER.solveStoichiometry(request);
          window.__CHEM_STOICH_REQUEST__ = request;
          window.__CHEM_STOICH_RESULT__ = result;
          window.__DATA__ = {};
          equation.textContent = result.equation;
          output.textContent = result.max_extent_mol + result.extent_mol +
            result.limiting_reactants + result.reactants[0].remaining_mol +
            result.products[0].produced_mol + result.element_balance.ok + result.checks.ok;
        """
        problems = generator_agent.hard_validate(sections, request)
        self.assertFalse(any("反应计量" in problem or "CHEMSOLVER.solveStoichiometry" in problem
                             for problem in problems), problems)

    def test_shell_inlines_offline_chemistry_solver(self):
        assembled = shell._with_libs("var result = CHEMSOLVER.solveStoichiometry(request);")
        self.assertIn("solveStoichiometry", assembled)
        self.assertTrue(assembled.endswith("var result = CHEMSOLVER.solveStoichiometry(request);"))
        self.assertNotIn("<script src=", assembled)

    def test_independent_reviewer_passes_correct_result_and_fails_tampering(self):
        machine = {
            "CHEM_STOICH_REQUEST": self.request,
            "CHEM_STOICH_RESULT": copy.deepcopy(self.result),
            "CHEM_STOICH_CONTROLS": {"indices": [0, 1], "initial_amounts_mol": [0.1, 0.06],
                                      "amount_min": [0, 0], "amount_max": [1, 1], "progress": 0.5},
            "CHEM_STOICH_DISPLAYED_EQUATION": self.result["equation"],
        }
        context = {
            "machine": machine,
            "text": "限量试剂与理论产量",
            "topic": "限量试剂与理论产量",
            "chem_stoich_oracle": {"result": self.result},
            "chem_stoich_sample_oracles": self.sample_oracles,
        }
        check = next(item for item in judges.j3_conservation(context)
                     if item["check_id"] == "J3-07")
        self.assertEqual(check["status"], "pass")

        machine["CHEM_STOICH_RESULT"]["reactants"][0]["remaining_mol"] += 0.01
        check = next(item for item in judges.j3_conservation(context)
                     if item["check_id"] == "J3-07")
        self.assertEqual(check["status"], "fail")

    def test_reviewer_fails_when_visible_controls_do_not_match_solver_request(self):
        machine = {
            "CHEM_STOICH_REQUEST": self.request,
            "CHEM_STOICH_RESULT": copy.deepcopy(self.result),
            "CHEM_STOICH_CONTROLS": {"indices": [0, 1], "initial_amounts_mol": [0.1, 0.08], "progress": 0.5},
            "CHEM_STOICH_DISPLAYED_EQUATION": self.result["equation"],
        }
        context = {"machine": machine, "text": "", "topic": "",
                   "chem_stoich_oracle": {"result": self.result},
                   "chem_stoich_sample_oracles": self.sample_oracles}
        check = next(item for item in judges.j3_conservation(context)
                     if item["check_id"] == "J3-07")
        self.assertEqual(check["status"], "fail")

    def test_reviewer_compares_numeric_control_strings_by_value(self):
        request = {**self.request, "initial_amounts_mol": ["0.1", "0.06"], "progress": "0.5"}
        result = solve_stoichiometry(request)
        context = {
            "machine": {
                "CHEM_STOICH_REQUEST": request,
                "CHEM_STOICH_RESULT": result,
                "CHEM_STOICH_CONTROLS": {
                    "indices": [0, 1], "initial_amounts_mol": [0.1, 0.06], "progress": 0.5,
                },
                "CHEM_STOICH_DISPLAYED_EQUATION": result["equation"],
            },
            "text": "", "topic": "", "chem_stoich_oracle": {"result": result},
            "chem_stoich_sample_oracles": self.sample_oracles,
        }
        check = next(item for item in judges.j3_conservation(context)
                     if item["check_id"] == "J3-07")
        self.assertEqual(check["status"], "pass")

    def test_reviewer_detects_missing_or_wrong_visible_equation(self):
        machine = {
            "CHEM_STOICH_REQUEST": self.request,
            "CHEM_STOICH_RESULT": copy.deepcopy(self.result),
            "CHEM_STOICH_DISPLAYED_EQUATION": "Fe + CuSO4 → Fe + CuSO4",
        }
        context = {"machine": machine, "text": "", "topic": "",
                   "chem_stoich_oracle": {"result": self.result},
                   "chem_stoich_sample_oracles": self.sample_oracles}
        check = next(item for item in judges.j3_conservation(context)
                     if item["check_id"] == "J3-07")
        self.assertEqual(check["status"], "fail")

    def test_reviewer_catches_tampered_page_during_control_mutation(self):
        sample = copy.deepcopy(self.sample)
        sample["result"]["extent_mol"] += 0.01
        context = {
            "machine": {
                "CHEM_STOICH_REQUEST": self.request,
                "CHEM_STOICH_RESULT": copy.deepcopy(self.result),
                "CHEM_STOICH_CONTROLS": {"indices": [0, 1], "initial_amounts_mol": [0.1, 0.06], "progress": 0.5},
                "CHEM_STOICH_DISPLAYED_EQUATION": self.result["equation"],
            },
            "text": "", "topic": "", "chem_stoich_oracle": {"result": self.result},
            "chem_stoich_sample_oracles": [{"sample": sample, "oracle": {"result": self.sample["result"]}}],
        }
        check = next(item for item in judges.j3_conservation(context)
                     if item["check_id"] == "J3-07")
        self.assertEqual(check["status"], "fail")

    def test_reviewer_requires_page_scale_progress_and_threshold_metamorphoses(self):
        context = {
            "machine": {
                "CHEM_STOICH_REQUEST": self.request,
                "CHEM_STOICH_RESULT": copy.deepcopy(self.result),
                "CHEM_STOICH_CONTROLS": {
                    "indices": [0, 1], "initial_amounts_mol": [0.1, 0.06],
                    "amount_min": [0, 0], "amount_max": [1, 1], "progress": 0.5,
                },
                "CHEM_STOICH_DISPLAYED_EQUATION": self.result["equation"],
            },
            "text": "限量试剂和理论产量", "topic": "限量试剂",
            "chem_stoich_oracle": {"result": self.result},
            "chem_stoich_sample_oracles": [],
        }
        check = next(item for item in judges.j3_conservation(context)
                     if item["check_id"] == "J3-07")
        self.assertEqual(check["status"], "fail")
        self.assertIn("同比缩放", check["actual"])
        self.assertIn("反应进度 0、0.5、1", check["actual"])
        self.assertIn("限量试剂临界点", check["actual"])


if __name__ == "__main__":
    unittest.main()
