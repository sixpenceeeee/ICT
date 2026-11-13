# -*- coding: utf-8 -*-
"""② 演示区：画布 + 图例 + 说明。

规范里这一区只放实验对象本身：不放步骤清单、不放标题、不放图片素材。
画布上 `data-visual-type` 必须与骨架声明一致，审查器按它选择对应的绘图判据
（器材看材质、图像看坐标轴、几何看拓扑），写错会让整页按错误标准打分。
"""

from . import atoms


def render_stage(spec):
    stage = spec.get("stage") or {}
    canvas = atoms.render_stage_canvas(
        stage.get("canvas_id", "lesson-scene"),
        spec.get("visual") or "apparatus",
        stage.get("aria") or spec.get("title") or "演示区")
    legend = atoms.render_legend(stage.get("legend") or [], klass="exp-note lesson-key")
    html = ('<div class="lesson-stage"><div class="lesson-plot">%s</div>%s</div>'
            % (canvas, legend))
    note = (stage.get("note") or "").strip()
    if note:
        html += atoms.render_note(note)
    return html


def markers(spec):
    return [("data-visual-type", spec.get("visual") or "apparatus")]
