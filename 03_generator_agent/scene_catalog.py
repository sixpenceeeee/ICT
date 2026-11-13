# -*- coding: utf-8 -*-
"""scene_catalog —— 场景的唯一来源（组块化的调度中心）。

以前同一件事写在三个地方：

    1. scene_registry.SCENE_SKELETONS   声明场景与求解器
    2. solver_templates.render_solver_template   一串 if scene_id == ...
    3. generator_agent.generate()        又一串 if scene_id == ...

加一个场景要改三处，漏一处就出现"能生成但没有模板"或"有模板但生成端不认"。
现在三处合成一张表：**场景 -> (渲染器种类, 模型/模板, UI 元数据)**。

渲染器种类只有四种：
    generic     PageSpec + 组件树（新场景只加元数据，不写渲染代码）
    math        MATHPAGE.mount 套装（现有 38 个数学场景）
    phys_legacy 三个早期物理模板（行为保持不变）
    chem_legacy 六个化学组件模板（行为保持不变）

`status()` 会对每个有求解器但还没法确定性渲染的场景给出**可执行的原因**，
所以"未来生成会不会出问题"这件事，跑一次 `python -m scene_catalog` 就有答案。
"""

import re

import page_spec
from generic_lesson import SceneNotRenderable

# --------------------------------------------------------------------------- 元数据

