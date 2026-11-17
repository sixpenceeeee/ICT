"""Requirement-Driven E2E Test Suite for Circuit Engine and Apparatus Workbench.

Implements the 4-tier testing methodology derived directly from:
- ORIGINAL_REQUEST.md (Requirements R1-R4)
- PROJECT.md Feature Inventory (Features 1-14)

Tiers:
- Tier 1: Feature Coverage (5 test cases per feature across F1-F5 = 25 tests)
- Tier 2: Boundary & Corner Cases (8 test cases: empty wires, short circuit, floating nodes, rheostat limits, overrange, etc.)
- Tier 3: Cross-Feature Combinations (5 test cases: switch toggling, rheostat regulation sweep, zoom editor postMessage, overrange lock, coordinate nudge)
- Tier 4: Real-World Application Scenarios (6 test cases: Voltage Divider, Dual-Resistor network, 4 regression presets)
"""
import copy
import json
import math
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import circuit_resources
import shell

# Direct MNA solver invocation via Node (returns raw result object with status, errors, components, nodeVoltages)
def solve_direct(config):
    node = 'node'
    code = (
        "const core = require('./frame/circuit/core.js');\n"
        "let buf = '';\n"
        "process.stdin.setEncoding('utf8');\n"
        "process.stdin.on('data', d => { buf += d; });\n"
        "process.stdin.on('end', () => {\n"
        "  try {\n"
        "    const cfg = JSON.parse(buf);\n"
        "    process.stdout.write(JSON.stringify(core.solve(cfg)));\n"
        "  } catch (err) {\n"
        "    process.stdout.write(JSON.stringify({ ok: false, error: err.message }));\n"
        "  }\n"
        "});\n"
    )
    proc = subprocess.run(
        [node, '-e', code],
        input=json.dumps(config, ensure_ascii=False, allow_nan=False),
        capture_output=True,
        text=True,
        encoding='utf-8',
        timeout=15,
        cwd=ROOT
    )
    return json.loads(proc.stdout)

# Production bridge invocation (Python -> circuit_bridge.js)
def solve_via_bridge(plan):
    node = 'node'
    payload = json.dumps(plan, ensure_ascii=False, allow_nan=False)
    proc = subprocess.run(
        [node, str(ROOT / 'tools' / 'circuit_bridge.js')],
        input=payload,
        capture_output=True,
        text=True,
        encoding='utf-8',
        timeout=15,
        cwd=ROOT
    )
    try:
        res = json.loads(proc.stdout)
    except Exception:
        res = {"error": proc.stderr}
    return res, proc.returncode


# =============================================================================
# TIER 1: FEATURE COVERAGE (>=5 test cases per feature for F1 to F5)
# =============================================================================

