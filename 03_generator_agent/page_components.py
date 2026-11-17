# -*- coding: utf-8 -*-
"""Small HTML components shared by deterministic lesson-page renderers."""

import html
import math
import re


def _data_marker(name, value):
    if not re.fullmatch(r"data-[a-z][a-z0-9-]*", name):
        raise ValueError(f"Invalid data attribute: {name}")
    return name if value is None else f'{name}="{html.escape(str(value))}"'


def _extra_attrs(attrs):
    """Render additional validated data/aria attributes for model controls."""
    if not attrs:
        return ""
    if not isinstance(attrs, dict):
        raise TypeError("extra_attrs must be a mapping")
    return " " + " ".join(_data_marker(str(name), value) for name, value in attrs.items())


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


def adaptive_range_step(minimum, maximum):
    """Choose a readable slider quantum from the covered range.

    A span of 10 therefore uses step 1, a span of 1 uses 0.1, and so on.
    The number input deliberately remains ``step=any`` so precise decimal
    values can still be entered manually.
    """
    try:
        span = abs(float(maximum) - float(minimum))
    except (TypeError, ValueError):
        span = 0
    if not math.isfinite(span) or span <= 0:
        return "1"
    # 目标是约 10 个可见步长：范围 10→1，范围 1→0.1，范围 0.8→0.1，
    # 范围 0.001→0.0001。这样小范围变量不会因一个像素就跳到末端。
    exponent = math.floor(math.log10(span / 10.0) + 1e-9)
    step = 10 ** exponent
    return format(step, ".12g")


def adaptive_range_minimum(minimum, step, value=None):
    """Keep the slider's lower bound within the number input's valid domain.

    A previous implementation mapped any tiny positive lower bound to zero
    when the adaptive step was larger.  That made a paired slider emit an
    invalid value (for example coefficient 0 while the number input required
    a positive integer), which in turn broke independent chemistry checks.
    The slider may start at a non-grid lower bound; subsequent drag values are
    still quantized by the declared step and clamped by the browser.
    """
    try:
        lower = float(minimum)
    except (TypeError, ValueError):
        return str(minimum)
    return format(lower, ".12g")


def adaptive_range_value(value, minimum, maximum, step):
    """Snap only the range's initial thumb; the paired number input stays exact."""
    try:
        value, lower, upper, quantum = map(float, (value, minimum, maximum, step))
        if not all(math.isfinite(item) for item in (value, lower, upper, quantum)) or quantum <= 0:
            return str(value)
        snapped = lower + round((value - lower) / quantum) * quantum
        snapped = min(max(snapped, lower), upper)
        return format(snapped, ".12g")
    except (TypeError, ValueError):
        return str(value)


def _slider_bounds(value, minimum, maximum, range_minimum=None, range_maximum=None):
    """Return a usable visual slider domain without narrowing number input.

    Solver safety limits are often intentionally very wide (for example
    ``1e-9..10`` m³).  Reusing those limits for a thumb makes one pixel of
    movement jump across the whole teaching range.  Unless a template gives
    explicit ``range_minimum``/``range_maximum``, use a local domain around
    the current value when the declared domain is several orders wider.  The
    paired number input keeps the original full domain and remains the place
    for precise/manual values.
    """
    try:
        current = float(value)
        lower = float(minimum)
        upper = float(maximum)
    except (TypeError, ValueError):
        return minimum, maximum
    if range_minimum is not None:
        lower = range_minimum
    if range_maximum is not None:
        upper = range_maximum
    try:
        lower, upper = float(lower), float(upper)
    except (TypeError, ValueError):
        return minimum, maximum
    if not all(math.isfinite(x) for x in (current, lower, upper)) or upper <= lower:
        return minimum, maximum
    # Explicit bounds always win.  Only infer a local range when the safety
    # domain is clearly disproportionate to the value being explored.
    if range_minimum is None and range_maximum is None:
        span = upper - lower
        scale = max(abs(current), abs(lower), 1e-12)
        if span > 5 * scale:
            if current > 0:
                lower = max(lower, current * 0.5)
                upper = min(upper, current * 2.0)
            elif current < 0:
                lower = max(lower, current * 2.0)
                upper = min(upper, current * 0.5)
            else:
                upper = min(upper, max(1.0, span * 0.1))
    if upper <= lower:
        upper = lower + max(abs(lower), 1.0)
    return lower, upper


def render_number_control(label, input_id, value, minimum, maximum, marker, aria_label, unit="", *, marker_value=None, extra_attrs=None):
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
        % (label, input_id, value, unit_html, input_id, minimum, maximum, value, marker + _extra_attrs(extra_attrs), aria_label)
    )


