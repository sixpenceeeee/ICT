# -*- coding: utf-8 -*-
"""③ 参数与操作：控件组 + 预设条 + 动作按钮。

控件的三条硬约束（都从这里保证，不靠提示词）：
1. 每个控件带 `data-solver-input="<字段名>"`，与求解器请求字段一一对应；
2. 数值控件是 `type=number step=any`（可精细输入），不是只给滑块；
3. 显示单位与求解器 SI 单位不同时，用 `scale` 换算，请求里永远是 SI。
"""

from . import atoms


def display_value(item):
    """把 spec 里的 SI 值换算成控件上的显示值（单位由 UI 元数据声明）。"""
    value = item["value"]
    scale = item.get("scale", 1.0) or 1.0
    if item.get("kind") == "select" or scale == 1:
        return value
    return value / scale


def display_bound(item, key):
    bound = item.get(key)
    scale = item.get("scale", 1.0) or 1.0
    if bound is None or item.get("kind") == "select" or scale == 1:
        return bound
    return bound / scale


def fmt_number(value):
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = ("%.6g" % value) if isinstance(value, float) else str(value)
    return text


def render_controls(spec):
    html = []
    markers = []
    for item in spec.get("inputs") or []:
        name = item["name"]
        if item.get("kind") == "select":
            options = [(key, text) for key, text in item.get("options") or []]
            html.append(atoms.render_select_control(
                item["label"], name, options, str(item["value"]),
                "data-solver-input", item["label"], marker_value=name))
        else:
            shown = display_value(item)
            html.append(atoms.render_number_control(
                item["label"], name, fmt_number(shown),
                fmt_number(display_bound(item, "minimum")),
                fmt_number(display_bound(item, "maximum")),
                "data-solver-input", item["label"], item.get("unit", ""),
                marker_value=name))
        markers.append(("data-solver-input", name))
    return "".join(html), markers


def render_presets(spec):
    """预设条：每个预设 = 一组完整输入，是变形测试的对照组。"""
    if "presets" not in (spec.get("components") or []):
        return "", {}
    buttons, preset_map = [], {}
    for preset in spec.get("presets") or []:
        buttons.append((preset["id"], preset["label"], False))
        preset_map[preset["id"]] = preset["values"]
    if not buttons:
        return "", {}
    return atoms.render_action_buttons(buttons), preset_map


def render_actions(spec):
    """③区按钮：预设 + 记录 + CSV + 复位 + 对照。"""
    components = spec.get("components") or []
    buttons = []
    preset_html, preset_map = render_presets(spec)
    if "comparison" in components:
        buttons.append(("set-baseline", "保存当前状态作对照", False))
    if "records" in components:
        buttons.append(("btn-record", "记录当前数据", True))
    if "csv" in components:
        buttons.append(("btn-export", "导出 CSV", False))
    buttons.append(("btn-reset", "重置参数", False))
    return preset_html + atoms.render_action_buttons(buttons), preset_map


def markers(spec):
    return [("data-solver-input", item["name"]) for item in spec.get("inputs") or []]
