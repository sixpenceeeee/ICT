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
from cube_net_solver import solve_cube_net


def free_hexominoes():
    """Generate the 35 free hexominoes (rotations/reflections equivalent)."""
    def canonical(cells):
        forms = []
        transforms = (
            lambda x, y: (x, y), lambda x, y: (x, -y),
            lambda x, y: (-x, y), lambda x, y: (-x, -y),
            lambda x, y: (y, x), lambda x, y: (y, -x),
            lambda x, y: (-y, x), lambda x, y: (-y, -x),
        )
        for transform in transforms:
            points = [transform(x, y) for x, y in cells]
            min_x = min(x for x, _ in points)
            min_y = min(y for _, y in points)
            forms.append(tuple(sorted((x-min_x, y-min_y) for x, y in points)))
        return min(forms)

    shapes = {canonical({(0, 0)})}
    for _ in range(5):
        grown = set()
        for shape in shapes:
            for x, y in shape:
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    neighbor = (x+dx, y+dy)
                    if neighbor not in shape:
                        grown.add(canonical(set(shape) | {neighbor}))
        shapes = grown
    return sorted(shapes)


def find_node():
    paths = glob.glob(os.path.join(os.path.expanduser("~"), ".workbuddy", "binaries", "node", "versions", "*", "node.exe"))
    return paths[0] if paths else shutil.which("node")


class CubeNetTests(unittest.TestCase):
    CROSS = [(0, 0), (-1, 0), (1, 0), (2, 0), (0, 1), (0, -1)]

    def test_classic_cross_and_rotated_net_fold_to_six_faces(self):
        for cells in (self.CROSS, [(0, 0), (1, 0), (2, 0), (3, 0), (1, 1), (1, -1)]):
            result = solve_cube_net(cells)
            with self.subTest(cells=cells):
                self.assertTrue(result["valid"], result["reason"])
                self.assertEqual(result["unique_face_normals"], 6)
                self.assertTrue(result["checks"]["six_distinct_faces"])
                self.assertTrue(result["checks"]["hinges_close"])
                self.assertLessEqual(result["hinge_residual"], 1e-8)
                self.assertEqual(len(result["faces"]), 6)

    def test_all_free_hexominoes_identify_exactly_eleven_cube_nets(self):
        shapes = free_hexominoes()
        self.assertEqual(len(shapes), 35)
        valid = [shape for shape in shapes if solve_cube_net(shape)["valid"]]
        self.assertEqual(len(valid), 11)

    def test_invalid_row_cycle_duplicate_and_disconnected_inputs(self):
        row = [(i, 0) for i in range(6)]
        cycle = [(0, 0), (1, 0), (2, 0), (0, 1), (1, 1), (2, 1)]
        self.assertFalse(solve_cube_net(row)["valid"])
        self.assertEqual(solve_cube_net(row)["unique_face_normals"], 4)
        cycle_result = solve_cube_net(cycle)
        self.assertFalse(cycle_result["valid"])
        self.assertFalse(cycle_result["tree"])
        self.assertEqual(cycle_result["hinge_count"], 7)
        disconnected = solve_cube_net([(0, 0), (1, 0), (2, 0), (3, 0), (4, 0), (8, 0)])
        self.assertFalse(disconnected["connected"])
        self.assertEqual(disconnected["reason"], "展开图不连通")
        with self.assertRaises(ValueError):
            solve_cube_net([(0, 0), (1, 0), (1, 0), (2, 0), (0, 1), (0, -1)])
        with self.assertRaises(ValueError):
            solve_cube_net([(i, 0) for i in range(5)])

    def test_edge_length_scales_folded_coordinates_without_changing_validity(self):
        unit = solve_cube_net(self.CROSS)
        scaled = solve_cube_net(self.CROSS, edge_length=3.5)
        self.assertTrue(scaled["valid"])
        self.assertAlmostEqual(scaled["hinge_residual"], 0, places=10)
        self.assertAlmostEqual(scaled["faces"][0]["center"][2], 1.75)
        for point_unit, point_scaled in zip(unit["faces"][0]["vertices"], scaled["faces"][0]["vertices"]):
            for a, b in zip(point_unit, point_scaled):
                self.assertAlmostEqual(b, 3.5*a)

    def test_rejects_invalid_edge_and_tolerance(self):
        for edge, tolerance in ((0, 1e-8), (math.inf, 1e-8), (1, -1), (1, math.nan)):
            with self.subTest(edge=edge, tolerance=tolerance), self.assertRaises(ValueError):
                solve_cube_net(self.CROSS, edge, tolerance)
        unsafe = [(2**53, 0), (2**53+1, 0), (2**53+2, 0), (2**53+3, 0), (2**53+4, 0), (2**53+5, 0)]
        with self.assertRaises(ValueError):
            solve_cube_net(unsafe)

    def test_null_optional_arguments_use_documented_defaults(self):
        result = solve_cube_net(self.CROSS, edge_length=None, tolerance=None)
        self.assertTrue(result["valid"])
        self.assertEqual(result["edge_length"], 1)

    def test_generator_routes_cube_net_and_does_not_require_circuit_fields(self):
        generator_dir = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
        sys.path.insert(0, generator_dir)
        from scene_registry import select_page_skeleton
        from generator_agent import hard_validate

        request = {"学科": "数学", "实验主题": "正方体展开图判定"}
        skeleton = select_page_skeleton(request)
        self.assertEqual(skeleton["id"], "math-cube-net-folding")
        self.assertEqual(skeleton["solver_api"], "MATH.solveCubeNet")
        js = ("function render(){var request={cells:[[0,0],[-1,0],[1,0],[2,0],[0,1],[0,-1]]};"
              "var result=MATH.solveCubeNet(request);"
              "window.__MATH_CUBE_NET_REQUEST__=request;"
              "window.__MATH_CUBE_NET_RESULT__=result;drawFaces(result.faces);window.__DATA__={};}")
        sections = {
            "1": "<h2>正方体展开图判定</h2>",
            "2": '<canvas data-visual-type="geometry"></canvas>',
            "3": '<div class="exp-field"></div>',
            "4": '<div class="exp-formula"></div>',
            "5": '<table class="exp-table"></table>',
            "6": "课堂说明",
            "js": js,
        }
        self.assertEqual(hard_validate(sections, request), [])

    @unittest.skipUnless(find_node(), "Node.js is not installed")
    def test_javascript_matches_python_on_all_free_hexominoes(self):
        repo = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
        shapes = free_hexominoes()
        source = r'''const fs=require('fs'),vm=require('vm');global.window={addEventListener(){}};global.document={readyState:'loading',addEventListener(){}};vm.runInThisContext(fs.readFileSync('frame/math.js','utf8'));const shapes=JSON.parse(process.argv[1]);console.log(JSON.stringify(shapes.map(cells=>window.MATH.solveCubeNet({cells}))));'''
        proc = subprocess.run([find_node(), "-e", source, json.dumps(shapes)], cwd=repo, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        actual = json.loads(proc.stdout)
        self.assertEqual(len(actual), len(shapes))
        for cells, js_result in zip(shapes, actual):
            py_result = solve_cube_net(cells)
            with self.subTest(cells=cells):
                self.assertEqual(js_result["valid"], py_result["valid"])
                self.assertEqual(js_result["unique_face_normals"], py_result["unique_face_normals"])
                self.assertEqual(js_result["hinge_count"], py_result["hinge_count"])
                if py_result["hinge_residual"] is not None:
                    self.assertAlmostEqual(js_result["hinge_residual"], py_result["hinge_residual"], places=10)


if __name__ == "__main__":
    unittest.main()
