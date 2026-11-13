# -*- coding: utf-8 -*-
"""mr_engine.py —— 变形测试引擎（关系级判定 + 计划执行 + 覆盖统计）

它解决的问题
------------
旧版审查能证明“拖了滑块，值变了”，但证明不了“按什么规律变”：
    · 页面把电流写死成 1 A，只要标签跟着动，也能通过“响应性”检查；
    · 电路页每个状态都用 Python 复算，但电压翻倍→电流翻倍这条关系没有被显式断言；
    · 变形测试散落在 if 分支里，新增主题没有可复用的入口；
    · 容差要么按 1e-9 比显示值，要么按 2% 比状态量，两边混用。

这一层的四件事
--------------
1. 关系判定：proportional / inverse / const / equal / change / formula。
2. 容差分级：状态量按相对误差；页面读数按文本显示位数反推。
3. 计划执行：reviewer 生成计划，checks_browser.js 按计划设置控件并在两个状态各采一次快照。
4. 证据输出：每条关系一行 expected / actual / evidence / advice，直接进审查报告。

约定
----
快照结构（由 checks_browser.js 产生）：
    {
      "controls": {"voltage": 3, "resistance": 10},
      "readouts": {"circuit:current": {"text": "0.30", "value": 0.3}},
      "globals": {"__CIRCUIT_MODEL__": {...}, "__CIRCUIT_RESULT__": {...}}
    }

读数键：
    control:<name>     控件当前值
    circuit:current    电流表读数（data-circuit-current-for）
    circuit:voltage    电压表读数（data-circuit-voltage-for）
    field:<name>       data-solver-field 读数
    label:<文字>        .exp-read 的“标签 → 值”
    global:<path>      机读全局量里的路径
"""

import argparse
import copy
import json
import math
import re

from mr_catalog import KINDS, PAGE_PLANS

# 状态量（求解结果、__GEO__）和页面读数用两套容差，不能混用。
STATE_REL_TOL = 1e-6
DISPLAY_REL_TOL = 0.02
DISPLAY_ABS_TOL = 0.005
EPS = 1e-12


# --------------------------------------------------------------------------- 基础

def _number(value):
    """把页面文本、JSON 数值统一成有限 float；空值/占位符返回 None。"""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        value = float(value)
        return value if math.isfinite(value) else None
    if isinstance(value, str):
        text = value.strip().replace("−", "-").replace(",", "")
        if not text or text in {"—", "-", "–", "无", "null", "None"}:
            return None
        try:
            value = float(text)
        except ValueError:
            return None
        return value if math.isfinite(value) else None
    return None


def close(left, right, rel=STATE_REL_TOL, abs_tol=EPS):
    if left is None or right is None:
        return False
    return abs(left - right) <= max(abs_tol, rel * max(abs(left), abs(right)))


def display_tolerance(text, value=None):
    """从读数文本的显示位数反推容差。

    “0.30” 的最后一位是 0.01，允许半个单位（0.005）再留 1% 余量；
    这样既不会把四舍五入判成错，也不会让 1 mA 的量级用 5 mA 的绝对容差蒙混过关。
    """
    text = (text or "").strip()
    match = re.search(r"\d+\.(\d+)", text)
    if match:
        absolute = 0.5 * (10 ** -len(match.group(1))) * 1.01
        return max(absolute, abs(value or 0.0) * 1e-6)
    if re.fullmatch(r"[-−]?\d+", text):
        return 0.51
    return DISPLAY_ABS_TOL


def path_get(obj, path):
    """支持 a.b.0.c / a.b[0].c 两种路径写法。"""
    current = obj
    for part in str(path or "").replace("[", ".").replace("]", "").split("."):
        if not part:
            continue
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list) and part.lstrip("-").isdigit():
            index = int(part)
            current = current[index] if -len(current) <= index < len(current) else None
        else:
            return None
        if current is None:
            return None
    return current


