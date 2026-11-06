# -*- coding: utf-8 -*-
"""把学科 × 判据矩阵画成内联 SVG（供 show_widget 使用）。"""
import io
import json

d = json.load(io.open("学科需求分类.json", encoding="utf-8"))
JS = ["J1", "J2", "J3", "J4", "J5", "J6", "J7", "J8", "J0"]
JN = {"J1": "数值复算", "J2": "几何复算", "J3": "计数守恒", "J4": "空间拓扑",
      "J5": "序列状态", "J6": "结构要素", "J7": "统计复算", "J8": "答案表",
      "J0": "不做"}
FILL = {"J1": "#dbeafe", "J2": "#dbeafe", "J3": "#dbeafe", "J4": "#dbeafe",
        "J5": "#ede9fe", "J6": "#ede9fe", "J7": "#ccfbf1", "J8": "#dcfce7",
        "J0": "#f3f4f6"}
INK = {"J1": "#1d4ed8", "J2": "#1d4ed8", "J3": "#1d4ed8", "J4": "#1d4ed8",
       "J5": "#6d28d9", "J6": "#6d28d9", "J7": "#0f766e", "J8": "#15803d",
       "J0": "#9ca3af"}

subs = [s["学科"] for s in d["学科"]]
have = {s["学科"]: s["现有案例数"] for s in d["学科"]}
M = {s: {j: sum(1 for r in d["需求类型"]
               if r["学科"] == s and r["判据编号"] == j) for j in JS}
     for s in subs}

X0, Y0, CW, CH = 96, 104, 54, 31
o = ['<svg viewBox="0 0 680 536" xmlns="http://www.w3.org/2000/svg" '
     'font-family="-apple-system,BlinkMacSystemFont,\'Segoe UI\',sans-serif">',
     '<rect width="680" height="536" fill="#ffffff"/>',
     '<text x="24" y="34" font-size="17" font-weight="700" fill="#111827">'
     '学科 × 审查判据：49 类需求落到 8 种判据上</text>',
     '<text x="24" y="56" font-size="12.5" fill="#6b7280">'
     '格子里的数字是「该学科有多少类需求用这条判据」；右侧是该学科已有案例数</text>']

for i, j in enumerate(JS):
    cx = X0 + i * CW + CW / 2
    o.append('<text x="%.0f" y="78" text-anchor="middle" font-size="11.5" '
             'font-weight="700" fill="%s">%s</text>' % (cx, INK[j], j))
    o.append('<text x="%.0f" y="91" text-anchor="middle" font-size="9" '
             'fill="#6b7280">%s</text>' % (cx, JN[j]))
o.append('<text x="624" y="82" text-anchor="middle" font-size="10.5" '
         'font-weight="700" fill="#6b7280">已有案例</text>')

for r, s in enumerate(subs):
    y = Y0 + r * CH
    if have[s] == 0:
        o.append('<rect x="20" y="%d" width="556" height="%d" rx="5" '
                 'fill="#fffbeb"/>' % (y - 2, CH - 2))
    o.append('<text x="84" y="%d" text-anchor="end" font-size="12" '
             'font-weight="600" fill="#111827">%s</text>' % (y + 18, s))
    for i, j in enumerate(JS):
        v = M[s][j]
        if not v:
            continue
        x = X0 + i * CW
        o.append('<rect x="%d" y="%d" width="%d" height="%d" rx="5" fill="%s"/>'
                 % (x + 3, y + 2, CW - 6, CH - 8, FILL[j]))
        o.append('<text x="%.0f" y="%d" text-anchor="middle" font-size="12.5" '
                 'font-weight="700" fill="%s">%d</text>'
                 % (x + CW / 2, y + 18, INK[j], v))
    n = have[s]
    o.append('<text x="624" y="%d" text-anchor="middle" font-size="12" '
             'font-weight="700" fill="%s">%d</text>'
             % (y + 18, "#15803d" if n else "#b45309", n))

ly = Y0 + 10 * CH + 16
o.append('<line x1="24" y1="%d" x2="656" y2="%d" stroke="#e5e7eb"/>'
         % (ly - 6, ly - 6))
legends = [(24, "#dbeafe", "理科主力：数值/几何/计数/空间"),
           (236, "#ede9fe", "过程与结构"),
           (356, "#ccfbf1", "统计复算"),
           (452, "#dcfce7", "答案表比对")]
for x, c, t in legends:
    o.append('<rect x="%d" y="%d" width="11" height="11" rx="3" fill="%s"/>'
             % (x, ly + 2, c))
    o.append('<text x="%d" y="%d" font-size="10.5" fill="#4b5563">%s</text>'
             % (x + 16, ly + 12, t))
o.append('<text x="24" y="%d" font-size="11.5" fill="#374151">'
         '蓝色块集中数理化——判据是「数值算得对不对」；紫绿块集中语英史道法——判据是「结构齐不齐、答案对不对」。</text>'
         % (ly + 38))
o.append('<text x="24" y="%d" font-size="11.5" font-weight="700" fill="#b45309">'
         '右侧为 0 的 4 个学科是本轮新扩的：类型已定义，答案表与知识库还没做。</text>'
         % (ly + 58))
o.append('</svg>')

io.open("_matrix.svg", "w", encoding="utf-8").write("\n".join(o))
print("lines", len(o))
