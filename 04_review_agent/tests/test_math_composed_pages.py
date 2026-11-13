"""Verify both component selections through generation and independent page review."""

import json
from pathlib import Path
import sys
import tempfile
import unittest

REVIEW_DIR = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REVIEW_DIR), str(REVIEW_DIR.parent / "03_generator_agent")]

from generator_agent import generate
from math_geometry_templates import GEOMETRY_MODELS
from math_page_templates import QUADRATIC
from reviewer import find_chrome, find_node, find_node_modules, run_review
from scene_registry import MATH_MODELS, SCENE_SKELETONS
import shell


MODELS = {**MATH_MODELS, "quadratic": QUADRATIC, **GEOMETRY_MODELS}
GEOMETRY_CHECKS = {
    "cube-cut-3d": "G4-14", "cuboid-section-3d": "G4-14", "triangular-prism-section-3d": "G4-14",
    "square-pyramid-section-3d": "G4-14", "cylinder-section": "G4-15", "cone-section": "G4-16",
    "sphere-section": "G4-17", "spatial-metrics": "G4-18", "solid-volume": "G4-19",
    "cube-net-folding": "G4-20", "cuboid-net-folding": "G4-21",
    "cylinder-net-unfolding": "G4-22", "cone-net-unfolding": "G4-23",
}


def variant(model, index):
    title = model["title"]
    description = "，学生探究版，增加对比表、实验记录和 CSV。" if index else "，课堂演示版。"
    return {"学科": "数学", "年级": "中学", "实验主题": title,
            "原始需求": title + description, "初始参数": list(model["cases"].values())[index]}


class ComposedMathPages(unittest.TestCase):
    def test_registered_models_generate_requested_components(self):
        expected = {scene["id"].removeprefix("math-") for scene in SCENE_SKELETONS
                    if scene["subject"] == "数学" and scene.get("solver_api")}
        self.assertEqual(set(MODELS), expected)
        for key, model in MODELS.items():
            for index in range(2):
                with self.subTest(scene=key, inquiry=bool(index)):
                    req = variant(model, index)
                    sections, meta = generate(req, {}, template_only=True)
                    self.assertTrue(meta["生成契约通过"], meta["问题"])
                    self.assertIn(json.dumps(req["初始参数"], ensure_ascii=False), sections["js"])
                    self.assertEqual('id="math-csv"' in sections["3"], bool(index))
                    self.assertEqual("<th>初始值</th>" in sections["5"], bool(index))
                    self.assertEqual('id="math-records"' in sections["5"], bool(index))

    @unittest.skipUnless(find_node() and find_node_modules() and find_chrome(), "需要 Node、Playwright 和浏览器")
    def test_optional_components_and_composite(self):
        requests = [
            ({"学科": "数学", "实验主题": "直角三角形", "原始需求": "直角三角形，课堂演示版，加对比图和计算过程。"},
             ("J3-31",), 'id="math-baseline-graph"'),
            ({"学科": "数学", "实验主题": "摸球实验", "原始需求": "摸球实验，只要树状图，默认不放回。"},
             ("J3-44",), 'panels: "tree"'),
            ({"学科": "数学", "实验主题": "组合体体积", "内部不重叠": True,
              "组成部分": [{"solid": "cube", "edge": 2}, {"solid": "cuboid", "length": 4, "width": 3, "height": 2}]},
             ("G4-19",), "MATH.solveCompositeVolume(request.components)"),
        ]
        with tempfile.TemporaryDirectory() as folder:
            for req, required, marker in requests:
                with self.subTest(scene=req["实验主题"]):
                    sections, meta = generate(req, {})
                    self.assertTrue(meta["生成契约通过"], meta["问题"])
                    self.assertIn(marker, "\n".join(sections.values()))
                    request_file = Path(folder) / "request.json"
                    request_file.write_text(json.dumps(req, ensure_ascii=False), encoding="utf-8")
                    title = req["实验主题"]
                    delivery = shell.deliver(shell.render(title, sections), title, folder, make_zip=False)
                    report = run_review(delivery["HTML"], request_file, verbose=False)
                    checks = {row["check_id"]: row for row in report["检查项"]}
                    for check in ("J1-01", "G4-32", *required):
                        self.assertEqual(checks[check]["status"], "pass", checks[check])
                    self.assertEqual([row for row in report["检查项"] if row["status"] == "fail"], [])

    @unittest.skipUnless(find_node() and find_node_modules() and find_chrome(), "需要 Node、Playwright 和浏览器")
    def test_two_page_variants_per_scene(self):
        with tempfile.TemporaryDirectory() as folder:
            for key, model in MODELS.items():
                for index in range(2):
                    with self.subTest(scene=key, inquiry=bool(index)):
                        req = variant(model, index)
                        sections, meta = generate(req, {}, template_only=True)
                        self.assertTrue(meta["生成契约通过"], meta["问题"])
                        request_file = Path(folder) / "request.json"
                        request_file.write_text(json.dumps(req, ensure_ascii=False), encoding="utf-8")
                        html = shell.render(model["title"], sections)
                        delivery = shell.deliver(html, model["title"], folder, make_zip=False)
                        report = run_review(delivery["HTML"], request_file, verbose=False)
                        checks = {row["check_id"]: row for row in report["检查项"]}
                        oracle = model.get("check", GEOMETRY_CHECKS.get(key, "J3-14"))
                        for check in ("J1-01", "G4-32", oracle):
                            self.assertEqual(checks[check]["status"], "pass", checks[check])
                        failures = [row for row in report["检查项"] if row["status"] == "fail"]
                        self.assertEqual(failures, [])
                        self.assertEqual(report["结论"], "通过")
