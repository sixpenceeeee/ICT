# -*- coding: utf-8 -*-
"""generic_lesson —— 「一个渲染器渲染所有 lesson 场景」。

输入：PageSpec（含求解器、控件、读数、组件开关、文案与取证契约）
输出：六区 dict + css + js，可直接交给 shell.render() 套壳

这个模块里**不允许出现任何具体学科的名字**。所有场景差异都写在 scene_catalog 的
UI 元数据里，所以加一个实验不需要改这里一行代码——这正是组块化要达到的状态。
"""

from components import registry, runtime
import page_spec


class SceneNotRenderable(RuntimeError):
    """该场景缺少确定性渲染所需的组件（通常是共享绘图函数）。

    宁可拒绝出页并说清缺什么，也不要退化成"只有数值没有实验对象"的页面。
    """


def render(spec):
    """PageSpec -> sections 字典。"""
    page_spec.require_valid(spec)
    sections, markers, presets = registry.assemble(spec)
    script = runtime.mount_script(spec, presets=presets)
    _check_contract(spec, sections, script, markers)
    sections["js"] = script
    return sections


def _check_contract(spec, sections, script, markers):
    """渲染完立刻自查：spec 声明的标记/调用必须真的落在页面上。

    这是"契约由组件产出"的兜底：组件漏写标记时，错误在这里暴露，
    而不是等到审查器判死整页。
    """
    markup = "\n".join(sections[key] for key in ("1", "2", "3", "4", "5", "6")) + "\n" + script
    missing = []
    for attr, value in markers:
        if not _attr_present(markup, attr, value):
            missing.append('%s="%s"' % (attr, value))
    for token in page_spec.runtime_tokens(spec):
        if token not in script:
            missing.append(token)
    if missing:
        raise SceneNotRenderable("页面契约未落地：%s" % "、".join(missing))


def _attr_present(markup, attr, value):
    if value in (None, ""):
        return attr in markup
    return ('%s="%s"' % (attr, value)) in markup


def preview(spec):
    """给测试/调试用：渲染并返回 HTML 片段统计。"""
    sections = render(spec)
    return {"sections": {key: len(value) for key, value in sections.items()},
            "has_formula": "exp-formula" in sections["4"]}
