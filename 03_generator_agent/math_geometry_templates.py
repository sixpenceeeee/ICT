"""Adapters for math solvers whose public requests contain geometric structures."""

from pathlib import Path
import sys

POLYHEDRA = Path(__file__).resolve().parent / "solvers" / "mathematics" / "solid_sections" / "polyhedra"
if str(POLYHEDRA) not in sys.path:
    sys.path.insert(0, str(POLYHEDRA))

from mathematics.solid_sections.curved_solids.cone_section_solver import solve_cone_cut
from mathematics.solid_sections.curved_solids.cylinder_section_solver import solve_cylinder_cut
from mathematics.solid_sections.curved_solids.sphere_section_solver import solve_sphere_cut
from mathematics.solid_sections.polyhedra.cube_cut_solver import solve_cube_cut
from mathematics.solid_sections.polyhedra.cuboid_cut_solver import solve_cuboid_cut
from mathematics.solid_sections.polyhedra.square_pyramid_cut_solver import solve_square_pyramid_cut
from mathematics.solid_sections.polyhedra.triangular_prism_cut_solver import solve_triangular_prism_cut
from mathematics.solid_geometry.volume.solid_volume_solver import solve_composite_volume, solve_solid_volume
from mathematics.spatial_geometry.distance_angles.spatial_metrics_solver import solve_spatial_metrics
from math_page_plan import MathPlanError
import json


def section_reference(solve, q, dimensions):
    values = [q[name] for name in dimensions]
    if any(type(value) not in (int, float) or value <= 0 for value in values):
        raise ValueError("立体尺寸必须为正数")
    return solve(*values, n=[q["nx"], q["ny"], q["nz"]], offset=q["offset"])


def section_model(api, prefix, title, draw, solve, dimensions, curved=False):
    sizes = {name: value for name, (_, value) in dimensions.items()}
    labels = {name: label for name, (label, _) in dimensions.items()}
    start = {**sizes, "nx": 0 if curved else 1, "ny": 0 if curved else 1, "nz": 1, "offset": 0}
    changed = {**start, **{name: value * 1.5 for name, value in sizes.items()}, "offset": 0.5}
    fields = {"shape": "截面形状", "area": "截面积", "volume": "原立体体积"}
    if not curved:
        fields["sides"] = "截面边数"
    if api == "solveSphereCut":
        fields.update({"section_radius": "截圆半径", "center": "截圆圆心"})
    return {
        "api": api, "prefix": prefix, "title": title, "draw": "MATH." + draw, "visual": "geometry",
        "layout": "改变平面方程 n·x=d，观察截面边界、形状和面积。",
        "assumptions": "长度用同一单位，平面法向量不能为零。无截面时面积为 0。",
        "inputs": {**labels, "nx": "法向量 x 分量", "ny": "法向量 y 分量", "nz": "法向量 z 分量",
                   "offset": "平面偏移 d"},
        "positive": tuple(sizes), "fields": fields,
        "cases": {"base": start, "moved": changed, "tilted": {**start, "nx": 1, "ny": 0}},
        "request_js": ("{...cfg, dimensions:[cfg.length,cfg.width,cfg.height], n:[cfg.nx,cfg.ny,cfg.nz]}"
                       if api == "solveCuboidCut" else "{...cfg, n:[cfg.nx,cfg.ny,cfg.nz]}"),
        "draw_config": "request",
        "reference": lambda q: section_reference(solve, q, sizes),
    }


GEOMETRY_MODELS = {
    "cube-cut-3d": section_model("solveCubeCut", "MATH_CUBE", "平面截正方体", "cubeCut", solve_cube_cut,
                                 {"a": ("棱长", 2)}),
    "cuboid-section-3d": section_model("solveCuboidCut", "MATH_POLYHEDRON", "长方体截面",
                                       "cuboidSection", solve_cuboid_cut,
                                       {"length": ("长", 4), "width": ("宽", 3), "height": ("高", 2)}),
    "triangular-prism-section-3d": section_model("solveTriangularPrismCut", "MATH_POLYHEDRON", "三棱柱截面",
                                                 "triangularPrismSection", solve_triangular_prism_cut,
                                                 {"base": ("底边", 3), "triangleHeight": ("底面高", 2),
                                                  "length": ("棱柱长", 4)}),
    "square-pyramid-section-3d": section_model("solveSquarePyramidCut", "MATH_POLYHEDRON", "正四棱锥截面",
                                               "squarePyramidSection", solve_square_pyramid_cut,
                                               {"base": ("底面边长", 2), "height": ("锥高", 3)}),
    "sphere-section": section_model("solveSphereCut", "MATH_SPHERE", "球体截面", "sphereSection", solve_sphere_cut,
                                    {"radius": ("球半径", 5)}, curved=True),
    "cylinder-section": section_model("solveCylinderCut", "MATH_CYLINDER", "圆柱截面",
                                      "cylinderSection", solve_cylinder_cut,
                                      {"radius": ("底面半径", 2), "height": ("圆柱高", 4)}, curved=True),
    "cone-section": section_model("solveConeCut", "MATH_CONE", "圆锥截面", "coneSection", solve_cone_cut,
                                  {"radius": ("底面半径", 2), "height": ("圆锥高", 4)}, curved=True),
}


