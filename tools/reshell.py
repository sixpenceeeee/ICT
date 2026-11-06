# -*- coding: utf-8 -*-
"""
reshell.py —— 给「已经生成好的页面」补/刷新 UI 规范

为什么需要它：
    shell.py 只管新生成的页面。可老师手上已经有一批做好的案例页，
    规范改了之后它们还停在旧样子（蓝色条一长串、① 区名字重复、
    正文偏蓝、字很小）。这里做一次「原地升级」，不重跑生成、不动画面。

补四件事（与回新页面完全一致的规范）：
    1. 蓝色条只留实验名字（.pf-page 文本 + <title>）
    2. 删掉 ① 区重复的 .exp-name
    3. 注入 / **刷新** normal.css、typo.js（正文纯黑 + 最小字号）
    4. 同步同目录的 frame.css / exp.css 副本（字号档位跟着平台走）

「刷新」是重点：规范改过一次以后再跑，不能因为「已经有 --pf-fs-min」就跳过，
否则字号从 13px 改到 26px 时老页面纹丝不动。

用法：
    python tools/reshell.py deliver/案例.html              # 原地修改
    python tools/reshell.py deliver/*/*.html               # 批量
    python tools/reshell.py x.html --dry-run               # 只看会改什么
    python tools/reshell.py x.html --no-css                # 只改 HTML，不动 css 副本
"""

import argparse
import io
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import shell

MARK_CSS = '<!-- 平台阅读规范'
MARK_JS = '<!-- 字号兜底'
MARK_CSS_NEW = '  <!-- 平台阅读规范：正文纯黑 / 最小字号 %s / 名称只在页眉 -->\n'
MARK_JS_NEW = '  <!-- 字号兜底：页面自己写的小字号统一抬到 %s 以上 -->\n'


def _fs_min():
    """从 normal.css 里读出当前最小字号，注释和页面提示都跟着它走。"""
    css = shell._read_soft(shell.NORMAL_CSS)
    m = re.search(r'--pf-fs-min:\s*([\d.]+)px', css)
    return (m.group(1) + 'px') if m else '13px'


def _normal_block():
    css = shell._read_soft(shell.NORMAL_CSS).strip()
    return MARK_CSS_NEW % _fs_min() + '  <style>\n' + css + '\n  </style>'


def _typo_block():
    js = shell._read_soft(shell.TYPO_JS).strip()
    return MARK_JS_NEW % _fs_min() + '  <script>\n' + js + '\n  </script>'


def _swap_block(html, mark, end_tag, block):
    """把 mark 起到下一个 end_tag 为止的整段换成 block。找不到返回 None。"""
    i = html.find(mark)
    if i < 0:
        return None
    j = html.find(end_tag, i)
    if j < 0:
        return None
    return html[:i] + block + html[j + len(end_tag):]


def patch(html, title_hint=""):
    """返回 (新 HTML, 改动说明列表)。已经是最新规范的页面会退化成「无改动」。"""
    notes = []
    out = html

    # 1) 页眉标题 → 实验名字
    m = re.search(r'(<span[^>]*\bclass="pf-page"[^>]*>)(.*?)(</span>)', out, re.S)
    if m:
        old = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        new = shell.short_title(old or title_hint)
        if new and new != old:
            out = out[:m.start(2)] + shell._esc(new) + out[m.end(2):]
            notes.append("页眉 %d 字 → %d 字：%s" % (len(old), len(new), new))
    m = re.search(r"<title>(.*?)</title>", out, re.S)
    if m:
        old_t = m.group(1).strip()
        core = re.sub(r"^师伴\s*[-－—]\s*", "", old_t)
        new_t = "师伴-" + shell.short_title(core)
        if new_t != old_t:
            out = out[:m.start(1)] + shell._esc(new_t) + out[m.end(1):]

    # 2) ① 区不重复名字
    before = out
    out = shell.strip_exp_name(out)
    if out != before:
        notes.append("删除 ① 区重复的实验名称（.exp-name）")

    # 3) 阅读规范：已有就整段换掉（规范会变），没有就插进去
    blk = _normal_block()
    swapped = _swap_block(out, MARK_CSS, '</style>', blk)
    if swapped is not None:
        if swapped != out:
            out = swapped
            notes.append("刷新 normal.css（正文纯黑 + 最小字号 %s）" % _fs_min())
    elif '</head>' in out:
        out = out.replace('</head>', blk + '\n</head>', 1)
        notes.append("注入 normal.css（正文纯黑 + 最小字号 %s）" % _fs_min())

    # 4) 字号兜底脚本，同样整段刷新
    blk = _typo_block()
    swapped = _swap_block(out, MARK_JS, '</script>', blk)
    if swapped is not None:
        if swapped != out:
            out = swapped
            notes.append("刷新 typo.js（运行时字号兜底 %s）" % _fs_min())
    elif '</body>' in out:
        out = out.replace('</body>', blk + '\n</body>', 1)
        notes.append("注入 typo.js（运行时字号兜底）")

    return out, notes


def css_pending(html_path):
    """同目录里哪些 css 副本和平台最新版不一致（只算已存在的）。"""
    d = os.path.dirname(os.path.abspath(html_path))
    gone = []
    for name in ('frame.css', 'exp.css'):
        dst = os.path.join(d, name)
        src = os.path.join(shell.FRAME_DIR, name)
        if not os.path.exists(dst) or not os.path.exists(src):
            continue
        if io.open(dst, encoding='utf-8').read() != io.open(src, encoding='utf-8').read():
            gone.append(name)
    return gone


def sync_css(html_path):
    """把同目录的 frame.css / exp.css 副本同步成平台最新版（只覆盖已存在的）。"""
    d = os.path.dirname(os.path.abspath(html_path))
    for name in css_pending(html_path):
        shutil.copyfile(os.path.join(shell.FRAME_DIR, name), os.path.join(d, name))


def main():
    ap = argparse.ArgumentParser(description="给已生成的页面补 / 刷新 UI 规范")
    ap.add_argument("paths", nargs="+", help="要处理的 html 文件")
    ap.add_argument("--dry-run", action="store_true", help="只打印改动，不写文件")
    ap.add_argument("--no-css", action="store_true", help="不同步 css 副本")
    args = ap.parse_args()

    for path in args.paths:
        if not os.path.exists(path):
            print("跳过（不存在）：%s" % path)
            continue
        html = io.open(path, encoding="utf-8").read()
        new, notes = patch(html)
        css = [] if args.no_css else css_pending(path)
        if not notes and not css:
            print("无改动：%s" % path)
            continue
        print("%s" % path)
        for n in notes:
            print("   - " + n)
        for n in css:
            print("   - 同步 %s（字号档位）" % n)
        if args.dry_run:
            continue
        if notes:
            io.open(path, "w", encoding="utf-8").write(new)
        if css:
            sync_css(path)


if __name__ == "__main__":
    main()
