# -*- coding: utf-8 -*-
"""Ksp equilibrium, molar-solubility and ion-product solver.

Ionic species and their dissolution stoichiometry are explicit inputs.  The
solver checks that those ions reconstruct the stated solid formula and neutral
charge, then solves the monotone mass-action equation in logarithmic space.
It classifies supersaturated mixtures but does not calculate precipitate yield.
"""

import math

from chemistry.equations.equation_balancer import parse_formula


MIN_KSP = 1e-80
MAX_KSP = 1e6
MAX_CONCENTRATION_MOL_L = 1e3
MAX_TOTAL_EXPONENT = 12

_SUBSCRIPTS = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")
_SUBSCRIPT_DISPLAY = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")
_SUPERSCRIPT_DISPLAY = str.maketrans("0123456789-+", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺")


def _number(raw, label, minimum, maximum):
    if isinstance(raw, bool) or raw is None or isinstance(raw, (dict, list, tuple)):
        raise ValueError(label + "必须是有限数值")
    try:
        value = float(raw)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(label + "必须是有限数值") from exc
    if not math.isfinite(value) or value < minimum or value > maximum:
        raise ValueError("%s 必须在 %s 到 %s 之间" % (label, minimum, maximum))
    return value


def _log_ion_product(ions, concentrations):
    total = 0.0
    for ion, concentration in zip(ions, concentrations):
        if concentration <= 0:
            return -math.inf
        total += ion["coefficient"] * math.log(concentration)
    return total


def _exp_clamped(log_value):
    if log_value == -math.inf or log_value < -745:
        return 0.0
    if log_value > math.log(1e300):
        return 1e300
    return math.exp(log_value)


def _display_species(ion):
    formula = ion["formula"].translate(_SUBSCRIPT_DISPLAY)
    charge = ion["charge"]
    magnitude = "" if abs(charge) == 1 else str(abs(charge)).translate(_SUPERSCRIPT_DISPLAY)
    return (str(ion["coefficient"]) if ion["coefficient"] != 1 else "") + formula + magnitude + (
        "⁺" if charge > 0 else "⁻") + "(aq)"


def _solve_positive_solubility(ions, background, log_ksp):
    """Bisect in log(s), avoiding loss of precision for small Ksp values."""
    def residual(log_s):
        solubility = math.exp(log_s)
        concentrations = [initial + ion["coefficient"] * solubility
                         for ion, initial in zip(ions, background)]
        return _log_ion_product(ions, concentrations) - log_ksp

    low = -700.0
    high = 0.0  # s = 1 mol/L
    if residual(low) >= 0:
        raise ValueError("Ksp 太小，超出首版溶解度数值范围")
    while residual(high) < 0 and high < math.log(1e6):
        high = min(high + math.log(2), math.log(1e6))
    if residual(high) < 0:
        raise ValueError("给定 Ksp 对应的溶解度超出首版数值范围")
    for _ in range(180):
        middle = (low + high) / 2
        if residual(middle) < 0:
            low = middle
        else:
            high = middle
    return math.exp((low + high) / 2)


def solve_solubility_equilibrium(request):
    """Evaluate a sparingly soluble solid's Ksp and common-ion equilibrium.

    Request::
      {"solid_formula":"CaF2", "Ksp":4e-11,
       "ions":[{"formula":"Ca","charge":2,"coefficient":1,
                 "initial_concentration_mol_L":0},
               {"formula":"F","charge":-1,"coefficient":2,
                 "initial_concentration_mol_L":0}]}

    Initial concentrations are the dissolved ions before adding excess solid.
    If the initial ion product is below Ksp, the returned molar solubility is
    the additional dissolution required to reach saturation. Supersaturated
    inputs are classified, but precipitation extent/equilibrium is not modeled.
    """
    if not isinstance(request, dict):
        raise ValueError("溶解平衡请求必须是对象")
    solid_raw = request.get("solid_formula", request.get("solid"))
    if not isinstance(solid_raw, str) or not solid_raw.strip():
        raise ValueError("必须提供难溶固体化学式 solid_formula")
    solid_formula = solid_raw.strip().translate(_SUBSCRIPTS)
    solid_atoms = parse_formula(solid_formula)
    ksp = _number(request.get("Ksp", request.get("ksp")), "Ksp", MIN_KSP, MAX_KSP)
    raw_ions = request.get("ions")
    if not isinstance(raw_ions, list) or not 2 <= len(raw_ions) <= 4:
        raise ValueError("ions 必须提供 2 到 4 种明确的溶解离子")

    ions = []
    atom_total = {}
    charge_total = 0
    exponent_total = 0
    seen = set()
    for index, raw in enumerate(raw_ions):
        label = "第 %d 种离子" % (index + 1)
        if not isinstance(raw, dict):
            raise ValueError(label + "必须是对象")
        formula = raw.get("formula")
        if not isinstance(formula, str) or not formula.strip():
            raise ValueError(label + "缺少 formula")
        formula = formula.strip().translate(_SUBSCRIPTS)
        atoms = parse_formula(formula)
        charge = raw.get("charge")
        if isinstance(charge, bool) or not isinstance(charge, int) or charge == 0 or abs(charge) > 12:
            raise ValueError(label + " charge 必须是 -12 到 12 之间的非零整数")
        coefficient = raw.get("coefficient")
        if isinstance(coefficient, bool) or not isinstance(coefficient, int) or not 1 <= coefficient <= 6:
            raise ValueError(label + " coefficient 必须是 1 到 6 的整数")
        key = (formula, charge)
        if key in seen:
            raise ValueError("同种离子重复出现，请合并其系数")
        seen.add(key)
        concentration = _number(raw.get("initial_concentration_mol_L", 0),
                                label + "初始浓度", 0, MAX_CONCENTRATION_MOL_L)
        ion = {"formula": formula, "charge": charge, "coefficient": coefficient,
               "initial_concentration_mol_L": concentration, "atoms": atoms}
        ions.append(ion)
        exponent_total += coefficient
        charge_total += coefficient * charge
        for element, count in atoms.items():
            atom_total[element] = atom_total.get(element, 0) + coefficient * count
    if exponent_total > MAX_TOTAL_EXPONENT:
        raise ValueError("Ksp 总指数不能超过 %d" % MAX_TOTAL_EXPONENT)
    if atom_total != solid_atoms:
        raise ValueError("离子及其系数合成的原子数与固体化学式不一致")
    if charge_total != 0:
        raise ValueError("固体溶解离子的化学计量电荷和必须为 0")

    background = [ion["initial_concentration_mol_L"] for ion in ions]
    log_q = _log_ion_product(ions, background)
    log_ksp = math.log(ksp)
    difference = log_q - log_ksp
    if difference > 1e-10:
        state = "supersaturated"
        solubility = None
        equilibrium_concentrations = None
        log_equilibrium_q = None
    elif difference >= -1e-10:
        state = "saturated"
        solubility = 0.0
        equilibrium_concentrations = list(background)
        log_equilibrium_q = log_q
    else:
        state = "unsaturated"
        solubility = _solve_positive_solubility(ions, background, log_ksp)
        equilibrium_concentrations = [initial + ion["coefficient"] * solubility
                                      for ion, initial in zip(ions, background)]
        log_equilibrium_q = _log_ion_product(ions, equilibrium_concentrations)

    mass_action_ok = (None if log_equilibrium_q is None else
                      math.isclose(log_equilibrium_q, log_ksp, rel_tol=0, abs_tol=1e-8))
    result_ions = [{key: ion[key] for key in
                    ("formula", "charge", "coefficient", "initial_concentration_mol_L")}
                   for ion in ions]
    checks = {
        "solid_formula_matches_ions": atom_total == solid_atoms,
        "dissolution_charge_balanced": charge_total == 0,
        "ion_product_classified": state in {"unsaturated", "saturated", "supersaturated"},
        # Supersaturated inputs have no modeled final equilibrium; report this
        # check as not applicable instead of claiming that Q equals Ksp.
        "mass_action_at_saturation": mass_action_ok,
        "supersaturation_not_misrepresented_as_equilibrium":
            state != "supersaturated" or log_equilibrium_q is None,
        "no_negative_concentrations": all(value >= 0 for value in background),
    }
    checks["ok"] = all(value is True or value is None for value in checks.values())
    return {
        "schema": "chem-solubility-ksp.v1",
        "solid_formula": solid_formula,
        "Ksp": ksp,
        "dissolution_equation": solid_formula.translate(_SUBSCRIPT_DISPLAY) + "(s) ⇌ " + " + ".join(
            _display_species(ion) for ion in ions),
        "ions": result_ions,
        "initial_ion_product": _exp_clamped(log_q),
        "initial_log_ion_product": log_q if math.isfinite(log_q) else None,
        "saturation_ratio": _exp_clamped(difference),
        "saturation_state": state,
        "molar_solubility_mol_L": solubility,
        "equilibrium_ion_concentrations_mol_L": equilibrium_concentrations,
        "equilibrium_ion_product": _exp_clamped(log_equilibrium_q) if log_equilibrium_q is not None else None,
        "precipitation_expected": state == "supersaturated",
        "assumes_excess_solid": True,
        "checks": checks,
    }
