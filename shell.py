# -*- coding: utf-8 -*-
"""
shell.py —— 平台外壳装配器（把「模型生成的内容」装进「师伴」外壳）

为什么要有这一层，而不是让模型直接吐完整 HTML：
    外壳（页眉 / 右侧图标栏 / 页脚 / 三个弹窗）必须 30 个页面长得完全一样，
    交给模型每次重写，一定会漂移——今天少个页脚，明天导航跑到页眉上去。
    所以拆成两半：模型只写「六区域内容」，外壳由本模块用固定模板拼上去。

一句话：模型负责「实验对不对」，这里负责「页面像不像同一个产品」。

对外接口：
    secs = parse_sections(text)          # 从模型回复里切出六段 + 附加 CSS/JS
    problems = check_sections(secs)      # 缺哪几块（缺了就退回让模型补）
    html = render(title, secs)           # 套壳，得到可直接打开的完整 HTML
    out = deliver(html, title, out_dir)  # 落盘成「一个案例一个文件夹」+ zip

命令行：
    python shell.py build 内容片段.txt --title 平面截正方体 --out deliver/
"""

import argparse
import io
import os
import re
import shutil
import zipfile

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRAME_DIR = os.path.join(BASE_DIR, "frame")
SHELL_PATH = os.path.join(FRAME_DIR, "shell.html")
NORMAL_CSS = os.path.join(FRAME_DIR, "normal.css")   # 平台阅读规范（后置强制层）
TYPO_JS = os.path.join(FRAME_DIR, "typo.js")         # 字号兜底（运行时抬到 --pf-fs-min 以上）

# 六个区域的固定顺序与名称，和规范第 1 节一一对应
SECTIONS = [
    ("1", "① 实验信息"),
    ("2", "② 演示画布"),
    ("3", "③ 参数与操作"),
    ("4", "④ 结果与反馈"),
    ("5", "⑤ 实验记录"),
    ("6", "⑥ 教学说明"),
]

# 每个区域至少要有的东西（用于判断模型是不是只写了个空壳）
SECTION_MUST_HAVE = {
    "2": ["<canvas", "<svg"],        # 演示区必须有画布
    "3": ["<input", "<button", "<select"],
    "4": ["exp-formula", "exp-read"],  # 必须有读数与代入式
    "5": ["<table", "<thead", "<tr"],
}


# ============================================================ 解析

_TAG = r"<!--\s*%s\s*-->"


def _split_by_tags(text):
    """按 <!--1--> … <!--6--> 切段。容忍空格、全角括号等写法差异。"""
    positions = []
    for key, _ in SECTIONS:
        m = re.search(r"<!--\s*[\[【(（]?\s*%s\s*[\]】)）]?\s*-->" % key, text)
        if m:
            positions.append((key, m.start(), m.end()))
    if not positions:
        return {}
    positions.sort(key=lambda x: x[1])

    out = {}
    for i, (key, start, end) in enumerate(positions):
        stop = positions[i + 1][1] if i + 1 < len(positions) else len(text)
        out[key] = text[end:stop].strip()
    return out


