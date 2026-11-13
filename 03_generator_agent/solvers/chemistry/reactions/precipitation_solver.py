# -*- coding: utf-8 -*-
"""Curated middle-school precipitation reaction solver.

The solver deliberately recognizes only a small catalog of classroom reactions.
It does not guess products from arbitrary salts or model solubility equilibria.
"""

import math

from chemistry.equations.equation_balancer import balance_equation, parse_formula
from chemistry.reactions.solution_mixing_solver import solve_solution_mixing


ATOMIC_MASSES_G_MOL = {
    "H": 1.008, "C": 12.011, "N": 14.007, "O": 15.999,
    "Na": 22.989769, "Mg": 24.305, "S": 32.06, "Cl": 35.45,
    "Ca": 40.078, "Fe": 55.845, "Cu": 63.546, "Ag": 107.8682,
    "Ba": 137.327,
}

REACTION_CATALOG = (
    {
        "id": "silver-chloride",
        "reactants": ("AgNO3", "NaCl"),
        "products": (("AgCl", "s"), ("NaNO3", "aq")),
        "precipitate_formula": "AgCl",
        "net_ionic_equation": "Ag⁺(aq) + Cl⁻(aq) → AgCl(s)",
        "net_ionic_reactants": (("Ag", 1), ("Cl", -1)),
    },
    {
        "id": "barium-sulfate",
        "reactants": ("BaCl2", "Na2SO4"),
        "products": (("BaSO4", "s"), ("NaCl", "aq")),
        "precipitate_formula": "BaSO4",
        "net_ionic_equation": "Ba²⁺(aq) + SO₄²⁻(aq) → BaSO₄(s)",
        "net_ionic_reactants": (("Ba", 2), ("SO4", -2)),
    },
    {
        "id": "calcium-carbonate",
        "reactants": ("CaCl2", "Na2CO3"),
        "products": (("CaCO3", "s"), ("NaCl", "aq")),
        "precipitate_formula": "CaCO3",
        "net_ionic_equation": "Ca²⁺(aq) + CO₃²⁻(aq) → CaCO₃(s)",
        "net_ionic_reactants": (("Ca", 2), ("CO3", -2)),
    },
    {
        "id": "copper-hydroxide",
        "reactants": ("CuSO4", "NaOH"),
        "products": (("Cu(OH)2", "s"), ("Na2SO4", "aq")),
        "precipitate_formula": "Cu(OH)2",
        "net_ionic_equation": "Cu²⁺(aq) + 2OH⁻(aq) → Cu(OH)₂(s)",
        "net_ionic_reactants": (("Cu", 2), ("OH", -1)),
    },
    {
        "id": "iron-iii-hydroxide",
        "reactants": ("FeCl3", "NaOH"),
        "products": (("Fe(OH)3", "s"), ("NaCl", "aq")),
        "precipitate_formula": "Fe(OH)3",
        "net_ionic_equation": "Fe³⁺(aq) + 3OH⁻(aq) → Fe(OH)₃(s)",
        "net_ionic_reactants": (("Fe", 3), ("OH", -1)),
    },
    {
        "id": "magnesium-hydroxide",
        "reactants": ("MgSO4", "NaOH"),
        "products": (("Mg(OH)2", "s"), ("Na2SO4", "aq")),
        "precipitate_formula": "Mg(OH)2",
        "net_ionic_equation": "Mg²⁺(aq) + 2OH⁻(aq) → Mg(OH)₂(s)",
        "net_ionic_reactants": (("Mg", 2), ("OH", -1)),
    },
)