def _readout_entry(snapshot, key):
    snapshot = snapshot or {}
    key = str(key or "")
    if key.startswith("control:"):
        value = _number((snapshot.get("controls") or {}).get(key.split(":", 1)[1]))
        return {"value": value, "text": "" if value is None else str(value)}
    if key.startswith("global:"):
        value = _number(path_get(snapshot.get("globals") or {}, key.split(":", 1)[1]))
        return {"value": value, "text": "" if value is None else str(value)}
    entry = (snapshot.get("readouts") or {}).get(key)
    if isinstance(entry, dict):
        return {"value": _number(entry.get("value")), "text": str(entry.get("text") or "")}
    value = _number(entry)
    return {"value": value, "text": "" if value is None else str(entry)}


def _readout(snapshot, key):
    return _readout_entry(snapshot, key)["value"]


def _tolerance(scene, snapshot, key):
    cfg = (scene or {}).get("tolerance") or {}
    rel = float(cfg.get("rel", DISPLAY_REL_TOL))
    absolute = float(cfg.get("abs", DISPLAY_ABS_TOL))
    entry = _readout_entry(snapshot, key)
    if entry["text"]:
        absolute = max(absolute, display_tolerance(entry["text"], entry["value"]))
    return rel, absolute


def _globals(snapshot, scene):
    values = (snapshot or {}).get("globals") or {}
    names = (scene or {}).get("globals") or {}
    if names.get("request") or names.get("result"):
        # 计划显式点名了全局量：只认这一组，避免页面上多个求解器互相串味。
        request = values.get(names.get("request")) if names.get("request") else None
        result = values.get(names.get("result")) if names.get("result") else None
        return request if isinstance(request, dict) else None, result if isinstance(result, dict) else {}
    # 兼容：计划没写名字时，自动找第一组 __*_REQUEST__/__*_RESULT__。
    for key in values:
        if key.endswith("_REQUEST__"):
            request = values[key]
            result = values.get(key.replace("_REQUEST__", "_RESULT__"))
            return request if isinstance(request, dict) else None, result if isinstance(result, dict) else {}
    return None, {}


# --------------------------------------------------------------------------- 行

def _row(mr_id, title, kind, status, expected, actual, evidence="", advice="", solver="", source="plan"):
    return {
        "id": mr_id, "title": title, "kind": kind, "status": status,
        "expected": expected, "actual": actual, "evidence": evidence,
        "advice": advice, "solver": solver, "source": source,
    }


def _fmt(value, digits=6):
    if value is None:
        return "—"
    if isinstance(value, float):
        return ("%." + str(digits) + "g") % value
    return str(value)


# --------------------------------------------------------------------------- 跨状态关系

def _cross_relation(scene, a, b):
    """返回 (ok, expected, actual, detail)。a/b 是 baseline/transformed 两个快照。"""
    relation = scene.get("relation") or {}
    op = relation.get("op")
    y_key = relation.get("y")
    y1_entry = _readout_entry(a, y_key)
    y2_entry = _readout_entry(b, y_key)
    if y1_entry["value"] is None or y2_entry["value"] is None:
        return False, "读数 %s 有数值" % y_key, "读数为空", "缺少可比较的读数"

    rel, abs_tol = _tolerance(scene, b, y_key)
    y1, y2 = y1_entry["value"], y2_entry["value"]

    if op == "const":
        target = _number(relation.get("value", 0)) or 0.0
        ok = abs(y2 - target) <= max(abs_tol, rel * abs(target))
        return ok, "%s = %s" % (y_key, _fmt(target)), "%s = %s" % (y_key, _fmt(y2)), \
            "变换后应回到 %s" % _fmt(target)

    if op == "equal":
        ok = close(y2, y1, rel, abs_tol)
        return ok, "%s 保持 %s" % (y_key, _fmt(y1)), "%s = %s" % (y_key, _fmt(y2)), "变换不应改变该量"

    if op == "change":
        ok = not close(y2, y1, rel, abs_tol)
        return ok, "%s 发生变化" % y_key, "%s: %s → %s" % (y_key, _fmt(y1), _fmt(y2)), "输入变了，读数必须跟着变"

    x_key = relation.get("x")
    x1, x2 = _readout(a, x_key), _readout(b, x_key)
    if x1 is None or x2 is None:
        return False, "控件 %s 有数值" % x_key, "控件读数为空", "缺少可比较的控件值"
    if abs(x1) <= EPS or abs(y1) <= EPS:
        return False, "基线不为 0（否则比例无定义）", "x1=%s, y1=%s" % (_fmt(x1), _fmt(y1)), \
            "请把基线设成非零值"

    if op == "proportional":
        expected_ratio = x2 / x1
        actual_ratio = y2 / y1
        deviation = actual_ratio / expected_ratio if expected_ratio else float("inf")
        ok = abs(deviation - 1.0) <= rel
        return ok, "y2/y1 = x2/x1 = %s" % _fmt(expected_ratio), \
            "y2/y1 = %s（x2/x1 = %s）" % (_fmt(actual_ratio), _fmt(expected_ratio)), \
            "实际比例偏离期望 %s" % _fmt(deviation)

    if op == "inverse":
        expected_ratio = x1 / x2 if abs(x2) > EPS else float("inf")
        actual_ratio = y2 / y1
        deviation = actual_ratio / expected_ratio if expected_ratio else float("inf")
        ok = abs(deviation - 1.0) <= rel
        return ok, "y2/y1 = x1/x2 = %s" % _fmt(expected_ratio), \
            "y2/y1 = %s（x1/x2 = %s）" % (_fmt(actual_ratio), _fmt(expected_ratio)), \
            "实际比例偏离期望 %s" % _fmt(deviation)

    if op == "ratio":
        target = _number(relation.get("value"))
        if target is None:
            return False, "ratio 需要 value", "缺少 value", "目录配置错误"
        actual = y2 / y1 if abs(y1) > EPS else float("inf")
        ok = abs(actual - target) <= rel
        return ok, "y2/y1 = %s" % _fmt(target), "y2/y1 = %s" % _fmt(actual), "比例不符合期望"

    return False, "已知的关系类型", "未知关系 %s" % op, "检查 mr_catalog.py"


