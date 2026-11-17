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
from chemistry.reactions.gas_collection_solver import solve_gas_collection


def make_request(zinc=0.02, acid=0.05, progress=0.6, temperature=25,
                 pressure=101.325, method="dry"):
    return {
        "reactants": [{"formula": "Zn", "phase": "s"}, {"formula": "HCl", "phase": "aq"}],
        "products": [{"formula": "ZnCl2", "phase": "aq"}, {"formula": "H2", "phase": "g"}],
        "initial_amounts_mol": [zinc, acid], "progress": progress,
        "gas_formula": "H2", "temperature_c": temperature,
        "total_pressure_kpa": pressure, "collection_method": method,
    }


def make_sample(request, kind):
    result = solve_gas_collection(request)
    return {
        "kind": kind, "request": copy.deepcopy(request), "result": result,
        "controls": {
            "amount_indices": [0, 1], "amounts_mol": request["initial_amounts_mol"],
            "progress": request["progress"], "temperature_c": request["temperature_c"],
            "total_pressure_kpa": request["total_pressure_kpa"],
            "collection_method": request["collection_method"],
        },
        "displayed_equation": result["equation"],
        "displayed_volume": "%.2f L" % result["gas_volume_l"],
    }


class GasCollectionPipelineIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.request = make_request()
        self.result = solve_gas_collection(self.request)
        self.samples = [
            make_sample(make_request(0.04, 0.10), "common-amount-scale"),
            make_sample(make_request(progress=0.7), "progress-change"),
            make_sample(make_request(temperature=30), "temperature-change"),
            make_sample(make_request(pressure=120), "pressure-change"),
            make_sample(make_request(method="over_water"), "method-toggle"),
        ]

    def _machine(self, result=None, samples=None, controls=None, equation=None, volume=None):
        return {
            "CHEM_GAS_REQUEST": self.request,
            "CHEM_GAS_RESULT": result or self.result,
            "CHEM_GAS_CONTROLS": controls or {
                "amount_indices": [0, 1], "amounts_mol": self.request["initial_amounts_mol"],
                "progress": self.request["progress"], "temperature_c": self.request["temperature_c"],
                "total_pressure_kpa": self.request["total_pressure_kpa"],
                "collection_method": self.request["collection_method"],
            },
            "CHEM_GAS_DISPLAYED_EQUATION": equation if equation is not None else self.result["equation"],
            "CHEM_GAS_DISPLAYED_VOLUME": volume if volume is not None else "%.2f L" % self.result["gas_volume_l"],
            "CHEM_GAS_SAMPLES": self.samples if samples is None else samples,
        }

    def _judge(self, result=None, samples=None, controls=None, equation=None, volume=None):
        machine = self._machine(result, samples, controls, equation, volume)
        sample_rows = [{"sample": item, "oracle": {"result": solve_gas_collection(item["request"])}}
                       for item in machine["CHEM_GAS_SAMPLES"]]
        context = {
            "machine": machine, "text": "气体制取与排水集气", "topic": "气体制取与排水集气",
            "chem_gas_oracle": {"result": solve_gas_collection(self.request)},
            "chem_gas_sample_oracles": sample_rows,
        }
        return next(item for item in judges.j3_conservation(context) if item["check_id"] == "J3-10")

    def test_scene_generation_guard_and_offline_bundle(self):
        request = {"学科": "化学", "实验主题": "锌与稀盐酸制取氢气并探究排水集气体积"}
        scene = scene_registry.select_page_skeleton(request)
        self.assertEqual(scene["id"], "chemistry-gas-collection")
        self.assertEqual(scene["solver_api"], "CHEMSOLVER.solveGasCollection")

        sections = {key: "占位" for key in ("1", "2", "3", "4", "5", "6")}
        sections["2"] = ('<canvas data-visual-type="apparatus"></canvas>'
                          '<output data-chem-gas-equation></output>')
        sections["3"] = " ".join('<input data-chem-gas-%s>' % marker for marker in (
            "amount-index=\"0\"", "amount-index=\"1\"", "progress", "temperature", "pressure", "method"))
        sections["4"] = '<output data-chem-gas-volume></output>'
        sections["js"] = "CHEMSOLVER.solveGasCollection(request);"
        problems = generator_agent.hard_validate(sections, request)
        self.assertTrue(any("__CHEM_GAS_REQUEST__" in item for item in problems))

        sections["js"] = """
          var result = CHEMSOLVER.solveGasCollection(request);
          window.__CHEM_GAS_REQUEST__ = request;
          window.__CHEM_GAS_RESULT__ = result;
          window.__DATA__ = {};
          equation.textContent = result.equation;
          volume.textContent = result.gas_volume_l + ' L';
          reading.textContent = result.gas_moles + result.gas_volume_l +
            result.dry_gas_partial_pressure_kpa + result.limiting_reactants + result.checks.ok;
          CHEM.gasCollection(cv, result);
        """
        problems = generator_agent.hard_validate(sections, request)
        self.assertFalse(any("气体制取" in item or "CHEMSOLVER.solveGasCollection" in item
                             for item in problems), problems)

        bundle = shell._with_libs("CHEMSOLVER.solveGasCollection(request); CHEM.gasCollection(cv,result);")
        self.assertIn("solveGasCollection", bundle)
        self.assertIn("gasCollection", bundle)
        self.assertNotIn("<script src=", bundle)

    def test_independent_reviewer_passes_and_detects_result_control_and_sample_tampering(self):
        self.assertEqual(self._judge()["status"], "pass")
        all_j3 = judges.j3_conservation({
            "machine": self._machine(), "text": "气体制取与排水集气", "topic": "气体制取与排水集气",
            "chem_gas_oracle": {"result": self.result},
            "chem_gas_sample_oracles": [
                {"sample": item, "oracle": {"result": solve_gas_collection(item["request"])}}
                for item in self.samples
            ],
        })
        self.assertFalse([item for item in all_j3 if item["status"] == "fail"], all_j3)
        result = copy.deepcopy(self.result)
        result["gas_volume_l"] += 0.1
        self.assertEqual(self._judge(result=result)["status"], "fail")
        controls = self._machine()["CHEM_GAS_CONTROLS"]
        controls["temperature_c"] += 5
        self.assertEqual(self._judge(controls=controls)["status"], "fail")
        samples = copy.deepcopy(self.samples)
        samples[0]["result"]["gas_moles"] += 0.01
        self.assertEqual(self._judge(samples=samples)["status"], "fail")

    def test_reviewer_detects_wrong_visible_equation_and_volume(self):
        self.assertEqual(self._judge(equation="Zn + HCl → Zn + HCl")["status"], "fail")
        self.assertEqual(self._judge(volume="999 L")["status"], "fail")
        self.assertEqual(self._judge(volume="%.0f mL" % (self.result["gas_volume_l"] * 1000))["status"], "pass")
        self.assertEqual(self._judge(volume="0.3 L")["status"], "fail")

    def test_page_metamorphic_gate_requires_real_gas_input_and_result_change(self):
        machine = self._machine()
        page = {
            "machine": machine,
            "chemistryGasCollection": {"initial": {"request": self.request, "result": self.result}},
            "metamorphic": {"samples": [{
                "inputChanged": True,
                "changedInputs": ["__CHEM_GAS_REQUEST__"],
                "changedResponses": ["__CHEM_GAS_RESULT__"],
            }]},
        }
        check = reviewer.verify_solver_page_metamorphic(page, "CHEMSOLVER.solveGasCollection")
        self.assertTrue(check["ok"], check["actual"])
        page["machine"]["CHEM_GAS_SAMPLES"] = []
        check = reviewer.verify_solver_page_metamorphic(page, "CHEMSOLVER.solveGasCollection")
        self.assertFalse(check["ok"])
        self.assertIn("气体制取与收集", check["missing"])


if __name__ == "__main__":
    unittest.main()
