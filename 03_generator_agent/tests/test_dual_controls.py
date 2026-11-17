import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from page_components import render_model_controls


def test_legacy_range_only_is_rendered_as_input_then_slider():
    html = render_model_controls([{
        "id": "density", "label": "密度", "kind": "range_only",
        "value": 600, "min": 0, "max": 1000, "marker": "data-solver-input",
    }])
    number_pos = html.index('id="density" type="number"')
    range_pos = html.index('id="density-range" type="range"')
    assert number_pos < range_pos
    assert 'data-solver-range-for="density"' in html


def test_standard_scene_pages_have_no_unpaired_numeric_controls():
    root = Path(__file__).parents[2] / "runs" / "all_scene_pages"
    pages = [p for p in root.rglob("*.html") if "待修复不可交付" not in p.name]
    assert len(pages) == 69
    for page in pages:
        text = page.read_text(encoding="utf-8", errors="ignore")
        numbers = set(re.findall(r'<input\b[^>]*type="number"[^>]*\sid="([^"]+)"', text))
        pairs = set(re.findall(r'data-solver-range-for="([^"]+)"', text))
        assert numbers <= pairs, f"unpaired numeric controls in {page}"


def test_wide_solver_bounds_use_a_local_slider_domain():
    html = render_model_controls([{
        "id": "volume", "label": "物体体积", "kind": "dual",
        "value": 0.001, "min": 1e-9, "max": 10,
        "range_minimum": 0.001, "range_maximum": 0.002,
        "marker": "data-solver-input",
    }])
    slider = re.search(r'<input id="volume-range"[^>]+>', html).group(0)
    assert 'min="0.001"' in slider
    assert 'max="0.002"' in slider
    assert 'step="0.0001"' in slider


def test_inferred_slider_domain_does_not_reuse_a_billion_fold_safety_limit():
    html = render_model_controls([{
        "id": "volume", "label": "物体体积", "kind": "dual",
        "value": 0.001, "min": 1e-9, "max": 10,
        "marker": "data-solver-input",
    }])
    slider = re.search(r'<input id="volume-range"[^>]+>', html).group(0)
    assert 'max="0.002"' in slider
    assert 'step="0.0001"' in slider