# --------------------------------------------------------------------------- 单状态公式

def _lens_formula(request, result):
    u, f = _number(request.get("u")), _number(request.get("f"))
    v = _number(result.get("image_distance_cm"))
    if u is None or f is None or abs(f) <= EPS:
        return False, "请求包含有效 u/f", "u=%s f=%s" % (_fmt(u), _fmt(f)), "求解请求不完整"
    if abs(u - f) <= 1e-9:
        ok = v is None
        return ok, "u=f 时无有限像（像距为空）", "像距 %s" % _fmt(v), "u=f 是临界状态，不能给出有限像距"
    if v is None or abs(v) <= EPS:
        return False, "u≠f 时像距非空", "像距 %s" % _fmt(v), "求解结果缺少像距"
    lhs, rhs = 1.0 / f, 1.0 / u + 1.0 / v
    ok = close(lhs, rhs, rel=1e-3)
    return ok, "1/f = 1/u + 1/v", "1/f=%s, 1/u+1/v=%s" % (_fmt(lhs), _fmt(rhs)), "高斯成像公式不闭合"


def _lens_magnification(request, result):
    u = _number(request.get("u"))
    v = _number(result.get("image_distance_cm"))
    m = _number(result.get("magnification"))
    if u is None or v is None or m is None:
        return False, "u、v、m 都有数值", "u=%s v=%s m=%s" % (_fmt(u), _fmt(v), _fmt(m)), "缺少放大率或像距"
    expected = -v / u
    ok = close(m, expected, rel=1e-3, abs_tol=1e-6)
    return ok, "m = -v/u = %s" % _fmt(expected), "m = %s" % _fmt(m), "放大率与像距/物距不一致"


def _mirror_distance(request, result):
    distance = _number(result.get("object_distance"))
    image = _number(result.get("image_distance"))
    if distance is None or image is None:
        return False, "物距与像距都有数值", "物距=%s 像距=%s" % (_fmt(distance), _fmt(image)), "求解结果缺少像距"
    ok = close(image, distance, rel=1e-9, abs_tol=1e-9)
    return ok, "像距 = 物距 = %s" % _fmt(distance), "像距 = %s" % _fmt(image), "平面镜成像的像距不等于物距"


def _mirror_magnification(request, result):
    m = _number(result.get("magnification"))
    if m is None:
        return False, "放大率为 1", "放大率为空", "求解结果缺少放大率"
    ok = close(m, 1.0, rel=1e-9, abs_tol=1e-9)
    return ok, "放大率 = 1", "放大率 = %s" % _fmt(m), "平面镜成正立等大虚像"


