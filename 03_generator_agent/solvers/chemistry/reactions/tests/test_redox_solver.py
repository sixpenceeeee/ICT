import json
import os
import shutil
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "../../../../../"))
sys.path.insert(0, os.path.join(PROJECT, "03_generator_agent", "solvers"))

from chemistry.reactions.redox_solver import solve_redox


def permanganate(medium="acidic", unicode=False):
    sub = (lambda value: value.replace("4", "₄")) if unicode else (lambda value: value)
    return {
        "medium": medium,
        "reactants": [
            {"formula": sub("MnO4"), "charge": -1, "phase": "aq"},
            {"formula": "Fe", "charge": 2, "phase": "aq"},
        ],
        "products": [
            {"formula": "Mn", "charge": 2, "phase": "aq"},
            {"formula": "Fe", "charge": 3, "phase": "aq"},
        ],
    }


class RedoxSolverTests(unittest.TestCase):
    def test_acidic_permanganate_iron_has_explicit_hydrogen_and_electron_balance(self):
        result = solve_redox(permanganate())
        self.assertEqual(result["equation"],
                         "MnO₄⁻(aq) + 5Fe²⁺(aq) + 8H⁺(aq) → Mn²⁺(aq) + 5Fe³⁺(aq) + 4H₂O(l)")
        self.assertEqual(result["coefficients"], {"reactants": [1, 5, 8], "products": [1, 5, 4]})
        self.assertEqual(result["electron_balance"], {
            "lost_electrons": 5, "gained_electrons": 5,
            "transferred_electrons": 5, "ok": True})
        self.assertEqual([(row["element"], row["before"], row["after"])
                          for row in result["oxidation_changes"]], [("Fe", 2, 3), ("Mn", 7, 2)])
        self.assertTrue(result["checks"]["ok"])

    def test_basic_medium_adds_hydroxide_and_water_as_needed(self):
        result = solve_redox(permanganate("basic"))
        self.assertIn("OH⁻(aq)", result["equation"])
        self.assertIn("H₂O(l)", result["equation"])
        self.assertEqual(result["electron_balance"]["transferred_electrons"], 5)
        self.assertTrue(result["checks"]["ok"])

    def test_basic_iodide_hypochlorite_reaction_balances_without_auxiliaries(self):
        result = solve_redox({
            "medium": "basic",
            "reactants": [{"formula": "ClO", "charge": -1}, {"formula": "I", "charge": -1}],
            "products": [{"formula": "Cl", "charge": -1}, {"formula": "IO3", "charge": -1}],
        })
        self.assertEqual(result["equation"], "3ClO⁻ + I⁻ → 3Cl⁻ + IO₃⁻")
        self.assertEqual(result["electron_balance"]["transferred_electrons"], 6)
        self.assertTrue(result["checks"]["ok"])

    def test_dichromate_sulfite_tracks_six_electrons(self):
        result = solve_redox({
            "medium": "酸性",
            "reactants": [{"formula": "Cr2O7", "charge": -2}, {"formula": "SO3", "charge": -2}],
            "products": [{"formula": "Cr", "charge": 3}, {"formula": "SO4", "charge": -2}],
        })
        self.assertEqual(result["coefficients"], {"reactants": [1, 3, 8], "products": [2, 3, 4]})
        self.assertEqual(result["electron_balance"]["transferred_electrons"], 6)

    def test_disproportionation_does_not_cancel_average_oxidation_state_changes(self):
        result = solve_redox({
            "medium": "acidic", "reactants": [{"formula": "H2O2", "charge": 0}],
            "products": [{"formula": "H2O", "charge": 0}, {"formula": "O2", "charge": 0}],
        })
        self.assertEqual(result["equation"], "2H₂O₂ → 2H₂O + O₂")
        self.assertEqual(result["electron_balance"]["lost_electrons"], 2)
        self.assertEqual(result["electron_balance"]["gained_electrons"], 2)
        self.assertEqual([row["delta"] for row in result["oxidation_changes"]], [-1, 1])

    def test_reordering_species_preserves_species_coefficients_and_electron_transfer(self):
        original = solve_redox(permanganate())
        request = permanganate()
        request["reactants"].reverse()
        request["products"].reverse()
        reordered = solve_redox(request)
        self.assertEqual(reordered["coefficients"]["reactants"][:2],
                         list(reversed(original["coefficients"]["reactants"][:2])))
        self.assertEqual(reordered["coefficients"]["products"][:2],
                         list(reversed(original["coefficients"]["products"][:2])))
        self.assertEqual(reordered["electron_balance"], original["electron_balance"])
        self.assertEqual(reordered["oxidation_changes"], original["oxidation_changes"])

    def test_subscript_notation_and_medium_aliases_preserve_reaction(self):
        plain = solve_redox(permanganate("acidic"))
        unicode = solve_redox(permanganate("酸性", unicode=True))
        self.assertEqual(unicode["coefficients"], plain["coefficients"])
        self.assertEqual(unicode["equation"], plain["equation"])
        self.assertEqual(unicode["electron_balance"], plain["electron_balance"])

    def test_acid_to_base_metamorphosis_preserves_redox_species_and_electron_count(self):
        acid = solve_redox(permanganate("acidic"))
        base = solve_redox(permanganate("basic"))
        self.assertEqual(acid["electron_balance"]["transferred_electrons"],
                         base["electron_balance"]["transferred_electrons"])
        self.assertEqual([(row["element"], row["before"], row["after"])
                          for row in acid["oxidation_changes"]],
                         [(row["element"], row["before"], row["after"])
                          for row in base["oxidation_changes"]])
        self.assertTrue(acid["checks"]["ok"] and base["checks"]["ok"])

    def test_neutralization_is_rejected_as_non_redox(self):
        with self.assertRaisesRegex(ValueError, "未识别到成对的氧化数"):
            solve_redox({
                "medium": "acidic",
                "reactants": [{"formula": "HCl", "charge": 0}, {"formula": "NaOH", "charge": 0}],
                "products": [{"formula": "NaCl", "charge": 0}, {"formula": "H2O", "charge": 0}],
            })

    def test_requires_explicit_medium_and_charges_and_rejects_ambiguous_formula(self):
        request = permanganate()
        request.pop("medium")
        with self.assertRaisesRegex(ValueError, "medium 必须"):
            solve_redox(request)
        request = permanganate()
        del request["reactants"][0]["charge"]
        with self.assertRaisesRegex(ValueError, "明确提供整数电荷"):
            solve_redox(request)
        with self.assertRaisesRegex(ValueError, "无法唯一判定"):
            solve_redox({"medium": "acidic", "reactants": [{"formula": "CNO", "charge": 0}],
                         "products": [{"formula": "CNO", "charge": 0}]})
        with self.assertRaisesRegex(ValueError, "平均氧化数"):
            solve_redox({"medium": "acidic", "reactants": [{"formula": "Fe3O4", "charge": 0}],
                         "products": [{"formula": "Fe", "charge": 0}]})

    @unittest.skipUnless(shutil.which("node"), "Node.js is not installed")
    def test_javascript_solver_matches_python_reference_and_metamorphic_variants(self):
        cases = [permanganate(), permanganate("basic"), permanganate("acidic", unicode=True), {
            "medium": "basic", "reactants": [{"formula": "ClO", "charge": -1}, {"formula": "I", "charge": -1}],
            "products": [{"formula": "Cl", "charge": -1}, {"formula": "IO3", "charge": -1}],
        }, {
            "medium": "acidic", "reactants": [{"formula": "H2O2", "charge": 0}],
            "products": [{"formula": "H2O", "charge": 0}, {"formula": "O2", "charge": 0}],
        }]
        solver_path = os.path.join(PROJECT, "frame", "chem_solver.js")
        source = r'''const fs=require('fs'),vm=require('vm');const c={};c.window=c;vm.createContext(c);
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),c);
process.stdout.write(JSON.stringify(JSON.parse(process.argv[2]).map(q=>c.CHEMSOLVER.solveRedox(q))));'''
        proc = subprocess.run([shutil.which("node"), "-e", source, solver_path,
                               json.dumps(cases, ensure_ascii=False)], capture_output=True, text=True, check=True)
        actual = json.loads(proc.stdout)
        expected = [solve_redox(case) for case in cases]
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
