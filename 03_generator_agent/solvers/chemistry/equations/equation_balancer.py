# -*- coding: utf-8 -*-
"""Exact chemical equation balancing for known reactants and products.

The solver does not predict reaction products. It parses each supplied formula,
builds an element/charge conservation matrix, and solves its one-dimensional
nullspace with rational arithmetic before reducing coefficients to integers.
"""

from collections import Counter
from fractions import Fraction
from functools import reduce
from math import gcd
import re


ELEMENTS = frozenset((
    "H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br Kr "
    "Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu "
    "Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es Fm Md No Lr Rf Db Sg "
    "Bh Hs Mt Ds Rg Cn Nh Fl Mc Lv Ts Og"
).split())
SUBSCRIPT_DIGITS = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")
MAX_COEFFICIENT = 1_000_000
MAX_FORMULA_LENGTH = 160
MAX_SPECIES = 16


def _positive_integer(raw, label):
    if isinstance(raw, bool):
        raise ValueError(label + "必须是正整数")
    try:
        value = int(raw)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(label + "必须是正整数") from exc
    if str(raw).strip() != str(value) or value <= 0:
        raise ValueError(label + "必须是正整数")
    return value


def _parse_segment(segment, allow_multiplier):
    factor = 1
    if segment and segment[0].isdigit():
        if not allow_multiplier:
            raise ValueError("化学式开头不能带配平系数；水合物分段系数除外")
        match = re.match(r"(\d+)", segment)
        factor = _positive_integer(match.group(1), "水合物分段系数")
        segment = segment[match.end():]
    if not segment:
        raise ValueError("化学式中存在空分段")

    pairs = {"(": ")", "[": "]"}

    def sequence(index, expected=None):
        counts = Counter()
        while index < len(segment):
            char = segment[index]
            if char in ")]":
                if expected != char:
                    raise ValueError("化学式括号不匹配")
                return counts, index + 1
            if char in pairs:
                nested, index = sequence(index + 1, pairs[char])
                if not nested:
                    raise ValueError("化学式不能包含空括号")
                start = index
                while index < len(segment) and segment[index].isdigit():
                    index += 1
                multiplier = int(segment[start:index]) if index > start else 1
                if multiplier <= 0:
                    raise ValueError("括号后的原子个数必须大于 0")
                for element, amount in nested.items():
                    counts[element] += amount * multiplier
                continue
            if char.isupper():
                start = index
                index += 1
                while index < len(segment) and segment[index].islower():
                    index += 1
                element = segment[start:index]
                if element not in ELEMENTS:
                    raise ValueError("未知元素符号：" + element)
                start = index
                while index < len(segment) and segment[index].isdigit():
                    index += 1
                amount = int(segment[start:index]) if index > start else 1
                if amount <= 0:
                    raise ValueError("原子个数必须大于 0")
                counts[element] += amount
                continue
            if char in ")]":
                raise ValueError("化学式括号不匹配")
            raise ValueError("化学式包含无法识别的字符：" + char)
        if expected:
            raise ValueError("化学式括号未闭合")
        return counts, index

    parsed, end = sequence(0)
    if end != len(segment) or not parsed:
        raise ValueError("无法解析化学式")
    return Counter({element: amount * factor for element, amount in parsed.items()})


def parse_formula(formula):
    """Parse a neutral formula; hydrate components use middle dot, e.g. CuSO4·5H2O."""
    if not isinstance(formula, str):
        raise ValueError("化学式必须是字符串")
    text = formula.translate(SUBSCRIPT_DIGITS).replace(" ", "")
    if not text or len(text) > MAX_FORMULA_LENGTH:
        raise ValueError("化学式不能为空且长度不能超过 %d 个字符" % MAX_FORMULA_LENGTH)
    parts = re.split(r"[·.]", text)
    if any(not part for part in parts):
        raise ValueError("化学式中存在空水合物分段")
    total = Counter()
    for index, part in enumerate(parts):
        total.update(_parse_segment(part, allow_multiplier=index > 0))
    if any(value > 1_000_000 for value in total.values()):
        raise ValueError("单种元素的原子数过大")
    return dict(sorted(total.items()))


