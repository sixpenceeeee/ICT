# -*- coding: utf-8 -*-
"""把 seed/ 下六个学科的主题数据渲染成 knowledge/ 里的 md 知识库。

为什么要一个渲染器而不是手写 145 个 md：
1. 每个主题固定 5 类（课标/教材/规范/安全/交互），手写必然格式漂移，kb.py 按 `类别` 做保底，格式一乱就检索不到；
2. frontmatter 的 `主题` 是检索过滤键，写错一个字整个主题就检索空；
3. 主题数据同时是 topics.py 的 PROFILE 来源（关键词/单位/上限/公式），一处改两处同步。

用法：python seed/build_kb.py [--check]
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
KB_DIR = os.path.join(ROOT, "knowledge")

KINDS = [
    ("课标", "课标依据", "课标依据"),
    ("教材", "教材内容", "教材内容"),
    ("规范", "实验规范", "实验规范"),
    ("安全", "安全约束", "安全约束"),
    ("交互", "交互设计", "交互设计"),
]

START_NO = 11


def source_of(t, kind):
    if kind == "课标":
        if t["学段"] == "高中":
            return "普通高中%s课程标准（2017年版2020年修订）· %s" % (t["学科"], t["课标主题"])
        return "义务教育%s课程标准（2022年版）· %s" % (t["学科"], t["课标主题"])
    if kind == "教材":
        return t["出处"]
    if kind == "规范":
        return "%s · 实验与探究" % t["出处"]
    if kind == "安全":
        return "平台内容安全边界（虚拟实验，不指导真实操作）"
    return "平台《界面设计+审查判据》六区域规范"


def render(t, kind, cat):
    body = t[kind]
    lines = []
    for title, val in body.items():
        lines.append("## %s" % title)
        if isinstance(val, (list, tuple)):
            for item in val:
                lines.append("- %s" % item)
        else:
            lines.append(val)
        lines.append("")
    return "\n".join([
        "---",
        "类别: %s" % cat,
        "主题: %s" % t["主题"],
        "来源: %s" % source_of(t, kind),
        "---",
        "",
    ]) + "\n".join(lines).rstrip() + "\n"


def load_topics():
    sys.path.insert(0, HERE)
    import biology_kb
    import chemistry_kb
    import geography_kb
    import informatics_kb
    import math_kb
    import physics_kb
    mods = [math_kb, physics_kb, chemistry_kb, biology_kb, geography_kb, informatics_kb]
    out = []
    for m in mods:
        out.extend(m.TOPICS)
    return out


def main():
    topics = load_topics()
    names = [t["主题"] for t in topics]
    dup = {n for n in names if names.count(n) > 1}
    if dup:
        raise SystemExit("主题重名：%s" % "、".join(dup))

    if "--check" in sys.argv:
        for t in topics:
            print("%-6s %-10s %-14s 课标%d 教材%d 规范%d 安全%d 交互%d" % (
                t["编号"], t["学科"], t["主题"],
                len(t["课标"]), len(t["教材"]), len(t["规范"]),
                len(t["安全"]), len(t["交互"])))
        print("合计 %d 个主题，%d 个文件" % (len(topics), len(topics) * 5))
        return

    n = START_NO
    written = []
    for t in topics:
        for kind, cat, _ in KINDS:
            path = os.path.join(KB_DIR, "%03d_%s_%s.md" % (n, t["短名"], cat))
            io.open(path, "w", encoding="utf-8").write(render(t, kind, cat))
            written.append(path)
            n += 1

    print("写入 %d 个文件，编号 %03d–%03d" % (len(written), START_NO, n - 1))
    by_subject = {}
    for t in topics:
        by_subject.setdefault(t["学科"], []).append(t["主题"])
    for s, ts in by_subject.items():
        print("  %s %d：%s" % (s, len(ts), "、".join(ts)))


if __name__ == "__main__":
    main()
