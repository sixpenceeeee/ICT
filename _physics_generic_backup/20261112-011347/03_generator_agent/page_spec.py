# -*- coding: utf-8 -*-
"""page_spec —— 页面生成的唯一结构化输入（PageSpec）。

为什么要有它
------------
以前"一个页面需要什么"分散在四个地方：scene_registry 里的自然语言契约、
generator_agent 里的硬校验、checks_browser.js 里的探针、渲染器里的字符串拼接。
加一个场景要同时改六处，任何一处漏改都会变成"页面能生成但审查判死"。

现在改成：**一切以 PageSpec 为准**。

    PageSpec = 学科求解器 + 控件清单 + 读数清单 + 组件开关 + 教学文案 + 取证契约

渲染器只做 "PageSpec → 六区 HTML"，标记（data-solver-input / data-solver-field …）
由 spec 推导，不再由人手写；因此渲染端、校验端、审查端对同一份 spec 的期望必然一致。

数据来源优先级
--------------
1. lesson_models.json（求解器参考实现 + 输入输出语义 + 预设 + 变形关系）
2. 场景 UI 元数据（scene_catalog.UI）—— 单位、范围、下拉选项、图例、文案
3. 需求 JSON（年级、学习目标、初始参数覆盖）
"""

import json
import math

SCHEMA_VERSION = 1

# 可选组件的合法取值（与 math_page_plan.COMPONENTS 保持一致）
COMPONENT_IDS = ("presets", "comparison", "comparison_graph", "records", "csv",
                 "observations", "derivation")

# 求解器命名空间白名单：页面里必须出现 `<NAMESPACE>.<fn>(` 这种可核验的字面调用
NAMESPACES = ("MATH", "PHYS", "CHEM", "CHEMSOLVER", "CIRCUIT", "VIS")

#: lesson_models.json 里只写函数名，命名空间由学科决定
NAMESPACE_BY_SUBJECT = {"物理": "PHYS", "数学": "MATH", "化学": "CHEMSOLVER", "化学结构": "CHEM"}

DEFAULT_RUNTIME = "lesson"


class SpecError(ValueError):
    """PageSpec 不合法：生成阶段应当直接拒绝出页，而不是产出半成品。"""


def normalize_api(api, subject=None, ui=None):
    """`solveBuoyancy` + 学科 -> `PHYS.solveBuoyancy`（已带命名空间的保持不变）。"""
    text = str(api or "").strip()
    if "." in text:
        return text
    namespace = (ui or {}).get("namespace") or NAMESPACE_BY_SUBJECT.get(str(subject or ""))
    if not namespace:
        raise SpecError("无法判断求解器 %r 的命名空间（请在 UI 元数据里声明 namespace）" % api)
    return "%s.%s" % (namespace, text)


# --------------------------------------------------------------------------- 构造


def split_api(api):
    """`PHYS.solveBuoyancy` -> ('PHYS', 'solveBuoyancy')。"""
    text = str(api or "").strip()
    if text.count(".") != 1:
        raise SpecError("求解器 API 必须写成 命名空间.函数名，收到 %r" % api)
    namespace, function = text.split(".")
    if namespace not in NAMESPACES:
        raise SpecError("未登记的求解器命名空间 %r（允许：%s）"
                        % (namespace, "、".join(NAMESPACES)))
    if not function.isidentifier():
        raise SpecError("求解器函数名不合法：%r" % function)
    return namespace, function


def keys_for(prefix):
    """统一推导浏览器取证用的全局变量名。"""
    prefix = str(prefix or "").strip()
    if not prefix.isidentifier():
        raise SpecError("求解器前缀不合法：%r" % prefix)
    return "__%s_REQUEST__" % prefix, "__%s_RESULT__" % prefix


def number_input(name, label, value, *, unit="", minimum=None, maximum=None,
                 step="any", scale=1.0, kind="number", note=""):
    item = {"name": name, "label": label, "kind": kind, "value": value, "unit": unit,
            "scale": scale, "step": step, "note": note}
    if kind == "select":
        item.setdefault("options", [])
    else:
        item["minimum"] = minimum if minimum is not None else 0
        item["maximum"] = maximum if maximum is not None else 1e6
    return item


def select_input(name, label, value, options):
    item = number_input(name, label, value, kind="select")
    item["options"] = [[str(key), str(text)] for key, text in options]
    return item


def output(name, label, *, unit=""):
    return {"field": name, "label": label, "unit": unit}


