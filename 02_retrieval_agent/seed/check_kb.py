# -*- coding: utf-8 -*-
"""知识库自检：主题识别、求解器覆盖、知识包全链路与跨主题污染。

覆盖主题/profile、页面场景/求解器 API、五类知识条目、真实多路检索组包、
同学科相近主题区分和跨学科范围过滤，避免只检查“文件存在”却检索不到。
"""
import argparse
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PROJ = os.path.dirname(ROOT)
sys.path.insert(0, PROJ)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(PROJ, "03_generator_agent"))

import build_kb
import kb as kbmod
from math_solver_kb import SOLVER_TOPICS as MATH_SOLVER_TOPICS
import retrieval_agent as retrieval
import scene_registry
import topics as tp


CHEM_SOLVER_TOPICS = {
    "CHEMSOLVER.balanceEquation": "化学方程式配平",
    "CHEMSOLVER.solveStoichiometry": "反应计量与限量试剂",
    "CHEMSOLVER.solveSolutionMixing": "溶液混合与反应计量",
    "CHEMSOLVER.solveAcidBaseTitration": "酸碱中和滴定",
    "CHEMSOLVER.solveGasCollection": "气体制取与集气定量",
    "CHEMSOLVER.solvePrecipitation": "沉淀反应定量",
    "CHEMSOLVER.solveRedox": "氧化还原方程式配平",
    "CHEMSOLVER.solveSolubilityEquilibrium": "溶解平衡与 Ksp",
}

CHEM_SCENE_TOPICS = {
    "chemistry-separation-stages": "化学分离与提纯",
    "chemistry-molecular-model": "分子结构与微观模型",
}

CHEM_SOLVER_PROBES = [
    ("配平化学方程式并检查最简整数系数", "化学方程式配平"),
    ("根据反应物的量判断限量试剂和理论产量", "反应计量与限量试剂"),
    ("两份溶液混合，按浓度体积 n=cV 计算反应量", "溶液混合与反应计量"),
    ("强酸强碱中和滴定，求当量点和 pH", "酸碱中和滴定"),
    ("排水集气，使用 PV=nRT 修正气体体积", "气体制取与集气定量"),
    ("计算氯化银沉淀质量与净离子方程式", "沉淀反应定量"),
    ("酸性介质中高锰酸根与亚铁离子氧化还原电子守恒配平", "氧化还原方程式配平"),
    ("CaF2 的 KSP 溶度积、共同离子效应与溶解平衡", "溶解平衡与 Ksp"),
    ("粗盐提纯的溶解过滤蒸发结晶流程", "化学分离与提纯"),
    ("H2O 球棍模型、化学键和分子空间结构", "分子结构与微观模型"),
]

CHEM_SCENE_SELECTION_PROBES = [
    ("给定 H2、O2 和 H2O，配平化学方程式并核对原子数。", "CHEMSOLVER.balanceEquation"),
    ("根据 2H2+O2→2H2O 和各反应物 mol 数，计算限量试剂、剩余量和理论产量。",
     "CHEMSOLVER.solveStoichiometry"),
    ("混合两份已知浓度和体积的 AgNO3 与 NaCl 溶液，按给定方程计算反应物剩余量。",
     "CHEMSOLVER.solveSolutionMixing"),
    ("酸碱中和滴定 HCl 与 NaOH，展示当量点前后 pH，并提供酸碱浓度、样品体积和滴定液体积控件。",
     "CHEMSOLVER.solveAcidBaseTitration"),
    ("根据已配平反应计算制得 O2 的量，并比较干燥集气和排水集气时的气体体积。",
     "CHEMSOLVER.solveGasCollection"),
    ("混合 AgNO3 与 NaCl 溶液，计算氯化银沉淀质量、限量试剂与净离子方程式。",
     "CHEMSOLVER.solvePrecipitation"),
    ("在酸性条件下配平 MnO4- 与 Fe2+ 的氧化还原离子方程式并展示电子守恒。",
     "CHEMSOLVER.solveRedox"),
    ("探究 CaF2 的 Ksp、Q/Ksp 饱和状态和共同离子对摩尔溶解度的影响。",
     "CHEMSOLVER.solveSolubilityEquilibrium"),
]

