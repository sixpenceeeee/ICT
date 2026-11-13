"""Exercise numerical boundaries and the generated page's solver contract."""

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


REVIEW_DIR = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REVIEW_DIR), str(REVIEW_DIR.parent / "03_generator_agent")]

from reviewer import (MATH_MODELS, PHYSICS_MODELS, dynamic_checks, find_chrome, find_node, find_node_modules,
                      run_review, solve_quadratic, solve_thin_lens)
from generator_agent import generate, hard_validate
from mathematics.lesson_models import solve_linear_system
from physics.lesson_models import (solve_horizontal_force, solve_inclined_plane,
                                   solve_mechanical_energy, solve_plane_mirror,
                                   solve_pulley_system, solve_wave_propagation, solve_work_power)
import shell


class LessonSolverTests(unittest.TestCase):
    def test_wave_emission_and_invalid_measurements(self):
        request = {"frequency": 4, "detector_distance": 8, "travel_time": 0.5, "observation_time": 0.25}
        result = solve_wave_propagation(request)
        self.assertEqual(result["speed"], 16)
        self.assertEqual(result["wavelength"], 4)
        self.assertEqual(result["crest_positions"], [4, 0])
        self.assertEqual(result["arrival_state"], "尚未到达")
        at_detector = solve_wave_propagation({**request, "observation_time": 0.5})
        self.assertEqual(at_detector["arrival_state"], "刚到达")
        for invalid in ({"frequency": 0}, {"travel_time": 0}, {"detector_distance": 0}, {"observation_time": -1}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                solve_wave_propagation({**request, **invalid})

    def test_plane_mirror_middle_visibility_and_equal_angles(self):
        request = {"object_distance": 2, "object_height": 4, "observer_distance": 2,
                   "observer_height": -2, "mirror_half_height": 0.5}
        result = solve_plane_mirror(request)
        self.assertEqual(result["visibility"], "部分可见")
        self.assertEqual(result["image_x"], -2)
        self.assertEqual(result["visible_rays"], [[1, -0.5], [3, 0.5]])
        for source, hit in result["visible_rays"]:
            self.assertEqual((hit - source) / 2, (-2 - hit) / 2)
        for invalid in ({"mirror_half_height": 0}, {"object_distance": -1}, {"observer_distance": 0}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                solve_plane_mirror({**request, **invalid})

    def test_pulley_zero_lift_and_invalid_layout(self):
        request = {"layout": "four_strands", "load_mass": 10, "moving_mass": 2,
                   "lift_height": 0, "rope_loss_force": 5}
        result = solve_pulley_system(request)
        self.assertEqual(result["supporting_strands"], 4)
        self.assertEqual(result["pull_distance"], 0)
        self.assertAlmostEqual(result["pull_force"], 34.4)
        self.assertIsNone(result["efficiency"])
        for invalid in ({"layout": "unknown"}, {"load_mass": 0}, {"rope_loss_force": -1}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                solve_pulley_system({**request, **invalid})

    def test_inclined_plane_geometry_and_zero_input_work(self):
        request = {"mass": 5, "length": 13, "height": 0, "friction_coefficient": 0}
        horizontal = solve_inclined_plane(request)
        self.assertEqual(horizontal["input_work"], 0)
        self.assertIsNone(horizontal["efficiency"])
        vertical = solve_inclined_plane({**request, "height": 13, "friction_coefficient": 0.2})
        self.assertEqual(vertical["normal_force"], 0)
        self.assertEqual(vertical["friction_loss"], 0)
        self.assertEqual(vertical["efficiency"], 100)
        with self.assertRaises(ValueError):
            solve_inclined_plane({**request, "height": 14})

    def test_mechanical_energy_turning_point_and_insufficient_energy(self):
        request = {"mass": 2, "initial_speed": 0, "start_height": 10, "end_height": 5,
                   "nonconservative_work": -98}
        stopped = solve_mechanical_energy(request)
        self.assertEqual(stopped["state"], "末速度为零")
        self.assertEqual(stopped["final_speed"], 0)
        self.assertEqual(stopped["final_energy"], 98)
        insufficient = solve_mechanical_energy({**request, "nonconservative_work": -100})
        self.assertEqual(insufficient["state"], "能量不足")
        self.assertEqual(insufficient["energy_shortfall"], 2)
        self.assertIsNone(insufficient["final_speed"])
        with self.assertRaises(ValueError):
            solve_mechanical_energy({**request, "mass": 0})

    def test_work_power_perpendicular_and_input_limits(self):
        request = {"force": 10, "distance": 6, "angle": 90, "duration": 3}
        perpendicular = solve_work_power(request)
        self.assertEqual(perpendicular["work"], 0)
        self.assertEqual(perpendicular["average_power"], 0)
        self.assertEqual(perpendicular["state"], "零功")
        self.assertGreater(solve_work_power({**request, "angle": 89.999999})["work"], 0)
        self.assertLess(solve_work_power({**request, "angle": 90.000001})["work"], 0)
        for invalid in ({"duration": 0}, {"angle": 181}, {"distance": -1}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                solve_work_power({**request, **invalid})

    def test_linear_system_close_slopes_are_distinct(self):
        request = {"k1": 1, "b1": 0, "k2": 1.0000000000000002, "b2": 1}
        result = solve_linear_system(request)
        self.assertEqual(result["status"], "唯一交点")
        self.assertEqual(result["x"], -4503599627370496)
        self.assertEqual(result["y"], result["x"])
        with self.assertRaises(ValueError):
            solve_linear_system({**request, "k1": True})

    def test_horizontal_force_zero_friction_and_input_limits(self):
        request = {"mass": 2, "applied_force": -6, "velocity": 0,
                   "static_coefficient": 0, "kinetic_coefficient": 0}
        result = solve_horizontal_force(request)
        self.assertEqual(result["state"], "开始滑动")
        self.assertEqual(result["friction"], 0)
        self.assertEqual(result["acceleration"], -3)
        stationary = solve_horizontal_force({**request, "applied_force": 0})
        self.assertEqual(stationary["state"], "静止")
        for invalid in ({"mass": 0}, {"kinetic_coefficient": 0.2}, {"static_coefficient": -0.1}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                solve_horizontal_force({**request, **invalid})

    def test_quadratic_roots_and_vertical_translation(self):
        base = solve_quadratic({"a": 1, "b": -2, "c": 0})
        tangent = solve_quadratic({"a": 1, "b": -2, "c": 1})
        above = solve_quadratic({"a": 1, "b": -2, "c": 2})
        self.assertEqual([base["roots"], tangent["roots"], above["roots"]], [[0, 2], [1], []])
        self.assertEqual([base["vertex_y"], tangent["vertex_y"], above["vertex_y"]], [-1, 0, 1])
        self.assertEqual([base["axis_x"], tangent["axis_x"], above["axis_x"]], [1, 1, 1])
        steep = solve_quadratic({"a": -1e-6, "b": 1e6, "c": -1})
        self.assertAlmostEqual(steep["roots"][0], 1e-6)
        self.assertEqual(steep["opening"], "开口向下")
        with self.assertRaises(ValueError):
            solve_quadratic({"a": 0, "b": 2, "c": 3})

    def test_lens_focus_and_twice_focal_distance(self):
        cases = [(5, -10, 2), (10, None, None), (15, 30, -2),
                 (20, 20, -1), (30, 15, -0.5)]
        for u, distance, magnification in cases:
            with self.subTest(u=u):
                result = solve_thin_lens({"u": u, "f": 10})
                self.assertEqual(result["image_distance_cm"], distance)
                self.assertEqual(result["magnification"], magnification)
        near = solve_thin_lens({"u": 10.000000000000002, "f": 10})
        self.assertGreater(near["image_distance_cm"], 1e15)
        with self.assertRaises(ValueError):
            solve_thin_lens({"u": 10, "f": 0})

    @unittest.skipUnless(find_node() and find_node_modules() and find_chrome(), "需要 Node、Playwright 和浏览器")
    def test_offline_pages_and_review(self):
        cases = (
            ("数学", "二次函数", "graph", "MATH_QUADRATIC", "MATH.solveQuadratic", "MATH.funcPlot",
             {"a": (-2, 2, 1), "b": (-2, 0, -2), "c": (0, 2, 0)},
             ("vertex_x", "vertex_y", "axis_x", "discriminant", "roots", "y_intercept", "opening"),
             "quadratic"),
            ("物理", "凸透镜成像", "apparatus", "PHYS_LENS", "PHYS.solveThinLens", "PHYS.optics",
             {"u": (10, 30, 30), "f": (5, 20, 10)}, ("image_distance_cm", "magnification", "state"),
             "thinLens"),
        )
        with tempfile.TemporaryDirectory() as folder:
            for case in cases:
                self.check_offline_page(folder, *case)

    @unittest.skipUnless(find_node() and find_node_modules() and find_chrome(), "需要 Node、Playwright 和浏览器")
    def test_generated_linear_template_with_horizontal_line(self):
        request = {"学科": "数学", "年级": "初中八年级", "实验主题": "一次函数与二元一次方程组",
                   "原始需求": "用 y=-2.5x+4 与 y=3 演示一次函数与二元一次方程组。"}
        sections, metadata = generate(request, {})
        self.assertTrue(metadata["生成契约通过"], metadata["问题"])
        with tempfile.TemporaryDirectory() as folder:
            title = request["实验主题"]
            delivery = shell.deliver(shell.render(title, sections), title, folder, make_zip=False)
            req_path = Path(folder) / "request.json"
            req_path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
            report = run_review(delivery["HTML"], req_path, verbose=False)
        checks = {item["check_id"]: item for item in report["检查项"]}
        for check_id in ("J1-01", "J3-30", "G4-32"):
            self.assertEqual(checks[check_id]["status"], "pass", checks[check_id])
        self.assertEqual(report["结论"], "通过")

    @unittest.skipUnless(find_node() and find_node_modules() and find_chrome(), "需要 Node、Playwright 和浏览器")
    def test_physics_batch_pages(self):
        self.check_preset_pages("物理", "PHYS", PHYSICS_MODELS)

    @unittest.skipUnless(find_node() and find_node_modules() and find_chrome(), "需要 Node、Playwright 和浏览器")
    def test_mathematics_batch_pages(self):
        self.check_preset_pages("数学", "MATH", MATH_MODELS)

    def check_preset_pages(self, subject, namespace, models):
        with tempfile.TemporaryDirectory() as folder:
            for key, model in models.items():
                first = next(iter(model["cases"].values()))
                inputs = {}
                for name, value in first.items():
                    values = [case[name] for case in model["cases"].values()]
                    inputs[name] = (min(values), max(values), value)
                self.check_offline_page(
                    folder, subject, model["title"], model["visual"], model["prefix"],
                    namespace + "." + model["api"], model.get("draw"), inputs, tuple(model["fields"]), key)

    def check_offline_page(self, folder, subject, title, visual, prefix, api, draw, inputs, fields, key):
        model = PHYSICS_MODELS.get(key) or MATH_MODELS.get(key)
        with self.subTest(title=title):
            controls = []
            for name, (low, high, start) in inputs.items():
                marker = f'data-solver-input="{name}"'
                if isinstance(start, str):
                    values = (dict.fromkeys(case[name] for case in model["cases"].values())
                              if model else (low, high))
                    control = f'<select {marker}>' + "".join(
                        f'<option value="{value}" {"selected" if value == start else ""}>{value}</option>'
                        for value in values) + "</select>"
                else:
                    options = 'type="number" step="any"' if model else 'type="range"'
                    control = f'<input {options} {marker} min="{low}" max="{high}" value="{start}">'
                controls.append(f'<label class="exp-field">{name}{control}</label>')
            draw_code = (f"{draw}(cv, cfg, result);" if draw else """
    const context = cv.getContext('2d');
    context.clearRect(0, 0, cv.width, cv.height);
    context.fillRect(10, 10, 80, 40);
""")
            sections = {
                "1": f"<p>{subject} · {title}</p>",
                "2": f'<canvas id="cv" data-visual-type="{visual}"></canvas>',
                "3": "".join(controls),
                "4": '<div class="exp-formula">计算结果</div><p data-solver-error hidden></p>' + "".join(
                    f'<p class="exp-read">{field} <span data-solver-field="{field}"></span></p>'
                    for field in fields),
                "5": '<table class="exp-table"><tr><th>实验记录</th></tr></table>',
                "6": ("<p>改变参数并观察计算结果。比较机械能守恒和摩擦力做功的情形。</p>"
                      if key == "mechanicalEnergy" else "<p>改变参数并观察计算结果。</p>"),
                "js": f"""
const inputs = [...document.querySelectorAll('[data-solver-input]')];
const cv = document.getElementById('cv');
const error = document.querySelector('[data-solver-error]');
function render() {{
    const cfg = Object.fromEntries(inputs.map(el => [el.dataset.solverInput,
        el.tagName === 'SELECT' ? el.value : el.valueAsNumber]));
    window.__{prefix}_REQUEST__ = cfg;
    try {{
    const result = {api}(cfg);
    error.hidden = true;
    window.__{prefix}_RESULT__ = result;
    window.__DATA__ = {{params: cfg, result}};
    {draw_code}
    VIS.bindSolverReadouts(result);
    }} catch (failure) {{
        window.__{prefix}_RESULT__ = null;
        window.__DATA__ = {{params: cfg}};
        cv.getContext('2d').clearRect(0, 0, cv.width, cv.height);
        VIS.bindSolverReadouts(null);
        error.textContent = failure.message;
        error.hidden = false;
    }}
}}
for (const el of inputs) el.addEventListener('input', render);
render();
""",
            }
            request = {"学科": subject, "实验主题": title}
            if key == "mechanicalEnergy":
                request["学习目标"] = ["观察摩擦力做功对机械能的影响"]
            self.assertEqual(hard_validate(sections, request, managed_readouts=bool(model)), [])
            delivery = shell.deliver(shell.render(title, sections), title, folder, make_zip=False)
            observed, reason = dynamic_checks(delivery["HTML"])
            self.assertIsNotNone(observed, reason)
            self.assertFalse(observed.get("fatal"), observed)
            self.assertEqual(observed.get("errors"), [])
            req_file = Path(folder) / "request.json"
            req_file.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
            check_id = model["check"] if model else "J3-14" if key == "quadratic" else "J3-15"
            with patch("reviewer.dynamic_checks", return_value=(observed, None)):
                report = run_review(delivery["HTML"], req_file, verbose=False)
            checks = {check["check_id"]: check for check in report["检查项"]}
            self.assertEqual(checks[check_id]["status"], "pass", checks[check_id])
            self.assertEqual(checks["G4-32"]["status"], "pass", checks["G4-32"])
            if model:
                self.assertEqual(sum(sample["label"].startswith("preset:")
                                     for sample in observed["lessonSolvers"][key]), len(model["cases"]))
                broken_relation = copy.deepcopy(observed)
                name, field, *_ = model["relations"][0]
                altered = next(sample for sample in broken_relation["lessonSolvers"][key]
                               if sample["label"] == f"preset:{name}")
                altered["result"][field] = 987654321
                with patch("reviewer.dynamic_checks", return_value=(broken_relation, None)):
                    report = run_review(delivery["HTML"], req_file, verbose=False)
                check = next(item for item in report["检查项"] if item["check_id"] == "G4-32")
                self.assertEqual(check["status"], "fail", check)
                self.assertIn("变形关系", check["actual"])

            if key == "horizontalForce":
                wrong_friction = copy.deepcopy(observed)
                presets = {sample["label"]: sample for sample in wrong_friction["lessonSolvers"][key]}
                moving = presets["preset:same_force_sliding"]
                resting = presets["preset:below"]
                # Simulate a solver that decides from force alone and ignores velocity.
                moving["result"] = resting["result"]
                moving["fields"] = resting["fields"]
                with patch("reviewer.dynamic_checks", return_value=(wrong_friction, None)):
                    report = run_review(delivery["HTML"], req_file, verbose=False)
                checks = {check["check_id"]: check for check in report["检查项"]}
                self.assertEqual(checks["J3-23"]["status"], "fail", checks["J3-23"])
                self.assertEqual(checks["G4-32"]["status"], "fail", checks["G4-32"])
                self.assertIn("same_force_sliding", checks["J3-23"]["actual"])

            if key == "workPower":
                ignores_angle = copy.deepcopy(observed)
                presets = {sample["label"]: sample for sample in ignores_angle["lessonSolvers"][key]}
                parallel = presets["preset:parallel"]
                perpendicular = presets["preset:perpendicular"]
                perpendicular["result"] = parallel["result"]
                perpendicular["fields"] = parallel["fields"]
                with patch("reviewer.dynamic_checks", return_value=(ignores_angle, None)):
                    report = run_review(delivery["HTML"], req_file, verbose=False)
                checks = {check["check_id"]: check for check in report["检查项"]}
                self.assertEqual(checks["J3-24"]["status"], "fail", checks["J3-24"])
                self.assertEqual(checks["G4-32"]["status"], "fail", checks["G4-32"])
                self.assertIn("perpendicular", checks["J3-24"]["actual"])

            if key == "mechanicalEnergy":
                ignores_loss = copy.deepcopy(observed)
                presets = {sample["label"]: sample for sample in ignores_loss["lessonSolvers"][key]}
                conserved = presets["preset:conserved"]
                dissipated = presets["preset:dissipation"]
                dissipated["result"] = conserved["result"]
                dissipated["fields"] = conserved["fields"]
                with patch("reviewer.dynamic_checks", return_value=(ignores_loss, None)):
                    report = run_review(delivery["HTML"], req_file, verbose=False)
                checks = {check["check_id"]: check for check in report["检查项"]}
                self.assertEqual(checks["J3-25"]["status"], "fail", checks["J3-25"])
                self.assertEqual(checks["G4-32"]["status"], "fail", checks["G4-32"])
                self.assertIn("dissipation", checks["J3-25"]["actual"])

            if key == "inclinedPlane":
                wrongly_conserves_work = copy.deepcopy(observed)
                presets = {sample["label"]: sample for sample in wrongly_conserves_work["lessonSolvers"][key]}
                short = presets["preset:rough_short"]
                long = presets["preset:rough_long"]
                # The ideal-ramp shortcut incorrectly holds input work fixed.
                long["result"]["input_work"] = short["result"]["input_work"]
                long["fields"]["input_work"] = short["fields"]["input_work"]
                with patch("reviewer.dynamic_checks", return_value=(wrongly_conserves_work, None)):
                    report = run_review(delivery["HTML"], req_file, verbose=False)
                checks = {check["check_id"]: check for check in report["检查项"]}
                self.assertEqual(checks["J3-26"]["status"], "fail", checks["J3-26"])
                self.assertEqual(checks["G4-32"]["status"], "fail", checks["G4-32"])
                self.assertIn("rough_long", checks["J3-26"]["actual"])

            if key == "pulleySystem":
                counts_pulleys = copy.deepcopy(observed)
                presets = {sample["label"]: sample for sample in counts_pulleys["lessonSolvers"][key]}
                redirect = presets["preset:redirect"]
                moving = presets["preset:two"]
                # Both layouts have two pulleys, but only one has two load-bearing strands.
                for field in ("supporting_strands", "pull_distance", "pull_force"):
                    redirect["result"][field] = moving["result"][field]
                    redirect["fields"][field] = moving["fields"][field]
                with patch("reviewer.dynamic_checks", return_value=(counts_pulleys, None)):
                    report = run_review(delivery["HTML"], req_file, verbose=False)
                checks = {check["check_id"]: check for check in report["检查项"]}
                self.assertEqual(checks["J3-27"]["status"], "fail", checks["J3-27"])
                self.assertEqual(checks["G4-32"]["status"], "fail", checks["G4-32"])
                self.assertIn("redirect", checks["J3-27"]["actual"])

            if key == "planeMirror":
                endpoint_only = copy.deepcopy(observed)
                presets = {sample["label"]: sample for sample in endpoint_only["lessonSolvers"][key]}
                middle = presets["preset:middle_only"]
                middle["result"].update(visibility="不可见", visible_from=None, visible_to=None, visible_rays=[])
                middle["fields"].update(visibility=["不可见"], visible_from=["—"], visible_to=["—"])
                with patch("reviewer.dynamic_checks", return_value=(endpoint_only, None)):
                    report = run_review(delivery["HTML"], req_file, verbose=False)
                checks = {check["check_id"]: check for check in report["检查项"]}
                self.assertEqual(checks["J3-28"]["status"], "fail", checks["J3-28"])
                self.assertEqual(checks["G4-32"]["status"], "fail", checks["G4-32"])
                self.assertIn("middle_only", checks["J3-28"]["actual"])

            if key == "wavePropagation":
                changes_speed = copy.deepcopy(observed)
                presets = {sample["label"]: sample for sample in changes_speed["lessonSolvers"][key]}
                higher_frequency = presets["preset:double_frequency"]
                # A mistaken implementation uses the higher source frequency to speed up the wave.
                wrong = {"speed": 680, "wavelength": 2, "front_distance": 6.8,
                         "arrival_time": 0.01, "arrival_state": "刚到达"}
                higher_frequency["result"].update(wrong)
                higher_frequency["fields"].update({field: [str(value)] for field, value in wrong.items()})
                with patch("reviewer.dynamic_checks", return_value=(changes_speed, None)):
                    report = run_review(delivery["HTML"], req_file, verbose=False)
                checks = {check["check_id"]: check for check in report["检查项"]}
                self.assertEqual(checks["J3-29"]["status"], "fail", checks["J3-29"])
                self.assertEqual(checks["G4-32"]["status"], "fail", checks["G4-32"])
                self.assertIn("double_frequency", checks["J3-29"]["actual"])

            tampered = copy.deepcopy(observed)
            sample = next(sample for sample in reversed(tampered["lessonSolvers"][key])
                          if isinstance(sample["result"], dict))
            sample["fields"][fields[0]] = ["987654321"]
            with patch("reviewer.dynamic_checks", return_value=(tampered, None)):
                report = run_review(delivery["HTML"], req_file, verbose=False)
            check = next(item for item in report["检查项"] if item["check_id"] == check_id)
            self.assertEqual(report["发布状态"], "禁止发布")
            self.assertEqual(check["status"], "fail", check)
            self.assertIn("可见读数", check["actual"])


if __name__ == "__main__":
    unittest.main()
