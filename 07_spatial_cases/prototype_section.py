# -*- coding: utf-8 -*-
"""
切割类教学工具的核心算法原型 —— 验证「平面截多面体」能否被精确计算。

为什么要写这个文件：
    立体几何的「切割」如果靠 3D 引擎的视觉裁剪（clipping plane），
    得到的是「看起来被切开了」，但截面形状、边数、两部分体积都无法复算，
    质量审查 Agent 就完全失效。
    而这三样恰恰是教学考点（截面是几边形？体积比是多少？）。

    本原型证明：凸多面体的切割结果是纯解析几何问题，可以精确求解。
      · 截面多边形 = 平面与 12 条棱的交点集合，按平面内极角排序
      · 两部分体积 = 沿法向切片做 Simpson 数值积分，误差 < 1e-9
      · 守恒校验：V1 + V2 必须等于 a³

    跑通之后，审查器的判据就有了：读页面暴露的截面顶点，复算边数与体积，
    与页面显示值比对。这比「截图看一眼像不像」可靠得多。

运行：
    python prototype_section.py
"""

import itertools
import math

A = 1.0  # 正方体棱长

# 8 个顶点 + 12 条棱
BOX = [(x, y, z) for x in (0.0, A) for y in (0.0, A) for z in (0.0, A)]
EDGES = [
    (i, j)
    for i, j in itertools.combinations(range(8), 2)
    if sum(1 for k in range(3) if BOX[i][k] != BOX[j][k]) == 1
]


# ---------------- 基础向量运算 ----------------
def dot(u, v):
    return sum(a * b for a, b in zip(u, v))


def sub(u, v):
    return tuple(a - b for a, b in zip(u, v))


def cross(u, v):
    return (
        u[1] * v[2] - u[2] * v[1],
        u[2] * v[0] - u[0] * v[2],
        u[0] * v[1] - u[1] * v[0],
    )


def norm(u):
    n = math.sqrt(dot(u, u))
    return tuple(c / n for c in u)


# ---------------- 核心 1：求截面多边形 ----------------
def section_polygon(n, d, eps=1e-12):
    """平面 n·x = d 与正方体的交多边形，顶点按平面内极角逆序排列。

    返回 (顶点列表, 诊断信息)。顶点数为 0 表示平面与立方体不相交。
    """
    pts = []
    for i, j in EDGES:
        p, q = BOX[i], BOX[j]
        fp = dot(n, p) - d
        fq = dot(n, q) - d
        if abs(fp) < eps and abs(fq) < eps:
            pts.extend([p, q])          # 整条棱落在平面上（退化为面，教学场景少见）
        elif abs(fp) < eps:
            pts.append(p)               # 平面正好过顶点
        elif abs(fq) < eps:
            pts.append(q)
        elif fp * fq < 0:
            t = fp / (fp - fq)
            pts.append(tuple(p[k] + t * (q[k] - p[k]) for k in range(3)))

    # 去重：平面过顶点时同一个点会由两条棱各贡献一次
    uniq = []
    for p in pts:
        if not any(math.dist(p, q) < 1e-9 for q in uniq):
            uniq.append(p)

    if len(uniq) < 3:
        return [], {"原因": "交点不足 3 个", "交点数": len(uniq)}

    # 在平面内建正交基，把三维点降到二维再按极角排序
    nn = norm(n)
    tmp = (1.0, 0.0, 0.0) if abs(nn[0]) < 0.9 else (0.0, 1.0, 0.0)
    u = norm(cross(nn, tmp))
    v = cross(nn, u)
    c = tuple(sum(p[k] for p in uniq) / len(uniq) for k in range(3))

    uniq.sort(key=lambda p: math.atan2(dot(sub(p, c), v), dot(sub(p, c), u)))
    return uniq, {"交点数": len(uniq)}


# ---------------- 核心 2：多边形面积 ----------------
def polygon_area(poly):
    """凸多边形面积（扇形三角剖分）。"""
    if len(poly) < 3:
        return 0.0
    c = tuple(sum(p[k] for p in poly) / len(poly) for k in range(3))
    area = 0.0
    for i in range(len(poly)):
        a, b = sub(poly[i], c), sub(poly[(i + 1) % len(poly)], c)
        area += 0.5 * math.sqrt(dot(cross(a, b), cross(a, b)))
    return area


# ---------------- 核心 3：一部分的体积（沿 z 做 Simpson 积分） ----------------
def clip_convex(poly, nx, ny, c):
    """Sutherland-Hodgman：保留 nx*x + ny*y <= c 的部分。"""
    if abs(nx) < 1e-12 and abs(ny) < 1e-12:
        return poly if c >= 0 else []

    def f(p):
        return nx * p[0] + ny * p[1] - c

    out, m = [], len(poly)
    for i in range(m):
        p, q = poly[i], poly[(i + 1) % m]
        fp, fq = f(p), f(q)
        if fp <= 0:
            out.append(p)
        if (fp < 0 < fq) or (fp > 0 > fq):
            t = fp / (fp - fq)
            out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
    return out


