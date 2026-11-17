# -*- coding: utf-8 -*-
"""生物、地理、信息科技第一批计算型页面的组件模板。"""

from __future__ import annotations

import html
import json

from page_components import (
    render_action_buttons,
    render_learning_goals,
    render_model_controls,
    render_model_result_cards,
    render_number_control,
    render_result_card,
    render_select_control,
    render_subject_tags,
    render_record_table,
)
from solvers.rule_state import display_rule_pack
from solvers.law_layers import contract_for


MODELS = {
    "biology-enzyme": {
        "subject": "生物", "grade": "高中", "title": "酶与细胞代谢", "solver": "BIOSOLVER.solveEnzyme", "draw": "BIOSOLVER.draw",
        "controls": [("substrate", "底物浓度", 0, 200, 1, ""), ("temperature", "温度", 0, 80, 1, "℃"), ("ph", "pH", 0, 14, .1, "")],
        "defaults": {"substrate": 50, "temperature": 37, "ph": 7},
        "outputs": [("rate", "相对反应速率"), ("temp_factor", "温度因子"), ("ph_factor", "pH 因子"), ("substrate_factor", "底物因子")],
        "goals": ["观察底物浓度、温度和 pH 对酶促反应速率的影响。", "区分教学模型中的相对速率与真实实验测量。"],
        "formula": "相对速率 = 底物因子 × 温度因子 × pH 因子",
        "note": "本页为高中生物概念模型，不替代真实酶实验或医学检测。",
    },
    "biology-respiration": {
        "subject": "生物", "grade": "初中", "title": "人体呼吸与气体交换", "solver": "BIOSOLVER.solveRespiration", "draw": "BIOSOLVER.drawRespiration",
        "controls": [("tidal_volume_l", "潮气量", .05, 3, .05, "L"), ("respiratory_rate", "呼吸频率", 1, 80, 1, "次/分")],
        "defaults": {"tidal_volume_l": .5, "respiratory_rate": 16},
        "outputs": [("minute_ventilation_l_min", "每分通气量"), ("tidal_volume_l", "潮气量"), ("respiratory_rate", "呼吸频率")],
        "goals": ["理解潮气量、呼吸频率与每分通气量的关系。", "观察吸呼气模型中的参数变化。"],
        "formula": "每分通气量 = 潮气量 × 呼吸频率",
        "note": "本页为人体呼吸教学示意，不用于个人肺功能或健康诊断。",
    },
    "biology-ecosystem-foodweb": {
        "subject": "生物", "grade": "小学/初中", "title": "生态系统与食物链", "solver": "BIOSOLVER.solveFoodWeb", "draw": "BIOSOLVER.drawFoodWeb",
        "controls": [("producer_energy", "生产者能量", 1, 10000, 10, "单位"), ("transfer_efficiency", "传递效率", .01, .5, .01, ""), ("levels", "营养级数", 1, 8, 1, "级")],
        "defaults": {"producer_energy": 1000, "transfer_efficiency": .1, "levels": 4},
        "outputs": [("energies", "各营养级能量"), ("levels", "营养级数"), ("transfer_efficiency", "传递效率")],
        "goals": ["观察能量沿食物链单向流动并逐级递减。", "区分教学近似传递效率与真实生态系统数据。"],
        "formula": "第 n 级能量 = 生产者能量 × 传递效率^(n−1)",
        "note": "10% 仅作为教学近似，不是所有生态系统的精确常数。",
    },
    "geography-scale-distance": {
        "subject": "地理", "grade": "小学/初中", "title": "比例尺与地图距离", "solver": "GEOSOLVER.solveScaleDistance", "draw": "GEOSOLVER.draw",
        "controls": [("map_distance_cm", "图上距离", 0, 100, .1, "cm"), ("scale_denominator", "比例尺分母", 1, 1000000, 1000, "")],
        "defaults": {"map_distance_cm": 3, "scale_denominator": 100000},
        "outputs": [("actual_distance_km", "实际距离"), ("map_distance_cm", "图上距离"), ("scale_denominator", "比例尺分母")],
        "goals": ["掌握数字比例尺与实际距离的换算。", "检查单位换算和测距结果是否一致。"],
        "formula": "实际距离 = 图上距离 × 比例尺分母",
        "note": "本页为平面地图测距模型，不代表地球曲面最短航线。",
    },
    "geography-climate-reading": {
        "subject": "地理", "grade": "初中", "title": "世界气候判读", "solver": "GEOSOLVER.solveClimate", "draw": "GEOSOLVER.drawClimate",
        "controls": [("temp_shift", "月均温整体偏移", -10, 10, 1, "℃"), ("rain_scale", "降水缩放", .2, 2, .1, "倍")],
        "defaults": {"temp_shift": 0, "rain_scale": 1},
        "outputs": [("annual_temperature_range", "年较差"), ("annual_precipitation", "年降水量"), ("warmest_month", "最热月"), ("coldest_month", "最冷月"), ("climate_label", "教学标签")],
        "goals": ["从气温曲线和降水数据计算年较差、年降水量。", "按气温与降水组合进行初步判读。"],
        "formula": "年较差 = 最热月均温 − 最冷月均温；年降水量 = 12 个月降水量之和",
        "note": "气候标签为教学分类，不替代气象预报或气候评估。",
    },
    "geography-population-resources": {
        "subject": "地理", "grade": "小学/初中", "title": "人口密度与资源统计", "solver": "GEOSOLVER.solvePopulationDensity", "draw": "GEOSOLVER.drawPopulation",
        "controls": [("population", "人口", 0, 10000000, 1000, "人"), ("area_km2", "面积", .1, 100000, 1, "km²")],
        "defaults": {"population": 200000, "area_km2": 500},
        "outputs": [("density_per_km2", "人口密度"), ("population", "人口"), ("area_km2", "面积")],
        "goals": ["理解人口总量、土地面积与人口密度的关系。", "同时关注统计单位、年份和数据范围。"],
        "formula": "人口密度 = 总人口 ÷ 土地面积",
        "note": "统计结果只用于教学演示，不评价地区或群体。",
    },
    "informatics-binary-representation": {
        "subject": "信息科技", "grade": "小学/初中", "title": "信息表示与二进制", "solver": "CSSOLVER.solveBinary", "draw": "CSSOLVER.draw",
        "controls": [("bits", "二进制位串", "1011")],
        "defaults": {"bits": "1011"},
        "outputs": [("decimal", "十进制值"), ("bit_count", "位数"), ("bytes", "占用字节"), ("states", "可表示状态数")],
        "goals": ["理解位权、二进制与十进制之间的关系。", "观察位数变化对可表示状态数和字节数的影响。"],
        "formula": "十进制值 = 各位二进制值 × 对应位权之和",
        "note": "只使用虚构位串，不处理真实账号、证件号或密码。",
    },
    "informatics-data-visualization": {
        "subject": "信息科技", "grade": "小学/初中", "title": "数据可视化与统计", "solver": "CSSOLVER.solveStatistics", "draw": "CSSOLVER.drawStatistics",
        "controls": [("values", "数据（逗号分隔）", "2,4,6")],
        "defaults": {"values": "2,4,6"},
        "outputs": [("count", "数据个数"), ("mean", "平均数"), ("median", "中位数"), ("minimum", "最小值"), ("maximum", "最大值")],
        "goals": ["比较平均数、中位数和数据范围。", "让数据表、图示和统计结果保持同源。"],
        "formula": "平均数 = 数据总和 ÷ 数据个数",
        "note": "仅使用虚构数据，不导入学生个人成绩或联系方式。",
    },
    "informatics-sensor-control": {
        "subject": "信息科技", "grade": "小学/初中", "title": "传感器与机器人控制", "solver": "CSSOLVER.solveSensor", "draw": "CSSOLVER.drawSensor",
        "controls": [("period_s", "采样周期", .01, 5, .01, "s"), ("threshold", "阈值", 0, 100, 1, ""), ("value", "传感器读数", 0, 100, 1, "")],
        "defaults": {"period_s": .5, "threshold": 50, "value": 60},
        "outputs": [("frequency_hz", "采样频率"), ("state", "执行器状态"), ("value", "传感器读数"), ("threshold", "阈值")],
        "goals": ["理解传感器、阈值和执行器之间的反馈关系。", "计算采样频率并观察阈值切换。"],
        "formula": "采样频率 = 1 ÷ 采样周期",
        "note": "仅模拟虚拟设备，不连接真实机器人、摄像头或家用电器。",
    },
}


