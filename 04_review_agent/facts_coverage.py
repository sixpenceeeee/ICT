# -*- coding: utf-8 -*-
"""生成教材事实库覆盖报告。"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from facts_store import (
    FACTS_REGISTRY_PATH,
    SCENE_FACT_MAP_PATH,
    SOURCE_REGISTRY_PATH,
    check_page_facts,
    is_source_verified,
    is_teacher_reviewed,
    load_facts,
    load_scene_fact_map,
    load_sources,
    validate_registry,
)


ROOT = Path(__file__).resolve().parent.parent
PAGES_ROOTS = [ROOT / "runs" / "all_scene_pages", ROOT / "03_generator_agent" / "output"]
JSON_OUT = Path(__file__).resolve().parent / "facts_coverage_report.json"
MD_OUT = Path(__file__).resolve().parent / "facts_coverage_report.md"


def visible_text(html: str) -> str:
    html = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    html = re.sub(r"<style[\s\S]*?</style>", " ", html, flags=re.I)
    html = re.sub(r"<!--[\s\S]*?-->", " ", html)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def page_scene_id(path: Path) -> str:
    try:
        return path.parent.name
    except Exception:
        return ""


def knowledge_topic_stats() -> tuple[dict[str, int], int]:
    counts: dict[str, set[str]] = defaultdict(set)
    package_total = 0
    source_dir = ROOT / "02_retrieval_agent" / "output"
    subject_alias = {"信息技术": "信息科技"}
    for path in source_dir.glob("知识包_*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        req = data.get("requirement") if isinstance(data, dict) else {}
        req = req if isinstance(req, dict) else {}
        subject = subject_alias.get(str(req.get("学科") or data.get("学科") or ""), str(req.get("学科") or data.get("学科") or ""))
        topic = data.get("主题") or req.get("实验主题")
        if subject and topic:
            package_total += 1
            counts[subject].add(str(topic))
    return {key: len(value) for key, value in sorted(counts.items())}, package_total


def main() -> None:
    facts = load_facts(FACTS_REGISTRY_PATH)
    sources = load_sources(SOURCE_REGISTRY_PATH)
    scene_maps = load_scene_fact_map(SCENE_FACT_MAP_PATH)
    fact_index = {str(x.get("fact_id")): x for x in facts}
    source_index = {str(x.get("source_id")): x for x in sources}
    map_index = {str(x.get("scene_id")): x for x in scene_maps}
    structure_issues = validate_registry(facts, sources, scene_maps)

    subject_fact_counts = Counter(str(x.get("subject") or "未标注") for x in facts)
    subject_scene_counts = Counter(str(x.get("subject") or "未标注") for x in scene_maps)
    knowledge_topics, knowledge_package_total = knowledge_topic_stats()
    fact_source_count = sum(bool(x.get("source_refs")) for x in facts)
    fact_reviewed_count = sum(is_teacher_reviewed(x) for x in facts)
    source_verified_count = sum(is_source_verified(x) for x in sources)
    normalized_claims: dict[str, list[str]] = defaultdict(list)
    for fact in facts:
        claim = re.sub(r"\s+", "", str(fact.get("claim") or "")).lower()
        if claim:
            normalized_claims[claim].append(str(fact.get("fact_id")))
    duplicate_facts = [ids for ids in normalized_claims.values() if len(ids) > 1]
    conflict_facts: list[list[str]] = []
    for i, left in enumerate(facts):
        left_topics = set(str(left.get("topic") or "").split("、"))
        left_forbidden = set(str(x) for x in left.get("must_not_include", []) or [])
        for right in facts[i + 1:]:
            right_topics = set(str(right.get("topic") or "").split("、"))
            if left_topics & right_topics and (set(left.get("must_include", []) or []) & set(right.get("must_not_include", []) or []) or
                                               set(right.get("must_include", []) or []) & left_forbidden):
                conflict_facts.append([str(left.get("fact_id")), str(right.get("fact_id"))])

    scenes_missing_facts: list[str] = []
    scenes_missing_source: list[str] = []
    scenes_pending_source: list[str] = []
    scenes_missing_safety: list[str] = []
    scenes_partial: list[str] = []
    for scene_id, mapping in map_index.items():
        ids = [str(x) for x in mapping.get("fact_ids", [])]
        if not ids or mapping.get("coverage_status") == "待补事实":
            scenes_missing_facts.append(scene_id)
        elif mapping.get("coverage_status") != "完整覆盖":
            scenes_partial.append(scene_id)
        refs = [ref for fid in ids for ref in (fact_index.get(fid, {}).get("source_refs") or [])]
        if not refs or any(ref not in source_index for ref in refs):
            scenes_missing_source.append(scene_id)
        elif any(not is_source_verified(source_index[ref]) for ref in refs):
            scenes_pending_source.append(scene_id)
        if not ids or any(not (fact_index.get(fid, {}).get("safety_boundary") or []) for fid in ids):
            scenes_missing_safety.append(scene_id)

    page_results: list[dict[str, Any]] = []
    forbidden_pages: list[dict[str, Any]] = []
    publish_allowed_pages: list[str] = []
    machine_only_pages: list[str] = []
    pending_review_pages: list[str] = []
    for root in PAGES_ROOTS:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.html")):
            sid = page_scene_id(path)
            if sid not in map_index:
                continue
            try:
                text = visible_text(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError):
                continue
            result = check_page_facts(text, sid, facts, sources, scene_maps)
            item = {"page": str(path), **result}
            page_results.append(item)
            if result["forbidden_term_found"]:
                forbidden_pages.append(item)
            if result["publish_allowed"]:
                publish_allowed_pages.append(str(path))
            elif result["facts_pass"]:
                machine_only_pages.append(str(path))
            if not result["publish_allowed"]:
                pending_review_pages.append(str(path))

    report = {
        "generated_at": "2026-11-13",
        "registry_paths": {
            "facts": str(FACTS_REGISTRY_PATH),
            "sources": str(SOURCE_REGISTRY_PATH),
            "scene_fact_map": str(SCENE_FACT_MAP_PATH),
        },
        "summary": {
            "subject_fact_counts": dict(subject_fact_counts),
            "subject_scene_counts": dict(subject_scene_counts),
            "knowledge_package_total": knowledge_package_total,
            "knowledge_topic_counts": knowledge_topics,
            "fact_total": len(facts),
            "fact_with_source_refs": fact_source_count,
            "fact_teacher_reviewed": fact_reviewed_count,
            "source_total": len(sources),
            "source_verified": source_verified_count,
            "scene_total": len(scene_maps),
            "scene_missing_facts": len(scenes_missing_facts),
            "scene_missing_source": len(scenes_missing_source),
            "scene_pending_source_review": len(scenes_pending_source),
            "scene_missing_safety": len(scenes_missing_safety),
            "scene_partial_coverage": len(scenes_partial),
            "page_total_checked": len(page_results),
            "page_forbidden_term": len(forbidden_pages),
            "page_publish_allowed": len(publish_allowed_pages),
            "page_machine_only_pending_review": len(machine_only_pages),
            "page_pending_teacher_review": len(pending_review_pages),
            "duplicate_fact_groups": len(duplicate_facts),
            "conflicting_fact_pairs": len(conflict_facts),
        },
        "structure_issues": structure_issues,
        "scenes_missing_facts": scenes_missing_facts,
        "scenes_missing_source": scenes_missing_source,
        "scenes_pending_source_review": scenes_pending_source,
        "scenes_missing_safety": scenes_missing_safety,
        "scenes_partial_coverage": scenes_partial,
        "pages_with_forbidden_terms": [
            {"page": x["page"], "scene_id": x["scene_id"], "terms": x["forbidden_terms"]}
            for x in forbidden_pages
        ],
        "duplicate_facts": duplicate_facts,
        "conflicting_facts": conflict_facts,
        "publish_allowed_pages": publish_allowed_pages,
        "machine_only_pages": machine_only_pages,
        "pending_review_pages": pending_review_pages,
        "scene_coverage": scene_maps,
    }
    JSON_OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# 教材事实库来源覆盖报告",
        "",
        "> 本报告只统计已登记的事实、来源和页面匹配结果；机器匹配成功不等于教师审核通过。",
        "",
        "## 总览",
        "",
        f"- 知识包总数：{knowledge_package_total}；按学科去重后的知识主题：{knowledge_topics}",
        f"- 六科教材事实总数：{len(facts)}",
        f"- 已有来源引用的事实：{fact_source_count}",
        f"- 已教师审核的事实：{fact_reviewed_count}",
        f"- 来源总数：{len(sources)}；已核验来源：{source_verified_count}",
        f"- 场景总数：{len(scene_maps)}；已检查页面：{len(page_results)}",
        f"- 可发布页面：{len(publish_allowed_pages)}",
        f"- 仅机器验收、仍待审核页面：{len(machine_only_pages)}",
        f"- 进入待教师审核页面：{len(pending_review_pages)}",
        "",
        "## 六科统计",
        "",
        "| 学科 | 事实数 | 场景数 |",
        "|---|---:|---:|",
    ]
    for subject in ("数学", "物理", "化学", "生物", "地理", "信息科技"):
        lines.append(f"| {subject} | {subject_fact_counts.get(subject, 0)} | {subject_scene_counts.get(subject, 0)} |")
    lines += [
        "",
        "## 待补清单",
        "",
        f"- 缺少事实的场景（{len(scenes_missing_facts)}）：" + ("、".join(scenes_missing_facts) or "无"),
        f"- 缺少来源引用的场景（{len(scenes_missing_source)}）：" + ("、".join(scenes_missing_source) or "无"),
        f"- 来源待核验的场景（{len(scenes_pending_source)}）：" + ("、".join(scenes_pending_source) or "无"),
        f"- 缺少安全边界的场景（{len(scenes_missing_safety)}）：" + ("、".join(scenes_missing_safety) or "无"),
        f"- 页面出现禁止表述（{len(forbidden_pages)}）：" + ("、".join(x["page"] for x in forbidden_pages) or "无"),
        f"- 重复事实组：{len(duplicate_facts)}；冲突事实对：{len(conflict_facts)}",
        "",
        "## 结构校验",
        "",
        f"- 结构问题数：{len(structure_issues)}",
    ]
    if structure_issues:
        lines.extend(f"  - {issue}" for issue in structure_issues)
    lines += [
        "",
        "## 发布判定",
        "",
        "页面只有在事实匹配、来源已核验、无禁止表述、安全边界齐全、事实已教师审核且场景覆盖完整时才允许发布。",
        "",
        f"机器验收通过但仍待来源或教师审核：{len(machine_only_pages)} 个页面。",
    ]
    MD_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