def _species(raw, side, index):
    if isinstance(raw, str):
        formula, charge, phase = raw, 0, ""
    elif isinstance(raw, dict):
        formula = raw.get("formula") or raw.get("化学式")
        charge = raw.get("charge", raw.get("电荷", 0))
        phase = str(raw.get("phase", raw.get("状态", "")))
    else:
        raise ValueError("%s第 %d 个物质必须是化学式字符串或对象" % (side, index + 1))
    if not isinstance(formula, str) or not formula.strip():
        raise ValueError("%s第 %d 个物质缺少 formula 化学式" % (side, index + 1))
    if isinstance(charge, bool) or not isinstance(charge, int):
        raise ValueError("%s第 %d 个物质的 charge 必须是整数" % (side, index + 1))
    if abs(charge) > 100:
        raise ValueError("离子电荷绝对值不能超过 100")
    return {"formula": formula.strip(), "phase": phase, "charge": charge,
            "atoms": parse_formula(formula.strip())}


def _lcm(a, b):
    return abs(a * b) // gcd(a, b) if a and b else 0


def _nullspace_one_vector(matrix):
    """Return rank and the unique nullspace basis vector, all as Fractions."""
    rows = [[Fraction(value) for value in row] for row in matrix]
    columns = len(rows[0]) if rows else 0
    pivot_columns = []
    pivot_row = 0
    for column in range(columns):
        candidate = next((r for r in range(pivot_row, len(rows)) if rows[r][column]), None)
        if candidate is None:
            continue
        rows[pivot_row], rows[candidate] = rows[candidate], rows[pivot_row]
        pivot = rows[pivot_row][column]
        rows[pivot_row] = [value / pivot for value in rows[pivot_row]]
        for r in range(len(rows)):
            if r == pivot_row or not rows[r][column]:
                continue
            scale = rows[r][column]
            rows[r] = [a - scale * b for a, b in zip(rows[r], rows[pivot_row])]
        pivot_columns.append(column)
        pivot_row += 1
        if pivot_row == len(rows):
            break

    free_columns = [column for column in range(columns) if column not in pivot_columns]
    if len(free_columns) != 1:
        raise ValueError("方程式%s：当前物质组合有 %d 个自由度，无法得到唯一配平结果" %
                         ("没有非零配平解" if not free_columns else "存在多组配平解", len(free_columns)))
    free = free_columns[0]
    vector = [Fraction(0) for _ in range(columns)]
    vector[free] = Fraction(1)
    for row_index, pivot_column in enumerate(pivot_columns):
        vector[pivot_column] = -rows[row_index][free]
    return len(pivot_columns), vector