SOLIDS = {"cube": "正方体", "cuboid": "长方体", "triangular_prism": "直三棱柱", "square_pyramid": "正四棱锥",
          "cylinder": "圆柱", "cone": "圆锥", "sphere": "球"}
VOLUME_BASE = {"solid": "cuboid", "edge": 3, "length": 4, "width": 3, "height": 2,
               "base": 3, "triangle_height": 2, "radius": 2, "fraction": 0.5}
GEOMETRY_MODELS["solid-volume"] = {
    "api": "solveSolidVolume", "prefix": "MATH_VOLUME", "title": "立体体积与分割守恒",
    "draw": "drawVolume", "visual": "geometry", "reference": solve_solid_volume,
    "layout": "选择基本立体并调整尺寸；通过相似的小立体核对分割前后体积和。",
    "assumptions": "所有尺寸使用同一长度单位。分割按线性比例生成一块相似小立体与其余部分。",
    "inputs": {"solid": "立体类型", "edge": "棱长", "length": "长", "width": "宽", "height": "高",
               "base": "底面边长", "triangle_height": "三角形底面高", "radius": "半径", "fraction": "相似分割长度比"},
    "positive": ("edge", "length", "width", "height", "base", "triangle_height", "radius"),
    "ranges": {"fraction": (0, 1)}, "fields": {"volume": "体积（立方单位）"}, "choice_labels": SOLIDS,
    "cases": {**{"base": VOLUME_BASE, "large": {**VOLUME_BASE, "length": 6, "width": 4, "fraction": 0.75}},
              **{key: {**VOLUME_BASE, "solid": key} for key in SOLIDS if key != "cuboid"}},
}


def composite_volume_model(req):
    parts = req.get("组成部分")
    if req.get("内部不重叠") is not True or not isinstance(parts, list) or not 2 <= len(parts) <= 6:
        raise MathPlanError("组合体需要 2–6 个有明确尺寸的组成部分，并确认内部互不重叠。")
    try:
        base = solve_composite_volume(parts)["components"]
    except (TypeError, ValueError, KeyError, OverflowError) as exc:
        raise MathPlanError(f"组合体尺寸或立体类型无效：{exc}") from exc
    normalized = [{"solid": part["solid"], **part["dimensions"]} for part in base]
    encoded = json.dumps(normalized, ensure_ascii=True, allow_nan=False)
    return {
        "api": "solveSolidVolume", "solve_js": "MATH.solveCompositeVolume(request.components)",
        "prefix": "MATH_VOLUME", "title": "组合体体积", "draw": "drawComposite", "visual": "geometry",
        "reference": lambda q: q, "layout": "将互不重叠的组成部分分别展示，观察其体积和。",
        "assumptions": "各部分的尺寸使用同一单位；各部分内部互不重叠，整体体积可以相加。",
        "inputs": {"scale": "所有长度的同比缩放"}, "fields": {"volume": "组合体体积（立方单位）"},
        "cases": {"base": {"scale": 1}, "double": {"scale": 2}}, "ranges": {"scale": (0.01, 10)},
        "request_js": f"MATHPAGE.compositeRequest(cfg, {encoded})", "draw_config": "request",
    }


SPATIAL_OPERATIONS = {
    "point_plane_distance": "点到平面距离", "point_point_distance": "两点距离",
    "point_line_distance": "点到直线距离", "line_line_distance": "两直线距离",
    "line_line_angle": "两直线夹角", "line_plane_distance": "直线与平面距离",
    "line_plane_angle": "线面角", "plane_plane_distance": "两平面距离", "plane_plane_angle": "平面夹角",
}


def spatial_request(q):
    a, b, u, v = ([q[group + axis] for axis in "xyz"] for group in ("a", "b", "u", "v"))
    return {"operation": q["operation"], "p": a, "q": b, "point": a, "line_point": b,
            "line_direction": u, "plane_normal": v, "plane_offset": q["d"],
            "line1_point": a, "line2_point": b, "line1_direction": u, "line2_direction": v,
            "plane1_normal": u, "plane2_normal": v, "plane1_offset": q["d"], "plane2_offset": q["e"]}