def render_dual_number_control(label, input_id, value, minimum, maximum, marker,
                               aria_label, unit="", *, marker_value=None, extra_attrs=None,
                               range_minimum=None, range_maximum=None, range_step=None):
    """Render a number input and a synchronized range input side by side.

    The number input remains the canonical solver control and keeps the existing
    ``data-solver-input`` (or chemistry marker).  The range input deliberately
    uses ``data-solver-range-for`` so generic solver code does not read the same
    variable twice; the page runtime synchronizes both controls before render.
    """
    label, aria_label = map(html.escape, (str(label), str(aria_label)))
    marker = _data_marker(marker, marker_value)
    value = html.escape(str(value))
    minimum, maximum = html.escape(str(minimum)), html.escape(str(maximum))
    range_minimum, range_maximum = _slider_bounds(value, minimum, maximum,
                                                  range_minimum, range_maximum)
    range_step = str(range_step) if range_step is not None else adaptive_range_step(
        range_minimum, range_maximum)
    range_minimum = adaptive_range_minimum(range_minimum, range_step, value)
    # 保留初始精确值显示；用户开始拖动后才按 step 吸附。
    range_value = value
    unit_html = (" " + html.escape(unit)) if unit else ""
    return (
        '<label class="exp-field exp-dual-field"><span class="exp-label"><span>%s</span>'
        '<span class="exp-val"><b id="%s-label">%s</b>%s</span></span>'
        '<span class="exp-control-pair">'
        '<input id="%s" type="number" min="%s" max="%s" step="any" value="%s" '
        '%s aria-label="输入%s">'
        '<input id="%s-range" type="range" min="%s" max="%s" step="%s" value="%s" '
        'data-solver-range-for="%s" aria-label="拖动调节%s">'
        '</span></label>'
        % (label, input_id, value, unit_html, input_id, minimum, maximum, value,
           marker + _extra_attrs(extra_attrs), aria_label, input_id, range_minimum, range_maximum, range_step, range_value, input_id, aria_label)
    )


def render_select_control(label, select_id, options, selected, marker, aria_label, *, marker_value=None, extra_attrs=None):
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
        % (label, html.escape(str(select_id)), marker + _extra_attrs(extra_attrs), aria_label, "".join(option_html))
    )


def render_range_number_control(label, input_id, value, minimum, maximum,
                                range_marker, number_marker, aria_label, unit="", *, range_value=None,
                                range_minimum=None, range_maximum=None):
    label, aria_label = map(html.escape, (str(label), str(aria_label)))
    value = html.escape(str(value))
    range_value = html.escape(str(value if range_value is None else range_value))
    minimum, maximum = html.escape(str(minimum)), html.escape(str(maximum))
    range_minimum, range_maximum = _slider_bounds(value, minimum, maximum,
                                                  range_minimum, range_maximum)
    range_step = adaptive_range_step(range_minimum, range_maximum)
    range_minimum = adaptive_range_minimum(range_minimum, range_step, value)
    # 保留初始精确值显示；用户开始拖动后才按 step 吸附。
    range_marker, number_marker = _data_marker(range_marker, None), _data_marker(number_marker, None)
    unit_html = (" " + html.escape(unit)) if unit else ""
    return (
        '<label class="exp-field exp-dual-field"><span class="exp-label"><span>%s</span>'
        '<span class="exp-val"><b id="%s-label">%s</b>%s</span></span>'
        '<span class="exp-control-pair">'
        '<input id="%s" type="number" min="%s" max="%s" step="any" value="%s" '
        '%s aria-label="输入%s">'
        '<input id="%s-range" type="range" min="%s" max="%s" step="%s" value="%s" '
        'data-solver-range-for="%s" %s aria-label="拖动调节%s">'
        '</span></label>'
        % (label, input_id, value, unit_html, input_id, minimum, maximum, value,
           number_marker, aria_label, input_id, range_minimum, maximum, range_step,
           range_value, input_id, range_marker, aria_label)
    )


def render_slider_number_control(label, input_id, value, maximum, index, aria_label, unit="mol/L"):
    label, aria_label = map(html.escape, (str(label), str(aria_label)))
    value, maximum = html.escape(str(value)), html.escape(str(maximum))
    range_step = adaptive_range_step(0, maximum)
    # 保留初始精确值显示；用户开始拖动后才按 step 吸附。
    range_value = value
    unit_html = (" " + html.escape(unit)) if unit else ""
    return (
        '<label class="exp-field exp-dual-field"><span class="exp-label"><span>%s</span>'
        '<span class="exp-val"><b id="%s-label">%s</b>%s</span></span>'
        '<span class="exp-control-pair">'
        '<input id="%s" type="number" min="0" max="%s" step="any" value="%s" '
        'data-chem-ksp-ion-index="%d" aria-label="输入%s">'
        '<input id="%s-slider" type="range" min="0" max="%s" step="%s" value="%s" '
        'data-solver-range-for="%s" data-chem-ksp-ion-slider-index="%d" aria-label="拖动调节%s">'
        '</span></label>'
        % (label, input_id, value, unit_html, input_id, maximum, value, index, aria_label,
           input_id, maximum, range_step, range_value, input_id, index, aria_label)
    )


def render_result_card(label, marker, initial="—", *, marker_value=None):
    label, initial = map(html.escape, (str(label), str(initial)))
    marker = _data_marker(marker, marker_value)
    return ('<div class="exp-read"><span class="k">%s</span>'
            '<span class="v"><b %s>%s</b></span></div>' % (label, marker, initial))


