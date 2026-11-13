# -*- coding: utf-8 -*-
"""page_components —— 兼容层（原子组件已迁到 components/atoms.py）。

保留这个模块是为了不让历史渲染器（math_page_templates /
solver_templates）被迫改动：它们继续 `from page_components import ...`，
拿到的就是组件层的同一份实现。

新代码请直接 `from components import atoms` / `from components import registry`。
"""

from components.atoms import (  # noqa: F401
    escape, raw,
    render_action_buttons, render_comparison_panel, render_error_slot,
    render_formula_block, render_learning_goals, render_legend,
    render_note, render_number_control, render_record_table,
    render_result_card, render_select_control, render_slider_number_control,
    render_range_number_control, render_stage_canvas, render_subject_tags,
    render_teaching_section,
)

__all__ = [
    "escape", "raw",
    "render_action_buttons", "render_comparison_panel", "render_error_slot",
    "render_formula_block", "render_learning_goals", "render_legend",
    "render_note", "render_number_control", "render_record_table",
    "render_result_card", "render_select_control", "render_slider_number_control",
    "render_range_number_control", "render_stage_canvas", "render_subject_tags",
    "render_teaching_section",
]
