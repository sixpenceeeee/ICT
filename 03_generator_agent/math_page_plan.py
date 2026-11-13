"""Resolve mathematics lesson inputs and choose the requested page components."""

import re


class MathPlanError(ValueError):
    """The request specifies a value or component outside the registered lesson."""


NUMBER = r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)(?:e[+-]?\d+)?"
COMPONENTS = {
    "presets": r"预设|一键|三种状态",
    "comparison": r"对比表|比较表|前后对照|基准对照",
    "comparison_graph": r"对比图|前后图|图形对照",
    "records": r"记录表|记录数据|实验记录|学生探究",
    "csv": r"CSV|导出数据",
    "observations": r"观察任务|探究问题|学生探究",
    "derivation": r"代入步骤|分步演算|计算过程",
}
ENUMS = {"with": "放回", "without": "不放回", "add": "加法", "subtract": "减法",
         "quadratic": "平方函数", "absolute": "绝对值函数", "cross": "十字展开", "offset": "错位展开"}
ALIASES = {
    "rightTriangle": {"opposite": ("对边",), "adjacent": ("邻边",)},
    "sampling": {"good": ("目标球数", "红球", "红球数"), "bad": ("其他球数", "蓝球", "蓝球数"),
                 "draws": ("抽取次数", "抽取", "抽"), "hits": ("目标命中次数", "命中次数", "恰好命中", "恰好抽到")},
    "orthographic": {"width": ("底座宽", "底宽"), "depth": ("底座深", "底深"),
                     "height": ("底座高", "底高"), "step_width": ("台阶宽",), "rise": ("台阶高",)},
}
UNSUPPORTED = {
    "sinusoid": (r"正切函数|\by\s*=\s*tan\b", "三角函数页面当前支持正弦波及相移表示的余弦。正切需要独立的定义域和渐近线绘制。"),
    "derivative": (r"三次函数|三次多项式|指数函数|对数函数|三角函数", "导数页面当前按二次多项式及其退化情形计算。"),
    "descriptiveStats": (r"无偏样本方差|样本方差|n\s*[-−]\s*1\s*(?:作|为)分母", "当前计算的是五个等权观测值的总体方差。"),
    "sampling": (r"三色球|三种颜色|四种颜色", "抽样求解器当前使用目标球和其他球两类。"),
    "solid-volume": (r"组合体体积|重叠体积", "当前组合页面支持七种单体和相似分割；组合体需要明确组件及重叠关系。"),
}


def request_text(req):
    raw = req.get("原始需求")
    if raw:
        return str(raw).translate(str.maketrans("−＝", "-="))
    interactions = req.get("交互要求") or []
    if isinstance(interactions, str):
        interactions = [interactions]
    return "。".join(map(str, [req.get("实验主题", ""), *interactions])).translate(str.maketrans("−＝", "-="))


def select_components(req, default=()):
    text = request_text(req)
    selected = set(default)
    if "课堂演示版" in text:
        selected.clear()
    elif "学生探究版" in text:
        selected.update(("presets", "comparison", "records", "observations"))
    for name, pattern in COMPONENTS.items():
        if re.search(pattern, text, re.I):
            selected.add(name)
        if re.search(rf"(?:不要|无需|不用|不需要|不加|不提供)\s*(?:{pattern})", text, re.I):
            selected.discard(name)
    if "页面组件" in req:
        explicit = req["页面组件"]
        if not isinstance(explicit, list) or any(not isinstance(name, str) or name not in COMPONENTS
                                                for name in explicit):
            raise MathPlanError("页面组件须从预设、对比图、对比表、记录、CSV、观察任务和公式代入中选择")
        selected = set(explicit)
    if "csv" in selected:
        selected.add("records")
    return selected


def sampling_panels(req):
    text = request_text(req)
    action = r"(?:添加|显示|展示|用|画出|增加|附上|提供)\s*(?:一张|一个)?\s*"
    tree = bool(re.search(action + r"(?:树状图|抽样树)", text))
    distribution = bool(re.search(action + r"(?:概率柱状图|柱状图|概率分布|分布图)", text))
    if re.search(r"(?:只要|仅显示|只显示)\s*(?:树状图|抽样树)|(?:不要|不需要)\s*(?:柱状图|分布图)", text):
        return "tree"
    if re.search(r"(?:只要|仅显示|只显示)\s*(?:概率柱状图|柱状图|概率分布|分布图)|(?:不要|不需要)\s*(?:树状图|抽样树)", text):
        return "distribution"
    return "tree" if tree and not distribution else "distribution" if distribution and not tree else "both"


