# -*- coding: utf-8 -*-
"""组件层的最小组件（原子）。

这里只放"不含学科知识、只负责把一段数据变成平台合规 HTML"的函数。
上面的分子组件（controls / readouts / records / stage / teaching）只能调用本模块，
不允许自己再手写 data-* 标记或 HTML 模板——标记来源唯一，审查器的期望才能自动生成。

历史兼容：`03_generator_agent/page_components.py` 仍然按原样导出这些函数，
所以旧渲染器（math_page_templates / physics_page_templates / solver_templates）
不需要任何改动就能用到新的原子实现。
"""

import html
import re


def _data_marker(name, value):
    if not re.fullmatch(r"data-[a-z][a-z0-9-]*", name):
        raise ValueError(f"Invalid data attribute: {name}")
    return name if value is None else f'{name}="{html.escape(str(value))}"'


def escape(value):
    return html.escape(str(value))


def raw(value):
    """显式声明"这段是受控 HTML"，避免调用方到处写 html.escape 的反面。"""
    return str(value)


# --------------------------------------------------------------------------- ①


def render_subject_tags(subject, grade, kind="教学演示（虚拟仿真）"):
    return (
        '<div class="exp-tags"><span class="exp-tag">%s</span>'
        '<span class="exp-tag">%s</span><span class="exp-tag is-plain">%s</span></div>'
        % tuple(html.escape(str(value)) for value in (subject, grade, kind))
    )


def render_learning_goals(goals):
    if isinstance(goals, str):
        goals = [goals]
    items = [str(goal).strip() for goal in goals or [] if str(goal).strip()]
    if not items:
        items = ["观察参数变化与求解结果之间的关系。"]
    return ('<div class="exp-goals-title">学习目标</div><ul class="exp-goals">%s</ul>' %
            "".join("<li>%s</li>" % html.escape(item) for item in items))


def render_note(text, *, klass="exp-note", element="p", element_id=None):
    if not (text or "").strip():
        return ""
    id_attr = ' id="%s"' % html.escape(str(element_id)) if element_id else ""
    return '<%s class="%s"%s>%s</%s>' % (element, klass, id_attr, html.escape(str(text)), element)


# --------------------------------------------------------------------------- ③


def render_number_control(label, input_id, value, minimum, maximum, marker, aria_label, unit="", *, marker_value=None):
    label, aria_label = map(html.escape, (str(label), str(aria_label)))
    marker = _data_marker(marker, marker_value)
    value = html.escape(str(value))
    minimum, maximum = html.escape(str(minimum)), html.escape(str(maximum))
    unit_html = (" " + html.escape(unit)) if unit else ""
    return (
        '<label class="exp-field"><span class="exp-label"><span>%s</span>'
        '<span class="exp-val"><b id="%s-label">%s</b>%s</span></span>'
        '<input id="%s" type="number" min="%s" max="%s" step="any" value="%s" '
        '%s aria-label="%s"></label>'
        % (label, input_id, value, unit_html, input_id, minimum, maximum, value, marker, aria_label)
    )


def render_select_control(label, select_id, options, selected, marker, aria_label, *, marker_value=None):
    label, aria_label = map(html.escape, (str(label), str(aria_label)))
    marker = _data_marker(marker, marker_value)
    option_html = []
    for value, text in options:
        value, text = html.escape(str(value)), html.escape(str(text))
        selected_attr = " selected" if str(value) == str(selected) else ""
        option_html.append('<option value="%s"%s>%s</option>' % (value, selected_attr, text))
    return (
        '<label class="exp-field"><span class="exp-label"><span>%s</span></span>'
        '<select id="%s" %s aria-label="%s">%s</select></label>'
        % (label, html.escape(str(select_id)), marker, aria_label, "".join(option_html))
    )


def render_range_number_control(label, input_id, value, minimum, maximum,
                                range_marker, number_marker, aria_label, unit="", *, range_value=None):
    label, aria_label = map(html.escape, (str(label), str(aria_label)))
    value = html.escape(str(value))
    range_value = html.escape(str(value if range_value is None else range_value))
    minimum, maximum = html.escape(str(minimum)), html.escape(str(maximum))
    range_marker, number_marker = _data_marker(range_marker, None), _data_marker(number_marker, None)
    unit_html = (" " + html.escape(unit)) if unit else ""
    return (
        '<label class="exp-field"><span class="exp-label"><span>%s</span>'
        '<span class="exp-val"><b id="%s-label">%s</b>%s</span></span>'
        '<input id="%s-range" type="range" min="%s" max="%s" step="any" value="%s" '
        '%s aria-label="拖动调节%s">'
        '<input id="%s" type="number" min="%s" max="1000000" step="any" value="%s" '
        '%s aria-label="输入%s"></label>'
        % (label, input_id, value, unit_html, input_id, minimum, maximum, range_value,
           range_marker, aria_label, input_id, minimum, value, number_marker, aria_label)
    )


