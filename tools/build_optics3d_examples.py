# -*- coding: utf-8 -*-
"""不调用模型，构建 3D 凸透镜成像的离线示例页。

照 tools/build_circuit_examples.py 的做法：模型参数 → 六区内容 → 外壳内联 →
shell.validate 全绿才落盘。产物两处：examples/optics/ 与 03_generator_agent/output/物理/。

跑法（仓库根）：python tools/build_optics3d_examples.py
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import optics_resources  # noqa: E402
import shell  # noqa: E402


def build():
    model = optics_resources.resolve_model()
    sections = optics_resources.render_sections(model)
    html = shell.render(optics_resources.TITLE, sections, optics_resources.SLUG)

    problems = shell.validate(html)
    if problems:
        raise SystemExit("外壳校验未通过：\n- " + "\n- ".join(problems))

    targets = [
        ROOT / "examples" / "optics" / "lens3d.html",
        ROOT / "03_generator_agent" / "output" / "物理" / "教学资源_凸透镜成像3D.html",
    ]
    for path in targets:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
        print("%s | %.1f KB" % (path.relative_to(ROOT), len(html.encode("utf-8")) / 1024.0))
    print("validate: OK（六区、注入、无外链）")


if __name__ == "__main__":
    build()
