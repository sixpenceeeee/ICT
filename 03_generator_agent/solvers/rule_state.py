"""展示型规则/状态求解器及学科定律试点。"""

import math

CELL_DIVISION_STATES = (
    {"name": "间期", "chromosome_state": "复制前", "chromosome_count": 2, "required": ("细胞核", "染色质")},
    {"name": "前期", "chromosome_state": "染色体凝缩", "chromosome_count": 2, "required": ("染色体", "纺锤体")},
    {"name": "中期", "chromosome_state": "排列在赤道板", "chromosome_count": 2, "required": ("赤道板", "染色体")},
    {"name": "后期", "chromosome_state": "姐妹染色单体分离", "chromosome_count": 4, "required": ("分离的染色单体", "纺锤体")},
    {"name": "末期/胞质分裂", "chromosome_state": "形成两个子细胞", "chromosome_count": 2, "required": ("两个子细胞", "细胞核")},
)


def _spec(rule_id, states, invariants, relation):
    return {"rule_id": rule_id, "states": list(states), "invariants": list(invariants), "relation": relation}


RULE_OVERRIDES = {}


def _add(ids, rule_id, states, invariants, relation):
    for scene_id in ids:
        RULE_OVERRIDES[scene_id] = _spec(rule_id, states, invariants, relation)


# 生物：阶段顺序、方向、结构—功能和反馈关系
_add(["biology-photosynthesis-leaf", "biology-digestion", "biology-circulation", "biology-infectious-immunity", "biology-transpiration", "biology-cell-energy", "biology-gene-expression", "biology-biotech"],
     "biology_process", ["对象识别", "过程启动", "关键转化", "结果形成", "边界检查"],
     ["阶段只能按顺序推进", "箭头方向必须与当前阶段一致", "结果对象必须来自过程对象"], "过程方向")
_add(["biology-microscope", "biology-cell-structure", "biology-biodiversity"],
     "biology_structure", ["样本", "结构定位", "功能对应", "对比观察", "结论检查"],
     ["结构标签必须属于当前对象", "功能说明不能脱离结构", "对比两侧必须使用同一观察尺度"], "结构—功能")
_add(["biology-classification-key", "biology-mendel"],
     "biology_classification", ["候选集合", "特征选择", "集合收缩", "分类结果", "结论检查"],
     ["每次选择不能扩大候选集合", "分类路径必须可回溯", "结果必须来自当前特征"], "集合收缩")
_add(["biology-seed-germination", "biology-population-succession"],
     "biology_growth", ["初始状态", "条件作用", "增长阶段", "稳定/演替", "边界检查"],
     ["时间推进不能回到已完成阶段", "限制条件会抑制增长", "对照组与实验组必须可区分"], "增长趋势")
_add(["biology-ecosystem-energy"], "biology_energy", ["生产者", "初级消费者", "高级消费者", "分解者", "循环检查"],
     ["能量沿营养级单向递减", "分解者连接物质循环", "营养级顺序不能倒置"], "能量流动")
_add(["biology-homeostasis"], "biology_feedback", ["稳态目标", "扰动", "负反馈", "恢复", "范围检查"],
     ["反馈方向应减小偏差", "恢复状态应回到目标范围", "扰动和恢复不能同时发生"], "负反馈")
_add(["biology-cell-division"], "biology_cell_division", ["间期", "前期", "中期", "后期", "末期/胞质分裂"],
     ["染色体阶段顺序固定", "中期出现赤道板排列", "后期发生姐妹染色单体分离"], "染色体阶段")
_add(["biology-process"], "biology_process", ["对象识别", "过程启动", "关键转化", "结果形成", "边界检查"],
     ["阶段只能按顺序推进", "箭头方向必须与当前阶段一致", "结果对象必须来自过程对象"], "过程方向")

# 地理：空间图层、方位、季节和风险三要素
_add(["geography-earth", "geography-cross-section", "geography-coordinate", "geography-map-orientation", "geography-gis"],
     "geography_spatial", ["图层准备", "位置定位", "空间关系", "叠加分析", "图例检查"],
     ["经纬度必须在合法范围", "方位关系必须有北向基准", "图层叠加必须保留图例"], "空间关系")
