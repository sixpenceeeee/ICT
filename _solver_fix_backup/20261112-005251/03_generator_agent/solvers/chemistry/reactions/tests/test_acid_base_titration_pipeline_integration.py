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
import reviewer
from chemistry.reactions.acid_base_titration_solver import solve_acid_base_titration


def make_request(base_volume=24, acid_volume=25, acid_unit="mL", base_unit="mL"):
    return {
        "acid": {"formula": "HCl", "concentration_mol_L": 0.1,
                 "volume": acid_volume, "volume_unit": acid_unit},
        "base": {"formula": "NaOH", "concentration_mol_L": 0.1,
                 "volume": base_volume, "volume_unit": base_unit},
    }


def sample(request, kind):
    result = solve_acid_base_titration(request)
    acid, base = request["acid"], request["base"]
    return {
        "kind": kind,
        "request": copy.deepcopy(request),
        "result": result,
        "controls": {
            "acid_concentration_mol_L": acid["concentration_mol_L"],
            "acid_volume": acid["volume"], "acid_volume_unit": acid["volume_unit"],
            "base_concentration_mol_L": base["concentration_mol_L"],
            "base_volume": base["volume"], "base_volume_unit": base["volume_unit"],
        },
        "displayed_equation": result["equation"],
        "displayed_ph": "pH = %.2f" % result["pH"],
    }


class AcidBaseTitrationPipelineIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.request = make_request()
        self.result = solve_acid_base_titration(self.request)
        self.samples = [
            sample(make_request(23.5), "input-change"),
            sample(make_request(0.024, 0.025, "L", "L"), "equivalent-volume-units"),
            sample(make_request(24.75), "below-equivalence"),
            sample(make_request(25), "at-equivalence"),
            sample(make_request(25.25), "above-equivalence"),
        ]
        self.sample_oracles = [{"sample": item, "oracle": {"result": solve_acid_base_titration(item["request"])}}
                               for item in self.samples]

    def _machine(self, request=None, result=None, samples=None, controls=None, equation=None, ph=None):
        request = request or self.request
        result = result or solve_acid_base_titration(request)
        acid, base = request["acid"], request["base"]
        return {
            "CHEM_TITRATION_REQUEST": request,
            "CHEM_TITRATION_RESULT": result,
            "CHEM_TITRATION_CONTROLS": controls or {
                "acid_concentration_mol_L": acid["concentration_mol_L"],
                "acid_volume": acid["volume"], "acid_volume_unit": acid["volume_unit"],
                "base_concentration_mol_L": base["concentration_mol_L"],
                "base_volume": base["volume"], "base_volume_unit": base["volume_unit"],
            },
            "CHEM_TITRATION_DISPLAYED_EQUATION": equation if equation is not None else result["equation"],
            "CHEM_TITRATION_DISPLAYED_PH": ph if ph is not None else "pH = %.2f" % result["pH"],
            "CHEM_TITRATION_SAMPLES": samples if samples is not None else self.samples,
        }

    def _judge(self, **kwargs):
        machine = self._machine(**kwargs)
        context = {
            "machine": machine,
            "text": "酸碱中和滴定",
            "topic": "酸碱中和滴定",
            "chem_titration_oracle": {"result": solve_acid_base_titration(machine["CHEM_TITRATION_REQUEST"])},
            "chem_titration_sample_oracles": [
                {"sample": item, "oracle": {"result": solve_acid_base_titration(item["request"])}}
                for item in machine.get("CHEM_TITRATION_SAMPLES", [])
            ],
        }
        return next(item for item in judges.j3_conservation(context) if item["check_id"] == "J3-09")

    def test_scene_generation_guard_and_offline_bundle(self):
        request = {"学科": "化学", "实验主题": "酸碱中和滴定，观察当量点前后的 pH 变化"}
        skeleton = scene_registry.select_page_skeleton(request)
        self.assertEqual(skeleton["id"], "chemistry-acid-base-titration")
        self.assertEqual(skeleton["solver_api"], "CHEMSOLVER.solveAcidBaseTitration")

        sections = {key: "占位" for key in ("1", "2", "3", "4", "5", "6")}
        sections["2"] = '<svg data-visual-type="apparatus"><text data-chem-titration-equation></text></svg>'
        sections["3"] = " ".join('<input data-chem-titration-%s>' % marker for marker in (
            "acid-concentration", "acid-volume", "acid-unit", "base-concentration", "base-volume", "base-unit"))
        sections["js"] = "CHEMSOLVER.solveAcidBaseTitration(request);"
        problems = generator_agent.hard_validate(sections, request)
        self.assertTrue(any("__CHEM_TITRATION_REQUEST__" in item for item in problems))

        sections["js"] = """
          var result = CHEMSOLVER.solveAcidBaseTitration(request);
          window.__CHEM_TITRATION_REQUEST__ = request;
          window.__CHEM_TITRATION_RESULT__ = result;
          window.__DATA__ = {};
          equation.textContent = result.equation;
          CHEM.titration(cv, result);
          output.textContent = result.equivalence_volume_ml + result.acid_moles_remaining +
            result.base_moles_remaining + result.pH + result.state + result.checks.ok;
        """
        sections["js"] = sections["js"].replace("CHEM.titration(cv, result);", "")
        problems = generator_agent.hard_validate(sections, request)
        self.assertTrue(any("CHEM.titration" in item for item in problems))
        sections["js"] += "\nCHEM.titration(cv, result);"
        problems = generator_agent.hard_validate(sections, request)
        self.assertFalse(any("酸碱滴定" in item or "CHEMSOLVER.solveAcidBaseTitration" in item
                             for item in problems), problems)

        assembled = shell._with_libs("CHEMSOLVER.solveAcidBaseTitration(request);")
        self.assertIn("solveAcidBaseTitration", assembled)
        self.assertIn("function titration", shell._with_libs("CHEM.titration(cv,result);"))

    def test_independent_reviewer_passes_and_detects_tampering(self):
        self.assertEqual(self._judge()["status"], "pass")
        all_j3 = judges.j3_conservation({
            "machine": self._machine(), "text": "酸碱中和滴定", "topic": "酸碱中和滴定",
            "chem_titration_oracle": {"result": self.result},
            "chem_titration_sample_oracles": self.sample_oracles,
        })
        self.assertFalse([item for item in all_j3 if item["status"] == "fail"], all_j3)
        result = copy.deepcopy(self.result)
        result["pH"] += 0.5
        self.assertEqual(self._judge(result=result)["status"], "fail")

        samples = copy.deepcopy(self.samples)
        samples[2]["result"]["state"] = "basic"
        self.assertEqual(self._judge(samples=samples)["status"], "fail")

    def test_independent_reviewer_checks_controls_equation_and_visible_ph(self):
        controls = self._machine()["CHEM_TITRATION_CONTROLS"]
        controls["base_volume"] = 30
        self.assertEqual(self._judge(controls=controls)["status"], "fail")
        self.assertEqual(self._judge(equation="HCl + NaOH → HCl + NaOH")["status"], "fail")
        self.assertEqual(self._judge(ph="pH = 11.2")["status"], "fail")

    def test_page_metamorphic_gate_requires_changed_request_and_named_transformations(self):
        machine = self._machine()
        page = {
            "machine": machine,
            "chemistryTitration": {"initial": {"request": self.request, "result": self.result}},
            "metamorphic": {"samples": [{
                "inputChanged": True,
                "changedInputs": ["__CHEM_TITRATION_REQUEST__"],
                "changedResponses": ["__CHEM_TITRATION_RESULT__"],
            }]},
        }
        result = reviewer.verify_solver_page_metamorphic(page, "CHEMSOLVER.solveAcidBaseTitration")
        self.assertTrue(result["ok"], result["actual"])
        page["machine"]["CHEM_TITRATION_SAMPLES"] = []
        result = reviewer.verify_solver_page_metamorphic(page, "CHEMSOLVER.solveAcidBaseTitration")
        self.assertFalse(result["ok"])
        self.assertIn("酸碱中和滴定", result["missing"])


if __name__ == "__main__":
    unittest.main()