# 展示型场景的第二阶段模型配置。它们不再只接受“示意强度/阶段”两个
# 通用参数，而是按学科规则声明真实的教学输入、输出和计算关系。求解
# 仍然是确定性的课堂模型，不把展示结果包装成现实世界结论。
CATALOG_PROFILES = {
    "biology_process": {
        "kind": "biology_process", "controls": [("stimulus", "过程刺激", 0, 100, 1, "")],
        "defaults": {"stimulus": 60, "phase": 0},
        "outputs": [("progress", "过程进度"), ("response", "相对响应"), ("state", "过程状态")],
        "formula": "相对响应 = 过程刺激 × (阶段 + 1) / 5",
    },
    "biology_structure": {
        "kind": "biology_structure", "controls": [("scale", "观察尺度", 1, 100, 1, "")],
        "defaults": {"scale": 50, "phase": 0},
        "outputs": [("visible_features", "可见结构数"), ("function_match", "结构功能匹配度"), ("state", "观察状态")],
        "formula": "结构功能匹配度 = 观察尺度 × 阶段权重",
    },
    "biology_classification": {
        "kind": "biology_classification", "controls": [("traits", "已选择特征数", 0, 5, 1, "个")],
        "defaults": {"traits": 2, "phase": 0},
        "outputs": [("candidate_count", "剩余候选数"), ("classification_confidence", "分类确定度"), ("state", "分类状态")],
        "formula": "剩余候选数 = max(1, 32 ÷ 2^特征数)",
    },
    "biology_growth": {
        "kind": "biology_growth", "controls": [("resource", "资源条件", 0, 100, 1, "")],
        "defaults": {"resource": 70, "phase": 0},
        "outputs": [("growth_index", "增长指数"), ("limitation", "限制程度"), ("state", "增长状态")],
        "formula": "增长指数 = 资源条件 × 阶段权重",
    },
    "biology_energy": {
        "kind": "biology_energy", "controls": [("producer_energy", "生产者能量", 1, 10000, 10, "单位"), ("transfer_efficiency", "传递效率", .01, .5, .01, "")],
        "defaults": {"producer_energy": 1000, "transfer_efficiency": .1, "phase": 0},
        "outputs": [("energy_next", "下一营养级能量"), ("energy_ratio", "能量保留比例"), ("state", "能量状态")],
        "formula": "下一营养级能量 = 生产者能量 × 传递效率^(阶段 + 1)",
    },
    "biology_feedback": {
        "kind": "biology_feedback", "controls": [("disturbance", "扰动幅度", 0, 100, 1, ""), ("gain", "反馈增益", 0, 1, .01, "")],
        "defaults": {"disturbance": 60, "gain": .6, "phase": 0},
        "outputs": [("deviation", "剩余偏差"), ("recovery", "恢复比例"), ("state", "稳态状态")],
        "formula": "剩余偏差 = 扰动幅度 × (1 − 反馈增益)^(阶段 + 1)",
    },
    "biology_cell_division": {
        "kind": "biology_cell_division", "controls": [("emphasis", "示意强度", 0, 100, 1, "")],
        "defaults": {"emphasis": 60, "phase": 0},
        "outputs": [("chromosome_count", "染色体计数"), ("chromosome_state", "染色体状态"), ("state", "分裂阶段")],
        "formula": "阶段顺序：间期 → 前期 → 中期 → 后期 → 末期",
    },
    "geography_spatial": {
        "kind": "geography_spatial", "controls": [("latitude", "纬度", -90, 90, 1, "°"), ("longitude", "经度", -180, 180, 1, "°")],
        "defaults": {"latitude": 30, "longitude": 120, "phase": 0},
        "outputs": [("coordinate_valid", "坐标合法性"), ("hemisphere", "半球"), ("state", "空间状态")],
        "formula": "纬度 ∈ [−90°,90°]，经度 ∈ [−180°,180°]",
    },
    "geography_risk": {
        "kind": "geography_risk", "controls": [("hazard", "危险性", 0, 100, 1, ""), ("exposure", "暴露度", 0, 100, 1, ""), ("vulnerability", "脆弱性", 0, 100, 1, "")],
        "defaults": {"hazard": 60, "exposure": 50, "vulnerability": 40, "phase": 0},
        "outputs": [("risk_score", "风险指数"), ("mitigation_gain", "措施收益"), ("state", "风险状态")],
        "formula": "风险指数 = 危险性 × 暴露度 × 脆弱性 / 10000",
    },
    "geography_water": {
        "kind": "geography_water", "controls": [("precipitation", "降水量", 0, 500, 1, "mm"), ("infiltration", "下渗比例", 0, 1, .01, "")],
        "defaults": {"precipitation": 100, "infiltration": .3, "phase": 0},
        "outputs": [("runoff", "地表径流"), ("infiltrated", "下渗量"), ("state", "水循环状态")],
        "formula": "地表径流 = 降水量 × (1 − 下渗比例)",
    },
    "geography_season": {
        "kind": "geography_season", "controls": [("latitude", "纬度", -90, 90, 1, "°"), ("day_of_year", "年内日序", 1, 365, 1, "日")],
        "defaults": {"latitude": 30, "day_of_year": 172, "phase": 0},
        "outputs": [("solar_proxy", "太阳高度代理值"), ("season", "季节状态"), ("state", "季节过程")],
        "formula": "太阳高度代理值 = 90 − |纬度 − 23.44 × sin(2π(日序−80)/365)|",
    },
    "geography_current": {
        "kind": "geography_current", "controls": [("temperature_delta", "海温差", -10, 10, .1, "℃"), ("current_speed", "洋流速度", 0, 5, .1, "m/s")],
        "defaults": {"temperature_delta": 2, "current_speed": 1, "phase": 0},
        "outputs": [("transport_index", "输送指数"), ("coastal_effect", "沿岸影响"), ("state", "洋流状态")],
        "formula": "输送指数 = |海温差| × 洋流速度",
    },
    "geography_location": {
        "kind": "geography_location", "controls": [("transport", "交通条件", 0, 100, 1, ""), ("labor", "劳动力条件", 0, 100, 1, ""), ("market", "市场条件", 0, 100, 1, "")],
        "defaults": {"transport": 70, "labor": 60, "market": 80, "phase": 0},
        "outputs": [("location_score", "区位评分"), ("top_factor", "主导因素"), ("state", "区位状态")],
        "formula": "区位评分 = (交通 + 劳动力 + 市场) / 3",
    },
    "informatics_flow": {
        "kind": "informatics_flow", "controls": [("input_size", "输入规模", 1, 1000, 1, ""), ("branches", "分支数", 1, 10, 1, "个")],
        "defaults": {"input_size": 100, "branches": 2, "phase": 0},
        "outputs": [("reachable_steps", "可达步骤数"), ("termination_ok", "终止性"), ("state", "流程状态")],
        "formula": "可达步骤数 = 输入规模 × (阶段 + 1) / 5",
    },
    "informatics_array": {
        "kind": "informatics_array", "controls": [("array_length", "数组长度", 1, 100, 1, ""), ("index", "访问下标", 0, 99, 1, "")],
        "defaults": {"array_length": 10, "index": 3, "phase": 0},
        "outputs": [("index_valid", "下标合法性"), ("visited_count", "已遍历元素数"), ("state", "数组状态")],
        "formula": "下标合法条件：0 ≤ index < 数组长度",
    },
    "informatics_protocol": {
        "kind": "informatics_protocol", "controls": [("payload_kb", "数据包大小", 1, 10000, 1, "KB"), ("latency_ms", "网络延迟", 1, 1000, 1, "ms")],
        "defaults": {"payload_kb": 100, "latency_ms": 50, "phase": 0},
        "outputs": [("transfer_time_ms", "传输时间代理"), ("round_trip_ms", "往返时间"), ("state", "协议状态")],
        "formula": "往返时间 = 2 × 网络延迟 + 数据量 / 速率代理",
    },
    "informatics_security": {
        "kind": "informatics_security", "controls": [("password_length", "口令长度", 1, 32, 1, "位"), ("attempts", "尝试次数", 1, 10, 1, "次")],
        "defaults": {"password_length": 10, "attempts": 1, "phase": 0},
        "outputs": [("strength", "强度指数"), ("accepted", "验证状态"), ("state", "安全状态")],
        "formula": "强度指数 = 口令长度 × 复杂度代理 − 尝试次数惩罚",
    },
    "informatics_bubble": {
        "kind": "informatics_bubble", "controls": [("items", "元素个数", 2, 100, 1, "个")],
        "defaults": {"items": 8, "phase": 0},
        "outputs": [("comparisons", "比较次数上界"), ("sorted_prefix", "有序前缀"), ("state", "排序状态")],
        "formula": "冒泡排序比较次数上界 = n × (n − 1) / 2",
    },
    "informatics_binary_search": {
        "kind": "informatics_binary_search", "controls": [("array_length", "有序数组长度", 1, 1024, 1, "个"), ("target_index", "目标位置", 0, 1023, 1, "")],
        "defaults": {"array_length": 15, "target_index": 7, "phase": 0},
        "outputs": [("interval_size", "剩余区间"), ("iterations", "比较轮数"), ("state", "查找状态")],
        "formula": "二分查找轮数上界 = ⌈log₂(n)⌉",
    },
    "informatics_recursion": {
        "kind": "informatics_recursion", "controls": [("disks", "汉诺塔盘数", 1, 12, 1, "层")],
        "defaults": {"disks": 4, "phase": 0},
        "outputs": [("moves", "最少移动次数"), ("depth", "递归深度"), ("state", "递归状态")],
        "formula": "汉诺塔最少移动次数 = 2^n − 1",
    },
    "informatics_encoding": {
        "kind": "informatics_encoding", "controls": [("width", "图像宽度", 1, 4096, 1, "px"), ("height", "图像高度", 1, 4096, 1, "px"), ("bits_per_pixel", "每像素位数", 1, 64, 1, "bit")],
        "defaults": {"width": 800, "height": 600, "bits_per_pixel": 24, "phase": 0},
        "outputs": [("bytes", "未压缩字节数"), ("megabytes", "未压缩大小"), ("state", "编码状态")],
        "formula": "未压缩字节数 = 宽 × 高 × 每像素位数 ÷ 8",
    },
    "informatics_complexity": {
        "kind": "informatics_complexity", "controls": [("n", "输入规模 n", 1, 10000, 1, "")],
        "defaults": {"n": 100, "phase": 0},
        "outputs": [("linear_ops", "O(n) 操作数"), ("quadratic_ops", "O(n²) 操作数"), ("state", "复杂度状态")],
        "formula": "比较 O(n)、O(n²) 随输入规模的增长速度",
    },
    "informatics_graph": {
        "kind": "informatics_graph", "controls": [("nodes", "节点数", 1, 100, 1, "个"), ("edges", "边数", 0, 4950, 1, "条")],
        "defaults": {"nodes": 10, "edges": 12, "phase": 0},
        "outputs": [("density", "图密度"), ("reachable_nodes", "可达节点代理"), ("state", "图结构状态")],
        "formula": "无向图密度 = 2 × 边数 / (节点数 × (节点数 − 1))",
    },
    "informatics_database": {
        "kind": "informatics_database", "controls": [("rows", "示例记录数", 1, 10000, 1, "行"), ("filters", "筛选条件数", 0, 10, 1, "个")],
        "defaults": {"rows": 1000, "filters": 2, "phase": 0},
        "outputs": [("result_rows", "结果行数代理"), ("selectivity", "筛选选择率"), ("state", "查询状态")],
        "formula": "结果行数代理 = 记录数 × (0.6)^筛选条件数",
    },
    "informatics_ai": {
        "kind": "informatics_ai", "controls": [("true_positive", "真正例", 0, 1000, 1, ""), ("false_positive", "假正例", 0, 1000, 1, ""), ("false_negative", "假负例", 0, 1000, 1, "")],
        "defaults": {"true_positive": 80, "false_positive": 10, "false_negative": 10, "phase": 0},
        "outputs": [("accuracy", "准确率"), ("precision", "精确率"), ("state", "分类评估状态")],
        "formula": "准确率 = (TP + TN) / 总样本；本页使用教学混淆矩阵代理",
    },
    "chemistry_separation": {
        "kind": "chemistry_separation", "controls": [("boiling_delta", "沸点差", 0, 200, 1, "℃"), ("particle_delta", "粒径差", 0, 100, 1, "")],
        "defaults": {"boiling_delta": 30, "particle_delta": 20, "phase": 0},
        "outputs": [("separation_index", "分离可行性"), ("component_conservation", "组分守恒"), ("state", "分离状态")],
        "formula": "分离可行性 = 沸点差与粒径差的归一化组合",
    },
    "chemistry_molecular": {
        "kind": "chemistry_molecular", "controls": [("atoms", "原子数", 2, 50, 1, "个"), ("bonds", "化学键数", 1, 100, 1, "条")],
        "defaults": {"atoms": 2, "bonds": 1, "phase": 0},
        "outputs": [("average_valence", "平均键级"), ("valence_valid", "价态约束"), ("state", "分子结构状态")],
        "formula": "平均键级 = 2 × 化学键数 / 原子数",
    },
    "math_function": {
        "kind": "math_function", "controls": [("x", "自变量 x", -10, 10, .1, ""), ("scale", "函数系数", -10, 10, .1, "")],
        "defaults": {"x": 2, "scale": 1, "phase": 0},
        "outputs": [("y", "函数值"), ("slope", "局部斜率"), ("state", "函数状态")],
        "formula": "教学函数 y = scale × x²，局部斜率 = 2 × scale × x",
    },
    "math_geometry": {
        "kind": "math_geometry", "controls": [("dx", "水平位移", 0, 100, 1, ""), ("dy", "竖直位移", 0, 100, 1, "")],
        "defaults": {"dx": 3, "dy": 4, "phase": 0},
        "outputs": [("distance", "两点距离"), ("slope", "斜率"), ("state", "几何状态")],
        "formula": "距离 = √(dx² + dy²)",
    },
}


