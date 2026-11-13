import json
import math
import os
import shutil
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "../../../../../"))
sys.path.insert(0, os.path.join(PROJECT, "03_generator_agent", "solvers"))

from chemistry.reactions.gas_collection_solver import (
    GAS_CONSTANT_L_KPA_PER_MOL_K,
    solve_gas_collection,
    water_vapor_pressure_kpa,
)


def request(zinc=0.02, acid=0.05, progress=1.0, temperature=25.0,
            pressure=101.325, method="dry"):
    return {
        "reactants": [{"formula": "Zn", "phase": "s"}, {"formula": "HCl", "phase": "aq"}],
        "products": [{"formula": "ZnCl2", "phase": "aq"}, {"formula": "H2", "phase": "g"}],
        "initial_amounts_mol": [zinc, acid],
        "progress": progress,
        "gas_formula": "H2",
        "temperature_c": temperature,
        "total_pressure_kpa": pressure,
        "collection_method": method,
    }


class GasCollectionSolverTests(unittest.TestCase):
    def test_reaction_yield_flows_into_ideal_gas_volume(self):
        result = solve_gas_collection(request())
        expected_volume = 0.02 * GAS_CONSTANT_L_KPA_PER_MOL_K * 298.15 / 101.325
        self.assertEqual(result["equation"], "Zn(s) + 2HCl(aq) → ZnCl2(aq) + H2(g)")
        self.assertEqual(result["limiting_reactants"], [{"index": 0, "formula": "Zn"}])
        self.assertAlmostEqual(result["gas_moles"], 0.02)
        self.assertAlmostEqual(result["gas_volume_l"], expected_volume)
        self.assertTrue(result["checks"]["ok"])
        self.assertTrue(result["checks"]["reaction_balanced_and_conserved"])

    def test_dry_gas_pressure_doubling_halves_volume(self):
        first = solve_gas_collection(request(pressure=100))
        second = solve_gas_collection(request(pressure=200))
        self.assertAlmostEqual(second["gas_volume_l"], first["gas_volume_l"] / 2)
        self.assertEqual(first["dry_gas_partial_pressure_kpa"], 100)

    def test_absolute_temperature_scaling_at_fixed_amount_and_pressure(self):
        cold = solve_gas_collection(request(temperature=25))
        hot = solve_gas_collection(request(temperature=325))
        expected_ratio = (325 + 273.15) / (25 + 273.15)
        self.assertAlmostEqual(hot["gas_volume_l"] / cold["gas_volume_l"], expected_ratio)

    def test_common_amount_scaling_preserves_limiting_species_and_scales_gas(self):
        original = solve_gas_collection(request(zinc=0.02, acid=0.05, progress=0.4))
        scaled = solve_gas_collection(request(zinc=0.06, acid=0.15, progress=0.4))
        self.assertEqual(scaled["limiting_reactants"], original["limiting_reactants"])
        self.assertAlmostEqual(scaled["gas_moles"], 3 * original["gas_moles"])
        self.assertAlmostEqual(scaled["gas_volume_l"], 3 * original["gas_volume_l"])

    def test_reaction_progress_scales_yield_and_collected_volume_linearly(self):
        quarter = solve_gas_collection(request(progress=0.25))
        full = solve_gas_collection(request(progress=1))
        self.assertAlmostEqual(quarter["gas_moles"], full["gas_moles"] / 4)
        self.assertAlmostEqual(quarter["gas_volume_l"], full["gas_volume_l"] / 4)

    def test_limiting_reagent_switch_at_stoichiometric_threshold(self):
        acid_limited = solve_gas_collection(request(zinc=0.02, acid=0.039))
        exact = solve_gas_collection(request(zinc=0.02, acid=0.04))
        zinc_limited = solve_gas_collection(request(zinc=0.02, acid=0.041))
        self.assertEqual(acid_limited["limiting_reactants"], [{"index": 1, "formula": "HCl"}])
        self.assertEqual(exact["limiting_reactants"], [
            {"index": 0, "formula": "Zn"}, {"index": 1, "formula": "HCl"}])
        self.assertEqual(zinc_limited["limiting_reactants"], [{"index": 0, "formula": "Zn"}])
        self.assertAlmostEqual(acid_limited["gas_moles"], 0.0195)
        self.assertAlmostEqual(exact["gas_moles"], zinc_limited["gas_moles"])

    def test_water_displacement_corrects_partial_pressure(self):
        dry = solve_gas_collection(request(method="dry"))
        over_water = solve_gas_collection(request(method="over_water"))
        expected_vapor = water_vapor_pressure_kpa(25)
        self.assertAlmostEqual(over_water["water_vapor_pressure_kpa"], expected_vapor)
        self.assertAlmostEqual(over_water["dry_gas_partial_pressure_kpa"], 101.325 - expected_vapor)
        self.assertAlmostEqual(over_water["dry_gas_partial_pressure_kpa"] +
                               over_water["water_vapor_pressure_kpa"], 101.325)
        self.assertGreater(over_water["gas_volume_l"], dry["gas_volume_l"])
        self.assertAlmostEqual(over_water["dry_gas_partial_pressure_kpa"] * over_water["gas_volume_l"],
                               dry["dry_gas_partial_pressure_kpa"] * dry["gas_volume_l"])

    def test_water_vapor_pressure_reference_points(self):
        self.assertAlmostEqual(water_vapor_pressure_kpa(0), 0.611, delta=0.01)
        self.assertAlmostEqual(water_vapor_pressure_kpa(25), 3.17, delta=0.03)
        self.assertAlmostEqual(water_vapor_pressure_kpa(100), 101.3, delta=0.2)

    def test_zero_progress_produces_zero_gas_volume(self):
        result = solve_gas_collection(request(progress=0))
        self.assertEqual(result["gas_moles"], 0)
        self.assertEqual(result["gas_volume_l"], 0)
        self.assertTrue(result["checks"]["ok"])

    def test_rejects_invalid_gas_phase_or_reaction_product(self):
        changed = request()
        changed["gas_formula"] = "ZnCl2"
        with self.assertRaisesRegex(ValueError, "phase"):
            solve_gas_collection(changed)
        changed = request()
        changed["gas_formula"] = "O2"
        with self.assertRaisesRegex(ValueError, "生成物"):
            solve_gas_collection(changed)

    def test_rejects_impossible_temperature_pressure_and_collection_conditions(self):
        cases = [
            request(temperature=-273.15), request(temperature=101, method="over_water"),
            request(pressure=0), request(method="sealed"), request(temperature=101, method="over_water", pressure=100),
        ]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ValueError):
                solve_gas_collection(case)

    def test_javascript_matches_python_reference(self):
        requests = [
            request(), request(method="over_water"), request(temperature=0, method="over_water", pressure=110),
            request(zinc=0.02, acid=0.039, progress=0.75, method="over_water"),
            request(progress=0), request(temperature=325, pressure=200),
        ]
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is not installed")
        solver_path = os.path.join(PROJECT, "frame", "chem_solver.js")
        source = r'''const fs=require('fs'),vm=require('vm');
const context={};context.window=context;vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),context);
const requests=JSON.parse(process.argv[2]);
process.stdout.write(JSON.stringify(requests.map(q=>context.CHEMSOLVER.solveGasCollection(q))));'''
        proc = subprocess.run([node, "-e", source, solver_path, json.dumps(requests)],
                              capture_output=True, text=True, check=True)
        actual = json.loads(proc.stdout)
        expected = [solve_gas_collection(item) for item in requests]
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
