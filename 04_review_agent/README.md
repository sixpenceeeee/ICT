# 质量审查 Agent（按《界面设计+审查判据》V1.0 重构）

回答三个不同的问题，别混在一起：

| 问题 | 字段 | 谁看 |
|---|---|---|
| 客观复算过没过？ | `总分` / `结论` | 流水线（决定是否返工） |
| 能不能上线？ | `发布状态` | 平台（可发布 / 待教师审核 / 禁止发布） |
| 哪一条错、错在哪？ | `检查项[].expected / actual / evidence` | 教研老师与生成 Agent |

## 一、五关流水线（规范 3.4）

```
第1关 结构与安全   文档骨架 / 外链 / 网络请求 / 密钥 / 动态执行 / 引擎白名单 / 参数范围
第2关 资源完整性   六区域齐备且非空 / 外壳资源 / 画布 / 控件数 / 记录表 / 重置 / CSV / 首屏数据
第3关 学科判据     J1–J8，由 judges.py 独立重算（不信页面自报）
第4关 浏览器测试   加载 / JS 报错 / 拖滑块和下拉选项 / 点按钮 / 重置 / 单步 / 记录追加 / 绘图适配 / 版式 / 窄屏溢出与控件标签
第5关 教学审核     学习目标 / 教学说明 / 虚拟仿真声明 / 实验性质 / 教师复核状态
```

判定只有四种状态：

| 状态 | 含义 | 是否计分 |
|---|---|---|
| `pass` | 独立复算通过 | 计入分子 |
| `fail` | 独立复算失败，附 expected/actual/evidence | 计入分母 |
| `review` | 无客观标准或事实表未复核 → 交教师 | **不计分** |
| `skip` | 本页没有这类内容，不适用 | **不计分** |

`skip` 不给分是有意的：**"不适用"不等于"通过"**，否则缺几何量的页面会白拿几何分。

数学“平面截正方体/长方体/三棱柱/正四棱锥”还会触发 G4-14：浏览器采集初始和交互后的截面顶点、边数、面积及 `__GEO__`，再由对应的 Python 适配器独立复算；未暴露求解结果、图形与求解结果不一致或独立复算失败都会判为严重不通过。

## 二、目录

```
04_review_agent/
├── reviewer.py            五关编排 + 打分 + 报告（主程序）
├── registry.py            25 类引擎白名单、场景注册表、J1–J8 定义、六区域定义
├── judges.py              J1–J8 的独立算法实现
├── facts.json             J8 用的教师事实表（含审核状态）
├── checks_browser.js      第4关取证：六区域、__DATA__/__GEO__、滑块/选择器响应、重置、单步、记录、离线请求、绘图和视口布局
├── tests/broken_example.html   反例：引 CDN、fetch、滑块不绑事件、220 V
└── output/审查报告_xxx.json     结构化报告
```

## 三、跑起来

```bash
cd 04_review_agent
python reviewer.py --html ../deliver/平面截正方体/平面截正方体.html
python reviewer.py --html ../deliver/平面截正方体/平面截正方体.html --quiet   # 只输出修改意见
python reviewer.py --html tests/broken_example.html                          # 看它怎么抓错
python reviewer.py --html xxx.html --no-browser                             # 没装 playwright 时降级
```

## 四、J1–J8 各自怎么判（关键：独立性）

| 判据 | 审查器独立算什么 | 需要页面暴露什么 | 没有数据时 |
|---|---|---|---|
| J1 数值复算 | 解析代入式，按四则运算重算；检查极值、单位、除零、值域 | 首屏一行代入式 + 滑块 | 无代入式 → fail |
| J2 几何复算 | 内角和、反射角=入射角、两点距离、太阳高度角 | `__GEO__` 或页面角度文本 | skip |
| J3 计数守恒 | 左右原子数；反应计量的进度、限量试剂、剩余/生成量；溶液混合的 n=cV 换算；强酸强碱滴定的 pH、当量点及单位变形；气体制取的 PV=nRT 与水蒸气压修正；沉淀反应的模板识别、沉淀质量、净离子方程式和限量比例临界点变形；氧化还原的酸/碱介质切换、离子方程、氧化数与电子守恒及真实物种换序；溶解平衡的 Ksp 质量作用、共同离子效应及 Q/Ksp 临界三态 | `__DATA__`；化学页暴露 `__CHEM_BALANCE_*` / `__CHEM_STOICH_*` / `__CHEM_MIX_*` / `__CHEM_TITRATION_*` / `__CHEM_GAS_*` / `__CHEM_PRECIP_*` / `__CHEM_REDOX_*` / `__CHEM_KSP_*` 请求、结果和实际可见控件/读数 | skip（主题不适用时） |
| J4 空间拓扑 | 体积可加、截面边数 3–6、欧拉公式 V−E+F=2、顶点共面 | `__GEO__.v_up/v_down/sides/V/E/F` | skip |
| J5 序列状态 | 单步不重复、末态有序、与**独立写的**冒泡参考实现逐步对拍 | `__DATA__.steps` + 单步按钮 | skip |
| J6 要素齐备 | 场景注册表里的 required 清单逐项在页面文本中查找 | 场景 `scene_id` | 未注册 → review |
| J7 统计复算 | 从表格/样本独立算均值、方差，与页面显示值比对 | `__DATA__.samples/result` 或数据表 | skip |
| J8 事实比对 | 与 `facts.json` 的「必须出现 / 至少出现 / 禁止出现」逐条比对 | — | 未命中 → review |

