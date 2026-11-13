import math
import os
import sys
import json
import glob
import shutil
import subprocess
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from sphere_section_solver import solve_sphere_cut


def find_node():
    paths = glob.glob(os.path.join(os.path.expanduser("~"), ".workbuddy", "binaries", "node", "versions", "*", "node.exe"))
    return paths[0] if paths else shutil.which("node")


class SphereSectionTests(unittest.TestCase):
    def test_equatorial_and_offset_circles(self):
        eq = solve_sphere_cut(2, (0, 0, 1), 0)
        offset = solve_sphere_cut(2, (0, 0, 1), 1)
        self.assertEqual(eq["shape"], "circle")
        self.assertAlmostEqual(eq["area"], 4*math.pi)
        self.assertAlmostEqual(offset["section_radius"], math.sqrt(3))
        self.assertAlmostEqual(offset["area"], 3*math.pi)

    def test_tangent_and_outside(self):
        tangent = solve_sphere_cut(2, (1, 2, 3), 2*math.sqrt(14))
        outside = solve_sphere_cut(2, (0, 0, 1), 2.01)
        self.assertEqual(tangent["shape"], "tangent")
        self.assertEqual(tangent["area"], 0)
        self.assertEqual(outside["shape"], "empty")
        self.assertIsNone(outside["center"])

    def test_boundary_on_plane_and_sphere(self):
        result = solve_sphere_cut(3, (1, 2, 3), 1.25)
        for x, y, z in result["boundary"]:
            self.assertAlmostEqual(sum(a*b for a,b in zip(result["normal"], (x,y,z))), result["offset"], places=8)
            self.assertAlmostEqual(x*x+y*y+z*z, 9, places=7)

    def test_normal_scaling_and_reversal(self):
        a = solve_sphere_cut(2, (1, 2, 3), .5)
        b = solve_sphere_cut(2, (7, 14, 21), 3.5)
        c = solve_sphere_cut(2, (-1, -2, -3), -.5)
        self.assertAlmostEqual(a["area"], b["area"], places=10)
        self.assertAlmostEqual(a["area"], c["area"], places=10)

    def test_invalid_inputs(self):
        for args in ((0, (1,0,0), 0), (1, (0,0,0), 0), (1, (1,0), 0), (1, (math.inf,0,0), 0)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                solve_sphere_cut(*args)

    @unittest.skipUnless(find_node(), "Node.js is not installed")
    def test_javascript_matches_python_reference(self):
        repo = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
        source = r'''const fs=require('fs'),vm=require('vm');global.window={addEventListener(){}};global.document={readyState:'loading',addEventListener(){}};vm.runInThisContext(fs.readFileSync('frame/math.js','utf8'));
const cs=[{radius:2,n:[0,0,1],offset:0},{radius:2,n:[0,0,1],offset:1},{radius:2,n:[1,2,3],offset:2*Math.sqrt(14)},{radius:2,n:[0,0,1],offset:2.01}];console.log(JSON.stringify(cs.map(c=>{const x=window.MATH.solveSphereCut(c);return {shape:x.shape,area:x.area,boundary_samples:x.boundary_samples};})));'''
        proc = subprocess.run([find_node(), "-e", source], cwd=repo, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        actual = json.loads(proc.stdout)
        cases = [(2,(0,0,1),0),(2,(0,0,1),1),(2,(1,2,3),2*math.sqrt(14)),(2,(0,0,1),2.01)]
        for args, got in zip(cases, actual):
            expected = solve_sphere_cut(*args)
            with self.subTest(args=args):
                self.assertEqual(got["shape"], expected["shape"])
                self.assertAlmostEqual(got["area"], expected["area"], places=10)
                self.assertEqual(got["boundary_samples"], expected["boundary_samples"])


if __name__ == "__main__":
    unittest.main()
