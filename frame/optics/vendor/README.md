# vendor — 第三方库原文

## 职责

存放 3D 光学页内联的第三方运行时原文与许可证，不改内容、不做本地修补。

## 内容

| 文件 | 说明 |
|---|---|
| `three.r118.js` | three.js r118 UMD 构建（1,255,477 B），带 `THREE` 全局 |
| `LICENSE-three.txt` | three.js 的 MIT 许可证正文 |

## 与上下层的关系

由 [`../../../shell.py`](../../../shell.py) 的 optics 分支按 `<script id="optics-vendor">` 内联；
上层的取舍说明与升级步骤见 [`../README.md`](../README.md)。

## 边界与纪律

- 不改 vendor 文件（r118 注释里有 425 处 URL 文本，任何清理都会破坏可追溯性）。
- 换版本时新增文件、更新 `shell.py` 的路径，并重跑 `python tools/build_optics3d_examples.py` 与
  `node tools/optics_page_probe.mjs examples/optics/lens3d.html`。