PHYSICS_PROBES = [
    ("CIRCUIT.solve", "电路", "探究欧姆定律，调节电源电压与电阻，观察电流"),
    ("CIRCUIT.solve", "伏安法测电阻", "用伏安法测电阻，接入电流表和电压表"),
    ("CIRCUIT.solve", "串并联电路", "串并联电路的等效电阻、分压和分流"),
    ("PHYS.solveThinLens", "凸透镜成像", "凸透镜成像，比较焦点和两倍焦距"),
    ("PHYS.solveBuoyancy", "浮力", "阿基米德原理与物体浮沉，比较浸没比和液体密度"),
    ("PHYS.solveLever", "杠杆平衡", "杠杆平衡实验，增大力同时减小力臂"),
    ("PHYS.solveLiquidPressure", "液体压强", "用压强计探究液面以下深度和静水压强"),
    ("PHYS.solveSpecificHeat", "比热容", "同样吸热量下比较水和其他材料的温升"),
    ("PHYS.solveUniformAcceleration", "匀变速直线运动", "匀变速直线运动，区分反向运动的路程与位移"),
    ("PHYS.solveHorizontalProjectile", "平抛运动", "小球水平抛出，比较水平速度和落点"),
    ("PHYS.solveRefraction", "折射与全反射", "光从高折射率介质入射，比较临界角前后的全反射"),
    ("PHYS.solveHorizontalForce", "一维受力与摩擦", "水平推物块，比较静摩擦、动摩擦和牛顿第二定律"),
    ("PHYS.solveWorkPower", "功与功率", "同一个恒力做功，改变力与位移夹角和耗时"),
    ("PHYS.solveMechanicalEnergy", "机械能变化与守恒", "机械能守恒实验，加入摩擦力做功并比较末速度"),
    ("PHYS.solveInclinedPlane", "斜面", "光滑和粗糙斜面的匀速拉升实验，比较拉力和总功"),
    ("PHYS.solvePulleySystem", "滑轮组", "滑轮组实验，用相同滑轮总数对比不同承重绳段"),
    ("PHYS.solvePlaneMirror", "平面镜成像", "缩短平面镜并移动眼睛，观察像的可见区间"),
    ("PHYS.solveWavePropagation", "波的传播与声速", "改变声波频率，比较声速、波长和到达时间"),
]


def check_physics_coverage(kb, seed):
    """Check the same topic selection and knowledge pack used in the pipeline."""
    registered = {item["solver_api"] for item in scene_registry.SCENE_SKELETONS
                  if item["subject"] == "物理" and item.get("solver_api")}
    verified = {api for api, _, _ in PHYSICS_PROBES}
    missing = registered ^ verified
    if missing:
        print("  ✗ 物理求解器覆盖表与注册表不一致：%s" % "、".join(sorted(missing)))
    grades = {topic["主题"]: topic["学段"] for topic in seed}
    expected_categories = set(retrieval.CATEGORY_ORDER)
    failed = bool(missing)
    for api, topic, title in PHYSICS_PROBES:
        req = {"学科": "物理", "年级": grades.get(topic, "初中"), "实验主题": title,
               "学习目标": [], "核心变量": []}
        detected = retrieval.select_knowledge_topic(req)
        selected = scene_registry.select_page_skeleton(req).get("solver_api")
        ranked = retrieval.retrieve(kb, retrieval.build_queries(req, detected), topic=detected)
        pack, _ = retrieval.build_pack(req, ranked)
        categories = {name for name, items in pack.items() if items}
        count = sum(len(items) for items in pack.values())
        ok = (detected == topic and selected == api and categories == expected_categories and count >= 4
              and tp.profile_of(topic).get("学科") == "物理"
              and all(item["chunk"]["主题"] == topic for item in ranked))
        print("  %s %-12s 识别=%s / %s / %d 条 %d 类" % (
            "✓" if ok else "✗", topic, detected or "无", selected or "无", count, len(categories)))
        failed |= not ok

    # A physical topic mentioned in an explanation must not replace the page's topic.
    mixed = (
        ("液体压强", ["与浮力、阿基米德原理、浸没和浮沉条件作对照"]),
        ("机械能变化与守恒", ["观察斜面中的摩擦力、静摩擦、动摩擦和功率"]),
        ("平面镜成像", ["比较凸透镜物距、焦距、像距和全反射的差异"]),
    )
    for title, goals in mixed:
        req = {"学科": "物理", "实验主题": title, "学习目标": goals}
        detected = retrieval.select_knowledge_topic(req)
        ranked = retrieval.retrieve(kb, retrieval.build_queries(req, detected), topic=detected)
        categories = {item["chunk"]["类别"] for item in ranked}
        if detected != title or categories != expected_categories or any(
                item["chunk"]["主题"] != title for item in ranked):
            print("  ✗ 物理标题优先与知识覆盖：%s → %s / %d 类" % (title, detected or "无", len(categories)))
            failed = True
    return not failed


