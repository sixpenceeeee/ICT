# 3D 凸透镜成像示例

## 职责

存放由当前源码零模型生成的 3D 光学示例页，供人工体验、截图与浏览器检查使用。

## 内容

| 文件 | 说明 |
|---|---|
| `lens3d.html` | 3D 光具座：固定模型 `f=10 cm / u=30 cm / h=2 cm / 光屏 15 cm`，单文件离线（内联 three r118、`frame/optics_solver.js`、`frame/optics3d.js`），约 2.4 MB |

生成命令（仓库根）：`python tools/build_optics3d_examples.py`——同一份产物还会写进
`03_generator_agent/output/物理/教学资源_凸透镜成像3D.html`，并在落盘前跑 `shell.validate`。

## 与上下层的关系

- 源码：[`../../optics_resources.py`](../../optics_resources.py)（六区内容与默认模型）、
  [`../../frame/optics_solver.js`](../../frame/optics_solver.js)（求解）、
  [`../../frame/optics3d.js`](../../frame/optics3d.js)（3D 渲染与交互）。
- 浏览器验收：[`../../tools/optics_page_probe.mjs`](../../tools/optics_page_probe.mjs)，
  对应的 pytest 是 [`../../tests/test_optics_page.py`](../../tests/test_optics_page.py)。
- 上层：[`../README.md`](../README.md)。

## 边界与纪律

- 这是**理想薄透镜**（近轴）演示：不含球差、色散与透镜厚度；不要用它演示这些现象。
- 产物是生成物，不要手改；改行为请改源码后重跑构建命令，并重跑页面验收。
