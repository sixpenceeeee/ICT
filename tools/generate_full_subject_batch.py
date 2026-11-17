# -*- coding: utf-8 -*-
"""批量生成生物、地理、信息科技全部场景页面。"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN = os.path.join(ROOT, "03_generator_agent")
sys.path.insert(0, GEN)
import generator_agent as generator  # noqa: E402


SUBJECTS = {"生物", "地理", "信息科技"}
CONFIG_DIR = os.path.join(GEN, "scenes")


def load_scenes():
    merged = {}
    for name in sorted(os.listdir(CONFIG_DIR)):
        if not name.endswith(".json"):
            continue
        with open(os.path.join(CONFIG_DIR, name), encoding="utf-8") as f:
            merged.update(json.load(f))
    return [(sid, cfg) for sid, cfg in merged.items() if cfg.get("subject") in SUBJECTS]


def title_for(scene_id, cfg):
    return str(cfg.get("title") or str(cfg.get("patterns") or scene_id).split("|")[0])


def main():
    out_root = os.path.join(ROOT, "runs", "full_subject_batch")
    rows = []
    for scene_id, cfg in load_scenes():
        title = title_for(scene_id, cfg)
        subject = cfg["subject"]
        goals = [
            "识别%s场景中的关键对象、过程或数据关系。" % title,
            "通过统一组件调整参数，观察同一场景状态的变化并记录结果。",
        ]
        req = {
            "场景ID": scene_id,
            "学科": subject,
            "年级": "小学/初中/高中",
            "实验名称": title,
            "实验主题": title,
            "学习目标": goals,
            "核心变量": [],
            "交互要求": ["真实可见控件", "参数变化后刷新同一图示、结果卡和记录表"],
            "技术要点": "统一场景配置、组件组合、展示状态与自动验收",
            "风险点": "展示型场景仅用于教学示意；不替代真实实验、实时地图或现实系统",
        }
        output_dir = os.path.join(out_root, scene_id)
        os.makedirs(output_dir, exist_ok=True)
        generator.OUTPUT_DIR = output_dir
        sections, meta = generator.generate(req, {}, template_only=True)
        html_path, meta_path, zip_path = generator.save(sections, req, meta)
        rows.append({
            "scene_id": scene_id, "subject": subject, "title": title,
            "mode": cfg.get("mode", "展示型"), "solver_api": cfg.get("solver_api"),
            "generation_pass": bool(meta.get("生成契约通过")),
            "problems": meta.get("问题", []), "html": html_path,
            "meta": meta_path, "zip": zip_path,
        })
        print(scene_id, "PASS" if meta.get("生成契约通过") else "FAIL", html_path)
    report = os.path.join(out_root, "batch_report.json")
    with open(report, "w", encoding="utf-8") as f:
        json.dump({"pages": rows, "total": len(rows),
                   "passed": sum(1 for r in rows if r["generation_pass"]),
                   "failed": sum(1 for r in rows if not r["generation_pass"])},
                  f, ensure_ascii=False, indent=2)
    print("REPORT", report)


if __name__ == "__main__":
    main()
