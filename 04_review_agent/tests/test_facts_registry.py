# -*- coding: utf-8 -*-
import copy
import sys
import unittest
from pathlib import Path


BASE = Path(__file__).resolve().parents[1]
PROJECT = BASE.parent
sys.path.insert(0, str(BASE))

from facts_store import (FACTS_REGISTRY_PATH, SCENE_FACT_MAP_PATH, SOURCE_REGISTRY_PATH,
                         check_page_facts, load_facts, load_scene_fact_map, load_sources,
                         validate_registry)


class FactsRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.facts = load_facts(FACTS_REGISTRY_PATH)
        cls.sources = load_sources(SOURCE_REGISTRY_PATH)
        cls.maps = load_scene_fact_map(SCENE_FACT_MAP_PATH)

    def test_fact_id_unique(self):
        ids = [x["fact_id"] for x in self.facts]
        self.assertEqual(len(ids), len(set(ids)))

    def test_source_id_unique(self):
        ids = [x["source_id"] for x in self.sources]
        self.assertEqual(len(ids), len(set(ids)))

    def test_all_source_refs_exist(self):
        issues = validate_registry(self.facts, self.sources, self.maps)
        self.assertFalse([x for x in issues if "不存在的来源" in x])

    def test_all_registered_scenes_have_map(self):
        import importlib.util
        path = PROJECT / "03_generator_agent" / "scene_registry.py"
        spec = importlib.util.spec_from_file_location("scene_registry_for_test", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        mapped = {x["scene_id"] for x in self.maps}
        self.assertTrue(set(module.SCENE_METADATA).issubset(mapped))

    def test_include_forbidden_disjoint(self):
        issues = validate_registry(self.facts, self.sources, self.maps)
        self.assertFalse([x for x in issues if "冲突" in x])

    def test_reviewed_fact_without_source_is_invalid(self):
        facts = copy.deepcopy(self.facts)
        facts[0]["source_refs"] = []
        issues = validate_registry(facts, self.sources, self.maps)
        self.assertTrue(any("无来源事实不能标记已审核" in x for x in issues))

    def test_forbidden_term_fails_page_check(self):
        fact = copy.deepcopy(self.facts[0])
        fact["fact_id"] = "test-fact"
        fact["must_include"] = ["铜"]
        fact["must_not_include"] = ["错误表述"]
        fact["source_refs"] = ["test-source"]
        fact["safety_boundary"] = ["虚拟模型"]
        source = {"source_id": "test-source", "source_status": "已核验"}
        scene = {"scene_id": "test-scene", "fact_ids": ["test-fact"], "coverage_status": "完整覆盖"}
        result = check_page_facts("铜 错误表述 虚拟模型", "test-scene", [fact], [source], [scene])
        self.assertTrue(result["forbidden_term_found"])
        self.assertFalse(result["facts_pass"])
        self.assertFalse(result["publish_allowed"])

    def test_missing_safety_enters_review(self):
        fact = copy.deepcopy(self.facts[0])
        fact["fact_id"] = "test-fact"
        fact["source_refs"] = ["test-source"]
        fact["safety_boundary"] = []
        source = {"source_id": "test-source", "source_status": "已核验"}
        scene = {"scene_id": "test-scene", "fact_ids": ["test-fact"], "coverage_status": "完整覆盖"}
        result = check_page_facts("铜", "test-scene", [fact], [source], [scene])
        self.assertTrue(result["safety_missing"])
        self.assertFalse(result["publish_allowed"])

    def test_version_trace_fields_present(self):
        self.assertTrue(all(x.get("version") for x in self.facts))
        self.assertTrue(all(x.get("last_checked") for x in self.maps))


if __name__ == "__main__":
    unittest.main()