#: 通用 lesson 场景的 UI 元数据。字段含义见 page_spec 文档。
#: 新增一个可确定性渲染的物理/数学场景时，只需要在这里加一条 + 模型里有 draw。
#: 通用 lesson 场景的 UI 元数据。字段含义见 page_spec 文档。
#: 新增一个可确定性渲染的物理/数学场景时，只需要在这里加一条 + 模型里有 draw。
#:
#: 每条只写"推导不出来"的部分：控件标签/单位/范围由 derive_ui 从 lesson_models.json
#: 的字段说明推导，这里只补 draw、可复算代入式、预设中文名和教学文案。
LAB_UI = {
    "physics-lever": {
        "draw": "PHYS.lever",
        "formula_js": ("'|左力矩| = ' + number(request.left_force) + ' N × ' "
                       "+ number(request.left_arm) + ' m = ' + number(result.left_torque) + ' N·m'"),
        "preset_labels": {"balanced": "左右平衡", "tradeoff": "换臂长仍平衡", "left_down": "左侧下沉",
                          "right_down": "右侧下沉", "mirror": "左右互换", "right_tradeoff": "右侧换臂长"},
        "teaching": {
            "principle": "杠杆平衡的条件是两侧力矩相等：F₁·L₁ = F₂·L₂。力臂是支点到力的作用线的距离，不是支点到钩码的距离。",
            "pitfall": "最常见的错误是把力臂量成支点到作用点的长度；斜着拉时力臂要按垂线量。",
            "question": "只改变右侧力臂，能让杠杆重新平衡吗？记录两组数据验证 F₁L₁ = F₂L₂。",
        },
    },
    "physics-pressure": {
        "draw": "PHYS.liquidPressure",
        "formula_js": ("'表压 = ' + number(request.density) + ' kg/m³ × 9.8 N/kg × ' "
                       "+ number(request.depth) + ' m = ' + number(result.pressure) + ' Pa'"),
        "preset_labels": {"base": "基准深度", "double_depth": "深度加倍", "tradeoff": "换液体", "surface": "液面处"},
        "teaching": {
            "principle": "液体压强只由液体密度和深度决定：p = ρgh。同一深度各个方向压强相等，与容器形状无关。",
            "pitfall": "深度是液面到测量点的竖直距离，不是容器底到桌面的高度。",
            "question": "把深度加倍，压强变成几倍？换一种液体再试一次，结论变不变？",
        },
    },
    "physics-heat": {
        "draw": "PHYS.specificHeat",
        "formula_js": ("'Q = ' + number(request.mass) + ' kg × ' + number(request.specific_heat) "
                       "+ ' J/kg·K × ' + number(Math.abs(result.temperature_change)) + ' K = ' "
                       "+ number(Math.abs(request.heat)) + ' J'"),
        "preset_labels": {"base": "基准加热", "double_mass": "质量加倍", "scaled": "同比例",
                          "double_capacity": "换大比热容", "warmer_start": "初温更高",
                          "cooling": "放热降温", "zero_heat": "不传热"},
        "teaching": {
            "principle": "物体温度变化吸收或放出的热量 Q = cmΔt。质量越大、比热容越大，同样热量下温升越小。",
            "pitfall": "Δt 是温度变化量而不是末温；放热时 Δt 取负，热量取绝对值。",
            "question": "同样的热量，质量加倍后温升变成多少？再换一种比热容更大的物质比较。",
        },
    },
    "physics-motion": {
        "draw": "PHYS.uniformAcceleration",
        "formula_js": ("'|Δv| = ' + number(Math.abs(request.acceleration)) + ' m/s² × ' "
                       "+ number(request.time) + ' s = ' "
                       "+ number(Math.abs(result.velocity - request.initial_velocity)) + ' m/s'"),
        "preset_labels": {"base": "基准加速", "double_time": "时间加倍", "uniform": "匀速",
                          "reverse": "反向运动", "start": "初始时刻"},
        "teaching": {
            "principle": "匀变速直线运动的速度随时间均匀变化：v = v₀ + at，v-t 图像是一条直线，图像下的面积等于位移。",
            "pitfall": "把 v-t 图像当成轨迹图；或把加速度为负当成减速（要看速度方向）。",
            "question": "时间加倍后速度、位移各变成几倍？把加速度改成 0 再看图像。",
        },
    },
    "physics-projectile": {
        "draw": "PHYS.horizontalProjectile",
        "formula_js": ("'射程 = ' + number(request.speed) + ' m/s × ' + number(result.flight_time) "
                       "+ ' s = ' + number(result.range) + ' m'"),
        "preset_labels": {"base": "基准抛出", "double_speed": "速度加倍", "quadruple_height": "高度四倍",
                          "landed": "落地时刻", "vertical": "竖直自由落体"},
        "teaching": {
            "principle": "平抛运动可以分解为水平方向的匀速直线运动和竖直方向的自由落体运动，两个分运动时间相同。",
            "pitfall": "以为初速度越大下落越快；实际上落地时间只由高度决定。",
            "question": "初速度加倍后射程、飞行时间各怎么变？只改高度呢？",
        },
    },
    "physics-refraction": {
        "draw": "PHYS.refraction",
        "formula_js": ("'v₁/v₂ = ' + number(request.n2) + ' ÷ ' + number(request.n1) + ' = ' "
                       "+ number(result.v1_over_v2 || (request.n2 / request.n1))"),
        "preset_labels": {"forward": "空气入水", "reverse": "水入空气", "below": "小角度",
                          "critical": "临界角", "above": "超过临界角", "normal": "垂直入射",
                          "same_medium": "同种介质"},
        "teaching": {
            "principle": "光从光疏介质射入光密介质时折射角变小；反过来折射角变大，超过临界角就发生全反射。",
            "pitfall": "把入射角量成与界面的夹角；全反射发生时还去算折射角。",
            "question": "逐渐增大入射角，折射角怎样变化？折射光线消失时入射角是多少？",
        },
    },
    "physics-horizontalForce": {
        "draw": "PHYS.horizontalForce",
        "formula_js": ("'f_max = ' + number(request.static_coefficient) + ' × ' "
                       "+ number(result.normal_force) + ' N = ' + number(result.static_limit) + ' N'"),
        "preset_labels": {"below": "推不动", "same_force_sliding": "刚好滑动", "threshold": "临界",
                          "above": "明显加速", "above_left": "反向推", "slide_right": "向右滑",
                          "slide_left": "向左滑", "force_against_motion": "阻力",
                          "double_mass": "质量加倍", "rougher": "更粗糙"},
        "teaching": {
            "principle": "水平面上物体是否运动取决于外力与最大静摩擦力的比较；滑动后摩擦力为 μ动·N，与速度无关。",
            "pitfall": "把静摩擦当成固定值；或认为速度越大摩擦力越大。",
            "question": "外力从 4 N 增到 6 N，物块什么时候开始滑动？滑动后加速度是多少？",
        },
    },
    "physics-workPower": {
        "draw": "PHYS.workPower",
        "formula_js": ("'|W| = ' + number(Math.abs(result.parallel_force)) + ' N × ' "
                       "+ number(request.distance) + ' m = ' + number(Math.abs(result.work)) + ' J'"),
        "preset_labels": {"parallel": "力与位移同向", "perpendicular": "力与位移垂直", "reverse": "力与位移反向",
                          "oblique": "斜拉", "supplement": "钝角", "slower": "耗时更长",
                          "double_distance_time": "位移加倍", "no_displacement": "没有位移",
                          "no_force": "没有力"},
        "teaching": {
            "principle": "功等于力在位移方向上的分量乘以位移：W = F·s·cosθ；功率是功与时间之比。",
            "pitfall": "以为有力就做功（垂直于位移的力不做功）；把功率当成力。",
            "question": "力与位移垂直时功是多少？耗时加倍后功率怎么变？",
        },
    },
    "physics-mechanicalEnergy": {
        "draw": "PHYS.mechanicalEnergy",
        "formula_js": ("'|ΔEp| = ' + number(request.mass) + ' kg × 9.8 N/kg × ' "
                       "+ number(Math.abs(request.start_height - request.end_height)) + ' m = ' "
                       "+ number(Math.abs(result.initial_potential - result.final_potential)) + ' J'"),
        "preset_labels": {"conserved": "只有重力做功", "shifted_datum": "换参考零点", "double_drop": "落差加倍",
                          "dissipation": "有摩擦损耗", "stop_threshold": "刚好停下", "insufficient": "能量不足",
                          "energy_gain": "外力输入能量", "double_mass_and_loss": "质量与损耗同时变",
                          "kinetic_to_potential": "动能转势能"},
        "teaching": {
            "principle": "只有重力做功时机械能守恒；有摩擦等非保守力做负功，机械能减少，减少量等于克服摩擦力做的功。",
            "pitfall": "把机械能守恒当成普遍规律；换参考零点后误以为势能变了。",
            "question": "加上摩擦损耗后总机械能去了哪里？把起始高度加倍，末速度变几倍？",
        },
    },
    "physics-planeMirror": {
        "draw": "PHYS.drawPlaneMirror",
        "inputs": {
            "object_distance": {"label": "物距", "unit": "m", "minimum": 0.05, "maximum": 5, "value": 0.5},
            "object_height": {"label": "物高", "unit": "m", "minimum": 0, "maximum": 6, "value": 0.3},
            "observer_distance": {"label": "眼睛到镜面距离", "unit": "m", "minimum": 0.05, "maximum": 10, "value": 1},
            "observer_height": {"label": "眼睛高于镜心", "unit": "m", "minimum": -10, "maximum": 10, "value": 0},
            "mirror_half_height": {"label": "镜面半高", "unit": "m", "minimum": 0.05, "maximum": 6, "value": 0.6},
        },
        "outputs": {
            "object_distance": {"label": "物距", "unit": "m"},
            "image_distance": {"label": "像距", "unit": "m"},
            "image_height": {"label": "像高", "unit": "m"},
            "magnification": {"label": "放大率"},
            "image_kind": {"label": "像的性质"},
            "visibility": {"label": "可见性"},
            "visible_from": {"label": "可见起点", "unit": "m"},
            "visible_to": {"label": "可见终点", "unit": "m"},
        },
        "formula_js": ("'像距 = ' + number(request.object_distance) + ' m × 1 = ' "
                       "+ number(result.image_distance) + ' m'"),
        "preset_labels": {"full": "整段可见", "double_object_distance": "物距加倍", "mirror_edge": "镜边",
                          "narrow": "窄镜", "observer_high": "眼睛偏高", "middle_only": "仅中段可见",
                          "observer_far": "眼睛后退", "short_object": "矮物体", "edge_only": "仅边缘可见"},
        "teaching": {
            "source": "物理知识库「平面镜成像」",
            "kind": "实验性质：虚拟仿真，数值取自理想模型。",
            "principle": "平面镜成像遵循光的反射定律：入射角等于反射角，物与像关于镜面对称，像距等于物距。",
            "pitfall": "入射角是入射光线与法线的夹角，不是与镜面的夹角；平面镜成的是虚像，不能呈现在光屏上。",
            "question": "移动眼睛的位置，可见范围怎样变化？只改变镜面大小，像的位置会变吗？",
            "conclusion": "像与物关于镜面对称；能否看到完整的像由眼睛位置和镜面大小共同决定。",
            "safety": "虚拟实验不涉及真实激光；真实实验中不要让强光直射眼睛。",
        },
    },
    "physics-wavePropagation": {
        "draw": "PHYS.drawWavePropagation",
        "inputs": {
            "frequency": {"label": "声源频率", "unit": "Hz", "minimum": 20, "maximum": 2000, "value": 440},
            "detector_distance": {"label": "声源到探测器距离", "unit": "m", "minimum": 1, "maximum": 1000, "value": 340},
            "travel_time": {"label": "首峰传播时间", "unit": "s", "minimum": 0.001, "maximum": 10, "value": 1},
            "observation_time": {"label": "观察时间", "unit": "s", "minimum": 0, "maximum": 10, "value": 0.5},
        },
        "outputs": {
            "speed": {"label": "波速", "unit": "m/s"},
            "period": {"label": "周期", "unit": "s"},
            "wavelength": {"label": "波长", "unit": "m"},
            "front_distance": {"label": "波前位置", "unit": "m"},
            "arrival_state": {"label": "到达状态"},
        },
        "formula_js": ("'波速 = ' + number(request.detector_distance) + ' m ÷ ' "
                       "+ number(request.travel_time) + ' s = ' + number(result.speed) + ' m/s'"),
        "preset_labels": {"base": "基准", "double_frequency": "频率加倍", "faster_medium": "更快的介质",
                          "before_arrival": "到达前", "arrival": "刚到达", "after_arrival": "到达后",
                          "double_baseline": "距离加倍", "emission": "刚发出", "one_period": "一个周期"},
        "teaching": {
            "source": "物理知识库「波的传播与声速」",
            "kind": "实验性质：虚拟仿真，按均匀静止介质中的一维传播计算。",
            "principle": "声源发出的波前以恒定波速向外传播，波速由介质决定：v = s / t，且 v = λf。",
            "pitfall": "频率加倍时波速不变、波长减半；不要以为频率越高声速越大。",
            "question": "保持介质不变，频率加倍后波长怎样变化？改变探测器距离，传播时间怎么变？",
            "conclusion": "同一介质中波速不变；波长与频率成反比，波前位置等于波速乘时间。",
            "safety": "虚拟实验不产生真实声响；真实实验注意控制音量，避免长时间高分贝暴露。",
        },
    },
    "physics-pulleySystem": {
        "draw": "PHYS.drawPulleySystem",
        "inputs": {
            "layout": {"kind": "select", "label": "绳路结构", "value": "fixed",
                       "options": [["fixed", "单定滑轮"], ["two_fixed", "两定滑轮"],
                                   ["two_strands", "两承重段"], ["three_strands", "三承重段"],
                                   ["four_strands", "四承重段"]]},
            "load_mass": {"label": "载荷质量", "unit": "kg", "minimum": 0.1, "maximum": 100, "value": 2},
            "moving_mass": {"label": "动滑轮组件质量", "unit": "kg", "minimum": 0, "maximum": 20, "value": 0.2},
            "lift_height": {"label": "提升高度", "unit": "m", "minimum": 0, "maximum": 5, "value": 1},
            "rope_loss_force": {"label": "绳端附加阻力", "unit": "N", "minimum": 0, "maximum": 100, "value": 0},
        },
        "outputs": {
            "supporting_strands": {"label": "承重绳段数"},
            "pull_force": {"label": "绳端拉力", "unit": "N"},
            "pull_distance": {"label": "拉绳长度", "unit": "m"},
            "useful_work": {"label": "有用功", "unit": "J"},
            "input_work": {"label": "总功", "unit": "J"},
            "efficiency": {"label": "机械效率", "unit": "%"},
        },
        "formula_js": ("'总功 = ' + number(result.pull_force) + ' N × ' + number(result.pull_distance) "
                       "+ ' m = ' + number(result.input_work) + ' J'"),
        "preset_labels": {"fixed": "单定滑轮", "redirect": "改变方向", "two": "两段绳", "three": "三段绳",
                          "four": "四段绳", "carrier": "计入动滑轮", "drag_two": "两段绳有阻力",
                          "drag_four": "四段绳有阻力", "double_height": "高度加倍", "zero_lift": "不提升",
                          "double_load": "载荷加倍"},
        "teaching": {
            "source": "物理知识库「滑轮组」",
            "kind": "实验性质：虚拟仿真，忽略绳重与滑轮摩擦，只计绳端附加阻力。",
            "principle": "滑轮组由定滑轮和动滑轮组成，承重绳段数为 n 时拉力约为载荷的 1/n，拉绳长度是提升高度的 n 倍。",
            "pitfall": "省力不省功：拉力变小但拉绳变长；机械效率是有用功与总功之比，不是拉力之比。",
            "question": "承重绳段数从 2 增到 4，拉力、拉绳长度和机械效率各怎样变化？",
            "conclusion": "n 段承重绳时 F ≈ G/n、s = nh；计入动滑轮与阻力后机械效率小于 100%。",
            "safety": "虚拟实验不涉及真实吊装；真实操作中严禁在吊物下方站人。",
        },
    },
    "physics-inclinedPlane": {
        "draw": "PHYS.inclinedPlane",
        "formula_js": ("'W有用 = ' + number(request.mass) + ' kg × 9.8 N/kg × ' "
                       "+ number(request.height) + ' m = ' + number(result.useful_work) + ' J'"),
        "preset_labels": {"ideal_short": "理想短斜面", "ideal_double_length": "长度加倍", "rough_short": "粗糙短斜面",
                          "rough_long": "粗糙长斜面", "vertical": "竖直提升", "horizontal_rough": "水平拖动",
                          "horizontal_smooth": "水平光滑", "double_mass": "质量加倍", "scale_ramp": "整条斜面放大"},
        "teaching": {
            "principle": "斜面省力不省功：W有用 = Gh，W总 = FL，机械效率 η = Gh/FL。摩擦越大效率越低。",
            "pitfall": "把斜面长度当成高度；或以为越省力效率越高。",
            "question": "斜面变长后拉力变小，机械效率怎么变？把摩擦系数调到 0 再比较。",
        },
    },
}

