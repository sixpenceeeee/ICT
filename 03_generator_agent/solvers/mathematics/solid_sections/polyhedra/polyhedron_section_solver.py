# -*- coding: utf-8 -*-
"""Plane-section kernel for convex polyhedra described by vertices and edges."""
import math


SHAPE_NAMES = {0: "无截面", 3: "三角形", 4: "四边形", 5: "五边形", 6: "六边形"}


def solve_plane_section(vertices, edges, faces, normal, offset, eps=1e-9):
    """Intersect a plane n·x=offset with a convex polyhedron topology.

    Vertices are 3D coordinates, edges are pairs of indices, and faces are
    cyclic lists of vertex indices. The face boundaries must reproduce the
    edge set. The output polygon is ordered in the plane. Curved and
    non-convex solids, and disconnected section polygons, are out of scope.
    """
    try:
        points = [tuple(float(v) for v in p) for p in vertices]
        edge_list = [(int(e[0]), int(e[1])) for e in edges]
        face_list = [tuple(int(i) for i in face) for face in faces]
        n = tuple(float(v) for v in normal)
        offset = float(offset)
    except (TypeError, ValueError, IndexError) as exc:
        raise ValueError("顶点、棱或平面参数格式无效") from exc
    if len(points) < 4 or any(len(p) != 3 or not all(math.isfinite(v) for v in p) for p in points):
        raise ValueError("凸多面体至少需要四个有限三维顶点")
    if len(n) != 3 or not all(math.isfinite(v) for v in n) or not math.isfinite(offset):
        raise ValueError("平面必须由三个有限法向量分量和有限偏移量定义")
    norm = math.hypot(*n)
    if norm <= eps:
        raise ValueError("平面法向量不能为零")
    n = tuple(v / norm for v in n)
    offset /= norm
    if not edge_list or any(i < 0 or j < 0 or i >= len(points) or j >= len(points) or i == j
                            for i, j in edge_list):
        raise ValueError("多面体棱索引无效")
    if len(face_list) < 4 or any(len(face) < 3 or len(set(face)) != len(face) or
                                 any(i < 0 or i >= len(points) for i in face) for face in face_list):
        raise ValueError("凸多面体面索引无效")
    declared_edges = {tuple(sorted((i, j))) for i, j in edge_list}
    face_edges = {tuple(sorted((face[k], face[(k + 1) % len(face)])))
                  for face in face_list for k in range(len(face))}
    if face_edges != declared_edges:
        raise ValueError("棱集合必须与各面的边界一致")

    scale = max(1.0, *(max(p[k] for p in points) - min(p[k] for p in points) for k in range(3)))
    tol = eps * scale
    values = [sum(n[k] * p[k] for k in range(3)) - offset for p in points]
    hits = []

    def add(p):
        if not any(math.dist(old, p) <= 1e-7 * scale for old in hits):
            hits.append(tuple(p))

    for ia, ib in edge_list:
        fa, fb = values[ia], values[ib]
        if abs(fa) <= tol:
            add(points[ia])
        if abs(fb) <= tol:
            add(points[ib])
        if fa * fb < -(tol * tol):
            t = fa / (fa - fb)
            add(tuple(points[ia][k] + t * (points[ib][k] - points[ia][k]) for k in range(3)))

    if len(hits) >= 3:
        center = tuple(sum(p[k] for p in hits) / len(hits) for k in range(3))
        ref = (1.0, 0.0, 0.0) if abs(n[0]) < .9 else (0.0, 1.0, 0.0)
        ux = (n[1] * ref[2] - n[2] * ref[1], n[2] * ref[0] - n[0] * ref[2],
              n[0] * ref[1] - n[1] * ref[0])
        length = math.sqrt(sum(v * v for v in ux))
        ux = tuple(v / length for v in ux)
        uy = (n[1] * ux[2] - n[2] * ux[1], n[2] * ux[0] - n[0] * ux[2],
              n[0] * ux[1] - n[1] * ux[0])
        hits.sort(key=lambda p: math.atan2(
            sum((p[k] - center[k]) * uy[k] for k in range(3)),
            sum((p[k] - center[k]) * ux[k] for k in range(3))))

    cross_sum = [0.0, 0.0, 0.0]
    if len(hits) >= 3:
        for i, p in enumerate(hits):
            q = hits[(i + 1) % len(hits)]
            cross_sum[0] += p[1] * q[2] - p[2] * q[1]
            cross_sum[1] += p[2] * q[0] - p[0] * q[2]
            cross_sum[2] += p[0] * q[1] - p[1] * q[0]
    area = .5 * math.sqrt(sum(v * v for v in cross_sum))
    sides = len(hits) if area > eps * scale * scale else 0
    residual = max([abs(sum(n[k] * p[k] for k in range(3)) - offset) for p in hits] or [0.0])
    return {"normal": list(n), "offset": offset, "vertices": [list(p) for p in hits],
            "solid_vertices": [list(p) for p in points],
            "edges": [list(e) for e in edge_list], "faces": [list(f) for f in face_list],
            "sides": sides, "shape": SHAPE_NAMES.get(sides, "多边形"), "area": area,
            "plane_residual": residual}
