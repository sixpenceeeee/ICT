# -*- coding: utf-8 -*-
"""3D 凸透镜成像的共享资源层。

与 circuit_resources.py 同一角色：只提供默认模型、量程、六区内容与页面脚本，
不做任何光学计算——数值一律由 frame/optics_solver.js 求解、由
03_generator_agent/solvers/optics_solver.py 独立复算。

页面侧的挂载协议：canvas#cv + OPTICS3D.mount(cv, model)；读数用
data-optics-readout，控件用 data-optics-control，记录表用 data-optics-record。
"""
import json
import os
import re
import sys
from html import escape

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "03_generator_agent", "solvers"))
from optics_solver import solve_optics  # noqa: E402

TITLE = "凸透镜成像（3D 光具座）"
SLUG = "凸透镜成像3D"

RANGES = {
    "f": (5.0, 20.0, 0.5),
    "u": (5.0, 120.0, 1.0),
    "h": (0.5, 8.0, 0.5),
    "s": (0.0, 150.0, 1.0),
}

PROVENANCE = "离线示例（未调用模型）"

DESCRIPTION = "调节焦距、物距与光屏位置，观察像距、放大率与成像性质，并检验「虚像不能呈现在光屏上」。"
PRINCIPLE = "薄透镜成像满足 1/f = 1/u + 1/v，像距 v = uf/(u−f)，放大率 m = −v/u（负号表示倒立）。"
PITFALLS = "物距从光心量起、像距从光心量起；u=f 时折射光平行射出，不成像；u<f 时是正立放大的虚像，光屏上接不到，必须从透镜另一侧观察。"
QUESTIONS = "固定焦距，依次取 u>2f、u=2f、f<u<2f、u=f、u<f 五种情形，记录像距与像的性质；再移动光屏，观察清晰度如何变化。"
CONCLUSION = "同一凸透镜的像距由物距决定；实像可被光屏承接，虚像不能。"
NOTICE = "本页为理想薄透镜的虚拟仿真（近轴光线、忽略像差与色散）。拖动空白处旋转视角，拖动蜡烛或光屏可沿光具座移动；读数一律由求解器给出。"


def is_optics_request(req):
    text = req.get("实验主题", "") if isinstance(req, dict) else str(req or "")
    return bool(re.search(r"凸透镜|透镜成像|光具座|物距|像距|放大率|平面镜|折射", text))


def template_requirement(user_input, optics_mode="auto"):
    mode = (optics_mode or "auto").lower()
    if mode not in ("2d", "3d"):
        mode = "2d" if re.search(r"(?:^|[^a-z])2d|二维|平面光路|平面图|平面镜|折射", user_input or "", re.I) else "3d"
    name = "凸透镜成像2D" if mode == "2d" else "凸透镜成像3D"
    return {
        "学科": "物理",
        "年级": "初中八年级",
        "实验名称": name,
        "实验主题": user_input or "凸透镜成像规律探究",
        "光学视图": mode,
        "学习目标": [
            "能画出平行光、过光心、过焦点三条特殊光线",
            "能说出 u>2f、u=2f、f<u<2f、u=f、u<f 五种情形的像",
            DESCRIPTION,
        ],
        "核心变量": [
            {"名称": "焦距 f", "范围": "5~20", "单位": "cm"},
            {"名称": "物距 u", "范围": "5~120", "单位": "cm"},
            {"名称": "物高 h", "范围": "0.5~8", "单位": "cm"},
            {"名称": "光屏位置 s", "范围": "0~150", "单位": "cm"},
        ],
        "交互要求": [
            "拖动滑块或沿导轨拖拽蜡烛与光屏，实时更新光线与成像读数",
            "提供复位与记录表，支持对比多组物距与像距",
            "3D 模式支持点击「放大调节 ↗」打开独立大页面自主调节并回传参数" if mode == "3d" else "2D 平面光路清晰标注焦距点与物像距",
        ],
        "技术要点": "单文件离线 HTML，纯前端求解与渲染（%s 光具座）" % ("3D" if mode == "3d" else "2D"),
        "风险点": ["本页为理想薄透镜虚拟仿真，需经教师复核后用于课堂教学"],
    }


def default_model():
    return {
        "schema_version": 1,
        "scene_id": "lens_imaging",
        "f": 10.0,
        "u": 30.0,
        "h": 3.0,
        "screen": {"s": 15.0},
        "view": {"yaw": -0.62, "pitch": 0.38},
    }


def _clamp(value, low, high):
    return min(high, max(low, value))


