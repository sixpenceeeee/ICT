# -*- coding: utf-8 -*-
"""凸透镜求解器的独立单测：五种情形、u=f、虚像、光屏清晰度与非法输入。"""
import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '03_generator_agent' / 'solvers'))

import optics_solver  # noqa: E402


def model(f=10.0, u=30.0, h=2.0, s=15.0):
    return {"f": f, "u": u, "h": h, "screen": {"s": s}}


class OpticsSolverTests(unittest.TestCase):
    def test_u_gt_2f(self):
        r = optics_solver.solve_optics(model(f=10, u=30))
        self.assertAlmostEqual(r["v"], 15.0)
        self.assertAlmostEqual(r["m"], -0.5)
        self.assertEqual(r["kind"], "real")
        self.assertEqual(r["uClass"], "u>2f")
        self.assertEqual(r["kindText"], "倒立·缩小·实像")
        self.assertTrue(r["checks"]["ok"])

    def test_u_eq_2f(self):
        r = optics_solver.solve_optics(model(f=10, u=20, s=20))
        self.assertAlmostEqual(r["v"], 20.0)
        self.assertAlmostEqual(r["m"], -1.0)
        self.assertEqual(r["uClass"], "u=2f")
        self.assertEqual(r["kindText"], "倒立·等大·实像")

    def test_between_f_and_2f(self):
        r = optics_solver.solve_optics(model(f=10, u=15, s=30))
        self.assertAlmostEqual(r["v"], 30.0)
        self.assertAlmostEqual(r["m"], -2.0)
        self.assertEqual(r["uClass"], "f<u<2f")
        self.assertEqual(r["kindText"], "倒立·放大·实像")

    def test_u_eq_f_has_no_image(self):
        r = optics_solver.solve_optics(model(f=10, u=10, s=15))
        self.assertEqual(r["kind"], "none")
        self.assertIsNone(r["v"])
        self.assertIsNone(r["m"])
        self.assertEqual(r["kindText"], "不成像")
        self.assertIn("不成像", r["onScreen"]["reason"])
        # u=f 时第三条特殊光线退化，只画两条
        self.assertEqual([ray["id"] for ray in r["rays"]], ["parallel", "center"])
        self.assertTrue(r["checks"]["ok"])

    def test_u_lt_f_virtual_image_never_on_screen(self):
        r = optics_solver.solve_optics(model(f=10, u=5, s=15))
        self.assertAlmostEqual(r["v"], -10.0)
        self.assertAlmostEqual(r["m"], 2.0)
        self.assertEqual(r["kind"], "virtual")
        self.assertEqual(r["uClass"], "u<f")
        self.assertEqual(r["kindText"], "正立·放大·虚像")
        self.assertFalse(r["onScreen"]["sharp"])
        self.assertIn("虚像", r["onScreen"]["reason"])
        # 三条光线都要有反向延长线，且都指向虚像点
        self.assertEqual(len(r["rays"]), 3)
        for ray in r["rays"]:
            self.assertTrue(ray["dashed"])
            self.assertAlmostEqual(ray["dashed"][-1][0], -10.0)
            self.assertAlmostEqual(ray["dashed"][-1][1], 4.0)

    def test_screen_off_image_is_blurred(self):
        r = optics_solver.solve_optics(model(f=10, u=30, s=20))
        self.assertEqual(r["kind"], "real")
        self.assertFalse(r["onScreen"]["sharp"])
        self.assertAlmostEqual(r["onScreen"]["blur"], 5.0)

    def test_screen_on_image_is_sharp(self):
        r = optics_solver.solve_optics(model(f=10, u=30, s=15))
        self.assertTrue(r["onScreen"]["sharp"])
        self.assertAlmostEqual(r["onScreen"]["blur"], 0.0)

    def test_near_focal_point_is_treated_as_no_image(self):
        u = 10.0 * (1 + 1e-9)
        r = optics_solver.solve_optics(model(f=10, u=u))
        self.assertEqual(r["kind"], "none")

    def test_just_outside_focal_point_is_finite_but_offscene(self):
        r = optics_solver.solve_optics(model(f=10, u=10.01, s=15))
        self.assertEqual(r["kind"], "real")
        self.assertAlmostEqual(r["v"], 10.0 * 10.01 / 0.01, places=6)
        self.assertTrue(r["image"]["offscene"])
        self.assertTrue(math.isfinite(r["v"]))

    def test_ray_geometry(self):
        r = optics_solver.solve_optics(model(f=10, u=30, s=15))
        x_right = 50.0  # min(400, max(15, 20, 40) + 10)
        rays = {ray["id"]: ray for ray in r["rays"]}
        self.assertAlmostEqual(rays["parallel"]["solid"][-1][0], x_right)
        self.assertAlmostEqual(rays["parallel"]["solid"][-1][1], 2.0 - 2.0 * x_right / 10.0)
        self.assertAlmostEqual(rays["center"]["solid"][-1][1], -2.0 * x_right / 30.0)
        self.assertAlmostEqual(rays["focus"]["solid"][1][1], -2.0 * 10.0 / (30.0 - 10.0))
        # 实像不需要反向延长线
        self.assertTrue(all(not ray["dashed"] for ray in r["rays"]))

    def test_invalid_inputs_are_rejected(self):
        bad_models = [
            model(f=0),
            model(f=-1),
            model(u=0),
            model(u=-5),
            model(h=0),
            model(s=-1),
            {"f": float("nan"), "u": 30, "h": 2, "screen": {"s": 15}},
            {"f": 10, "u": float("inf"), "h": 2, "screen": {"s": 15}},
            {"f": True, "u": 30, "h": 2, "screen": {"s": 15}},
            {"u": 30},
        ]
        for bad in bad_models:
            with self.assertRaises(optics_solver.OpticsError):
                optics_solver.solve_optics(bad)


if __name__ == '__main__':
    unittest.main()
