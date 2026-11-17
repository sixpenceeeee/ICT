import math
import os
import json
import shutil
import sys
import subprocess
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SOLVERS = os.path.abspath(os.path.join(HERE, "../../../"))
sys.path.insert(0, SOLVERS)

from chemistry.reactions.solubility_equilibrium_solver import solve_solubility_equilibrium


def agcl(ksp=1.8e-10, ag=0.0, chloride=0.0):
    return {
        "solid_formula": "AgCl", "Ksp": ksp,
        "ions": [
            {"formula": "Ag", "charge": 1, "coefficient": 1,
             "initial_concentration_mol_L": ag},
            {"formula": "Cl", "charge": -1, "coefficient": 1,
             "initial_concentration_mol_L": chloride},
        ],
    }


def caf2(ksp=4e-11, calcium=0.0, fluoride=0.0):
    return {
        "solid_formula": "CaF2", "Ksp": ksp,
        "ions": [
            {"formula": "Ca", "charge": 2, "coefficient": 1,
             "initial_concentration_mol_L": calcium},
            {"formula": "F", "charge": -1, "coefficient": 2,
             "initial_concentration_mol_L": fluoride},
        ],
    }


class SolubilityEquilibriumSolverTests(unittest.TestCase):
    def test_agcl_pure_water_has_square_root_solubility(self):
        result = solve_solubility_equilibrium(agcl())
        self.assertEqual(result["saturation_state"], "unsaturated")
        self.assertAlmostEqual(result["molar_solubility_mol_L"], math.sqrt(1.8e-10), places=13)
        self.assertAlmostEqual(result["equilibrium_ion_product"], result["Ksp"], delta=1e-20)
        self.assertIn("Ag⁺(aq) + Cl⁻(aq)", result["dissolution_equation"])
        self.assertTrue(result["checks"]["ok"])

    def test_caf2_pure_water_obeys_cubic_ion_product(self):
        result = solve_solubility_equilibrium(caf2())
        expected = (4e-11 / 4) ** (1 / 3)
        self.assertAlmostEqual(result["molar_solubility_mol_L"], expected, places=13)
        self.assertAlmostEqual(result["equilibrium_ion_concentrations_mol_L"][0], expected, places=13)
        self.assertAlmostEqual(result["equilibrium_ion_concentrations_mol_L"][1], 2 * expected, places=13)
        self.assertAlmostEqual(result["equilibrium_ion_product"], 4e-11, delta=1e-20)

    def test_common_ion_reduces_additional_molar_solubility(self):
        pure = solve_solubility_equilibrium(agcl())
        common = solve_solubility_equilibrium(agcl(ag=0.01))
        self.assertEqual(common["saturation_state"], "unsaturated")
        self.assertLess(common["molar_solubility_mol_L"], pure["molar_solubility_mol_L"])
        self.assertAlmostEqual(common["equilibrium_ion_product"], common["Ksp"], delta=1e-19)

    def test_ksp_scale_for_agcl_scales_pure_water_s_by_square_root(self):
        original = solve_solubility_equilibrium(agcl(ksp=1e-10))
        transformed = solve_solubility_equilibrium(agcl(ksp=4e-10))
        self.assertAlmostEqual(transformed["molar_solubility_mol_L"],
                               2 * original["molar_solubility_mol_L"], places=13)

    def test_saturation_threshold_classifies_below_at_and_above(self):
        threshold = math.sqrt(1.8e-10)
        below = solve_solubility_equilibrium(agcl(ag=threshold * 0.95, chloride=threshold))
        at = solve_solubility_equilibrium(agcl(ag=threshold, chloride=threshold))
        above = solve_solubility_equilibrium(agcl(ag=threshold * 1.05, chloride=threshold))
        self.assertEqual(below["saturation_state"], "unsaturated")
        self.assertGreater(below["molar_solubility_mol_L"], 0)
        self.assertEqual(at["saturation_state"], "saturated")
        self.assertEqual(at["molar_solubility_mol_L"], 0)
        self.assertEqual(above["saturation_state"], "supersaturated")
        self.assertTrue(above["precipitation_expected"])
        self.assertIsNone(above["molar_solubility_mol_L"])
        self.assertIsNone(above["equilibrium_ion_concentrations_mol_L"])
        self.assertIsNone(above["checks"]["mass_action_at_saturation"])
        self.assertTrue(above["checks"]["supersaturation_not_misrepresented_as_equilibrium"])

    def test_formula_charge_stoichiometry_and_duplicates_are_rejected(self):
        bad_atoms = caf2()
        bad_atoms["ions"][1]["coefficient"] = 1
        with self.assertRaisesRegex(ValueError, "原子数"):
            solve_solubility_equilibrium(bad_atoms)
        bad_charge = caf2()
        bad_charge["ions"][0]["charge"] = 1
        with self.assertRaisesRegex(ValueError, "电荷"):
            solve_solubility_equilibrium(bad_charge)
        duplicate = agcl()
        duplicate["ions"][1] = dict(duplicate["ions"][0])
        with self.assertRaisesRegex(ValueError, "重复"):
            solve_solubility_equilibrium(duplicate)

    def test_invalid_numeric_and_structural_boundaries_are_rejected(self):
        for value in (0, -1, 1e7, float("nan"), float("inf"), True):
            with self.subTest(Ksp=value), self.assertRaises(ValueError):
                solve_solubility_equilibrium(agcl(ksp=value))
        too_concentrated = agcl(ag=1001)
        with self.assertRaisesRegex(ValueError, "浓度"):
            solve_solubility_equilibrium(too_concentrated)
        with self.assertRaisesRegex(ValueError, "2 到 4"):
            solve_solubility_equilibrium({"solid_formula": "AgCl", "Ksp": 1e-10, "ions": []})

    @unittest.skipUnless(shutil.which("node"), "Node.js is not installed")
    def test_javascript_solver_matches_independent_python_reference(self):
        threshold = math.sqrt(1.8e-10)
        cases = [agcl(), agcl(ag=0.01), caf2(),
                 agcl(ag=threshold * 0.95, chloride=threshold),
                 agcl(ag=threshold, chloride=threshold),
                 agcl(ag=threshold * 1.05, chloride=threshold)]
        solver_path = os.path.abspath(os.path.join(HERE, "../../../../../frame/chem_solver.js"))
        source = r'''const fs=require('fs'),vm=require('vm');const c={};c.window=c;vm.createContext(c);
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),c);
process.stdout.write(JSON.stringify(JSON.parse(process.argv[2]).map(q=>c.CHEMSOLVER.solveSolubilityEquilibrium(q))));'''
        proc = subprocess.run([shutil.which("node"), "-e", source, solver_path,
                               json.dumps(cases, ensure_ascii=False)],
                              capture_output=True, text=True, check=True)
        actual = json.loads(proc.stdout)
        expected = [solve_solubility_equilibrium(case) for case in cases]
        def assert_close_tree(left, right, path="result"):
            if isinstance(right, bool) or right is None or isinstance(right, str):
                self.assertEqual(left, right, path)
            elif isinstance(right, (int, float)):
                self.assertIsInstance(left, (int, float), path)
                self.assertTrue(math.isclose(left, right, rel_tol=1e-12, abs_tol=1e-300),
                                "%s: %r != %r" % (path, left, right))
            elif isinstance(right, list):
                self.assertEqual(len(left), len(right), path)
                for index, (a, b) in enumerate(zip(left, right)):
                    assert_close_tree(a, b, "%s[%d]" % (path, index))
            else:
                self.assertEqual(set(left), set(right), path)
                for key in right:
                    assert_close_tree(left[key], right[key], "%s.%s" % (path, key))
        assert_close_tree(actual, expected)


if __name__ == "__main__":
    unittest.main()
