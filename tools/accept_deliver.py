# -*- coding: utf-8 -*-
"""批量验收 deliver 下的页面，输出 Markdown + CSV 汇总。"""
import csv
import os
import sys
import time
from datetime import datetime

ROOT = r"D:\Users\wangq\Desktop\2026-10-18-11-03-28"
REVIEW = os.path.join(ROOT, "04_review_agent")
sys.path.insert(0, REVIEW)
os.chdir(REVIEW)

import reviewer  # noqa: E402


def pages():
    base = os.path.join(ROOT, "deliver")
    for folder in sorted(os.listdir(base)):
        case_dir = os.path.join(base, folder)
        if not os.path.isdir(case_dir) or "统一质感" in folder:
            continue
        html = [name for name in os.listdir(case_dir) if name.lower().endswith(".html")]
        if not html:
            continue
        yield folder, os.path.join(case_dir, sorted(html)[0])


def main():
    rows = []
    for case, path in pages():
        started = time.time()
        print("ACCEPT", case, flush=True)
        try:
            report = reviewer.run_review(path, None, use_browser=True, verbose=False)
            failed = [item for item in report.get("检查项", []) if item.get("status") == "fail"]
            critical = [item for item in failed if item.get("severity") == "严重"]
            mr = report.get("变形测试") or {}
            if not mr.get("checked"):
                mr_text = "无页面计划"
            else:
                mr_text = "通过 %d / 失败 %d / 跳过 %d" % (
                    mr.get("pass", 0), mr.get("fail", 0), mr.get("skip", 0))
            rows.append({
                "页面": case,
                "结论": report.get("结论", ""),
                "总分": report.get("总分", 0),
                "严重问题数": len(critical),
                "发布状态": report.get("发布状态", ""),
                "变形测试": mr_text,
                "主要失败项": "；".join(
                    "%s %s" % (item.get("check_id"), item.get("name")) for item in failed[:4]),
                "耗时秒": round(time.time() - started, 1),
            })
        except Exception as exc:  # noqa: BLE001
            rows.append({
                "页面": case, "结论": "审查异常", "总分": 0, "严重问题数": 99,
                "发布状态": "未验证", "变形测试": "-",
                "主要失败项": "%s: %s" % (type(exc).__name__, exc),
                "耗时秒": round(time.time() - started, 1),
            })
        print("DONE", case, rows[-1]["结论"], rows[-1]["总分"], flush=True)

    rows.sort(key=lambda item: (-item["严重问题数"], item["总分"]))
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    md_path = os.path.join(ROOT, "验收汇总.md")
    csv_path = os.path.join(ROOT, "验收汇总.csv")
    with open(md_path, "w", encoding="utf-8") as handle:
        handle.write("# 页面验收汇总\n\n> %s ｜ 共 %d 篇 ｜ 审查器：reviewer.py（含浏览器第4关）\n\n" % (stamp, len(rows)))
        handle.write("| 页面 | 结论 | 总分 | 严重 | 发布状态 | 变形测试 | 主要失败项 |\n")
        handle.write("|---|---|---:|---:|---|---|---|\n")
        for row in rows:
            handle.write("| %s | %s | %.1f | %d | %s | %s | %s |\n" % (
                row["页面"], row["结论"], row["总分"], row["严重问题数"],
                row["发布状态"], row["变形测试"], row["主要失败项"]))
        handle.write("\n判定规则：有“严重”项即不通过，分数只作参考。\n")
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else ["页面"])
        writer.writeheader()
        writer.writerows(rows)
    print("WROTE", md_path, csv_path, flush=True)


if __name__ == "__main__":
    main()