def parse_sections(text):
    """把模型回复整理成 {'1':..., '6':..., 'css':..., 'js':...}。

    兼容三种写法：
        1) 标准：<!--1--> … <!--6-->，另有 <!--CSS--> / <!--JS-->
        2) 把 <style> / <script> 混在正文里 —— 自动抽出来放到 css / js
        3) 直接吐完整 HTML —— 从 <main> 里取 .exp-wrap 的内层，尽量抢救
    """
    text = (text or "").strip()
    text = re.sub(r"^```(?:html)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text).strip()

    # 完整 HTML 兜底：只取内容区
    if "<!doctype" in text.lower() or "<html" in text.lower():
        m = re.search(r'<div class="exp-wrap">(.*?)</div>\s*</main>', text, re.S)
        if m:
            text = m.group(1)

    # 先抽 CSS / JS，避免里面的 <!-- --> 干扰切段
    css, js = "", ""
    m = re.search(r"<!--\s*CSS\s*-->(.*?)(?=<!--\s*(?:JS|1)\s*-->|$)", text, re.S)
    if m:
        css = re.sub(r"</?style[^>]*>", "", m.group(1)).strip()
        text = text[:m.start()] + text[m.end():]
    m = re.search(r"<!--\s*JS\s*-->(.*)$", text, re.S)
    if m:
        js = re.sub(r"</?script[^>]*>", "", m.group(1)).strip()
        text = text[:m.start()]

    # 正文里残留的 <style>/<script> 也收走
    for block in re.findall(r"<style[^>]*>(.*?)</style>", text, re.S | re.I):
        css = (css + "\n" + block).strip()
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.S | re.I)
    for block in re.findall(r"<script[^>]*>(.*?)</script>", text, re.S | re.I):
        js = (js + "\n" + block).strip()
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.S | re.I)

    secs = _split_by_tags(text)
    secs["css"] = css
    secs["js"] = js
    return secs


def check_sections(secs):
    """返回问题清单；空清单表示六块齐全且每块都有该有的东西。"""
    problems = []
    for key, name in SECTIONS:
        body = (secs.get(key) or "").strip()
        if not body:
            problems.append("缺少「%s」区域（用 <!--%s--> 标记）" % (name, key))
            continue
        must = SECTION_MUST_HAVE.get(key)
        if must and not any(tag in body for tag in must):
            problems.append("「%s」区域内容不完整，至少要有 %s 之一"
                            % (name, " / ".join(must)))
    if not (secs.get("js") or "").strip():
        problems.append("缺少脚本（用 <!--JS--> 标记，页面交互全靠它）")
    return problems


# ============================================================ 渲染

def _read(path):
    with io.open(path, encoding="utf-8") as f:
        return f.read()


def _read_soft(path):
    return _read(path) if os.path.exists(path) else ""


# ---------------------------------------------------------------- 页眉标题
# 「实验主题」是给下游 Agent 看的描述（往往一整句，带条件、带结论），
# 直接塞进蓝色条会把页眉撑成两行还得省略号。所以这里统一缩成「实验名字」：
#   用平面截正方体所得截面形状随平面位置与倾斜角度变化的规律 → 平面截正方体
#   铁与硫酸铜溶液发生置换反应，生成铜和硫酸亚铁，验证金属活动性顺序 → 铁与硫酸铜溶液反应
# 需求 Agent 若给出了「实验名称」字段就直接用，这里只负责兜底。

TITLE_MAX = 16

# 只去「怎么做的」这类工具性动词；探究/观察/验证 本身就是实验名的一部分
_LEAD_VERB = ("用", "通过", "利用", "借助")
_CUTS = ("：", ":", "——", "，", ",", "；", ";", "。")
# 出现这些词，后面的内容都是「怎么变的」，不属于名字
_TAILS = ("所得", "随", "并", "的规律", "的探究", "的过程")


def short_title(text, limit=TITLE_MAX):
    """把一句「实验主题」压成能放进蓝色条的实验名字。"""
    s = re.sub(r"\s+", "", (text or "").strip())
    s = re.sub(r"^师伴\s*[-－—]\s*", "", s)
    s = s.strip("《》\"'“”")
    if not s:
        return "教学资源"

    # 1) 有冒号时，冒号前通常就是主标题
    for sep in ("：", ":"):
        if sep in s:
            head = s.split(sep)[0].strip()
            # 冒号前够长就直接当名字（欧姆定律：电压、电阻… → 欧姆定律）
            if 3 <= len(head) <= limit:
                return head
            # 太短（浮力：…）说明「浮力」是泛指，整句又不超长就整句留着
            if len(s) <= limit:
                return s
            s = head
            break

    # 2) 只取第一分句
    for sep in _CUTS:
        if sep in s:
            s = s.split(sep)[0]

    # 3) 「发生置换反应」→「反应」，既去掉冗词又能留住实验类型
    s = s.replace("发生置换反应", "反应").replace("发生反应", "反应")

    # 4) 砍掉描述性尾巴
    for t in _TAILS:
        pos = s.find(t)
        if pos >= 3:
            s = s[:pos]

    # 5) 去掉开头的动词，但剩下的部分得够长（「测量浮力」不能只剩「浮力」）
    changed = True
    while changed:
        changed = False
        for v in _LEAD_VERB:
            if s.startswith(v) and len(s) - len(v) >= 4:
                s = s[len(v):]
                changed = True
                break

    s = s.strip("的与和及、， ")
    if len(s) > limit:
        s = s[:limit].rstrip("的与和及、， ")
    return s or "教学资源"


