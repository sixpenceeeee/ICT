# -*- coding: utf-8 -*-
"""
judges.py —— J1–J8 学科判据的独立实现（《界面设计+审查判据》3.1–3.3）

三条原则写在最前面，改代码前请先读：

1. **独立性**（规范 3.2 注意事项 1）
   页面自己说"守恒成立"不算证据。凡是从页面读来的布尔值（__DATA__.checks），
   一律只标 review，不计入通过；必须由本文件用独立算法重算一遍才判 pass。

2. **容差按量纲走**（注意事项 2）
   体积、角度、电流的容差不同。统一用 JUDGE_TOL 里的相对/绝对误差，不搞"一律 5%"。

3. **不适用不等于通过**（注意事项 3、5）
   页面没有几何量、没有统计量时返回 skip，不计入分母，而不是白送分。
   没有可审核事实（J8）/没有注册场景（J6）时返回 review，交教师判断，不伪造结论。
"""

import math
import re

from registry import JUDGES, scene_of
from chemistry.reactions.redox_solver import solve_redox
from chemistry.reactions.solubility_equilibrium_solver import solve_solubility_equilibrium

# ---------------------------------------------------------------- 容差

JUDGE_TOL = {
    "角度": {"绝对": 0.6},
    "长度": {"相对": 0.02, "绝对": 0.01},
    "面积": {"相对": 0.02, "绝对": 0.001},
    "体积": {"相对": 0.02, "绝对": 0.002},
    "数值": {"相对": 0.02, "绝对": 0.01},
    "统计": {"相对": 0.03, "绝对": 0.01},
    "计数": {"绝对": 0},
}


def within(expect, actual, kind="数值"):
    """按量纲判断两个数是否一致。"""
    tol = JUDGE_TOL.get(kind, JUDGE_TOL["数值"])
    if actual is None or expect is None:
        return False
    if "绝对" in tol and "相对" not in tol:
        return abs(expect - actual) <= tol["绝对"]
    rel = tol.get("相对", 0.02)
    ab = tol.get("绝对", 0.0)
    return abs(expect - actual) <= max(ab, abs(expect) * rel)


