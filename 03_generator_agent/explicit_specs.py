# -*- coding: utf-8 -*-
"""explicit_specs —— 显式规格通道（非 lesson 模型的场景）。

lesson_models.json 能自动推出控件与读数；但有些场景的求解器只吃一组自定义字段
（薄透镜 u/f、电路 netlist、化学模板的浓度体积…）。这些场景以前必须各写一个渲染器。
现在只要在这份表里声明"输入/输出/代入式/教学文案/绘图 API"，就自动获得：

    PageSpec → 组件树 → 六区 → 套壳
    控件标记、读数标记、取证变量、完整性检查 —— 全部由声明推导

新增一个这样的场景 = 在 EXPLICIT_SPECS 里加一条，不改渲染器、不改校验。
"""

import page_spec

EXPLICIT_SPECS = {
    "physics-thin-lens": {
        "subject": "物理",
        "title": "凸透镜成像规律",
        "visual": "apparatus",
        "solver": "PHYS.solveThinLens",
        "prefix": "PHYS_LENS",
        "canvas_key": "lens",
        "draw": "PHYS.optics",
        "aria": "光具座、凸透镜、物体与光屏，带刻度与三条特殊光线",
        "legend": [
            {"label": "物体", "color": "#a3362b"},
            {"label": "凸透镜", "color": "#1b62b0"},
            {"label": "光屏", "color": "#5b6875"},
        ],
        "inputs": [
            {"name": "u", "label": "物距", "unit": "cm", "value": 30, "minimum": 1, "maximum": 100},
            {"name": "f", "label": "焦距", "unit": "cm", "value": 10, "minimum": 2, "maximum": 40},
        ],
        "outputs": [
            {"field": "image_distance_cm", "label": "像距", "unit": "cm"},
            {"field": "magnification", "label": "放大率"},
            {"field": "state", "label": "成像性质"},
        ],
        "formula_js": (
            "result.image_distance_cm == null"
            " ? ('u = f，无有限像')"
            " : ('|m| = |v| ÷ u = ' + number(Math.abs(result.image_distance_cm))"
            " + ' cm ÷ ' + number(request.u)"
            " + ' cm = ' + number(Math.abs(result.magnification)))"
        ),
        "summary_js": (
            "result.image_distance_cm == null"
            " ? 'u = f，不成像'"
            " : ('像距 ' + number(result.image_distance_cm) + ' cm，' + result.state)"
        ),
        "teaching": {
            "source": "物理知识库「凸透镜成像」",
            "kind": "实验性质：虚拟仿真，光路按理想薄透镜计算。",
            "principle": ("凸透镜成像由折射决定，满足 1/f = 1/u + 1/v。物距大于二倍焦距成倒立缩小的实像；"
                          "在一倍与二倍焦距之间成倒立放大的实像；小于焦距成正立放大的虚像，虚像不能用光屏承接。"),
            "pitfall": ("把光屏位置当成像距（像距由 u 和 f 决定，移动光屏只改变是否清晰）；"
                        "在 u = f 时仍去找像（此时出射光平行，不成像）。"),
            "question": "保持焦距不变，把物距从大于 2f 逐渐减小到小于 f，像的大小、正倒和虚实怎样变化？记录三组数据。",
            "conclusion": "像的性质由物距与焦距的比值决定；在光具座上移动光屏只能承接实像，像距与物距满足 1/f = 1/u + 1/v。",
            "safety": "本页为虚拟仿真，不涉及真实光源；真实实验避免激光直射眼睛。",
        },
    },
    "physics-reflection": {
        "subject": "物理",
        "title": "光的反射定律",
        "visual": "diagram",
        "solver": "PHYS.solveReflection",
        "prefix": "PHYS_REFLECTION",
        "canvas_key": "reflection",
        "draw": "PHYS.reflection",
        "aria": "平面镜、法线、入射光线与反射光线，标注入射角和反射角",
        "components": ["presets", "records", "observations"],
        "presets": [
            {"id": "preset-45", "label": "入射角 45°", "values": {"incident_angle": 45}},
            {"id": "preset-30", "label": "入射角 30°", "values": {"incident_angle": 30}},
            {"id": "preset-0", "label": "垂直入射", "values": {"incident_angle": 0}},
            {"id": "preset-70", "label": "入射角 70°", "values": {"incident_angle": 70}},
        ],
        "legend": [
            {"label": "入射光线", "color": "#a3622b"},
            {"label": "反射光线", "color": "#1b62b0"},
            {"label": "法线", "color": "#5b6875"},
        ],
        "inputs": [
            {"name": "incident_angle", "label": "入射角", "unit": "°", "value": 45,
             "minimum": 0, "maximum": 85},
        ],
        "outputs": [
            {"field": "reflected_angle", "label": "反射角", "unit": "°"},
            {"field": "angle_between", "label": "两光线夹角", "unit": "°"},
            {"field": "state", "label": "反射状态"},
        ],
        "formula_js": ("'入射角 + 反射角 = ' + number(request.incident_angle) + '° + ' "
                       "+ number(result.reflected_angle) + '° = ' "
                       "+ number(request.incident_angle + result.reflected_angle) + '°'"),
        "summary_js": ("'反射角 ' + number(result.reflected_angle) + '°，两光线夹角 ' "
                       "+ number(result.angle_between) + '°'"),
        "teaching": {
            "source": "物理知识库「光的反射」",
            "kind": "实验性质：虚拟仿真，光路按几何光学作图。",
            "principle": "光的反射遵循反射定律：反射光线、入射光线和法线在同一平面内，反射光线与入射光线分居法线两侧，反射角等于入射角。",
            "pitfall": "把入射角量成与镜面的夹角（应与法线量）；认为镜面越粗糙反射角越大（改变的是漫反射方向，不是角度关系）。",
            "question": "改变入射角，反射角和两条光线的夹角各怎样变化？把入射角调到 0° 时反射光线在哪里？",
            "conclusion": "反射角始终等于入射角，两光线夹角等于入射角的 2 倍；垂直入射时反射光沿原路返回。",
            "safety": "本页为虚拟仿真；真实实验不要让强光直射眼睛。",
        },
    },
    "chemistry-dilution": {
        "subject": "化学",
        "title": "溶液稀释与浓度",
        "visual": "apparatus",
        "solver": "CHEMSOLVER.solveDilution",
        "prefix": "CHEM_DILUTION",
        "canvas_key": "dilution",
        "draw": "CHEM.dilution",
        "aria": "稀释前后两只烧杯，液面高度表示体积、颜色深浅表示浓度",
        "components": ["presets", "records", "observations"],
        "presets": [
            {"id": "preset-half", "label": "稀释 2 倍", "values": {"stock_concentration_mol_L": 0.2, "stock_volume_ml": 50, "added_water_ml": 50}},
            {"id": "preset-ten", "label": "稀释 5 倍", "values": {"stock_concentration_mol_L": 0.2, "stock_volume_ml": 50, "added_water_ml": 200}},
            {"id": "preset-none", "label": "不加水", "values": {"stock_concentration_mol_L": 0.2, "stock_volume_ml": 50, "added_water_ml": 0}},
        ],
        "legend": [{"label": "稀释前", "color": "#1b62b0"}, {"label": "稀释后", "color": "#5b93c4"}],
        "inputs": [
            {"name": "stock_concentration_mol_L", "label": "母液浓度", "unit": "mol/L", "value": 0.2, "minimum": 0.001, "maximum": 5},
            {"name": "stock_volume_ml", "label": "母液体积", "unit": "mL", "value": 50, "minimum": 1, "maximum": 1000},
            {"name": "added_water_ml", "label": "加水体积", "unit": "mL", "value": 50, "minimum": 0, "maximum": 2000},
        ],
        "outputs": [
            {"field": "final_concentration_mol_L", "label": "稀释后浓度", "unit": "mol/L"},
            {"field": "final_volume_ml", "label": "稀释后体积", "unit": "mL"},
            {"field": "solute_moles_mol", "label": "溶质的物质的量", "unit": "mol"},
            {"field": "dilution_factor", "label": "稀释倍数"},
            {"field": "state", "label": "操作状态"},
        ],
        "formula_js": ("'c₂ = c₁ × V₁ ÷ V₂ = ' + number(request.stock_concentration_mol_L) + ' × ' "
                       "+ number(request.stock_volume_ml) + ' ÷ ' "
                       "+ number(request.stock_volume_ml + request.added_water_ml) + ' = ' "
                       "+ number(result.final_concentration_mol_L) + ' mol/L'"),
        "summary_js": "'稀释后 ' + number(result.final_concentration_mol_L) + ' mol/L，' + result.state",
        "teaching": {
            "source": "化学知识库「溶液与浓度」",
            "kind": "实验性质：虚拟仿真，按溶质物质的量守恒计算。",
            "principle": "加水稀释时溶质的物质的量不变，所以 c₁V₁ = c₂V₂：体积变成几倍，浓度就变成几分之一。",
            "pitfall": "把体积相加算成浓度相加；用质量分数公式去套体积稀释。",
            "question": "加水体积分别取 50 mL 和 200 mL，浓度各变成原来的几分之几？记录三组数据核对 c₁V₁ = c₂V₂。",
            "conclusion": "稀释前后溶质的物质的量守恒，浓度与溶液体积成反比。",
            "safety": "本页为虚拟仿真；真实实验量取浓溶液须戴护目镜，遵循「酸入水」。",
        },
    },
    "chemistry-mass-conservation": {
        "subject": "化学",
        "title": "质量守恒与质量变化",
        "visual": "apparatus",
        "solver": "CHEMSOLVER.solveMassConservation",
        "prefix": "CHEM_MASS",
        "canvas_key": "mass",
        "draw": "CHEM.massConservation",
        "aria": "天平对照反应前后总质量；敞口时标出逸出的二氧化碳",
        "components": ["presets", "records", "observations"],
        "presets": [
            {"id": "preset-sealed", "label": "密闭容器", "values": {"calcium_carbonate_g": 10, "progress": 1, "vessel": "sealed"}},
            {"id": "preset-open", "label": "敞口容器", "values": {"calcium_carbonate_g": 10, "progress": 1, "vessel": "open"}},
            {"id": "preset-half", "label": "分解一半", "values": {"calcium_carbonate_g": 10, "progress": 0.5, "vessel": "open"}},
        ],
        "legend": [
            {"label": "反应前", "color": "#1b62b0"},
            {"label": "反应后", "color": "#5b93c4"},
            {"label": "逸出气体", "color": "#a3362b"},
        ],
        "inputs": [
            {"name": "calcium_carbonate_g", "label": "碳酸钙质量", "unit": "g", "value": 10, "minimum": 0.1, "maximum": 200},
            {"name": "progress", "label": "分解程度", "unit": "", "value": 1, "minimum": 0, "maximum": 1},
            {"name": "vessel", "kind": "select", "label": "容器", "value": "sealed",
             "options": [["sealed", "密闭容器"], ["open", "敞口容器"]]},
        ],
        "outputs": [
            {"field": "before_mass_g", "label": "反应前总质量", "unit": "g"},
            {"field": "after_mass_g", "label": "反应后总质量", "unit": "g"},
            {"field": "gas_mass_g", "label": "逸出气体质量", "unit": "g"},
            {"field": "residue_mass_g", "label": "剩余固体质量", "unit": "g"},
            {"field": "mass_change_g", "label": "质量变化", "unit": "g"},
            {"field": "state", "label": "体系状态"},
        ],
        "formula_js": ("'反应后总质量 = 反应前 − 逸出气体 = ' + number(result.before_mass_g) + ' g − ' "
                       "+ number(result.gas_mass_g) + ' g = ' + number(result.after_mass_g) + ' g'"),
        "summary_js": ("'反应前 ' + number(result.before_mass_g) + ' g → 反应后 ' "
                       "+ number(result.after_mass_g) + ' g，' + result.state"),
        "teaching": {
            "source": "化学知识库「质量守恒定律」",
            "kind": "实验性质：虚拟仿真，按 CaCO₃ → CaO + CO₂ 的计量关系计算。",
            "principle": "质量守恒定律：参加化学反应的各物质质量总和等于反应后生成的各物质质量总和。密闭容器里总质量不变；敞口容器中生成的气体逸出，称量到的质量会减少。",
            "pitfall": "把敞口称量变轻当成质量不守恒；忽略气体的质量而不去称量。",
            "question": "密闭和敞口两种情形反应后总质量各是多少？质量减少的部分去了哪里？记录两组数据比较。",
            "conclusion": "密闭体系中反应前后总质量相等；敞口体系减少的质量恰好等于逸出气体的质量。",
            "safety": "本页为虚拟仿真；真实实验加热碳酸钙需高温，注意通风与防护。",
        },
    },
    "chemistry-ph-indicator": {
        "subject": "化学",
        "title": "pH 与酸碱指示剂",
        "visual": "diagram",
        "solver": "CHEMSOLVER.solvePhIndicator",
        "prefix": "CHEM_PH",
        "canvas_key": "ph",
        "draw": "CHEM.phIndicator",
        "aria": "pH 色卡与紫色石蕊、无色酚酞在酸碱性下的颜色",
        "components": ["presets", "records", "observations"],
        "presets": [
            {"id": "preset-acid", "label": "pH = 2", "values": {"ph": 2}},
            {"id": "preset-neutral", "label": "pH = 7", "values": {"ph": 7}},
            {"id": "preset-weak", "label": "pH = 9", "values": {"ph": 9}},
            {"id": "preset-base", "label": "pH = 13", "values": {"ph": 13}},
        ],
        "legend": [
            {"label": "酸性", "color": "#c0392b"},
            {"label": "中性", "color": "#7fb069"},
            {"label": "碱性", "color": "#2f86c4"},
        ],
        "inputs": [
            {"name": "ph", "label": "溶液 pH", "value": 7, "minimum": 0, "maximum": 14},
        ],
        "outputs": [
            {"field": "nature", "label": "酸碱性"},
            {"field": "litmus_color", "label": "石蕊颜色"},
            {"field": "phenolphthalein_color", "label": "酚酞颜色"},
            {"field": "poh", "label": "pOH"},
        ],
        "formula_js": ("'pH + pOH = ' + number(request.ph) + ' + ' + number(result.poh) "
                       "+ ' = ' + number(request.ph + result.poh)"),
        "summary_js": "'pH ' + number(result.ph) + ' → ' + result.nature + '，石蕊 ' + result.litmus_color",
        "teaching": {
            "source": "化学知识库「酸碱性与指示剂」",
            "kind": "实验性质：虚拟仿真，按 25 °C 下的变色范围判定。",
            "principle": "pH 小于 7 为酸性、等于 7 为中性、大于 7 为碱性；25 °C 时 pH + pOH = 14。向酸中逐渐加碱，pH 会逐渐升高；向碱中加酸，pH 会逐渐降低。紫色石蕊遇酸变红、遇碱变蓝；无色酚酞遇酸和中性不变色，遇碱变红。",
            "pitfall": "记反酚酞的变色（酚酞在酸性、中性都无色）；把 pH 试纸的比色当成精确测量。",
            "question": "把 pH 从 2 调到 13，石蕊和酚酞的颜色各在哪一段发生突变？为什么酚酞在 pH 7 时仍无色？",
            "conclusion": "指示剂只在特定 pH 区间变色，只能判断酸碱性、不能精确测 pH；酚酞的变色区间在 pH 8.2–10。",
            "safety": "本页为虚拟仿真；真实实验取用酸碱须戴护目镜，注意废液处理。",
        },
    },
    "chemistry-reaction-amounts": {
        "subject": "化学",
        "title": "化学计量与气体摩尔体积",
        "visual": "diagram",
        "solver": "CHEMSOLVER.solveReactionAmounts",
        "prefix": "CHEM_AMOUNT",
        "canvas_key": "amount",
        "draw": "CHEM.reactionAmounts",
        "aria": "反应物剩余与生成物的物质的量条形图，标出限量试剂",
        "components": ["presets", "records", "observations"],
        "presets": [
            {"id": "preset-exact", "label": "恰好完全反应", "values": {"hydrogen_mol": 2, "oxygen_mol": 1, "progress": 1}},
            {"id": "preset-h2", "label": "氢气过量", "values": {"hydrogen_mol": 4, "oxygen_mol": 1, "progress": 1}},
            {"id": "preset-half", "label": "反应一半", "values": {"hydrogen_mol": 2, "oxygen_mol": 1, "progress": 0.5}},
        ],
        "legend": [
            {"label": "剩余 H₂", "color": "#2f86c4"},
            {"label": "剩余 O₂", "color": "#c07a34"},
            {"label": "生成 H₂O", "color": "#2f7a55"},
        ],
        "inputs": [
            {"name": "hydrogen_mol", "label": "H₂ 的物质的量", "unit": "mol", "value": 2, "minimum": 0, "maximum": 20},
            {"name": "oxygen_mol", "label": "O₂ 的物质的量", "unit": "mol", "value": 1, "minimum": 0, "maximum": 20},
            {"name": "progress", "label": "反应进度", "value": 1, "minimum": 0, "maximum": 1},
        ],
        "outputs": [
            {"field": "limiting_reagent", "label": "限量试剂"},
            {"field": "water_mol", "label": "生成 H₂O", "unit": "mol"},
            {"field": "hydrogen_left_mol", "label": "剩余 H₂", "unit": "mol"},
            {"field": "oxygen_left_mol", "label": "剩余 O₂", "unit": "mol"},
            {"field": "gas_left_mol", "label": "剩余气体总量", "unit": "mol"},
            {"field": "gas_volume_L", "label": "剩余气体体积", "unit": "L"},
        ],
        "formula_js": ("'气体体积 = n × 22.4 L/mol = ' + number(result.gas_left_mol) + ' × 22.4 = ' "
                       "+ number(result.gas_volume_L) + ' L'"),
        "summary_js": ("'限量试剂 ' + result.limiting_reagent + '，生成 H₂O ' "
                       "+ number(result.water_mol) + ' mol'"),
        "teaching": {
            "source": "化学知识库「化学计量」",
            "kind": "实验性质：虚拟仿真，按 2H₂ + O₂ → 2H₂O 计量。",
            "principle": "按方程式系数之比判断限量试剂：2 mol H₂ 与 1 mol O₂ 恰好完全反应生成 2 mol H₂O。标准状况下 1 mol 任何气体的体积约为 22.4 L。",
            "pitfall": "直接按「谁少谁限量」判断（要看物质的量之比与系数之比）；把 22.4 L/mol 用在非标准状况。",
            "question": "分别取 H₂ 4 mol、O₂ 1 mol 和 H₂ 2 mol、O₂ 2 mol，哪种情况氧气过量？剩余气体体积各是多少？",
            "conclusion": "限量试剂由 n(反应物) ÷ 系数 的较小者决定；剩余气体体积 = 剩余物质的量 × 22.4 L/mol。",
            "safety": "本页为虚拟仿真；真实实验点燃氢气前必须验纯，防止爆炸。",
        },
    },
    "chemistry-solubility-curve": {
        "subject": "化学",
        "title": "溶解度曲线与饱和溶液",
        "visual": "graph",
        "solver": "CHEMSOLVER.solveSolubilityCurve",
        "prefix": "CHEM_SOLUBILITY",
        "canvas_key": "solubility",
        "draw": "CHEM.solubilityCurve",
        "aria": "溶解度随温度变化的曲线，标出当前温度点与是否饱和",
        "components": ["presets", "records", "observations"],
        "presets": [
            {"id": "preset-unsaturated", "label": "不饱和", "values": {"temperature_c": 40, "water_g": 100, "solute_g": 20}},
            {"id": "preset-saturated", "label": "恰好饱和", "values": {"temperature_c": 40, "water_g": 100, "solute_g": 52}},
            {"id": "preset-excess", "label": "有剩余固体", "values": {"temperature_c": 40, "water_g": 100, "solute_g": 70}},
            {"id": "preset-cold", "label": "降温到 10 °C", "values": {"temperature_c": 10, "water_g": 100, "solute_g": 70}},
        ],
        "legend": [
            {"label": "溶解度曲线", "color": "#1b62b0"},
            {"label": "当前状态", "color": "#a3362b"},
        ],
        "inputs": [
            {"name": "temperature_c", "label": "温度", "unit": "°C", "value": 40, "minimum": 0, "maximum": 100},
            {"name": "solute_g", "label": "加入溶质质量", "unit": "g", "value": 40, "minimum": 0, "maximum": 200},
            {"name": "water_g", "label": "水的质量", "unit": "g", "value": 100, "minimum": 1, "maximum": 500},
        ],
        "outputs": [
            {"field": "solubility_g_per_100g", "label": "该温度溶解度", "unit": "g/100g水"},
            {"field": "capacity_g", "label": "该水量最多溶解", "unit": "g"},
            {"field": "dissolved_g", "label": "已溶解", "unit": "g"},
            {"field": "undissolved_g", "label": "未溶解", "unit": "g"},
            {"field": "saturation", "label": "饱和状态"},
        ],
        "formula_js": ("'最多溶解 = S × 水量 ÷ 100 = ' + number(result.solubility_g_per_100g) + ' × ' "
                       "+ number(request.water_g / 100) + ' = ' + number(result.capacity_g) + ' g'"),
        "summary_js": ("'S = ' + number(result.solubility_g_per_100g) + ' g/100g 水，' + result.saturation"),
        "teaching": {
            "source": "化学知识库「溶解度与饱和溶液」",
            "kind": "实验性质：虚拟仿真，溶解度曲线为简化线性模型（S = 20 + 0.8T）。",
            "principle": "一定温度下，某固体物质在 100 g 溶剂中达到饱和时所溶解的质量叫溶解度。溶解度随温度升高而增大，曲线上的点表示饱和状态。",
            "pitfall": "把「溶解度随温度升高而增大」当成所有固体都成立（如氢氧化钙相反）；忽略饱和溶液仍能溶解其他溶质。",
            "question": "把 70 g 溶质加入 100 g 水中，40 °C 和 10 °C 时各溶解多少？未溶解的部分怎样变化？",
            "conclusion": "低于曲线饱和：溶质全部溶解；高于曲线：超出部分不再溶解，成为未溶解固体。",
            "safety": "本页为虚拟仿真；真实实验加热溶液注意烫伤与蒸发皿使用规范。",
        },
    },
    "chemistry-rate-equilibrium": {
        "subject": "化学",
        "title": "反应速率与化学平衡",
        "visual": "graph",
        "solver": "CHEMSOLVER.solveRateEquilibrium",
        "prefix": "CHEM_RATE",
        "canvas_key": "rate",
        "draw": "CHEM.rateEquilibrium",
        "aria": "反应速率随时间下降的曲线，对比加催化剂与基准条件",
        "components": ["presets", "records", "observations"],
        "presets": [
            {"id": "preset-base", "label": "25 °C 基准", "values": {"temperature_c": 25, "reactant_concentration_mol_L": 1, "catalyst": "no"}},
            {"id": "preset-hot", "label": "升温到 55 °C", "values": {"temperature_c": 55, "reactant_concentration_mol_L": 1, "catalyst": "no"}},
            {"id": "preset-catalyst", "label": "加催化剂", "values": {"temperature_c": 25, "reactant_concentration_mol_L": 1, "catalyst": "yes"}},
            {"id": "preset-concentrated", "label": "浓度加倍", "values": {"temperature_c": 25, "reactant_concentration_mol_L": 2, "catalyst": "no"}},
        ],
        "legend": [
            {"label": "当前条件", "color": "#2f86c4"},
            {"label": "对比条件", "color": "#a3362b"},
        ],
        "inputs": [
            {"name": "temperature_c", "label": "温度", "unit": "°C", "value": 25, "minimum": 0, "maximum": 100},
            {"name": "reactant_concentration_mol_L", "label": "反应物浓度", "unit": "mol/L", "value": 1, "minimum": 0.01, "maximum": 5},
            {"name": "catalyst", "kind": "select", "label": "催化剂", "value": "no",
             "options": [["no", "不加"], ["yes", "加催化剂"]]},
        ],
        "outputs": [
            {"field": "rate_relative", "label": "相对反应速率"},
            {"field": "conversion_percent", "label": "平衡转化率", "unit": "%"},
            {"field": "time_to_equilibrium_s", "label": "达平衡时间", "unit": "s"},
            {"field": "temperature_effect", "label": "温度效应"},
            {"field": "catalyst_effect", "label": "催化剂效应"},
        ],
        "formula_js": ("'v = k × c = ' + number(result.rate_constant) + ' × ' "
                       "+ number(request.reactant_concentration_mol_L) + ' = ' "
                       "+ number(result.rate_constant * request.reactant_concentration_mol_L)"),
        "summary_js": ("'相对速率 ' + number(result.rate_relative) + '，转化率 ' "
                       "+ number(result.conversion_percent) + ' %'"),
        "teaching": {
            "source": "化学知识库「化学反应速率与平衡」",
            "kind": "实验性质：虚拟仿真，速率与转化率按经验规则简化计算（每升 10 °C 速率约翻倍）。",
            "principle": "反应速率随温度升高、浓度增大而加快，催化剂降低活化能从而加快反应；但催化剂不改变平衡状态，只有温度会改变平衡转化率。",
            "pitfall": "以为催化剂能提高转化率（只加快达到平衡）；以为升温一定提高转化率（放热反应升温反而降低）。",
            "question": "升温和加催化剂分别怎样影响速率和转化率？为什么催化剂不改变转化率？记录三组数据比较。",
            "conclusion": "催化剂只改变速率、不改变平衡；温度同时改变速率与平衡转化率（放热反应升温使转化率下降）。",
            "safety": "本页为虚拟仿真；真实实验涉及加热与催化剂使用，须遵守实验室安全规范。",
        },
    },
    "chemistry-metal-activity": {
        "subject": "化学",
        "title": "金属活动性顺序与置换反应",
        "visual": "apparatus",
        "solver": "CHEMSOLVER.solveMetalActivity",
        "prefix": "CHEM_ACTIVITY",
        "canvas_key": "activity",
        "draw": "CHEM.metalActivity",
        "aria": "金属活动性顺序表与盛有盐溶液的烧杯，判定能否发生置换反应",
        "components": ["presets", "records", "observations"],
        "presets": [
            {"id": "preset-fe-cuso4", "label": "铁 + 硫酸铜", "values": {"metal": "Fe", "salt_solution": "CuSO4"}},
            {"id": "preset-cu-hcl", "label": "铜 + 稀盐酸", "values": {"metal": "Cu", "salt_solution": "HCl"}},
            {"id": "preset-zn-cuso4", "label": "锌 + 硫酸铜", "values": {"metal": "Zn", "salt_solution": "CuSO4"}},
            {"id": "preset-ag-hcl", "label": "银 + 稀盐酸", "values": {"metal": "Ag", "salt_solution": "HCl"}},
        ],
        "legend": [
            {"label": "活动性强", "color": "#d99441"},
            {"label": "活动性弱", "color": "#aebdcd"},
        ],
        "inputs": [
            {"name": "metal", "kind": "select", "label": "金属", "value": "Fe",
             "options": [["Mg", "镁"], ["Zn", "锌"], ["Fe", "铁"], ["Cu", "铜"], ["Ag", "银"]]},
            {"name": "salt_solution", "kind": "select", "label": "溶液", "value": "CuSO4",
             "options": [["CuSO4", "硫酸铜"], ["AgNO3", "硝酸银"], ["ZnSO4", "硫酸锌"],
                         ["MgSO4", "硫酸镁"], ["HCl", "稀盐酸"]]},
        ],
        "outputs": [
            {"field": "reacts", "label": "能否反应"},
            {"field": "metal_rank", "label": "金属位次"},
            {"field": "target_rank", "label": "目标金属位次"},
            {"field": "equation", "label": "反应方程式"},
            {"field": "phenomenon", "label": "实验现象"},
            {"field": "state", "label": "判定"},
        ],
        "formula_js": ("'位次差 = 目标位次 − 金属位次 = ' + number(result.target_rank) + ' − ' "
                       "+ number(result.metal_rank) + ' = ' "
                       "+ number(result.target_rank - result.metal_rank)"),
        "summary_js": "result.state + '，' + result.phenomenon",
        "teaching": {
            "source": "化学知识库「金属活动性顺序」",
            "kind": "实验性质：虚拟仿真，按金属活动性顺序判定，不涉及真实操作。",
            "principle": "金属活动性顺序：K Ca Na Mg Al Zn Fe Sn Pb (H) Cu Hg Ag Pt Au。排在前面的金属能把排在后面的金属从其盐溶液中置换出来；排在氢前面的金属能与稀酸反应放出氢气。",
            "pitfall": "铜与稀盐酸没有现象时误以为实验失败（不反应本身就是结论）；把钠等活泼金属直接投入盐溶液（先与水反应）。",
            "question": "把铁、铜、银分别放入硫酸铜溶液，哪些能反应？把铜放入稀盐酸呢？记录判定与方程式。",
            "conclusion": "活动性强的金属置换活动性弱的金属；排在氢之后的金属不与稀酸反应。",
            "safety": "本页为虚拟仿真；真实实验使用硝酸银等试剂须戴手套，废液按规定回收。",
        },
    },
    "chemistry-change-type": {
        "subject": "化学",
        "numeric": False,
        "title": "物理变化与化学变化",
        "visual": "diagram",
        "solver": "CHEMSOLVER.solveChangeType",
        "prefix": "CHEM_CHANGE",
        "canvas_key": "change",
        "draw": "CHEM.changeType",
        "aria": "物理变化与化学变化两栏对照，标出当前现象所属类别",
        "components": ["presets", "records", "observations"],
        "presets": [
            {"id": "preset-melt", "label": "冰融化", "values": {"phenomenon": "ice_melt"}},
            {"id": "preset-rust", "label": "铁生锈", "values": {"phenomenon": "iron_rust"}},
            {"id": "preset-evaporate", "label": "酒精挥发", "values": {"phenomenon": "alcohol_evaporate"}},
            {"id": "preset-burn", "label": "蜡烛燃烧", "values": {"phenomenon": "candle_burn"}},
        ],
        "inputs": [
            {"name": "phenomenon", "kind": "select", "label": "现象", "value": "ice_melt",
             "options": [["ice_melt", "冰融化成水"], ["alcohol_evaporate", "酒精挥发"],
                         ["water_boil", "水沸腾"], ["iron_rust", "铁生锈"],
                         ["candle_burn", "蜡烛燃烧"], ["milk_spoil", "牛奶变质"]]},
        ],
        "outputs": [
            {"field": "change_type", "label": "变化类型"},
            {"field": "criterion", "label": "判断依据"},
            {"field": "reason", "label": "解释"},
            {"field": "phenomenon", "label": "现象"},
        ],
        "formula_js": ("'判断依据：' + result.criterion + ' → ' + result.change_type"),
        "summary_js": "result.change_type + '：' + result.reason",
        "teaching": {
            "source": "化学知识库「物质的变化」",
            "kind": "实验性质：虚拟仿真，按「是否生成新物质」判定。",
            "principle": "没有新物质生成的变化是物理变化（状态、形状改变）；有新物质生成的变化是化学变化，常伴随颜色改变、放出气体、生成沉淀、发光放热等现象。",
            "pitfall": "把发光放热一律当成化学变化（灯泡发光是物理变化）；把状态变化当成化学变化。",
            "question": "冰融化、铁生锈、酒精挥发、蜡烛燃烧各属于哪一类？判断依据是什么？",
            "conclusion": "判断标准只有一条：有没有新物质生成，而不是看有没有发光、放热或状态改变。",
            "safety": "本页为虚拟仿真；真实实验涉及燃烧须远离可燃物并在通风处进行。",
        },
    },
    "chemistry-galvanic": {
        "subject": "化学",
        "title": "原电池原理",
        "visual": "apparatus",
        "solver": "CHEMSOLVER.solveGalvanicCell",
        "prefix": "CHEM_CELL",
        "canvas_key": "cell",
        "draw": "CHEM.galvanicCell",
        "aria": "原电池装置：两种金属电极、电解液、导线与电子流向",
        "components": ["presets", "records", "observations"],
        "presets": [
            {"id": "preset-zn-cu", "label": "Zn–Cu", "values": {"electrode_a": "Zn", "electrode_b": "Cu"}},
            {"id": "preset-fe-cu", "label": "Fe–Cu", "values": {"electrode_a": "Fe", "electrode_b": "Cu"}},
            {"id": "preset-zn-ag", "label": "Zn–Ag", "values": {"electrode_a": "Zn", "electrode_b": "Ag"}},
            {"id": "preset-cu-ag", "label": "Cu–Ag", "values": {"electrode_a": "Cu", "electrode_b": "Ag"}},
        ],
        "inputs": [
            {"name": "electrode_a", "kind": "select", "label": "电极 A", "value": "Zn",
             "options": [["Zn", "锌 Zn"], ["Fe", "铁 Fe"], ["Cu", "铜 Cu"], ["Ag", "银 Ag"]]},
            {"name": "electrode_b", "kind": "select", "label": "电极 B", "value": "Cu",
             "options": [["Zn", "锌 Zn"], ["Fe", "铁 Fe"], ["Cu", "铜 Cu"], ["Ag", "银 Ag"]]},
        ],
        "outputs": [
            {"field": "anode", "label": "负极"},
            {"field": "cathode", "label": "正极"},
            {"field": "anode_potential", "label": "负极电势", "unit": "V"},
            {"field": "cathode_potential", "label": "正极电势", "unit": "V"},
            {"field": "emf_v", "label": "电动势", "unit": "V"},
            {"field": "state", "label": "电池状态"},
        ],
        "formula_js": ("'电动势 = E正 + |E负| = ' + number(result.cathode_potential) + ' + ' "
                       "+ number(-result.anode_potential) + ' = ' + number(result.emf_v) + ' V'"),
        "summary_js": "'负极 ' + result.anode + '、正极 ' + result.cathode + '，电动势 ' + number(result.emf_v) + ' V'",
        "teaching": {
            "source": "化学知识库「原电池」",
            "kind": "实验性质：虚拟仿真，按标准电极电势计算（25 °C，1 mol/L）。",
            "principle": "原电池把化学能转化为电能：活动性强的金属作负极失电子，电子经导线流向正极；电动势等于正极电势与负极电势之差。",
            "pitfall": "把电子流向与电流方向弄反（电子由负极到正极，电流相反）；以为两极金属相同也能构成原电池。",
            "question": "换不同电极对，电动势怎样变化？为什么 Zn–Ag 的电动势最大？记录三组数据。",
            "conclusion": "两极标准电势差越大，电动势越大；电子从负极经外电路流向正极。",
            "safety": "本页为虚拟仿真；真实实验使用硝酸银等试剂须戴手套，废液回收。",
        },
    },
    "chemistry-isomer": {
        "subject": "化学",
        "title": "同分异构体计数",
        "visual": "diagram",
        "solver": "CHEMSOLVER.solveIsomerCount",
        "prefix": "CHEM_ISOMER",
        "canvas_key": "isomer",
        "draw": "CHEM.isomerCount",
        "aria": "同分异构体清单，逐条列出碳骨架异构体名称",
        "components": ["presets", "records", "observations"],
        "presets": [
            {"id": "preset-c4", "label": "C₄H₁₀", "values": {"formula": "C4H10"}},
            {"id": "preset-c5", "label": "C₅H₁₂", "values": {"formula": "C5H12"}},
            {"id": "preset-c3o", "label": "C₃H₆O", "values": {"formula": "C3H6O"}},
        ],
        "inputs": [
            {"name": "formula", "kind": "select", "label": "分子式", "value": "C5H12",
             "options": [["C4H10", "C₄H₁₀"], ["C5H12", "C₅H₁₂"], ["C3H6O", "C₃H₆O"]]},
        ],
        "outputs": [
            {"field": "total", "label": "异构体总数"},
            {"field": "chain_count", "label": "直链数"},
            {"field": "branched_count", "label": "支链数"},
            {"field": "note", "label": "规律"},
        ],
        "formula_js": ("'异构体总数 = 直链 + 支链 = ' + number(result.chain_count) + ' + ' "
                       "+ number(result.branched_count) + ' = ' + number(result.total)"),
        "summary_js": "'该分子式有 ' + number(result.total) + ' 种碳骨架异构体'",
        "teaching": {
            "source": "化学知识库「有机物的同分异构」",
            "kind": "实验性质：虚拟仿真，按碳骨架异构计数（不计顺反异构）。",
            "principle": "分子式相同而结构不同的化合物互为同分异构体。烷烃的同分异构来自碳骨架（直链与支链）的差异，碳原子越多，异构体越多。",
            "pitfall": "把同一种物质的两种写法算成两种（如异丁烷与 2-甲基丙烷）；漏掉支链多但对称的结构。",
            "question": "C₄H₁₀ 和 C₅H₁₂ 各有几种碳骨架异构体？为什么碳原子越多异构体越多？",
            "conclusion": "同分异构体计数要先固定碳骨架，再检查是否重复（对称结构会重复计数）。",
            "safety": "本页为虚拟仿真，只做结构计数，不涉及试剂与操作。",
        },
    },
    "chemistry-crystal": {
        "subject": "化学",
        "title": "晶体结构与配位数",
        "visual": "diagram",
        "numeric": False,
        "solver": "CHEMSOLVER.solveCrystal",
        "prefix": "CHEM_CRYSTAL",
        "canvas_key": "crystal",
        "draw": "CHEM.crystalLattice",
        "aria": "晶胞示意：顶点与面心粒子，标注配位数与晶胞粒子数",
        "components": ["presets", "records", "observations"],
        "presets": [
            {"id": "preset-nacl", "label": "NaCl", "values": {"crystal": "NaCl"}},
            {"id": "preset-cscl", "label": "CsCl", "values": {"crystal": "CsCl"}},
            {"id": "preset-diamond", "label": "金刚石", "values": {"crystal": "diamond"}},
            {"id": "preset-co2", "label": "干冰", "values": {"crystal": "CO2"}},
        ],
        "inputs": [
            {"name": "crystal", "kind": "select", "label": "晶体", "value": "NaCl",
             "options": [["NaCl", "氯化钠"], ["CsCl", "氯化铯"], ["diamond", "金刚石"],
                         ["CO2", "干冰"], ["Cu", "铜"]]},
        ],
        "outputs": [
            {"field": "name", "label": "晶体"},
            {"field": "crystal_type", "label": "晶体类型"},
            {"field": "coordination", "label": "配位数"},
            {"field": "cell_particles", "label": "晶胞粒子数"},
            {"field": "note", "label": "结构说明"},
        ],
        "formula_js": ("'配位数 = ' + number(result.coordination) + '，晶胞粒子数 = ' "
                       "+ number(result.cell_particles)"),
        "summary_js": "'配位数 ' + number(result.coordination) + '，晶胞含 ' + number(result.cell_particles) + ' 个粒子'",
        "teaching": {
            "source": "化学知识库「晶体结构」",
            "kind": "实验性质：虚拟仿真，按常见晶体结构模型说明。",
            "principle": "晶体按构成粒子与作用力分为离子晶体、共价晶体、分子晶体和金属晶体；配位数指一个粒子周围最近的异号（或相邻）粒子数，晶胞粒子数按顶点、棱、面心、体内的分摊计算。",
            "pitfall": "把配位数与晶胞粒子数混为一谈；计算顶点粒子时不乘 1/8。",
            "question": "NaCl 与 CsCl 的配位数各是多少？为什么同为离子晶体却不同？",
            "conclusion": "配位数由阴阳离子半径比与堆积方式决定；晶胞粒子数按分摊规则求和。",
            "safety": "本页为虚拟仿真，只做结构讲解，不涉及试剂与操作。",
        },
    },
    "physics-density": {
        "subject": "物理",
        "title": "密度测量",
        "visual": "apparatus",
        "solver": "PHYS.solveDensity",
        "prefix": "PHYS_DENSITY",
        "canvas_key": "density",
        "draw": "PHYS.density",
        "aria": "托盘天平（物体与砝码）、量筒（水与刻度）、物块，读数同步给出密度与浮沉判断",
        "stage_note": "器材：托盘天平（含砝码）、量筒、水；物体用细线系住浸没，读量筒时视线与凹液面最低处相平。",
        "components": ["presets", "records", "csv", "observations"],
        "presets": [
            {"id": "preset-iron", "label": "铁块 39 g / 5 cm³", "values": {"mass_g": 39, "volume_cm3": 5}},
            {"id": "preset-aluminum", "label": "铝块 27 g / 10 cm³", "values": {"mass_g": 27, "volume_cm3": 10}},
            {"id": "preset-water", "label": "密度与水的密度相同", "values": {"mass_g": 10, "volume_cm3": 10}},
            {"id": "preset-wood", "label": "木块 4 g / 8 cm³", "values": {"mass_g": 4, "volume_cm3": 8}},
        ],
        "legend": [
            {"label": "物体", "color": "#9d6f3c"},
            {"label": "砝码", "color": "#cdae52"},
            {"label": "水", "color": "#1b74b8"},
        ],
        "inputs": [
            {"name": "mass_g", "label": "质量 m", "unit": "g", "value": 20, "minimum": 1, "maximum": 500},
            {"name": "volume_cm3", "label": "体积 V", "unit": "cm³", "value": 8, "minimum": 1, "maximum": 60},
        ],
        "outputs": [
            {"field": "density_g_cm3", "label": "密度", "unit": "g/cm³"},
            {"field": "density_kg_m3", "label": "密度（国际单位）", "unit": "kg/m³"},
            {"field": "state", "label": "浮沉判断"},
        ],
        "formula_js": ("'密度 = 质量 ÷ 体积 = ' + number(request.mass_g) + ' g ÷ ' "
                       "+ number(request.volume_cm3) + ' cm³ = ' "
                       "+ number(result.density_g_cm3) + ' g/cm³'"),
        "summary_js": ("'密度 ' + number(result.density_g_cm3) + ' g/cm³，' + String(result.state)"),
        "teaching": {
            "source": "物理知识库「物质的密度」",
            "kind": "实验性质：虚拟仿真，按天平与量筒的读数计算，不模拟称量误差。",
            "principle": ("密度是物质的一种特性：ρ = m/V。用天平测质量、量筒排水法测体积（末读数减初读数），"
                          "两者之比即密度。同种物质密度一般相同，与物体的大小、形状无关。"),
            "pitfall": ("把量筒读数直接当成物体体积（应取末读数减初读数）；"
                        "单位换算错（1 g/cm³ = 1000 kg/m³）；认为质量大的物体密度一定大。"),
            "question": "把质量与体积同时放大到原来的两倍，密度读数变不变？换一种材料再测一次，密度由什么决定？",
            "conclusion": "密度等于质量与体积的比值，与物体大小无关；把 ρ 与水的密度 1 g/cm³ 比较即可判断浮沉。",
            "safety": "本页为虚拟仿真；真实实验取放砝码要用镊子，读量筒时视线与凹液面最低处相平。",
        },
    },
}