MATH_SOLVER_PROBES = {
    "solveQuadratic": "用抛物线说明一元二次方程的判别式和实根个数",
    "solveCubeCut": "平面截正方体，改变截平面并检查边数与分割体积",
    "solveCubeNet": "正方体的展开图能否折成立方体",
    "solveRightTriangle": "在直角三角形中用两条直角边求斜边和锐角三角比",
    "solveDescriptiveStats": "调整五个观测值，观察均值与方差怎样变化",
    "solveLinearSystem": "用两条一次函数直线的交点解释二元一次方程组",
    "solveSequences": "拖动首项、公差和公比，比较等差数列和等比数列的前 n 项和",
    "solveReciprocal": "改变反比例系数与横坐标，观察反比例函数的双曲线",
    "solveSinusoid": "通过振幅与周期控件探究正弦函数图像",
    "solveExpLog": "在同一坐标系比较指数函数和对数函数的底数变化",
    "solveFunctionTransform": "函数图像的变换，拖动水平平移和纵向伸缩",
    "solveDerivative": "在二次函数上移动切点，观察导数与切线斜率",
    "solveSimilarTriangles": "改变相似三角形的相似比，比较周长和面积",
    "solveCircle": "用垂径定理和圆周角解释弦距、弦长与圆心角",
    "solvePolygonArea": "用割补法演示梯形面积公式和等积矩形",
    "solveConstructions": "用尺规作图构造垂直平分线和角平分线",
    "solveEllipse": "调整椭圆长短半轴，观察焦点与离心率",
    "solveSampling": "摸球实验中的放回与不放回抽样",
    "solveBinomial": "画二项分布，比较独立重复试验的成功次数",
    "solveRegression": "改变三个数据点，观察一元线性回归的残差",
    "solveDotProduct": "调整平面向量的分量，显示数量积和垂直情形",
    "solveFractions": "用数轴展示异分母分数加法和减法的通分",
    "solveAmgm": "用半圆比较几何平均与算术平均，演示基本不等式",
    "solveOrthographic": "台阶形立体的三视图，显示三个投影面积和体积",
    "solveSphereContact": "长方体的内切球和外接球，比较接触面数",
    "solveSurfacePath": "长方体的表面最短路径，比较三种展开",
    "solveCavalieri": "用祖暅原理比较斜棱柱和直棱柱的体积",
    "solveTravel": "画位置–时间图像，演示行程问题中的相向而行和同向追及",
    "solveSquarePyramidCut": "平面截正四棱锥，显示截面顶点和面积",
    "solveTriangularPrismCut": "平面截三棱柱并显示边数、面积",
    "solveCuboidCut": "旋转截平面，观察长方体截面的形状和面积",
    "solveSolidVolume": "计算组合体体积，检验不重叠部件的体积分割守恒",
    "solveSpatialMetrics": "用空间向量求点到平面距离和线面角",
    "solveSphereCut": "平面截球，改变偏移量判断截圆、相切或无交",
    "solveConeNet": "改变圆锥的展开图扇形弧长，检查折叠有效性",
    "solveConeCut": "平面截圆锥，查看水平切割和过顶点切割",
    "solveCylinderNet": "圆柱侧面展开图，比较矩形宽与底面周长",
    "solveCylinderCut": "平面截圆柱，比较轴截面和水平截面积",
    "solveCuboidNet": "长方体的展开图，检查三对面与折叠闭合",
}


