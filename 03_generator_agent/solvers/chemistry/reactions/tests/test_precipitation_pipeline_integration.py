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
from chemistry.reactions.precipitation_solver import solve_precipitation


def make_request(vb=90, ub="mL", ca=0.2, va=50, ua="mL", progress=0.8):
    return {"solutions": [
        {"formula": "BaCl2", "concentration_mol_L": ca, "volume": va, "volume_unit": ua},
        {"formula": "Na2SO4", "concentration_mol_L": 0.1, "volume": vb, "volume_unit": ub},
    ], "progress": progress}


def make_sample(request, kind, threshold_index=None):
    result = solve_precipitation(request)
    sample = {
        "kind": kind, "request": copy.deepcopy(request), "result": result,
        "controls": {
            "concentration_indices": [0, 1],
            "concentrations_mol_L": [item["concentration_mol_L"] for item in request["solutions"]],
            "volume_indices": [0, 1], "volumes": [item["volume"] for item in request["solutions"]],
            "unit_indices": [0, 1], "volume_units": [item["volume_unit"] for item in request["solutions"]],
            "progress": request["progress"],
        },
        "displayed_equation": result["equation"],
        "displayed_net_ionic": result["net_ionic_equation"],
        "displayed_mass": "%.4f g" % result["precipitate_mass_g"],
    }
    if threshold_index is not None:
        sample["threshold_input_index"] = threshold_index
    return sample


class PrecipitationPipelineIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.request = make_request()
        self.result = solve_precipitation(self.request)
        self.samples = [
            make_sample(make_request(vb=180, va=100), "common-volume-scale"),
            make_sample(make_request(vb=0.09, ub="L", va=0.05, ua="L"), "equivalent-unit"),
            make_sample(make_request(ca=0.22), "concentration-change"),
            make_sample(make_request(progress=0.4), "progress-change"),
            make_sample(make_request(vb=100), "stoichiometric-threshold-at", 1),
            make_sample(make_request(vb=98), "stoichiometric-threshold-below", 1),
            make_sample(make_request(vb=102), "stoichiometric-threshold-above", 1),
        ]

    def _machine(self, result=None, samples=None, controls=None, equation=None, net=None, mass=None):
        request = self.request
        return {
            "CHEM_PRECIP_REQUEST": request,
            "CHEM_PRECIP_RESULT": result or self.result,
            "CHEM_PRECIP_CONTROLS": controls or {
                "concentration_indices": [0, 1], "concentrations_mol_L": [0.2, 0.1],
                "volume_indices": [0, 1], "volumes": [50, 90],
                "unit_indices": [0, 1], "volume_units": ["mL", "mL"], "progress": 0.8,
            },
            "CHEM_PRECIP_DISPLAYED_EQUATION": equation or self.result["equation"],
            "CHEM_PRECIP_DISPLAYED_NET_IONIC": net or self.result["net_ionic_equation"],
            "CHEM_PRECIP_DISPLAYED_MASS": mass or "%.4f g" % self.result["precipitate_mass_g"],
            "CHEM_PRECIP_SAMPLES": self.samples if samples is None else samples,
        }

    def _judge(self, **overrides):
        machine = self._machine(**overrides)
        rows = [{"sample": sample, "oracle": {"result": solve_precipitation(sample["request"])}}
                for sample in machine["CHEM_PRECIP_SAMPLES"]]
        context = {
            "machine": machine, "text": "沉淀反应定量", "topic": "沉淀质量计算",
            "chem_precip_oracle": {"result": solve_precipitation(self.request)},
            "chem_precip_sample_oracles": rows,
        }
        return next(item for item in judges.j3_conservation(context) if item["check_id"] == "J3-11")

    def test_scene_selection_generation_contract_and_offline_bundle(self):
        request = {"学科": "化学", "实验主题": "混合硫酸钠和氯化钡，计算硫酸钡沉淀质量"}
        scene = scene_registry.select_page_skeleton(request)
        self.assertEqual(scene["id"], "chemistry-precipitation-quantitative")
        self.assertEqual(scene["solver_api"], "CHEMSOLVER.solvePrecipitation")

        sections = {key: "占位" for key in ("1", "2", "3", "4", "5", "6")}
        sections["2"] = ('<canvas data-visual-type="apparatus"></canvas>'
                          '<output data-chem-precip-equation></output>'
                          '<output data-chem-precip-net-ionic></output>')
        sections["3"] = (''.join(
            '<input data-chem-precip-concentration-index="%d">'
            '<input data-chem-precip-volume-index="%d">'
            '<select data-chem-precip-unit-index="%d"></select>' % (i, i, i) for i in range(2)) +
            '<input data-chem-precip-progress>')
        sections["4"] = '<output data-chem-precip-mass></output>'
        sections["js"] = "CHEMSOLVER.solvePrecipitation(request);"
        problems = generator_agent.hard_validate(sections, request)
        self.assertTrue(any("__CHEM_PRECIP_REQUEST__" in problem for problem in problems))
        sections["js"] = """
          var result = CHEMSOLVER.solvePrecipitation(request);
          window.__CHEM_PRECIP_REQUEST__ = request;
          window.__CHEM_PRECIP_RESULT__ = result;
          equation.textContent = result.equation;
          net.textContent = result.net_ionic_equation;
          mass.textContent = result.precipitate_mass_g.toFixed(4) + ' g';
          reading.textContent = result.precipitate_formula + result.precipitate_moles +
            result.limiting_reactants + result.checks.ok;
          CHEM.precipitation(cv, result);
        """
        problems = generator_agent.hard_validate(sections, request)
        self.assertFalse(any("沉淀反应页面" in problem or "CHEMSOLVER.solvePrecipitation" in problem
                             for problem in problems), problems)
        bundle = shell._with_libs("CHEMSOLVER.solvePrecipitation(request); CHEM.precipitation(cv,result);")
        self.assertIn("solvePrecipitation", bundle)
        self.assertIn("precipitation", bundle)
        self.assertNotIn("<script src=", bundle)

    def test_independent_reviewer_accepts_and_detects_tampering(self):
        self.assertEqual(self._judge()["status"], "pass")
        result = copy.deepcopy(self.result)
        result["precipitate_mass_g"] += 0.5
        self.assertEqual(self._judge(result=result)["status"], "fail")
        self.assertEqual(self._judge(net="Ag⁺ + Cl⁻ → AgCl(s)")["status"], "fail")
        controls = self._machine()["CHEM_PRECIP_CONTROLS"]
        controls["volumes"][1] = 91
        self.assertEqual(self._judge(controls=controls)["status"], "fail")

    def test_all_seven_page_metamorphic_states_are_required(self):
        machine = self._machine()
        page = {
            "machine": machine,
            "chemistryPrecipitation": {"initial": {"request": self.request, "result": self.result}},
            "metamorphic": {"samples": [{
                "inputChanged": True,
                "changedInputs": ["__CHEM_PRECIP_REQUEST__"],
                "changedResponses": ["__CHEM_PRECIP_RESULT__"],
            }]},
        }
        check = reviewer.verify_solver_page_metamorphic(page, "CHEMSOLVER.solvePrecipitation")
        self.assertTrue(check["ok"], check["actual"])
        page["machine"]["CHEM_PRECIP_SAMPLES"] = []
        check = reviewer.verify_solver_page_metamorphic(page, "CHEMSOLVER.solvePrecipitation")
        self.assertFalse(check["ok"])
        self.assertIn("沉淀反应定量", check["missing"])


if __name__ == "__main__":
    unittest.main()
