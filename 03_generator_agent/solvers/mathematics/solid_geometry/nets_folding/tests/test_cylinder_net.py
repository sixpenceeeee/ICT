import copy
import glob
import json
import math
import os
import shutil
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from cylinder_net_solver import solve_cylinder_net


def find_node():
    paths = glob.glob(os.path.join(os.path.expanduser("~"), ".workbuddy", "binaries", "node", "versions", "*", "node.exe"))
    return paths[0] if paths else shutil.which("node")


def standard_request():
    radius, height = 2.0, 5.0
    return {"radius": radius, "height": height,
            "net": {"lateral_width": 2*math.pi*radius,
                    "lateral_height": height, "cap_radii": [radius, radius]},
            "segments": 24}


class CylinderNetTests(unittest.TestCase):
    def test_standard_net_matches_circumference_height_and_area(self):
        result = solve_cylinder_net(standard_request())
        self.assertTrue(result["valid"], result["reason"])
        self.assertAlmostEqual(result["circumference"], 4*math.pi)
        self.assertAlmostEqual(result["lateral_area"], 20*math.pi)
        self.assertAlmostEqual(result["cap_area"], 8*math.pi)
        self.assertAlmostEqual(result["surface_area"], 28*math.pi)
        self.assertAlmostEqual(result["net_area"], result["surface_area"])
        self.assertTrue(all(result["checks"].values()))

    def test_fold_mapping_produces_closed_top_and_bottom_rims(self):
        result = solve_cylinder_net(standard_request())
        bottom, top = result["surface_grid"]
        self.assertEqual(len(bottom), 25)
        self.assertEqual(len(top), 25)
        self.assertAlmostEqual(bottom[0][0], bottom[-1][0], places=12)
        self.assertAlmostEqual(bottom[0][1], bottom[-1][1], places=12)
        self.assertAlmostEqual(top[0][0], 2)
        self.assertAlmostEqual(top[0][2], 2.5)
        self.assertEqual(result["bottom_cap"]["center"], [0, 0, -2.5])

    def test_wrong_rectangle_dimensions_caps_and_area_are_rejected(self):
        request = standard_request()
        request["net"]["lateral_width"] *= 0.9
        result = solve_cylinder_net(request)
        self.assertFalse(result["valid"])
        self.assertFalse(result["checks"]["lateral_width_matches_circumference"])

        request = standard_request()
        request["net"]["lateral_height"] = 4
        self.assertFalse(solve_cylinder_net(request)["checks"]["lateral_height_matches_solid_height"])

        request = standard_request()
        request["net"]["cap_radii"][1] = 1.5
        result = solve_cylinder_net(request)
        self.assertFalse(result["valid"])
        self.assertFalse(result["checks"]["two_caps_match_radius"])
        self.assertFalse(result["checks"]["area_conserved"])

    def test_rejects_invalid_geometry_and_sampling_arguments(self):
        for request in (
            {"radius": 0, "height": 2, "net": {}},
            {"radius": math.inf, "height": 2, "net": {}},
            {"radius": 1, "height": 2, "net": {"lateral_width": 2*math.pi, "lateral_height": 2, "cap_radii": [1]}},
        ):
            with self.subTest(request=request), self.assertRaises(ValueError):
                solve_cylinder_net(request)
        for segments in (0, 7, 129, 8.5, "24"):
            request = standard_request()
            request["segments"] = segments
            with self.subTest(segments=segments), self.assertRaises(ValueError):
                solve_cylinder_net(request)

    def test_uniform_scaling_preserves_surface_relations(self):
        request = standard_request()
        scaled = copy.deepcopy(request)
        factor = 3
        scaled["radius"] *= factor
        scaled["height"] *= factor
        scaled["net"]["lateral_width"] *= factor
        scaled["net"]["lateral_height"] *= factor
        scaled["net"]["cap_radii"] = [r*factor for r in scaled["net"]["cap_radii"]]
        original = solve_cylinder_net(request)
        result = solve_cylinder_net(scaled)
        self.assertTrue(result["valid"])
        self.assertAlmostEqual(result["surface_area"], original["surface_area"]*factor**2)

    def test_generator_routes_and_reviewer_independently_recomputes(self):
        generator_dir = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
        sys.path.insert(0, generator_dir)
        from scene_registry import select_page_skeleton
        from generator_agent import hard_validate

        request = standard_request()
        page_request = {"学科": "数学", "实验主题": "圆柱侧面展开图与表面积"}
        skeleton = select_page_skeleton(page_request)
        self.assertEqual(skeleton["id"], "math-cylinder-net-unfolding")
        self.assertEqual(skeleton["solver_api"], "MATH.solveCylinderNet")
        js = ("function render(){var request=" + json.dumps(request) + ";"
              "var result=MATH.solveCylinderNet(request);"
              "window.__MATH_CYLINDER_NET_REQUEST__=request;"
              "window.__MATH_CYLINDER_NET_RESULT__=result;"
              "drawCylinder(result.surface_grid);window.__DATA__={};}")
        sections = {
            "1": "<h2>圆柱侧面展开图与表面积</h2>",
            "2": '<canvas data-visual-type="geometry"></canvas>',
            "3": '<div class="exp-field"></div>',
            "4": '<div class="exp-formula"></div>',
            "5": '<table class="exp-table"></table>',
            "6": "课堂说明",
            "js": js,
        }
        self.assertEqual(hard_validate(sections, page_request), [])

        reviewer_dir = os.path.abspath(os.path.join(generator_dir, "..", "04_review_agent"))
        sys.path.insert(0, reviewer_dir)
        from reviewer import verify_cylinder_net_samples
        result = solve_cylinder_net(request)
        report = verify_cylinder_net_samples({"cylinderNet": {"samples": [
            {"label": "initial", "request": request, "result": result}]}})
        self.assertTrue(report["ok"], report["actual"])

    @unittest.skipUnless(find_node(), "Node.js is not installed")
    def test_javascript_matches_python_for_valid_and_invalid_nets(self):
        repo = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
        cases = [standard_request()]
        wrong_width = standard_request()
        wrong_width["net"]["lateral_width"] *= .9
        cases.append(wrong_width)
        wrong_height = standard_request()
        wrong_height["net"]["lateral_height"] = 4
        cases.append(wrong_height)
        wrong_cap = standard_request()
        wrong_cap["net"]["cap_radii"][1] = 1.5
        cases.append(wrong_cap)
        source = r'''const fs=require('fs'),vm=require('vm');global.window={addEventListener(){}};global.document={readyState:'loading',addEventListener(){}};vm.runInThisContext(fs.readFileSync('frame/math.js','utf8'));const cases=JSON.parse(process.argv[1]);console.log(JSON.stringify(cases.map(q=>window.MATH.solveCylinderNet(q))));'''
        proc = subprocess.run([find_node(), "-e", source, json.dumps(cases)], cwd=repo, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        actual = json.loads(proc.stdout)
        for request, js_result in zip(cases, actual):
            py_result = solve_cylinder_net(request)
            with self.subTest(request=request):
                self.assertEqual(js_result["valid"], py_result["valid"])
                self.assertEqual(js_result["reason"], py_result["reason"])
                self.assertEqual(js_result["checks"], py_result["checks"])
                for key in ("circumference", "lateral_area", "cap_area", "surface_area", "net_area", "area_error"):
                    self.assertTrue(math.isclose(js_result[key], py_result[key], rel_tol=1e-9, abs_tol=1e-9))
                for js_ring, py_ring in zip(js_result["surface_grid"], py_result["surface_grid"]):
                    for js_point, py_point in zip(js_ring, py_ring):
                        for a, b in zip(js_point, py_point):
                            self.assertTrue(math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9))


if __name__ == "__main__":
    unittest.main()
