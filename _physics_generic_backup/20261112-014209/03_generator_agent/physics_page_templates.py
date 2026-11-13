"""Compose physics lessons from system-owned controls and solver bindings."""

import html
import json
import re
from string import Template

from math_page_plan import MathPlanError, NUMBER, request_text, resolve_inputs, select_components
from page_components import (render_action_buttons, render_comparison_panel, render_learning_goals,
                             render_number_control, render_record_table, render_result_card,
                             render_select_control, render_subject_tags)
from physics.lesson_models import solve_plane_mirror, solve_pulley_system, solve_wave_propagation


MIRROR_INPUTS = {
    "object_distance": ("物距", 1e-9),
    "object_height": ("物高", 0),
    "observer_distance": ("观察者到镜面的距离", 1e-9),
    "observer_height": ("观察者高度", -1e9),
    "mirror_half_height": ("镜面半高", 1e-9),
}
LESSON_COMPONENTS = {"presets", "comparison", "records", "observations", "derivation"}
WAVE_INPUTS = {
    "frequency": ("声源频率", "Hz", 1e-9, 1000),
    "detector_distance": ("探测距离", "m", 1e-9, 20),
    "travel_time": ("传播耗时", "s", 1e-9, 0.1),
    "observation_time": ("观察时间", "s", 0, 0.1),
}
PULLEY_INPUTS = {
    "load_mass": ("载荷质量", "kg", 1e-9, 1000),
    "moving_mass": ("动滑轮及吊钩质量", "kg", 0, 1000),
    "lift_height": ("提升高度", "m", 0, 100),
    "rope_loss_force": ("绳端附加阻力", "N", 0, 1000),
}
PULLEY_LAYOUTS = (
    ("fixed", "单定滑轮"), ("two_fixed", "两定滑轮改向"),
    ("two_strands", "两承重绳段"), ("three_strands", "三承重绳段"),
    ("four_strands", "四承重绳段"),
)
STAGE_CSS = (
    '.physics-stage{display:grid;grid-template-rows:minmax(0,1fr) auto;height:100%;min-width:0;max-width:100%;overflow:hidden}'
    '.physics-plot{position:relative;min-height:0;min-width:0;max-width:100%;overflow:hidden}.physics-plot canvas{position:absolute;inset:0;max-width:100%}'
    '.physics-key{display:flex;justify-content:center;flex-wrap:wrap;gap:0 0.6em;'
    'margin:0;padding:0.25em 0.6em}'
    '.exp-field input{min-width:0;max-width:100%;box-sizing:border-box}'
    '.exp-table-wrap{width:100%;min-width:0;max-width:100%;overflow-x:auto}'
    '.exp-read{min-width:0}.exp-read .v{min-width:0;overflow-wrap:anywhere}'
)


def _stage(key, visual, aria, legend):
    labels = "".join(f"<span>{html.escape(label)}</span>" for label in legend)
    return ('<div class="physics-stage"><div class="physics-plot">'
            f'<canvas id="{key}-scene" data-visual-type="{visual}" aria-label="{aria}"></canvas></div>'
            f'<p class="exp-note physics-key {key}-key">{labels}</p></div>')


def _components(req, defaults, title):
    components = set(select_components(req, defaults))
    unsupported = components - LESSON_COMPONENTS
    if unsupported:
        raise MathPlanError(f"{title}页面暂未配置这些组件：" + "、".join(sorted(unsupported)))
    return components


def _controls(model, initial, inputs):
    controls = []
    for name, (label, unit, lower, upper) in inputs.items():
        values = [case[name] for case in model["cases"].values()]
        controls.append(render_number_control(label, name, initial[name], min(lower, initial[name], *values),
                                              max(upper, initial[name], *values), "data-solver-input",
                                              label, unit, marker_value=name))
    return "".join(controls)


def _pulley_controls(model, initial):
    controls = [render_select_control("绳路结构", "layout", PULLEY_LAYOUTS, initial["layout"],
                                     "data-solver-input", "绳路结构", marker_value="layout")]
    controls.append(_controls(model, initial, PULLEY_INPUTS))
    return "".join(controls)


