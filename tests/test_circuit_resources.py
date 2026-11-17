"""电路配置、页面装配与模型协议的集成回归。"""
import importlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class CircuitResourceTests(unittest.TestCase):
    def resources(self):
        self.assertTrue((ROOT / 'circuit_resources.py').exists(), '缺少电路资源适配模块')
        return importlib.import_module('circuit_resources')

    def test_all_recipes_are_real_solved_circuits(self):
        api = self.resources()
        for recipe, expected in [('ohm', .6), ('series', .2), ('parallel', .9), ('resistance', .3)]:
            config, solved = api.resolve_plan({'recipe': recipe, 'params': {'voltage': 6}})
            self.assertTrue(solved['ok'])
            self.assertAlmostEqual(solved['totalCurrent'], expected)
            self.assertTrue(config['wires'])

    def test_plan_validation_rejects_unknown_device_and_nan(self):
        api = self.resources()
        with self.assertRaises(ValueError):
            api.resolve_plan({'recipe': 'not-a-recipe'})
        config, _ = api.resolve_plan({'recipe': 'ohm'})
        config['components'][0]['type'] = 'magic_source'
        with self.assertRaises(ValueError):
            api.resolve_plan(config)
        with self.assertRaises(ValueError):
            api.resolve_plan({'recipe': 'ohm', 'params': {'voltage': float('nan')}})
        with self.assertRaises(ValueError):
            api.resolve_plan({'recipe': 'ohm', 'params': {'voltage': 220}})
        config, _ = api.resolve_plan({'recipe': 'ohm'})
        config['components'][0]['x'] = 1e9
        with self.assertRaises(ValueError):
            api.resolve_plan(config)

    def test_topic_selection_and_unsupported_requests(self):
        api = self.resources()
        self.assertEqual(api.choose_recipe({'实验主题': '伏安法测电阻'}), 'resistance')
        self.assertEqual(api.choose_recipe({'实验主题': '并联电路'}), 'parallel')
        with self.assertRaises(ValueError):
            api.choose_recipe({'实验主题': 'RC 电容充放电电路'})
        with self.assertRaises(ValueError):
            api.choose_recipe({'实验主题': '焦耳定律中电流产生热量与时间的关系'})

    def test_template_requirement_retains_requested_circuit(self):
        api = self.resources()
        self.assertTrue(hasattr(api, 'template_requirement'), '需要不调用模型的需求预设')
        req = api.template_requirement('生成一个伏安法测电阻实验')
        self.assertEqual(req['实验名称'], '伏安法测电阻')
        self.assertEqual(api.choose_recipe(req), 'resistance')

    def test_circuit_prompt_carries_catalog_and_connections(self):
        api = self.resources()
        prompt = api.build_circuit_prompt({'学科': '物理', '实验主题': '伏安法测电阻'}, {})
        for key in ['power_supply', 'ammeter', 'voltmeter', 'rheostat', 'wires', 'positive', 'negative']:
            self.assertIn(key, prompt)

    def test_sections_keep_original_six_regions_and_use_components(self):
        api = self.resources()
        config, _ = api.resolve_plan({'recipe': 'resistance'})
        secs = api.render_sections(config)
        self.assertTrue(all(str(n) in secs for n in range(1, 7)))
        self.assertIn('CIRCUIT_PAGE.mount(', secs['js'])
        self.assertIn('btn-enlarge', secs['2'])
        self.assertIn('data-visual-type="apparatus"', secs['2'])

    def test_export_is_standalone_and_keeps_platform_shell(self):
        api = self.resources()
        import shell
        config, _ = api.resolve_plan({'recipe': 'ohm'})
        html = shell.render('欧姆定律', api.render_sections(config))
        self.assertIn('class="pf-header"', html)
        self.assertIn('class="pf-footer"', html)
        for region in ['info', 'stage', 'control', 'result', 'record', 'teach']:
            self.assertIn('id="sec-' + region + '"', html)
        self.assertNotIn('href="frame.css"', html)
        self.assertNotIn('src="logo.png"', html)
        self.assertIn('id="circuit-core"', html)
        self.assertIn('id="circuit-editor"', html)
        self.assertEqual(shell.validate(html), [])

    def test_model_reply_supports_json_fences_and_rejects_prose(self):
        api = self.resources()
        self.assertEqual(api.parse_plan('```json\n{"recipe":"ohm"}\n```')['recipe'], 'ohm')
        with self.assertRaises(ValueError):
            api.parse_plan('这是一个电路，不是配置')

    def test_voltage_divider_recipe_selection_and_resolution(self):
        api = self.resources()
        self.assertEqual(api.choose_recipe({'实验主题': '滑动变阻器分压控制实验'}), 'voltage_divider')
        self.assertEqual(api.choose_recipe({'实验名称': '电位器分压电路'}), 'voltage_divider')
        config, sol = api.resolve_plan({'recipe': 'voltage_divider'})
        self.assertTrue(sol['ok'])
        self.assertAlmostEqual(sol['totalCurrent'], 14 / 75, places=5)
        self.assertAlmostEqual(sol['components']['M1']['voltage'], 4 / 3, places=5)
        self.assertAlmostEqual(sol['components']['A1']['current'], 2 / 15, places=5)

    def test_voltage_divider_template_requirement_and_sections(self):
        api = self.resources()
        req = api.template_requirement('滑动变阻器分压控制实验')
        self.assertEqual(req['实验名称'], '滑动变阻器分压控制实验')
        self.assertEqual(api.choose_recipe(req), 'voltage_divider')
        config, _ = api.resolve_plan({'recipe': 'voltage_divider'})
        secs = api.render_sections(config)
        self.assertTrue(all(str(n) in secs for n in range(1, 7)))
        self.assertIn('分压', secs['1'])
        self.assertIn('btn-enlarge', secs['2'])
        self.assertIn('voltage_divider', secs['js'])
        import shell
        html = shell.render('滑动变阻器分压控制实验', secs)
        self.assertEqual(shell.validate(html), [])


if __name__ == '__main__':
    unittest.main()
