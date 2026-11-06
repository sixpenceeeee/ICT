# -*- coding: utf-8 -*-
"""
把交付页里内联的旧版 math.js 整段换成 frame/math.js 最新版。

背景：math.js 的兜底 auto() 会「接管」页面画布（把页面自己的 canvas 设为
display:none，再新建一张画布画一版写死参数的图）。页面之后的每次重绘都落在
被隐藏的节点上，学生拖滑块就看到「演示画面不随系数变化」。

边界必须卡死，否则会像上一次那样把页面自己的脚本一起删掉：
  - 起点：math.js 的文件头注释（唯一）
  - 终点：math.js IIFE 的收尾 `window.MATH = {...};\n})();`（唯一）
  - 落地前断言：终点之后确实是页面自己的 JS，且页面 JS 主体仍在
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(ROOT, "frame", "math.js")

START = "/* math.js —— 数学学科场景库（基于 vis.js 原语，外壳注入）"
END = "  window.MATH = { cubeCut: cubeCut, funcPlot: funcPlot, auto: auto };\n})();"


def relib(path, dry=False):
    src = io.open(path, encoding="utf-8").read()
    newlib = io.open(LIB, encoding="utf-8").read().strip()

    i = src.find(START)
    if i < 0:
        return "skip:未内联 math.js"
    j = src.find(END, i)
    if j < 0:
        return "FAIL:找不到 math.js 的收尾标记"

    j_end = j + len(END)

    # 起点到终点之间不许出现 </script>：否则说明库的收尾标记不是这一块的，
    # 按它切会跨过 </script> 把页面自己的脚本一起吃掉（上次就是这么翻的车）。
    if "</script>" in src[i:j_end]:
        return "FAIL:math.js 区间内含 </script>，边界不可信"
    # 终点之后必须还找得到 </script>，且它不能离得太远（说明还在同一个脚本块里）
    tail = src[j_end:]
    k = tail.find("</script>")
    if k < 0:
        return "FAIL:math.js 收尾后没有 </script>，边界不可信"
    if k > 20000:
        return "FAIL:收尾标记后 20k 字符内没有 </script>，边界可疑"

    out = src[:i] + newlib + src[j_end:]

    # 落地前自检
    if len(out) < len(src) * 0.5:
        return "FAIL:替换后体积异常缩小，已中止"
    if out.count(START) != 1:
        return "FAIL:替换后出现多个 math.js 头，已中止"
    if "var cv = " not in out and "getElementById('cv')" not in out:
        return "WARN:未找到页面脚本特征，请人工确认"

    if not dry:
        io.open(path, "w", encoding="utf-8").write(out)
    return "ok:%d→%d 字节" % (len(src), len(out))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry" in sys.argv
    for p in args:
        print("%-60s %s" % (os.path.basename(p), relib(p, dry)))


if __name__ == "__main__":
    main()
