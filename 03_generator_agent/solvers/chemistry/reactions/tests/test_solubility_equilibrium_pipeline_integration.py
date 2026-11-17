import copy
import math
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
import run_pipeline
import scene_registry
import shell
from chemistry.reactions.solubility_equilibrium_solver import solve_solubility_equilibrium


def request(ksp=4e-11, calcium=0.0, fluoride=0.0):
    return {
        "solid_formula": "CaF2", "Ksp": ksp,
        "ions": [
            {"formula": "Ca", "charge": 2, "coefficient": 1,
             "initial_concentration_mol_L": calcium},
            {"formula": "F", "charge": -1, "coefficient": 2,
             "initial_concentration_mol_L": fluoride},
        ],
    }


def sample_for(req, kind, ion_index=None, threshold_index=None):
    result = solve_solubility_equilibrium(req)
    state = {"unsaturated": "未饱和 · 可继续溶解", "saturated": "饱和 · 动态平衡",
             "supersaturated": "过饱和 · 有沉淀倾向"}[result["saturation_state"]]
    solubility = ("过饱和，当前不计算溶解度解" if result["molar_solubility_mol_L"] is None
                  else "%.8e mol/L" % result["molar_solubility_mol_L"])
    sample = {
        "kind": kind, "request": copy.deepcopy(req), "result": result,
        "controls": {"Ksp": req["Ksp"], "ion_indices": list(range(len(req["ions"]))),
                     "initial_concentrations_mol_L": [ion["initial_concentration_mol_L"]
                                                       for ion in req["ions"]]},
        "displayed_equation": result["dissolution_equation"],
        "displayed_q": "%.8e" % result["initial_ion_product"],
        "displayed_state": state, "displayed_solubility": solubility,
    }
    if ion_index is not None:
        sample["ion_index"] = ion_index
    if threshold_index is not None:
        sample["threshold_index"] = threshold_index
    return sample


def canonical_samples(req):
    base = solve_solubility_equilibrium(req)
    ksp_request = copy.deepcopy(req)
    ksp_request["Ksp"] *= 2
    samples = [sample_for(ksp_request, "ksp-increase")]
    common_request = copy.deepcopy(req)
    common_request["ions"][0]["initial_concentration_mol_L"] = base["molar_solubility_mol_L"]
    samples.append(sample_for(common_request, "common-ion-increase", ion_index=0))
    threshold = req["Ksp"] ** (1 / sum(ion["coefficient"] for ion in req["ions"]))
    for kind, factor in (("saturation-below", 0.95), ("saturation-at", 1), ("saturation-above", 1.05)):
        threshold_request = copy.deepcopy(req)
        for ion in threshold_request["ions"]:
            ion["initial_concentration_mol_L"] = threshold
        threshold_request["ions"][0]["initial_concentration_mol_L"] *= factor
        samples.append(sample_for(threshold_request, kind, threshold_index=0))
    return samples