def _canonical_formula(raw):
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("每份溶液都必须提供溶质化学式 formula")
    formula = raw.strip().translate(str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789"))
    parse_formula(formula)  # reject malformed formula before catalog lookup
    return formula


def _molar_mass(formula):
    atoms = parse_formula(formula)
    unknown = sorted(set(atoms) - set(ATOMIC_MASSES_G_MOL))
    if unknown:
        raise ValueError("沉淀摩尔质量缺少元素原子量：" + ", ".join(unknown))
    return round(sum(ATOMIC_MASSES_G_MOL[element] * count for element, count in atoms.items()), 9)


def _find_reaction(formulas):
    if len(formulas) != 2 or formulas[0] == formulas[1]:
        raise ValueError("首版只支持两种不同溶质的混合")
    wanted = frozenset(formulas)
    for item in REACTION_CATALOG:
        if wanted == frozenset(item["reactants"]):
            return item
    raise ValueError("该溶液组合不在首版沉淀反应目录中；请勿把未识别组合判为无沉淀")


def solve_precipitation(request):
    """Solve a catalogued precipitation reaction from solution concentrations.

    Request::

        {"solutions":[
           {"formula":"BaCl2","concentration_mol_L":0.2,"volume":50,"volume_unit":"mL"},
           {"formula":"Na2SO4","concentration_mol_L":0.15,"volume":100,"volume_unit":"mL"}],
         "progress":1}
    """
    if not isinstance(request, dict):
        raise ValueError("沉淀反应请求必须是对象")
    solutions_raw = request.get("solutions")
    if not isinstance(solutions_raw, list) or len(solutions_raw) != 2:
        raise ValueError("首版必须提供两份溶液 solutions")
    formulas = [_canonical_formula(item.get("formula") if isinstance(item, dict) else None)
                for item in solutions_raw]
    reaction = _find_reaction(formulas)
    solution_by_formula = {formula: item for formula, item in zip(formulas, solutions_raw)}
    ordered_solutions = [solution_by_formula[formula] for formula in reaction["reactants"]]
    reactants = [{"formula": formula, "phase": "aq"} for formula in reaction["reactants"]]
    products = [{"formula": formula, "phase": phase} for formula, phase in reaction["products"]]

    mixing = solve_solution_mixing({
        "reactants": reactants,
        "products": products,
        "solutions": [{key: solution.get(key) for key in
                       ("concentration_mol_L", "volume", "volume_unit")}
                      for solution in ordered_solutions],
        "progress": request.get("progress", 1.0),
    })
    precipitate_formula = reaction["precipitate_formula"]
    precipitate = next((item for item in mixing["products"]
                        if item["formula"] == precipitate_formula and item["phase"] == "s"), None)
    if precipitate is None:
        raise ValueError("目录反应的沉淀必须是方程式中的固态生成物")
    molar_mass = _molar_mass(precipitate_formula)
    net_ionic_balance = balance_equation({
        "reactants": [{"formula": formula, "charge": charge, "phase": "aq"}
                      for formula, charge in reaction["net_ionic_reactants"]],
        "products": [{"formula": precipitate_formula, "charge": 0, "phase": "s"}],
    })
    moles = precipitate["produced_mol"]
    mass = moles * molar_mass
    checks = dict(mixing["checks"])
    checks.update({
        "catalog_reaction_recognized": True,
        "precipitate_is_solid_product": True,
        "net_ionic_equation_balanced": bool(net_ionic_balance["checks"]["ok"]),
        "molar_mass_from_formula": math.isfinite(molar_mass) and molar_mass > 0,
        "precipitate_mass_calculation": math.isclose(mass, moles * molar_mass,
                                                     rel_tol=1e-12, abs_tol=1e-15),
        "nonnegative_precipitate": moles >= 0 and mass >= 0,
    })
    checks["ok"] = all(checks.values())
    return {
        **mixing,
        "schema": "chem-precipitation.v1",
        "reaction_id": reaction["id"],
        "precipitate_formula": precipitate_formula,
        "precipitate_moles": moles,
        "precipitate_molar_mass_g_mol": molar_mass,
        "precipitate_mass_g": mass,
        "precipitation_occurs": moles > 1e-15,
        "net_ionic_equation": reaction["net_ionic_equation"],
        "net_ionic_balance": net_ionic_balance,
        "checks": checks,
    }
