# 求解器目录

按“学科 / 题型”组织，Python 求解器作为质量审查参考实现；页面运行时的 JavaScript 实现位于 `frame/`。各测试与对应题型放在同一目录下的 `tests/`。

```text
solvers/
├── mathematics/
│   ├── solid_sections/
│   │   ├── polyhedra/       # 正方体、长方体、三棱柱、正四棱锥截面，共享多面体内核与体积复算
│   │   └── curved_solids/   # 圆柱、圆锥、球体截面
│   ├── spatial_geometry/
│       └── distance_angles/ # 点/线/面距离和角度
│   └── solid_geometry/
│       ├── volume/           # 立体体积、组合体求和、分割守恒
│       └── nets_folding/     # 正方体/长方体/圆柱/圆锥展开与折叠验证
├── chemistry/
│   ├── equations/          # 化学式解析、方程式精确配平与守恒复算
│   └── reactions/          # 反应计量、溶液混合、沉淀定量、酸碱滴定、气体收集和氧化还原配平
└── physics/
    └── electric_circuits/  # 直流电路
```

## 数学：立体截面

- `solid_sections/polyhedra/`：共享凸多面体平面截面内核及正方体、长方体、直三棱柱、正四棱锥适配器；支持边界顶点、面重合、相切、空截面。体积分割用面裁剪法独立复算。
- `solid_sections/curved_solids/`：直圆柱和直圆锥使用逐高度弦长积分，返回截面边界采样；球体使用解析截圆公式。圆柱轴/圆锥轴沿 z 轴；球心在原点。
- 页面端求解和绘图 API 在 `frame/math.js`；场景选择在 `scene_registry.py`；生成约束与独立浏览器采样分别在 `generator_agent.py` 和 `04_review_agent/`。

## 数学：空间距离与角度

`mathematics/spatial_geometry/distance_angles/spatial_metrics_solver.py` 支持点点、点线、点面、线线、线面、面面距离，以及线线、线面、面面锐角；页面端 API 为 `MATH.solveSpatialMetrics(request)`。直线输入为“线上一点 + 方向向量”，平面输入为 `n·x=offset`。空间角返回 0°–90° 的较小角；相交的线面/面面距离为 0。场景库要求页面暴露 request/result，质量审查使用 Python 实现独立复算。

## 数学：立体体积

`mathematics/solid_geometry/volume/solid_volume_solver.py` 支持立方体、长方体、直三棱柱、正四棱锥、圆柱、圆锥和球体的体积公式；组合体目前只对声明为互不重叠的组成部分求和，并提供切割后的体积分割守恒检查。页面 API 为 `MATH.solveSolidVolume()`、`MATH.solveCompositeVolume()` 和 `MATH.checkVolumePartition()`；生成器和审查器要求页面暴露体积请求与结果，审查器独立复算体积。

## 数学：正方体展开与折叠

`mathematics/solid_geometry/nets_folding/cube_net_solver.py` 与 `MATH.solveCubeNet({cells,edge_length})` 面向正方体六方格展开图：先校验六个格子的连通性和五条铰链树结构，再按 90° 传播面坐标，检查六个面是否对应六个不同轴向法向，并计算公共棱端点闭合残差。验证覆盖全部 35 种自由六格连通形状，识别出 11 种正方体展开图；不支持长方体展开、曲面展开或一般折纸的自交/动画碰撞分析。

`mathematics/solid_geometry/nets_folding/cuboid_net_solver.py` 与 `MATH.solveCuboidNet({dimensions,faces})` 支持指定长、宽、高的矩形展开图。每个 face 使用 `{x,y,width,height}` 描述平面矩形位置和实际面尺寸；求解器检查面重叠、部分公共边、连通树结构，折叠后核对每个面的轴向尺寸、六个朝向和铰链闭合。质量审查使用 Python 实现独立复算。暂不处理连续折叠过程中的碰撞，也不支持圆柱/圆锥展开。

