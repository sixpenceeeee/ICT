# optics — 3D 光具座的内联运行时

## 职责

存放 3D 凸透镜成像页面运行时需要的第三方库与许可证。页面由 `shell.py` 的 optics 分支按
`vendor/three.r118.js` → `frame/optics_solver.js` → `frame/optics3d.js` 的顺序内联成单文件。

## 内容

| 文件 | 说明 |
|---|---|
| `vendor/three.r118.js` | three.js **r118 的 UMD 构建**（1,255,477 B），来自 3JCN 离线镜像 `source/upstream/3jcn/offline/js/three.js`；带 `THREE` 全局，不需要 ESM/构建工具 |
| `vendor/LICENSE-three.txt` | three.js 的 MIT 许可证正文（取自本机 `three@0.186.1` 包的 LICENSE） |

## 为什么是 r118 而不是新版

本机 `three` 只有 r186 的 ESM 构建（`three.module.js` 662,772 B + `three.core.js` 1,458,113 B，
`three.cjs` 只是一个弃用桩），而仓库里没有 esbuild/rollup 这类打包器，也没有 npm workspace。
要在「单文件、无外链、双击可开」的约束下用真 3D，r118 UMD 是唯一现成可内联的完整构建；
它只用于相机/网格/线段/材质这些基础能力，不需要新版的 WebGPU 或后处理。

## 与上下层的关系

- 被 [`../../shell.py`](../../shell.py) 的 `render()` 内联（`<script id="optics-vendor">`），
  静态安全门会先把这一整段剥掉再查外链/网络调用（见 [`../../04_review_agent/reviewer.py`](../../04_review_agent/reviewer.py) 的 `strip_vendor`）。
- 上层：[`../README.md`](../README.md)；页面与示例见 [`../../examples/optics/`](../../examples/optics/README.md)。

## 边界与纪律

- **不要改 vendor 文件的内容**：r118 源码注释里有 425 处 URL 文本，任何「清理」都会破坏可追溯性；
  需要换版本时新增文件（如 `three.r186.bundle.js`）并同轮更新本表与 `shell.py` 的路径。
- 升级 three 必须重跑 `python tools/build_optics3d_examples.py` 与
  `node tools/optics_page_probe.mjs examples/optics/lens3d.html`，确认 3D 仍能起、视角可复位。