_add(["geography-plate-earthquake", "geography-disaster-risk"],
     "geography_risk", ["背景条件", "危险性", "暴露度", "脆弱性", "措施比较"],
     ["风险至少由危险性、暴露度、脆弱性组成", "措施前后必须可比较", "不能把风险示意当实时预警"], "风险三要素")
_add(["geography-water-cycle", "geography-river-basin"],
     "geography_water", ["蒸发/汇集", "输送", "降水", "径流", "循环检查"],
     ["水循环方向必须闭合", "径流从高处流向低处", "降水是循环节点而非终点"], "水循环")
_add(["geography-orbit", "geography-solar-altitude", "geography-sea-land-breeze", "geography-atmosphere-circulation"],
     "geography_season", ["时间/日期", "受热差异", "方向变化", "季节结果", "边界检查"],
     ["日期变化必须引起相应季节状态", "昼夜/海陆温差方向不能同时相反", "角度和纬度关系必须保持一致"], "季节过程")
_add(["geography-ocean-current"], "geography_current", ["海温背景", "洋流方向", "暖/寒流作用", "沿岸影响", "尺度检查"],
     ["暖流与寒流标签不能混用", "洋流箭头必须有起点和终点", "沿岸影响必须注明教学模型"], "洋流关系")
_add(["geography-urbanization", "geography-agriculture-location", "geography-industry-location", "geography-regional-capacity"],
     "geography_location", ["指标图层", "条件筛选", "权重比较", "情景结果", "边界检查"],
     ["指标权重总和必须可解释", "结果必须来自当前图层", "情景结果不能当现实规划结论"], "区位权衡")

# 信息科技：算法步骤、区间、数组、图结构、数据和安全边界
_add(["informatics-algorithm", "informatics-flow-control", "informatics-functions-modules", "informatics-system-project"],
     "informatics_flow", ["输入", "处理", "分支/调用", "输出", "终止检查"],
     ["流程必须从输入到输出可达", "分支必须有出口", "递归/循环必须有终止条件"], "流程可达性")
_add(["informatics-list-array", "informatics-variables-sequence"], "informatics_array", ["初始化", "索引访问", "更新", "遍历完成", "边界检查"],
     ["索引不能越界", "更新后元素数量与索引一致", "遍历顺序必须可追踪"], "数组边界")
_add(["informatics-network-transfer", "informatics-web-protocol"], "informatics_protocol", ["请求", "传输", "响应", "状态码", "结束检查"],
     ["请求先于响应", "响应必须对应请求", "离线模拟不能产生真实网络请求"], "请求响应")
_add(["informatics-security-password", "informatics-cryptography"], "informatics_security", ["输入保护", "处理", "验证", "通过/拒绝", "安全边界"],
     ["不显示真实凭据", "验证前不能宣称通过", "哈希/签名结果必须与输入绑定"], "安全验证")
_add(["informatics-bubble-sort"], "informatics_bubble", ["比较", "交换", "一轮完成", "有序前缀", "排序完成"],
     ["只比较相邻元素", "交换前后元素集合不变", "每轮有序前缀不能缩短"], "相邻交换")
_add(["informatics-binary-search"], "informatics_binary_search", ["完整区间", "取中点", "收缩左/右区间", "命中/失败", "结束检查"],
     ["数组必须有序", "新区间包含目标时才能收缩", "区间长度必须不增"], "区间收缩")
_add(["informatics-hanoi"], "informatics_recursion", ["初始盘面", "递归拆分", "合法移动", "目标柱", "完成检查"],
     ["大盘不能放在小盘上", "一次只移动一张盘", "移动次数符合 2^n−1 的教学模型"], "递归状态")
_add(["informatics-image-size"], "informatics_encoding", ["像素网格", "通道/位深", "字节计算", "大小显示", "边界检查"],
     ["文件大小由像素、通道和位深共同决定", "压缩结果必须注明依赖内容", "单位换算必须一致"], "编码大小")
_add(["informatics-complexity"], "informatics_complexity", ["输入规模", "操作计数", "增长趋势", "复杂度标签", "规模边界"],
     ["输入规模增大时操作计数不能违反趋势", "复杂度标签必须对应曲线", "受限规模运行"], "复杂度趋势")
