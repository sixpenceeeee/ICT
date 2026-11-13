# 组块化覆盖度看板

- 清单：06_full_catalog 全学段案例（数理化）
- 判定：该知识点能否由确定性渲染器出页（不调模型）
- 总计：**77 条，可确定性渲染 61 条（79%）**

## 按学科

| 学科 | 案例 | 可渲染 | 覆盖率 |
|---|---|---|---|
| 数学 | 28 | 27 | 96% |
| 物理 | 32 | 18 | 56% |
| 化学 | 17 | 16 | 94% |

## 按场景骨架（范式）

| 学科 | 场景 | 案例 | 可渲染 | 说明 |
|---|---|---|---|---|
| 化学 | chemistry-reaction-amounts | 4 | 4 |  |
| 化学 | chemistry-solubility-curve | 2 | 2 |  |
| 化学 | chemistry-rate-equilibrium | 2 | 2 |  |
| 化学 | chemistry-change-type | 1 | 1 |  |
| 化学 | chemistry-equation-balance | 1 | 0 | 化学配平范式：需要 PageSpec 化的配平页模板 |
| 化学 | chemistry-dilution | 1 | 1 |  |
| 化学 | chemistry-ph-indicator | 1 | 1 |  |
| 化学 | chemistry-metal-activity | 1 | 1 |  |
| 化学 | chemistry-acid-base-titration | 1 | 1 |  |
| 化学 | chemistry-galvanic | 1 | 1 |  |
| 化学 | chemistry-isomer | 1 | 1 |  |
| 化学 | chemistry-crystal | 1 | 1 |  |
| 数学 | math-circle | 2 | 2 |  |
| 数学 | math-sampling | 2 | 2 |  |
| 数学 | math-quadratic | 2 | 2 |  |
| 数学 | math-rightTriangle | 2 | 2 |  |
| 数学 | math-solid-volume | 1 | 1 |  |
| 数学 | math-polygonArea | 1 | 1 |  |
| 数学 | math-spatial-geometry | 1 | 0 | 立体几何范式：尺寸参数 + 体积/展开装配 |
| 数学 | math-fractions | 1 | 1 |  |
| 数学 | math-travel | 1 | 1 |  |
| 数学 | math-linearSystem | 1 | 1 |  |
| 数学 | math-reciprocal | 1 | 1 |  |
| 数学 | math-similarTriangles | 1 | 1 |  |
| 数学 | math-cube-net-folding | 1 | 1 |  |
| 数学 | math-descriptiveStats | 1 | 1 |  |
| 数学 | math-sinusoid | 1 | 1 |  |
| 数学 | math-expLog | 1 | 1 |  |
| 数学 | math-derivative | 1 | 1 |  |
| 数学 | math-ellipse | 1 | 1 |  |
| 数学 | math-dotProduct | 1 | 1 |  |
| 数学 | math-sequences | 1 | 1 |  |
| 数学 | math-binomial | 1 | 1 |  |
| 数学 | math-regression | 1 | 1 |  |
| 数学 | math-amgm | 1 | 1 |  |
| 数学 | math-functionTransform | 1 | 1 |  |
| 物理 | physics-investigation | 10 | 0 | 学科通用探究范式：该知识点还没登记专用场景与 UI 元数据 |
| 物理 | physics-circuit-lab | 4 | 0 | 电路装配范式：netlist 控件 + 电表 DOM 绑定（CIRCUIT.draw 已就绪） |
| 物理 | physics-lever | 2 | 2 |  |
| 物理 | physics-buoyancy | 2 | 2 |  |
| 物理 | physics-refraction | 2 | 2 |  |
| 物理 | physics-motion | 2 | 2 |  |
| 物理 | physics-inclinedPlane | 1 | 1 |  |
| 物理 | physics-thin-lens | 1 | 1 |  |
| 物理 | physics-pressure | 1 | 1 |  |
| 物理 | physics-pulleySystem | 1 | 1 |  |
| 物理 | physics-density | 1 | 1 |  |
| 物理 | physics-reflection | 1 | 1 |  |
| 物理 | physics-heat | 1 | 1 |  |
| 物理 | physics-horizontalForce | 1 | 1 |  |
| 物理 | physics-projectile | 1 | 1 |  |
| 物理 | physics-mechanicalEnergy | 1 | 1 |  |

## 未覆盖知识点（按缺口归并）

**物理 · physics-investigation**（10 条）

- 缺什么：学科通用探究范式：该知识点还没登记专用场景与 UI 元数据
- 知识点：光的传播与影子、电功率、焦耳定律、大气压与海拔、圆周运动与向心力、动量守恒、带电粒子在磁场中的运动、单摆周期、气体实验定律、电磁感应定律

**物理 · physics-circuit-lab**（4 条）

- 缺什么：电路装配范式：netlist 控件 + 电表 DOM 绑定（CIRCUIT.draw 已就绪）
- 知识点：简单电路、电路：电压电阻与电流关系、串联与并联电阻、闭合电路欧姆定律

**数学 · math-spatial-geometry**（1 条）

- 缺什么：立体几何范式：尺寸参数 + 体积/展开装配
- 知识点：长方体与正方体

**化学 · chemistry-equation-balance**（1 条）

- 缺什么：化学配平范式：需要 PageSpec 化的配平页模板
- 知识点：化学方程式配平