def check_math_coverage(kb, seed):
    """Verify each registered solver's scene, topic and five-category pack."""
    prefix = "MATH."
    registered = {item["solver_api"].removeprefix(prefix) for item in scene_registry.SCENE_SKELETONS
                  if item["subject"] == "数学" and item.get("solver_api", "").startswith(prefix)}
    expected_categories = set(retrieval.CATEGORY_ORDER)
    levels = {item["主题"]: item["学段"] for item in seed if item["学科"] == "数学"}
    covered = MATH_SOLVER_TOPICS.keys() & MATH_SOLVER_PROBES.keys()
    failures = sorted((registered - covered) | ((MATH_SOLVER_TOPICS.keys() | MATH_SOLVER_PROBES.keys()) - registered))
    for api in sorted(registered & covered):
        wanted, query = MATH_SOLVER_TOPICS[api], MATH_SOLVER_PROBES[api]
        req = {"学科": "数学", "年级": levels.get(wanted, ""), "实验主题": query,
               "学习目标": [], "核心变量": []}
        actual_api = scene_registry.select_page_skeleton(req).get("solver_api")
        detected = retrieval.select_knowledge_topic(req)
        ranked = retrieval.retrieve(kb, retrieval.build_queries(req, detected), final_k=12, topic=detected)
        pack, _ = retrieval.build_pack(req, ranked)
        categories = {name for name, entries in pack.items() if entries}
        retrieved_topics = {item["chunk"]["主题"] for item in ranked}
        ok = (actual_api == prefix + api and detected == wanted and wanted in levels
              and categories == expected_categories and retrieved_topics == {wanted})
        print("  %s %-16s 场景=%s 主题=%s %d 类" %
              ("✓" if ok else "✗", wanted, actual_api or "无", detected or "无", len(categories)))
        if not ok:
            failures.append(api)
    if failures:
        print("  未通过：%s" % "、".join(failures))
    else:
        print("  全部 %d 个数学求解器均能检索到对应主题和五类知识" % len(registered))
    return failures


