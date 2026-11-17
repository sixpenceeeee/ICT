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
from solid_volume_solver import solve_solid_volume, solve_composite_volume, check_volume_partition


def find_node():
    paths = glob.glob(os.path.join(os.path.expanduser("~"), ".workbuddy", "binaries", "node", "versions", "*", "node.exe"))
    return paths[0] if paths else shutil.which("node")


class SolidVolumeTests(unittest.TestCase):
    def test_known_solid_volumes(self):
        cases = [
            ({"solid":"cube","edge":2}, 8),
            ({"solid":"cuboid","length":2,"width":3,"height":4}, 24),
            ({"solid":"triangular_prism","base":3,"triangle_height":2,"length":4}, 12),
            ({"solid":"square_pyramid","base":2,"height":3}, 4),
            ({"solid":"cylinder","radius":2,"height":3}, 12*math.pi),
            ({"solid":"cone","radius":2,"height":3}, 4*math.pi),
            ({"solid":"sphere","radius":3}, 36*math.pi),
        ]
        for request, expected in cases:
            with self.subTest(solid=request["solid"]):
                result = solve_solid_volume(request)
                self.assertAlmostEqual(result["volume"], expected, places=9)
                self.assertEqual(result["unit"], "unit^3")
                self.assertTrue(result["checks"]["positive"])

    def test_dimensions_scale_volume_cubically(self):
        for req in ({"solid":"cube","edge":2}, {"solid":"sphere","radius":2},
                    {"solid":"cylinder","radius":2,"height":3}):
            scaled = dict(req)
            for key in scaled:
                if key != "solid":
                    scaled[key] *= 2
            self.assertAlmostEqual(solve_solid_volume(scaled)["volume"],
                                   solve_solid_volume(req)["volume"]*8, places=8)

    def test_disjoint_composite_sum(self):
        result = solve_composite_volume([{"solid":"cube","edge":1}, {"solid":"sphere","radius":1}])
        self.assertEqual(result["operation"], "sum_disjoint_components")
        self.assertAlmostEqual(result["volume"], 1+4*math.pi/3)

    def test_partition_conservation_pass_and_fail(self):
        ok = check_volume_partition(10, [4, 6])
        bad = check_volume_partition(10, [4, 5])
        self.assertTrue(ok["ok"])
        self.assertFalse(bad["ok"])
        self.assertAlmostEqual(bad["relative_error"], .1)

    def test_invalid_solid_dimensions_and_combinations(self):
        invalid = [{"solid":"cube","edge":0}, {"solid":"sphere","radius":math.inf},
                   {"solid":"cone","radius":1,"height":-1}, {"solid":"unknown","edge":2}]
        for req in invalid:
            with self.subTest(request=req), self.assertRaises(ValueError):
                solve_solid_volume(req)
        for items in ([], None):
            with self.subTest(items=items), self.assertRaises(ValueError):
                solve_composite_volume(items)
        for parts in ([], [-1, 2], [float("nan")]):
            with self.subTest(parts=parts), self.assertRaises(ValueError):
                check_volume_partition(2, parts)

    @unittest.skipUnless(find_node(), "Node.js is not installed")
    def test_javascript_matches_python_reference(self):
        repo = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
        solids = [
            {"solid":"cube","edge":2}, {"solid":"cuboid","length":2,"width":3,"height":4},
            {"solid":"triangular_prism","base":3,"triangle_height":2,"length":4},
            {"solid":"square_pyramid","base":2,"height":3},
            {"solid":"cylinder","radius":2,"height":3}, {"solid":"cone","radius":2,"height":3},
            {"solid":"sphere","radius":3},
        ]
        composite = [{"solid":"cube","edge":1},{"solid":"sphere","radius":1}]
        source = r'''const fs=require('fs'),vm=require('vm');global.window={addEventListener(){}};global.document={readyState:'loading',addEventListener(){}};vm.runInThisContext(fs.readFileSync('frame/math.js','utf8'));const ss=JSON.parse(process.argv[1]),cc=JSON.parse(process.argv[2]);console.log(JSON.stringify({solids:ss.map(x=>window.MATH.solveSolidVolume(x).volume),composite:window.MATH.solveCompositeVolume(cc).volume,partition:window.MATH.checkVolumePartition(10,[4,6]).ok}));'''
        proc = subprocess.run([find_node(), "-e", source, json.dumps(solids), json.dumps(composite)],
                              cwd=repo, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        actual = json.loads(proc.stdout)
        for req, value in zip(solids, actual["solids"]):
            with self.subTest(solid=req["solid"]):
                self.assertAlmostEqual(value, solve_solid_volume(req)["volume"], places=9)
        self.assertAlmostEqual(actual["composite"], solve_composite_volume(composite)["volume"], places=9)
        self.assertTrue(actual["partition"])


if __name__ == "__main__":
    unittest.main()
