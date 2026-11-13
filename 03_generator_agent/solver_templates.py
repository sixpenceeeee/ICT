# -*- coding: utf-8 -*-
"""Configuration-driven deterministic pages for registered solver scenes."""

import copy
import html
import json
import re

from page_components import (render_action_buttons, render_learning_goals,
                             render_number_control, render_record_table,
                             render_comparison_panel, render_result_card, render_slider_number_control,
                             render_subject_tags, render_select_control,
                             render_range_number_control)


# This is a deliberate allowlist: ion identities and charges come from reviewed
# entries, never from model guesses. Ksp may be supplied by the request; only
# CaF2 retains the project's established example value as a default.
KSP_SOLIDS = [
    {
        "formula": "CaF2", "display": "CaF₂", "names": ["氟化钙", "CaF2"],
        "default_ksp": 4e-11,
        "ions": [
            {"formula": "Ca", "display": "Ca²⁺", "charge": 2, "coefficient": 1,
             "aliases": [r"Ca\s*2\s*\+", r"钙离子"]},
            {"formula": "F", "display": "F⁻", "charge": -1, "coefficient": 2,
             "aliases": [r"F\s*-", r"氟离子"]},
        ],
    },
    {
        "formula": "AgCl", "display": "AgCl", "names": ["氯化银", "AgCl"],
        "ions": [
            {"formula": "Ag", "display": "Ag⁺", "charge": 1, "coefficient": 1,
             "aliases": [r"Ag\s*\+", r"银离子"]},
            {"formula": "Cl", "display": "Cl⁻", "charge": -1, "coefficient": 1,
             "aliases": [r"Cl\s*-", r"氯离子"]},
        ],
    },
    {
        "formula": "PbI2", "display": "PbI₂", "names": ["碘化铅", "PbI2"],
        "ions": [
            {"formula": "Pb", "display": "Pb²⁺", "charge": 2, "coefficient": 1,
             "aliases": [r"Pb\s*2\s*\+", r"铅离子"]},
            {"formula": "I", "display": "I⁻", "charge": -1, "coefficient": 2,
             "aliases": [r"I\s*-", r"碘离子"]},
        ],
    },
    {
        "formula": "BaSO4", "display": "BaSO₄", "names": ["硫酸钡", "BaSO4"],
        "ions": [
            {"formula": "Ba", "display": "Ba²⁺", "charge": 2, "coefficient": 1,
             "aliases": [r"Ba\s*2\s*\+", r"钡离子"]},
            {"formula": "SO4", "display": "SO₄²⁻", "charge": -2, "coefficient": 1,
             "aliases": [r"SO\s*4\s*2\s*-", r"硫酸根"]},
        ],
    },
    {
        "formula": "CaCO3", "display": "CaCO₃", "names": ["碳酸钙", "CaCO3"],
        "ions": [
            {"formula": "Ca", "display": "Ca²⁺", "charge": 2, "coefficient": 1,
             "aliases": [r"Ca\s*2\s*\+", r"钙离子"]},
            {"formula": "CO3", "display": "CO₃²⁻", "charge": -2, "coefficient": 1,
             "aliases": [r"CO\s*3\s*2\s*-", r"碳酸根"]},
        ],
    },
    {
        "formula": "Mg(OH)2", "display": "Mg(OH)₂", "names": ["氢氧化镁", "Mg(OH)2"],
        "ions": [
            {"formula": "Mg", "display": "Mg²⁺", "charge": 2, "coefficient": 1,
             "aliases": [r"Mg\s*2\s*\+", r"镁离子"]},
            {"formula": "OH", "display": "OH⁻", "charge": -1, "coefficient": 2,
             "aliases": [r"OH\s*-", r"氢氧根"]},
        ],
    },
]

_SUBSCRIPTS = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")
_SUPERSCRIPTS = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺", "0123456789-+")
_SUPERSCRIPT_DIGITS = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")


class KspConfigurationError(ValueError):
    """The request is outside the reviewed Ksp page configuration catalog."""


TITRATION_ACIDS = [
    {"formula": "HCl", "name": "盐酸", "aliases": ["盐酸", "HCl"]},
    {"formula": "HBr", "name": "氢溴酸", "aliases": ["氢溴酸", "HBr"]},
    {"formula": "HI", "name": "氢碘酸", "aliases": ["氢碘酸", "HI"]},
    {"formula": "HNO3", "name": "硝酸", "aliases": ["硝酸", "HNO3"]},
    {"formula": "HClO4", "name": "高氯酸", "aliases": ["高氯酸", "HClO4"]},
]
TITRATION_BASES = [
    {"formula": "LiOH", "name": "氢氧化锂", "aliases": ["氢氧化锂", "LiOH"]},
    {"formula": "NaOH", "name": "氢氧化钠", "aliases": ["氢氧化钠", "烧碱", "NaOH"]},
    {"formula": "KOH", "name": "氢氧化钾", "aliases": ["氢氧化钾", "KOH"]},
]

PRECIPITATION_REACTIONS = [
    {
        "id": "silver-chloride", "reactants": ["AgNO3", "NaCl"],
        "names": ["硝酸银", "氯化钠", "AgNO3", "NaCl"],
        "display": ["AgNO₃", "NaCl"], "precipitate": "AgCl",
        "precipitate_display": "AgCl", "colors": ["#eef2f4", "#9daab3"],
    },
    {
        "id": "barium-sulfate", "reactants": ["BaCl2", "Na2SO4"],
        "names": ["氯化钡", "硫酸钠", "BaCl2", "Na2SO4"],
        "display": ["BaCl₂", "Na₂SO₄"], "precipitate": "BaSO4",
        "precipitate_display": "BaSO₄", "colors": ["#f4f4ed", "#b7c1c8"],
    },
    {
        "id": "calcium-carbonate", "reactants": ["CaCl2", "Na2CO3"],
        "names": ["氯化钙", "碳酸钠", "CaCl2", "Na2CO3"],
        "display": ["CaCl₂", "Na₂CO₃"], "precipitate": "CaCO3",
        "precipitate_display": "CaCO₃", "colors": ["#f1eee6", "#aa9a78"],
    },
    {
        "id": "copper-hydroxide", "reactants": ["CuSO4", "NaOH"],
        "names": ["硫酸铜", "氢氧化钠", "CuSO4", "NaOH"],
        "display": ["CuSO₄", "NaOH"], "precipitate": "Cu(OH)2",
        "precipitate_display": "Cu(OH)₂", "colors": ["#9bd8ed", "#348eb6"],
    },
    {
        "id": "iron-iii-hydroxide", "reactants": ["FeCl3", "NaOH"],
        "names": ["氯化铁", "氢氧化钠", "FeCl3", "NaOH"],
        "display": ["FeCl₃", "NaOH"], "precipitate": "Fe(OH)3",
        "precipitate_display": "Fe(OH)₃", "colors": ["#d8a06c", "#97572f"],
    },
    {
        "id": "magnesium-hydroxide", "reactants": ["MgSO4", "NaOH"],
        "names": ["硫酸镁", "氢氧化钠", "MgSO4", "NaOH"],
        "display": ["MgSO₄", "NaOH"], "precipitate": "Mg(OH)2",
        "precipitate_display": "Mg(OH)₂", "colors": ["#f1f4f5", "#aab8c2"],
    },
]

GAS_REACTIONS = [
    {
        "id": "zinc-hydrogen", "reactants": ["Zn", "HCl"],
        "products": [("ZnCl2", "aq"), ("H2", "g")],
        "names": ["锌", "盐酸", "氢气", "Zn", "HCl", "H2"], "gas": "H2",
        "display": ["Zn", "HCl"],
    },
    {
        "id": "calcium-carbonate-carbon-dioxide", "reactants": ["CaCO3", "HCl"],
        "products": [("CaCl2", "aq"), ("H2O", "l"), ("CO2", "g")],
        "names": ["碳酸钙", "盐酸", "二氧化碳", "CaCO3", "HCl", "CO2"], "gas": "CO2",
        "display": ["CaCO₃", "HCl"],
    },
    {
        "id": "hydrogen-peroxide-oxygen", "reactants": ["H2O2"],
        "products": [("H2O", "l"), ("O2", "g")],
        "names": ["过氧化氢", "氧气", "H2O2", "O2"], "gas": "O2",
        "display": ["H₂O₂"],
    },
]

REDOX_REACTIONS = [
    {
        "id": "permanganate-iron", "names": ["高锰酸钾", "高锰酸根", "亚铁", "Fe²⁺", "MnO4"],
        "medium": "acidic",
        "reactants": [{"formula": "MnO4", "charge": -1, "phase": "aq"},
                      {"formula": "Fe", "charge": 2, "phase": "aq"}],
        "products": [{"formula": "Mn", "charge": 2, "phase": "aq"},
                     {"formula": "Fe", "charge": 3, "phase": "aq"}],
    },
    {
        "id": "dichromate-sulfite", "names": ["重铬酸根", "亚硫酸根", "Cr2O7", "SO3"],
        "medium": "acidic",
        "reactants": [{"formula": "Cr2O7", "charge": -2, "phase": "aq"},
                      {"formula": "SO3", "charge": -2, "phase": "aq"}],
        "products": [{"formula": "Cr", "charge": 3, "phase": "aq"},
                     {"formula": "SO4", "charge": -2, "phase": "aq"}],
    },
    {
        "id": "hypochlorite-iodide", "names": ["次氯酸根", "碘离子", "ClO", "I"],
        "medium": "basic",
        "reactants": [{"formula": "ClO", "charge": -1, "phase": "aq"},
                      {"formula": "I", "charge": -1, "phase": "aq"}],
        "products": [{"formula": "Cl", "charge": -1, "phase": "aq"},
                     {"formula": "IO3", "charge": -1, "phase": "aq"}],
    },
    {
        "id": "peroxide-disproportionation", "names": ["过氧化氢", "H2O2"],
        "medium": "acidic",
        "reactants": [{"formula": "H2O2", "charge": 0, "phase": "aq"}],
        "products": [{"formula": "H2O", "charge": 0, "phase": "l"},
                     {"formula": "O2", "charge": 0, "phase": "g"}],
    },
]


def _request_text(req):
    parts = [str(req.get("实验主题", "")), str(req.get("实验名称", "")),
             str(req.get("原始需求", "")), str(req.get("input", ""))]
    for key in ("学习目标", "交互要求", "技术要点", "风险点"):
        value = req.get(key) or []
        parts.extend([str(x) for x in value] if isinstance(value, list) else [str(value)])
    for item in req.get("核心变量", []) or []:
        if isinstance(item, dict):
            parts.extend(str(value) for value in item.values())
    return " ".join(parts)


def _normalized_text(value):
    return (str(value or "").translate(_SUBSCRIPTS).translate(_SUPERSCRIPTS)
            .replace("×10", "e").replace("·10", "e"))


def _species_match(value, catalog):
    text = _normalized_text(value).strip()
    if not text:
        return None
    for item in sorted(catalog, key=lambda entry: len(entry["formula"]), reverse=True):
        for alias in item["aliases"]:
            if alias.isascii():
                if re.search(r"(?<![A-Za-z0-9])%s(?![A-Za-z0-9])" % re.escape(alias), text, re.I):
                    return item
            elif alias in text:
                return item
    return None


def _titration_species(req, kind):
    if kind == "acid":
        catalog = TITRATION_ACIDS
        direct_keys = ("酸化学式", "酸", "酸液", "acid_formula", "acid")
        unsupported = ("乙酸", "醋酸", "硫酸", "磷酸", "碳酸", "氢氟酸", "H2SO4", "H3PO4", "H2CO3", "HF")
        default_formula = "HCl"
        label = "酸"
    else:
        catalog = TITRATION_BASES
        direct_keys = ("碱化学式", "碱", "碱液", "base_formula", "base")
        unsupported = ("氨水", "氨", "氢氧化钙", "氢氧化钡", "Ca(OH)2", "Ba(OH)2", "NH3")
        default_formula = "NaOH"
        label = "碱"

    for key in direct_keys:
        value = req.get(key)
        if value is None:
            continue
        if isinstance(value, dict):
            value = value.get("formula") or value.get("化学式") or value.get("名称") or ""
        if not str(value).strip():
            continue
        generic_labels = {"酸", "强酸", "强一元酸", "待测酸", "待测酸液", "酸液"} if kind == "acid" else {
            "碱", "强碱", "强一元碱", "滴定液", "滴定剂", "碱液"}
        if str(value).strip() in generic_labels:
            continue
        matched = _species_match(value, catalog)
        if matched:
            return matched
        raise ValueError("当前滴定页面未登记该%s；支持的%s为：%s。" % (
            label, label, "、".join(item["name"] for item in catalog)))

    text = _normalized_text(_request_text(req))
    matched = _species_match(text, catalog)
    if matched:
        return matched
    for item in unsupported:
        if item.isascii():
            if re.search(r"(?<![A-Za-z0-9])%s(?![A-Za-z0-9])" % re.escape(item), text, re.I):
                raise ValueError("当前滴定模型不适用%s；仅支持登记的强一元酸和强一元碱。" % item)
        elif item in text:
            raise ValueError("当前滴定模型不适用%s；仅支持登记的强一元酸和强一元碱。" % item)
    return next(item for item in catalog if item["formula"] == default_formula)


