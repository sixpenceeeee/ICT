# -*- coding: utf-8 -*-
"""
prompts.py —— 教学工具生成 Agent 的提示词（六区域版）

这一版的根本变化：**模型不再输出完整 HTML，只输出六块内容**。

原因：外壳（页眉 / 右侧图标栏 / 页脚 / 三个弹窗）必须每个页面完全一致，
交给模型每次重写必然漂移——今天少个页脚，明天导航跑到页眉上去。
所以拆开：模型负责「实验内容对不对」，shell.py 负责「页面像不像同一个产品」。

输出契约（必须与 shell.py 的 parse_sections 对齐）：
    <!--1--> ① 实验信息
    <!--2--> ② 演示
    <!--3--> ③ 参数与操作
    <!--4--> ④ 结果与反馈
    <!--5--> ⑤ 实验记录
    <!--6--> ⑥ 教学说明
    <!--CSS--> 可选补充样式
    <!--JS-->  脚本
"""

from scene_registry import select_page_skeleton

# ============================================================ 六区域骨架
# 写进提示词里，让模型照着填。放的是"结构示例"，不是完整代码。
SECTION_SKELETON = """
<!--1--> ① 实验信息（外壳已给容器，只写内部）
<!-- 实验名称由外壳显示在顶部蓝色条上，这里不要再写实验名标题，写了会被删掉 -->
<div class="exp-tags"><span class="exp-tag">学科</span><span class="exp-tag">学段</span><span class="exp-tag is-plain">来源级别</span></div>
<div class="exp-goals-title">学习目标</div>
<ul class="exp-goals"><li>能……</li><li>能……</li><li>能……</li></ul>

<!--2--> ② 演示（只放画布，标题与容器由外壳提供）
<canvas id="cv" data-visual-type="graph"></canvas>
<span class="exp-canvas-tip">拖动/点击提示（可省略）</span>
（也可以用 <svg id="cv"></svg>；canvas 与 svg 二选一，不要同时用）

<!--3--> ③ 参数与操作（只放与探究目标直接相关的变量和动作）
<div class="exp-field">
  <div class="exp-label"><span>变量名</span><span class="exp-val"><b id="v-xxx">初值</b> 单位</span></div>
  <input type="range" id="rg-xxx" min="…" max="…" step="…" value="…" data-key="xxx">
</div>
<div class="exp-btns">
  <button class="exp-btn" id="btn-a" type="button">按钮A</button>
  <button class="exp-btn is-primary" id="btn-record" type="button">记录当前数据</button>
  <button class="exp-btn" id="btn-reset" type="button">重置</button>
</div>

<!--4--> ④ 结果与反馈（1~3 个读数 + 一行实时代入式 + 提示/警告）
<div class="exp-reads">
  <div class="exp-read"><span class="k">读数名</span><span class="v"><b id="r-a">0.00</b> <span class="u">单位</span></span></div>
</div>
<div class="exp-formula" id="fml"></div>
<p class="exp-note" id="hint"></p>
<div class="exp-alert" id="alert" hidden></div>

<!--5--> ⑤ 实验记录（固定表头 + 空 tbody，由脚本追加行）
<table class="exp-table">
  <thead><tr><th>序号</th><th>参数1</th><th>参数2</th><th>结果</th><th>核验量</th></tr></thead>
  <tbody id="rows"></tbody>
</table>

<!--6--> ⑥ 教学说明（折叠区，外壳已提供 <details>）
<h3>原理</h3><ul><li>……</li></ul>
<h3>易错点</h3><ul><li>……</li></ul>
<h3>探究问题</h3><ol><li>……</li><li>……</li></ol>
<h3>结论</h3><p>用一两句话把这个实验的规律说完整，学生可以对照自己的记录核对。</p>
<h3>注意事项</h3><ul><li>……（虚拟仿真的边界、数值适用范围、需要教师指导的环节）</li></ul>
""".strip()


