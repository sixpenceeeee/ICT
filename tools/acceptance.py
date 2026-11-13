# -*- coding: utf-8 -*-
"""acceptance —— 页面验收集一键验收（不需要浏览器）。

跑什么
------
对验收集里每一篇：
    生成（确定性路径，不调模型） → 硬校验 → 完整性检查（元素/步骤） → 套壳出页
输出一张 Markdown 表 + 退出码；有任一失败即非 0，便于接 CI。

怎么跑
------
    python tools/acceptance.py                    # 默认写到项目根 acceptance.md
    python tools/acceptance.py --out D:\\tmp\\a.md  # 指定输出

为什么不含生物/地理/信息
------------------------
这三科目前没有确定性渲染器（全部走大模型），结果逐次不同，
不能作为"可复跑"的验收依据，单独列为「待评审」。
"""

import argparse
import io
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
for path in (os.path.join(PROJECT, "03_generator_agent"), PROJECT):
    if path not in sys.path:
        sys.path.insert(0, path)

import completeness          # noqa: E402
import generator_agent       # noqa: E402
import shell                 # noqa: E402

#: 验收集：全部为确定性渲染，可复跑、可比对
ACCEPT_SET = [
    ("数学", "二次函数", "为初中九年级生成二次函数 y=ax²+bx+c 的图像与系数关系探究页，"
                        "显示顶点、对称轴，支持记录多组数据和导出 CSV。"),
    ("数学", "平面截正方体", "为初中八年级生成平面截正方体的交互页面，可拖动旋转视角，"
                            "实时显示截面边数、形状和面积，提供重置。"),
    ("数学", "勾股定理", "为初中八年级生成勾股定理动态验证页面，拖动两条直角边时"
                        "三个正方形的面积同步变化，可记录多组数据。"),
    ("物理", "浮力", "为初中八年级生成探究浮力大小与排开液体体积关系的浮力实验，"
                    "显示测力计示数、浮力和排开液体体积，支持记录和 CSV。"),
    ("物理", "杠杆平衡", "为初中八年级生成杠杆平衡条件探究页，可调节两侧的力和力臂，"
                        "显示两侧力矩和是否平衡，支持记录。"),
    ("物理", "匀变速直线运动", "为初中生成匀变速直线运动的 v-t 图像探究页，"
                              "可调初速度、加速度和时间，显示瞬时速度和位移。"),
    ("物理", "斜面", "为初中八年级生成斜面机械效率探究页，可调物重、斜面长度、高度和摩擦系数，"
                    "显示拉力、有用功、总功和效率。"),
    ("物理", "密度测量", "为初中八年级生成密度测量实验页：用托盘天平测质量、量筒排水法测体积，"
                        "显示密度并与水的密度比较判断浮沉，支持记录和导出 CSV。"),
    ("化学", "酸碱中和滴定", "用 0.1 mol/L 的 HCl 滴定 25 mL 0.1 mol/L 的 NaOH 溶液，"
                            "观察当量点前后的 pH 变化并绘制滴定曲线。"),
    ("化学", "沉淀反应定量", "向 50 mL 0.1 mol/L 的 BaCl2 溶液中加入 0.1 mol/L 的 Na2SO4 溶液，"
                            "研究沉淀质量与限量试剂的关系。"),
]

#: 待评审：走大模型，结果不可复跑，只登记不计分
PENDING = [
    ("生物", "孟德尔杂交", "需要大模型生成 + 人工过目"),
    ("地理", "等高线剖面", "需要大模型生成 + 人工过目"),
    ("信息科技", "冒泡排序", "需要大模型生成 + 人工过目"),
]


