# -*- coding: utf-8 -*-
"""
reviewer.py —— 质量审查 Agent（按《界面设计+审查判据》V1.0 重构）

规范 3.4 把审查拆成五关，这个文件就是这五关的执行器：

    第1关 结构与安全   JSON Schema / 字段类型 / 引擎白名单 / 参数范围 / 离线 / 密钥
    第2关 资源完整性   六区域是否齐备、外壳资源、画布、控件、记录、重置、CSV
    第3关 学科判据     按 J1–J8 配置运行**独立**校验（judges.py）
    第4关 浏览器测试   加载、JS 报错、拖滑块、点按钮、重置回初态、单步、记录
    第5关 教学审核     实验性质、虚拟仿真声明、教学说明、教师复核状态

判定只有四种状态，对齐规范：
    pass   客观复算通过
    fail   客观复算失败（带 expected / actual / evidence）
    review 无客观标准或事实表未复核 —— 交教师判断，**不伪造结论**
    skip   本页没有这类内容，不计入分母（不适用 ≠ 通过）

分数与结论分开：
    总分      只统计 pass/fail，review 与 skip 不进分母
    结论      通过 / 需修改 / 不通过（给流水线判断是否返工）
    发布状态  可发布 / 待教师审核 / 禁止发布（给平台决定能不能上线）

这三者必须分开，否则"没有标准答案的开放任务"会被机器硬判成合格。

用法：
    python reviewer.py                          # 审最新生成结果
    python reviewer.py --html ../deliver/x/x.html --req ../01_single_agent/output/需求_x.json
    python reviewer.py --quiet                  # 只输出可回传生成 Agent 的修改意见
"""

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT = os.path.dirname(BASE_DIR)
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
CHECK_JS = os.path.join(BASE_DIR, "checks_browser.js")
FACTS_PATH = os.path.join(BASE_DIR, "facts.json")

sys.path.insert(0, PARENT)
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(PARENT, "03_generator_agent", "solvers"))

from topics import detect_topic, profile_of, unit_pattern  # noqa: E402
import judges as judge_lib                                  # noqa: E402
import registry                                            # noqa: E402
from circuit_solver import CircuitError, solve_circuit      # noqa: E402

PASS_SCORE = 80
MAJOR_LINE = 60

CRITICAL = "严重"
MAJOR = "一般"
MINOR = "建议"

# 五关的满分（规范没有规定权重，这里按"能不能上课"的影响程度分配）
GATES = [
    ("G1", "结构与安全", 25),
    ("G2", "资源完整性", 25),
    ("G3", "学科判据", 25),
    ("G4", "浏览器测试", 15),
    ("G5", "教学审核", 10),
]
GATE_NAME = {g: n for g, n, _ in GATES}
GATE_FULL = {g: f for g, _, f in GATES}


# ============ 环境查找 ============

def find_node():
    exe = shutil.which("node")
    if exe:
        return exe
    for p in glob.glob(os.path.expanduser("~/.workbuddy/binaries/node/versions/*/node.exe")):
        return p
    return None


def find_node_modules():
    for p in (
        os.path.expanduser("~/.workbuddy/binaries/node/workspace/node_modules"),
        os.path.expanduser("~/.workbuddy/binaries/node/lib/node_modules"),
    ):
        if os.path.isdir(os.path.join(p, "playwright")):
            return p
    return None


def find_chrome():
    bases = [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "ms-playwright"),
        os.path.join(os.path.expanduser("~"), "AppData", "Local", "ms-playwright"),
    ]
    for base in bases:
        for d in sorted(glob.glob(os.path.join(base, "chromium-*")), reverse=True):
            exe = os.path.join(d, "chrome-win64", "chrome.exe")
            if os.path.exists(exe):
                return exe
    return None


# ============ 检查项构造 ============

def mk(gate, cid, name, status, expected, actual, message,
       evidence="", advice="", severity=MAJOR, weight=1, judge=""):
    return {
        "check_id": cid, "gate": gate, "gate_name": GATE_NAME[gate], "judge": judge,
        "name": name, "status": status, "severity": severity, "weight": weight,
        "expected": expected, "actual": actual, "message": message,
        "evidence": evidence, "advice": advice,
    }


def strip_namespaces(html):
    """xmlns 里的 http:// 是命名空间标识，不是网络请求。"""
    return re.sub(r'xmlns(:\w+)?="[^"]*"', "", html)


# ============ 第1关：结构与安全 ============

SECRET_PATTERNS = [
    (r"sk-[A-Za-z0-9]{12,}", "OpenAI 风格密钥"),
    (r"AKIA[0-9A-Z]{12,}", "AWS AccessKey"),
    (r"(?i)(api[_-]?key|secret[_-]?key|access[_-]?token)\s*[:=]\s*['\"][^'\"]{8,}", "明文密钥字段"),
    (r"(?i)authorization\s*:\s*bearer\s+[A-Za-z0-9\-\._]{8,}", "Bearer Token"),
    (r"(?i)(password|passwd)\s*[:=]\s*['\"][^'\"]{6,}", "明文口令"),
]

CODE_EXEC = [
    (r"\beval\s*\(", "eval()"),
    (r"new\s+Function\s*\(", "new Function()"),
    (r"document\.write\s*\(", "document.write()"),
    (r"\bexec\s*\(\s*[a-zA-Z_$]", "exec() 动态执行"),
]


def gate1_safety(html, low, text, topic, br, subject, cfg, engine="", scene=None):
    out = []
    bare = strip_namespaces(html)

    # G1-01 文档结构
    need = {
        "doctype": "<!doctype" in low,
        "html lang": bool(re.search(r"<html[^>]*\blang=", low)),
        "meta charset": bool(re.search(r'<meta[^>]+charset', low)),
        "title": "<title" in low and "</title>" in low,
        "body": "<body" in low,
    }
    miss = [k for k, v in need.items() if not v]
    out.append(mk("G1", "G1-01", "文档结构完整", "pass" if not miss else "fail",
                  "包含 doctype / html[lang] / charset / title / body",
                  "缺失：%s" % "、".join(miss) if miss else "结构完整",
                  "HTML 骨架不完整，部分浏览器会进入怪异模式" if miss else "文档结构完整",
                  advice="按模板补齐 <!doctype html>、lang、meta charset 与 title",
                  severity=CRITICAL, weight=4))

    # G1-02 无外部依赖（离线导出的前提）
    ext = [u for u in re.findall(r"https?://[^\s\"'<>)]+", bare)
           if not u.startswith("http://www.w3.org")]
    out.append(mk("G1", "G1-02", "无外部资源引用", "pass" if not ext else "fail",
                  "所有样式/脚本/图片均为本地或内联",
                  "发现 %d 个外链：%s" % (len(ext), "、".join(ext[:3])) if ext else "全部本地",
                  "断网教室打开会白屏" if ext else "可离线运行",
                  evidence="、".join(ext[:5]),
                  advice="把外部 CSS/JS/字体/图片下载到本地并改为相对路径",
                  severity=CRITICAL, weight=6))

    # G1-03 无网络请求代码
    net_api = [kw for kw in ("fetch(", "xmlhttprequest", "websocket", "eventsource") if kw in low]
    out.append(mk("G1", "G1-03", "无网络请求代码", "pass" if not net_api else "fail",
                  "不包含 fetch / XHR / WebSocket 调用",
                  "发现 %s" % "、".join(net_api) if net_api else "未发现网络请求",
                  "离线不可用" if net_api else "纯前端运行",
                  advice="移除网络调用，教学资源必须在无网环境可用",
                  severity=CRITICAL, weight=4))

    # G1-04 运行时零外部请求（真浏览器实测，比源码扫描更硬）
    net = (br or {}).get("network") or []
    if br is None:
        out.append(mk("G1", "G1-04", "运行时零外部请求", "skip",
                      "加载后不发起 file:// 之外的请求", "未执行浏览器检查",
                      "浏览器不可用，运行时网络无法验证", weight=3))
    else:
        out.append(mk("G1", "G1-04", "运行时零外部请求", "pass" if not net else "fail",
                      "加载后不发起 file:// 之外的请求",
                      "捕获 %d 个外部请求：%s" % (len(net), "、".join(net[:3])) if net else "零外部请求",
                      "运行时会联网，离线教室直接失败" if net else "运行时完全离线",
                      evidence="、".join(net[:5]),
                      advice="去掉 CDN 字体、统计埋点、远程图标等一切运行时请求",
                      severity=CRITICAL, weight=3))

    # G1-05 密钥泄露（规范 7.4：API 密钥绝不写入教师下载的单文件 HTML）
    leaks = []
    for pat, label in SECRET_PATTERNS:
        for m in re.finditer(pat, html):
            leaks.append("%s（%s…）" % (label, m.group(0)[:14]))
    out.append(mk("G1", "G1-05", "无密钥泄露", "pass" if not leaks else "fail",
                  "页面内不出现任何 API Key / Token / 口令",
                  "；".join(leaks[:3]) if leaks else "未发现密钥",
                  "密钥随页面发给教师，等于公开" if leaks else "无密钥泄露",
                  advice="把模型调用全部放在后端，HTML 只保留确定性计算",
                  severity=CRITICAL, weight=4))

    # G1-06 不执行任意代码（规范 7.4：模型返回的字符串不当代码执行）
    hard = [label for pat, label in CODE_EXEC if re.search(pat, html)]
    # 注意：\s* 会回溯，必须把空白也放进后视类，否则 innerHTML = '' 也会被判成变量赋值
    soft = bool(re.search(r"innerHTML\s*=\s*(?![\s'\"`])", html))
    if hard:
        out.append(mk("G1", "G1-06", "不执行动态代码", "fail",
                      "不使用 eval / new Function / document.write",
                      "发现 %s" % "、".join(hard),
                      "动态执行字符串等同于把模型输出当代码运行",
                      advice="改为确定性的状态更新函数，不要执行拼出来的字符串",
                      severity=CRITICAL, weight=3))
    elif soft:
        out.append(mk("G1", "G1-06", "不执行动态代码", "review",
                      "模型返回的文本按纯文本渲染",
                      "发现 innerHTML 赋值为变量",
                      "若该变量来自模型输出，存在把文本当 HTML 执行的风险",
                      advice="改用 textContent，或先做转义；静态模板字符串可以保留",
                      weight=3))
    else:
        out.append(mk("G1", "G1-06", "不执行动态代码", "pass",
                      "不使用 eval / new Function，不把变量直接写进 innerHTML",
                      "未发现动态执行", "页面只做确定性计算", weight=3))

    # G1-07 引擎与场景白名单（规范 7.3）
    engine = engine or cfg.get("scene_engine") or cfg.get("engine") \
        or (scene or {}).get("engine", "")
    scene_id = cfg.get("scene_id")
    if not engine and not scene_id:
        out.append(mk("G1", "G1-07", "引擎与场景白名单", "skip",
                      "scene_engine 取自 25 类白名单，scene_id 已注册",
                      "页面未声明引擎/场景配置", "无配置可比对，本项不适用", weight=3))
    else:
        ok, target = registry.engine_ok(subject, engine or "")
        problems = []
        if engine and not ok:
            problems.append("引擎「%s」不在%s的白名单内" % (engine, subject or "任何学科"))
        if scene_id and not registry.scene_of(scene_id):
            problems.append("场景「%s」未在 registry.SCENES 注册" % scene_id)
        if engine in registry.PROTOTYPE_MAP and not ok:
            problems.append("旧原型引擎「%s」不能直接当作规划引擎使用" % engine)
        status = "pass" if not problems else "fail"
        if not problems and scene_id and not registry.scene_of(scene_id):
            status = "review"
        out.append(mk("G1", "G1-07", "引擎与场景白名单", status,
                      "引擎取自 25 类白名单，场景与已审核注册表对应",
                      "；".join(problems) if problems
                      else "引擎 %s / 场景 %s" % (engine or "未声明", scene_id or "未登记"),
                      "不允许模型自由创造引擎名并执行" if problems else "配置在许可范围内",
                      evidence=str(cfg)[:200],
                      advice="在 registry.ENGINES/SCENES 中登记该引擎与场景，并补充 required 与 facts 绑定",
                      severity=CRITICAL, weight=3))

    # G1-08 数值安全范围（沿用 topics 阈值，警示语境豁免）
    WARN_CONTEXT = ("禁止", "严禁", "不得", "切勿", "不可", "不要", "避免", "危险", "超出", "量程")
    profile = profile_of(topic)
    limits = profile.get("数值上限") or []
    if not limits:
        out.append(mk("G1", "G1-08", "数值安全范围", "skip",
                      "参数落在真实器材范围内", "该主题未配置安全阈值",
                      "主题未识别，阈值检查不适用", weight=3))
    else:
        bad_all, exempted = [], 0
        for item in limits:
            pat = r"(\d+(?:\.\d+)?)\s*%s(?![a-zA-Z])" % unit_pattern(item["单位"])
            for m in re.finditer(pat, text):
                v = float(m.group(1))
                if v <= item["上限"]:
                    continue
                # Dimensional identities such as "1 A = 1 V/Ω" name the
                # ampere unit; they are not proposed apparatus settings.
                tail = text[m.end():m.end() + 18]
                if re.match(r"\s*(?:=|≈|等于)\s*\d", tail):
                    continue
                ctx_s = text[max(0, m.start() - 14):m.start()]
                if any(w in ctx_s for w in WARN_CONTEXT):
                    exempted += 1
                    continue
                bad_all.append("%g %s" % (v, item["单位"]))
        rule = "、".join("%s≤%s %s" % (i["名称"], i["上限"], i["单位"]) for i in limits)
        out.append(mk("G1", "G1-08", "数值安全范围", "pass" if not bad_all else "fail",
                      rule,
                      "越界值：%s" % "、".join(bad_all[:4]) if bad_all
                      else ("另有 %d 处超限值出现在警示语中，属正确用法" % exempted if exempted else "未出现越界值"),
                      "参数超出真实器材范围，可能被当成真实操作依据" if bad_all else "数值在安全范围内",
                      advice="参数上限按真实器材设定：%s；警示语里提到超限值请加「禁止」" % rule,
                      severity=MAJOR, weight=3))
    return out


