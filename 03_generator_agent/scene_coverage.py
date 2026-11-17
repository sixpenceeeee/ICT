# -*- coding: utf-8 -*-
"""Build the cross-subject scene coverage matrix."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import scene_registry  # noqa: E402
from supplement_page_templates import CATALOG_PROFILES  # noqa: E402
from solvers.rule_state import display_rule_pack  # noqa: E402


def build_coverage():
    rows = []
    for skeleton in scene_registry.SCENE_SKELETONS:
        if skeleton.get("subject") not in {"数学", "物理", "化学", "生物", "地理", "信息科技"}:
            continue
        scene_id = skeleton["id"]
        config = scene_registry.scene_config(scene_id)
        solver_api = config.get("solver_api") or skeleton.get("solver_api")
        mode = config.get("mode") or ("计算型" if solver_api else "展示型")
        rule_id = display_rule_pack(skeleton).get("rule_id")
        has_model = bool(skeleton.get("lesson_model") or solver_api or rule_id in CATALOG_PROFILES or scene_id == "physics-optics-bench")
        model_kind = "domain_solver" if solver_api or skeleton.get("lesson_model") else ("law_model" if scene_id == "physics-optics-bench" else ("profile_model" if rule_id in CATALOG_PROFILES else "generic"))
        rows.append({
            "scene_id": scene_id,
            "subject": skeleton.get("subject", "通用"),
            "title": (skeleton.get("lesson_model") or {}).get("title", scene_id),
            "mode": mode,
            "solver_api": solver_api,
            "draw_api": config.get("api") or skeleton.get("api"),
            "patterns": config.get("patterns", skeleton.get("patterns", "")),
            "components": config.get("components", []),
            "required": config.get("required", []),
            "config_complete": all(key in config for key in ("patterns", "layout", "controls", "visual_type", "mode")),
            "solver_ready": bool(solver_api) if mode == "计算型" else True,
            "model_configured": has_model,
            "model_kind": model_kind,
            "review_status": "待生成" if mode == "计算型" else "已接入配置模型",
        })
    return rows


def main():
    rows = build_coverage()
    summary = {}
    for row in rows:
        subject = row["subject"]
        summary.setdefault(subject, {"total": 0, "computable": 0, "display_only": 0, "config_complete": 0, "model_configured": 0, "domain_solver": 0, "profile_model": 0, "law_model": 0})
        summary[subject]["total"] += 1
        summary[subject]["computable"] += row["mode"] == "计算型"
        summary[subject]["display_only"] += row["mode"] == "展示型"
        summary[subject]["config_complete"] += row["config_complete"]
        summary[subject]["model_configured"] += row["model_configured"]
        summary[subject][row["model_kind"]] = summary[subject].get(row["model_kind"], 0) + 1
    report = {"summary": summary, "total": len(rows), "scenes": rows}
    output = ROOT.parent / "04_review_agent" / "output" / "scene_coverage_report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "summary": summary, "total": len(rows)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