def _wave_speed(request, result):
    distance = _number(request.get("detector_distance"))
    travel = _number(request.get("travel_time"))
    speed = _number(result.get("speed"))
    if distance is None or travel is None or abs(travel) <= EPS or speed is None:
        return False, "v = 距离 / 传播耗时", "距离=%s 耗时=%s 声速=%s" % (_fmt(distance), _fmt(travel), _fmt(speed)), \
            "缺少距离、耗时或声速"
    expected = distance / travel
    ok = close(speed, expected, rel=1e-6)
    return ok, "v = %s / %s = %s" % (_fmt(distance), _fmt(travel), _fmt(expected)), "v = %s" % _fmt(speed), \
        "声速不等于距离除以传播耗时"


def _wave_wavelength(request, result):
    frequency = _number(request.get("frequency"))
    speed = _number(result.get("speed"))
    wavelength = _number(result.get("wavelength"))
    if frequency is None or abs(frequency) <= EPS or speed is None or wavelength is None:
        return False, "λ = v / f", "f=%s v=%s λ=%s" % (_fmt(frequency), _fmt(speed), _fmt(wavelength)), \
            "缺少频率、声速或波长"
    expected = speed / frequency
    ok = close(wavelength, expected, rel=1e-6)
    return ok, "λ = %s / %s = %s" % (_fmt(speed), _fmt(frequency), _fmt(expected)), \
        "λ = %s" % _fmt(wavelength), "波长不等于声速除以频率"


def _readout_matches(check, snapshot, scene):
    key = check.get("readout")
    path = check.get("path")
    entry = _readout_entry(snapshot, key)
    if entry["value"] is None:
        return False, "读数 %s 有数值" % key, "读数为空", "页面没有渲染该读数"
    request, result = _globals(snapshot, scene)
    expected = _number(path_get(result, path))
    if expected is None:
        return False, "求解结果包含 %s" % path, "结果缺少 %s" % path, "读数与求解结果不是同一来源"
    tolerance = max(display_tolerance(entry["text"], entry["value"]), abs(expected) * 1e-6)
    ok = abs(entry["value"] - expected) <= tolerance
    return ok, "%s = %s" % (key, _fmt(expected)), "%s = %s" % (key, _fmt(entry["value"])), \
        "读数与 result.%s 不一致，可能是页面另算了一套" % path


_STATE_CHECKS = {
    "lens_formula": _lens_formula,
    "lens_magnification": _lens_magnification,
    "mirror_image_distance": _mirror_distance,
    "mirror_magnification": _mirror_magnification,
    "wave_speed": _wave_speed,
    "wave_wavelength": _wave_wavelength,
    "readout_matches": _readout_matches,
}


def _state_check(check, snapshot, scene):
    name = check.get("op")
    handler = _STATE_CHECKS.get(name)
    if not handler:
        return False, "已知的单状态公式", "未知公式 %s" % name, "检查 mr_catalog.py"
    if name == "readout_matches":
        # 读数一致性检查需要 check（读数键/路径）和 scene（全局量名字），
        # 与“请求+结果”的公式检查签名不同。
        return _readout_matches(check, snapshot, scene)
    request, result = _globals(snapshot, scene)
    if request is None:
        return False, "页面暴露 %s" % ((scene.get("globals") or {}).get("request") or "求解请求"), \
            "未找到求解请求", "页面必须在每次 render 时写入 __*_REQUEST__"
    return handler(request, result)


# --------------------------------------------------------------------------- 计划执行

def _precondition_failure(scene, snapshot):
    """关系适用条件不满足时返回原因；满足或无法判断时返回空串。

    典型例子：I∝1/R 只对“单一被测电阻”成立。串联了滑动变阻器后，
    总电阻是 R+R滑，R 翻倍不会让电流减半。这时应记 skip 并说明原因，
    而不是把正确的页面判成失败。
    """
    condition = (scene or {}).get("precondition") or {}
    limit = condition.get("circuit_resistors")
    if limit is None:
        return ""
    model = (snapshot.get("globals") or {}).get("__CIRCUIT_MODEL__")
    if not isinstance(model, dict):
        return ""
    count = 0
    for component in model.get("components") or []:
        if not isinstance(component, dict):
            continue
        if str(component.get("type", "")).lower().replace("-", "_") != "resistor":
            continue
        ohms = _number(component.get("ohms"))
        if ohms is not None and ohms > 0.01:
            count += 1
    if count > int(limit):
        return "页面含 %d 个有效电阻，超过该关系适用的 %d 个" % (count, int(limit))
    return ""