def render_slider_number_control(label, input_id, value, maximum, index, aria_label, unit="mol/L"):
    label, aria_label = map(html.escape, (str(label), str(aria_label)))
    value, maximum = html.escape(str(value)), html.escape(str(maximum))
    unit_html = (" " + html.escape(unit)) if unit else ""
    return (
        '<label class="exp-field"><span class="exp-label"><span>%s</span>'
        '<span class="exp-val"><b id="%s-label">%s</b>%s</span></span>'
        '<input id="%s-slider" type="range" min="0" max="%s" step="any" value="%s" '
        'data-chem-ksp-ion-slider-index="%d" aria-label="拖动调节%s">'
        '<input id="%s" type="number" min="0" max="%s" step="any" value="%s" '
        'data-chem-ksp-ion-index="%d" aria-label="输入%s">'
        '</label>'
        % (label, input_id, value, unit_html, input_id, maximum, value, index, aria_label,
           input_id, maximum, value, index, aria_label)
    )


# --------------------------------------------------------------------------- ④


def render_result_card(label, marker, initial="—", *, marker_value=None):
    label, initial = map(html.escape, (str(label), str(initial)))
    marker = _data_marker(marker, marker_value)
    return ('<div class="exp-read"><span class="k">%s</span>'
            '<span class="v"><b %s>%s</b></span></div>' % (label, marker, initial))


def render_formula_block(element_id, *, present=True):
    """代入式容器：J1 只认 `.exp-formula` 里的文本，所以元素与类名都不能改。"""
    return ('<p class="exp-formula" id="%s">%s</p>'
            % (html.escape(str(element_id)), "—" if not present else ""))


def render_error_slot(extra=""):
    return ('<p class="exp-alert" data-solver-error hidden>%s</p>' % html.escape(str(extra)))


def render_action_buttons(buttons):
    rendered = []
    for index, (button_id, label, primary) in enumerate(buttons):
        css = "exp-btn is-primary" if primary else "exp-btn"
        rendered.append('<button class="%s" id="%s" type="button">%s</button>' %
                        (css, html.escape(str(button_id)), html.escape(str(label))))
    return '<div class="exp-btns">%s</div>' % "".join(rendered)


def render_comparison_panel(component_id, title, left_label, right_label,
                            left_value_id, right_value_id):
    """可选对照组件：基线值 / 当前值。"""
    values = (component_id, title, left_label, right_label, left_value_id, right_value_id)
    component_id, title, left_label, right_label, left_value_id, right_value_id = [
        html.escape(str(value)) for value in values]
    return (
        '<section class="exp-comparison" id="%s" data-page-component="comparison">'
        '<h3>%s</h3><div class="exp-comparison-grid">'
        '<div class="exp-read"><span class="k">%s</span><span class="v"><b id="%s">—</b></span></div>'
        '<div class="exp-read"><span class="k">%s</span><span class="v"><b id="%s">—</b></span></div>'
        '</div></section>'
        % (component_id, title, left_label, left_value_id, right_label, right_value_id)
    )


# --------------------------------------------------------------------------- ⑤


def render_record_table(headers, body_id):
    th = "".join("<th>%s</th>" % html.escape(str(label)) for label in headers)
    return ('<div class="exp-table-wrap"><table class="exp-table"><thead><tr>%s</tr></thead>'
            '<tbody id="%s"></tbody></table></div>' % (th, html.escape(str(body_id))))


# --------------------------------------------------------------------------- ②


def render_stage_canvas(canvas_id, visual_type, aria_label):
    """②区只放画布；标题由外壳提供，图例放在画布下方而不是画进画布。"""
    return ('<canvas id="%s" data-visual-type="%s" aria-label="%s"></canvas>'
            % (html.escape(str(canvas_id)), html.escape(str(visual_type)), html.escape(str(aria_label))))


def render_legend(legend, *, klass="exp-note"):
    """图例：每项自带颜色，色觉差异由文字标签兜住（不靠颜色单独区分）。

    行内 style 是故意的：normal.css 里 `.pf-hosted .exp-wrap .exp-note` 选择器
    权重高于组件侧的 `.lesson-key`，会把图例压成一行没有间隔的连写文字
    （"物体砝码水"）。行内样式权重最高，保证 flex + 间隙生效。
    """
    items = [item for item in (legend or []) if str(item.get("label", "")).strip()]
    if not items:
        return ""
    spans = []
    for item in items:
        color = item.get("color")
        style = ' style="color:%s"' % html.escape(str(color)) if color else ""
        spans.append("<span%s>%s</span>" % (style, html.escape(str(item["label"]))))
    return ('<p class="%s" style="display:flex;justify-content:center;'
            'flex-wrap:wrap;gap:0 .9em">%s</p>' % (html.escape(klass), "".join(spans)))


# --------------------------------------------------------------------------- ⑥


def render_teaching_section(blocks):
    """blocks: [(标题, 正文)] -> ⑥区。空正文整块跳过。"""
    parts = []
    for title, body in blocks or []:
        body = str(body or "").strip()
        if not body:
            continue
        parts.append("<h3>%s</h3><p>%s</p>" % (html.escape(str(title)), html.escape(body)))
    return "".join(parts)