def resolve_model(params=None):
    """把外部参数（dict）收成型别正确的模型；缺省用 default_model()。"""
    model = default_model()
    params = params or {}
    if "f" in params:
        model["f"] = float(params["f"])
    if "u" in params:
        model["u"] = float(params["u"])
    if "h" in params:
        model["h"] = float(params["h"])
    if "s" in params:
        model["screen"] = {"s": float(params["s"])}
    elif isinstance(params.get("screen"), dict) and "s" in params["screen"]:
        model["screen"] = {"s": float(params["screen"]["s"])}
    for key, (low, high, _step) in RANGES.items():
        if key == "s":
            model["screen"]["s"] = _clamp(model["screen"]["s"], low, high)
        else:
            model[key] = _clamp(model[key], low, high)
    return model


def _slider(key, label, unit, value, initial):
    low, high, step = RANGES[key]
    return (
        '<label class="exp-field"><span class="exp-label">' + label
        + '<span class="exp-val"><b data-optics-readout="' + ("screen" if key == "s" else key) + '">'
        + initial + '</b></span></span>'
        + '<input type="range" data-optics-control="' + key + '" min="' + str(low) + '" max="' + str(high)
        + '" step="' + str(step) + '" value="' + str(value) + '" aria-label="' + label + '"></label>'
    )


def _trim(value, digits=2):
    text = ("%." + str(digits) + "f") % value
    return text.rstrip("0").rstrip(".")


UCLASS_TEXT = {
    "u>2f": "物距大于二倍焦距（u>2f）：倒立、缩小的实像",
    "u=2f": "物距等于二倍焦距（u=2f）：倒立、等大的实像",
    "f<u<2f": "物距在一倍与二倍焦距之间（f<u<2f）：倒立、放大的实像",
    "u=f": "物距等于焦距（u=f）：折射光平行射出，不成像",
    "u<f": "物距小于焦距（u<f）：正立、放大的虚像，光屏上接不到",
}


def _readout(model, result, key):
    """首屏静态读数：与页面运行时的 OPTICS.meter 同一套口径（JS 随后会覆盖）。"""
    if key == "v":
        return "—" if result["v"] is None else _trim(result["v"]) + " cm"
    if key == "m":
        return "—" if result["m"] is None else _trim(result["m"]) + "×"
    if key == "kind":
        return result["kindText"]
    if key == "sharp":
        return "清晰" if result["onScreen"]["sharp"] else "不清晰"
    if key == "screen":
        return _trim(result["s"], 1) + " cm"
    if key in ("f", "u", "h"):
        return _trim(model[key]) + " cm"
    if key == "uClass":
        return UCLASS_TEXT.get(result["uClass"], result["uClass"])
    return "—"


def _formula_text(model, result):
    if result["kind"] == "none":
        return "u = f：1/u + 1/v = 1/f 无有限解，折射光平行射出，不成像。"
    if model["u"] > model["f"]:
        text = ("v = u·f ÷ (u − f) = %s × %s ÷ %s = %s cm；"
                % (_trim(model["u"], 1), _trim(model["f"], 1), _trim(model["u"] - model["f"], 1),
                   _trim(result["v"], 1)))
    else:
        text = ("v = −u·f ÷ (f − u) = −(%s × %s ÷ %s) = %s cm；"
                % (_trim(model["u"], 1), _trim(model["f"], 1), _trim(model["f"] - model["u"], 1),
                   _trim(result["v"], 1)))
    return text + "m = −v ÷ u = %s×（%s）" % (_trim(result["m"], 2), result["kindText"])