def _parse_request_number(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        for key in ("初始值", "初值", "数值", "值", "value", "default", "范围", "range"):
            if key in value and value[key] is not None:
                number = _parse_request_number(value[key])
                if number is not None:
                    return number
        return None
    text = _normalized_text(value).replace("^", "")
    text = re.sub(r"[xX×·]\s*10\s*([+-]?\d+)", r"e\1", text)
    match = re.search(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", text)
    if not match:
        return None
    try:
        number = float(match.group(0))
    except (ValueError, OverflowError):
        return None
    return number if number == number and abs(number) != float("inf") else None


def _request_unit(value, default="mL"):
    candidates = []
    if isinstance(value, dict):
        candidates.extend(value.get(key) for key in ("单位", "unit", "范围", "range") if value.get(key) is not None)
    else:
        candidates.append(value)
    for candidate in candidates:
        text = str(candidate).strip().lower()
        if re.search(r"\bml\b|毫升", text):
            return "mL"
        if re.search(r"\bl\b|升", text):
            return "L"
    return default


def _named_quantity(req, direct_keys, name_patterns, default, default_unit="mL"):
    for key in direct_keys:
        if key in req and req[key] is not None:
            number = _parse_request_number(req[key])
            if number is not None:
                return number, _request_unit(req[key], default_unit)
    variables = req.get("核心变量") or []
    if isinstance(variables, list):
        patterns = tuple(pattern.lower() for pattern in name_patterns)
        for variable in variables:
            if not isinstance(variable, dict):
                continue
            name = str(variable.get("名称") or variable.get("name") or "").lower()
            if any(pattern in name for pattern in patterns):
                raw = next((variable[key] for key in ("初始值", "初值", "数值", "值", "value", "范围", "range")
                            if variable.get(key) is not None), None)
                number = _parse_request_number(raw)
                if number is not None:
                    unit = variable.get("单位") or variable.get("unit") or raw
                    return number, _request_unit(unit, default_unit)
    return float(default), default_unit


def _nested_solution_quantity(req, containers, value_keys, unit_keys, default_unit):
    for container_key in containers:
        source = req.get(container_key)
        if not isinstance(source, dict):
            continue
        for key in value_keys:
            if source.get(key) is not None:
                number = _parse_request_number(source[key])
                if number is not None:
                    unit = next((source[unit_key] for unit_key in unit_keys
                                 if source.get(unit_key) is not None), source[key])
                    return number, _request_unit(unit, default_unit)
    return None


def _named_range_upper(req, name_patterns, fallback, fallback_unit="mL"):
    patterns = tuple(pattern.lower() for pattern in name_patterns)
    for variable in req.get("核心变量", []) or []:
        if not isinstance(variable, dict):
            continue
        name = str(variable.get("名称") or variable.get("name") or "").lower()
        if not any(pattern in name for pattern in patterns):
            continue
        raw = variable.get("范围") or variable.get("range")
        if isinstance(raw, dict):
            upper = next((raw[key] for key in ("最大值", "max", "上限") if raw.get(key) is not None), None)
            number = _parse_request_number(upper)
        else:
            text = _normalized_text(raw).replace("^", "")
            text = re.sub(r"[xX×·]\s*10\s*([+-]?\d+)", r"e\1", text)
            tokens = re.findall(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", text)
            try:
                number = float(tokens[-1]) if len(tokens) > 1 else None
            except (ValueError, OverflowError):
                number = None
        if number is not None and number >= 0:
            unit = variable.get("单位") or variable.get("unit") or raw
            return number, _request_unit(unit, fallback_unit)
    return float(fallback), fallback_unit


def resolve_acid_base_titration_config(req):
    """Normalize a supported strong-acid/strong-base titration page request."""
    req = req or {}
    acid = _titration_species(req, "acid")
    base = _titration_species(req, "base")
    acid_concentration, _ = _named_quantity(
        req, ("酸浓度", "酸液浓度", acid["name"] + "浓度", "acid_concentration_mol_L"),
        ("酸浓度", "酸液浓度", acid["name"] + "浓度", acid["formula"].lower() + "浓度",
         "acid concentration"), 0.1, "mol/L")
    acid_volume, acid_unit = _named_quantity(
        req, ("酸体积", "酸液体积", acid["name"] + "体积", "样品体积", "acid_volume"),
        ("酸体积", "酸液体积", acid["name"] + "体积", "样品体积", "待测液体积", "acid volume"),
        25.0, "mL")
    base_concentration, _ = _named_quantity(
        req, ("碱浓度", "碱液浓度", "滴定液浓度", "滴定剂浓度",
             base["name"] + "浓度", "base_concentration_mol_L"),
        ("碱浓度", "碱液浓度", "滴定液浓度", "滴定剂浓度", base["name"] + "浓度",
         base["formula"].lower() + "浓度", "base concentration"), 0.1, "mol/L")
    base_volume, base_unit = _named_quantity(
        req, ("滴加体积", "滴定体积", "碱体积", "碱液体积", base["name"] + "体积", "base_volume"),
        ("滴加体积", "滴定体积", "滴定液体积", "滴定剂体积", "碱体积", "碱液体积",
         base["name"] + "体积", base["formula"].lower() + "体积", "base volume"), 0.0, "mL")

    nested = _nested_solution_quantity(req, ("acid", "酸液"),
        ("concentration_mol_L", "concentration", "浓度"), ("concentration_unit",), "mol/L")
    if nested:
        acid_concentration = nested[0]
    nested = _nested_solution_quantity(req, ("acid", "酸液"),
        ("volume", "体积"), ("volume_unit", "体积单位"), acid_unit)
    if nested:
        acid_volume, acid_unit = nested
    nested = _nested_solution_quantity(req, ("base", "碱液", "滴定液"),
        ("concentration_mol_L", "concentration", "浓度"), ("concentration_unit",), "mol/L")
    if nested:
        base_concentration = nested[0]
    nested = _nested_solution_quantity(req, ("base", "碱液", "滴定液"),
        ("volume", "体积"), ("volume_unit", "体积单位"), base_unit)
    if nested:
        base_volume, base_unit = nested

    if not (0 < acid_concentration <= 1 and 0 < base_concentration <= 1):
        raise ValueError("酸、碱浓度必须大于 0 且不超过 1 mol/L。")
    if not (0 < acid_volume <= 1_000_000 and 0 <= base_volume <= 1_000_000):
        raise ValueError("酸液体积必须大于 0；滴定液体积不能为负数，体积输入上限为 1,000,000。")

    acid_volume_l = acid_volume / 1000 if acid_unit == "mL" else acid_volume
    base_volume_l = base_volume / 1000 if base_unit == "mL" else base_volume
    equivalence_volume_ml = acid_concentration * acid_volume_l / base_concentration * 1000
    base_volume_ml = base_volume_l * 1000
    requested_base_max, requested_base_max_unit = _named_range_upper(
        req, ("滴加体积", "滴定体积", "滴定液体积", "滴定剂体积", "碱体积",
              base["name"] + "体积", base["formula"].lower() + "体积"), base_volume, base_unit)
    requested_base_max_ml = requested_base_max * (1000 if requested_base_max_unit == "L" else 1)
    slider_max_ml = min(1_000_000.0, max(equivalence_volume_ml * 1.5,
        base_volume_ml * 1.15, requested_base_max_ml, 1.0))
    return {
        "scene_id": "chemistry-acid-base-titration",
        "acid": {"formula": acid["formula"], "name": acid["name"],
                 "concentration_mol_L": acid_concentration,
                 "volume": acid_volume, "volume_unit": acid_unit},
        "base": {"formula": base["formula"], "name": base["name"],
                 "concentration_mol_L": base_concentration,
                 "volume": base_volume, "volume_unit": base_unit},
        "equivalence_volume_ml": equivalence_volume_ml,
        "slider_max_ml": slider_max_ml,
        "modules": ["实验装置", "参数控制", "滴定曲线", "求解结果", "数据记录", "教学说明"],
        "assumptions": ["强一元酸与强一元碱", "1:1 完全中和", "25°C", "理想溶液"],
    }


def titration_template_values(req):
    config = resolve_acid_base_titration_config(req)
    return {"酸": dict(config["acid"]), "碱": dict(config["base"]),
            "理论当量体积mL": config["equivalence_volume_ml"],
            "页面模块": list(config["modules"])}


def _precipitation_formula_match(value):
    text = _normalized_text(value).replace(" ", "")
    if not text:
        return None
    for item in PRECIPITATION_REACTIONS:
        for formula in item["reactants"]:
            if text.casefold() == formula.casefold():
                return formula
        for name in item["names"]:
            if name.casefold() in text.casefold():
                return next((formula for formula in item["reactants"] if formula.casefold() == name.casefold()), None)
    return None


def _precipitation_reaction(req):
    candidates = []
    for key in ("solutions", "溶液", "反应物", "reactants"):
        value = req.get(key)
        if isinstance(value, list):
            for item in value:
                raw = item.get("formula") if isinstance(item, dict) else item
                formula = _precipitation_formula_match(raw)
                if formula and formula not in candidates:
                    candidates.append(formula)
    if len(candidates) == 2:
        for item in PRECIPITATION_REACTIONS:
            if set(item["reactants"]) == set(candidates):
                return item
    text = _normalized_text(_request_text(req))
    for item in PRECIPITATION_REACTIONS:
        if all(any(name.casefold() in text.casefold() for name in item["names"]
                   if name.casefold() == formula.casefold() or not name.isascii())
               or re.search(r"(?<![A-Za-z0-9])%s(?![A-Za-z0-9])" % re.escape(formula), text, re.I)
               for formula in item["reactants"]):
            return item
    raise ValueError("当前沉淀页面只登记了 AgNO3/NaCl、BaCl2/Na2SO4、CaCl2/Na2CO3、CuSO4/NaOH、FeCl3/NaOH、MgSO4/NaOH 配对；需求中的组合未登记。")


def _solution_from_request(req, formula, item, index, reaction):
    item = item if isinstance(item, dict) else {}
    name_index = reaction["reactants"].index(formula)
    display = reaction["display"][name_index]
    name_aliases = [formula, display] + [name for name in reaction["names"] if name.casefold() != formula.casefold()]
    concentration = _parse_request_number(
        item.get("concentration_mol_L", item.get("concentration", item.get("浓度"))))
    volume = _parse_request_number(item.get("volume", item.get("体积")))
    unit = _request_unit(item.get("volume_unit", item.get("体积单位", "mL")), "mL")
    if concentration is None:
        concentration, _ = _named_quantity(
            req, tuple(alias + "浓度" for alias in name_aliases) + (formula + "_concentration_mol_L",),
            tuple(alias + "浓度" for alias in name_aliases), 0.1, "mol/L")
    if volume is None:
        volume, unit = _named_quantity(
            req, tuple(alias + "体积" for alias in name_aliases) + (formula + "_volume",),
            tuple(alias + "体积" for alias in name_aliases), (50.0 if index == 0 else 40.0), "mL")
    if not (0 < concentration <= 1):
        raise ValueError("%s 浓度必须大于 0 且不超过 1 mol/L。" % display)
    if not (0 < volume <= 1_000_000):
        raise ValueError("%s 体积必须大于 0，且不超过 1,000,000。" % display)
    return {"formula": formula, "display": display,
            "concentration_mol_L": concentration, "volume": volume, "volume_unit": unit}


def resolve_precipitation_config(req):
    """Normalize a reviewed precipitation pair into a deterministic page config."""
    req = req or {}
    reaction = _precipitation_reaction(req)
    supplied = []
    for key in ("solutions", "溶液", "reactants"):
        if isinstance(req.get(key), list):
            supplied = req[key]
            break
    by_formula = {}
    for item in supplied:
        raw = item.get("formula") if isinstance(item, dict) else item
        formula = _precipitation_formula_match(raw)
        if formula:
            by_formula[formula] = item
    solutions = [_solution_from_request(req, formula, by_formula.get(formula), index, reaction)
                 for index, formula in enumerate(reaction["reactants"])]
    progress = _parse_request_number(req.get("progress", req.get("反应进度", 1.0)))
    progress = 1.0 if progress is None else progress
    if not 0 <= progress <= 1:
        raise ValueError("反应进度必须在 0 到 1 之间。")
    return {
        "scene_id": "chemistry-precipitation-quantitative",
        "reaction_id": reaction["id"], "reactants": reaction["reactants"],
        "display": reaction["display"], "precipitate": reaction["precipitate"],
        "precipitate_display": reaction["precipitate_display"], "colors": reaction["colors"],
        "solutions": solutions, "progress": progress,
        "modules": ["实验装置", "参数控制", "求解结果", "数据记录", "教学说明"],
        "assumptions": ["目录内定性完全沉淀", "不计算 Ksp、络合和副反应"],
    }


def precipitation_template_values(req):
    config = resolve_precipitation_config(req)
    return {"反应": config["reaction_id"], "溶液": [dict(item) for item in config["solutions"]],
            "反应进度": config["progress"], "页面模块": list(config["modules"])}


def _gas_formula_match(value):
    text = _normalized_text(value).replace(" ", "")
    if not text:
        return None
    for reaction in GAS_REACTIONS:
        for formula in reaction["reactants"] + [item[0] for item in reaction["products"]]:
            if text.casefold() == formula.casefold():
                return formula
        for name in reaction["names"]:
            if name.casefold() in text.casefold():
                for formula in reaction["reactants"] + [item[0] for item in reaction["products"]]:
                    if formula.casefold() == name.casefold():
                        return formula
    return None


def _gas_reaction(req):
    reactant_formulas = []
    product_formulas = []
    for key, target in (("reactants", reactant_formulas), ("反应物", reactant_formulas),
                        ("products", product_formulas), ("生成物", product_formulas)):
        value = req.get(key)
        if isinstance(value, list):
            for item in value:
                raw = item.get("formula") if isinstance(item, dict) else item
                formula = _gas_formula_match(raw)
                if formula and formula not in target:
                    target.append(formula)
    if reactant_formulas and product_formulas:
        for reaction in GAS_REACTIONS:
            if set(reaction["reactants"]) == set(reactant_formulas) and set(
                    item[0] for item in reaction["products"]) == set(product_formulas):
                return reaction
    text = _normalized_text(_request_text(req))
    for reaction in GAS_REACTIONS:
        if all(name.casefold() in text.casefold() for name in reaction["names"][:2]):
            return reaction
    raise ValueError("当前气体页面只登记了锌与盐酸制氢气、碳酸钙与盐酸制二氧化碳、过氧化氢制氧气。需求中的反应尚未登记。")


def _gas_numeric(req, direct_keys, patterns, default, default_unit=""):
    value, unit = _named_quantity(req, tuple(direct_keys), tuple(patterns), default, default_unit or "mL")
    return value, unit


def resolve_gas_collection_config(req):
    """Normalize a reviewed gas-reaction page into solver-ready data."""
    req = req or {}
    reaction = _gas_reaction(req)
    gas_formula = req.get("gas_formula") or req.get("目标气体") or req.get("气体化学式")
    gas_formula = _gas_formula_match(gas_formula) if gas_formula else reaction["gas"]
    if gas_formula != reaction["gas"]:
        raise ValueError("当前登记反应的目标气体只能是 %s。" % reaction["gas"])

    supplied = req.get("reactants") if isinstance(req.get("reactants"), list) else req.get("反应物", [])
    by_formula = {}
    for item in supplied or []:
        raw = item.get("formula") if isinstance(item, dict) else item
        formula = _gas_formula_match(raw)
        if formula:
            by_formula[formula] = item
    amounts = []
    for index, formula in enumerate(reaction["reactants"]):
        item = by_formula.get(formula) or {}
        amount = _parse_request_number(item.get("amount_mol", item.get("amount", item.get("物质的量"))))
        if amount is None:
            amount, _ = _gas_numeric(req,
                (formula + "物质的量", formula + "_amount_mol", "物质的量" + formula),
                (formula + "物质的量", formula + "的物质的量", formula + "用量"),
                0.02 if index == 0 else 0.05)
        if not 0 <= amount <= 1_000_000:
            raise ValueError("%s 的物质的量必须在 0 到 1,000,000 mol 之间。" % formula)
        amounts.append(amount)

    progress = _parse_request_number(req.get("progress", req.get("反应进度", 1.0)))
    progress = 1.0 if progress is None else progress
    temperature = _parse_request_number(req.get("temperature_c", req.get("温度", req.get("温度°C"))))
    if temperature is None:
        temperature, _ = _gas_numeric(req, ("温度", "temperature_c"), ("温度", "temperature"), 25.0)
    pressure = _parse_request_number(req.get("total_pressure_kpa", req.get("总压强", req.get("压强"))))
    if pressure is None:
        pressure, _ = _gas_numeric(req, ("总压强", "压强", "total_pressure_kpa"), ("总压强", "压强", "pressure"), 101.325)
    method = req.get("collection_method", req.get("集气方式", "over_water"))
    method_text = str(method).strip().lower()
    if method_text in ("over_water", "water", "排水", "排水集气"):
        method = "over_water"
    elif method_text in ("dry", "排空气", "干燥集气", "向上排空气", "向下排空气"):
        method = "dry"
    else:
        raise ValueError("集气方式只支持排水集气或干燥/排空气集气。")
    if not 0 <= progress <= 1:
        raise ValueError("反应进度必须在 0 到 1 之间。")
    if not -273.149 <= temperature <= 2_000:
        raise ValueError("温度必须高于绝对零度且不超过 2000°C。")
    if method == "over_water" and not 0 <= temperature <= 100:
        raise ValueError("Antoine 水蒸气压模型只支持 0–100°C 的排水集气。")
    if not 1e-9 <= pressure <= 100_000:
        raise ValueError("总压强必须在安全范围内。")
    return {
        "scene_id": "chemistry-gas-collection", "reaction_id": reaction["id"],
        "reactants": [{"formula": formula, "phase": "s" if formula == "Zn" else "aq"}
                      for formula in reaction["reactants"]],
        "products": [{"formula": formula, "phase": phase} for formula, phase in reaction["products"]],
        "display": reaction["display"], "gas_formula": gas_formula,
        "initial_amounts_mol": amounts, "progress": progress,
        "temperature_c": temperature, "total_pressure_kpa": pressure,
        "collection_method": method,
        "modules": ["实验装置", "参数控制", "气体体积结果", "数据记录", "教学说明"],
        "assumptions": ["理想气体", "指定反应与产率为完全反应", "排水集气使用 0–100°C Antoine 水蒸气压"],
    }


def gas_collection_template_values(req):
    config = resolve_gas_collection_config(req)
    return {"反应": config["reaction_id"], "目标气体": config["gas_formula"],
            "初始物质的量mol": list(config["initial_amounts_mol"]),
            "反应进度": config["progress"], "温度°C": config["temperature_c"],
            "总压强kPa": config["total_pressure_kpa"], "集气方式": config["collection_method"],
            "页面模块": list(config["modules"])}


def _redox_formula(value):
    text = _normalized_text(value).strip().replace(" ", "")
    return text


def _redox_reaction(req):
    supplied_r = req.get("reactants") if isinstance(req.get("reactants"), list) else []
    supplied_p = req.get("products") if isinstance(req.get("products"), list) else []
    if supplied_r and supplied_p:
        r_keys = {_redox_formula(item.get("formula") if isinstance(item, dict) else item) for item in supplied_r}
        p_keys = {_redox_formula(item.get("formula") if isinstance(item, dict) else item) for item in supplied_p}
        for reaction in REDOX_REACTIONS:
            if r_keys == {_redox_formula(item["formula"]) for item in reaction["reactants"]} and \
                    p_keys == {_redox_formula(item["formula"]) for item in reaction["products"]}:
                return reaction
    text = _normalized_text(_request_text(req)).casefold()
    for reaction in REDOX_REACTIONS:
        if sum(1 for name in reaction["names"] if _normalized_text(name).casefold() in text) >= 2:
            return reaction
    return REDOX_REACTIONS[0]


def resolve_redox_config(req):
    """Normalize a reviewed redox reaction into solver-ready core species."""
    req = req or {}
    reaction = _redox_reaction(req)
    medium = req.get("medium", req.get("介质", reaction["medium"]))
    medium_text = str(medium).strip().lower()
    medium = "basic" if medium_text in ("basic", "base", "碱性", "碱") else "acidic"
    def species_from(value, fallback):
        if not isinstance(value, list) or not value:
            return copy.deepcopy(fallback)
        rows = []
        for index, item in enumerate(value):
            source = item if isinstance(item, dict) else {"formula": item}
            formula = _redox_formula(source.get("formula"))
            if not formula:
                raise ValueError("氧化还原物种必须提供化学式")
            try:
                charge = int(source.get("charge", source.get("电荷", 0)))
            except (TypeError, ValueError):
                raise ValueError("氧化还原物种电荷必须是整数")
            rows.append({"formula": formula, "charge": charge,
                         "phase": source.get("phase", "aq")})
        return rows
    reactants = species_from(req.get("reactants"), reaction["reactants"])
    products = species_from(req.get("products"), reaction["products"])
    if len(reactants) > 5 or len(products) > 5:
        raise ValueError("每侧氧化还原核心物种最多 5 项")
    return {"scene_id": "chemistry-redox-electron-balance", "reaction_id": reaction["id"],
            "medium": medium, "reactants": reactants, "products": products,
            "modules": ["氧化数变化图", "介质与物种顺序控制", "离子方程式结果", "数据记录", "教学说明"],
            "assumptions": ["核心物种由需求明确给出", "酸/碱介质只补入 H₂O 与 H⁺/OH⁻", "不判断热力学可行性"]}


def redox_template_values(req):
    config = resolve_redox_config(req)
    return {"反应": config["reaction_id"], "介质": config["medium"],
            "反应物": copy.deepcopy(config["reactants"]), "生成物": copy.deepcopy(config["products"]),
            "页面模块": list(config["modules"])}


def _redox_config_for_js(config):
    safe = {"medium": config["medium"], "reactants": config["reactants"], "products": config["products"]}
    return (json.dumps(safe, ensure_ascii=False, separators=(",", ":"))
            .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))


def _redox_collection_js_template(config):
    template = r'''(function(){
  'use strict';
  var CFG=__REDOX_CONFIG__, $=function(s){return document.querySelector(s);};
  var medium=$('[data-chem-redox-medium]'), reorder=$('[data-chem-redox-reorder]'),
      canvas=document.getElementById('redox-diagram'), rows=document.getElementById('redox-rows'),
      alertBox=document.getElementById('redox-alert'), reversed=false;
  function render(){
    var reactants=reversed?CFG.reactants.slice().reverse():CFG.reactants.slice();
    var products=reversed?CFG.products.slice().reverse():CFG.products.slice();
    var request={medium:medium.value,reactants:reactants,products:products};
    window.__CHEM_REDOX_REQUEST__=request;
    try{
      var result=CHEMSOLVER.solveRedox(request);
      if(!result.checks||result.checks.ok!==true)throw new Error('求解器守恒检查未通过');
      window.__CHEM_REDOX_RESULT__=result;
      $('[data-chem-redox-equation]').textContent=result.equation;
      $('[data-chem-redox-electrons]').textContent='失电子 '+result.electron_balance.lost_electrons+'，得电子 '+result.electron_balance.gained_electrons+'，转移 '+result.electron_balance.transferred_electrons+' e⁻';
      $('[data-chem-redox-changes]').textContent=(result.oxidation_changes||[]).map(function(row){
        return row.element+'：'+row.before+' → '+row.after+'（'+(row.delta>0?'失':'得')+Math.abs(row.delta)+' e⁻）';
      }).join('；');
      $('[data-chem-redox-medium-label]').textContent=result.medium==='basic'?'碱性介质':'酸性介质';
      $('[data-chem-redox-state]').textContent=result.checks.ok?'原子、电荷、电子均守恒':'无法确认守恒';
      CHEM.redox(canvas,result); alertBox.hidden=true; alertBox.textContent='';
      window.__CHEM_REDOX_CONTROLS__={medium:medium.value,reordered:reversed,reorder_button_visible:true};
      window.__DATA__={params:request,result:result,checks:result.checks};
    }catch(error){
      window.__CHEM_REDOX_RESULT__=null;
      ['[data-chem-redox-equation]','[data-chem-redox-electrons]','[data-chem-redox-changes]','[data-chem-redox-state]']
        .forEach(function(selector){$(selector).textContent='—';});
      alertBox.textContent='输入无效或氧化还原求解失败：'+error.message; alertBox.hidden=false;
      var context=canvas.getContext('2d'); context.clearRect(0,0,canvas.width,canvas.height);
      window.__DATA__={params:request,result:null,checks:{ok:false}};
    }
  }
  medium.addEventListener('change',render);
  reorder.addEventListener('click',function(){reversed=!reversed; reorder.textContent=reversed?'恢复物种顺序':'交换物质顺序验证'; render();});
  document.getElementById('btn-record').addEventListener('click',function(){
    var result=window.__CHEM_REDOX_RESULT__; if(!result)return;
    var tr=document.createElement('tr'), values=[rows.children.length+1,result.medium,result.electron_balance.transferred_electrons,result.equation];
    values.forEach(function(value){var td=document.createElement('td');td.textContent=String(value);tr.appendChild(td);}); rows.appendChild(tr);
  });
  document.getElementById('btn-reset').addEventListener('click',function(){medium.value=CFG.medium;reversed=false;reorder.textContent='交换物质顺序验证';rows.textContent='';render();});
  window.addEventListener('resize',function(){if(window.__CHEM_REDOX_RESULT__)CHEM.redox(canvas,window.__CHEM_REDOX_RESULT__);});
  render();
})();'''
    return template.replace("__REDOX_CONFIG__", _redox_config_for_js(config))


def render_redox_template(req, config=None):
    """Compose an oxidation-reduction page from an allowlisted core reaction."""
    config = config or resolve_redox_config(req)
    title = html.escape(str(req.get("实验名称") or "氧化还原电子守恒"))
    goals = req.get("学习目标") or ["按酸碱介质配平氧化还原离子方程式。", "比较氧化数变化并核对电子守恒。"]
    medium_options = [("acidic", "酸性介质"), ("basic", "碱性介质")]
    species_text = lambda item: html.escape(str(item["formula"])) + ("（电荷 %s）" % item["charge"])
    sections = {
        "1": render_subject_tags("化学", req.get("年级") or "高中") + render_learning_goals(goals),
        "2": ('<div class="redox-stage"><canvas id="redox-diagram" width="880" height="620" data-visual-type="diagram" '
               'aria-label="%s 氧化数变化与电子转移图"></canvas><p class="redox-caption">图示中的氧化数变化、电子箭头和介质说明均由求解结果驱动。</p></div>' % title),
        "3": ('<div class="redox-controls">'
               + render_select_control("反应介质", "redox-medium", medium_options, config["medium"],
                                       "data-chem-redox-medium", "反应介质")
               + '<div class="redox-species"><strong>反应物</strong><span>%s</span><span>%s</span></div>' %
               (species_text(config["reactants"][0]), species_text(config["reactants"][1]) if len(config["reactants"]) > 1 else "")
               + '<div class="redox-species"><strong>生成物</strong><span>%s</span><span>%s</span></div>' %
               (species_text(config["products"][0]), species_text(config["products"][1]) if len(config["products"]) > 1 else "")
               + '<button type="button" class="exp-btn secondary" data-chem-redox-reorder>交换物质顺序验证</button>'
               + render_action_buttons([("btn-record", "记录当前数据", True), ("btn-reset", "重置", False)])
               + '</div>'),
        "4": ('<div class="exp-formula"><div class="exp-reads">'
               + render_result_card("离子方程式", "data-chem-redox-equation")
               + render_result_card("电子守恒", "data-chem-redox-electrons")
               + render_result_card("氧化数变化", "data-chem-redox-changes")
               + render_result_card("当前介质", "data-chem-redox-medium-label")
               + render_result_card("守恒结论", "data-chem-redox-state")
               + '</div></div><div class="exp-alert" id="redox-alert" hidden></div>'),
        "5": render_record_table(["序号", "介质", "转移电子数", "配平结果"], "redox-rows"),
        "6": ('<h3>计算方法</h3><p>系统先按给定核心物种和反应介质补入水与氢离子或氢氧根，再检查原子、电荷、氧化数和电子守恒。</p>'
               '<h3>模型范围</h3><p>本页只处理需求明确给出的常见物种，不预测生成物，也不判断反应的热力学可行性或反应速率。</p>'),
        "css": ('.redox-stage{width:100%;min-width:0;box-sizing:border-box;padding:14px;border:1px solid #d8e7f5;border-radius:14px;'
                'background:linear-gradient(160deg,#fbfdff,#eaf3fb)}.redox-stage canvas{display:block;width:100%;height:clamp(340px,48vw,520px);max-width:100%}'
                '.redox-caption{color:#536b80;font-size:14px;line-height:1.6}.redox-controls{display:grid;gap:14px;min-width:0}'
                '.redox-controls select{width:100%;min-height:42px;padding:8px 12px;border:1px solid #c9d8e6;border-radius:8px;background:#fff;color:#20384d}'
                '.redox-species{display:grid;grid-template-columns:120px repeat(2,minmax(0,1fr));gap:8px;align-items:center;padding:10px;border:1px solid #d8e7f5;border-radius:10px;background:#f8fbfe}'
                '.redox-species span{overflow-wrap:anywhere}.exp-reads{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.exp-read{min-width:0}.exp-read .v{overflow-wrap:anywhere;min-width:0}'
                '@media(max-width:700px){.redox-stage{padding:8px}.redox-stage canvas{height:360px}.redox-species{grid-template-columns:minmax(0,1fr)}.exp-reads{grid-template-columns:minmax(0,1fr)}}'),
        "js": _redox_collection_js_template(config),
    }
    return sections


def _find_solid(req):
    for key in ("固体化学式", "solid_formula", "化学式"):
        direct = _normalized_text(req.get(key, "")).replace(" ", "")
        if direct:
            for entry in KSP_SOLIDS:
                if direct.casefold() == entry["formula"].casefold():
                    return entry
    text = _normalized_text(_request_text(req))
    candidates = []
    for entry in KSP_SOLIDS:
        for name in entry["names"]:
            normalized_name = _normalized_text(name)
            if normalized_name and normalized_name.casefold() in text.casefold():
                candidates.append((len(normalized_name), entry))
    return max(candidates, key=lambda pair: pair[0])[1] if candidates else None


def _read_positive_number(value):
    try:
        number = float(_normalized_text(value).strip())
        return number if 0 < number <= 1e6 else None
    except (TypeError, ValueError, OverflowError):
        return None


def _ksp_number(req, default=None):
    for key in ("Ksp", "ksp", "溶度积"):
        if req.get(key) is not None:
            value = _read_positive_number(req[key])
            if value is not None:
                return value
    text = _normalized_text(_request_text(req))
    number = r"(\d+(?:\.\d+)?(?:\s*e[+-]?\d+)?)"
    patterns = (
        r"(?:K\s*_?\s*sp|溶度积)[^\d]{0,24}" + number,
        r"K\s*_?\s*sp\s*[:=：]\s*" + number,
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            value = _read_positive_number(match.group(1).replace(" ", ""))
            if value is not None:
                return value
    return default


def _normalize_numeric_text(value):
    return (str("" if value is None else value).strip().translate(_SUPERSCRIPTS)
            .replace("×10", "e").replace("·10", "e").replace("×", "e"))


def _ion_value(req, ion, default=0.0):
    direct = req.get("离子初始浓度", req.get("initial_ion_concentrations", {}))
    if isinstance(direct, dict):
        for key in (ion["formula"], ion["display"], *ion["aliases"]):
            if key in direct:
                try:
                    value = float(_normalize_numeric_text(direct[key]).split()[0])
                    if 0 <= value <= 1e3:
                        return value
                except (TypeError, ValueError, OverflowError):
                    pass

    for variable in req.get("核心变量", []) or []:
        if not isinstance(variable, dict):
            continue
        variable_name = _normalized_text(variable.get("名称", ""))
        if any(re.search(alias, variable_name, re.I) for alias in ion["aliases"]):
            for key in ("初始值", "默认值", "重置值", "初值"):
                if variable.get(key) is not None:
                    try:
                        value = float(_normalize_numeric_text(variable[key]).split()[0])
                        if 0 <= value <= 1e3:
                            return value
                    except (TypeError, ValueError, OverflowError):
                        pass

    text = _normalize_numeric_text(_request_text(req))
    number = r"((?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?)"
    for alias in ion["aliases"]:
        match = re.search(alias + r"[^\d]{0,24}" + number, text, re.I)
        if match:
            try:
                value = float(match.group(1))
                if 0 <= value <= 1e3:
                    return value
            except (TypeError, ValueError, OverflowError):
                pass
    return default


def _ion_max(req, ion, default=0.1):
    for variable in req.get("核心变量", []) or []:
        if not isinstance(variable, dict):
            continue
        variable_name = _normalized_text(variable.get("名称", ""))
        if not any(re.search(alias, variable_name, re.I) for alias in ion["aliases"]):
            continue
        values = re.findall(r"(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?",
                            _normalize_numeric_text(variable.get("范围", "")), re.I)
        try:
            maximum = max(float(value) for value in values)
            if maximum > 0:
                return min(maximum, 1e3)
        except (ValueError, TypeError):
            pass
    return default


def _requested_page_modules(req):
    raw = req.get("页面模块", []) or []
    if isinstance(raw, str):
        requested = [raw]
    elif isinstance(raw, (list, tuple, set)):
        requested = [str(item) for item in raw]
    else:
        requested = []
    interactions = req.get("交互要求", []) or []
    if isinstance(interactions, str):
        interactions = [interactions]
    source = " ".join(requested + [str(value) for value in interactions])
    compare = any(word in source for word in ("共同离子对比", "基准对比", "对照组", "对比纯水"))
    modules = ["实验示意图", "参数控制", "求解结果", "数据记录", "教学说明"]
    if compare:
        modules.append("共同离子对比")
    return modules


def resolve_ksp_config(req):
    """Convert a lesson request into validated, allowlisted Ksp page data."""
    req = req or {}
    solid = _find_solid(req)
    if solid is None:
        supported = "、".join(entry["display"] for entry in KSP_SOLIDS)
        raise KspConfigurationError("当前 Ksp 模板已登记的物质为：%s；此需求中的物质尚未登记。" % supported)
    ksp = _ksp_number(req, solid.get("default_ksp"))
    if ksp is None:
        raise KspConfigurationError("需求没有给出 %s 的 Ksp 数值；模板不会自行猜测。" % solid["display"])

    ions = []
    for ion in copy.deepcopy(solid["ions"]):
        initial = _ion_value(req, ion)
        maximum = max(_ion_max(req, ion), initial, 1e-6)
        ion.update({"initial_concentration_mol_L": initial,
                    "control_max_mol_L": maximum})
        ions.append(ion)
    return {
        "scene_id": "chemistry-solubility-ksp",
        "solid_formula": solid["formula"],
        "solid_display": solid["display"],
        "Ksp": ksp,
        "ions": ions,
        "assumptions": ["固定温度", "理想稀溶液", "过饱和只判断沉淀倾向"],
        "modules": _requested_page_modules(req),
    }


def ksp_template_values(req):
    config = resolve_ksp_config(req)
    return {"物质": config["solid_formula"], "Ksp": config["Ksp"],
            "初始离子浓度mol_L": [ion["initial_concentration_mol_L"] for ion in config["ions"]],
            "页面模块": config["modules"]}


def _q_expression(ions):
    terms = []
    for ion in ions:
        exponent = int(ion["coefficient"])
        suffix = str(exponent).translate(_SUPERSCRIPT_DIGITS) if exponent > 1 else ""
        terms.append("[%s]%s" % (ion["display"], suffix))
    return "Q=" + "".join(terms)


def _config_for_js(config):
    safe = {"solid_formula": config["solid_formula"], "Ksp": config["Ksp"],
            "ions": [{key: ion[key] for key in
                      ("formula", "display", "charge", "coefficient", "initial_concentration_mol_L")}
                     for ion in config["ions"]]}
    return (json.dumps(safe, ensure_ascii=False, separators=(",", ":"))
            .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))


def _js_template(config):
    template = r'''(function(){
  var CFG=__KSP_CONFIG__;
  var canvas=document.getElementById('ksp-canvas');
  var kspInput=document.getElementById('ksp-value');
  var ionInputs=Array.from(document.querySelectorAll('[data-chem-ksp-ion-index]'))
    .sort(function(a,b){return Number(a.dataset.chemKspIonIndex)-Number(b.dataset.chemKspIonIndex);});
  var ionSliders=Array.from(document.querySelectorAll('[data-chem-ksp-ion-slider-index]'))
    .sort(function(a,b){return Number(a.dataset.chemKspIonSliderIndex)-Number(b.dataset.chemKspIonSliderIndex);});
  var equation=document.querySelector('[data-chem-ksp-equation]');
  var expression=document.querySelector('[data-chem-ksp-expression]');
  var qOut=document.querySelector('[data-chem-ksp-ion-product]');
  var stateOut=document.querySelector('[data-chem-ksp-state]');
  var solOut=document.querySelector('[data-chem-ksp-solubility]');
  var alertBox=document.getElementById('ksp-alert');
  var rows=document.getElementById('ksp-rows');
  var defaults=[kspInput.value].concat(ionInputs.map(function(input){return input.value;}));
  function exp(value){return Number(value).toExponential(4);}
  function render(){
    var request={solid_formula:CFG.solid_formula,Ksp:kspInput.valueAsNumber,ions:CFG.ions.map(function(ion,index){
      return {formula:ion.formula,charge:ion.charge,coefficient:ion.coefficient,
        initial_concentration_mol_L:ionInputs[index].valueAsNumber};
    })};
    window.__CHEM_KSP_REQUEST__=request;
    try{
      var result=CHEMSOLVER.solveSolubilityEquilibrium(request);
      window.__CHEM_KSP_RESULT__=result;
      if(!result.checks||result.checks.ok!==true) throw new Error('求解器校验未通过');
      equation.textContent=result.dissolution_equation;
      expression.textContent='Q='+result.ions.map(function(ion,index){
        var power=ion.coefficient>1?String(ion.coefficient).replace(/[0-9]/g,function(d){return '⁰¹²³⁴⁵⁶⁷⁸⁹'[Number(d)];}):'';
        return '['+CFG.ions[index].display+']'+power;
      }).join('');
      qOut.textContent='Q='+exp(result.initial_ion_product)+'；Ksp='+exp(result.Ksp);
      stateOut.textContent=({unsaturated:'未饱和 · 可继续溶解',saturated:'饱和 · 动态平衡',
        supersaturated:'过饱和 · 有沉淀倾向'})[result.saturation_state]||'状态未知';
      solOut.textContent=result.molar_solubility_mol_L===null?'无定义（过饱和）':
        exp(result.molar_solubility_mol_L)+' mol/L';
      document.getElementById('ksp-value-label').textContent=exp(result.Ksp);
      ionInputs.forEach(function(input,index){
        document.getElementById('ksp-ion-'+index+'-label').textContent=String(request.ions[index].initial_concentration_mol_L);
      });
      document.getElementById('ksp-formula').textContent='Q / Ksp = '+exp(result.saturation_ratio);
      document.getElementById('ksp-hint').textContent=result.precipitation_expected?
        'Q 大于 Ksp：有沉淀倾向；页面不计算沉淀量或新的平衡。':
        '按固定温度、理想稀溶液模型计算；图示和读数使用同一求解结果。';
      alertBox.hidden=true;alertBox.textContent='';
      CHEM.solubility(canvas,result);
      var comparison=document.getElementById('ksp-common-ion-comparison');
      if(comparison){
        var baselineRequest={solid_formula:request.solid_formula,Ksp:request.Ksp,
          ions:request.ions.map(function(ion){return Object.assign({},ion,{initial_concentration_mol_L:0});})};
        var baselineResult=CHEMSOLVER.solveSolubilityEquilibrium(baselineRequest);
        if(!baselineResult.checks||baselineResult.checks.ok!==true) throw new Error('共同离子基准值求解失败');
        document.getElementById('ksp-baseline-solubility').textContent=
          baselineResult.molar_solubility_mol_L===null?'无定义':exp(baselineResult.molar_solubility_mol_L)+' mol/L';
        document.getElementById('ksp-current-solubility').textContent=
          result.molar_solubility_mol_L===null?'无定义（过饱和）':exp(result.molar_solubility_mol_L)+' mol/L';
      }
      window.__CHEM_KSP_CONTROLS__={Ksp:kspInput.valueAsNumber,
        ion_indices:ionInputs.map(function(input,index){return index;}),
        initial_concentrations_mol_L:request.ions.map(function(ion){return ion.initial_concentration_mol_L;})};
      window.__DATA__={params:{Ksp:request.Ksp,ions:request.ions},
        result:{Q:result.initial_ion_product,state:result.saturation_state,
          solubility:result.molar_solubility_mol_L},checks:result.checks};
    }catch(error){
      window.__CHEM_KSP_RESULT__=null;
      equation.textContent='—';qOut.textContent='—';stateOut.textContent='无法计算';solOut.textContent='—';
      alertBox.textContent='输入无效或求解失败：'+error.message;alertBox.hidden=false;
      var context=canvas.getContext('2d');context.clearRect(0,0,canvas.width,canvas.height);
      window.__DATA__={params:{Ksp:request.Ksp,ions:request.ions},result:null,checks:{ok:false}};
    }
  }
  ionSliders.forEach(function(slider,index){slider.addEventListener('input',function(){
    ionInputs[index].value=slider.value;render();
  });});
  ionInputs.forEach(function(input,index){input.addEventListener('input',function(){
    ionSliders[index].value=input.value;render();
  });});
  kspInput.addEventListener('input',render);
  document.getElementById('btn-record').addEventListener('click',function(){
    if(!window.__CHEM_KSP_RESULT__)return;
    var result=window.__CHEM_KSP_RESULT__,tr=document.createElement('tr');
    var values=[rows.children.length+1,exp(kspInput.valueAsNumber)];
    ionInputs.forEach(function(input){values.push(String(input.valueAsNumber));});
    values.push(exp(result.initial_ion_product),stateOut.textContent,solOut.textContent);
    values.forEach(function(value){var td=document.createElement('td');td.textContent=String(value);tr.appendChild(td);});
    rows.appendChild(tr);
  });
  document.getElementById('btn-reset').addEventListener('click',function(){
    kspInput.value=defaults[0];ionInputs.forEach(function(input,index){
      input.value=defaults[index+1];ionSliders[index].value=defaults[index+1];
    });rows.innerHTML='';render();
  });
  render();
})();'''
    return template.replace("__KSP_CONFIG__", _config_for_js(config))


def render_ksp_template(req, config=None):
    """Compose a Ksp lesson from an allowlisted solid config and page parts."""
    config = config or resolve_ksp_config(req)
    title = html.escape(str(req.get("实验名称") or (config["solid_display"] + "溶解平衡")))
    goals = req.get("学习目标") or [
        "比较离子积 Q 与 Ksp，判断溶液状态。",
        "观察共同离子浓度对额外摩尔溶解度的影响。",
    ]
    ksp_text = format(config["Ksp"], ".12g")
    ion_controls = []
    for index, ion in enumerate(config["ions"]):
        ion_controls.append(render_slider_number_control(
            "初始 %s 浓度" % ion["display"], "ksp-ion-%d" % index,
            format(ion["initial_concentration_mol_L"], ".12g"),
            format(ion["control_max_mol_L"], ".12g"), index,
            ion["display"] + "浓度", unit="mol/L"))
    table_headers = ["序号", "Ksp"] + ["[%s]初始" % ion["display"] for ion in config["ions"]] + [
        "Q", "状态", "s（mol/L）"]
    expression = _q_expression(config["ions"])
    equation_description = "%s(s) ⇌ %s" % (
        config["solid_display"], " + ".join(
            ((str(ion["coefficient"]) if ion["coefficient"] > 1 else "") + ion["display"] + "(aq)")
            for ion in config["ions"]))

    comparison_html = ""
    if "共同离子对比" in config["modules"]:
        comparison_html = render_comparison_panel(
            "ksp-common-ion-comparison", "共同离子影响对比",
            "无初始共同离子时的摩尔溶解度", "当前输入下的额外摩尔溶解度",
            "ksp-baseline-solubility", "ksp-current-solubility")

    sections = {
        "1": render_subject_tags("化学", req.get("年级") or "高中") + render_learning_goals(goals),
        "2": (
            '<div class="ksp-scene-card"><canvas id="ksp-canvas" data-visual-type="apparatus" '
            'aria-label="%s 固体、溶液离子与溶解平衡示意图"></canvas>'
            '<p class="ksp-scene-caption">图示随当前求解结果更新；过饱和只表示有沉淀倾向。</p></div>'
            % html.escape(config["solid_display"])
        ),
        "3": (
            '<div class="ksp-controls">' +
            render_number_control("溶度积 Ksp", "ksp-value", ksp_text, "1e-80", "1e6",
                                  "data-chem-ksp-value", "溶度积 Ksp") +
            "".join(ion_controls) +
            render_action_buttons([("btn-record", "记录当前数据", True), ("btn-reset", "重置", False)]) +
            "</div>"
        ),
        "4": (
            '<div class="exp-reads">' +
            render_result_card("溶解方程", "data-chem-ksp-equation") +
            render_result_card("离子积表达式", "data-chem-ksp-expression", expression) +
            render_result_card("当前离子积", "data-chem-ksp-ion-product") +
            render_result_card("溶液状态", "data-chem-ksp-state") +
            render_result_card("额外摩尔溶解度", "data-chem-ksp-solubility") +
            '</div>' + comparison_html + '<div class="exp-formula" id="ksp-formula"></div>'
            '<p class="exp-note" id="ksp-hint">本页为教学演示（虚拟仿真），按固定温度、理想稀溶液模型计算。</p>'
            '<div class="exp-alert" id="ksp-alert" hidden></div>'
        ),
        "5": render_record_table(table_headers, "ksp-rows"),
        "6": (
            '<h3>原理</h3><p>%s；离子积表达式为 %s。'
            '比较 Q 与 Ksp 可判断未饱和、饱和或过饱和状态；共同离子会降低额外溶解量。</p>'
            '<h3>易错点</h3><p>难溶固体不写入 Ksp 表达式；过饱和表示有沉淀倾向，本页面不计算沉淀后的新平衡。</p>'
            '<h3>结论</h3><p>数值读数和实验示意图由同一个学科求解结果驱动。</p>'
            '<h3>适用范围</h3><p>按给定 Ksp、固定温度和理想稀溶液近似计算；不推算活度系数、络合或温度依赖。</p>'
            % (html.escape(equation_description), html.escape(expression))
        ),
        "css": (
            '.ksp-scene-card{width:100%;min-width:0;padding:14px;box-sizing:border-box;'
            'border:1px solid #d8e7f5;border-radius:14px;background:linear-gradient(160deg,#fbfdff,#eaf3fb)}'
            '#ksp-canvas{display:block;width:100%;height:460px;max-width:100%}'
            '.ksp-scene-caption{margin:8px 4px 0;color:#536b80;font-size:14px}'
            '.ksp-controls{display:grid;gap:14px;min-width:0}'
            '.ksp-controls input{width:100%;max-width:100%;box-sizing:border-box}'
            '.ksp-controls input[type=range]{accent-color:#438bd2;margin:10px 0}'
            '.exp-comparison{margin:16px 0;padding:14px;border:1px solid #d8e7f5;border-radius:12px;'
            'background:#f7fbff}.exp-comparison-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}'
            '.exp-read .v{overflow-wrap:anywhere;min-width:0}'
            '@media(max-width:700px){#ksp-canvas{height:340px}.ksp-scene-card{padding:8px} '
            '.exp-comparison-grid{grid-template-columns:minmax(0,1fr)}}'
        ),
        "js": _js_template(config),
    }
    return sections


def _titration_config_for_js(config):
    safe = {
        "acid": {key: config["acid"][key] for key in
                 ("formula", "name", "concentration_mol_L", "volume", "volume_unit")},
        "base": {key: config["base"][key] for key in
                 ("formula", "name", "concentration_mol_L", "volume", "volume_unit")},
        "slider_max_ml": config["slider_max_ml"],
    }
    return (json.dumps(safe, ensure_ascii=False, separators=(",", ":"))
            .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))


def _titration_js_template(config):
    template = r'''(function(){
  'use strict';
  var CFG=__TITRATION_CONFIG__;
  var $=function(selector){return document.querySelector(selector);};
  var acidC=$('[data-chem-titration-acid-concentration]');
  var acidV=$('[data-chem-titration-acid-volume]');
  var acidU=$('[data-chem-titration-acid-unit]');
  var baseC=$('[data-chem-titration-base-concentration]');
  var baseV=$('[data-chem-titration-base-volume]');
  var baseU=$('[data-chem-titration-base-unit]');
  var baseRange=document.getElementById('titration-base-volume-range');
  var apparatus=document.getElementById('titration-apparatus');
  var curve=document.getElementById('titration-curve');
  var rows=document.getElementById('titration-rows');
  var alertBox=document.getElementById('titration-alert');
  var defaults={acidC:acidC.value,acidV:acidV.value,acidU:acidU.value,
    baseC:baseC.value,baseV:baseV.value,baseU:baseU.value};
  function volumeFactor(unit){return String(unit).toLowerCase()==='ml'?1:1000;}
  function formatNumber(value,digits){
    var number=Number(value);
    return Number.isFinite(number)?number.toPrecision(digits||4).replace(/(?:\.0+|(\.\d*?)0+)$/,'$1'):String(value);
  }
  function stateLabel(state){return ({acidic:'酸性（酸过量）',equivalence:'当量点（恰好中和）',basic:'碱性（碱过量）'})[state]||'状态未知';}
  function makeRequest(){
    return {acid:{formula:CFG.acid.formula,concentration_mol_L:acidC.valueAsNumber,
      volume:acidV.valueAsNumber,volume_unit:acidU.value},
      base:{formula:CFG.base.formula,concentration_mol_L:baseC.valueAsNumber,
        volume:baseV.valueAsNumber,volume_unit:baseU.value}};
  }
  function clearCanvas(canvas){
    if(!canvas)return;
    var ctx=canvas.getContext('2d');
    if(ctx)ctx.clearRect(0,0,canvas.width,canvas.height);
  }
  function solveCurve(request,result){
    var equivalenceMl=Number(result.equivalence_volume_ml);
    var factor=volumeFactor(request.base.volume_unit);
    var currentMl=Number(request.base.volume)*factor;
    var allowedMl=1000000*factor;
    var maxMl=Math.min(allowedMl,Math.max(equivalenceMl*1.5,currentMl*1.12,1));
    var values=[];
    for(var i=0;i<=48;i++)values.push(maxMl*i/48);
    values.push(Math.min(maxMl,currentMl));
    if(equivalenceMl<=maxMl){
      var delta=Math.max(equivalenceMl*0.004,0.001);
      values.push(Math.max(0,equivalenceMl-delta),equivalenceMl,Math.min(maxMl,equivalenceMl+delta));
    }
    values=Array.from(new Set(values.map(function(value){return Number(value.toPrecision(12));})))
      .sort(function(a,b){return a-b;});
    var samples=values.map(function(volumeMl){
      var sampleRequest={acid:Object.assign({},request.acid),
        base:Object.assign({},request.base,{volume:volumeMl/factor})};
      var sampleResult=CHEMSOLVER.solveAcidBaseTitration(sampleRequest);
      if(!sampleResult.checks||sampleResult.checks.ok!==true)throw new Error('滴定曲线样本未通过求解器守恒校验');
      return {volume_ml:volumeMl,pH:sampleResult.pH,state:sampleResult.state,
        request:sampleRequest,result:sampleResult};
    });
    return {max_ml:maxMl,equivalence_ml:equivalenceMl,current_ml:currentMl,samples:samples};
  }
  function syncBaseSlider(request){
    var ml=request.base.volume*volumeFactor(request.base.volume_unit);
    var max=Math.max(Number(baseRange.max)||CFG.slider_max_ml,ml,1);
    baseRange.max=String(Math.min(1000000,max));
    baseRange.value=String(Math.min(ml,Number(baseRange.max)));
    var unitLabel=document.getElementById('titration-base-volume-unit-label');
    if(unitLabel)unitLabel.textContent=request.base.volume_unit;
    var acidUnitLabel=document.getElementById('titration-acid-volume-unit-label');
    if(acidUnitLabel)acidUnitLabel.textContent=request.acid.volume_unit;
  }
  function render(){
    var request=makeRequest();
    window.__CHEM_TITRATION_REQUEST__=request;
    try{
      var result=CHEMSOLVER.solveAcidBaseTitration(request);
      if(!result.checks||result.checks.ok!==true)throw new Error('求解器守恒校验未通过');
      var curveData=solveCurve(request,result);
      window.__CHEM_TITRATION_RESULT__=result;
      window.__CHEM_TITRATION_CURVE_SAMPLES__=curveData.samples;
      window.__CHEM_TITRATION_CURVE_DATA__=curveData;
      document.querySelector('[data-chem-titration-equation]').textContent=result.equation;
      document.querySelector('[data-chem-titration-ph]').textContent='pH = '+result.pH.toFixed(2);
      document.querySelector('[data-chem-titration-state]').textContent=stateLabel(result.state);
      document.querySelector('[data-chem-titration-equivalence]').textContent=formatNumber(result.equivalence_volume_ml,4)+' mL';
      document.querySelector('[data-chem-titration-acid-remaining]').textContent=formatNumber(result.acid_moles_remaining,4)+' mol';
      document.querySelector('[data-chem-titration-base-remaining]').textContent=formatNumber(result.base_moles_remaining,4)+' mol';
      document.getElementById('titration-formula').textContent=
        'n(酸) = '+formatNumber(result.acid_moles_initial,4)+' mol；n(碱) = '+formatNumber(result.base_moles_added,4)+
        ' mol；n(已中和) = '+formatNumber(result.neutralized_moles,4)+' mol。';
      document.getElementById('titration-acid-concentration-label').textContent=formatNumber(request.acid.concentration_mol_L,4);
      document.getElementById('titration-acid-volume-label').textContent=formatNumber(request.acid.volume,4);
      document.getElementById('titration-base-concentration-label').textContent=formatNumber(request.base.concentration_mol_L,4);
      document.getElementById('titration-base-volume-label').textContent=formatNumber(request.base.volume,4);
      document.getElementById('titration-chart-summary').textContent=
        '当前 pH '+result.pH.toFixed(2)+'；理论当量体积 '+formatNumber(result.equivalence_volume_ml,4)+' mL；图中数据点逐个由滴定求解器计算。';
      syncBaseSlider(request);
      CHEM.titration(apparatus,result);
      CHEM.titrationCurve(curve,curveData,result);
      alertBox.hidden=true;alertBox.textContent='';
      window.__DATA__={params:request,result:result,checks:result.checks,
        titrationCurveSamples:curveData.samples.length};
    }catch(error){
      window.__CHEM_TITRATION_RESULT__=null;window.__CHEM_TITRATION_CURVE_SAMPLES__=[];
      window.__CHEM_TITRATION_CURVE_DATA__=null;
      document.querySelector('[data-chem-titration-equation]').textContent='—';
      document.querySelector('[data-chem-titration-ph]').textContent='pH = —';
      document.querySelector('[data-chem-titration-state]').textContent='无法计算';
      ['[data-chem-titration-equivalence]','[data-chem-titration-acid-remaining]','[data-chem-titration-base-remaining]']
        .forEach(function(selector){document.querySelector(selector).textContent='—';});
      document.getElementById('titration-formula').textContent='当前输入无法形成有效计算结果。';
      alertBox.textContent='输入无效或超出当前模型范围：'+error.message;alertBox.hidden=false;
      clearCanvas(apparatus);clearCanvas(curve);
      window.__DATA__={params:request,result:null,checks:{ok:false}};
    }
  }
  [acidC,acidV,acidU,baseC,baseV,baseU].forEach(function(control){
    control.addEventListener('input',render);control.addEventListener('change',render);
  });
  baseRange.addEventListener('input',function(){
    var value=Number(baseRange.value),factor=volumeFactor(baseU.value);
    baseV.value=String(value/factor);render();
  });
  document.getElementById('btn-record').addEventListener('click',function(){
    var result=window.__CHEM_TITRATION_RESULT__;if(!result)return;
    var values=[rows.children.length+1,formatNumber(result.base.volume_input,4)+' '+result.base.volume_unit,
      result.pH.toFixed(2),stateLabel(result.state),formatNumber(result.acid_moles_remaining,4),formatNumber(result.base_moles_remaining,4)];
    var row=document.createElement('tr');values.forEach(function(value){var cell=document.createElement('td');cell.textContent=String(value);row.appendChild(cell);});rows.appendChild(row);
  });
  document.getElementById('btn-reset').addEventListener('click',function(){
    acidC.value=defaults.acidC;acidV.value=defaults.acidV;acidU.value=defaults.acidU;
    baseC.value=defaults.baseC;baseV.value=defaults.baseV;baseU.value=defaults.baseU;
    rows.textContent='';render();
  });
  window.addEventListener('resize',function(){
    var result=window.__CHEM_TITRATION_RESULT__,data=window.__CHEM_TITRATION_CURVE_DATA__;
    if(result&&data){CHEM.titration(apparatus,result);CHEM.titrationCurve(curve,data,result);}
  });
  render();
})();'''
    return template.replace("__TITRATION_CONFIG__", _titration_config_for_js(config))


def render_acid_base_titration_template(req, config=None):
    """Compose a titration page from shared parts plus a dedicated curve and apparatus."""
    config = config or resolve_acid_base_titration_config(req)
    acid, base = config["acid"], config["base"]
    goals = req.get("学习目标") or [
        "理解酸碱中和反应和理论当量点。",
        "观察滴定液体积变化时溶液 pH 的变化。",
    ]
    title = html.escape(str(req.get("实验名称") or "酸碱中和滴定"))
    unit_options = [("mL", "mL（毫升）"), ("L", "L（升）")]
    controls = (
        '<section class="titration-control-group"><h3>待测酸液</h3>'
        + render_number_control("酸液浓度", "titration-acid-concentration",
            format(acid["concentration_mol_L"], ".12g"), "0.000001", "1",
            "data-chem-titration-acid-concentration", "酸液浓度", "mol/L")
        + render_number_control("酸液体积", "titration-acid-volume",
            format(acid["volume"], ".12g"), "0.000001", "1000000",
            "data-chem-titration-acid-volume", "待测酸液体积")
        + render_select_control("酸液体积单位", "titration-acid-unit", unit_options,
            acid["volume_unit"], "data-chem-titration-acid-unit", "酸液体积单位")
        + '</section><section class="titration-control-group"><h3>滴定液</h3>'
        + render_number_control("滴定液浓度", "titration-base-concentration",
            format(base["concentration_mol_L"], ".12g"), "0.000001", "1",
            "data-chem-titration-base-concentration", "滴定液浓度", "mol/L")
        + render_range_number_control("滴入体积", "titration-base-volume",
            format(base["volume"], ".12g"), "0", format(config["slider_max_ml"], ".12g"),
            "data-chem-titration-base-volume-range", "data-chem-titration-base-volume",
            "滴定液加入体积", unit="", range_value=format(
                base["volume"] * (1 if base["volume_unit"] == "mL" else 1000), ".12g"))
        + '<span class="titration-unit-caption">当前数值单位：<b id="titration-base-volume-unit-label">%s</b></span>'
          % html.escape(base["volume_unit"])
        + render_select_control("滴定液体积单位", "titration-base-unit", unit_options,
            base["volume_unit"], "data-chem-titration-base-unit", "滴定液体积单位")
        + '</section>'
    )
    table = render_record_table(
        ["序号", "滴入体积", "pH", "状态", "剩余酸量（mol）", "剩余碱量（mol）"],
        "titration-rows")
    sections = {
        "1": render_subject_tags("化学", req.get("年级") or "高中") + render_learning_goals(goals),
        "2": (
            '<div class="titration-stage"><div class="titration-apparatus-frame">'
            '<canvas id="titration-apparatus" width="880" height="700" data-visual-type="apparatus" '
            'aria-label="%s滴定实验装置图"></canvas></div>'
            '<p class="titration-scene-caption">滴定管中的滴定液加入锥形瓶；装置状态随当前求解结果更新。'
            '本页为教学虚拟仿真，指示剂颜色仅作示意。</p><div id="tip" class="sr-only"></div></div>'
            % html.escape(acid["name"] + "与" + base["name"])
        ),
        "3": '<div class="titration-controls">%s</div>' % controls +
             render_action_buttons([("btn-record", "记录当前数据", True), ("btn-reset", "重置", False)]),
        "4": (
            '<div class="exp-reads">'
            + render_result_card("中和方程式", "data-chem-titration-equation")
            + render_result_card("当前 pH", "data-chem-titration-ph")
            + render_result_card("溶液状态", "data-chem-titration-state")
            + render_result_card("理论当量体积", "data-chem-titration-equivalence")
            + render_result_card("剩余酸的物质的量", "data-chem-titration-acid-remaining")
            + render_result_card("剩余碱的物质的量", "data-chem-titration-base-remaining")
            + '</div><div class="exp-formula" id="titration-formula"></div>'
            '<section class="titration-chart-panel"><h3>pH—滴入体积曲线</h3>'
            '<canvas id="titration-curve" data-chem-titration-curve aria-label="滴定曲线"></canvas>'
            '<p id="titration-chart-summary" class="titration-chart-summary"></p></section>'
            '<div class="exp-alert" id="titration-alert" hidden></div>'
        ),
        "5": table,
        "6": (
            '<h3>反应方程式</h3><p>%s(aq) + %s(aq) → %s(aq) + H₂O(l)。'
            '当前模型按 1:1 反应计算。</p>'
            '<h3>实验现象</h3><p>逐滴加入滴定液后，溶液 pH 由低逐渐升高；接近理论当量点时 pH 出现突跃，'
            '越过当量点后变化趋于平缓。指示剂在当量点附近发生颜色转变。</p>'
            '<h3>当量点</h3><p>酸与碱恰好按反应比例完全反应时到达理论当量点。曲线上的每个采样点都由同一个滴定求解器重新计算，'
            '蓝色虚线标出理论当量体积，圆点表示当前输入。</p>'
            '<h3>模型范围</h3><p>当前仅支持强一元酸 HCl、HBr、HI、HNO₃、HClO₄ 与强一元碱 LiOH、NaOH、KOH；'
            '按 25°C、理想溶液和完全电离近似计算，并考虑水的自电离。弱酸弱碱、多元酸碱、活度效应和指示剂误差不在本模型范围内。</p>'
            % (html.escape(acid["formula"]), html.escape(base["formula"]),
               html.escape(base["formula"].replace("OH", "") + acid["formula"].replace("H", "")))
        ),
        "css": (
            '.titration-stage,.titration-chart-panel{width:100%;min-width:0;box-sizing:border-box;'
            'padding:14px;border:1px solid #d8e7f5;border-radius:14px;background:linear-gradient(160deg,#fbfdff,#eaf3fb)}'
            '.titration-apparatus-frame{width:100%;height:clamp(360px,52vw,560px);min-width:0;overflow:hidden;border-radius:10px}'
            '#titration-apparatus{display:block;width:100%;height:100%;max-width:100%}'
            '.titration-scene-caption,.titration-chart-summary,.titration-unit-caption{color:#536b80;font-size:14px;line-height:1.6}'
            '.titration-controls{display:grid;gap:14px;min-width:0}.titration-control-group{display:grid;gap:10px;'
            'min-width:0;padding:16px;border:1px solid #d8e7f5;border-radius:12px;background:#f8fbfe}'
            '.titration-control-group h3,.titration-chart-panel h3{margin:0 0 4px;color:#000;font-size:18px}'
            '.titration-controls input,.titration-controls select{width:100%;max-width:100%;box-sizing:border-box}'
            '.titration-controls input[type=range]{accent-color:#438bd2;margin:8px 0}'
            '.titration-controls select{min-height:42px;padding:8px 12px;border:1px solid #c9d8e6;border-radius:8px;background:#fff;color:#20384d}'
            '.titration-controls .exp-field{min-width:0}.titration-controls .exp-label{gap:12px;flex-wrap:wrap}'
            '.titration-unit-caption{margin-top:-7px}.exp-reads{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}'
            '.exp-read{min-width:0}.exp-read .v{overflow-wrap:anywhere;min-width:0}'
            '.titration-chart-panel{margin-top:16px}.titration-chart-panel canvas{display:block;width:100%;height:320px;max-width:100%;margin-top:12px}'
            '@media(max-width:700px){.titration-apparatus-frame{height:390px}.exp-reads{grid-template-columns:minmax(0,1fr)}'
            '.titration-stage,.titration-chart-panel{padding:8px}.titration-chart-panel canvas{height:260px}}'
        ),
        "js": _titration_js_template(config),
    }
    return sections


def _precipitation_config_for_js(config):
    safe = {
        "reaction_id": config["reaction_id"],
        "solutions": [{key: item[key] for key in
                       ("formula", "concentration_mol_L", "volume", "volume_unit")}
                      for item in config["solutions"]],
        "progress": config["progress"],
    }
    return (json.dumps(safe, ensure_ascii=False, separators=(",", ":"))
            .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))


