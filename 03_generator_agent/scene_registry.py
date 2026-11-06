# -*- coding: utf-8 -*-
"""Reusable page skeleton selection by subject and teaching topic.

Keep topic matching, prompt guidance, and generation-time hard checks in one
place so they cannot silently disagree.
"""

import re


SCENE_SKELETONS = [
    {
        "id": "chemistry-reaction-compare", "subject": "化学",
        "patterns": r"置换反应|硫酸铜|金属活动性|酸碱中和|溶液变色|反应前后|化学反应",
        "visual_type": "apparatus", "api": "CHEM.scene",
        "layout": "反应前后双烧杯对照 + 关键现象标签 + 方程式条。参数区保留影响反应的变量；结果区显示现象、产物和守恒核验。",
        "controls": "只保留有科学依据的反应物浓度、体积、质量或反应进度；将反应前后溶液和固体变化同步传入场景库。",
    },
    {
        "id": "chemistry-separation-stages", "subject": "化学",
        "patterns": r"粗盐提纯|过滤|蒸发结晶|溶解.{0,6}过滤|分离提纯|结晶实验|实验室制取",
        "visual_type": "process", "api": "CHEM.stages",
        "layout": "按真实实验顺序显示阶段卡；每阶段使用匹配的烧杯、漏斗或蒸发皿，并标明当前物态/观察现象。",
        "controls": "用步骤切换或逐步推进控制阶段；允许调节的变量必须影响对应阶段，不要将多步骤实验画成反应双烧杯。",
    },
    {
        "id": "chemistry-molecular-model", "subject": "化学",
        "patterns": r"分子|球棍|原子模型|化学键|微观结构|空间构型",
        "visual_type": "molecular", "api": None,
        "layout": "中心分子/粒子模型 + 原子与键图例 + 结构或计数结果；使用球棍或粒子阵列表达微观结构。",
        "controls": "参数控制原子种类、数目、键或构型；不得将反应宏观器材骨架硬套到分子模型。",
    },
    {
        "id": "physics-buoyancy-lab", "subject": "物理",
        "patterns": r"浮力|阿基米德|测力计|浸没|浮沉|排开液体",
        "visual_type": "apparatus", "api": "PHYS.floating",
        "layout": "烧杯液面 + 物块浸没状态 + 弹簧测力计/读数 + 力或体积关系。",
        "controls": "密度、浸没比等参数必须同步驱动物块位置、液面/排液读数、浮力和测力计示数。",
    },
    {
        "id": "physics-optics-bench", "subject": "物理",
        "patterns": r"凸透镜|光具座|物距|像距|透镜成像",
        "visual_type": "apparatus", "api": "PHYS.optics",
        "layout": "光具座 + 光学元件 + 物/像 + 带方向的光路 + 焦点和物像距标注。平面镜/折射变体需按其原理調整，不可誤用凸透鏡模型。",
        "controls": "物距、焦距、屏位置等控件要与成像位置、光线和公式读数共用状态。",
    },
    {
        "id": "physics-circuit-lab", "subject": "物理",
        "patterns": r"欧姆定律|电路|电压|电流|电阻|串联|并联",
        "visual_type": "apparatus", "api": None,
        "layout": "电源、开关、导线、用电器和电表组成可读电路；闭合路径、接线端和电表量程清楚。",
        "controls": "电压、电阻、开关状态改变时，同步更新电路状态、电流/电压表读数和公式。",
    },
    {
        "id": "math-cube-cut-3d", "subject": "数学",
        "patterns": r"正方体截面|截平面|平面截.{0,5}(正方体|立方体|长方体)",
        "visual_type": "geometry", "api": "MATH.cubeCut",
        "layout": "可旋转真 3D 立方体 + 截平面与截面高亮 + 顶点/边标注 + 边数面积结果。",
        "controls": "倾角、方位和偏移映射到 theta/phi/t；提供恢复默认视角按钮时必须调用 MATH.resetView(cv)。",
    },
    {
        "id": "math-function-exploration", "subject": "数学",
        "patterns": r"二次函数|一次函数|函数图像|抛物线|函数曲线|系数与图像",
        "visual_type": "graph", "api": "MATH.funcPlot",
        "layout": "坐标网格 + 函数曲线 + 关键点/对称轴/交点 + 参数变化提示。",
        "controls": "系数滑块应即时改变曲线与对应关键量；公式、图像和数据表来自同一次计算。",
    },
    {
        "id": "math-spatial-geometry", "subject": "数学",
        "patterns": r"空间想象|展开与折叠|外接球|内接球|空间几何|立体几何|长方体",
        "visual_type": "geometry", "api": None,
        "layout": "立体对象主视图 + 可交互视角/步骤 + 关键几何量；图形标记与结果区使用一致的数据。",
        "controls": "旋转、展开或尺寸参数必须影响几何图形；如有视角控制，提供可工作的视角复位。",
    },
    {
        "id": "biology-photosynthesis-leaf", "subject": "生物",
        "patterns": r"光合作用|绿叶在光下制造有机物|叶片淀粉|绿叶制造淀粉",
        "visual_type": "diagram", "api": "BIO.photosynthesis",
        "no_step_flow": True,
        "layout": "只绘制实验对象主图：有自然叶形和叶脉的叶片、光照/遮光或碘液显色结果。画布不得放步骤清单、六步流程、按钮或阶段导航。",
        "controls": "实验阶段切换放在③区，通过 phase='light'|'covered'|'iodine' 更新主图；不得把操作流程画进②演示区。",
    },
    {
        "id": "biology-microscope", "subject": "生物",
        "patterns": r"显微镜|洋葱表皮|细胞观察|显微视野",
        "visual_type": "apparatus", "api": "BIO.microscope",
        "layout": "圆形视野 + 可辨认细胞/组织 + 倍率与标尺信息 + 观察记录。",
        "controls": "倍率、染色或样本参数应改变视野和可见结构；数量/尺寸读数须与图示同源。",
    },
    {
        "id": "biology-process", "subject": "生物",
        "patterns": r"光合作用|遗传|豌豆|性状分离|细胞分裂|生理过程|食物链",
        "visual_type": "diagram", "api": None,
        "layout": "②演示区只显示实验对象/结构/结果图；阶段说明和逐步操作放在③区或⑥区，不能把流程列表塞进图中。",
        "controls": "时间、条件或遗传组合驱动主图/计数；需要逐步操作时放到③区控件，提供复位，不在②区绘制步骤导航。",
    },
    {
        "id": "geography-earth", "subject": "地理",
        "patterns": r"地球自转|地球公转|昼夜交替|四季成因|太阳高度|地球光照",
        "visual_type": "diagram", "api": "GEO.earth",
        "layout": "地球球体 + 经纬网 + 太阳光照方向 + 昼夜线/季节标记。",
        "controls": "日期、倾角或自转时刻同步更新光照、位置与读数。",
    },
    {
        "id": "geography-cross-section", "subject": "地理",
        "patterns": r"地层|地质剖面|地球圈层|地形剖面|等高线",
        "visual_type": "diagram", "api": "GEO.profile",
        "layout": "地表轮廓 + 分层剖面 + 图例/高度或深度标尺。",
        "controls": "图层或剖面参数应更新对应地形/岩层，并在结果区解释空间关系。",
    },
    {
        "id": "informatics-algorithm", "subject": "信息科技",
        "patterns": r"算法|排序|二分查找|数据结构|程序流程|数据流|位串",
        "visual_type": "process", "api": "CS.flow",
        "layout": "步骤节点/数据结构 + 当前状态高亮 + 输入输出和执行次数。",
        "controls": "播放/单步/重置改变算法状态；执行序列须与参考实现一致。",
    },
]