def lesson_spec(scene_id, model, subject, *, grade="初中", title=None, ui=None,
                req=None, components=(), initial=None):
    """由 lesson_models.json 的模型 + UI 元数据装配一个 lesson 运行时 PageSpec。"""
    ui = ui or {}
    req = req or {}
    api = normalize_api(model["api"], subject, ui)
    namespace, function = split_api(api)
    prefix = model["prefix"]
    request_key, result_key = keys_for(prefix)

    inputs = []
    for name, meaning in (model.get("inputs") or {}).items():
        meta = (ui.get("inputs") or {}).get(name)
        if not meta:
            raise SpecError("场景 %s 的输入 %s 缺少 UI 元数据（标签/单位/范围）" % (scene_id, meaning))
        if meta.get("kind") == "select":
            inputs.append(select_input(name, meta["label"], meta["value"], meta["options"]))
        else:
            inputs.append(number_input(
                name, meta["label"], meta["value"], unit=meta.get("unit", ""),
                minimum=meta.get("minimum"), maximum=meta.get("maximum"),
                scale=meta.get("scale", 1.0), note=meta.get("note", "")))

    outputs = []
    for name, meaning in (model.get("fields") or {}).items():
        meta = (ui.get("outputs") or {}).get(name, {})
        outputs.append(output(name, meta.get("label") or meaning, unit=meta.get("unit", "")))

    presets = []
    labels = ui.get("preset_labels") or {}
    for case, values in (model.get("cases") or {}).items():
        presets.append({"id": "preset-" + case,
                        "label": labels.get(case, case),
                        "values": dict(values)})

    spec = {
        "schema": SCHEMA_VERSION,
        "scene": scene_id,
        "subject": subject,
        "grade": grade,
        "title": title or model.get("title") or scene_id,
        "runtime": DEFAULT_RUNTIME,
        "visual": model.get("visual") or ui.get("visual") or "apparatus",
        "solver": {"api": api, "namespace": namespace, "function": function,
                   "prefix": prefix, "request_key": request_key, "result_key": result_key},
        "draw": {"api": (ui.get("draw") or "PHYS." + function.replace("solve", "draw"))},
        "inputs": inputs,
        "outputs": outputs,
        "presets": presets,
        "components": [name for name in components if name],
        "stage": {"canvas_id": "%s-scene" % (ui.get("canvas_key") or function.replace("solve", "").lower() or scene_id),
                  "aria": ui.get("aria") or (title or model.get("title") or scene_id),
                  "legend": list(ui.get("legend") or []),
                  "note": ui.get("stage_note", "")},
        "formula": {"js": ui.get("formula_js", ""), "note": ui.get("formula_note", "")},
        "records": {"body_id": "%s-records" % (ui.get("record_key") or "lesson"),
                    "headers": list(ui.get("record_headers") or []),
                    "fields": list(ui.get("record_fields") or [])},
        "comparison": {"id": "%s-comparison" % (ui.get("record_key") or "lesson"),
                       "title": "观察前后对照", "left": "对照", "right": "当前"},
        "summary_js": ui.get("summary_js", ""),
        "teaching": dict(ui.get("teaching") or {}),
        "relations": list(model.get("relations") or []),
        "assumptions": model.get("assumptions", ""),
        "lesson_model": model.get("api"),
        "source": ui.get("source", ""),
    }
    if initial:
        spec = apply_initial(spec, initial)
    return spec


def apply_initial(spec, values):
    """把需求里给出的初始值写回 spec（教室演示版/学生探究版都用同一个入口）。"""
    known = {item["name"]: item for item in spec["inputs"]}
    for name, value in (values or {}).items():
        if name not in known:
            raise SpecError("初始参数含有当前求解器未登记的字段：%s" % name)
        item = known[name]
        if item["kind"] == "select":
            allowed = [option[0] for option in item["options"]]
            if str(value) not in allowed:
                raise SpecError("%s 只能取 %s" % (item["label"], "、".join(allowed)))
            item["value"] = str(value)
        else:
            number = float(value)
            if not math.isfinite(number):
                raise SpecError("%s 的初始值必须是有限数字" % item["label"])
            item["value"] = number
    return spec


def with_components(spec, names):
    spec["components"] = [name for name in dict.fromkeys(names) if name]
    return spec


# --------------------------------------------------------------------------- 校验


