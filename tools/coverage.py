# -*- coding: utf-8 -*-
"""coverage —— 组块化覆盖度看板（数理化全场景）。

回答一个问题：**案例清单里的知识点，有多少能确定性渲染，没覆盖的归到哪个范式。**

判据
----
对 06_full_catalog 的每条案例，合成一条需求 → select_page_skeleton → render_scene：
能返回六区内容 = 可确定性渲染；返回 None = 还缺范式（或该知识点没登记）。

输出
----
* 按学科、按场景骨架统计覆盖率
* 未覆盖案例按「缺哪个范式」归并（同一 scene_id 归一类），给出每类还差多少条
* 写入 coverage.md，便于每轮迭代对比

用法：
    python tools/coverage.py
"""

import collections
import csv
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
for path in (os.path.join(PROJECT, "03_generator_agent"), PROJECT):
    if path not in sys.path:
        sys.path.insert(0, path)

import scene_catalog          # noqa: E402
import scene_registry         # noqa: E402

SUBJECTS = ("数学", "物理", "化学")
CATALOG = os.path.join(PROJECT, "06_full_catalog", "全学段案例清单.csv")
OUT = os.path.join(PROJECT, "coverage.md")

#: 未覆盖时"还缺什么"的人话说明
MISSING_HINT = {
    "physics-circuit-lab": "电路装配范式：netlist 控件 + 电表 DOM 绑定（CIRCUIT.draw 已就绪）",
    "physics-investigation": "学科通用探究范式：该知识点还没登记专用场景与 UI 元数据",
    "physics-thin-lens": "薄透镜范式：显式规格通道（PHYS.optics 已就绪）",
    "math-exploration": "数学通用范式：该知识点还没登记 lesson 模型/几何装配",
    "math-spatial-geometry": "立体几何范式：尺寸参数 + 体积/展开装配",
    "chemistry-lab": "化学通用范式：缺页面模板与 data-chem-* 契约",
    "chemistry-equation-balance": "化学配平范式：需要 PageSpec 化的配平页模板",
}


def load_cases():
    with io.open(CATALOG, encoding="utf-8-sig") as handle:
        return [row for row in csv.DictReader(handle) if row.get("学科") in SUBJECTS]


def renderable(case, subject):
    request = {"学科": subject, "实验主题": case, "技术要点": "", "学习目标": [], "交互要求": []}
    skeleton = scene_registry.select_page_skeleton(request)
    try:
        return scene_catalog.render_scene(request, skeleton) is not None, skeleton.get("id")
    except Exception:  # noqa: BLE001 - 体检要把异常算成"不可渲染"
        return False, skeleton.get("id")


def main():
    rows = load_cases()
    by_subject = collections.defaultdict(lambda: [0, 0])
    by_scene = collections.defaultdict(lambda: [0, 0])
    missing = collections.defaultdict(list)

    for row in rows:
        subject, case = row["学科"], row["案例"]
        ok, scene_id = renderable(case, subject)
        by_subject[subject][0] += 1
        by_scene[(subject, scene_id)][0] += 1
        if ok:
            by_subject[subject][1] += 1
            by_scene[(subject, scene_id)][1] += 1
        else:
            missing[(subject, scene_id)].append(case)

    total = sum(v[0] for v in by_subject.values())
    done = sum(v[1] for v in by_subject.values())

    lines = ["# 组块化覆盖度看板", "",
             "- 清单：06_full_catalog 全学段案例（数理化）",
             "- 判定：该知识点能否由确定性渲染器出页（不调模型）",
             "- 总计：**%d 条，可确定性渲染 %d 条（%.0f%%）**" % (total, done, 100 * done / max(total, 1)),
             "",
             "## 按学科", "", "| 学科 | 案例 | 可渲染 | 覆盖率 |", "|---|---|---|---|"]
    for subject in SUBJECTS:
        count, ok = by_subject.get(subject, [0, 0])
        lines.append("| %s | %d | %d | %.0f%% |" % (subject, count, ok, 100 * ok / max(count, 1)))

    lines += ["", "## 按场景骨架（范式）", "", "| 学科 | 场景 | 案例 | 可渲染 | 说明 |", "|---|---|---|---|---|"]
    for (subject, scene_id), (count, ok) in sorted(by_scene.items(), key=lambda kv: (kv[0][0], -kv[1][0])):
        note = "" if ok == count else MISSING_HINT.get(scene_id, "缺确定性渲染器")
        lines.append("| %s | %s | %d | %d | %s |" % (subject, scene_id, count, ok, note))

    lines += ["", "## 未覆盖知识点（按缺口归并）", ""]
    for (subject, scene_id), cases in sorted(missing.items(), key=lambda kv: -len(kv[1])):
        lines.append("**%s · %s**（%d 条）" % (subject, scene_id, len(cases)))
        lines.append("")
        lines.append("- 缺什么：%s" % MISSING_HINT.get(scene_id, "确定性渲染器"))
        lines.append("- 知识点：%s" % "、".join(cases))
        lines.append("")

    text = "\n".join(lines) + "\n"
    io.open(OUT, "w", encoding="utf-8", newline="\n").write(text)
    print(text)
    print("已写入 %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
