import copy
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "../../../../../"))
sys.path.insert(0, PROJECT)
sys.path.insert(0, os.path.join(PROJECT, "03_generator_agent"))
sys.path.insert(0, os.path.join(PROJECT, "04_review_agent"))
sys.path.insert(0, os.path.join(PROJECT, "03_generator_agent", "solvers", "chemistry", "equations"))

import generator_agent
import judges
import scene_registry
import shell
from equation_balancer import balance_equation, check_coefficients


class EquationPipelineIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.request = {"reactants": ["Fe", "CuSO4"], "products": ["FeSO4", "Cu"]}
        self.result = balance_equation(self.request)

    def test_scene_selection_and_generator_guard(self):
        request = {"学科": "化学", "实验主题": "化学方程式配平"}
        skeleton = scene_registry.select_page_skeleton(request)
        self.assertEqual(skeleton["id"], "chemistry-equation-balance")
        self.assertEqual(skeleton["solver_api"], "CHEMSOLVER.balanceEquation")

        sections = {key: "占位" for key in ("1", "2", "3", "4", "5", "6")}
        sections["2"] = '<canvas data-visual-type="diagram"></canvas>'
        sections["js"] = "var result = {};"
        problems = generator_agent.hard_validate(sections, request)
        self.assertTrue(any("CHEMSOLVER.balanceEquation" in problem for problem in problems))
        self.assertTrue(any("__CHEM_BALANCE_REQUEST__" in problem for problem in problems))

    def test_shell_inlines_offline_solver(self):
        page_js = "var result = CHEMSOLVER.balanceEquation(request);"
        assembled = shell._with_libs(page_js)
        self.assertIn("root.CHEMSOLVER", assembled)
        self.assertTrue(assembled.endswith(page_js))
        self.assertNotIn("<script src=", assembled)

    def test_independent_reviewer_passes_correct_result_and_fails_tampering(self):
        scaled_request = {"reactants": ["(Fe)2", "(CuSO4)2"],
                         "products": ["(FeSO4)2", "(Cu)2"]}
        unicode_request = {"reactants": ["Fe", "CuSO₄"], "products": ["FeSO₄", "Cu"]}
        reordered_request = {"reactants": ["CuSO4", "Fe"], "products": ["Cu", "FeSO4"]}
        meta_samples = [
            {"kind": "uniform-formula-scaling", "request": scaled_request,
             "result": balance_equation(scaled_request)},
            {"kind": "unicode-subscript-equivalence", "request": unicode_request,
             "result": balance_equation(unicode_request)},
            {"kind": "species-reordering", "request": reordered_request,
             "result": balance_equation(reordered_request)},
            {"kind": "student-coefficients-common-scale", "request": self.request,
             "student_coefficients": {"reactants": [2, 2], "products": [2, 2]},
             "student_check": check_coefficients(self.request,
                 {"reactants": [2, 2], "products": [2, 2]}),
             "displayed_check": {"balanced": "true", "primitive": "false"}},
        ]
        sample_oracles = [
            {"sample": sample, "oracle": {"result": sample["student_check"] if sample["kind"] == "student-coefficients-common-scale" else sample["result"]}}
            for sample in meta_samples
        ]
        machine = {
            "CHEM_BALANCE_REQUEST": self.request,
            "CHEM_BALANCE_RESULT": copy.deepcopy(self.result),
            "CHEM_BALANCE_DISPLAYED_EQUATION": self.result["equation"],
            "CHEM_BALANCE_SAMPLES": meta_samples,
        }
        context = {
            "machine": machine,
            "text": "化学方程式配平",
            "topic": "化学方程式配平",
            "chem_balance_oracle": {"result": self.result},
            "chem_balance_sample_oracles": sample_oracles,
        }
        checks = judges.j3_conservation(context)
        balance_check = next(check for check in checks if check["check_id"] == "J3-06")
        self.assertEqual(balance_check["status"], "pass")

        machine["CHEM_BALANCE_RESULT"]["coefficients"]["products"] = [1, 2]
        checks = judges.j3_conservation(context)
        balance_check = next(check for check in checks if check["check_id"] == "J3-06")
        self.assertEqual(balance_check["status"], "fail")


if __name__ == "__main__":
    unittest.main()