UI = {
    "physics-buoyancy": {
        "canvas_key": "buoyancy",
        "record_key": "buoyancy",
        "draw": "PHYS.floating",
        "aria": "烧杯、液体、物块与弹簧测力计",
        "legend": [
            {"label": "物块", "color": "#1b62b0"},
            {"label": "液面", "color": "#0f63a3"},
            {"label": "测力计", "color": "#a3362b"},
        ],
        "inputs": {
            "object_density": {"label": "物块密度", "unit": "kg/m³", "minimum": 100, "maximum": 3000, "value": 600},
            "liquid_density": {"label": "液体密度", "unit": "kg/m³", "minimum": 700, "maximum": 2000, "value": 1000},
            "volume": {"label": "物体体积", "unit": "cm³", "minimum": 0.00001, "maximum": 0.002,
                       "value": 0.0002, "scale": 1e-6},
            "fraction": {"label": "浸入比例", "unit": "", "minimum": 0, "maximum": 1, "value": 0.5},
            "mode": {"kind": "select", "label": "悬挂方式", "value": "hang",
                     "options": [["hang", "悬挂"], ["free", "自由释放"]]},
        },
        "outputs": {
            "displaced_volume": {"label": "排液体积", "unit": "m³"},
            "weight": {"label": "重力", "unit": "N"},
            "buoyancy": {"label": "浮力", "unit": "N"},
            "tension": {"label": "测力计示数", "unit": "N"},
            "state": {"label": "状态"},
        },
        "preset_labels": {
            "partial": "部分浸入", "double_displacement": "排液量加倍", "double_volume": "体积加倍",
            "denser_liquid": "换更密液体", "slack": "绳松弛", "float": "漂浮", "neutral": "悬浮", "sink": "下沉",
        },
        "summary_js": "'浮力 ' + number(result.buoyancy) + ' N，' + result.state",
        "formula_js": ("'F浮 = ' + number(request.liquid_density) + ' kg/m³ × 9.8 N/kg × ' "
                       "+ number(result.displaced_volume) + ' m³ = ' + number(result.buoyancy) + ' N'"),
        "formula_note": "阿基米德原理：浮力等于排开液体所受的重力，与浸入深度无关。",
        "record_headers": ["物块密度/(kg·m⁻³)", "液体密度/(kg·m⁻³)", "体积/cm³",
                           "浸入比例", "排液体积/m³", "重力/N", "浮力/N", "示数/N", "状态"],
        "record_fields": [
            {"js": "request.object_density"},
            {"js": "request.liquid_density"},
            {"js": "number(request.volume * 1000000)"},
            {"js": "number(request.fraction)"},
            {"js": "number(result.displaced_volume)"},
            {"js": "number(result.weight)"},
            {"js": "number(result.buoyancy)"},
            {"js": "result.tension == null ? '—' : number(result.tension)"},
            {"js": "result.state"},
        ],
        "teaching": {
            "source": "物理知识库「浮力」",
            "kind": "实验性质：虚拟仿真，数值取自理想模型，不作为真实测量数据。",
            "principle": ("浸在液体中的物块受到向上的浮力，大小等于排开液体所受的重力：F浮 = ρ液 · g · V排。"
                          "同一液体里，排开体积越大浮力越大；完全浸没后体积不再增加，浮力也就不再变大。"),
            "pitfall": ("常见的两个错误：以为越深浮力越大（实际上完全浸没后浮力不变）；"
                        "以为漂浮时浮力比重力小（漂浮恰好意味着 F浮 = G，两者相等）。"),
            "question": "保持液体和物块不变，只改变浸入比例，浮力与测力计示数怎样变化？记录三组数据比较。",
            "conclusion": "浮力只由液体密度与排开体积决定；悬挂时测力计示数 = 重力 − 浮力。",
            "safety": "虚拟实验不涉及真实液体操作；真实实验中注意玻璃器皿与液体洒漏。",
        },
    },
}

