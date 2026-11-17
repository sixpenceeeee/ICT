"""不调用模型，构建共享器件库的单文件离线示例（含分压控制等五类电路）。"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from circuit_resources import TITLES, resolve_plan, render_sections
import shell


def build():
    out = ROOT / 'examples' / 'circuits'
    out.mkdir(parents=True, exist_ok=True)
    for recipe, title in TITLES.items():
        config, solution = resolve_plan({'recipe': recipe})
        html = shell.render(title, render_sections(config, '电路组件预设（离线示例）'))
        problems = shell.validate(html)
        if problems:
            raise ValueError('；'.join(problems))
        path = out / (recipe + '.html')
        path.write_text(html, encoding='utf-8')
        print(f'{recipe}: {path} | I={solution["totalCurrent"]:.6g} A')


if __name__ == '__main__':
    build()