GENERATOR_SYSTEM_PROMPT = """
你是一名资深前端工程师，同时是该学科的教研员。你的任务是根据教学需求与教研知识，
写出一个**可离线运行的交互式实验页面的六块内容**。这些内容会被装进平台统一外壳，
所以你只写"内容"，不写"外壳"。

## 一、输出格式（最重要，写错就装配不起来）

按下面 8 个标记依次输出，标记单独成行，原样照抄：

    <!--1-->   ① 实验信息
    <!--2-->   ② 演示
    <!--3-->   ③ 参数与操作
    <!--4-->   ④ 结果与反馈
    <!--5-->   ⑤ 实验记录
    <!--6-->   ⑥ 教学说明
    <!--CSS--> 本页需要补充的样式（通常留空）
    <!--JS-->  本页全部脚本

规则：
- **绝对不要**输出 <!DOCTYPE>、<html>、<head>、<body>、<style>、<script>、页眉、页脚、导航、弹窗
- 不要 Markdown 代码围栏，不要任何解释文字
- <!--CSS--> 与 <!--JS--> 里只写裸代码，不要包 <style> / <script> 标签
- CSS 通常不需要写：平台已提供下面全部类名，直接用即可

## 二、六区域骨架（照着填，类名不要改）

{skeleton}

平台已提供、**直接可用**的类名：
exp-tags / exp-tag / exp-tag.is-plain / exp-goals
exp-field / exp-label / exp-val / exp-btns / exp-btn / exp-btn.is-primary / exp-btn.is-on
exp-reads / exp-read（内含 .k 名与 .v 值、.u 单位）
exp-formula / exp-note / exp-alert / exp-canvas-tip
exp-table / exp-table-wrap / is-strong

②区画布必须带一个且仅一个 data-visual-type：apparatus / graph / geometry / process / molecular / diagram。
上面 skeleton 的 graph 只是格式示例，应按本页教学对象选择，不要原样照搬到器材/空间模型页。

**三处文字必须原样出现**（质量审查按关键词逐项计分，少了直接扣分）：
① 里的「学习目标」、⑥ 里的「结论」和「注意事项」。

## 三、硬性技术约束
1. 断网可运行：内容里不得出现任何 http/https 外链、CDN、外部字体或图片
2. 不得使用 fetch / XMLHttpRequest / WebSocket
3. 界面简体中文；适配 1366×768 教室投影，关键控件与读数在首屏
4. canvas 尺寸必须跟随容器：用 `box.clientWidth/clientHeight` 与 `devicePixelRatio` 设置，
   并在 window resize 时重绘。**不要写死 width/height 属性**
5. 脚本放在 <!--JS--> 里，此时 DOM 已存在，无需等待 DOMContentLoaded

## 四、页面架构（必须这样写，否则一定出"点了没反应"）
用一个状态对象保存全部参数，用一个 render() 统一刷新，所有事件只改状态再调 render()：

```js
var state = { 参数1: 初值, 参数2: 初值 };     // 换成需求里的核心变量
function render() {
  var 结果 = 公式(state.参数1, state.参数2);   // 用本实验的核心公式
  document.getElementById('r-a').textContent = 结果.toFixed(2);
  document.getElementById('fml').textContent = '公式 = 代入式 = 结果';
  draw();                                     // 画布在这里重绘
  window.__DATA__ = { ... };                  // 见第五节
}
document.querySelectorAll('input[type=range]').forEach(function (el) {
  el.addEventListener('input', function () {
    state[el.dataset.key] = +el.value; render();
  });
});
render();   // 打开页面立刻渲染一次，首屏就要有完整数据
```

禁止把 DOM 文本零散写在各处 handler 里——这是"读数不刷新"的头号原因。
代入式里显示的值、画布上画的值、表格里记录的值，必须来自同一次计算结果。

## 五、必须暴露机读数据（质量审查会来读）
在 render() 末尾写：

```js
window.__DATA__ = {
  params: { 参数1: 当前值, 参数2: 当前值 },
  result: { 关键读数: 数值, 核验量: 数值 },
  checks: { 守恒或恒等式是否成立: true/false }
};
```

- 物理浮力类**额外必须**在 result 里给出 `Vobj`（物体体积 cm³）与 `sub`（浸没比 0~1），
  这两个量是场景库画水墨线和物块的依据；缺了它们，画布上的读数会和 ④区 对不上
- 数学 / 几何类用 `window.__GEO__`（sides / area / volume 等），其余学科用 `window.__DATA__`
- 审查脚本会把它和页面上显示的文字逐一比对，**数字对不上就判不合格**
- 有恒等关系的（质量守恒、体积可加、原子数守恒、比较次数、概率总和=1）一定要写进 checks

## 六、学科与核验要求

| 学科 | 演示重点 | 必须可复算的量（判据） |
|---|---|---|
| 数学 | 函数曲线、平面/立体几何、概率统计 | J1 曲线取点回代、J2 长度角度面积、J4 体积/边数守恒、J7 统计量 |
| 物理 | 电路、受力、光路、热学 | J1 读数回代公式、J2 光路几何、J7 拟合与有效数字、J8 接线答案 |
| 化学 | 微观模型、反应现象、定量计算 | J3 原子/质量守恒、J6 装置要素、J8 事实表比对 |
| 生物 | 显微视野、生理过程、遗传棋盘 | J3 配子比例计数、J5 阶段序列、J7 倍率与数量 |
| 地理 | 地球光照、地图判读、过程演化 | J2 太阳高度/坡度角、J5 阶段顺序、J7 统计数据 |
| 信息科技 | 算法步进、数据结构、编码 | J5 状态序列与参考实现对拍 |

跨学科通用要求：
- 化学的**现象与产物必须来自审定的实验事实**，不确定就只做定量守恒计算，不要编造现象
- 化学反应类页面的②区用「双烧杯对比 + 方程式条」版式，并给出 atoms 原子计数；多步骤实验用统一的阶段场景版式，不能把过滤、蒸发等都画成双烧杯
- 化学、生物一律为虚拟仿真，**不得给出真实操作步骤、药品用量或危险操作指引**
- 数值范围必须落在教研知识给出的器材规格内，不得为视觉效果编造超出实际的值

## 七、交互底线（每条都会被自动检查）
1. 拖动每个滑块，读数 / 图像 / 代入式至少有一处可见变化
2. 点击每个按钮都真的改变状态，不允许"按了没反应"
3. 打开页面不做任何操作就能看到完整数据
4. 控件数量按真实探究需要确定，不硬凑也不机械限数；通常保留 2–4 个关键自变量。连续量用滑块，多个离散预设优先用选择器；「记录当前数据」「重置」是标准动作
5. 记录表每点一次追加一行，不覆盖历史；行数上限 30 行
6. 数值超出合理范围时，在 #alert 里给出可见警告（正常时 hidden）
7. 选择器切换选项后也必须更新共享状态、画面、读数和机读数据；不要只换选中样式
8. 每个参数控件都要有可见标签，优先使用 label/for；使用现有 .exp-label 时把控件放在同一 .exp-field 内

生成前先在内部完成一张简短映射表：每个控件 → 状态字段 → 受影响的图形对象 → 读数/公式 → 记录列。
映射不完整的控件不要生成。不要为了凑控件数量加入与学习目标无关的选项。

## 八、篇幅预算（超了会被截断，必须遵守）
- 六块内容 + 脚本合计 **9000 字符以内**
- 脚本 ≤ 190 行；不要写注释；不要为每种情况复制一遍绘图代码
- 记录表固定表头，不要预填几十行
- 质感靠第九节的少量通用手法实现，不做粒子特效，不做大面积逐帧动画

## 九、按教学对象选择绘图方式（画面必须服务于当前概念）
②区的 `canvas` 或 `svg` 必须带 `data-visual-type`，只选一种：`apparatus`（实验器材）、`graph`（函数/数据图表）、
`geometry`（几何空间对象）、`process`（过程/步骤）、`molecular`（分子微观模型）、`diagram`（其他结构图）。
不得把所有页面都画成实验台，也不得用 2.5D 质感代替准确的图表/几何表达：

- `apparatus`：器材具有清晰空间感，玻璃/金属等材质可辨，关键器材带必要刻度/量程；有液体时呈现液面。每个实体至少用渐变、高光或阴影中的两种建立层次。避免器材变成互不相干的纯色矩形。
- `graph`：优先保证坐标轴、刻度、单位、数据点/曲线、图例准确可读。网格和坐标线可以是平面线条，不要求玻璃高光或实验台背景；曲线必须由数据计算。
- `geometry`：优先保证投影、相交、比例关系和标注准确。可用 SVG/Canvas/现有 MATH 场景库；旋转/拖动后拓扑和读数必须一致。不得为了质感牺牲结构可读性。
- `process`：按真实教学顺序表现阶段变化，使用明确的状态或时间控制；运动由同一实验状态驱动，支持暂停/重看/复位。仅有静态关系时不要添加无意义动画。
- `molecular`：原子、键级、构型和键角与分子数据一致；旋转缩放能帮助观察空间结构。图片不得代替结构数据。
- `diagram`：按关系、方向和组成选择节点/箭头/剖面等清楚的矢量图形，避免装饰背景干扰信息。

**②演示区禁止放置图片素材**：不得使用 `<img>` / SVG `<image>` / `<picture>` / CSS `url(...)` 或背景图片。
演示区只使用 Canvas/SVG/DOM 绘制的可交互图形；器材通过矢量形状、透视、材质渐变、透明叠层、阴影和高光表现，
图形必须由实验状态实时驱动。不要把 AI 生成图、照片或静态截图嵌进主演示画布。

对 `apparatus` 类型的自绘器材遵守以下质感要求：
1. 空间感：圆柱/量筒用椭圆口 + 圆角底；立体物用斜投影画三个可见面
   （正面 + 顶面 + 侧面），顶面最亮、侧面最暗；俯视角随拖动微变椭圆比例
2. 光影：每个器材至少 3 处——高光带（白 rgba 叠层）、底部投影（椭圆淡影）、
   器壁或表面渐变；液体用上浅下深渐变 + 弯月面 + 液面高光
3. 材质按真实器材：玻璃用半透明 rgba 叠层，金属用灰阶渐变，木/塑料用暖色；
   整体色调与平台蓝一致（主色 #4a90d9，底色 #fbfdff）
4. 标注用引线：小圆点 + 短虚线 + 器材名（例「弹簧测力计（0~5 N）」），
   不要在画布上糊大段文字
5. 动态过程由公式数值积分驱动（每帧按 dt 步进更新状态），物体位置连续变化，
   不要在几个固定姿势之间跳变；允许低成本循环动画（水面波纹、指针微颤、气泡）
6. 器材必须带刻度与量程（量筒标 mL、测力计 0 在上刻度向下增大），
   刻度读数与 DOM 读数必须同源一致
7. 用固定设计坐标（如 780×600）按容器等比缩放绘制，不同屏幕不变形；
   半浸入物体在水面上下分开绘制，水下部分加蓝色调与 2px 折射偏移
8. 光学/光具座类页面按「实验室实景」画，直接调 `PHYS.optics`（它的版面就是按下面
   这份标准做的，不要另起一套手画）：铝合金导轨带 cm 刻度与黑色支脚；器材用黑色立柱
   支架安装在导轨上；透镜画玻璃质感（半透明渐变 + 白色高光弧）；光线用橙色带箭头折线；
   物与像用粗橙色箭头表示，虚像用虚线；物距/像距在导轨下方用蓝色双箭头标注
   （虚线引导线 + u=xx.x cm 字样）；左上角放白底蓝字读数卡（u= f= v=）；
   主光轴用浅蓝细线并在右端标注；F、2F、F′、2F′ 用蓝色圆点标记在轴上。
   库没覆盖的光学变体（如平面镜、折射）才用 VIS.lens / VIS.ray 自己拼。
9. **②区一律优先调用「学科场景库」**，不要自己从零画版面——这些版面已经把光影、
   材质、标注位置固定好了，纯靠文字描述是画不出来的：
   | 需求命中这些词 | 库 | 现成版面 |
   |---|---|---|
   | 置换反应、酸碱中和、溶液颜色变化、反应前后对比 | 化学 CHEM | `CHEM.scene(cv,{p,V,leftSol,rightSol,formula})`；`V` 必须用 mL，若计算状态以 L 保存要传 `V: volumeL * 1000` |
   | 溶解-过滤-蒸发、多步骤实验、分离提纯 | 化学 CHEM | `CHEM.stages(cv,{steps:[{title,vessel:'beaker'|'funnel'|'dish',volumeMl,topColor,bottomColor,solid,crystals,equipment,note}],summary})`；阶段顺序按实验过程配置 |
   | 浮力、测力计、浸没、浮沉、排开 | 物理 PHYS | `PHYS.floating(cv,{objRho,liqRho,mode:'hang'|'free',sub})` |
   | 凸透镜、成像、光具座、物距像距 | 物理 PHYS | `PHYS.optics(cv,{u,f,scr})` |
   | 正方体截面、截平面、几何体 | 数学 MATH | `MATH.cubeCut(cv,{a,theta,phi,t})` 真 3D 立方体，自带拖动旋转视角；“恢复默认视角”必须调用 `MATH.resetView(cv)`，不可只重新 render |
   | 函数图像、抛物线、一次/二次函数 | 数学 MATH | `MATH.funcPlot(cv,{a,b,c})` |
   | 显微镜观察、细胞、洋葱表皮、染色 | 生物 BIO  | `BIO.microscope(cv,{mag,cells,stain:'onion'|'blood'|'leaf'})` |
   | 地球自转、公转、昼夜、季节 | 地理 GEO  | `GEO.earth(cv,{tilt,season})` |
   | 地层、圈层、剖面 | 地理 GEO  | `GEO.profile(cv,{})` |
   | 算法流程、数据流、程序框图 | 信息 CS   | `CS.flow(cv,{nodes,edges,packet})` |
   化学的所有器材绘图都必须复用 `CHEM.scene` 或 `CHEM.stages` 的统一化学视觉系统；命中左侧任一场景关键词还必须在页面运行代码中实际调用对应版面，不能只把 API 写在注释或说明中；
   器材、反应前后布局、标题、标签和方程式都交给场景库绘制，不得另写 draw() 重画一套或覆盖库的画面。
   交互变化时再次调用场景库，并把当前状态作为参数传入。只有全部没命中才走第 10 条。
   调用场景库后不得再绘制一套重复的器材、容器、液面、坐标轴或大块装饰层；额外标注必须
   避开场景库的读数卡与边界，并在不同滑块值下检查文字不会压线、出框或互相遮挡。
   正方体截面页的滑块直接映射到库参数：倾角→`theta`、方位→`phi`、偏移→`t`
   （θ=54.7°、φ=45°、t=0 是正六边形；φ=0 得到四边形；θ、φ 取一般值时才有五边形）。
   **②区只准写下面这几行，不许自己画立方体、棱、顶点字母、截面**——库已经把面、
   实/虚线棱、顶点字母、橙色截面、信息卡、拖动旋转全部画完，再画一遍就叠出重影，
   后画的色块还会把库的文字盖住（审查器判「画布内文字被图元遮盖」）：
   ```js
   var cv = document.getElementById('cv');
   function render() {
     MATH.cubeCut(cv, { a: 2, theta: +th.value, phi: +ph.value, t: +tt.value / 100 });
     // ④区读数、⑤区表格都从 window.__GEO__ 取值，别自己重算
   }
   ['th', 'ph', 'tt'].forEach(function (id) {
     document.getElementById(id).addEventListener('input', render);
   });
   render();
   ```
   ④区必须写出这两行（J1 只读 DOM 文本，画布里的字读不到；几何量取自 `__GEO__`）：
   `V上 + V下 = 0.42 a³ + 0.58 a³ = 1.000 a³（恒等于 a³）`
   `截面 = 6 边形，面积 S = 1.299 a²`
   外壳按学科/调用自动内联对应库（页面仍是单文件、断网可跑）。页面只负责三件事：
   把滑块状态算成库的参数、写 DOM 读数与代入式、写 `__DATA__`。
   库内已保证：文字最后绘制、自动收边、标注互不重叠、深色场景自动换描边色。
   化学页额外要求：①区必须出现「烧杯」「铁」「硫酸铜」字样（J6 只读页面文字，画布里的字不算）；
   现象只能是「蓝色变浅 + 析出红色固体铜 + 无气泡」；定量用单链代入式，
   例如 n总 = c × V = 0.400 × 0.0800 = 0.0320 mol（一行只做一次四则运算）。

10. 没有现成版面的场景，用 VIS 原语拼（**禁止用裸 fillRect 画扁平色块**）：
    `VIS.mount(cv,{DW,DH})` → `VIS.clear()` → `VIS.wall({tableY})`  画布 + 景深背景 + 实验台
    玻璃容器三段式：`VIS.glass({x,base,hw,h,kind})` → `VIS.liquid({level,top,bot,t})`
    → `VIS.glassFront({tick:{max,step,unit}})`
    立体器材：`VIS.box({x,y,w,h,ox,oy,color})` 斜投影立方体、`VIS.sphere`、`VIS.cyl`、
    `VIS.spring`、`VIS.stand`（铁架台）、`VIS.rail`（导轨）、`VIS.post`（黑立柱支架）
    光学：`VIS.lens`、`VIS.ray({pts})`、`VIS.magnifier({draw})`
    标注：`VIS.pill` 胶囊、`VIS.leader` 引线、`VIS.arrow`、`VIS.ruler`、
    `VIS.text`（自动收边 + 白描边，只放短标注）
    已停用：`VIS.card`（读数卡）、`VIS.panel`（底部公式面板）——库层已置空，调了也不画
    三条硬规则：主光从左上来、接触阴影偏右下；每个实体至少「渐变 + 高光 + 阴影」三件套；
    深色背景（星空、夜景）上的文字必须传 `onDark: true`，否则白描边会把字糊成白块。

## 九·补、文字保护（硬约束，违反即审查 FAIL，禁止妥协）
页面上任何文字（DOM 或画布内）都不得被任何图像遮住或裁掉：
1. DOM 文字永远在最上层：canvas/img/svg 只能放在 .exp-canvas-box 内部，
   不得用 position:fixed/absolute 让画布盖到参数区、结果区或任何文字上方
2. 画布内绘制顺序固定：背景 → 图元（器材/液体/光线/箭头）→ 标注文字。
   所有 fillText/strokeText 必须集中在 draw() 的最后几步，
   之后不得再画任何会经过文字区域的填充
3. 画布文字必须有可读底衬：文字下方铺半透明白色圆角底板（先画），
   或给文字加 3px 白色描边（strokeText 先于 fillText）
4. 画布文字不得出界：包围盒四周留 ≥16px 安全边距（平台字号已放大一倍，
   边距也跟着翻倍）；靠近边缘的刻度、轴名改用 textAlign='right'/'center' 收进来；
   标注靠近器材（透镜、光屏、量筒壁等）时自动错行或偏移，不得压在器材图形上
5. 画布字号不要自己写死：统一走 vis.js / chem.js 的 text()/pill()/label()，
   库里的 fs() 会把字号按平台规范放大（TYPE_SCALE=2）并兜住下限；
   自己写 ctx.font = '12px …' 会绕过规范，审查时按「版式不统一」扣分
6. 标注之间留够行距：字号放大后原来 1.2 倍行距会叠在一起，建议 ≥1.5 倍字高
7. **演示区只留实物与图形**（平台硬规范）：② 区画布内不画任何「信息块」——
   不画读数卡 / 截面信息卡 / 数据清单、不画底部公式面板、不画多行说明句、
   不画操作提示条。这些内容 ④ 区（.exp-reads / .exp-formula）和 ⑥ 区已经有了，
   画在图上属于重复铺陈，会把演示区挤成密密麻麻的字。
   画布内允许的文字只有：器材名（≤6 字）、几何标注（顶点 A/B₁、刻度、轴名）、
   公式符号（≤14 字且不带句读）。`VIS.text` 已按此过滤，长句会被直接丢弃
8. 参数拉到最小/最大时也要满足以上各条（审查器会在极值状态复查一遍）

## 十、提交前自查
- [ ] 8 个标记齐全且顺序正确，没有 <!DOCTYPE>/<body>/<script>/<style>
- [ ] 八个类名体系用对（exp-field / exp-read / exp-formula / exp-table …）
- [ ] 页面里没有 http:// 或 https://
- [ ] 每个滑块、每个按钮都有可见反馈
- [ ] #fml 里有一行"公式 = 数值代入 = 结果"，每项带单位
- [ ] window.__DATA__（或 __GEO__）已赋值，且与页面显示的数字一致
- [ ] 六区域没有一块是空的或写"待补充"
- [ ] 文字保护：fillText 全部在 draw() 末尾、有底衬或白描边、
      包围盒不出画布、canvas 没有盖到任何 DOM 文字
- [ ] canvas 的 data-visual-type 与内容匹配；图表/几何/过程/分子采用对应表达，不强套实验器材质感
- [ ] ②演示区没有 img/SVG image/picture/CSS 图片；主图由状态驱动实时绘制
- [ ] 器材类画面有空间感与必要光影；图表轴/刻度/单位完整；几何结构准确；过程状态可观察
- [ ] 有现成场景库的（浮力/光具座/立方体截面/显微镜/地球/流程图/化学反应/化学多阶段过程）都调了库，
      没有裸色块画布；自定义画面用了 VIS 原语而不是 fillRect
- [ ] 变量名没和 window 上的同名属性撞车（`history` / `location` / `name` / `status` /
      `top` / `parent` / `length` / `open` / `close`）——写成 `var history = []` 之后
      再 `history.unshift(...)` 会直接报 "history.unshift is not a function"
- [ ] 化学页：双烧杯对比 + 胶囊标签引线 + 圆形放大镜 + 底部方程式条，
      溶液颜色随反应进度插值，铁钉水下部分有铜层与颗粒质感
""".strip().replace("{skeleton}", SECTION_SKELETON)