#: 场景 -> 调度信息
SCENE_RENDERERS = {
    # generic：PageSpec + 组件树
    "physics-buoyancy": {"renderer": "generic", "model": "buoyancy", "subject": "物理"},
    "physics-lever": {"renderer": "generic", "model": "lever", "subject": "物理"},
    "physics-pressure": {"renderer": "generic", "model": "pressure", "subject": "物理"},
    "physics-heat": {"renderer": "generic", "model": "heat", "subject": "物理"},
    "physics-motion": {"renderer": "generic", "model": "motion", "subject": "物理"},
    "physics-projectile": {"renderer": "generic", "model": "projectile", "subject": "物理"},
    "physics-refraction": {"renderer": "generic", "model": "refraction", "subject": "物理"},
    "physics-horizontalForce": {"renderer": "generic", "model": "horizontalForce", "subject": "物理"},
    "physics-workPower": {"renderer": "generic", "model": "workPower", "subject": "物理"},
    "physics-mechanicalEnergy": {"renderer": "generic", "model": "mechanicalEnergy", "subject": "物理"},
    "physics-inclinedPlane": {"renderer": "generic", "model": "inclinedPlane", "subject": "物理"},

    # 早期物理模板（行为不变，仅登记以便统一调度）
    "physics-planeMirror": {"renderer": "generic", "model": "planeMirror", "subject": "物理"},
    "physics-wavePropagation": {"renderer": "generic", "model": "wavePropagation", "subject": "物理"},
    "physics-pulleySystem": {"renderer": "generic", "model": "pulleySystem", "subject": "物理"},
    "physics-thin-lens": {"renderer": "generic", "model": "thinLens", "subject": "物理"},
    "physics-reflection": {"renderer": "generic", "subject": "物理"},
    "physics-density": {"renderer": "generic", "subject": "物理"},
    "chemistry-dilution": {"renderer": "generic", "subject": "化学"},
    "chemistry-mass-conservation": {"renderer": "generic", "subject": "化学"},
    "chemistry-ph-indicator": {"renderer": "generic", "subject": "化学"},
    "chemistry-reaction-amounts": {"renderer": "generic", "subject": "化学"},
    "chemistry-solubility-curve": {"renderer": "generic", "subject": "化学"},
    "chemistry-rate-equilibrium": {"renderer": "generic", "subject": "化学"},
    "chemistry-metal-activity": {"renderer": "generic", "subject": "化学"},
    "chemistry-change-type": {"renderer": "generic", "subject": "化学"},
    "chemistry-galvanic": {"renderer": "generic", "subject": "化学"},
    "chemistry-isomer": {"renderer": "generic", "subject": "化学"},
    "chemistry-crystal": {"renderer": "generic", "subject": "化学"},

    # 数学：几何/体积/展开/线性方程组各有专门装配，走 MATHPAGE.mount
    "math-linearSystem": {"renderer": "linear_system", "subject": "数学"},
    # 化学：置换反应的“现象 + 方程式 + 反应计量”走专用模板
    "chemistry-reaction-compare": {"renderer": "reaction_compare", "subject": "化学"},
}

