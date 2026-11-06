# -*- coding: utf-8 -*-
"""生成六学科展示矩阵图（SVG）。与 展示清单.md 同源，改清单后重跑即可。"""
import io
import os

import build_plan as bp

OUT = os.path.dirname(os.path.abspath(__file__))

SHORT = {
    "M1": "二次函数", "M2": "截面形状", "M3": "展开折叠", "M4": "勾股定理", "M5": "均值方差",
    "P1": "浮力", "P2": "伏安法", "P3": "凸透镜", "P4": "杠杆", "P5": "串并联",
    "C1": "铁铜置换", "C2": "质量守恒", "C3": "金属活动性", "C4": "溶解度", "C5": "pH 试纸",
    "B1": "显微镜", "B2": "孟德尔", "B3": "细胞对比", "B4": "种子萌发", "B5": "光合作用",
    "G1": "等高线", "G2": "公转四季", "G3": "正午高度", "G4": "海陆风", "G5": "气温统计",
    "I1": "冒泡排序", "I2": "二分查找", "I3": "汉诺塔", "I4": "进制转换", "I5": "图像大小",
}

BLUE_D, BLUE_L, BLUE_S, BLUE_T = "#185FA5", "#E6F1FB", "#185FA5", "#0C447C"
GRAY_L, GRAY_S, GRAY_T = "#F1EFE8", "#B4B2A9", "#444441"
INK, INK2 = "#2C2C2A", "#5F5E5A"


def main():
    rs = list(bp.rows())
    x0, lw, cw, gap, rh = 110, 100, 102, 4, 44
    top = 22

    parts = []
    a = parts.append
    a('<svg width="100%" viewBox="0 0 680 400" role="img" xmlns="http://www.w3.org/2000/svg">')
    a('<title>六学科展示清单矩阵</title>')
    a('<desc>数学、物理、化学、生物、地理、信息科技各 5 篇，共 30 篇，按已完成、A 批、B 批着色。</desc>')

    for i, s in enumerate(bp.SUBJECT_ORDER):
        y = top + i * 52
        a('<text x="40" y="%d" font-family="system-ui,sans-serif" font-size="13" '
          'font-weight="500" fill="%s" dominant-baseline="central">%s</text>' % (y + rh / 2, INK, s))
        sub = [r for r in rs if r["学科"] == s]
        for j, r in enumerate(sub):
            x = x0 + j * (cw + gap)
            if r["前置"].startswith("已完成"):
                fill, stroke, t1, t2 = BLUE_D, BLUE_D, "#FFFFFF", "rgba(255,255,255,0.82)"
            elif r["批次"] == "A":
                fill, stroke, t1, t2 = BLUE_L, BLUE_S, BLUE_T, "#185FA5"
            else:
                fill, stroke, t1, t2 = GRAY_L, GRAY_S, GRAY_T, INK2
            a('<rect x="%d" y="%d" width="%d" height="%d" rx="8" fill="%s" stroke="%s" stroke-width="0.5"/>'
              % (x, y, cw, rh, fill, stroke))
            cx = x + cw / 2
            a('<text x="%.0f" y="%d" font-family="system-ui,sans-serif" font-size="13" font-weight="500" '
              'fill="%s" text-anchor="middle" dominant-baseline="central">%s</text>'
              % (cx, y + 15, t1, SHORT.get(r["序号"], r["实验名"])))
            a('<text x="%.0f" y="%d" font-family="system-ui,sans-serif" font-size="12" '
              'fill="%s" text-anchor="middle" dominant-baseline="central">%s</text>'
              % (cx, y + 32, t2, r["判据"].replace(" ", "")))

    ly = top + 6 * 52 + 8
    legend = [
        (BLUE_D, BLUE_D, "已完成 2 篇"),
        (BLUE_L, BLUE_S, "A 批 · 判据现成 10 篇"),
        (GRAY_L, GRAY_S, "B 批 · 需补场景 18 篇"),
    ]
    lx = 40
    for fill, stroke, label in legend:
        a('<rect x="%d" y="%d" width="12" height="12" rx="3" fill="%s" stroke="%s" stroke-width="0.5"/>'
          % (lx, ly, fill, stroke))
        a('<text x="%d" y="%d" font-family="system-ui,sans-serif" font-size="12" fill="%s" '
          'dominant-baseline="central">%s</text>' % (lx + 18, ly + 6, INK2, label))
        lx += 18 + len(label) * 7 + 26

    a("</svg>")
    svg = "\n".join(parts)
    path = os.path.join(OUT, "展示矩阵.svg")
    io.open(path, "w", encoding="utf-8").write(svg)
    print("输出:", path, "| 长度:", len(svg))


if __name__ == "__main__":
    main()
