# circuit — 可调用的实物电路器件与独立放大编辑页

## 职责

把 Agent 输出的器件与接线配置变成可求解、可操作、可离线导出的实物电路。主页面仍使用师伴原有六区域外壳，电路放在②演示区；标题旁的「放大调整」进入独立编辑页，可改参数、量程、位置，应用回主页面或取消丢弃。

## 内容与调用

| 文件 | 作用 |
|---|---|
| [catalog.json](catalog.json) | 器件类型、端口、参数、配方与来源；Agent 获取目录的入口 |
| [core.js](core.js) | `CIRCUIT.createExperiment(recipe, params)` 与 `CIRCUIT.solve(config)`；端子图、MNA 与理想仪表 |
| [core-README.md](core-README.md) | 配置格式、接线极性、错误和计算模型的详细说明 |
| [apparatus.js](apparatus.js) | `CIRCUIT_VIEW.render(svg, config, solution, options)`：SVG 实物教具、真实接线柱、指针、滑片、导线与位置编辑 |
| [page.js](page.js) | 主页面控件、同源读数/公式、记录、CSV、自包含 HTML 导出与放大页通信 |
| [editor.js](editor.js) | 独立放大工作区；草稿隔离、量程选择、拖动/键盘移动、应用与取消 |
| [core.test.js](core.test.js)、[apparatus.test.js](apparatus.test.js) | 计算、拓扑、异常与绘制/移动回归 |
| [LICENSE-PHET.txt](LICENSE-PHET.txt) | 本地 PhET 适配部分的完整 MIT 许可；也内嵌进生成 HTML |

浏览器装配顺序：目录 → core → apparatus → editor → page → 当前电路配置。Node 可直接 `require('./core.js')`：

```javascript
const { createExperiment, solve } = require('./core.js');
const config = createExperiment('resistance', { voltage: 6, resistance: 10, maxResistance: 50, position: 0.2 });
const result = solve(config); // 总电流 0.3 A；M1 读 R1 两端 3 V
```

`recipe` 支持 `ohm`、`resistance`、`series`、`parallel`，并扩展支持 `voltage_divider`（滑动变阻器分压控制实验）。配置持有稳定的器件 ID、`ID.port` 端点与导线 ID，位置变化不会改变连接。`M1` 测被测电阻两端电压，`A1` 测支路/干路电流；并联结果区另列两支路电流与等效电阻，串联另列 R2 分压，分压控制显示实时输出电压与负载电流。

## 与上下层的关系

- 上层：[frame](../README.md)，平台外壳、样式仍由 `shell.py` 装配，本目录不重写外壳。
- Python 接口：[circuit_resources.py](../../circuit_resources.py) 读取目录并以 Node 真实求解配置，再生成六区域；[生成 Agent](../../03_generator_agent/README.md) 让模型输出 JSON 并验证，失败回退明确标注的电路预设。
- 验收：[circuit_judge.py](../../04_review_agent/circuit_judge.py) 用纯 Python 独立 MNA 求解与解析公式复算，不采信页面自报通过；[示例](../../examples/circuits/README.md) 可直接双击打开。
- 资源来源：MNA 适配 ICT 原有 `code/eduforge/tools/labkit/circuit/core.mjs`；电源内电池金属渐变、导线端点法向曲线适配本地 `source/upstream/phet/libs/scenery-phet/js/{BatteryNode,WireNode}.ts`。表盘、电源面板、电阻、滑变与开关为项目新增，并未加载完整 PhET 仿真或 CircuitJS 多文件站点。

## 已知边界与实测

计算限于一个电源的线性稳态直流电阻网络，电表采用理想模型；生成侧电源限定 0–12 V。第一阶段保留已生成接线，完整自由增删器件/接线训练留到下一阶段。理想断路显示 0 A，不将 U/I 写成无穷大读数；无解、悬空、短路或错误端点明确报告。

并联预设使用 3 A 量程；其他预设使用 0.6 A。超量程会提示并禁用记录，放大页可改量程；满量程浮点尾差不判成超量程。放大页使用本文件内嵌资源生成的本地 Blob 页面，需浏览器允许弹出窗口；通信核对窗口对象和会话随机标识，取消不修改原页。

本轮已实测 Node 计算/器材回归、Python 配置与独立纯 Python MNA 复算、五类离线页面的浏览器交互、放大应用/取消、器材移动、量程告警及导出后重开。真实模型服务本轮未调用，模型输出协议采用替身测试；正式教学仍待教师审核。测试规模唯一登记于 ICT 的 `code/eduforge/catalog/engines/ray-optics.yaml`，这里不重复计数。

从 sgrz 根目录复测：

```powershell
node --test frame/circuit/core.test.js frame/circuit/apparatus.test.js
python -B -m unittest discover -s tests -v
python tools/build_circuit_examples.py
node tools/test_circuit_browser.js
```