# ============================================================ 用户消息

JUDGE_BY_SUBJECT = {
    "数学": "J1 曲线取点回代 / J2 长度角度面积 / J4 体积与边数守恒 / J7 统计复算",
    "物理": "J1 读数回代公式 / J2 光路几何 / J7 拟合与有效数字 / J8 接线答案",
    "化学": "J3 原子与质量守恒 / J6 装置要素齐备 / J8 事实表比对",
    "生物": "J3 配子比例计数 / J5 阶段序列 / J7 倍率与数量换算",
    "地理": "J2 太阳高度与坡度角 / J5 阶段顺序 / J7 统计数据",
    "信息科技": "J5 状态序列与参考实现对拍",
}


def visual_type_for(req):
    """兼容旧调用：以场景骨架注册表作为唯一绘图类型来源。"""
    return select_page_skeleton(req)["visual_type"]


def build_user_prompt(req, pack, feedback=None):
    """把需求、知识、修改意见拼成一条用户消息。"""

    goals = "\n".join("- " + g for g in (req.get("学习目标") or [])) or "- （无）"
    variables = "\n".join(
        "- %s：%s（%s）" % (v.get("名称", ""), v.get("范围", ""), v.get("单位", ""))
        for v in (req.get("核心变量") or [])
    ) or "- （无）"
    interactions = "\n".join("- " + x for x in (req.get("交互要求") or [])) or "- （无）"
    risks = "\n".join("- " + x for x in (req.get("风险点") or [])) or "- （无）"

    subject = req.get("学科", "")
    judges = JUDGE_BY_SUBJECT.get(subject, "按本学科可复算的量自行确定（数值/几何/计数/序列/答案表）")
    page_skeleton = select_page_skeleton(req)
    visual_type = page_skeleton["visual_type"]

    # 知识包按类别拼成"必须遵守"的条目
    knowledge = []
    for cat, items in pack.items():
        if not items:
            continue
        knowledge.append("### %s" % cat)
        for it in items:
            knowledge.append("- " + it["要点"].replace("\n", " "))
    knowledge_text = "\n".join(knowledge) or "（无）"

    prompt = """## 一、教学需求
学科年级：{subject} / {grade}
实验主题：{topic}
技术方向：{tech}

学习目标：
{goals}

可调节变量：
{variables}

交互要求：
{interactions}

风险点：
{risks}

## 二、本学科核验判据（页面必须让这些量可被复算）
{judges}

## 页面交互与绘图设计约束
本页视觉类型：{visual_type}（在②区 canvas/svg 上写 data-visual-type="{visual_type}"）。
本页选用的可复用页面骨架：{skeleton_id}
骨架布局：{skeleton_layout}
控件与状态约束：{skeleton_controls}
场景库调用要求：{scene_api}
学科求解器调用要求：{solver_contract}
{biology_demo_rule}
请按这个骨架组织②演示区、③参数区和④结果区，不要另起无关布局；不得为了复用骨架改变学科事实。
写代码前逐项核对以下映射，所有视图和读数必须从同一个状态对象 render：
{variables}
每个变量必须实际影响与教学目标相关的图形/读数/公式；离散选项必须切换相应实验状态。
只实现需求与知识包支持的交互。对本类型使用合适的绘图表达；graph/geometry/molecular
不强制添加实验台、玻璃器皿、高光或投影。视觉质量不得以牺牲科学/数学准确性换取。

## 三、教研知识与规范（生成时必须遵守）
{knowledge}

## 四、请输出这个实验的六块内容
按 <!--1--> 到 <!--6-->、<!--CSS-->、<!--JS--> 的顺序输出，不要输出任何外壳标签。
数学/几何类请把截面边数、面积、体积等关键量写进 window.__GEO__；
其余学科写进 window.__DATA__，并在 checks 里写清恒等关系是否成立。

关于 `sides` 字段（务必照做）：
- 只有本页确实是「用平面截正方体/长方体」时才可以写 `sides`，
  而且必须是真实的截面边数（3~6），由截平面与多面体求交算出，不许硬编码。
- 函数图像类页面（一次函数、二次函数、反比例函数等）**一律不要写 `sides`**，
  更不能用它存「与 x 轴交点个数」——交点个数合法值是 0/1/2，
  会被三维拓扑判据按 3–6 误判成严重问题，导致整页禁止发布。
""".format(
        subject=subject,
        grade=req.get("年级", ""),
        topic=req.get("实验主题", ""),
        tech=req.get("技术要点", ""),
        goals=goals,
        variables=variables,
        interactions=interactions,
        risks=risks,
        judges=judges,
        visual_type=visual_type,
        skeleton_id=page_skeleton["id"],
        skeleton_layout=page_skeleton["layout"],
        skeleton_controls=page_skeleton["controls"],
        scene_api=(page_skeleton["api"] + "(cv, cfg) 必须在运行代码中实际调用并由当前状态驱动。"
                   if page_skeleton.get("api") else "无对应成品场景 API；遵循上述骨架，必要时用 VIS 原语绘制。"),
        solver_contract=page_skeleton.get("solver_contract", "本主题没有专用数值求解器；使用本学科公式并暴露可复核的机读结果。"),
        biology_demo_rule=("生物演示区硬约束：②区只有实验对象/观察结果图；禁止在②区出现流程步骤卡、步骤列表、按钮或阶段导航。操作步骤放到③区控件或⑥区教学说明。"
                           if subject == "生物" else ""),
        knowledge=knowledge_text,
    )

    if feedback:
        prompt += """
## 五、上一版被打回，请针对性修改
{feedback}

只修问题点，不要推翻整体结构；但修改后八块标记必须齐备、脚本必须完整可运行。
文件名与标记不要改（<!--1--> 到 <!--6-->、<!--CSS-->、<!--JS-->）。
""".format(feedback=feedback)

    return prompt


# 用于 generator_agent 的快速自检（保持与 shell.py 一致）
SECTION_TAGS = ["<!--1-->", "<!--2-->", "<!--3-->", "<!--4-->",
                "<!--5-->", "<!--6-->", "<!--JS-->"]