def strip_exp_name(html):
    """① 区不再重复实验名称 —— 名字只在页眉出现一次。

    模型爱在 ① 区写 <h2 class="exp-name">xxx</h2>，和页眉重复一遍。
    这里直接摘掉整个节点（不是 display:none），免得屏幕阅读器念两遍。
    """
    if not html:
        return html or ""
    return re.sub(
        r'<([a-zA-Z0-9]+)[^>]*\bclass\s*=\s*(["\'])[^"\']*\bexp-name\b[^"\']*\2[^>]*>.*?</\1>',
        "", html, flags=re.S | re.I)


# ---------------------------------------------------------------- 共享绘图层
# 统一质感分三层：
#   vis.js    —— 全学科共用的视觉原语（玻璃器皿/立体实体/光影/标注）
#   <学科>.js —— 该学科的固定版面（浮力、光具座、立方体截面、显微镜、地球、流程图）
#   页面 JS   —— 只给状态量和读数，不画版面
# 这里按学科把需要的层内联进 HTML，保持「单文件、断网可跑」。
VIS_LIB = os.path.join(FRAME_DIR, "vis.js")
CHEM_LIB = os.path.join(FRAME_DIR, "chem.js")

# 学科 → 场景库。chem.js 自带画布实现（历史原因），不依赖 vis.js；
# 其余库都建立在 vis.js 之上。
SCENE_LIBS = {
    "化学": "chem.js",
    "物理": "phys.js",
    "数学": "math.js",
    "生物": "bio.js",
    "地理": "geo.js",
    "信息": "cs.js",
    "编程": "cs.js",
    "算法": "cs.js",
}
# 页面 JS 里直接调用的库名，用于正文没写学科时的兜底判断
CALL_HINTS = [
    ("CHEM.", "chem.js"), ("PHYS.", "phys.js"), ("MATH.", "math.js"),
    ("BIO.", "bio.js"), ("GEO.", "geo.js"), ("CS.", "cs.js"),
]


def _read_lib(name):
    path = os.path.join(FRAME_DIR, name)
    if not os.path.exists(path):
        return ""
    return _read(path).strip()


def pick_scene_libs(js, secs):
    """判断这一页要用哪些共享库，返回 (库文件名列表, 学科名)。

    先看页面 JS 里实际调了哪个库（最可靠），再看正文提到了哪一科。
    """
    js = js or ""
    for token, lib in CALL_HINTS:
        if token in js:
            return [lib], lib.replace(".js", "")
    text = " ".join((secs or {}).values())
    for subject, lib in SCENE_LIBS.items():
        if subject in text:
            return [lib], subject
    return [], ""


def _with_libs(js, secs=None):
    """把共享绘图层内联进来（保持单文件离线可运行）。

    注入顺序：vis.js（原语）→ 学科场景库 → 页面自己的脚本。
    这样页面里可以直接用 VIS.xxx 拼自定义画面，也可以直接调 PHYS.floating 这类成品版面。
    """
    libs, _ = pick_scene_libs(js, secs)
    if not js and not libs:
        return js
    blocks = []
    if libs:
        if "chem.js" not in libs:
            vis = _read_lib("vis.js")
            if vis:
                blocks.append(vis)
        for name in libs:
            code = _read_lib(name)
            if code:
                blocks.append(code)
    elif "VIS." in (js or ""):
        vis = _read_lib("vis.js")
        if vis:
            blocks.append(vis)
    if not blocks:
        return js
    return "\n\n".join(blocks) + "\n\n" + (js or "")


