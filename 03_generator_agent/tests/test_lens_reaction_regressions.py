# -*- coding: utf-8 -*-
"""凸透镜 / 铁与硫酸铜 的生成回归用例。

这三条曾经真实踩过：
    1. “凸透镜成像规律”只命中无求解器的通用光具座骨架，退回大模型自由生成；
    2. 铁与硫酸铜被“反应进度/计量”抢走场景，生成纯计量页；
    3. 页面没有暴露 __PHYS_LENS_* / __CHEM_*，审查端无法独立复算。

这里锁住“场景选择”和“确定性渲染契约”，防止下次生成再退化。
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "../.."))
sys.path.insert(0, PROJECT)
sys.path.insert(0, os.path.join(PROJECT, "03_generator_agent"))

import generator_agent                      # noqa: E402
from scene_registry import select_page_skeleton  # noqa: E402
from solver_templates import render_solver_template  # noqa: E402


LENS_REQ = {
    "学科": "物理", "年级": "初中八年级", "实验名称": "凸透镜成像规律",
    "实验主题": "探究物距变化时像距、像的大小、正倒和虚实的变化规律",
    "学习目标": ["能说出 u>2f、f<u<2f、u<f 三种情况的成像特点"],
    "核心变量": [{"名称": "物距", "范围": "1-100", "单位": "cm"}],
    "交互要求": ["能记录多组数据"], "技术要点": "", "风险点": [],
}

FE_REQ = {
    "学科": "化学", "年级": "初中九年级", "实验名称": "铁与硫酸铜溶液的置换反应",
    "实验主题": "铁与硫酸铜溶液发生置换反应，溶液由蓝色逐渐变浅绿色，铁钉表面析出红色铜",
    "学习目标": ["能写出 Fe + CuSO4 → FeSO4 + Cu 并说明现象", "能判断限量试剂"],
    "核心变量": [{"名称": "铁的量", "范围": "0.001-0.2", "单位": "mol"}],
    "交互要求": ["能调节反应进度"], "技术要点": "", "风险点": [],
}


class SceneSelectionTests(unittest.TestCase):
    def test_lens_request_selects_solver_scene(self):
        skeleton = select_page_skeleton(LENS_REQ)
        self.assertEqual(skeleton["id"], "physics-thin-lens")
        self.assertEqual(skeleton["solver_api"], "PHYS.solveThinLens")

    def test_fe_request_selects_reaction_compare_scene(self):
        skeleton = select_page_skeleton(FE_REQ)
        self.assertEqual(skeleton["id"], "chemistry-reaction-compare")
        self.assertEqual(skeleton["solver_api"], "CHEMSOLVER.balanceEquation")


class DeterministicRenderTests(unittest.TestCase):
    def test_lens_page_exposes_solver_contract(self):
        skeleton = select_page_skeleton(LENS_REQ)
        sections = render_solver_template(LENS_REQ, skeleton)
        self.assertIsNotNone(sections)
        markup = "".join(str(sections.get(key) or "") for key in
                         ("1", "2", "3", "4", "5", "6", "css", "js"))
        for token in ("PHYS.solveThinLens", "__PHYS_LENS_REQUEST__",
                      "__PHYS_LENS_RESULT__", 'data-solver-input="u"',
                      'data-solver-input="f"', 'data-solver-field="image_distance_cm"'):
            self.assertIn(token, markup)
        self.assertEqual(generator_agent.hard_validate(sections, LENS_REQ), [])

    def test_fe_page_exposes_solver_contract(self):
        skeleton = select_page_skeleton(FE_REQ)
        sections = render_solver_template(FE_REQ, skeleton)
        self.assertIsNotNone(sections)
        markup = "".join(str(sections.get(key) or "") for key in
                         ("1", "2", "3", "4", "5", "6", "css", "js"))
        for token in ("CHEMSOLVER.balanceEquation", "CHEMSOLVER.solveStoichiometry",
                      "__CHEM_BALANCE_REQUEST__", "__CHEM_BALANCE_RESULT__",
                      "__CHEM_STOICH_REQUEST__", "__CHEM_STOICH_RESULT__",
                      "data-chem-balance-equation", "data-chem-stoich-progress",
                      'data-chem-stoich-amount-index="0"', "CHEM.scene("):
            self.assertIn(token, markup)
        self.assertEqual(generator_agent.hard_validate(sections, FE_REQ), [])

    def test_generate_uses_deterministic_template_without_llm(self):
        for req in (LENS_REQ, FE_REQ):
            sections, meta = generator_agent.generate(req, {}, template_only=True)
            self.assertIsNotNone(sections)
            self.assertTrue(meta.get("生成契约通过"), meta.get("问题"))
            self.assertNotIn("兜底片段", str(meta.get("来源")))

    def test_lesson_runtime_defines_round12(self):
        # 曾经因为 runtime 漏了 round12，整页在浏览器里报错、求解器状态全丢。
        from components import runtime
        self.assertIn("const round12", runtime._BODY.template)

    def test_reaction_template_refuses_other_reactions(self):
        # 这个模板固定为 Fe + CuSO4；其他置换反应必须返回 None，不能套错产物。
        from reaction_compare_template import render_reaction_compare_template
        self.assertIsNone(render_reaction_compare_template(
            {"实验名称": "铜与稀盐酸", "实验主题": "铜与稀盐酸反应"}))


if __name__ == "__main__":
    unittest.main()
