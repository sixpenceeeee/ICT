# -*- coding: utf-8 -*-
"""
agent.py —— 单 Agent 主程序（需求理解 Agent）

运行方式：
    python agent.py                          # 用内置示例需求跑一遍
    python agent.py "生成一个大气压存在的演示实验"   # 传自己的需求
    python agent.py                          # 不带参数时也可以交互输入

整个 Agent 的全部逻辑，其实就是这个函数：
    agent(需求) = 拼消息 → 调模型 → 解析 JSON → 校验字段 → 存盘
"""

import json
import os
import re
import sys
import time

from llm import call_llm, load_env
from prompts import DEMO_INPUT, REQUIREMENT_SYSTEM_PROMPT

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

# 下游程序依赖的必备字段。少一个就说明模型没听话，需要重试或报错。
REQUIRED_FIELDS = ["学科", "年级", "实验主题", "学习目标", "核心变量", "交互要求", "技术要点", "风险点"]


# ============ 第 1 步：从模型回复里"抠"出 JSON ============

def extract_json(text):
    """模型有时候会好心加一句"好的，这是结果："或者裹上 ```json 围栏。

    所以不能直接 json.loads，要先做一次清洗：找到第一个 { 到最后一个 }。
    """
    text = text.strip()

    # 情况 A：```json ... ``` 围栏
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()

    # 情况 B：前后有废话，只取最外层大括号之间的内容
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]

    return json.loads(text)


# ============ 第 2 步：校验 + 补默认值 ============

def validate(data):
    """字段级校验。缺字段时给默认值并记录，而不是直接崩掉。

    Agent 工程里这一步很关键：模型输出是不可靠的，代码必须兜住。
    """
    missing = [f for f in REQUIRED_FIELDS if f not in data]
    for field in missing:
        if field in ("学习目标", "核心变量", "交互要求", "风险点"):
            data[field] = []
        else:
            data[field] = ""
    return data, missing


# ============ 第 3 步：Agent 本体 ============

def requirement_agent(user_input):
    """一次完整的 Agent 调用。返回 (结构化结果, 元信息)。"""

    messages = [
        {"role": "system", "content": REQUIREMENT_SYSTEM_PROMPT},
        {"role": "user", "content": user_input},
    ]

    started = time.time()
    raw, is_mock = call_llm(messages, temperature=0.2)
    cost = time.time() - started

    data = extract_json(raw)
    data, missing = validate(data)

    meta = {
        "耗时秒": round(cost, 2),
        "假数据": is_mock,
        "缺失字段": missing,
        "原始回复": raw,
    }
    return data, meta


# ============ 第 4 步：存盘 ============

def save_result(user_input, data, meta):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    safe_name = re.sub(r'[\\/:*?"<>|\s]+', "_", user_input)[:20]
    path = os.path.join(OUTPUT_DIR, "需求_%s.json" % safe_name)

    payload = {
        "input": user_input,
        "output": data,
        "meta": {"耗时秒": meta["耗时秒"], "假数据": meta["假数据"], "缺失字段": meta["缺失字段"]},
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path


# ============ 第 5 步：把结果打印得像人看的 ============

def pretty_print(data, meta):
    print("")
    print("=" * 56)
    print("学科年级  %s / %s" % (data["学科"], data["年级"]))
    print("实验主题  %s" % data["实验主题"])
    print("-" * 56)
    print("学习目标")
    for i, item in enumerate(data["学习目标"], 1):
        print("  %d. %s" % (i, item))
    print("核心变量")
    for var in data["核心变量"]:
        print("  · %s：%s（%s）" % (var.get("名称", ""), var.get("范围", ""), var.get("单位", "")))
    print("交互要求")
    for i, item in enumerate(data["交互要求"], 1):
        print("  %d. %s" % (i, item))
    print("技术要点  %s" % data["技术要点"])
    print("风险点")
    for item in data["风险点"]:
        print("  ! %s" % item)
    print("=" * 56)
    print("耗时 %.2fs%s" % (meta["耗时秒"], "  【假数据，未调用真实模型】" if meta["假数据"] else ""))
    if meta["缺失字段"]:
        print("警告：模型漏了这些字段 -> %s" % "、".join(meta["缺失字段"]))
    print("")


# ============ 入口 ============

def main():
    load_env()

    if len(sys.argv) > 1:
        user_input = " ".join(sys.argv[1:]).strip()
    else:
        print("请输入教学需求（直接回车用示例）：")
        user_input = input("> ").strip() or DEMO_INPUT

    print("\n[1/3] 正在调用需求理解 Agent ...")
    data, meta = requirement_agent(user_input)

    print("[2/3] 解析与校验字段 ...")
    print("[3/3] 保存结果 ...")

    path = save_result(user_input, data, meta)
    pretty_print(data, meta)
    print("已保存：%s" % path)

    if meta["假数据"]:
        print("\n提示：现在用的是内置假数据。把 .env.example 复制成 .env，填上 key 就会走真实模型。")


if __name__ == "__main__":
    main()
