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
from spatial_metrics_solver import solve_spatial_metrics


def find_node():
    paths = glob.glob(os.path.join(os.path.expanduser("~"), ".workbuddy", "binaries", "node", "versions", "*", "node.exe"))
    return paths[0] if paths else shutil.which("node")


class SpatialMetricsTests(unittest.TestCase):
    def assert_value(self, query, expected):
        result = solve_spatial_metrics(query)
        self.assertAlmostEqual(result["value"], expected, places=8)
        self.assertTrue(result["checks"]["finite"])
        self.assertTrue(result["checks"]["non_negative"])
        return result

    def test_point_distances(self):
        self.assert_value({"operation":"point_point_distance","p":[0,0,0],"q":[3,4,0]},5)
        self.assert_value({"operation":"point_line_distance","point":[0,2,0],"line_point":[0,0,0],"line_direction":[3,0,0]},2)
        self.assert_value({"operation":"point_plane_distance","point":[0,0,5],"plane_normal":[0,0,2],"plane_offset":4},3)

    def test_line_line_distance_parallel_and_skew(self):
        parallel = {"operation":"line_line_distance","line1_point":[0,0,0],"line1_direction":[1,0,0],"line2_point":[0,3,0],"line2_direction":[-2,0,0]}
        skew = {"operation":"line_line_distance","line1_point":[0,0,0],"line1_direction":[1,0,0],"line2_point":[0,2,1],"line2_direction":[0,0,1]}
        self.assert_value(parallel,3)
        self.assert_value(skew,2)

    def test_line_and_plane_distances(self):
        self.assert_value({"operation":"line_plane_distance","line_point":[0,0,4],"line_direction":[1,0,0],"plane_normal":[0,0,1],"plane_offset":1},3)
        self.assert_value({"operation":"line_plane_distance","line_point":[0,0,4],"line_direction":[0,0,1],"plane_normal":[0,0,1],"plane_offset":1},0)
        self.assert_value({"operation":"plane_plane_distance","plane1_normal":[0,0,1],"plane1_offset":2,"plane2_normal":[0,0,-3],"plane2_offset":-12},2)
        self.assert_value({"operation":"plane_plane_distance","plane1_normal":[0,0,1],"plane1_offset":0,"plane2_normal":[1,0,0],"plane2_offset":0},0)

    def test_angles(self):
        self.assert_value({"operation":"line_line_angle","line1_point":[0,0,0],"line1_direction":[1,0,0],"line2_point":[0,0,0],"line2_direction":[1,1,0]},45)
        self.assert_value({"operation":"line_plane_angle","line_point":[0,0,0],"line_direction":[1,0,1],"plane_normal":[0,0,1],"plane_offset":0},45)
        result = self.assert_value({"operation":"plane_plane_angle","plane1_normal":[0,0,1],"plane1_offset":0,"plane2_normal":[0,1,1],"plane2_offset":3},45)
        self.assertTrue(result["checks"]["angle_in_range"])
        self.assert_value({"operation":"line_line_angle","line1_point":[0,0,0],"line1_direction":[1,0,0],"line2_point":[0,0,0],"line2_direction":[-1,0,0]},0)

    def test_invalid_vectors_and_operations(self):
        invalid = [
            {"operation":"point_line_distance","point":[0,0,0],"line_point":[0,0,0],"line_direction":[0,0,0]},
            {"operation":"point_plane_distance","point":[0,0,0],"plane_normal":[0,0,0],"plane_offset":0},
            {"operation":"line_line_angle","line1_point":[0,0,0],"line1_direction":[0,0,0],"line2_point":[0,0,0],"line2_direction":[1,0,0]},
            {"operation":"bad_operation"},
        ]
        for q in invalid:
            with self.subTest(query=q), self.assertRaises(ValueError):
                solve_spatial_metrics(q)

    @unittest.skipUnless(find_node(), "Node.js is not installed")
    def test_javascript_matches_python_reference(self):
        repo = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
        queries = [
            {"operation":"point_point_distance","p":[0,0,0],"q":[3,4,0]},
            {"operation":"point_line_distance","point":[0,2,0],"line_point":[0,0,0],"line_direction":[3,0,0]},
            {"operation":"point_plane_distance","point":[0,0,5],"plane_normal":[0,0,2],"plane_offset":4},
            {"operation":"line_line_distance","line1_point":[0,0,0],"line1_direction":[1,0,0],"line2_point":[0,2,1],"line2_direction":[0,0,1]},
            {"operation":"line_line_angle","line1_point":[0,0,0],"line1_direction":[1,0,0],"line2_point":[0,0,0],"line2_direction":[1,1,0]},
            {"operation":"line_plane_distance","line_point":[0,0,4],"line_direction":[1,0,0],"plane_normal":[0,0,1],"plane_offset":1},
            {"operation":"line_plane_angle","line_point":[0,0,0],"line_direction":[1,0,1],"plane_normal":[0,0,1],"plane_offset":0},
            {"operation":"plane_plane_distance","plane1_normal":[0,0,1],"plane1_offset":2,"plane2_normal":[0,0,-3],"plane2_offset":-12},
            {"operation":"plane_plane_angle","plane1_normal":[0,0,1],"plane1_offset":0,"plane2_normal":[0,1,1],"plane2_offset":3},
        ]
        encoded = json.dumps(queries)
        source = r'''const fs=require('fs'),vm=require('vm');global.window={addEventListener(){}};global.document={readyState:'loading',addEventListener(){}};vm.runInThisContext(fs.readFileSync('frame/math.js','utf8'));const qs=JSON.parse(process.argv[1]);console.log(JSON.stringify(qs.map(q=>window.MATH.solveSpatialMetrics(q))));'''
        proc = subprocess.run([find_node(), "-e", source, encoded], cwd=repo, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        actual = json.loads(proc.stdout)
        for q, got in zip(queries, actual):
            expected = solve_spatial_metrics(q)
            with self.subTest(operation=q["operation"]):
                self.assertAlmostEqual(got["value"], expected["value"], places=8)
                self.assertEqual(got["unit"], expected["unit"])


if __name__ == "__main__":
    unittest.main()