SUBJECT_DEFAULTS = {
    "化学": ("chemistry-lab", "apparatus", "化学实验通用版面：先明确反应器材、物态和观察现象；若命中已注册主题，必须优先使用其专用骨架。"),
    "物理": ("physics-investigation", "apparatus", "物理探究版面：器材/实验对象 + 可操作变量 + 同步测量读数；若命中已注册主题，必须优先使用其专用骨架。"),
    "数学": ("math-exploration", "graph", "数学探究版面：根据对象选函数图、统计图或几何图，展示关键量与可复算依据；若命中已注册主题，必须优先使用其专用骨架。"),
    "生物": ("biology-observation", "diagram", "生物观察/过程版面：②区只呈现实验对象、显微视野、结构图或结果对照；步骤与阶段操作放③区或⑥区。命中已注册主题时优先使用专用骨架。"),
    "地理": ("geography-spatial", "diagram", "地理空间过程版面：地图/球体/剖面与图例配套，突出空间位置或时间演变。"),
    "信息科技": ("informatics-stepper", "process", "信息科技步骤版面：状态序列/节点图 + 逐步执行控件 + 输出。"),
    "信息": ("informatics-stepper", "process", "信息科技步骤版面：状态序列/节点图 + 逐步执行控件 + 输出。"),
}

SUBJECT_ALIASES = {
    "物理学": "物理", "化学": "化学", "数学": "数学", "生物学": "生物",
    "地理学": "地理", "信息技术": "信息科技", "信息": "信息科技",
    "计算机": "信息科技", "编程": "信息科技", "算法": "信息科技",
}


def select_page_skeleton(req):
    """Return the highest-priority topic skeleton, else the subject default."""
    req = req or {}
    subject = str(req.get("学科", "")).strip()
    subject = SUBJECT_ALIASES.get(subject, subject)
    haystack = " ".join(str(req.get(k, "")) for k in
                        ("实验主题", "技术要点", "学习目标", "交互要求"))
    if isinstance(req.get("交互要求"), list):
        haystack += " " + " ".join(map(str, req["交互要求"]))
    for item in SCENE_SKELETONS:
        if item["subject"] == subject and re.search(item["patterns"], haystack, re.I):
            return dict(item)
    if subject == "数学" and re.search(r"概率|统计|平均数|方差|抽样", haystack):
        return {"id": "math-statistics", "subject": subject,
                "visual_type": "graph", "api": None,
                "layout": "数据样本/分布图 + 可调整样本或参数 + 统计量结果与计算依据。",
                "controls": "样本变更必须同步更新图表、均值/方差等统计量和记录表。"}
    key, visual_type, layout = SUBJECT_DEFAULTS.get(
        subject, ("general-investigation", "diagram", "按教学对象选择清晰的图示、操作与结果布局。"))
    return {"id": key, "subject": subject, "visual_type": visual_type,
            "api": None, "layout": layout,
            "controls": "每个控件都应改变教学对象或结果；显示公式、读数与图形须共用同一状态。"}


def required_scene_call(req):
    """Compatibility helper used by hard validation."""
    skeleton = select_page_skeleton(req)
    api = skeleton.get("api")
    if not api:
        return None
    return re.escape(api).replace(r"\.", r"\s*\.\s*") + r"\s*\(", api
