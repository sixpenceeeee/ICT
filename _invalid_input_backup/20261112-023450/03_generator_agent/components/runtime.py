# -*- coding: utf-8 -*-
"""components.runtime —— 页面运行时的唯一实现（lesson 版）。

一段通用脚本负责所有 lesson 类页面的生命周期：

    读控件 → 组请求 → 调求解器 → 发布 __PREFIX_REQUEST__/__PREFIX_RESULT__
    → VIS.bindSolverReadouts(同一结果) → 调绘图组件 → 写代入式 → 记录 → CSV → 复位 → 错误态

以前这段脚本在 `physics_page_templates._lesson_script` 里，只服务物理 3 个场景，
而且硬编码了 `PHYS.` 命名空间。现在抽到组件层并参数化：

* `namespace`：PHYS / MATH / CHEM —— 求解器与绘图都从同一命名空间取
* `scales`：控件显示单位与求解器 SI 单位不同时（cm³ ↔ m³）由这里换算，
  请求对象始终是 SI，代入式与记录表因此不会混单位
* `presentation`：summary / substitution / record_values 三段文案由 PageSpec 注入，
  不再每个场景手写一份脚本

`physics_page_templates._lesson_script` 保留同名薄包装，输出逐字节不变，
所以已有页面不受影响。
"""

import json
from string import Template

_BODY = Template("""
    window.__CONFIG__ = {scene_id: '$scene'};
    const scales = ${scales};
    window.__SOLVER_SCALES__ = scales;
    const formatters = ${formatters};
    const round12 = value => Number(value.toPrecision(12));
    const controls = [...document.querySelectorAll('[data-solver-input]')];
    const cv = document.getElementById('$canvas');
    const error = document.querySelector('[data-solver-error]');
    const formula = document.getElementById('$formula');
    const current = document.getElementById('$current');
    const baseline = document.getElementById('$baseline');
    const rows = document.getElementById('$rows');
    const optional = (id, handler) => document.getElementById(id)?.addEventListener('click', handler);
    const presetHint = document.querySelector('[data-preset-hint]');
    const number = value => {
      const x = Number(value);
      if (!Number.isFinite(x)) return String(value);
      if (x === 0) return '0';
      const abs = Math.abs(x);
      if (abs < 1e-4) {
        let text = x.toFixed(8);
        while (text.endsWith('0')) text = text.slice(0, -1);
        if (text.endsWith('.')) text = text.slice(0, -1);
        return text;
      }
      return String(Number(x.toPrecision(6)));
    };
    const toRequest = (name, value) => scales[name] ? round12(value * scales[name]) : value;
    const toDisplay = (name, value) => round12(value / (scales[name] || 1));
    $presentation
    let snapshot = null;
    function readRequest() {
        return Object.fromEntries(controls.map(el => [el.dataset.solverInput,
            el.tagName === 'SELECT' ? el.value : toRequest(el.dataset.solverInput, el.valueAsNumber)]));
    }
    function render() {
        const request = readRequest();
        window.__${prefix}_REQUEST__ = request;
        for (const el of controls) {
            const label = document.getElementById(el.id + '-label');
            if (label) label.textContent = el.value || '—';
        }
        try {
            if (!controls.every(el => el.value && el.validity.valid)) throw new Error('请填入范围内的参数。');
            const result = $namespace.$solver(request);
            window.__${prefix}_RESULT__ = result;
            window.__DATA__ = {params: request, result};
            VIS.bindSolverReadouts(result, document, formatters);
            ${draw_call}(cv, request, result);
            formula.textContent = substitution(request, result);
            if (current) current.textContent = summary(result);
            if (baseline && !snapshot) {
                snapshot = result;
                baseline.textContent = summary(snapshot);
            }
            error.hidden = true;
        } catch (failure) {
            window.__${prefix}_RESULT__ = null;
            window.__DATA__ = {params: request};
            VIS.bindSolverReadouts(null);
            cv.getContext('2d').clearRect(0, 0, cv.width, cv.height);
            formula.textContent = '';
            if (current) current.textContent = '—';
            error.textContent = failure.message;
            error.hidden = false;
        }
    }
    function apply(values) {
        for (const el of controls) {
            const name = el.dataset.solverInput;
            el.value = el.tagName === 'SELECT' ? values[name] : toDisplay(name, values[name]);
        }
        render();
    }
    for (const el of controls) el.addEventListener('input', render);
    for (const el of controls) el.addEventListener('change', render);
    for (const [id, values] of Object.entries(config.presets)) optional(id, event => {
        apply(values);
        if (presetHint) {
            const label = ((event && event.currentTarget && event.currentTarget.textContent) || '').trim();
            presetHint.textContent = label ? '已应用预设：' + label : '已应用预设';
        }
    });
    optional('btn-reset', () => {
        snapshot = null;
        if (rows) rows.replaceChildren();
        apply(config.initial);
        if (presetHint) presetHint.textContent = '';
    });
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
        link.download = '$scene-records.csv';
        link.click();
        URL.revokeObjectURL(link.href);
    });
    window.addEventListener('resize', render);
    render();
""")


