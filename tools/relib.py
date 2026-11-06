# -*- coding: utf-8 -*-
"""
把交付页里内联的旧版场景库整段换成 frame/ 下最新版。

背景：场景库的「兜底 auto()」以前不判断页面是否自绘，直接在**同一张画布**
上作画，phys.js / chem.js 还会再挂 input 监听补一帧。两套版面抢一张画布，
表现就是演示区闪动、背景来回换。库修好后，需要把已生成的页面同步刷新。

边界必须卡死（否则会像上次那样把页面自己的脚本一起删掉）：
  - 起点：库文件头注释（唯一）
  - 终点：库 IIFE 的收尾 `window.<NS> = {...}\n})();`（在起点之后首次出现）
  - 落地前断言：起点到终点之间不含 </script>，确保没有跨出这一个脚本块
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRAME = os.path.join(ROOT, "frame")

# 库名 -> (文件头标记, 全局命名空间)
LIBS = {
    "vis": ("/* vis.js ——", "VIS"),
    "phys": ("/* phys.js ——", "PHYS"),
    "math": ("/* math.js ——", "MATH"),
    "chem": ("/* chem.js ——", "CHEM"),
    "bio": ("/* bio.js ——", "BIO"),
    "geo": ("/* geo.js ——", "GEO"),
    "cs": ("/* cs.js ——", "CS"),
}


def find_block(src, header, ns):
    """返回 (起点, 终点)；找不到返回 None。"""
    i = src.find(header)
    if i < 0:
        return None
    kw = "window.%s = " % ns
    j = src.find(kw, i)
    if j < 0:
        return None
    k = src.find("\n})();", j)
    if k < 0:
        return None
    return i, k + len("\n})();")


def relib(path, names=None, dry=False):
    src = io.open(path, encoding="utf-8").read()
    out = src
    report = []
    for name in (names or LIBS.keys()):
        header, ns = LIBS[name]
        blk = find_block(out, header, ns)
        if not blk:
            continue                      # 这一页没内联该库
        i, j_end = blk
        if "</script>" in out[i:j_end]:
            report.append("%s:FAIL(区间含</script>)" % name)
            continue
        if out[j_end:].find("</script>") < 0:
            report.append("%s:FAIL(收尾后无</script>)" % name)
            continue
        new = io.open(os.path.join(FRAME, name + ".js"), encoding="utf-8").read().strip()
        if out[i:j_end].strip() == new.strip():
            report.append("%s:已是最新" % name)
            continue
        out = out[:i] + new + out[j_end:]
        if len(out) < len(src) * 0.5:
            return "FAIL:%s 替换后体积异常缩小，已中止" % name
        report.append("%s:已更新" % name)

    if out != src and not dry:
        bak = path + ".bak"
        if not os.path.exists(bak):
            io.open(bak, "w", encoding="utf-8").write(src)
        io.open(path, "w", encoding="utf-8").write(out)
    return ("已更新" if out != src else "无变化") + " %d→%d 字节 | %s" % (
        len(src), len(out), "，".join(report) or "本页未内联这些库")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry" in sys.argv
    for p in args:
        print("%-46s %s" % (os.path.basename(p), relib(p, dry=dry)))


if __name__ == "__main__":
    main()