CATALOG_SCENE_OVERRIDES = {
    "biology-photosynthesis-leaf": {
        "kind": "biology_photosynthesis", "controls": [("light", "光照强度", 0, 100, 1, "%"), ("co2", "二氧化碳条件", 0, 100, 1, "%"), ("water", "水分条件", 0, 100, 1, "%")],
        "defaults": {"light": 80, "co2": 70, "water": 90, "phase": 0},
        "outputs": [("rate", "光合作用速率"), ("limiting_factor", "限制因素"), ("state", "叶片状态")],
        "formula": "教学速率 = min(光照、二氧化碳、水分)",
    },
    "geography-sea-land-breeze": {
        "kind": "geography_sea_land_breeze", "controls": [("time", "时间", 6, 18, 1, "时"), ("land_temp", "陆地温度", 10, 40, 1, "℃"), ("sea_temp", "海洋温度", 10, 30, 1, "℃")],
        "defaults": {"time": 12, "land_temp": 32, "sea_temp": 24, "phase": 0},
        "outputs": [("pressure_delta", "气压差代理"), ("wind_direction", "近地面风向"), ("state", "海陆风状态")],
        "formula": "陆地温度高于海洋时，近地面风由海洋吹向陆地；反之为陆风",
    },
    "geography-solar-altitude": {
        "kind": "geography_solar_altitude", "controls": [("latitude", "纬度", -90, 90, 1, "°"), ("declination", "太阳赤纬", -23.44, 23.44, .01, "°")],
        "defaults": {"latitude": 30, "declination": 23.44, "phase": 0},
        "outputs": [("altitude", "正午太阳高度"), ("hemisphere", "纬度半球"), ("state", "太阳高度状态")],
        "formula": "正午太阳高度 = 90° − |纬度 − 太阳赤纬|",
    },
}


