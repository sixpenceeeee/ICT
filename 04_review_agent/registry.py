# -*- coding: utf-8 -*-
"""
registry.py —— 审查用的注册表（对齐《界面设计+审查判据》V1.0）

这份文件只放"规范里写死的清单"，不放判定逻辑：
    ENGINES          25 类规划引擎白名单 + 各自首选判据（规范 4.3–4.8）
    PROTOTYPE_MAP    旧原型 engine → 规划引擎的映射（规范第五节）
    SCENES           已审核场景注册表（规范 7.3 的 approvedScenes 雏形）
    JUDGES           J1–J8 判据的定义（规范 3.1）
    SUBJECT_JUDGES   六学科首选/补充判据（规范 3.3 + 提示词侧对齐）
    SECTIONS         六个统一区域（规范 2.1/2.2）

改这里意味着"改了比赛规范"，不要为了过审而放宽白名单。
"""

# ---------------------------------------------------------------- 学科

SUBJECTS = ["数学", "物理", "化学", "生物", "地理", "信息科技"]

SUBJECT_ALIASES = {
    "数学": ["数学", "几何", "函数", "统计"],
    "物理": ["物理", "电路", "力学", "光学", "热学"],
    "化学": ["化学", "反应", "溶液", "原子"],
    "生物": ["生物", "生物学", "细胞", "遗传"],
    "地理": ["地理", "地形", "等高线", "气候"],
    "信息科技": ["信息科技", "信息技术", "算法", "编程", "排序"],
}

# ---------------------------------------------------------------- 引擎（规范 4.3–4.8）

ENGINES = {
    "数学": {
        "function_plot": "函数绘图",
        "geometry_2d": "二维几何",
        "geometry_3d": "三维几何",
        "statistics": "概率与统计",
        "step_calculation": "分步演算",
    },
    "物理": {
        "circuit": "电路仿真",
        "mechanics": "力学仿真",
        "ray_optics": "几何光学",
        "thermodynamics": "热学演示",
        "measurement": "仪器测量",
        "physics_general": "通用物理演示",
    },
    "化学": {
        "virtual_reaction": "虚拟化学反应",
        "lab_instrument": "化学器材与操作",
        "chemistry_chart": "化学数据图表",
        "molecular_model": "分子与微观结构",
    },
    "生物": {
        "microscope_cell": "显微观察与细胞",
        "genetics": "遗传模拟",
        "bioprocess": "生理与细胞过程",
        "ecology": "生态与种群",
    },
    "地理": {
        "earth_sun": "地球与太阳运动",
        "map_terrain": "地图与地形",
        "weather_climate": "天气与气候",
        "geo_process": "地理过程",
    },
    "信息科技": {
        "algorithm_trace": "算法过程跟踪",
        "binary_encoding": "数据表示与编码",
    },
}

# 每个引擎的首选判据（规范 4.x 的"首选判据"列）
ENGINE_JUDGES = {
    "function_plot": ["J1", "J2"],
    "geometry_2d": ["J2", "J6"],
    "geometry_3d": ["J4", "J2"],
    "statistics": ["J7", "J3"],
    "step_calculation": ["J1", "J5"],
    "circuit": ["J1", "J8", "J6"],
    "mechanics": ["J1", "J2"],
    "ray_optics": ["J2", "J1"],
    "thermodynamics": ["J1", "J7"],
    "measurement": ["J1", "J8", "J7"],
    "physics_general": [],
    "virtual_reaction": ["J8", "J3"],
    "lab_instrument": ["J5", "J6", "J8"],
    "chemistry_chart": ["J1", "J7"],
    "molecular_model": ["J3", "J4", "J6"],
    "microscope_cell": ["J5", "J6", "J8"],
    "genetics": ["J3", "J1"],
    "bioprocess": ["J5", "J6"],
    "ecology": ["J1", "J7", "J6"],
    "earth_sun": ["J2", "J1"],
    "map_terrain": ["J2", "J6"],
    "weather_climate": ["J5", "J7"],
    "geo_process": ["J5", "J6"],
    "algorithm_trace": ["J5", "J3"],
    "binary_encoding": ["J1", "J3"],
}

