import math
import os
import json
import glob
import shutil
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

def find_node():
    candidates = glob.glob(os.path.join(os.path.expanduser("~"), ".workbuddy", "binaries", "node",
                                        "versions", "*", "node.exe"))
    return candidates[0] if candidates else shutil.which("node")


from cylinder_section_solver import solve_cylinder_cut


class CylinderSectionTests(unittest.TestCase):
    def test_horizontal_cut_is_circle(self):
        r = solve_cylinder_cut(2, 5, (0, 0, 1), 0)
        self.assertEqual(r["shape"], "circle")
        self.assertAlmostEqual(r["area"], 4*math.pi, places=8)
        self.assertEqual(len(r["boundary"]), 720)

    def test_vertical_axis_plane_is_rectangle(self):
        r = solve_cylinder_cut(1, 2, (1, 0, 0), 0)
        self.assertEqual(r["shape"], "rectangle")
        self.assertAlmostEqual(r["area"], 4, places=8)
        self.assertEqual(len(r["boundary"]), 4)

    def test_oblique_cut_area_and_plane_residual(self):
        r = solve_cylinder_cut(1, 2, (1, 0, 1), 0)
        self.assertAlmostEqual(r["area"], math.pi*math.sqrt(2), places=6)
        self.assertGreater(r["boundary_samples"], 32)
        for x, y, z in r["boundary"]:
            self.assertLessEqual(abs((x+z)/math.sqrt(2)), 1e-8)
            self.assertLessEqual(x*x+y*y, 1+1e-8)
            self.assertLessEqual(abs(z), 1+1e-8)

    def test_empty_and_tangent(self):
        empty = solve_cylinder_cut(1, 2, (1, 0, 0), 1.01)
        tangent = solve_cylinder_cut(1, 2, (1, 0, 0), 1)
        self.assertEqual(empty["shape"], "empty")
        self.assertEqual(empty["area"], 0)
        self.assertEqual(tangent["shape"], "tangent")
        self.assertEqual(tangent["area"], 0)

    def test_scaling_plane_does_not_change_area(self):
        a = solve_cylinder_cut(1, 2, (1, 0, 1), .2)
        b = solve_cylinder_cut(1, 2, (8, 0, 8), 1.6)
        self.assertAlmostEqual(a["area"], b["area"], places=9)

    def test_invalid_inputs_rejected(self):
        for args in ((0, 2, (1, 0, 0), 0), (1, math.inf, (1, 0, 0), 0),
                     (1, 2, (0, 0, 0), 0), (1, 2, (1, 0), 0)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                solve_cylinder_cut(*args)

    @unittest.skipUnless(find_node(), "Node.js is not installed")
    def test_javascript_solver_matches_python_reference(self):
        repo = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
        source = r'''const fs=require('fs'),vm=require('vm');
global.window={addEventListener(){}};global.document={readyState:'loading',addEventListener(){}};
vm.runInThisContext(fs.readFileSync('frame/math.js','utf8'));
const cases=[
 {radius:1,height:2,n:[0,0,1],offset:0},
 {radius:1,height:2,n:[1,0,0],offset:0},
 {radius:1,height:2,n:[1,0,1],offset:0},
 {radius:1,height:2,n:[1,0,0],offset:1},
 {radius:1,height:2,n:[1,0,0],offset:1.01},
 {radius:1.3,height:4,n:[1,2,-3],offset:.2}
]; console.log(JSON.stringify(cases.map(c=>{const r=window.MATH.solveCylinderCut(c);return {shape:r.shape,area:r.area,boundary_samples:r.boundary_samples};})));'''
        proc = subprocess.run([find_node(), "-e", source], cwd=repo,
                              capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        js_results = json.loads(proc.stdout)
        cases = [
            (1, 2, (0, 0, 1), 0), (1, 2, (1, 0, 0), 0),
            (1, 2, (1, 0, 1), 0), (1, 2, (1, 0, 0), 1),
            (1, 2, (1, 0, 0), 1.01), (1.3, 4, (1, 2, -3), .2),
        ]
        for args, actual in zip(cases, js_results):
            expected = solve_cylinder_cut(*args)
            with self.subTest(args=args):
                self.assertEqual(actual["shape"], expected["shape"])
                self.assertAlmostEqual(actual["area"], expected["area"], delta=2e-5)
                self.assertEqual(actual["boundary_samples"], expected["boundary_samples"])


if __name__ == "__main__":
    unittest.main()
