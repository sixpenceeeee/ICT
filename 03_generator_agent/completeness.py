# -*- coding: utf-8 -*-
"""completeness —— 页面完整性检查（"不少元素、不少步骤"）。

为什么单独一层
--------------
hard_validate 管的是"能不能装配出来"（六区齐、类名对、求解器被调用），
审查器管的是"做得好不好"（数值对不对、版式是否合规）。
中间缺一层：**这页该有的东西在不在**——记录表、CSV、重置、探究问题、结论、
注意事项、分步实验的步骤清单。少了这些，页面能生成、也能过装配，但老师没法用。

本模块不依赖浏览器，纯静态 + 结构判定，因此可以放在生成端或验收脚本里跑。

用法：
    from completeness import check_page
    problems = check_page(sections, spec=spec_or_None)
"""

import re

#: 每个元素：id、名称、严重度（error 必须补 / warn 建议补）
ELEMENTS = (
    ("goals", "学习目标", "error"),
    ("controls", "可操作控件", "error"),
    ("readouts", "结果读数", "error"),
    ("formula", "可复算代入式", "error"),
    ("records", "实验记录表", "error"),
    ("csv", "记录导出（CSV）", "error"),
    ("reset", "重置功能", "error"),
    ("question", "探究问题", "error"),
    ("conclusion", "结论", "error"),
    ("safety", "注意事项", "error"),
    ("pitfall", "易错点", "warn"),
    ("binding", "读数与求解结果绑定", "error"),
    ("offline", "离线可用（无外链）", "error"),
)

#: 需要分步流程的场景关键词 → 最少步骤数
STEP_SCENES = (
    (r"粗盐|提纯|过滤|蒸发", 3),
    (r"光合作用|遮光|脱色|碘液", 4),
    (r"孟德尔|杂交|棋盘", 3),
    (r"显微镜|低倍|高倍", 3),
    (r"排序|冒泡|二分查找|汉诺塔|进制转换", 3),
)


def _text(sections):
    return "\n".join(str(sections.get(key) or "") for key in ("1", "2", "3", "4", "5", "6", "css", "js"))