def evaluate_plan(plan, payload):
    """把浏览器按计划采到的快照变成一行行可读的关系判定。"""
    rows = []
    if not plan:
        return rows
    executed = {}
    for sample in (((payload or {}).get("mr") or {}).get("scenes") or []):
        if isinstance(sample, dict) and sample.get("id"):
            executed[sample["id"]] = sample
    solver = plan.get("solver") or ""
    for scene in plan.get("scenes") or []:
        mr_id = scene.get("id")
        title = scene.get("title") or mr_id
        kind = scene.get("kind") or "formula"
        sample = executed.get(mr_id)
        if not sample:
            status = "skip" if scene.get("optional") else "fail"
            rows.append(_row(mr_id, title, kind, status,
                             "浏览器执行该变形状态", "未执行",
                             advice=scene.get("advice", ""), solver=solver))
            continue
        errors = [str(item) for item in (sample.get("errors") or []) if item]
        a, b = sample.get("a") or {}, sample.get("b") or {}
        blocked = _precondition_failure(scene, a)
        if blocked:
            rows.append(_row(mr_id, title, kind, "skip",
                             "适用条件：%s" % scene.get("precondition"),
                             blocked, advice=scene.get("advice", ""), solver=solver))
            continue
        details = []
        failures = 0
        fail_details = []
        state_checks = scene.get("state_checks") or []

        relation = scene.get("relation")
        if relation:
            ok, expected, actual, detail = _cross_relation(scene, a, b)
            details.append("%s：%s%s" % ("通过" if ok else "失败", actual,
                                        "" if ok else "（%s）" % detail))
            if not ok:
                failures += 1
                fail_details.append(actual)
            expected_text = expected
            actual_text = actual
        else:
            expected_text, actual_text = "每个状态满足声明的公式", ""

        first_expected = ""
        for check in state_checks:
            for label, snapshot in (("基线", a), ("变换", b)):
                ok, expected, actual, detail = _state_check(check, snapshot, scene)
                first_expected = first_expected or expected
                details.append("%s %s：%s%s" % (label, "通过" if ok else "失败", actual,
                                               "" if ok else "（%s）" % detail))
                if not ok:
                    failures += 1
                    fail_details.append("%s %s：%s" % (label, check.get("op"), actual))
        if state_checks:
            if fail_details:
                actual_text = "；".join(fail_details[:4])
            else:
                actual_text = "两个状态均满足 %d 项公式" % len(state_checks)
        if not relation and first_expected:
            expected_text = first_expected

        if errors:
            failures += 1
            details.append("控件执行失败：" + "；".join(errors[:3]))

        if not scene.get("relation") and not scene.get("state_checks"):
            failures += 1
            details.append("场景既没有跨状态关系也没有单状态公式")

        missing_names = {item.split("：")[-1] for item in errors}
        if failures and scene.get("optional") and missing_names and len(missing_names) >= len(scene.get("controls") or {}):
            status = "skip"
            actual_text = "缺少控件：%s（可选关系，已跳过）" % "、".join(sorted(missing_names))
        else:
            status = "pass" if failures == 0 else "fail"
        rows.append(_row(mr_id, title, kind, status,
                         expected_text or "满足声明的变形关系",
                         actual_text or ("；".join(details[:4]) if status != "pass" else "两个状态均满足"),
                         evidence="；".join(details), advice=scene.get("advice", ""), solver=solver))
    return rows


# --------------------------------------------------------------------------- 电路样本关系（不依赖计划）