`mathematics/solid_geometry/nets_folding/cylinder_net_solver.py` 与 `MATH.solveCylinderNet(request)` 校验圆柱展开图：侧面矩形宽为 `2πr`、高为 `h`，两个底圆半径均为 `r`，并验证展开前后表面积守恒。结果还提供圆柱表面的三维采样网格，页面端和质量审查端使用同一几何数据对拍。当前不处理圆锥展开和连续折叠动画碰撞。

`mathematics/solid_geometry/nets_folding/cone_net_solver.py` 与 `MATH.solveConeNet(request)` 校验圆锥展开图：扇形半径为母线长 `l=sqrt(r²+h²)`，扇形角为 `360r/l` 度，弧长等于底面周长 `2πr`，并核对底圆和表面积守恒。输出扇形边界、底圆边界与折叠后的圆锥侧面采样网格；质量审查使用 Python 参考实现独立复算。连续折叠动画碰撞分析不在当前范围。

## 物理：直流电路

`physics/electric_circuits/circuit_solver.py` 使用改进节点电压法；页面运行时实现为 `frame/circuit_solver.js`。支持范围、模型约定和不支持的元件见该题型相关文档与测试。

## 数学：二次函数

`mathematics/quadratic_solver.py` 与 `MATH.solveQuadratic({a,b,c})` 计算顶点、对称轴、开口方向、判别式、实根和纵轴交点。接近零的判别式按相对容差 `1e-14` 归零。页面将同一结果交给 `MATH.funcPlot(cv,cfg,result)`。审查项 J3-14 复算初始状态和 a、b、c 控件变更后的结果与可见读数。

## 物理：凸透镜成像

`physics/thin_lens_solver.py` 与 `PHYS.solveThinLens({u,f})` 使用理想薄透镜模型，输入物距和焦距（cm），输出带符号像距、带符号放大率及成像状态。物距等于焦距时无有限像，像距和放大率返回 `null`。页面将同一结果交给 `PHYS.optics(cv,cfg,result)`，移动光屏不改变理论像距。审查项 J3-15 复算初始状态和物距、焦距控件变更后的结果与可见读数。

## 物理：教学模块与开发批次

| 模块 | 本轮实现 | 总清单中仍待补的题型 |
|---|---|---|
| 运动与受力 | 匀变速直线运动（含匀速）、平抛运动、一维受力与摩擦 | — |
| 功、能与简单机械 | 杠杆平衡、功与功率、机械能变化与守恒、斜面、滑轮组 | — |
| 光学成像 | 凸透镜成像、折射与全反射、平面镜成像 | — |
| 热学与流体 | 第一批：浮力与浮沉、液体压强、比热容 | — |
| 波与声学 | 波的传播与声速，含频率、周期、波长及传播速度联动 | — |

页面端接口位于 `frame/phys.js`。Python 独立实现位于 `physics/lesson_models.py`。输入、读数字段、实际浏览器控件取值及各状态之间的变形关系集中维护在 `physics/lesson_models.json`。新增题型按 J3-16 至 J3-29 独立复算，G4-32 验证真实控件变形及物理关系。

`PHYS.solveHorizontalForce(request)` 计算水平面上物块的瞬时受力和加速度。最大静摩擦力处仍可静止，超过后按将要滑动的方向计算动摩擦。物块已经滑动时，动摩擦方向由当前速度决定。网页求解器检查竖直平衡、水平合力与加速度的关系，以及静摩擦的上限或动摩擦的方向。

J3-23 的 Python 复算从动量平衡反推接触冲量。静止物块要维持静止，摩擦冲量必须抵消外力冲量，并落在静摩擦允许的区间内。超过该区间时，利用剩余冲量确定起滑方向。已滑动时，动摩擦冲量取与当前速度相反的方向。单位时间仅用于将力换算成冲量，复算仍对应当前时刻。

`PHYS.solveWorkPower(request)` 计算单个恒力沿直线位移所做的有符号功和平均功率。网页端将力投影到位移方向并乘以位移。J3-24 用同位移、同耗时的匀速等效过程先求功率，再从功率—时间图的有符号面积复算功。浏览器验收比较同一力的顺向、垂直和反向作用，也比较同一位移下不同耗时的平均功率。

