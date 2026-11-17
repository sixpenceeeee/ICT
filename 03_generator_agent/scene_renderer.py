# -*- coding: utf-8 -*-
"""统一的场景配置与渲染调度。

场景配置只描述场景使用哪个确定性求解器、哪些页面组件和哪些审查元数据。
具体 HTML 仍由现有学科模板生成，保证迁移过程中保留已经验收的页面行为。
"""

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from solvers.law_layers import contract_for


@dataclass(frozen=True)
class SceneSpec:
    scene_id: str
    subject: str
    solver: str
    components: tuple[str, ...]
    required: tuple[str, ...]
    visual_type: str
    mode: str = "展示型"
    config_resolver: Callable[[Mapping[str, Any]], Any] | None = None
    config_serializer: Callable[[Mapping[str, Any]], Any] | None = None


SCENE_SPECS = {
    "chemistry-solubility-ksp": SceneSpec(
        "chemistry-solubility-ksp", "化学", "solveSolubilityEquilibrium",
        ("experiment_stage", "parameter_controls", "result_cards", "particle_diagram", "records_table", "csv_export"),
        ("化学方程式", "离子电荷", "Q 值", "溶液状态", "粒子示意图"), "particle"),
    "chemistry-acid-base-titration": SceneSpec(
        "chemistry-acid-base-titration", "化学", "solveAcidBaseTitration",
        ("experiment_stage", "parameter_controls", "result_cards", "comparison_panel", "records_table", "csv_export"),
        ("滴定装置", "pH", "当量点", "中和方程式"), "apparatus"),
    "chemistry-precipitation-quantitative": SceneSpec(
        "chemistry-precipitation-quantitative", "化学", "solvePrecipitation",
        ("experiment_stage", "parameter_controls", "result_cards", "records_table", "csv_export"),
        ("沉淀化学式", "限量试剂", "净离子方程式", "沉淀质量"), "apparatus"),
    "chemistry-gas-collection": SceneSpec(
        "chemistry-gas-collection", "化学", "solveGasCollection",
        ("experiment_stage", "parameter_controls", "result_cards", "records_table", "csv_export"),
        ("气体制取装置", "限量试剂", "目标气体体积", "水蒸气压修正"), "apparatus"),
    "chemistry-redox-electron-balance": SceneSpec(
        "chemistry-redox-electron-balance", "化学", "solveRedox",
        ("experiment_stage", "parameter_controls", "result_cards", "records_table", "csv_export"),
        ("氧化数变化", "电子守恒", "带电荷离子方程式"), "diagram"),
}


def _load_external_specs():
    root = Path(__file__).resolve().parent / "scenes"
    loaded = {}
    for path in sorted(root.glob("*.json")):
        loaded.update(json.loads(path.read_text(encoding="utf-8")))
    for scene_id, data in loaded.items():
        current = SCENE_SPECS.get(scene_id)
        if current is None:
            SCENE_SPECS[scene_id] = SceneSpec(
                scene_id,
                data.get("subject", "通用"),
                data.get("solver", ""),
                tuple(data.get("components", ())),
                tuple(data.get("required", ())),
                data.get("visual_type", "diagram"),
                data.get("mode", "计算型" if data.get("solver") else "展示型"),
            )
        else:
            SCENE_SPECS[scene_id] = SceneSpec(
                current.scene_id,
                data.get("subject", current.subject),
                data.get("solver", current.solver),
                tuple(data.get("components", current.components)),
                tuple(data.get("required", current.required)),
                data.get("visual_type", current.visual_type),
                data.get("mode", current.mode),
                current.config_resolver,
                current.config_serializer,
            )


_load_external_specs()


def scene_spec(scene_id: str, fallback: Mapping[str, Any] | None = None) -> SceneSpec:
    """返回注册场景，未迁移的数学和物理场景使用骨架元数据。"""
    registered = SCENE_SPECS.get(scene_id)
    if registered:
        return registered
    data = fallback or {}
    subject = str(data.get("subject") or "通用")
    return SceneSpec(
        scene_id, subject, str(data.get("solver_api") or ""),
        ("experiment_stage", "parameter_controls", "result_cards", "records_table"),
        tuple(), str(data.get("visual_type") or "diagram"),
        str(data.get("mode") or ("计算型" if data.get("solver_api") else "展示型")))


def render_registered_scene(req, skeleton, *, render_solver, hard_validate,
                            resolvers=None, serializers=None):
    """统一调用配置解析器、学科模板和页面验收。

    返回 ``(sections, metadata)``。没有专用配置解析器的场景返回 ``None``，
    由生成器继续使用通用数学、物理模板或模型生成流程。
    """
    spec = scene_spec(skeleton.get("id"), skeleton)
    resolver = (resolvers or {}).get(spec.scene_id)
    serializer = (serializers or {}).get(spec.scene_id)
    config = resolver(req or {}) if resolver is not None else None
    sections = render_solver(req or {}, skeleton, config=config)
    if sections is None:
        return None
    if spec.subject in ("数学", "物理"):
        problems = hard_validate(sections, req or {}, managed_readouts=True)
    else:
        problems = hard_validate(sections, req or {})
    metadata = {
        "场景配置": {
            "scene_id": spec.scene_id,
            "学科": spec.subject,
            "求解器": spec.solver,
            "组件": list(spec.components),
            "必需元素": list(spec.required),
            "绘图类型": spec.visual_type,
            "模式": spec.mode,
        },
        "生成契约通过": not problems,
        "问题": problems,
        "求解器分层": contract_for(spec.scene_id, spec.solver, spec.mode).as_dict(),
    }
    if serializer is not None:
        metadata["页面参数"] = serializer(req or {})
    return sections, metadata

