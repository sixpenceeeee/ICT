"""Compile supported teaching requests into requirements shared by rendering and review."""

import re

WATER_DENSITY = 1000
GRAVITY = 9.8
FLOAT_SCENE = "physics-buoyancy"


def compile_contract(req, scene=None):
    req = req or {}
    if scene is not None and scene != FLOAT_SCENE:
        return None
    original = str(req.get("原始需求") or "")
    detail = " ".join(str(req.get(key, "")) for key in
                      ("实验名称", "实验主题", "学习目标", "核心变量", "交互要求", "技术要点"))
    topic = original or " ".join(str(req.get(key, "")) for key in ("实验名称", "实验主题"))
    if not re.search(r"浮力|阿基米德", topic) or not re.search(r"排开|排液|浸入体积", topic + detail):
        return None
    fixed = r"(?:液体密度|水的密度|密度)(?:保持|始终|固定|恒定|不变|相同)|(?:固定(?:使用|用|为)?水|液体固定|保持(?:液体|水)|同种液体|只(?:改变|调节|调)排开)"
    changing = r"(?:改变|调节|调整|切换|比较|更换|可调)(?:不同)?(?:液体密度|液体种类|液体|介质)"
    if re.search(changing, original) and not re.search(fixed, original):
        return None
    if not re.search(fixed, original + detail):
        return None
    # The supported classroom profile uses water. Another explicitly requested
    # liquid stays on the existing general buoyancy path.
    if re.search(r"盐水|海水|酒精|甘油|煤油|食用油|油液", original):
        return None
    bounds = r"(?<![\d.])0\s*(?:~|～|—|–|-|至|到)\s*(\d+(?:\.\d+)?)\s*(?:mL|毫升|cm[³3]|立方厘米)"
    match = re.search(bounds, original, re.I) or re.search(bounds, detail, re.I)
    maximum = float(match[1]) if match else 100
    if not 1 <= maximum <= 2000:
        return None

    def requested(pattern, default):
        for source in (original, detail):
            clauses = re.split(r"[。；;，,\n]", source)
            relevant = [part for part in clauses if re.search(pattern, part, re.I)]
            if any(re.search(r"不要|无需|不用|禁止|不(?:需|提供|显示|导出|记录)|无须|取消|关闭", part)
                   for part in relevant):
                return False
            if relevant:
                return True
        return default

    csv = requested(r"CSV|导出", False)
    records = csv or requested(r"记录表|记录(?:当前)?数据|实验记录", True)
    return {
        "scene": FLOAT_SCENE,
        "profile": "fixed-water-displacement",
        "fixed": {"liquid_density": WATER_DENSITY, "object_density": 1200,
                  "volume": maximum * 1e-6, "mode": "hang"},
        "slider": {"field": "fraction", "min": 0, "max": maximum, "unit": "mL"},
        "records": records, "csv": csv,
    }


def vessel_geometry(contract):
    """Use a straight-walled vessel with enough headroom for the block."""
    capacity = max(1000, 3 * contract["slider"]["max"])
    return {"initialMl": 0.6 * capacity, "scaleMl": capacity, "scaleFill": 0.86}


def apply_to_spec(spec, contract):
    """Expose volume in mL while the existing solver still receives a fraction."""
    slider = contract["slider"]
    maximum = slider["max"]
    spec["teaching_contract"] = contract
    spec["fixed_inputs"] = dict(contract["fixed"])
    vessel = vessel_geometry(contract)
    spec["draw"]["options"] = {"waterDisplacement": vessel}
    field = next(item for item in spec["inputs"] if item["name"] == slider["field"])
    field.update(kind="range", label="排开液体体积", unit="mL", value=0,
                 minimum=0, maximum=1, scale=1 / maximum, step="any", display_digits=2)
    spec["inputs"] = [field]
    spec["presets"] = []
    spec["components"] = [part for part, enabled in
                          (("records", contract["records"]), ("csv", contract["csv"])) if enabled]
    spec["stage"]["note"] = ("初始水量 %g mL（密度 1000 kg/m³）。水量不变，"
                            "水位读数随排开液体的体积上升。" % vessel["initialMl"])
    spec["records"].update(headers=["序号", "排开液体体积（mL）", "浮力（N）"],
                           fields=["rows.rows.length", "number(result.displaced_volume * 1e6)",
                                   "number(result.buoyancy)"])
    return spec