def _actions(key, model, components, preset_labels):
    buttons = [("btn-reset", "重置参数", False)]
    presets = {}
    if "presets" in components:
        for case, label in preset_labels:
            button = "preset-" + case
            buttons.append((button, label, False))
            presets[button] = model["cases"][case]
    comparison = ""
    if "comparison" in components:
        buttons.append(("set-baseline", "保存当前状态作对照", False))
        comparison = render_comparison_panel(f"{key}-comparison", "观察前后对照", "对照", "当前",
                                             f"{key}-baseline", f"{key}-current")
    if "records" in components:
        buttons.append(("btn-record", "记录当前数据", True))
        buttons.append(("btn-export", "导出 CSV", False))
    return render_action_buttons(buttons), presets, comparison


def _result_section(key, model, comparison, derivation=""):
    cards = "".join(render_result_card(label, "data-solver-field", marker_value=name)
                    for name, label in model["fields"].items())
    return (f'<div class="exp-reads">{cards}</div><p class="exp-formula" id="{key}-formula"></p>'
            f'{derivation}<p class="exp-alert" data-solver-error hidden></p>{comparison}')


def _normalize_measurements(text, labels, factors):
    names = "|".join(map(re.escape, labels))
    units = "|".join(
        re.escape(unit) + (r"(?![A-Za-z])" if unit.isascii() else "")
        for unit in sorted(factors, key=len, reverse=True))
    return re.sub(
        rf"((?:{names})\s*(?:初始值|初始|默认)?\s*(?:[:=]|为|设为)\s*)({NUMBER})\s*({units})",
        lambda match: match[1] + str(float(match[2]) * factors[match[3].lower()]),
        text, flags=re.I)


def render_plane_mirror(req, model):
    named_inputs = {**model, "inputs": {name: label for name, (label, _) in MIRROR_INPUTS.items()}}
    text = request_text(req)
    meters = {"毫米": 0.001, "mm": 0.001, "厘米": 0.01, "cm": 0.01, "米": 1, "m": 1}
    normalized = _normalize_measurements(text, named_inputs["inputs"].values(), meters)
    initial = resolve_inputs(dict(req, 原始需求=normalized), "planeMirror", named_inputs, solve_plane_mirror)
    observer_lesson = bool(re.search(r"移动(?:眼睛|观察者)|可见范围|中段可见|可见区间", text))
    defaults = ("presets", "records", "comparison") if observer_lesson else ("presets", "records")
    components = _components(req, defaults, "平面镜")
    controls = _controls(model, initial, {name: (label, "m", max(minimum, -10), 10)
                                         for name, (label, minimum) in MIRROR_INPUTS.items()})
    actions, presets, comparison = _actions(
        "mirror", model, components, (("full", "整段可见"), ("middle_only", "仅中段可见"), ("observer_high", "不可见")))
    records = render_record_table(("物距 (m)", "像距 (m)", "眼距 (m)", "眼高 (m)", "可见范围"), "mirror-records")
    question = ("保持物体和镜子的位置，移动眼睛。像的位置和可见区间各有什么变化？"
                if observer_lesson else "只改变物距，记录两组像距。像到镜面的距离与物距有什么关系？")
    if "observations" in components:
        question += "先写下预测，再选一个对照状态验证。"
    derivation = ('<p class="exp-note">把物距乘以 1 得到像距大小。像横坐标带负号，表示像在镜后。</p>'
                  if "derivation" in components else "")
    return {
        "1": render_subject_tags("物理", req.get("年级") or "初中") +
             '<p>来源：物理知识库「平面镜成像」。</p>' + render_learning_goals(req.get("学习目标") or [question]),
        "2": _stage("mirror", "apparatus", "平面镜和反射光路", ("物体", "虚像", "镜面", "观察者")),
        "3": controls + actions,
        "4": _result_section("mirror", model, comparison, derivation),
        "5": records,
        "6": '<h3>成像原理</h3><p>物与像关于镜面对称。反射角与入射角相等。'
             '观察者的位置决定哪些反射光线可以进入眼睛。图中的橙色实线表示实际光线，虚线表示反向延长线。</p>'
             '<h3>探究问题</h3><p>' + html.escape(question) + '</p>',
        "css": (STAGE_CSS +
                '.mirror-key span:nth-child(1){color:#1b62b0}.mirror-key span:nth-child(2){color:#8653a0}'
                '.mirror-key span:nth-child(3){color:#306765}.mirror-key span:nth-child(4){color:#a3362b}'),
        "js": _lesson_script("mirror", model, initial, presets, "plane_mirror", "drawPlaneMirror",
                             _MIRROR_PRESENTATION),
    }