def resolve_inputs(req, key, model, solve, defaults=None):
    cases = model["cases"]
    initial = dict(defaults or next(iter(cases.values())))
    text = request_text(req)
    if key in UNSUPPORTED:
        pattern, problem = UNSUPPORTED[key]
        if re.search(pattern, text, re.I):
            raise MathPlanError(problem)
    variables = req.get("核心变量") or []
    for name, label in model["inputs"].items():
        aliases = ALIASES.get(key, {}).get(name, ()) + (re.split(r"[，、（]", label)[0],)
        choices = {case[name] for case in cases.values() if isinstance(case[name], str)}
        if choices:
            labels = {**ENUMS, **model.get("choice_labels", {})}
            for value in sorted(choices, key=lambda value: (-len(labels.get(value, value)), value)):
                label = labels.get(value, value)
                if (re.search(rf"(?:初始|默认)(?:为|选择)?\s*{re.escape(label)}", text)
                        or name in {"solid", "operation"} and label in str(req.get("实验主题", ""))):
                    initial[name] = value
                    break
            continue
        tag = rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])"
        pattern = "|".join((tag, *(re.escape(alias) for alias in aliases)))
        match = re.search(rf"(?:{pattern})\s*(?:初始值|初始|默认)?\s*(?:[:=]|为|设为)\s*({NUMBER})", text, re.I)
        if not match and key == "sampling" and name in ("good", "bad"):
            ball = "红球" if name == "good" else "蓝球"
            match = re.search(rf"({NUMBER})\s*个?\s*{ball}", text)
        if not match and key == "sampling" and name in ("draws", "hits"):
            prefix = "抽取?" if name == "draws" else "恰好(?:抽到|命中)"
            match = re.search(rf"(?:{prefix})\s*({NUMBER})\s*(?:次|个)", text)
        if match:
            initial[name] = float(match[1])
            continue
        for variable in variables:
            if not isinstance(variable, dict):
                continue
            label_text = str(variable.get("名称", ""))
            value = variable.get("初始值")
            if value is not None and (re.search(tag, label_text, re.I)
                                      or re.fullmatch(rf"(?:{pattern})", label_text, re.I)):
                try:
                    initial[name] = float(value)
                except (ValueError, TypeError, OverflowError) as exc:
                    raise MathPlanError(f"{label_text}的初始值须为数字") from exc
    if key == "orthographic":
        for names, pattern in ((("width", "depth", "height"), r"底座宽[、，,]深[、，,]高"),
                               (("step_width", "rise"), r"台阶宽[、，,]高")):
            match = re.search(pattern + r"\s*(?:初始)?\s*(?:分别)?(?:为|[:=])\s*"
                              + r"[、，,]\s*".join(f"({NUMBER})" for _ in names), text)
            if match:
                initial.update(zip(names, map(float, match.groups())))
    if "nx" in initial:
        axis_plane = re.search(rf"(?:默认截平面|初始截平面|截平面)\s*(?:为|是)?\s*([xyz])\s*=\s*({NUMBER})",
                               text, re.I)
        if axis_plane:
            initial.update({f"n{axis}": int(axis == axis_plane[1].lower()) for axis in "xyz"})
            initial["offset"] = float(axis_plane[2])
    explicit = req.get("初始参数", {})
    if not isinstance(explicit, dict) or explicit.keys() - initial.keys():
        raise MathPlanError("初始参数含有当前求解器未登记的字段")
    initial.update(explicit)
    for name, (low, high) in model.get("ranges", {}).items():
        value = initial[name]
        if type(value) not in (int, float) or not low <= value <= high:
            raise MathPlanError(f"{model['inputs'][name]}须在 {low} 到 {high} 之间")
    try:
        solve(initial)
    except (TypeError, ValueError, OverflowError) as exc:
        raise MathPlanError(str(exc)) from exc
    return initial


def number_bounds(value, samples):
    bound = max(10, abs(value), *(abs(sample) for sample in samples))
    return -bound, bound


