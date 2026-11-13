# -*- coding: utf-8 -*-
"""Reaction extent, limiting-reagent, and amount-of-substance solver."""

import math
import re

from chemistry.equations.equation_balancer import balance_equation


MAX_INITIAL_AMOUNT_MOL = 1_000_000.0
MAX_PROGRESS = 1.0


def _finite_number(raw, label, minimum=None, maximum=None):
    if isinstance(raw, bool):
        raise ValueError(label + "必须是有限数值")
    if isinstance(raw, str) and not re.fullmatch(
            r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", raw.strip()):
        raise ValueError(label + "必须是有限数值")
    try:
        value = float(raw)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(label + "必须是有限数值") from exc
    if not math.isfinite(value):
        raise ValueError(label + "必须是有限数值")
    if minimum is not None and value < minimum:
        raise ValueError(label + "不能小于 %s" % minimum)
    if maximum is not None and value > maximum:
        raise ValueError(label + "不能大于 %s" % maximum)
    return value


def _totals(items, amounts, elements):
    atom_moles = {element: 0.0 for element in elements}
    charge_moles = 0.0
    for item, amount in zip(items, amounts):
        for element in elements:
            atom_moles[element] += item["atoms"].get(element, 0) * amount
        charge_moles += item["charge"] * amount
    return atom_moles, charge_moles


def _conserved(initial, final):
    errors = {key: abs(initial.get(key, 0.0) - final.get(key, 0.0))
              for key in sorted(set(initial) | set(final))}
    ok = all(error <= max(1e-12, abs(initial.get(key, 0.0)) * 1e-10)
             for key, error in errors.items())
    return {"initial_mol": initial, "final_mol": final,
            "absolute_error_mol": errors, "ok": ok}


def solve_stoichiometry(request):
    """Solve a specified reaction at a selected fraction of maximum extent.

    Input:
      {reactants, products, initial_amounts_mol:[...], progress:0..1}
    Amounts align with reactants. The solver balances the supplied species
    itself and never predicts products.
    """
    if not isinstance(request, dict):
        raise ValueError("反应计量请求必须是对象")
    amounts_raw = request.get("initial_amounts_mol")
    reactants_raw = request.get("reactants")
    products_raw = request.get("products")
    if not isinstance(amounts_raw, list):
        raise ValueError("initial_amounts_mol 必须是与反应物一一对应的数组")

    balanced = balance_equation({"reactants": reactants_raw, "products": products_raw})
    reactants = balanced["reactants"]
    products = balanced["products"]
    coeff_r = balanced["coefficients"]["reactants"]
    coeff_p = balanced["coefficients"]["products"]
    if len(amounts_raw) != len(reactants):
        raise ValueError("初始物质的量数量必须与反应物数量一致")

    initial = [_finite_number(value, "反应物 %s 初始物质的量" % reactants[i]["formula"],
                              minimum=0.0, maximum=MAX_INITIAL_AMOUNT_MOL)
               for i, value in enumerate(amounts_raw)]
    if not any(value > 0 for value in initial):
        raise ValueError("至少一种反应物的初始物质的量必须大于 0")
    progress = _finite_number(request.get("progress", 1.0), "反应进度",
                              minimum=0.0, maximum=MAX_PROGRESS)

    extents = [amount / coefficient for amount, coefficient in zip(initial, coeff_r)]
    max_extent = min(extents)
    extent_tol = max(1e-30, abs(max_extent) * 1e-10)
    limiting_indices = [i for i, value in enumerate(extents)
                        if abs(value - max_extent) <= extent_tol]
    extent = max_extent * progress

    consumed = [coefficient * extent for coefficient in coeff_r]
    remaining = []
    no_negative = True
    for initial_amount, used in zip(initial, consumed):
        value = initial_amount - used
        tol = max(1e-12, abs(initial_amount) * 1e-10)
        if value < 0 and abs(value) <= tol:
            value = 0.0
        elif value < 0:
            no_negative = False
        remaining.append(value)
    produced = [coefficient * extent for coefficient in coeff_p]

    elements = balanced["elements"]
    initial_atoms, initial_charge = _totals(reactants, initial, elements)
    final_reactant_atoms, final_reactant_charge = _totals(reactants, remaining, elements)
    product_atoms, product_charge = _totals(products, produced, elements)
    final_atoms = {element: final_reactant_atoms[element] + product_atoms[element]
                   for element in elements}
    element_balance = _conserved(initial_atoms, final_atoms)
    charge_balance = _conserved({"charge": initial_charge},
                                {"charge": final_reactant_charge + product_charge})

    reactant_rows = []
    for i, item in enumerate(reactants):
        reactant_rows.append({
            "index": i, "formula": item["formula"], "phase": item["phase"],
            "coefficient": coeff_r[i], "initial_mol": initial[i],
            "consumed_mol": consumed[i], "remaining_mol": remaining[i],
        })
    product_rows = []
    for i, item in enumerate(products):
        product_rows.append({
            "index": i, "formula": item["formula"], "phase": item["phase"],
            "coefficient": coeff_p[i], "produced_mol": produced[i],
        })
    limiting = [{"index": i, "formula": reactants[i]["formula"]}
                for i in limiting_indices]
    checks = {
        "equation_balanced": balanced["checks"]["ok"],
        "no_negative_remaining": no_negative,
        "element_conservation": element_balance["ok"],
        "charge_conservation": charge_balance["ok"],
        "limiting_reagents_defined": bool(limiting),
        "ok": balanced["checks"]["ok"] and no_negative and
              element_balance["ok"] and charge_balance["ok"] and bool(limiting),
    }
    return {
        "schema": "chem-stoichiometry.v1",
        "equation": balanced["equation"],
        "coefficients": balanced["coefficients"],
        "initial_amounts_mol": initial,
        "progress": progress,
        "max_extent_mol": max_extent,
        "extent_mol": extent,
        "limiting_reactants": limiting,
        "stoichiometric_mix": len(limiting_indices) == len(reactants),
        "reactants": reactant_rows,
        "products": product_rows,
        "element_balance": element_balance,
        "charge_balance": charge_balance,
        "checks": checks,
    }