def check_page(sections, spec=None, req=None):
    """返回 [{"id","名称","状态","说明"}]，状态取 pass / fail / skip。"""
    secs = sections or {}
    body = {key: str(secs.get(key) or "") for key in "123456"}
    js = str(secs.get("js") or "")
    everything = "\n".join(body.values()) + "\n" + js
    results = []

    def add(element_id, status, detail):
        name = dict((item[0], item[1]) for item in ELEMENTS).get(element_id, element_id)
        results.append({"id": element_id, "名称": name, "状态": status, "说明": detail})

    add("goals", "pass" if "学习目标" in body["1"] else "fail",
        "① 区有学习目标" if "学习目标" in body["1"] else "① 区缺少「学习目标」")

    controls = len(re.findall(r"data-solver-input\s*=|type=[\"'](?:range|number)[\"']|data-chem-[a-z-]+-index", everything))
    add("controls", "pass" if controls else "fail",
        "控件 %d 个" % controls if controls else "页面上没有可操作控件")

    readouts = len(re.findall(r"data-solver-field\s*=|class=\"exp-read\"|data-circuit-(?:current|voltage)-for", everything))
    add("readouts", "pass" if readouts else "fail",
        "读数 %d 处" % readouts if readouts else "④ 区没有读数")

    has_formula = ("exp-formula" in everything) and (
        "textContent" in js or "innerHTML" in js or "result." in js
        or "MATHPAGE.mount" in js or "VIS.bindSolverReadouts" in js)
    add("formula", "pass" if has_formula else "fail",
        "代入式容器与赋值都在" if has_formula else "缺少可复算的代入式（容器或赋值缺失）")

    if spec is not None:
        components = set(spec.get("components") or [])
        records_expected = "records" in components
        csv_expected = "csv" in components
    else:
        records_expected = csv_expected = True

    has_table = bool(re.search(r"<table[^>]*class=\"exp-table\"|exp-table", everything))
    add("records", "pass" if has_table else ("skip" if not records_expected else "fail"),
        "有记录表" if has_table else "缺少实验记录表")

    has_csv = bool(re.search(r"导出\s*CSV|text/csv|\.csv", everything))
    add("csv", "pass" if has_csv else ("skip" if not csv_expected else "fail"),
        "有 CSV 导出" if has_csv else (
            "未要求 CSV 导出" if not csv_expected else "缺少 CSV 导出（记录只能看不能带走）"))

    has_reset = bool(re.search(r"重置|btn-reset", everything))
    add("reset", "pass" if has_reset else "fail", "有重置" if has_reset else "缺少重置功能")

    add("question", "pass" if re.search(r"探究问题|观察任务|引导问题", body["6"] + body["1"]) else "fail",
        "有探究问题" if re.search(r"探究问题|观察任务|引导问题", body["6"] + body["1"]) else "⑥ 区缺少探究问题")

    add("conclusion", "pass" if "结论" in body["6"] else "fail",
        "有结论" if "结论" in body["6"] else "⑥ 区缺少结论")

    add("safety", "pass" if re.search(r"注意事项|安全", body["6"]) else "fail",
        "有注意事项" if re.search(r"注意事项|安全", body["6"]) else "⑥ 区缺少注意事项")

    add("pitfall", "pass" if re.search(r"易错|常见错误", body["6"]) else "warn",
        "有易错点" if re.search(r"易错|常见错误", body["6"]) else "建议补易错点")

    # 化学模板用 data-chem-* / 电表用 data-circuit-* 手动绑定；其余走 bindSolverReadouts
    bound = bool(re.search(r"VIS\.bindSolverReadouts|bindMeters|data-solver-field"
                          r"|data-chem-[a-z-]+-(?:equation|mass|volume|ph|state|result)"
                          r"|data-circuit-(?:current|voltage)-for", everything))
    add("binding", "pass" if bound else "fail",
        "读数由求解结果绑定" if bound else "读数没有和求解结果绑定（可能是手写数值）")

    external = re.findall(r"(?:src|href)=\"(https?://[^\"]+)\"|fetch\(\s*[\"']https?://", everything)
    add("offline", "pass" if not external else "fail",
        "无外链" if not external else "存在外链/联网请求：%s" % "、".join(external[:3]))

    steps = _check_steps(body, js, everything, req)
    results.extend(steps)
    return results


def _check_steps(body, js, everything, req):
    """分步实验的步骤齐备性。非过程类页面返回 skip。"""
    text = "".join(body[key] for key in "123456")
    haystack = str((req or {}).get("实验主题") or "") or text[:80]
    required = None
    for pattern, count in STEP_SCENES:
        if re.search(pattern, haystack):
            required = count
            break
    has_step_ui = bool(re.search(r"下一步|上一步|单步|开始反应|开始实验|播放", everything))
    if required is None and not has_step_ui:
        return [{"id": "steps", "名称": "分步流程", "状态": "skip", "说明": "非分步页面"}]

    indexed = len(set(re.findall(r"data-step-index=\"(\d+)\"", everything)))
    listed = len(re.findall(r"<li[^>]*>", body["6"]))
    marker = "__DATA__" in js and "steps" in js
    detail = "步骤标记 %d 个、⑥区条目 %d 个%s" % (indexed, listed, "、__DATA__.steps 已暴露" if marker else "")
    if required is not None:
        found = max(indexed, 1 if marker else 0)
        if found >= required:
            return [{"id": "steps", "名称": "分步流程", "状态": "pass", "说明": "步骤 ≥ %d（%s）" % (required, detail)}]
        return [{"id": "steps", "名称": "分步流程", "状态": "fail",
                 "说明": "需要至少 %d 个可定位的步骤，%s" % (required, detail)}]
    return [{"id": "steps", "名称": "分步流程", "状态": "pass", "说明": "有分步控件（%s）" % detail}]


def summarize(results):
    failed = [item for item in results if item["状态"] == "fail"]
    warned = [item for item in results if item["状态"] == "warn"]
    skipped = [item for item in results if item["状态"] == "skip"]
    passed = [item for item in results if item["状态"] == "pass"]
    return {"pass": len(passed), "fail": len(failed), "warn": len(warned),
            "skip": len(skipped), "失败项": failed, "建议项": warned,
            "可验收": not failed}