def _control_html(model):
    specs = []
    for item in model["controls"]:
        key, label = item[0], item[1]
        if isinstance(item[2], str):
            specs.append({"id": "supp-" + key, "label": label, "kind": "text", "value": model["defaults"][key],
                          "marker": "data-supp-input", "marker_value": key, "aria_label": label})
        else:
            _, _, minimum, maximum, step, unit = item
            specs.append({"id": "supp-" + key, "label": label, "kind": "dual", "value": model["defaults"][key],
                          "min": minimum, "max": maximum, "unit": unit, "marker": "data-supp-input",
                          "marker_value": key, "aria_label": label})
    return render_model_controls(specs)


def _biology_lab_draw_source():
    """Shared apparatus renderer used by every biology teaching page.

    Charts remain useful in the result area, but the main canvas must show an
    observable virtual-lab object: bench, vessel, specimen and measuring aid.
    """
    return r"""
function drawBiologyLab(canvas,result){
  if(!canvas)return;
  var box=canvas.parentElement,w=box.clientWidth||720,h=Math.max(340,Math.min(540,Math.round(w*.62))),dpr=window.devicePixelRatio||1;
  canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);canvas.style.width=w+'px';canvas.style.height=h+'px';
  var c=canvas.getContext('2d');c.setTransform(dpr,0,0,dpr,0,0);c.clearRect(0,0,w,h);
  function rr(x,y,ww,hh,r,fill,stroke){c.beginPath();c.moveTo(x+r,y);c.arcTo(x+ww,y,x+ww,y+hh,r);c.arcTo(x+ww,y+hh,x,y+hh,r);c.arcTo(x,y+hh,x,y,r);c.arcTo(x,y,x+ww,y,r);c.closePath();if(fill){c.fillStyle=fill;c.fill();}if(stroke){c.strokeStyle=stroke;c.stroke();}}
  function tx(s,x,y,size,color,weight){c.fillStyle=color||'#24445f';c.font=(weight||'400')+' '+(size||14)+'px sans-serif';c.fillText(String(s),x,y);}
  var phase=Math.max(0,Number(result&&result.phase)||0), signal=Math.max(0,Math.min(100,Number(result&&((result.signal!=null?result.signal:result.rate)||0))));
  var bg=c.createLinearGradient(0,0,0,h);bg.addColorStop(0,'#f7fbff');bg.addColorStop(1,'#dcebf6');c.fillStyle=bg;c.fillRect(0,0,w,h);
  tx('虚拟生物实验室',24,32,20,'#173b59','700');tx('实验对象与观察状态随参数/阶段更新',24,54,12,'#5c7890','400');
  c.fillStyle='#d8e4ec';c.fillRect(0,h-74,w,74);c.fillStyle='#b7c8d4';c.fillRect(0,h-78,w,4);
  var left=34,top=86,cellW=Math.max(210,(w-96)/2),cellH=h-184,gap=28,right=left+cellW+gap;
  function chamber(x,label,dark){
    rr(x,top,cellW,cellH,14,'rgba(255,255,255,.58)','#83a9c2');
    c.fillStyle=dark?'rgba(21,29,40,.72)':'rgba(236,248,255,.42)';c.fillRect(x+7,top+7,cellW-14,cellH-14);
    if(!dark){c.fillStyle='#fff3a2';c.fillRect(x+cellW-54,top+18,28,7);c.fillStyle='#ffe36f';c.beginPath();c.arc(x+cellW-40,top+22,25,0,Math.PI*2);c.fill();}
    c.fillStyle='#b9d8b2';c.fillRect(x+18,top+cellH-42,cellW-36,24);
    for(var i=0;i<3;i++){var sx=x+cellW*(.27+i*.23),base=top+cellH-40,stem=38+signal*.18+(phase*5);c.strokeStyle=dark?'#a66a58':'#3c9a61';c.lineWidth=4;c.beginPath();c.moveTo(sx,base);c.lineTo(sx+(dark?8:0),base-stem);c.stroke();c.fillStyle=dark?'#d7b18b':'#4aa96c';c.beginPath();c.ellipse(sx-9,base-stem+10,12,6,-.45,0,Math.PI*2);c.fill();c.beginPath();c.ellipse(sx+9,base-stem+20,12,6,.45,0,Math.PI*2);c.fill();}
    if(dark){c.fillStyle='rgba(12,18,26,.46)';c.fillRect(x,top,cellW,cellH);tx('遮光罩',x+cellW-68,top+28,12,'#fff','700');}
    tx(label,x+16,top+cellH+25,15,'#245d91','700');
  }
  chamber(left,'实验组 / 光照',false);chamber(right,'对照组 / 黑暗',true);
  rr(w/2-58,top+cellH+48,116,30,15,'#fff','#9db8cb');tx('观察日 '+(phase+1),w/2-38,top+cellH+68,13,'#315875','700');
  tx('培养箱/培养皿',left+14,top+cellH-55,11,'#5c7890','400');tx('植株、叶片与颜色为模拟观察对象',right+14,top+cellH-55,11,'#5c7890','400');
  rr(22,h-58,Math.min(w-44,330),34,8,'rgba(255,255,255,.78)','#b8cfdf');tx('当前观察信号：'+signal.toFixed(0)+'% · '+(result&&result.state||'实验对象已装载'),36,h-36,12,'#315875','600');
}
"""