def _precipitation_js_template(config):
    template = r'''(function(){
  'use strict';
  var CFG=__PRECIPITATION_CONFIG__, $=function(s){return document.querySelector(s);};
  var concentrations=Array.from(document.querySelectorAll('[data-chem-precip-concentration-index]'))
    .sort(function(a,b){return Number(a.dataset.chemPrecipConcentrationIndex)-Number(b.dataset.chemPrecipConcentrationIndex);});
  var volumes=Array.from(document.querySelectorAll('[data-chem-precip-volume-index]'))
    .sort(function(a,b){return Number(a.dataset.chemPrecipVolumeIndex)-Number(b.dataset.chemPrecipVolumeIndex);});
  var units=Array.from(document.querySelectorAll('[data-chem-precip-unit-index]'))
    .sort(function(a,b){return Number(a.dataset.chemPrecipUnitIndex)-Number(b.dataset.chemPrecipUnitIndex);});
  var progress=$('[data-chem-precip-progress]'), canvas=document.getElementById('precipitation-apparatus');
  var rows=document.getElementById('precipitation-rows'), alertBox=document.getElementById('precipitation-alert');
  var defaults={concentrations:concentrations.map(function(x){return x.value;}),volumes:volumes.map(function(x){return x.value;}),
    units:units.map(function(x){return x.value;}),progress:progress.value};
  function factor(unit){return String(unit).toLowerCase()==='ml'?0.001:1;}
  function fmt(value){var n=Number(value);return Number.isFinite(n)?n.toPrecision(5).replace(/(?:\.0+|(\.\d*?)0+)$/,'$1'):String(value);}
  function makeRequest(){return {solutions:CFG.solutions.map(function(item,index){return {formula:item.formula,
    concentration_mol_L:concentrations[index].valueAsNumber,volume:volumes[index].valueAsNumber,volume_unit:units[index].value};}),
    progress:progress.valueAsNumber};}
  function render(){
    var request=makeRequest();window.__CHEM_PRECIP_REQUEST__=request;
    try{
      var result=CHEMSOLVER.solvePrecipitation(request);
      if(!result.checks||result.checks.ok!==true)throw new Error('求解器守恒校验未通过');
      window.__CHEM_PRECIP_RESULT__=result;
      $('[data-chem-precip-equation]').textContent=result.equation;
      $('[data-chem-precip-net-ionic]').textContent=result.net_ionic_equation;
      $('[data-chem-precip-mass]').textContent=fmt(result.precipitate_mass_g)+' g';
      $('[data-chem-precip-moles]').textContent=fmt(result.precipitate_moles)+' mol';
      $('[data-chem-precip-state]').textContent=result.precipitation_occurs?'已生成 '+result.precipitate_formula+' 沉淀':'当前未生成可见沉淀';
      $('[data-chem-precip-limiting]').textContent=(result.limiting_reactants||[]).join('、')||'无';
      document.getElementById('precipitation-progress-label').textContent=Math.round(request.progress*100)+'%';
      document.getElementById('precipitation-summary').textContent='沉淀质量 '+fmt(result.precipitate_mass_g)+' g；图示、方程式和读数使用同一个求解结果。';
      CHEM.precipitation(canvas,result);
      alertBox.hidden=true;alertBox.textContent='';
      window.__DATA__={params:request,result:result,checks:result.checks};
    }catch(error){
      window.__CHEM_PRECIP_RESULT__=null;
      ['[data-chem-precip-equation]','[data-chem-precip-net-ionic]','[data-chem-precip-mass]',
       '[data-chem-precip-moles]','[data-chem-precip-state]','[data-chem-precip-limiting]']
        .forEach(function(selector){$(selector).textContent='—';});
      alertBox.textContent='输入无效或不支持该组合：'+error.message;alertBox.hidden=false;
      var context=canvas.getContext('2d');context.clearRect(0,0,canvas.width,canvas.height);
      window.__DATA__={params:request,result:null,checks:{ok:false}};
    }
  }
  concentrations.concat(volumes,units,[progress]).forEach(function(input){input.addEventListener('input',render);input.addEventListener('change',render);});
  document.getElementById('btn-record').addEventListener('click',function(){var result=window.__CHEM_PRECIP_RESULT__;if(!result)return;
    var row=document.createElement('tr'),values=[rows.children.length+1,Math.round(progress.valueAsNumber*100)+'%',fmt(result.precipitate_moles),fmt(result.precipitate_mass_g)+' g',result.precipitation_occurs?'有':'无'];
    values.forEach(function(value){var td=document.createElement('td');td.textContent=String(value);row.appendChild(td);});rows.appendChild(row);});
  document.getElementById('btn-reset').addEventListener('click',function(){concentrations.forEach(function(x,i){x.value=defaults.concentrations[i];});
    volumes.forEach(function(x,i){x.value=defaults.volumes[i];});units.forEach(function(x,i){x.value=defaults.units[i];});progress.value=defaults.progress;rows.textContent='';render();});
  window.addEventListener('resize',function(){if(window.__CHEM_PRECIP_RESULT__)CHEM.precipitation(canvas,window.__CHEM_PRECIP_RESULT__);});
  render();
})();'''
    return template.replace("__PRECIPITATION_CONFIG__", _precipitation_config_for_js(config))


