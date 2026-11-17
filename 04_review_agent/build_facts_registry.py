# -*- coding: utf-8 -*-
"""把旧版 facts.json 增量迁移为可追踪事实、来源和场景映射。

迁移只读取现有事实表和场景注册表。来源标题沿用旧事实中的「依据」字段，
不补写页码、网址、出版社或核验日期；这些字段保持空值并标记为「待核验」。
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
REVIEW_DIR = ROOT / "04_review_agent"
FACTS_PATH = REVIEW_DIR / "facts.json"
BACKUP_DIR = REVIEW_DIR / "backups" / date.today().strftime("%Y%m%d")
FACTS_OUT = REVIEW_DIR / "facts_registry.json"
SOURCES_OUT = REVIEW_DIR / "source_registry.json"
MAP_OUT = REVIEW_DIR / "scene_fact_map.json"

sys.path.insert(0, str(ROOT / "03_generator_agent"))
try:
    import scene_registry  # type: ignore
except ImportError:  # pragma: no cover - script is normally run from project root
    scene_registry = None


SUBJECT_PREFIX = {
    "CHE": "chemistry", "PHY": "physics", "BIO": "biology",
    "GEO": "geography", "ICT": "informatics", "MAT": "mathematics",
}

CLAIM_TYPES = {
    "CHE-F-001": "规律", "CHE-F-002": "规律", "CHE-F-003": "规律", "CHE-F-004": "定律",
    "PHY-F-001": "定律", "PHY-F-002": "规律", "PHY-F-003": "定律", "PHY-F-004": "公式",
    "PHY-F-005": "规律", "BIO-F-001": "公式", "BIO-F-002": "规律", "BIO-F-003": "流程",
    "GEO-F-001": "规律", "GEO-F-002": "公式", "GEO-F-003": "规律",
    "ICT-F-001": "规律", "ICT-F-002": "定义", "MAT-F-001": "公式", "MAT-F-002": "规律",
    "MAT-F-003": "定理",
}

GENERIC_MATCH_TERMS = {
    "函数", "图像", "规律", "关系", "实验", "模型", "数据", "主题", "场景",
    "参数", "变化", "公式", "结果", "方法", "过程", "定律", "作用", "计算",
}


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def source_type(title: str) -> str:
    if "课程标准" in title:
        return "课程标准"
    if "人教" in title or "教材" in title or "必修" in title:
        return "教材"
    return "待补证来源"


def canonical_fact_id(legacy_id: str) -> str:
    prefix, _, number = legacy_id.partition("-")
    number = legacy_id.rsplit("-", 1)[-1] if "-" in legacy_id else number
    subject = SUBJECT_PREFIX.get(prefix, "legacy")
    return f"{subject}-fact-{number or hashlib.sha1(legacy_id.encode()).hexdigest()[:8]}"


def grades_for(source: str, subject: str) -> list[str]:
    if "高中" in source:
        return ["高中"]
    if any(x in source for x in ("七年级", "八年级", "九年级", "初中")):
        return ["初中"]
    if "课程标准" in source:
        return ["初中", "高中"]
    return ["初中", "高中"]


def build_sources(legacy_facts: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    source_by_title: dict[str, str] = {}
    sources: list[dict[str, Any]] = []
    for item in legacy_facts:
        title = str(item.get("依据") or "").strip()
        if not title or title in source_by_title:
            continue
        source_id = f"source-legacy-{len(sources) + 1:03d}"
        source_by_title[title] = source_id
        sources.append({
            "source_id": source_id,
            "source_type": source_type(title),
            "subject": item.get("学科", ""),
            "title": title,
            "publisher": "",
            "edition": "",
            "chapter": "",
            "page": "",
            "url": "",
            "retrieved_at": "",
            "source_status": "待核验",
            "copyright_note": "只保存摘要和定位信息，不复制整段教材正文",
            "migration_note": "来源标题由旧 facts.json 的依据字段迁移，尚未完成外部核验",
            "review": {"status": "待教师审核", "reviewer": "", "review_date": "", "notes": ""},
        })
    return sources, source_by_title


def build_facts(legacy_facts: list[dict[str, Any]], source_by_title: dict[str, str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in legacy_facts:
        legacy_id = str(item.get("id") or "").strip()
        if not legacy_id:
            continue
        subject = str(item.get("学科") or "").strip()
        source_title = str(item.get("依据") or "").strip()
        topics = [str(x) for x in item.get("主题", []) if x]
        boundary = (
            "本页为虚拟教学模型，读数和图示用于学习演示，不替代真实实验操作或安全培训。"
            if subject in {"物理", "化学", "生物"}
            else "本页为教学演示模型，结论需结合教材、课程标准和教师指导使用。"
        )
        out.append({
            "fact_id": canonical_fact_id(legacy_id),
            "legacy_fact_id": legacy_id,
            "scene_id": "",
            "subject": subject,
            "grade": grades_for(source_title, subject),
            "unit": topics[0] if topics else "待补单元",
            "topic": "、".join(topics),
            "claim": str(item.get("事实") or "").strip(),
            "claim_type": CLAIM_TYPES.get(legacy_id, "规律"),
            "must_include": list(item.get("必须出现") or []),
            "must_not_include": list(item.get("禁止出现") or []),
            "safety_boundary": [boundary],
            "applicable_stage": "/".join(grades_for(source_title, subject)),
            "source_refs": [source_by_title[source_title]] if source_title in source_by_title else [],
            "review": {
                "status": str(item.get("审核状态") or "待教师审核"),
                "reviewer": "",
                "review_date": "",
                "notes": "保留旧事实表审核状态；来源仍待核验。",
            },
            "version": "1.0.0",
        })
    return out


def scene_terms(scene_id: str, data: dict[str, Any]) -> set[str]:
    raw = " ".join([
        scene_id,
        str(data.get("patterns") or ""),
        " ".join(str(x) for x in data.get("required", []) if x),
        str(data.get("layout") or ""),
        str(data.get("controls") or ""),
    ])
    return {x.lower() for x in re.split(r"[|、，,；;\s_\-]+", raw)
            if len(x) >= 2 and x not in GENERIC_MATCH_TERMS}


def term_in_scene(term: str, raw_scene: str) -> bool:
    term = str(term or "").lower()
    if not term:
        return False
    if re.search(r"[a-z0-9]", term):
        return re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", raw_scene) is not None
    return term in raw_scene


def build_scene_map(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    metadata = dict(getattr(scene_registry, "SCENE_METADATA", {}) if scene_registry else {})
    # 场景注册表之外的默认需求也必须有映射；没有注册元数据时只保留
    # 需求中的学科/主题信息，不根据主题臆造事实。
    req_dir = ROOT / "runs" / "default_scene_requirements"
    for req_path in sorted(req_dir.glob("*.json")):
        try:
            req = json.loads(req_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        metadata.setdefault(req_path.stem, {
            "subject": req.get("学科", ""),
            "patterns": req.get("实验主题", ""),
            "required": req.get("页面模块", []) or [],
            "layout": req.get("实验主题", ""),
            "controls": " ".join(str(x) for x in req.get("交互要求", []) if x),
        })
    maps: list[dict[str, Any]] = []
    for scene_id, data in sorted(metadata.items()):
        terms = scene_terms(scene_id, data)
        raw_scene = " ".join([
            scene_id, str(data.get("patterns") or ""),
            " ".join(str(x) for x in data.get("required", []) if x),
            str(data.get("layout") or ""), str(data.get("controls") or ""),
        ]).lower()
        fact_ids: list[str] = []
        for fact in facts:
            fact_terms = {str(x).lower() for x in fact.get("topic", "").split("、")
                          if x and str(x) not in GENERIC_MATCH_TERMS}
            if fact_terms & terms or any(term_in_scene(term, raw_scene) for term in fact_terms):
                fact_ids.append(str(fact["fact_id"]))
        fact_ids = sorted(set(fact_ids))
        if len(fact_ids) >= 4:
            status = "完整覆盖"
            missing = []
        elif fact_ids:
            status = "部分覆盖"
            missing = ["核心概念事实", "公式或定律事实", "边界条件", "安全边界"]
        else:
            status = "待补事实"
            missing = ["核心概念事实", "公式或定律事实", "边界条件", "安全边界"]
        maps.append({
            "scene_id": scene_id,
            "subject": str(data.get("subject") or ""),
            "topic": str(data.get("patterns") or ""),
            "fact_ids": fact_ids,
            "required_fact_count": 4,
            "coverage_status": status,
            "missing_topics": missing,
            "last_checked": date.today().isoformat(),
            "source": "由现有 facts.json 与场景注册表保守匹配；未匹配部分不做科学推断",
        })
    return maps


def main() -> None:
    if not FACTS_PATH.exists():
        raise SystemExit(f"missing legacy facts: {FACTS_PATH}")
    legacy = json.loads(FACTS_PATH.read_text(encoding="utf-8"))
    legacy_facts = list(legacy.get("条目") or [])
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUP_DIR / "facts.json"
    if not backup_path.exists():
        shutil.copy2(FACTS_PATH, backup_path)
    sources, source_by_title = build_sources(legacy_facts)
    facts = build_facts(legacy_facts, source_by_title)
    scene_maps = build_scene_map(facts)
    write_json(FACTS_OUT, {
        "version": "1.0.0",
        "migration": {"from": "04_review_agent/facts.json", "legacy_backup": str(backup_path),
                       "policy": "保留旧条目；缺少可靠来源定位时标记待核验，不补写页码或网址"},
        "facts": facts,
    })
    write_json(SOURCES_OUT, {"version": "1.0.0", "sources": sources})
    write_json(MAP_OUT, {"version": "1.0.0", "scene_fact_map": scene_maps})
    print(json.dumps({"facts": len(facts), "sources": len(sources), "scenes": len(scene_maps),
                      "subjects": Counter(x.get("subject", "") for x in facts)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

