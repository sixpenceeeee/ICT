"""Compose registered math solver pages from shared controls and teaching components."""

import html
import json

from mathematics.lesson_models import SOLVERS
from mathematics.quadratic_solver import solve_quadratic
from math_page_plan import ENUMS, number_bounds, resolve_inputs, sampling_panels, select_components
from page_components import (render_action_buttons, render_learning_goals, render_number_control,
                             render_record_table, render_result_card, render_subject_tags)


QUADRATIC = {
    "api": "solveQuadratic", "prefix": "MATH_QUADRATIC", "title": "二次函数",
    "visual": "graph", "draw": "MATH.funcPlot", "assumptions": "使用 y=ax²+bx+c，a 非零。",
    "layout": "观察开口、顶点、对称轴与横轴交点的关系。",
    "inputs": {"a": "二次项系数", "b": "一次项系数", "c": "常数项"},
    "fields": {"vertex_x": "顶点横坐标", "vertex_y": "顶点纵坐标", "axis_x": "对称轴横坐标",
               "discriminant": "判别式", "roots": "实根", "y_intercept": "纵截距", "opening": "开口方向"},
    "cases": {"two": {"a": 1, "b": -2, "c": 0}, "one": {"a": 1, "b": -2, "c": 1},
              "none": {"a": -1, "b": 0, "c": -2}},
}

CASE_LABELS = {
    "unique": "相交", "swapped": "交换两条直线", "parallel": "平行", "coincident": "重合",
    "horizontal": "水平线", "base": "基准", "double": "放大", "swap": "交换",
    "equal": "相等", "replacement": "放回抽样", "zero": "零值情形",
    "no_step": "没有台阶", "full_step": "整宽台阶", "two": "两个实根",
    "one": "一个实根", "none": "无实根",
}

PROBES = {
    "linearSystem": ("消去 y 后得到 (k₁−k₂)x=b₂−b₁。", "只改第二条直线的斜率，再改截距，解的个数怎样变化？"),
    "rightTriangle": ("面积等于两条直角边乘积的一半；三角比按角 A 区分对边和邻边。", "同时放大两条直角边，哪些量变了，哪些量保持？"),
    "sampling": ("放回时每次抽取条件相同；不放回时，剩余球数会影响下一次概率。", "切换放回方式，比较恰好命中与期望命中次数。"),
    "orthographic": ("主视图用宽和高，左视图用深和高，俯视图用宽和深。", "把五个尺寸加倍，再把台阶高改为 0，比较投影和体积。"),
    "quadratic": ("判别式 Δ=b²−4ac 决定实根个数。", "保持 a、b，改变 c，观察抛物线怎样从两交点变为相切或无交。"),
    "descriptiveStats": ("均值表示数据的中心，方差描述偏离中心的程度。",
                         "把每个数加上同一个常数，再尝试把每个数加倍。哪次操作会改变方差？"),
    "sequences": ("等差数列按固定差递推，等比数列按固定倍数递推。", "改变项数，比较两类数列的末项与前若干项之和。"),
    "reciprocal": ("同一条反比例曲线上 x 和 y 的乘积恒定。", "先把 x 加倍，再改变 k 的符号，观察取样点和象限。"),
    "sinusoid": ("振幅由纵向伸缩决定，角频率决定一个周期的长度。", "分别加倍振幅与角频率，哪次会使周期缩短？"),
    "expLog": ("同底的指数函数和对数函数互为反函数。", "把底数换成它的倒数，对比两条曲线的增减性。"),
    "functionTransform": ("函数图像可平移、纵向伸缩或翻转。", "只改变水平平移量，跟踪顶点的两个坐标。"),
    "derivative": ("导数给出切线的斜率。", "保持切点横坐标不变，把整条曲线上移，比较切线斜率。"),
    "similarTriangles": ("周长按相似比变化，面积按相似比的平方变化。", "把相似比加倍，比较两组周长和面积。"),
    "circle": ("过圆心且垂直于弦的直线平分弦。", "保持半径不变，把弦移向圆心，观察弦长和同弧圆周角。"),
    "polygonArea": ("割补和等积变形保持面积。", "交换上下底后，面积是否变化？上底变成零时是什么形状？"),
    "constructions": ("垂直平分线来自到两个端点等距的点，角平分线来自对称的辅助构造。",
                      "改变线段长度和角的大小，分别验证中点和半角。"),
    "ellipse": ("椭圆上点到两个焦点的距离和等于长轴长。", "把两个半轴同时加倍，比较半焦距与离心率。"),
    "binomial": ("二项分布描述独立重复试验的成功次数。", "把成功概率换成失败概率，并把目标次数换成其补数，比较概率。"),
    "regression": ("带截距的拟合直线通过样本中心。", "把所有观测的纵坐标增加同一个值，比较斜率与截距。"),
    "dotProduct": ("数量积等于对应分量乘积之和。", "交换两个向量，再把其中一个变成零向量，比较数量积和夹角。"),
    "fractions": ("通分保持各分数的值，并使分母一致。", "用等值分数替换原输入，观察约分后的结果是否改变。"),
    "amgm": ("两个非负数的几何平均至多等于算术平均。", "交换两个数，再令它们相等，观察差值何时为零。"),
    "sphereContact": ("内含球的半径由最短边决定，外接球的半径由体对角线决定。",
                      "只加长最长边，比较两个球半径与切面数。"),
    "surfacePath": ("表面路径可沿棱展开后比较平面直线距离。", "交换长宽高的顺序，观察最短长度与候选路线。"),
    "cavalieri": ("对应高度处的平行截面等积时，两立体等体积。", "只剪切斜棱柱顶部，观察截面和体积是否保持。"),
    "travel": ("两物体的位置随时间线性变化，交点表示相遇。", "固定两者速度并加倍间距，再试同速，比较相遇时间。"),
}


