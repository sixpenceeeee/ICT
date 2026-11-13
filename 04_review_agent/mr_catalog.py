# -*- coding: utf-8 -*-
"""mr_catalog.py —— 变形测试目录（数据层，不放判定逻辑）

为什么要有这一层：
    以前“变形测试”散在 reviewer.py 的 if 分支、checks_browser.js 的探针和
    lesson_models.json 的 relations 里。加一个主题就要在三个地方写代码，
    而且没人说得清“这个页面到底测了哪几条变形关系”。

这份文件只回答三件事：
    1. 每个求解器场景要执行哪些变形关系（id / kind / 控件 / 观测点）；
    2. 控件和读数用什么选择器找（新页面按 data-mr-control 写，老页面走兼容候选）；
    3. 哪些关系是可选的（页面没有开关控件时跳过，而不是误判失败）。

判定逻辑全部在 mr_engine.py；这里只放数据，方便审阅和扩充。
"""

# 关系类型。与 mr_engine.KINDS 对齐，报告里按这个统计覆盖率。
KINDS = (
    "linearity",     # 正比：x 翻倍，y 翻倍
    "inverse",       # 反比：x 翻倍，y 减半
    "invariance",    # 不变：变换后结果应保持不变
    "conservation",  # 守恒：分项之和等于总量
    "boundary",      # 边界：临界/极值状态
    "formula",       # 公式：每个状态独立满足学科公式
    "readout",       # 显示一致：页面读数等于求解结果
)

# ---------------------------------------------------------------------------
# 控件选择器约定
#
# 新页面（推荐）：给控件加 data-mr-control="voltage" / "resistance" / "u" ...
# 生成器仍可用 data-solver-input，二者都认。
# 老页面：兼容 data-key、#rg-u、name= 等历史写法。
# 选择器按顺序尝试，找到第一个可见、可用的控件即用。
# ---------------------------------------------------------------------------

def _selectors(*names):
    selectors = []
    for name in names:
        selectors.extend((
            '[data-mr-control="%s"]' % name,
            '[data-solver-input="%s"]' % name,
            '[data-key="%s"]' % name,
            'input[name="%s"]' % name,
            'select[name="%s"]' % name,
        ))
    return selectors


CIRCUIT_VOLTAGE = _selectors("voltage", "U", "u") + ["#rg-u", "#rg-U"]
CIRCUIT_RESISTANCE = _selectors("resistance", "R", "r") + ["#rg-r", "#rg-R"]
CIRCUIT_SWITCH = _selectors("switch", "S", "s") + ["#rg-s", "#rg-S"]

LENS_U = _selectors("u", "object_distance", "objectDistance")
LENS_F = _selectors("f", "focal_length", "focalLength")

MIRROR_OBJECT_DISTANCE = _selectors("object_distance", "objectDistance", "u")
MIRROR_OBJECT_HEIGHT = _selectors("object_height", "objectHeight", "h")
MIRROR_OBSERVER_DISTANCE = _selectors("observer_distance", "observerDistance")
MIRROR_OBSERVER_HEIGHT = _selectors("observer_height", "observerHeight")
MIRROR_HALF_HEIGHT = _selectors("mirror_half_height", "mirrorHalfHeight")

WAVE_FREQUENCY = _selectors("frequency", "f")
WAVE_DETECTOR = _selectors("detector_distance", "detectorDistance", "distance")
WAVE_TRAVEL = _selectors("travel_time", "travelTime", "time")
WAVE_OBSERVATION = _selectors("observation_time", "observationTime")


def _control(selectors, baseline, transformed, kind="number"):
    return {"selectors": list(selectors), "baseline": baseline,
            "transformed": transformed, "kind": kind}


# ---------------------------------------------------------------------------
# 页面级变形计划
#
# 场景字段：
#   id          唯一编号，报告与测试都用它
#   title       人话标题（会出现在审查报告和修改意见里）
#   kind        关系类型（见 KINDS）
#   controls    需要设置的控件：baseline / transformed 两组值
#   relation    跨状态关系：x / y 是控件或读数键
#   state_checks 每个状态各自要满足的公式（formula 类）
#   optional    true 表示控件不存在时记 skip，不判失败
# ---------------------------------------------------------------------------

