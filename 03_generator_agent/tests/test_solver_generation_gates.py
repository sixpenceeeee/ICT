# -*- coding: utf-8 -*-
import json
import os
import sys
import tempfile
import unittest
import zipfile
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "../.."))
sys.path.insert(0, PROJECT)
sys.path.insert(0, os.path.join(PROJECT, "03_generator_agent"))

import generator_agent
import run_pipeline
from solver_templates import render_ksp_template
from scene_registry import select_page_skeleton
from solver_templates import resolve_ksp_config


class SolverGenerationGateTests(unittest.TestCase):
    def setUp(self):
        self.ksp_request = {
            "学科": "化学",
            "年级": "高中二年级",
            "实验名称": "氟化钙溶解平衡",
            "实验主题": "CaF₂ 溶解平衡与共同离子效应，Ksp=4e-11",
            "学习目标": ["比较 Q 与 Ksp 并观察共同离子效应"],
        }

    def test_ksp_template_calls_solver_and_passes_contract(self):
        sections = render_ksp_template(self.ksp_request)
        self.assertIsNotNone(sections)
        self.assertEqual(generator_agent.hard_validate(sections, self.ksp_request), [])
        self.assertIn("CHEMSOLVER.solveSolubilityEquilibrium", sections["js"])
        self.assertIn("window.__CHEM_KSP_REQUEST__", sections["js"])
        self.assertIn("window.__CHEM_KSP_RESULT__", sections["js"])

    def test_linear_system_contract_uses_actual_statuses_and_accepts_try_assignment(self):
        req = {"学科": "数学", "实验主题": "一次函数与二元一次方程组"}
        contract = select_page_skeleton(req)["solver_contract"]
        self.assertIn('"status":"唯一交点"', contract)
        self.assertIn('"平行"', contract)
        self.assertIn('"重合"', contract)
        sections = {
            "1": "<p>学习目标</p>",
            "2": '<canvas data-visual-type="graph"></canvas>',
            "3": "".join(f'<label class="exp-field"><input type="number" data-solver-input="{name}"></label>'
                         for name in ("k1", "b1", "k2", "b2")),
            "4": '<div class="exp-formula">计算结果</div>' + "".join(
                f'<span data-solver-field="{name}">—</span>' for name in ("status", "x", "y")),
            "5": '<table class="exp-table"><tr><th>数据</th></tr></table>',
            "6": "<p>比较解的个数。</p>",
            "js": """
                let result = null;
                try {
                    window.__MATH_LINEAR_SYSTEM_REQUEST__ = cfg;
                    result = MATH.solveLinearSystem(cfg);
                    window.__MATH_LINEAR_SYSTEM_RESULT__ = result;
                    window.__DATA__ = {params: cfg, result};
                    VIS.bindSolverReadouts(result);
                    MATH.linearSystem(cv, cfg, result);
                } catch (failure) {
                    VIS.bindSolverReadouts(null);
                }
            """,
        }
        self.assertEqual(generator_agent.hard_validate(sections, req, managed_readouts=True), [])
        sections["js"] = sections["js"].replace("cv, cfg, result", "cv, cfg, unrelated")
        self.assertTrue(any("返回的结果传给" in issue for issue in
                            generator_agent.hard_validate(sections, req, managed_readouts=True)))
        sections["js"] = sections["js"].replace("bindSolverReadouts(result)", "bindSolverReadouts(unrelated)")
        self.assertTrue(any("直接绑定" in issue for issue in
                            generator_agent.hard_validate(sections, req, managed_readouts=True)))

    def test_template_only_solver_without_scene_template_is_blocked_by_contract(self):
        request = {
            "学科": "物理", "实验名称": "声速验收", "实验主题": "波的传播与声速",
            "学习目标": ["观察波前到达"],
        }
        with mock.patch.object(generator_agent, "render_solver_template", return_value=None), \
                mock.patch("solver_templates.render_solver_template", return_value=None):
            _sections, meta = generator_agent.generate(request, {}, template_only=True)
        self.assertFalse(meta["生成契约通过"])
        self.assertTrue(meta["问题"])
        self.assertIn("求解器契约", meta["来源"])

    def test_linear_system_uses_requested_equations_without_model_code(self):
        req = {"学科": "数学", "实验主题": "一次函数与二元一次方程组",
               "原始需求": "比较 y = -2.5x + 4 与 y = 3 的交点。"}
        with mock.patch.object(generator_agent, "call_llm", side_effect=AssertionError("LLM should not run")):
            sections, meta = generator_agent.generate(req, {})
        self.assertTrue(meta["生成契约通过"], meta["问题"])
        self.assertEqual(meta["来源"], "一次函数参数化页面模板")
        self.assertIn('"k1": -2.5, "b1": 4.0, "k2": 0, "b2": 3.0', sections["js"])
        self.assertRegex(sections["js"], r"VIS\.bindSolverReadouts\(result[,)]")

    def test_linear_template_does_not_replace_a_single_line_request(self):
        req = {"学科": "数学", "实验主题": "一次函数的斜率与截距",
               "原始需求": "用 y=2x+1 演示斜率和截距。"}
        self.assertIsNone(generator_agent.render_solver_template(req, select_page_skeleton(req)))

    def test_plane_mirror_composes_two_lessons_with_fixed_solver_wiring(self):
        req = {"学科": "物理", "实验主题": "平面镜成像", "年级": "初中八年级"}
        distance = dict(req, 原始需求="探究物距与像距，初始物距为 300 厘米，提供实验记录表和代入步骤。")
        observer = dict(req, 原始需求="比较移动观察者前后的可见范围，提供对比表和探究问题。")
        with mock.patch.object(generator_agent, "call_llm", side_effect=AssertionError("no model code")):
            first, first_meta = generator_agent.generate(distance, {})
            second, second_meta = generator_agent.generate(observer, {})
        for sections, meta in ((first, first_meta), (second, second_meta)):
            self.assertTrue(meta["生成契约通过"], meta["问题"])
            self.assertEqual(meta["来源"], "PageSpec 组件装配页面")
            self.assertEqual(sections["3"].count("step=\"any\""), 5)
            self.assertRegex(sections["js"], r"VIS\.bindSolverReadouts\(result[,)]")
            self.assertIn("PHYS.drawPlaneMirror(cv, request, result)", sections["js"])
        self.assertIn('"object_distance": 3.0', first["js"])
        self.assertNotIn('data-page-component="comparison"', first["4"])
        self.assertIn('data-page-component="comparison"', second["4"])
        self.assertNotEqual(first["4"], second["4"])

    def test_wave_component_has_precise_time_controls(self):
        req = {"学科": "物理", "实验主题": "波的传播与声速",
               "原始需求": "观察时间设为 20 毫秒，提供对比表和代入步骤。"}
        with mock.patch.object(generator_agent, "call_llm", side_effect=AssertionError("no model code")):
            sections, meta = generator_agent.generate(req, {})
        self.assertTrue(meta["生成契约通过"], meta["问题"])
        self.assertEqual(meta["来源"], "PageSpec 组件装配页面")
        self.assertIn('"observation_time": 0.02', sections["js"])
        self.assertIn('data-solver-input="observation_time"', sections["3"])
        self.assertIn('min="0"', sections["3"])
        self.assertIn('step="any"', sections["3"])
        self.assertIn("PHYS.drawWavePropagation(cv, request, result)", sections["js"])
        self.assertRegex(sections["js"], r"VIS\.bindSolverReadouts\(result[,)]")

    def test_template_only_ksp_uses_deterministic_solver_page(self):
        sections, meta = generator_agent.generate(self.ksp_request, {}, template_only=True)
        self.assertTrue(meta["生成契约通过"])
        self.assertEqual(meta["来源"], "Ksp 参数化页面模板")
        self.assertIn("CHEMSOLVER.solveSolubilityEquilibrium", sections["js"])

    def test_ksp_template_uses_changed_request_values_and_learning_goals(self):
        request = dict(self.ksp_request)
        request["实验主题"] = "CaF₂ 溶解平衡与共同离子效应，Ksp=8e-11"
        request["学习目标"] = ["比较不同 Ksp 下的摩尔溶解度"]
        request["核心变量"] = [
            {"名称": "Ca²⁺浓度", "范围": "0 ~ 0.10 mol/L"},
            {"名称": "F⁻浓度", "范围": "0 ~ 0.10 mol/L"},
        ]
        request["交互要求"] = [
            "重置到纯水饱和时的值 [Ca²⁺]=2.15×10⁻⁴ M，[F⁻]=4.30×10⁻⁴ M"
        ]
        sections, meta = generator_agent.generate(request, {}, template_only=False)
        page = "\n".join(sections.values())
        self.assertTrue(meta["生成契约通过"])
        self.assertEqual(meta["Ksp页面参数"]["Ksp"], 8e-11)
        self.assertEqual(meta["Ksp页面参数"]["物质"], "CaF2")
        self.assertAlmostEqual(meta["Ksp页面参数"]["初始离子浓度mol_L"][0], 2.15e-4)
        self.assertAlmostEqual(meta["Ksp页面参数"]["初始离子浓度mol_L"][1], 4.30e-4)
        self.assertIn('value="8e-11"', sections["3"])
        self.assertIn('value="0.000215"', sections["3"])
        self.assertIn('value="0.00043"', sections["3"])
        self.assertIn('type="range"', sections["3"])
        self.assertIn("比较不同 Ksp 下的摩尔溶解度", page)

    def test_ksp_template_composes_different_registered_salt_ions(self):
        request = {"学科": "化学", "实验名称": "碘化铅溶解平衡",
                   "实验主题": "PbI2 溶解平衡，Ksp=8e-9",
                   "学习目标": ["计算 PbI2 的溶解度"],
                   "页面模块": ["共同离子对比"]}
        config = resolve_ksp_config(request)
        sections = render_ksp_template(request, config=config)
        self.assertEqual(config["solid_formula"], "PbI2")
        self.assertEqual([ion["coefficient"] for ion in config["ions"]], [1, 2])
        self.assertEqual(generator_agent.hard_validate(sections, request), [])
        self.assertIn('"solid_formula":"PbI2"', sections["js"])
        self.assertIn("PbI₂(s) ⇌ Pb²⁺(aq) + 2I⁻(aq)", sections["6"])
        self.assertEqual(sections["3"].count("data-chem-ksp-ion-index"), 2)
        self.assertIn('id="ksp-common-ion-comparison"', sections["4"])
        self.assertIn("baselineRequest", sections["js"])

    def test_unknown_ksp_solid_is_rejected_and_not_guessed(self):
        request = {"学科": "化学", "实验名称": "硫化镉溶解平衡",
                   "实验主题": "CdS 溶解平衡，Ksp=1e-28"}
        with self.assertRaisesRegex(ValueError, "尚未登记"):
            resolve_ksp_config(request)

    def test_ksp_configuration_keeps_explicit_zero_initial_concentrations(self):
        request = dict(self.ksp_request)
        request["核心变量"] = [
            {"名称": "Ca²⁺浓度", "范围": "0 ~ 0.1", "初始值": 0},
            {"名称": "F⁻浓度", "范围": "0 ~ 0.1", "初始值": 0},
        ]
        config = resolve_ksp_config(request)
        self.assertEqual([ion["initial_concentration_mol_L"] for ion in config["ions"]], [0, 0])

    def test_ksp_primary_path_does_not_call_model_and_blocks_unsupported_compound(self):
        with mock.patch.object(generator_agent, "call_llm", side_effect=AssertionError("LLM should not run")):
            sections, meta = generator_agent.generate(self.ksp_request, {}, template_only=False)
            self.assertEqual(meta["来源"], "Ksp 参数化页面模板")
            self.assertTrue(meta["生成契约通过"])

            unsupported = dict(self.ksp_request)
            unsupported["实验名称"] = "硫化镉溶解平衡"
            unsupported["实验主题"] = "CdS 溶解平衡，Ksp=1e-28"
            _fallback_sections, blocked = generator_agent.generate(unsupported, {}, template_only=False)
            self.assertFalse(blocked["生成契约通过"])
            self.assertEqual(blocked["来源"], "Ksp 场景暂不支持（不可交付）")
            self.assertTrue(blocked["问题"])

    def test_download_archive_matches_shell_link(self):
        sections = render_ksp_template(self.ksp_request)
        meta = {"生成契约通过": True, "来源": "场景库确定性模板"}
        with tempfile.TemporaryDirectory(dir=os.path.join(PROJECT, "runs")) as output_dir:
            with mock.patch.object(generator_agent, "OUTPUT_DIR", output_dir):
                html_path, meta_path, zip_path = generator_agent.save(sections, self.ksp_request, meta)
            with open(html_path, "r", encoding="utf-8") as f:
                self.assertIn('href="氟化钙溶解平衡.zip"', f.read())
            self.assertEqual(os.path.basename(zip_path), "氟化钙溶解平衡.zip")
            self.assertTrue(os.path.exists(os.path.join(output_dir, "教学资源_氟化钙溶解平衡.zip")))
            with zipfile.ZipFile(zip_path) as archive:
                self.assertIn("氟化钙溶解平衡.html", archive.namelist())
            with open(meta_path, "r", encoding="utf-8") as f:
                self.assertEqual(json.load(f)["压缩包"], "氟化钙溶解平衡.zip")

    def test_release_gate_requires_publish_status_and_generation_contract(self):
        ready = {"结论": "通过", "发布状态": "可发布", "生成契约通过": True, "总分": 80}
        waiting = {"结论": "通过", "发布状态": "待教师审核", "生成契约通过": True, "总分": 100}
        broken_contract = {"结论": "通过", "发布状态": "可发布", "生成契约通过": False, "总分": 100}
        self.assertTrue(run_pipeline.is_release_ready(ready))
        self.assertFalse(run_pipeline.is_release_ready(waiting))
        self.assertTrue(run_pipeline.is_awaiting_teacher_review(waiting))
        self.assertFalse(run_pipeline.is_release_ready(broken_contract))
        self.assertGreater(run_pipeline.round_quality_key(ready), run_pipeline.round_quality_key(waiting))
        self.assertGreater(run_pipeline.round_quality_key(ready), run_pipeline.round_quality_key(broken_contract))


if __name__ == "__main__":
    unittest.main()