def render_choice(name, label, values, initial, labels):
    options = "".join(
        f'<option value="{html.escape(value)}"{" selected" if value == initial else ""}>'
        f'{html.escape(labels.get(value, value))}</option>' for value in values)
    return (f'<label class="exp-field"><span>{html.escape(label)}</span>'
            f'<select data-solver-input="{name}">{options}</select></label>')


def render_math_model(req, key, model, defaults=None, default_components=()):
    solver_name = model["api"]
    solve = model.get("reference") or (solve_quadratic if key == "quadratic" else SOLVERS[solver_name])
    initial = resolve_inputs(req, key, model, solve, defaults)
    components = select_components(req, default_components)
    cases = model["cases"]
    inputs = []
    for name, label in model["inputs"].items():
        samples = [case[name] for case in cases.values()]
        value = initial[name]
        if isinstance(value, str):
            inputs.append(render_choice(name, label.split("，select")[0], sorted(set(samples)), value,
                                        {**ENUMS, **model.get("choice_labels", {})}))
        else:
            lo, hi = number_bounds(value, samples)
            if name in model.get("positive", ()):
                lo = min(0.01, value, *samples)
            if name in model.get("ranges", {}):
                lo, hi = model["ranges"][name]
            if key == "linearSystem":
                lo, hi = number_bounds(value, [*samples, initial[name[0] + ("1" if name[1] == "2" else "2")]])
            inputs.append(render_number_control(label, name, value, lo, hi, "data-solver-input",
                                                label, marker_value=name))
    buttons = [("btn-reset", "重置参数", False)]
    presets = {}
    if "presets" in components:
        for index, (case, values) in enumerate(cases.items()):
            button = f"math-preset-{index}"
            buttons.append((button, CASE_LABELS.get(case, f"对照案例 {index + 1}"), False))
            presets[button] = values
    if "records" in components:
        buttons.append(("btn-record", "记录当前数据", True))
    if "csv" in components:
        buttons.append(("math-csv", "导出 CSV", False))
    fields = model["fields"]
    cards = "".join(render_result_card(label, "data-solver-field", marker_value=name)
                    for name, label in fields.items())
    headers = ["结果", "初始值", "当前值"] if "comparison" in components else ["结果", "当前值"]
    table = render_record_table(headers, "math-current")
    if "records" in components:
        table += "<h3>实验记录</h3>" + render_record_table(("操作参数", *fields.values()), "math-records")
    principle, question = PROBES.get(key, (model["assumptions"], "改变一个参数，比较图示与读数的变化。"))
    teaching = ("<h3>原理</h3><p>" + html.escape(principle) + "</p><h3>易错点</h3><p>" +
                html.escape(model["assumptions"]) + "</p>")
    if "observations" in components:
        teaching += "<h3>探究问题</h3><p>" + html.escape(question) + "</p>"
    else:
        teaching += "<h3>探究问题</h3><p>选择一个参数，预测读数怎样变化，再操作验证。</p>"
    prefix = model["prefix"]
    config = {"key": key, "initial": initial, "presets": presets, "fields": fields,
              "requestKey": f"__{prefix}_REQUEST__", "resultKey": f"__{prefix}_RESULT__",
              "comparison": "comparison" in components, "derivation": "derivation" in components}
    graph = f'<canvas id="math-graph" data-visual-type="{model["visual"]}" aria-label="{html.escape(model["title"])}"></canvas>'
    if "comparison_graph" in components:
        graph = ('<div class="math-compare"><div><p>当前图形</p>' + graph +
                 '</div><div><p>初始图形</p><canvas id="math-baseline-graph" aria-label="初始图形"></canvas></div></div>'
                 '<p class="exp-note">两幅图各自适配显示范围，数值比较请看读数。</p>')
    script_config = json.dumps(config, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c")
    request_js = model.get("request_js", "cfg")
    draw_config = model.get("draw_config", "cfg")
    draw_setup = ""
    if key == "sampling":
        panels = sampling_panels(req)
        draw_setup = f"const sampling = {{...cfg, panels: {json.dumps(panels)}}};"
        draw_config = "sampling"
    draw_api = model["draw"]
    if "." not in draw_api:
        draw_api = "MATHPAGE." + draw_api
    solve_js = model.get("solve_js", f"MATH.{solver_name}(request)")
    js = f"""MATHPAGE.mount({script_config}, {{
        request(cfg) {{ return ({request_js}); }},
        solve(request) {{ const result = {solve_js}; return result; }},
        publish(cfg, result) {{ window.__DATA__ = {{params: cfg, result}}; }},
        draw(cv, cfg, request, result) {{
            VIS.bindSolverReadouts(result);
            {draw_setup}
            {draw_api}(cv, {draw_config}, result);
        }},
    }});"""
    return {
        "1": render_subject_tags("数学", req.get("年级") or "中学") +
             '<p>实验性质：数学教学演示。来源：ICT 数学知识库。</p>' +
             render_learning_goals(req.get("学习目标") or [model["layout"]]),
        "2": graph + f'<p class="exp-note">{html.escape(model["layout"])}</p>',
        "3": "".join(inputs) + render_action_buttons(buttons) + '<p id="math-action" class="exp-note" aria-live="polite"></p>',
        "4": f'<div class="exp-reads">{cards}</div><div class="exp-formula" id="math-formula"></div>'
             '<p class="exp-note" id="math-derivation" hidden></p><p data-solver-error class="exp-alert" hidden></p>',
        "5": table,
        "6": teaching,
        "css": (".exp-grid > *, .exp-table-wrap{min-width:0;max-width:100%}"
                ".exp-field input,.exp-field select{box-sizing:border-box;min-width:0;max-width:100%}"
                ".exp-read .v,.exp-info,.exp-note{overflow-wrap:anywhere}"
                ".exp-table td{white-space:normal;overflow-wrap:anywhere}"
                "#math-graph,#math-baseline-graph{display:block;width:100%;height:100%}"
                ".math-compare{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}"
                ".math-compare canvas{height:auto!important;aspect-ratio:16/11}"
                "@media(max-width:720px){.math-compare{grid-template-columns:minmax(0,1fr)}}"),
        "js": js,
    }, sorted(components)
