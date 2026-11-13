# -*- coding: utf-8 -*-
"""Strong monoprotic acid–strong monobasic base titration solver.

This educational model supports HCl, HBr, HI, HNO3, or HClO4 titrated by
LiOH, NaOH, or KOH. It assumes ideal, complete dissociation at 25 °C and
includes water autoionization near the equivalence point. Weak acids/bases,
polyprotic species, activity corrections, and indicators are out of scope.
"""

import math
import re

from chemistry.equations.equation_balancer import balance_equation


MAX_CONCENTRATION_MOL_L = 1.0
MAX_VOLUME_INPUT = 1_000_000.0
MAX_AMOUNT_MOL = 1_000_000.0
KW_25C = 1e-14
PH_TOLERANCE = 1e-10

_ACIDS = {
    "HCl": "Cl", "HBr": "Br", "HI": "I", "HNO3": "NO3", "HClO4": "ClO4",
}
_BASES = {"LiOH": "Li", "NaOH": "Na", "KOH": "K"}


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


def _volume_unit(raw, label):
    if not isinstance(raw, str):
        raise ValueError(label + "单位必须是 mL 或 L")
    key = raw.strip().lower()
    if key in ("ml", "毫升"):
        return "mL", 0.001
    if key in ("l", "升"):
        return "L", 1.0
    raise ValueError(label + "单位只支持 mL 或 L")


def _solution(raw, label, *, allow_zero_volume):
    if not isinstance(raw, dict):
        raise ValueError(label + "输入必须是对象")
    formula = raw.get("formula")
    concentration = _finite_number(
        raw.get("concentration_mol_L"), label + "浓度", 0.0, MAX_CONCENTRATION_MOL_L)
    if concentration <= 0:
        raise ValueError(label + "浓度必须大于 0")
    volume_input = _finite_number(
        raw.get("volume"), label + "体积", 0.0, MAX_VOLUME_INPUT)
    if volume_input <= 0 and not allow_zero_volume:
        raise ValueError(label + "体积必须大于 0")
    unit, to_litre = _volume_unit(raw.get("volume_unit"), label)
    volume_l = volume_input * to_litre
    amount = concentration * volume_l
    if not math.isfinite(amount) or amount > MAX_AMOUNT_MOL:
        raise ValueError(label + "物质的量超过安全上限")
    return {
        "formula": formula,
        "concentration_mol_L": concentration,
        "volume_input": volume_input,
        "volume_unit": unit,
        "volume_L": volume_l,
        "amount_mol": amount,
    }


