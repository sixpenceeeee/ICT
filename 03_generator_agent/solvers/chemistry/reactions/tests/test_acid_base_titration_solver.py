import json
import math
import os
import shutil
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "../../../../../"))
SOLVER_ROOT = os.path.join(PROJECT, "03_generator_agent", "solvers")
sys.path.insert(0, SOLVER_ROOT)

from chemistry.reactions.acid_base_titration_solver import solve_acid_base_titration


def request(acid_volume=25, base_volume=24, acid_unit="mL", base_unit="mL",
            acid_concentration=0.1, base_concentration=0.1,
            acid_formula="HCl", base_formula="NaOH"):
    return {
        "acid": {"formula": acid_formula, "concentration_mol_L": acid_concentration,
                 "volume": acid_volume, "volume_unit": acid_unit},
        "base": {"formula": base_formula, "concentration_mol_L": base_concentration,
                 "volume": base_volume, "volume_unit": base_unit},
    }


class AcidBaseTitrationSolverTests(unittest.TestCase):
    def test_acid_excess_and_equivalence_volume(self):
        result = solve_acid_base_titration(request(base_volume=20))
        self.assertEqual(result["equation"], "HCl(aq) + NaOH(aq) → NaCl(aq) + H2O(l)")
        self.assertAlmostEqual(result["equivalence_volume_ml"], 25)
        self.assertAlmostEqual(result["acid_moles_remaining"], 0.0005)
        self.assertEqual(result["base_moles_remaining"], 0)
        self.assertEqual(result["state"], "acidic")
        self.assertLess(result["pH"], 7)
        self.assertTrue(result["checks"]["ok"])

    def test_equivalence_includes_water_autoionization(self):
        result = solve_acid_base_titration(request(base_volume=25))
        self.assertEqual(result["state"], "equivalence")
        self.assertAlmostEqual(result["pH"], 7, places=10)
        self.assertAlmostEqual(result["hydrogen_concentration_mol_L"], 1e-7, places=15)
        self.assertAlmostEqual(result["hydroxide_concentration_mol_L"], 1e-7, places=15)
        self.assertTrue(result["checks"]["water_ion_product"])

    def test_base_excess_and_poh_relation(self):
        result = solve_acid_base_titration(request(base_volume=30))
        self.assertEqual(result["state"], "basic")
        self.assertGreater(result["pH"], 7)
        self.assertAlmostEqual(result["pH"] + result["pOH"], 14, places=12)
        self.assertAlmostEqual(result["base_moles_remaining"], 0.0005)

    def test_unit_equivalence_is_invariant(self):
        millilitres = solve_acid_base_titration(request())
        litres = solve_acid_base_titration(request(
            acid_volume=0.025, base_volume=0.024, acid_unit="L", base_unit="L"))
        for field in ("equation", "salt_formula", "acid_moles_initial", "base_moles_added",
                      "neutralized_moles", "acid_moles_remaining", "base_moles_remaining",
                      "equivalence_volume_l", "total_volume_l", "pH", "pOH", "state", "checks"):
            self.assertEqual(litres[field], millilitres[field], field)

    def test_uniform_volume_scaling_preserves_concentration_and_ph(self):
        original = solve_acid_base_titration(request(base_volume=21))
        scaled = solve_acid_base_titration(request(acid_volume=75, base_volume=63))
        for field in ("acid_moles_initial", "base_moles_added", "neutralized_moles",
                      "acid_moles_remaining", "base_moles_remaining", "total_volume_l",
                      "equivalence_volume_l", "equivalence_volume_ml"):
            self.assertAlmostEqual(scaled[field], 3 * original[field], msg=field)
        for field in ("net_acid_concentration_mol_L", "excess_acid_concentration_mol_L",
                      "excess_base_concentration_mol_L", "pH", "pOH", "state"):
            self.assertAlmostEqual(scaled[field], original[field], msg=field)

    def test_titration_around_equivalence_changes_state_and_ph_monotonically(self):
        below = solve_acid_base_titration(request(base_volume=24.75))
        exact = solve_acid_base_titration(request(base_volume=25))
        above = solve_acid_base_titration(request(base_volume=25.25))
        self.assertEqual([below["state"], exact["state"], above["state"]],
                         ["acidic", "equivalence", "basic"])
        self.assertLess(below["pH"], exact["pH"])
        self.assertLess(exact["pH"], above["pH"])

    def test_equivalence_volume_scales_with_acid_volume_and_concentration_ratio(self):
        first = solve_acid_base_titration(request(acid_volume=25, acid_concentration=0.1,
                                                  base_concentration=0.2))
        second = solve_acid_base_titration(request(acid_volume=50, acid_concentration=0.1,
                                                   base_concentration=0.2))
        self.assertAlmostEqual(first["equivalence_volume_ml"], 12.5)
        self.assertAlmostEqual(second["equivalence_volume_ml"], 2 * first["equivalence_volume_ml"])

    def test_supported_strong_acid_and_monobasic_base_pairs_balance(self):
        result = solve_acid_base_titration(request(acid_formula="HNO3", base_formula="KOH"))
        self.assertEqual(result["salt_formula"], "KNO3")
        self.assertEqual(result["equation"], "HNO3(aq) + KOH(aq) → KNO3(aq) + H2O(l)")
        self.assertTrue(result["checks"]["equation_balanced"])

    def test_zero_added_titrant_is_valid_but_zero_sample_is_not(self):
        result = solve_acid_base_titration(request(base_volume=0))
        self.assertEqual(result["state"], "acidic")
        self.assertAlmostEqual(result["neutralization_fraction"], 0)
        with self.assertRaises(ValueError):
            solve_acid_base_titration(request(acid_volume=0))

    def test_rejects_unsupported_weak_polyprotic_or_mismatched_species(self):
        for changed in (
            request(acid_formula="CH3COOH"),
            request(acid_formula="H2SO4"),
            request(base_formula="Ca(OH)2"),
            request(acid_formula="NaOH"),
        ):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                solve_acid_base_titration(changed)

    def test_rejects_invalid_units_ranges_and_nonfinite_values(self):
        invalid = [
            request(acid_unit="g"), request(base_unit="m^3"),
            request(acid_concentration=0), request(base_concentration=-0.1),
            request(acid_concentration=1.1), request(base_volume=-1),
            request(base_volume=float("inf")),
        ]
        for changed in invalid:
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                solve_acid_base_titration(changed)
        malformed = [None, [], "0x1", True]
        for value in malformed:
            changed = request()
            changed["base"]["volume"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                solve_acid_base_titration(changed)


class AcidBaseTitrationMetamorphicTests(unittest.TestCase):
    def test_common_volume_scale_preserves_ph_and_state(self):
        base = solve_acid_base_titration(request(base_volume=18))
        transformed = solve_acid_base_titration(request(acid_volume=50, base_volume=36))
        self.assertEqual(transformed["state"], base["state"])
        self.assertAlmostEqual(transformed["pH"], base["pH"], places=12)
        self.assertAlmostEqual(transformed["neutralized_moles"], 2 * base["neutralized_moles"])
        self.assertAlmostEqual(transformed["equivalence_volume_ml"], 2 * base["equivalence_volume_ml"])

    def test_unit_change_and_equivalence_boundary_relations(self):
        ml = solve_acid_base_titration(request(acid_volume=25, base_volume=24.9))
        l = solve_acid_base_titration(request(acid_volume=0.025, base_volume=0.0249,
                                              acid_unit="L", base_unit="L"))
        self.assertAlmostEqual(ml["pH"], l["pH"], places=12)
        self.assertEqual(ml["state"], l["state"])
        below = solve_acid_base_titration(request(base_volume=24.9))
        exact = solve_acid_base_titration(request(base_volume=25))
        above = solve_acid_base_titration(request(base_volume=25.1))
        self.assertLess(below["pH"], exact["pH"])
        self.assertLess(exact["pH"], above["pH"])


class AcidBaseTitrationCrossRuntimeTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node.js is not installed")
    def test_javascript_solver_matches_independent_python_reference(self):
        requests = [
            request(base_volume=0), request(base_volume=20), request(base_volume=25),
            request(base_volume=30), request(acid_volume=0.025, base_volume=0.024,
                                             acid_unit="L", base_unit="L"),
            request(acid_formula="HNO3", base_formula="KOH", base_volume=40),
        ]
        solver_path = os.path.join(PROJECT, "frame", "chem_solver.js")
        source = r'''const fs=require('fs'),vm=require('vm');
const context={};context.window=context;vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),context);
const requests=JSON.parse(process.argv[2]);
process.stdout.write(JSON.stringify(requests.map(q=>context.CHEMSOLVER.solveAcidBaseTitration(q))));'''
        proc = subprocess.run([shutil.which("node"), "-e", source, solver_path, json.dumps(requests)],
                              capture_output=True, text=True, check=True)
        js_results = json.loads(proc.stdout)
        py_results = [solve_acid_base_titration(item) for item in requests]
        self.assertEqual(js_results, py_results)


if __name__ == "__main__":
    unittest.main()
