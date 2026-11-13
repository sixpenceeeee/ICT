# -*- coding: utf-8 -*-
"""求解器统一契约与第一层自检（solver self-check）。

约定
----
每个学科求解器（JS 与 Python）在返回业务结果之外，必须能给出同一形状的自检：

    {"ok": bool, "api": str, "failures": [str, ...]}

自检只做“同一个结果内部必须成立的恒等式/量纲/边界”，
不重复一遍求解过程——重复求解由审查端的独立实现（第二层）负责。

用法
----
    from solver_contract import audit
    report = audit("solveBuoyancy", request, result)
    if not report["ok"]:
        ...  # 页面不得展示正常读数

新增求解器时：
1. 在 physics_audits.py / math_audits.py / geometry_audits.py 用
   @register("solveXxx") 注册一个自检函数；
2. 运行 `py -B -m unittest tests.test_solver_contract`；
3. 未注册的 API 会退化为 generic 自检（只查有限数值），
   但 tests/test_solver_contract.py 会强制要求教学模型必须有专用自检。
"""

import math

G = 9.8
TOL = 1e-9

#: api -> callable(request, result) -> dict
AUDITS = {}


def register(*apis):
    """把同一个自检函数注册给一个或多个求解器 API。"""

    def decorate(function):
        for api in apis:
            AUDITS[api] = function
        return function

    return decorate


def close(left, right, rel=TOL, abs_tol=TOL):
    """None 只与 None 相等；字符串按字面比较；数值按相对/绝对容差比较。"""
    if left is None or right is None:
        return left is None and right is None
    if isinstance(left, str) or isinstance(right, str):
        return left == right
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right
    if isinstance(left, (list, tuple)) or isinstance(right, (list, tuple)):
        if not isinstance(left, (list, tuple)) or not isinstance(right, (list, tuple)):
            return False
        return (len(left) == len(right)
                and all(close(a, b, rel, abs_tol) for a, b in zip(left, right)))
    try:
        return math.isclose(float(left), float(right), rel_tol=rel, abs_tol=abs_tol)
    except (TypeError, ValueError):
        return False


class Audit:
    """收集一次自检里的所有失败项，而不是遇到第一条就抛错。"""

    def __init__(self, api):
        self.api = api
        self.failures = []

    def need(self, name, condition, detail=""):
        if not condition:
            self.failures.append(name + (":" + detail if detail else ""))
        return bool(condition)

    def same(self, name, actual, expected, rel=TOL, abs_tol=TOL):
        if not close(actual, expected, rel, abs_tol):
            self.failures.append("%s: %r != %r" % (name, actual, expected))
            return False
        return True

    def positive(self, name, value):
        return self.need(name, isinstance(value, (int, float)) and math.isfinite(value) and value > 0,
                         repr(value))

    def nonnegative(self, name, value):
        return self.need(name, isinstance(value, (int, float)) and math.isfinite(value) and value >= -TOL,
                         repr(value))

    def one_of(self, name, value, allowed):
        return self.need(name, value in allowed, repr(value))

    def result(self):
        return {"ok": not self.failures, "api": self.api, "failures": self.failures[:12]}


def non_finite_paths(value, path=""):
    """递归找出所有 NaN / ±Infinity 的字段路径。"""
    bad = []
    if isinstance(value, bool):
        return bad
    if isinstance(value, (int, float)):
        if not math.isfinite(value):
            bad.append(path or "<root>")
    elif isinstance(value, dict):
        for key, item in value.items():
            bad.extend(non_finite_paths(item, "%s.%s" % (path, key) if path else str(key)))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            bad.extend(non_finite_paths(item, "%s[%d]" % (path, index)))
    return bad


def generic_audit(api, request, result):
    audit = Audit(api)
    audit.need("result_is_object", isinstance(result, dict))
    if isinstance(result, dict):
        bad = non_finite_paths({key: value for key, value in result.items() if key != "checks"})
        audit.need("finite_numbers", not bad, "、".join(bad[:5]))
    return audit.result()


def _normalize(api):
    """允许同时使用 'solveBuoyancy' 与 'PHYS.solveBuoyancy' 两种写法。"""
    return str(api or "").rsplit(".", 1)[-1]


def audit(api, request, result):
    """对一次求解结果执行自检。自检自身异常也算未通过，绝不静默放过。"""
    checker = AUDITS.get(api) or AUDITS.get(_normalize(api))
    if checker is None:
        return generic_audit(api, request, result)
    try:
        report = checker(request or {}, result or {})
    except Exception as exc:  # noqa: BLE001 - 自检异常必须暴露为不通过
        return {"ok": False, "api": api, "failures": ["自检异常: %s: %s" % (type(exc).__name__, exc)]}
    report.setdefault("api", api)
    return report


def has_specific_audit(api):
    return api in AUDITS or _normalize(api) in AUDITS
