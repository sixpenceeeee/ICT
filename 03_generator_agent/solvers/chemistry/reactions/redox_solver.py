# -*- coding: utf-8 -*-
"""Redox balancing with condition-specific H2O/H+/OH- completion.

The learner supplies the core ionic reactants and products, including their
charges.  The solver tries only water/proton/hydroxide placements appropriate
to the stated medium, then uses exact atom/charge balancing and checks the
oxidation-number electron transfer independently.
"""

from fractions import Fraction
from itertools import product
import math

from chemistry.equations.equation_balancer import balance_equation, parse_formula


_SUBSCRIPTS = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")
_ALKALI = {"Li", "Na", "K", "Rb", "Cs", "Fr"}
_ALKALINE_EARTH = {"Be", "Mg", "Ca", "Sr", "Ba", "Ra"}
_OXIDATION_RULES = {**{item: 1 for item in _ALKALI},
                    **{item: 2 for item in _ALKALINE_EARTH},
                    "Al": 3, "Zn": 2, "Ag": 1, "F": -1}
_AUXILIARIES = {
    "acidic": (("H2O", 0, "l"), ("H", 1, "aq")),
    "basic": (("H2O", 0, "l"), ("OH", -1, "aq")),
}
_MEDIUM_ALIASES = {
    "acidic": "acidic", "acid": "acidic", "酸性": "acidic",
    "basic": "basic", "base": "basic", "碱性": "basic", "鹼性": "basic",
}
_SUBSCRIPT_DISPLAY = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")
_SUPERSCRIPT_DISPLAY = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")


def _normalize_species(raw, label):
    if isinstance(raw, str):
        formula, charge, phase = raw, 0, ""
    elif isinstance(raw, dict):
        formula = raw.get("formula", raw.get("化学式"))
        if "charge" not in raw and "电荷" not in raw:
            raise ValueError(label + "必须明确提供整数电荷 charge（中性物质也填 0）")
        charge = raw.get("charge", raw.get("电荷", 0))
        phase = str(raw.get("phase", raw.get("状态", "")))
    else:
        raise ValueError(label + "必须是化学式或物质对象")
    if not isinstance(formula, str) or not formula.strip():
        raise ValueError(label + "缺少化学式")
    if isinstance(charge, bool) or not isinstance(charge, int) or abs(charge) > 100:
        raise ValueError(label + "电荷必须是 -100 到 100 的整数")
    formula = formula.strip().translate(_SUBSCRIPTS)
    atoms = parse_formula(formula)
    if (formula, charge) in (("H", 1), ("OH", -1)):
        raise ValueError("H+ 和 OH- 由溶液条件自动补入，请勿放入核心反应物")
    return {"formula": formula, "charge": charge, "phase": phase, "atoms": atoms}


def _medium(raw):
    if not isinstance(raw, str) or raw.strip().lower() not in _MEDIUM_ALIASES:
        raise ValueError("medium 必须明确指定 acidic/酸性 或 basic/碱性")
    return _MEDIUM_ALIASES[raw.strip().lower()]


def _oxidation_states(species):
    """Return average oxidation state per element for common school species."""
    atoms = species["atoms"]
    formula = species["formula"]
    charge = species["charge"]
    if len(atoms) == 1:
        element, count = next(iter(atoms.items()))
        return {element: Fraction(charge, count)}

    known = {}
    for element in atoms:
        if element in _OXIDATION_RULES:
            known[element] = Fraction(_OXIDATION_RULES[element])
        elif element == "H":
            known[element] = Fraction(1)
        elif element == "O":
            known[element] = Fraction(-2)
        elif element in {"Cl", "Br", "I"} and "O" not in atoms and "F" not in atoms:
            known[element] = Fraction(-1)

    # Peroxides and superoxides: infer the oxygen average from the known
    # counter-ion instead of incorrectly forcing oxygen to -2.
    if "O" in atoms and atoms["O"] >= 2 and all(
            element == "O" or element in known for element in atoms):
        remainder = Fraction(charge) - sum(
            atoms[element] * state for element, state in known.items() if element != "O")
        if remainder < 0 and abs(remainder) <= atoms["O"]:
            known["O"] = remainder / atoms["O"]

    unknown = [element for element in atoms if element not in known]
    if not unknown:
        if sum(atoms[element] * state for element, state in known.items()) != charge:
            raise ValueError("%s 的常见氧化数规则与总电荷不符" % formula)
        return known
    if len(unknown) != 1:
        raise ValueError("无法唯一判定 %s 中各元素氧化数；首版不支持该化学式" % formula)
    element = unknown[0]
    residual = Fraction(charge) - sum(
        atoms[key] * state for key, state in known.items())
    known[element] = residual / atoms[element]
    if any(state.denominator != 1 for state in known.values()):
        raise ValueError("%s 中存在平均氧化数，首版无法区分混合价态" % formula)
    return known