def render_precipitation_template(req, config=None):
    """Compose a precipitation page from shared controls/results and the precipitation solver."""
    config = config or resolve_precipitation_config(req)
    solutions = config["solutions"]
    unit_options = [("mL", "mL（毫升）"), ("L", "L（升）")]
    controls = []
    for index, item in enumerate(solutions):
        controls.append('<section class="precip-control-group"><h3>溶液 %d：%s</h3>' %
                        (index + 1, html.escape(item["display"])))
        controls.append(render_number_control("浓度", "precip-concentration-%d" % index,
            format(item["concentration_mol_L"], ".12g"), "0.000001", "1",
            "data-chem-precip-concentration-index", "溶液 %d 浓度" % (index + 1), "mol/L",
            marker_value=index))
        controls.append(render_number_control("体积", "precip-volume-%d" % index,
            format(item["volume"], ".12g"), "0.000001", "1000000",
            "data-chem-precip-volume-index", "溶液 %d 体积" % (index + 1), "",
            marker_value=index))
        controls.append(render_select_control("体积单位", "precip-unit-%d" % index, unit_options,
            item["volume_unit"], "data-chem-precip-unit-index", "溶液 %d 体积单位" % (index + 1),
            marker_value=index))
        controls.append('</section>')
    controls.append('<label class="exp-field"><span class="exp-label"><span>反应进度</span>'
                    '<span class="exp-val"><b id="precipitation-progress-label">%d%%</b></span></span>'
                    '<input id="precipitation-progress" type="range" min="0" max="1" step="0.01" value="%s" '
                    'data-chem-precip-progress aria-label="反应进度"></label>' %
                    (round(config["progress"] * 100), format(config["progress"], ".12g")))
    sections = {
        "1": render_subject_tags("化学", req.get("年级") or "高中") + render_learning_goals(
            req.get("学习目标") or ["根据物质的量关系判断限量试剂。", "观察沉淀生成量随反应进度和溶液用量变化。"]),
        "2": ('<div class="precip-stage"><canvas id="precipitation-apparatus" width="880" height="700" '
               'data-visual-type="apparatus" aria-label="沉淀反应装置图"></canvas>'
               '<p class="precip-caption">左侧为混合前溶液，右侧显示沉淀生成状态；图示只展示求解器已经计算出的结果。</p></div>'),
        "3": ('<div class="precip-controls">%s</div>' % "".join(controls) +
               render_action_buttons([("btn-record", "记录当前数据", True), ("btn-reset", "重置", False)])),
        "4": ('<div class="exp-reads">' +
               render_result_card("分子方程式", "data-chem-precip-equation") +
               render_result_card("净离子方程式", "data-chem-precip-net-ionic") +
               render_result_card("沉淀状态", "data-chem-precip-state") +
               render_result_card("沉淀物质的量", "data-chem-precip-moles") +
               render_result_card("沉淀质量", "data-chem-precip-mass") +
               render_result_card("限量试剂", "data-chem-precip-limiting") +
               '</div><div class="exp-formula" id="precipitation-summary"></div>'
               '<div class="exp-alert" id="precipitation-alert" hidden></div>'),
        "5": render_record_table(["序号", "反应进度", "沉淀物质的量（mol）", "沉淀质量", "是否生成"], "precipitation-rows"),
        "6": ('<h3>判定方法</h3><p>系统先按登记的反应目录识别反应物，再由物质的量和方程式系数计算反应进度、限量试剂和沉淀质量。'
               '页面中的方程式、净离子方程式、结果卡片和实验图都读取同一个求解器结果。</p>'
               '<h3>模型范围</h3><p>当前仅支持已审核的六组定性完全沉淀反应；不猜测未登记组合，也不模拟 Ksp、络合、沉淀纯度或副反应。</p>'),
        "css": ('.precip-stage,.precip-control-group{width:100%;min-width:0;box-sizing:border-box;padding:14px;'
                'border:1px solid #d8e7f5;border-radius:14px;background:linear-gradient(160deg,#fbfdff,#eaf3fb)}'
                '.precip-stage canvas{display:block;width:100%;height:clamp(360px,52vw,560px);max-width:100%}'
                '.precip-caption{color:#536b80;font-size:14px;line-height:1.6}.precip-controls{display:grid;gap:14px;min-width:0}'
                '.precip-control-group{display:grid;gap:10px;background:#f8fbfe}.precip-control-group h3{margin:0;color:#245d91;font-size:18px}'
                '.precip-controls input,.precip-controls select{width:100%;max-width:100%;box-sizing:border-box}'
                '.precip-controls input[type=range]{accent-color:#438bd2;margin:8px 0}.precip-controls select{min-height:42px;padding:8px 12px;'
                'border:1px solid #c9d8e6;border-radius:8px;background:#fff;color:#20384d}.exp-reads{display:grid;'
                'grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.exp-read{min-width:0}.exp-read .v{overflow-wrap:anywhere;min-width:0}'
                '@media(max-width:700px){.precip-stage{padding:8px}.precip-stage canvas{height:390px}.exp-reads{grid-template-columns:minmax(0,1fr)}}'),
        "js": _precipitation_js_template(config),
    }
    return sections