def main():
    parser = argparse.ArgumentParser(description="检查知识库主题和求解器知识包")
    parser.add_argument("--physics", action="store_true", help="只检查物理求解器场景与知识包")
    args = parser.parse_args()
    seed = build_kb.load_topics()
    kb = kbmod.KnowledgeBase()
    if args.physics:
        print("物理求解器场景与五类知识包")
        return 0 if check_physics_coverage(kb, seed) else 1

    print("=" * 72)
    print("一、主题识别")
    miss = []
    for t in seed:
        got = tp.detect_topic(t["主题"], t["学科"])
        if got != t["主题"]:
            miss.append((t["主题"], got))
    if miss:
        for name, got in miss:
            print("  ✗ %-10s → %s" % (name, got or "None"))
    else:
        print("  全部 %d 个主题识别正确" % len(seed))

    print("=" * 72)
    print("数学求解器主题覆盖")
    math_miss = check_math_coverage(kb, seed)

    print("=" * 72)
    print("化学求解器主题覆盖")
    scene_path = os.path.join(PROJ, "03_generator_agent", "scene_registry.py")
    with io.open(scene_path, "r", encoding="utf-8") as f:
        scene_source = f.read()
    seed_names = {t["主题"] for t in seed}
    coverage_miss = []
    for registry_item, topic in {**CHEM_SOLVER_TOPICS, **CHEM_SCENE_TOPICS}.items():
        if registry_item not in scene_source or topic not in seed_names or topic not in kb.by_topic:
            coverage_miss.append((registry_item, topic))
    if coverage_miss:
        for api, topic in coverage_miss:
            print("  ✗ %-45s → %s 缺场景注册/主题/知识条目" % (api, topic))
    else:
        print("  全部 %d 个化学求解器 API 和 %d 个专用场景都有对应主题与知识条目"
              % (len(CHEM_SOLVER_TOPICS), len(CHEM_SCENE_TOPICS)))

    scene_miss = []
    for query, expected_api in CHEM_SCENE_SELECTION_PROBES:
        scene = scene_registry.select_page_skeleton({
            "学科": "化学", "年级": "高中", "实验主题": query,
        })
        actual_api = scene.get("solver_api")
        ok = actual_api == expected_api
        print("  %s 页面骨架 %-38s → %s" % (
            "✓" if ok else "✗", expected_api, actual_api or scene.get("id")))
        if not ok:
            scene_miss.append((query, expected_api, actual_api, scene.get("id")))

    probe_miss = []
    for query, wanted in CHEM_SOLVER_PROBES:
        detected = tp.detect_topic(query, "化学")
        hits = kb.search(query, top_k=5)
        retrieved = hits[0][0]["主题"] if hits else None
        ok = detected == wanted and retrieved == wanted
        print("  %s %-18s 识别=%s 检索=%s" % (
            "✓" if ok else "✗", wanted, detected or "无", retrieved or "无"))
        if not ok:
            probe_miss.append((query, wanted, detected, retrieved))

    print("=" * 72)
    print("知识包全链路覆盖（需求 → 主题 → 多路检索 → 五类知识）")
    pack_miss = []
    expected_categories = set(retrieval.CATEGORY_ORDER)
    for query, wanted in CHEM_SOLVER_PROBES:
        req = {"学科": "化学", "年级": "高中", "实验主题": query,
               "学习目标": [], "核心变量": []}
        detected = tp.detect_topic(query, req["学科"])
        ranked = retrieval.retrieve(
            kb, retrieval.build_queries(req, detected), final_k=12, topic=detected)
        pack, _ = retrieval.build_pack(req, ranked)
        categories = {name for name, entries in pack.items() if entries}
        count = sum(len(entries) for entries in pack.values())
        wrong_topic = any(item["chunk"]["主题"] != wanted for item in ranked)
        ok = (detected == wanted and count >= 4 and categories == expected_categories
              and not wrong_topic)
        print("  %s %-18s %d 条 / %d 类" % (
            "✓" if ok else "✗", wanted, count, len(categories)))
        if not ok:
            pack_miss.append((query, wanted, detected, count, sorted(categories), wrong_topic))

    subject_scope_miss = []
    for query, subject in (("电路 电阻 电压 电流 欧姆定律", "化学"),
                           ("CaF2 KSP 溶度积 共同离子效应", "物理")):
        got = tp.detect_topic(query, subject)
        if got is not None:
            subject_scope_miss.append((query, subject, got))
    print("  %s 学科范围过滤（化学需求不误入物理主题，物理需求不误入化学主题）" %
          ("✓" if not subject_scope_miss else "✗"))

    print("=" * 72)
    print("物理求解器场景与五类知识包")
    physics_ok = check_physics_coverage(kb, seed)

    print("=" * 72)
    print("二、检索类别覆盖（top8）")
    thin = []
    for t in seed:
        q = " ".join(t["关键词"][:4]) + " " + t["核心公式"]
        hits = kb.search(q, top_k=8, topic=t["主题"])
        cats = {c["类别"] for c, _ in hits}
        if len(cats) < 4:
            thin.append((t["主题"], sorted(cats)))
    if thin:
        for name, cats in thin:
            print("  ! %-10s 只命中 %d 类：%s" % (name, len(cats), "、".join(cats)))
    else:
        print("  全部主题 top8 覆盖 ≥4 类")

    print("=" * 72)
    print("三、跨主题污染（不指定 topic，全库检索）")
    probes = [
        ("CaF2 KSP 溶度积 溶解平衡 共同离子效应", "溶解平衡与 Ksp"),
        ("KNO3 溶解度曲线 80℃ 降温结晶 溶解度", "溶解度曲线"),
        ("凸透镜 物距 像距 焦距", "凸透镜成像"),
        ("冒泡排序 比较 交换 轮次", "冒泡排序"),
        ("等高线 山脊 山谷 剖面", "等高线剖面"),
        ("光合作用 遮光 碘液 淀粉", "光合作用"),
        ("金属活动性 置换 稀盐酸", "金属活动性"),
        ("勾股定理 直角三角形 斜边", "勾股定理"),
    ]
    bad = 0
    for q, want in probes:
        hits = kb.search(q, top_k=5)
        top_topic = hits[0][0]["主题"] if hits else "无"
        ok = top_topic == want
        bad += 0 if ok else 1
        print("  %s %-22s → %s" % ("✓" if ok else "✗", q[:12], top_topic))

    print("=" * 72)
    print("片段总数 %d，主题数 %d" % (len(kb.chunks), len(kb.topics())))
    return 0 if (not miss and not math_miss and not coverage_miss and not scene_miss
                 and not probe_miss and not pack_miss
                 and not subject_scope_miss and physics_ok and not thin and not bad) else 1


if __name__ == "__main__":
    sys.exit(main())
