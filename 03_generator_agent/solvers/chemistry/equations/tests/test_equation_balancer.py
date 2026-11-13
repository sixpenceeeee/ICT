import os
import json
import shutil
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from equation_balancer import balance_equation, check_coefficients, parse_formula


class FormulaParserTests(unittest.TestCase):
    def test_nested_groups_and_hydrate(self):
        self.assertEqual(parse_formula("K4[Fe(CN)6]"), {"C": 6, "Fe": 1, "K": 4, "N": 6})
        self.assertEqual(parse_formula("CuSO4·5H2O"), {"Cu": 1, "H": 10, "O": 9, "S": 1})

    def test_unicode_subscripts(self):
        self.assertEqual(parse_formula("H₂O"), {"H": 2, "O": 1})

    def test_rejects_malformed_formula(self):
        for formula in ("Xx2", "H()", "Ca(OH2", "2H2O", "H0"):
            with self.subTest(formula=formula), self.assertRaises(ValueError):
                parse_formula(formula)


class EquationBalancerTests(unittest.TestCase):
    def test_iron_copper_sulfate(self):
        result = balance_equation({
            "reactants": ["Fe", "CuSO4"],
            "products": ["FeSO4", "Cu"],
        })
        self.assertEqual(result["coefficients"], {"reactants": [1, 1], "products": [1, 1]})
        self.assertEqual(result["equation"], "Fe + CuSO4 → FeSO4 + Cu")
        self.assertTrue(result["checks"]["ok"])

    def test_fractional_nullspace_is_reduced_to_smallest_integers(self):
        result = balance_equation({"reactants": ["H2", "O2"], "products": ["H2O"]})
        self.assertEqual(result["coefficients"], {"reactants": [2, 1], "products": [2]})
        self.assertTrue(result["checks"]["primitive_coefficients"])

    def test_polyatomic_groups(self):
        result = balance_equation({
            "reactants": ["Fe2(SO4)3", "KOH"],
            "products": ["Fe(OH)3", "K2SO4"],
        })
        self.assertEqual(result["coefficients"], {"reactants": [1, 6], "products": [2, 3]})

    def test_ionic_charge_conservation(self):
        result = balance_equation({
            "reactants": [{"formula": "Ag", "charge": 1}, {"formula": "Cl", "charge": -1}],
            "products": ["AgCl"],
        })
        self.assertEqual(result["coefficients"], {"reactants": [1, 1], "products": [1]})
        self.assertEqual(result["charge_counts"], {"left": 0, "right": 0})

    def test_check_coefficients_reports_nonprimitive_solution(self):
        request = {"reactants": ["H2", "O2"], "products": ["H2O"]}
        checked = check_coefficients(request, {"reactants": [4, 2], "products": [4]})
        self.assertTrue(checked["balanced"])
        self.assertFalse(checked["primitive"])
        self.assertFalse(check_coefficients(request, {"reactants": [1, 1], "products": [1]})["balanced"])

    def test_rejects_underdetermined_equations(self):
        request = {"reactants": ["C", "O2"], "products": ["CO", "CO2"]}
        with self.assertRaisesRegex(ValueError, "多组配平解"):
            balance_equation(request)

    def test_rejects_no_positive_balance(self):
        request = {"reactants": ["H2", "O2"], "products": ["CO2"]}
        with self.assertRaises(ValueError):
            balance_equation(request)