规范 3.2 的第 1 条是这套设计的底线：**同一个模型生成完再让它自己说对不对，不算校验**。
所以页面写在 `__DATA__.checks` 里的 `守恒: true` 只记为 `review`，绝不当证据。

## 五、判分与结论

五关各自有满分，关内按权重算比例：

| 关 | 满分 |
|---|---|
| 结构与安全 | 25 |
| 资源完整性 | 25 |
| 学科判据 | 25 |
| 浏览器测试 | 15 |
| 教学审核 | 10 |

```
有"严重"级 fail        → 不通过      （一票否决，不看分数）
总分 < 60               → 不通过
60 ≤ 总分 < 80          → 需修改
总分 ≥ 80               → 通过
```

`发布状态` 单独看：有任何 `review` 就是**待教师审核**，不管分数多高。
这条对应规范 3.4 的"只有关键检查通过且学科审核状态符合发布规则时，才允许作为正式资源发布"。

## 六、实测

| 页面 | 结果 | 抓到了什么 |
|---|---|---|
| `deliver/平面截正方体` | 100.0 · 通过 · 待教师审核 | 客观项全过；4 条 review（innerHTML、CSV、实验性质、教师复核） |
| 电路兜底页 | 93.1 · 通过 · 待教师审核 | J6 缺"电源/电流表/电压表"——兜底页是通用 y=kx 演示，不是真电路 |
| `tests/broken_example.html` | 40.8 · 不通过 · 禁止发布 | 外链 2 个、fetch、运行时联网、220 V、六区域全缺、无画布、无重置、无代入式 |

反例那份被拦住不是因为分数低，而是因为**每一条都有证据**：
`actual` 写着"捕获 1 个外部请求：https://cdn.jsdelivr.net/…"，老师可以直接核对。

## 七、闭环：审查打回 → 自动返工

```bash
python ../04_review_agent/reviewer.py --quiet > feedback.txt
cd ../03_generator_agent && python generator_agent.py --feedback "$(cat feedback.txt)"
```

`修改意见` 里每条都带「应为 / 实际」，生成 Agent 不用猜。

## 八、答辩时要说清的三件事

1. **25 类是规划分类，不是 25 套已实现引擎**（规范第五节）。`registry.PROTOTYPE_MAP`
   记录旧原型名到规划引擎的映射，映射不等于功能已补齐。
2. **J6 没有场景注册表就只会给 review**。这是有意的——不知道"该有哪些器材"时，
   宁可交给人，也不凭空判合格。
3. **J8 的覆盖面等于事实表的大小**。现在 `facts.json` 有 20 条六学科教材事实，
   加学科要加事实；没有事实就用 J1–J7 的复算兜底。

## 八·补、文字与场景显示检查（G2-10 至 G2-16）

用户要求「所有生成出的 HTML 中的文字不可以被任何图像遮住」，落成三条检查：

| 编号 | 查什么 | 怎么查 |
|---|---|---|
| G2-10 | DOM 文字被 canvas/img/svg 压住 | 每段可见文字取 5 个采样点，`elementsFromPoint` 看最上层是不是图形元素（桌面 + 移动端两个视口） |
| G2-11 | 画布内文字被后绘制的图元盖住 | 注入 hook 记录 `fillText/fill/fillRect`；后绘制的填充盖住文字 ≥35% 即 fail。累积最近 12 帧 |
| G2-12 | 画布内文字超出画布被裁切 | 同上，文字包围盒出画布即严重 fail |
| G2-13 | 画布文字与边框/文字冲突 | 记录 `strokeRect` 的边缘带，检查文字撞边框及不同文字框重叠；发现冲突即严重 fail |
| G2-14 | 演示区不嵌入图片素材 | 检查 `sec-stage` 的图片节点、CSS `url()`，浏览器再检查计算后的背景图 |
| G2-15 | 演示文字无对象占位符 | 检查 Canvas/DOM 中的 `[object Object]` 等默认对象字符串；发现即严重 fail |
| G2-16 | 化学场景液量可见 | 检查 `CHEM.scene` 实际采用的 mL 液量与液面比例；接近空杯或溢出即严重 fail |

