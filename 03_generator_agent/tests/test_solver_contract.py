# -*- coding: utf-8 -*-
"""求解器契约守卫。

这一组测试回答一个问题：**新增/修改求解器后，页面生成还会不会带着问题出门？**

它强制检查：
1. 每个教学模型求解器都有专用自检（不能退化成“只查有限数值”的通用自检）；
2. 每个验收 case 的自检通过，且结果里的每个声明字段都存在、都是有限值；
3. 变形关系引用的 case / 字段真实存在；
4. 每个场景声明的学科求解器都能在 Python 侧找到参考实现；
5. 自检本身不是空的（篡改结果必须被抓到）。
"""
import copy
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
GENERATOR = os.path.abspath(os.path.join(HERE, ".."))
PROJECT = os.path.abspath(os.path.join(GENERATOR, ".."))
SOLVER_ROOT = os.path.join(GENERATOR, "solvers")
for path in (PROJECT, GENERATOR, SOLVER_ROOT):
    if path not in sys.path:
        sys.path.insert(0, path)

import solver_contract
import physics_audits   # noqa: F401  注册物理自检
import math_audits      # noqa: F401  注册数学自检
import geometry_audits  # noqa: F401  注册几何/二次函数/透镜自检

import scene_registry
from mathematics.lesson_models import SOLVERS as MATH_SOLVERS
from mathematics.quadratic_solver import solve_quadratic
from physics.lesson_models import SOLVERS as PHYSICS_SOLVERS
from physics.thin_lens_solver import solve_thin_lens


def load_models(family):
    with open(os.path.join(SOLVER_ROOT, family, "lesson_models.json"), encoding="utf-8") as handle:
        return json.load(handle)


PHYSICS_MODELS = load_models("physics")
MATH_MODELS = load_models("mathematics")
LESSON_MODELS = [(family, key, model)
                 for family, models in (("physics", PHYSICS_MODELS), ("mathematics", MATH_MODELS))
                 for key, model in models.items()]


class SolverSelfCheckTests(unittest.TestCase):
    def test_every_lesson_solver_has_a_dedicated_self_check(self):
        missing = [model["api"] for _, _, model in LESSON_MODELS
                   if not solver_contract.has_specific_audit(model["api"])]
        self.assertEqual([], missing, "缺少专用自检的求解器：%s" % "、".join(missing))

    def test_special_purpose_solvers_have_self_checks(self):
        for api in ("solveQuadratic", "solveThinLens"):
            self.assertTrue(solver_contract.has_specific_audit(api), api)

    def test_all_acceptance_cases_pass_self_check(self):
        failures = []
        for family, key, model in LESSON_MODELS:
            solvers = PHYSICS_SOLVERS if family == "physics" else MATH_SOLVERS
            for case_name, case in model["cases"].items():
                result = solvers[model["api"]](dict(case))
                report = solver_contract.audit(model["api"], dict(case), result)
                if not report["ok"]:
                    failures.append("%s/%s:%s -> %s" % (family, key, case_name,
                                                        "；".join(report["failures"][:4])))
        self.assertEqual([], failures, "\n".join(failures))

    def test_declared_fields_are_present_and_finite(self):
        failures = []
        for family, key, model in LESSON_MODELS:
            solvers = PHYSICS_SOLVERS if family == "physics" else MATH_SOLVERS
            for case_name, case in model["cases"].items():
                result = solvers[model["api"]](dict(case))
                for field in model["fields"]:
                    if field not in result:
                        failures.append("%s/%s:%s 缺少字段 %s" % (family, key, case_name, field))
                bad = solver_contract.non_finite_paths(
                    {name: value for name, value in result.items() if name != "checks"})
                if bad:
                    failures.append("%s/%s:%s 非有限数值 %s" % (family, key, case_name, "、".join(bad)))
        self.assertEqual([], failures, "\n".join(failures))

    def test_metamorphic_relations_reference_real_cases_and_fields(self):
        missing = object()

        def resolve(result, path):
            value = result
            for part in str(path).split("."):
                if isinstance(value, dict):
                    value = value.get(part, missing)
                elif isinstance(value, (list, tuple)) and part.isdecimal() and int(part) < len(value):
                    value = value[int(part)]
                else:
                    return missing
            return value

        failures = []
        for family, key, model in LESSON_MODELS:
            solvers = PHYSICS_SOLVERS if family == "physics" else MATH_SOLVERS
            results = {name: solvers[model["api"]](dict(case))
                       for name, case in model["cases"].items()}
            for relation in model.get("relations", []):
                if len(relation) not in (3, 5):
                    failures.append("%s/%s 关系格式不合法：%r" % (family, key, relation))
                    continue
                case, field = relation[0], relation[1]
                if case not in results:
                    failures.append("%s/%s 关系引用了不存在的 case %s" % (family, key, case))
                elif resolve(results[case], field) is missing:
                    failures.append("%s/%s 关系字段无法解析 %s" % (family, key, field))
                if len(relation) == 5:
                    baseline, baseline_field = relation[2], relation[3]
                    if baseline not in results:
                        failures.append("%s/%s 关系基线 case 不存在 %s" % (family, key, baseline))
                    elif resolve(results[baseline], baseline_field) is missing:
                        failures.append("%s/%s 关系基线字段无法解析 %s" % (family, key, baseline_field))
        self.assertEqual([], failures, "\n".join(failures))

    def test_self_check_catches_tampered_results(self):
        request = {"fraction": 0.2, "object_density": 800, "liquid_density": 1000,
                   "volume": 0.001, "mode": "hang"}
        result = PHYSICS_SOLVERS["solveBuoyancy"](dict(request))
        tampered = copy.deepcopy(result)
        tampered["buoyancy"] = tampered["buoyancy"] * 1.5
        self.assertFalse(solver_contract.audit("solveBuoyancy", request, tampered)["ok"])

        sampling_request = {"good": 3, "bad": 2, "draws": 2, "hits": 1, "mode": "without"}
        sampling = MATH_SOLVERS["solveSampling"](dict(sampling_request))
        broken = copy.deepcopy(sampling)
        broken["probabilities"] = [0.5, 0.5, 0.5]
        self.assertFalse(solver_contract.audit("solveSampling", sampling_request, broken)["ok"])