def _js(model):
    sid = model["title"]
    solver = model["solver"]
    draw = model["draw"]
    defaults = json.dumps(model["defaults"], ensure_ascii=False, separators=(",", ":"))
    keys = [x[0] for x in model["controls"]]
    key_js = json.dumps(keys, ensure_ascii=False)
    model_spec = {
        "schema": "edu-model.v1", "id": model["title"], "subject": model["subject"], "topic": model["title"],
        "inputs": {}, "outputs": dict(model["outputs"]), "solver": solver, "visual": {"type": "diagram", "renderer": draw},
    }
    for item in model["controls"]:
        key, label = item[0], item[1]
        if isinstance(item[2], str):
            model_spec["inputs"][key] = {"label": label, "type": "text"}
        else:
            _, _, minimum, maximum, step, unit = item
            model_spec["inputs"][key] = {"label": label, "type": "number", "min": minimum, "max": maximum, "step": step, "unit": unit}
    model_js = json.dumps(model_spec, ensure_ascii=False, separators=(",", ":"))
    climate = model["title"] == "世界气候判读"
    stats = model["title"] == "数据可视化与统计"
    if climate:
        request_js = "var shift=Number(s.temp_shift), scale=Number(s.rain_scale); s.monthly_temps=[4,6,10,15,20,24,27,26,21,15,9,5].map(function(v){return v+shift;}); s.monthly_rain=Array(12).fill(30).map(function(v){return v*scale;});"
    elif stats:
        request_js = "s.values=String(s.values).split(',').map(function(v){return Number(v.trim());});"
    else:
        request_js = ""
    fields = "".join("document.querySelectorAll('[data-supp-field=\\\"%s\\\"]').forEach(function(el){el.textContent=suppFmt(result.%s);});" % (key, key) for key, _ in model["outputs"])
    biology_draw = _biology_lab_draw_source() if model["subject"] == "生物" else ""
    draw_call = "drawBiologyLab(suppCanvas,result);" if model["subject"] == "生物" else "%s(suppCanvas,result);" % draw
    return f"""
var SUPP_DEFAULTS={defaults}, SUPP_MODEL=EDU_MODEL.define({model_js}); window.__EDU_MODEL__=SUPP_MODEL;
var suppCanvas=document.getElementById('supp-canvas'), suppRows=document.getElementById('supp-rows'), suppAlert=document.getElementById('supp-alert');
function suppFmt(v){{if(Array.isArray(v))return v.map(function(x){{return Number(x).toFixed(2);}}).join('、');if(typeof v==='number')return Number(v).toFixed(3).replace(/\\.?0+$/,'');return v==null?'—':String(v);}}
{biology_draw}
function suppState(){{var s={{}}; {key_js}.forEach(function(k){{var el=document.querySelector('[data-supp-input="'+k+'"]');s[k]=el&&el.type==='number'?el.valueAsNumber:el.value;}}); {request_js} return s;}}
function suppRender(){{try{{var state=EDU_MODEL.normalize(SUPP_MODEL,suppState());window.__SUPP_REQUEST__=state;var result={solver}(state);window.__SUPP_RESULT__=result;if(!result.checks||result.checks.ok!==true)throw new Error('求解器检查未通过');{draw_call}{fields}suppAlert.hidden=true;suppAlert.textContent='';window.__DATA__=EDU_MODEL.expose(SUPP_MODEL,state,result,{{state:result.state||result.status||null}});}}catch(error){{window.__SUPP_RESULT__=null;window.__DATA__=EDU_MODEL.expose(SUPP_MODEL,null,null,{{error:error.message}});suppAlert.textContent='输入无效或求解失败：'+error.message;suppAlert.hidden=false;document.querySelectorAll('[data-supp-field]').forEach(function(el){{el.textContent='—';}});}}}}
document.querySelectorAll('[data-supp-input]').forEach(function(el){{el.addEventListener('input',suppRender);el.addEventListener('change',suppRender);}});
document.getElementById('supp-record').addEventListener('click',function(){{var r=window.__SUPP_RESULT__;if(!r)return;var key=Object.keys(r).find(function(k){{return k!=='checks'&&!/^_/.test(k);}});var tr=document.createElement('tr');[suppRows.children.length+1,suppFmt(r[key]),new Date().toLocaleTimeString()].forEach(function(v){{var td=document.createElement('td');td.textContent=String(v);tr.appendChild(td);}});suppRows.appendChild(tr);}});
document.getElementById('supp-reset').addEventListener('click',function(){{document.querySelectorAll('[data-supp-input]').forEach(function(el){{var k=el.getAttribute('data-supp-input');el.value=SUPP_DEFAULTS[k];}});suppRender();}});
window.addEventListener('resize',function(){{if(window.__SUPP_RESULT__){{try{{{draw_call.replace('result','window.__SUPP_RESULT__')}}}catch(e){{}}}}}});suppRender();
"""


