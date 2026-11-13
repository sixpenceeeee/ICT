# -*- coding: utf-8 -*-
"""变形测试引擎的回归用例。

这些用例刻意覆盖三类问题：
    1. 关系算错（该翻倍没翻倍、该减半没减半）；
    2. 控件没接线 / 读数没刷新（值完全不变）；
    3. 容差写死导致小量级错误漏检。
"""

import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import mr_catalog
import mr_engine


def snapshot(controls=None, readouts=None, globals_=None):
    return {"controls": controls or {}, "readouts": readouts or {}, "globals": globals_ or {}}


def readout(value, text=None):
    return {text or ("%g" % value): {"text": text or ("%g" % value), "value": value}}


class RelationTests(unittest.TestCase):
    def test_proportional_passes_when_ratio_matches(self):
        plan = mr_engine.build_plan("CIRCUIT.solve")
        scene = plan["scenes"][0]
        a = snapshot({"voltage": 3}, {"circuit:current": {"text": "0.30", "value": 0.3}})
        b = snapshot({"voltage": 6}, {"circuit:current": {"text": "0.60", "value": 0.6}})
        ok, expected, actual, _ = mr_engine._cross_relation(scene, a, b)
        self.assertTrue(ok, (expected, actual))

    def test_proportional_fails_when_current_does_not_scale(self):
        plan = mr_engine.build_plan("CIRCUIT.solve")
        scene = plan["scenes"][0]
        a = snapshot({"voltage": 3}, {"circuit:current": {"text": "0.30", "value": 0.3}})
        b = snapshot({"voltage": 6}, {"circuit:current": {"text": "0.45", "value": 0.45}})
        ok, _, actual, _ = mr_engine._cross_relation(scene, a, b)
        self.assertFalse(ok)
        self.assertIn("1.5", actual)

    def test_inverse_fails_when_resistance_is_ignored(self):
        plan = mr_engine.build_plan("CIRCUIT.solve")
        scene = plan["scenes"][1]
        a = snapshot({"resistance": 10}, {"circuit:current": {"text": "0.60", "value": 0.6}})
        b = snapshot({"resistance": 20}, {"circuit:current": {"text": "0.60", "value": 0.6}})
        ok, _, actual, _ = mr_engine._cross_relation(scene, a, b)
        self.assertFalse(ok)
        self.assertIn("1", actual)

    def test_const_zero_catches_stale_current(self):
        plan = mr_engine.build_plan("CIRCUIT.solve")
        scene = plan["scenes"][2]
        b = snapshot({"switch": 0}, {"circuit:current": {"text": "0.60", "value": 0.6}})
        ok, _, actual, _ = mr_engine._cross_relation(scene, b, b)
        self.assertFalse(ok)
        self.assertIn("0.6", actual)

    def test_zero_baseline_is_not_comparable(self):
        plan = mr_engine.build_plan("CIRCUIT.solve")
        scene = plan["scenes"][0]
        a = snapshot({"voltage": 0}, {"circuit:current": {"text": "0", "value": 0}})
        b = snapshot({"voltage": 6}, {"circuit:current": {"text": "0.6", "value": 0.6}})
        ok, _, _, detail = mr_engine._cross_relation(scene, a, b)
        self.assertFalse(ok)
        self.assertIn("基线", detail)


class ToleranceTests(unittest.TestCase):
    def test_display_tolerance_follows_shown_precision(self):
        self.assertAlmostEqual(mr_engine.display_tolerance("1.00", 1.0), 0.00505, places=9)
        self.assertAlmostEqual(mr_engine.display_tolerance("0.001", 0.001), 0.000505, places=9)
        self.assertAlmostEqual(mr_engine.display_tolerance("12", 12), 0.51, places=9)

    def test_milliamp_scale_error_is_not_hidden(self):
        # 1.000 mA 显示成 1.006 mA：旧版 max(0.005, 2%) 会放过，新容差必须抓住。
        expected = 0.001
        shown = 0.001006
        tolerance = mr_engine.display_tolerance("0.001006", shown)
        self.assertGreater(abs(shown - expected), tolerance)