class SceneContractTests(unittest.TestCase):
    def test_every_registered_lesson_model_has_a_scene(self):
        ids = {scene["id"] for scene in scene_registry.SCENE_SKELETONS}
        missing = []
        for family, key, model in LESSON_MODELS:
            if family == "physics" and key == "thinLens":
                scene_id = "physics-thin-lens"   # 凸透镜由专用骨架承载
            else:
                scene_id = ("physics-" if family == "physics" else "math-") + key
            if scene_id not in ids:
                missing.append(scene_id)
        self.assertEqual([], missing, "未注册为场景的教学模型：%s" % "、".join(missing))

    def test_every_scene_solver_has_a_reference_implementation(self):
        import math_geometry_templates as geometry

        geometry_apis = {model["api"] for model in geometry.GEOMETRY_MODELS.values()
                         if model.get("api")}
        known = {"CIRCUIT.solve", None, ""}
        missing = []
        for scene in scene_registry.SCENE_SKELETONS:
            api = scene.get("solver_api")
            if not api or api in known or api.startswith("CHEMSOLVER."):
                continue
            namespace, _, name = api.partition(".")
            if namespace == "PHYS":
                if name != "solveThinLens" and name not in PHYSICS_SOLVERS:
                    missing.append(api)
            elif namespace == "MATH":
                if (name != "solveQuadratic" and name not in MATH_SOLVERS
                        and name not in geometry_apis):
                    missing.append(api)
            else:
                missing.append(api)
        self.assertEqual([], missing, "场景声明了没有参考实现的求解器：%s" % "、".join(sorted(set(missing))))

    def test_geometry_models_pass_self_check(self):
        import math_geometry_templates as geometry

        failures = []
        for key, model in geometry.GEOMETRY_MODELS.items():
            reference = model.get("reference")
            if reference is None:
                continue
            for case_name, case in model["cases"].items():
                result = reference(dict(case))
                if result is None:  # 展开图需要页面端适配器把控件状态拼成请求
                    continue
                report = solver_contract.audit(model["api"], dict(case), result)
                if not report["ok"]:
                    failures.append("%s:%s -> %s" % (key, case_name, "；".join(report["failures"][:4])))
        self.assertEqual([], failures, "\n".join(failures))


if __name__ == "__main__":
    unittest.main(verbosity=2)