def render_sections(model=None, provenance=PROVENANCE):
    model = model or default_model()
    result = solve_optics(model)
    encoded = json.dumps(model, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c")
    return {
        "1": '<div class="exp-tags"><span class="exp-tag">物理</span><span class="exp-tag">初中八年级</span>'
             '<span class="exp-tag is-plain">' + escape(provenance) + '</span></div>'
             '<div class="exp-goals-title">学习目标</div><ul class="exp-goals">'
             '<li>能画出平行光、过光心、过焦点三条特殊光线</li>'
             '<li>能说出 u&gt;2f、u=2f、f&lt;u&lt;2f、u=f、u&lt;f 五种情形的像</li>'
             '<li>' + DESCRIPTION + '</li></ul>',
        "2": '<canvas id="cv" data-visual-type="apparatus" role="img" aria-label="3D 光具座：透镜、蜡烛、光屏与三条光线"></canvas>'
             '<div class="optics-stage-tools"><span class="exp-canvas-tip">拖动空白处旋转视角，滚轮缩放；拖动蜡烛或光屏可沿光具座移动，点击右上角可放大自主调节</span>'
             '<button class="exp-btn" id="btn-optics-enlarge" type="button" data-optics-enlarge>放大调节 ↗</button></div>',
        "3": '<div class="exp-fields">'
             + _slider("f", "焦距 f", "cm", model["f"], escape(_readout(model, result, "f")))
             + _slider("u", "物距 u", "cm", model["u"], escape(_readout(model, result, "u")))
             + _slider("h", "物高 h", "cm", model["h"], escape(_readout(model, result, "h")))
             + _slider("s", "光屏位置 s", "cm", model["screen"]["s"], escape(_readout(model, result, "screen")))
             + '</div><div class="exp-btns">'
             '<button class="exp-btn is-primary" type="button" data-optics-record-btn>记录当前数据</button>'
             '<button class="exp-btn" type="button" data-optics-reset-view>恢复默认视角</button>'
             '<button class="exp-btn" type="button" id="btn-reset-params">重置</button>'
             '</div>',
        "4": '<div class="exp-reads">'
             '<div class="exp-read"><span class="k">像距 v</span><span class="v"><b data-optics-readout="v">'
             + escape(_readout(model, result, "v")) + '</b></span></div>'
             '<div class="exp-read"><span class="k">放大率 m</span><span class="v"><b data-optics-readout="m">'
             + escape(_readout(model, result, "m")) + '</b></span></div>'
             '<div class="exp-read"><span class="k">成像性质</span><span class="v"><b data-optics-readout="kind">'
             + escape(_readout(model, result, "kind")) + '</b></span></div>'
             '<div class="exp-read"><span class="k">光屏清晰度</span><span class="v"><b data-optics-readout="sharp">'
             + escape(_readout(model, result, "sharp")) + '</b></span></div>'
             '<div class="exp-read"><span class="k">光屏位置</span><span class="v"><b data-optics-readout="screen">'
             + escape(_readout(model, result, "screen")) + '</b></span></div>'
             '</div>'
             '<div class="exp-formula" data-optics-formula>' + escape(_formula_text(model, result)) + '</div>'
             '<p class="exp-note" data-optics-readout="uClass" aria-live="polite">'
             + escape(_readout(model, result, "uClass")) + '</p>'
             '<p class="exp-note" data-optics-status aria-live="polite" hidden></p>',
        "5": '<table class="exp-table"><thead><tr><th>f / cm</th><th>u / cm</th><th>光屏 / cm</th>'
             '<th>v / cm</th><th>m</th><th>像</th><th>清晰度</th></tr></thead>'
             '<tbody data-optics-record></tbody></table>',
        "6": '<h3>原理</h3><p>' + PRINCIPLE + '</p>'
             '<h3>易错点</h3><p>' + PITFALLS + '</p>'
             '<h3>探究问题</h3><p>' + QUESTIONS + '</p>'
             '<h3>结论</h3><p>' + CONCLUSION + '</p>'
             '<h3>注意事项</h3><p>' + NOTICE + '</p>',
        "css": '#cv{display:block;width:100%;height:460px;border-radius:10px;background:#f6f8fb}'
               '.exp-stage>h2{display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap}'
               '.exp-stage #btn-optics-enlarge{flex:0 0 auto;white-space:nowrap;margin-left:auto}'
               '.optics-stage-tools{display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap}'
               '.exp-fields{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}'
               '.exp-fields .exp-label{display:flex;align-items:center;justify-content:space-between;'
               'gap:8px;white-space:nowrap}'
               '.exp-fields .exp-label .exp-val{font-variant-numeric:tabular-nums}'
               '@media(max-width:760px){#cv{height:320px}}',
        "js": 'window.__DATA__={};\n'
              'window.__OPTICS_INITIAL__=' + encoded + ';\n'
              'var __optics=OPTICS3D.mount(document.getElementById("cv"), window.__OPTICS_INITIAL__);\n'
              'document.getElementById("btn-reset-params").addEventListener("click", function(){'
              ' __optics.setModel(window.__OPTICS_INITIAL__); });',
    }


def render_2d_sections(model=None, provenance=PROVENANCE):
    """2D 光具座（PHYS.optics）共享六区模板，供 2D 模式生成与模板兜底使用。"""
    model = model or default_model()
    secs = render_sections(model, provenance=provenance)
    secs["2"] = (
        '<canvas id="cv" data-visual-type="apparatus" role="img" '
        'aria-label="2D 光具座：凸透镜、物体、光屏与三条特殊光线"></canvas>'
        '<div class="exp-canvas-tip" id="tip">拖动下方滑块调节焦距、物距与光屏位置</div>'
    )
    secs["3"] = (
        '<div class="exp-fields">'
        + _slider("f", "焦距 f", "cm", model["f"], escape(_readout(model, solve_optics(model), "f")))
        + _slider("u", "物距 u", "cm", model["u"], escape(_readout(model, solve_optics(model), "u")))
        + _slider("s", "光屏位置 s", "cm", model["screen"]["s"], escape(_readout(model, solve_optics(model), "screen")))
        + '</div><div class="exp-btns">'
        '<button class="exp-btn is-primary" type="button" data-optics-record-btn>记录当前数据</button>'
        '<button class="exp-btn" type="button" id="btn-reset-params">重置</button>'
        '</div>'
    )
    secs["css"] = (
        '#cv{display:block;width:100%;height:460px;border-radius:10px;background:#fbfdff}'
        '.exp-fields{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}'
        '.exp-fields .exp-label{display:flex;align-items:center;justify-content:space-between;gap:8px;white-space:nowrap}'
        '.exp-fields .exp-label .exp-val{font-variant-numeric:tabular-nums}'
        '@media(max-width:760px){#cv{height:320px}}'
    )
    encoded = json.dumps(model, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c")
    secs["js"] = (
        'window.__DATA__={};\n'
        'window.__OPTICS_INITIAL__=' + encoded + ';\n'
        '(function(){\n'
        '  var cv=document.getElementById("cv");\n'
        '  var m=JSON.parse(JSON.stringify(window.__OPTICS_INITIAL__));\n'
        '  function paint(){\n'
        '    var r=OPTICS.solve(m);\n'
        '    PHYS.optics(cv,{u:m.u,f:m.f,scr:m.screen.s,lensAt:45});\n'
        '    OPTICS.bindReadouts(r,document);\n'
        '    var fml=document.querySelector("[data-optics-formula]");\n'
        '    if(fml){\n'
        '      fml.textContent=r.kind==="none"?"u = f：折射光平行射出，不成像。":\n'
        '        (m.u>m.f?"v = u·f ÷ (u − f) = "+m.u.toFixed(1)+" × "+m.f.toFixed(1)+" ÷ "+(m.u-m.f).toFixed(1)+" = "+r.v.toFixed(1)+" cm；":\n'
        '         "v = −u·f ÷ (f − u) = −("+m.u.toFixed(1)+" × "+m.f.toFixed(1)+" ÷ "+(m.f-m.u).toFixed(1)+") = "+r.v.toFixed(1)+" cm；")\n'
        '        +"m = −v ÷ u = "+r.m.toFixed(2)+"×（"+r.kindText+"）";\n'
        '    }\n'
        '    window.__OPTICS_MODEL__=JSON.parse(JSON.stringify(m));\n'
        '    window.__OPTICS_RESULT__=r;\n'
        '    window.__DATA__={f:m.f,u:m.u,s:m.screen.s,v:r.v,m:r.m,kind:r.kind,sharp:r.onScreen.sharp};\n'
        '  }\n'
        '  document.addEventListener("input",function(e){\n'
        '    var k=e.target&&e.target.getAttribute&&e.target.getAttribute("data-optics-control");\n'
        '    if(!k)return;\n'
        '    var v=Number(e.target.value);if(!isFinite(v))return;\n'
        '    if(k==="f")m.f=v;if(k==="u")m.u=v;if(k==="s")m.screen={s:v};paint();\n'
        '  });\n'
        '  document.getElementById("btn-reset-params").addEventListener("click",function(){\n'
        '    m=JSON.parse(JSON.stringify(window.__OPTICS_INITIAL__));\n'
        '    document.querySelectorAll("[data-optics-control]").forEach(function(el){\n'
        '      var k=el.getAttribute("data-optics-control");\n'
        '      if(k==="f")el.value=m.f;if(k==="u")el.value=m.u;if(k==="s")el.value=m.screen.s;\n'
        '    });\n'
        '    paint();\n'
        '  });\n'
        '  document.querySelector("[data-optics-record-btn]").addEventListener("click",function(){\n'
        '    var r=OPTICS.solve(m),tb=document.querySelector("[data-optics-record]");\n'
        '    var tr=document.createElement("tr");\n'
        '    [m.f.toFixed(0),m.u.toFixed(0),m.screen.s.toFixed(0),r.v==null?"—":r.v.toFixed(1),r.m==null?"—":r.m.toFixed(2),r.kindText,r.onScreen.sharp?"清晰":"不清晰"].forEach(function(t){\n'
        '      var td=document.createElement("td");td.textContent=t;tr.appendChild(td);\n'
        '    });\n'
        '    tb.appendChild(tr);\n'
        '  });\n'
        '  paint();\n'
        '})();'
    )
    return secs