def _lesson_script(key, model, initial, presets, scene, draw, presentation):
    """历史签名薄包装：脚本实现已迁到 components/runtime.py（全站唯一一份）。

    保留函数名是为了让三个早期物理模板零改动继续工作；行为保持不变
    （同一段脚本、同样的 `__PREFIX_REQUEST__/__PREFIX_RESULT__` 取证）。
    """
    from components.runtime import legacy_spec, mount_script
    return mount_script(legacy_spec(key, model, scene, draw), initial=initial,
                        presets=presets, presentation=presentation)


_MIRROR_PRESENTATION = """
    const visible = result => result.visible_from === null ? '不可见'
        : result.visibility + '，' + number(result.visible_from) + ' 至 ' + number(result.visible_to) + ' m';
    const summary = result => '像距 ' + number(result.image_distance) + ' m，' + visible(result);
    const substitution = (request, result) => '像距 = ' + number(result.object_distance)
        + ' m × 1 = ' + number(result.image_distance) + ' m';
    const recordValues = (request, result) => [result.object_distance, result.image_distance,
        request.observer_distance, request.observer_height, visible(result)];
"""


_WAVE_PRESENTATION = """
    const summary = result => '声速 ' + number(result.speed) + ' m/s，波长 '
        + number(result.wavelength) + ' m，' + result.arrival_state;
    const substitution = (request, result) => '声速 = ' + number(request.detector_distance)
        + ' m ÷ ' + number(request.travel_time) + ' s = ' + number(result.speed) + ' m/s';
    const recordValues = (request, result) => [request.frequency, request.observation_time,
        result.speed, result.wavelength, result.arrival_state];
"""


def render_wave_propagation(req, model):
    named = {**model, "inputs": {name: label for name, (label, *_) in WAVE_INPUTS.items()}}
    text = _normalize_measurements(request_text(req), ("传播耗时", "观察时间"),
                                   {"毫秒": 0.001, "ms": 0.001, "秒": 1, "s": 1})
    text = _normalize_measurements(text, ("探测距离",), {"厘米": 0.01, "cm": 0.01, "米": 1, "m": 1})
    text = _normalize_measurements(text, ("声源频率",), {"千赫兹": 1000, "khz": 1000, "赫兹": 1, "hz": 1})
    initial = resolve_inputs(dict(req, 原始需求=text), "wavePropagation", named, solve_wave_propagation)
    components = _components(req, ("presets", "comparison", "records"), "声速")
    controls = _controls(model, initial, WAVE_INPUTS)
    actions, presets, comparison = _actions(
        "wave", model, components,
        (("base", "基准"), ("double_frequency", "频率加倍"), ("before_arrival", "到达前"),
         ("arrival", "刚到达"), ("after_arrival", "到达后")))
    question = "保持探测距离和实测耗时，把频率加倍。波长和首峰到达时间分别怎样变化？"
    if "observations" in components:
        question += "先记录预测，再用基准和频率加倍两个预设验证。"
    derivation = ('<p class="exp-note">测距除以传播耗时得到声速，再用声速除以频率求波长。</p>'
                  if "derivation" in components else "")
    return {
        "1": render_subject_tags("物理", req.get("年级") or "初中") +
             '<p>来源：物理知识库「波的传播与声速」。</p>' + render_learning_goals(req.get("学习目标") or [question]),
        "2": _stage("wave", "graph", "声源、波前和探测器的位置图", ("声源", "波前", "探测器")),
        "3": controls + actions,
        "4": _result_section("wave", model, comparison, derivation),
        "5": render_record_table(("频率 (Hz)", "观察时间 (s)", "声速 (m/s)", "波长 (m)", "到达状态"), "wave-records"),
        "6": '<h3>传播规律</h3><p>在均匀介质中，声速由实测传播距离和耗时确定。改变声源频率时，波长随之变化。</p>'
             '<h3>探究问题</h3><p>' + html.escape(question) + '</p>',
        "css": (STAGE_CSS + '.wave-key span:nth-child(1){color:#1b62b0}'
                '.wave-key span:nth-child(2){color:#b65315}.wave-key span:nth-child(3){color:#306765}'),
        "js": _lesson_script("wave", model, initial, presets, "wave_propagation", "drawWavePropagation",
                             _WAVE_PRESENTATION),
    }