class SolubilityEquilibriumPipelineTests(unittest.TestCase):
    def setUp(self):
        self.request = request()
        self.result = solve_solubility_equilibrium(self.request)
        self.samples = canonical_samples(self.request)

    def machine(self, result=None, samples=None, controls=None, displayed=None):
        shown = displayed or {
            "equation": self.result["dissolution_equation"],
            "q": "%.8e" % self.result["initial_ion_product"],
            "state": "未饱和 · 可继续溶解",
            "solubility": "%.8e mol/L" % self.result["molar_solubility_mol_L"],
        }
        return {
            "CHEM_KSP_REQUEST": self.request,
            "CHEM_KSP_RESULT": self.result if result is None else result,
            "CHEM_KSP_CONTROLS": controls or {
                "Ksp": self.request["Ksp"], "ion_indices": [0, 1],
                "initial_concentrations_mol_L": [0.0, 0.0]},
            "CHEM_KSP_DISPLAYED_EQUATION": shown["equation"],
            "CHEM_KSP_DISPLAYED_Q": shown["q"],
            "CHEM_KSP_DISPLAYED_STATE": shown["state"],
            "CHEM_KSP_DISPLAYED_SOLUBILITY": shown["solubility"],
            "CHEM_KSP_SAMPLES": self.samples if samples is None else samples,
        }

    def judge(self, **overrides):
        machine = self.machine(**overrides)
        context = {
            "machine": machine, "text": "CaF2 溶解平衡与 Ksp 共同离子效应",
            "topic": "溶解平衡和溶度积计算",
            "chem_ksp_oracle": {"result": solve_solubility_equilibrium(self.request)},
            "chem_ksp_sample_oracles": [
                {"sample": sample, "oracle": {"result": solve_solubility_equilibrium(sample["request"])}}
                for sample in machine["CHEM_KSP_SAMPLES"]
            ],
        }
        return next(item for item in judges.j3_conservation(context)
                    if item["check_id"] == "J3-13")

    def test_scene_selection_generation_contract_and_offline_bundle(self):
        req = {"学科": "化学", "实验主题": "CaF2溶解平衡与Ksp共同离子效应"}
        scene = scene_registry.select_page_skeleton(req)
        self.assertEqual(scene["id"], "chemistry-solubility-ksp")
        self.assertEqual(scene["solver_api"], "CHEMSOLVER.solveSolubilityEquilibrium")
        sections = {key: "占位" for key in ("1", "2", "3", "4", "5", "6")}
        sections["2"] = ('<canvas data-visual-type="apparatus"></canvas>'
                          '<output data-chem-ksp-equation></output>'
                          '<output data-chem-ksp-expression></output>'
                          '<output data-chem-ksp-ion-product></output>'
                          '<output data-chem-ksp-state></output>'
                          '<output data-chem-ksp-solubility></output>')
        sections["3"] = ('<input type="number" min="1e-80" step="any" data-chem-ksp-value>'
                          '<input type="number" min="0" step="any" data-chem-ksp-ion-index="0">'
                          '<input type="number" min="0" step="any" data-chem-ksp-ion-index="1">')
        sections["js"] = "CHEMSOLVER.solveSolubilityEquilibrium(request);"
        self.assertTrue(any("__CHEM_KSP_REQUEST__" in issue
                            for issue in generator_agent.hard_validate(sections, req)))
        sections["js"] = """
          var result = CHEMSOLVER.solveSolubilityEquilibrium(request);
          window.__CHEM_KSP_REQUEST__ = request;
          window.__CHEM_KSP_RESULT__ = result;
          equation.textContent = result.dissolution_equation;
          expression.textContent = 'Q = Π[cᵢ]ᵛⁱ';
          q.textContent = result.initial_ion_product;
          state.textContent = result.saturation_state;
          solubility.textContent = result.molar_solubility_mol_L;
          if (result.checks.ok) CHEM.solubility(cv,result);
        """
        problems = generator_agent.hard_validate(sections, req)
        self.assertFalse(any("Ksp 页面" in issue for issue in problems), problems)
        bundle = shell._with_libs("CHEMSOLVER.solveSolubilityEquilibrium(request); CHEM.solubility(cv,result);")
        self.assertIn("solveSolubilityEquilibrium", bundle)
        self.assertIn("solubility", bundle)
        self.assertNotIn("<script src=", bundle)

        sections["js"] += "\nequation.textContent = result.dissolution_equation + ' | Q expression';"
        problems = generator_agent.hard_validate(sections, req)
        self.assertTrue(any("方程元素必须只显示" in issue for issue in problems), problems)

    def test_shell_accepts_iife_root_namespace_export(self):
        sections = {key: "<div></div>" for key in ("1", "2", "3", "4", "5", "6")}
        sections["js"] = "CHEMSOLVER.solveSolubilityEquilibrium(request);"
        html = shell.render("Ksp", sections)
        self.assertTrue(shell._namespace_exported(html, "CHEMSOLVER"))
        self.assertFalse(any("CHEMSOLVER" in issue and "没有注入" in issue
                             for issue in shell.validate(html)))

    def test_j3_13_accepts_valid_baseline_and_five_metamorphic_samples(self):
        self.assertEqual(self.judge()["status"], "pass")

    def test_j3_parses_ui_scientific_notation_with_caret_and_superscript_exponents(self):
        def ui_number(value):
            if value == 0:
                return "0"
            exponent = math.floor(math.log10(abs(value)))
            mantissa = value / (10 ** exponent)
            return "%.2f×10^%d" % (mantissa, exponent)

        samples = copy.deepcopy(self.samples)
        for sample in samples:
            expected = solve_solubility_equilibrium(sample["request"])
            sample["displayed_q"] = ui_number(expected["initial_ion_product"])
            solubility = expected["molar_solubility_mol_L"]
            sample["displayed_solubility"] = (
                "无定义（过饱和）" if solubility is None else ui_number(solubility) + " mol/L")
        displayed = {
            "equation": self.result["dissolution_equation"],
            "q": "0",
            "state": "不饱和",
            "solubility": ui_number(self.result["molar_solubility_mol_L"]) + " mol/L",
        }
        self.assertEqual(self.judge(samples=samples, displayed=displayed)["status"], "pass")

        samples[2]["displayed_q"] = "3.80×10⁻¹¹ mol³/L³"
        # The formatter above emits caret exponents; this check specifically
        # covers superscript minus/digits used by generated chemistry pages.
        self.assertEqual(self.judge(samples=samples, displayed=displayed)["status"], "pass")

    def test_independent_reviewer_detects_result_display_and_sample_tampering(self):
        altered = copy.deepcopy(self.result)
        altered["molar_solubility_mol_L"] *= 1.1
        self.assertEqual(self.judge(result=altered)["status"], "fail")
        displayed = {"equation": self.result["dissolution_equation"], "q": "1e-5",
                     "state": "未饱和", "solubility": "1e-5 mol/L"}
        self.assertEqual(self.judge(displayed=displayed)["status"], "fail")
        samples = copy.deepcopy(self.samples)
        samples[0]["displayed_q"] = "1e-4"
        self.assertEqual(self.judge(samples=samples)["status"], "fail")

    def test_j3_rejects_equation_element_mixed_with_explanation(self):
        displayed = {
            "equation": self.result["dissolution_equation"] + " ｜ Q = [Ca²⁺][F⁻]²",
            "q": "0", "state": "不饱和",
            "solubility": "%.8e mol/L" % self.result["molar_solubility_mol_L"],
        }
        check = self.judge(displayed=displayed)
        self.assertEqual(check["status"], "fail")
        self.assertIn("方程式", check["actual"])

        displayed["state"] = "过饱和"
        self.assertEqual(self.judge(displayed=displayed)["status"], "fail")

    def test_j3_requires_all_real_transformation_families(self):
        samples = self.samples[:-1]
        self.assertEqual(self.judge(samples=samples)["status"], "fail")
        samples = copy.deepcopy(self.samples)
        samples[1]["request"]["ions"][1]["initial_concentration_mol_L"] = 1e-5
        self.assertEqual(self.judge(samples=samples)["status"], "fail")

    def test_j3_accepts_chinese_state_synonyms_and_undefined_solubility(self):
        samples = copy.deepcopy(self.samples)
        labels = {"unsaturated": "不饱和", "saturated": "饱和", "supersaturated": "过饱和"}
        for sample in samples:
            state = solve_solubility_equilibrium(sample["request"])["saturation_state"]
            sample["displayed_state"] = labels[state]
            if state == "supersaturated":
                sample["displayed_solubility"] = "s 无定义（过饱和）"
        displayed = {"equation": self.result["dissolution_equation"],
                     "q": "0", "state": "不饱和", "solubility": "%.8e mol/L" % self.result["molar_solubility_mol_L"]}
        self.assertEqual(self.judge(samples=samples, displayed=displayed)["status"], "pass")

    def test_ksp_topic_does_not_trigger_solution_mixing_audit(self):
        context = {
            "machine": {"CHEM_KSP_REQUEST": self.request},
            "text": "溶液中离子浓度变化对溶解平衡的影响",
            "topic": "CaF2 的 Ksp 与共同离子效应",
        }
        self.assertFalse(any(item["check_id"] == "J3-08"
                             for item in judges.j3_conservation(context)))

        context["machine"]["CHEM_MIX_REQUEST"] = {}
        self.assertTrue(any(item["check_id"] == "J3-08"
                            for item in judges.j3_conservation(context)))

    def test_equal_score_selection_prefers_fewer_critical_and_failed_checks(self):
        first = {"轮次": 1, "总分": 75, "结论": "未通过", "严重问题数": 2, "失败项数": 2}
        second = {"轮次": 2, "总分": 75, "结论": "未通过", "严重问题数": 1, "失败项数": 1}
        self.assertTrue(run_pipeline.should_replace_best(first, second))
        self.assertFalse(run_pipeline.should_replace_best(second, first))

    def test_approved_round_beats_higher_scoring_rejected_round(self):
        approved = {"轮次": 1, "总分": 82, "结论": "通过", "严重问题数": 0, "失败项数": 0}
        rejected = {"轮次": 2, "总分": 99, "结论": "未通过", "严重问题数": 1, "失败项数": 1}
        self.assertFalse(run_pipeline.should_replace_best(approved, rejected))

    def test_page_metamorphic_gate_requires_ksp_page_mutation(self):
        machine = self.machine()
        page = {"machine": machine,
                "chemistryKsp": {"initial": {"request": self.request, "result": self.result}},
                "metamorphic": {"samples": [{"kind": "ksp-increase", "inputChanged": True,
                    "changedInputs": ["__CHEM_KSP_REQUEST__"],
                    "changedResponses": ["__CHEM_KSP_RESULT__"]}]}}
        check = reviewer.verify_solver_page_metamorphic(page, "CHEMSOLVER.solveSolubilityEquilibrium")
        self.assertTrue(check["ok"], check["actual"])
        machine["CHEM_KSP_SAMPLES"] = []
        check = reviewer.verify_solver_page_metamorphic(page, "CHEMSOLVER.solveSolubilityEquilibrium")
        self.assertFalse(check["ok"])
        self.assertIn("溶解平衡与 Ksp", check["missing"])


if __name__ == "__main__":
    unittest.main()