class TestTier1FeatureCoverage(unittest.TestCase):
    """Tier 1: Feature Coverage for F1 (Catalog), F2 (Assembly), F3 (MNA), F4 (Page Gen), F5 (Offline Viewing)."""

    # -------------------------------------------------------------------------
    # Feature 1: Catalog Query (circuit_query_catalog)
    # -------------------------------------------------------------------------
    def test_f1_01_catalog_schema_structure(self):
        cat = circuit_resources.catalog()
        self.assertIsInstance(cat, dict, "Catalog must be a valid JSON dictionary")
        self.assertIn("components", cat, "Catalog must define components list")
        self.assertIsInstance(cat["components"], list)
        self.assertGreaterEqual(len(cat["components"]), 6)

    def test_f1_02_catalog_six_device_types(self):
        cat = circuit_resources.catalog()
        types = {c["type"] for c in cat["components"]}
        expected = {"power_supply", "switch", "resistor", "rheostat", "ammeter", "voltmeter"}
        self.assertTrue(expected.issubset(types), f"Missing core device types: {expected - types}")

    def test_f1_03_catalog_terminal_contracts(self):
        cat = circuit_resources.catalog()
        by_type = {c["type"]: c for c in cat["components"]}
        self.assertEqual(by_type["power_supply"]["ports"], ["positive", "negative"])
        self.assertEqual(by_type["switch"]["ports"], ["a", "b"])
        self.assertEqual(by_type["resistor"]["ports"], ["a", "b"])
        self.assertEqual(by_type["rheostat"]["ports"], ["a", "slider", "b"])
        self.assertEqual(by_type["ammeter"]["ports"], ["positive", "negative"])
        self.assertEqual(by_type["voltmeter"]["ports"], ["positive", "negative"])

    def test_f1_04_catalog_parameter_bounds_contract(self):
        cat = circuit_resources.catalog()
        by_type = {c["type"]: c for c in cat["components"]}
        v_bounds = by_type["power_supply"]["parameters"]["voltage"]
        self.assertEqual(v_bounds["minimum"], 0)
        self.assertEqual(v_bounds["maximum"], 12)

        r_bounds = by_type["resistor"]["parameters"]["resistance"]
        self.assertEqual(r_bounds["exclusiveMinimum"], 0)

        rh_pos = by_type["rheostat"]["parameters"]["position"]
        self.assertEqual(rh_pos["minimum"], 0)
        self.assertEqual(rh_pos["maximum"], 1)

    def test_f1_05_catalog_defaults_and_provenance(self):
        cat = circuit_resources.catalog()
        by_type = {c["type"]: c for c in cat["components"]}
        self.assertEqual(by_type["power_supply"]["parameters"]["voltage"]["default"], 6)
        self.assertEqual(by_type["resistor"]["parameters"]["resistance"]["default"], 10)
        self.assertTrue(by_type["switch"]["parameters"]["closed"]["default"])
        # Provenance: no unexpected root mutations
        self.assertIn("schema_version", cat)
        self.assertEqual(cat["schema_version"], 1)

    # -------------------------------------------------------------------------
    # Feature 2: Device Assembly (circuit_assemble)
    # -------------------------------------------------------------------------
    def test_f2_01_valid_circuit_assembly(self):
        plan = {
            "schema_version": 1,
            "recipe": "ohm",
            "params": {"voltage": 6, "resistance": 10, "closed": True}
        }
        cfg, sol = circuit_resources.resolve_plan(plan)
        self.assertEqual(cfg["schema_version"], 1)
        self.assertEqual(cfg["recipe"], "ohm")
        self.assertTrue(sol["ok"])
        self.assertEqual(len(cfg["components"]), 5)
        self.assertEqual(len(cfg["wires"]), 6)

    def test_f2_02_assembly_duplicate_id_rejection(self):
        plan = {
            "schema_version": 1,
            "recipe": "custom",
            "components": [
                {"id": "R1", "type": "resistor", "params": {"resistance": 10}},
                {"id": "R1", "type": "resistor", "params": {"resistance": 20}}
            ],
            "wires": []
        }
        sol = solve_direct(plan)
        self.assertFalse(sol["ok"])
        err_codes = [e["code"] for e in sol.get("errors", [])]
        self.assertIn("DUPLICATE_ID", err_codes)

    def test_f2_03_assembly_invalid_endpoint_rejection(self):
        plan = {
            "schema_version": 1,
            "recipe": "custom",
            "components": [
                {"id": "V1", "type": "power_supply", "params": {"voltage": 6}},
                {"id": "R1", "type": "resistor", "params": {"resistance": 10}}
            ],
            "wires": [
                {"id": "W1", "from": "V1.positive", "to": "R1.nonexistent_port"}
            ]
        }
        sol = solve_direct(plan)
        self.assertFalse(sol["ok"])
        err_codes = [e["code"] for e in sol.get("errors", [])]
        self.assertIn("INVALID_ENDPOINT", err_codes)

    def test_f2_04_assembly_out_of_bounds_parameters(self):
        # Power supply voltage > 12V must be rejected
        plan = {
            "schema_version": 1,
            "recipe": "ohm",
            "params": {"voltage": 15, "resistance": 10}
        }
        with self.assertRaises(ValueError):
            circuit_resources.resolve_plan(plan)

    def test_f2_05_assembly_unknown_device_type(self):
        plan = {
            "schema_version": 1,
            "recipe": "custom",
            "components": [
                {"id": "X1", "type": "superconducting_qubit", "params": {"freq": 5.0}}
            ],
            "wires": []
        }
        sol = solve_direct(plan)
        self.assertFalse(sol["ok"])
        err_codes = [e["code"] for e in sol.get("errors", [])]
        self.assertIn("UNKNOWN_COMPONENT_TYPE", err_codes)

    # -------------------------------------------------------------------------
    # Feature 3: Deterministic MNA Calculation (circuit_solve_validate)
    # -------------------------------------------------------------------------
    def test_f3_01_mna_ohms_law(self):
        cfg, sol = circuit_resources.resolve_plan({"recipe": "ohm", "params": {"voltage": 6, "resistance": 10}})
        self.assertTrue(sol["ok"])
        self.assertAlmostEqual(sol["totalCurrent"], 0.6, places=7)
        self.assertAlmostEqual(sol["components"]["A1"]["current"], 0.6, places=7)
        self.assertAlmostEqual(sol["components"]["M1"]["voltage"], 6.0, places=7)

    def test_f3_02_mna_series_circuit(self):
        cfg, sol = circuit_resources.resolve_plan({
            "recipe": "series",
            "params": {"voltage": 6, "resistance": 10, "resistance2": 20}
        })
        self.assertTrue(sol["ok"])
        self.assertAlmostEqual(sol["totalCurrent"], 0.2, places=7)
        self.assertAlmostEqual(sol["components"]["R1"]["voltage"], 2.0, places=7)
        self.assertAlmostEqual(sol["components"]["R2"]["voltage"], 4.0, places=7)
        # KVL: U1 + U2 = U_total
        self.assertAlmostEqual(
            sol["components"]["R1"]["voltage"] + sol["components"]["R2"]["voltage"],
            sol["sourceVoltage"],
            places=7
        )

    def test_f3_03_mna_parallel_circuit(self):
        cfg, sol = circuit_resources.resolve_plan({
            "recipe": "parallel",
            "params": {"voltage": 6, "resistance": 10, "resistance2": 20}
        })
        self.assertTrue(sol["ok"])
        self.assertAlmostEqual(sol["totalCurrent"], 0.9, places=7)
        self.assertAlmostEqual(sol["components"]["R1"]["current"], 0.6, places=7)
        self.assertAlmostEqual(sol["components"]["R2"]["current"], 0.3, places=7)
        # KCL: I1 + I2 = I_total
        self.assertAlmostEqual(
            sol["components"]["R1"]["current"] + sol["components"]["R2"]["current"],
            sol["totalCurrent"],
            places=7
        )

    def test_f3_04_mna_voltage_divider_potentiometer(self):
        # 3-terminal potentiometer voltage divider
        plan = {
            "schema_version": 1,
            "recipe": "voltage_divider",
            "components": [
                {"id": "V1", "type": "power_supply", "params": {"voltage": 6}},
                {"id": "S1", "type": "switch", "params": {"closed": True}},
                {"id": "RH1", "type": "rheostat", "params": {"maxResistance": 50, "position": 0.5}},
                {"id": "A1", "type": "ammeter", "params": {"range": 0.6}},
                {"id": "M1", "type": "voltmeter", "params": {"range": 15}},
                {"id": "R1", "type": "resistor", "params": {"resistance": 10}}
            ],
            "wires": [
                {"id": "W1", "from": "V1.positive", "to": "S1.a"},
                {"id": "W2", "from": "S1.b", "to": "RH1.a"},
                {"id": "W3", "from": "RH1.b", "to": "V1.negative"},
                {"id": "W4", "from": "RH1.slider", "to": "A1.positive"},
                {"id": "W5", "from": "A1.negative", "to": "R1.a"},
                {"id": "W6", "from": "R1.b", "to": "V1.negative"},
                {"id": "W7", "from": "M1.positive", "to": "R1.a"},
                {"id": "W8", "from": "M1.negative", "to": "R1.b"}
            ]
        }
        res, code = solve_via_bridge(plan)
        self.assertEqual(code, 0)
        sol = res["solution"]
        self.assertTrue(sol["ok"])
        # Derivation:
        # Ra = 25Ω, Rb = 25Ω. Rp = (25*10)/(25+10) = 50/7 Ω. Rtot = 25 + 50/7 = 225/7 Ω.
        # Itot = 6 / (225/7) = 14/75 ≈ 0.186667 A.
        # Vp = 14/75 * 50/7 = 4/3 ≈ 1.333333 V.
        # I_load = (4/3)/10 = 2/15 ≈ 0.133333 A.
        self.assertAlmostEqual(sol["totalCurrent"], 14 / 75, places=5)
        self.assertAlmostEqual(sol["components"]["A1"]["current"], 2 / 15, places=5)
        self.assertAlmostEqual(sol["components"]["M1"]["voltage"], 4 / 3, places=5)

    def test_f3_05_mna_dual_resistor_network(self):
        # Dual-resistor network with unequal branches
        plan = {
            "schema_version": 1,
            "recipe": "dual_resistor",
            "components": [
                {"id": "V1", "type": "power_supply", "params": {"voltage": 6}},
                {"id": "S1", "type": "switch", "params": {"closed": True}},
                {"id": "A1", "type": "ammeter", "params": {"range": 3}},
                {"id": "R1", "type": "resistor", "params": {"resistance": 15}},
                {"id": "R2", "type": "resistor", "params": {"resistance": 30}}
            ],
            "wires": [
                {"id": "W1", "from": "V1.positive", "to": "S1.a"},
                {"id": "W2", "from": "S1.b", "to": "A1.positive"},
                {"id": "W3", "from": "A1.negative", "to": "R1.a"},
                {"id": "W4", "from": "A1.negative", "to": "R2.a"},
                {"id": "W5", "from": "R1.b", "to": "V1.negative"},
                {"id": "W6", "from": "R2.b", "to": "V1.negative"}
            ]
        }
        res, code = solve_via_bridge(plan)
        self.assertEqual(code, 0)
        sol = res["solution"]
        self.assertTrue(sol["ok"])
        # Req = (15*30)/(15+30) = 450/45 = 10Ω.
        # Itot = 6 / 10 = 0.6A.
        # I(R1) = 6/15 = 0.4A, I(R2) = 6/30 = 0.2A.
        self.assertAlmostEqual(sol["totalCurrent"], 0.6, places=7)
        self.assertAlmostEqual(sol["components"]["R1"]["current"], 0.4, places=7)
        self.assertAlmostEqual(sol["components"]["R2"]["current"], 0.2, places=7)

    # -------------------------------------------------------------------------
    # Feature 4: Page Generation (circuit_render_page)
    # -------------------------------------------------------------------------
    def test_f4_01_standalone_single_file_html_regions(self):
        cfg, _ = circuit_resources.resolve_plan({"recipe": "ohm"})
        sections = circuit_resources.render_sections(cfg, "测试离线组件")
        html = shell.render("欧姆定律实验", sections)
        for sec_id in ("sec-info", "sec-stage", "sec-control", "sec-result", "sec-record", "sec-teach"):
            self.assertIn(f'id="{sec_id}"', html, f"Page missing region #{sec_id}")

    def test_f4_02_css_js_complete_inlining(self):
        cfg, _ = circuit_resources.resolve_plan({"recipe": "ohm"})
        sections = circuit_resources.render_sections(cfg, "离线检验")
        html = shell.render("离线自包含检验", sections)
        self.assertNotIn('<script src="http', html)
        self.assertNotIn('<link href="http', html)
        self.assertIn('<style>', html)
        self.assertIn('<script>', html)

    def test_f4_03_apparatus_svg_canvas_binding(self):
        cfg, _ = circuit_resources.resolve_plan({"recipe": "resistance"})
        sections = circuit_resources.render_sections(cfg, "器材画板检验")
        html = shell.render("伏安法测电阻", sections)
        self.assertIn('<svg id="cv"', html)
        self.assertIn('viewBox="0 0 1000 650"', html)
        self.assertIn('data-visual-type="apparatus"', html)

    def test_f4_04_dynamic_readout_elements(self):
        cfg, _ = circuit_resources.resolve_plan({"recipe": "parallel"})
        sections = circuit_resources.render_sections(cfg, "并联电表检验")
        html = shell.render("并联电路", sections)
        self.assertIn('id="read-current"', html)
        self.assertIn('id="read-voltage"', html)
        self.assertIn('id="read-resistance"', html)
        self.assertIn('id="fml"', html)
        self.assertIn('id="alert"', html)

    def test_f4_05_zoom_editor_launcher_present(self):
        cfg, _ = circuit_resources.resolve_plan({"recipe": "series"})
        sections = circuit_resources.render_sections(cfg, "放大编辑检验")
        html = shell.render("串联电路", sections)
        self.assertIn('id="btn-enlarge"', html)
        self.assertIn('CIRCUIT_PAGE.mount', html)

    # -------------------------------------------------------------------------
    # Feature 5: Offline Viewing & Interactive Operation
    # -------------------------------------------------------------------------
    def test_f5_01_offline_shell_validation_passes(self):
        cfg, _ = circuit_resources.resolve_plan({"recipe": "ohm"})
        sections = circuit_resources.render_sections(cfg, "离线示例")
        html = shell.render("欧姆定律", sections)
        problems = shell.validate(html)
        self.assertEqual(problems, [], f"Shell validation failed: {problems}")

    def test_f5_02_meter_reading_dom_attributes(self):
        ohm_html = (ROOT / 'examples' / 'circuits' / 'ohm.html').read_text(encoding='utf-8')
        self.assertIn('CIRCUIT_PAGE', ohm_html)
        self.assertIn('window.__CIRCUIT_INITIAL__', ohm_html)

    def test_f5_03_switch_control_contract(self):
        cfg, _ = circuit_resources.resolve_plan({"recipe": "ohm"})
        sections = circuit_resources.render_sections(cfg, "开关控制检验")
        html = shell.render("欧姆定律", sections)
        self.assertIn('id="btn-switch"', html)

    def test_f5_04_responsive_layout_contract(self):
        cfg, _ = circuit_resources.resolve_plan({"recipe": "ohm"})
        sections = circuit_resources.render_sections(cfg, "响应式检验")
        html = shell.render("响应式布局", sections)
        self.assertIn('@media', html)
        self.assertIn('760px', html)

    def test_f5_05_data_record_and_reset_contract(self):
        cfg, _ = circuit_resources.resolve_plan({"recipe": "resistance"})
        sections = circuit_resources.render_sections(cfg, "记录表格检验")
        html = shell.render("伏安法测电阻", sections)
        self.assertIn('id="btn-record"', html)
        self.assertIn('id="btn-reset"', html)
        self.assertIn('id="rows"', html)