def area_2d(poly):
    if len(poly) < 3:
        return 0.0
    s = 0.0
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2


def volume_below(n, d, steps=200):
    """n·x <= d 那一侧的体积。沿 z 切片，每片是正方形被半平面裁剪。

    注意一个坑：截面积随 z 变化时是分段光滑的，在平面扫过正方形角点处有拐点。
    直接对 [0,1] 整体做 Simpson，跨过拐点会引入 O(h) 误差——
    中截面本应 V=0.5，实测却得到 0.500167。
    所以先按「平面扫过四个角点」的 z 值切段，每段内再接 Simpson，即可精确。
    """
    nx, ny, nz = n

    def slice_area(z):
        return area_2d(clip_convex([(0, 0), (A, 0), (A, A), (0, A)], nx, ny, d - nz * z))

    if abs(nz) < 1e-12:
        return A * slice_area(0)

    breaks = {0.0, A}
    for x in (0.0, A):
        for y in (0.0, A):
            z = (d - nx * x - ny * y) / nz
            if 0.0 < z < A:
                breaks.add(z)
    zs = sorted(breaks)

    total = 0.0
    for lo, hi in zip(zs, zs[1:]):
        h = (hi - lo) / steps
        # 端点向内缩一个极小量：截面积在断点处是跳跃间断（左极限 1、右极限 0），
        # 直接取端点值会把左侧的截面积算进右侧区间，每段多出 h/3 的虚假体积。
        # 缩进后左右两段各自拿到本段内的极限值，Simpson 才精确。
        eps = h * 1e-6
        s = slice_area(lo + eps) + slice_area(hi - eps)
        for i in range(1, steps):
            s += (4 if i % 2 else 2) * slice_area(lo + i * h)
        total += s * h / 3
    return total


# ---------------- 测试 ----------------
def run():
    cases = [
        # (法向量, 截距, 期望边数, 说明)
        ((0, 0, 1), 0.5, 4, "平行于底面的中截面 → 正方形"),
        ((1, 1, 1), 1.5, 6, "过中心且垂直体对角线 → 正六边形"),
        ((1, 1, 1), 1.0, 3, "过三个相邻顶点 → 正三角形"),
        ((1, 1, 0), 1.0, 4, "对角面 → 矩形，面积 √2"),
        ((1, 0, 0), 0.5, 4, "竖直中截面 → 正方形"),
        ((1, 2, 3), 2.0, 4, "斜切且平面绕过一条棱上的顶点 → 四边形"),
        ((1, 2, 3), 2.5, 5, "斜切 → 五边形（截面边数可以不是 3/4/6）"),
        ((1, 1, 1), 3.0, 0, "完全在体外 → 无交点"),
    ]

    print("=" * 74)
    print("平面截正方体（棱长 a = %.1f，体积 %.1f）" % (A, A ** 3))
    print("=" * 74)

    ok_all = True
    for n, d, expect_sides, desc in cases:
        poly, diag = section_polygon(n, d)
        sides = len(poly)

        if sides == 0:
            passed = expect_sides == 0
            print("\n%-30s  n=%s d=%.1f" % (desc, n, d))
            print("  截面：无（%s）  %s" % (diag.get("原因", ""), "OK" if passed else "FAIL"))
            ok_all &= passed
            continue

        # 共面性：所有顶点都应满足 n·x = d
        dev = max(abs(dot(n, p) - d) for p in poly)
        # 体积守恒
        v1 = volume_below(n, d)
        v2 = A ** 3 - v1
        v_sum = volume_below(n, d) + volume_below(tuple(-c for c in n), -d)

        checks = [
            ("顶点共面", dev < 1e-9, "最大偏差 %.2e" % dev),
            ("体积守恒", abs(v_sum - A ** 3) < 1e-6, "V1+V2 = %.9f" % v_sum),
            ("边数", expect_sides is None or sides == expect_sides,
             "%d 边%s" % (sides, "（期望 %d）" % expect_sides if expect_sides else "")),
        ]
        passed = all(c[1] for c in checks)
        ok_all &= passed

        print("\n%-30s  n=%s d=%.1f" % (desc, n, d))
        print("  截面面积 %.6f   两部分体积 %.6f / %.6f" % (polygon_area(poly), v1, v2))
        for name, good, detail in checks:
            print("  %-8s %s  %s" % (name, "OK  " if good else "FAIL", detail))

    print("\n" + "=" * 74)
    print("结论：%s" % ("全部通过 —— 截面与体积可精确解析，无需 3D 引擎"
                     if ok_all else "存在失败项，需要修"))
    print("=" * 74)
    return ok_all


if __name__ == "__main__":
    raise SystemExit(0 if run() else 1)