def presentation_js(spec):
    """由 PageSpec 生成 summary / substitution / recordValues 三段脚本。

    三段都是"纯文案生成"，不参与计算：数值一律来自同一份 result，
    所以 J1 复算、记录表与读数卡不会互相打架。
    """
    summary = (spec.get("summary_js")
               or _default_summary(spec))
    formula = (spec.get("formula") or {}).get("js") or "''"
    records = _default_record_values(spec)
    return "\n".join((
        "    const summary = result => %s;" % summary,
        "    const substitution = (request, result) => %s;" % formula,
        "    const recordValues = (request, result) => [%s];" % records,
    ))


def _unit_join(parts):
    text = "".join(parts)
    return text


def _default_summary(spec):
    """默认摘要：'读数A 值 单位，读数B 值 单位'。"""
    pieces = []
    for index, item in enumerate(spec.get("outputs") or []):
        value = "result.%s" % item["field"]
        unit = item.get("unit") or ""
        label = item["label"]
        separator = "，" if index else ""
        if unit:
            pieces.append("'%s%s ' + number(%s) + ' %s'" % (separator, label, value, unit))
        else:
            pieces.append("'%s%s ' + number(%s)" % (separator, label, value))
    return " + ".join(pieces) if pieces else "''"


def _default_record_values(spec):
    records = spec.get("records") or {}
    fields = records.get("fields") or []
    if fields:
        values = []
        for item in fields:
            if isinstance(item, str):
                values.append(item)
                continue
            expr = item.get("js") or ""
            values.append(expr)
        return ", ".join(values)
    values = ["request.%s" % item["name"] for item in spec.get("inputs") or []]
    values += ["result.%s" % item["field"] for item in spec.get("outputs") or []]
    return ", ".join(values)


def mount_script(spec, *, initial=None, presets=None, presentation=None):
    """生成页面脚本。spec 是完整 PageSpec；initial/presets 缺省取 spec 内的声明。"""
    solver = spec["solver"]
    draw = spec["draw"]
    inputs = spec.get("inputs") or []
    scales = {item["name"]: item.get("scale", 1.0) for item in inputs
              if item.get("kind") != "select" and item.get("scale", 1.0) != 1.0}
    initial = initial if initial is not None else {
        item["name"]: item["value"] for item in inputs}
    if presets is None:
        presets = {preset["id"]: preset["values"] for preset in spec.get("presets") or []}
    config = json.dumps({"initial": initial, "presets": presets},
                        ensure_ascii=False, allow_nan=False)
    return ("(function () { const config = " + config + ";\n" + _BODY.substitute(
        scene=spec.get("scene", ""),
        namespace=solver["namespace"],
        prefix=solver["prefix"],
        solver=solver["function"],
        draw=draw["api"].split(".", 1)[1],
        draw_call=draw["api"],
        canvas=spec["stage"]["canvas_id"],
        formula="%s-formula" % _key(spec),
        current="%s-current" % _key(spec),
        baseline="%s-baseline" % _key(spec),
        rows=spec["records"]["body_id"],
        presentation=presentation if presentation is not None else presentation_js(spec),
        scales=json.dumps(scales, ensure_ascii=False, allow_nan=False),
        formatters=json.dumps({item["field"]: item["digits"] for item in (spec.get("outputs") or []) if item.get("digits")}, ensure_ascii=False, allow_nan=False),
    ) + "\n})();")


def _key(spec):
    return (spec.get("stage") or {}).get("canvas_id", "lesson-scene").split("-scene")[0]


def legacy_spec(key, model, scene, draw, namespace="PHYS"):
    """给历史渲染器用的最小 spec：把 (key, model, draw) 适配成 mount_script 的入参。

    历史渲染器自带 initial/presets/presentation 与六区文案，这里只负责
    "脚本怎么跑"，因此输入字段清单可以为空（不参与单位换算）。
    """
    api = model["api"]
    if "." not in api:
        api = "%s.%s" % (namespace, api)
    namespace_of_api, function = api.split(".", 1)
    return {
        "scene": scene,
        "solver": {"api": api, "namespace": namespace_of_api, "function": function,
                   "prefix": model["prefix"]},
        "draw": {"api": draw if "." in draw else "%s.%s" % (namespace, draw)},
        "inputs": [],
        "outputs": [],
        "components": [],
        "stage": {"canvas_id": "%s-scene" % key},
        "records": {"body_id": "%s-records" % key},
        "formula": {"js": "''"},
        "summary_js": "'—'",
    }
