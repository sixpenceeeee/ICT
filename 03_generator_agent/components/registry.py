# -*- coding: utf-8 -*-
"""components.registry —— 组件登记表 + 六区装配。

这是"组块化"的核心：**页面 = 一组已登记组件的组合**。

组件只声明三件事：
1. 它属于哪个区（1–6）；
2. 它需要渲染什么（吃 PageSpec，吐 HTML）；
3. 它产出哪些机读标记（供硬校验与审查器核对）。

于是"加一个场景"不再需要动渲染器、硬校验、探针三处：
只要 PageSpec 里的组件开关和字段变了，HTML 与取证契约自动跟着变。
"""

from dataclasses import dataclass, field
from typing import Callable

from . import atoms, controls, readouts, records, stage, teaching


@dataclass
class Rendered:
    html: str = ""
    markers: tuple = ()
    presets: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Part:
    id: str
    region: str
    render: Callable


def _meta(spec):
    return Rendered(teaching.render_meta(spec), teaching.markers(spec))


def _stage(spec):
    return Rendered(stage.render_stage(spec), stage.markers(spec))


def _controls(spec):
    html, markers = controls.render_controls(spec)
    actions, presets = controls.render_actions(spec)
    return Rendered(html + actions, tuple(markers), presets)


def _readouts(spec):
    key = (spec.get("stage") or {}).get("canvas_id", "lesson-scene").split("-scene")[0]
    html, markers = readouts.render_readouts(spec)
    html += readouts.render_formula("%s-formula" % key)
    html += readouts.render_teaching_note(spec)
    html += readouts.render_error()
    comparison, comparison_markers = readouts.render_comparison(spec)
    return Rendered(html + comparison, tuple(markers + comparison_markers))


def _records(spec):
    return Rendered(records.render_records(spec), records.markers(spec))


def _teaching(spec):
    return Rendered(teaching.render_teaching(spec), teaching.markers(spec))


PARTS = (
    Part("meta", "1", _meta),
    Part("stage", "2", _stage),
    Part("controls", "3", _controls),
    Part("readouts", "4", _readouts),
    Part("records", "5", _records),
    Part("teaching", "6", _teaching),
)

# 组件级 CSS：只声明一次，六个区共用；不再由每个渲染器各自内联
COMPONENT_CSS = (
    '.exp-grid > *, .exp-table-wrap{min-width:0;max-width:100%}'
    '.exp-field input,.exp-field select{box-sizing:border-box;min-width:0;max-width:100%}'
    '.exp-read .v,.exp-info,.exp-note{overflow-wrap:anywhere}'
    '.exp-table td{white-space:normal;overflow-wrap:anywhere}'
    '.exp-reads{display:flex;flex-wrap:wrap;gap:8px}'
    '.exp-comparison-grid{display:flex;flex-wrap:wrap;gap:8px}'
)

STAGE_CSS = (
    '.physics-stage{display:grid;grid-template-rows:minmax(0,1fr) auto;height:100%;min-width:0;max-width:100%;overflow:hidden}'
    '.physics-plot{position:relative;min-height:0;min-width:0;max-width:100%;overflow:hidden}'
    '.physics-plot canvas{position:absolute;inset:0;max-width:100%}'
    '.physics-key{display:flex;justify-content:center;flex-wrap:wrap;gap:0 0.6em;margin:0;padding:0.25em 0.6em}'
)

LESSON_CSS = (
    '.lesson-stage{display:grid;grid-template-rows:minmax(0,1fr) auto;height:100%;min-width:0;max-width:100%;overflow:hidden}'
    '.lesson-plot{position:relative;min-height:0;min-width:0;max-width:100%;overflow:hidden}'
    '.lesson-plot canvas{position:absolute;inset:0;max-width:100%}'
    '.lesson-key{display:flex;justify-content:center;flex-wrap:wrap;gap:0 0.6em;margin:0;padding:0.25em 0.6em}'
)


def assemble(spec):
    """PageSpec -> ({'1'..'6','css'}, markers, presets)。"""
    sections = {str(index): [] for index in range(1, 7)}
    markers = []
    presets = {}
    for part in PARTS:
        rendered = part.render(spec)
        if rendered.html:
            sections[part.region].append(rendered.html)
        markers.extend(rendered.markers)
        presets.update(rendered.presets)
    body = {key: "".join(value) for key, value in sections.items()}
    body["css"] = COMPONENT_CSS + STAGE_CSS
    return body, markers, presets


def contract(spec):
    """只算契约不渲染：给校验器与测试用（期望的标记集合）。"""
    markers = []
    for part in PARTS:
        markers.extend(part.render(spec).markers)
    return markers


__all__ = ["Rendered", "Part", "PARTS", "assemble", "contract",
           "COMPONENT_CSS", "STAGE_CSS", "LESSON_CSS", "atoms"]