取证不需要页面配合（`addInitScript` 注入），坐标已换算 `getTransform()`，
页面用 `ctx.scale` 做设计坐标缩放不会误报。

自测反例：`tests/text_overlap_example.html`——canvas 绝对定位盖住 DOM 文字、
先写字再画矩形盖住、文字画出右边界，三条全部精确命中。

排查工具（独立运行，不用走完整审查）：
`node ../tools/check_text_overlap.js <页面.html>`（DOM 层）、
`node ../tools/canvas_text_audit.js <页面.html>`（画布层）。

## 八·补二、版式统一检查（G4-09）

用户要求「生成的每张静态网页都必须长得一样」，落成一条检查 `G4-09 版式统一`，
量的是三条**平台外壳级**规范（实现见 `frame/UI规范.md`）：

| 三项规范 | 判 pass 的条件 | 取证字段（`result.typography`） |
|---|---|---|
| 蓝色条只放实验名字 | 页眉标题 ≤18 字 | `titleLen` / `title` |
| 蓝条下方不再重复实验名 | ①区不存在 `.exp-name` 节点 | `hasName` |
| 正文统一黑色 + 最小字号 | `minFs ≥ --pf-fs-min` 且非黑正文 0 处 | `fsMin` / `minFs` / `small` / `colored` |

四项任一不满足即 `fail`（MAJOR，权重 2），`advice` 直接指向修法：
走 `shell.py` 装配拿到 `normal.css` / `typo.js`，标题传「实验名字」而不是整句主题。

取证在 `checks_browser.js` 的 `page.evaluate` 里完成，不需要页面配合：

- 字号：遍历正文文字节点读 `computedStyle.fontSize`，统计低于门槛的处数与最小值。
  门槛**不写死**，从页面的 `--pf-fs-min` 变量读（当前 26px，即最初 13px 的 2 倍）；
- 颜色：读 `color`，跳过纯黑/近黑，再向上找祖先底色算亮度，
  **深底白字不动**（按钮、深色胶囊上的字天然是白的）；
- 重复名字：查 `.exp-name` 是否还挂在 ①区。

正反对照：化学置换新页 100 分 → G4-09 pass；旧的平面截正方体页 88.9 分 → G4-09 抓到
「标题 28 字 / ①区重复名称 / 11.5px / 64 处非黑」四项。历史页面用
`python ../tools/reshell.py deliver/xxx/xxx.html` 原地升级（幂等，`--dry-run` 只预览）。

独立体检工具：`node ../tools/ui_audit.js <页面.html> [--shot]` —— 只量这三条，不跑完整审查。

## 九、已知局限

1. 不判断教学法优劣（交互设计对学生是否有帮助，需教师或另配评审节点）。
2. 公式校验依赖页面把代入过程写出来，只显示结果会判 fail——这是刻意的。
3. 3D 拓扑只校验体积可加、边数、欧拉公式与共面四项，复杂曲面不覆盖。
4. 单步序列的参考实现对拍目前只内置冒泡排序；二分查找、递归需补 `judges._bubble_ref` 同类参考实现。
5. 规范 4.2 的引擎统一接口（`init/setParams/step/getState/getResults/reset/validate`）**没有强制检查**：
   现有原型还没按这套接口实现，硬性要求会把所有页面判死。等引擎重构完成后再加一条 G1 检查。
6. 无浏览器环境下（`--no-browser`）分数会偏高，所以发布状态强制为「待验证」，不进可发布。
7. 画布文字的「底衬对比度」暂不量化（只查遮挡与裁切）；文字压在复杂背景上的
   可读性仍靠 G2-11 的底衬要求 + 人工复核兜底。

## 十、优质页面标准接入

本地新增的 G4 检查项：

| 编号 | 检查 | 判定方式 |
|---|---|---|
| G4-08 | 绘图方式适配教学对象 | `apparatus` 检查器材的材质/层次；图表、几何、过程、分子和其他结构图转教师复核，不拿 2.5D 填充比例误判 |
| G4-10 | 离散选项切换有效 | 切换每个 `<select>` 的备选项，确认机读状态或可见画面发生变化，再恢复原选项 |
| G4-11 | 窄屏布局与控件标签 | 在桌面和 390px 视口量页面横向溢出，并检查参数控件是否有 label/ARIA/字段标签 |
| G4-12 | 旋转视角可恢复 | 对画布执行真实拖动旋转，再点“恢复默认视角”，比较旋转前后的 yaw/pitch；恢复按钮无效即严重 fail |

