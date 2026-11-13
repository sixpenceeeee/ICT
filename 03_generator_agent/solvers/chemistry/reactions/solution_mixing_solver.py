# -*- coding: utf-8 -*-
"""Concentration/volume conversion followed by reaction stoichiometry."""

import math
import re

from chemistry.equations.equation_balancer import balance_equation
from chemistry.reactions.stoichiometry_solver import MAX_INITIAL_AMOUNT_MOL, solve_stoichiometry


MAX_CONCENTRATION_MOL_L = 1_000_000.0
MAX_VOLUME_INPUT = 1_000_000.0


def _finite_number(raw, label, minimum, maximum):
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
    if value < minimum:
        raise ValueError(label + "不能小于 %s" % minimum)
    if value > maximum:
        raise ValueError(label + "不能大于 %s" % maximum)
    return value


def _volume_unit(raw):
    if not isinstance(raw, str):
        raise ValueError("体积单位必须是 mL 或 L")
    key = raw.strip().lower()
    if key in ("ml", "毫升"):
        return "mL", 0.001
    if key in ("l", "升"):
        return "L", 1.0
    raise ValueError("不支持体积单位 %r；只支持 mL 或 L" % raw)


def solve_solution_mixing(request):
    """Convert solution molarity and volume to moles, then solve the reaction.

    Request schema:
      {reactants, products,
       solutions:[{concentration_mol_L, volume, volume_unit}, ...], progress?}
    Each solution entry aligns with one reactant. Products are supplied by the
    caller; this solver does not predict chemical reactions or precipitates.
    """
    if not isinstance(request, dict):
        raise ValueError("溶液混合请求必须是对象")
    balanced = balance_equation({
        "reactants": request.get("reactants"),
        "products": request.get("products"),
    })
    solutions_raw = request.get("solutions")
    if not isinstance(solutions_raw, list) or len(solutions_raw) != len(balanced["reactants"]):
        raise ValueError("solutions 数量必须与反应物数量一致")

    rows = []
    amounts = []
    for i, solution in enumerate(solutions_raw):
        if not isinstance(solution, dict):
            raise ValueError("第 %d 个溶液输入必须是对象" % (i + 1))
        formula = balanced["reactants"][i]["formula"]
        concentration = _finite_number(
            solution.get("concentration_mol_L"), "反应物 %s 浓度" % formula,
            0.0, MAX_CONCENTRATION_MOL_L)
        volume_input = _finite_number(
            solution.get("volume"), "反应物 %s 体积" % formula,
            0.0, MAX_VOLUME_INPUT)
        if volume_input == 0:
            raise ValueError("反应物 %s 的溶液体积必须大于 0" % formula)
        unit, to_litre = _volume_unit(solution.get("volume_unit"))
        volume_l = volume_input * to_litre
        amount_mol = concentration * volume_l
        if not math.isfinite(amount_mol) or amount_mol > MAX_INITIAL_AMOUNT_MOL:
            raise ValueError("反应物 %s 换算后的物质的量超过安全上限" % formula)
        amounts.append(amount_mol)
        rows.append({
            "index": i,
            "formula": formula,
            "concentration_mol_L": concentration,
            "volume_input": volume_input,
            "volume_unit": unit,
            "volume_L": volume_l,
            "amount_mol": amount_mol,
        })

    stoich = solve_stoichiometry({
        "reactants": request.get("reactants"),
        "products": request.get("products"),
        "initial_amounts_mol": amounts,
        "progress": request.get("progress", 1.0),
    })
    checks = dict(stoich["checks"])
    checks.update({
        "solution_inputs_valid": True,
        "concentration_volume_conversion": all(
            math.isclose(row["amount_mol"], row["concentration_mol_L"] * row["volume_L"],
                         rel_tol=1e-12, abs_tol=1e-15) for row in rows),
    })
    checks["ok"] = checks["ok"] and checks["solution_inputs_valid"] and checks["concentration_volume_conversion"]
    return {
        **stoich,
        "schema": "chem-solution-mixing.v1",
        "solution_inputs": rows,
        "checks": checks,
    }