# =============================================================================
# TIER 2: BOUNDARY & CORNER CASES (8 test cases)
# =============================================================================

class TestTier2BoundaryCases(unittest.TestCase):
    """Tier 2: Boundary & Corner Cases (empty wires, short circuit, floating nodes, limits, overrange)."""

    def test_b1_empty_wires_disconnected_circuit(self):
        plan = {
            "schema_version": 1,
            "recipe": "custom",
            "components": [
                {"id": "V1", "type": "power_supply", "params": {"voltage": 6}},
                {"id": "R1", "type": "resistor", "params": {"resistance": 10}}
            ],
            "wires": []
        }
        sol = solve_direct(plan)
        self.assertFalse(sol["ok"])
        err_codes = [e["code"] for e in sol.get("errors", [])]
        self.assertIn("FLOATING_SUBCIRCUIT", err_codes)

    def test_b2_short_circuit_protection_source_short(self):
        plan = {
            "schema_version": 1,
            "recipe": "custom",
            "components": [
                {"id": "V1", "type": "power_supply", "params": {"voltage": 6}}
            ],
            "wires": [
                {"id": "W1", "from": "V1.positive", "to": "V1.negative"}
            ]
        }
        sol = solve_direct(plan)
        self.assertFalse(sol["ok"])
        err_codes = [e["code"] for e in sol.get("errors", [])]
        self.assertIn("SOURCE_SHORT", err_codes, "Must trigger SOURCE_SHORT diagnostic")

    def test_b3_floating_subcircuit_protection(self):
        plan = {
            "schema_version": 1,
            "recipe": "custom",
            "components": [
                {"id": "V1", "type": "power_supply", "params": {"voltage": 6}},
                {"id": "R1", "type": "resistor", "params": {"resistance": 10}},
                {"id": "R2", "type": "resistor", "params": {"resistance": 20}}
            ],
            "wires": [
                {"id": "W1", "from": "V1.positive", "to": "R1.a"},
                {"id": "W2", "from": "R1.b", "to": "V1.negative"},
                # R2 is floating
                {"id": "W3", "from": "R2.a", "to": "R2.b"}
            ]
        }
        sol = solve_direct(plan)
        self.assertFalse(sol["ok"])
        err_codes = [e["code"] for e in sol.get("errors", [])]
        self.assertIn("FLOATING_SUBCIRCUIT", err_codes)

    def test_b4_rheostat_at_position_zero_limit(self):
        # pos=0.0: branch a-slider has 0Ω, slider-b has 50Ω
        cfg, sol = circuit_resources.resolve_plan({
            "recipe": "resistance",
            "params": {"voltage": 6, "resistance": 10, "maxResistance": 50, "position": 0.0}
        })
        self.assertTrue(sol["ok"])
        # Series: RH1(0Ω) + R1(10Ω) = 10Ω => I = 0.6A
        self.assertAlmostEqual(sol["totalCurrent"], 0.6, places=7)
        self.assertAlmostEqual(sol["components"]["R1"]["voltage"], 6.0, places=7)

    def test_b5_rheostat_at_position_one_limit(self):
        # pos=1.0: branch a-slider has 50Ω, slider-b has 0Ω
        cfg, sol = circuit_resources.resolve_plan({
            "recipe": "resistance",
            "params": {"voltage": 6, "resistance": 10, "maxResistance": 50, "position": 1.0}
        })
        self.assertTrue(sol["ok"])
        # Series: RH1(50Ω) + R1(10Ω) = 60Ω => I = 0.1A
        self.assertAlmostEqual(sol["totalCurrent"], 0.1, places=7)
        self.assertAlmostEqual(sol["components"]["R1"]["voltage"], 1.0, places=7)

    def test_b6_meter_overrange_flagging(self):
        # 6V / 10Ω = 0.6A, but ammeter range set to 0.06A
        plan = {
            "recipe": "ohm",
            "params": {"voltage": 6, "resistance": 10, "ammeterRange": 0.06}
        }
        cfg, sol = circuit_resources.resolve_plan(plan)
        self.assertTrue(sol["ok"])
        a1 = sol["components"]["A1"]
        self.assertTrue(a1["overrange"], "Ammeter must be flagged as overrange")
        self.assertAlmostEqual(a1["current"], 0.6, places=7)
        self.assertEqual(a1["range"], 0.06)

    def test_b7_zero_source_voltage_stability(self):
        cfg, sol = circuit_resources.resolve_plan({"recipe": "ohm", "params": {"voltage": 0, "resistance": 10}})
        self.assertTrue(sol["ok"])
        self.assertEqual(sol["totalCurrent"], 0.0)
        self.assertGreater(sol["equivalentResistance"], 0.0)

    def test_b8_non_finite_parameter_rejection(self):
        invalid_plans = [
            {"recipe": "ohm", "params": {"voltage": float("nan")}},
            {"recipe": "ohm", "params": {"voltage": float("inf")}},
            {"recipe": "ohm", "params": {"resistance": -5.0}},
            {"recipe": "resistance", "params": {"position": 1.5}}
        ]
        for plan in invalid_plans:
            with self.subTest(plan=plan):
                with self.assertRaises((ValueError, Exception)):
                    circuit_resources.resolve_plan(plan)