滑块和按钮的响应指纹现在包含页面文字、机读状态和 Canvas 像素采样，因而只有画面变化的交互也能被识别。
生成器会要求并校验 `data-visual-type`，避免把所有学科的图都按实验器材的 2.5D 材质阈值打分。
完整的教学交互、绘图、发布阻断与人工复核口径见根目录 [优质页面标准.md](../优质页面标准.md)。

## 十一、关系级变形测试（mr_catalog.py + mr_engine.py）

### 为什么加这一层

旧版第 4 关能证明“拖了滑块，值变了”（响应性），但证明不了“按什么规律变”。
把像距写死成 15 cm 的页面，只要标签跟着动，也能通过响应性检查。
这一层把“变形关系”做成可执行、可复算、可报告的独立判定。

### 两个文件

| 文件 | 职责 |
|---|---|
| `mr_catalog.py` | 数据层：每个求解器场景测哪些关系、控件选择器、baseline/transformed 两组值、适用条件 |
| `mr_engine.py` | 判定层：比例/反比/常量/相等/变化/公式，容差策略，计划执行，覆盖统计 |

关系类型：`linearity`、`inverse`、`invariance`、`conservation`、`boundary`、`formula`、`readout`。

### 执行链路

```
run_review()
  → expected_solver_api_for_page() 预判求解器
  → mr_engine.build_plan(api) 生成计划
  → checks_browser.js 按计划设置控件，在 baseline / transformed 各采一次快照
  → mr_engine.evaluate_page() 判定关系
  → 第4关 G4-40（关系级） / G4-41（计划可执行） + 报告 "变形测试" 字段
```

快照包含：控件值、可见读数（`circuit:current` / `field:*` / `label:*`）、
机读全局量（`__*_REQUEST__` / `__*_RESULT__`）。

### 容差

- 状态量：相对误差 `1e-6`（求解结果之间对拍）。
- 页面读数：按**文本显示位数**反推，`0.5 × 最后一位 × 1.01`。
  例如 `0.001 A` 显示成 `0.001006 A` 会被抓住；旧版 `max(0.005, 2%)` 会放过。
- 比例关系默认相对容差 2%，可在场景的 `tolerance` 里覆盖。

### 新增一个场景

在 `mr_catalog.PAGE_PLANS` 里加一条：

```python
"CIRCUIT.solve": {
    "solver": "CIRCUIT.solve",
    "scenes": [{
        "id": "circuit.voltage-proportional",
        "title": "电压翻倍，电流翻倍（电阻不变）",
        "kind": "linearity",
        "controls": {"voltage": _control(CIRCUIT_VOLTAGE, 3, 6),
                     "resistance": _control(CIRCUIT_RESISTANCE, 10, 10)},
        "relation": {"op": "proportional", "x": "control:voltage", "y": "circuit:current"},
        "tolerance": {"rel": 0.02, "abs": 0.005},
        "advice": "电流表读数加 data-circuit-current-for",
    }]
}
```

页面侧只需要：

1. 控件加 `data-solver-input="变量名"`（或 `data-mr-control`）；
2. 每次输入重建 `__<前缀>_REQUEST__`、调用求解器、写 `__<前缀>_RESULT__`；
3. 读数加 `data-solver-field="字段名"`；电路表计加 `data-circuit-current-for`；
4. 控件范围允许翻倍/减半这类变形。

### 适用条件（避免误判）

`precondition` 用来声明关系成立的前提。例如 `I∝1/R` 只适用于**单一被测电阻**；
含滑动变阻器的串联电路里，R 翻倍不会让电流减半，此时记 `skip` 并说明原因，
而不是把正确页面判死。

### 测试

```bash
cd 04_review_agent
python -B -m unittest tests.test_mr_engine -v
python -B -m unittest test_solver_metamorphic_review -v
```

夹具 `tests/mr_fixture_lens_ok.html`（应通过）与
`tests/mr_fixture_lens_broken.html`（像距写死，应被 G4-40 拦住）可用于端到端回归。

### 已知边界

1. 目前页面级计划覆盖电路、凸透镜、平面镜、波的传播四类；
   物理/数学课程模型仍走 `lesson_models.json` 的 `relations`，化学仍走 `CHEM_*_SAMPLES`。
2. 几何截面、展开图等“无 UI 对应变换”的关系留在求解器单测，不强行塞进浏览器。
3. 计划要求页面暴露 `__*_REQUEST__/__*_RESULT__`；没有暴露的旧页面会判 fail，
   这是有意的 fail-closed，按 `advice` 补上即可。
