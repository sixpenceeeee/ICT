import json
import os
import shutil
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "../../../../../"))
sys.path.insert(0, os.path.join(PROJECT, "03_generator_agent", "solvers"))

from chemistry.reactions.solution_mixing_solver import solve_solution_mixing


class SolutionMixingSolverTests(unittest.TestCase):
    def request(self, na2so4_volume=100, na2so4_unit="mL", progress=1):
        return {
            "reactants": ["BaCl2", "Na2SO4"],
            "products": ["BaSO4", "NaCl"],
            "solutions": [
                {"concentration_mol_L": 0.20, "volume": 50, "volume_unit": "mL"},
                {"concentration_mol_L": 0.15, "volume": na2so4_volume, "volume_unit": na2so4_unit},
            ],
            "progress": progress,
        }

    def test_converts_concentration_and_volume_then_solves_limiting_reagent(self):
        result = solve_solution_mixing(self.request())
        self.assertEqual(result["schema"], "chem-solution-mixing.v1")
        self.assertEqual(result["equation"], "BaCl2 + Na2SO4 → BaSO4 + 2NaCl")
        self.assertAlmostEqual(result["initial_amounts_mol"][0], 0.01)
        self.assertAlmostEqual(result["initial_amounts_mol"][1], 0.015)
        self.assertEqual(result["limiting_reactants"], [{"index": 0, "formula": "BaCl2"}])
        self.assertAlmostEqual(result["reactants"][1]["remaining_mol"], 0.005)
        self.assertAlmostEqual(result["products"][0]["produced_mol"], 0.01)
        self.assertAlmostEqual(result["products"][1]["produced_mol"], 0.02)
        self.assertTrue(result["checks"]["concentration_volume_conversion"])
        self.assertTrue(result["checks"]["element_conservation"])
        self.assertTrue(result["checks"]["charge_conservation"])
        self.assertTrue(result["checks"]["ok"])

    def test_millilitre_and_litre_inputs_are_equivalent(self):
        in_ml = solve_solution_mixing(self.request(na2so4_volume=100, na2so4_unit="mL"))
        in_l = solve_solution_mixing(self.request(na2so4_volume=0.1, na2so4_unit="L"))
        self.assertEqual(in_ml["initial_amounts_mol"], in_l["initial_amounts_mol"])
        self.assertEqual(in_ml["limiting_reactants"], in_l["limiting_reactants"])
        self.assertEqual(in_ml["reactants"], in_l["reactants"])
        self.assertEqual(in_ml["products"], in_l["products"])
        self.assertEqual(in_l["solution_inputs"][1]["volume_L"], 0.1)

    def test_scaling_all_solution_volumes_scales_amounts_and_yield(self):
        original = solve_solution_mixing(self.request(progress=0.4))
        scaled_request = self.request(na2so4_volume=200, na2so4_unit="mL", progress=0.4)
        scaled_request["solutions"][0]["volume"] = 100
        scaled = solve_solution_mixing(scaled_request)
        self.assertEqual(original["limiting_reactants"], scaled["limiting_reactants"])
        for before, after in zip(original["initial_amounts_mol"], scaled["initial_amounts_mol"]):
            self.assertAlmostEqual(after, 2 * before)
        self.assertAlmostEqual(scaled["extent_mol"], 2 * original["extent_mol"])
        for before, after in zip(original["products"], scaled["products"]):
            self.assertAlmostEqual(after["produced_mol"], 2 * before["produced_mol"])

    def test_limiting_reagent_switches_across_concentration_volume_threshold(self):
        below = solve_solution_mixing(self.request(na2so4_volume=66.0))
        exact = solve_solution_mixing(self.request(na2so4_volume=100 / 1.5))
        above = solve_solution_mixing(self.request(na2so4_volume=67.0))
        self.assertEqual(below["limiting_reactants"], [{"index": 1, "formula": "Na2SO4"}])
        self.assertEqual(exact["limiting_reactants"], [
            {"index": 0, "formula": "BaCl2"}, {"index": 1, "formula": "Na2SO4"}])
        self.assertTrue(exact["stoichiometric_mix"])
        self.assertEqual(above["limiting_reactants"], [{"index": 0, "formula": "BaCl2"}])

    def test_progress_endpoints(self):
        zero = solve_solution_mixing(self.request(progress=0))
        complete = solve_solution_mixing(self.request(progress=1))
        self.assertEqual(zero["extent_mol"], 0)
        self.assertEqual([row["produced_mol"] for row in zero["products"]], [0, 0])
        self.assertAlmostEqual(complete["extent_mol"], 0.01)
        self.assertTrue(complete["checks"]["ok"])

    def test_zero_concentration_means_no_reaction_not_a_fake_yield(self):
        request = self.request()
        request["solutions"][1]["concentration_mol_L"] = 0
        result = solve_solution_mixing(request)
        self.assertEqual(result["max_extent_mol"], 0)
        self.assertEqual([row["produced_mol"] for row in result["products"]], [0, 0])
        self.assertTrue(result["checks"]["ok"])

    def test_uses_balanced_coefficients_for_non_one_to_one_reaction(self):
        result = solve_solution_mixing({
            "reactants": ["H2SO4", "NaOH"], "products": ["Na2SO4", "H2O"],
            "solutions": [
                {"concentration_mol_L": 0.1, "volume": 50, "volume_unit": "mL"},
                {"concentration_mol_L": 0.2, "volume": 40, "volume_unit": "mL"},
            ],
        })
        self.assertEqual(result["coefficients"], {"reactants": [1, 2], "products": [1, 2]})
        self.assertEqual(result["limiting_reactants"], [{"index": 1, "formula": "NaOH"}])
        self.assertAlmostEqual(result["reactants"][0]["remaining_mol"], 0.001)
        self.assertAlmostEqual(result["products"][0]["produced_mol"], 0.004)
        self.assertTrue(result["checks"]["ok"])

    def test_rejects_bad_units_values_and_shapes(self):
        bad = [
            self.request(na2so4_unit="g"),
            {**self.request(), "solutions": [{"concentration_mol_L": 0.2, "volume": 0, "volume_unit": "L"},
                                                 self.request()["solutions"][1]]},
            {**self.request(), "solutions": [{"concentration_mol_L": -0.1, "volume": 1, "volume_unit": "L"},
                                                 self.request()["solutions"][1]]},
            {**self.request(), "solutions": self.request()["solutions"][:1]},
            {**self.request(), "solutions": [{"concentration_mol_L": "NaN", "volume": 1, "volume_unit": "L"},
                                                 self.request()["solutions"][1]]},
            {**self.request(), "solutions": [{"concentration_mol_L": 1_000_000, "volume": 2, "volume_unit": "L"},
                                                 self.request()["solutions"][1]]},
        ]
        for request in bad:
            with self.subTest(request=request), self.assertRaises(ValueError):
                solve_solution_mixing(request)


class SolutionMixingCrossRuntimeParityTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node.js is not installed")
    def test_javascript_solver_matches_python_reference(self):
        requests = [
            {"reactants": ["BaCl2", "Na2SO4"], "products": ["BaSO4", "NaCl"],
             "solutions": [{"concentration_mol_L": 0.2, "volume": 50, "volume_unit": "mL"},
                           {"concentration_mol_L": 0.15, "volume": 100, "volume_unit": "mL"}],
             "progress": 1},
            {"reactants": ["BaCl2", "Na2SO4"], "products": ["BaSO4", "NaCl"],
             "solutions": [{"concentration_mol_L": 0.2, "volume": 0.05, "volume_unit": "L"},
                           {"concentration_mol_L": 0.15, "volume": 0.1, "volume_unit": "L"}],
             "progress": 0.37},
            {"reactants": ["HCl", "NaOH"], "products": ["NaCl", "H2O"],
             "solutions": [{"concentration_mol_L": 0.1, "volume": 25, "volume_unit": "毫升"},
                           {"concentration_mol_L": 0.2, "volume": 0.0125, "volume_unit": "升"}],
             "progress": 0},
            {"reactants": ["H2SO4", "NaOH"], "products": ["Na2SO4", "H2O"],
             "solutions": [{"concentration_mol_L": 0.1, "volume": 50, "volume_unit": "mL"},
                           {"concentration_mol_L": 0.2, "volume": 40, "volume_unit": "mL"}],
             "progress": 1},
        ]
        solver_path = os.path.join(PROJECT, "frame", "chem_solver.js")
        source = r'''const fs=require('fs'),vm=require('vm');
const context={};context.window=context;vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),context);
const requests=JSON.parse(process.argv[2]);
process.stdout.write(JSON.stringify(requests.map(q=>context.CHEMSOLVER.solveSolutionMixing(q))));'''
        proc = subprocess.run([shutil.which("node"), "-e", source, solver_path, json.dumps(requests)],
                              capture_output=True, text=True, check=True)
        js_results = json.loads(proc.stdout)
        py_results = [solve_solution_mixing(request) for request in requests]
        self.assertEqual(js_results, py_results)


if __name__ == "__main__":
    unittest.main()