def _json_number(value):
    value = Fraction(value)
    if value.denominator == 1:
        return value.numerator
    return float(value)


def _display_equation(items_left, coeff_left, items_right, coeff_right):
    def side(items, coefficients):
        rendered = []
        for item, coefficient in zip(items, coefficients):
            formula = item["formula"].translate(_SUBSCRIPT_DISPLAY)
            charge = item["charge"]
            if charge:
                magnitude = "" if abs(charge) == 1 else str(abs(charge)).translate(_SUPERSCRIPT_DISPLAY)
                formula += magnitude + ("⁺" if charge > 0 else "⁻")
            phase = "(" + item["phase"] + ")" if item["phase"] else ""
            rendered.append((str(coefficient) if coefficient != 1 else "") + formula + phase)
        return " + ".join(rendered)
    return side(items_left, coeff_left) + " → " + side(items_right, coeff_right)


def _redox_analysis(balanced, reactant_core_count, product_core_count):
    reactants, products = balanced["reactants"], balanced["products"]
    coeff_r, coeff_p = balanced["coefficients"]["reactants"], balanced["coefficients"]["products"]
    # Include condition auxiliaries in atom-weighted oxidation-state totals.
    # H+/OH-/H2O are not redox-active in ordinary cases, but their atoms must
    # be present for oxygen/hydrogen totals to be compared correctly.
    core_r, core_p = reactants, products
    core_coeff_r, core_coeff_p = coeff_r, coeff_p
    elements = sorted({element for item in core_r + core_p for element in item["atoms"]})
    states_r = [_oxidation_states(item) for item in core_r]
    states_p = [_oxidation_states(item) for item in core_p]
    changes = []
    electrons_lost = Fraction(0)
    electrons_gained = Fraction(0)
    for element in elements:
        distribution_r = [(states[element], item["atoms"].get(element, 0) * coeff)
                          for item, coeff, states in zip(core_r, core_coeff_r, states_r)
                          if element in item["atoms"]]
        distribution_p = [(states[element], item["atoms"].get(element, 0) * coeff)
                          for item, coeff, states in zip(core_p, core_coeff_p, states_p)
                          if element in item["atoms"]]
        atom_count_r = sum(count for _, count in distribution_r)
        atom_count_p = sum(count for _, count in distribution_p)
        if not atom_count_r and not atom_count_p:
            continue
        if atom_count_r != atom_count_p:
            raise ValueError("元素 %s 的反应物/生成物原子数不守恒" % element)
        if not atom_count_r:
            continue
        # Sort and pair oxidation-state distributions. This also detects
        # disproportionation (one element is oxidized and reduced at once),
        # which a simple before/after average would incorrectly cancel out.
        distribution_r.sort(key=lambda row: row[0])
        distribution_p.sort(key=lambda row: row[0])
        ri = pi = 0
        rleft, pleft = distribution_r[0][1], distribution_p[0][1]
        while ri < len(distribution_r) and pi < len(distribution_p):
            before, after = distribution_r[ri][0], distribution_p[pi][0]
            amount = min(rleft, pleft)
            delta = after - before
            if delta:
                lost = amount * delta if delta > 0 else Fraction(0)
                gained = amount * -delta if delta < 0 else Fraction(0)
                electrons_lost += lost
                electrons_gained += gained
                changes.append({"element": element, "atoms_per_reaction": amount,
                                "before": before, "after": after, "delta": delta,
                                "electrons_lost": lost, "electrons_gained": gained})
            rleft -= amount
            pleft -= amount
            if not rleft:
                ri += 1
                if ri < len(distribution_r):
                    rleft = distribution_r[ri][1]
            if not pleft:
                pi += 1
                if pi < len(distribution_p):
                    pleft = distribution_p[pi][1]
    if not changes or electrons_lost <= 0 or electrons_gained <= 0:
        raise ValueError("输入物质中未识别到成对的氧化数升高与降低，不能判定为氧化还原反应")
    if electrons_lost != electrons_gained:
        raise ValueError("按氧化数独立计算的失电子与得电子不相等")
    for row in changes:
        for key in ("atoms_per_reaction", "before", "after", "delta", "electrons_lost", "electrons_gained"):
            row[key] = _json_number(row[key])
    return changes, _json_number(electrons_lost), _json_number(electrons_gained)