#: 化学组件模板：scene_id -> {配置解析器, 渲染器, 元信息键, 来源标签, 超范围提示}
#:
#: 这里的每一条都是"可确定性渲染"的完整声明：解析器从需求里取出受支持的
#: 物种/条件（取不到就判不可交付，绝不猜），渲染器按组件装配整页，
#: 元信息写进运行档案，老师能看到当时用的是哪一套参数。
CHEM_TEMPLATES = {
    "chemistry-solubility-ksp": {
        "resolve": "resolve_ksp_config", "render": "render_ksp_template",
        "values": "ksp_template_values", "meta": "Ksp页面参数",
        "label": "Ksp 参数化页面模板",
        "fallback": "Ksp 场景暂不支持（不可交付）",
        "error": "该 Ksp 需求尚未配置好：%s 未调用大模型猜测离子价态或方程式。",
    },
    "chemistry-acid-base-titration": {
        "resolve": "resolve_acid_base_titration_config",
        "render": "render_acid_base_titration_template",
        "values": "titration_template_values", "meta": "酸碱滴定页面参数",
        "label": "酸碱滴定组件页面",
        "fallback": "酸碱滴定场景暂不支持（不可交付）",
        "error": "该酸碱滴定需求超出当前已核验模型：%s 未调用大模型猜测反应物或结果。",
    },
    "chemistry-precipitation-quantitative": {
        "resolve": "resolve_precipitation_config", "render": "render_precipitation_template",
        "values": "precipitation_template_values", "meta": "沉淀反应页面参数",
        "label": "沉淀反应组件页面",
        "fallback": "沉淀场景暂不支持（不可交付）",
        "error": "该沉淀需求超出当前已核验反应目录：%s 未调用大模型猜测产物或沉淀质量。",
    },
    "chemistry-gas-collection": {
        "resolve": "resolve_gas_collection_config", "render": "render_gas_collection_template",
        "values": "gas_collection_template_values", "meta": "气体制取页面参数",
        "label": "气体制取组件页面",
        "fallback": "气体制取场景暂不支持（不可交付）",
        "error": "该气体制取需求超出当前已核验反应目录：%s 未调用大模型猜测产物或气体体积。",
    },
    "chemistry-redox-electron-balance": {
        "resolve": "resolve_redox_config", "render": "render_redox_template",
        "values": "redox_template_values", "meta": "氧化还原页面参数",
        "label": "氧化还原组件页面",
        "fallback": "氧化还原场景暂不支持（不可交付）",
        "error": "该氧化还原需求不满足当前已核验物种目录：%s 未调用大模型猜测方程式。",
    },
}

