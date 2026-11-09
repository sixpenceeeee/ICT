# 直流电路求解器（第一版）

这组模块把欧姆定律页面的数值计算从大模型生成代码中独立出来：

- `frame/circuit_solver.js`：随 HTML 内联的页面运行时求解器，暴露 `CIRCUIT.solve(model)`。
- 同一运行时模块还提供 `CIRCUIT.bindMeters(result)` 和 `CIRCUIT.draw(cv, model, result)`：前者从支路结果写入表计 DOM，后者按 netlist 节点连接绘制原理图。
- `circuit_solver.py`：审查器使用的独立参考实现，采用 Python 改进节点电压法，与页面实现分开运行。

## 支持范围

直流电阻网络，元件包括电阻、理想独立电压源、理想独立电流源、理想开关、理想电流表和高内阻电压表。支持串联、并联和混联；闭合开关按零电压支路处理，断开开关不导通。电流表按零压降串联支路建模；电压表按默认 10 MΩ 输入电阻的并联支路建模（可通过 `inputOhms` 调整）。出现浮空节点、矛盾理想电压源等奇异拓扑时会报错，页面应显示无效/保护状态，不可展示伪造的正常读数。

当前不模拟二极管、晶体管、电容/电感动态过程、交流电、温升、真实电表内阻和器材烧毁后的热效应。需要这些能力时应扩充模型和独立校验，不能将当前求解结果外推到这些场景。

## 模型格式

```js
var model = {
  ground: '0',
  components: [
    { id: 'V1', type: 'voltage_source', positive: 'n1', negative: '0', volts: 6 },
    { id: 'A1', type: 'ammeter', from: 'n1', to: 'n2' },
    { id: 'R1', type: 'resistor', from: 'n2', to: '0', ohms: 10 },
    { id: 'V2', type: 'voltmeter', from: 'n2', to: '0', inputOhms: 10000000 }
  ]
};
var result = CIRCUIT.solve(model);
var currentR1 = CIRCUIT.meter(result, 'R1', 'current');
var voltageR1 = CIRCUIT.meter(result, 'R1', 'voltage');
```

上例中电流表 `A1` 与 `R1` 串联，电压表 `V2` 并联在 `R1` 两端，理论读数约为 `0.6 A` 和 `6 V`；电压表有限内阻会带来极小负载效应。结果同时满足 KCL、KVL 和功率守恒。

返回 `nodes` 节点电压、`branches` 每支路电压/电流/功率和 `checks` KCL 残差、独立回路的 KVL 残差、理想电压源约束、功率平衡残差。所有支路电流方向均为 `from` → `to`；电压源也可用 `positive` / `negative` 表示正负端。

页面生成要求将当前拓扑赋给 `window.__CIRCUIT_MODEL__`，将解赋给 `window.__CIRCUIT_RESULT__`，每次 render 顺序调用 `CIRCUIT.solve(model)`、`CIRCUIT.draw(cv, model, result)` 和 `CIRCUIT.bindMeters(result)`。原理图导线直接由模型中的 `from/to` 节点连接关系绘制；表计 DOM 用 `data-circuit-current-for="R1"` 或 `data-circuit-voltage-for="R1"` 指定被测支路，数值由 `bindMeters` 写入，页面不得手算或在求解失败时回退到欧姆定律公式。审查器在首屏与参数变化后复算模型，检查图示拓扑签名、表计绑定和数值结果。

## 审查不变量

- 每个节点的 KCL 电流残差接近 0。
- 活跃电路图的基环路电压代数和接近 0（KVL）。
- 每个理想电压源两端电势差符合其设定值。
- 所有元件吸收功率的代数和接近 0（源供电与负载耗电平衡）。
- 页面求解值与独立 Python 实现的节点电压、支路电流和功率一致。
