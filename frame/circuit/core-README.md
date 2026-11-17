# 直流器材内核

## 职责

[core.js](core.js) 将实物器材的端口和导线配置求解为稳态直流读数。第一阶段页面只生成固定实验；配置格式为后续接线交互预留，不表示页面已经支持自由接线。求解器不依赖 DOM、网络或 npm 包。

## 内容与用法

- [core.js](core.js)：浏览器脚本提供全局 `CIRCUIT`，Node 通过 `require` 使用相同 API。
- [catalog.json](catalog.json)：器材类型、端口、参数、四个固定实验、能力边界与来源。
- [core.test.js](core.test.js)：解析值、开关、滑片端点、表头极性、超量程、错误拓扑、配置校验与浏览器加载测试。实测命令为 `node --test frame/circuit/core.test.js`，在工程根目录执行。

```js
const config = CIRCUIT.createExperiment('resistance', {
  voltage: 6, resistance: 10, maxResistance: 50, position: 0.2
});
const solution = CIRCUIT.solve(config);
// solution.ok === true
// solution.components.A1.value 约为 0.3 A
// solution.components.M1.value 约为 3 V
```

`createExperiment(recipe, params={})` 支持 `ohm`、`resistance`、`series`、`parallel`。参数为 `voltage`（6 V）、`resistance`（10 Ω）、`resistance2`（20 Ω）、`maxResistance`（50 Ω）、`position`（0.2）、`closed`（true）、`ammeterRange`（并联默认 3 A，其余默认 0.6 A）、`voltmeterRange`（15 V）。显式传入的非法物理参数由 `solve` 返回校验错误；未知实验抛出带 `UNKNOWN_RECIPE` 的异常。

配置为 `{schema_version:1, recipe, components, wires}`。器材项使用 `{id,type,params}`，允许附加 `x`、`y` 等展示信息；导线为 `{id,from,to}`，端点示例是 `R1.a`、`M1.positive`。展示信息不参与求解。固定实验 ID 是 `V1`、`A1`、`M1`、`R1`、`S1`，串并联增加 `R2`，测电阻增加 `RH1`。

`solve(config)` 不修改配置，返回 `{ok,status,errors,components,totalCurrent,sourceVoltage,equivalentResistance,nodeVoltages}`：

- `status` 为 `ok`、`open` 或 `error`。正常断路的 `ok` 仍为 true，总电流为 0，等效电阻为 `Infinity`；没有为电压表填入虚构的电源电压。
- `components[id]` 含 `current`、`voltage`、`value`、`range`、`overrange`。电流表的 `value` 是 A，电压表是 V，电阻与变阻器是 Ω，电源是 V，开关是 1/0。非仪表的 `range` 为 null。
- 正负端器材的电压为 `positive-negative`，电流为流入 positive 的方向；电源供电时器材自身 `current` 为负，`totalCurrent` 为正。电阻电流以 a→b 为正，变阻器读 a→slider；仪表读数保留正负号，超量程按绝对值比较。
- `nodeVoltages` 以端点字符串为键，以电源负端为 0 V。`errors` 为 `{code,message}` 数组；非法配置与不支持的拓扑返回空读数 null，不把 null 当作 0。

## 与上下层的关系

页面根据 [catalog.json](catalog.json) 展示器材、用 `createExperiment` 生成配置，再让 `solve` 提供统一读数。`M1` 始终测 `R1` 两端，`A1` 测回路总电流；串联中 `M1` 显示 R1 的分压。测电阻实验用 RH1 的 a 和 slider 串联调流，b 可不接；完整轨道包含 a→slider 与 slider→b 两段。

电阻与电压源的改进节点法（MNA）盖章、部分主元消元改编自工作区 `code/eduforge/tools/labkit/circuit/core.mjs`。本模块新增器材端口图、并查集合点、理想仪表、三端变阻器、错误校验及固定实验。工作区 `source/library/circuit-lab-evidence.json` 是 CircuitJS1 的历史证据；当前模块没有调用 CircuitJS1，当前结论以本地解析测试为准，不能把历史引擎测试写成本轮实测。

## 已知边界与纪律

- 第一阶段仅支持一个直流电源；电压非负，电阻与最大阻值必须大于 0，滑片位置是 0～1。量程必须为正的有限数。
- 导线与闭合开关通过并查集合并节点；电流表作为理想零电压支路，电压表无限内阻。闭合开关电流在合点后不唯一，返回 null；断开开关电流为 0，电压仍由端点求得。
- 电源短路（含电流表误并联）、悬空子电路/表头、重复 ID、无效端点和冲突的理想支路会显式报错。电源供电正常但完全被导线旁路的电流表读数可为 null，不能把它呈现为已测得的 0。
- 非线性、交流、电容/电感暂态、有限内阻仪表、任意多电源或任意接线能力为 pending；极端参数可能超出数值求解范围，返回错误而非伪造读数。
- `Infinity` 是正常断路的内存结果；若序列化求解结果为 JSON，应明确转换为产品约定的断路标识，原始配置不受此限制。不要将 `JSON.stringify` 自动转成的 null 解释为已知等效电阻。