def _gas_config_for_js(config):
    safe = {"reactants": config["reactants"], "products": config["products"],
            "gas_formula": config["gas_formula"]}
    return (json.dumps(safe, ensure_ascii=False, separators=(",", ":"))
            .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))


def _gas_collection_js_template(config):
    template = r'''(function(){
  'use strict';
  var CFG=__GAS_CONFIG__, $=function(s){return document.querySelector(s);};
  var amounts=Array.from(document.querySelectorAll('[data-chem-gas-amount-index]'))
    .sort(function(a,b){return Number(a.dataset.chemGasAmountIndex)-Number(b.dataset.chemGasAmountIndex);});
  var progress=$('[data-chem-gas-progress]'), temperature=$('[data-chem-gas-temperature]'),
      pressure=$('[data-chem-gas-pressure]'), method=$('[data-chem-gas-method]'),
      canvas=document.getElementById('gas-apparatus'), rows=document.getElementById('gas-rows'),
      alertBox=document.getElementById('gas-alert');
  var defaults={amounts:amounts.map(function(x){return x.value;}),progress:progress.value,
    temperature:temperature.value,pressure:pressure.value,method:method.value};
  function fmt(value){var n=Number(value);return Number.isFinite(n)?n.toPrecision(5).replace(/(?:\.0+|(\.\d*?)0+)$/,'$1'):String(value);}
  function makeRequest(){return {reactants:CFG.reactants,products:CFG.products,
    initial_amounts_mol:amounts.map(function(x){return x.valueAsNumber;}),progress:progress.valueAsNumber,
    gas_formula:CFG.gas_formula,temperature_c:temperature.valueAsNumber,
    total_pressure_kpa:pressure.valueAsNumber,collection_method:method.value};}
  function render(){
    var request=makeRequest();window.__CHEM_GAS_REQUEST__=request;
    try{
      var result=CHEMSOLVER.solveGasCollection(request);
      if(!result.checks||result.checks.ok!==true)throw new Error('求解器守恒或状态方程校验未通过');
      window.__CHEM_GAS_RESULT__=result;
      $('[data-chem-gas-equation]').textContent=result.equation;
      $('[data-chem-gas-volume]').textContent=fmt(result.gas_volume_l)+' L';
      $('[data-chem-gas-moles]').textContent=fmt(result.gas_moles)+' mol';
      $('[data-chem-gas-dry-pressure]').textContent=fmt(result.dry_gas_partial_pressure_kpa)+' kPa';
      $('[data-chem-gas-vapor-pressure]').textContent=fmt(result.water_vapor_pressure_kpa)+' kPa';
      $('[data-chem-gas-state]').textContent=result.collection_method==='over_water'?'排水集气（已扣除水蒸气压）':'干燥/排空气集气';
      $('[data-chem-gas-limiting]').textContent=(result.limiting_reactants||[]).join('、')||'无';
      document.getElementById('gas-progress-label').textContent=Math.round(request.progress*100)+'%';
      document.getElementById('gas-summary').textContent='目标气体 '+result.gas_formula+'，体积 '+fmt(result.gas_volume_l)+' L；气体体积由 PV=nRT 结果驱动。';
      CHEM.gasCollection(canvas,result);alertBox.hidden=true;alertBox.textContent='';
      window.__DATA__={params:request,result:result,checks:result.checks};
    }catch(error){
      window.__CHEM_GAS_RESULT__=null;
      ['[data-chem-gas-equation]','[data-chem-gas-volume]','[data-chem-gas-moles]','[data-chem-gas-pressure]',
       '[data-chem-gas-vapor-pressure]','[data-chem-gas-state]','[data-chem-gas-limiting]']
        .forEach(function(selector){$(selector).textContent='—';});
      alertBox.textContent='输入无效或气体模型求解失败：'+error.message;alertBox.hidden=false;
      var context=canvas.getContext('2d');context.clearRect(0,0,canvas.width,canvas.height);
      window.__DATA__={params:request,result:null,checks:{ok:false}};
    }
  }
  amounts.concat([progress,temperature,pressure,method]).forEach(function(input){input.addEventListener('input',render);input.addEventListener('change',render);});
  document.getElementById('btn-record').addEventListener('click',function(){var result=window.__CHEM_GAS_RESULT__;if(!result)return;
    var row=document.createElement('tr'),values=[rows.children.length+1,Math.round(result.progress*100)+'%',fmt(result.gas_moles),fmt(result.gas_volume_l)+' L',result.collection_method==='over_water'?'排水':'干燥'];
    values.forEach(function(value){var td=document.createElement('td');td.textContent=String(value);row.appendChild(td);});rows.appendChild(row);});
  document.getElementById('btn-reset').addEventListener('click',function(){amounts.forEach(function(x,i){x.value=defaults.amounts[i];});
    progress.value=defaults.progress;temperature.value=defaults.temperature;pressure.value=defaults.pressure;method.value=defaults.method;rows.textContent='';render();});
  window.addEventListener('resize',function(){if(window.__CHEM_GAS_RESULT__)CHEM.gasCollection(canvas,window.__CHEM_GAS_RESULT__);});
  render();
})();'''
    return template.replace("__GAS_CONFIG__", _gas_config_for_js(config))


