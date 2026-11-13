# -*- coding: utf-8 -*-
"""页面端 JS 求解器与 Python 参考实现的逐字段对拍。

同一个场景有两套实现：`frame/` 下给浏览器用，`solvers/` 下给审查端用。
只要两边漂移，页面就会出现“算对了但显示错”或“审查端与页面各说各话”。
这里用 Node 直接加载页面端场景库，把每个验收 case 的结果与 Python 对拍，
不需要启动浏览器，几秒内就能发现漂移。
"""
import json
import math
import os
import shutil
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
GENERATOR = os.path.abspath(os.path.join(HERE, ".."))
PROJECT = os.path.abspath(os.path.join(GENERATOR, ".."))
SOLVER_ROOT = os.path.join(GENERATOR, "solvers")
for path in (PROJECT, GENERATOR, SOLVER_ROOT):
    if path not in sys.path:
        sys.path.insert(0, path)

from mathematics.lesson_models import SOLVERS as MATH_SOLVERS
from physics.lesson_models import SOLVERS as PHYSICS_SOLVERS

NODE = shutil.which("node")
PARITY_SCRIPT = os.path.join(PROJECT, "tools", "solver_parity.js")


def same(left, right):
    if left is None or right is None:
        return left is None and right is None
    if isinstance(left, str) or isinstance(right, str):
        return left == right
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right
    if isinstance(left, (list, tuple)):
        return (isinstance(right, (list, tuple)) and len(left) == len(right)
                and all(same(a, b) for a, b in zip(left, right)))
    try:
        return math.isclose(float(left), float(right), rel_tol=1e-9, abs_tol=1e-9)
    except (TypeError, ValueError):
        return False


@unittest.skipUnless(NODE and os.path.exists(PARITY_SCRIPT), "需要 Node.js 与 tools/solver_parity.js")
class SolverJsParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 直接读 stdout，避免在受限环境里创建临时目录。
        completed = subprocess.run(
            [NODE, PARITY_SCRIPT], cwd=PROJECT, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=180)
        if completed.returncode != 0:
            raise AssertionError("solver_parity.js 执行失败：\n%s\n%s"
                                 % (completed.stdout[-2000:], completed.stderr[-2000:]))
        cls.data = json.loads(completed.stdout)

    def test_every_page_solver_loads(self):
        failures = [key + ":" + sample["case"] + " " + str(sample.get("error"))
                    for key, samples in self.data.items() for sample in samples if not sample["ok"]]
        self.assertEqual([], failures, "\n".join(failures))

    def test_page_results_match_python_reference(self):
        failures = []
        for key, samples in self.data.items():
            family = "physics" if key.startswith("PHYS.") else "mathematics"
            api = key.split(".", 1)[1]
            solvers = PHYSICS_SOLVERS if family == "physics" else MATH_SOLVERS
            with open(os.path.join(SOLVER_ROOT, family, "lesson_models.json"), encoding="utf-8") as handle:
                models = json.load(handle)
            model = next(item for item in models.values() if item["api"] == api)
            for sample in samples:
                if not sample["ok"]:
                    continue
                expected = solvers[api](dict(model["cases"][sample["case"]]))
                actual = sample["result"]
                for field, value in expected.items():
                    if field in ("checks", "version"):
                        continue
                    if field not in actual:
                        failures.append("%s/%s 页面端缺少字段 %s" % (key, sample["case"], field))
                    elif not same(value, actual[field]):
                        failures.append("%s/%s 字段 %s：Python=%r，页面=%r"
                                        % (key, sample["case"], field, value, actual[field]))
        self.assertEqual([], failures, "\n".join(failures))


if __name__ == "__main__":
    unittest.main(verbosity=2)
