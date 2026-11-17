# -*- coding: utf-8 -*-
"""Validate and fold a six-square net into a unit-topology cube."""
from collections import deque
import math


_DIRS = ((1, 0, "east"), (-1, 0, "west"), (0, 1, "north"), (0, -1, "south"))
_ZERO, _X, _Y, _Z = (0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)


def _neg(v):
    return tuple(-x for x in v)


def _add(a, b):
    return tuple(x+y for x, y in zip(a, b))


def _scale(v, k):
    return tuple(x*k for x in v)


def solve_cube_net(cells, edge_length=1.0, tolerance=1e-8):
    """Fold integer-grid square cells by 90° about shared edges.

    A valid cube net must have six unique cells, form a connected tree through
    shared edges, and fold to the six distinct axis normals of a cube.
    """
    if edge_length is None:
        edge_length = 1.0
    if tolerance is None:
        tolerance = 1e-8
    try:
        edge_length = float(edge_length)
        tolerance = float(tolerance)
        coords = [tuple(cell) for cell in cells]
    except (TypeError, ValueError) as exc:
        raise ValueError("展开图必须提供可精确表示的整数网格坐标") from exc
    if not math.isfinite(edge_length) or edge_length <= 0:
        raise ValueError("正方形边长必须为有限正数")
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("折叠闭合容差必须为有限非负数")
    if len(coords) != 6 or any(len(c) != 2 or any(type(v) is not int or abs(v) > 2**53-1 for v in c) for c in coords):
        raise ValueError("正方体展开图必须恰有六个可精确表示坐标的网格正方形")
    if len(set(coords)) != 6:
        raise ValueError("展开图不能有重叠或重复的正方形位置")
    cells_set = set(coords)
    graph = {c: [] for c in coords}
    hinges = []
    for c in coords:
        for dx, dy, direction in _DIRS:
            neighbor = (c[0]+dx, c[1]+dy)
            if neighbor in cells_set:
                graph[c].append((neighbor, direction))
                if c < neighbor:
                    hinges.append({"from": list(c), "to": list(neighbor), "direction": direction})
    seen, queue = {coords[0]}, deque([coords[0]])
    while queue:
        current = queue.popleft()
        for neighbor, _ in graph[current]:
            if neighbor not in seen:
                seen.add(neighbor)
                queue.append(neighbor)
    connected = len(seen) == 6
    tree = connected and len(hinges) == 5
    result_base = {"solid": "cube", "edge_length": edge_length,
                   "cells": [list(c) for c in coords], "hinges": hinges,
                   "connected": connected, "hinge_count": len(hinges), "tree": tree}
    if not connected or not tree:
        return {**result_base, "valid": False,
                "reason": "六个面必须通过五条公共边连成一棵树" if connected else "展开图不连通",
                "faces": [], "unique_face_normals": 0, "hinge_residual": None}

    frames = {coords[0]: {"u": _X, "v": _Y, "normal": _Z}}
    queue = deque([coords[0]])
    while queue:
        cell = queue.popleft()
        frame = frames[cell]
        u, v, normal = frame["u"], frame["v"], frame["normal"]
        for neighbor, direction in graph[cell]:
            if neighbor in frames:
                continue
            if direction == "east":
                child = {"u": _neg(normal), "v": v, "normal": u}
            elif direction == "west":
                child = {"u": normal, "v": v, "normal": _neg(u)}
            elif direction == "north":
                child = {"u": u, "v": _neg(normal), "normal": v}
            else:
                child = {"u": u, "v": normal, "normal": _neg(v)}
            frames[neighbor] = child
            queue.append(neighbor)

    half = edge_length/2
    faces = []
    normal_set = set()
    for cell in coords:
        f = frames[cell]
        n = f["normal"]
        normal_set.add(n)
        center = _scale(n, half)
        corners = []
        for su, sv in ((-1,-1),(1,-1),(1,1),(-1,1)):
            point = _add(center, _add(_scale(f["u"], su*half), _scale(f["v"], sv*half)))
            corners.append(list(point))
        faces.append({"cell": list(cell), "normal": list(n), "center": list(center), "vertices": corners})

    def face_map():
        return {tuple(face["cell"]): face for face in faces}

    mapped = face_map()
    residual = 0.0
    for hinge in hinges:
        a, b = tuple(hinge["from"]), tuple(hinge["to"])
        fa, fb = mapped[a], mapped[b]
        # Compare unordered 3D corner sets lying on the common hinge edge.
        dx, dy = b[0]-a[0], b[1]-a[1]
        def edge_vertices(face, cell, is_a):
            x, y = cell
            # Select face vertices by their expected midpoint in the unfolded grid.
            target_x, target_y = a[0]+dx/2, a[1]+dy/2
            u, v = frames[cell]["u"], frames[cell]["v"]
            center2 = (x, y)
            selected = []
            for su, sv in ((-1,-1),(1,-1),(1,1),(-1,1)):
                px, py = x+su/2, y+sv/2
                if abs(px-target_x) < 1e-9 or abs(py-target_y) < 1e-9:
                    point = _add(_scale(frames[cell]["normal"], half),
                                 _add(_scale(u, su*half), _scale(v, sv*half)))
                    selected.append(point)
            return selected
        va, vb = edge_vertices(fa, a, True), edge_vertices(fb, b, False)
        if len(va) != 2 or len(vb) != 2:
            residual = float("inf")
            break
        distances = [min(math.dist(p, q) for q in vb) for p in va]
        residual = max(residual, *distances)

    cardinal = {tuple(_scale(axis, sign)) for axis in (_X, _Y, _Z) for sign in (-1, 1)}
    valid = normal_set == cardinal and residual <= tolerance*max(1.0, edge_length)
    return {**result_base, "valid": valid,
            "reason": "合法正方体展开图" if valid else "折叠后存在重合面或公共边不闭合",
            "faces": faces, "unique_face_normals": len(normal_set),
            "hinge_residual": residual,
            "checks": {"six_distinct_faces": len(normal_set) == 6,
                       "hinges_close": residual <= tolerance*max(1.0, edge_length)}}
