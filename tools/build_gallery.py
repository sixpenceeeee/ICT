# 把 deliver/六学科统一质感/gallery.html（外链 frame/*.js）打成单文件离线版
# 用法：python build_gallery.py
import os, re, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(BASE, "deliver", "六学科统一质感", "gallery.html")
OUT = os.path.join(BASE, "deliver", "六学科统一质感", "六学科统一质感.html")

html = open(SRC, encoding="utf-8").read()

def inline(m):
    path = m.group(1)
    full = os.path.normpath(os.path.join(os.path.dirname(SRC), path))
    if not os.path.exists(full):
        sys.exit("缺少库文件：%s" % full)
    code = open(full, encoding="utf-8").read()
    # 防止库里的 </script> 提前闭合
    code = code.replace("</script>", "<\\/script>")
    return "<script>\n/* ===== %s ===== */\n%s\n</script>" % (os.path.basename(full), code)

html2 = re.sub(r'<script src="([^"]+)"></script>', inline, html)
if 'src="' in html2 and ".js" in html2:
    left = re.findall(r'<script src="([^"]+)"></script>', html2)
    if left:
        sys.exit("仍有未内联的脚本：%s" % left)

open(OUT, "w", encoding="utf-8").write(html2)
print("已生成：%s（%.0f KB）" % (OUT, os.path.getsize(OUT) / 1024))
for name in ["vis.js", "chem.js", "phys.js", "math.js", "bio.js", "geo.js", "cs.js"]:
    p = os.path.join(BASE, "frame", name)
    print("  内联 %-9s %6.1f KB" % (name, os.path.getsize(p) / 1024))