`PHYS.solveMechanicalEnergy(request)` 计算初末态的动能、重力势能、机械能与末速度大小。网页端按机械能收支结算，J3-25 从重力功与非保守力总功出发，用动能定理独立复算。能量不足时返回缺口，末态读数为空。模型判断指定端点的能量相容性，沿途运动取决于实际路径和施力过程。

`PHYS.solveInclinedPlane(request)` 计算沿斜面匀速拉升时的拉力、输入功和机械效率。网页端先分解重力并平衡斜面方向上的力，J3-26 先由提升高度计算有用功，由斜面水平底边计算摩擦耗能，再把总功除以斜长反推拉力。两种计算路径都假定拉力平行于斜面。

`PHYS.solvePulleySystem(request)` 支持单定滑轮、两定滑轮和两至四承重段绳路。网页端按承重绳段分摊载荷与移动组件的重量，并叠加绳端等效阻力。J3-27 在独立绳路中模拟提升，利用绳长约束求自由端行程，再用提升功和阻力耗能反推拉力。效率只计载荷提升的有用功。

`PHYS.solvePlaneMirror(request)` 用镜面对称确定虚像，求眼睛到像的连线与镜面的交点，再用有限镜段确定实际可见部分。J3-28 按反射定律反向追迹复算像位置与光路。浏览器验收覆盖镜面边界、移眼和只看见中间一段的情形。

`PHYS.solveWavePropagation(request)` 通过实测路程和传播时间求声速，再计算周期、波长及波前位置。J3-29 从声源按周期发出波峰的时空轨迹复算位置，用相邻波峰间距求波长。模型适用于均匀静止介质中的一维传播。

## 化学：化学方程式配平

`chemistry/equations/equation_balancer.py` 解析给定化学式，构造元素/电荷守恒矩阵，用有理数高斯消元求一维零空间，再化为最简正整数系数。页面端 API 为 `CHEMSOLVER.balanceEquation(request)`，独立审查端使用 Python 参考实现重新配平并对拍系数、方程式、原子数和电荷数。支持元素符号、括号/中括号、下标数字和水合物点号；离子电荷通过 `{formula,charge}` 显式提供。此求解器只平衡用户提供的反应物和生成物，不负责预测产物；多解、无正系数解、无解和超范围输入会报错。

## 化学：反应计量与限量试剂

`chemistry/reactions/stoichiometry_solver.py` 接收任意已明确给出反应物、生成物和初始物质的量的反应，先调用配平器取得最简系数，再按 `ξ_max=min(nᵢ/νᵢ)` 和 `ξ=进度×ξ_max` 计算限量试剂、消耗/剩余量、产物量，并独立核对元素与电荷守恒。页面端 API 为 `CHEMSOLVER.solveStoichiometry(request)`；页面暴露请求、结果和可见方程式，由 Python 参考实现独立复算。J3-07 的真实控件变形包括单项物质的量/进度变化、全体用量同比缩放，以及当输入范围可达时对限量试剂临界点下方/临界点/上方进行实际页面操作；分别检查线性缩放关系、限量试剂切换和每个状态的独立复算。输入单位为 mol；不从质量或溶液浓度换算，不预测反应产物，也不模拟可逆反应和平衡。测试：`test_stoichiometry_solver.py`、`test_stoichiometry_pipeline_integration.py` 和 `browser_acceptance_stoichiometry.js`。

`chemistry/reactions/solution_mixing_solver.py` 在反应计量求解器上增加溶液输入：每种反应物给出 `concentration_mol_L`、体积和 `mL`/`L` 单位，按 `n=cV` 换算为 mol 后交给同一反应计量内核；不推断生成物或沉淀。页面端 API 为 `CHEMSOLVER.solveSolutionMixing(request)`。浏览器审查会读实际浓度、体积、单位和进度控件，改变控件生成变形样本，再由 Python 参考实现独立复算；并要求 mL 与 L 等价输入产生相同反应结果。