# ============ 第2关：资源完整性 ============

def gate2_assets(html, low, text, br, html_path):
    out = []

    def section(sec):
        for s in (br or {}).get("sections") or []:
            if s.get("id") == sec["id"]:
                return s
        return None

    # G2-01 六区域容器齐全（规范 2.1）
    missing = []
    for sec in registry.SECTIONS:
        found = re.search(r'id=["\']%s["\']' % re.escape(sec["id"]), html) \
            or re.search(r'class=["\'][^"\']*\b%s\b' % re.escape(sec["cls"]), html)
        if not found:
            missing.append(sec["name"])
    out.append(mk("G2", "G2-01", "六区域容器齐全", "pass" if not missing else "fail",
                  "①实验信息 ②实验演示 ③参数与操作 ④结果与反馈 ⑤实验记录 ⑥教学说明",
                  "缺失：%s" % "、".join(missing) if missing else "六区域齐全",
                  "没有六区域就无法按统一界面交付" if missing else "六区域结构与规范一致",
                  advice="按 frame/shell.html 补上缺失的 section，id 用 sec-info/sec-stage/…",
                  severity=CRITICAL, weight=5))

    # G2-02 六区域内容非空
    if not br:
        out.append(mk("G2", "G2-02", "六区域内容非空", "skip",
                      "每个区域都有实际内容，不出现「待补充」", "未执行浏览器检查",
                      "浏览器不可用，区域渲染无法验证", weight=5))
    else:
        empty = [s["name"] for s in br.get("sections") or []
                 if s.get("存在") and s.get("空")]
        absent = [s["name"] for s in br.get("sections") or [] if not s.get("存在")]
        if absent:
            out.append(mk("G2", "G2-02", "六区域内容非空", "fail",
                          "六个区域都存在且都有实际内容",
                          "未渲染出：%s" % "、".join(absent),
                          "区域没渲染，学生看到的是空白", weight=5, severity=CRITICAL))
        else:
            out.append(mk("G2", "G2-02", "六区域内容非空", "pass" if not empty else "fail",
                          "六个区域都存在且都有实际内容",
                          "内容过少：%s" % "、".join(empty) if empty else "六区域均有内容",
                          "空区域等于页面上有个洞" if empty else "六区域内容完整",
                          advice="把缺失区域补全；确实不适用的区域要写明原因，不能留空",
                          severity=MAJOR, weight=5))

    # G2-03 外壳与本页资源可解析（相对路径必须真的存在）
    refs = re.findall(r'(?:href|src)=["\']([^"\'#?]+)["\']', html)
    # mailto:/tel:/javascript: 是协议不是文件路径，别当成缺失资源
    local = [r for r in refs
             if not r.startswith(("http", "data:", "//")) and not re.match(r"^[a-zA-Z][\w+.-]*:", r)]
    base = os.path.dirname(os.path.abspath(html_path))
    gone = [r for r in local if not os.path.exists(os.path.join(base, r))]
    if gone:
        pack = [r for r in gone if r.lower().endswith((".zip", ".rar", ".7z"))]
        asset = [r for r in gone if r not in pack]
        if asset:
            out.append(mk("G2", "G2-03", "本地资源可解析", "fail",
                          "样式/脚本/图片等相对路径引用的文件都在同目录",
                          "缺失：%s" % "、".join(asset[:4]),
                          "只发 HTML 会没样式/没 logo", evidence="、".join(asset[:5]),
                          advice="交付时把 html + frame.css + exp.css + logo.png 一起打包",
                          severity=MAJOR, weight=4))
        else:
            out.append(mk("G2", "G2-03", "本地资源可解析", "review",
                          "下载弹窗指向的压缩包应随案例一起交付",
                          "压缩包未生成：%s" % "、".join(pack[:2]),
                          "页面能正常显示，但「下载本案例」会 404",
                          advice="打包时把 zip 放到与 html 同目录，或改为指向资源目录",
                          severity=MINOR, weight=4))
    else:
        out.append(mk("G2", "G2-03", "本地资源可解析", "pass",
                      "所有相对路径引用的文件都在同目录",
                      "%d 个本地引用全部存在" % len(local),
                      "资源随页面完整交付", weight=4))

    # G2-04 演示画布存在（规范 2.2 ②）
    has_canvas = "<canvas" in low or "<svg" in low
    out.append(mk("G2", "G2-04", "演示画布存在", "pass" if has_canvas else "fail",
                  "②区至少有一个 canvas 或 svg",
                  "canvas %d 个，svg %d 个" % (low.count("<canvas"), low.count("<svg")),
                  "没有画布就不是交互实验，只是读数面板" if not has_canvas else "有可视化画布",
                  advice="用 canvas/svg 画出实验对象与过程，不要只放数字",
                  severity=CRITICAL, weight=4))

    # G2-14 ②区只允许状态驱动的绘图，不能用静态图片代替交互演示
    stage = re.search(r'<section\b[^>]*\bid=["\']sec-stage["\'][^>]*>(.*?)</section>',
                      html, re.I | re.S)
    stage_html = stage.group(1) if stage else ""
    image_refs = re.findall(r'<(?:img|image|picture|video)\b[^>]*>|url\s*\([^)]*\)', stage_html, re.I)
    runtime_images = (br or {}).get("stageImages") or []
    if not stage:
        out.append(mk("G2", "G2-14", "演示区不嵌入图片素材", "skip",
                      "②区使用 Canvas/SVG/DOM 状态驱动绘图，不插入静态图片",
                      "没有解析到 sec-stage", "区域结构检查已由 G2-01 报告", weight=3))
    elif image_refs or runtime_images:
        found = image_refs + ["runtime:%s#%s" % (x.get("tag", ""), x.get("id", ""))
                              for x in runtime_images]
        out.append(mk("G2", "G2-14", "演示区不嵌入图片素材", "fail",
                      "②区使用 Canvas/SVG/DOM 状态驱动绘图，不插入静态图片",
                      "发现 %d 个图片节点或背景图片：%s" % (len(found), "；".join(found[:3])[:180]),
                      "静态图片不能响应参数变化，会让演示与实验状态脱节",
                      evidence="；".join(found[:4])[:300],
                      advice="移除演示区的 img/SVG image/背景图片，改用实时 Canvas/SVG 绘制；需要配图时放在演示区之外",
                      severity=CRITICAL, weight=3))
    else:
        out.append(mk("G2", "G2-14", "演示区不嵌入图片素材", "pass",
                      "②区使用 Canvas/SVG/DOM 状态驱动绘图，不插入静态图片",
                      "演示区未发现图片节点或 CSS url()",
                      "主演示通过网页图形绘制，不依赖静态图片", weight=3))

    # G2-05 关键控件数量（规范 2.2 ③ 建议 2–4 个）
    ranges = (br or {}).get("ranges") or {}
    n_range = ranges.get("count", 0)
    n_btn = (br or {}).get("buttons", 0)
    if br is None:
        out.append(mk("G2", "G2-05", "关键控件数量", "skip",
                      "2–4 个关键参数控件", "未执行浏览器检查，无法枚举控件",
                      "静态条件下无法统计控件", weight=3))
    elif n_range == 0 and n_btn == 0:
        out.append(mk("G2", "G2-05", "关键控件数量", "fail",
                      "2–4 个关键参数控件", "既没有滑块也没有按钮",
                      "学生没有任何可操作的入口", severity=CRITICAL, weight=3))
    elif n_range > 4:
        out.append(mk("G2", "G2-05", "关键控件数量", "fail",
                      "2–4 个关键参数控件", "%d 个滑块 + %d 个按钮" % (n_range, n_btn),
                      "控件过多会稀释探究重点", severity=MINOR, weight=3,
                      advice="保留与结论直接相关的 2–4 个变量，其余改为固定常量"))
    else:
        out.append(mk("G2", "G2-05", "关键控件数量", "pass",
                      "2–4 个关键参数控件", "%d 个滑块 + %d 个按钮" % (n_range, n_btn),
                      "控件数量合适", weight=3))

    # G2-06 实验记录区（规范 2.3 建议 3 条以上）
    has_table = "<table" in low
    out.append(mk("G2", "G2-06", "实验记录区", "pass" if has_table else "fail",
                  "⑤区有数据表或步骤日志，可记录 3 条以上",
                  "table %d 个" % low.count("<table"),
                  "没有记录区，探究过程无法留痕" if not has_table else "有记录表",
                  advice="固定表头 + 空 tbody，由脚本追加行，不覆盖历史",
                  severity=MAJOR, weight=3))

    # G2-07 重置按钮（规范 2.3 必做：必须回到同一初始状态）
    reset = (br or {}).get("reset") or {}
    if not br:
        out.append(mk("G2", "G2-07", "具备重置功能", "skip",
                      "有「重置」并能回到初始状态", "未执行浏览器检查",
                      "浏览器不可用，重置无法验证", weight=4))
    else:
        if not reset.get("found"):
            out.append(mk("G2", "G2-07", "具备重置功能", "fail",
                          "有「重置」并能回到初始状态", "页面上找不到重置按钮",
                          "讲完一轮无法复位，下一个学生接手时状态是乱的",
                          advice="加一个重置按钮：把 state 恢复默认值后调用同一个 render()",
                          severity=CRITICAL, weight=4))
        else:
            out.append(mk("G2", "G2-07", "具备重置功能", "pass" if reset.get("restored") else "fail",
                          "点重置后与首屏状态完全一致",
                          "已回到初态" if reset.get("restored")
                          else "重置后状态与首屏不一致（机读数据差异=%s，文本差异≈%s 字）"
                               % (reset.get("dataDiff"), reset.get("textDiff")),
                          "重置没回到同一初始状态，两轮实验的数据不可比"
                          if not reset.get("restored") else "重置有效",
                          evidence=str(reset.get("resetText", ""))[:160],
                          advice="reset 里逐个恢复每个参数与状态变量，再调用 render()，不要只清记录表",
                          severity=MAJOR, weight=4))

    # G2-08 CSV 导出（规范 2.3 数值实验建议）
    csv_ok = bool((br or {}).get("csv", {}).get("found")) or bool(re.search(r"csv", low))
    out.append(mk("G2", "G2-08", "CSV 导出", "pass" if csv_ok else "review",
                  "数值型实验提供「导出 CSV」", "已提供" if csv_ok else "未提供导出",
                  "可以把数据带到 Excel 里继续分析" if csv_ok else "数值实验建议补一个导出（非必做）",
                  advice="用 Blob + URL.createObjectURL 生成 CSV，与表格共用同一份数据",
                  severity=MINOR, weight=1))

    # G2-09 首屏即可用（不做任何操作就有完整数据）
    result_sec = section({"id": "sec-result"}) or {}
    sample = result_sec.get("text") or ""
    has_number = bool(re.search(r"\d", sample)) or bool(
        re.search(r"\d+(?:\.\d+)?\s*(?:V|A|Ω|N|kg|m|°|%|mol|g|个|条)", text))
    if br and not result_sec.get("存在"):
        out.append(mk("G2", "G2-09", "首屏数据完整", "fail",
                      "打开页面不操作就能在④区看到读数",
                      "页面上找不到④结果与反馈区",
                      "没有结果区，学生看不到任何反馈",
                      advice="按六区域补上 sec-result，并在首屏渲染一次",
                      severity=MAJOR, weight=3))
    else:
        out.append(mk("G2", "G2-09", "首屏数据完整", "pass" if has_number else "fail",
                      "打开页面不操作就能看到读数",
                      "④区有数值" if has_number else "④区未见到数值",
                      "首屏空着，学生不知道从哪开始" if not has_number else "首屏即有完整数据",
                      advice="脚本末尾无条件调用一次 render()，不要等用户先拖滑块",
                      severity=MAJOR, weight=3))

    # ---------- 文字可读性：文字不得被任何图像遮住 ----------
    # 判定原料来自 checks_browser.js 的注入式取证：
    #   画布内 = 后绘制的图元盖住先绘制的文字；DOM 层 = 文字位置最上层是 canvas/img/svg。
    ov = (br or {}).get("textOverlap") or {}
    cvs = ov.get("canvas") or {}
    dom = ov.get("dom") or {}
    dom_issues = dom.get("issues") or []
    cvs_covered = cvs.get("covered") or []
    cvs_out = cvs.get("outOfBounds") or []

    # G2-10 DOM 文字被图形层压住
    if not br:
        out.append(mk("G2", "G2-10", "文字不被图形遮挡", "skip",
                      "页面上每段文字的最上层都是文字本身",
                      "未执行浏览器取证", "没有浏览器数据，无法判定遮挡",
                      weight=5))
    elif dom_issues:
        detail = "；".join(
            "「%s」被 %s 覆盖(%s)" % (x.get("text", "")[:18], x.get("coveredBy", "?"), x.get("points", ""))
            for x in dom_issues[:3])
        out.append(mk("G2", "G2-10", "文字不被图形遮挡", "fail",
                      "页面上每段文字的最上层都是文字本身，不被画布/图片压住",
                      "%d 处文字被图形层覆盖：%s" % (len(dom_issues), detail),
                      "文字被图像盖住会直接影响可读性，学生看不到参数和读数",
                      evidence="视口：%s" % "、".join(sorted({x.get("viewport", "") for x in dom_issues})),
                      advice="把画布限制在 sec-stage 内，不要让 canvas 绝对定位盖到参数区/结果区；"
                             "浮动标签用 .exp-canvas-tip 并给实底背景",
                      severity=CRITICAL, weight=5))
    else:
        out.append(mk("G2", "G2-10", "文字不被图形遮挡", "pass",
                      "页面上每段文字的最上层都是文字本身",
                      "%d 段文字实测未被 canvas/img/svg 覆盖" % (dom.get("checked") or 0),
                      "DOM 层文字均在最上层",
                      weight=5))

    # G2-11 画布内文字被后绘制的图元盖住
    if not br:
        out.append(mk("G2", "G2-11", "画布内文字不被图元遮盖", "skip",
                      "先画图元、后画标注，文字始终在最上层",
                      "未执行浏览器取证", "没有浏览器数据，无法判定遮挡", weight=4))
    elif not cvs.get("textCount"):
        out.append(mk("G2", "G2-11", "画布内文字不被图元遮盖", "skip",
                      "先画图元、后画标注，文字始终在最上层",
                      "画布内未绘制文字", "本页没有画布文字，此项不适用", weight=4))
    elif cvs_covered:
        detail = "；".join("「%s」被 %s 盖住 %d%%" % (c.get("text", "")[:16], c.get("by", "图元"),
                                                    round((c.get("ratio") or 0) * 100))
                          for c in cvs_covered[:3])
        out.append(mk("G2", "G2-11", "画布内文字不被图元遮盖", "fail",
                      "文字在最后一步绘制，不被任何后续填充覆盖",
                      "%d 段画布文字被后绘制的图元覆盖：%s" % (len(cvs_covered), detail),
                      "标注被图形盖住，等于这段字没写",
                      evidence="最严重覆盖比例 %.0f%%" % ((cvs.get("worst") or 0) * 100),
                      advice="把所有 fillText 集中到 draw() 末尾（图元 → 标注 → 数值），"
                             "并在文字下先铺一层半透明底衬",
                      severity=CRITICAL, weight=4))
    else:
        out.append(mk("G2", "G2-11", "画布内文字不被图元遮盖", "pass",
                      "文字在最后一步绘制，不被任何后续填充覆盖",
                      "%d 段画布文字均未被后续图元覆盖" % cvs.get("textCount"),
                      "绘制顺序正确", weight=4))

    # G2-12 画布内文字出界（被画布边缘裁掉）
    if not br:
        out.append(mk("G2", "G2-12", "画布内文字不被裁切", "skip",
                      "文字包围盒完整落在画布内并留安全边距",
                      "未执行浏览器取证", "没有浏览器数据，无法判定裁切", weight=3))
    elif not cvs.get("textCount"):
        out.append(mk("G2", "G2-12", "画布内文字不被裁切", "skip",
                      "文字包围盒完整落在画布内并留安全边距",
                      "画布内未绘制文字", "本页没有画布文字，此项不适用", weight=3))
    elif cvs_out:
        detail = "；".join("「%s」box=%s 画布=%s" % (o.get("text", "")[:14],
                                                  ",".join(map(str, o.get("box") or [])),
                                                  ",".join(map(str, o.get("canvas") or [])))
                          for o in cvs_out[:3])
        out.append(mk("G2", "G2-12", "画布内文字不被裁切", "fail",
                      "文字包围盒完整落在画布内并留 ≥8px 安全边距",
                      "%d 段文字超出画布被裁切：%s" % (len(cvs_out), detail),
                      "文字出了画布边界，学生只能看到半截字",
                      advice="标注靠近边缘时改对齐方式或在绘制前夹取坐标；"
                             "导轨末端刻度、轴名要留出安全边距",
                      severity=CRITICAL, weight=3))
    else:
        out.append(mk("G2", "G2-12", "画布内文字不被裁切", "pass",
                      "文字包围盒完整落在画布内并留 ≥8px 安全边距",
                      "%d 段文字全部在画布内" % cvs.get("textCount"),
                      "无文字被裁切", weight=3))

    # G2-13 画布文字不得撞上卡片边框或其他文字（G2-11 只覆盖后绘制填充，抓不到 strokeRect）
    border_hits = cvs.get("borderOverlap") or []
    text_hits = cvs.get("textOverlaps") or []
    if not br:
        out.append(mk("G2", "G2-13", "画布文字与边框/文字不冲突", "skip",
                      "画布标注不与面板边框或其他标注重叠", "未执行浏览器取证",
                      "没有动态绘制数据，无法判断边框与文字布局", weight=4))
    elif border_hits or text_hits:
        samples = []
        samples.extend("「%s」撞边框(%d%%)" % (x.get("text", "")[:16], round((x.get("ratio") or 0) * 100))
                       for x in border_hits[:3])
        samples.extend("「%s」与「%s」重叠(%d%%)" % (x.get("first", "")[:12], x.get("second", "")[:12],
                                                    round((x.get("ratio") or 0) * 100))
                       for x in text_hits[:3])
        out.append(mk("G2", "G2-13", "画布文字与边框/文字不冲突", "fail",
                      "文字与面板描边、相邻标注之间留出可读间距",
                      "%d 处边框冲突、%d 处文字重叠：%s"
                      % (len(border_hits), len(text_hits), "；".join(samples)),
                      "描边穿过文字或标注互相盖住，文字不可读",
                      evidence=str((border_hits[:2], text_hits[:2])),
                      advice="扩大卡片留白并把文字放回内边距内；调整标签锚点/行距，避免文字包围盒相交",
                      severity=CRITICAL, weight=4))
    else:
        out.append(mk("G2", "G2-13", "画布文字与边框/文字不冲突", "pass",
                      "文字与面板描边、相邻标注之间留出可读间距",
                      "%d 段画布文字未与卡片描边或其他文字相撞" % cvs.get("textCount", 0),
                      "画布内标注留有可读间距", weight=4))

    # G2-15 防止对象被隐式转成用户可见的 [object Object]
    bad_canvas_text = cvs.get("badText") or []
    bad_dom_text = (br or {}).get("stageBadText") or []
    if bad_canvas_text or bad_dom_text:
        examples = [x.get("text", "") for x in bad_canvas_text[:2]] + [x.get("text", "") for x in bad_dom_text[:2]]
        out.append(mk("G2", "G2-15", "演示文字无对象占位符", "fail",
                      "演示区只显示面向学生的文字，不显示 JavaScript 对象默认字符串",
                      "检测到 %d 处对象占位文字：%s" % (len(bad_canvas_text) + len(bad_dom_text), "；".join(examples)),
                      "[object Object] 是程序对象被当作字符串显示，通常意味着标签配置类型错误",
                      evidence=str((bad_canvas_text[:2], bad_dom_text[:2])),
                      advice="传入明确的标签字符串；对象参数先读取 name/title/label 字段，不要直接拼接对象",
                      severity=CRITICAL, weight=5))
    else:
        out.append(mk("G2", "G2-15", "演示文字无对象占位符", "pass",
                      "演示区只显示面向学生的文字",
                      "画布和 DOM 演示内容中没有 [object Object] 占位文字",
                      "未发现对象默认字符串", weight=5))

    # G2-16 化学场景不能把毫升/升单位错配后画成空杯
    chem_scene = (br or {}).get("chemScene") or {}
    if not chem_scene:
        out.append(mk("G2", "G2-16", "化学场景液量可见", "skip",
                      "共享化学场景的液量换算后应对应可见液面",
                      "页面未暴露 CHEM 场景状态", "仅适用于使用 CHEM.scene 的页面", weight=3))
    elif chem_scene.get("type") == "stages":
        nstages = chem_scene.get("count", 0)
        out.append(mk("G2", "G2-16", "化学场景液量可见", "pass" if nstages else "fail",
                      "阶段式化学场景按配置展示过程器材",
                      "统一化学阶段场景 %s 个" % nstages,
                      "阶段版式已采用统一化学器材风格",
                      severity=CRITICAL if not nstages else MINOR, weight=3))
    else:
        volume_ml = chem_scene.get("volumeMl")
        fill = chem_scene.get("fillFraction")
        invalid_volume = (not isinstance(volume_ml, (int, float)) or not isinstance(fill, (int, float))
                          or volume_ml < 5 or fill < 0.05 or fill > 1)
        if invalid_volume:
            out.append(mk("G2", "G2-16", "化学场景液量可见", "fail",
                          "液量单位应明确为 mL，且画面液面不能接近空杯或越过杯口",
                          "场景记录液量 %s mL、液面比例 %s" % (volume_ml, fill),
                          "化学场景把 L 当成 mL 会令液面几乎消失",
                          advice="CHEM.scene 的 V 用 mL；升值先乘 1000，或传 V_mL",
                          severity=CRITICAL, weight=3))
        else:
            out.append(mk("G2", "G2-16", "化学场景液量可见", "pass",
                          "液量单位应明确为 mL，且画面液面不能接近空杯或越过杯口",
                          "场景记录液量 %.1f mL（液面比例 %.0f%%）" % (volume_ml, fill * 100),
                          "场景液量处在可见范围内", weight=3))

    return out