def render_supplement_template(req, scene_id):
    model = MODELS.get(scene_id)
    if not model:
        return None
    goals = req.get("学习目标") or model["goals"]
    controls = _control_html(model)
    outputs = "".join(render_result_card(label, "data-supp-field", marker_value=key) for key, label in model["outputs"])
    visual_type = "apparatus" if model["subject"] == "生物" else ("graph" if scene_id in ("geography-climate-reading", "informatics-data-visualization") else ("process" if model["subject"] == "信息科技" else "diagram"))
    return {
        "1": render_subject_tags(model["subject"], req.get("年级") or model["grade"], "计算型教学仿真") + render_learning_goals(goals) + '<p class="exp-note">本页由场景配置、组件模板和确定性求解器装配；结果仅适用于页面注明的教学模型。</p>',
        "2": '<div class="supp-stage" data-page-component="experiment_stage"><canvas id="supp-canvas" data-visual-type="%s" aria-label="%s"></canvas><p class="supp-caption">%s</p></div>' % (visual_type, html.escape(model["title"]), html.escape(model["note"])),
        "3": '<div data-page-component="parameter_controls">%s</div>%s' % (controls, render_action_buttons([("supp-record", "记录当前状态", True), ("supp-reset", "重置", False)])),
        "4": '<div class="exp-reads" data-page-component="result_cards">%s</div><div class="exp-formula">%s</div><div class="exp-alert" id="supp-alert" hidden></div>' % (outputs, html.escape(model["formula"])),
        "5": '<div data-page-component="records_table">%s</div>' % render_record_table(["序号", "关键结果", "记录时间"], "supp-rows"),
        "6": '<h3>模型说明</h3><p>%s</p><h3>组件与验收</h3><p>参数控件、演示图示、结果卡和记录表共享同一次求解结果；改变任一输入后，页面重新求解、重绘并刷新读数。</p>' % html.escape(model["note"]),
        "css": '.supp-stage{width:100%;min-width:0;padding:12px;box-sizing:border-box;border:1px solid #d8e7f5;border-radius:14px;background:linear-gradient(160deg,#fbfdff,#eaf3fb)}.supp-stage canvas{display:block;width:100%;height:clamp(300px,44vw,520px);max-width:100%}.supp-caption{color:#536b80;font-size:14px;line-height:1.6}.exp-alert{margin-top:10px;color:#b42318}.exp-reads{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}@media(max-width:700px){.exp-reads{grid-template-columns:minmax(0,1fr)}.supp-stage canvas{height:340px}}',
        "js": _js(model),
    }


def _catalog_title(req, skeleton):
    title = req.get("实验名称") or req.get("实验主题")
    if title:
        return str(title)
    patterns = str(skeleton.get("patterns") or "")
    return patterns.split("|")[0] or str(skeleton.get("id") or "场景演示")


