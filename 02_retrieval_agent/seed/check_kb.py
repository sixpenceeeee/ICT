# -*- coding: utf-8 -*-
"""知识库自检：主题识别 + 检索类别覆盖 + 跨主题污染。

三个要检查的东西：
1. 拿清单里的实验名当需求，detect_topic 必须命中自己（不能认成别的学科主题）；
2. 每个主题按自己的关键词检索 top8，5 个类别至少覆盖 4 类（少了说明该主题知识写得太薄）；
3. 检索结果不能串到别的主题（按主题索引本身不该串，这里验证 fallback 路径）。
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PROJ = os.path.dirname(ROOT)
sys.path.insert(0, PROJ)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import build_kb
import kb as kbmod
import topics as tp


def main():
    seed = build_kb.load_topics()
    kb = kbmod.KnowledgeBase()

    print("=" * 72)
    print("一、主题识别")
    miss = []
    for t in seed:
        got = tp.detect_topic(t["主题"])
        if got != t["主题"]:
            miss.append((t["主题"], got))
    if miss:
        for name, got in miss:
            print("  ✗ %-10s → %s" % (name, got or "None"))
    else:
        print("  全部 %d 个主题识别正确" % len(seed))

    print("=" * 72)
    print("二、检索类别覆盖（top8）")
    thin = []
    for t in seed:
        q = " ".join(t["关键词"][:4]) + " " + t["核心公式"]
        hits = kb.search(q, top_k=8, topic=t["主题"])
        cats = {c["类别"] for c, _ in hits}
        if len(cats) < 4:
            thin.append((t["主题"], sorted(cats)))
    if thin:
        for name, cats in thin:
            print("  ! %-10s 只命中 %d 类：%s" % (name, len(cats), "、".join(cats)))
    else:
        print("  全部主题 top8 覆盖 ≥4 类")

    print("=" * 72)
    print("三、跨主题污染（不指定 topic，全库检索）")
    probes = [
        ("凸透镜 物距 像距 焦距", "凸透镜成像"),
        ("冒泡排序 比较 交换 轮次", "冒泡排序"),
        ("等高线 山脊 山谷 剖面", "等高线剖面"),
        ("光合作用 遮光 碘液 淀粉", "光合作用"),
        ("金属活动性 置换 稀盐酸", "金属活动性"),
        ("勾股定理 直角三角形 斜边", "勾股定理"),
    ]
    bad = 0
    for q, want in probes:
        hits = kb.search(q, top_k=5)
        top_topic = hits[0][0]["主题"] if hits else "无"
        ok = top_topic == want
        bad += 0 if ok else 1
        print("  %s %-22s → %s" % ("✓" if ok else "✗", q[:12], top_topic))

    print("=" * 72)
    print("片段总数 %d，主题数 %d" % (len(kb.chunks), len(kb.topics())))
    return 0 if not miss and not thin and not bad else 1


if __name__ == "__main__":
    sys.exit(main())