# ============ 第3关：学科判据 ============

def gate3_subject(ctx, subject):
    if not subject:
        return [mk("G3", "G3-00", "学科判据可执行", "review",
                   "识别学科后按 J1–J8 配置校验",
                   "未能识别学科（需求与页面都没有学科信息）",
                   "没有学科就无法选择判据组合",
                   advice="在需求 JSON 中给出「学科」，或在页面①区标注学科", weight=0)]
    judges = registry.subject_judges(subject)
    out = judge_lib.run(judges, ctx)
    # 引擎的首选判据若不在学科组合里，补一条提示
    engine = ctx.get("engine")
    for j in registry.ENGINE_JUDGES.get(engine or "", []):
        if j not in judges:
            out.append(mk("G3", "G3-99", "引擎首选判据未覆盖", "review",
                          "引擎 %s 的首选判据为 %s" % (engine, "、".join(registry.ENGINE_JUDGES[engine])),
                          "学科「%s」当前只跑 %s" % (subject, "、".join(judges)),
                          "引擎与学科的判据组合不一致，需确认是否有意省略",
                          advice="在 registry.SUBJECT_JUDGES 中补充该判据，或说明省略理由",
                          weight=0, judge=j))
    return out


# ============ 第4关：浏览器测试 ============

def infer_visual_type(text):
    """旧页面未声明绘图类型时按主题粗略识别，避免对图表强套器材质感阈值。"""
    t = text or ""
    if any(k in t for k in ("球棍模型", "分子式", "原子总数", "键角")):
        return "molecular"
    if any(k in t for k in ("二次函数", "函数图像", "抛物线", "坐标轴", "函数曲线")):
        return "graph"
    if any(k in t for k in ("截面边数", "平面截正方体", "外接球", "立体几何", "空间几何", "椭圆离心率")):
        return "geometry"
    if any(k in t for k in ("反应时间", "开始反应", "反应阶段", "过程演示")):
        return "process"
    if any(k in t for k in ("实验器材", "弹簧测力计", "烧杯", "试管", "电路", "量筒",
                            "杠杆", "浮力", "电阻", "动量", "光具座", "反应实验")):
        return "apparatus"
    return ""