`chemistry/reactions/acid_base_titration_solver.py` 计算强一元酸与强一元碱的 1:1 中和滴定：输入两侧浓度、体积和单位，求初始/剩余物质的量、理论当量体积、溶液 pH/pOH 与酸性/当量/碱性状态。25°C 理想模型显式纳入水的自电离，使当量点 pH 稳定为 7。页面 API 为 `CHEMSOLVER.solveAcidBaseTitration(request)`；同一结果传给 `CHEM.titration(canvas,result)` 绘制滴定管、锥形瓶和指示剂的定性颜色。首版支持 HCl/HBr/HI/HNO3/HClO4 与 LiOH/NaOH/KOH；不适用于弱酸弱碱、多元酸碱、非理想溶液或精确预测指示剂终点。页面层变形测试使用实际控件核验酸碱浓度/体积/单位变化、mL/L 等价以及当量点前后状态，再用 Python 独立实现复算页面结果。

`chemistry/reactions/gas_collection_solver.py` 串联反应计量/限量试剂与理想气体状态方程：先由用户给出的已配平或可配平反应、反应物 mol 数和进度求目标气体产量，再按 `PV=nRT` 求体积。干燥集气使用总压；排水集气按 Antoine 方程（0–100°C）扣除水蒸气分压。页面 API 为 `CHEMSOLVER.solveGasCollection(request)`；同一结果传给 `CHEM.gasCollection(canvas,result)` 绘制发生器、导气管和排水集气槽/气体注射器。质量审查项 `J3-10` 使用 Python 独立实现复算，并在真实浏览器中变形反应物数量、进度、温度、压强和集气方式。只支持明确给定的反应与目标气体，按理想气体、指定进度计算；不预测反应产物/收率，也不模拟气体溶解、泄漏或非理想效应。测试：`test_gas_collection_solver.py`、`test_gas_collection_pipeline_integration.py` 与 `browser_acceptance_gas_collection.js`。

`chemistry/reactions/precipitation_solver.py` 使用六个可审计的常见沉淀反应模板识别反应物配对，调用已有配平、溶液 `n=cV` 换算和限量试剂内核，计算沉淀物质的量/质量与净离子方程式。支持 AgNO₃+NaCl、BaCl₂+Na₂SO₄、CaCl₂+Na₂CO₃、CuSO₄+NaOH、FeCl₃+NaOH、MgSO₄+NaOH；目录外反应明确报错，不猜产物。页面 API 为 `CHEMSOLVER.solvePrecipitation(request)`，同一结果传给 `CHEM.precipitation(canvas,result)` 显示反应前后烧杯与沉淀。J3-11 在浏览器层检查两份溶液控件、mL/L 等价、浓度和进度变化，并构造化学计量比临界点及两侧状态后由 Python 独立复算。当前假设目录反应中的沉淀完全生成，不处理 Ksp、残余溶解度、络合与副反应。测试：`test_precipitation_solver.py`、`test_precipitation_pipeline_integration.py` 与 `browser_acceptance_precipitation.js`。

`chemistry/reactions/redox_solver.py` 按明确给定的酸性/碱性介质，为用户提供的氧化还原离子方程式补入 H₂O、H⁺/OH⁻，调用精确配平器核对原子数和电荷，再用常见氧化数规则独立计算氧化/还原变化与电子守恒。支持高锰酸根/亚铁、重铬酸根/亚硫酸根、次氯酸根/碘离子和过氧化氢歧化等代表场景；页面 API 为 `CHEMSOLVER.solveRedox(request)`，同一结果传给 `CHEM.redox(canvas,result)` 展示电子转移关系。页面层必须提供酸/碱介质选择和真实的物种换序按钮；浏览器实际切换介质、改变反应物/生成物顺序后，J3-12 用 Python 参考实现分别复算，并检查方程式、氧化数、电子数和系数顺序。首版要求所有核心离子显式带整数电荷；只处理氧化数可唯一判定且为整数的常见物种，不预测产物、不判定反应是否自发，也不支持混合价态平均氧化数、复杂配合物或含歧义的物种。测试：`test_redox_solver.py`、`test_redox_pipeline_integration.py` 与 `browser_acceptance_redox.js`。