def _integer_coefficients(vector):
    denominator = reduce(_lcm, (value.denominator for value in vector), 1)
    values = [int(value * denominator) for value in vector]
    if all(value < 0 for value in values):
        values = [-value for value in values]
    if any(value <= 0 for value in values):
        raise ValueError("给定反应物和生成物无法形成所有系数均为正数的方程式")
    common = reduce(gcd, values)
    values = [value // common for value in values]
    if any(value > MAX_COEFFICIENT for value in values):
        raise ValueError("最简系数超过安全上限 %d，暂不支持该方程式" % MAX_COEFFICIENT)
    return values


def _totals(species, coefficients):
    atoms = Counter()
    charge = 0
    for item, coefficient in zip(species, coefficients):
        for element, amount in item["atoms"].items():
            atoms[element] += amount * coefficient
        charge += item["charge"] * coefficient
    return dict(sorted(atoms.items())), charge


def _display_species(species, coefficients):
    rendered = []
    for item, coefficient in zip(species, coefficients):
        name = item["formula"]
        if item["phase"]:
            name += "(" + item["phase"] + ")"
        rendered.append((str(coefficient) if coefficient != 1 else "") + name)
    return " + ".join(rendered)


def balance_equation(request):
    """Balance supplied reactant/product formulas using exact atom/charge conservation."""
    if not isinstance(request, dict):
        raise ValueError("配平方程式请求必须是对象")
    reactants_raw = request.get("reactants", request.get("反应物"))
    products_raw = request.get("products", request.get("生成物"))
    if not isinstance(reactants_raw, list) or not isinstance(products_raw, list) or not reactants_raw or not products_raw:
        raise ValueError("反应物和生成物两侧都必须至少包含一个物质")
    if len(reactants_raw) + len(products_raw) > MAX_SPECIES:
        raise ValueError("物质种类总数不能超过 %d" % MAX_SPECIES)

    reactants = [_species(item, "反应物", i) for i, item in enumerate(reactants_raw)]
    products = [_species(item, "生成物", i) for i, item in enumerate(products_raw)]
    all_species = reactants + products
    elements = sorted({element for item in all_species for element in item["atoms"]})
    has_charge = any(item["charge"] for item in all_species)
    rows = []
    for element in elements:
        rows.append([item["atoms"].get(element, 0) * (1 if i < len(reactants) else -1)
                     for i, item in enumerate(all_species)])
    if has_charge:
        rows.append([item["charge"] * (1 if i < len(reactants) else -1)
                     for i, item in enumerate(all_species)])

    rank, vector = _nullspace_one_vector(rows)
    coefficients = _integer_coefficients(vector)
    left_coeffs = coefficients[:len(reactants)]
    right_coeffs = coefficients[len(reactants):]
    left_atoms, left_charge = _totals(reactants, left_coeffs)
    right_atoms, right_charge = _totals(products, right_coeffs)
    atom_ok = left_atoms == right_atoms
    charge_ok = left_charge == right_charge
    checks = {
        "positive_integer_coefficients": all(isinstance(value, int) and value > 0 for value in coefficients),
        "primitive_coefficients": reduce(gcd, coefficients) == 1,
        "atoms_balanced": atom_ok,
        "charge_balanced": charge_ok,
        "ok": atom_ok and charge_ok,
    }
    return {
        "schema": "chem-equation-balance.v1",
        "reactants": reactants,
        "products": products,
        "coefficients": {"reactants": left_coeffs, "products": right_coeffs},
        "equation": _display_species(reactants, left_coeffs) + " → " + _display_species(products, right_coeffs),
        "atom_counts": {"left": left_atoms, "right": right_atoms},
        "charge_counts": {"left": left_charge, "right": right_charge},
        "elements": elements,
        "rank": rank,
        "nullity": len(all_species) - rank,
        "checks": checks,
    }


def check_coefficients(request, coefficients):
    """Check learner-supplied positive integer coefficients without revealing a solution."""
    if not isinstance(request, dict):
        raise ValueError("配平方程式请求必须是对象")
    reactants_raw = request.get("reactants", request.get("反应物"))
    products_raw = request.get("products", request.get("生成物"))
    if not isinstance(reactants_raw, list) or not isinstance(products_raw, list) or not reactants_raw or not products_raw:
        raise ValueError("反应物和生成物两侧都必须至少包含一个物质")
    if not isinstance(coefficients, dict):
        raise ValueError("系数必须按 reactants/products 两侧提供")
    left = coefficients.get("reactants")
    right = coefficients.get("products")
    if not isinstance(left, list) or not isinstance(right, list) or len(left) != len(reactants_raw) or len(right) != len(products_raw):
        raise ValueError("系数数量必须与方程式两侧物质数量一致")
    values = [_positive_integer(value, "系数") for value in left + right]
    if any(value > MAX_COEFFICIENT for value in values):
        raise ValueError("系数超过安全上限 %d" % MAX_COEFFICIENT)
    reactants = [_species(item, "反应物", i) for i, item in enumerate(reactants_raw)]
    products = [_species(item, "生成物", i) for i, item in enumerate(products_raw)]
    left_atoms, left_charge = _totals(reactants, values[:len(left)])
    right_atoms, right_charge = _totals(products, values[len(left):])
    atom_ok, charge_ok = left_atoms == right_atoms, left_charge == right_charge
    return {"balanced": atom_ok and charge_ok, "atoms_balanced": atom_ok,
            "charge_balanced": charge_ok, "atom_counts": {"left": left_atoms, "right": right_atoms},
            "charge_counts": {"left": left_charge, "right": right_charge},
            "primitive": reduce(gcd, values) == 1}