# 旧原型字段 engine → 规划引擎（规范第五节：不能只改名就宣称功能补齐）
PROTOTYPE_MAP = {
    "ohm": ("circuit", "简化示例：理想电阻模型，不等于完整接线训练"),
    "quadratic": ("function_plot", "一个具体场景"),
    "reaction": ("virtual_reaction", "不等于真实反应事实模拟"),
    "mendel": ("genetics", "一个具体场景"),
    "sun": ("earth_sun", "简化太阳高度演示"),
    "bubble": ("algorithm_trace", "一个具体场景"),
    "buoyancy": ("measurement", "浮力测量，属仪器测量类简化示例"),
}

# ---------------------------------------------------------------- 场景（规范 7.1 的 scene_id）

# required: J6 检查的强制要素（器材/标签/图例）
# facts:    J8 绑定的事实表条目 id
SCENES = {
    "quadratic": {
        "name": "二次函数图像", "subject": "数学", "engine": "function_plot",
        "required": ["坐标轴", "顶点", "对称轴"], "facts": ["MAT-F-001"],
    },
    "cube_section": {
        "name": "平面截正方体", "subject": "数学", "engine": "geometry_3d",
        "required": ["截面", "体积"], "facts": ["MAT-F-002"],
    },
    "ohm": {
        "name": "欧姆定律", "subject": "物理", "engine": "circuit",
        "required": ["电源", "电流表", "电压表"], "facts": ["PHY-F-001", "PHY-F-002"],
    },
    "voltmeter_ammeter_resistance": {
        "name": "伏安法测电阻", "subject": "物理", "engine": "circuit",
        "required": ["电源", "开关", "滑动变阻器", "电流表", "电压表"], "facts": ["PHY-F-001"],
    },
    "buoyancy_measure": {
        "name": "浮力测量", "subject": "物理", "engine": "measurement",
        "required": ["弹簧测力计", "量筒", "水"], "facts": ["PHY-F-004"],
    },
    "lens_imaging": {
        "name": "凸透镜成像规律", "subject": "物理", "engine": "ray_optics",
        "required": ["凸透镜", "光屏", "光具座"], "facts": ["PHY-F-005"],
    },
    "fe_cuso4": {
        "name": "铁与硫酸铜溶液的置换反应", "subject": "化学", "engine": "virtual_reaction",
        "required": ["烧杯", "铁", "硫酸铜"], "facts": ["CHE-F-001"],
    },
    "cu_hcl": {
        "name": "铜与稀盐酸", "subject": "化学", "engine": "virtual_reaction",
        "required": ["试管", "铜", "稀盐酸"], "facts": ["CHE-F-002"],
    },
    "micro_cell": {
        "name": "显微镜观察植物细胞", "subject": "生物", "engine": "microscope_cell",
        "required": ["目镜", "物镜", "视野"], "facts": ["BIO-F-001"],
    },
    "monohybrid": {
        "name": "单因子遗传杂交", "subject": "生物", "engine": "genetics",
        "required": ["配子", "基因型"], "facts": ["BIO-F-002"],
    },
    "contour_profile": {
        "name": "等高线与地形剖面", "subject": "地理", "engine": "map_terrain",
        "required": ["等高线", "剖面"], "facts": ["GEO-F-001"],
    },
    "earth_sun_altitude": {
        "name": "太阳高度角与昼夜长短", "subject": "地理", "engine": "earth_sun",
        "required": ["纬线", "太阳高度角"], "facts": ["GEO-F-002", "GEO-F-003"],
    },
    "bubble": {
        "name": "冒泡排序过程", "subject": "信息科技", "engine": "algorithm_trace",
        "required": ["比较", "交换"], "facts": ["ICT-F-001"],
    },
    "binary_code": {
        "name": "进制转换与编码", "subject": "信息科技", "engine": "binary_encoding",
        "required": ["二进制"], "facts": ["ICT-F-002"],
    },
}

# ---------------------------------------------------------------- 判据（规范 3.1）

