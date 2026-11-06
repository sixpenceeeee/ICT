# -*- coding: utf-8 -*-
"""
retrieval_agent.py —— 知识检索 Agent

它的工作不是"搜一下"，而是三步：
    ① 查询规划：把需求 JSON 翻译成 5 条互补的检索式（主题 / 变量 / 规范 / 交互 / 安全）
    ② 多路召回 + 融合：每条检索式各搜一批，用 RRF 算法合并排序
    ③ 组装知识包：按"课标依据 / 教材内容 / 实验规范 / 安全约束 / 交互设计"分类打包
                   交给下游的"教学工具生成 Agent"直接使用

用法：
    python retrieval_agent.py                                  # 用内置示例需求
    python retrieval_agent.py --req ../01_single_agent/output/需求_xxx.json
    python retrieval_agent.py "生成一个可以改变电阻和电压的电路实验"   # 直接给原始需求
"""

import argparse
import json
import os
import re
import sys

from kb import KnowledgeBase

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 主题配置放在项目根目录，02 / 04 共用一份，加实验时只改 topics.py
sys.path.insert(0, os.path.dirname(BASE_DIR))
from topics import detect_topic, profile_of  # noqa: E402

OUTPUT_DIR = os.path.join(BASE_DIR, "output")

# 知识包按这个顺序排列，方便下游按需取用
CATEGORY_ORDER = ["课标依据", "教材内容", "实验规范", "安全约束", "交互设计"]

DEMO_REQUIREMENT = {
    "学科": "物理",
    "年级": "初中九年级",
    "实验主题": "欧姆定律：电压、电阻与电流的关系",
    "学习目标": [
        "理解电压是推动电流的原因，电阻是对电流的阻碍",
        "能通过调节滑动变阻器改变电阻，观察电流变化",
        "能用 I=U/R 解释观察到的现象",
    ],
    "核心变量": [
        {"名称": "电压 U", "范围": "1~6 V", "单位": "V"},
        {"名称": "电阻 R", "范围": "5~50 Ω", "单位": "Ω"},
    ],
    "交互要求": [
        "拖动滑块改变电压和电阻，实时刷新电流数值",
        "用柱状图直观对比电流大小",
        "电流过大时给出安全提示",
    ],
    "技术要点": "单文件 HTML，用原生 JS 计算并绘制 Canvas 图表，不依赖任何 CDN",
    "风险点": ["电压过高可能烧毁元件，需要上限提示"],
}


# ============ ① 查询规划 ============

def build_queries(req, topic=None):
    """把结构化需求拆成多条检索式。

    为什么要多条？因为一个查询只能命中一个"语义方向"。
    "欧姆定律 电压 电阻" 能搜到教材内容，但搜不到实验安全规范。
    拆成 6 条分别搜，覆盖面完全不同——这是检索 Agent 和普通搜索框的关键差别。

    后三条（规范 / 安全 / 交互）的措辞不能写死成电路术语，
    否则浮力实验会去搜"接线 电表 滑动变阻器"，全落空。
    这部分措辞放在 topics.py 的主题配置里，换实验只换配置。
    """
    subject = req.get("学科", "")
    grade = req.get("年级", "")
    topic_name = req.get("实验主题", "")

    # 冒号后面的部分往往更具体，例如"欧姆定律：电压、电阻与电流的关系" → "电压、电阻与电流的关系"
    topic_tail = re.split(r"[：:]", topic_name)[-1].strip() if topic_name else ""

    var_names = " ".join(v.get("名称", "") for v in req.get("核心变量", []))

    profile = profile_of(topic)
    queries = [
        "%s %s %s" % (subject, grade, topic_name),
        topic_tail or topic_name,
        "%s 关系 规律 结论" % var_names,
    ] + list(profile["检索侧重"])

    # 去空、去重，保持顺序
    seen, result = set(), []
    for q in queries:
        q = q.strip()
        if q and q not in seen:
            seen.add(q)
            result.append(q)
    return result


