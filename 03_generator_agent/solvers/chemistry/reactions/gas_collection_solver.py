# -*- coding: utf-8 -*-
"""Reaction stoichiometry and ideal-gas collection-volume solver.

The caller supplies a balanced-or-balanceable reaction, reactant amounts,
and the formula of a gaseous product. Dry collection uses P V = n R T.
Collection over water subtracts the saturation vapor pressure of water using
the Antoine equation (valid here from 0 to 100 °C).
"""

import math
import re

from chemistry.reactions.stoichiometry_solver import solve_stoichiometry


GAS_CONSTANT_L_KPA_PER_MOL_K = 8.31446261815324
MAX_INITIAL_AMOUNT_MOL = 1_000_000.0
MAX_PRESSURE_KPA = 100_000.0
MIN_TEMPERATURE_C = -273.149
MAX_TEMPERATURE_C = 2_000.0


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
    if value < minimum or value > maximum:
        raise ValueError("%s必须在 %s 至 %s 范围内" % (label, minimum, maximum))
    return value


def water_vapor_pressure_kpa(temperature_c):
    """Saturation vapor pressure of water from Antoine (0–100 °C)."""
    temperature_c = _finite_number(temperature_c, "水上集气温度", 0.0, 100.0)
    # Antoine constants return pressure in mmHg. Convert to kPa.
    pressure_mmhg = 10 ** (8.07131 - 1730.63 / (233.426 + temperature_c))
    return pressure_mmhg * 0.133322368


def _gas_phase(phase):
    return str(phase or "").strip().lower() in ("g", "gas", "气", "气态")


def solve_gas_collection(request):
    """Compute collected target-gas volume after a specified reaction extent.

    Request example::

        {"reactants": [{"formula":"Zn","phase":"s"},
                       {"formula":"HCl","phase":"aq"}],
         "products": [{"formula":"ZnCl2","phase":"aq"},
                      {"formula":"H2","phase":"g"}],
         "initial_amounts_mol": [0.02, 0.05], "progress": 1,
         "gas_formula":"H2", "temperature_c":25,
         "total_pressure_kpa":101.325, "collection_method":"over_water"}

    The result models only the selected gaseous product. It does not predict
    reaction products, gas solubility, non-ideal-gas behavior, leaks, or yield.
    """
    if not isinstance(request, dict):
        raise ValueError("气体收集请求必须是对象")
    gas_formula = request.get("gas_formula")
    if not isinstance(gas_formula, str) or not gas_formula.strip():
        raise ValueError("必须指定目标气体 gas_formula")
    gas_formula = gas_formula.strip()
    temperature_c = _finite_number(request.get("temperature_c"), "温度", MIN_TEMPERATURE_C,
                                   MAX_TEMPERATURE_C)
    temperature_k = temperature_c + 273.15
    if temperature_k <= 0:
        raise ValueError("温度必须高于绝对零度")
    total_pressure = _finite_number(request.get("total_pressure_kpa"), "总压强", 1e-9,
                                    MAX_PRESSURE_KPA)
    method = request.get("collection_method", "dry")
    if method not in ("dry", "over_water"):
        raise ValueError("collection_method 只支持 dry 或 over_water")

    reaction = solve_stoichiometry({
        "reactants": request.get("reactants"),
        "products": request.get("products"),
        "initial_amounts_mol": request.get("initial_amounts_mol"),
        "progress": request.get("progress", 1.0),
    })
    matches = [item for item in reaction["products"] if item["formula"] == gas_formula]
    if len(matches) != 1:
        raise ValueError("目标气体必须且只能对应方程式中的一种生成物")
    gas = matches[0]
    if not _gas_phase(gas.get("phase")):
        raise ValueError("目标气体生成物必须将 phase 标记为 g/gas/气态")
    gas_moles = gas["produced_mol"]

    if method == "over_water":
        vapor_pressure = water_vapor_pressure_kpa(temperature_c)
        dry_gas_pressure = total_pressure - vapor_pressure
        if dry_gas_pressure <= 0:
            raise ValueError("总压强必须大于当前温度下水的饱和蒸气压")
        vapor_model = "Antoine-0-to-100C"
    else:
        vapor_pressure = 0.0
        dry_gas_pressure = total_pressure
        vapor_model = "none-dry-gas"

    gas_volume_l = gas_moles * GAS_CONSTANT_L_KPA_PER_MOL_K * temperature_k / dry_gas_pressure
    checks = {
        "reaction_balanced_and_conserved": bool(reaction["checks"]["ok"]),
        "target_is_single_gas_product": True,
        "gas_amount_matches_product_yield": math.isclose(
            gas_moles, gas["produced_mol"], rel_tol=1e-12, abs_tol=1e-15),
        "partial_pressure_decomposition": math.isclose(
            total_pressure, dry_gas_pressure + vapor_pressure, rel_tol=1e-12, abs_tol=1e-12),
        "ideal_gas_relation": math.isclose(
            dry_gas_pressure * gas_volume_l,
            gas_moles * GAS_CONSTANT_L_KPA_PER_MOL_K * temperature_k,
            rel_tol=1e-12, abs_tol=1e-15),
        "nonnegative_volume": gas_volume_l >= 0 and math.isfinite(gas_volume_l),
    }
    checks["ok"] = all(checks.values())

    return {
        **reaction,
        "schema": "chem-gas-collection.v1",
        "gas_formula": gas_formula,
        "gas_moles": gas_moles,
        "temperature_c": temperature_c,
        "temperature_k": temperature_k,
        "total_pressure_kpa": total_pressure,
        "collection_method": method,
        "water_vapor_pressure_kpa": vapor_pressure,
        "dry_gas_partial_pressure_kpa": dry_gas_pressure,
        "water_vapor_model": vapor_model,
        "gas_constant_l_kpa_mol_k": GAS_CONSTANT_L_KPA_PER_MOL_K,
        "gas_volume_l": gas_volume_l,
        "checks": checks,
    }
