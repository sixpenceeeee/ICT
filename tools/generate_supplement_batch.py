# -*- coding: utf-8 -*-
"""生成第一批生地信计算型页面，不调用大模型。"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "03_generator_agent"))
import generator_agent as generator  # noqa: E402


CASES = [
    ("biology-enzyme", "生物", "高中", "酶与细胞代谢", ["观察底物浓度、温度和 pH 对酶促反应速率的影响。", "区分相对速率模型与真实实验测量。"]),
    ("biology-respiration", "生物", "初中", "人体呼吸与气体交换", ["理解潮气量、呼吸频率与每分通气量的关系。", "观察气体交换模型中的参数变化。"]),
    ("biology-ecosystem-foodweb", "生物", "小学/初中", "生态系统与食物链", ["观察能量沿食物链单向流动并逐级递减。", "区分教学近似传递效率与真实生态系统数据。"]),
    ("geography-scale-distance", "地理", "小学/初中", "比例尺与地图距离", ["掌握数字比例尺与实际距离的换算。", "检查单位换算和测距结果是否一致。"]),
    ("geography-climate-reading", "地理", "初中", "世界气候判读", ["从气温曲线和降水数据计算年较差、年降水量。", "按气温与降水组合进行初步判读。"]),
    ("geography-population-resources", "地理", "小学/初中", "人口密度与资源统计", ["理解人口总量、土地面积与人口密度的关系。", "同时关注统计单位、年份和数据范围。"]),
    ("informatics-binary-representation", "信息科技", "小学/初中", "信息表示与二进制", ["理解位权、二进制与十进制之间的关系。", "观察位数变化对可表示状态数和字节数的影响。"]),
    ("informatics-data-visualization", "信息科技", "小学/初中", "数据可视化与统计", ["比较平均数、中位数和数据范围。", "让数据表、图示和统计结果保持同源。"]),
    ("informatics-sensor-control", "信息科技", "小学/初中", "传感器与机器人控制", ["理解传感器、阈值和执行器之间的反馈关系。", "计算采样频率并观察阈值切换。"]),
]


def main():
    out_root = os.path.join(ROOT, "runs", "supplement_batch")
    rows = []
    for scene_id, subject, grade, title, goals in CASES:
        output_dir = os.path.join(out_root, scene_id)
        os.makedirs(output_dir, exist_ok=True)
        generator.OUTPUT_DIR = output_dir
        req = {
            "学科": subject,
            "年级": grade,
            "实验名称": title,
            "实验主题": title,
            "学习目标": goals,
            "核心变量": [],
            "交互要求": ["真实可见控件", "参数变化后重新求解并刷新图示与读数"],
            "技术要点": "统一场景配置、组件组合、确定性求解器和记录表",
            "风险点": "仅用于教学模型；生物页面不替代真实实验，地理页面不替代现实决策，信息科技页面不连接真实系统",
        }
        sections, meta = generator.generate(req, {}, template_only=True)
        html_path, meta_path, zip_path = generator.save(sections, req, meta)
        rows.append({"scene_id": scene_id, "title": title, "subject": subject,
                     "generation_pass": bool(meta.get("生成契约通过")),
                     "problems": meta.get("问题", []), "html": html_path,
                     "meta": meta_path, "zip": zip_path})
        print(scene_id, "PASS" if meta.get("生成契约通过") else "FAIL", html_path)
    report = os.path.join(out_root, "batch_report.json")
    with open(report, "w", encoding="utf-8") as f:
        json.dump({"pages": rows, "passed": sum(1 for r in rows if r["generation_pass"]),
                   "failed": sum(1 for r in rows if not r["generation_pass"])},
                  f, ensure_ascii=False, indent=2)
    print("REPORT", report)


if __name__ == "__main__":
    main()