def run_one(subject, topic, prompt):
    request = {"学科": subject, "实验主题": topic, "原始需求": prompt, "年级": "初中",
               "学习目标": [], "交互要求": [], "技术要点": ""}
    started = time.time()
    try:
        sections, meta = generator_agent.generate(request, {})
    except Exception as exc:  # noqa: BLE001 - 验收脚本要把任何异常都变成一行结论
        return {"subject": subject, "topic": topic, "source": "异常",
                "contract": "-", "missing": "%s: %s" % (type(exc).__name__, exc),
                "verdict": "不通过", "size": 0, "seconds": round(time.time() - started, 1)}
    problems = generator_agent.hard_validate(sections, request, managed_readouts=True)
    spec = None
    try:
        import scene_catalog
        import re as _re
        skeleton = generator_agent.select_page_skeleton(request)
        if scene_catalog.SCENE_RENDERERS.get(skeleton.get("id"), {}).get("renderer") == "generic":
            spec = scene_catalog.spec_for(skeleton["id"], request)
        else:
            # 非 PageSpec 页面（数学套装/化学模板）：按需求里是否点名 CSV 决定期望
            components = ["records"]
            if _re.search(r"CSV|导出", prompt):
                components.append("csv")
            spec = {"components": components}
    except Exception:  # noqa: BLE001
        spec = None
    items = completeness.check_page(sections, spec=spec, req=request)
    summary = completeness.summarize(items)
    html = shell.render(topic, sections)
    passed = not problems and summary["可验收"] and meta.get("生成契约通过")
    return {"subject": subject, "topic": topic, "source": meta.get("来源", "-"),
            "contract": "通过" if not problems else "失败(%d)" % len(problems),
            "problems": problems,
            "missing": "、".join(item["名称"] for item in summary["失败项"]) or "无",
            "warn": "、".join(item["名称"] for item in summary["建议项"]) or "无",
            "element_pass": summary["pass"], "element_skip": summary["skip"],
            "verdict": "可验收" if passed else "不通过",
            "size": len(html) // 1024, "seconds": round(time.time() - started, 1)}


def main(argv=None):
    parser = argparse.ArgumentParser(description="页面验收集一键验收")
    parser.add_argument("--out", default=os.path.join(PROJECT, "acceptance.md"))
    args = parser.parse_args(argv)

    rows = [run_one(*item) for item in ACCEPT_SET]
    good = [row for row in rows if row["verdict"] == "可验收"]

    lines = ["# 页面验收报告", "",
             "- 时间：%s" % time.strftime("%Y-%m-%d %H:%M:%S"),
             "- 验收集：%d 篇（确定性渲染，可复跑）" % len(rows),
             "- 结果：**%d/%d 可验收**" % (len(good), len(rows)),
             "", "## 验收集明细", "",
             "| 学科 | 主题 | 生成来源 | 硬校验 | 元素通过/跳过 | 缺什么 | 建议补 | 页面 | 判定 |",
             "|---|---|---|---|---|---|---|---|---|"]
    for row in rows:
        lines.append("| %s | %s | %s | %s | %d/%d | %s | %s | %dKB | %s |" % (
            row["subject"], row["topic"], row["source"], row["contract"],
            row.get("element_pass", 0), row.get("element_skip", 0),
            row["missing"], row["warn"], row["size"], row["verdict"]))
    failed = [row for row in rows if row["verdict"] != "可验收"]
    if failed:
        lines += ["", "## 需要修的项", ""]
        for row in failed:
            lines.append("- **%s / %s**：%s" % (row["subject"], row["topic"], row["missing"]))
            for problem in (row.get("problems") or [])[:5]:
                lines.append("  - 硬校验：%s" % problem)
    lines += ["", "## 待评审（走大模型，不计入可验收）", "",
              "| 学科 | 主题 | 说明 |", "|---|---|---|"]
    for subject, topic, note in PENDING:
        lines.append("| %s | %s | %s |" % (subject, topic, note))
    lines += ["", "## 判定口径", "",
              "- 可验收 = 生成契约通过 + 生成端硬校验 0 问题 + 完整性检查无失败项",
              "- 完整性检查覆盖：学习目标、控件、读数、代入式、记录表、CSV、重置、"
              "探究问题、结论、注意事项、结果绑定、离线、分步流程",
              "- 浏览器侧审查（playwright）不在此脚本内：本机跑 `python 04_review_agent/reviewer.py "
              "--html <页面>` 补一次即可"]

    text = "\n".join(lines) + "\n"
    with io.open(args.out, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    print(text)
    print("已写入 %s" % args.out)
    return 0 if len(good) == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
