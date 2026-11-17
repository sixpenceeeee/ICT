"""用模型协议替身检查调用与拒绝路径，不向外发送真实模型请求。"""
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def load_generator():
    directory = ROOT / '03_generator_agent'
    sys.path.insert(0, str(directory))
    old_prompt = sys.modules.pop('prompts', None)
    try:
        spec = importlib.util.spec_from_file_location('circuit_generator_test_target', directory / 'generator_agent.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.modules.pop('prompts', None)
        if old_prompt:
            sys.modules['prompts'] = old_prompt
        sys.path.remove(str(directory))


@unittest.skip(
    "旧版「电路配置（recipe+params→电路配置）」协议已被远端 0992008 的 CIRCUIT.solve 求解器契约取代"
    "（scene_registry 里电路场景 api=None、solver_api=CIRCUIT.solve；生成器改为校验模型产出的 netlist）。"
    "保留本组用例作为旧协议的可执行记录；迁移到新契约后取消 skip。"
    "旧实现的电路钩子仍保存在分支 backup/pre-merge-16c2548。"
)
class GeneratorProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.generator = load_generator()
        cls.req = {'学科': '物理', '实验主题': '欧姆定律', '实验名称': '欧姆定律'}

    def test_model_plan_drives_actual_component_config(self):
        g = self.generator
        with patch.object(g, 'HAS_LLM', True), patch.object(g, 'get_config', return_value={'api_key': 'test', 'model': 'protocol-test'}), patch.object(g, 'call_llm', return_value=(json.dumps({'recipe': 'ohm', 'params': {'voltage': 3}}), False)):
            sections, meta = g.generate(self.req, {})
        self.assertEqual(meta['电路配置']['components'][0]['params']['voltage'], 3)
        self.assertIn('大模型电路配置', meta['来源'])
        self.assertEqual(g.hard_validate(sections, self.req), [])

    def test_invalid_plan_is_repaired_once_then_uses_labelled_circuit(self):
        g = self.generator
        with patch.object(g, 'HAS_LLM', True), patch.object(g, 'get_config', return_value={'api_key': 'test', 'model': 'protocol-test'}), patch.object(g, 'call_llm', return_value=('not json', False)) as model:
            sections, meta = g.generate(self.req, {})
        self.assertEqual(model.call_count, 2)
        self.assertIn('模型配置未通过', meta['来源'])
        self.assertEqual(meta['电路配置']['recipe'], 'ohm')
        self.assertEqual(g.hard_validate(sections, self.req), [])

    def test_template_mode_never_calls_model(self):
        g = self.generator
        with patch.object(g, 'call_llm', side_effect=AssertionError('不应调用模型')):
            _, meta = g.generate(self.req, {}, template_only=True)
        self.assertIn('未使用模型', meta['来源'])


if __name__ == '__main__':
    unittest.main()