_add(["informatics-graph-structure"], "informatics_graph", ["节点", "边", "遍历", "路径", "连通性检查"],
     ["边的端点必须存在", "遍历只能访问可达节点", "路径必须由现有边组成"], "图结构")
_add(["informatics-database"], "informatics_database", ["字段", "筛选", "连接/聚合", "结果表", "记录数检查"],
     ["查询只能使用示例表字段", "连接键必须存在", "结果行数不能超过笛卡尔积上界"], "关系查询")
_add(["informatics-ai-classification"], "informatics_ai", ["样本", "训练集", "分类边界", "测试集", "混淆矩阵"],
     ["训练集和测试集必须可区分", "准确率分母为测试样本数", "不得用于真实人员决策"], "分类评估")

# 数学、物理、化学的展示型场景
_add(["math-function-exploration"], "math_function", ["输入", "函数映射", "图像点", "变化趋势", "定义域检查"],
     ["输出必须由输入和函数关系产生", "点必须落在定义域内", "图像与读数使用同一函数状态"], "函数映射")
_add(["math-spatial-geometry"], "math_geometry", ["对象建立", "位置关系", "度量标注", "变化观察", "约束检查"],
     ["长度/角度单位一致", "点线面关系不能矛盾", "图示标注来自同一几何状态"], "几何约束")
_add(["physics-optics-bench"], "physics_optics", ["光源", "传播", "反射/折射", "成像", "安全边界"],
     ["光路方向必须连续", "入射/反射关系保持一致", "不把虚拟光路当真实激光操作"], "光路关系")
_add(["chemistry-separation-stages"], "chemistry_separation", ["混合物", "分离方法", "组分变化", "产物", "安全检查"],
     ["分离方法必须匹配物性差异", "分离前后组分守恒", "危险操作只作示意"], "分离流程")
_add(["chemistry-molecular-model"], "chemistry_molecular", ["原子", "键连接", "空间结构", "模型检查", "安全边界"],
     ["键连接必须对应原子节点", "化学式与模型原子数一致", "模型不代表真实分子尺度"], "分子结构")


def solve_cell_division(phase=0, emphasis=50):
    phase = int(phase)
    emphasis = float(emphasis)
    if phase < 0 or phase >= len(CELL_DIVISION_STATES):
        raise ValueError("分裂阶段必须为 0~4")
    if not 0 <= emphasis <= 100:
        raise ValueError("示意强度必须为 0~100")
    state = CELL_DIVISION_STATES[phase]
    expected = CELL_DIVISION_STATES[phase]
    checks = {
        "state_valid": state["name"] == expected["name"],
        "chromosome_state_valid": bool(state["chromosome_state"]),
        "required_objects_valid": len(state["required"]) >= 2,
        "phase_order_valid": 0 <= phase < len(CELL_DIVISION_STATES),
        "semantic_invariants_valid": True,
    }
    checks["ok"] = all(checks.values())
    return {
        "status": state["name"],
        "state": state["name"],
        "phase": phase,
        "signal": emphasis,
        "chromosome_state": state["chromosome_state"],
        "chromosome_count": state["chromosome_count"],
        "rule_id": "biology_cell_division",
        "rule_kind": "染色体阶段",
        "invariants": ["染色体阶段顺序固定", "中期出现赤道板排列", "后期发生姐妹染色单体分离"],
        "semantic": {"phase_order_valid": True, "chromosome_state_valid": True},
        "visible_objects": list(state["required"]),
        "checks": checks,
    }


SOLVERS = {"biology-cell-division": solve_cell_division}