_PULLEY_PRESENTATION = """
    const summary = result => '承重绳段 ' + number(result.supporting_strands)
        + '，拉力 ' + number(result.pull_force) + ' N，自由端行程 '
        + number(result.pull_distance) + ' m，机械效率 '
        + (result.efficiency === null ? '—' : number(result.efficiency) + '%');
    const substitution = (request, result) => '输入功 = ' + number(result.pull_force)
        + ' N × ' + number(result.pull_distance) + ' m = ' + number(result.input_work) + ' J';
    const recordValues = (request, result) => [request.layout, result.supporting_strands,
        request.load_mass, request.moving_mass, request.lift_height, result.pull_distance,
        result.pull_force, result.input_work, result.efficiency === null ? '—' : result.efficiency];
"""


def render_pulley_system(req, model):
    named = {**model, "inputs": {name: label for name, label in model["inputs"].items()}}
    initial = resolve_inputs(dict(req, 原始需求=request_text(req)), "pulleySystem", named,
                            solve_pulley_system)
    components = _components(req, ("presets", "comparison", "records", "observations"), "滑轮组")
    controls = _pulley_controls(model, initial)
    actions, presets, comparison = _actions(
        "pulley", model, components,
        (("redirect", "两定滑轮改向"), ("two", "两承重段"),
         ("three", "三承重段"), ("four", "四承重段"), ("carrier", "带动滑轮质量"),
         ("drag_two", "带绳端阻力"), ("drag_four", "四段带阻力"),
         ("double_height", "提升高度加倍"), ("zero_lift", "零提升"),
         ("double_load", "载荷加倍")))
    question = "比较不同承重绳段数时，拉力和自由端行程怎样变化？"
    if "observations" in components:
        question += "先预测承重段数加倍后的变化，再用预设验证。"
    derivation = ('<p class="exp-note">匀速提升时，承重绳段分摊载荷和移动组件的重力；'
                  '自由端行程由绳长约束确定，绳端阻力的耗能单列。</p>'
                  if "derivation" in components else "")
    return {
        "1": render_subject_tags("物理", req.get("年级") or "初中") +
             '<p>来源：物理知识库「滑轮组」。</p>' +
             render_learning_goals(req.get("学习目标") or [question]),
        "2": _stage("pulley", "apparatus", "滑轮组绳路、载荷和自由端", ("绳路", "定滑轮", "动滑轮", "载荷")),
        "3": controls + actions,
        "4": _result_section("pulley", model, comparison, derivation),
        "5": render_record_table(("绳路", "承重段数", "载荷质量 (kg)", "组件质量 (kg)",
                                  "提升高度 (m)", "自由端行程 (m)", "拉力 (N)",
                                  "输入功 (J)", "效率 (%)"), "pulley-records"),
        "6": '<h3>滑轮组规律</h3><p>理想情况下，承重绳段越多，匀速提升所需的拉力越小，'
             '自由端移动距离越长。页面将载荷有用功、移动组件功和绳端阻力耗能分开显示。</p>'
             '<h3>探究问题</h3><p>' + html.escape(question) + '</p>',
        "css": (STAGE_CSS + '.pulley-key span:nth-child(1){color:#1b62b0}'
                '.pulley-key span:nth-child(2){color:#306765}.pulley-key span:nth-child(3){color:#b65315}'
                '.pulley-key span:nth-child(4){color:#a3362b}'),
        "js": _lesson_script("pulley", model, initial, presets, "pulley_system", "drawPulleySystem",
                             _PULLEY_PRESENTATION),
    }
