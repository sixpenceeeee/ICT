# -*- coding: utf-8 -*-
"""
给各学科场景库的「兜底 auto()」统一加上让位判断。

问题：库在没有判断页面是否自绘的情况下，直接在**页面同一张画布**上作画，
      phys.js / chem.js 还会再挂 input 监听「补一帧」。于是每次拖滑块，
      页面画一遍、库再覆盖一遍，谁排在最后谁露脸且顺序逐帧漂移 —— 表现就是
      演示区闪动、背景来回换。

修法：加 isBlank(cv) —— 画布已有内容就说明页面自己在画，库彻底收手
     （既不画，也不挂监听）。同时把接管时机从 DOMContentLoaded 推到
     load 之后，避免误把「还没来得及画」当成「没画」。
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRAME = os.path.join(ROOT, "frame")

ISBLANK = u"""  /* 画布上到底有没有东西。
   *
   * 库的兜底和页面自己的 draw() 用的是**同一张画布**（不是各画一张），
   * 两边都画 = 每次交互产出两幅互斥的版面，谁排在最后谁露脸，顺序还会漂移
   * → 学生看到画面闪动、背景来回换。所以只要页面已经自己画了东西，
   * 库就必须彻底收手：不画，也不挂监听。
   */
  function isBlank(cv0) {
    try {
      var w = cv0 && cv0.width, h = cv0 && cv0.height;
      if (!w || !h) return true;
      var c2 = cv0.getContext('2d');
      if (!c2) return true;
      var d = c2.getImageData(0, 0, w, h).data;
      var rowBytes = w * 4;
      // 每 16 行采一行，采到的行整行扫完：横竖线条都不会漏
      for (var y = 0; y < h; y += 16) {
        var base = y * rowBytes;
        for (var x = 0; x < w; x++) {
          var i = base + x * 4;
          if (d[i + 3] < 8) continue;                                   // 全透明 = 没画
          if (d[i] > 246 && d[i + 1] > 246 && d[i + 2] > 246) continue; // 白/近白底
          return false;
        }
      }
      return true;
    } catch (e) {
      return true;
    }
  }

"""

SCHEDULE = u"""  /* 时机同样关键：必须等页面自己的脚本跑完、画完第一帧再判断是否兜底。
   * 以前挂在 DOMContentLoaded+setTimeout(0)，页面可能还没画 → 误判空白 → 抢画布。
   * 改成 load 之后再等两帧。 */
  function scheduleAuto() {
    var run = function () {
      requestAnimationFrame(function () {
        requestAnimationFrame(function () {
          try { %s(); } catch (e) { }
        });
      });
    };
    if (document.readyState === 'complete') setTimeout(run, 60);
    else window.addEventListener('load', function () { setTimeout(run, 60); });
  }
  scheduleAuto();
"""

OLD_SCHED = """  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { setTimeout(%s, 0); });
  } else { setTimeout(%s, 0); }
"""

OLD_SCHED_ALT = """  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { setTimeout(%s, 0); });
  } else {
    setTimeout(%s, 0);
  }
"""

# 库名 -> (文件名, 兜底函数名, 已画标记名)
LIBS = [
    ("BIO", "bio.js", "auto", "__BIO_DRAWN__"),
    ("GEO", "geo.js", "auto", "__GEO_DRAWN__"),
    ("CS", "cs.js", "auto", "__CS_DRAWN__"),
    ("CHEM", "chem.js", "autoScene", "__CHEM_DRAWN__"),
]


def patch(name, file, fn, flag):
    path = os.path.join(FRAME, file)
    s = io.open(path, encoding="utf-8").read()
    if "function isBlank(" in s:
        return "skip:已有 isBlank"

    anchor = "  function %s() {" % fn
    if anchor not in s:
        return "FAIL:找不到 %s 函数" % fn

    # 1) 在兜底函数前插入 isBlank
    s = s.replace(anchor, ISBLANK + anchor, 1)

    # 2) 在「拿到 cv 之后」插入让位判断
    guardline = "    var cv = document.querySelector('.exp-canvas-box canvas') || document.querySelector('canvas');\n    if (!cv) return;\n"
    if guardline not in s:
        return "FAIL:找不到 cv 定位语句"
    guard = ("    // 页面自己画得出来就必须让位，否则两套版面抢同一张画布（见 isBlank 注释）\n"
             "    if (!isBlank(cv)) { window.%s = true; return; }\n" % flag)
    s = s.replace(guardline, guardline + guard, 1)

    # 3) 换掉调度方式
    for tpl in (OLD_SCHED, OLD_SCHED_ALT):
        old = tpl % (fn, fn)
        if old in s:
            s = s.replace(old, SCHEDULE % fn, 1)
            break
    else:
        return "FAIL:找不到调度代码"

    io.open(path, "w", encoding="utf-8").write(s)
    return "ok"


def main():
    for name, file, fn, flag in LIBS:
        print("%-10s %-10s %s" % (name, file, patch(name, file, fn, flag)))


if __name__ == "__main__":
    main()
