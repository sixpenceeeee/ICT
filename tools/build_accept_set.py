# -*- coding: utf-8 -*-
"""build_accept_set —— 批量生成验收集，落到 deliver/ 下并附验收单。

    python tools/build_accept_set.py               # 生成 9 篇到 deliver/
    python tools/build_accept_set.py --only 浮力    # 只生成某一篇

每篇产出：HTML + frame.css / exp.css / logo.png + zip + 验收单.md。
生成全部走确定性路径，不调模型，可重复跑。
"""

import argparse
import io
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
for path in (HERE, os.path.join(PROJECT, "03_generator_agent"), PROJECT):
    if path not in sys.path:
        sys.path.insert(0, path)

import acceptance            # noqa: E402
import completeness          # noqa: E402
import generator_agent       # noqa: E402
import shell                 # noqa: E402
import scene_catalog         # noqa: E402

CHECKLIST_TAIL = [
    "", "## 人工验收（请在页面里逐项确认）", "",
    "- [ ] 打开页面无需联网，控制台无报错",
    "- [ ] 改参数后读数、图示、代入式同步变化",
    "- [ ] 预设按钮点了有变化（含「已应用预设」提示）",
    "- [ ] 「记录当前数据」能追加多行；「重置」回到初始状态",
    "- [ ] 图形内文字没有被压住或裁到画布外",
    "- [ ] ⑥ 区：原理、易错点、探究问题、结论、注意事项齐全且通顺",
    "", "打开方式：双击同目录 HTML（frame.css / exp.css / logo.png 必须同目录）。",
]


def build(subject, topic, prompt):
    request = {"学科": subject, "实验主题": topic, "原始需求": prompt, "年级": "初中",
               "学习目标": [], "交互要求": [], "技术要点": ""}
    sections, meta = generator_agent.generate(request, {})
    problems = generator_agent.hard_validate(sections, request, managed_readouts=True)
    skeleton = generator_agent.select_page_skeleton(request)
    spec = None
    try:
        if scene_catalog.SCENE_RENDERERS.get(skeleton.get("id"), {}).get("renderer") == "generic":
            spec = scene_catalog.spec_for(skeleton["id"], request)
        else:
            # 非 PageSpec 页面（数学套装/化学模板）：CSV 只按需求里是否点名来判断
            components = ["records"]
            if "CSV" in prompt or "导出" in prompt:
                components.append("csv")
            spec = {"components": components}
    except Exception:  # noqa: BLE001
        spec = None
    items = completeness.check_page(sections, spec=spec, req=request)
    summary = completeness.summarize(items)
    html = shell.render(topic, sections)
    saved = shell.deliver(html, topic, os.path.join(PROJECT, "deliver"), make_zip=True)
    folder = os.path.dirname(saved["HTML"])

    lines = ["# 验收单：%s" % topic, "",
             "- 学科：%s" % subject,
             "- 生成时间：%s" % time.strftime("%Y-%m-%d %H:%M:%S"),
             "- 生成来源：%s" % meta.get("来源"),
             "- 场景：%s" % skeleton.get("id"),
             "- 生成契约：%s" % ("通过" if meta.get("生成契约通过") else "未通过"),
             "- 硬校验问题：%s" % ("0" if not problems else "；".join(problems)),
             "- 完整性：pass %d / fail %d / skip %d" % (summary["pass"], summary["fail"], summary["skip"]),
             "", "## 元素清单（机器判定）", "", "| 元素 | 状态 | 说明 |", "|---|---|---|"]
    for item in items:
        lines.append("| %s | %s | %s |" % (item["名称"], item["状态"], item["说明"]))
    lines += CHECKLIST_TAIL
    io.open(os.path.join(folder, "验收单.md"), "w", encoding="utf-8", newline="\n").write(
        "\n".join(lines) + "\n")

    return {"学科": subject, "主题": topic, "来源": meta.get("来源"),
            "硬校验": "通过" if not problems else "失败(%d)" % len(problems),
            "完整性": "%d/%d" % (summary["pass"], summary["pass"] + summary["fail"]),
            "缺失": "、".join(i["名称"] for i in summary["失败项"]) or "无",
            "大小KB": os.path.getsize(saved["HTML"]) // 1024,
            "页面": saved["HTML"], "压缩包": saved.get("ZIP") or "",
            "补齐": "、".join(meta.get("补齐项") or []) or "无"}


def main(argv=None):
    parser = argparse.ArgumentParser(description="批量生成验收集")
    parser.add_argument("--only", help="只生成指定主题")
    args = parser.parse_args(argv)

    targets = [item for item in acceptance.ACCEPT_SET if not args.only or item[1] == args.only]
    rows = []
    for subject, topic, prompt in targets:
        rows.append(build(subject, topic, prompt))
        print("· %-14s %s" % (topic, rows[-1]["页面"]))

    print()
    print("| 学科 | 主题 | 生成来源 | 硬校验 | 完整性 | 缺失 | 页面 |")
    print("|---|---|---|---|---|---|---|")
    for row in rows:
        print("| %s | %s | %s | %s | %s | %s | %dKB |" % (
            row["学科"], row["主题"], row["来源"], row["硬校验"], row["完整性"], row["缺失"], row["大小KB"]))
    bad = [row for row in rows if row["缺失"] != "无" or row["硬校验"] != "通过"]
    print()
    print("共 %d 篇，缺项 %d 篇" % (len(rows), len(bad)))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
