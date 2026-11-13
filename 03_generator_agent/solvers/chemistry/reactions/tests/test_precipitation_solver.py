import json
import os
import shutil
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "../../../../../"))
sys.path.insert(0, os.path.join(PROJECT, "03_generator_agent", "solvers"))

from chemistry.reactions.precipitation_solver import REACTION_CATALOG, solve_precipitation


def request(a="BaCl2", b="Na2SO4", ca=0.2, va=50, ua="mL", cb=0.15, vb=100, ub="mL", progress=1):
    return {"solutions": [
        {"formula": a, "concentration_mol_L": ca, "volume": va, "volume_unit": ua},
        {"formula": b, "concentration_mol_L": cb, "volume": vb, "volume_unit": ub},
    ], "progress": progress}


class PrecipitationSolverTests(unittest.TestCase):
    def test_barium_sulfate_mass_uses_solution_conversion_and_limiting_reagent(self):
        result = solve_precipitation(request())
        self.assertEqual(result["schema"], "chem-precipitation.v1")
        self.assertEqual(result["reaction_id"], "barium-sulfate")
        self.assertEqual(result["equation"], "BaCl2(aq) + Na2SO4(aq) → BaSO4(s) + 2NaCl(aq)")
        self.assertEqual(result["net_ionic_equation"], "Ba²⁺(aq) + SO₄²⁻(aq) → BaSO₄(s)")
        self.assertEqual(result["limiting_reactants"], [{"index": 0, "formula": "BaCl2"}])
        self.assertAlmostEqual(result["precipitate_moles"], 0.01)
        self.assertAlmostEqual(result["precipitate_molar_mass_g_mol"], 233.383)
        self.assertAlmostEqual(result["precipitate_mass_g"], 2.33383)
        self.assertTrue(result["precipitation_occurs"])
        self.assertTrue(result["checks"]["ok"])

    def test_catalog_all_reactions_balance_and_have_valid_solid_products(self):
        for reaction in REACTION_CATALOG:
            with self.subTest(reaction=reaction["id"]):
                solutions = [{"formula": formula, "concentration_mol_L": 0.1,
                              "volume": 100, "volume_unit": "mL"}
                             for formula in reaction["reactants"]]
                result = solve_precipitation({"solutions": solutions})
                self.assertEqual(result["reaction_id"], reaction["id"])
                self.assertTrue(result["checks"]["ok"])
                self.assertGreater(result["precipitate_molar_mass_g_mol"], 0)
                self.assertTrue(any(row["formula"] == reaction["precipitate_formula"] and row["phase"] == "s"
                                    for row in result["products"]))

    def test_solution_order_and_unicode_subscripts_do_not_change_reaction(self):
        standard = solve_precipitation(request())
        reversed_order = solve_precipitation(request(
            a="Na₂SO₄", b="BaCl₂", ca=0.15, va=100, cb=0.2, vb=50))
        self.assertEqual(standard["equation"], reversed_order["equation"])
        self.assertEqual(standard["initial_amounts_mol"], reversed_order["initial_amounts_mol"])
        self.assertEqual(standard["precipitate_mass_g"], reversed_order["precipitate_mass_g"])

    def test_millilitre_litre_equivalence_and_common_volume_scaling(self):
        in_ml = solve_precipitation(request())
        in_l = solve_precipitation(request(va=0.05, ua="L", vb=0.1, ub="L"))
        self.assertEqual(in_ml["initial_amounts_mol"], in_l["initial_amounts_mol"])
        self.assertEqual(in_ml["precipitate_mass_g"], in_l["precipitate_mass_g"])

        scaled = solve_precipitation(request(va=100, vb=200))
        self.assertEqual(in_ml["limiting_reactants"], scaled["limiting_reactants"])
        self.assertAlmostEqual(scaled["precipitate_moles"], 2 * in_ml["precipitate_moles"])
        self.assertAlmostEqual(scaled["precipitate_mass_g"], 2 * in_ml["precipitate_mass_g"])

    def test_limiting_reagent_boundary_below_at_and_above(self):
        below = solve_precipitation(request(cb=0.1, vb=90))
        exact = solve_precipitation(request(cb=0.1, vb=100))
        above = solve_precipitation(request(cb=0.1, vb=110))
        self.assertEqual(below["limiting_reactants"], [{"index": 1, "formula": "Na2SO4"}])
        self.assertEqual(exact["limiting_reactants"], [
            {"index": 0, "formula": "BaCl2"}, {"index": 1, "formula": "Na2SO4"}])
        self.assertEqual(above["limiting_reactants"], [{"index": 0, "formula": "BaCl2"}])
        self.assertTrue(exact["stoichiometric_mix"])

    def test_progress_scales_solid_moles_and_mass_and_zero_progress_has_no_solid(self):
        full = solve_precipitation(request(progress=1))
        partial = solve_precipitation(request(progress=0.35))
        zero = solve_precipitation(request(progress=0))
        self.assertAlmostEqual(partial["precipitate_moles"], full["precipitate_moles"] * 0.35)
        self.assertAlmostEqual(partial["precipitate_mass_g"], full["precipitate_mass_g"] * 0.35)
        self.assertEqual(zero["precipitate_moles"], 0)
        self.assertEqual(zero["precipitate_mass_g"], 0)
        self.assertFalse(zero["precipitation_occurs"])

    def test_rejects_unknown_reaction_pairs_instead_of_claiming_no_precipitate(self):
        with self.assertRaisesRegex(ValueError, "不在首版沉淀反应目录"):
            solve_precipitation(request(a="NaCl", b="KNO3"))

    def test_rejects_malformed_and_duplicate_solution_formulas(self):
        for bad in (
                {"solutions": [{"formula": "AgNo3"}, {"formula": "NaCl"}]},
                {"solutions": [{"formula": "AgNO3"}, {"formula": "AgNO3"}]},
                {"solutions": [{"formula": "AgNO3"}]},
        ):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                solve_precipitation(bad)

    @unittest.skipUnless(shutil.which("node"), "Node.js is not installed")
    def test_javascript_solver_matches_python_for_each_catalog_reaction(self):
        requests = []
        for reaction in REACTION_CATALOG:
            requests.append({"solutions": [
                {"formula": formula, "concentration_mol_L": 0.1 + i * 0.04,
                 "volume": 70 + i * 30, "volume_unit": "mL"}
                for i, formula in enumerate(reaction["reactants"])], "progress": 0.6})
        requests.extend([request(), request(a="NaOH", b="CuSO4", ca=0.2, va=100, cb=0.1, vb=50),
                         request(progress=0)])
        solver_path = os.path.join(PROJECT, "frame", "chem_solver.js")
        source = r'''const fs=require('fs'),vm=require('vm');
const context={};context.window=context;vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),context);
const requests=JSON.parse(process.argv[2]);
process.stdout.write(JSON.stringify(requests.map(q=>context.CHEMSOLVER.solvePrecipitation(q))));'''
        proc = subprocess.run([shutil.which("node"), "-e", source, solver_path, json.dumps(requests)],
                              capture_output=True, text=True, check=True)
        actual = json.loads(proc.stdout)
        expected = [solve_precipitation(item) for item in requests]
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