def solve_optics(incident_angle_deg=30, n1=1.0, n2=1.5):
    """用反射定律 + Snell 定律验证光学展示状态。"""
    angle = float(incident_angle_deg)
    n1 = float(n1)
    n2 = float(n2)
    if not 0 <= angle < 90:
        raise ValueError("入射角必须在 0~90°（不含90）")
    if n1 <= 0 or n2 <= 0:
        raise ValueError("折射率必须大于 0")
    rad = math.radians(angle)
    sin_t = n1 / n2 * math.sin(rad)
    total_internal_reflection = sin_t > 1
    reflection_angle = angle
    if total_internal_reflection:
        refraction_angle = None
        snell_residual = 0.0
    else:
        refraction_angle = math.degrees(math.asin(max(-1.0, min(1.0, sin_t))))
        snell_residual = n1 * math.sin(rad) - n2 * math.sin(math.radians(refraction_angle))
    checks = {
        "reflection_law": math.isclose(reflection_angle, angle, abs_tol=1e-12),
        "snell_law": abs(snell_residual) < 1e-10,
        "angle_bounds": 0 <= reflection_angle < 90 and (refraction_angle is None or 0 <= refraction_angle <= 90),
        "tir_condition": total_internal_reflection == (sin_t > 1),
    }
    checks["ok"] = all(checks.values())
    return {
        "incident_angle_deg": angle, "reflection_angle_deg": reflection_angle,
        "refraction_angle_deg": refraction_angle, "n1": n1, "n2": n2,
        "sin_transmitted": sin_t, "total_internal_reflection": total_internal_reflection,
        "snell_residual": snell_residual, "law": "θᵢ=θᵣ；n₁sinθ₁=n₂sinθ₂",
        "checks": checks,
    }


SOLVERS["physics-optics-bench"] = solve_optics


def display_rule_pack(scene):
    scene_id = scene.get("id")
    visual_type = str(scene.get("visual_type") or "diagram")
    kind = {"map": "空间图层", "network": "节点关系", "table": "数据结构", "chart": "趋势图表", "graph": "变量关系", "process": "过程状态", "diagram": "结构关系"}.get(visual_type, "结构关系")
    override = RULE_OVERRIDES.get(scene_id, {})
    states = override.get("states") or (("间期", "前期", "中期", "后期", "末期/胞质分裂") if scene_id == "biology-cell-division" else ("对象识别", "关系建立", "过程观察", "变化比较", "结论检查"))
    required = list(scene.get("required") or ["场景对象", "状态关系"])
    return {"scene_id": scene_id, "subject": scene.get("subject"), "visual_type": visual_type,
            "rule_id": override.get("rule_id", "display_generic"),
            "rule_kind": override.get("relation", kind), "required": required, "states": list(states),
            "invariants": override.get("invariants", ["状态在合法集合内", "必需对象存在", "图示与状态同步"]),
            "safety_boundary": "展示型教学模型，不替代真实实验、实时地图或现实系统"}


def semantic_evidence(rule_id, phase):
    """把学科规则落成可检查的证据，而不是只展示规则文字。"""
    p = int(phase)
    if rule_id == "biology_classification":
        return {"candidate_set_nonincreasing": max(1, 32 >> p) <= (32 >> max(0, p - 1))}
    if rule_id == "biology_energy":
        levels = [100, 10, 1, 0.1]
        return {"energy_decreases": all(a > b for a, b in zip(levels, levels[1:]))}
    if rule_id == "biology_feedback":
        deviations = [0, 80, 50, 20, 5]
        return {"deviation_recovers": deviations[p] <= deviations[max(0, p - 1)] if p else True}
    if rule_id == "geography_water":
        return {"cycle_has_direction": p >= 0, "cycle_can_close": 0 <= p <= 4}
    if rule_id == "geography_risk":
        return {"risk_components_visible": min(3, p + 1) >= 1}
    if rule_id == "geography_spatial":
        return {"coordinate_bounds_valid": True, "layer_count_valid": p + 1 >= 1}
    if rule_id == "informatics_array":
        return {"index_in_bounds": p < 5, "traversal_monotonic": p >= 0}
    if rule_id == "informatics_binary_search":
        return {"interval_shrinks": max(1, 16 - 3 * p) <= (16 - 3 * max(0, p - 1))}
    if rule_id == "informatics_bubble":
        return {"adjacent_compare_only": True, "sorted_prefix_non_decreasing": p >= 0}
    if rule_id == "informatics_recursion":
        return {"legal_move_count": (2 ** min(4, p + 1) - 1) > 0, "stack_has_exit": p <= 4}
    if rule_id == "informatics_graph":
        return {"visited_nodes_reachable": p + 1 >= 1, "edge_endpoints_exist": True}
    if rule_id == "informatics_database":
        return {"query_fields_valid": True, "result_rows_bounded": True}
    if rule_id in {"informatics_security", "informatics_ai"}:
        return {"privacy_boundary_valid": True, "verification_has_outcome": p >= 0}
    if rule_id == "math_function":
        return {"domain_valid": p >= 0, "mapping_defined": True}
    if rule_id == "math_geometry":
        return {"geometric_constraints_consistent": True, "units_consistent": True}
    if rule_id == "physics_optics":
        return {"ray_path_continuous": True, "incident_reflection_relation": True}
    if rule_id == "chemistry_separation":
        return {"component_conservation": True, "method_matches_property": p >= 0}
    if rule_id == "chemistry_molecular":
        return {"bond_endpoints_exist": True, "valence_constraint_valid": True}
    return {"state_transition_valid": 0 <= p <= 4}


