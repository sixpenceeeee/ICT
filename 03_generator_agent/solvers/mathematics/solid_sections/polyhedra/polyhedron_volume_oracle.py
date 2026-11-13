# -*- coding: utf-8 -*-
"""Independent convex-polyhedron clipping oracle for split-volume checks.

Unlike the section kernel, this computes each half's boundary by clipping the
solid's face polygons, adding a planar cap, and summing oriented tetrahedra.
"""
import math


def split_polyhedron_volumes(vertices, faces, normal, offset, eps=1e-9):
    points = [tuple(float(x) for x in p) for p in vertices]
    n = tuple(float(x) for x in normal)
    norm = math.hypot(*n)
    if norm <= eps or not math.isfinite(norm):
        raise ValueError("平面法向量不能为零")
    n = tuple(x / norm for x in n)
    offset = float(offset) / norm
    if not math.isfinite(offset) or len(points) < 4:
        raise ValueError("多面体或平面参数无效")
    center = tuple(sum(p[k] for p in points) / len(points) for k in range(3))
    scale = max(1.0, *(max(p[k] for p in points) - min(p[k] for p in points) for k in range(3)))
    tol = eps * scale
    signed = [sum(n[k] * p[k] for k in range(3)) - offset for p in points]
    plane_is_existing_face = any(all(abs(signed[i]) <= tol for i in face) for face in faces)

    def unique_add(items, point):
        if not any(math.dist(old, point) <= 1e-7 * scale for old in items):
            items.append(tuple(point))

    def clipped_face(face, keep_negative):
        polygon = [points[i] for i in face]
        result = []
        for idx, current in enumerate(polygon):
            previous = polygon[idx - 1]
            fc = sum(n[k] * current[k] for k in range(3)) - offset
            fp = sum(n[k] * previous[k] for k in range(3)) - offset
            inside_c = fc <= tol if keep_negative else fc >= -tol
            inside_p = fp <= tol if keep_negative else fp >= -tol
            if inside_c != inside_p:
                t = fp / (fp - fc)
                result.append(tuple(previous[k] + t * (current[k] - previous[k]) for k in range(3)))
            if inside_c:
                result.append(current)
        deduped = []
        for p in result:
            unique_add(deduped, p)
        if len(deduped) > 1 and math.dist(deduped[0], deduped[-1]) <= 1e-7 * scale:
            deduped.pop()
        return deduped

    ref = (1.0, 0.0, 0.0) if abs(n[0]) < .9 else (0.0, 1.0, 0.0)
    ux = (n[1]*ref[2]-n[2]*ref[1], n[2]*ref[0]-n[0]*ref[2], n[0]*ref[1]-n[1]*ref[0])
    ul = math.sqrt(sum(x*x for x in ux))
    ux = tuple(x / ul for x in ux)
    uy = (n[1]*ux[2]-n[2]*ux[1], n[2]*ux[0]-n[0]*ux[2], n[0]*ux[1]-n[1]*ux[0])

    def volume(keep_negative):
        # A supporting plane may touch only a face/edge/vertex.  Such a side
        # has no interior, even though clipping can leave a coplanar polygon.
        if keep_negative and not any(v < -tol for v in signed):
            return 0.0
        if not keep_negative and not any(v > tol for v in signed):
            return 0.0
        clipped = [p for face in faces if len(p := clipped_face(face, keep_negative)) >= 3]
        cap = []
        for poly in clipped:
            for p in poly:
                if abs(sum(n[k] * p[k] for k in range(3)) - offset) <= tol * 4:
                    unique_add(cap, p)
        if len(cap) >= 3 and not plane_is_existing_face:
            c = tuple(sum(p[k] for p in cap) / len(cap) for k in range(3))
            cap.sort(key=lambda p: math.atan2(sum((p[k]-c[k])*uy[k] for k in range(3)),
                                             sum((p[k]-c[k])*ux[k] for k in range(3))))
            # The negative half's cap points along +n; the positive half along -n.
            clipped.append(cap if keep_negative else list(reversed(cap)))
        signed_volume = 0.0
        for poly in clipped:
            p0 = tuple(poly[0][k] - center[k] for k in range(3))
            for i in range(1, len(poly) - 1):
                p1 = tuple(poly[i][k] - center[k] for k in range(3))
                p2 = tuple(poly[i+1][k] - center[k] for k in range(3))
                cross = (p1[1]*p2[2]-p1[2]*p2[1], p1[2]*p2[0]-p1[0]*p2[2],
                         p1[0]*p2[1]-p1[1]*p2[0])
                signed_volume += sum(p0[k] * cross[k] for k in range(3)) / 6.0
        return abs(signed_volume)

    return {"negative": volume(True), "positive": volume(False)}