def render_model_result_cards(outputs, default_marker="data-solver-field"):
    """Render result cards from a declarative model output map.

    ``outputs`` accepts either ``{id: label}`` or a list of
    ``{id, label, marker, initial}`` dictionaries.  Keeping this helper in
    the shared component layer lets physics, chemistry and mathematics use
    the same result-card renderer while preserving each solver's data marker.
    """
    if isinstance(outputs, dict):
        items = [{"id": key, "label": value} for key, value in outputs.items()]
    else:
        items = list(outputs or [])
    cards = []
    for item in items:
        item = dict(item)
        marker = item.get("marker", default_marker)
        cards.append(render_result_card(item.get("label", item.get("id", "结果")), marker,
                                        item.get("initial", "—"),
                                        marker_value=item.get("marker_value", item.get("id"))))
    return "".join(cards)


def render_model_controls(specs):
    """Render controls from a declarative input specification list.

    Supported ``kind`` values are ``number``, ``dual``, ``range``, ``range_only``,
    ``slider_number``, ``select`` and ``text``.  The returned HTML deliberately keeps the established
    ``data-solver-*``/discipline-specific markers so existing runtimes and
    browser audits continue to work unchanged.
    """
    controls = []
    for raw in specs or []:
        spec = dict(raw)
        kind = spec.get("kind", "number")
        label = spec.get("label", spec.get("id", "参数"))
        marker = spec.get("marker", "data-solver-input")
        marker_value = spec.get("marker_value")
        extra_attrs = spec.get("extra_attrs")
        aria = spec.get("aria_label", label)
        if kind == "text":
            value = html.escape(str(spec.get("value", "")))
            controls.append(
                '<label class="exp-field"><span class="exp-label"><span>%s</span></span>'
                '<input id="%s" type="text" value="%s" %s aria-label="%s"></label>'
                % (html.escape(str(label)), html.escape(str(spec["id"])), value,
                   _data_marker(marker, marker_value) + _extra_attrs(extra_attrs), html.escape(str(aria))))
            continue
        if kind == "select":
            controls.append(render_select_control(label, spec["id"], spec.get("options", []),
                                                  spec.get("value", ""), marker, aria,
                                                  marker_value=marker_value, extra_attrs=extra_attrs))
            continue
        args = (label, spec["id"], spec.get("value", ""), spec.get("min", 0),
                spec.get("max", 1), marker, aria, spec.get("unit", ""))
        if kind == "dual":
            controls.append(render_dual_number_control(
                *args, marker_value=marker_value, extra_attrs=extra_attrs,
                range_minimum=spec.get("range_minimum"), range_maximum=spec.get("range_maximum"),
                range_step=spec.get("range_step")))
        elif kind == "range_only":
            # 兼容旧场景声明：所有连续数值控件统一升级为“输入 + 滑块”双控件。
            controls.append(render_dual_number_control(
                *args, marker_value=marker_value, extra_attrs=extra_attrs,
                range_minimum=spec.get("range_minimum"), range_maximum=spec.get("range_maximum"),
                range_step=spec.get("range_step")))
        elif kind == "slider_number":
            controls.append(render_slider_number_control(
                label, spec["id"], spec.get("value", ""), spec.get("max", 1),
                spec.get("index", 0), aria, spec.get("unit", "mol/L")))
        elif kind == "range":
            controls.append(render_range_number_control(
                label, spec["id"], spec.get("value", ""), spec.get("min", 0), spec.get("max", 1),
                spec.get("range_marker", marker + "-range"), marker, aria,
                spec.get("unit", ""), range_value=spec.get("range_value"),
                range_minimum=spec.get("range_minimum"), range_maximum=spec.get("range_maximum")))
        else:
            # 未明确声明 kind 的数值变量也必须提供精确输入和拖动调节。
            controls.append(render_dual_number_control(
                *args, marker_value=marker_value, extra_attrs=extra_attrs,
                range_minimum=spec.get("range_minimum"), range_maximum=spec.get("range_maximum"),
                range_step=spec.get("range_step")))
    return "".join(controls)


def render_action_buttons(buttons):
    rendered = []
    for index, (button_id, label, primary) in enumerate(buttons):
        button_id = str(button_id)
        # 预设、对照保存、导出属于实现细节，不作为默认教学操作暴露。
        if (button_id.startswith(("preset-", "math-preset-")) or
                button_id in {"set-baseline", "btn-export", "math-csv"}):
            continue
        css = "exp-btn is-primary" if primary else "exp-btn"
        rendered.append('<button class="%s" id="%s" type="button">%s</button>' %
                        (css, html.escape(button_id), html.escape(str(label))))
    return '<div class="exp-btns">%s</div>' % "".join(rendered)


def render_record_table(headers, body_id):
    th = "".join("<th>%s</th>" % html.escape(str(label)) for label in headers)
    return ('<div class="exp-table-wrap"><table class="exp-table"><thead><tr>%s</tr></thead>'
            '<tbody id="%s"></tbody></table></div>' % (th, html.escape(str(body_id))))


def render_comparison_panel(component_id, title, left_label, right_label,
                            left_value_id, right_value_id):
    """A small optional comparison component for baseline/current results."""
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