`chemistry/reactions/solubility_equilibrium_solver.py` 处理难溶盐的离子积、饱和状态与共同离子背景下的额外摩尔溶解度。输入必须明确给出固体化学式、Ksp、溶解离子的原子式/整数电荷/化学计量系数和初始浓度；先独立核对离子原子数和电荷能否还原固体，再以对数空间二分求解 `Ksp=Π(cᵢ,0+νᵢs)^νⁱ`。页面 API 为 `CHEMSOLVER.solveSolubilityEquilibrium(request)`，结果传给 `CHEM.solubility(canvas,result)` 绘制晶体、离子与可逆溶解/结晶示意。J3-13 用 Python 参考实现对拍方程、Q、状态和 s；真实控件变形提高 Ksp、增加一个共同离子浓度，并把 Q/Ksp 移到临界点下方/等于/上方，逐个检查页面输出。过饱和时只报告沉淀倾向，不假称达到新的平衡，也不计算析出量。首版按固定温度、理想稀溶液和已给定 Ksp 处理；不覆盖活度系数、温度依赖、络合、副反应或沉淀终态。测试：`test_solubility_equilibrium_solver.py`、`test_solubility_equilibrium_pipeline_integration.py` 与 `browser_acceptance_solubility_ksp.js`。

运行全部 Python 回归：

```powershell
python -m unittest discover -s 03_generator_agent/solvers -p "test_*.py" -v
```

化学反应计量的浏览器验收（需要 Node.js、Playwright 和本机 Chrome/Edge）：

```powershell
$env:NODE_PATH = "C:\Users\wangq\.workbuddy\binaries\node\workspace\node_modules"
node 03_generator_agent/solvers/chemistry/reactions/tests/browser_acceptance_stoichiometry.js
node 03_generator_agent/solvers/chemistry/reactions/tests/browser_acceptance_solution_mixing.js
node 03_generator_agent/solvers/chemistry/reactions/tests/browser_acceptance_acid_base_titration.js
node 03_generator_agent/solvers/chemistry/reactions/tests/browser_acceptance_gas_collection.js
node 03_generator_agent/solvers/chemistry/reactions/tests/browser_acceptance_precipitation.js
node 03_generator_agent/solvers/chemistry/reactions/tests/browser_acceptance_redox.js
node 03_generator_agent/solvers/chemistry/reactions/tests/browser_acceptance_solubility_ksp.js
```

## 求解器契约与第一层自检

每个求解器除了返回业务结果，还必须能回答“这个结果自己是否自洽”。统一入口：

```python
from solver_contract import audit
report = audit("solveBuoyancy", request, result)
# {"ok": True/False, "api": "...", "failures": [...]}
```

- 自检实现按学科放在 `physics_audits.py` / `math_audits.py` / `geometry_audits.py`，
  用 `@register("solveXxx")` 注册；未注册的 API 退化为“只查有限数值”的通用自检。
- 自检只验证**同一结果内部**必须成立的恒等式（滑轮组：拉力×拉绳长=输入功；
  功与功率：F∥·s=W；统计：Σ(x−x̄)=0），不重复求解过程。
- 页面端 `VIS.bindSolverReadouts(result)` 是总闸：`checks.ok === false` 或出现
  NaN / Infinity 时，读数全部清空并显示错误，不得把坏数据当实验现象。
- 审查端 `reviewer.py` 在独立复算后调用同一个 `audit()`，自检不过直接判 J3 失败。

两条守卫测试（改求解器后必须跑）：

```powershell
py -B -m unittest discover -s 03_generator_agent/tests -p test_solver_contract.py -v
py -B -m unittest discover -s 03_generator_agent/tests -p test_solver_js_parity.py -v
```

第一条保证每个教学模型都有专用自检、所有验收 case 通过、变形关系引用的字段真实存在；
第二条用 Node 直接加载 `frame/phys.js` / `frame/math.js`，把所有 case 与 Python 参考实现逐字段对拍，
不需要浏览器就能发现两套实现的漂移。

新增一个求解器的顺序：写 Python 参考实现 → 写页面端 JS → 注册自检 →
把 case 加进 `lesson_models.json` → 跑上面两条测试。
