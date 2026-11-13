# -*- coding: utf-8 -*-
"""paradigm_gaps —— 把"覆盖率不够"翻译成"下一步做哪个范式"。

coverage.py 只回答"覆盖了多少"；本脚本回答"没覆盖的归到哪一类、每类还缺什么、
大概多久"。它不修改任何共享文件，只读清单 + 场景表 + 现有求解器/绘图 API，
产出一份可执行的工单 paradigm_gaps.md。

用法：
    python tools/paradigm_gaps.py
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
OUT = os.path.join(PROJECT, "paradigm_gaps.md")

#: 范式表：关键词命中即归入该范式。
#: 字段：id, 名称, 关键词, 需要的求解器, 需要的组件, 现状, 工期(天)
PARADIGMS = [
    ("P01", "溶液浓度与稀释", ("溶质质量分数", "稀释", "浓度"), "CHEMSOLVER.solveDilution（缺）",
     "溶液配比控件 + 浓度读数 + 记录", "求解器与组件都缺", 1.0),
    ("P02", "溶解度与溶解度曲线", ("溶解与饱和", "溶解度", "饱和溶液", "结晶"), "CHEMSOLVER.solveSolubilityCurve（缺）",
     "温度—溶解度曲线 + 饱和判定", "求解器与组件都缺（可复用滴定曲线组件）", 1.5),
    ("P03", "质量守恒与过量判断", ("质量守恒", "过量", "反应物质量"), "CHEMSOLVER.solveStoichiometry（已有）",
     "PageSpec 化 + 质量单位换算", "求解器已有，缺规格声明", 0.5),
    ("P04", "酸碱指示剂与 pH", ("pH", "指示剂", "石蕊", "酚酞"), "CHEMSOLVER.solveAcidBaseTitration（已有）",
     "pH 色卡 + 指示剂切换", "判定类，需 facts 条目兜底", 1.0),
    ("P05", "物质变化类型判定", ("物理变化", "化学变化"), "无需求解器",
     "现象卡 + 判定题组件（J6 要素型）", "判据偏软，建议列为不做/教师复核", 0.5),
    ("P06", "电路装配", ("电路", "串联", "并联", "欧姆", "电功率", "焦耳"), "CIRCUIT.solve（已有）",
     "netlist 控件（元件/接线）+ 电表绑定", "求解器与绘图都已就绪，缺规格通道", 2.0),
    ("P07", "光学反射与平面镜", ("反射", "平面镜", "影子", "小孔"), "PHYS.solvePlaneMirror（已有）",
     "光线与角度组件", "已有绘图组件，缺显式规格入口", 0.5),
    ("P08", "热学与气体定律", ("大气压", "气体", "压强与温度", "热值"), "PHYS.solveIdealGas（缺）",
     "活塞/气压计 + 曲线", "求解器与组件都缺", 1.5),
    ("P09", "力学进阶（动量/圆周/单摆）", ("动量", "圆周运动", "向心", "单摆", "机械振动"),
     "PHYS.solveMomentum / solveCircular / solvePendulum（缺）", "矢量图 + 过程动画",
     "求解器与组件都缺（3 个求解器）", 2.5),
    ("P10", "电磁感应与磁场", ("电磁感应", "安培", "磁场", "洛伦兹", "带电粒子"), "PHYS.solveLorentz（缺）",
     "场线 + 粒子轨迹", "求解器与组件都缺", 1.5),
    ("P11", "密度与测量", ("密度", "质量与体积", "量筒"), "PHYS.solveDensity（缺）", "量筒/天平 + 读数",
     "求解器缺，组件可复用 glass/box", 0.5),
    ("P12", "立体几何体（圆柱圆锥长方体）", ("圆柱", "圆锥", "长方体", "正方体"), "MATH.solveSolidVolume（已有）",
     "尺寸控件 + 体积/表面积读数", "求解器已有，缺主题登记", 0.5),
]
ASSUMED_SOLVED = ("chemistry-acid-base-titration",)


def load_cases():
    with io.open(CATALOG, encoding="utf-8-sig") as handle:
        return [row for row in csv.DictReader(handle) if row.get("学科") in SUBJECTS]


def is_renderable(case, subject):
    request = {"学科": subject, "实验主题": case, "技术要点": "", "学习目标": [], "交互要求": []}
    skeleton = scene_registry.select_page_skeleton(request)
    try:
        return scene_catalog.render_scene(request, skeleton) is not None
    except Exception:  # noqa: BLE001
        return False


def classify(case):
    for pid, name, keywords, solver, component, state, days in PARADIGMS:
        if any(keyword in case for keyword in keywords):
            return pid, name, solver, component, state, days
    return "P99", "其他/待归类", "待评估", "待评估", "需人工判断", 1.0


def main():
    rows = load_cases()
    covered = 0
    gaps = collections.OrderedDict()
    for row in rows:
        subject, case = row["学科"], row["案例"]
        if is_renderable(case, subject):
            covered += 1
            continue
        pid, name, solver, component, state, days = classify(case)
        item = gaps.setdefault(pid, {"name": name, "solver": solver, "component": component,
                                     "state": state, "days": days, "cases": []})
        item["cases"].append("%s·%s" % (subject, case))

    total = len(rows)
    lines = ["# 范式缺口工单（组块化覆盖）", "",
             "- 清单：06_full_catalog 数理化 %d 条" % total,
             "- 已覆盖：%d 条（%.0f%%）；缺口归并为 **%d 个范式**" % (
                 covered, 100 * covered / max(total, 1), len(gaps)),
             "",
             "## 工单", "",
             "| 范式 | 缺什么 | 现状 | 案例数 | 工期 |", "|---|---|---|---|---|"]
    total_days = 0
    for pid, item in sorted(gaps.items(), key=lambda kv: -len(kv[1]["cases"])):
        lines.append("| %s %s | %s + %s | %s | %d | %.1f 天 |" % (
            pid, item["name"], item["solver"], item["component"], item["state"],
            len(item["cases"]), item["days"]))
        total_days += item["days"]

    lines += ["", "## 逐范式明细", ""]
    for pid, item in sorted(gaps.items(), key=lambda kv: -len(kv[1]["cases"])):
        lines += ["### %s %s（%d 条，%.1f 天）" % (pid, item["name"], len(item["cases"]), item["days"]),
                  "",
                  "- 需要：%s" % item["solver"],
                  "- 组件：%s" % item["component"],
                  "- 现状：%s" % item["state"],
                  "- 案例：%s" % "、".join(item["cases"]),
                  ""]

    lines += ["## 建议顺序", "",
              "1. **P07 光学反射**（0.5 天）：绘图组件已有，只差显式规格入口",
              "2. **P12 立体几何**（0.5 天）：求解器已有，只差主题登记",
              "3. **P03 质量守恒**（0.5 天）：求解器已有，只差规格声明",
              "4. **P06 电路装配**（2 天）：演示权重最高，求解器与绘图都已就绪",
              "5. **P01/P02 溶液与溶解度**（2.5 天）：化学覆盖率从 6% 拉到 60%",
              "6. **P08/P09/P10/P11**（6 天）：物理长尾",
              "",
              "合计约 **%.1f 天**可把数理化覆盖推到 ~95%%；剩余 5%% 是单点长尾（每范式 1–3 条）。"
              % total_days]

    text = "\n".join(lines) + "\n"
    io.open(OUT, "w", encoding="utf-8", newline="\n").write(text)
    print(text)
    print("已写入 %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