def _circuit_diff(left, right):
    """只比较“元件参数”变化；拓扑/元件集合变化不算可解释变形。"""
    if not isinstance(left, dict) or not isinstance(right, dict):
        return None
    a = {str(c.get("id")): c for c in left.get("components") or [] if isinstance(c, dict)}
    b = {str(c.get("id")): c for c in right.get("components") or [] if isinstance(c, dict)}
    if set(a) != set(b):
        return None
    changes = []
    for cid in a:
        first, second = a[cid], b[cid]
        if (str(first.get("type", "")).lower().replace("-", "_") !=
                str(second.get("type", "")).lower().replace("-", "_")):
            return None
        for key in ("from", "to", "positive", "negative"):
            if first.get(key) != second.get(key):
                return None
        for key in ("volts", "ohms", "amps", "closed"):
            if key in first or key in second:
                if first.get(key) != second.get(key):
                    changes.append((cid, key, first.get(key), second.get(key)))
    return changes


def _circuit_branch(model):
    components = (model or {}).get("components") or []
    for component in components:
        kind = str(component.get("type", "")).lower().replace("-", "_")
        if kind == "ammeter":
            return str(component.get("id"))
    return None


def circuit_sample_rows(payload):
    """从已有采样里推导电路关系：U×k→I×k、R×k→I÷k、断开关→0。"""
    samples = ((payload or {}).get("circuit") or {}).get("samples") or []
    if len(samples) < 2:
        return []
    baseline = samples[0]
    base_model = baseline.get("model") or {}
    base_result = baseline.get("result") or {}
    base_branches = base_result.get("branches") or {}
    branch_id = _circuit_branch(base_model)
    if branch_id is None:
        # 没有电流表就退而求其次：取基线下电流绝对值最大的支路。
        candidates = [(abs(_number(item.get("current")) or 0), key)
                      for key, item in base_branches.items() if isinstance(item, dict)]
        if not candidates:
            return []
        branch_id = max(candidates)[1]
    y1 = _number((base_branches.get(branch_id) or {}).get("current"))
    if y1 is None:
        return []
    rows, seen = [], set()
    for sample in samples[1:]:
        changes = _circuit_diff(base_model, sample.get("model"))
        if not changes or len(changes) != 1:
            continue
        cid, field, old, new = changes[0]
        branches = (sample.get("result") or {}).get("branches") or {}
        y2 = _number((branches.get(branch_id) or {}).get("current"))
        if y2 is None:
            continue
        source = "samples"
        if field == "closed":
            if bool(new):
                continue
            key = ("boundary", cid)
            if key in seen:
                continue
            seen.add(key)
            ok = abs(y2) <= DISPLAY_ABS_TOL
            rows.append(_row("circuit.sample.open.%s" % cid, "断开开关后电流为 0",
                             "boundary", "pass" if ok else "fail",
                             "开关断开 → I = 0", "I = %s" % _fmt(y2),
                             evidence="开关 id=%s" % cid,
                             advice="断开状态必须进入求解模型；电流表应显示 0，而不是停在旧值",
                             solver="CIRCUIT.solve", source=source))
            continue
        old_value, new_value = _number(old), _number(new)
        if old_value is None or new_value is None or abs(old_value) <= EPS:
            continue
        if field == "volts":
            key = ("linearity", cid)
            if key in seen:
                continue
            seen.add(key)
            ratio = new_value / old_value
            actual = y2 / y1
            ok = close(actual, ratio, rel=DISPLAY_REL_TOL, abs_tol=DISPLAY_ABS_TOL)
            rows.append(_row("circuit.sample.voltage.%s" % cid, "电压变化后电流按比例变化",
                             "linearity", "pass" if ok else "fail",
                             "%s 电压 ×%s → 电流 ×%s" % (cid, _fmt(ratio), _fmt(ratio)),
                             "电流实际 ×%s" % _fmt(actual),
                             evidence="基线 I=%s，变换后 I=%s" % (_fmt(y1), _fmt(y2)),
                             advice="电流必须由 CIRCUIT.solve 按当前电压重算，不能缓存旧值",
                             solver="CIRCUIT.solve", source=source))
        elif field == "ohms":
            key = ("inverse", cid)
            if key in seen:
                continue
            seen.add(key)
            ratio = old_value / new_value
            actual = y2 / y1
            ok = close(actual, ratio, rel=DISPLAY_REL_TOL, abs_tol=DISPLAY_ABS_TOL)
            rows.append(_row("circuit.sample.resistance.%s" % cid, "电阻变化后电流按反比变化",
                             "inverse", "pass" if ok else "fail",
                             "%s 电阻 ×%s → 电流 ÷%s" % (cid, _fmt(new_value / old_value),
                                                        _fmt(new_value / old_value)),
                             "电流实际 ×%s" % _fmt(actual),
                             evidence="基线 I=%s，变换后 I=%s" % (_fmt(y1), _fmt(y2)),
                             advice="检查电阻控件是否真的进入 __CIRCUIT_MODEL__，并重算电流",
                             solver="CIRCUIT.solve", source=source))
    return rows


