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
import reviewer
import scene_registry
import shell
from chemistry.reactions.redox_solver import solve_redox


def request(reversed_order=False, medium="acidic"):
    reactants = [
        {"formula": "MnO4", "charge": -1, "phase": "aq"},
        {"formula": "Fe", "charge": 2, "phase": "aq"},
    ]
    products = [
        {"formula": "Mn", "charge": 2, "phase": "aq"},
        {"formula": "Fe", "charge": 3, "phase": "aq"},
    ]
    if reversed_order:
        reactants.reverse()
        products.reverse()
    return {"medium": medium, "reactants": reactants, "products": products}


def sample_for(req):
    result = solve_redox(req)
    return {
        "kind": "species-reordering", "request": copy.deepcopy(req), "result": result,
        "controls": {"medium": req["medium"], "reorder_button_visible": True},
        "displayed_equation": result["equation"],
        "displayed_electrons": "%s e⁻" % result["electron_balance"]["transferred_electrons"],
        "displayed_changes": " ".join(
            "%s %s %s %s" % (row["element"], row["before"], row["after"],
                              row["electrons_lost"] or row["electrons_gained"])
            for row in result["oxidation_changes"]),
    }


class RedoxPipelineIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.request = request()
        self.result = solve_redox(self.request)
        self.sample = sample_for(request(reversed_order=True))
        self.medium_sample = sample_for(request(medium="basic"))
        self.medium_sample["kind"] = "medium-change"

    def _machine(self, result=None, sample=None, equation=None, electrons=None, changes=None):
        return {
            "CHEM_REDOX_REQUEST": self.request,
            "CHEM_REDOX_RESULT": result or self.result,
            "CHEM_REDOX_CONTROLS": {"medium": "acidic", "reorder_button_visible": True},
            "CHEM_REDOX_DISPLAYED_EQUATION": equation or self.result["equation"],
            "CHEM_REDOX_DISPLAYED_ELECTRONS": electrons or "%s e⁻" % self.result["electron_balance"]["transferred_electrons"],
            "CHEM_REDOX_DISPLAYED_CHANGES": changes or "Fe +2 +3 Mn +7 +2",
            "CHEM_REDOX_SAMPLES": ([self.sample, self.medium_sample] if sample is None else [sample]),
        }

    def _judge(self, **overrides):
        machine = self._machine(**overrides)
        context = {
            "machine": machine, "text": "氧化还原电子守恒", "topic": "酸性条件氧化还原配平",
            "chem_redox_oracle": {"result": solve_redox(self.request)},
            "chem_redox_sample_oracles": [{
                "sample": sample, "oracle": {"result": solve_redox(sample["request"])},
            } for sample in machine["CHEM_REDOX_SAMPLES"]],
        }
        return next(item for item in judges.j3_conservation(context) if item["check_id"] == "J3-12")

    def test_scene_generation_contract_and_offline_bundle(self):
        req = {"学科": "化学", "实验主题": "酸性高锰酸钾与亚铁离子氧化还原电子守恒配平"}
        scene = scene_registry.select_page_skeleton(req)
        self.assertEqual(scene["id"], "chemistry-redox-electron-balance")
        self.assertEqual(scene["solver_api"], "CHEMSOLVER.solveRedox")

        sections = {key: "占位" for key in ("1", "2", "3", "4", "5", "6")}
        sections["2"] = '<canvas data-visual-type="diagram"></canvas>'
        sections["3"] = ('<div class="exp-field"><select data-chem-redox-medium><option value="acidic"></option>'
                          '<option value="basic"></option></select>'
                          '<button data-chem-redox-reorder>交换物质顺序验证</button></div>')
        sections["4"] = ('<div class="exp-formula"><output data-chem-redox-equation></output>'
                          '<output data-chem-redox-electrons></output>'
                          '<div data-chem-redox-changes></div></div>')
        sections["5"] = '<table class="exp-table"><tbody><tr><td>校验</td></tr></tbody></table>'
        sections["js"] = """
          var result = CHEMSOLVER.solveRedox(request);
          window.__DATA__ = {request: request, result: result};
          window.__CHEM_REDOX_REQUEST__ = request;
          window.__CHEM_REDOX_RESULT__ = result;
          equation.textContent = result.equation;
          electrons.textContent = result.electron_balance.transferred_electrons;
          changes.textContent = result.oxidation_changes;
          if (result.checks.ok) CHEM.redox(cv, result);
        """
        self.assertFalse(generator_agent.hard_validate(sections, req))
        sections["3"] = '<select data-chem-redox-medium></select>'
        self.assertTrue(any("data-chem-redox-reorder" in issue
                            for issue in generator_agent.hard_validate(sections, req)))
        bundle = shell._with_libs("CHEMSOLVER.solveRedox(request); CHEM.redox(cv,result);")
        self.assertIn("solveRedox", bundle)
        self.assertIn("redox", bundle)
        self.assertNotIn("<script src=", bundle)

    def test_independent_review_accepts_and_detects_page_tampering(self):
        self.assertEqual(self._judge()["status"], "pass")
        result = copy.deepcopy(self.result)
        result["electron_balance"]["lost_electrons"] = 99
        self.assertEqual(self._judge(result=result)["status"], "fail")
        self.assertEqual(self._judge(equation="MnO4 → Fe")["status"], "fail")

    def test_page_metamorphic_review_requires_live_reordered_request_and_response(self):
        machine = self._machine()
        page = {
            "machine": machine,
            "chemistryRedox": {"initial": {"request": self.request, "result": self.result}},
            "metamorphic": {"samples": [{
                "kind": "species-reordering", "inputChanged": True,
                "changedInputs": ["__CHEM_REDOX_REQUEST__"],
                "changedResponses": ["__CHEM_REDOX_RESULT__"],
            }]},
        }
        check = reviewer.verify_solver_page_metamorphic(page, "CHEMSOLVER.solveRedox")
        self.assertTrue(check["ok"], check["actual"])
        machine["CHEM_REDOX_SAMPLES"] = []
        check = reviewer.verify_solver_page_metamorphic(page, "CHEMSOLVER.solveRedox")
        self.assertFalse(check["ok"])
        self.assertIn("氧化还原电子守恒", check["missing"])


if __name__ == "__main__":
    unittest.main()
