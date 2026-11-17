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
from cuboid_net_solver import solve_cuboid_net


def find_node():
    paths = glob.glob(os.path.join(os.path.expanduser("~"), ".workbuddy", "binaries", "node", "versions", "*", "node.exe"))
    return paths[0] if paths else shutil.which("node")


def standard_net():
    return {
        "dimensions": [4, 3, 2],
        "faces": [
            {"x": 0, "y": 0, "width": 4, "height": 3},
            {"x": -2, "y": 0, "width": 2, "height": 3},
            {"x": 4, "y": 0, "width": 2, "height": 3},
            {"x": 0, "y": -2, "width": 4, "height": 2},
            {"x": 0, "y": 3, "width": 4, "height": 2},
            {"x": 0, "y": -5, "width": 4, "height": 3},
        ],
    }


class CuboidNetTests(unittest.TestCase):
    def test_standard_rectangular_net_closes_to_six_cuboid_faces(self):
        result = solve_cuboid_net(standard_net())
        self.assertTrue(result["valid"], result["reason"])
        self.assertEqual(result["unique_face_normals"], 6)
        self.assertAlmostEqual(result["hinge_residual"], 0, places=10)
        self.assertTrue(all(result["checks"].values()))
        self.assertEqual(len(result["faces"]), 6)
        for face in result["faces"]:
            self.assertEqual(len(face["vertices"]), 4)
            self.assertIn(face["u_axis"], range(3))
            self.assertIn(face["v_axis"], range(3))
            self.assertNotEqual(face["u_axis"], face["v_axis"])

    def test_equal_dimensions_allow_cube_as_a_special_cuboid(self):
        cells = [(0, 0), (-1, 0), (1, 0), (2, 0), (0, 1), (0, -1)]
        request = {"dimensions": [2, 2, 2],
                   "faces": [{"x": x*2, "y": y*2, "width": 2, "height": 2} for x, y in cells]}
        self.assertTrue(solve_cuboid_net(request)["valid"])

    def test_root_face_can_have_swapped_axis_orientation(self):
        request = {"dimensions": [4, 3, 2], "faces": [
            {"x": 0, "y": 0, "width": 3, "height": 4},
            {"x": -2, "y": 0, "width": 2, "height": 4},
            {"x": 3, "y": 0, "width": 2, "height": 4},
            {"x": 0, "y": -2, "width": 3, "height": 2},
            {"x": 0, "y": 4, "width": 3, "height": 2},
            {"x": 0, "y": -6, "width": 3, "height": 4},
        ]}
        result = solve_cuboid_net(request)
        self.assertTrue(result["valid"], result["reason"])
        self.assertEqual(len({tuple(face["normal"]) for face in result["faces"]}), 6)

    def test_wrong_dimensions_partial_hinge_overlap_and_cycle_are_rejected(self):
        wrong_dimensions = standard_net()
        wrong_dimensions["dimensions"] = [4, 3, 3]
        self.assertEqual(solve_cuboid_net(wrong_dimensions)["reason"], "展开面尺寸与给定长、宽、高不匹配")

        partial = standard_net()
        partial["faces"][2]["height"] = 2
        self.assertEqual(solve_cuboid_net(partial)["reason"], "相邻面只有部分边接触，公共棱长度不一致")

        overlapping = standard_net()
        overlapping["faces"][2]["x"] = 3.5
        self.assertEqual(solve_cuboid_net(overlapping)["reason"], "展开图中矩形面发生面积重叠")

        cycle = {"dimensions": [1, 1, 1], "faces": [
            {"x": x, "y": y, "width": 1, "height": 1}
            for x, y in ((0, 0), (1, 0), (2, 0), (0, 1), (1, 1), (2, 1))]}
        result = solve_cuboid_net(cycle)
        self.assertFalse(result["valid"])
        self.assertFalse(result["tree"])
        self.assertEqual(result["hinge_count"], 7)

        row = {"dimensions": [1, 1, 1], "faces": [
            {"x": x, "y": 0, "width": 1, "height": 1} for x in range(6)]}
        row_result = solve_cuboid_net(row)
        self.assertFalse(row_result["valid"])
        self.assertEqual(row_result["reason"], "折叠后存在重合面")
        self.assertLess(row_result["unique_face_normals"], 6)

    def test_disconnected_faces_and_invalid_dimensions_are_rejected(self):
        disconnected = standard_net()
        disconnected["faces"][5]["x"] = 20
        self.assertFalse(solve_cuboid_net(disconnected)["connected"])
        for request in (
            {"dimensions": [1, 2], "faces": standard_net()["faces"]},
            {"dimensions": [1, 2, 0], "faces": standard_net()["faces"]},
            {"dimensions": [1, 2, 3], "faces": standard_net()["faces"][:5]},
            {"dimensions": [1, 2, 3], "faces": [{"x": 0, "y": 0, "width": 1}] * 6},
        ):
            with self.subTest(request=request), self.assertRaises(ValueError):
                solve_cuboid_net(request)

    def test_uniform_scale_preserves_topology_and_scales_space_coordinates(self):
        request = standard_net()
        scaled = copy.deepcopy(request)
        factor = 2.5
        scaled["dimensions"] = [x*factor for x in request["dimensions"]]
        for rect in scaled["faces"]:
            for key in rect:
                rect[key] *= factor
        original_result = solve_cuboid_net(request)
        scaled_result = solve_cuboid_net(scaled)
        self.assertTrue(scaled_result["valid"])
        for old, new in zip(original_result["faces"], scaled_result["faces"]):
            for a, b in zip(old["center"], new["center"]):
                self.assertAlmostEqual(b, factor*a)

    def test_generator_routes_cuboid_net_and_reviewer_refolds_independently(self):
        generator_dir = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
        sys.path.insert(0, generator_dir)
        from scene_registry import select_page_skeleton
        from generator_agent import hard_validate

        request = standard_net()
        page_request = {"学科": "数学", "实验主题": "长方体展开图与折叠"}
        skeleton = select_page_skeleton(page_request)
        self.assertEqual(skeleton["id"], "math-cuboid-net-folding")
        self.assertEqual(skeleton["solver_api"], "MATH.solveCuboidNet")
        js = ("function render(){var request=" + json.dumps(request) + ";"
              "var result=MATH.solveCuboidNet(request);"
              "window.__MATH_CUBOID_NET_REQUEST__=request;"
              "window.__MATH_CUBOID_NET_RESULT__=result;drawFaces(result.faces);window.__DATA__={};}")
        sections = {
            "1": "<h2>长方体展开图与折叠</h2>",
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
        from reviewer import verify_cuboid_net_samples
        expected = solve_cuboid_net(request)
        report = verify_cuboid_net_samples({"cuboidNet": {"samples": [
            {"label": "initial", "request": request, "result": expected}]}})
        self.assertTrue(report["ok"], report["actual"])

    @unittest.skipUnless(find_node(), "Node.js is not installed")
    def test_javascript_matches_python_for_valid_and_boundary_cases(self):
        repo = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
        cases = [standard_net()]
        cases.append({"dimensions": [4, 3, 2], "faces": [
            {"x": 0, "y": 0, "width": 3, "height": 4},
            {"x": -2, "y": 0, "width": 2, "height": 4},
            {"x": 3, "y": 0, "width": 2, "height": 4},
            {"x": 0, "y": -2, "width": 3, "height": 2},
            {"x": 0, "y": 4, "width": 3, "height": 2},
            {"x": 0, "y": -6, "width": 3, "height": 4},
        ]})
        mismatch = standard_net()
        mismatch["dimensions"] = [4, 3, 3]
        cases.append(mismatch)
        partial = standard_net()
        partial["faces"][2]["height"] = 2
        cases.append(partial)
        cycle = {"dimensions": [1, 1, 1], "faces": [
            {"x": x, "y": y, "width": 1, "height": 1}
            for x, y in ((0, 0), (1, 0), (2, 0), (0, 1), (1, 1), (2, 1))]}
        cases.append(cycle)
        cases.append({"dimensions": [1, 1, 1], "faces": [
            {"x": x, "y": 0, "width": 1, "height": 1} for x in range(6)]})
        source = r'''const fs=require('fs'),vm=require('vm');global.window={addEventListener(){}};global.document={readyState:'loading',addEventListener(){}};vm.runInThisContext(fs.readFileSync('frame/math.js','utf8'));const cases=JSON.parse(process.argv[1]);console.log(JSON.stringify(cases.map(q=>window.MATH.solveCuboidNet(q))));'''
        proc = subprocess.run([find_node(), "-e", source, json.dumps(cases)], cwd=repo, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        actual = json.loads(proc.stdout)
        for request, js_result in zip(cases, actual):
            py_result = solve_cuboid_net(request)
            with self.subTest(request=request):
                self.assertEqual(js_result["valid"], py_result["valid"])
                self.assertEqual(js_result["reason"], py_result["reason"])
                self.assertEqual(js_result["hinges"], py_result["hinges"])
                self.assertEqual(js_result["checks"], py_result["checks"])
                self.assertEqual(len(js_result["faces"]), len(py_result["faces"]))
                self.assertEqual(js_result["unique_face_normals"], py_result["unique_face_normals"])
                if py_result["hinge_residual"] is not None:
                    self.assertAlmostEqual(js_result["hinge_residual"], py_result["hinge_residual"], places=9)
                for js_face, py_face in zip(js_result["faces"], py_result["faces"]):
                    self.assertEqual(js_face["normal"], py_face["normal"])
                    for js_point, py_point in zip([js_face["center"]] + js_face["vertices"],
                                                  [py_face["center"]] + py_face["vertices"]):
                        for a, b in zip(js_point, py_point):
                            self.assertTrue(math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9))


if __name__ == "__main__":
    unittest.main()