# =============================================================================
# TIER 3: CROSS-FEATURE COMBINATIONS (5 test cases)
# =============================================================================

class TestTier3CrossFeatureCombinations(unittest.TestCase):
    """Tier 3: Pairwise & Cross-Feature Interactions."""

    def test_c1_switch_toggle_meter_deflection_interaction(self):
        # Closed switch -> I=0.6A; Open switch -> I=0A, supply stays energized
        cfg_closed, sol_closed = circuit_resources.resolve_plan({"recipe": "ohm", "params": {"closed": True}})
        self.assertAlmostEqual(sol_closed["totalCurrent"], 0.6, places=7)
        self.assertAlmostEqual(sol_closed["components"]["A1"]["current"], 0.6, places=7)
        self.assertAlmostEqual(sol_closed["components"]["M1"]["voltage"], 6.0, places=7)

        cfg_open, sol_open = circuit_resources.resolve_plan({"recipe": "ohm", "params": {"closed": False}})
        self.assertEqual(sol_open["totalCurrent"], 0.0)
        self.assertEqual(sol_open["components"]["A1"]["current"], 0.0)
        self.assertEqual(sol_open["components"]["M1"]["voltage"], 0.0)
        self.assertEqual(sol_open["sourceVoltage"], 6.0)

    def test_c2_rheostat_sweep_load_voltage_regulation_interaction(self):
        # Monotonicity test: varying rheostat position must continuously vary load current
        prev_current = -1
        for pos in (0.0, 0.2, 0.5, 0.8, 1.0):
            cfg, sol = circuit_resources.resolve_plan({
                "recipe": "resistance",
                "params": {"voltage": 6, "resistance": 10, "maxResistance": 50, "position": pos}
            })
            curr = sol["totalCurrent"]
            if prev_current >= 0:
                self.assertLess(curr, prev_current, f"Current must strictly decrease as position increases: {curr} >= {prev_current}")
            prev_current = curr

    def test_c3_isolated_zoom_editor_postmessage_contract(self):
        editor_path = ROOT / 'frame' / 'circuit' / 'editor.js'
        self.assertTrue(editor_path.exists(), "editor.js must exist")
        content = editor_path.read_text(encoding='utf-8')
        # Verify token authorization and postMessage contracts
        self.assertIn("postMessage", content)
        self.assertIn("circuit-apply", content)
        self.assertIn("token", content)

    def test_c4_meter_range_switch_overrange_warning_record_lock(self):
        page_path = ROOT / 'frame' / 'circuit' / 'page.js'
        content = page_path.read_text(encoding='utf-8')
        self.assertIn("overrange", content)
        self.assertIn("btn-record", content)
        self.assertIn("disabled", content)

    def test_c5_apparatus_coordinate_nudge_preserves_wire_topology(self):
        cfg, sol = circuit_resources.resolve_plan({"recipe": "resistance"})
        initial_wires = copy.deepcopy(cfg["wires"])
        for comp in cfg["components"]:
            comp["x"] = comp.get("x", 100) + 40
            comp["y"] = comp.get("y", 100) + 25
        resolved_cfg, resolved_sol = circuit_resources.resolve_plan(cfg)
        self.assertEqual(resolved_cfg["wires"], initial_wires, "Moving components must not alter wire topology")
        self.assertAlmostEqual(resolved_sol["totalCurrent"], sol["totalCurrent"], places=7)


