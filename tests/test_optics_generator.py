# -*- coding: utf-8 -*-
"""生成端光学门：骨架必须前置到 3D，且硬校验能拦住「没调 OPTICS3D.mount」的页面。"""
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import optics_resources  # noqa: E402


def load_generator():
    directory = ROOT / '03_generator_agent'
    sys.path.insert(0, str(directory))
    old_prompts = sys.modules.pop('prompts', None)
    try:
        spec = importlib.util.spec_from_file_location('optics_generator_test_target', directory / 'generator_agent.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.modules.pop('prompts', None)
        if old_prompts:
            sys.modules['prompts'] = old_prompts
        sys.path.remove(str(directory))


REQ = {'学科': '物理', '实验主题': '凸透镜成像', '实验名称': '凸透镜成像'}


class OpticsGeneratorGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.generator = load_generator()

    def test_skeleton_is_3d_first(self):
        skeleton = self.generator.select_page_skeleton(REQ)
        self.assertEqual(skeleton['id'], 'physics-optics-3d')
        self.assertEqual(skeleton.get('solver_api'), 'OPTICS.solve')

    def test_skeleton_can_select_2d_and_3d(self):
        req_2d = dict(REQ, 光学视图='2d')
        sk_2d = self.generator.select_page_skeleton(req_2d)
        self.assertEqual(sk_2d['id'], 'physics-optics-bench')
        self.assertEqual(sk_2d.get('api'), 'PHYS.optics')
        req_2d_kw = {'学科': '物理', '实验主题': '凸透镜成像（2D平面光路）', '实验名称': '凸透镜成像2D'}
        self.assertEqual(self.generator.select_page_skeleton(req_2d_kw)['id'], 'physics-optics-bench')
        req_3d = dict(REQ, 光学视图='3d')
        self.assertEqual(self.generator.select_page_skeleton(req_3d)['id'], 'physics-optics-3d')

    def test_valid_2d_sections_pass(self):
        req_2d = dict(REQ, 光学视图='2d')
        sections = optics_resources.render_2d_sections()
        problems = self.generator.hard_validate(sections, req_2d)
        self.assertEqual(problems, [], '2D 合规页面不应报错：%s' % problems)

    def test_valid_sections_pass(self):
        sections = optics_resources.render_sections()
        problems = self.generator.hard_validate(sections, REQ)
        optics_related = [p for p in problems if '光学' in p]
        self.assertEqual(optics_related, [], '合规页面不应触发光学门：%s' % optics_related)

    def test_missing_mount_is_rejected(self):
        sections = optics_resources.render_sections()
        sections = dict(sections)
        sections['js'] = 'window.__DATA__={}; function paint(){ return 1; }'
        problems = self.generator.hard_validate(sections, REQ)
        self.assertTrue(any('OPTICS3D.mount' in p for p in problems), problems)

    def test_hand_computed_v_is_rejected(self):
        sections = dict(optics_resources.render_sections())
        sections['js'] = ('var model={f:10,u:30}; var v = u * f / (u - f);'
                          'OPTICS3D.mount(document.getElementById("cv"), model);')
        problems = self.generator.hard_validate(sections, REQ)
        self.assertTrue(any('不得自己用公式算像距' in p or 'Infinity' in p for p in problems), problems)


if __name__ == '__main__':
    unittest.main()
