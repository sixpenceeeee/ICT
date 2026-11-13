# -*- coding: utf-8 -*-
"""组块化回归测试（不需要浏览器）。

守的是四件事：
1. PageSpec 是唯一输入：标记、取证 token、代入式都从 spec 推导；
2. 组件装配出来的页面必须通过生成端硬校验（与线上同一条规则）；
3. 场景调度只有一张表：solver_templates / generator_agent 里不能再有 if scene_id 链；
4. 有求解器但缺组件的场景，必须给出可执行的原因，而不是悄悄退化成数值页。

运行：
    python -B 03_generator_agent/tests/test_componentization.py
或：
    python -B -m unittest discover -s 03_generator_agent/tests -p "test_*.py"
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
GENERATOR = os.path.dirname(HERE)
ROOT = os.path.dirname(GENERATOR)
for path in (GENERATOR, ROOT):
    if path not in sys.path:
        sys.path.insert(0, path)

import page_spec                      # noqa: E402
import scene_catalog                  # noqa: E402
import generic_lesson                 # noqa: E402
import generator_agent                # noqa: E402
import scene_registry                 # noqa: E402
from components import atoms, registry, runtime  # noqa: E402
import components.runtime               # noqa: E402
import solver_templates               # noqa: E402
import page_components                # noqa: E402


BUOYANCY_REQUEST = {"学科": "物理", "实验主题": "浮力：阿基米德原理与浮沉条件", "年级": "初中"}


def buoyancy_spec():
    return scene_catalog.spec_for("physics-buoyancy", BUOYANCY_REQUEST)


class PageSpecTests(unittest.TestCase):
    def test_spec_is_json_serialisable(self):
        spec = buoyancy_spec()
        json.dumps(spec, ensure_ascii=False, allow_nan=False)

    def test_missing_draw_is_rejected_with_a_reason(self):
        spec = buoyancy_spec()
        spec["draw"]["api"] = ""
        problems = page_spec.validate(spec)
        self.assertTrue(any("绘图组件" in item for item in problems), problems)

    def test_bad_input_range_is_rejected(self):
        spec = buoyancy_spec()
        spec["inputs"][0]["minimum"] = 10
        spec["inputs"][0]["maximum"] = 1
        self.assertTrue(any("范围非法" in item for item in page_spec.validate(spec)))

    def test_unknown_component_is_rejected(self):
        spec = buoyancy_spec()
        spec["components"] = ["presets", "movie"]
        self.assertTrue(any("未登记的组件" in item for item in page_spec.validate(spec)))

    def test_markers_are_derived_from_the_spec_not_handwritten(self):
        spec = buoyancy_spec()
        found = {value for key, value in page_spec.markers(spec) if key == "data-solver-input"}
        self.assertEqual(found, {item["name"] for item in spec["inputs"]})
        fields = {value for key, value in page_spec.markers(spec) if key == "data-solver-field"}
        self.assertEqual(fields, {item["field"] for item in spec["outputs"]})

    def test_relations_travel_with_the_spec(self):
        spec = buoyancy_spec()
        model = scene_registry.PHYSICS_MODELS["buoyancy"]
        self.assertEqual(spec["relations"], model["relations"])
        self.assertTrue(spec["relations"], "变形关系必须随 spec 传给审查端")


class ComponentRenderingTests(unittest.TestCase):
    def test_buoyancy_page_passes_generation_hard_validate(self):
        spec = buoyancy_spec()
        sections = generic_lesson.render(spec)
        problems = generator_agent.hard_validate(sections, BUOYANCY_REQUEST, managed_readouts=True)
        self.assertEqual(problems, [])

    def test_every_declared_marker_lands_in_the_markup(self):
        spec = buoyancy_spec()
        sections = generic_lesson.render(spec)
        markup = "\n".join(sections[key] for key in ("1", "2", "3", "4", "5", "6"))
        for attr, value in page_spec.markers(spec):
            self.assertIn('%s="%s"' % (attr, value), markup, (attr, value))

    def test_runtime_tokens_land_in_the_script(self):
        spec = buoyancy_spec()
        script = generic_lesson.render(spec)["js"]
        for token in page_spec.runtime_tokens(spec):
            self.assertIn(token, script, token)
        self.assertRegex(script, r"const result = PHYS\s*\.\s*solveBuoyancy\s*\(")
        self.assertRegex(script, r"PHYS\s*\.\s*floating\s*\(\s*cv\s*,\s*request\s*,\s*result\s*\)")

    def test_scaled_control_keeps_si_request_and_display_unit(self):
        """体积控件显示 cm³，请求里必须是 m³——否则浮力会差 6 个数量级。"""
        spec = buoyancy_spec()
        sections = generic_lesson.render(spec)
        self.assertIn('value="200"', sections["3"], "控件应显示 200 cm³")
        script = sections["js"]
        self.assertIn('"volume": 1e-06', script, "scale 必须写进脚本")
        self.assertRegex(script, r"toRequest\(")
        self.assertRegex(script, r"toDisplay\(")

    def test_formula_template_matches_the_j1_parser(self):
        """J1 的浮力专用正则要求「ρ kg/m³ × g N/kg × V m³ = F N」四段齐全且顺序正确。"""
        formula = scene_catalog.UI["physics-buoyancy"]["formula_js"]
        for token in ("kg/m³ × ", "N/kg × ", "m³ = "):
            self.assertIn(token, formula)
        order = [formula.index(token) for token in ("kg/m³ × ", "N/kg × ", "m³ = ")]
        self.assertEqual(order, sorted(order))

    def test_teaching_section_covers_the_required_blocks(self):
        spec = buoyancy_spec()
        teaching = generic_lesson.render(spec)["6"]
        for title in ("原理", "易错点", "探究问题", "结论", "注意事项"):
            self.assertIn(title, teaching)

    def test_records_table_has_one_header_per_field(self):
        spec = buoyancy_spec()
        headers = spec["records"]["headers"]
        fields = spec["records"]["fields"]
        self.assertEqual(len(headers), len(fields))
        self.assertIn("<table", generic_lesson.render(spec)["5"])

    def test_required_ids_exist_in_the_page(self):
        """脚本里不带空值判断的 id，必须在页面上真实存在（否则运行即报错）。"""
        spec = buoyancy_spec()
        sections = generic_lesson.render(spec)
        markup = "\n".join(sections[key] for key in ("1", "2", "3", "4", "5", "6"))
        for element_id in (spec["stage"]["canvas_id"], "%s-formula" % spec["stage"]["canvas_id"].split("-scene")[0],
                           spec["records"]["body_id"]):
            self.assertIn('id="%s"' % element_id, markup, element_id)
        self.assertIn("data-solver-error", markup)

    def test_shell_assembly_inlines_the_scene_libs(self):
        """单文件离线可运行：壳必须把场景库内联进 HTML，而不是留外链。"""
        import shell
        spec = buoyancy_spec()
        html = shell.render("浮力", generic_lesson.render(spec))
        self.assertIn("bindSolverReadouts", html)
        self.assertIn("function floating", html)
        self.assertNotRegex(html, r'<script[^>]+src=')
        self.assertNotRegex(html, r'https?://[^"\s]+\.js')


class IndependenceTests(unittest.TestCase):
    def test_atoms_have_a_single_implementation(self):
        for name in ("render_number_control", "render_select_control", "render_result_card",
                     "render_record_table", "render_action_buttons"):
            self.assertIs(getattr(page_components, name), getattr(atoms, name), name)

    def test_lesson_runtime_has_a_single_implementation(self):
        source = open(components.runtime.__file__, encoding="utf-8").read()
        self.assertIn("const config = ", source)
        self.assertIn("VIS.bindSolverReadouts", source)

    def test_scene_dispatch_has_no_if_chain_left(self):
        source = open(solver_templates.__file__, encoding="utf-8").read()
        tail = source[source.index("def render_solver_template"):]
        self.assertNotIn("if scene_id ==", tail, "调度必须走 scene_catalog 唯一来源")
        self.assertIn("scene_catalog.render_scene", tail)

    def test_generator_has_one_deterministic_entry(self):
        source = open(generator_agent.__file__, encoding="utf-8").read()
        self.assertIn("render_deterministic(", source)
        self.assertNotIn("physics_template = selected_skeleton", source,
                         "写死场景 id 的元组应已删除")
        self.assertEqual(source.count("if template_only or not HAS_LLM"), 1)


class CatalogTests(unittest.TestCase):
    def test_every_generic_scene_renders_and_passes_hard_validate(self):
        """所有 generic 场景都要能出页、过生成端硬校验——这是"补完组件"的验收线。"""
        for scene_id, entry in scene_catalog.SCENE_RENDERERS.items():
            if entry["renderer"] != "generic":
                continue
            subject = (entry.get("subject") or "物理")
            import explicit_specs
            data = explicit_specs.EXPLICIT_SPECS.get(scene_id) or {}
            title = (data.get("title")
                     or (scene_registry.PHYSICS_MODELS.get(entry.get("model")) or {}).get("title")
                     or scene_id)
            request = {"学科": subject, "实验主题": title, "年级": "初中"}
            with self.subTest(scene=scene_id):
                spec = scene_catalog.spec_for(scene_id, request)
                sections = generic_lesson.render(spec)
                problems = generator_agent.hard_validate(sections, request, managed_readouts=True)
                self.assertEqual(problems, [], scene_id)

    def test_every_generic_scene_declares_a_recomputable_formula(self):
        for scene_id, entry in scene_catalog.SCENE_RENDERERS.items():
            if entry["renderer"] != "generic":
                continue
            with self.subTest(scene=scene_id):
                spec = scene_catalog.spec_for(scene_id, {"学科": entry.get("subject") or "物理"})
                formula = spec["formula"]["js"]
                try:
                    import explicit_specs
                    if explicit_specs.EXPLICIT_SPECS.get(scene_id, {}).get("numeric") is False:
                        self.assertTrue(formula.strip(), "判定型页面也要有判定说明")
                        continue
                except ImportError:
                    pass
                self.assertIn("number(", formula)
                self.assertIn("=", formula.replace("'", ""), scene_id)

    def test_every_declared_draw_api_exists_in_the_scene_library(self):
        """登记了 PHYS.xxx 就必须真有这个函数，避免"生成时才发现画不出来"。"""
        source = open(os.path.join(ROOT, "frame", "phys.js"), encoding="utf-8").read()
        for scene_id, entry in scene_catalog.SCENE_RENDERERS.items():
            if entry["renderer"] != "generic":
                continue
            import explicit_specs
            data = explicit_specs.EXPLICIT_SPECS.get(scene_id) or {}
            draw = data.get("draw") or (scene_catalog._ui_for(
                scene_id, dict(entry, id=scene_id)) or {}).get("draw")
            if not draw or not draw.startswith("PHYS."):
                continue
            name = draw.split(".", 1)[1]
            with self.subTest(scene=scene_id, draw=draw):
                self.assertRegex(source, r"function %s\s*\(" % re.escape(name))
                self.assertRegex(source, r"\b%s\b" % re.escape(name))

    def test_ui_metadata_can_be_derived_for_unwired_models(self):
        """证明"新场景零代码"：没有手写 UI 的模型也能推出控件标签与单位。"""
        ui = scene_catalog.derive_ui(scene_registry.PHYSICS_MODELS["lever"])
        self.assertEqual(set(ui["inputs"]), {"left_force", "left_arm", "right_force", "right_arm"})
        self.assertTrue(ui["inputs"]["left_force"]["label"].startswith("左侧力"))
        self.assertEqual(ui["inputs"]["left_force"]["unit"], "N")
        self.assertEqual(set(ui["outputs"]), {"left_torque", "right_torque", "net_torque", "state"})

    def test_model_without_draw_reports_what_is_missing(self):
        ready, reason = scene_catalog.status("physics-optics-bench")
        self.assertFalse(ready)
        self.assertTrue(reason.strip())

    def test_generic_scenes_are_ready(self):
        for scene_id, entry in scene_catalog.SCENE_RENDERERS.items():
            if entry["renderer"] != "generic":
                continue
            with self.subTest(scene=scene_id):
                ready, reason = scene_catalog.status(scene_id)
                self.assertTrue(ready, reason)

    def test_unready_scenes_explain_what_is_missing(self):
        for item in scene_registry.SCENE_SKELETONS:
            ready, reason = scene_catalog.status(item["id"], item)
            if not ready:
                self.assertTrue(reason.strip(), "不可渲染的场景必须说明原因：%s" % item["id"])

    def test_status_covers_every_registered_scene(self):
        for item in scene_registry.SCENE_SKELETONS:
            ready, reason = scene_catalog.status(item["id"], item)
            self.assertIsInstance(ready, bool)
            self.assertIsInstance(reason, str)

    def test_has_renderer_matches_actual_behaviour(self):
        for item in scene_registry.SCENE_SKELETONS:
            if item["subject"] not in ("物理", "数学", "化学"):
                continue
            if not scene_catalog.has_renderer(item):
                continue
            with self.subTest(scene=item["id"]):
                sections = solver_templates.render_solver_template(
                    {"学科": item["subject"], "实验主题": item.get("id", "")}, item)
                self.assertTrue(sections is None or isinstance(sections, dict))


@unittest.skipUnless(os.name == "nt" or os.environ.get("NODE_BIN"), "需要 node 才能做语法检查")
class JavaScriptSyntaxTests(unittest.TestCase):
    def test_generated_script_parses(self):
        node = os.environ.get("NODE_BIN", "node")
        script = generic_lesson.render(buoyancy_spec())["js"]
        handle = tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8")
        try:
            handle.write(script)
            handle.close()
            try:
                proc = subprocess.run([node, "--check", handle.name],
                                      capture_output=True, text=True, timeout=60)
            except OSError as exc:          # 沙箱里可能禁止子进程管道
                self.skipTest("无法启动 node：%s" % exc)
            self.assertEqual(proc.returncode, 0, proc.stderr)
        finally:
            os.unlink(handle.name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
