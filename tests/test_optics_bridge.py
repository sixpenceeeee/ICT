# -*- coding: utf-8 -*-
"""JS ↔ Python 求解器一致性：同一份模型两边算出的结果必须一致。

这条测试的存在理由与 circuit 线相同：页面里的 JS 求解器与审查端的 Python
求解器是两份独立实现，只测各自单测并不能证明它们对同一模型给同一个答案。
"""
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '03_generator_agent' / 'solvers'))

import optics_solver  # noqa: E402

BRIDGE = ROOT / 'tools' / 'optics_bridge.js'
NODE = shutil.which('node')

CASES = [
    {"f": 10, "u": 30, "h": 2, "screen": {"s": 15}},
    {"f": 10, "u": 20, "h": 2, "screen": {"s": 20}},
    {"f": 10, "u": 15, "h": 2, "screen": {"s": 30}},
    {"f": 10, "u": 10, "h": 2, "screen": {"s": 15}},
    {"f": 10, "u": 5, "h": 2, "screen": {"s": 15}},
    {"f": 8, "u": 40, "h": 3, "screen": {"s": 10}},
    {"f": 20, "u": 12, "h": 1.5, "screen": {"s": 30}},
    {"f": 10, "u": 10.01, "h": 2, "screen": {"s": 15}},
]


def js_solve(model):
    proc = subprocess.run(
        [NODE, str(BRIDGE)],
        input=json.dumps(model),
        capture_output=True, text=True, encoding='utf-8', timeout=60,
    )
    if proc.returncode != 0:
        raise AssertionError('node bridge 失败：%s' % (proc.stdout or proc.stderr))
    return json.loads(proc.stdout)


def close(a, b, rel=1e-12, abs_tol=1e-12):
    if a is None or b is None:
        return a is None and b is None
    return math.isclose(a, b, rel_tol=rel, abs_tol=abs_tol)


@unittest.skipIf(NODE is None, '本机没有 node，跳过 JS↔Python 对拍')
class OpticsBridgeParityTests(unittest.TestCase):
    def assert_points(self, left, right, label):
        self.assertEqual(len(left), len(right), label)
        for p1, p2 in zip(left, right):
            self.assertEqual(len(p1), len(p2), label)
            for a, b in zip(p1, p2):
                self.assertTrue(close(a, b), '%s: %r != %r' % (label, p1, p2))

    def test_parity_on_all_cases(self):
        for model in CASES:
            with self.subTest(model=model):
                py = optics_solver.solve_optics(model)
                js = js_solve(model)
                for key in ('f', 'u', 'h', 's'):
                    self.assertTrue(close(py[key], js[key]), key)
                for key in ('kind', 'uClass', 'kindText', 'scene_id', 'schema_version'):
                    self.assertEqual(py[key], js[key], key)
                self.assertTrue(close(py['v'], js['v']), 'v')
                self.assertTrue(close(py['m'], js['m']), 'm')
                self.assertEqual(py['onScreen']['sharp'], js['onScreen']['sharp'])
                self.assertTrue(close(py['onScreen']['blur'], js['onScreen']['blur']), 'blur')
                self.assertEqual(py['checks']['ok'], js['checks']['ok'])
                self.assertTrue(close(py['checks']['gauss'], js['checks']['gauss']), 'gauss')
                self.assertEqual(len(py['rays']), len(js['rays']))
                for ray_py, ray_js in zip(py['rays'], js['rays']):
                    self.assertEqual(ray_py['id'], ray_js['id'])
                    self.assert_points(ray_py['solid'], ray_js['solid'], ray_py['id'] + '/solid')
                    self.assert_points(ray_py['dashed'], ray_js['dashed'], ray_py['id'] + '/dashed')
                if py['image'] is None:
                    self.assertIsNone(js['image'])
                else:
                    for key in ('x', 'y', 'h'):
                        self.assertTrue(close(py['image'][key], js['image'][key]), 'image.' + key)
                    self.assertEqual(py['image']['inverted'], js['image']['inverted'])
                    self.assertEqual(py['image']['offscene'], js['image']['offscene'])

    def test_js_rejects_invalid_model(self):
        strict = {"f": 0, "u": 30, "h": 2, "screen": {"s": 15}}
        with self.assertRaises(AssertionError):
            js_solve(strict)


if __name__ == '__main__':
    unittest.main()