def validate(spec):
    """返回问题清单（空清单 = 可以交给渲染器）。"""
    problems = []
    if not isinstance(spec, dict):
        return ["PageSpec 必须是 dict"]
    if spec.get("schema") != SCHEMA_VERSION:
        problems.append("PageSpec schema 版本应为 %d" % SCHEMA_VERSION)
    for key in ("scene", "subject", "grade", "title", "runtime", "visual"):
        if not str(spec.get(key) or "").strip():
            problems.append("PageSpec 缺少字段 %s" % key)

    solver = spec.get("solver") or {}
    try:
        namespace, function = split_api(solver.get("api"))
    except SpecError as exc:
        problems.append(str(exc))
        namespace = function = ""
    if namespace and solver.get("namespace") != namespace:
        problems.append("solver.namespace 与 api 不一致")
    if function and solver.get("function") != function:
        problems.append("solver.function 与 api 不一致")
    try:
        request_key, result_key = keys_for(solver.get("prefix"))
    except SpecError as exc:
        problems.append(str(exc))
        request_key = result_key = ""
    if solver.get("request_key") != request_key or solver.get("result_key") != result_key:
        problems.append("solver.request_key/result_key 必须由 prefix 推导")

    draw = (spec.get("draw") or {}).get("api")
    if not draw:
        problems.append("缺少绘图组件：页面不能只给数值不画实验对象")
    else:
        try:
            split_api(draw)
        except SpecError as exc:
            problems.append("draw.api：%s" % exc)

    inputs, outputs = spec.get("inputs") or [], spec.get("outputs") or []
    if not inputs:
        problems.append("PageSpec 至少需要一个可操作控件")
    if not outputs:
        problems.append("PageSpec 至少需要一个可复算读数")
    for item in inputs:
        name = str(item.get("name") or "").strip()
        if not name.isidentifier():
            problems.append("控件名不合法：%r" % name)
        if not str(item.get("label") or "").strip():
            problems.append("控件 %s 缺少中文标签" % name)
        if item.get("kind") == "select":
            if not item.get("options"):
                problems.append("下拉控件 %s 缺少可选项" % name)
        else:
            low, high = item.get("minimum"), item.get("maximum")
            value = item.get("value")
            if not isinstance(low, (int, float)) or not isinstance(high, (int, float)):
                problems.append("数值控件 %s 缺少范围" % name)
            elif low >= high:
                problems.append("数值控件 %s 范围非法（%s–%s）" % (name, low, high))
            elif isinstance(value, (int, float)) and not low <= value <= high:
                problems.append("数值控件 %s 初值 %s 不在 %s–%s 内" % (name, value, low, high))
            scale = item.get("scale", 1.0)
            if not isinstance(scale, (int, float)) or scale <= 0:
                problems.append("数值控件 %s 的 scale 必须是正数" % name)
    for item in outputs:
        if not str(item.get("field") or "").strip():
            problems.append("读数缺少 field")
        if not str(item.get("label") or "").strip():
            problems.append("读数 %s 缺少中文标签" % item.get("field"))

    known = set(COMPONENT_IDS)
    for name in spec.get("components") or []:
        if name not in known:
            problems.append("未登记的组件 %r（允许：%s）" % (name, "、".join(COMPONENT_IDS)))
    if "csv" in (spec.get("components") or []) and "records" not in (spec.get("components") or []):
        problems.append("导出 CSV 必须同时启用记录表")

    if spec.get("runtime") == DEFAULT_RUNTIME:
        if not (spec.get("formula") or {}).get("js"):
            problems.append("lesson 页面必须提供可复算的代入式（formula.js）")
        if not (spec.get("summary_js") or "").strip():
            problems.append("lesson 页面必须提供读数摘要（summary_js）")
        if "records" in (spec.get("components") or []):
            records = spec.get("records") or {}
            if len(records.get("headers") or []) != len(records.get("fields") or []):
                problems.append("记录表表头数与字段数不一致")
            if not records.get("fields"):
                problems.append("记录表缺少字段来源定义")
    try:
        json.dumps(spec, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        problems.append("PageSpec 不能序列化成 JSON（NaN/Inf 或非基本类型）：%s" % exc)
    return problems


def require_valid(spec):
    problems = validate(spec)
    if problems:
        raise SpecError("；".join(problems))
    return spec


# --------------------------------------------------------------------------- 取证契约


def markers(spec):
    """由 spec 推导出页面必须出现的机读标记。

    渲染器、外壳校验、审查器三方共用这一份结果，禁止任何一方再手写标记清单。
    """
    found = [("data-visual-type", spec.get("visual") or "")]
    for item in spec.get("inputs") or []:
        found.append(("data-solver-input", item["name"]))
        if item.get("kind") == "range":
            found.append(("data-solver-range", item["name"]))
    for item in spec.get("outputs") or []:
        found.append(("data-solver-field", item["field"]))
    if "comparison" in (spec.get("components") or []):
        found.append(("data-page-component", "comparison"))
    return found


def runtime_tokens(spec):
    """页面上必须出现的 JS 取证 token（浏览器与审查器按这些抓状态）。"""
    solver = spec.get("solver") or {}
    draw = spec.get("draw") or {}
    tokens = [solver.get("request_key"), solver.get("result_key"),
              "%s(" % solver.get("api"), "%s(" % draw.get("api"),
              "VIS.bindSolverReadouts", "__DATA__"]
    return [token for token in tokens if token]