# =============================================================================
# TIER 4: REAL-WORLD APPLICATION SCENARIOS (6 test cases)
# =============================================================================

class TestTier4RealWorldScenarios(unittest.TestCase):
    """Tier 4: Real-World Scenarios (Voltage Divider, Dual-Resistor Network, 4 Regressions)."""

    def test_r1_voltage_divider_potentiometer_experiment_e2e(self):
        """Voltage Divider Experiment: continuous 0-6V regulation across a load resistor."""
        # Test 3 positions: 0.2, 0.5, 0.8
        for pos in (0.2, 0.5, 0.8):
            with self.subTest(pos=pos):
                plan = {
                    "schema_version": 1,
                    "recipe": "voltage_divider",
                    "components": [
                        {"id": "V1", "type": "power_supply", "params": {"voltage": 6}},
                        {"id": "S1", "type": "switch", "params": {"closed": True}},
                        {"id": "RH1", "type": "rheostat", "params": {"maxResistance": 50, "position": pos}},
                        {"id": "A1", "type": "ammeter", "params": {"range": 0.6}},
                        {"id": "M1", "type": "voltmeter", "params": {"range": 15}},
                        {"id": "R1", "type": "resistor", "params": {"resistance": 10}}
                    ],
                    "wires": [
                        {"id": "W1", "from": "V1.positive", "to": "S1.a"},
                        {"id": "W2", "from": "S1.b", "to": "RH1.a"},
                        {"id": "W3", "from": "RH1.b", "to": "V1.negative"},
                        {"id": "W4", "from": "RH1.slider", "to": "A1.positive"},
                        {"id": "W5", "from": "A1.negative", "to": "R1.a"},
                        {"id": "W6", "from": "R1.b", "to": "V1.negative"},
                        {"id": "W7", "from": "M1.positive", "to": "R1.a"},
                        {"id": "W8", "from": "M1.negative", "to": "R1.b"}
                    ]
                }
                res, code = solve_via_bridge(plan)
                self.assertEqual(code, 0)
                sol = res["solution"]
                self.assertTrue(sol["ok"])

                # Analytical formula check
                r_a = 50 * pos
                r_b = 50 * (1 - pos)
                r_p = (r_b * 10) / (r_b + 10) if (r_b + 10) > 0 else 0
                r_tot = r_a + r_p
                i_tot = 6.0 / r_tot
                v_p = i_tot * r_p
                i_load = v_p / 10.0

                self.assertAlmostEqual(sol["totalCurrent"], i_tot, places=5)
                self.assertAlmostEqual(sol["components"]["M1"]["voltage"], v_p, places=5)
                self.assertAlmostEqual(sol["components"]["A1"]["current"], i_load, places=5)

    def test_r2_dual_resistor_network_experiment_e2e(self):
        """Dual-Resistor Network: Current splitting between parallel branches."""
        plan = {
            "schema_version": 1,
            "recipe": "dual_resistor",
            "components": [
                {"id": "V1", "type": "power_supply", "params": {"voltage": 6}},
                {"id": "S1", "type": "switch", "params": {"closed": True}},
                {"id": "A1", "type": "ammeter", "params": {"range": 3}},
                {"id": "R1", "type": "resistor", "params": {"resistance": 20}},
                {"id": "R2", "type": "resistor", "params": {"resistance": 30}}
            ],
            "wires": [
                {"id": "W1", "from": "V1.positive", "to": "S1.a"},
                {"id": "W2", "from": "S1.b", "to": "A1.positive"},
                {"id": "W3", "from": "A1.negative", "to": "R1.a"},
                {"id": "W4", "from": "A1.negative", "to": "R2.a"},
                {"id": "W5", "from": "R1.b", "to": "V1.negative"},
                {"id": "W6", "from": "R2.b", "to": "V1.negative"}
            ]
        }
        res, code = solve_via_bridge(plan)
        self.assertEqual(code, 0)
        sol = res["solution"]
        self.assertTrue(sol["ok"])
        # Req = (20*30)/50 = 12Ω. Itot = 6/12 = 0.5A. I(R1) = 6/20 = 0.3A. I(R2) = 6/30 = 0.2A.
        self.assertAlmostEqual(sol["totalCurrent"], 0.5, places=7)
        self.assertAlmostEqual(sol["components"]["R1"]["current"], 0.3, places=7)
        self.assertAlmostEqual(sol["components"]["R2"]["current"], 0.2, places=7)

    def test_r3_ohm_experiment_regression_e2e(self):
        cfg, sol = circuit_resources.resolve_plan({"recipe": "ohm"})
        self.assertAlmostEqual(sol["totalCurrent"], 0.6, places=7)
        self.assertAlmostEqual(sol["components"]["M1"]["voltage"], 6.0, places=7)
        path = ROOT / 'examples' / 'circuits' / 'ohm.html'
        self.assertTrue(path.exists(), "examples/circuits/ohm.html must exist")

    def test_r4_resistance_experiment_regression_e2e(self):
        cfg, sol = circuit_resources.resolve_plan({"recipe": "resistance"})
        self.assertAlmostEqual(sol["totalCurrent"], 0.3, places=7)
        self.assertAlmostEqual(sol["components"]["M1"]["voltage"], 3.0, places=7)
        path = ROOT / 'examples' / 'circuits' / 'resistance.html'
        self.assertTrue(path.exists(), "examples/circuits/resistance.html must exist")

    def test_r5_series_experiment_regression_e2e(self):
        cfg, sol = circuit_resources.resolve_plan({"recipe": "series"})
        self.assertAlmostEqual(sol["totalCurrent"], 0.2, places=7)
        self.assertAlmostEqual(sol["components"]["R1"]["voltage"], 2.0, places=7)
        self.assertAlmostEqual(sol["components"]["R2"]["voltage"], 4.0, places=7)
        path = ROOT / 'examples' / 'circuits' / 'series.html'
        self.assertTrue(path.exists(), "examples/circuits/series.html must exist")

    def test_r6_parallel_experiment_regression_e2e(self):
        cfg, sol = circuit_resources.resolve_plan({"recipe": "parallel"})
        self.assertAlmostEqual(sol["totalCurrent"], 0.9, places=7)
        self.assertAlmostEqual(sol["components"]["R1"]["current"], 0.6, places=7)
        self.assertAlmostEqual(sol["components"]["R2"]["current"], 0.3, places=7)
        path = ROOT / 'examples' / 'circuits' / 'parallel.html'
        self.assertTrue(path.exists(), "examples/circuits/parallel.html must exist")


if __name__ == '__main__':
    unittest.main()