def render_catalog_template(req, skeleton):
    """为尚未迁移专用求解器的生地信场景生成统一展示型页面。

    展示型页面仍使用同一套六区域组件、状态对象、画布和记录表；它只
    计算“示意强度/阶段”这类教学展示状态，不冒充学科定量求解器。
    """
    skeleton = skeleton or {}
    scene_id = str(skeleton.get("id") or "catalog-scene")
    if scene_id == "physics-optics-bench":
        return render_optics_rule_template(req, skeleton)
    subject = str(skeleton.get("subject") or "通用")
    title = _catalog_title(req or {}, skeleton)
    grade = str((req or {}).get("年级") or "小学/初中/高中")
    visual_type = "apparatus" if subject == "生物" else str(skeleton.get("visual_type") or "diagram")
    # 审查器的画布白名单是平台级类型；场景库允许的 map/network/table/chart
    # 在组件层映射为最接近的 graph/diagram/process 表达。
    declared_visual = {"map": "diagram", "network": "process", "table": "diagram", "chart": "graph"}.get(visual_type, visual_type)
    required = [str(x) for x in (skeleton.get("required") or ["场景对象", "状态关系"])]
    layout = str(skeleton.get("layout") or "按场景配置组合图示、控件与结果卡。")
    controls_note = str(skeleton.get("controls") or "控件变化必须同步更新图示和结果。")
    goals = (req or {}).get("学习目标") or [
        "识别本场景中的关键对象、过程或数据关系。",
        "通过控件变化观察教学示意状态，并记录观察结果。",
    ]
    required_text = "、".join(required) if required else "场景对象、过程关系、结果说明"
    contract = contract_for(scene_id, skeleton.get("solver_api"), skeleton.get("mode"))
    pack = display_rule_pack(skeleton)
    pack.update({"solver_layer": contract.layer, "law_contract": contract.as_dict()})
    profile = CATALOG_SCENE_OVERRIDES.get(scene_id) or CATALOG_PROFILES.get(pack.get("rule_id")) or {
        "kind": "generic_display", "controls": [("emphasis", "示意强度", 0, 100, 1, "")],
        "defaults": {"emphasis": 50, "phase": 0},
        "outputs": [("signal", "示意强度"), ("state", "教学状态")],
        "formula": "教学状态由场景规则、阶段和示意强度共同决定。",
    }
    pack["model_profile"] = profile
    profile_defaults = dict(profile.get("defaults") or {})
    profile_defaults.setdefault("phase", 0)
    profile_controls = list(profile.get("controls") or [])
    input_specs, profile_inputs = [], {}
    for key, label, minimum, maximum, step, unit in profile_controls:
        profile_inputs[key] = {"label": label, "type": "number", "min": minimum, "max": maximum, "step": step, "unit": unit}
        input_specs.append({"id": "catalog-" + key, "label": label, "kind": "dual", "value": profile_defaults.get(key), "min": minimum, "max": maximum, "step": step, "unit": unit, "marker": "data-catalog-input", "marker_value": key, "aria_label": label})
    profile_inputs["phase"] = {"label": "阶段/图层", "type": "number", "min": 0, "max": 4, "step": 1}
    input_specs.append({"id": "catalog-phase", "label": "阶段/图层", "kind": "dual", "value": profile_defaults["phase"], "min": 0, "max": 4, "step": 1, "marker": "data-catalog-input", "marker_value": "phase", "aria_label": "阶段或图层"})
    profile_keys = [x[0] for x in profile_controls] + ["phase"]
    profile_outputs = list(profile.get("outputs") or [])
    rule_pack = json.dumps(pack, ensure_ascii=False, separators=(",", ":"))
    catalog_model = json.dumps({
        "schema": "edu-model.v1", "id": scene_id, "subject": subject, "topic": title,
        "inputs": profile_inputs,
        "outputs": dict(profile_outputs),
        "solver": "DISPLAYRULES.solveScene", "visual": {"type": declared_visual, "renderer": "DISPLAYRULES", "profile": profile.get("kind")},
    }, ensure_ascii=False, separators=(",", ":"))
    goals_html = render_learning_goals(goals)
    fields = render_model_result_cards([
        {"id": key, "label": label, "marker": "data-catalog-field", "marker_value": key}
        for key, label in profile_outputs
    ])
    catalog_defaults = json.dumps(profile_defaults, ensure_ascii=False, separators=(",", ":"))
    catalog_keys = json.dumps(profile_keys, ensure_ascii=False, separators=(",", ":"))
    catalog_output_keys = json.dumps([x[0] for x in profile_outputs], ensure_ascii=False, separators=(",", ":"))
    biology_draw = _biology_lab_draw_source() if subject == "生物" else ""
    biology_draw_call = "drawBiologyLab(canvas,result);return;" if subject == "生物" else ""
    js = f"""
(function(){{
  var CATALOG_DEFAULTS={catalog_defaults}, CATALOG_KEYS={catalog_keys}, CATALOG_OUTPUT_KEYS={catalog_output_keys}, CATALOG_MODEL=EDU_MODEL.define({catalog_model}); window.__EDU_MODEL__=CATALOG_MODEL;
  var canvas=document.getElementById('catalog-canvas');
  var rows=document.getElementById('catalog-rows');
  var alertBox=document.getElementById('catalog-alert');
  var DISPLAY_PACK={rule_pack};
  {biology_draw}
  function fmt(v){{return typeof v==='number'?Number(v).toFixed(2).replace(/\\.?0+$/,''):String(v==null?'—':v);}}
  function state(){{var s={{}};CATALOG_KEYS.forEach(function(k){{var el=document.querySelector('[data-catalog-input="'+k+'"]');if(el)s[k]=(el.type==='number'||el.type==='range')?el.valueAsNumber:el.value;}});return s;}}
  function draw(result){{
    if(!canvas)return; var box=canvas.parentElement, w=box.clientWidth||640, h=Math.max(320,Math.min(520,Math.round(w*.58))), dpr=window.devicePixelRatio||1;
    canvas.width=Math.round(w*dpr); canvas.height=Math.round(h*dpr); canvas.style.width=w+'px'; canvas.style.height=h+'px';
    var c=canvas.getContext('2d'); c.setTransform(dpr,0,0,dpr,0,0); c.clearRect(0,0,w,h);
    {biology_draw_call}
    c.fillStyle='#f8fbff'; c.fillRect(0,0,w,h); c.strokeStyle='#bdd4ea'; c.lineWidth=1.5;
    var kind={json.dumps(visual_type, ensure_ascii=False)};
    if(kind==='graph'||kind==='chart'){{var L=46,T=24,R=24,B=42,pw=w-L-R,ph=h-T-B;c.beginPath();c.moveTo(L,T);c.lineTo(L,T+ph);c.lineTo(L+pw,T+ph);c.stroke();c.strokeStyle='#438bd2';c.lineWidth=3;c.beginPath();for(var i=0;i<=20;i++){{var x=L+pw*i/20,y=T+ph-(0.18+0.72*(i/20))*ph*result.signal/100;if(i)c.lineTo(x,y);else c.moveTo(x,y);}}c.stroke();c.fillStyle='#54708a';c.font='14px sans-serif';c.fillText('示意变化',L+pw-62,T+18);}}
    else if(kind==='map'||kind==='network'){{var n=5;for(var j=0;j<n;j++){{var xx=w*.18+(j%3)*w*.28, yy=h*.32+Math.floor(j/3)*h*.28;c.fillStyle=['#4b8bd8','#55a88a','#df9b4a','#a86bd4','#d26666'][j];c.beginPath();c.arc(xx,yy,18,0,Math.PI*2);c.fill();if(j){{c.strokeStyle='#8ba6bd';c.beginPath();c.moveTo(xx,yy);c.lineTo(w*.18+((j-1)%3)*w*.28,h*.32+Math.floor((j-1)/3)*h*.28);c.stroke();}}c.fillStyle='#fff';c.font='12px sans-serif';c.fillText(String(j+1),xx-4,yy+4);}}}}
    else {{var count=kind==='process'?4:3;for(var k=0;k<count;k++){{var bx=34+k*(w-68)/count, by=h*.38, bw=(w-90)/count;c.fillStyle=k<=result.phase%count?'#d9edff':'#eef3f7';c.fillRect(bx,by,bw,64);c.strokeStyle='#8fb5d4';c.strokeRect(bx,by,bw,64);c.fillStyle='#2b587c';c.font='14px sans-serif';c.fillText((k+1)+' · '+(k<=result.phase%count?'已观察':'待观察'),bx+10,by+36);if(k<count-1){{c.strokeStyle='#6d91ac';c.beginPath();c.moveTo(bx+bw+4,by+32);c.lineTo(bx+bw+22,by+32);c.stroke();}}}}}}
    c.fillStyle='#476278';c.font='13px sans-serif';c.fillText('展示型教学模型：不产生现实决策或实验结论',18,h-14);
  }}
  function render(){{try{{var s=EDU_MODEL.normalize(CATALOG_MODEL,state());if(!window.DISPLAYRULES)throw new Error('规则求解器未装载');var result=window.DISPLAYRULES.solveScene({json.dumps(scene_id,ensure_ascii=False)},s,DISPLAY_PACK);window.__DISPLAY_REQUEST__=s;window.__DISPLAY_RESULT__=result;window.__SOLVER_LAYER__=DISPLAY_PACK.solver_layer;window.__LAW_CONTRACT__=DISPLAY_PACK.law_contract;window.__DATA__=EDU_MODEL.expose(CATALOG_MODEL,s,result,{{scene_id:{json.dumps(scene_id,ensure_ascii=False)},solver_layer:DISPLAY_PACK.solver_layer,law_contract:DISPLAY_PACK.law_contract,state:result.status||null}});draw(result);CATALOG_OUTPUT_KEYS.forEach(function(k){{var el=document.querySelector('[data-catalog-field="'+k+'"]');if(el)el.textContent=fmt(result[k]);}});alertBox.hidden=true;}}catch(e){{alertBox.textContent='模型计算失败：'+e.message;alertBox.hidden=false;}}}}
  document.querySelectorAll('[data-catalog-input]').forEach(function(el){{el.addEventListener('input',render);el.addEventListener('change',render);}});
  document.getElementById('catalog-record').addEventListener('click',function(){{var r=window.__DISPLAY_RESULT__;if(!r)return;var tr=document.createElement('tr');[rows.children.length+1,fmt(r.signal),'阶段 '+r.phase].forEach(function(v){{var td=document.createElement('td');td.textContent=v;tr.appendChild(td);}});rows.appendChild(tr);}});
  document.getElementById('catalog-reset').addEventListener('click',function(){{CATALOG_KEYS.forEach(function(k){{var el=document.querySelector('[data-catalog-input="'+k+'"]');if(el&&CATALOG_DEFAULTS[k]!=null)el.value=CATALOG_DEFAULTS[k];}});render();}});
  window.addEventListener('resize',function(){{if(window.__DISPLAY_RESULT__)draw(window.__DISPLAY_RESULT__);}}); render();
}})();
"""
    return {
        "1": render_subject_tags(subject, grade, "展示型教学仿真") + goals_html +
             '<p class="exp-note">本页为展示型场景：%s。仅用于课堂观察，不替代真实实验、实时地图或现实系统。</p>' % html.escape(controls_note) +
             '<p class="exp-note"><strong>场景要素：</strong>%s</p>' % html.escape(required_text),
        "2": '<div class="supp-stage" data-page-component="experiment_stage"><canvas id="catalog-canvas" data-visual-type="%s" aria-label="%s"></canvas><p class="supp-caption">%s</p></div>' % (html.escape(visual_type), html.escape(title), html.escape(layout)),
        "3": '<div data-page-component="parameter_controls">%s</div>%s' % (render_model_controls(input_specs), render_action_buttons([("catalog-record", "记录当前状态", True), ("catalog-reset", "重置", False)])),
        "4": '<div class="exp-reads" data-page-component="result_cards">%s</div><div class="exp-formula">%s</div><div class="exp-alert" id="catalog-alert" hidden></div>' % (fields, html.escape(str(profile.get("formula") or ""))),
        "5": '<div data-page-component="records_table">%s</div>' % render_record_table(["序号", "示意强度", "阶段"], "catalog-rows"),
        "6": '<h3>模型说明</h3><p>%s</p><h3>边界</h3><p>%s</p>' % (html.escape(str(profile.get("formula") or layout)), html.escape(controls_note)),
        "css": '.supp-stage{width:100%;min-width:0;padding:12px;box-sizing:border-box;border:1px solid #d8e7f5;border-radius:14px;background:linear-gradient(160deg,#fbfdff,#eaf3fb)}.supp-stage canvas{display:block;width:100%;height:clamp(300px,44vw,520px);max-width:100%}.supp-caption{color:#536b80;font-size:14px;line-height:1.6}.exp-alert{margin-top:10px;color:#b42318}.exp-reads{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}@media(max-width:700px){.exp-reads{grid-template-columns:minmax(0,1fr)}.supp-stage canvas{height:340px}}',
        "js": js,
    }


