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
from cone_net_solver import solve_cone_net


def find_node():
    paths = glob.glob(os.path.join(os.path.expanduser("~"), ".workbuddy", "binaries", "node", "versions", "*", "node.exe"))
    return paths[0] if paths else shutil.which("node")


def standard_request():
    radius, height, slant = 3.0, 4.0, 5.0
    return {"radius": radius, "height": height,
            "net": {"sector_radius": slant, "sector_angle_deg": 360*radius/slant,
                    "cap_radius": radius}, "segments": 24}


class ConeNetTests(unittest.TestCase):
    def test_standard_net_matches_slant_arc_and_surface_area(self):
        result = solve_cone_net(standard_request())
        self.assertTrue(result["valid"], result["reason"])
        self.assertAlmostEqual(result["slant_height"], 5)
        self.assertAlmostEqual(result["expected_sector_angle_deg"], 216)
        self.assertAlmostEqual(result["sector_arc_length"], 6*math.pi)
        self.assertAlmostEqual(result["base_circumference"], 6*math.pi)
        self.assertAlmostEqual(result["lateral_area"], 15*math.pi)
        self.assertAlmostEqual(result["cap_area"], 9*math.pi)
        self.assertAlmostEqual(result["surface_area"], 24*math.pi)
        self.assertAlmostEqual(result["net_area"], result["surface_area"])
        self.assertTrue(all(result["checks"].values()))

    def test_planar_sector_and_folded_cone_mesh_are_returned(self):
        result = solve_cone_net(standard_request())
        self.assertEqual(len(result["sector_boundary"]), 26)
        self.assertEqual(len(result["base_boundary"]), 25)
        bottom, apex = result["side_grid"]
        self.assertEqual(len(bottom), 25)
        self.assertEqual(len(apex), 25)
        self.assertEqual(apex[0], [0, 0, 2])
        self.assertAlmostEqual(bottom[0][0], 3)
        self.assertAlmostEqual(bottom[0][2], -2)
        self.assertEqual(result["base_cap"]["center"], [0, 0, -2])

    def test_wrong_sector_radius_angle_and_base_radius_are_rejected(self):
        request = standard_request()
        request["net"]["sector_radius"] = 4.8
        result = solve_cone_net(request)
        self.assertFalse(result["valid"])
        self.assertFalse(result["checks"]["sector_radius_matches_slant_height"])

        request = standard_request()
        request["net"]["sector_angle_deg"] = 200
        self.assertFalse(solve_cone_net(request)["checks"]["sector_arc_matches_base_circumference"])

        request = standard_request()
        request["net"]["cap_radius"] = 2.5
        result = solve_cone_net(request)
        self.assertFalse(result["valid"])
        self.assertFalse(result["checks"]["cap_radius_matches_base"])
        self.assertFalse(result["checks"]["area_conserved"])

    def test_rejects_invalid_geometry_angle_and_sampling_arguments(self):
        for request in (
            {"radius": 0, "height": 2, "net": {}},
            {"radius": math.inf, "height": 2, "net": {}},
            {"radius": 1, "height": 2, "net": {"sector_radius": 3, "sector_angle_deg": 360, "cap_radius": 1}},
        ):
            with self.subTest(request=request), self.assertRaises(ValueError):
                solve_cone_net(request)
        for segments in (0, 7, 129, 8.5, "24"):
            request = standard_request()
            request["segments"] = segments
            with self.subTest(segments=segments), self.assertRaises(ValueError):
                solve_cone_net(request)

    def test_uniform_scaling_preserves_angles_and_scales_areas_quadratically(self):
        request = standard_request()
        scaled = copy.deepcopy(request)
        factor = 2.5
        scaled["radius"] *= factor
        scaled["height"] *= factor
        scaled["net"]["sector_radius"] *= factor
        scaled["net"]["cap_radius"] *= factor
        original = solve_cone_net(request)
        result = solve_cone_net(scaled)
        self.assertTrue(result["valid"])
        self.assertAlmostEqual(result["net"]["sector_angle_deg"], original["net"]["sector_angle_deg"])
        self.assertAlmostEqual(result["surface_area"], original["surface_area"]*factor**2)

    def test_generator_routes_and_reviewer_independently_recomputes(self):
        generator_dir = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
        sys.path.insert(0, generator_dir)
        from scene_registry import select_page_skeleton
        from generator_agent import hard_validate

        request = standard_request()
        page_request = {"学科": "数学", "实验主题": "圆锥展开图与侧面积"}
        skeleton = select_page_skeleton(page_request)
        self.assertEqual(skeleton["id"], "math-cone-net-unfolding")
        self.assertEqual(skeleton["solver_api"], "MATH.solveConeNet")
        js = ("function render(){var request=" + json.dumps(request) + ";"
              "var result=MATH.solveConeNet(request);"
              "window.__MATH_CONE_NET_REQUEST__=request;"
              "window.__MATH_CONE_NET_RESULT__=result;"
              "drawCone(result.side_grid,result.sector_boundary);window.__DATA__={};}")
        sections = {
            "1": "<h2>圆锥展开图与侧面积</h2>",
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
        from reviewer import verify_cone_net_samples
        result = solve_cone_net(request)
        report = verify_cone_net_samples({"coneNet": {"samples": [
            {"label": "initial", "request": request, "result": result}]}})
        self.assertTrue(report["ok"], report["actual"])

    @unittest.skipUnless(find_node(), "Node.js is not installed")
    def test_javascript_matches_python_for_valid_and_invalid_nets(self):
        repo = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
        cases = [standard_request()]
        wrong_radius = standard_request()
        wrong_radius["net"]["sector_radius"] = 4.8
        cases.append(wrong_radius)
        wrong_angle = standard_request()
        wrong_angle["net"]["sector_angle_deg"] = 200
        cases.append(wrong_angle)
        wrong_cap = standard_request()
        wrong_cap["net"]["cap_radius"] = 2.5
        cases.append(wrong_cap)
        source = r'''const fs=require('fs'),vm=require('vm');global.window={addEventListener(){}};global.document={readyState:'loading',addEventListener(){}};vm.runInThisContext(fs.readFileSync('frame/math.js','utf8'));const cases=JSON.parse(process.argv[1]);console.log(JSON.stringify(cases.map(q=>window.MATH.solveConeNet(q))));'''
        proc = subprocess.run([find_node(), "-e", source, json.dumps(cases)], cwd=repo, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        actual = json.loads(proc.stdout)
        for request, js_result in zip(cases, actual):
            py_result = solve_cone_net(request)
            with self.subTest(request=request):
                self.assertEqual(js_result["valid"], py_result["valid"])
                self.assertEqual(js_result["reason"], py_result["reason"])
                self.assertEqual(js_result["checks"], py_result["checks"])
                for key in ("slant_height", "expected_sector_angle_deg", "sector_arc_length",
                            "lateral_area", "cap_area", "surface_area", "sector_area",
                            "net_area", "area_error"):
                    self.assertTrue(math.isclose(js_result[key], py_result[key], rel_tol=1e-9, abs_tol=1e-9))
                for js_rows, py_rows in ((js_result["sector_boundary"], py_result["sector_boundary"]),
                                         (js_result["base_boundary"], py_result["base_boundary"])):
                    for js_point, py_point in zip(js_rows, py_rows):
                        for a, b in zip(js_point, py_point):
                            self.assertTrue(math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9))


if __name__ == "__main__":
    unittest.main()
