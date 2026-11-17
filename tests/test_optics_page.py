# -*- coding: utf-8 -*-
"""3D 凸透镜成像页的真浏览器验收（file:// + 本机 chromium）。

依赖 tools/optics_page_probe.mjs（playwright-core）。断言的是「页面行为」：
三处快照、读数绑定、三种成像（实像清晰/实像模糊/虚像）、画面像素随参数变、
视角可拖动并复位、记录表追加。求解器数值本身的正确性由
tests/test_optics_solver.py 与 test_optics_bridge.py 负责，这里不重复。
"""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / 'examples' / 'optics' / 'lens3d.html'
PROBE = ROOT / 'tools' / 'optics_page_probe.mjs'
NODE = shutil.which('node')


def playwright_available():
    for candidate in (ROOT / 'node_modules' / 'playwright-core',
                      ROOT.parent / 'node_modules' / 'playwright-core'):
        if candidate.is_dir():
            return True
    return False


@unittest.skipIf(NODE is None or not PAGE.exists() or not playwright_available(),
                 '缺少 node / 页面产物 / playwright-core，跳过 3D 页面验收')
class OpticsPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        proc = subprocess.run(
            [NODE, str(PROBE), str(PAGE)],
            capture_output=True, text=True, encoding='utf-8', timeout=300,
        )
        try:
            cls.data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            raise AssertionError('探针没有输出 JSON：%s' % (proc.stdout or proc.stderr)[:800])

    def state(self, key):
        state = self.data.get(key)
        self.assertIsNotNone(state, '缺少状态 %s（failure=%r）' % (key, self.data.get('failure')))
        return state

    def test_no_runtime_errors(self):
        self.assertIsNone(self.data.get('failure'))
        self.assertEqual(self.data.get('errors'), [])

    def test_snapshots_and_bindings(self):
        initial = self.state('initial')
        self.assertEqual(initial['render3d'], 'ready')
        self.assertGreaterEqual(initial['bound'], 5)
        self.assertIsNotNone(initial['model'])
        self.assertIsNotNone(initial['result'])
        self.assertIsNotNone(initial['view'])
        self.assertIsNotNone(initial['mathView'])
        self.assertTrue(initial['sig'])

    def test_three_imaging_states(self):
        initial = self.state('initial')
        self.assertEqual(initial['result']['kind'], 'real')
        self.assertAlmostEqual(initial['result']['v'], 15.0, places=6)
        self.assertTrue(initial['result']['onScreen']['sharp'])

        u15 = self.state('u15')
        self.assertAlmostEqual(u15['result']['v'], 30.0, places=6)
        self.assertFalse(u15['result']['onScreen']['sharp'])

        u5 = self.state('u5')
        self.assertEqual(u5['result']['kind'], 'virtual')
        self.assertLess(u5['result']['v'], 0)
        self.assertFalse(u5['result']['onScreen']['sharp'])

        uf = self.state('uf')
        self.assertEqual(uf['result']['kind'], 'none')
        self.assertIsNone(uf['result']['v'])
        self.assertFalse(uf['result']['onScreen']['sharp'])
        self.assertEqual(uf['readouts'].get('v'), '—')

    def test_pixels_change_with_parameters(self):
        hashes = [self.state(key)['pixelHash'] for key in ('initial', 'u15', 'u5')]
        self.assertEqual(len(set(hashes)), 3, '三种参数下画面像素应各不相同：%s' % hashes)

    def test_orbit_drag_and_reset(self):
        initial = self.state('initial')['view']
        dragged = self.data.get('dragged') or {}
        reset = self.data.get('reset') or {}
        self.assertIsNotNone(dragged.get('view'))
        self.assertGreater(abs(dragged['view']['yaw'] - initial['yaw'])
                           + abs(dragged['view']['pitch'] - initial['pitch']), 1e-3)
        self.assertAlmostEqual(reset['view']['yaw'], initial['yaw'], places=6)
        self.assertAlmostEqual(reset['view']['pitch'], initial['pitch'], places=6)

    def test_record_rows(self):
        self.assertEqual(self.data.get('rowsAfterRecord'), 2)

    def test_formula_is_substituted(self):
        formula = self.state('initial')['formula']
        self.assertIn('30.0', formula)
        self.assertIn('15.0', formula)
        self.assertRegex(formula, r'30\.0\s*×\s*10\.0\s*÷\s*20\.0\s*=\s*15\.0')

    def test_enlarge_editor_isolates_draft_and_applies(self):
        enlarge = self.state('enlarge')
        self.assertEqual(enlarge['mainBeforeApply'], 30.0)
        self.assertEqual(enlarge['appliedU'], 20.0)
        self.assertAlmostEqual(enlarge['appliedV'], 20.0, places=6)


if __name__ == '__main__':
    unittest.main()