SUBJECT_DEFAULT_RENDERER = {
    "物理": "physics-investigation", "数学": "math-exploration", "化学": "chemistry-lab",
    "生物": "biology-observation", "地理": "geography-spatial", "信息科技": "informatics-stepper",
}


# --------------------------------------------------------------------------- 元数据推导

_MEANING_UNIT = re.compile(r"([^\s，,（(]+)\s*([A-Za-zμΩρθ°%³²·][A-Za-z0-9μΩρθ°%³²·/^-]*)")


def derive_ui(model):
    """从 lesson_models.json 的字段说明推导 UI 元数据。

    说明文字形如「物体密度 kg/m³，正数」：标签取前半段，单位取紧跟的符号。
    这是"新场景零代码"的兜底路径；需要精确范围/下拉/文案时再在 UI 里显式覆盖。
    """
    inputs = {}
    for name, meaning in (model.get("inputs") or {}).items():
        text = str(meaning)
        if "select" in text.lower():
            raise SceneNotRenderable(
                "输入 %s 是下拉选项，必须在 scene_catalog.UI 里显式声明可选项" % name)
        match = _MEANING_UNIT.match(text)
        label, unit = (match.group(1), match.group(2)) if match else (text.split("，")[0], "")
        values = [case[name] for case in (model.get("cases") or {}).values()
                  if isinstance(case.get(name), (int, float))]
        guess = next(iter((model.get("cases") or {}).values()), {}).get(name, 1)
        span = abs(max(values + [abs(guess) or 1])) * 2 or 1
        inputs[name] = {"label": label, "unit": unit, "value": guess,
                        "minimum": min(0, *(values or [0])), "maximum": span}
    outputs = {}
    for name, meaning in (model.get("fields") or {}).items():
        text = str(meaning)
        match = _MEANING_UNIT.match(text)
        label, unit = (match.group(1), match.group(2)) if match else (text.split("，")[0], "")
        outputs[name] = {"label": label, "unit": unit}
    return {"inputs": inputs, "outputs": outputs}


def _ui_for(scene_id, entry):
    """LAB_UI（学科文案） + UI（显式覆盖） + derive_ui（自动推导） 三层合并。"""
    ui = dict(LAB_UI.get(scene_id) or {})
    ui.update(UI.get(scene_id) or {})
    model = _model_of(entry)
    if not ui.get("inputs") or not ui.get("outputs"):
        derived = derive_ui(model)
        if not ui.get("inputs"):
            ui["inputs"] = derived["inputs"]
        if not ui.get("outputs"):
            ui["outputs"] = derived["outputs"]
    ui.setdefault("canvas_key", entry.get("model") or scene_id)
    ui.setdefault("record_key", entry.get("model") or scene_id)
    ui.setdefault("draw", model.get("draw"))
    ui.setdefault("teaching", {
        "principle": model.get("assumptions") or "",
        "question": "改变一个参数，比较读数与图示的变化。",
    })
    if not ui.get("formula_js"):
        raise SceneNotRenderable(
            "场景 %s 缺少可复算代入式模板：请在 scene_catalog.LAB_UI['%s']['formula_js'] 里"
            "写一条能独立复算的算式（J1 只认带数字的等式，不接受'读数 = 结果'）" % (scene_id, scene_id))
    if not ui.get("summary_js"):
        ui["summary_js"] = _derive_summary(model)
    if not ui.get("record_headers"):
        headers = []
        for name in (model.get("inputs") or {}):
            meta = ui["inputs"].get(name) or {}
            headers.append(_header(meta))
        for name in (model.get("fields") or {}):
            meta = ui["outputs"].get(name) or {}
            headers.append(_header(meta))
        ui["record_headers"] = headers
    if not ui.get("record_fields"):
        input_fields = []
        for name in (model.get("inputs") or {}):
            meta = ui["inputs"].get(name) or {}
            # 下拉项（如滑轮组绳路）是字符串，套 number() 会变成 NaN
            input_fields.append({"js": ("request.%s" if meta.get("kind") == "select"
                                        else "number(request.%s)") % name})
        output_fields = []
        for name in (model.get("fields") or {}):
            # 读数可能是字符串（状态）或空值（无有限像）；记录表必须原样保留，不能显示 NaN/0
            output_fields.append({"js": (
                "result.{0} == null ? '—' : (typeof result.{0} === 'number' "
                "? number(result.{0}) : result.{0})".format(name))})
        ui["record_fields"] = input_fields + output_fields
    return ui


