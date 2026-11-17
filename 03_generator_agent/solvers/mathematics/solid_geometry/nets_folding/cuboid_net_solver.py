# -*- coding: utf-8 -*-
"""Validate and fold a rectangular net into a specified cuboid."""
from collections import deque
from itertools import permutations
import math


_DIRECTIONS = ((1, 0, "east"), (-1, 0, "west"), (0, 1, "south"), (0, -1, "north"))
_OPPOSITE = {"east": "west", "west": "east", "south": "north", "north": "south"}
_AXIS = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
_CORNER_SIGNS = ((-1, -1), (1, -1), (1, 1), (-1, 1))


def _add(a, b):
    return tuple(x+y for x, y in zip(a, b))


def _neg(v):
    return tuple(-x for x in v)


def _scale(v, factor):
    return tuple(x*factor for x in v)


def _cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def _near(a, b, eps):
    return abs(a-b) <= eps


def solve_cuboid_net(request):
    """Fold six axis-aligned net rectangles into a cuboid.

    Request format: ``{"dimensions":[length,width,height], "faces":[
    {"x":0,"y":0,"width":4,"height":3}, ...]}``. Net coordinates are
    arbitrary finite 2D positions; face dimensions are physical edge lengths.
    """
    if not isinstance(request, dict):
        raise ValueError("长方体展开图请求必须是对象")
    raw_dimensions = request.get("dimensions")
    if not isinstance(raw_dimensions, (list, tuple)):
        raise ValueError("长方体尺寸必须是长、宽、高三个数值")
    try:
        dimensions = tuple(float(x) for x in raw_dimensions)
        raw_faces = request.get("faces")
        if not isinstance(raw_faces, list):
            raise ValueError("faces 必须是六个矩形面组成的数组")
        rects = []
        for face in raw_faces:
            if not isinstance(face, dict):
                raise ValueError("每个展开面必须是矩形参数对象")
            rect = {key: float(face[key]) for key in ("x", "y", "width", "height")}
            rects.append(rect)
        raw_tolerance = request.get("tolerance")
        tolerance = float(1e-8 if raw_tolerance is None else raw_tolerance)
    except (TypeError, KeyError, ValueError) as exc:
        if isinstance(exc, ValueError) and str(exc).startswith(("faces ", "每个展开面")):
            raise
        raise ValueError("长方体尺寸、展开坐标和面宽高必须是有限数") from exc

    if len(dimensions) != 3 or any(not math.isfinite(x) or x <= 0 for x in dimensions):
        raise ValueError("长方体长、宽、高必须是三个有限正数")
    if len(rects) != 6:
        raise ValueError("长方体展开图必须恰有六个矩形面")
    if any(not all(math.isfinite(r[k]) for k in r) or r["width"] <= 0 or r["height"] <= 0 for r in rects):
        raise ValueError("展开面的位置必须有限，宽和高必须为正数")
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("几何容差必须为有限非负数")

    eps = tolerance * max(1.0, *dimensions, *(r["width"] for r in rects), *(r["height"] for r in rects))
    graph = [[] for _ in rects]
    hinges = []
    has_overlap = False
    has_partial_contact = False

    for i in range(6):
        a = rects[i]
        for j in range(i+1, 6):
            b = rects[j]
            overlap_x = min(a["x"]+a["width"], b["x"]+b["width"]) - max(a["x"], b["x"])
            overlap_y = min(a["y"]+a["height"], b["y"]+b["height"]) - max(a["y"], b["y"])
            if overlap_x > eps and overlap_y > eps:
                has_overlap = True

            relation = None
            if _near(a["x"]+a["width"], b["x"], eps):
                relation = ("east", max(0.0, min(a["y"]+a["height"], b["y"]+b["height"])
                                          - max(a["y"], b["y"])),
                            _near(a["y"], b["y"], eps) and _near(a["y"]+a["height"], b["y"]+b["height"], eps))
            elif _near(b["x"]+b["width"], a["x"], eps):
                relation = ("west", max(0.0, min(a["y"]+a["height"], b["y"]+b["height"])
                                         - max(a["y"], b["y"])),
                            _near(a["y"], b["y"], eps) and _near(a["y"]+a["height"], b["y"]+b["height"], eps))
            elif _near(a["y"]+a["height"], b["y"], eps):
                relation = ("south", max(0.0, min(a["x"]+a["width"], b["x"]+b["width"])
                                          - max(a["x"], b["x"])),
                            _near(a["x"], b["x"], eps) and _near(a["x"]+a["width"], b["x"]+b["width"], eps))
            elif _near(b["y"]+b["height"], a["y"], eps):
                relation = ("north", max(0.0, min(a["x"]+a["width"], b["x"]+b["width"])
                                          - max(a["x"], b["x"])),
                            _near(a["x"], b["x"], eps) and _near(a["x"]+a["width"], b["x"]+b["width"], eps))
            if relation and relation[1] > eps:
                direction, contact_length, full_edge = relation
                if full_edge:
                    graph[i].append((j, direction))
                    graph[j].append((i, _OPPOSITE[direction]))
                    hinges.append({"from": i, "to": j, "direction": direction,
                                   "length": contact_length})
                else:
                    has_partial_contact = True

    seen, queue = {0}, deque([0])
    while queue:
        current = queue.popleft()
        for neighbor, _ in graph[current]:
            if neighbor not in seen:
                seen.add(neighbor)
                queue.append(neighbor)
    connected = len(seen) == 6
    tree = connected and len(hinges) == 5
    base = {"solid": "cuboid", "dimensions": list(dimensions),
            "rectangles": [dict(r) for r in rects], "hinges": hinges,
            "connected": connected, "tree": tree, "hinge_count": len(hinges)}
    if has_overlap or has_partial_contact:
        reason = "展开图中矩形面发生面积重叠" if has_overlap else "相邻面只有部分边接触，公共棱长度不一致"
        checks = {"six_faces": True, "connected": connected, "tree": tree,
                  "dimensions_match": False, "six_distinct_face_normals": False,
                  "hinges_close": False}
        if has_overlap:
            checks["overlaps"] = True
        if has_partial_contact:
            checks["partial_edge_contact"] = True
        return {**base, "valid": False, "reason": reason, "faces": [],
                "unique_face_normals": 0, "hinge_residual": None, "checks": checks}
    if not connected or not tree:
        return {**base, "valid": False,
                "reason": "六个面必须通过五条完整公共棱连成一棵树" if connected else "展开图不连通",
                "faces": [], "unique_face_normals": 0, "hinge_residual": None,
                "checks": {"six_faces": True, "connected": connected, "tree": tree,
                           "dimensions_match": False, "six_distinct_face_normals": False,
                           "hinges_close": False}}

    def fold_for_root(root_axes):
        root = rects[0]
        root_u, root_v = _AXIS[root_axes[0]], _AXIS[root_axes[1]]
        root_frame = {"u": root_u, "v": root_v, "normal": _cross(root_u, root_v)}
        root_center = _scale(root_frame["normal"], dimensions[root_axes[2]]/2)
        frames = {0: root_frame}
        centers = {0: root_center}
        pending = deque([0])
        while pending:
            parent = pending.popleft()
            frame = frames[parent]
            u, v, normal = frame["u"], frame["v"], frame["normal"]
            p = rects[parent]
            for child, direction in graph[parent]:
                if child in frames:
                    continue
                q = rects[child]
                if direction == "east":
                    child_frame = {"u": _neg(normal), "v": v, "normal": u}
                    hinge_center = _add(centers[parent], _scale(u, p["width"]/2))
                    child_center = _add(hinge_center, _scale(child_frame["u"], q["width"]/2))
                elif direction == "west":
                    child_frame = {"u": normal, "v": v, "normal": _neg(u)}
                    hinge_center = _add(centers[parent], _scale(u, -p["width"]/2))
                    child_center = _add(hinge_center, _scale(child_frame["u"], -q["width"]/2))
                elif direction == "south":
                    child_frame = {"u": u, "v": _neg(normal), "normal": v}
                    hinge_center = _add(centers[parent], _scale(v, p["height"]/2))
                    child_center = _add(hinge_center, _scale(child_frame["v"], q["height"]/2))
                else:
                    child_frame = {"u": u, "v": normal, "normal": _neg(v)}
                    hinge_center = _add(centers[parent], _scale(v, -p["height"]/2))
                    child_center = _add(hinge_center, _scale(child_frame["v"], -q["height"]/2))
                frames[child] = child_frame
                centers[child] = child_center
                pending.append(child)

        face_data = []
        normal_set = set()
        dimensions_match = True
        for i, rect in enumerate(rects):
            f = frames[i]
            normal_set.add(f["normal"])
            u_axis = next((k for k, axis in enumerate(_AXIS) if f["u"] in (axis, _neg(axis))), None)
            v_axis = next((k for k, axis in enumerate(_AXIS) if f["v"] in (axis, _neg(axis))), None)
            dimensions_match = dimensions_match and _near(rect["width"], dimensions[u_axis], eps) \
                and _near(rect["height"], dimensions[v_axis], eps)
            vertices = []
            for su, sv in _CORNER_SIGNS:
                point = _add(centers[i], _add(_scale(f["u"], su*rect["width"]/2),
                                              _scale(f["v"], sv*rect["height"]/2)))
                vertices.append(list(point))
            face_data.append({"index": i, "rect": dict(rect), "width": rect["width"],
                              "height": rect["height"], "u_axis": u_axis, "v_axis": v_axis,
                              "normal": list(f["normal"]), "center": list(centers[i]),
                              "vertices": vertices})

        residual = 0.0
        for hinge in hinges:
            direction = hinge["direction"]
            first, second = hinge["from"], hinge["to"]
            def points_on_edge(index, side):
                rect = rects[index]
                frame = frames[index]
                sign_u = 1 if side == "east" else -1 if side == "west" else None
                sign_v = 1 if side == "south" else -1 if side == "north" else None
                signs = [pair for pair in _CORNER_SIGNS
                         if (sign_u is None or pair[0] == sign_u)
                         and (sign_v is None or pair[1] == sign_v)]
                return [_add(centers[index], _add(_scale(frame["u"], su*rect["width"]/2),
                                                   _scale(frame["v"], sv*rect["height"]/2)))
                        for su, sv in signs]
            va = points_on_edge(first, direction)
            vb = points_on_edge(second, _OPPOSITE[direction])
            residual = max(residual, *(min(math.dist(p, q) for q in vb) for p in va))
        return face_data, len(normal_set), dimensions_match, residual

    root_candidates = [p for p in permutations(range(3))
                       if _near(rects[0]["width"], dimensions[p[0]], eps)
                       and _near(rects[0]["height"], dimensions[p[1]], eps)]
    folded = None
    for candidate in root_candidates:
        attempt = fold_for_root(candidate)
        if attempt[2]:
            folded = attempt
            break
    if folded is None:
        return {**base, "valid": False, "reason": "展开面尺寸与给定长、宽、高不匹配",
                "faces": [], "unique_face_normals": 0, "hinge_residual": None,
                "checks": {"six_faces": True, "connected": True, "tree": True,
                           "dimensions_match": False, "six_distinct_face_normals": False,
                           "hinges_close": False}}

    faces, normal_count, dimensions_match, residual = folded
    cardinal = {axis for unit in _AXIS for axis in (unit, _neg(unit))}
    distinct = normal_count == 6 and {tuple(face["normal"]) for face in faces} == cardinal
    hinges_close = residual <= eps
    valid = dimensions_match and distinct and hinges_close
    reason = "合法长方体展开图" if valid else (
        "折叠后面尺寸与长方体不一致" if not dimensions_match else
        "折叠后存在重合面" if not distinct else "公共棱端点无法闭合")
    return {**base, "valid": valid, "reason": reason, "faces": faces,
            "unique_face_normals": normal_count, "hinge_residual": residual,
            "checks": {"six_faces": True, "connected": True, "tree": True,
                       "dimensions_match": dimensions_match,
                       "six_distinct_face_normals": distinct,
                       "hinges_close": hinges_close}}