# ============ ② 多路召回 + RRF 融合 ============

def retrieve(kb, queries, per_query=8, final_k=12, rrf_k=60, per_cat_min=2, topic=None):
    """每条检索式各召回一批，然后用两种信号融合排序。

    【第零步：按主题圈定范围】
        知识库里同时有电路和浮力两套材料。不先过滤，
        "实验 规范"这种查询会把另一个实验的规范也召回来，
        知识包就串了。topic 给定时只在该主题内检索。

    【信号一：RRF（倒数排名融合）】
        一条片段在越多查询里排得越前，分越高。反映"通用性"。
        好处：不需要把不同查询的分数归一化，只看排第几。

    【信号二：查询内相对得分】
        这条片段在自己那批结果里，离最高分有多近（0~1）。反映"精准度"。

    【为什么要两个都用】
        只用 RRF 会出事：像"学生常见错误"这种通用片段会被 5 条查询同时命中，
        分数很高；而"电表的使用"只被"实验规范"这一条查询命中，排第 1 却被挤掉。
        混入相对得分后，"在某条查询里排第一"的价值就被保住了。
        最终分 = 0.5 × RRF 归一化 + 0.5 × 相对得分。

    【类别覆盖保障】
        最后再保证每个类别至少 per_cat_min 条，避免某一类知识整体缺席。
    """
    merged = {}

    for q in queries:
        hits = kb.search(q, top_k=per_query, topic=topic)
        q_max = hits[0][1] if hits and hits[0][1] > 0 else 1.0

        for rank, (chunk, bm25_score) in enumerate(hits, 1):
            if bm25_score <= 0:
                continue
            item = merged.setdefault(chunk["id"], {
                "chunk": chunk,
                "rrf": 0.0,
                "rel": 0.0,
                "bm25_best": 0.0,
                "命中查询": [],
            })
            item["rrf"] += 1.0 / (rrf_k + rank)
            item["rel"] = max(item["rel"], bm25_score / q_max)
            item["bm25_best"] = max(item["bm25_best"], bm25_score)
            item["命中查询"].append(q)

    if not merged:
        return []

    # 归一化 RRF（除以本批次最大值），再和相对得分各占一半
    rrf_max = max(v["rrf"] for v in merged.values())
    for item in merged.values():
        item["score"] = 0.5 * (item["rrf"] / rrf_max) + 0.5 * item["rel"]

    ranked = sorted(merged.values(), key=lambda x: x["score"], reverse=True)

    # 第一步：每个类别先保底，防止某一类知识整体缺席
    chosen, chosen_ids = [], set()
    for _ in range(per_cat_min):
        for cat in CATEGORY_ORDER:
            best = next((r for r in ranked
                         if r["chunk"]["类别"] == cat and r["chunk"]["id"] not in chosen_ids), None)
            if best:
                chosen.append(best)
                chosen_ids.add(best["chunk"]["id"])

    # 第二步：剩余名额按综合分从高到低补满
    for item in ranked:
        if len(chosen) >= final_k:
            break
        if item["chunk"]["id"] not in chosen_ids:
            chosen.append(item)
            chosen_ids.add(item["chunk"]["id"])

    # 第三步：按综合分重新排序，保证输出的顺序仍然是"最相关在前"
    return sorted(chosen, key=lambda x: x["score"], reverse=True)


# ============ ③ 组装知识包 ============

def build_pack(req, ranked):
    """把命中的片段按类别归拢，形成下游可以直接吃的结构。"""
    pack = {cat: [] for cat in CATEGORY_ORDER}
    citations = []

    for item in ranked:
        c = item["chunk"]
        cat = c["类别"] if c["类别"] in pack else "其他"
        pack.setdefault(cat, []).append({
            "片段": c["id"],
            "章节": c["章节"],
            "要点": c["内容"],
        })
        citations.append({
            "片段": c["id"],
            "类别": c["类别"],
            "来源": c["来源"],
            "章节": c["章节"],
            "命中查询数": len(item["命中查询"]),
        })

    return pack, citations