SPATIAL_BASE = dict(operation="point_plane_distance", ax=1, ay=1, az=3, bx=0, by=0, bz=0,
                    ux=1, uy=0, uz=0, vx=0, vy=0, vz=1, d=1, e=2)
GEOMETRY_MODELS["spatial-metrics"] = {
    "api": "solveSpatialMetrics", "prefix": "MATH_SPATIAL", "title": "空间距离与角度",
    "draw": "drawSpatial", "visual": "geometry", "reference": lambda q: solve_spatial_metrics(spatial_request(q)),
    "layout": "选择距离或夹角类型，按图示修改点坐标、方向向量和法向量。",
    "assumptions": "平面使用 n·x=d，夹角取 0° 到 90°；方向和法向量不能为零。",
    "inputs": {"operation": "度量类型",
               **{g + a: f"{label}的 {a} 分量" for g, label in (("a", "点 A"), ("b", "点 B"),
                                                                 ("u", "向量 u"), ("v", "向量 v")) for a in "xyz"},
               "d": "平面偏移 d", "e": "第二平面偏移 e"},
    "fields": {"value": "距离或角度", "unit": "单位"},
    "choice_labels": SPATIAL_OPERATIONS,
    "cases": {"base": SPATIAL_BASE, "changed": {**SPATIAL_BASE, "az": 5},
              **{key: {**SPATIAL_BASE, "operation": key} for key in SPATIAL_OPERATIONS if key != "point_plane_distance"}},
    "request_js": "MATHPAGE.spatialRequest(cfg)", "draw_config": "request",
}


def validate_net_inputs(q):
    for key, value in q.items():
        if key == "layout":
            if value not in {"cross", "offset"}:
                raise ValueError("展开布局须为十字展开或错位展开")
        elif type(value) not in (int, float) or not 0 < value <= 1e6:
            raise ValueError("所有尺寸须为有限正数")


def net_model(api, prefix, title, inputs, first, second, request_js, draw):
    return {
        "api": api, "prefix": prefix, "title": title, "draw": draw, "visual": "geometry",
        "reference": validate_net_inputs,
        "layout": "左侧显示展开图，右侧显示由同一求解结果得出的折叠形状。",
        "assumptions": "两幅图使用同一组尺寸。展开图尺寸或邻接不匹配时，仅显示展开图及原因。",
        "inputs": inputs, "positive": tuple(name for name in inputs if name != "layout"),
        "fields": {"reason": "展开图判定"},
        "cases": {"base": first, "changed": second,
                  **({"offset": {**first, "layout": "offset"}} if "layout" in inputs else {})},
        "request_js": "MATHPAGE." + request_js, "draw_config": "request",
    }


GEOMETRY_MODELS.update({
    "cube-net-folding": net_model("solveCubeNet", "MATH_CUBE_NET", "正方体展开图",
                                  {"edge_length": "棱长", "layout": "展开布局"},
                                  {"edge_length": 1, "layout": "cross"}, {"edge_length": 2, "layout": "cross"},
                                  "cubeNetRequest(cfg)", "drawCubeNet"),
    "cuboid-net-folding": net_model("solveCuboidNet", "MATH_CUBOID_NET", "长方体展开图",
                                    {"a": "长", "b": "宽", "c": "高", "layout": "展开布局"},
                                    {"a": 4, "b": 3, "c": 2, "layout": "cross"},
                                    {"a": 6, "b": 4, "c": 3, "layout": "cross"},
                                    "cuboidNetRequest(cfg)", "drawCuboidNet"),
    "cylinder-net-unfolding": net_model("solveCylinderNet", "MATH_CYLINDER_NET", "圆柱展开图",
                                        {"radius": "底面半径", "height": "圆柱高", "stretch": "矩形宽度比例"},
                                        {"radius": 2, "height": 3, "stretch": 1},
                                        {"radius": 3, "height": 4, "stretch": 1.1},
                                        "cylinderNetRequest(cfg)", "drawCylinderNet"),
    "cone-net-unfolding": net_model("solveConeNet", "MATH_CONE_NET", "圆锥展开图",
                                    {"radius": "底面半径", "height": "圆锥高", "stretch": "扇形半径比例"},
                                    {"radius": 3, "height": 4, "stretch": 1},
                                    {"radius": 6, "height": 8, "stretch": 1.1},
                                    "coneNetRequest(cfg)", "drawConeNet"),
})
for model in GEOMETRY_MODELS.values():
    if model["api"] in ("solveCylinderNet", "solveConeNet"):
        model["fields"].update({"net_area": "展开面积", "surface_area": "立体表面积"})
    elif model["api"] in ("solveCubeNet", "solveCuboidNet"):
        model["fields"]["unique_face_normals"] = "折叠后的不同面方向数"