def num_of(x):
    """从 '2.00 N'、'0.6A'、'55°' 这类文本里取出数字。"""
    if isinstance(x, (int, float)):
        return float(x)
    m = re.search(r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", str(x or ""))
    return float(m.group(0)) if m else None


def mk(judge, cid, name, status, expected, actual, message,
       evidence="", advice="", severity="major", weight=0):
    """统一的一条审查记录，字段对齐规范 3.4 的报告要求。"""
    return {
        "check_id": cid,
        "gate": "G3",
        "gate_name": "学科判据",
        "judge": judge,
        "judge_name": JUDGES.get(judge, {}).get("名称", ""),
        "name": name,
        "status": status,           # pass / fail / review / skip
        "severity": severity,
        "weight": weight,
        "expected": expected,
        "actual": actual,
        "message": message,
        "evidence": evidence,
        "advice": advice,
    }


# ================================================================ J1 数值复算

def j1_numeric(ctx):
    out = []
    # 没有浏览器就没有代入式与滑块读数：这一判据整体不适用，不能判失败
    if ctx.get("br") is None:
        return [mk("J1", "J1-00", "J1 数值复算", "skip",
                   "由浏览器取回页面上的代入式与滑块范围后复算",
                   "未执行浏览器检查",
                   "静态条件下拿不到渲染后的数字，J1 无法判定", weight=8)]
    br = ctx.get("br") or {}
    formula = br.get("formula") or {}
    items = formula.get("checks") or []
    profile = ctx.get("profile") or {}
    text = ctx.get("text") or ""
    advice_formula = "把核心公式写成带数值的代入式：" + profile.get(
        "公式示例", "公式 = 数值代入 = 结果（每项带单位）")

    # J1-01 首屏代入式：算得对不对
    if not items:
        out.append(mk("J1", "J1-01", "J1 代入式可复算", "fail",
                      "页面可见「公式 = 数值 = 结果」的完整代入过程",
                      "页面上没有解析出可复算的代入式",
                      "拿不到可复算的数值，数值维度的正确性无法证明",
                      advice=advice_formula, severity="critical", weight=8))
    else:
        bad = [c for c in items if not c.get("ok")]
        sample = items[0]
        if bad:
            b = bad[0]
            out.append(mk("J1", "J1-01", "J1 代入式可复算", "fail",
                          "按公式独立重算后与显示值一致",
                          "「%s」显示 %s，独立重算应为 %s（共 %d 组不一致）"
                          % (b["text"], b["显示"], b["应为"], len(bad)),
                          "代入式的算术结果与显示值不符，学生会照着一个错数学习",
                          evidence="；".join("「%s」=%s≠%s" % (x["text"], x["显示"], x["应为"])
                                            for x in bad[:3]),
                          advice=advice_formula, severity="critical", weight=8))
        else:
            out.append(mk("J1", "J1-01", "J1 代入式可复算", "pass",
                          "按公式独立重算后与显示值一致",
                          "%d 组代入式全部复算通过" % len(items),
                          "页面数值与独立复算一致",
                          evidence=sample["text"], weight=8))

    # J1-02 极值下仍自洽（参数拉到端点后重算）
    extreme = [c for c in items if c.get("阶段") == "极值"]
    if not extreme:
        out.append(mk("J1", "J1-02", "J1 极值下仍自洽", "skip",
                      "参数取端点时代入式仍成立",
                      "页面没有可拖动参数，或极值状态未产生新的代入式",
                      "无参数可拖，本项不适用", weight=4))
    else:
        bad = [c for c in extreme if not c.get("ok")]
        if bad:
            b = bad[0]
            out.append(mk("J1", "J1-02", "J1 极值下仍自洽", "fail",
                          "参数取端点时代入式仍成立",
                          "极值处 %d 组不一致，例如「%s」显示 %s，应为 %s"
                          % (len(bad), b["text"], b["显示"], b["应为"]),
                          "参数变化后读数没有跟着重算，常见原因是只在初始化时算了一次",
                          advice="每次参数变化都走同一个 render()，读数、画布、代入式同源",
                          severity="major", weight=4))
        else:
            out.append(mk("J1", "J1-02", "J1 极值下仍自洽", "pass",
                          "参数取端点时代入式仍成立",
                          "%d 组极值状态复算通过" % len(extreme),
                          "极值端点的数值仍自洽", weight=4))

    # J1-03 单位标注完整
    groups = profile.get("单位组") or []
    if not groups:
        out.append(mk("J1", "J1-03", "J1 单位标注完整", "skip",
                      "关键读数带单位", "该主题未配置单位组",
                      "主题未识别，单位检查不适用", weight=3))
    else:
        miss = [label for label, aliases in groups if not any(a in text for a in aliases)]
        out.append(mk("J1", "J1-03", "J1 单位标注完整", "pass" if not miss else "fail",
                      "、".join(label for label, _ in groups) + " 均带单位",
                      "缺失单位：%s" % "、".join(miss) if miss else "单位齐全",
                      "读数缺单位，学生无法判断量纲" if miss else "关键读数均带单位",
                      advice="为每个读数和公式项补上单位，且与知识库中的器材规格一致",
                      severity="major", weight=3))

    # J1-04 值域与除零（规范 3.2 示例：R=0 须禁止除零）
    bounds = (br.get("ranges") or {}).get("bounds") or []
    problems = []
    for b in bounds:
        lo, hi, val = b.get("min"), b.get("max"), b.get("value")
        if lo is None or hi is None or lo >= hi:
            problems.append("滑块「%s」范围非法（%s–%s）" % (b.get("名称", ""), lo, hi))
        elif val is not None and not (lo <= val <= hi):
            problems.append("滑块「%s」初值 %s 不在 %s–%s 内" % (b.get("名称", ""), val, lo, hi))
    if re.search(r"[÷/]\s*0(?:\.0+)?(?![.\d])", text):
        problems.append("页面出现除数为 0 的代入式")
    if not bounds:
        out.append(mk("J1", "J1-04", "J1 值域与除零", "skip",
                      "参数上下限有效、不出现除零",
                      "页面没有滑块，参数值域不适用", "无参数控件，本项不适用", weight=3))
    else:
        out.append(mk("J1", "J1-04", "J1 值域与除零", "pass" if not problems else "fail",
                      "参数上下限有效、不出现除零",
                      "；".join(problems) if problems else "%d 个滑块范围与初值均合法" % len(bounds),
                      "参数越界或除零会让实验在边界处崩溃" if problems else "参数值域合法",
                      advice="在 setParams 里做上下界校验，除数为 0 时给出提示而不是直接计算",
                      severity="major", weight=3))
    return out


# ================================================================ J2 几何复算

def _geo(ctx):
    return ((ctx.get("machine") or {}).get("GEO")
            or (ctx.get("machine") or {}).get("DATA", {}).get("geometry") or {})


def j2_geometry(ctx):
    out = []
    geo = _geo(ctx) or {}
    text = ctx.get("text") or ""
    checked = 0
    fails = []

    # J2-01 三角形内角和 / 多边形外角和
    angles = geo.get("angles") or geo.get("内角")
    if isinstance(angles, list) and len(angles) >= 3:
        checked += 1
        s = sum(num_of(a) or 0 for a in angles)
        need = 180.0 if len(angles) == 3 else (len(angles) - 2) * 180.0
        if not within(need, s, "角度"):
            fails.append("内角和 %s°，应为 %s°" % (round(s, 2), need))

    # J2-02 反射角 = 入射角（文本级，适用于光学页）
    m_in = re.search(r"入射角\s*[为是=:：]?\s*(\d+(?:\.\d+)?)\s*°", text)
    m_out = re.search(r"反射角\s*[为是=:：]?\s*(\d+(?:\.\d+)?)\s*°", text)
    if m_in and m_out:
        checked += 1
        a, b = float(m_in.group(1)), float(m_out.group(1))
        if not within(a, b, "角度"):
            fails.append("入射角 %s° 与反射角 %s° 不相等" % (a, b))

    # J2-03 顶点坐标与显示长度一致
    pts = geo.get("points")
    lens = geo.get("lengths")
    if isinstance(pts, list) and len(pts) >= 2 and isinstance(lens, list) and lens:
        try:
            p0, p1 = pts[0], pts[1]
            d = math.dist([float(p0["x"]), float(p0["y"])], [float(p1["x"]), float(p1["y"])])
            checked += 1
            if not within(d, num_of(lens[0]), "长度"):
                fails.append("两点距离重算 %.3f，页面显示 %s" % (d, lens[0]))
        except (KeyError, TypeError, ValueError):
            pass

    # J2-04 太阳高度角：H = 90 - |纬度 - 直射纬度|
    lat, decl, alt = geo.get("lat"), geo.get("decl"), geo.get("altitude")
    if lat is not None and decl is not None and alt is not None:
        checked += 1
        need = 90 - abs(num_of(lat) - num_of(decl))
        if not within(need, num_of(alt), "角度"):
            fails.append("太阳高度角显示 %s°，按 90−|%s−%s| 应为 %.2f°"
                         % (alt, lat, decl, need))

    # J2-05 边界与数值合理性
    area = num_of(geo.get("area"))
    if area is not None:
        checked += 1
        if area <= 0:
            fails.append("面积重算为非正数（%s）" % area)

    if not checked:
        out.append(mk("J2", "J2-01", "J2 几何量可复算", "skip",
                      "页面暴露可复算的几何量（角度/坐标/长度）",
                      "未在 __GEO__ 或页面文本中找到几何约束",
                      "本页没有可复算的几何关系，J2 不适用", weight=6))
        return out

    out.append(mk("J2", "J2-01", "J2 几何复算", "pass" if not fails else "fail",
                  "几何约束（内角和/反射角/距离/高度角）独立重算成立",
                  "；".join(fails) if fails else "%d 项几何约束复算通过" % checked,
                  "几何关系与独立重算不符，画面看着对但数值是错的" if fails else "几何量自洽",
                  evidence="；".join(fails[:3]), severity="critical" if fails else "major",
                  advice="几何量必须由同一套坐标/角度计算得出，不要为画面好看单独写死数值",
                  weight=6))
    return out


# ================================================================ J3 计数与守恒

def _j3_precipitation(ctx):
    """Independently audit the supported precipitation solver and page mutations."""
    machine = ctx.get("machine") or {}
    text = (ctx.get("text") or "") + " " + str(ctx.get("topic") or "")
    if not isinstance(machine.get("CHEM_PRECIP_REQUEST"), dict) and not re.search(
            r"沉淀反应|生成沉淀|沉淀质量|沉淀物质的量|硫酸钡|氯化银|碳酸钙沉淀|氢氧化铜|氢氧化铁|氢氧化镁", text):
        return []

    def same(actual, expected):
        if isinstance(actual, bool) or isinstance(expected, bool):
            return type(actual) is type(expected) and actual == expected
        if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
            return math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-12)
        if isinstance(expected, dict):
            return isinstance(actual, dict) and set(actual) == set(expected) and all(
                same(actual[key], expected[key]) for key in expected)
        if isinstance(expected, list):
            return isinstance(actual, list) and len(actual) == len(expected) and all(
                same(a, b) for a, b in zip(actual, expected))
        return actual == expected

    def same_num(a, b):
        try:
            return not isinstance(a, bool) and not isinstance(b, bool) and math.isclose(
                float(a), float(b), rel_tol=1e-9, abs_tol=1e-12)
        except (TypeError, ValueError, OverflowError):
            return False

    def mass_reading(raw):
        matches = list(re.finditer(r"([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*(mg|毫克|g|克)(?![A-Za-z])",
                                   str(raw or ""), re.I))
        if not matches:
            return None, None, "沉淀质量必须标注 g 或 mg"
        number, unit = matches[-1].group(1), matches[-1].group(2).lower()
        decimals = len(number.partition(".")[2])
        factor = 0.001 if unit in ("mg", "毫克") else 1.0
        if factor == 1 and decimals < 3:
            return None, None, "以 g 显示时至少保留三位小数"
        return float(number) * factor, 0.5 * (10 ** -decimals) * factor + 1e-12, None

    request, page_result = machine.get("CHEM_PRECIP_REQUEST"), machine.get("CHEM_PRECIP_RESULT")
    oracle = ctx.get("chem_precip_oracle") or {}
    issues = []
    if not isinstance(request, dict) or not isinstance(page_result, dict):
        issues.append("缺少 CHEM_PRECIP_REQUEST / CHEM_PRECIP_RESULT")
    elif oracle.get("error"):
        issues.append("独立沉淀反应复算失败：%s" % oracle["error"])
    else:
        expected = oracle.get("result") or {}
        solutions = request.get("solutions") or []
        controls = machine.get("CHEM_PRECIP_CONTROLS")
        expected_controls = {
            "concentration_indices": list(range(len(solutions))),
            "concentrations_mol_L": [item.get("concentration_mol_L") for item in solutions],
            "volume_indices": list(range(len(solutions))),
            "volumes": [item.get("volume") for item in solutions],
            "unit_indices": list(range(len(solutions))),
            "volume_units": [item.get("volume_unit") for item in solutions],
            "progress": request.get("progress", 1.0),
        }
        if not isinstance(controls, dict):
            issues.append("缺少页面真实浓度、体积、单位和反应进度控件")
        else:
            for key, value in expected_controls.items():
                actual = controls.get(key)
                equal = actual == value if key.endswith("indices") or key == "volume_units" else (
                    all(same_num(a, b) for a, b in zip(actual, value)) and len(actual) == len(value)
                    if isinstance(value, list) and isinstance(actual, list) else same_num(actual, value))
                if not equal:
                    issues.append("页面控件 %s 与沉淀反应请求不一致" % key)

        fields = ("schema", "reaction_id", "equation", "coefficients", "initial_amounts_mol",
                  "progress", "max_extent_mol", "extent_mol", "limiting_reactants",
                  "stoichiometric_mix", "reactants", "products", "element_balance", "charge_balance",
                  "solution_inputs", "precipitate_formula", "precipitate_moles",
                  "precipitate_molar_mass_g_mol", "precipitate_mass_g", "precipitation_occurs",
                  "net_ionic_equation", "net_ionic_balance", "checks")
        for field in fields:
            if not same(page_result.get(field), expected.get(field)):
                issues.append("页面 %s 与 Python 独立复算不一致" % field)
        normalize = lambda value: re.sub(
            r"\s+", "", str(value or "").translate(str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")))
        if normalize(machine.get("CHEM_PRECIP_DISPLAYED_EQUATION")) != normalize(expected.get("equation")):
            issues.append("可见分子方程式与求解结果不一致")
        if re.sub(r"\s+", "", str(machine.get("CHEM_PRECIP_DISPLAYED_NET_IONIC") or "")) != re.sub(
                r"\s+", "", str(expected.get("net_ionic_equation") or "")):
            issues.append("可见净离子方程式与反应目录不一致")
        visible_mass, mass_tol, mass_error = mass_reading(machine.get("CHEM_PRECIP_DISPLAYED_MASS"))
        if mass_error:
            issues.append(mass_error)
        elif not math.isclose(visible_mass, expected.get("precipitate_mass_g", math.nan),
                              rel_tol=0.0, abs_tol=mass_tol):
            issues.append("页面沉淀质量读数与独立复算不一致")
        if not (page_result.get("checks") or {}).get("ok"):
            issues.append("页面配平、溶液换算或沉淀质量内部检查未通过")

        sample_rows = ctx.get("chem_precip_sample_oracles") or []
        if not sample_rows:
            issues.append("浏览器未执行沉淀页面真实控件变形")
        observed, samples_by_kind = set(), {}
        for i, row in enumerate(sample_rows):
            sample, sample_oracle = row.get("sample") or {}, row.get("oracle") or {}
            sample_request, sample_result = sample.get("request"), sample.get("result")
            kind = sample.get("kind")
            observed.add(kind)
            label = "沉淀变形 %d（%s）" % (i + 1, kind or "未命名")
            if sample_oracle.get("error"):
                issues.append("%s独立复算失败：%s" % (label, sample_oracle["error"]))
                continue
            sample_expected = sample_oracle.get("result") or {}
            if not isinstance(sample_request, dict) or not isinstance(sample_result, dict):
                issues.append("%s缺少请求或结果" % label)
                continue
            samples_by_kind[kind] = (sample, sample_expected)
            rows = sample_request.get("solutions") or []
            sample_controls = sample.get("controls") or {}
            expected_sample_controls = {
                "concentration_indices": list(range(len(rows))),
                "concentrations_mol_L": [item.get("concentration_mol_L") for item in rows],
                "volume_indices": list(range(len(rows))), "volumes": [item.get("volume") for item in rows],
                "unit_indices": list(range(len(rows))), "volume_units": [item.get("volume_unit") for item in rows],
                "progress": sample_request.get("progress", 1.0),
            }
            for key, value in expected_sample_controls.items():
                actual = sample_controls.get(key)
                equal = actual == value if key.endswith("indices") or key == "volume_units" else (
                    all(same_num(a, b) for a, b in zip(actual, value)) and len(actual) == len(value)
                    if isinstance(value, list) and isinstance(actual, list) else same_num(actual, value))
                if not equal:
                    issues.append("%s控件 %s 与变形请求不一致" % (label, key))
            for field in fields:
                if not same(sample_result.get(field), sample_expected.get(field)):
                    issues.append("%s页面 %s 与参考实现不一致" % (label, field))
            if normalize(sample.get("displayed_equation")) != normalize(sample_expected.get("equation")):
                issues.append("%s分子方程式未同步更新" % label)
            if re.sub(r"\s+", "", str(sample.get("displayed_net_ionic") or "")) != re.sub(
                    r"\s+", "", str(sample_expected.get("net_ionic_equation") or "")):
                issues.append("%s净离子方程式未同步更新" % label)
            shown, tolerance, error = mass_reading(sample.get("displayed_mass"))
            if error:
                issues.append("%s%s" % (label, error))
            elif not math.isclose(shown, sample_expected.get("precipitate_mass_g", math.nan),
                                  rel_tol=0.0, abs_tol=tolerance):
                issues.append("%s沉淀质量读数与独立复算不一致" % label)

        required = {"common-volume-scale", "equivalent-unit", "concentration-change", "progress-change",
                    "stoichiometric-threshold-at", "stoichiometric-threshold-below",
                    "stoichiometric-threshold-above"}
        if not required.issubset(observed):
            issues.append("页面变形未覆盖溶液同比缩放、mL/L 等价、浓度/进度变化和限量比例临界点")
        for kind, (sample, sample_expected) in samples_by_kind.items():
            rows = sample["request"].get("solutions") or []
            if kind == "common-volume-scale":
                base = request.get("solutions") or []
                ratios = [new.get("volume", 0) / old.get("volume", 1)
                          for old, new in zip(base, rows) if old.get("volume")]
                if len(ratios) != 2 or not all(math.isclose(x, ratios[0], rel_tol=1e-9, abs_tol=1e-12)
                                               for x in ratios):
                    issues.append("同比体积变形没有对两种溶液使用相同倍数")
                elif not same(sample_expected.get("limiting_reactants"), expected.get("limiting_reactants")) or not math.isclose(
                        sample_expected.get("precipitate_mass_g", 0), expected.get("precipitate_mass_g", 0) * ratios[0],
                        rel_tol=1e-9, abs_tol=1e-12):
                    issues.append("同比放大后限量试剂应不变、沉淀质量应同比变化")
            elif kind == "equivalent-unit":
                before, after = expected.get("solution_inputs", []), sample_expected.get("solution_inputs", [])
                if len(before) != len(after) or not all(same_num(a.get("amount_mol"), b.get("amount_mol"))
                                                          for a, b in zip(before, after)) or not same_num(
                        sample_expected.get("precipitate_mass_g"), expected.get("precipitate_mass_g")):
                    issues.append("mL/L 等价输入改变了物质的量或沉淀质量")
            elif kind == "progress-change":
                product = next((p for p in sample_expected.get("products", [])
                                if p.get("formula") == sample_expected.get("precipitate_formula")), {})
                if not math.isclose(sample_expected.get("precipitate_moles", 0),
                                    sample_expected.get("extent_mol", 0) * product.get("coefficient", 0),
                                    rel_tol=1e-9, abs_tol=1e-12):
                    issues.append("反应进度与沉淀物质的量未满足计量关系")
            elif kind == "stoichiometric-threshold-at":
                if not sample_expected.get("stoichiometric_mix") or len(sample_expected.get("limiting_reactants", [])) != 2:
                    issues.append("临界配比处没有识别出两种反应物同时为限量试剂")
            elif kind in ("stoichiometric-threshold-below", "stoichiometric-threshold-above"):
                controlled = sample.get("threshold_input_index")
                if controlled not in (0, 1):
                    issues.append("临界配比变形缺少被改变溶液的索引")
                else:
                    controlled_formula = rows[controlled].get("formula")
                    other_formula = rows[1 - controlled].get("formula")
                    expected_formula = controlled_formula if kind.endswith("below") else other_formula
                    actual = [item.get("formula") for item in sample_expected.get("limiting_reactants", [])]
                    if actual != [expected_formula]:
                        issues.append("临界比例两侧的限量试剂未正确翻转")

    if issues:
        return [mk("J3", "J3-11", "沉淀反应与质量定量独立复算", "fail",
                   "页面反应识别、溶液换算、沉淀质量和比例临界变形与 Python 参考实现一致",
                   "；".join(issues), "沉淀反应或页面变形未通过独立复算",
                   evidence="；".join(issues[:3]),
                   advice="使用 CHEMSOLVER.solvePrecipitation 的同一结果驱动方程、净离子式、沉淀质量和画布，并通过两侧临界配比变形",
                   severity="critical", weight=8)]
    return [mk("J3", "J3-11", "沉淀反应与质量定量独立复算", "pass",
               "页面反应识别、溶液换算、沉淀质量和比例临界变形与 Python 参考实现一致",
               "沉淀量、页面读数、真实控件和七类变形状态均通过独立复算",
               "沉淀反应定量通过页面层独立验证",
               evidence=(ctx.get("chem_precip_oracle") or {}).get("result", {}).get("equation", ""), weight=8)]


def _j3_redox(ctx):
    """Independently check redox equation, oxidation states and page reordering."""
    machine = ctx.get("machine") or {}
    text = (ctx.get("text") or "") + " " + str(ctx.get("topic") or "")
    topic_hit = bool(re.search(r"氧化还原|电子守恒|电子转移|半反应法|氧化数变化|氧化数配平", text))
    request = machine.get("CHEM_REDOX_REQUEST")
    if not isinstance(request, dict) and not topic_hit:
        return []
    oracle = ctx.get("chem_redox_oracle") or {}
    result = machine.get("CHEM_REDOX_RESULT")
    controls = machine.get("CHEM_REDOX_CONTROLS") or {}
    issues = []

    def same(actual, expected):
        if isinstance(actual, bool) or isinstance(expected, bool):
            return type(actual) is type(expected) and actual == expected
        if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
            return math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-12)
        if isinstance(expected, dict):
            return isinstance(actual, dict) and set(actual) == set(expected) and all(
                same(actual[key], expected[key]) for key in expected)
        if isinstance(expected, list):
            return isinstance(actual, list) and len(actual) == len(expected) and all(
                same(a, b) for a, b in zip(actual, expected))
        return actual == expected

    if not isinstance(request, dict) or not isinstance(result, dict):
        issues.append("缺少 CHEM_REDOX_REQUEST / CHEM_REDOX_RESULT")
    elif oracle.get("error"):
        issues.append("氧化还原参考求解失败：%s" % oracle["error"])
    else:
        expected = oracle.get("result") or {}
        if controls.get("medium") != request.get("medium"):
            issues.append("页面反应介质与求解请求不一致")
        if controls.get("reorder_button_visible") is not True:
            issues.append("缺少可见的物种顺序变形控件")
        fields = ("schema", "medium", "equation", "coefficients", "reactants", "products",
                  "oxidation_changes", "electron_balance", "atom_counts", "charge_counts", "checks")
        for field in fields:
            if not same(result.get(field), expected.get(field)):
                issues.append("页面 %s 与 Python 独立复算不一致" % field)
        normalize = lambda value: re.sub(r"\s+", "", str(value or ""))
        if normalize(machine.get("CHEM_REDOX_DISPLAYED_EQUATION")) != normalize(expected.get("equation")):
            issues.append("页面可见带电荷方程式与独立复算不一致")
        electron_text = str(machine.get("CHEM_REDOX_DISPLAYED_ELECTRONS") or "")
        electron_values = re.findall(r"\d+(?:\.\d+)?", electron_text)
        expected_electrons = expected.get("electron_balance", {}).get("transferred_electrons")
        if not electron_values or not any(math.isclose(float(value), expected_electrons,
                                                       rel_tol=1e-9, abs_tol=1e-12)
                                           for value in electron_values):
            issues.append("页面可见电子转移数与独立结果不一致")
        changes_text = normalize(machine.get("CHEM_REDOX_DISPLAYED_CHANGES"))
        for change in expected.get("oxidation_changes", []):
            if str(change["element"]) not in changes_text:
                issues.append("可见氧化数变化表缺少元素 %s" % change["element"])
            for value in (change["before"], change["after"]):
                token = ("%+g" % value).replace("+", "")
                if token not in changes_text:
                    issues.append("可见氧化数变化表未标出 %s 的变化数值 %s" %
                                  (change["element"], value))
        if not (result.get("checks") or {}).get("ok"):
            issues.append("页面的原子/电荷/电子守恒检查未全部通过")

        sample_rows = ctx.get("chem_redox_sample_oracles") or []
        if not sample_rows:
            issues.append("浏览器没有通过真实控件执行介质切换和物种换序变形测试")
        observed = set()
        for index, row in enumerate(sample_rows):
            sample = row.get("sample") or {}
            sample_oracle = row.get("oracle") or {}
            kind = sample.get("kind")
            observed.add(kind)
            prefix = "氧化还原变形 %d（%s）" % (index + 1, kind or "未命名")
            if sample_oracle.get("error"):
                issues.append("%s 独立复算失败：%s" % (prefix, sample_oracle["error"]))
                continue
            sample_expected = sample_oracle.get("result") or {}
            sample_result = sample.get("result") or {}
            sample_request = sample.get("request") or {}
            if not sample_result:
                issues.append(prefix + "缺少页面求解结果")
                continue
            for field in fields:
                if not same(sample_result.get(field), sample_expected.get(field)):
                    issues.append("%s 的 %s 与 Python 独立复算不一致" % (prefix, field))
            if normalize(sample.get("displayed_equation")) != normalize(sample_expected.get("equation")):
                issues.append(prefix + "可见带电荷方程式与求解结果不一致")
            if sample.get("controls", {}).get("medium") != sample_request.get("medium"):
                issues.append(prefix + "介质控件与变形请求不一致")
        if "species-reordering" not in observed:
            issues.append("浏览器未覆盖反应物/生成物顺序变形")
        else:
            sample = next((row.get("sample") or {} for row in sample_rows
                           if (row.get("sample") or {}).get("kind") == "species-reordering"), {})
            sample_request, sample_result = sample.get("request") or {}, sample.get("result") or {}
            baseline_coeff, sample_coeff = expected.get("coefficients") or {}, (sample_result.get("coefficients") or {})
            for side in ("reactants", "products"):
                baseline_species = [item.get("formula") if isinstance(item, dict) else item
                                    for item in request.get(side) or []]
                transformed_species = [item.get("formula") if isinstance(item, dict) else item
                                       for item in sample_request.get(side) or []]
                if transformed_species != list(reversed(baseline_species)):
                    issues.append("换序变形没有反转 %s" % ("反应物" if side == "reactants" else "生成物"))
                core_count = len(baseline_species)
                if (sample_coeff.get(side) or [])[:core_count] != list(
                        reversed((baseline_coeff.get(side) or [])[:core_count])):
                    issues.append("换序后 %s 配平系数没有按同一顺序重排" % side)
            if not same(sample_result.get("electron_balance"), expected.get("electron_balance")):
                issues.append("换序后电子转移量未保持不变")
        if "medium-change" not in observed:
            issues.append("浏览器未切换酸/碱介质并重新求解")
        else:
            sample = next((row.get("sample") or {} for row in sample_rows
                           if (row.get("sample") or {}).get("kind") == "medium-change"), {})
            sample_request = sample.get("request") or {}
            if sample_request.get("medium") == request.get("medium"):
                issues.append("介质变形样本没有改变酸/碱条件")

    if issues:
        return [mk("J3", "J3-12", "氧化还原配平与电子守恒", "fail",
                   "酸/碱条件下的离子方程、原子/电荷及氧化数电子守恒与 Python 独立实现一致",
                   "；".join(issues), "氧化还原方程或页面换序变形未通过独立复算",
                   evidence="；".join(issues[:3]),
                   advice="用 CHEMSOLVER.solveRedox 的同一结果驱动带电荷方程、氧化数变化和电子读数，并保留可执行的换序变形",
                   severity="critical", weight=8)]
    return [mk("J3", "J3-12", "氧化还原配平与电子守恒", "pass",
               "酸/碱条件下的离子方程、原子/电荷及氧化数电子守恒与 Python 独立实现一致",
               "带电荷方程、电子数、氧化数变化及真实物种换序结果均通过独立复算",
               "氧化还原求解通过页面层独立验证",
               evidence=expected.get("equation", ""), weight=8)]


def _j3_ksp(ctx):
    """Independently verify Ksp mass action, saturation state and page mutations."""
    machine = ctx.get("machine") or {}
    text = (ctx.get("text") or "") + " " + str(ctx.get("topic") or "")
    request = machine.get("CHEM_KSP_REQUEST")
    # A precipitation page may mention that Ksp is outside its model scope.
    # Its explicit solver request identifies the page type and must take
    # precedence over those explanatory words.
    if not isinstance(request, dict) and isinstance(machine.get("CHEM_PRECIP_REQUEST"), dict):
        return []
    topic_hit = bool(re.search(r"Ksp|K_sp|溶度积|溶解平衡|共同离子效应|溶解度积", text, re.I))
    if not isinstance(request, dict) and not topic_hit:
        return []
    result = machine.get("CHEM_KSP_RESULT")
    controls = machine.get("CHEM_KSP_CONTROLS") or {}
    oracle = ctx.get("chem_ksp_oracle") or {}
    issues = []

    def same(actual, expected):
        if isinstance(actual, bool) or isinstance(expected, bool):
            return type(actual) is type(expected) and actual == expected
        if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
            return math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-300)
        if isinstance(expected, dict):
            return isinstance(actual, dict) and set(actual) == set(expected) and all(
                same(actual[key], expected[key]) for key in expected)
        if isinstance(expected, list):
            return isinstance(actual, list) and len(actual) == len(expected) and all(
                same(a, b) for a, b in zip(actual, expected))
        return actual == expected

    def parse_reading(raw):
        # UI labels often use compact scientific notation such as
        # ``2.15×10^-4`` or superscript ``2.15×10⁻⁴``. Parse the exponent as
        # part of the number; reading only the mantissa silently turns it into
        # 2.15 and falsely fails correct Ksp/Q/solubility displays.
        text = str(raw or "").translate(str.maketrans(
            "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻", "0123456789+-")).replace("−", "-")
        number = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)"
        scientific = re.search(
            r"(" + number + r")\s*(?:×|[xX]|·|⋅)\s*10\s*(?:\^\s*)?([+-]?\d+)",
            text)
        if scientific:
            try:
                value = float(scientific.group(1)) * (10.0 ** int(scientific.group(2)))
                return value if math.isfinite(value) else None
            except (ValueError, OverflowError):
                return None
        match = re.search(r"(" + number + r"(?:e[+-]?\d+)?)", text, re.I)
        try:
            return float(match.group(1)) if match else None
        except (TypeError, ValueError, OverflowError):
            return None

    def state_matches(raw, wanted):
        state = re.sub(r"\s+", "", str(raw or "")).lower()
        if wanted == "unsaturated":
            return ("不饱和" in state or "未饱和" in state or "可继续溶解" in state or
                    "unsaturated" in state) and "过饱和" not in state
        if wanted == "saturated":
            if any(term in state for term in ("不饱和", "未饱和", "过饱和", "unsaturated", "supersaturated")):
                return False
            return "饱和" in state or "动态平衡" in state or state == "saturated"
        if wanted == "supersaturated":
            return any(term in state for term in ("过饱和", "析出", "沉淀倾向", "supersaturated"))
        return False

    if not isinstance(request, dict) or not isinstance(result, dict):
        issues.append("缺少 CHEM_KSP_REQUEST / CHEM_KSP_RESULT")
    elif oracle.get("error"):
        issues.append("Ksp Python 独立复算失败：%s" % oracle["error"])
    else:
        expected = oracle.get("result") or {}
        expected_ions = request.get("ions") or []
        if not same(controls.get("Ksp"), request.get("Ksp", request.get("ksp"))):
            issues.append("页面 Ksp 控件值与求解请求不一致")
        if controls.get("ion_indices") != list(range(len(expected_ions))):
            issues.append("页面离子浓度控件索引缺失、重复或顺序不完整")
        if not same(controls.get("initial_concentrations_mol_L"),
                    [ion.get("initial_concentration_mol_L", 0) for ion in expected_ions]):
            issues.append("页面初始离子浓度控件与求解请求不一致")
        fields = ("schema", "solid_formula", "Ksp", "dissolution_equation", "ions",
                  "initial_ion_product", "initial_log_ion_product", "saturation_ratio",
                  "saturation_state", "molar_solubility_mol_L",
                  "equilibrium_ion_concentrations_mol_L", "equilibrium_ion_product",
                  "precipitation_expected", "assumes_excess_solid", "checks")
        for field in fields:
            if not same(result.get(field), expected.get(field)):
                issues.append("页面 %s 与 Python 独立复算不一致" % field)
        normalize = lambda value: re.sub(r"\s+", "", str(value or ""))
        if normalize(machine.get("CHEM_KSP_DISPLAYED_EQUATION")) != normalize(expected.get("dissolution_equation")):
            issues.append("页面可见溶解方程式与求解结果不一致")
        displayed_q = parse_reading(machine.get("CHEM_KSP_DISPLAYED_Q"))
        if displayed_q is None or not math.isclose(displayed_q, expected.get("initial_ion_product", 0),
                                                    rel_tol=0.025, abs_tol=1e-300):
            issues.append("页面可见离子积 Q 与独立计算不一致")
        state_text = machine.get("CHEM_KSP_DISPLAYED_STATE")
        if not state_matches(state_text, expected.get("saturation_state")):
            issues.append("页面可见饱和状态与 Q/Ksp 判定不一致")
        displayed_s = machine.get("CHEM_KSP_DISPLAYED_SOLUBILITY")
        if expected.get("molar_solubility_mol_L") is None:
            if not re.search(r"过饱和|析出|无定义|无溶解度解|不计算", str(displayed_s or "")):
                issues.append("过饱和页面必须明确说明当前不提供溶解度解")
        else:
            shown_s = parse_reading(displayed_s)
            if shown_s is None or not math.isclose(shown_s, expected["molar_solubility_mol_L"],
                                                    rel_tol=0.025, abs_tol=1e-300):
                issues.append("页面可见摩尔溶解度与独立计算不一致")
        if not (result.get("checks") or {}).get("ok"):
            issues.append("Ksp 求解器原子配比/电荷/质量作用检查未通过")

        sample_rows = ctx.get("chem_ksp_sample_oracles") or []
        sample_by_kind = {}
        for index, row in enumerate(sample_rows):
            sample = row.get("sample") or {}
            sample_expected = (row.get("oracle") or {}).get("result") or {}
            sample_result = sample.get("result") or {}
            kind = sample.get("kind")
            if (row.get("oracle") or {}).get("error"):
                issues.append("Ksp 变形 %s 独立复算失败：%s" % (kind, row["oracle"]["error"]))
                continue
            if not sample_result:
                issues.append("Ksp 变形 %s 缺少页面结果" % kind)
                continue
            for field in fields:
                if not same(sample_result.get(field), sample_expected.get(field)):
                    issues.append("Ksp 变形 %s 的 %s 与 Python 复算不一致" % (kind, field))
            sample_request = sample.get("request") or {}
            sample_ions = sample_request.get("ions") or []
            sample_controls = sample.get("controls") or {}
            if not same(sample_controls.get("Ksp"), sample_request.get("Ksp", sample_request.get("ksp"))):
                issues.append("Ksp 变形 %s 的 Ksp 控件与请求不一致" % kind)
            if not same(sample_controls.get("initial_concentrations_mol_L"),
                        [ion.get("initial_concentration_mol_L", 0) for ion in sample_ions]):
                issues.append("Ksp 变形 %s 的浓度控件与请求不一致" % kind)
            if not same(sample_controls.get("ion_indices"), list(range(len(sample_ions)))):
                issues.append("Ksp 变形 %s 的离子控件索引不完整" % kind)
            normalize = lambda value: re.sub(r"\s+", "", str(value or ""))
            if normalize(sample.get("displayed_equation")) != normalize(sample_expected.get("dissolution_equation")):
                issues.append("Ksp 变形 %s 的可见溶解方程式错误" % kind)
            shown_q = parse_reading(sample.get("displayed_q"))
            wanted_q = sample_expected.get("initial_ion_product", 0)
            if shown_q is None or not math.isclose(shown_q, wanted_q, rel_tol=0.025, abs_tol=1e-300):
                issues.append("Ksp 变形 %s 的可见 Q 与独立计算不一致" % kind)
            wanted_state = sample_expected.get("saturation_state")
            state_text = sample.get("displayed_state")
            if not state_matches(state_text, wanted_state):
                issues.append("Ksp 变形 %s 的可见饱和状态错误" % kind)
            shown_s_text = str(sample.get("displayed_solubility") or "")
            wanted_s = sample_expected.get("molar_solubility_mol_L")
            if wanted_s is None:
                if not re.search(r"过饱和|析出|无定义|无溶解度解|不计算", shown_s_text):
                    issues.append("Ksp 变形 %s 未在过饱和时说明溶解度无定义" % kind)
            else:
                shown_s = parse_reading(shown_s_text)
                if shown_s is None or not math.isclose(shown_s, wanted_s, rel_tol=0.025, abs_tol=1e-300):
                    issues.append("Ksp 变形 %s 的可见摩尔溶解度错误" % kind)
            sample_by_kind.setdefault(kind, []).append(sample)

        required = {"ksp-increase", "common-ion-increase", "saturation-below", "saturation-at", "saturation-above"}
        missing = required - set(sample_by_kind)
        if missing:
            issues.append("浏览器未完成 Ksp/共同离子/Q-Ksp 临界点变形：" + "、".join(sorted(missing)))
        else:
            ksp_sample = sample_by_kind["ksp-increase"][0]
            ksp_request = ksp_sample.get("request") or {}
            ksp_result = ksp_sample.get("result") or {}
            if not (float(ksp_request.get("Ksp", ksp_request.get("ksp", 0))) >
                    float(request.get("Ksp", request.get("ksp", 0)))):
                issues.append("Ksp 变形没有提高 Ksp")
            if (ksp_request.get("solid_formula", ksp_request.get("solid")) !=
                    request.get("solid_formula", request.get("solid")) or
                    not same(ksp_request.get("ions"), request.get("ions"))):
                issues.append("Ksp 变形意外改变了固体或离子组成")
            base_s, changed_s = expected.get("molar_solubility_mol_L"), ksp_result.get("molar_solubility_mol_L")
            if base_s is not None and changed_s is not None and changed_s <= base_s:
                issues.append("提高 Ksp 后摩尔溶解度没有增大")

            common_sample = sample_by_kind["common-ion-increase"][0]
            common_request = common_sample.get("request") or {}
            common_ions = common_request.get("ions") or []
            common_index = common_sample.get("ion_index")
            if (not isinstance(common_index, int) or common_index < 0 or common_index >= len(expected_ions) or
                    len(common_ions) != len(expected_ions)):
                issues.append("共同离子变形未标明有效的离子索引")
            else:
                changed_indices = [i for i, (old, new) in enumerate(zip(expected_ions, common_ions))
                                   if not same(old.get("initial_concentration_mol_L", 0),
                                               new.get("initial_concentration_mol_L", 0))]
                if changed_indices != [common_index] or not (
                        float(common_ions[common_index].get("initial_concentration_mol_L", 0)) >
                        float(expected_ions[common_index].get("initial_concentration_mol_L", 0))):
                    issues.append("共同离子变形没有只提高一个真实离子浓度")
                if (common_request.get("solid_formula", common_request.get("solid")) !=
                        request.get("solid_formula", request.get("solid")) or
                        not same(common_request.get("Ksp", common_request.get("ksp")),
                                 request.get("Ksp", request.get("ksp"))) or
                        any(not same({key: value for key, value in old.items()
                                      if key != "initial_concentration_mol_L"},
                                     {key: value for key, value in new.items()
                                      if key != "initial_concentration_mol_L"})
                            for old, new in zip(expected_ions, common_ions))):
                    issues.append("共同离子变形改变了离子身份、系数或 Ksp")
                common_s = (common_sample.get("result") or {}).get("molar_solubility_mol_L")
                if base_s is not None and common_s is not None and common_s >= base_s:
                    issues.append("增加共同离子后摩尔溶解度没有降低")

            expected_states = {"saturation-below": "unsaturated", "saturation-at": "saturated",
                               "saturation-above": "supersaturated"}
            for kind, wanted_state in expected_states.items():
                sample = sample_by_kind[kind][0]
                sample_result = sample.get("result") or {}
                sample_request = sample.get("request") or {}
                threshold_ions = sample_request.get("ions") or []
                if sample_result.get("saturation_state") != wanted_state:
                    issues.append("Q/Ksp 临界点变形 %s 未判定为 %s" % (kind, wanted_state))
                if (len(threshold_ions) != len(expected_ions) or
                        sample_request.get("solid_formula", sample_request.get("solid")) !=
                        request.get("solid_formula", request.get("solid")) or
                        not same(sample_request.get("Ksp", sample_request.get("ksp")),
                                 request.get("Ksp", request.get("ksp"))) or
                        any(not same({key: value for key, value in old.items()
                                      if key != "initial_concentration_mol_L"},
                                     {key: value for key, value in new.items()
                                      if key != "initial_concentration_mol_L"})
                            for old, new in zip(expected_ions, threshold_ions))):
                    issues.append("Q/Ksp 临界点变形 %s 意外改变化学体系" % kind)
                ratio = float(sample_result.get("saturation_ratio", -1))
                if ((kind.endswith("below") and not ratio < 1 - 1e-8) or
                    (kind.endswith("at") and not math.isclose(ratio, 1, rel_tol=1e-8, abs_tol=1e-8)) or
                    (kind.endswith("above") and not ratio > 1 + 1e-8)):
                    issues.append("Q/Ksp 临界点变形 %s 没有位于要求的一侧" % kind)

    if issues:
        return [mk("J3", "J3-13", "溶解平衡与 Ksp 独立复算", "fail",
                   "溶度积、共同离子摩尔溶解度及 Q/Ksp 饱和状态与 Python 参考模型一致",
                   "；".join(issues), "Ksp 页面数值或变形验证未通过独立复算",
                   evidence="；".join(issues[:3]),
                   advice="用 CHEMSOLVER.solveSolubilityEquilibrium 的结果驱动方程、Q、饱和状态和 s，并保留共同离子与 Q/Ksp 临界点变形",
                   severity="critical", weight=8)]
    return [mk("J3", "J3-13", "溶解平衡与 Ksp 独立复算", "pass",
               "溶度积、共同离子摩尔溶解度及 Q/Ksp 饱和状态与 Python 参考模型一致",
               "页面读数、共同离子效应、Ksp 改变和临界点三态均通过独立复算",
               "溶解平衡页面通过独立验证", evidence=expected.get("dissolution_equation", ""), weight=8)]