def _header(meta):
    label = str(meta.get("label") or "").strip()
    unit = str(meta.get("unit") or "").strip()
    return "%s/%s" % (label, unit) if unit else label


def _model_of(entry):
    from scene_registry import PHYSICS_MODELS, MATH_MODELS
    name = entry.get("model")
    if name in PHYSICS_MODELS:
        return PHYSICS_MODELS[name]
    if name in MATH_MODELS:
        return MATH_MODELS[name]
    raise SceneNotRenderable("场景 %s 指向的模型 %s 未登记在 lesson_models.json" % (entry.get("id"), name))


def _derive_summary(model):
    fields = list((model.get("fields") or {}).items())
    if not fields:
        return "'—'"
    head = fields[0][0]
    return "'%s ' + number(result.%s)" % (fields[0][1].split("，")[0], head)


def _derive_formula(model):
    """**不要用**：猜测"读数 = 输入连乘"在多数模型上是错的（力矩、百分比、比值都会算错）。

    保留这个函数只为说明取舍：代入式必须由 LAB_UI/UI 显式声明，缺失时
    `_ui_for` 会直接拒绝渲染，而不是猜一个看似合理、实际会被 J1 判错的式子。
    """
    raise SceneNotRenderable(
        "代入式不能用连乘猜测：请在 scene_catalog.LAB_UI 里声明 formula_js")


# --------------------------------------------------------------------------- 调度


_UNIT_FACTORS = {
    "毫米": 0.001, "mm": 0.001, "厘米": 0.01, "cm": 0.01, "米": 1.0, "m": 1.0,
    "毫秒": 0.001, "ms": 0.001, "秒": 1.0, "s": 1.0,
    "千克": 1.0, "kg": 1.0, "克": 0.001, "g": 0.001,
    "牛": 1.0, "n": 1.0, "度": 1.0, "°": 1.0,
}


def request_text(req):
    parts = [req.get("原始需求"), req.get("实验主题")]
    interactions = req.get("交互要求") or []
    if isinstance(interactions, str):
        interactions = [interactions]
    parts.extend(interactions)
    return " ".join(str(part) for part in parts if part)


def parse_initial(req, inputs, model):
    """从老师原话里取初始值（"初始物距为 300 厘米" -> object_distance=3.0）。

    PageSpec 的控件是 SI 单位，文本里的单位先换算到基准再换成控件单位。
    取不到就返回空字典，让场景默认值生效；不猜、不覆盖老师明确给出的数。
    """
    text = request_text(req or {})
    if not text:
        return {}
    found = {}
    for name, meta in inputs.items():
        aliases = [str(meta.get("label") or ""), str((model.get("inputs") or {}).get(name) or ""),
                   name]
        for alias in aliases:
            alias = alias.split("，")[0].split(" ")[0].strip()
            if not alias:
                continue
            pattern = (r"(?:初始|默认)?\s*" + re.escape(alias) +
                       r"\s*(?:为|设为|是|取|=|:|：)?\s*(-?\d+(?:\.\d+)?)\s*"
                       r"(毫米|厘米|米|毫秒|秒|千克|克|牛|度|cm|mm|m|ms|s|kg|g|N|°)?")
            match = re.search(pattern, text, re.I)
            if not match:
                continue
            value = float(match.group(1))
            unit = (match.group(2) or "").lower()
            if unit:
                ui_unit = str(meta.get("unit") or "").lower()
                value = value * _UNIT_FACTORS.get(unit, 1.0) / (_UNIT_FACTORS.get(ui_unit, 1.0)
                                                                if ui_unit else 1.0)
            found[name] = value
            break
    return found


def spec_for(scene_id, req=None, entry=None):
    """由 catalog 条目 + 需求构造 PageSpec（显式规格 / lesson 模型两条来源）。"""
    import explicit_specs
    if explicit_specs.has(scene_id):
        return explicit_specs.spec_for(scene_id, req)
    entry = entry or SCENE_RENDERERS.get(scene_id)
    if not entry:
        raise SceneNotRenderable("场景 %s 未在 scene_catalog 登记" % scene_id)
    model = _model_of(entry)
    ui = _ui_for(scene_id, dict(entry, id=scene_id))
    if not (ui.get("draw") or model.get("draw")):
        raise SceneNotRenderable(
            "场景 %s 有求解器 %s，但缺少共享绘图组件：请在 frame/phys.js（或对应场景库）"
            "补一个 draw 函数，并在 scene_catalog.UI.%s.draw 里登记" % (scene_id, model["api"], scene_id))
    required = set((model.get("inputs") or {}))
    declared = set((ui.get("inputs") or {}))
    if required - declared:
        raise SceneNotRenderable("场景 %s 的 UI 元数据缺少输入：%s"
                                 % (scene_id, "、".join(sorted(required - declared))))
    from math_page_plan import select_components
    components = select_components(
        req or {}, ui.get("components") or ("presets", "records", "observations"))
    spec = page_spec.lesson_spec(
        scene_id, model, entry.get("subject") or ui.get("subject") or "物理",
        grade=(req or {}).get("年级") or "初中",
        title=(req or {}).get("实验名称") or model.get("title"),
        ui=ui, req=req or {}, components=components,
        initial=parse_initial(req or {}, ui.get("inputs") or {}, model))
    spec["draw"]["api"] = ui.get("draw") or model.get("draw")
    if model.get("visual"):
        spec["visual"] = model["visual"]
    goals = (req or {}).get("学习目标")
    if isinstance(goals, str):
        goals = [goals]
    spec["learning_goals"] = [goal for goal in (goals or []) if str(goal).strip()] or \
        [(ui.get("teaching") or {}).get("question") or ""]
    return page_spec.require_valid(spec)


