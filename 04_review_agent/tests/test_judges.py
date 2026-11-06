# -*- coding: utf-8 -*-
"""
test_judges.py —— J1–J8 的自测：正例必须过，反例必须被抓。

跑法：
    python tests/test_judges.py

为什么要有这组测试：
    审查器最容易出现的问题不是"报错"，而是**什么都判 skip 然后看起来全绿**。
    每一关都要有"故意写错"的输入，确认它真的会 fail。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import judges  # noqa: E402

PASS, FAIL = [], []


def check(name, checks, expect_status):
    got = [c["status"] for c in checks]
    ok = expect_status in got
    (PASS if ok else FAIL).append("%s（期望含 %s，实际 %s）" % (name, expect_status, got))
    return ok


def ctx(**kw):
    base = {"br": {}, "machine": {}, "text": "", "facts": [], "scene": {}, "subject": ""}
    base.update(kw)
    return base


# ---------------- J2 反射角 ----------------
check("J2 反射角=入射角（正确）",
      judges.j2_geometry(ctx(text="入射角 30°，反射角 30°")), "pass")
check("J2 反射角写错（应抓出）",
      judges.j2_geometry(ctx(text="入射角 40°，反射角 55°")), "fail")

# ---------------- J3 原子守恒 ----------------
check("J3 原子守恒（Fe+CuSO4）",
      judges.j3_conservation(ctx(machine={"DATA": {"atoms": {
          "left": {"Fe": 1, "Cu": 1, "S": 1, "O": 4},
          "right": {"Fe": 1, "Cu": 1, "S": 1, "O": 4}}}})), "pass")
check("J3 原子不守恒（应抓出）",
      judges.j3_conservation(ctx(machine={"DATA": {"atoms": {
          "left": {"H": 4, "O": 2}, "right": {"H": 4, "O": 1}}}})), "fail")
check("J3 遗传比例 3:1 写错（应抓出）",
      judges.j3_conservation(ctx(machine={"DATA": {"ratio": [1, 1]}})), "fail")

# ---------------- J4 体积可加 ----------------
check("J4 体积 0.5+0.5=1（正确）",
      judges.j4_topology(ctx(machine={"GEO": {"v_up": 0.5, "v_down": 0.5, "sides": 6, "area": 1.299}}),
                         ), "pass")
check("J4 体积加起来不等于 1（应抓出）",
      judges.j4_topology(ctx(machine={"GEO": {"v_up": 0.7, "v_down": 0.5, "sides": 6}})), "fail")
check("J4 截面写成七边形（应抓出，正方体最多六边）",
      judges.j4_topology(ctx(machine={"GEO": {"v_up": 0.5, "v_down": 0.5, "sides": 7}})), "fail")

# ---------------- J5 序列对拍 ----------------
check("J5 冒泡序列正确（正确）",
      judges.j5_sequence(ctx(machine={"DATA": {"steps": [
          [3, 1, 2], [1, 3, 2], [1, 2, 3]]}})), "pass")
check("J5 序列少了一步（应抓出）",
      judges.j5_sequence(ctx(machine={"DATA": {"steps": [[3, 1, 2], [1, 2, 3]]}})), "fail")
check("J5 单步卡死（应抓出）",
      judges.j5_sequence(ctx(br={"steps": {"found": True, "count": 8, "stuck": 6, "unique": 2}})), "fail")

# ---------------- J7 统计 ----------------
tables = [[["序号", "电压 U", "电流 I"], ["1", "2.0", "0.20"],
           ["2", "4.0", "0.40"], ["3", "6.0", "0.60"]]]
check("J7 均值写错（应抓出）",
      judges.j7_statistics(ctx(br={"tables": tables}, text="平均电流 0.80 A")), "fail")
check("J7 均值正确",
      judges.j7_statistics(ctx(br={"tables": tables}, text="平均电流 0.40 A")), "pass")

# ---------------- J8 事实表 ----------------
FACTS = [{"id": "CHE-F-002", "学科": "化学", "主题": ["铜", "稀盐酸", "活动性"],
          "事实": "铜与稀盐酸不反应", "必须出现": [], "至少出现": ["不反应", "无明显现象"],
          "禁止出现": ["铜与稀盐酸反应产生气泡"], "审核状态": "教研复核通过"}]
check("J8 正确表述（铜不与稀盐酸反应）",
      judges.j8_facts(ctx(text="铜与稀盐酸不反应，无明显现象", facts=FACTS, subject="化学")), "pass")
check("J8 编造现象（应抓出）",
      judges.j8_facts(ctx(text="铜与稀盐酸反应产生气泡", facts=FACTS, subject="化学")), "fail")
check("J8 无对应事实（应转人工）",
      judges.j8_facts(ctx(text="钠与水反应", facts=FACTS, subject="化学")), "review")

# ---------------- J1 代入式 ----------------
check("J1 代入式算错（应抓出）",
      judges.j1_numeric(ctx(br={"formula": {"found": True, "checks": [
          {"类型": "通用", "text": "6.0 V ÷ 20 Ω = 0.500 A", "显示": 0.5, "应为": 0.3, "ok": False}]}},
          text="电压 6.0 V，电阻 20 Ω，电流 0.500 A",
          profile={"单位组": [("电压", ["V"]), ("电阻", ["Ω"]), ("电流", ["A"])],
                   "公式示例": "I = U/R"})), "fail")
check("J1 除零（应抓出）",
      judges.j1_numeric(ctx(br={"ranges": {"bounds": [{"名称": "R", "min": 0, "max": 50, "value": 10}]},
                               "formula": {"found": True, "checks": [
                                   {"类型": "通用", "text": "6 V ÷ 10 Ω = 0.6 A", "显示": 0.6, "应为": 0.6, "ok": True}]}},
                               text="电流 6 V ÷ 0 = 0 A",
                               profile={"单位组": [], "公式示例": "I=U/R"})), "fail")

print("=" * 60)
for line in PASS:
    print("  PASS  " + line)
for line in FAIL:
    print("  FAIL  " + line)
print("-" * 60)
print("通过 %d / %d" % (len(PASS), len(PASS) + len(FAIL)))
sys.exit(0 if not FAIL else 1)