# --------------------------------------------------------------------------- 汇总

def summarize(rows, plan=None, api=""):
    rows = list(rows or [])
    passed = sum(1 for row in rows if row["status"] == "pass")
    failed = sum(1 for row in rows if row["status"] == "fail")
    skipped = sum(1 for row in rows if row["status"] == "skip")
    kinds = {}
    for row in rows:
        if row["status"] != "skip":
            kinds[row["kind"]] = kinds.get(row["kind"], 0) + 1
    return {
        "checked": bool(rows),
        "required": bool(plan),
        "ok": failed == 0 and (bool(rows) or not plan),
        "api": api,
        "rows": rows,
        "pass": passed,
        "fail": failed,
        "skip": skipped,
        "kinds": kinds,
        "coverage": {kind: kinds.get(kind, 0) for kind in KINDS},
    }


def evaluate_page(browser_payload, plan=None, api=""):
    """审查端入口：计划关系 + 电路样本关系 + 已有的课程/化学覆盖统计。"""
    payload = browser_payload or {}
    rows = evaluate_plan(plan, payload)
    plan_ids = {row["id"] for row in rows}
    # 计划已经覆盖电路时，不再重复“样本推导”的同类关系。
    if not any(row["solver"] == "CIRCUIT.solve" and row["status"] == "pass" for row in rows):
        for row in circuit_sample_rows(payload):
            if row["id"] not in plan_ids:
                rows.append(row)
    summary = summarize(rows, plan, api)

    lesson_states = sum(len(value or []) for value in (payload.get("lessonSolvers") or {}).values())
    chem_kinds = set()
    for key, value in (payload.get("machine") or {}).items():
        if key.endswith("_SAMPLES") and isinstance(value, list):
            for sample in value:
                if isinstance(sample, dict) and sample.get("kind"):
                    chem_kinds.add(sample["kind"])
    summary["lesson_states"] = lesson_states
    summary["chem_kinds"] = sorted(chem_kinds)
    summary["plan_id"] = (plan or {}).get("solver", "")
    summary["coverage_note"] = (
        "页面级关系 %d 条（通过 %d / 失败 %d / 跳过 %d）；课程模型采样 %d 个状态；化学变形 %d 类"
        % (len(rows), summary["pass"], summary["fail"], summary["skip"],
           lesson_states, len(chem_kinds)))
    return summary


def build_plan(api, html=""):
    """按求解器 API 取页面计划；没有登记就返回 None（不适用，而不是失败）。"""
    template = PAGE_PLANS.get(api or "")
    if not template:
        return None
    plan = copy.deepcopy(template)
    plan["version"] = 1
    plan["solver"] = api
    return plan


def print_rows(summary):
    for row in summary.get("rows") or []:
        print("[%s] %-34s %s" % (row["status"].upper(), row["id"], row["actual"]))
    print(summary.get("coverage_note", ""))


def main():
    parser = argparse.ArgumentParser(description="变形测试引擎（离线调试用）")
    parser.add_argument("--api", help="求解器 API，例如 CIRCUIT.solve")
    parser.add_argument("--payload", help="checks_browser.js 输出的 JSON 文件")
    parser.add_argument("--plan", help="计划 JSON 文件（不给则按 --api 生成）")
    args = parser.parse_args()
    plan = None
    if args.plan:
        with open(args.plan, "r", encoding="utf-8") as handle:
            plan = json.load(handle)
    elif args.api:
        plan = build_plan(args.api)
    payload = {}
    if args.payload:
        with open(args.payload, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    summary = evaluate_page(payload, plan, args.api or (plan or {}).get("solver", ""))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print_rows(summary)


if __name__ == "__main__":
    main()
