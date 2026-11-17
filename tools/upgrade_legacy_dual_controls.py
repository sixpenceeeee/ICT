"""Upgrade legacy generated pages to the shared number+range control contract."""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path


def step_for(minimum: str, maximum: str) -> str:
    try:
        span = abs(float(maximum) - float(minimum))
        if span <= 0:
            return "1"
        import math
        return format(10 ** (math.floor(math.log10(span) + 1e-9) - 1), ".12g")
    except (TypeError, ValueError):
        return "1"


def attr(tag: str, name: str, default: str = "") -> str:
    match = re.search(r'\s' + re.escape(name) + r'="([^"]*)"', tag, re.I)
    return match.group(1) if match else default


def upgrade(text: str) -> tuple[str, int]:
    changed = 0

    def field(match: re.Match[str]) -> str:
        nonlocal changed
        block = match.group(0)
        if "exp-control-pair" in block:
            return block
        number_tags = re.findall(r'<input\b[^>]*\btype="number"[^>]*>', block, re.I)
        range_tags = re.findall(r'<input\b[^>]*\btype="range"[^>]*>', block, re.I)
        if number_tags and not range_tags:
            number = number_tags[0]
            input_id = attr(number, "id")
            if not input_id or not attr(number, "min") or not attr(number, "max"):
                return block
            minimum, maximum = attr(number, "min"), attr(number, "max")
            value = attr(number, "value", minimum)
            label = attr(number, "aria-label", input_id)
            slider = (
                f'<input id="{html.escape(input_id)}-range" type="range" '
                f'min="{html.escape(minimum)}" max="{html.escape(maximum)}" '
                f'step="{step_for(minimum, maximum)}" value="{html.escape(value)}" '
                f'data-legacy-range-for="{html.escape(input_id)}" '
                f'aria-label="拖动调节{html.escape(label)}">'
            )
            return block.replace(number, '<span class="exp-control-pair">' + number + slider + '</span>', 1)
        if range_tags and not number_tags:
            slider = range_tags[0]
            range_id = attr(slider, "id")
            if not range_id:
                return block
            input_id = range_id + "-input"
            minimum, maximum, value = attr(slider, "min", "0"), attr(slider, "max", "1"), attr(slider, "value", "0")
            label = attr(slider, "aria-label", range_id).replace("拖动调节", "")
            number = (
                f'<input id="{html.escape(input_id)}" type="number" '
                f'min="{html.escape(minimum)}" max="{html.escape(maximum)}" step="any" '
                f'value="{html.escape(value)}" data-legacy-number-for="{html.escape(range_id)}" '
                f'aria-label="输入{html.escape(label)}">'
            )
            slider = slider.replace(">", f' data-legacy-range-for="{html.escape(input_id)}">', 1)
            return block.replace(range_tags[0], '<span class="exp-control-pair">' + number + slider + '</span>', 1)
        return block

    upgraded = re.sub(r'<label\b[^>]*class="[^"]*exp-field[^"]*"[^>]*>.*?</label>', field, text, flags=re.I | re.S)
    if upgraded == text:
        return text, 0

    if "legacy-dual-control-style" not in upgraded:
        style = """
<style id="legacy-dual-control-style">
.exp-control-pair{display:grid;grid-template-columns:minmax(150px,.85fr) minmax(180px,1.5fr);gap:12px;align-items:center}
.exp-control-pair input{width:100%;min-width:0;box-sizing:border-box}
@media(max-width:720px){.exp-control-pair{grid-template-columns:minmax(0,1fr)}}
</style>
"""
        upgraded = upgraded.replace("</head>", style + "</head>", 1)

    if "legacy-dual-control-bridge" not in upgraded:
        bridge = """
<script id="legacy-dual-control-bridge">
(function(){
  function bind(){
    document.querySelectorAll('input[data-legacy-range-for]').forEach(function(range){
      if(range.dataset.legacyBound==='1')return;
      var number=document.getElementById(range.dataset.legacyRangeFor); if(!number)return;
      range.dataset.legacyBound='1';
      range.addEventListener('input',function(){number.value=range.value;number.dispatchEvent(new Event('input',{bubbles:true}));});
      range.addEventListener('change',function(){number.value=range.value;number.dispatchEvent(new Event('change',{bubbles:true}));});
      number.addEventListener('input',function(){if(number.value!==''){range.value=number.value;range.dispatchEvent(new Event('input',{bubbles:true}));}});
      number.addEventListener('change',function(){if(number.value!==''){range.value=number.value;range.dispatchEvent(new Event('change',{bubbles:true}));}});
    });
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',bind);else bind();
})();
</script>
"""
        upgraded = upgraded.replace("</body>", bridge + "</body>", 1)

    changed = len(re.findall(r'data-legacy-range-for=', upgraded))
    return upgraded, changed


def main() -> int:
    paths = [Path(item) for item in sys.argv[1:]]
    if not paths:
        print("usage: upgrade_legacy_dual_controls.py PAGE.html [...]")
        return 2
    for path in paths:
        text = path.read_text(encoding="utf-8")
        updated, count = upgrade(text)
        if count:
            path.write_text(updated, encoding="utf-8")
            print(f"{path}: upgraded {count} controls")
        else:
            print(f"{path}: no legacy numeric control found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