def has(scene_id):
    return scene_id in EXPLICIT_SPECS


def spec_for(scene_id, req=None):
    """把声明装配成 PageSpec（与 page_spec.lesson_spec 同构）。"""
    data = EXPLICIT_SPECS[scene_id]
    req = req or {}
    namespace, function = page_spec.split_api(data["solver"])
    request_key, result_key = page_spec.keys_for(data["prefix"])
    inputs = []
    for item in data["inputs"]:
        if item.get("kind") == "select":
            inputs.append(page_spec.select_input(item["name"], item["label"], item["value"],
                                                 item.get("options") or []))
        else:
            inputs.append(page_spec.number_input(
                item["name"], item["label"], item["value"], unit=item.get("unit", ""),
                minimum=item.get("minimum"), maximum=item.get("maximum"),
                scale=item.get("scale", 1.0)))
    outputs = [page_spec.output(item["field"], item["label"], unit=item.get("unit", ""))
               for item in data["outputs"]]
    key = data.get("canvas_key") or scene_id
    headers = [_header(item) for item in data["inputs"]] + [_header(item) for item in data["outputs"]]
    fields = ([{"js": "number(request.%s)" % item["name"]} for item in data["inputs"]] +
              [{"js": "number(result.%s)" % item["field"]} for item in data["outputs"]])
    goals = req.get("学习目标")
    if isinstance(goals, str):
        goals = [goals]
    teaching = dict(data.get("teaching") or {})
    spec = {
        "schema": page_spec.SCHEMA_VERSION,
        "scene": scene_id,
        "subject": data["subject"],
        "grade": req.get("年级") or "初中",
        "title": data["title"],
        "runtime": page_spec.DEFAULT_RUNTIME,
        "visual": data["visual"],
        "solver": {"api": data["solver"], "namespace": namespace, "function": function,
                   "prefix": data["prefix"], "request_key": request_key, "result_key": result_key},
        "draw": {"api": data["draw"]},
        "inputs": inputs,
        "outputs": outputs,
        "presets": list(data.get("presets") or []),
        "components": list(data.get("components") or ["records", "observations"]),
        "stage": {"canvas_id": "%s-scene" % key, "aria": data.get("aria") or data["title"],
                  "legend": list(data.get("legend") or []), "note": data.get("stage_note", "")},
        "formula": {"js": data["formula_js"], "note": data.get("formula_note", "")},
        "records": {"body_id": "%s-records" % key, "headers": headers, "fields": fields},
        "comparison": {"id": "%s-comparison" % key, "title": "观察前后对照",
                       "left": "对照", "right": "当前"},
        "summary_js": data["summary_js"],
        "teaching": teaching,
        "relations": [],
        "assumptions": "",
        "lesson_model": None,
        "source": teaching.get("source", ""),
        "learning_goals": [goal for goal in (goals or []) if str(goal).strip()]
                          or [teaching.get("question") or ""],
    }
    return page_spec.require_valid(spec)


def _header(item):
    label = str(item.get("label") or "").strip()
    unit = str(item.get("unit") or "").strip()
    return "%s/%s" % (label, unit) if unit else label
