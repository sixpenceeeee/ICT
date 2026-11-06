# -*- coding: utf-8 -*-
"""从 seed 数据生成 topics_extra.py（29 个主题的 PROFILE）。

为什么要生成而不是手写：PROFILE 里的关键词、单位组、数值上限、核心公式
和知识库是同一份事实，手写两处必然漂移。这里以 seed 为唯一源。
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import build_kb

FOCUS = {
    "数学": ["课标 要求 内容", "教材 公式 结论 推导", "交互 参数 图像 学生 易错"],
    "物理": ["实验 规范 器材 步骤 操作", "安全 量程 数值 边界 准确", "交互 滑块 读数 学生 易错"],
    "化学": ["实验 现象 方程式 配平", "安全 试剂 有毒 腐蚀 禁止", "交互 选择 观察 学生 易错"],
    "生物": ["实验 步骤 顺序 对照", "安全 材料 显微镜 规范", "交互 观察 识别 学生 易错"],
    "地理": ["图表 判读 计算 过程", "安全 数值 范围 模型 假设", "交互 拖动 读数 学生 易错"],
    "信息科技": ["算法 过程 步骤 状态", "安全 输入 边界 校验", "交互 单步 高亮 学生 易错"],
}


def q(s):
    return '"%s"' % s.replace('"', '\\"')


def main():
    topics = build_kb.load_topics()
    L = []
    a = L.append
    a("# -*- coding: utf-8 -*-")
    a('"""自动生成，勿手改。源数据在 seed/*_kb.py，改完重跑 seed/build_topics.py。"""')
    a("")
    a("EXTRA_PROFILES = {")
    for t in topics:
        a("    %s: {" % q(t["主题"]))
        a("        \"关键词\": [%s]," % ", ".join(q(k) for k in t["关键词"]))
        a("        \"检索侧重\": [%s]," % ", ".join(q(x) for x in FOCUS[t["学科"]]))
        units = t.get("单位组") or []
        if units:
            a("        \"单位组\": [")
            for name, alts in units:
                a("            (%s, [%s])," % (q(name), ", ".join(q(x) for x in alts)))
            a("        ],")
        else:
            a("        \"单位组\": [],")
        caps = t.get("上限") or []
        if caps:
            a("        \"数值上限\": [")
            for c in caps:
                a("            {\"单位\": %s, \"名称\": %s, \"上限\": %s}," % (
                    q(c["单位"]), q(c["名称"]), c["上限"]))
            a("        ],")
        else:
            a("        \"数值上限\": [],")
        a("        \"核心公式\": %s," % q(t["核心公式"]))
        a("        \"公式示例\": %s," % q(t["公式示例"]))
        a("    },")
    a("}")
    a("")

    path = os.path.join(os.path.dirname(ROOT), "topics_extra.py")
    io.open(path, "w", encoding="utf-8").write("\n".join(L))
    print("写入 %s：%d 个主题" % (path, len(topics)))


if __name__ == "__main__":
    main()
