# 离线实物电路示例

## 职责

提供欧姆定律、伏安法测电阻、串联、并联以及滑动变阻器分压控制的五类实物器材教学页面。

## 内容

| 文件 | 教学内容 |
|---|---|
| [ohm.html](ohm.html) | 欧姆定律：改变电压与电阻，观察电流 |
| [resistance.html](resistance.html) | 伏安法测电阻：观察负载电压、电流与滑动变阻器分压 |
| [series.html](series.html) | 串联：比较相同电流与电阻分压 |
| [parallel.html](parallel.html) | 并联：比较支路电流、干路电流与等效电阻 |
| [voltage_divider.html](voltage_divider.html) | 滑动变阻器分压控制：调节滑片，观察负载两端电压从 0 V 至电源电压连续可调 |

HTML 由 `python tools/build_circuit_examples.py` 从本地电路预设与配置生成，包含电源、开关、导线、电表与相应负载，内联运行脚本、样式与资源。[ohm-preview.png](ohm-preview.png) 是主页面预览，[editor-preview.png](editor-preview.png) 是独立放大工作区预览；它们由浏览器检查脚本重新截图。

## 层级关系

上层：[examples](../README.md)；预设、求解和器材源码见 [frame/circuit](../../frame/circuit/README.md)，生成与检查工具见 [tools](../../tools/README.md)。

## 边界与纪律

从 sgrz 根运行 `python tools/build_circuit_examples.py`，随后双击上表任一 HTML 即可离线体验。主页面保留师伴六区域位置，可调参数、开关、记录和复位。

1. 点击演示区标题旁的“放大调整”，浏览器会打开独立编辑页；如被拦截，允许该页面弹出窗口。
2. 在放大页改变参数、电表量程，拖动器材；选中器材后也可用方向键微调位置。
3. 点击“应用并返回”写回参数、量程和位置；点击“取消并返回”丢弃本次编辑，原页面保持打开前的状态。
4. 需要分享时使用页面导出功能，导出的 HTML 仍内联资源，可以离线重开。

第一阶段保持已生成的接线，不提供任意自由接线。浏览器复测用 `node tools/test_circuit_browser.js`；本轮流水线证据与首次窄屏问题见 [验证运行档案](../../runs/circuit-phase1-verification/README.md)。