def solve_acid_base_titration(request):
    """Compute a strong monoprotic acid titrated by a strong monobasic base.

    Request example::

        {"acid": {"formula": "HCl", "concentration_mol_L": 0.1,
                   "volume": 25, "volume_unit": "mL"},
         "base": {"formula": "NaOH", "concentration_mol_L": 0.1,
                   "volume": 24, "volume_unit": "mL"}}

    The solution assumes 1:1 neutralization and ideal concentrations at 25 °C.
    """
    if not isinstance(request, dict):
        raise ValueError("酸碱滴定请求必须是对象")
    acid = _solution(request.get("acid"), "酸液", allow_zero_volume=False)
    base = _solution(request.get("base"), "碱液", allow_zero_volume=True)
    acid_formula = acid["formula"]
    base_formula = base["formula"]
    if not isinstance(acid_formula, str) or not isinstance(base_formula, str):
        raise ValueError("酸、碱必须以支持的化学式字符串指定")
    if acid_formula not in _ACIDS:
        raise ValueError("当前只支持强一元酸 HCl、HBr、HI、HNO3、HClO4")
    if base_formula not in _BASES:
        raise ValueError("当前只支持强一元碱 LiOH、NaOH、KOH")

    salt_formula = _BASES[base_formula] + _ACIDS[acid_formula]
    balanced = balance_equation({
        "reactants": [
            {"formula": acid_formula, "phase": "aq"},
            {"formula": base_formula, "phase": "aq"},
        ],
        "products": [
            {"formula": salt_formula, "phase": "aq"},
            {"formula": "H2O", "phase": "l"},
        ],
    })
    if balanced["coefficients"] != {"reactants": [1, 1], "products": [1, 1]}:
        raise ValueError("该酸碱组合不符合当前 1:1 中和模型")

    acid_mol = acid["amount_mol"]
    base_mol = base["amount_mol"]
    reacted_mol = min(acid_mol, base_mol)
    acid_remaining = acid_mol - reacted_mol
    base_remaining = base_mol - reacted_mol
    total_volume_l = acid["volume_L"] + base["volume_L"]
    if not math.isfinite(total_volume_l) or total_volume_l <= 0:
        raise ValueError("混合后的总体积必须大于 0")

    net_acid_concentration = (acid_mol - base_mol) / total_volume_l
    water_root = math.sqrt(net_acid_concentration * net_acid_concentration + 4 * KW_25C)
    if net_acid_concentration >= 0:
        hydrogen = 0.5 * (net_acid_concentration + water_root)
        hydroxide = KW_25C / hydrogen
    else:
        hydroxide = 0.5 * (-net_acid_concentration + water_root)
        hydrogen = KW_25C / hydroxide
    ph = -math.log10(hydrogen)
    poh = -math.log10(hydroxide)

    balance_tolerance = max(1e-15, max(acid_mol, base_mol) * 1e-12)
    if acid_mol - base_mol > balance_tolerance:
        state = "acidic"
    elif base_mol - acid_mol > balance_tolerance:
        state = "basic"
    else:
        state = "equivalence"
    neutralization_fraction = reacted_mol / acid_mol
    equivalence_volume_l = acid_mol / base["concentration_mol_L"]
    checks = {
        "equation_balanced": bool(balanced["checks"]["ok"]),
        "acid_mole_balance": math.isclose(acid_mol, reacted_mol + acid_remaining,
                                           rel_tol=1e-12, abs_tol=1e-15),
        "base_mole_balance": math.isclose(base_mol, reacted_mol + base_remaining,
                                           rel_tol=1e-12, abs_tol=1e-15),
        "nonnegative_excess": acid_remaining >= 0 and base_remaining >= 0,
        "water_ion_product": math.isclose(hydrogen * hydroxide, KW_25C,
                                           rel_tol=1e-10, abs_tol=1e-24),
        "ph_poh_sum": math.isclose(ph + poh, 14.0, rel_tol=0.0, abs_tol=1e-10),
    }
    checks["ok"] = all(checks.values()) and all(math.isfinite(value) for value in (
        ph, poh, hydrogen, hydroxide, equivalence_volume_l, total_volume_l))

    return {
        "schema": "chem-acid-base-titration.v1",
        "temperature_c": 25.0,
        "equation": balanced["equation"],
        "acid": acid,
        "base": base,
        "salt_formula": salt_formula,
        "acid_moles_initial": acid_mol,
        "base_moles_added": base_mol,
        "neutralized_moles": reacted_mol,
        "acid_moles_remaining": acid_remaining,
        "base_moles_remaining": base_remaining,
        "equivalence_volume_l": equivalence_volume_l,
        "equivalence_volume_ml": equivalence_volume_l * 1000.0,
        "total_volume_l": total_volume_l,
        "net_acid_concentration_mol_L": net_acid_concentration,
        "excess_acid_concentration_mol_L": acid_remaining / total_volume_l,
        "excess_base_concentration_mol_L": base_remaining / total_volume_l,
        "hydrogen_concentration_mol_L": hydrogen,
        "hydroxide_concentration_mol_L": hydroxide,
        "neutralization_fraction": neutralization_fraction,
        "pH": ph,
        "pOH": poh,
        "state": state,
        "checks": checks,
    }