class StateFormulaTests(unittest.TestCase):
    def lens(self, u, f, v, m):
        return ({"u": u, "f": f},
                {"image_distance_cm": v, "magnification": m})

    def test_lens_formula_holds(self):
        request, result = self.lens(30, 10, 15, -0.5)
        ok, expected, actual, _ = mr_engine._lens_formula(request, result)
        self.assertTrue(ok, (expected, actual))

    def test_lens_formula_broken(self):
        request, result = self.lens(30, 10, 12, -0.4)
        ok, _, _, detail = mr_engine._lens_formula(request, result)
        self.assertFalse(ok)
        self.assertIn("不闭合", detail)

    def test_lens_at_focal_length_requires_empty_image(self):
        request, result = self.lens(10, 10, None, None)
        self.assertTrue(mr_engine._lens_formula(request, result)[0])
        request, result = self.lens(10, 10, 100, 10)
        self.assertFalse(mr_engine._lens_formula(request, result)[0])

    def test_mirror_distance_and_magnification(self):
        request = {"object_distance": 4}
        result = {"object_distance": 4, "image_distance": 4, "magnification": 1}
        self.assertTrue(mr_engine._mirror_distance(request, result)[0])
        self.assertTrue(mr_engine._mirror_magnification(request, result)[0])
        bad = {"object_distance": 4, "image_distance": 3.5, "magnification": 1}
        self.assertFalse(mr_engine._mirror_distance(request, bad)[0])

    def test_wave_speed_and_wavelength(self):
        request = {"detector_distance": 6.8, "travel_time": 0.02, "frequency": 170}
        result = {"speed": 340, "wavelength": 2}
        self.assertTrue(mr_engine._wave_speed(request, result)[0])
        self.assertTrue(mr_engine._wave_wavelength(request, result)[0])
        self.assertFalse(mr_engine._wave_speed(request, {"speed": 300})[0])

    def test_readout_must_equal_solver_result(self):
        scene = {"globals": {"result": "__PHYS_LENS_RESULT__"}}
        good = snapshot({}, {"field:image_distance_cm": {"text": "15.0", "value": 15.0}},
                        {"__PHYS_LENS_RESULT__": {"image_distance_cm": 15.0}})
        bad = snapshot({}, {"field:image_distance_cm": {"text": "15.0", "value": 15.0}},
                       {"__PHYS_LENS_RESULT__": {"image_distance_cm": 16.0}})
        check = {"op": "readout_matches", "readout": "field:image_distance_cm",
                 "path": "image_distance_cm"}
        self.assertTrue(mr_engine._readout_matches(check, good, scene)[0])
        self.assertFalse(mr_engine._readout_matches(check, bad, scene)[0])
        # 走统一的 _state_check 分发也要能通过（防止签名不匹配）。
        self.assertTrue(mr_engine._state_check(check, good, scene)[0])


class PlanEvaluationTests(unittest.TestCase):
    def test_missing_required_scene_fails(self):
        plan = mr_engine.build_plan("CIRCUIT.solve")
        summary = mr_engine.evaluate_page({"mr": {"scenes": []}}, plan, "CIRCUIT.solve")
        self.assertFalse(summary["ok"])
        # 两条必测关系失败，开关那条是 optional，记 skip。
        self.assertEqual(summary["fail"], 2)
        self.assertEqual(summary["skip"], 1)

    def test_optional_scene_missing_is_skipped(self):
        plan = mr_engine.build_plan("CIRCUIT.solve")
        payload = {"mr": {"scenes": [
            {"id": "circuit.voltage-proportional",
             "a": snapshot({"voltage": 3}, {"circuit:current": {"text": "0.30", "value": 0.3}}),
             "b": snapshot({"voltage": 6}, {"circuit:current": {"text": "0.60", "value": 0.6}})},
            {"id": "circuit.resistance-inverse",
             "a": snapshot({"resistance": 10}, {"circuit:current": {"text": "0.60", "value": 0.6}}),
             "b": snapshot({"resistance": 20}, {"circuit:current": {"text": "0.30", "value": 0.3}})},
        ]}}
        summary = mr_engine.evaluate_page(payload, plan, "CIRCUIT.solve")
        self.assertTrue(summary["ok"], summary)
        self.assertEqual(summary["skip"], 1)

    def test_missing_control_is_reported(self):
        plan = mr_engine.build_plan("CIRCUIT.solve")
        payload = {"mr": {"scenes": [
            {"id": "circuit.voltage-proportional", "errors": ["缺少可用控件：voltage"],
             "a": snapshot({}, {}), "b": snapshot({}, {})}
        ]}}
        summary = mr_engine.evaluate_page(payload, plan, "CIRCUIT.solve")
        self.assertFalse(summary["ok"])
        self.assertTrue(any("控件" in row["evidence"] for row in summary["rows"]))

    def test_series_rheostat_skips_inverse_relation(self):
        plan = mr_engine.build_plan("CIRCUIT.solve")
        model = {"components": [
            {"id": "R1", "type": "resistor", "ohms": 10},
            {"id": "Rh", "type": "resistor", "ohms": 20},
        ]}
        payload = {"mr": {"scenes": [
            {"id": "circuit.voltage-proportional",
             "a": snapshot({"voltage": 3}, {"circuit:current": {"text": "0.10", "value": 0.1}}),
             "b": snapshot({"voltage": 6}, {"circuit:current": {"text": "0.20", "value": 0.2}})},
            {"id": "circuit.resistance-inverse",
             "a": snapshot({"voltage": 6, "resistance": 10}, {"circuit:current": {"text": "0.20", "value": 0.2}}),
             "b": snapshot({"voltage": 6, "resistance": 20}, {"circuit:current": {"text": "0.15", "value": 0.15}}),
             "errors": []},
        ]}}
        # 给 inverse 场景补上带两个电阻的模型，触发 precondition。
        for scene in payload["mr"]["scenes"]:
            scene["a"]["globals"] = {"__CIRCUIT_MODEL__": model}
            scene["b"]["globals"] = {"__CIRCUIT_MODEL__": model}
        summary = mr_engine.evaluate_page(payload, plan, "CIRCUIT.solve")
        rows = {row["id"]: row for row in summary["rows"]}
        self.assertEqual(rows["circuit.resistance-inverse"]["status"], "skip")
        self.assertIn("2 个有效电阻", rows["circuit.resistance-inverse"]["actual"])

    def test_unknown_solver_has_no_plan(self):
        self.assertIsNone(mr_engine.build_plan("UNKNOWN.solve"))