def render_scene(req, skeleton, config=None):
    """统一调度入口。返回六区 dict；无法确定性渲染时返回 None（交给上层策略）。"""
    scene_id = (skeleton or {}).get("id")
    entry = SCENE_RENDERERS.get(scene_id)
    if entry and entry["renderer"] == "generic":
        spec = spec_for(scene_id, req, entry)
        from generic_lesson import render
        return render(spec)
    if entry and entry["renderer"] == "linear_system":
        from linear_system_template import render_linear_system_template
        return render_linear_system_template(req or {})
    if entry and entry["renderer"] == "reaction_compare":
        from reaction_compare_template import render_reaction_compare_template
        return render_reaction_compare_template(req or {})
    if scene_id in CHEM_TEMPLATES:
        import solver_templates as st
        chem = CHEM_TEMPLATES[scene_id]
        if config is None:
            try:
                config = getattr(st, chem["resolve"])(req or {})
            except ValueError:
                return None
        return getattr(st, chem["render"])(req or {}, config=config)
    if (skeleton or {}).get("subject") == "数学":
        return render_math_scene(req, skeleton)
    return None


def has_renderer(skeleton):
    """该场景是否有确定性渲染路径（决定生成端是否调用大模型）。"""
    scene_id = (skeleton or {}).get("id")
    if scene_id in CHEM_TEMPLATES or scene_id in SCENE_RENDERERS:
        return True
    # 数学场景逐个尝试装配，装配不出来（未登记的模型）再退回大模型
    return (skeleton or {}).get("subject") == "数学"


def renderer_label(scene_id, subject):
    """写进运行档案的"生成来源"文案（保持历史措辞，便于横向对比旧运行）。"""
    if scene_id == "math-linearSystem":
        return "一次函数参数化页面模板"
    if scene_id in SCENE_RENDERERS and SCENE_RENDERERS[scene_id]["renderer"] == "generic":
        return "PageSpec 组件装配页面"
    return (subject or "场景") + "组件页面"


def render_math_scene(req, skeleton):
    """数学场景：几何/体积/展开走专门装配，其余走 lesson 模型 + MATHPAGE.mount。"""
    from math_page_templates import QUADRATIC, render_math_model
    scene_id = (skeleton or {}).get("id")
    model = QUADRATIC if scene_id == "math-quadratic" else skeleton.get("lesson_model")
    if model is None:
        from math_geometry_templates import GEOMETRY_MODELS, composite_volume_model
        if scene_id == "math-solid-volume" and (req or {}).get("组成部分") is not None:
            return render_math_model(req, "composite-volume", composite_volume_model(req),
                                     default_components=("presets", "records", "observations"))[0]
        model = GEOMETRY_MODELS.get(scene_id.removeprefix("math-"))
    if model:
        return render_math_model(req or {}, scene_id.removeprefix("math-"), model,
                                 default_components=("presets", "records", "observations"))[0]
    return None


# --------------------------------------------------------------------------- 体检


def status(scene_id, skeleton=None):
    """返回 (是否可确定性渲染, 原因)。"""
    entry = SCENE_RENDERERS.get(scene_id)
    if entry and entry["renderer"] == "generic":
        try:
            spec_for(scene_id, {"年级": "初中"})
        except SceneNotRenderable as exc:
            return False, str(exc)
        except Exception as exc:  # noqa: BLE001 - 体检要把任何异常都变成可读原因
            return False, "%s: %s" % (type(exc).__name__, exc)
        return True, ""
    if entry:
        return True, ""
    if scene_id in CHEM_TEMPLATES:
        return True, "需要需求中点名受支持的物种/条件，否则判为不可交付"
    subject = (skeleton or {}).get("subject") or ""
    if subject == "数学":
        return True, ""
    api = (skeleton or {}).get("solver_api")
    if api:
        return False, ("有求解器 %s 但没有确定性渲染器：缺 PageSpec 元数据或共享绘图组件" % api)
    return False, "未登记求解器：只能走大模型路径"


def report(skeletons):
    """生成可读的覆盖率表（`python -m scene_catalog` 用）。"""
    rows = []
    for item in skeletons:
        ready, reason = status(item.get("id"), item)
        rows.append((item.get("subject", ""), item.get("id", ""), item.get("solver_api") or "-",
                     "可确定性渲染" if ready else "需补组件", reason))
    return rows


def _cli():
    import scene_registry
    rows = report(scene_registry.SCENE_SKELETONS)
    ready = [row for row in rows if row[3] == "可确定性渲染"]
    print("场景总数 %d：可确定性渲染 %d，需补组件 %d"
          % (len(rows), len(ready), len(rows) - len(ready)))
    print()
    print("%-6s %-44s %-40s %-12s %s" % ("学科", "场景", "求解器", "状态", "说明"))
    for subject, scene_id, api, state, reason in rows:
        if state == "可确定性渲染" and not reason:
            continue
        print("%-6s %-44s %-40s %-12s %s" % (subject, scene_id, api, state, reason))


if __name__ == "__main__":
    _cli()