def solve_redox(request):
    """Balance an ionic redox equation, adding H2O and H+/OH- for its medium.

    Input: {medium:'acidic'|'basic', reactants:[species], products:[species]}.
    The input species are the chemistry-specific core, without H2O, H+, OH-.
    """
    if not isinstance(request, dict):
        raise ValueError("氧化还原请求必须是对象")
    medium = _medium(request.get("medium"))
    reactants_raw, products_raw = request.get("reactants"), request.get("products")
    if not isinstance(reactants_raw, list) or not reactants_raw or not isinstance(products_raw, list) or not products_raw:
        raise ValueError("反应物和生成物两侧都必须提供核心物质数组")
    if len(reactants_raw) + len(products_raw) > 10:
        raise ValueError("核心物质种类总数不能超过 10")
    reactants = [_normalize_species(item, "反应物第 %d 项" % (i + 1))
                 for i, item in enumerate(reactants_raw)]
    products = [_normalize_species(item, "生成物第 %d 项" % (i + 1))
                for i, item in enumerate(products_raw)]
    for item in reactants + products:
        _oxidation_states(item)
    for side, rows in (("反应物", reactants), ("生成物", products)):
        keys = [(row["formula"], row["charge"]) for row in rows]
        if len(keys) != len(set(keys)):
            raise ValueError(side + "中有重复的同种物质，请合并后再输入")

    auxiliary = _AUXILIARIES[medium]
    candidates = []
    errors = []
    # Each condition species is either absent, on the left, or on the right.
    # This is a finite search over at most nine placements, not model guessing.
    contains_water = any(row["formula"] == "H2O" and row["charge"] == 0
                         for row in reactants + products)
    water_choices = (0,) if contains_water else (0, 1, -1)
    for water_side, ion_side in product(water_choices, (0, 1, -1)):
        additions_left, additions_right = [], []
        additions_count = 0
        for (formula, charge, phase), side in zip(auxiliary, (water_side, ion_side)):
            if side == 0:
                continue
            additions_count += 1
            row = {"formula": formula, "charge": charge, "phase": phase}
            (additions_left if side == 1 else additions_right).append(row)
        try:
            balanced = balance_equation({
                "reactants": [*reactants_raw, *additions_left],
                "products": [*products_raw, *additions_right],
            })
            changes, lost, gained = _redox_analysis(balanced, len(reactants), len(products))
        except (TypeError, ValueError) as exc:
            errors.append(str(exc))
            continue
        coeff_r, coeff_p = balanced["coefficients"]["reactants"], balanced["coefficients"]["products"]
        candidates.append((additions_count, sum(coeff_r) + sum(coeff_p), balanced, changes, lost, gained))
    if not candidates:
        detail = next((error for error in errors if "氧化还原反应" in error or "氧化数" in error), None)
        raise ValueError(detail or "无法在指定酸碱条件下获得唯一的正整数氧化还原方程式")
    candidates.sort(key=lambda row: (row[0], row[1]))
    _, _, balanced, changes, lost, gained = candidates[0]
    electron_balance = {
        "lost_electrons": lost, "gained_electrons": gained,
        "transferred_electrons": lost, "ok": math.isclose(lost, gained, rel_tol=0, abs_tol=1e-12),
    }
    checks = {
        "atoms_balanced": balanced["checks"]["atoms_balanced"],
        "charge_balanced": balanced["checks"]["charge_balanced"],
        "primitive_coefficients": balanced["checks"]["primitive_coefficients"],
        "oxidation_number_changes_detected": bool(changes),
        "electron_transfer_balanced": electron_balance["ok"],
    }
    checks["ok"] = all(checks.values())
    return {
        "schema": "chem-redox.v1", "medium": medium,
        "equation": _display_equation(balanced["reactants"], balanced["coefficients"]["reactants"],
                                      balanced["products"], balanced["coefficients"]["products"]),
        "coefficients": balanced["coefficients"],
        "reactants": balanced["reactants"], "products": balanced["products"],
        "oxidation_changes": changes, "electron_balance": electron_balance,
        "atom_counts": balanced["atom_counts"], "charge_counts": balanced["charge_counts"],
        "checks": checks,
    }
