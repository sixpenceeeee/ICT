# -*- coding: utf-8 -*-
"""① 实验信息 / ⑥ 教学说明。

两区都是"文字区"，但承担不同的取证职责：
* ① 区给学科胶囊 + 实验性质 + 学习目标（学习目标必须能被本页操作验证）
* ⑥ 区给原理 / 易错点 / 探究问题 / 结论 / 注意事项，审查器从这里取"教学闭环"证据
"""

from . import atoms

TEACHING_BLOCKS = (
    ("principle", "原理"),
    ("pitfall", "易错点"),
    ("question", "探究问题"),
    ("conclusion", "结论"),
    ("safety", "注意事项"),
)


def render_meta(spec):
    goals = list(spec.get("learning_goals") or [])
    if not goals:
        goals = [(spec.get("teaching") or {}).get("question")
                 or "改变一个参数，比较读数与图示的变化。"]
    html = atoms.render_subject_tags(spec.get("subject") or "跨学科",
                                     spec.get("grade") or "初中")
    source = (spec.get("teaching") or {}).get("source") or spec.get("source")
    if source:
        html += atoms.render_note("来源：%s" % source)
    kind = (spec.get("teaching") or {}).get("kind")
    if kind:
        html += atoms.render_note(kind)
    html += atoms.render_learning_goals(goals)
    return html


def render_teaching(spec):
    teaching = spec.get("teaching") or {}
    blocks = [(title, teaching.get(key, "")) for key, title in TEACHING_BLOCKS]
    html = atoms.render_teaching_section(blocks)
    derivation = (spec.get("teaching") or {}).get("derivation") or ""
    if derivation and "derivation" in (spec.get("components") or []):
        html += atoms.render_note(derivation, element="p")
    return html


def markers(spec):
    return []