def verify_circuit_samples(br):
    """Compare browser JS solver outputs to this independent Python MNA oracle."""
    def diagram_signature(model):
        parts = []
        for c in model.get("components") or []:
            kind = str(c.get("type", "")).lower().replace("-", "_")
            if kind == "voltagesource":
                kind = "voltage_source"
            if kind == "currentsource":
                kind = "current_source"
            start = c.get("from") if c.get("from") is not None else c.get("positive")
            end = c.get("to") if c.get("to") is not None else c.get("negative")
            switch = ("1" if c.get("closed") else "0") if kind == "switch" else "-"
            parts.append("|".join((str(c.get("id", "")), kind, str(start), str(end), switch)))
        return ";".join(sorted(parts))

    circuit = (br or {}).get("circuit") or {}
    samples = circuit.get("samples") or []
    if not samples:
        return {"checked": False, "ok": False,
                "actual": "浏览器未暴露 window.__CIRCUIT_MODEL__ 与 window.__CIRCUIT_RESULT__"}
    checked = 0
    for sample in samples[:12]:
        model, actual = sample.get("model"), sample.get("result")
        if not isinstance(model, dict) or not isinstance(actual, dict):
            return {"checked": True, "ok": False,
                    "actual": "%s: 电路模型或结果不是对象" % sample.get("label", "state")}
        components = model.get("components") or []
        if len(components) > 80:
            return {"checked": True, "ok": False,
                    "actual": "电路元件数超过审查上限 80，拒绝执行过大模型"}
        expected_signature = diagram_signature(model)
        actual_signature = sample.get("diagramSignature")
        if not actual_signature or actual_signature != expected_signature:
            return {"checked": True, "ok": False,
                    "actual": "%s: 电路图未由当前 netlist 绘制，或图示拓扑签名与模型不一致" % sample.get("label", "state"),
                    "advice": "每次 render 调用 CIRCUIT.draw(cv, model, solverResult)，不要另画独立导线图"}
        try:
            expected = solve_circuit(model)
        except CircuitError as exc:
            return {"checked": True, "ok": False,
                    "actual": "%s: 独立求解器拒绝该拓扑（%s）" % (sample.get("label", "state"), exc),
                    "advice": "检查节点连通、开关状态、电源极性和元件参数；奇异/不安全电路应在页面显示错误状态"}
        except Exception as exc:  # noqa: BLE001
            return {"checked": True, "ok": False,
                    "actual": "%s: 独立求解器错误（%s）" % (sample.get("label", "state"), exc)}

        # For the initial state of a requested Ohm-law experiment, a closed
        # switch and non-zero source must produce a conducting load current.
        # A mathematically solvable dead-end branch can satisfy KCL/KVL while
        # still failing to demonstrate the requested experiment.
        if sample.get("label") == "initial":
            components = model.get("components") or []
            sources = [c for c in components if str(c.get("type", "")).lower().replace("-", "_") == "voltage_source"]
            all_switches_closed = all(bool(c.get("closed")) for c in components
                                      if str(c.get("type", "")).lower() == "switch")
            ammeters = [c for c in components if str(c.get("type", "")).lower() == "ammeter"]
            energized = any(abs(float(c.get("volts", 0) or 0)) > 1e-9 for c in sources)
            if energized and all_switches_closed and ammeters and all(
                    abs(expected["branches"].get(str(c.get("id")), {}).get("current", 0)) < 1e-9
                    for c in ammeters):
                return {"checked": True, "ok": False,
                        "actual": "initial: 电源有电压且开关闭合，但电流表支路电流为 0；电路没有形成有效闭合实验回路",
                        "advice": "把被测电阻串入电源正负端之间的闭合回路，确认电流表串联在回路中"}

        exp_nodes, act_nodes = expected.get("nodes", {}), actual.get("nodes", {})
        exp_branches, act_branches = expected.get("branches", {}), actual.get("branches", {})
        if not isinstance(act_nodes, dict) or not isinstance(act_branches, dict):
            return {"checked": True, "ok": False,
                    "actual": "%s: 结果缺少 nodes/branches" % sample.get("label", "state")}
        for key, value in exp_nodes.items():
            got = act_nodes.get(key)
            if not isinstance(got, (int, float)) or abs(float(got) - value) > max(1e-7, abs(value) * 1e-6):
                return {"checked": True, "ok": False,
                        "actual": "%s 节点 %s：参考 %.9g V，页面求解器 %s" % (sample.get("label", "state"), key, value, got)}
        for key, branch in exp_branches.items():
            got = act_branches.get(key)
            if not isinstance(got, dict):
                return {"checked": True, "ok": False,
                        "actual": "%s 缺少支路 %s" % (sample.get("label", "state"), key)}
            for field, unit in (("voltage", "V"), ("current", "A"), ("power", "W")):
                value = branch[field]
                actual_value = got.get(field)
                tol = max(1e-7, abs(value) * 1e-6)
                if not isinstance(actual_value, (int, float)) or abs(float(actual_value) - value) > tol:
                    return {"checked": True, "ok": False,
                            "actual": "%s 支路 %s 的 %s：参考 %.9g %s，页面求解器 %s" %
                                     (sample.get("label", "state"), key, field, value, unit, actual_value)}
        readings = sample.get("readings") or []
        if not readings:
            return {"checked": True, "ok": False,
                    "actual": "%s: 页面没有带支路绑定标记的电流表/电压表读数" % sample.get("label", "state"),
                    "advice": "给读数元素添加 data-circuit-current-for 或 data-circuit-voltage-for，并绑定实际测量支路元件 id"}
        for reading in readings:
            cid = str(reading.get("component", ""))
            field = "current" if reading.get("kind") == "current" else "voltage"
            branch = exp_branches.get(cid)
            raw_components = model.get("components") or []
            component_by_id = {str(c.get("id", "")): c for c in raw_components}
            shown = reading.get("value")
            if branch is None or not isinstance(shown, (int, float)):
                return {"checked": True, "ok": False,
                        "actual": "%s: %s 表读数绑定了无效元件或非数值内容（id=%s，文本=%s）" %
                                 (sample.get("label", "state"), field, cid, reading.get("text", ""))}
            if reading.get("bound") is not True:
                return {"checked": True, "ok": False,
                        "actual": "%s: %s 表 %s 没有由 CIRCUIT.bindMeters 绑定" %
                                 (sample.get("label", "state"), field, cid),
                        "advice": "在每次 render 的求解之后调用 CIRCUIT.bindMeters(solverResult)"}
            target_component = component_by_id.get(cid, {})
            target_type = str(target_component.get("type", "")).lower().replace("-", "_")
            if field == "current" and target_type != "ammeter":
                return {"checked": True, "ok": False,
                        "actual": "%s: 电流表示数绑定到 %s（%s），不是网表中的 ammeter 元件" %
                                 (sample.get("label", "state"), cid, target_type or "未知元件"),
                        "advice": "电流表读数必须测量真实的串联 ammeter 支路；不能把电流源或普通电阻当电流表"}
            if field == "voltage" and target_type in ("resistor", "voltmeter"):
                def endpoints(c):
                    a = c.get("from", c.get("positive")); b = c.get("to", c.get("negative"))
                    return frozenset((str(a), str(b)))
                meter_components = [c for c in raw_components
                                    if str(c.get("type", "")).lower().replace("-", "_") == "voltmeter"]
                if not any(endpoints(c) == endpoints(target_component) for c in meter_components):
                    return {"checked": True, "ok": False,
                            "actual": "%s: 电压表没有并联在被测支路 %s 的两个端点上" %
                                     (sample.get("label", "state"), cid),
                            "advice": "voltmeter 的 from/to 必须与 data-circuit-voltage-for 指定的电阻支路端点相同"}
            expected_value = branch[field]
            tol = max(0.005, abs(expected_value) * 0.02)
            if abs(float(shown) - expected_value) > tol:
                return {"checked": True, "ok": False,
                        "actual": "%s: %s 表 %s 显示 %s，参考值 %.6g" %
                                 (sample.get("label", "state"), field, cid, shown, expected_value)}
        checks = actual.get("checks") or {}
        if checks.get("ok") is not True:
            return {"checked": True, "ok": False,
                    "actual": "%s：页面求解器的 KCL/电源/功率守恒检查未通过" % sample.get("label", "state")}
        checked += 1
    return {"checked": checked > 0, "ok": checked > 0,
            "actual": "独立 MNA 对拍通过 %d 个状态（首屏与滑块/选择器操作后）" % checked,
            "advice": "继续扩充边界拓扑样例，重点覆盖断路、短路和并联分支"}