def render(title, secs, slug=None):
    """套上平台外壳，返回完整 HTML 字符串。"""
    shell = _read(SHELL_PATH)
    title = short_title(title)          # 蓝色条只放实验名字
    secs = dict(secs or {})
    secs["1"] = strip_exp_name(secs.get("1") or "")   # ① 区不重复名字
    mapping = {
        "{{TITLE}}": _esc(title),
        "{{SLUG}}": _esc(slug or title),
        "{{EXTRA_CSS}}": (secs.get("css") or "").strip(),
        "{{NORMAL_CSS}}": _read_soft(NORMAL_CSS).strip(),
        "{{TYPO_JS}}": _read_soft(TYPO_JS).strip(),
        "{{JS}}": _with_libs((secs.get("js") or "").strip(), secs),
    }
    for key, _ in SECTIONS:
        mapping["{{SEC%s}}" % key] = (secs.get(key) or "").strip()

    html = shell
    for k, v in mapping.items():
        html = html.replace(k, v)
    return html


def _esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


# ============================================================ 校验

_NS_CALL_RE = {}


def _calls(html, token):
    """页面里是否真的「以库命名空间的方式」调用了 token，例如 "GEO."。

    要求 token 左侧不是标识符字符也不是 '.' / '$'。否则 `PAGE_GEO.params`
    这种普通变量会被当成地理库调用，报出根本不存在的注入缺失。
    """
    pat = _NS_CALL_RE.get(token)
    if pat is None:
        pat = re.compile(r"(?<![A-Za-z0-9_.$])" + re.escape(token))
        _NS_CALL_RE[token] = pat
    return pat.search(html) is not None


def validate(html):
    """外壳完整性校验：交付前必须全过，否则页面上会缺导航或缺页脚。"""
    problems = []
    low = html.lower()

    for marker, label in [
        ('class="pf-header"', "页眉"),
        ('class="pf-side"', "右侧图标栏"),
        ('class="pf-footer"', "页脚"),
        ('href="frame.css"', "frame.css 引用"),
        ('href="exp.css"', "exp.css 引用"),
        ('src="logo.png"', "logo.png 引用"),
        ('class="pf-modal pf-modal-gen"', "生成案例弹窗"),
        ('class="pf-modal pf-modal-dl"', "下载弹窗"),
        ('class="pf-modal pf-modal-contact"', "联系我们弹窗"),
    ]:
        if marker not in html and marker not in low:
            problems.append("外壳缺少：%s（%s）" % (label, marker))

    for token, lib in CALL_HINTS:
        ns = token.rstrip(".")
        # 必须按「标识符左边界」匹配。以前直接 `token in html`，会把
        # PAGE_GEO.params 里的 "GEO." 当成地理库调用，报出根本不存在的
        # 注入缺失（二次函数页就被这样误伤），日志里一片红但页面是好的。
        if _calls(html, token) and ("window." + ns) not in html:
            problems.append("页面调用了 %s，但 %s 没有注入（检查 shell.py 的注入路由）" % (token, lib))
    if _calls(html, "VIS.") and "window.VIS" not in html:
        problems.append("页面调用了 VIS 原语，但 vis.js 没有注入（检查 frame/vis.js）")

    for key, name in SECTIONS:
        if 'id="sec-%s"' % _sec_id(key) not in html:
            problems.append("缺少区域容器：%s" % name)

    if "<h1 class=\"pf-title\"" not in html:
        problems.append("页眉标题结构不对（应有 .pf-title 与 .pf-page）")

    # 蓝色条只放实验名字：太长会挤成两行 + 省略号，等于没写
    m = re.search(r'<span[^>]*\bclass="pf-page"[^>]*>(.*?)</span>', html, re.S)
    page_title = re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else ""
    if len(page_title) > TITLE_MAX + 2:
        problems.append("页眉标题太长（%d 字：%s），蓝色条只放实验名字"
                        % (len(page_title), page_title[:24]))

    # 名字只在页眉出现一次，① 区不能再有同名大标题
    if 'id="sec-info"' in html:
        info = html.split('id="sec-info"', 1)[1].split("</section>", 1)[0]
        if re.search(r'class\s*=\s*["\'][^"\']*\bexp-name\b', info):
            problems.append("① 区仍有实验名称标题（.exp-name），名字只应在页眉出现一次")

    # 阅读规范（正文纯黑 / 最小字号）必须注入
    if "--pf-fs-min" not in html:
        problems.append("缺少平台阅读规范（frame/normal.css 未注入）")

    urls = re.findall(r"https?://[^\s\"'<>)]+", html)
    urls = [u for u in urls if "w3.org" not in u]      # svg/xml 命名空间不算外链
    if urls:
        problems.append("出现外部链接（离线会失效）：%s" % "、".join(urls[:3]))

    return problems


