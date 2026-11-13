# -*- coding: utf-8 -*-
"""④ 结果与反馈：读数卡 + 代入式 + 错误态 + 对照面板。

读数卡只放"值与单位"，标签写在卡外——审查器按 `data-solver-field` 取到的
必须是可 parseFloat 的纯数值，混进单位会让 J1/J7 全部误判。
"""

from . import atoms


def render_readouts(spec):
    cards = []
    markers = []
    for item in spec.get("outputs") or []:
        label = item["label"]
        unit = item.get("unit") or ""
        text = ("%s（%s）" % (label, unit)) if unit else label
        cards.append(atoms.render_result_card(text, "data-solver-field",
                                              marker_value=item["field"]))
        markers.append(("data-solver-field", item["field"]))
    return '<div class="exp-reads">%s</div>' % "".join(cards), markers


def render_formula(key, note=""):
    html = atoms.render_formula_block(key)
    if note:
        html += atoms.render_note(note)
    return html


def render_teaching_note(spec):
    return atoms.render_note((spec.get("formula") or {}).get("note", ""))


def render_error():
    return atoms.render_error_slot()


def render_comparison(spec):
    if "comparison" not in (spec.get("components") or []):
        return "", []
    panel = spec.get("comparison") or {}
    key = panel.get("id", "lesson-comparison")
    html = atoms.render_comparison_panel(
        key, panel.get("title", "观察前后对照"),
        panel.get("left", "对照"), panel.get("right", "当前"),
        "%s-baseline" % key.rsplit("-comparison", 1)[0],
        "%s-current" % key.rsplit("-comparison", 1)[0])
    return html, [("data-page-component", "comparison")]


def markers(spec):
    values = [("data-solver-field", item["field"]) for item in spec.get("outputs") or []]
    if "comparison" in (spec.get("components") or []):
        values.append(("data-page-component", "comparison"))
    return values