class CatalogTests(unittest.TestCase):
    def test_ids_are_unique_and_kinds_are_known(self):
        seen = set()
        for api, plan in mr_catalog.PAGE_PLANS.items():
            self.assertEqual(api, plan.get("solver"))
            for scene in plan["scenes"]:
                self.assertNotIn(scene["id"], seen)
                seen.add(scene["id"])
                self.assertIn(scene["kind"], mr_catalog.KINDS)
                self.assertTrue(scene.get("controls"), scene["id"])
                self.assertTrue(scene.get("relation") or scene.get("state_checks"), scene["id"])

    def test_every_control_has_selectors_and_two_values(self):
        for plan in mr_catalog.PAGE_PLANS.values():
            for scene in plan["scenes"]:
                for name, spec in scene["controls"].items():
                    self.assertTrue(spec.get("selectors"), (scene["id"], name))
                    self.assertIn("baseline", spec)
                    self.assertIn("transformed", spec)

    def test_required_controls_are_exposed(self):
        self.assertCountEqual(mr_catalog.required_controls("CIRCUIT.solve"),
                              ["voltage", "resistance", "switch"])


class CircuitSampleTests(unittest.TestCase):
    @staticmethod
    def sample(volts, ohms, current, closed=True):
        return {
            "model": {"components": [
                {"id": "V1", "type": "voltage_source", "positive": "n1", "negative": "0", "volts": volts},
                {"id": "R1", "type": "resistor", "from": "n1", "to": "0", "ohms": ohms},
                {"id": "S1", "type": "switch", "from": "n1", "to": "n2", "closed": closed},
                {"id": "A1", "type": "ammeter", "from": "n2", "to": "0"},
            ]},
            "result": {"branches": {"A1": {"current": current}}},
        }

    def test_voltage_scaling_is_derived(self):
        payload = {"circuit": {"samples": [self.sample(3, 10, 0.3), self.sample(6, 10, 0.6)]}}
        rows = mr_engine.circuit_sample_rows(payload)
        self.assertTrue(rows)
        self.assertEqual(rows[0]["status"], "pass")

    def test_inverse_is_derived(self):
        payload = {"circuit": {"samples": [self.sample(6, 10, 0.6), self.sample(6, 20, 0.3)]}}
        rows = mr_engine.circuit_sample_rows(payload)
        self.assertTrue(any(row["kind"] == "inverse" and row["status"] == "pass" for row in rows))

    def test_open_switch_zero_is_derived(self):
        payload = {"circuit": {"samples": [self.sample(6, 10, 0.6), self.sample(6, 10, 0, closed=False)]}}
        rows = mr_engine.circuit_sample_rows(payload)
        self.assertTrue(any(row["kind"] == "boundary" and row["status"] == "pass" for row in rows))


class ReadoutTests(unittest.TestCase):
    def test_readout_entry_supports_field_and_label_keys(self):
        snap = snapshot({}, {"field:image_distance_cm": {"text": "15.0", "value": 15.0},
                             "label:电流 I": {"text": "0.60", "value": 0.6}})
        self.assertEqual(mr_engine._readout(snap, "field:image_distance_cm"), 15.0)
        self.assertEqual(mr_engine._readout(snap, "label:电流 I"), 0.6)

    def test_global_path_reads_nested_branch(self):
        snap = snapshot({}, {}, {"__CIRCUIT_RESULT__": {"branches": {"A1": {"current": 0.25}}}})
        self.assertEqual(mr_engine._readout(snap, "global:__CIRCUIT_RESULT__.branches.A1.current"), 0.25)


if __name__ == "__main__":
    unittest.main()