JUDGES = {
    "J1": {"名称": "数值复算", "对象": "数值、公式、单位和值域",
           "方法": "以独立公式重新计算，对比容差和边界"},
    "J2": {"名称": "几何复算", "对象": "坐标、角度、长度、位置关系",
           "方法": "坐标重算、几何约束、角度/相交关系判断"},
    "J3": {"名称": "计数与守恒", "对象": "原子数、元素数、颗粒/概率计数",
           "方法": "统计前后数量，验证守恒及组合统计"},
    "J4": {"名称": "空间拓扑", "对象": "三维面边顶点、截面、折叠关系",
           "方法": "检查共面、封闭、邻接关系及必要拓扑不变量"},
    "J5": {"名称": "序列与状态", "对象": "操作顺序、过程阶段、算法执行状态",
           "方法": "与有限状态机/参考过程逐步比对"},
    "J6": {"名称": "结构要素齐备", "对象": "必要器材、标注、结构组成",
           "方法": "检查强制部件、连接和标签"},
    "J7": {"名称": "统计复算", "对象": "测量统计、回归、分布、图表",
           "方法": "独立算均值、方差、斜率、频数等，并核对图表"},
    "J8": {"名称": "答案表比对", "对象": "确定性事实、选项判定、步骤规范",
           "方法": "与教师审核的标准事实/答案及错误理由表对照"},
    "J0": {"名称": "开放任务", "对象": "没有客观标准的探究结论、文学评价",
           "方法": "不进入自动判分闭环，交教师判断"},
}

# 六学科的首选/补充判据（规范 3.3 + 提示词 JUDGE_BY_SUBJECT 对齐）
SUBJECT_JUDGES = {
    "数学": {"首选": ["J1", "J2", "J4"], "补充": ["J6", "J7"]},
    "物理": {"首选": ["J1", "J2", "J8"], "补充": ["J6", "J7"]},
    "化学": {"首选": ["J3", "J8"], "补充": ["J6", "J5"]},
    "生物": {"首选": ["J3", "J5"], "补充": ["J6", "J7", "J8"]},
    "地理": {"首选": ["J2", "J5"], "补充": ["J6", "J7"]},
    "信息科技": {"首选": ["J5"], "补充": ["J3", "J8"]},
}

# ---------------------------------------------------------------- 六区域（规范 2.1/2.2）

SECTIONS = [
    {"key": "info", "id": "sec-info", "cls": "exp-info", "name": "① 实验信息",
     "must": ["实验名", "学科", "学段", "学习目标"]},
    {"key": "stage", "id": "sec-stage", "cls": "exp-stage", "name": "② 实验演示",
     "must": ["画布", "标签或刻度"]},
    {"key": "control", "id": "sec-control", "cls": "exp-control", "name": "③ 参数与操作",
     "must": ["2–4 个关键控件", "开始/执行", "重置"]},
    {"key": "result", "id": "sec-result", "cls": "exp-result", "name": "④ 结果与反馈",
     "must": ["1–3 项读数", "公式或图像", "状态提示"]},
    {"key": "record", "id": "sec-record", "cls": "exp-record", "name": "⑤ 实验记录",
     "must": ["记录表或步骤日志", "结论输入"]},
    {"key": "teach", "id": "sec-teach", "cls": "exp-teach", "name": "⑥ 教学说明",
     "must": ["原理", "易错点", "探究问题"]},
]

# 化学/生物：必须是虚拟仿真，不得给出真实危险操作指引
SIMULATION_ONLY = {"化学", "生物"}


def engines_of(subject):
    return ENGINES.get(subject, {})


def engine_ok(subject, engine_id):
    """白名单校验：允许规划引擎名，也允许旧原型名（但要能映射）。"""
    if engine_id in engines_of(subject):
        return True, engine_id
    if engine_id in PROTOTYPE_MAP:
        target = PROTOTYPE_MAP[engine_id][0]
        if target in engines_of(subject) or not subject:
            return True, target
    return False, engine_id


def scene_of(scene_id):
    return SCENES.get(scene_id or "")


def subject_judges(subject):
    cfg = SUBJECT_JUDGES.get(subject)
    if not cfg:
        return ["J1", "J2", "J6"]
    return list(dict.fromkeys(cfg["首选"] + cfg["补充"]))


def default_subject(html_text, req_subject=""):
    if req_subject in SUBJECTS:
        return req_subject
    for subj, keys in SUBJECT_ALIASES.items():
        if any(k in html_text for k in keys):
            return subj
    return ""
