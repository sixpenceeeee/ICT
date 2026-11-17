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
    candidates = glob.glob(os.path.join(os.path.expanduser("~"), ".workbuddy", "binaries", "node", "versions", "*", "node.exe"))
    return candidates[0] if candidates else shutil.which("node")


from cone_section_solver import solve_cone_cut


class ConeSectionTests(unittest.TestCase):
    def test_horizontal_base_mid_and_apex(self):
        base = solve_cone_cut(1, 2, (0, 0, 1), -1)
        middle = solve_cone_cut(1, 2, (0, 0, 1), 0)
        apex = solve_cone_cut(1, 2, (0, 0, 1), 1)
        self.assertEqual(base["shape"], "circle")
        self.assertAlmostEqual(base["area"], math.pi, places=8)
        self.assertAlmostEqual(middle["area"], math.pi/4, places=8)
        self.assertEqual(apex["shape"], "tangent")
        self.assertEqual(apex["area"], 0)

    def test_plane_through_axis_is_triangle(self):
        r = solve_cone_cut(1, 2, (1, 0, 0), 0)
        self.assertEqual(r["shape"], "triangle")
        self.assertAlmostEqual(r["area"], 2, places=7)
        self.assertGreaterEqual(len(r["boundary"]), 64)

    def test_parallel_axis_offset_tangent_and_empty(self):
        section = solve_cone_cut(1, 2, (1, 0, 0), .5)
        tangent = solve_cone_cut(1, 2, (1, 0, 0), 1)
        empty = solve_cone_cut(1, 2, (1, 0, 0), 1.01)
        self.assertGreater(section["area"], 0)
        self.assertEqual(tangent["shape"], "tangent")
        self.assertEqual(tangent["area"], 0)
        self.assertEqual(empty["shape"], "empty")

    def test_boundary_points_obey_plane_and_cone(self):
        r = solve_cone_cut(1.2, 3, (1, 2, 3), .2)
        self.assertGreater(r["area"], 0)
        for x, y, z in r["boundary"]:
            self.assertAlmostEqual(sum(a*b for a, b in zip(r["normal"], (x, y, z))), r["offset"], places=7)
            local_radius = 1.2*max(0, (1.5-z)/3)
            self.assertLessEqual(x*x+y*y, local_radius*local_radius+1e-7)
            self.assertGreaterEqual(z, -1.5-1e-7)
            self.assertLessEqual(z, 1.5+1e-7)

    def test_plane_scale_invariance(self):
        a = solve_cone_cut(1, 2, (1, 1, 2), .2)
        b = solve_cone_cut(1, 2, (7, 7, 14), 1.4)
        self.assertEqual(a["shape"], b["shape"])
        self.assertAlmostEqual(a["area"], b["area"], places=9)

    def test_invalid_inputs(self):
        for args in ((0, 2, (1, 0, 0), 0), (1, math.inf, (1, 0, 0), 0),
                     (1, 2, (0, 0, 0), 0), (1, 2, (1, 0), 0)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                solve_cone_cut(*args)

    @unittest.skipUnless(find_node(), "Node.js is not installed")
    def test_javascript_matches_python_reference(self):
        repo = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
        source = r'''const fs=require('fs'),vm=require('vm');global.window={addEventListener(){}};global.document={readyState:'loading',addEventListener(){}};vm.runInThisContext(fs.readFileSync('frame/math.js','utf8'));
const cs=[{radius:1,height:2,n:[0,0,1],offset:-1},{radius:1,height:2,n:[0,0,1],offset:0},{radius:1,height:2,n:[0,0,1],offset:1},{radius:1,height:2,n:[1,0,0],offset:0},{radius:1,height:2,n:[1,0,0],offset:1.01},{radius:1.2,height:3,n:[1,2,3],offset:.2}];
console.log(JSON.stringify(cs.map(c=>{const x=window.MATH.solveConeCut(c);return {shape:x.shape,area:x.area,boundary_samples:x.boundary_samples}})));'''
        proc = subprocess.run([find_node(), "-e", source], cwd=repo, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        actual = json.loads(proc.stdout)
        cases = [(1,2,(0,0,1),-1),(1,2,(0,0,1),0),(1,2,(0,0,1),1),
                 (1,2,(1,0,0),0),(1,2,(1,0,0),1.01),(1.2,3,(1,2,3),.2)]
        for args, got in zip(cases, actual):
            expected = solve_cone_cut(*args)
            with self.subTest(args=args):
                self.assertEqual(got["shape"], expected["shape"])
                self.assertAlmostEqual(got["area"], expected["area"], delta=2e-5)
                self.assertEqual(got["boundary_samples"], expected["boundary_samples"])


if __name__ == "__main__":
    unittest.main()