def j3_conservation(ctx):
    out = _j3_precipitation(ctx) + _j3_redox(ctx) + _j3_ksp(ctx)
    machine = ctx.get("machine") or {}
    data = machine.get("DATA") or {}
    text = ctx.get("text") or ""
    precip_topic = (isinstance(machine.get("CHEM_PRECIP_REQUEST"), dict) or
                    bool(re.search(r"沉淀反应|生成沉淀|沉淀质量|沉淀物质的量|硫酸钡|氯化银|碳酸钙沉淀|氢氧化铜|氢氧化铁|氢氧化镁",
                                   text + " " + str(ctx.get("topic") or ""))))
    redox_topic = (isinstance(machine.get("CHEM_REDOX_REQUEST"), dict) or
                   bool(re.search(r"氧化还原|电子守恒|电子转移|半反应法|氧化数变化|氧化数配平",
                                  text + " " + str(ctx.get("topic") or ""))))
    ksp_topic = (isinstance(machine.get("CHEM_KSP_REQUEST"), dict) or
                 bool(re.search(r"Ksp|K_sp|溶度积|溶解平衡|共同离子效应|溶解度积",
                                text + " " + str(ctx.get("topic") or ""), re.I)))
    checked, fails, reviews = 0, [], []

    def same_value(actual, expected):
        if isinstance(actual, bool) or isinstance(expected, bool):
            return type(actual) is type(expected) and actual == expected
        if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
            return math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-12)
        if isinstance(expected, dict):
            return isinstance(actual, dict) and set(actual) == set(expected) and all(
                same_value(actual[key], expected[key]) for key in expected)
        if isinstance(expected, list):
            return isinstance(actual, list) and len(actual) == len(expected) and all(
                same_value(a, b) for a, b in zip(actual, expected))
        return actual == expected

    def same_numeric(actual, expected):
        if isinstance(actual, bool) or isinstance(expected, bool):
            return False
        if not isinstance(actual, (int, float, str)) or not isinstance(expected, (int, float, str)):
            return False
        try:
            a, b = float(actual), float(expected)
        except (TypeError, ValueError, OverflowError):
            return False
        return math.isfinite(a) and math.isfinite(b) and math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)

    def same_numeric_list(actual, expected):
        return isinstance(actual, list) and isinstance(expected, list) and len(actual) == len(expected) and all(
            same_numeric(a, b) for a, b in zip(actual, expected))

    def displayed_gas_volume_l(raw):
        """Parse a labeled gas-volume reading and its displayed rounding step."""
        matches = list(re.finditer(
            r"([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*(mL|ml|毫升|L|升)(?![A-Za-z])", str(raw or ""), re.I))
        if not matches:
            return None, None, "读数必须带 L 或 mL 单位"
        match = matches[-1]
        number, unit = match.group(1), match.group(2)
        decimals = len(number.partition(".")[2])
        if unit.lower() in ("ml", "毫升"):
            factor = 0.001
        else:
            factor = 1.0
            if decimals < 2:
                return None, None, "以 L 显示时至少保留两位小数"
        value_l = float(number) * factor
        tolerance_l = (10 ** (-decimals)) * factor / 2 + 1e-12
        return value_l, tolerance_l, None

    gas_topic = (isinstance(machine.get("CHEM_GAS_REQUEST"), dict) or
                 bool(re.search(r"气体制取|气体收集|排水集气|制取氢气|收集氢气|制取二氧化碳|收集二氧化碳|制取氧气|气体体积定量",
                                text + " " + str(ctx.get("topic") or ""))))
    if gas_topic:
        request = machine.get("CHEM_GAS_REQUEST")
        page_result = machine.get("CHEM_GAS_RESULT")
        controls = machine.get("CHEM_GAS_CONTROLS")
        oracle = ctx.get("chem_gas_oracle") or {}
        issues = []
        if not isinstance(request, dict) or not isinstance(page_result, dict):
            issues.append("缺少可复算的 CHEM_GAS_REQUEST / CHEM_GAS_RESULT")
        elif oracle.get("error"):
            issues.append("独立气体收集复算失败：%s" % oracle["error"])
        else:
            expected = oracle.get("result") or {}
            expected_controls = {
                "amount_indices": list(range(len(request.get("initial_amounts_mol") or []))),
                "amounts_mol": request.get("initial_amounts_mol"),
                "progress": request.get("progress", 1.0),
                "temperature_c": request.get("temperature_c"),
                "total_pressure_kpa": request.get("total_pressure_kpa"),
                "collection_method": request.get("collection_method", "dry"),
            }
            if not isinstance(controls, dict):
                issues.append("缺少页面实际反应物、进度、温度、压强和集气方式控件")
            else:
                for key, value in expected_controls.items():
                    if key == "collection_method":
                        if controls.get(key) != value:
                            issues.append("页面集气方式控件与求解请求不一致")
                    elif key == "amount_indices":
                        if controls.get(key) != value:
                            issues.append("页面反应物物质的量控件索引缺失、重复或错位")
                    elif key == "amounts_mol":
                        if not same_numeric_list(controls.get(key), value):
                            issues.append("页面物质的量控件与求解请求不一致")
                    elif not same_numeric(controls.get(key), value):
                        issues.append("页面 %s 控件与求解请求不一致" % key)

            fields = ("schema", "equation", "coefficients", "initial_amounts_mol", "progress",
                      "max_extent_mol", "extent_mol", "limiting_reactants", "stoichiometric_mix",
                      "reactants", "products", "element_balance", "charge_balance", "gas_formula",
                      "gas_moles", "temperature_c", "temperature_k", "total_pressure_kpa",
                      "collection_method", "water_vapor_pressure_kpa", "dry_gas_partial_pressure_kpa",
                      "water_vapor_model", "gas_constant_l_kpa_mol_k", "gas_volume_l", "checks")
            for field in fields:
                if not same_value(page_result.get(field), expected.get(field)):
                    issues.append("页面 %s 与 Python 独立复算不一致" % field)
            normalize_equation = lambda value: re.sub(
                r"\s+", "", str(value).translate(str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")))
            displayed_equation = machine.get("CHEM_GAS_DISPLAYED_EQUATION") or ""
            if normalize_equation(displayed_equation) != normalize_equation(expected.get("equation", "")):
                issues.append("页面可见方程式与独立配平结果不一致")
            displayed_volume = str(machine.get("CHEM_GAS_DISPLAYED_VOLUME") or "")
            displayed_value_l, displayed_tolerance_l, volume_error = displayed_gas_volume_l(displayed_volume)
            if volume_error:
                issues.append("页面可见气体体积 " + volume_error)
            elif not math.isclose(displayed_value_l, expected.get("gas_volume_l", math.nan),
                                  rel_tol=0.0, abs_tol=displayed_tolerance_l):
                issues.append("页面可见气体体积与独立复算不一致或缺失")
            if not (page_result.get("checks") or {}).get("ok"):
                issues.append("页面反应守恒、分压分解或 PV=nRT 检查未通过")

            sample_rows = ctx.get("chem_gas_sample_oracles") or []
            if not sample_rows:
                issues.append("浏览器未完成气体页面真实控件变形测试")
            observed_kinds = set()
            sample_results = {}
            for index, sample_row in enumerate(sample_rows):
                sample = sample_row.get("sample") or {}
                sample_oracle = sample_row.get("oracle") or {}
                sample_request = sample.get("request")
                sample_result = sample.get("result")
                sample_controls = sample.get("controls") or {}
                kind = sample.get("kind")
                observed_kinds.add(kind)
                prefix = "气体变形 %d（%s）" % (index + 1, kind or "未命名")
                if sample_oracle.get("error"):
                    issues.append("%s独立复算失败：%s" % (prefix, sample_oracle["error"]))
                    continue
                sample_expected = sample_oracle.get("result") or {}
                sample_results[kind] = (sample_request, sample_result, sample_expected)
                if not isinstance(sample_request, dict) or not isinstance(sample_result, dict):
                    issues.append("%s缺少浏览器请求或结果" % prefix)
                    continue
                amounts = sample_request.get("initial_amounts_mol") or []
                control_expectations = {
                    "amount_indices": list(range(len(amounts))), "amounts_mol": amounts,
                    "progress": sample_request.get("progress", 1.0),
                    "temperature_c": sample_request.get("temperature_c"),
                    "total_pressure_kpa": sample_request.get("total_pressure_kpa"),
                    "collection_method": sample_request.get("collection_method", "dry"),
                }
                for key, value in control_expectations.items():
                    if key == "collection_method":
                        if sample_controls.get(key) != value:
                            issues.append("%s集气方式控件与请求不一致" % prefix)
                    elif key == "amount_indices":
                        if sample_controls.get(key) != value:
                            issues.append("%s反应物控件索引错位" % prefix)
                    elif key == "amounts_mol":
                        if not same_numeric_list(sample_controls.get(key), value):
                            issues.append("%s物质的量控件与请求不一致" % prefix)
                    elif not same_numeric(sample_controls.get(key), value):
                        issues.append("%s控件 %s 与请求不一致" % (prefix, key))
                for field in fields:
                    if not same_value(sample_result.get(field), sample_expected.get(field)):
                        issues.append("%s页面 %s 与参考实现不一致" % (prefix, field))
                if normalize_equation(sample.get("displayed_equation")) != normalize_equation(sample_expected.get("equation", "")):
                    issues.append("%s页面可见方程式与计算结果不一致" % prefix)
                sample_value_l, sample_tolerance_l, sample_volume_error = displayed_gas_volume_l(
                    sample.get("displayed_volume"))
                if sample_volume_error:
                    issues.append("%s页面可见气体体积 %s" % (prefix, sample_volume_error))
                elif not math.isclose(sample_value_l, sample_expected.get("gas_volume_l", math.nan),
                                      rel_tol=0.0, abs_tol=sample_tolerance_l):
                    issues.append("%s页面可见体积读数与计算结果不一致" % prefix)

            required_kinds = {"common-amount-scale", "progress-change", "temperature-change",
                              "pressure-change", "method-toggle"}
            if not required_kinds.issubset(observed_kinds):
                issues.append("浏览器未覆盖物质的量、进度、温度、压强和集气方式变形")
            baseline_amounts = request.get("initial_amounts_mol") or []
            for kind, row in sample_results.items():
                sample_request, _, sample_expected = row
                if kind == "common-amount-scale":
                    changed_amounts = sample_request.get("initial_amounts_mol") or []
                    ratios = [new / old for old, new in zip(baseline_amounts, changed_amounts) if old]
                    if len(changed_amounts) != len(baseline_amounts) or not ratios or not all(
                            math.isclose(ratio, ratios[0], rel_tol=1e-9, abs_tol=1e-12) for ratio in ratios):
                        issues.append("同比放大变形未对所有反应物物质的量使用同一倍数")
                    elif not same_value(sample_expected.get("limiting_reactants"), expected.get("limiting_reactants")):
                        issues.append("同比放大后限量试剂发生了不应有的改变")
                    elif not math.isclose(sample_expected.get("gas_moles", 0),
                                          expected.get("gas_moles", 0) * ratios[0], rel_tol=1e-9, abs_tol=1e-12):
                        issues.append("同比放大后产气量没有同比变化")
                elif kind == "progress-change":
                    gas_row = next((item for item in sample_expected.get("products", [])
                                    if item.get("formula") == sample_expected.get("gas_formula")), {})
                    expected_progress_moles = (sample_expected.get("extent_mol", 0) *
                                               gas_row.get("coefficient", 0))
                    if not math.isclose(sample_expected.get("gas_moles", 0),
                                        expected_progress_moles, rel_tol=1e-9, abs_tol=1e-12):
                        issues.append("反应进度与生成气体物质的量不符合线性关系")
                elif kind == "temperature-change":
                    if not math.isclose(sample_expected.get("gas_moles", 0), expected.get("gas_moles", 0),
                                         rel_tol=1e-9, abs_tol=1e-12) or not math.isclose(
                            sample_expected.get("gas_volume_l", 0) * sample_expected.get("dry_gas_partial_pressure_kpa", 0) /
                            sample_expected.get("temperature_k", 1),
                            expected.get("gas_volume_l", 0) * expected.get("dry_gas_partial_pressure_kpa", 0) /
                            expected.get("temperature_k", 1), rel_tol=1e-9, abs_tol=1e-12):
                        issues.append("温度变形未满足定量气体状态关系")
                elif kind == "pressure-change":
                    if not math.isclose(sample_expected.get("gas_moles", 0), expected.get("gas_moles", 0),
                                         rel_tol=1e-9, abs_tol=1e-12) or not math.isclose(
                            sample_expected.get("gas_volume_l", 0) * sample_expected.get("dry_gas_partial_pressure_kpa", 0),
                            expected.get("gas_volume_l", 0) * expected.get("dry_gas_partial_pressure_kpa", 0),
                            rel_tol=1e-9, abs_tol=1e-12):
                        issues.append("压强变形未满足 P干气·V=nRT")
            method_row = sample_results.get("method-toggle")
            if method_row:
                method_request, _, method_expected = method_row
                if any(not same_value(method_request.get(key), request.get(key)) for key in (
                        "reactants", "products", "initial_amounts_mol", "progress", "temperature_c",
                        "total_pressure_kpa", "gas_formula")):
                    issues.append("集气方式变形同时改变了反应条件，无法检验水蒸气压修正")
                dry_result = expected if request.get("collection_method", "dry") == "dry" else method_expected
                wet_result = method_expected if method_request.get("collection_method") == "over_water" else expected
                if dry_result.get("collection_method") != "dry" or wet_result.get("collection_method") != "over_water":
                    issues.append("集气方式变形没有实际覆盖干燥集气与排水集气")
                elif not math.isclose(wet_result.get("dry_gas_partial_pressure_kpa", 0),
                                      wet_result.get("total_pressure_kpa", 0) -
                                      wet_result.get("water_vapor_pressure_kpa", 0), rel_tol=1e-9, abs_tol=1e-12):
                    issues.append("排水集气没有扣除水蒸气分压")
                elif not wet_result.get("gas_volume_l", 0) > dry_result.get("gas_volume_l", 0):
                    issues.append("相同温度/总压下，排水集气体积应大于干燥集气体积")

        if issues:
            out.append(mk("J3", "J3-10", "气体制取量与状态方程独立复算", "fail",
                          "页面反应产气量、温压条件、集气修正和读数与 Python 独立实现一致",
                          "；".join(issues), "气体生成量或 PV=nRT 页面变形未通过独立复算",
                          evidence="；".join(issues[:3]),
                          advice="用 CHEMSOLVER.solveGasCollection 的同一结果驱动方程式、装置和读数；对页面真实控件执行量、进度、温度、压强及干/湿集气变形",
                          severity="critical", weight=8))
        else:
            out.append(mk("J3", "J3-10", "气体制取量与状态方程独立复算", "pass",
                          "页面反应产气量、温压条件、集气修正和读数与 Python 独立实现一致",
                          "页面读数、限量试剂、物质的量/进度/温度/压强/集气方式变形均通过独立复算",
                          "气体体积通过反应计量与理想气体独立验证",
                          evidence=expected.get("equation", ""), weight=8))

    titration_topic = (isinstance(machine.get("CHEM_TITRATION_REQUEST"), dict) or
                       bool(re.search(r"酸碱中和滴定|酸碱滴定|中和滴定",
                                      text + " " + str(ctx.get("topic") or ""))))
    if titration_topic:
        request = machine.get("CHEM_TITRATION_REQUEST")
        page_result = machine.get("CHEM_TITRATION_RESULT")
        controls = machine.get("CHEM_TITRATION_CONTROLS")
        oracle = ctx.get("chem_titration_oracle") or {}
        issues = []
        if not isinstance(request, dict) or not isinstance(page_result, dict):
            issues.append("缺少可复算的 CHEM_TITRATION_REQUEST / CHEM_TITRATION_RESULT")
        elif oracle.get("error"):
            issues.append("独立酸碱滴定复算失败：%s" % oracle["error"])
        else:
            expected = oracle.get("result") or {}
            acid, base = request.get("acid") or {}, request.get("base") or {}
            control_fields = {
                "acid_concentration_mol_L": acid.get("concentration_mol_L"),
                "acid_volume": acid.get("volume"),
                "acid_volume_unit": acid.get("volume_unit"),
                "base_concentration_mol_L": base.get("concentration_mol_L"),
                "base_volume": base.get("volume"),
                "base_volume_unit": base.get("volume_unit"),
            }
            if not isinstance(controls, dict):
                issues.append("缺少页面实际酸/碱浓度、体积和单位控件")
            else:
                for key, value in control_fields.items():
                    if key.endswith("_unit"):
                        if str(controls.get(key, "")).lower() != str(value or "").lower():
                            issues.append("页面 %s 控件与请求不一致" % key)
                    elif not same_numeric(controls.get(key), value):
                        issues.append("页面 %s 控件与请求不一致" % key)

            fields = ("schema", "temperature_c", "equation", "acid", "base", "salt_formula",
                      "acid_moles_initial", "base_moles_added", "neutralized_moles",
                      "acid_moles_remaining", "base_moles_remaining", "equivalence_volume_l",
                      "equivalence_volume_ml", "total_volume_l", "net_acid_concentration_mol_L",
                      "excess_acid_concentration_mol_L", "excess_base_concentration_mol_L",
                      "hydrogen_concentration_mol_L", "hydroxide_concentration_mol_L",
                      "neutralization_fraction", "pH", "pOH", "state", "checks")
            for field in fields:
                if not same_value(page_result.get(field), expected.get(field)):
                    issues.append("页面 %s 与独立复算不一致" % field)
            normalize_equation = lambda value: re.sub(
                r"\s+", "", str(value).translate(str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")))
            displayed = machine.get("CHEM_TITRATION_DISPLAYED_EQUATION") or ""
            if normalize_equation(displayed) != normalize_equation(expected.get("equation", "")):
                issues.append("页面实际显示的中和方程式与独立复算不一致")
            displayed_ph = str(machine.get("CHEM_TITRATION_DISPLAYED_PH") or "")
            ph_values = re.findall(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)", displayed_ph)
            if not ph_values or not math.isclose(float(ph_values[-1]), expected.get("pH", math.nan),
                                                 rel_tol=0.0, abs_tol=0.011):
                issues.append("页面显示的 pH 与独立复算不一致或缺失")
            if not (page_result.get("checks") or {}).get("ok"):
                issues.append("页面中和、物质的量或水的离子积检查未通过")

            sample_rows = ctx.get("chem_titration_sample_oracles") or []
            if not sample_rows:
                issues.append("浏览器未完成酸碱滴定页面变形测试")
            observed_kinds = set()
            for index, sample_row in enumerate(sample_rows):
                sample = sample_row.get("sample") or {}
                sample_oracle = sample_row.get("oracle") or {}
                sample_request = sample.get("request")
                sample_result = sample.get("result")
                sample_controls = sample.get("controls") or {}
                kind = sample.get("kind")
                observed_kinds.add(kind)
                prefix = "滴定变形状态 %d（%s）" % (index + 1, kind or "未命名")
                if sample_oracle.get("error"):
                    issues.append("%s独立复算失败：%s" % (prefix, sample_oracle["error"]))
                    continue
                sample_expected = sample_oracle.get("result") or {}
                if not isinstance(sample_request, dict) or not isinstance(sample_result, dict):
                    issues.append("%s缺少页面请求或结果" % prefix)
                    continue
                s_acid, s_base = sample_request.get("acid") or {}, sample_request.get("base") or {}
                sample_controls_expected = {
                    "acid_concentration_mol_L": s_acid.get("concentration_mol_L"),
                    "acid_volume": s_acid.get("volume"),
                    "acid_volume_unit": s_acid.get("volume_unit"),
                    "base_concentration_mol_L": s_base.get("concentration_mol_L"),
                    "base_volume": s_base.get("volume"),
                    "base_volume_unit": s_base.get("volume_unit"),
                }
                for key, value in sample_controls_expected.items():
                    if key.endswith("_unit"):
                        if str(sample_controls.get(key, "")).lower() != str(value or "").lower():
                            issues.append("%s %s 控件与请求不一致" % (prefix, key))
                    elif not same_numeric(sample_controls.get(key), value):
                        issues.append("%s %s 控件与请求不一致" % (prefix, key))
                for field in fields:
                    if not same_value(sample_result.get(field), sample_expected.get(field)):
                        issues.append("%s页面 %s 与 Python 参考结果不一致" % (prefix, field))
                if normalize_equation(sample.get("displayed_equation")) != normalize_equation(sample_expected.get("equation", "")):
                    issues.append("%s可见方程式未与求解结果同步" % prefix)
                sample_ph = re.findall(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)",
                                       str(sample.get("displayed_ph") or ""))
                if not sample_ph or not math.isclose(float(sample_ph[-1]), sample_expected.get("pH", math.nan),
                                                     rel_tol=0.0, abs_tol=0.011):
                    issues.append("%s可见 pH 未与求解结果同步" % prefix)

            required_kinds = {"equivalent-volume-units", "below-equivalence",
                              "at-equivalence", "above-equivalence"}
            if not required_kinds.issubset(observed_kinds):
                issues.append("浏览器未覆盖单位等价和当量点前/当量点/当量点后三态")
            sample_by_kind = {(row.get("sample") or {}).get("kind"): row.get("oracle", {}).get("result")
                              for row in sample_rows}
            unit_result = sample_by_kind.get("equivalent-volume-units")
            if unit_result:
                for field in ("acid_moles_initial", "base_moles_added", "neutralized_moles",
                              "acid_moles_remaining", "base_moles_remaining", "equivalence_volume_l",
                              "total_volume_l", "hydrogen_concentration_mol_L",
                              "hydroxide_concentration_mol_L", "neutralization_fraction", "pH", "pOH", "state"):
                    if not same_value(unit_result.get(field), expected.get(field)):
                        issues.append("mL/L 等价变形后 %s 未保持不变" % field)
            threshold = [sample_by_kind.get(kind) for kind in
                         ("below-equivalence", "at-equivalence", "above-equivalence")]
            if all(threshold):
                if [item.get("state") for item in threshold] != ["acidic", "equivalence", "basic"]:
                    issues.append("当量点前/当量点/当量点后的溶液状态不正确")
                if not (threshold[0].get("pH") < threshold[1].get("pH") < threshold[2].get("pH")):
                    issues.append("滴定越过当量点时 pH 没有按酸性→中性→碱性递增")

        if issues:
            out.append(mk("J3", "J3-09", "酸碱滴定 pH 与当量点独立复算", "fail",
                          "页面读数、控件、方程式和当量点变形与独立强酸强碱模型一致",
                          "；".join(issues), "页面滴定结果或页面变形测试未通过独立复算",
                          evidence="；".join(issues[:3]),
                          advice="以 CHEMSOLVER.solveAcidBaseTitration 的同一返回对象驱动 pH、方程和实验图；保留 mL/L 等价与当量点前后实控件变形",
                          severity="critical", weight=8))
        else:
            out.append(mk("J3", "J3-09", "酸碱滴定 pH 与当量点独立复算", "pass",
                          "页面读数、控件、方程式和当量点变形与独立强酸强碱模型一致",
                          "页面计算、实际控件、可见读数、单位等价及当量点三态均通过 Python 独立复算",
                          "酸碱滴定通过页面层独立验证",
                          evidence=expected.get("equation", ""), weight=8))

    explicit_mix_request = isinstance(machine.get("CHEM_MIX_REQUEST"), dict)
    inferred_mix_topic = bool(re.search(
        r"溶液混合|混合.{0,12}溶液|溶液.{0,12}(?:混合|浓度|体积|限量试剂|理论产量)|浓度.{0,12}(?:毫升|体积|混合|限量试剂)",
        text + " " + str(ctx.get("topic") or "")))
    # An explicit machine request is authoritative. Text heuristics are only
    # used when a more specific chemistry solver family has not claimed the page;
    # otherwise Ksp prose about ion concentrations/solutions can look like mixing.
    mix_topic = explicit_mix_request or (
        inferred_mix_topic and not any((precip_topic, redox_topic, ksp_topic, gas_topic, titration_topic)))
    if mix_topic:
        request = machine.get("CHEM_MIX_REQUEST")
        page_result = machine.get("CHEM_MIX_RESULT")
        controls = machine.get("CHEM_MIX_CONTROLS")
        oracle = ctx.get("chem_mix_oracle") or {}
        issues = []
        if not isinstance(request, dict) or not isinstance(page_result, dict):
            issues.append("缺少可复算的 CHEM_MIX_REQUEST / CHEM_MIX_RESULT")
        elif oracle.get("error"):
            issues.append("独立溶液混合复算失败：%s" % oracle["error"])
        else:
            expected = oracle.get("result") or {}
            solutions = request.get("solutions") or []
            if not isinstance(controls, dict):
                issues.append("缺少页面实际浓度、体积、单位或进度控件值")
            else:
                indices = list(range(len(solutions)))
                for key in ("concentration_indices", "volume_indices", "unit_indices"):
                    if controls.get(key) != indices:
                        issues.append("页面溶液控件索引缺失、重复或顺序不完整（%s）" % key)
                if not same_numeric_list(controls.get("concentrations_mol_L"),
                                         [item.get("concentration_mol_L") for item in solutions]):
                    issues.append("页面浓度控件与求解请求不一致")
                if not same_numeric_list(controls.get("volumes"), [item.get("volume") for item in solutions]):
                    issues.append("页面体积控件与求解请求不一致")
                if controls.get("volume_units") != [item.get("volume_unit") for item in solutions]:
                    issues.append("页面体积单位控件与求解请求不一致")
                if not same_numeric(controls.get("progress"), request.get("progress", 1.0)):
                    issues.append("页面反应进度控件与求解请求不一致")
            fields = ("equation", "coefficients", "solution_inputs", "initial_amounts_mol", "progress",
                      "max_extent_mol", "extent_mol", "limiting_reactants", "stoichiometric_mix",
                      "reactants", "products", "element_balance", "charge_balance", "checks")
            for field in fields:
                if not same_value(page_result.get(field), expected.get(field)):
                    issues.append("页面 %s 与独立复算不一致" % field)
            normalize_equation = lambda value: re.sub(
                r"\s+", "", str(value).translate(str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")))
            displayed = machine.get("CHEM_MIX_DISPLAYED_EQUATION") or ""
            if normalize_equation(displayed) != normalize_equation(expected.get("equation", "")):
                issues.append("页面实际显示的反应方程式与求解结果不一致")
            if not (page_result.get("checks") or {}).get("ok"):
                issues.append("页面溶液换算或反应守恒检查未通过")

            sample_rows = ctx.get("chem_mix_sample_oracles") or []
            if not sample_rows:
                issues.append("浏览器未完成浓度/体积/进度控件变形测试")
            has_unit_equivalence = False
            for index, sample_row in enumerate(sample_rows):
                sample = sample_row.get("sample") or {}
                sample_oracle = sample_row.get("oracle") or {}
                sample_request = sample.get("request")
                sample_result = sample.get("result")
                sample_controls = sample.get("controls") or {}
                prefix = "溶液混合变形状态 %d" % (index + 1)
                if sample_oracle.get("error"):
                    issues.append("%s独立复算失败：%s" % (prefix, sample_oracle["error"]))
                    continue
                sample_expected = sample_oracle.get("result") or {}
                if not isinstance(sample_request, dict) or not isinstance(sample_result, dict):
                    issues.append("%s缺少请求或页面结果" % prefix)
                    continue
                sample_solutions = sample_request.get("solutions") or []
                sample_indices = list(range(len(sample_solutions)))
                for key in ("concentration_indices", "volume_indices", "unit_indices"):
                    if sample_controls.get(key) != sample_indices:
                        issues.append("%s控件索引缺失或错位（%s）" % (prefix, key))
                if not same_numeric_list(sample_controls.get("concentrations_mol_L"),
                                         [item.get("concentration_mol_L") for item in sample_solutions]):
                    issues.append("%s浓度控件与请求不一致" % prefix)
                if not same_numeric_list(sample_controls.get("volumes"),
                                         [item.get("volume") for item in sample_solutions]):
                    issues.append("%s体积控件与请求不一致" % prefix)
                if sample_controls.get("volume_units") != [item.get("volume_unit") for item in sample_solutions]:
                    issues.append("%s单位控件与请求不一致" % prefix)
                if not same_numeric(sample_controls.get("progress"), sample_request.get("progress", 1.0)):
                    issues.append("%s进度控件与请求不一致" % prefix)
                for field in fields:
                    if not same_value(sample_result.get(field), sample_expected.get(field)):
                        issues.append("%s页面 %s 与独立复算不一致" % (prefix, field))
                if normalize_equation(sample.get("displayed_equation")) != normalize_equation(sample_expected.get("equation", "")):
                    issues.append("%s页面显示方程式与求解结果不一致" % prefix)
                if not (sample_result.get("checks") or {}).get("ok"):
                    issues.append("%s页面换算或守恒检查未通过" % prefix)
                if sample.get("kind") == "equivalent-volume-unit":
                    has_unit_equivalence = True
                    for field in ("initial_amounts_mol", "progress", "max_extent_mol", "extent_mol",
                                  "limiting_reactants", "reactants", "products"):
                        if not same_value(sample_result.get(field), expected.get(field)):
                            issues.append("等价 mL/L 变形后 %s 未保持不变" % field)
            if not has_unit_equivalence:
                issues.append("浏览器未验证 mL 与 L 等价换算")
        if issues:
            out.append(mk("J3", "J3-08", "溶液混合换算与反应计量独立复算", "fail",
                          "Python 参考实现与页面的浓度/体积换算、反应结果及控件变形关系一致",
                          "；".join(issues), "页面溶液换算、单位变化或反应结果未通过独立复算",
                          evidence="；".join(issues[:3]),
                          advice="用 CHEMSOLVER.solveSolutionMixing 的结果驱动全部读数；变化单位时将体积同步换算，并由参考实现复算",
                          severity="critical", weight=8))
        else:
            out.append(mk("J3", "J3-08", "溶液混合换算与反应计量独立复算", "pass",
                          "Python 参考实现与页面的浓度/体积换算、反应结果及控件变形关系一致",
                          "页面结果、控件变形样本和 mL/L 等价换算均通过独立复算",
                          "溶液混合计算通过独立复算",
                          evidence=expected.get("equation", ""), weight=8))

    stoich_topic = not precip_topic and not gas_topic and not mix_topic and (
        isinstance(machine.get("CHEM_STOICH_REQUEST"), dict) or
        bool(re.search(r"限量试剂|过量试剂|理论产量|反应物剩余|反应进度|反应物用量|化学计量",
                       text + " " + str(ctx.get("topic") or "")))
    )
    if stoich_topic:
        request = machine.get("CHEM_STOICH_REQUEST")
        page_result = machine.get("CHEM_STOICH_RESULT")
        controls = machine.get("CHEM_STOICH_CONTROLS")
        oracle = ctx.get("chem_stoich_oracle") or {}
        issues = []
        if not isinstance(request, dict) or not isinstance(page_result, dict):
            issues.append("缺少可复算的 CHEM_STOICH_REQUEST / CHEM_STOICH_RESULT")
        elif oracle.get("error"):
            issues.append("独立反应计量复算失败：%s" % oracle["error"])
        else:
            expected = oracle.get("result") or {}
            if not isinstance(controls, dict):
                issues.append("缺少页面实际物质的量/反应进度控件值")
            else:
                expected_indices = list(range(len(request.get("initial_amounts_mol") or [])))
                if controls.get("indices") != expected_indices:
                    issues.append("页面物质的量控件索引缺失、重复或顺序不完整")
                if not same_numeric_list(controls.get("initial_amounts_mol"), request.get("initial_amounts_mol")):
                    issues.append("页面物质的量控件值与求解请求不一致")
                if not same_numeric(controls.get("progress"), request.get("progress", 1.0)):
                    issues.append("页面反应进度控件值与求解请求不一致")
            for field in ("equation", "coefficients", "initial_amounts_mol", "progress",
                          "max_extent_mol", "extent_mol", "limiting_reactants",
                          "stoichiometric_mix", "reactants", "products",
                          "element_balance", "charge_balance", "checks"):
                if not same_value(page_result.get(field), expected.get(field)):
                    issues.append("页面 %s 与独立复算不一致" % field)
            displayed = machine.get("CHEM_STOICH_DISPLAYED_EQUATION") or ""
            normalize_equation = lambda value: re.sub(
                r"\s+", "", str(value).translate(str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")))
            if normalize_equation(displayed) != normalize_equation(expected.get("equation", "")):
                issues.append("页面实际显示的反应方程式与求解结果不一致")
            if not (page_result.get("checks") or {}).get("ok"):
                issues.append("页面反应计量结果未通过守恒校验")
            sample_rows = ctx.get("chem_stoich_sample_oracles") or []
            if not sample_rows:
                issues.append("浏览器未完成物质的量/进度控件变形测试")
            samples_by_kind = {}
            for index, sample_row in enumerate(sample_rows):
                sample = sample_row.get("sample") or {}
                sample_oracle = sample_row.get("oracle") or {}
                sample_request = sample.get("request")
                sample_result = sample.get("result")
                sample_controls = sample.get("controls") or {}
                sample_prefix = "变形状态 %d" % (index + 1)
                if sample_oracle.get("error"):
                    issues.append("%s独立复算失败：%s" % (sample_prefix, sample_oracle["error"]))
                    continue
                sample_expected = sample_oracle.get("result") or {}
                if not isinstance(sample_request, dict) or not isinstance(sample_result, dict):
                    issues.append("%s缺少请求或页面结果" % sample_prefix)
                    continue
                expected_indices = list(range(len(sample_request.get("initial_amounts_mol") or [])))
                if sample_controls.get("indices") != expected_indices:
                    issues.append("%s物质的量控件索引缺失、重复或顺序不完整" % sample_prefix)
                if not same_numeric_list(sample_controls.get("initial_amounts_mol"), sample_request.get("initial_amounts_mol")):
                    issues.append("%s物质的量控件与求解请求不一致" % sample_prefix)
                if not same_numeric(sample_controls.get("progress"), sample_request.get("progress", 1.0)):
                    issues.append("%s进度控件与求解请求不一致" % sample_prefix)
                for field in ("equation", "coefficients", "initial_amounts_mol", "progress",
                              "max_extent_mol", "extent_mol", "limiting_reactants",
                              "stoichiometric_mix", "reactants", "products",
                              "element_balance", "charge_balance", "checks"):
                    if not same_value(sample_result.get(field), sample_expected.get(field)):
                        issues.append("%s页面 %s 与独立复算不一致" % (sample_prefix, field))
                if normalize_equation(sample.get("displayed_equation")) != normalize_equation(sample_expected.get("equation", "")):
                    issues.append("%s页面实际方程式与求解结果不一致" % sample_prefix)
                if not (sample_result.get("checks") or {}).get("ok"):
                    issues.append("%s页面反应计量守恒校验未通过" % sample_prefix)
                samples_by_kind.setdefault(sample.get("kind"), []).append(sample)

            scaled_samples = samples_by_kind.get("common-scaling") or []
            if not scaled_samples:
                issues.append("页面没有用真实物质的量控件执行同比缩放变形")
            for sample in scaled_samples:
                sample_request, sample_result = sample.get("request") or {}, sample.get("result") or {}
                factor = sample.get("scale_factor")
                if not same_numeric(factor, factor) or same_numeric(factor, 1):
                    issues.append("同比缩放变形缺少有效比例")
                    continue
                expected_amounts = request.get("initial_amounts_mol") or []
                changed_amounts = sample_request.get("initial_amounts_mol") or []
                if len(expected_amounts) != len(changed_amounts) or any(
                        not same_numeric(changed, float(original) * float(factor))
                        for original, changed in zip(expected_amounts, changed_amounts)):
                    issues.append("同比缩放没有按同一比例改变全部反应物用量")
                if not same_value(sample_result.get("equation"), expected.get("equation")) or not same_value(
                        sample_result.get("coefficients"), expected.get("coefficients")):
                    issues.append("同比缩放后化学方程式或配平系数发生变化")
                if not same_numeric(sample_request.get("progress"), request.get("progress", 1.0)):
                    issues.append("同比缩放时反应进度发生了变化")
                if not same_value(sample_result.get("limiting_reactants"), expected.get("limiting_reactants")):
                    issues.append("同比缩放后限量试剂发生了变化")
                if not same_value(sample_result.get("stoichiometric_mix"), expected.get("stoichiometric_mix")):
                    issues.append("同比缩放后化学计量比状态发生了变化")
                for key in ("max_extent_mol", "extent_mol"):
                    if not same_numeric(sample_result.get(key), expected.get(key, 0) * factor):
                        issues.append("同比缩放后 %s 未按比例变化" % key)
                for side, amount_key in (("reactants", "consumed_mol"),
                                         ("reactants", "remaining_mol"),
                                         ("products", "produced_mol")):
                    base_rows = expected.get(side) or []
                    changed_rows = sample_result.get(side) or []
                    if len(base_rows) != len(changed_rows) or any(
                            not same_numeric(new.get(amount_key), old.get(amount_key, 0) * factor)
                            for old, new in zip(base_rows, changed_rows)):
                        issues.append("同比缩放后 %s.%s 未按比例变化" % (side, amount_key))

            progress_kinds = {"progress-zero", "progress-half", "progress-complete"}
            if not progress_kinds.issubset(samples_by_kind):
                issues.append("页面未通过真实进度控件覆盖反应进度 0、0.5、1")
            else:
                progress_samples = {kind: samples_by_kind[kind][0] for kind in progress_kinds}
                base_amounts_for_progress = request.get("initial_amounts_mol") or []
                for kind, progress_value in (("progress-zero", 0), ("progress-half", 0.5),
                                             ("progress-complete", 1)):
                    sample = progress_samples[kind]
                    sample_request, sample_result = sample.get("request") or {}, sample.get("result") or {}
                    if not same_numeric(sample_request.get("progress"), progress_value):
                        issues.append("进度变形 %s 的页面请求不是 %s" % (kind, progress_value))
                    if not same_numeric_list(sample_request.get("initial_amounts_mol"), base_amounts_for_progress):
                        issues.append("进度变形时反应物初始用量发生变化")
                    if not same_numeric(sample_result.get("extent_mol"),
                                        sample_result.get("max_extent_mol", 0) * progress_value):
                        issues.append("反应程度不等于最大反应程度乘反应进度")
                    if kind == "progress-zero":
                        if any(not same_numeric(row.get("consumed_mol"), 0)
                               for row in sample_result.get("reactants") or []) or any(
                                not same_numeric(row.get("produced_mol"), 0)
                                for row in sample_result.get("products") or []):
                            issues.append("反应进度为 0 时仍有反应物消耗或产物生成")
                half_result = progress_samples["progress-half"].get("result") or {}
                complete_result = progress_samples["progress-complete"].get("result") or {}
                complete_limiting = {row.get("index") for row in
                                     complete_result.get("limiting_reactants") or []}
                for row in complete_result.get("reactants") or []:
                    if row.get("index") in complete_limiting and not same_numeric(row.get("remaining_mol"), 0):
                        issues.append("完全反应时限量试剂没有恰好耗尽")
                for side, amount_key in (("reactants", "consumed_mol"), ("products", "produced_mol")):
                    half_rows = half_result.get(side) or []
                    complete_rows = complete_result.get(side) or []
                    if len(half_rows) != len(complete_rows) or any(
                            not same_numeric(half.get(amount_key), complete.get(amount_key, 0) * 0.5)
                            for half, complete in zip(half_rows, complete_rows)):
                        issues.append("反应进度 0.5 的 %s 未达到完全反应状态的一半" % amount_key)

            base_amounts = request.get("initial_amounts_mol") or []
            coefficients = (expected.get("coefficients") or {}).get("reactants") or []
            ranges = (controls or {}) if isinstance(controls, dict) else {}
            mins, maxs = ranges.get("amount_min") or [], ranges.get("amount_max") or []
            threshold_candidate = None
            if len(base_amounts) > 1 and len(coefficients) == len(base_amounts) and all(
                    same_numeric(value, value) and float(value) > 0 for value in base_amounts):
                for candidate_index, coefficient in enumerate(coefficients):
                    other_extent = min(float(value) / other_coefficient
                                       for other_index, (value, other_coefficient) in enumerate(zip(base_amounts, coefficients))
                                       if other_index != candidate_index)
                    threshold_value = other_extent * coefficient
                    delta = min(threshold_value * 0.02, threshold_value * 0.25)
                    min_value = float(mins[candidate_index]) if len(mins) == len(base_amounts) else 0.0
                    max_value = float(maxs[candidate_index]) if len(maxs) == len(base_amounts) else float("inf")
                    if threshold_value > 0 and threshold_value - delta >= min_value and threshold_value + delta <= max_value:
                        threshold_candidate = (candidate_index, threshold_value, delta, other_extent)
                        break
            if threshold_candidate:
                required_threshold_kinds = {"limiting-threshold-below", "limiting-threshold-at",
                                            "limiting-threshold-above"}
                observed_threshold_kinds = {kind for kind in required_threshold_kinds
                                            if samples_by_kind.get(kind)}
                if observed_threshold_kinds != required_threshold_kinds:
                    issues.append("页面没有通过真实控件覆盖限量试剂临界点下方/临界点/上方")
                else:
                    candidate_index, threshold_value, delta, other_extent = threshold_candidate
                    limiting_sets = {}
                    for kind in required_threshold_kinds:
                        sample = samples_by_kind[kind][0]
                        sample_request, sample_result = sample.get("request") or {}, sample.get("result") or {}
                        sample_index = sample.get("threshold_index")
                        sample_threshold = sample.get("threshold_mol")
                        values = sample_request.get("initial_amounts_mol") or []
                        if sample_index != candidate_index or not same_numeric(sample_threshold, threshold_value):
                            issues.append("限量试剂临界点变形使用了错误的目标物质或阈值")
                            continue
                        target_extent = float(values[candidate_index]) / coefficients[candidate_index]
                        tolerance = max(1e-12, abs(other_extent) * 1e-9)
                        if kind.endswith("below") and not target_extent < other_extent - tolerance:
                            issues.append("临界点下方没有让目标反应物成为限量试剂")
                        elif kind.endswith("at") and not math.isclose(target_extent, other_extent, rel_tol=1e-9, abs_tol=tolerance):
                            issues.append("临界点状态没有达到化学计量比")
                        elif kind.endswith("above") and not target_extent > other_extent + tolerance:
                            issues.append("临界点上方没有越过化学计量比")
                        limiting_sets[kind] = {item.get("index") for item in
                                               sample_result.get("limiting_reactants") or []}
                    if ("limiting-threshold-below" in limiting_sets and candidate_index not in
                            limiting_sets["limiting-threshold-below"]):
                        issues.append("临界点下方页面结果未将目标物质标为限量试剂")
                    if ("limiting-threshold-above" in limiting_sets and candidate_index in
                            limiting_sets["limiting-threshold-above"]):
                        issues.append("临界点上方页面结果仍将目标物质标为限量试剂")
        if issues:
            out.append(mk("J3", "J3-07", "限量试剂与反应计量独立复算", "fail",
                          "Python 参考实现与页面的反应进度、限量试剂、剩余量、生成量及守恒结果一致",
                          "；".join(issues), "页面反应计量结果未通过独立复算",
                          evidence="；".join(issues[:3]),
                          advice="用 CHEMSOLVER.solveStoichiometry 的同一结果驱动读数和演示；不要手算或缓存旧值",
                          severity="critical", weight=8))
        else:
            out.append(mk("J3", "J3-07", "限量试剂与反应计量独立复算", "pass",
                          "Python 参考实现与页面的反应进度、限量试剂、剩余量、生成量及守恒结果一致",
                          "页面读数、显示方程式和守恒量与独立复算一致",
                          "反应计量结果通过独立精确复算",
                          evidence=oracle["result"].get("equation", ""), weight=8))

    # J3-06: recompute chemical equation coefficients with the independent
    # Python reference solver, then compare against the browser solver result.
    topic_text = text + " " + str(ctx.get("topic") or "")
    balance_topic = (not precip_topic and not redox_topic and not ksp_topic and not gas_topic and not titration_topic and not stoich_topic and (isinstance(machine.get("CHEM_BALANCE_REQUEST"), dict) or
                     bool(re.search(r"化学方程式.{0,8}配平|方程式.{0,6}配平|配平.{0,12}(?:化学)?(?:方程式|反应)|原子守恒|置换反应|金属活动性|酸碱中和|中和反应|复分解反应|化合反应|分解反应|硫酸铜.{0,10}反应", topic_text))))
    if balance_topic:
        request = machine.get("CHEM_BALANCE_REQUEST")
        page_result = machine.get("CHEM_BALANCE_RESULT")
        oracle = ctx.get("chem_balance_oracle") or {}
        issues = []
        if not isinstance(request, dict) or not isinstance(page_result, dict):
            issues.append("缺少可复算的 CHEM_BALANCE_REQUEST / CHEM_BALANCE_RESULT")
        elif oracle.get("error"):
            issues.append("独立求解失败：%s" % oracle["error"])
        else:
            expected = oracle.get("result") or {}
            if page_result.get("coefficients") != expected.get("coefficients"):
                issues.append("页面系数与独立配平结果不一致（页面 %s / 复算 %s）" %
                              (page_result.get("coefficients"), expected.get("coefficients")))
            if page_result.get("equation") != expected.get("equation"):
                issues.append("页面展示方程式与独立配平结果不一致")
            normalize_equation = lambda value: re.sub(
                r"\s+", "", str(value).translate(str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")))
            if normalize_equation(machine.get("CHEM_BALANCE_DISPLAYED_EQUATION")) != normalize_equation(expected.get("equation")):
                issues.append("页面实际显示的方程式与独立配平结果不一致或缺少配平结果标记")
            if page_result.get("atom_counts") != expected.get("atom_counts"):
                issues.append("页面原子数与独立复算不一致")
            if page_result.get("charge_counts") != expected.get("charge_counts"):
                issues.append("页面电荷数与独立复算不一致")
            if not (page_result.get("checks") or {}).get("ok"):
                issues.append("页面求解器未报告原子数和电荷守恒全部通过")
            sample_rows = ctx.get("chem_balance_sample_oracles") or []
            required_kinds = {"uniform-formula-scaling", "unicode-subscript-equivalence", "species-reordering"}
            equation_activity = "方程式配平" in topic_text or "化学方程式配平" in topic_text
            if equation_activity:
                required_kinds.add("student-coefficients-common-scale")
            observed_kinds = set()
            for index, sample_row in enumerate(sample_rows):
                sample = sample_row.get("sample") or {}
                sample_expected = (sample_row.get("oracle") or {}).get("result") or {}
                kind = sample.get("kind")
                observed_kinds.add(kind)
                if (sample_row.get("oracle") or {}).get("error"):
                    issues.append("配平变形 %s 独立复算失败：%s" % (kind, sample_row["oracle"]["error"]))
                    continue
                if kind == "student-coefficients-common-scale":
                    if not same_value(sample.get("student_check"), sample_expected):
                        issues.append("学生系数共同倍乘后的页面校验与 Python 参考结果不一致")
                    if sample_expected.get("balanced") is not True or sample_expected.get("primitive") is not False:
                        issues.append("学生系数共同倍乘关系未得到‘仍配平但非最简’")
                    shown = sample.get("displayed_check") or {}
                    if str(shown.get("balanced", "")).lower() != "true" or str(shown.get("primitive", "")).lower() != "false":
                        issues.append("学生系数变形后的可见校验状态未同步")
                else:
                    sample_result = sample.get("result") or {}
                    for field in ("coefficients", "equation", "atom_counts", "charge_counts", "checks"):
                        if not same_value(sample_result.get(field), sample_expected.get(field)):
                            issues.append("配平变形 %s 的页面 %s 与 Python 参考结果不一致" % (kind, field))
                    if kind in ("uniform-formula-scaling", "unicode-subscript-equivalence"):
                        if not same_value(sample_result.get("coefficients"), expected.get("coefficients")):
                            issues.append("化学式表示变化后最简系数未保持不变")
                    elif kind == "species-reordering":
                        for side in ("reactants", "products"):
                            if sample_result.get("coefficients", {}).get(side) != list(reversed(expected.get("coefficients", {}).get(side, []))):
                                issues.append("物质顺序变化后 %s 系数没有按同样顺序重排" % side)
            missing_kinds = required_kinds - observed_kinds
            if missing_kinds:
                issues.append("浏览器未完成配平变形测试：%s" % "、".join(sorted(missing_kinds)))
        if issues:
            out.append(mk("J3", "J3-06", "化学方程式独立配平", "fail",
                          "页面结果与 Python 参考实现的最简系数、方程式和守恒数据一致",
                          "；".join(issues), "化学方程式未通过独立复算",
                          evidence="；".join(issues[:3]),
                          advice="用 CHEMSOLVER.balanceEquation 的同一返回对象驱动方程式、系数和守恒表；求解失败时显示错误状态",
                          severity="critical", weight=8))
        else:
            expected = oracle["result"]
            out.append(mk("J3", "J3-06", "化学方程式独立配平", "pass",
                          "页面结果与 Python 参考实现的最简系数、方程式和守恒数据一致",
                          "页面系数、原子数和电荷数与独立复算完全一致",
                          "化学方程式通过独立精确复算",
                          evidence=expected.get("equation", ""), weight=8))

    # J3-01 原子/元素计数守恒（化学）
    atoms = data.get("atoms") or data.get("原子数")
    if isinstance(atoms, dict) and atoms.get("left") and atoms.get("right"):
        checked += 1
        for el in set(atoms["left"]) | set(atoms["right"]):
            l, r = atoms["left"].get(el, 0), atoms["right"].get(el, 0)
            if l != r:
                fails.append("%s 原子不守恒（左 %s / 右 %s）" % (el, l, r))

    # J3-02 前后数量相等（颗粒、细胞数、样本数）
    counts = data.get("counts") or {}
    if isinstance(counts, dict) and "before" in counts and "after" in counts:
        checked += 1
        if counts["before"] != counts["after"]:
            fails.append("前后计数不等（%s → %s）" % (counts["before"], counts["after"]))

    # J3-03 概率/比例之和为 1（遗传棋盘、分布）
    probs = data.get("probabilities") or data.get("概率")
    if isinstance(probs, list) and probs:
        checked += 1
        s = sum(num_of(p) or 0 for p in probs)
        if not within(1.0, s, "统计"):
            fails.append("概率之和为 %.4f，应为 1" % s)

    # J3-04 遗传比例（1:2:1 / 3:1）
    ratio = data.get("ratio") or data.get("比例")
    if isinstance(ratio, (list, str)):
        checked += 1
        nums = [num_of(x) for x in (ratio if isinstance(ratio, list) else re.split(r"[:：]", ratio))]
        nums = [n for n in nums if n is not None]
        if len(nums) == 3:
            if not (within(1, nums[0], "计数") and within(2, nums[1], "计数") and within(1, nums[2], "计数")):
                fails.append("基因型比 %s 不是 1:2:1" % ratio)
        elif len(nums) == 2:
            if not (within(3, nums[0], "计数") and within(1, nums[1], "计数")):
                fails.append("表现型比 %s 不是 3:1" % ratio)

    # J3-05 页面自报的守恒布尔：独立性不足，只能转人工
    page_checks = data.get("checks") or {}
    if isinstance(page_checks, dict):
        self_reported = {k: v for k, v in page_checks.items() if "守恒" in str(k) or "相等" in str(k)}
        if self_reported:
            reviews.append("页面自报 %s；按规范 3.2，模型自报不作为独立校验证据"
                           % "、".join("%s=%s" % (k, v) for k, v in self_reported.items()))
            if any(v is False for v in self_reported.values()):
                fails.append("页面自报守恒不成立：%s"
                             % "、".join(k for k, v in self_reported.items() if v is False))

    if not checked and not reviews and not balance_topic and not redox_topic and not ksp_topic:
        out.append(mk("J3", "J3-01", "J3 计数与守恒", "skip",
                      "原子数/计数/概率前后一致", "未在 __DATA__ 中找到可计数的量",
                      "本页无计数类可复算量，J3 不适用", weight=6))
        return out

    if fails:
        out.append(mk("J3", "J3-01", "J3 计数与守恒", "fail",
                      "原子数/计数/概率前后一致", "；".join(fails),
                      "守恒关系不成立，或页面自报不成立",
                      evidence="；".join(fails[:3]), severity="critical",
                      advice="把反应物与产物的元素计数同时写出并逐元素比对，不要只显示总量",
                      weight=6))
    elif checked:
        out.append(mk("J3", "J3-01", "J3 计数与守恒", "pass",
                      "原子数/计数/概率前后一致", "%d 项守恒独立复算通过" % checked,
                      "守恒关系成立", weight=6))
    if reviews:
        out.append(mk("J3", "J3-02", "J3 自报结果需人工确认", "review",
                      "守恒结论应由外部独立复算，而非页面自报",
                      "；".join(reviews),
                      "页面自报的校验结果不能作为通过依据", weight=0))
    return out


# ================================================================ J4 空间拓扑

def j4_topology(ctx):
    out = []
    geo = _geo(ctx) or {}
    text = ctx.get("text") or ""
    checked, fails = 0, []

    # J4-01 体积可加（截面把体分成两块）
    v_up, v_down = num_of(geo.get("v_up")), num_of(geo.get("v_down"))
    total = num_of(geo.get("v_total") or geo.get("volume"))
    if v_up is not None and v_down is not None:
        checked += 1
        target = total if total is not None else 1.0
        if not within(target, v_up + v_down, "体积"):
            fails.append("两段体积之和 %.4f，应为 %.4f" % (v_up + v_down, target))
        if v_up < -1e-6 or v_down < -1e-6:
            fails.append("出现负体积（%.4f / %.4f）" % (v_up, v_down))

    # J4-02 截面边数合法性（正方体最多 6 边）
    #
    # 只有本页确实是「三维截面」页才校验 sides。函数页也常往 __GEO__ 里写
    # sides —— 二次函数页把它当成「与 x 轴交点个数」，合法值是 0/1/2，
    # 拿 3–6 去卡必然误杀，还会被判成 critical 直接禁止发布。
    # 所以这里要求 __GEO__ 里有真正的三维量才认 sides。
    sec_v = geo.get("section_vertices") or geo.get("vertices")
    is3d = bool(
        (isinstance(sec_v, list) and len(sec_v) >= 3)
        or (num_of(geo.get("v_up")) is not None
            and num_of(geo.get("v_down")) is not None)
        or None not in (geo.get("V"), geo.get("E"), geo.get("F"))
    )
    sides = geo.get("sides")
    if sides is not None and is3d:
        checked += 1
        n = int(num_of(sides) or 0)
        max_sides = 5 if geo.get("solid") in {"triangular_prism", "square_pyramid"} else 6
        degenerate = 0 <= n < 3 and num_of(geo.get("area_abs")) == 0 and len(sec_v or []) == n
        if not (degenerate or 3 <= n <= max_sides):
            fails.append("截面边数 %d 超出此立体的合法范围" % n)

    # J4-03 欧拉公式 V−E+F=2（仅连通、闭合、亏格 0 的多面体适用）
    V, E, F = geo.get("V"), geo.get("E"), geo.get("F")
    if None not in (V, E, F):
        checked += 1
        if int(V) - int(E) + int(F) != 2:
            fails.append("V−E+F=%d，不等于 2（曲面非凸或不闭合）" % (int(V) - int(E) + int(F)))

    # J4-04 截面顶点共面
    verts = geo.get("section_vertices") or geo.get("vertices")
    if isinstance(verts, list) and len(verts) >= 3:
        try:
            p = [[float(v["x"]), float(v["y"]), float(v["z"])] for v in verts[:6]]
            p0, p1, p2 = p[0], p[1], p[2]
            u = [p1[i] - p0[i] for i in range(3)]
            w = [p2[i] - p0[i] for i in range(3)]
            n = [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]]
            norm = math.sqrt(sum(x * x for x in n)) or 1
            checked += 1
            off = max(abs(sum(n[i] * (q[i] - p0[i]) for i in range(3))) / norm for q in p)
            if off > 1e-3:
                fails.append("截面顶点不共面（最大偏移 %.4f）" % off)
        except (KeyError, TypeError, ValueError):
            pass

    # J4-05 六边形截面的面积关系（a/√2 边长正六边形）
    area = num_of(geo.get("area"))
    if (geo.get("solid") in (None, "cube") and sides is not None and is3d
            and int(num_of(sides) or 0) == 6 and area is not None):
        checked += 1
        if not (0.5 < area < 2.0):
            fails.append("六边形截面面积 %.3f 超出单位立方体的合理范围" % area)

    if not checked:
        out.append(mk("J4", "J4-01", "J4 空间拓扑", "skip",
                      "三维面/边/顶点、截面、体积关系成立",
                      "未在 __GEO__ 中找到三维拓扑量",
                      "本页不是三维几何页，J4 不适用", weight=6))
        return out

    out.append(mk("J4", "J4-01", "J4 空间拓扑", "pass" if not fails else "fail",
                  "截点共面、截面闭合、体积可加",
                  "；".join(fails) if fails else "%d 项拓扑不变量成立" % checked,
                  "三维结构自相矛盾，画面可能看着正常但拓扑是错的" if fails else "拓扑关系自洽",
                  evidence="；".join(fails[:3]), severity="critical" if fails else "major",
                  advice="把截面顶点坐标与体积分量暴露到 __GEO__，由截平面与立方体求交得出，不要按边数硬编码图形",
                  weight=6))
    return out


# ================================================================ J5 序列与状态

def _bubble_ref(arr):
    """独立的参考实现：冒泡排序每一步的数组快照。"""
    a = list(arr)
    steps = [list(a)]
    n = len(a)
    for i in range(n):
        for j in range(n - 1 - i):
            if a[j] > a[j + 1]:
                a[j], a[j + 1] = a[j + 1], a[j]
                steps.append(list(a))
    return steps


def j5_sequence(ctx):
    out = []
    br = ctx.get("br") or {}
    data = (ctx.get("machine") or {}).get("DATA") or {}
    steps = br.get("steps") or {}
    checked, fails = 0, []

    # J5-01 单步不卡死：每次「下一步」后状态都应变化
    if steps.get("found"):
        checked += 1
        cnt, stuck = steps.get("count", 0), steps.get("stuck", 0)
        uniq = steps.get("unique", cnt)
        if stuck > 0:
            fails.append("连续 %d 次单步后状态没有变化（共 %d 步）" % (stuck, cnt))
        elif uniq < 2:
            fails.append("单步 %d 次只出现 1 个状态，过程没有真正推进" % cnt)

    # J5-02 与参考实现对拍（数组类算法）
    seq = data.get("steps") or data.get("history")
    if isinstance(seq, list) and len(seq) >= 2 and all(isinstance(x, list) for x in seq[:3]):
        checked += 1
        ref = _bubble_ref(seq[0])
        ok = len(seq) <= len(ref) and all(
            [num_of(v) for v in s] == [num_of(v) for v in ref[i]]
            for i, s in enumerate(seq) if i < len(ref)
        )
        final = [num_of(v) for v in seq[-1]]
        if not ok:
            fails.append("执行序列与参考冒泡排序不一致（第 %d 步起偏离）"
                         % next((i + 1 for i, s in enumerate(seq)
                                 if i < len(ref) and [num_of(v) for v in s] != [num_of(v) for v in ref[i]]), 0))
        if final != sorted(final):
            fails.append("终态未有序：%s" % final)

    # J5-03 阶段序号单调（细胞分裂、地理过程）
    stage = data.get("stage") or data.get("阶段")
    if isinstance(stage, (int, float)):
        checked += 1
        total = num_of(data.get("stageTotal") or data.get("总阶段"))
        if total and not (1 <= stage <= total):
            fails.append("当前阶段 %s 超出 1–%s" % (stage, total))

    if not checked:
        out.append(mk("J5", "J5-01", "J5 序列与状态", "skip",
                      "单步执行的状态序列与参考过程一致",
                      "页面没有单步按钮，也未暴露状态序列",
                      "本页无过程/序列类内容，J5 不适用", weight=6))
        return out

    out.append(mk("J5", "J5-01", "J5 序列与状态", "pass" if not fails else "fail",
                  "每一步只发生合法的状态迁移，末态正确",
                  "；".join(fails) if fails else "状态序列与参考过程一致",
                  "过程顺序或状态迁移有误，学生看到的是错误的过程" if fails else "过程可逐步复现",
                  evidence="；".join(fails[:3]), severity="critical" if fails else "major",
                  advice="用单一 state + 单步函数实现过程，每步只允许相邻阶段迁移，并把历史快照写进 __DATA__.steps",
                  weight=6))
    return out


# ================================================================ J6 结构要素齐备

def j6_structure(ctx):
    out = []
    text = ctx.get("text") or ""
    scene = ctx.get("scene") or {}
    required = scene.get("required") or []

    if scene:
        miss = [x for x in required if x not in text]
        # Circuit equipment can be rendered as symbols rather than Chinese
        # labels. Use the browser-captured netlist and meter bindings as
        # independent structural evidence for the required apparatus.
        br = ctx.get("br") or {}
        samples = ((br.get("circuit") or {}).get("samples") or [])
        sample_model = next((s.get("model") for s in samples if s.get("model")), {})
        components = sample_model.get("components") or []
        circuit_evidence = bool(components)
        if circuit_evidence and "电源" in miss and any(
                str(c.get("type", "")).lower() in ("voltage_source", "voltagesource")
                for c in components):
            miss.remove("电源")
        readings = next((s.get("readings") or [] for s in samples if s.get("readings")), [])
        if circuit_evidence and "电流表" in miss and any(r.get("kind") == "current" and r.get("bound") for r in readings):
            miss.remove("电流表")
        if circuit_evidence and "电压表" in miss and any(r.get("kind") == "voltage" and r.get("bound") for r in readings):
            miss.remove("电压表")
        # A circuit is a core experimental structure: missing required parts
        # must block the overall verdict instead of being outweighed by score.
        out.append(mk("J6", "J6-01", "J6 强制要素齐备", "pass" if not miss else "fail",
                      "场景「%s」必须具备：%s" % (scene.get("name", ""), "、".join(required)),
                      "缺失：%s" % "、".join(miss) if miss else "要素齐全",
                      "装置/器材/标注缺失，实验无法成立" if miss else "强制要素完整",
                      evidence=scene.get("name", ""),
                      advice="按场景注册表的 required 清单补齐器材与标注，并确保名称与教材一致",
                      severity="critical", weight=5))
    else:
        # 没有注册场景就没有"强制清单"，不能凭空判合格
        hits = [w for w in ("单位", "图例", "刻度", "标注", "坐标轴") if w in text]
        out.append(mk("J6", "J6-01", "J6 强制要素齐备", "review",
                      "按已审核场景注册表核对器材/标注/图例",
                      "场景未注册，仅命中通用标注 %d 项（%s）" % (len(hits), "、".join(hits) or "无"),
                      "缺少场景注册表就无法确定「该有哪些器材」，此项交教师确认",
                      advice="在 registry.SCENES 里登记该场景及 required 清单，或先在知识库完成场景审核",
                      weight=5))
    return out


# ================================================================ J7 统计复算

def _table_series(tables):
    """从表格里抽数值列，返回 {列名: [值...]}。"""
    series = {}
    for tb in tables or []:
        if len(tb) < 3:
            continue
        header = tb[0]
        for ci in range(len(header)):
            vals = []
            for row in tb[1:]:
                if ci < len(row):
                    v = num_of(row[ci])
                    if v is not None:
                        vals.append(v)
            if len(vals) >= 3:
                series[header[ci] or ("列%d" % (ci + 1))] = vals
    return series


def j7_statistics(ctx):
    out = []
    br = ctx.get("br") or {}
    data = (ctx.get("machine") or {}).get("DATA") or {}
    text = ctx.get("text") or ""
    checked, fails, notes = 0, [], []

    series = _table_series(br.get("tables"))
    # J7-01 表格均值核对：必须"列名 + 平均"对得上，不能拿电压列去比电流的均值
    wants_mean = any(k in text for k in ("平均", "均值"))
    if series and wants_mean:
        for name, vals in list(series.items())[:3]:
            mean = sum(vals) / len(vals)
            core = re.sub(r"[（(].*?[)）]", "", str(name))
            core = re.sub(r"[A-Za-zμΩ°%³²·/\s]", "", core)   # 去掉单位与字母，只留中文列名
            shown = []
            if core:
                shown += re.findall(r"平均[^0-9]{0,10}%s[^0-9]{0,6}(\d+(?:\.\d+)?)" % re.escape(core), text)
                shown += re.findall(r"%s[^0-9]{0,10}平均[^0-9]{0,6}(\d+(?:\.\d+)?)" % re.escape(core), text)
            if not shown:
                notes.append("表格「%s」有 %d 个数据，未见对应的平均值" % (name, len(vals)))
                continue
            checked += 1
            if not any(within(mean, float(s), "统计") for s in shown):
                fails.append("「%s」均值应为 %.3f，页面显示 %s" % (name, mean, "、".join(shown[:2])))

    # J7-02 页面自报的统计量与样本复算
    result = data.get("result") or {}
    sample = data.get("samples") or data.get("series")
    if isinstance(sample, list) and len(sample) >= 3:
        vals = [num_of(v) for v in sample if num_of(v) is not None]
        if vals:
            mean = sum(vals) / len(vals)
            var = sum((v - mean) ** 2 for v in vals) / len(vals)
            for key, expect in (("均值", mean), ("平均", mean), ("方差", var)):
                if key in result:
                    checked += 1
                    if not within(expect, num_of(result[key]), "统计"):
                        fails.append("%s 显示 %s，独立复算 %.3f" % (key, result[key], expect))

    if not checked:
        out.append(mk("J7", "J7-01", "J7 统计复算", "skip",
                      "均值/方差/斜率等统计量可由样本独立复算",
                      "页面没有统计量或样本少于 3 组",
                      "本页无统计内容，J7 不适用", weight=5))
        return out

    if fails:
        out.append(mk("J7", "J7-01", "J7 统计复算", "fail",
                      "统计量与样本独立复算一致", "；".join(fails),
                      "统计结果与数据不符，图表和数字会互相矛盾",
                      evidence="；".join(fails[:3]), severity="major",
                      advice="所有统计量在同一处由样本数组算出，图表与表格共用同一份数据",
                      weight=5))
    else:
        msg = "%d 项统计量复算通过" % checked
        if notes:
            msg += "；" + "；".join(notes[:2])
        out.append(mk("J7", "J7-01", "J7 统计复算", "pass",
                      "统计量与样本独立复算一致", msg, "统计量自洽", weight=5))
    return out


# ================================================================ J8 答案表比对

def _match_facts(facts, subject, text):
    matched = []
    for f in facts:
        if subject and f.get("学科") != subject:
            continue
        keys = [k for k in (f.get("主题") or []) if k in text]
        if len(keys) >= 2:
            matched.append((f, keys))
    return matched


def j8_facts(ctx):
    out = []
    text = ctx.get("text") or ""
    subject = ctx.get("subject") or ""
    facts = ctx.get("facts") or []
    scene = ctx.get("scene") or {}

    matched = _match_facts(facts, subject, text)
    # 场景绑定的事实优先
    if scene.get("facts"):
        ids = set(scene["facts"])
        matched = [(f, k) for f, k in matched if f.get("id") in ids] or matched

    if not matched:
        out.append(mk("J8", "J8-01", "J8 答案表比对", "review",
                      "与教师审核过的事实表比对现象与结论",
                      "本页主题未命中事实表（现有 %d 条已审核事实）" % len(facts),
                      "缺少可比对的事实条目，不能断定科学结论正确",
                      advice="在 facts.json 中补充该主题的事实条目（现象、必须出现、禁止出现的错误表述）",
                      weight=6))
        return out

    fails, passes, reviews = [], [], []
    for f, keys in matched:
        fid = f.get("id", "")
        reviewed = f.get("审核状态") == "教研复核通过"
        for bad in f.get("禁止出现") or []:
            if bad in text:
                fails.append("[%s] 出现错误表述「%s」（事实：%s）" % (fid, bad, f.get("事实", "")))
        for must in f.get("必须出现") or []:
            if must not in text:
                fails.append("[%s] 缺少必要表述「%s」" % (fid, must))
        any_of = f.get("至少出现") or []
        if any_of and not any(x in text for x in any_of):
            fails.append("[%s] 未出现关键现象/结论（应含其一：%s）" % (fid, "、".join(any_of)))
        if not reviewed:
            reviews.append("[%s] 事实表条目尚未通过教研复核" % fid)
        elif not fails:
            passes.append("[%s] 命中：%s" % (fid, "、".join(keys)))

    if fails:
        out.append(mk("J8", "J8-01", "J8 答案表比对", "fail",
                      "页面表述与已审核事实表一致",
                      "；".join(fails[:3]),
                      "页面出现与教材事实相反的表述，属于科学性错误",
                      evidence="；".join(fails[:3]), severity="critical",
                      advice="对照 facts.json 的『禁止出现』逐条改写；不确定的现象宁可不写，也不要编造",
                      weight=6))
    elif passes:
        out.append(mk("J8", "J8-01", "J8 答案表比对", "pass",
                      "页面表述与已审核事实表一致",
                      "；".join(passes[:3]),
                      "关键现象与结论与审核事实一致", weight=6))
    if reviews:
        out.append(mk("J8", "J8-02", "J8 事实条目待复核", "review",
                      "所引用事实条目应已通过教研复核",
                      "；".join(reviews), "事实条目未复核，暂不计入通过", weight=0))
    return out


# ================================================================ 调度

JUDGE_FUNCS = {
    "J1": j1_numeric,
    "J2": j2_geometry,
    "J3": j3_conservation,
    "J4": j4_topology,
    "J5": j5_sequence,
    "J6": j6_structure,
    "J7": j7_statistics,
    "J8": j8_facts,
}


def run(judges, ctx):
    """按学科配置的判据顺序执行。J0 的开放任务直接转人工。"""
    out = []
    for j in judges:
        fn = JUDGE_FUNCS.get(j)
        if fn:
            out.extend(fn(ctx))
        elif j == "J0":
            out.append(mk("J0", "J0-01", "J0 开放任务", "review",
                          "有客观可复算标准的任务才进入自动判分",
                          "本任务无客观标准", "开放任务需教师判断，不伪造机器判分", weight=0))
    return out
