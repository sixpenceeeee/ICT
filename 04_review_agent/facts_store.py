# -*- coding: utf-8 -*-
"""教材事实库、来源注册表与场景映射的统一读写和校验。

该模块只处理结构化事实和来源定位信息，不下载或复制教材正文。旧版
``facts.json`` 仍由审查器的 J8 兼容逻辑读取；新流水线使用本模块读取
``facts_registry.json``、``source_registry.json`` 和 ``scene_fact_map.json``。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping


BASE_DIR = Path(__file__).resolve().parent
FACTS_REGISTRY_PATH = BASE_DIR / "facts_registry.json"
SOURCE_REGISTRY_PATH = BASE_DIR / "source_registry.json"
SCENE_FACT_MAP_PATH = BASE_DIR / "scene_fact_map.json"

APPROVED_REVIEW_STATUSES = {"教研复核通过", "教师审核通过", "复核通过", "approved"}
VERIFIED_SOURCE_STATUSES = {"已核验", "核验通过", "verified"}

LEGACY_SCENE_ALIASES = {
    "buoyancy": "physics-buoyancy",
    "thin_lens": "physics-thin-lens",
    "plane_mirror": "physics-planeMirror",
    "wave_propagation": "physics-wavePropagation",
    "pulley_system": "physics-pulleySystem",
    "quadratic": "math-quadratic",
    "right_triangle": "math-rightTriangle",
    "descriptive_stats": "math-descriptiveStats",
}


def load_json(path: str | Path, default: Any) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return default


def _records(data: Any, keys: Iterable[str]) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in keys:
            value = data.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
    return []


def load_facts(path: str | Path = FACTS_REGISTRY_PATH) -> list[dict[str, Any]]:
    return _records(load_json(path, {}), ("facts", "事实", "条目"))


def load_sources(path: str | Path = SOURCE_REGISTRY_PATH) -> list[dict[str, Any]]:
    return _records(load_json(path, {}), ("sources", "来源", "条目"))


def load_scene_fact_map(path: str | Path = SCENE_FACT_MAP_PATH) -> list[dict[str, Any]]:
    return _records(load_json(path, {}), ("scene_fact_map", "scene_fact_maps", "映射"))


def index_by(records: Iterable[Mapping[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {str(item.get(key)): dict(item) for item in records if item.get(key)}


def resolve_scene_id(scene_id: str | None, scene_index: Mapping[str, Any]) -> str:
    requested = str(scene_id or "")
    if requested in scene_index:
        return requested
    alias = LEGACY_SCENE_ALIASES.get(requested)
    if alias and alias in scene_index:
        return alias
    for candidate in (f"math-{requested}", f"physics-{requested}", f"chemistry-{requested}"):
        if candidate in scene_index:
            return candidate
    return requested


def review_status(item: Mapping[str, Any]) -> str:
    review = item.get("review")
    if isinstance(review, Mapping):
        return str(review.get("status") or "待教师审核")
    return str(item.get("审核状态") or item.get("review_status") or "待教师审核")


def source_status(item: Mapping[str, Any]) -> str:
    return str(item.get("source_status") or item.get("状态") or "待核验")


def is_teacher_reviewed(item: Mapping[str, Any]) -> bool:
    return review_status(item) in APPROVED_REVIEW_STATUSES


def is_source_verified(item: Mapping[str, Any]) -> bool:
    return source_status(item) in VERIFIED_SOURCE_STATUSES


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(x) for x in value if x is not None]


def validate_registry(
    facts: Iterable[Mapping[str, Any]],
    sources: Iterable[Mapping[str, Any]],
    scene_maps: Iterable[Mapping[str, Any]],
) -> list[str]:
    """返回结构问题；空列表表示结构校验通过。"""
    issues: list[str] = []
    fact_list = [dict(x) for x in facts]
    source_list = [dict(x) for x in sources]
    map_list = [dict(x) for x in scene_maps]
    fact_ids = [str(x.get("fact_id") or "") for x in fact_list]
    source_ids = [str(x.get("source_id") or "") for x in source_list]
    map_ids = [str(x.get("scene_id") or "") for x in map_list]
    for label, ids in (("fact_id", fact_ids), ("source_id", source_ids), ("scene_id", map_ids)):
        seen: set[str] = set()
        for value in ids:
            if not value:
                issues.append(f"缺少 {label}")
            elif value in seen:
                issues.append(f"重复 {label}: {value}")
            seen.add(value)
    source_index = set(source_ids)
    map_index = set(map_ids)
    for fact in fact_list:
        fid = fact.get("fact_id")
        refs = _as_list(fact.get("source_refs"))
        if not refs:
            issues.append(f"事实无来源: {fid}")
        for ref in refs:
            if ref not in source_index:
                issues.append(f"事实引用不存在的来源: {fid} -> {ref}")
        if is_teacher_reviewed(fact) and not refs:
            issues.append(f"无来源事实不能标记已审核: {fid}")
        include = set(_as_list(fact.get("must_include")))
        forbidden = set(_as_list(fact.get("must_not_include")))
        overlap = include & forbidden
        for term in sorted(overlap):
            issues.append(f"must_include 与 must_not_include 冲突: {fid} -> {term}")
    for scene_map in map_list:
        for fid in _as_list(scene_map.get("fact_ids")):
            if fid not in set(fact_ids):
                issues.append(f"场景引用不存在的事实: {scene_map.get('scene_id')} -> {fid}")
    return issues


def _terms(value: Any) -> list[str]:
    return [x for x in _as_list(value) if x]


def check_page_facts(
    page_text: str,
    scene_id: str | None,
    facts: Iterable[Mapping[str, Any]],
    sources: Iterable[Mapping[str, Any]],
    scene_maps: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """对页面做事实、来源、安全和教师审核状态检查。

    ``facts_pass`` 只表示页面内容匹配机器事实约束；来源核验和教师审核
    单独列出，不能被机器匹配替代。
    """
    fact_index = index_by(facts, "fact_id")
    source_index = index_by(sources, "source_id")
    map_index = index_by(scene_maps, "scene_id")
    requested_sid = str(scene_id or "")
    sid = resolve_scene_id(requested_sid, map_index)
    scene_map = map_index.get(sid)
    result: dict[str, Any] = {
        "scene_id": sid,
        "requested_scene_id": requested_sid,
        "fact_ids": [],
        "facts_pass": False,
        "facts_missing": False,
        "source_missing": False,
        "forbidden_term_found": False,
        "safety_missing": False,
        "teacher_review_pending": False,
        "publish_allowed": False,
        "coverage_status": "待补事实",
        "missing_topics": [],
        "missing_terms": [],
        "forbidden_terms": [],
        "missing_source_refs": [],
        "unverified_sources": [],
    }
    if not scene_map:
        result["facts_missing"] = True
        result["missing_topics"] = ["场景事实映射"]
        result["safety_missing"] = True
        return result
    fact_ids = _terms(scene_map.get("fact_ids"))
    result["fact_ids"] = fact_ids
    result["coverage_status"] = str(scene_map.get("coverage_status") or "待补事实")
    if not fact_ids:
        result["facts_missing"] = True
        result["safety_missing"] = True
        result["missing_topics"] = _terms(scene_map.get("missing_topics")) or ["核心事实", "安全边界"]
        return result

    missing_terms: list[str] = []
    forbidden_terms: list[str] = []
    missing_refs: list[str] = []
    unverified_sources: list[str] = []
    safety_missing = False
    teacher_pending = False
    for fid in fact_ids:
        fact = fact_index.get(fid)
        if not fact:
            result["facts_missing"] = True
            result["missing_topics"].append(f"事实 {fid}")
            continue
        for term in _terms(fact.get("must_include")):
            if term not in page_text:
                missing_terms.append(term)
        for term in _terms(fact.get("must_not_include")):
            if term and term in page_text:
                forbidden_terms.append(term)
        boundaries = _terms(fact.get("safety_boundary"))
        if boundaries and not any(term in page_text for term in boundaries):
            safety_missing = True
        if not boundaries:
            safety_missing = True
        refs = _terms(fact.get("source_refs"))
        if not refs:
            missing_refs.append(fid)
        for ref in refs:
            source = source_index.get(ref)
            if not source:
                missing_refs.append(ref)
            elif not is_source_verified(source):
                unverified_sources.append(ref)
        if not is_teacher_reviewed(fact):
            teacher_pending = True
    result["missing_terms"] = sorted(set(missing_terms))
    result["forbidden_terms"] = sorted(set(forbidden_terms))
    result["missing_source_refs"] = sorted(set(missing_refs))
    result["unverified_sources"] = sorted(set(unverified_sources))
    result["forbidden_term_found"] = bool(forbidden_terms)
    result["safety_missing"] = safety_missing
    result["teacher_review_pending"] = teacher_pending
    if missing_terms:
        result["facts_missing"] = True
    result["facts_pass"] = bool(
        fact_ids and not result["facts_missing"] and not result["forbidden_term_found"] and
        not result["safety_missing"] and not result["missing_source_refs"]
    )
    result["source_missing"] = bool(missing_refs or unverified_sources)
    result["publish_allowed"] = bool(
        result["facts_pass"] and not result["source_missing"] and
        not teacher_pending and result["coverage_status"] == "完整覆盖"
    )
    return result


def slug_terms(value: str) -> list[str]:
    """用于场景—事实迁移的保守关键词拆分，不承担科学判断。"""
    return [x for x in re.split(r"[|、，,；;\s]+", value or "") if len(x) >= 2]