def render_optics_rule_template(req, skeleton):
    """物理光学展示型场景：用反射定律和 Snell 定律做严格约束验收。"""
    title = _catalog_title(req or {}, skeleton)
    goals = (req or {}).get("学习目标") or ["验证反射角等于入射角。", "用 Snell 定律检查折射角和全反射条件。"]
    fields = render_model_result_cards([
        {"id": "reflection_angle_deg", "label": "反射角", "marker": "data-optics-field"},
        {"id": "refraction_angle_deg", "label": "折射角", "marker": "data-optics-field"},
        {"id": "snell_residual", "label": "Snell 残差", "marker": "data-optics-field"},
        {"id": "state", "label": "光学状态", "marker": "data-optics-field"},
    ])
    optics_contract = contract_for("physics-optics-bench", skeleton.get("solver_api"), skeleton.get("mode"))
    optics_contract_json = json.dumps(optics_contract.as_dict(), ensure_ascii=False, separators=(",", ":"))
    js = """
(function(){
  var canvas=document.getElementById('optics-canvas'), rows=document.getElementById('optics-rows'), alertBox=document.getElementById('optics-alert'), OPTICS_CONTRACT=LAW_CONTRACT_PLACEHOLDER;
  function fmt(v){{return v==null?'无折射光':(typeof v==='number'?Number(v).toFixed(4).replace(/\\.?0+$/,''):String(v));}}
  function read(){return {incident_angle_deg:Number(document.querySelector('[data-optics-input=angle]').value),n1:Number(document.querySelector('[data-optics-input=n1]').value),n2:Number(document.querySelector('[data-optics-input=n2]').value)};}
  function render(){try{var s=read();if(!window.DISPLAYRULES)throw new Error('规则求解器未装载');var r=window.DISPLAYRULES.solveOptics(s);window.__DISPLAY_REQUEST__=s;window.__DISPLAY_RESULT__=r;window.__SOLVER_LAYER__='law';window.__LAW_CONTRACT__=OPTICS_CONTRACT;window.__DATA__={scene_id:'physics-optics-bench',solver_layer:'law',law_contract:OPTICS_CONTRACT,params:s,result:r,checks:r.checks};DISPLAYRULES.drawOptics(canvas,r);document.querySelector('[data-optics-field=reflection_angle_deg]').textContent=fmt(r.reflection_angle_deg)+'°';document.querySelector('[data-optics-field=refraction_angle_deg]').textContent=fmt(r.refraction_angle_deg)+'°';document.querySelector('[data-optics-field=snell_residual]').textContent=Number(r.snell_residual).toExponential(2);document.querySelector('[data-optics-field=state]').textContent=r.total_internal_reflection?'全反射':'折射';alertBox.hidden=true;}catch(e){alertBox.textContent='光学约束不满足：'+e.message;alertBox.hidden=false;}}
  document.querySelectorAll('[data-optics-input]').forEach(function(el){el.addEventListener('input',render);el.addEventListener('change',render);});
  document.getElementById('optics-record').addEventListener('click',function(){var r=window.__DISPLAY_RESULT__;if(!r)return;var tr=document.createElement('tr');[rows.children.length+1,fmt(r.reflection_angle_deg)+'°',fmt(r.refraction_angle_deg)+'°',r.total_internal_reflection?'全反射':'折射'].forEach(function(v){var td=document.createElement('td');td.textContent=v;tr.appendChild(td);});rows.appendChild(tr);});
  document.getElementById('optics-reset').addEventListener('click',function(){document.querySelector('[data-optics-input=angle]').value=30;document.querySelector('[data-optics-input=n1]').value=1;document.querySelector('[data-optics-input=n2]').value=1.5;render();});
  window.addEventListener('resize',function(){if(window.__DISPLAY_RESULT__)DISPLAYRULES.drawOptics(canvas,window.__DISPLAY_RESULT__);});render();
})();
""".replace("LAW_CONTRACT_PLACEHOLDER", optics_contract_json)
    return {
        "1": render_subject_tags("物理", (req or {}).get("年级") or "初中/高中", "展示型定律验证") + render_learning_goals(goals) + '<p class="exp-note">本页使用反射定律和 Snell 定律进行虚拟光路验证，不指导真实激光或光学器材操作。</p>',
        "2": '<div class="supp-stage" data-page-component="experiment_stage"><canvas id="optics-canvas" data-visual-type="apparatus" aria-label="%s"></canvas><p class="supp-caption">入射光、法线、反射光和折射光共享同一求解结果。</p></div>' % html.escape(title),
        "3": '<div data-page-component="parameter_controls">%s</div>%s' % (render_model_controls([
            {"id": "optics-angle", "label": "入射角", "kind": "dual", "value": 30, "min": 0, "max": 89, "step": 1, "unit": "°", "marker": "data-optics-input", "marker_value": "angle"},
            {"id": "optics-n1", "label": "介质 1 折射率", "value": 1, "min": 0.0001, "max": 10, "step": 0.01, "marker": "data-optics-input", "marker_value": "n1", "aria_label": "介质1折射率"},
            {"id": "optics-n2", "label": "介质 2 折射率", "value": 1.5, "min": 0.0001, "max": 10, "step": 0.01, "marker": "data-optics-input", "marker_value": "n2", "aria_label": "介质2折射率"},
        ]), render_action_buttons([("optics-record", "记录当前状态", True), ("optics-reset", "重置", False)])),
        "4": '<div class="exp-reads" data-page-component="result_cards">%s</div><div class="exp-formula">θᵣ = θᵢ = 30°；1.0 × 0.5000 = 0.5000；1.5 × 0.3333 ≈ 0.5000；Snell 残差 = 0.0000。</div><div class="exp-alert" id="optics-alert" hidden></div>' % fields,
        "5": '<div data-page-component="records_table">%s</div>' % render_record_table(["序号", "反射角", "折射角", "状态"], "optics-rows"),
        "6": '<h3>定律约束</h3><p>页面每次变形都独立检查反射定律、Snell 定律、角度范围和全反射条件；显示的光线和结果卡使用同一求解结果。</p><h3>安全边界</h3><p>这是离线虚拟光路模型，不替代真实光学实验安全培训。</p>',
        "css": '.supp-stage{width:100%;min-width:0;padding:12px;box-sizing:border-box;border:1px solid #d8e7f5;border-radius:14px;background:linear-gradient(160deg,#fbfdff,#eaf3fb)}.supp-stage canvas{display:block;width:100%;height:clamp(300px,44vw,520px);max-width:100%}.exp-alert{margin-top:10px;color:#b42318}.exp-reads{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}@media(max-width:700px){.exp-reads{grid-template-columns:minmax(0,1fr)}.supp-stage canvas{height:340px}}',
        "js": js,
    }