def render_gas_collection_template(req, config=None):
    """Compose a gas collection page from shared controls/results and the gas solver."""
    config = config or resolve_gas_collection_config(req)
    amount_controls = []
    for index, item in enumerate(config["reactants"]):
        amount_controls.append(render_number_control(
            "反应物 %s 的物质的量" % item["formula"], "gas-amount-%d" % index,
            format(config["initial_amounts_mol"][index], ".12g"), "0", "1000000",
            "data-chem-gas-amount-index", "反应物 %d 物质的量" % (index + 1), "mol",
            marker_value=index))
    method_options = [("over_water", "排水集气"), ("dry", "干燥/排空气集气")]
    controls_html = (
        '<div class="gas-controls">' + "".join(amount_controls)
        + '<label class="exp-field"><span class="exp-label"><span>反应进度</span>'
          '<span class="exp-val"><b id="gas-progress-label">%d%%</b></span></span>'
          '<input id="gas-progress" type="range" min="0" max="1" step="0.01" value="%s" '
          'data-chem-gas-progress aria-label="反应进度"></label>'
        % (round(config["progress"] * 100), format(config["progress"], ".12g"))
        + render_number_control("温度", "gas-temperature", format(config["temperature_c"], ".12g"), "-273.149", "2000",
                                "data-chem-gas-temperature", "温度", "°C")
        + render_number_control("总压强", "gas-pressure", format(config["total_pressure_kpa"], ".12g"), "0.000000001", "100000",
                                "data-chem-gas-pressure", "总压强", "kPa")
        + render_select_control("集气方式", "gas-method", method_options, config["collection_method"],
                                "data-chem-gas-method", "集气方式")
        + "</div>"
        + render_action_buttons([("btn-record", "记录当前数据", True), ("btn-reset", "重置", False)])
    )
    sections = {
        "1": render_subject_tags("化学", req.get("年级") or "高中") + render_learning_goals(
            req.get("学习目标") or ["用物质的量和化学计量关系计算目标气体的量。", "比较排水集气和干燥集气的气体体积修正。"]),
        "2": ('<div class="gas-stage"><canvas id="gas-apparatus" width="880" height="700" data-visual-type="apparatus" '
               'aria-label="气体制取与收集装置图"></canvas><p class="gas-caption">演示区只显示发生器、导气管和集气装置；气泡、液面和活塞状态由求解结果驱动。</p></div>'),
        "3": controls_html,
        "4": ('<div class="exp-reads">' +
               render_result_card("化学方程式", "data-chem-gas-equation") +
               render_result_card("目标气体体积", "data-chem-gas-volume") +
               render_result_card("目标气体物质的量", "data-chem-gas-moles") +
               render_result_card("干燥气体压强", "data-chem-gas-dry-pressure") +
               render_result_card("水蒸气压", "data-chem-gas-vapor-pressure") +
               render_result_card("集气状态", "data-chem-gas-state") +
               render_result_card("限量试剂", "data-chem-gas-limiting") +
               '</div><div class="exp-formula" id="gas-summary"></div><div class="exp-alert" id="gas-alert" hidden></div>'),
        "5": render_record_table(["序号", "反应进度", "气体物质的量（mol）", "气体体积", "集气方式"], "gas-rows"),
        "6": ('<h3>计算方法</h3><p>系统先用反应方程式和物质的量计算目标气体的生成量，再用 PV=nRT 计算体积。排水集气时扣除当前温度下水的饱和蒸气压。</p>'
               '<h3>模型范围</h3><p>本页只计算登记反应、指定目标气体和理想气体体积，不预测反应收率、气体溶解、泄漏、非理想气体行为或副反应。</p>'),
        "css": ('.gas-stage{width:100%;min-width:0;box-sizing:border-box;padding:14px;border:1px solid #d8e7f5;border-radius:14px;'
                'background:linear-gradient(160deg,#fbfdff,#eaf3fb)}.gas-stage canvas{display:block;width:100%;height:clamp(360px,52vw,560px);max-width:100%}'
                '.gas-caption{color:#536b80;font-size:14px;line-height:1.6}.gas-controls{display:grid;gap:14px;min-width:0}'
                '.gas-controls input,.gas-controls select{width:100%;max-width:100%;box-sizing:border-box}.gas-controls input[type=range]{accent-color:#438bd2;margin:8px 0}'
                '.gas-controls select{min-height:42px;padding:8px 12px;border:1px solid #c9d8e6;border-radius:8px;background:#fff;color:#20384d}'
                '.exp-reads{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.exp-read{min-width:0}.exp-read .v{overflow-wrap:anywhere;min-width:0}'
                '@media(max-width:700px){.gas-stage{padding:8px}.gas-stage canvas{height:390px}.exp-reads{grid-template-columns:minmax(0,1fr)}}'),
        "js": _gas_collection_js_template(config),
    }
    return sections


def render_solver_template(req, skeleton, config=None):
    """按场景调度确定性渲染器（调度表在 scene_catalog，本函数只查一次表）。

    历史版本在这里维护了 10 个「按场景 id 分支」的判断，且与 scene_registry、
    generator_agent 各存一份，加场景要改三处。现在统一成 scene_catalog.render_scene：
    「场景 -> (渲染器种类, 模型/模板, UI 元数据)」只有一张表。
    """
    import scene_catalog
    return scene_catalog.render_scene(req, skeleton, config=config)