def gate4_browser(br, reason, text=""):
    if br is None:
        return [mk("G4", "G4-00", "浏览器测试", "skip",
                   "加载、点击、参数变化、重置、离线运行",
                   "未执行：%s" % reason,
                   "没有动态验证，可运行性只能算「未验证」",
                   advice="安装 playwright 后重跑", weight=1)]

    out = []
    if br.get("fatal"):
        out.append(mk("G4", "G4-01", "页面可以打开", "fail",
                      "浏览器能正常加载", "打开失败：%s" % br["fatal"],
                      "页面根本打不开", advice="检查 HTML 结构与脚本语法",
                      severity=CRITICAL, weight=3))
        return out

    out.append(mk("G4", "G4-01", "页面可以打开", "pass",
                  "浏览器能正常加载", "加载耗时 %d ms" % br.get("loadMs", 0),
                  "页面可加载", weight=3))

    errors = br.get("errors") or []
    out.append(mk("G4", "G4-02", "无 JS 运行时错误", "pass" if not errors else "fail",
                  "控制台零报错、零未捕获异常",
                  "无报错" if not errors else "%d 条：%s" % (len(errors), "；".join(errors[:3])),
                  "有报错时后续交互随时可能失效" if errors else "脚本运行干净",
                  advice="常见原因：DOM 取到 null、函数名拼错、脚本早于元素执行",
                  severity=CRITICAL, weight=4))

    if br.get("circuitRequired") or re.search(r"欧姆定律|电路|电流表|电压表", text or ""):
        cc = br.get("circuitCheck")
        if not cc or not cc.get("checked"):
            out.append(mk("G4", "G4-13", "电路仿真与独立求解器对拍", "fail",
                          "页面暴露电路模型/求解结果，且初始与参数变化后的结果均与独立 MNA 求解一致",
                          (cc or {}).get("actual", "未发现可对拍的电路模型或浏览器样本"),
                          "页面读数还没有被独立电路求解器验证",
                          advice="调用 CIRCUIT.solve(model)，暴露 window.__CIRCUIT_MODEL__ 与 window.__CIRCUIT_RESULT__，并将读数绑定到求解结果",
                          severity=CRITICAL, weight=5))
        else:
            out.append(mk("G4", "G4-13", "电路仿真与独立求解器对拍",
                          "pass" if cc.get("ok") else "fail",
                          "页面暴露电路模型/求解结果，且初始与参数变化后的结果均与独立 MNA 求解一致",
                          cc.get("actual", ""),
                          "页面与独立电路模型结果一致" if cc.get("ok") else "页面计算或机读读数偏离独立求解结果",
                          advice=cc.get("advice", "检查电路拓扑映射、元件值及页面读数是否来自同一结果对象"),
                          severity=CRITICAL, weight=5))

    r = br.get("ranges") or {}
    if r.get("count", 0) == 0:
        out.append(mk("G4", "G4-03", "参数变化有响应", "skip",
                      "拖动任一滑块，读数/图像/代入式至少一处变化",
                      "页面没有滑块", "无滑块可测，本项不适用", weight=3))
    else:
        ok = r.get("responsive", 0) == r.get("count", 0)
        out.append(mk("G4", "G4-03", "参数变化有响应", "pass" if ok else "fail",
                      "拖动每个滑块都有可见变化",
                      "%d/%d 个滑块拖动后有变化" % (r.get("responsive", 0), r.get("count", 0)),
                      "有滑块拖了没反应，学生无法改变自变量" if not ok else "所有滑块都生效",
                      advice="检查是否监听 input 事件、是否在 handler 里调用 render()",
                      severity=CRITICAL, weight=3))

    selects = br.get("selects") or {}
    if not selects.get("count", 0):
        out.append(mk("G4", "G4-10", "离散选项切换有效", "skip",
                      "每个下拉选择器切换后同步更新实验状态和可见结果",
                      "页面没有下拉选择器", "本页不使用离散选择器", weight=2))
    else:
        details = selects.get("details") or []
        applicable = [x for x in details if x.get("applicable", True)]
        failed_selects = [x for x in applicable if not x.get("changed")]
        if not applicable:
            out.append(mk("G4", "G4-10", "离散选项切换有效", "skip",
                          "每个有多个有效选项的选择器切换后更新状态和结果",
                          "选择器均只有一个有效选项", "没有可测试的离散状态切换", weight=2))
        else:
            ok = not failed_selects and len(applicable) == selects.get("responsive", 0)
            actual = "%d/%d 个有效选择器切换后状态与视图均变化" % (
                selects.get("responsive", 0), len(applicable))
            if failed_selects:
                actual += "；未响应：" + "、".join(str(x.get("index")) for x in failed_selects)
            out.append(mk("G4", "G4-10", "离散选项切换有效", "pass" if ok else "fail",
                          "切换选项后共享状态、画面/读数/公式同步更新", actual,
                          "选择器只改了控件外观，未驱动页面结果" if not ok else "离散选项确实驱动了页面",
                          evidence=str(details[:4]),
                          advice="为 select 监听 change 事件；把所选值写入 state 并统一调用 render()",
                          severity=MAJOR, weight=2))

    clicked = br.get("buttonsClicked") or []
    if not clicked:
        out.append(mk("G4", "G4-04", "按钮可操作", "skip",
                      "点击按钮后页面状态变化", "页面没有按钮", "无按钮可测", weight=2))
    else:
        dead = [b.get("按钮", "") for b in clicked if not b.get("有响应")]
        alive = len(clicked) - len(dead)
        ok = alive >= max(1, len(clicked) // 2)
        out.append(mk("G4", "G4-04", "按钮可操作", "pass" if ok else "fail",
                      "点击按钮后页面状态变化",
                      "%d/%d 个按钮有响应%s" % (alive, len(clicked),
                                             "，死键：%s" % "、".join(dead[:4]) if dead else ""),
                      "死键比算错更致命：学生根本没法继续" if not ok else "按钮均可用",
                      advice="给按钮绑定事件；开关类按钮必须改变实验状态并刷新读数",
                      severity=MAJOR, weight=2))

    canvases = br.get("canvas") or []
    painted = [c for c in canvases if c.get("painted", 0) > 100]
    out.append(mk("G4", "G4-05", "图像有实际绘制", "pass" if (painted or not canvases) else "fail",
                  "canvas 上有实际像素内容",
                  ("%d/%d 个 canvas 有内容" % (len(painted), len(canvases))) if canvases
                  else "未使用 canvas（图像检查已在第2关计分）",
                  "画布是空的，学生看到的是一片白" if (canvases and not painted) else "画布正常",
                  advice="检查绘制函数是否在数据变化后重绘、宽高是否被设为 0",
                  severity=MAJOR, weight=2))

    # 画面表达按教学对象区分：器材看材质层次；图表/几何/过程/分子由教师复核表达质量。
    q = br.get("quality")
    visual_type = br.get("visualType") or infer_visual_type(text)
    if visual_type != "apparatus":
        out.append(mk("G4", "G4-08", "绘图方式适配教学对象", "review",
                      "绘图类型与教学内容相符；轴/标注/几何/阶段/分子结构准确可读",
                      "绘图类型：%s；器材 2.5D 指标不适用于或无法识别该类型"
                      % (visual_type or "未识别"),
                      "需人工确认图表、空间结构、过程或微观模型是否清晰且准确",
                      evidence="声明：%s；页面内容推断：%s"
                      % (br.get("visualType") or "未声明", visual_type or "无"),
                      advice="声明 data-visual-type，并核对坐标轴和单位、几何关系、过程状态或分子结构；确认参数变化后表达同步更新",
                      severity=MINOR, weight=3))
    elif not q or q.get("填充数", 0) < 6:
        out.append(mk("G4", "G4-08", "画面具备立体质感", "skip",
                      "渐变/半透明叠层/曲线/无色块堆砌",
                      "画布绘制次数过少，无法取样" if q else "未取到质感数据",
                      "该项不适用", weight=3))
    else:
        grad, alpha = q.get("渐变占比", 0), q.get("叠层占比", 0)
        solid, curve = q.get("立体件占比", 0), q.get("曲线占比", 0)
        flat, flatN = q.get("扁平占比", 0), q.get("扁平色块", 0)
        # 函数图像类页面（坐标系 + 曲线）不按器材页的质感标准卡：
        # 网格和坐标轴本来就是直线，曲线占比天然只有百分之十几，
        # 拿 40% 的器材页门槛去卡，所有函数页都会被误判成「扁平示意图」。
        func_plot = False
        bad = []
        if grad < 0.05 and alpha < 0.03:
            bad.append("渐变 3%、半透明叠层 3% 均接近零，器材是纯色贴片")
        if curve < (0.05 if func_plot else 0.40):
            bad.append("曲线路径仅 %d%%，画面由矩形堆成" % round(curve * 100))
        if flat > 0.15:
            bad.append("大面积纯色块 %d 处（占填充 %d%%）" % (flatN, round(flat * 100)))
        detail = ("渐变 %d%% · 叠层 %d%% · 立体件 %d%% · 曲线 %d%% · 纯色块 %d 处"
                  % (round(grad * 100), round(alpha * 100), round(solid * 100),
                     round(curve * 100), flatN))
        if bad:
            out.append(mk("G4", "G4-08", "画面具备立体质感", "fail",
                          "渐变/半透明叠层/曲线/无色块堆砌",
                          detail + "｜" + "；".join(bad),
                          "器材画面缺少层次，达不到器材表达标准",
                          advice="②区改调学科场景库（PHYS/MATH/CHEM/BIO/GEO/CS），"
                                 "不要用裸 fillRect 拼版面；容器走 glass/liquid/glassFront 三段式",
                          severity=MAJOR, weight=3))
        elif solid <= 0.005:
            out.append(mk("G4", "G4-08", "画面具备立体质感", "review",
                          "渐变/半透明叠层/曲线/无色块堆砌",
                          detail + "｜未出现径向渐变/椭圆/柔光阴影，立体件可能不足",
                          "缺少立体件，器材看起来是平面图",
                          advice="每个实体补「渐变 + 高光 + 阴影」，接触面加椭圆投影",
                          severity=MINOR, weight=3))
        else:
            out.append(mk("G4", "G4-08", "画面具备立体质感", "pass",
                          "渐变/半透明叠层/曲线/无色块堆砌", detail,
                          "器材画面质感达到基础要求", weight=3))

    # 版式统一：蓝色条只放实验名字 / ①区不重复 / 正文纯黑 / 最小字号
    # 这一项对应「每张页面看起来必须是同一个产品」的硬要求，允许 typo.js 修过之后再量
    # 字号门槛不写死：取页面 --pf-fs-min 的实测值，规范改成 26px 时提示语自动跟着走
    ty = br.get("typography")
    if not ty or not ty.get("titleLen"):
        out.append(mk("G4", "G4-09", "版式统一", "skip",
                      "名字只在页眉出现一次 / 正文纯黑 / 最小字号按 --pf-fs-min",
                      "未取到版式数据", "该项不适用", weight=2))
    else:
        fmin = ty.get("fsMin") or 13
        fs_txt = ("%g" % fmin) + "px"
        want = "名字只在页眉出现一次 / 正文纯黑 / 最小字号 " + fs_txt
        bad = []
        if ty.get("titleLen", 0) > 18:
            bad.append("蓝色条标题 %d 字（应只放实验名字，≤18 字）：%s"
                       % (ty["titleLen"], ty.get("title", "")[:26]))
        if ty.get("hasName"):
            bad.append("①区又写了一遍实验名称（.exp-name），与页眉重复")
        if ty.get("small", 0) > 0:
            bad.append("仍有 %d 处文字小于 %s（最小 %spx）"
                       % (ty["small"], fs_txt, ty.get("minFs")))
        if ty.get("colored", 0) > 0:
            bad.append("仍有 %d 处正文不是黑色（蓝/灰蓝等）" % ty["colored"])
        detail = ("标题 %d 字「%s」· ①区重复名称 %s · 最小字号 %spx · 小于%s %d 处 · 非黑正文 %d 处"
                  % (ty.get("titleLen", 0), ty.get("title", ""), "有" if ty.get("hasName") else "无",
                     ty.get("minFs"), fs_txt, ty.get("small", 0), ty.get("colored", 0)))
        if bad:
            out.append(mk("G4", "G4-09", "版式统一", "fail",
                          want, detail, "；".join(bad),
                          "页面没走平台外壳规范，和同批案例长得不一样",
                          advice="走 shell.py 装配（自动注入 normal.css / typo.js）；"
                                 "标题传实验名字而不是整句主题；①区不要重复写名称",
                          severity=MAJOR, weight=2))
        else:
            out.append(mk("G4", "G4-09", "版式统一", "pass",
                          want, detail, "版式与平台规范一致", weight=2))

    # 单步序列（J5 的现场证据，这里只判"能不能推进"）
    steps = br.get("steps") or {}
    if steps.get("found"):
        ok = steps.get("stuck", 0) == 0 and steps.get("unique", 0) >= 2
        out.append(mk("G4", "G4-06", "单步过程可推进", "pass" if ok else "fail",
                      "每次单步都进入新状态",
                      "单步 %d 次，出现 %d 个状态，连续重复 %d 次"
                      % (steps.get("count", 0), steps.get("unique", 0), steps.get("stuck", 0)),
                      "单步卡住，过程演示无法继续" if not ok else "单步序列正常",
                      advice="用有限状态机推进；每步只允许合法迁移，并立即刷新画布",
                      severity=MAJOR, weight=2))
    else:
        out.append(mk("G4", "G4-06", "单步过程可推进", "skip",
                      "每次单步都进入新状态", "页面没有单步按钮",
                      "该实验没有过程演示，本项不适用", weight=2))

    rec = br.get("records") or {}
    if rec.get("clicked"):
        ok = rec.get("added", 0) >= 1
        out.append(mk("G4", "G4-07", "记录可追加", "pass" if ok else "fail",
                      "点「记录」后表格追加一行",
                      "点 %d 次，表格行数 %d→%d" % (rec.get("clicked", 0), rec.get("before", 0), rec.get("after", 0)),
                      "记录按钮没写进表格，数据无法留存" if not ok else "记录功能正常",
                      advice="记录时把当前参数与结果一起写入一行，不要只写结果",
                      severity=MAJOR, weight=2))
    else:
        out.append(mk("G4", "G4-07", "记录可追加", "skip",
                      "点「记录」后表格追加一行", "页面没有记录按钮",
                      "无记录按钮，本项不适用", weight=2))

    layout = br.get("layout") or {}
    viewports = layout.get("viewports") or []
    mobile = next((x for x in viewports if x.get("name") == "mobile"), None)
    over = [x for x in viewports if x.get("overflow")]
    unlabeled = layout.get("unlabeled") or []
    if not viewports:
        out.append(mk("G4", "G4-11", "窄屏布局与控件标签", "skip",
                      "桌面/窄屏无页面级横向溢出，参数控件有可读标签",
                      "未取到布局测量", "没有浏览器视口数据", weight=2))
    else:
        ok = not over and not unlabeled
        detail = "视口：" + "; ".join(
            "%s %d/%d%s" % (x.get("name"), x.get("documentWidth", 0), x.get("width", 0),
                             " 溢出" if x.get("overflow") else " 正常") for x in viewports)
        if unlabeled:
            detail += "；无标签控件：" + ", ".join(x.get("id") or x.get("tag") for x in unlabeled[:4])
        out.append(mk("G4", "G4-11", "窄屏布局与控件标签", "pass" if ok else "fail",
                      "桌面/窄屏无页面级横向溢出，参数控件有可读标签", detail,
                      "横向溢出会让投影/手机上的内容被裁掉；无标签控件难以理解",
                      evidence="mobile=%s; unlabeled=%s" % (mobile, unlabeled[:4]),
                      advice="为控件补 label/aria-label；窄屏下让卡片换列、表格容器局部滚动、画布宽度不超出页面",
                      severity=MAJOR, weight=2))

    vr = br.get("viewReset") or {}
    if vr.get("applicable"):
        good = vr.get("rotated") and vr.get("restored")
        out.append(mk("G4", "G4-12", "旋转视角可恢复", "pass" if good else "fail",
                      "拖动画布改变视角后，点击恢复按钮，yaw/pitch 回到初始视角",
                      "已旋转=%s；恢复=%s" % (vr.get("rotated"), vr.get("restored")),
                      "视角重置按钮只重绘但没有恢复视角状态" if not good else "视角已回到初始状态",
                      evidence=str(vr),
                      advice="调用 MATH.resetView(canvas)，不要只调用 render()",
                      severity=CRITICAL, weight=4))
    else:
        out.append(mk("G4", "G4-12", "旋转视角可恢复", "skip",
                      "带视角恢复按钮的可旋转场景应回到初始 yaw/pitch",
                      "页面没有恢复视角类按钮", "本项仅适用于提供视角复位的场景", weight=1))
    return out


# ============ 第5关：教学审核 ============

def gate5_teaching(html, low, text, req, subject, br):
    out = []

    # G5-01 学习目标（规范 2.2 ①）
    goals = [g for g in (req.get("学习目标") or []) if g]
    has_goal = "学习目标" in text or "目标" in text
    out.append(mk("G5", "G5-01", "学习目标可读", "pass" if has_goal else "fail",
                  "①区给出 1–2 条可观察的学习目标",
                  "已呈现（需求中 %d 条）" % len(goals) if has_goal else "未找到学习目标",
                  "没有目标，教师无法判断这节课要达成什么" if not has_goal else "学习目标已呈现",
                  advice="用「能……」开头写 1–2 条，指向可观察的行为",
                  severity=MAJOR, weight=2))

    # G5-02 教学说明三段（原理 / 易错点 / 探究问题）
    parts = {"原理": "原理" in text or "规律" in text,
             "易错点": "易错" in text or "注意" in text,
             "探究问题": "探究" in text or "问题" in text}
    miss = [k for k, v in parts.items() if not v]
    out.append(mk("G5", "G5-02", "教学说明完整", "pass" if not miss else "fail",
                  "⑥区含原理、易错点、1–2 道探究问题",
                  "缺失：%s" % "、".join(miss) if miss else "三段齐备",
                  "教师备课时缺可直接用的文字材料" if miss else "教学说明完整",
                  advice="原理写公式与适用条件；易错点写学生真实会犯的错；探究问题要能回到实验操作",
                  severity=MAJOR, weight=2))

    # G5-03 虚拟仿真声明（化学/生物必须，规范 4.5 特别注意）
    if subject in registry.SIMULATION_ONLY:
        has_sim = any(w in text for w in ("虚拟", "仿真", "模拟"))
        out.append(mk("G5", "G5-03", "虚拟仿真声明", "pass" if has_sim else "fail",
                      "化学/生物页面明确标注「虚拟仿真」，不给出真实危险操作指引",
                      "已声明" if has_sim else "未找到「虚拟/仿真/模拟」字样",
                      "把仿真写成真实操作步骤，可能引导学生动手尝试" if not has_sim else "边界清楚",
                      advice="在①区与⑥区写明「本页为虚拟仿真，不能替代真实实验」",
                      severity=CRITICAL, weight=2))
    else:
        out.append(mk("G5", "G5-03", "虚拟仿真声明", "skip",
                      "非化学/生物学科不强制", "学科：%s" % (subject or "未识别"),
                      "本学科不涉及该强制项", weight=2))

    # G5-04 实验性质与来源（规范 2.2 ①：不得把演示误写为课标必做）
    nature = re.search(r"(教学演示|演示实验|课标必做|常规实验|拓展活动|探究实验)", text)
    # "非课标必做"是正确的免责写法，不能当成"自称课标必做"
    overstated = bool(re.search(r"(?<!非)课标必做", text)) and not re.search(r"(来源|教材|依据)", text)
    if overstated:
        out.append(mk("G5", "G5-04", "实验性质标注", "review",
                      "明确标注实验性质与来源（课标必做 / 常规实验 / 教学演示）",
                      "出现「课标必做」但未标注来源",
                      "不能把演示误写成课标必做，需教研确认", weight=0))
    elif nature:
        out.append(mk("G5", "G5-04", "实验性质标注", "review",
                      "明确标注实验性质与来源（课标必做 / 常规实验 / 教学演示）",
                      "已标注「%s」" % nature.group(1),
                      "性质已写明，课标地位仍需教研确认", weight=0))
    else:
        out.append(mk("G5", "G5-04", "实验性质标注", "review",
                      "明确标注实验性质与来源", "①区未见实验性质/来源",
                      "缺少性质标注，对外汇报时容易把演示说成必做实验", weight=0))

    # G5-05 教师复核状态（规范 3.4 第5关）
    meta = re.search(r'<meta[^>]+name=["\']review[_-]?status["\'][^>]*content=["\']([^"\']+)', html, re.I)
    status = meta.group(1) if meta else "未标注"
    ok = status not in ("未标注", "", "pending", "待审核")
    out.append(mk("G5", "G5-05", "教师复核状态", "pass" if ok else "review",
                  "页面带教研复核结论（通过/修订后通过）",
                  "复核状态：%s" % status,
                  "机器审完只是「可进入人工审核」，不等于可以上课" if not ok else "已有人工复核记录",
                  advice="在 <head> 加 <meta name=\"review-status\" content=\"复核通过\">，由教研填写",
                  weight=0))

    # G5-06 图文描述不混淆真实与模拟
    confusable = re.search(r"(真实实验|亲手操作|请同学们实际)", text) and not re.search(
        r"(虚拟|仿真|模拟|不得替代)", text)
    out.append(mk("G5", "G5-06", "真实/模拟表述清晰", "pass" if not confusable else "review",
                  "明确区分虚拟现象与真实实验",
                  "存在可能与真实操作混淆的表述" if confusable else "表述清晰",
                  "混淆真实与模拟会带来教学与安全风险", weight=0))
    return out


# ============ 打分与报告 ============

def aggregate(checks):
    gates = []
    total = 0.0
    for gid, gname, full in GATES:
        items = [c for c in checks if c["gate"] == gid]
        scored = [c for c in items if c["status"] in ("pass", "fail")]
        tw = sum(c["weight"] for c in scored)
        pw = sum(c["weight"] for c in scored if c["status"] == "pass")
        score = round(full * pw / tw, 2) if tw else float(full)
        total += score
        gates.append({
            "关": gid, "名称": gname, "满分": full, "得分": score,
            "通过": len([c for c in items if c["status"] == "pass"]),
            "失败": len([c for c in items if c["status"] == "fail"]),
            "待审": len([c for c in items if c["status"] == "review"]),
            "不适用": len([c for c in items if c["status"] == "skip"]),
            "无可判项": tw == 0,
        })
    return gates, round(total, 1)


def judge_summary(checks):
    out = {}
    for c in checks:
        if c["gate"] != "G3" or not c.get("judge"):
            continue
        d = out.setdefault(c["judge"], {"名称": c.get("judge_name", ""),
                                        "pass": 0, "fail": 0, "review": 0, "skip": 0})
        d[c["status"]] = d.get(c["status"], 0) + 1
    return {k: out[k] for k in sorted(out)}


def legacy_item(c):
    """兼容编排器：它按 维度/检查项/级别/说明/建议 打印与落档。"""
    dim = c["gate_name"] + ("·" + c["judge"] if c.get("judge") else "")
    return {
        "维度": dim,
        "检查项": c["name"],
        "级别": c["severity"],
        "说明": c["message"] + ("（%s）" % c["actual"] if c["actual"] else ""),
        "建议": c["advice"],
        "check_id": c["check_id"],
        "status": c["status"],
        "expected": c["expected"],
        "actual": c["actual"],
        "evidence": c["evidence"],
    }


def build_feedback(failed):
    if not failed:
        return ""
    lines = ["上一版质检未通过，请逐条修改（共 %d 项）：" % len(failed)]
    for i, c in enumerate(failed, 1):
        lines.append("%d. [%s/%s] %s：%s。应为：%s；实际：%s。修改建议：%s"
                     % (i, c["gate_name"], c["check_id"], c["name"],
                        c["message"], c["expected"], c["actual"], c["advice"]))
    return "\n".join(lines)


def run_review(html_path, req_path, facts_path=FACTS_PATH, use_browser=True, verbose=True):
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()
    low = html.lower()
    # 正文只取可见内容：脚本、样式、注释都不算页面文字（否则 JS 注释里的 "// 0" 会被当成除零）
    visible = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    visible = re.sub(r"<style[\s\S]*?</style>", " ", visible, flags=re.I)
    visible = re.sub(r"<!--[\s\S]*?-->", " ", visible)
    text = re.sub(r"<[^>]+>", " ", visible)
    text = re.sub(r"\s+", " ", text)

    req = {}
    if req_path and os.path.exists(req_path):
        with open(req_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        req = raw.get("output", raw)
    else:
        reqs = glob.glob(os.path.join(PARENT, "01_single_agent", "output", "需求_*.json"))
        if reqs:
            with open(max(reqs, key=os.path.getmtime), "r", encoding="utf-8") as f:
                raw = json.load(f)
            req = raw.get("output", raw)

    # 主题决定单位与安全阈值；先看页面再看需求（需求可能是另一次实验的）
    content = re.sub(r"<[^>]+>", " ", visible)
    probe = " ".join([req.get("实验主题", "")]
                     + [str(g) for g in req.get("学习目标", [])]
                     + [v.get("名称", "") for v in req.get("核心变量", [])])
    # 学科优先看页面本身：需求文件默认取最新，可能来自另一次实验（拿电路需求审几何页会全错）
    subject = registry.default_subject(content) or registry.default_subject("", req.get("学科", ""))
    # topics.py 的单位组与安全阈值只服务物理/化学这类有量纲的实验；
    # 数学页里出现"体积"不代表要用浮力的单位组去卡它。
    if subject in ("物理", "化学") or not subject:
        topic = detect_topic(content) or detect_topic(probe)
    else:
        topic = subject
    profile = profile_of(topic) if subject in ("物理", "化学") or not subject else profile_of(None)

    br, reason = (None, "未启用")
    if use_browser:
        br, reason = dynamic_checks(html_path)
    circuit_topic = bool(re.search(r"欧姆定律|电路|电流表|电压表", content + " " + probe))
    if br is not None and circuit_topic:
        br["circuitRequired"] = True
        br["circuitCheck"] = verify_circuit_samples(br)

    machine = (br or {}).get("machine") or {}
    cfg = {}
    for key in ("CONFIG", "EXP"):
        if isinstance(machine.get(key), dict):
            cfg = dict(machine[key])
            break
    if not cfg:
        m = re.search(r'<meta[^>]+name=["\']scene[_-]engine["\'][^>]+content=["\']([^"\']+)', html, re.I)
        if m:
            cfg["scene_engine"] = m.group(1)
    engine = cfg.get("scene_engine") or cfg.get("engine") or ""
    scene = registry.scene_of(cfg.get("scene_id"))
    if not scene:
        # 从场景名称反查（模型不一定声明 scene_id）
        title = ""
        mt = re.search(r"<title>(.*?)</title>", html, re.S)
        if mt:
            title = mt.group(1)
        for sid, s in registry.SCENES.items():
            if s["name"] in title or (s["name"] in text and s["name"][:4] in text):
                scene = s
                cfg.setdefault("scene_id", sid)
                break
    if not engine and scene:
        engine = scene.get("engine", "")
    if not subject and scene:
        subject = scene.get("subject", "")

    try:
        with open(facts_path, "r", encoding="utf-8") as f:
            facts = json.load(f).get("条目", [])
    except (OSError, ValueError):
        facts = []

    ctx = {"html": html, "low": low, "text": text, "req": req, "profile": profile,
           "br": br, "machine": machine, "subject": subject, "engine": engine,
           "scene": scene, "facts": facts, "topic": topic}

    checks = []
    if verbose:
        print("\n[1/5] 第1关 结构与安全")
    checks += gate1_safety(html, low, text, topic, br, subject, cfg, engine, scene)
    if verbose:
        print("[2/5] 第2关 资源完整性")
    checks += gate2_assets(html, low, text, br, html_path)
    if verbose:
        print("[3/5] 第3关 学科判据（%s：%s）"
              % (subject or "未识别",
                 "、".join(registry.subject_judges(subject)) if subject else "无"))
    checks += gate3_subject(ctx, subject)
    if verbose:
        print("[4/5] 第4关 浏览器测试")
    checks += gate4_browser(br, reason, text)
    if verbose:
        print("[5/5] 第5关 教学审核")
    checks += gate5_teaching(html, low, text, req, subject, br)

    gates, total = aggregate(checks)
    failed = [c for c in checks if c["status"] == "fail"]
    # Subject judges use the English token ``critical`` while the reviewer
    # gates use the Chinese label ``严重``. Treat both as blocking severities;
    # otherwise a failed J1/J6/J8 item can silently coexist with verdict=通过.
    critical = [c for c in failed if str(c.get("severity", "")).lower()
                in (CRITICAL.lower(), "critical")]
    reviews = [c for c in checks if c["status"] == "review"]

    if critical or total < MAJOR_LINE:
        verdict = "不通过"
    elif total < PASS_SCORE:
        verdict = "需修改"
    else:
        verdict = "通过"

    if br is None:
        # 没有第4关就没有"页面真的能跑"的证据，不能算可发布
        release = "待验证（未执行第4关）"
    elif critical:
        release = "禁止发布"
    elif reviews:
        release = "待教师审核"
    elif verdict == "通过":
        release = "可发布"
    else:
        release = "禁止发布"

    report = {
        "文件": os.path.basename(html_path),
        "审查时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "实验ID": cfg.get("experiment_id") or "未登记（应由知识库 experiment_id 提供）",
        "学科": subject or "未识别",
        "主题": topic or "未识别",
        "引擎": engine or "未声明",
        "场景": (cfg.get("scene_id") or "未登记") if (cfg.get("scene_id") or scene) else "未登记",
        "总分": total,
        "结论": verdict,
        "发布状态": release,
        "严重问题数": len(critical),
        "五关": gates,
        "判据": judge_summary(checks),
        "检查项": checks,
        "问题清单": [legacy_item(c) for c in failed],
        "待审清单": [legacy_item(c) for c in reviews],
        "修改意见": build_feedback(failed),
        "动态验证": "已执行" if br is not None else "跳过（%s）" % reason,
        "独立性说明": "J1–J8 由本文件独立重算，页面自报的 __DATA__.checks 只记为 review，"
                      "不作为通过依据；J8 依赖 facts.json 中已通过教研复核的条目。",
    }
    return report


def dynamic_checks(html_path):
    node = find_node()
    modules = find_node_modules()
    if not node:
        return None, "未找到 node"
    if not modules:
        return None, "未找到 playwright 模块"

    env = dict(os.environ)
    env["NODE_PATH"] = modules
    chrome = find_chrome()
    if chrome:
        env["CHROME_PATH"] = chrome

    try:
        proc = subprocess.run([node, CHECK_JS, html_path],
                              capture_output=True, text=True, encoding="utf-8",
                              timeout=240, env=env)
    except subprocess.TimeoutExpired:
        return None, "浏览器检查超时"

    out = (proc.stdout or "").strip().splitlines()
    if not out:
        return None, "浏览器检查无输出：%s" % (proc.stderr or "")[:200]
    try:
        return json.loads(out[-1]), None
    except json.JSONDecodeError:
        return None, "浏览器检查输出无法解析：%s" % out[-1][:200]


MARK = {"pass": "OK  ", "fail": "FAIL", "review": "REVIEW", "skip": "SKIP"}


def print_report(report, report_path):
    print("")
    print("=" * 70)
    print("质量审查  %s    学科 %s / 主题 %s" % (report["文件"], report["学科"], report["主题"]))
    print("结论      %s    总分 %.1f / 100    发布状态：%s"
          % (report["结论"], report["总分"], report["发布状态"]))
    print("=" * 70)
    for g in report["五关"]:
        print("\n【第%s关 %s】%.1f / %d    通过 %d · 失败 %d · 待审 %d · 不适用 %d"
              % (g["关"][1], g["名称"], g["得分"], g["满分"],
                 g["通过"], g["失败"], g["待审"], g["不适用"]))
        gid = g["关"]
        for c in report["检查项"]:
            if c["gate"] != gid:
                continue
            judge = ("[%s] " % c["judge"]) if c.get("judge") else ""
            print("  %s %s%s  %s" % (MARK[c["status"]], judge, c["name"], c["actual"] or c["message"]))
    if report["判据"]:
        print("\n判据通过情况：")
        for j, v in report["判据"].items():
            print("  %s %-8s 通过 %d · 失败 %d · 待审 %d · 不适用 %d"
                  % (j, v["名称"], v["pass"], v["fail"], v["review"], v["skip"]))
    print("\n" + "-" * 70)
    if report["修改意见"]:
        print(report["修改意见"])
    else:
        print("客观检查项全部通过。")
    if report["待审清单"]:
        print("\n以下事项需教师确认（不计入分数，未确认前不能发布）：")
        for c in report["待审清单"]:
            print("  · [%s] %s：%s" % (c["维度"], c["检查项"], c["说明"]))
    print("-" * 70)
    print("报告已保存：%s" % report_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--html", help="要审查的 HTML 路径")
    parser.add_argument("--req", help="需求 JSON 路径（默认取最新的）")
    parser.add_argument("--facts", default=FACTS_PATH, help="事实表路径（默认 facts.json）")
    parser.add_argument("--quiet", action="store_true", help="只输出修改意见（给生成 Agent 用）")
    parser.add_argument("--no-browser", action="store_true", help="跳过第4关（离线/调试用）")
    args = parser.parse_args()

    html_path = args.html
    if not html_path:
        files = glob.glob(os.path.join(PARENT, "03_generator_agent", "output", "教学资源_*.html"))
        if not files:
            raise SystemExit("找不到待审查的 HTML，请先运行 03_generator_agent/generator_agent.py")
        html_path = max(files, key=os.path.getmtime)

    report = run_review(html_path, args.req, args.facts,
                        use_browser=not args.no_browser, verbose=not args.quiet)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    name = os.path.splitext(os.path.basename(html_path))[0]
    report_path = os.path.join(OUTPUT_DIR, "审查报告_%s.json" % name)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    if args.quiet:
        print(report["修改意见"] or "（无问题）")
        return
    print_report(report, report_path)


if __name__ == "__main__":
    main()