# ============ 主流程 ============

def load_requirement(argv_input, req_path):
    if req_path:
        with open(req_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # 兼容 01 阶段存的文件格式 {input, output, meta}
        return data.get("output", data), data.get("input", "")
    if argv_input:
        return {"实验主题": argv_input, "学科": "物理", "年级": "初中九年级", "核心变量": []}, argv_input
    return DEMO_REQUIREMENT, "（内置示例）"


def pretty_print(req, queries, ranked, pack, topic=None):
    print("")
    print("=" * 62)
    print("检索需求  %s / %s / %s" % (req.get("学科", ""), req.get("年级", ""), req.get("实验主题", "")))
    print("主题范围  %s" % (topic or "未识别（全库检索）"))
    print("-" * 62)
    print("查询规划（%d 条）" % len(queries))
    for i, q in enumerate(queries, 1):
        print("  Q%d  %s" % (i, q))
    print("-" * 62)
    print("命中片段（%d 条）" % len(ranked))
    for item in ranked:
        c = item["chunk"]
        print("  %s  %-6s %-20s 综合分 %.2f  命中 %d 路"
              % (c["id"], c["类别"], c["章节"][:20], item["score"], len(item["命中查询"])))
    print("-" * 62)
    print("知识包")
    for cat in CATEGORY_ORDER:
        items = pack.get(cat, [])
        if not items:
            continue
        print("  【%s】%d 条" % (cat, len(items)))
        for it in items:
            print("      · %s：%s" % (it["章节"], it["要点"][:40].replace("\n", " ") + "…"))
    print("=" * 62)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("text", nargs="*", help="直接给一句教学需求")
    parser.add_argument("--req", help="读取 01 阶段生成的需求 JSON")
    parser.add_argument("--topk", type=int, default=12, help="最终保留多少个知识片段")
    parser.add_argument("--topic", help="手动指定知识主题（默认从需求自动识别）")
    args = parser.parse_args()

    req, raw_input = load_requirement(" ".join(args.text).strip(), args.req)

    kb = KnowledgeBase()
    print("知识库已加载：%d 个片段，主题 %s" % (len(kb.chunks), "、".join(kb.topics())))

    # 主题识别：用主题词 + 学习目标 + 变量名判断，避免只靠标题一两个字误判
    if args.topic:
        topic = args.topic
    else:
        probe = " ".join(
            [req.get("实验主题", "")]
            + [str(g) for g in req.get("学习目标", [])]
            + [v.get("名称", "") for v in req.get("核心变量", [])]
        )
        topic = detect_topic(probe)

    if topic and topic in kb.by_topic:
        print("识别主题：%s（该主题知识 %d 个片段）" % (topic, len(kb.by_topic[topic])))
    else:
        print("未识别出主题，将在全部知识中检索（结果可能串主题）")
        topic = topic or None

    queries = build_queries(req, topic)
    ranked = retrieve(kb, queries, final_k=args.topk, topic=topic)
    pack, citations = build_pack(req, ranked)

    pretty_print(req, queries, ranked, pack, topic)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    name = re.sub(r'[\\/:*?"<>|\s]+', "_", raw_input or req.get("实验主题", "知识包"))[:24]
    path = os.path.join(OUTPUT_DIR, "知识包_%s.json" % name)

    payload = {
        "input": raw_input,
        "主题": topic,
        "requirement": req,
        "queries": queries,
        "knowledge_pack": pack,
        "citations": citations,
        "hits": [
            {
                "片段": it["chunk"]["id"],
                "类别": it["chunk"]["类别"],
                "章节": it["chunk"]["章节"],
                "综合分": round(it["score"], 4),
                "相对得分": round(it["rel"], 4),
                "命中查询数": len(it["命中查询"]),
                "内容": it["chunk"]["内容"],
            }
            for it in ranked
        ],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print("\n知识包已保存：%s" % path)


if __name__ == "__main__":
    main()