PAGE_PLANS = {
    # ------------------------------------------------------------------ 电路
    "CIRCUIT.solve": {
        "solver": "CIRCUIT.solve",
        "scenes": [
            {
                "id": "circuit.voltage-proportional",
                "title": "电压翻倍，电流翻倍（电阻不变）",
                "kind": "linearity",
                "controls": {
                    "voltage": _control(CIRCUIT_VOLTAGE, 3, 6),
                    "resistance": _control(CIRCUIT_RESISTANCE, 10, 10),
                },
                "relation": {"op": "proportional", "x": "control:voltage", "y": "circuit:current"},
                "tolerance": {"rel": 0.02, "abs": 0.005},
                "required_readout": "circuit:current",
                "advice": "电流表读数加 data-circuit-current-for，并保证读数来自 CIRCUIT.solve 的结果",
            },
            {
                "id": "circuit.resistance-inverse",
                "title": "电阻翻倍，电流减半（电压不变）",
                "kind": "inverse",
                "controls": {
                    "voltage": _control(CIRCUIT_VOLTAGE, 6, 6),
                    "resistance": _control(CIRCUIT_RESISTANCE, 10, 20),
                },
                "relation": {"op": "inverse", "x": "control:resistance", "y": "circuit:current"},
                "tolerance": {"rel": 0.02, "abs": 0.005},
                "required_readout": "circuit:current",
                # 只有“单一被测电阻”的电路才满足 I∝1/R；
                # 含滑动变阻器的串联电路里，总电阻不是 R，反比关系不成立。
                "precondition": {"circuit_resistors": 1},
                "advice": "确认电阻控件真的进入 __CIRCUIT_MODEL__，且电流表读数随之更新",
            },
            {
                "id": "circuit.switch-open-zero",
                "title": "断开开关，电流应为 0",
                "kind": "boundary",
                "optional": True,
                "controls": {
                    "switch": _control(CIRCUIT_SWITCH, 1, 0, kind="checkbox"),
                },
                "relation": {"op": "const", "y": "circuit:current", "value": 0},
                "tolerance": {"rel": 0.02, "abs": 0.005},
                "required_readout": "circuit:current",
                "advice": "开关控件加 data-mr-control=\"switch\"，断开后电流表必须显示 0 A，而不是报错或停在旧值",
            },
        ],
    },

    # ------------------------------------------------------------------ 凸透镜
    "PHYS.solveThinLens": {
        "solver": "PHYS.solveThinLens",
        "scenes": [
            {
                "id": "lens.gauss-formula",
                "title": "每个状态满足 1/f = 1/u + 1/v",
                "kind": "formula",
                "controls": {
                    "u": _control(LENS_U, 30, 15),
                    "f": _control(LENS_F, 10, 10),
                },
                "state_checks": [
                    {"op": "lens_formula"},
                    {"op": "readout_matches", "readout": "field:image_distance_cm",
                     "path": "image_distance_cm"},
                ],
                "globals": {"request": "__PHYS_LENS_REQUEST__", "result": "__PHYS_LENS_RESULT__"},
                "advice": "每次控件变化都重新调用 PHYS.solveThinLens，并把同一个结果交给读数与光路绘制",
            },
            {
                "id": "lens.magnification",
                "title": "放大率满足 m = -v/u",
                "kind": "formula",
                "controls": {
                    "u": _control(LENS_U, 30, 40),
                    "f": _control(LENS_F, 10, 10),
                },
                "state_checks": [
                    {"op": "lens_magnification"},
                    {"op": "readout_matches", "readout": "field:magnification",
                     "path": "magnification"},
                ],
                "globals": {"request": "__PHYS_LENS_REQUEST__", "result": "__PHYS_LENS_RESULT__"},
                "advice": "放大率读数必须读取求解结果的 magnification，不能另算一套",
            },
        ],
    },

    # ------------------------------------------------------------------ 平面镜
    "PHYS.solvePlaneMirror": {
        "solver": "PHYS.solvePlaneMirror",
        "scenes": [
            {
                "id": "mirror.image-distance",
                "title": "平面镜成像：像距等于物距，放大率为 1",
                "kind": "formula",
                "controls": {
                    "object_distance": _control(MIRROR_OBJECT_DISTANCE, 2, 4),
                    "object_height": _control(MIRROR_OBJECT_HEIGHT, 4, 4),
                    "observer_distance": _control(MIRROR_OBSERVER_DISTANCE, 2, 2),
                    "observer_height": _control(MIRROR_OBSERVER_HEIGHT, 0, 0),
                    "mirror_half_height": _control(MIRROR_HALF_HEIGHT, 3, 3),
                },
                "state_checks": [
                    {"op": "mirror_image_distance"},
                    {"op": "mirror_magnification"},
                    {"op": "readout_matches", "readout": "field:image_distance",
                     "path": "image_distance"},
                ],
                "globals": {"request": "__PHYS_PLANE_MIRROR_REQUEST__", "result": "__PHYS_PLANE_MIRROR_RESULT__"},
                "advice": "像距必须等于物距，放大率恒为 1；观察者位置只影响可见范围，不应改变像的位置",
            },
        ],
    },

    # ------------------------------------------------------------------ 波的传播
    "PHYS.solveWavePropagation": {
        "solver": "PHYS.solveWavePropagation",
        "scenes": [
            {
                "id": "wave.speed-formula",
                "title": "声速满足 v = 距离 / 传播耗时，且波长 = v / 频率",
                "kind": "formula",
                "controls": {
                    "detector_distance": _control(WAVE_DETECTOR, 6.8, 13.6),
                    "travel_time": _control(WAVE_TRAVEL, 0.02, 0.04),
                    "frequency": _control(WAVE_FREQUENCY, 170, 170),
                    "observation_time": _control(WAVE_OBSERVATION, 0.01, 0.01),
                },
                "state_checks": [
                    {"op": "wave_speed"},
                    {"op": "wave_wavelength"},
                    {"op": "readout_matches", "readout": "field:speed", "path": "speed"},
                    {"op": "readout_matches", "readout": "field:wavelength", "path": "wavelength"},
                ],
                "globals": {"request": "__PHYS_WAVE_PROPAGATION_REQUEST__",
                            "result": "__PHYS_WAVE_PROPAGATION_RESULT__"},
                "advice": "声速、波长、波前位置必须来自同一个 PHYS 求解结果；距离和耗时同时翻倍时声速应不变",
            },
        ],
    },
}


# 生成端可读的“页面必须提供什么”。reviewer 用它判断页面是否具备可执行条件，
# generator 以后也可以直接读它做生成前自检。
def required_controls(api):
    plan = PAGE_PLANS.get(api or "")
    if not plan:
        return []
    names = []
    for scene in plan.get("scenes", []):
        for name in (scene.get("controls") or {}):
            if name not in names:
                names.append(name)
    return names


def plan_for(api):
    """返回某求解器的页面变形计划（只读模板，调用方需要深拷贝）。"""
    return PAGE_PLANS.get(api or "")
