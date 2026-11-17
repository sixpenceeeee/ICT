# -*- coding: utf-8 -*-
"""生成六科全部无定量求解器场景的规则/状态求解器页面。"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "03_generator_agent"))
import generator_agent as generator  # noqa: E402
import scene_registry  # noqa: E402


SUBJECTS = {"数学", "物理", "化学", "生物", "地理", "信息科技"}


def title_for(scene):
    patterns = str(scene.get("patterns") or scene.get("id") or "展示场景")
    return patterns.split("|")[0]


def main():
    out_root = os.path.join(ROOT, "runs", "display_rule_batch")
    rows = []
    scenes = [s for s in scene_registry.SCENE_SKELETONS
              if s.get("subject") in SUBJECTS and not s.get("solver_api")]
    for scene in scenes:
        scene_id = scene["id"]
        title = title_for(scene)
        req = {
            "场景ID": scene_id,
            "学科": scene.get("subject"),
            "年级": "小学/初中/高中",
            "实验名称": title,
            "实验主题": title,
            "学习目标": ["识别场景中的关键对象、状态和关系。", "通过规则状态变化观察并记录教学示意。"],
            "交互要求": ["调整阶段和示意强度", "图示、状态卡和记录表同步更新", "支持重置"],
            "技术要点": "展示型规则/状态求解器、组件组合、确定性 Canvas 渲染",
            "风险点": "展示型教学模型，不替代真实实验、实时地图或现实系统",
        }
        output_dir = os.path.join(out_root, scene_id)
        os.makedirs(output_dir, exist_ok=True)
        generator.OUTPUT_DIR = output_dir
        sections, meta = generator.generate(req, {}, template_only=True)
        html_path, meta_path, zip_path = generator.save(sections, req, meta)
        rows.append({"scene_id": scene_id, "subject": scene.get("subject"), "title": title,
                     "generation_pass": bool(meta.get("生成契约通过")), "problems": meta.get("问题", []),
                     "html": html_path, "meta": meta_path, "zip": zip_path})
        print(scene_id, "PASS" if meta.get("生成契约通过") else "FAIL", html_path)
    report = os.path.join(out_root, "batch_report.json")
    with open(report, "w", encoding="utf-8") as f:
        json.dump({"total": len(rows), "passed": sum(x["generation_pass"] for x in rows),
                   "failed": sum(not x["generation_pass"] for x in rows), "pages": rows},
                  f, ensure_ascii=False, indent=2)
    print("REPORT", report)


if __name__ == "__main__":
    main()
