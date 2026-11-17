import json
import os
import shutil
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "../../../../../"))
SOLVER_ROOT = os.path.join(PROJECT, "03_generator_agent", "solvers")
sys.path.insert(0, SOLVER_ROOT)

from chemistry.reactions.stoichiometry_solver import solve_stoichiometry


class StoichiometrySolverTests(unittest.TestCase):
    def request(self, iron=0.1, copper_sulfate=0.06, progress=1.0):
        return {
            "reactants": ["Fe", "CuSO4"],
            "products": ["FeSO4", "Cu"],
            "initial_amounts_mol": [iron, copper_sulfate],
            "progress": progress,
        }

    def test_limiting_reagent_and_theoretical_yield(self):
        result = solve_stoichiometry(self.request())
        self.assertEqual(result["equation"], "Fe + CuSO4 → FeSO4 + Cu")
        self.assertEqual(result["limiting_reactants"], [{"index": 1, "formula": "CuSO4"}])
        self.assertAlmostEqual(result["max_extent_mol"], 0.06)
        self.assertAlmostEqual(result["reactants"][0]["remaining_mol"], 0.04)
        self.assertEqual(result["reactants"][1]["remaining_mol"], 0.0)
        self.assertEqual([row["produced_mol"] for row in result["products"]], [0.06, 0.06])
        self.assertTrue(result["checks"]["ok"])

    def test_progress_zero_half_and_complete(self):
        zero = solve_stoichiometry(self.request(progress=0))
        half = solve_stoichiometry(self.request(progress=0.5))
        complete = solve_stoichiometry(self.request(progress=1))
        self.assertEqual([row["consumed_mol"] for row in zero["reactants"]], [0.0, 0.0])
        self.assertEqual([row["produced_mol"] for row in zero["products"]], [0.0, 0.0])
        self.assertEqual(half["extent_mol"], 0.03)
        self.assertEqual([row["remaining_mol"] for row in half["reactants"]], [0.07, 0.03])
        self.assertEqual(complete["reactants"][1]["remaining_mol"], 0.0)

    def test_limiting_reagent_switches_at_stoichiometric_threshold(self):
        below = solve_stoichiometry(self.request(iron=0.1, copper_sulfate=0.099))
        exact = solve_stoichiometry(self.request(iron=0.1, copper_sulfate=0.1))
        above = solve_stoichiometry(self.request(iron=0.1, copper_sulfate=0.101))
        self.assertEqual(below["limiting_reactants"], [{"index": 1, "formula": "CuSO4"}])
        self.assertEqual(exact["limiting_reactants"], [
            {"index": 0, "formula": "Fe"}, {"index": 1, "formula": "CuSO4"}])
        self.assertTrue(exact["stoichiometric_mix"])
        self.assertEqual(above["limiting_reactants"], [{"index": 0, "formula": "Fe"}])
        self.assertAlmostEqual(above["reactants"][1]["remaining_mol"], 0.001)

    def test_scaling_all_initial_amounts_scales_products_and_extent(self):
        original = solve_stoichiometry(self.request(progress=0.4))
        scaled = solve_stoichiometry(self.request(iron=0.3, copper_sulfate=0.18, progress=0.4))
        self.assertEqual(scaled["limiting_reactants"], original["limiting_reactants"])
        self.assertAlmostEqual(scaled["max_extent_mol"], 3 * original["max_extent_mol"])
        self.assertAlmostEqual(scaled["extent_mol"], 3 * original["extent_mol"])
        for side, field in (("reactants", "remaining_mol"), ("products", "produced_mol")):
            for a, b in zip(original[side], scaled[side]):
                self.assertAlmostEqual(b[field], 3 * a[field])

    def test_reordering_reactants_with_their_amounts_preserves_physical_results(self):
        original_request = {
            "reactants": ["H2", "O2"], "products": ["H2O"],
            "initial_amounts_mol": [2.0, 0.5], "progress": 0.6,
        }
        reordered_request = {
            **original_request,
            "reactants": list(reversed(original_request["reactants"])),
            "initial_amounts_mol": list(reversed(original_request["initial_amounts_mol"])),
        }
        original = solve_stoichiometry(original_request)
        reordered = solve_stoichiometry(reordered_request)
        self.assertAlmostEqual(original["max_extent_mol"], reordered["max_extent_mol"])
        self.assertAlmostEqual(original["extent_mol"], reordered["extent_mol"])
        self.assertEqual(original["limiting_reactants"][0]["formula"],
                         reordered["limiting_reactants"][0]["formula"])
        original_remaining = {row["formula"]: row["remaining_mol"] for row in original["reactants"]}
        reordered_remaining = {row["formula"]: row["remaining_mol"] for row in reordered["reactants"]}
        self.assertEqual(original_remaining.keys(), reordered_remaining.keys())
        for formula in original_remaining:
            self.assertAlmostEqual(original_remaining[formula], reordered_remaining[formula])
        self.assertEqual(original["products"], reordered["products"])

    def test_element_and_charge_conservation_for_ionic_reaction(self):
        result = solve_stoichiometry({
            "reactants": [{"formula": "Ag", "charge": 1}, {"formula": "Cl", "charge": -1}],
            "products": ["AgCl"], "initial_amounts_mol": [0.02, 0.03], "progress": 0.75,
        })
        self.assertTrue(result["element_balance"]["ok"])
        self.assertTrue(result["charge_balance"]["ok"])
        self.assertTrue(result["checks"]["ok"])

    def test_zero_amount_of_one_reactant_means_zero_progress(self):
        result = solve_stoichiometry(self.request(iron=0, copper_sulfate=0.06, progress=1))
        self.assertEqual(result["max_extent_mol"], 0)
        self.assertEqual(result["extent_mol"], 0)
        self.assertEqual(result["reactants"][1]["remaining_mol"], 0.06)
        self.assertEqual(result["products"][0]["produced_mol"], 0)

    def test_rejects_invalid_progress_amounts_and_shapes(self):
        bad_requests = [
            self.request(progress=-0.01), self.request(progress=1.01),
            self.request(iron=-0.1), self.request(iron=float("inf")),
            self.request(iron=1_000_000.01), self.request(iron=0, copper_sulfate=0),
            self.request(progress=None), self.request(progress=[]), self.request(progress="0x1"),
            {**self.request(), "initial_amounts_mol": [0.1]},
            {**self.request(), "initial_amounts_mol": [True, 0.06]},
        ]
        for request in bad_requests:
            with self.subTest(request=request), self.assertRaises(ValueError):
                solve_stoichiometry(request)


class StoichiometryCrossRuntimeParityTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node.js is not installed")
    def test_javascript_solver_matches_python_reference(self):
        requests = [
            {"reactants": ["Fe", "CuSO4"], "products": ["FeSO4", "Cu"],
             "initial_amounts_mol": [0.1, 0.06], "progress": 1},
            {"reactants": ["Fe", "CuSO4"], "products": ["FeSO4", "Cu"],
             "initial_amounts_mol": [0.1, 0.06]},
            {"reactants": ["Fe", "CuSO4"], "products": ["FeSO4", "Cu"],
             "initial_amounts_mol": [0.1, 0.099], "progress": 0.37},
            {"reactants": ["H2", "O2"], "products": ["H2O"],
             "initial_amounts_mol": [2, 0.5], "progress": 0},
            {"reactants": [{"formula": "Ag", "charge": 1}, {"formula": "Cl", "charge": -1}],
             "products": ["AgCl"], "initial_amounts_mol": [0.02, 0.03], "progress": 0.75},
        ]
        solver_path = os.path.join(PROJECT, "frame", "chem_solver.js")
        source = r'''const fs=require('fs'),vm=require('vm');
const context={};context.window=context;vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),context);
const requests=JSON.parse(process.argv[2]);
process.stdout.write(JSON.stringify(requests.map(q=>context.CHEMSOLVER.solveStoichiometry(q))));'''
        proc = subprocess.run([shutil.which("node"), "-e", source, solver_path, json.dumps(requests)],
                              capture_output=True, text=True, check=True)
        js_results = json.loads(proc.stdout)
        py_results = [solve_stoichiometry(request) for request in requests]
        self.assertEqual(js_results, py_results)


if __name__ == "__main__":
    unittest.main()