class MetamorphicEquationTests(unittest.TestCase):
    CASES = [
        {"reactants": ["Fe", "CuSO4"], "products": ["FeSO4", "Cu"]},
        {"reactants": ["H2", "O2"], "products": ["H2O"]},
        {"reactants": ["Fe2(SO4)3", "KOH"], "products": ["Fe(OH)3", "K2SO4"]},
    ]

    @staticmethod
    def _map_species(request, transform):
        return {
            side: [transform(species) for species in request[side]]
            for side in ("reactants", "products")
        }

    def test_uniform_formula_scaling_preserves_primitive_coefficients(self):
        # Multiplying every species' atom vector by the same factor changes
        # atom totals, but not the nullspace or its primitive coefficient ratio.
        for request in self.CASES:
            with self.subTest(request=request):
                original = balance_equation(request)
                for factor in (2, 3, 7):
                    transformed_request = self._map_species(
                        request, lambda formula: "(" + formula + ")" + str(factor))
                    transformed = balance_equation(transformed_request)
                    self.assertEqual(transformed["coefficients"], original["coefficients"])
                    for side in ("left", "right"):
                        expected = {element: factor * count
                                    for element, count in original["atom_counts"][side].items()}
                        self.assertEqual(transformed["atom_counts"][side], expected)
                    self.assertTrue(transformed["checks"]["ok"])

    def test_reordering_species_reorders_coefficients_but_preserves_totals(self):
        for request in self.CASES:
            with self.subTest(request=request):
                original = balance_equation(request)
                transformed_request = {
                    "reactants": list(reversed(request["reactants"])),
                    "products": list(reversed(request["products"])),
                }
                transformed = balance_equation(transformed_request)
                self.assertEqual(transformed["coefficients"]["reactants"],
                                 list(reversed(original["coefficients"]["reactants"])))
                self.assertEqual(transformed["coefficients"]["products"],
                                 list(reversed(original["coefficients"]["products"])))
                self.assertEqual(transformed["atom_counts"], original["atom_counts"])

    def test_ascii_and_unicode_subscripts_are_equivalent(self):
        to_subscript = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")
        for request in self.CASES:
            with self.subTest(request=request):
                original = balance_equation(request)
                transformed_request = self._map_species(request, lambda formula: formula.translate(to_subscript))
                transformed = balance_equation(transformed_request)
                self.assertEqual(transformed["coefficients"], original["coefficients"])
                self.assertEqual(transformed["atom_counts"], original["atom_counts"])

    def test_common_scaling_of_student_coefficients_preserves_balance(self):
        for request in self.CASES:
            with self.subTest(request=request):
                solution = balance_equation(request)["coefficients"]
                for factor in (2, 5):
                    checked = check_coefficients(request, {
                        "reactants": [factor * value for value in solution["reactants"]],
                        "products": [factor * value for value in solution["products"]],
                    })
                    self.assertTrue(checked["balanced"])
                    self.assertFalse(checked["primitive"])

    def test_coefficient_cap_transition_around_critical_value(self):
        # For H + O_n -> H2O, the primitive hydrogen coefficient is 2n.
        # n=500000 lands exactly on MAX_COEFFICIENT; n=500001 crosses it.
        for oxygen_count in (499999, 500000):
            with self.subTest(oxygen_count=oxygen_count):
                result = balance_equation({
                    "reactants": ["H", "O" + str(oxygen_count)],
                    "products": ["H2O"],
                })
                self.assertEqual(result["coefficients"], {
                    "reactants": [2 * oxygen_count, 1],
                    "products": [oxygen_count],
                })
                self.assertTrue(result["checks"]["ok"])

        with self.assertRaisesRegex(ValueError, "安全上限"):
            balance_equation({
                "reactants": ["H", "O500001"],
                "products": ["H2O"],
            })

    def test_atom_count_cap_accepts_boundary_and_rejects_next_value(self):
        result = balance_equation({"reactants": ["H1000000"], "products": ["H1000000"]})
        self.assertEqual(result["coefficients"], {"reactants": [1], "products": [1]})
        with self.assertRaisesRegex(ValueError, "原子数过大"):
            balance_equation({"reactants": ["H1000001"], "products": ["H1000001"]})


class CrossRuntimeParityTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node.js is not installed")
    def test_browser_solver_matches_python_reference(self):
        requests = [
            {"reactants": ["Fe", "CuSO4"], "products": ["FeSO4", "Cu"]},
            {"reactants": ["C3H8", "O2"], "products": ["CO2", "H2O"]},
            {"reactants": ["Fe2(SO4)3", "KOH"], "products": ["Fe(OH)3", "K2SO4"]},
            {"reactants": [{"formula": "Ag", "charge": 1}, {"formula": "Cl", "charge": -1}], "products": ["AgCl"]},
            {"reactants": ["CuSO4·5H2O"], "products": ["CuSO4", "H2O"]},
            {"reactants": ["H", "O500000"], "products": ["H2O"]},
        ]
        solver_path = os.path.abspath(os.path.join(HERE, "../../../../../frame/chem_solver.js"))
        source = r'''const fs=require('fs'),vm=require('vm');
const context={};context.window=context;vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),context);
const requests=JSON.parse(process.argv[2]);
process.stdout.write(JSON.stringify(requests.map(q=>context.CHEMSOLVER.balanceEquation(q))));'''
        proc = subprocess.run([shutil.which("node"), "-e", source, solver_path, json.dumps(requests)],
                              capture_output=True, text=True, check=True)
        js_results = json.loads(proc.stdout)
        py_results = [balance_equation(request) for request in requests]
        self.assertEqual(js_results, py_results)


if __name__ == "__main__":
    unittest.main()