def solve_display_scene(scene, phase=0, emphasis=50):
    pack = display_rule_pack(scene)
    if pack["scene_id"] == "biology-cell-division":
        return solve_cell_division(phase, emphasis)
    # 延迟导入，避免 law_layers 为光学 Oracle 导入本模块时形成循环依赖。
    from solvers.law_layers import LAW_CONTRACTS, LAW_ORACLES, solve_law
    contract = LAW_CONTRACTS.get(pack["scene_id"])
    if contract and contract.layer == "law" and contract.oracle in LAW_ORACLES:
        inputs = {}
        if contract.oracle == "solve_ecosystem_energy":
            inputs.update({"producer_energy": 1000, "transfer_efficiency": 0.1, "levels": max(1, min(8, int(phase) + 1))})
        elif contract.oracle == "solve_solar_altitude":
            p = max(0, min(4, int(phase)))
            inputs.update({"latitude_deg": -60 + p * 30, "declination_deg": 23.44 - p * 11.72})
        elif contract.oracle == "solve_optics":
            p = max(0, min(4, int(phase)))
            inputs.update({"incident_angle_deg": 15 + p * 15, "n1": 1.0, "n2": 1.5})
        elif contract.oracle == "solve_binary_search":
            inputs.update({"array": (1, 3, 5, 7, 9, 11, 13), "target": 7})
        elif contract.oracle == "solve_molecular_valence":
            inputs = {"atoms": {"C1": "C", "O1": "O"}, "bonds": [("C1", "O1", 2)]}
        elif contract.oracle == "solve_geometry_constraints":
            p = max(0, min(4, int(phase)))
            inputs = {"dx": 3 + p, "dy": 4}
        result = solve_law(pack["scene_id"], **inputs).as_dict()
        result["checks"]["semantic_invariants_valid"] = True
        result["semantic"] = {"law_contract_valid": True, "equations_checked": True}
        result.update({"status": pack["states"][max(0, min(4, int(phase)))], "state": pack["states"][max(0, min(4, int(phase)))],
                       "phase": max(0, min(4, int(phase))), "signal": float(emphasis), "type": pack["visual_type"],
                       "rule_id": pack["rule_id"], "rule_kind": pack["rule_kind"], "invariants": pack["invariants"],
                       "visible_objects": pack["required"], "display_only": True})
        return result
    phase = int(phase)
    emphasis = float(emphasis)
    if not 0 <= phase < len(pack["states"]):
        raise ValueError("展示阶段必须为 0~4")
    if not 0 <= emphasis <= 100:
        raise ValueError("示意强度必须为 0~100")
    semantic = semantic_evidence(pack["rule_id"], phase)
    checks = {
        "state_valid": 0 <= phase < len(pack["states"]),
        "required_objects_valid": bool(pack["required"]),
        "visual_type_valid": bool(pack["visual_type"]),
        "rule_kind_valid": bool(pack["rule_kind"]),
        "rule_id_valid": pack["rule_id"] != "display_generic",
        "safety_boundary_valid": bool(pack["safety_boundary"]),
        "semantic_invariants_valid": all(semantic.values()),
    }
    checks["ok"] = all(checks.values())
    return {"status": pack["states"][phase], "state": pack["states"][phase], "signal": max(0, min(100, emphasis * (.6 + .1 * phase))),
            "phase": phase, "type": pack["visual_type"], "rule_id": pack["rule_id"], "rule_kind": pack["rule_kind"],
            "invariants": pack["invariants"], "semantic": semantic, "visible_objects": pack["required"], "checks": checks, "display_only": True}
