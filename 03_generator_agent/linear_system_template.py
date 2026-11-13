# -*- coding: utf-8 -*-
"""Parameterized classroom page for two lines in slope-intercept form."""

import re

from math_page_plan import MathPlanError
from math_page_templates import render_math_model
from scene_registry import MATH_MODELS


DEFAULTS = {"k1": 2, "b1": 1, "k2": -1, "b2": 4}
NUMBER = r"(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?"
LINE = re.compile(
    rf"\by\s*=\s*(?:(?P<k>[+-]?\s*(?:{NUMBER})?)\s*\*?\s*x"
    rf"(?:\s*(?P<sign>[+-])\s*(?P<b>{NUMBER}))?|(?P<constant>[+-]?{NUMBER}))"
    rf"(?!\s*[0-9.a-z+*/^−-])", re.I)


def initial_coefficients(request):
    """Use explicitly requested lines or coefficients before classroom defaults."""
    explicit = request.get("初始参数")
    if isinstance(explicit, dict) and explicit.keys() >= DEFAULTS.keys():
        return {name: explicit[name] for name in DEFAULTS}
    interactions = request.get("交互要求") or []
    if isinstance(interactions, str):
        interactions = [interactions]
    for text in (request.get("原始需求", ""), request.get("实验主题", ""), *interactions):
        text = str(text).translate(str.maketrans("−＝", "-="))
        equations = list(LINE.finditer(text))
        if len(equations) >= 2:
            result = {}
            for index, match in enumerate(equations[:2], 1):
                if match["constant"] is not None:
                    result[f"k{index}"] = 0
                    result[f"b{index}"] = float(match["constant"])
                    continue
                slope = re.sub(r"\s+", "", match["k"])
                slope = {"": "1", "+": "1", "-": "-1"}.get(slope, slope)
                result[f"k{index}"] = float(slope)
                result[f"b{index}"] = float((match["sign"] or "+") + (match["b"] or "0"))
            return result
        values = {name: re.search(rf"\b{name}\s*=\s*([+-]?{NUMBER})", text, re.I)
                  for name in DEFAULTS}
        if all(values.values()):
            return {name: float(match[1]) for name, match in values.items()}
    return DEFAULTS.copy()


def render_linear_system_template(request):
    # Explicit equations outside the supported syntax need request-specific generation.
    raw = str(request.get("原始需求") or "")
    normalized = raw.translate(str.maketrans("−＝", "-="))
    text = raw + " " + str(request.get("实验主题") or "")
    lines = list(LINE.finditer(normalized))
    if len(lines) < 2 and not re.search(r"二元一次方程组|两[条个]直线|两[条个]一次函数", text):
        return None
    if "竖直直线" in raw:
        raise MathPlanError("当前直线求解器使用斜截式，竖直直线需要一般式求解器。")
    if re.search(r"\by\s*=", normalized, re.I) and len(lines) != 2:
        raise MathPlanError("当前页面需要两条可识别的斜截式直线，请提供两条方程或四个系数。")
    initial = initial_coefficients(request)
    return render_math_model(request, "linearSystem", MATH_MODELS["linearSystem"], initial,
                             default_components=("presets", "records", "csv", "observations"))[0]