def _sec_id(key):
    return {"1": "info", "2": "stage", "3": "control",
            "4": "result", "5": "record", "6": "teach"}[key]


# ============================================================ 落盘交付

def safe_name(title, limit=32):
    """Windows 文件名安全化，保留中文。"""
    name = re.sub(r'[\\/:*?"<>|]+', "_", title or "未命名案例")
    name = re.sub(r"\s+", "", name).strip("._")
    return name[:limit] or "未命名案例"


def deliver(html, title, out_dir, make_zip=True):
    """一个案例落成一个文件夹：html + frame.css + exp.css + logo.png（+ zip）。

    这样老师双击 html 就能看，把整个文件夹（或 zip）发给别人也不会缺样式。
    """
    name = safe_name(title)
    case_dir = os.path.join(out_dir, name)
    os.makedirs(case_dir, exist_ok=True)

    html_path = os.path.join(case_dir, "%s.html" % name)
    with io.open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    for res in ("frame.css", "exp.css", "logo.png"):
        shutil.copy2(os.path.join(FRAME_DIR, res), os.path.join(case_dir, res))

    zip_path = ""
    if make_zip:
        zip_path = os.path.join(case_dir, "%s.zip" % name)
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(html_path, "%s.html" % name)
            for res in ("frame.css", "exp.css", "logo.png"):
                z.write(os.path.join(case_dir, res), res)

    return {"目录": case_dir, "HTML": html_path, "压缩包": zip_path,
            "文件名": os.path.basename(html_path)}


# ============================================================ 命令行

def main():
    ap = argparse.ArgumentParser(description="把六区域内容片段装配成平台页面")
    sub = ap.add_subparsers(dest="cmd")

    b = sub.add_parser("build", help="从内容片段文本生成完整页面")
    b.add_argument("src", help="含 <!--1-->…<!--6--> 标记的文本文件")
    b.add_argument("--title", required=True, help="页面标题（不带「师伴-」前缀）")
    b.add_argument("--out", default=os.path.join(BASE_DIR, "deliver"))

    args = ap.parse_args()
    if args.cmd != "build":
        ap.print_help()
        return

    secs = parse_sections(_read(args.src))
    problems = check_sections(secs)
    if problems:
        print("内容片段有问题：")
        for p in problems:
            print("  -", p)
        raise SystemExit(1)

    html = render(args.title, secs)
    shell_problems = validate(html)
    if shell_problems:
        print("外壳装配有问题：")
        for p in shell_problems:
            print("  -", p)
        raise SystemExit(1)

    info = deliver(html, args.title, args.out)
    print("已生成：%s" % info["HTML"])
    print("压缩包：%s" % info["压缩包"])


if __name__ == "__main__":
    main()
