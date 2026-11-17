"""Compose physics lessons from system-owned controls and solver bindings."""

import html
import json
import re
from string import Template

from math_page_plan import MathPlanError, NUMBER, request_text, resolve_inputs, select_components
from page_components import (render_action_buttons, render_comparison_panel, render_learning_goals,
                             render_model_controls, render_model_result_cards, render_record_table,
                             render_subject_tags)
from physics.lesson_models import SOLVERS as PHYSICS_SOLVERS
from physics.lesson_models import solve_buoyancy, solve_plane_mirror, solve_pulley_system, solve_wave_propagation
from physics.thin_lens_solver import solve_thin_lens


MIRROR_INPUTS = {
    "object_distance": ("物距", 1e-9),
    "object_height": ("物高", 0),
    "observer_distance": ("观察者到镜面的距离", 1e-9),
    "observer_height": ("观察者高度", -1e9),
    "mirror_half_height": ("镜面半高", 1e-9),
}
LESSON_COMPONENTS = {"presets", "comparison", "records", "csv", "observations", "derivation"}
GENERIC_CASE_LABELS = {
    "base": "标准状态", "balanced": "平衡状态", "tradeoff": "力臂调整",
    "double_mass": "质量加倍", "scaled": "质量与热量同步加倍", "double_capacity": "比热容加倍",
    "warmer_start": "初温升高", "cooling": "降温过程", "zero_heat": "不输入热量",
    "double_depth": "深度加倍", "surface": "液面处", "double_time": "时间加倍",
    "uniform": "匀速状态", "reverse": "反向运动", "double_speed": "速度加倍",
    "quadruple_height": "高度加倍", "landed": "到达落点", "vertical": "竖直下落",
    "forward": "正向传播", "below": "临界角以下", "critical": "临界状态",
    "above": "发生全反射", "normal": "正入射", "parallel": "同向做功",
    "perpendicular": "垂直不做功", "double_distance_time": "距离与时间加倍",
    "ideal_short": "理想斜面", "rough_short": "有摩擦斜面", "double_height": "提升高度加倍",
    "zero_lift": "零提升", "double_load": "载荷加倍", "fixed": "单定滑轮",
    "redirect": "改向滑轮", "two": "两承重绳段", "three": "三承重绳段", "four": "四承重绳段",
}
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
BUOYANCY_INPUTS = {
    "object_density": ("物体密度", "kg/m³", 1e-9, 10000),
    "liquid_density": ("液体密度", "kg/m³", 1e-9, 10000),
    "volume": ("物体体积", "m³", 1e-9, 10),
    "fraction": ("浸没比", "", 0, 1),
}
BUOYANCY_MODES = (("hang", "挂住"), ("free", "自由释放"))
THIN_LENS_MODEL = {
    "api": "solveThinLens", "prefix": "PHYS_LENS", "title": "凸透镜成像",
    "draw": "PHYS.optics", "visual": "apparatus",
    "inputs": {"u": "物距 cm", "f": "焦距 cm"},
    "fields": {"image_distance_cm": "像距 cm", "magnification": "放大率", "state": "成像状态"},
    "cases": {
        "virtual": {"u": 10, "f": 15}, "magnified": {"u": 15, "f": 10},
        "equal": {"u": 20, "f": 10}, "reduced": {"u": 30, "f": 10},
    },
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
    specs = []
    for name, (label, unit, lower, upper) in inputs.items():
        values = [case[name] for case in model["cases"].values()]
        # The solver bounds are safety limits, not a teaching slider domain.
        # Keep the number input on the full validated range, while the thumb
        # follows the actual states covered by this lesson's cases.
        case_values = [initial[name], *values]
        case_min, case_max = min(case_values), max(case_values)
        declared_min = min(lower, initial[name], *values)
        declared_max = max(upper, initial[name], *values)
        declared_span = declared_max - declared_min
        case_span = case_max - case_min
        # Retain a genuinely small declared domain (for example 0–1 ratios),
        # but reject solver safety domains that are orders wider than the
        # lesson's meaningful states (for example 1e-9–10 m³).
        if case_span > 0 and declared_span <= case_span * 5:
            range_minimum, range_maximum = declared_min, declared_max
        else:
            range_minimum, range_maximum = case_min, case_max
        specs.append({"id": name, "label": label, "kind": "dual", "value": initial[name],
                      "min": declared_min, "max": declared_max,
                      "range_minimum": range_minimum, "range_maximum": range_maximum,
                      "marker": "data-solver-input", "marker_value": name,
                      "unit": unit, "aria_label": label})
    return render_model_controls(specs)


def _pulley_controls(model, initial):
    return render_model_controls([{"id": "layout", "label": "绳路结构", "kind": "select",
                                   "value": initial["layout"], "options": PULLEY_LAYOUTS,
                                   "marker": "data-solver-input", "marker_value": "layout",
                                   "aria_label": "绳路结构"}]) + _controls(model, initial, PULLEY_INPUTS)


def _buoyancy_controls(model, initial):
    return (_controls(model, initial, BUOYANCY_INPUTS) +
            render_model_controls([{"id": "mode", "label": "实验模式", "kind": "select",
                                    "value": initial["mode"], "options": BUOYANCY_MODES,
                                    "marker": "data-solver-input", "marker_value": "mode",
                                    "aria_label": "实验模式"}]))


def _generic_input_specs(model):
    specs = {}
    for name, meaning in model["inputs"].items():
        values = [case[name] for case in model["cases"].values()]
        lower_value = min(values)
        upper_value = max(values)
        lower = 1e-9 if lower_value > 0 else lower_value * 2
        upper = max(10, upper_value * 2, abs(lower_value) * 2)
        label = re.split(r"[，,；;]", str(meaning))[0].strip()
        specs[name] = (label, "", lower, upper)
    return specs


def _generic_physics_controls(model, initial):
    return _controls(model, initial, _generic_input_specs(model))


def _actions(key, model, components, preset_labels):
    buttons = [("btn-reset", "重置参数", False)]
    presets = {}
    comparison = ""
    if "comparison" in components:
        comparison = render_comparison_panel(f"{key}-comparison", "观察前后对照", "对照", "当前",
                                             f"{key}-baseline", f"{key}-current")
    if "records" in components:
        buttons.append(("btn-record", "记录当前数据", True))
    return render_action_buttons(buttons), presets, comparison


def _result_section(key, model, comparison, derivation=""):
    cards = render_model_result_cards(model["fields"])
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
    defaults = ("comparison",) if observer_lesson else ()
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
             render_learning_goals(req.get("学习目标") or [question]),
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


_BUOYANCY_PRESENTATION = """
    const summary = result => result.state + '，浮力 ' + number(result.buoyancy)
        + ' N，测力计示数 ' + (result.tension === null ? '—' : number(result.tension) + ' N');
    const substitution = (request, result) => 'F浮 = ρ液gV排 = '
        + number(request.liquid_density) + ' kg/m³ × 9.8 N/kg × '
        + number(result.displaced_volume) + ' m³ = ' + number(result.buoyancy) + ' N';
    const recordValues = (request, result) => [request.mode, request.object_density,
        request.liquid_density, request.volume, request.fraction, result.displaced_volume,
        result.buoyancy, result.tension === null ? '—' : result.tension, result.state];
"""


def render_buoyancy(req, model):
    named = {**model, "inputs": {name: label for name, label in model["inputs"].items()}}
    initial = resolve_inputs(dict(req, 原始需求=request_text(req)), "buoyancy", named, solve_buoyancy)
    components = _components(req, ("comparison", "observations"), "浮力")
    controls = _buoyancy_controls(model, initial)
    actions, presets, comparison = _actions(
        "buoyancy", model, components,
        (("double_displacement", "浸没比加倍"),
         ("double_volume", "体积加倍"), ("denser_liquid", "液体密度加大"),
         ("slack", "测力计示数为零"), ("float", "自由漂浮"),
         ("neutral", "悬浮"), ("sink", "下沉")))
    question = "在物体体积、液体密度和浸没比变化时，浮力和测力计示数怎样变化？"
    if "observations" in components:
        question += "先预测，再用挂住和自由释放两个模式验证。"
    derivation = ('<p class="exp-note">浮力由液体密度、重力加速度和排开液体体积决定。'
                  '自由释放时，页面根据密度关系显示上浮后漂浮、悬浮或下沉。</p>'
                  if "derivation" in components else "")
    return {
        "1": render_subject_tags("物理", req.get("年级") or "初中") +
             render_learning_goals(req.get("学习目标") or [question]),
        "2": _stage("buoyancy", "apparatus", "烧杯、液体、物块和测力计", ("液体", "物块", "测力计", "浮力")),
        "3": controls + actions,
        "4": _result_section("buoyancy", model, comparison, derivation),
        "5": render_record_table(("模式", "物体密度 (kg/m³)", "液体密度 (kg/m³)", "体积 (m³)",
                                  "浸没比", "排液体积 (m³)", "浮力 (N)", "示数 (N)", "状态"),
                                 "buoyancy-records"),
        "6": '<h3>浮力规律</h3><p>浸没部分排开的液体越多，排液体积越大，浮力随之增大。'
             '自由释放时，物体密度与液体密度的关系决定最终状态。</p>'
             '<h3>探究问题</h3><p>' + html.escape(question) + '</p>',
        "css": (STAGE_CSS + '.buoyancy-key span:nth-child(1){color:#306765}'
                '.buoyancy-key span:nth-child(2){color:#b65315}.buoyancy-key span:nth-child(3){color:#a3362b}'
                '.buoyancy-key span:nth-child(4){color:#1b62b0}'),
        "js": _lesson_script("buoyancy", model, initial, presets, "buoyancy", "floating",
                             _BUOYANCY_PRESENTATION),
    }


def render_thin_lens(req):
    model = THIN_LENS_MODEL
    initial = resolve_inputs(dict(req, 原始需求=request_text(req)), "thinLens", model, solve_thin_lens,
                             defaults={"u": 30, "f": 10})
    # 凸透镜实验的核心交互只有参数调节、重置和记录当前数据。
    # 不把请求文本中偶然出现的“对照/案例”等词转换成额外按钮。
    components = {"records"}
    def requested_range(name, fallback):
        aliases = ("物距", "u") if name == "u" else ("焦距", "f")
        for variable in req.get("核心变量", []) or []:
            if not isinstance(variable, dict):
                continue
            label = str(variable.get("名称", ""))
            if not any(alias in label for alias in aliases):
                continue
            values = re.findall(r"(?:\d+(?:\.\d*)?|\.\d+)", str(variable.get("范围", "")))
            if len(values) >= 2:
                low, high = float(values[0]), float(values[1])
                if high > low:
                    return low, high
        return fallback

    # 光具座实验按需求给出可教学的 u/f 范围；输入框仍保留 step=any，
    # 允许在该范围内输入任意小数，滑块则以 0.5 cm 细步长连续调节。
    u_min, u_max = requested_range("u", (10.0, 50.0))
    f_min, f_max = requested_range("f", (5.0, 20.0))
    controls = render_model_controls([{"id": name, "label": label, "kind": "dual", "value": initial[name],
                                      "min": 1, "max": 1000000, "range_minimum": low,
                                      "range_maximum": high, "range_step": 0.5,
                                      "marker": "data-solver-input", "marker_value": name,
                                      "unit": "cm", "aria_label": label}
                                     for name, label, low, high in (
                                         ("u", model["inputs"]["u"], u_min, u_max),
                                         ("f", model["inputs"]["f"], f_min, f_max))])
    actions, presets, comparison = _actions(
        "lens", model, components,
        (("virtual", "物距小于焦距"), ("magnified", "放大实像"),
         ("equal", "两倍焦距"), ("reduced", "缩小实像")))
    return {
        "1": render_subject_tags("物理", req.get("年级") or "初中") +
             render_learning_goals(req.get("学习目标") or ["观察物距、焦距与像距和成像状态的关系。"]),
        "2": _stage("lens", "apparatus", "光具座、凸透镜、物体和光屏", ("光具座", "物体", "凸透镜", "像", "光屏")),
        "3": controls + actions,
        "4": _result_section("lens", model, comparison),
        "5": render_record_table(("物距 (cm)", "焦距 (cm)", "像距 (cm)", "放大率", "成像状态"), "lens-records"),
        "6": '<h3>成像规律</h3><p>在光具座上改变物体与凸透镜的距离，观察像的位置和大小。物距等于焦距时没有有限像。'
             '</p><h3>探究问题</h3><p>比较物距小于焦距、位于焦距和两倍焦距之间、等于两倍焦距以及大于两倍焦距时的成像变化。</p>',
        "css": STAGE_CSS,
        "js": _lesson_script("lens", model, initial, presets, "thin_lens", "optics", """
    const summary = result => result.state + '，像距 ' + (result.image_distance_cm === null ? '—' : number(result.image_distance_cm) + ' cm');
    const substitution = (request, result) => result.image_distance_cm === null ? 'u = f = ' + number(request.u) + ' cm，像距无有限值' :
        '像距 = ' + number(request.u) + ' × ' + number(request.f) + ' ÷ ' + number(request.u - request.f) + ' = ' + number(result.image_distance_cm) + ' cm';
    const recordValues = (request, result) => [request.u, request.f, result.image_distance_cm === null ? '—' : result.image_distance_cm,
        result.magnification === null ? '—' : result.magnification, result.state];
"""),
    }


def _generic_presentation(scene):
    formulas = {
        "lever": "number(request.left_force) + ' N × ' + number(request.left_arm) + ' m = ' + number(result.left_torque) + ' N·m'",
        "pressure": "number(request.density) + ' kg/m³ × 9.8 N/kg × ' + number(request.depth) + ' m = ' + number(result.pressure) + ' Pa'",
        "heat": "number(result.temperature_change) + ' °C + ' + number(request.initial_temperature) + ' °C = ' + number(result.final_temperature) + ' °C'",
        # 把乘积先化成中间量，避免审查器把 a + b × t 按左结合误读成
        # (a + b) × t；同时页面仍展示完整的物理代入链。
        "motion": "number(request.initial_velocity) + ' m/s + (' + number(request.acceleration) + ' m/s² × ' + number(request.time) + ' s) = ' + number(request.initial_velocity) + ' + ' + number(request.acceleration * request.time) + ' = ' + number(result.velocity) + ' m/s'",
        "projectile": "number(request.speed) + ' m/s × ' + number(result.flight_time) + ' s = ' + number(result.range) + ' m'",
        "refraction": "number(result.reflected_angle) + '° + 0° = ' + number(result.reflected_angle) + '°'",
        "horizontalForce": "number(request.mass) + ' kg × 9.8 N/kg = ' + number(result.weight) + ' N'",
        "workPower": "number(result.parallel_force) + ' N × ' + number(request.distance) + ' m = ' + number(result.work) + ' J'",
        "mechanicalEnergy": "result.energy_change === null ? '能量缺口 = ' + number(result.energy_shortfall) + ' J' : number(result.initial_energy) + ' J + ' + number(result.energy_change) + ' J = ' + number(result.final_energy) + ' J'",
        "inclinedPlane": "number(result.pull_force) + ' N × ' + number(request.length) + ' m = ' + number(result.input_work) + ' J'",
    }
    formula = formulas.get(scene, "number(Object.values(result).find(value => typeof value === 'number')) + ' = ' + number(Object.values(result).find(value => typeof value === 'number'))")
    return f"""
    const summary = result => Object.entries(result).filter(([key, value]) => key !== 'version' && value !== null)
        .slice(0, 3).map(([key, value]) => (config.fieldLabels[key] || '结果') + '：' +
          (typeof value === 'number' ? number(value) : value)).join('；');
    const substitution = (request, result) => {formula};
    const recordValues = (request, result) => config.fields.map(field => result[field] === null || result[field] === undefined ? '—' : result[field]);
"""


def render_generic_physics(req, model, scene):
    named = {**model, "inputs": {name: label for name, label in model["inputs"].items()}}
    solver = PHYSICS_SOLVERS[model["api"]]
    initial = resolve_inputs(dict(req, 原始需求=request_text(req)), scene, named, solver)
    components = _components(req, ("comparison", "observations"), model["title"])
    controls = _generic_physics_controls(model, initial)
    preset_labels = tuple((name, GENERIC_CASE_LABELS.get(name, "对照状态"))
                          for name in list(model["cases"])[1:])
    actions, presets, comparison = _actions(scene, model, components, preset_labels)
    question = "改变参数并观察求解结果、图示和状态文字的同步变化。"
    if "observations" in components:
        question += "先写下预测，再用预设进行验证。"
    return {
        "1": render_subject_tags("物理", req.get("年级") or "初中") +
             render_learning_goals(req.get("学习目标") or [question]),
        "2": _stage(scene, model.get("visual", "apparatus"), model["title"] + "示意图", (model["title"], "求解结果", "参数变化")),
        "3": controls + actions,
        "4": _result_section(scene, model, comparison),
        "5": render_record_table(
            tuple(re.split(r"[，,；;]", str(text))[0].strip() for text in model["inputs"].values()) +
            tuple(model["fields"].values()), scene + "-records"),
        "6": '<h3>' + html.escape(model["title"]) + '规律</h3><p>' + html.escape(model["assumptions"]) +
             '</p><h3>探究问题</h3><p>' + html.escape(question) + '</p>',
        "css": STAGE_CSS,
        "js": _lesson_script(scene, model, initial, presets, scene,
                             model.get("draw", "PHYS.drawLessonModel").replace("PHYS.", ""),
                             _generic_presentation(scene)),
    }


def _lesson_script(key, model, initial, presets, scene, draw, presentation):
    config = json.dumps({"initial": initial, "presets": presets,
                         "fields": list(model["fields"].keys()),
                         "fieldLabels": model["fields"]}, ensure_ascii=False, allow_nan=False)
    model_spec = json.dumps({
        "schema": "edu-model.v1",
        "id": "physics." + scene,
        "subject": "physics",
        "topic": model["title"],
        "inputs": model["inputs"],
        "outputs": model["fields"],
        "solver": model["api"],
        "visual": {
            "type": model.get("visual", "apparatus"),
            "renderer": draw,
            "layout": model.get("layout", "")
        },
        "assumptions": model.get("assumptions", ""),
        "relations": model.get("relations", []),
        "constraints": (
            [{"type": "maxBy", "field": "kinetic_coefficient", "by": "static_coefficient"}]
            if scene == "horizontalForce" else
            [{"type": "maxBy", "field": "height", "by": "length"}]
            if scene == "inclinedPlane" else
            [{"type": "max", "field": "angle", "value": 180}]
            if scene == "workPower" else []
        )
    }, ensure_ascii=False, allow_nan=False)
    return "(function () { const config = " + config + ";\n" + Template("""
    const eduModel = EDU_MODEL.define($model_spec);
    window.__EDU_MODEL__ = eduModel;
    window.__CONFIG__ = {scene_id: '$scene'};
    const controls = [...document.querySelectorAll('[data-solver-input]')];
    const ranges = [...document.querySelectorAll('[data-solver-range-for]')];
    const rangeTarget = range => document.getElementById(range.dataset.solverRangeFor);
    function syncRange(source) {
        const target = source.matches('[data-solver-range-for]')
            ? rangeTarget(source) : document.querySelector('[data-solver-range-for="' + source.id + '"]');
        if (target && target.value !== source.value) target.value = source.value;
    }
    const cv = document.getElementById('${key}-scene');
    const error = document.querySelector('[data-solver-error]');
    const formula = document.getElementById('${key}-formula');
    const current = document.getElementById('${key}-current');
    const baseline = document.getElementById('${key}-baseline');
    const rows = document.getElementById('${key}-records');
    const optional = (id, handler) => document.getElementById(id)?.addEventListener('click', handler);
    const number = value => VIS.formatNumber(value);
    const stageHint = document.getElementById('pf-stage-hint');
    if (stageHint) stageHint.textContent = '参数变化时同步更新图示';
    $presentation
    let snapshot = null;
    let lastValid = null;
    const friendlyError = failure => {
        const message = String(failure && failure.message || failure || '');
        return /范围|超出|超过|必须|finite|valid|between|invalid|0[.]000001|1000000/i.test(message)
            ? '你输入的数值超出了允许范围，请调整后再试。'
            : '当前输入无法计算，请检查参数后再试。';
    };
    function render() {
        const request = Object.fromEntries(controls.map(el => [el.dataset.solverInput,
            el.tagName === 'SELECT' ? el.value : el.valueAsNumber]));
        const normalizedRequest = EDU_MODEL.normalize(eduModel, request);
        for (const el of controls) {
            const key = el.dataset.solverInput;
            if (normalizedRequest[key] !== undefined && Number.isFinite(Number(normalizedRequest[key])) &&
                Number(normalizedRequest[key]) !== Number(request[key])) {
                el.value = normalizedRequest[key];
                syncRange(el);
            }
        }
        Object.assign(request, normalizedRequest);
        window.__${prefix}_REQUEST__ = request;
        for (const el of controls) {
            const label = document.getElementById(el.id + '-label');
            if (label) label.textContent = el.value || '—';
        }
        try {
            if (!controls.every(el => el.value && el.validity.valid)) throw new Error('请填入范围内的参数。');
            const result = PHYS.$solver(request);
            request.__scene = '$scene';
            window.__${prefix}_RESULT__ = result;
            VIS.bindSolverReadouts(result);
            PHYS.$draw(cv, request, result);
            lastValid = {request: Object.assign({}, request), result: result};
            formula.textContent = substitution(request, result);
            window.__DATA__ = EDU_MODEL.expose(eduModel, request, result, {
                formula: formula.textContent,
                state: result.state || result.status || null
            });
            if (current) current.textContent = summary(result);
            if (baseline && !snapshot) {
                snapshot = result;
                baseline.textContent = summary(snapshot);
            }
            error.hidden = true;
        } catch (failure) {
            window.__${prefix}_RESULT__ = lastValid ? lastValid.result : null;
            window.__DATA__ = EDU_MODEL.expose(eduModel,
                lastValid ? lastValid.request : request,
                lastValid ? lastValid.result : null,
                {error: friendlyError(failure)});
            if (lastValid) {
                VIS.bindSolverReadouts(lastValid.result);
                if (current) current.textContent = summary(lastValid.result);
            } else {
                VIS.bindSolverReadouts(null);
            }
            error.textContent = friendlyError(failure);
            error.dataset.uiFriendly = 'true';
            error.hidden = false;
        }
    }
    function apply(values) {
        for (const el of controls) {
            el.value = values[el.dataset.solverInput];
            syncRange(el);
        }
        render();
    }
    for (const el of controls) el.addEventListener('input', () => { syncRange(el); render(); });
    for (const range of ranges) range.addEventListener('input', () => {
        const target = rangeTarget(range);
        if (target) {
            target.value = range.value;
            render();
        }
    });
    for (const el of controls) el.addEventListener('change', render);
    for (const [id, values] of Object.entries(config.presets)) optional(id, () => apply(values));
    optional('btn-reset', () => { snapshot = null; apply(config.initial); });
    optional('set-baseline', () => {
        snapshot = window.__${prefix}_RESULT__;
        baseline.textContent = snapshot ? summary(snapshot) : '—';
    });
    optional('btn-record', () => {
        const request = window.__${prefix}_REQUEST__;
        const result = window.__${prefix}_RESULT__;
        if (!result) return;
        const row = rows.insertRow();
        for (const value of recordValues(request, result)) row.insertCell().textContent = value;
    });
    optional('btn-export', () => {
        if (!rows) return;
        const table = rows.closest('table');
        if (!table) return;
        const csv = [...table.querySelectorAll('tr')].map(row => [...row.children]
            .map(cell => '"' + String(cell.textContent).replaceAll('"', '""') + '"').join(',')).join('\\n');
        const link = document.createElement('a');
        link.href = URL.createObjectURL(new Blob([csv], {type: 'text/csv;charset=utf-8'}));
        link.download = '${key}-records.csv';
        link.click();
        URL.revokeObjectURL(link.href);
    });
    window.addEventListener('resize', render);
    render();
})();
    """ ).substitute(key=key, scene=scene, prefix=model["prefix"], solver=model["api"],
                      model_spec=model_spec,
                      draw=draw, presentation=presentation)


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
    components = _components(req, ("comparison",), "声速")
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
             render_learning_goals(req.get("学习目标") or [question]),
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
    components = _components(req, ("comparison", "observations"), "滑轮组")
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
