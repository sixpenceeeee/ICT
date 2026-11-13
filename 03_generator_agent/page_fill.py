# -*- coding: utf-8 -*-
"""page_fill —— 给确定性页面补齐"教学闭环"必备文字。

为什么要有这一层
----------------
组件化保证了"画了什么就有什么"，但不同渲染器（数学套装 / 物理 PageSpec / 化学模板）
各自写的 ⑥ 区内容不一样：有的只有原理，没有结论和注意事项。
按《优质页面标准》§3，学习闭环最后两环是「结论与解释」和「安全/边界说明」，
缺了老师就没法直接上课。

这里只补"文字性的闭环"，且**只在缺失时**追加，不覆盖渲染器自己写的内容；
数值、图示、读数一概不碰，所以不会影响可复算性。
"""

import html

SAFETY_BY_SUBJECT = {
    "物理": "本页为虚拟仿真，数值来自理想模型，不作为真实测量数据；真实实验请注意器材量程与用电安全。",
    "化学": "本页为虚拟仿真，仅演示原理与计量关系，不构成真实实验操作指引；真实实验须在教师指导下进行。",
    "数学": "本页为数学演示，图形按数值比例绘制但不代替作图规范；结论请结合教材口径复核。",
    "生物": "本页为虚拟仿真，显微视野与染色结果为示意；真实实验请遵守实验室规范。",
    "地理": "本页为示意图，比例与方位经过简化；判读结论请结合地图与教材。",
    "信息科技": "本页为算法演示，数据规模经过简化；实际复杂度请结合代码分析。",
}
DEFAULT_SAFETY = "本页为教学演示，数值与图示为示意结果，请结合教材复核。"


def _has(text, *keywords):
    return any(keyword in text for keyword in keywords)


def ensure_teaching(sections, subject=None, spec=None):
    """就地补齐 ⑥ 区的「探究问题 / 结论 / 注意事项」，返回补了哪些项。"""
    secs = sections or {}
    teaching = str(secs.get("6") or "")
    filled = []

    if not _has(teaching + str(secs.get("1") or ""), "探究问题", "观察任务", "引导问题"):
        secs["6"] = teaching + _question()
        filled.append("探究问题")

    if not _has(secs["6"], "结论"):
        secs["6"] = secs["6"] + _conclusion(spec, subject)
        filled.append("结论")

    if not _has(secs["6"], "注意事项", "安全"):
        secs["6"] = secs["6"] + _safety(subject)
        filled.append("注意事项")
    return filled


def _question():
    return ("<h3>探究问题</h3><p>改变一个参数，先预测读数与图示会怎么变，"
            "再用「记录当前数据」记下两组数据比较，看看结论是否成立。</p>")


def _conclusion(spec, subject):
    target = ""
    if spec:
        outputs = spec.get("outputs") or []
        if outputs:
            target = outputs[0].get("label") or outputs[0].get("field") or ""
    if target:
        body = ("把 ④ 区的读数与代入式对照，可以验证：%s 由页面状态按公式唯一确定，"
                "且随参数连续变化；改变一个参数时，读数、图示与记录表同步更新。" % html.escape(str(target)))
    else:
        body = ("把 ④ 区的读数与代入式对照，可以验证：本页每个状态的结果都由同一组参数按公式确定，"
                "改变一个参数时读数、图示与记录表同步更新。")
    return "<h3>结论</h3><p>%s</p>" % body


def _safety(subject):
    return "<h3>注意事项</h3><p>%s</p>" % SAFETY_BY_SUBJECT.get(subject or "", DEFAULT_SAFETY)
