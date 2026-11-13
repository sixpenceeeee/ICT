# -*- coding: utf-8 -*-
"""Reusable page skeleton selection by subject and teaching topic.

Keep topic matching, prompt guidance, and generation-time hard checks in one
place so they cannot silently disagree.
"""

import json
from pathlib import Path
import re
import sys

SOLVER_ROOT = Path(__file__).resolve().parent / "solvers"
if str(SOLVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SOLVER_ROOT))

from mathematics.lesson_models import SOLVERS as MATH_REFERENCES
from physics.lesson_models import SOLVERS as PHYSICS_REFERENCES

PHYSICS_MODELS = json.loads(
    (SOLVER_ROOT / "physics" / "lesson_models.json").read_text(encoding="utf-8"))
MATH_MODELS = json.loads(
    (SOLVER_ROOT / "mathematics" / "lesson_models.json").read_text(encoding="utf-8"))


def lesson_skeleton(key, model, subject="物理"):
    namespace = "PHYS" if subject == "物理" else "MATH"
    api = namespace + "." + model["api"]
    numeric_limits = "正数范围 1e-9 到 1e9，其余数值的绝对值至多 1e9，并遵守题型范围。" if subject == "物理" else ""
    prefix = model["prefix"]
    inputs = "、".join(f"{name}（{meaning}）" for name, meaning in model["inputs"].items())
    fields = "、".join(f"{name}（{meaning}）" for name, meaning in model["fields"].items())
    cases = json.dumps(list(model["cases"].values()), ensure_ascii=False, separators=(",", ":"))
    reference = (PHYSICS_REFERENCES if subject == "物理" else MATH_REFERENCES)[model["api"]]
    readouts = [{field: result[field] for field in model["fields"]}
                for result in map(reference, model["cases"].values())]
    sample = json.dumps(readouts[0], ensure_ascii=False, separators=(",", ":"))
    states = {field: sorted({row[field] for row in readouts if isinstance(row[field], str)})
              for field in model["fields"]}
    state_values = json.dumps({field: values for field, values in states.items() if values},
                              ensure_ascii=False, separators=(",", ":"))
    return {
        "id": ("physics-" if subject == "物理" else "math-") + key,
        "subject": subject, "patterns": model["patterns"],
        "visual_type": model["visual"], "api": model.get("draw"), "solver_api": api,
        "lesson_model": model, "layout": model["layout"],
        "controls": "每个参数使用真实可见控件，变化时重新求解并刷新读数、图示。",
        "solver_contract": (
            f'{model["assumptions"]} 输入字段：{inputs}。{numeric_limits}'
            '参数控件分别标记 data-solver-input="字段名"；'
            '数值优先使用 type=number step=any，枚举用 select。'
            f'初始状态可用验收表首行。每个控件的范围和精度必须能达到以下验收输入：{cases}。'
            f'每次 render 先保存 window.__{prefix}_REQUEST__，调用 const result={api}(request)，'
            f'保存 window.__{prefix}_RESULT__。可见读数用 data-solver-field 标记：{fields}。'
            f'验收表首行对应的真实输出：{sample}。验收中的状态原文：{state_values}。'
            '状态判断使用求解器的实际字符串，禁止猜测或转换成英文枚举；教学解释另用独立元素。'
            '每次求解成功后调用 VIS.bindSolverReadouts(result)，由平台按字段直接绑定原值。'
            '结果标签和单位置于标记外。若没有结果，调用 VIS.bindSolverReadouts(null) 清空旧读数。'
            '如需保留两位小数，将近似值显示在标记外。绘图与读数使用同一 result。'
            '若求解抛错，清空结果、图和旧读数，'
            '并在 data-solver-error 元素中显示错误。'
        ),
    }


SCENE_SKELETONS = [
    {
        "id": "chemistry-solubility-ksp", "subject": "化学",
        "patterns": r"Ksp|K_sp|溶度积|溶解平衡|共同离子效应|沉淀溶解平衡|溶解度积",
        "visual_type": "apparatus", "api": "CHEM.solubility",
        "solver_api": "CHEMSOLVER.solveSolubilityEquilibrium",
        "layout": "演示区只画难溶盐晶体、溶液离子和可逆溶解/结晶过程；参数区调整 Ksp 与各溶解离子的初始浓度；结果区分别显示纯方程、离子积表达式、初始离子积 Q、饱和状态和摩尔溶解度。",
        "controls": "用 data-chem-ksp-value 标记 Ksp 数值控件；按离子化学计量顺序用 data-chem-ksp-ion-index 标记各离子的初始浓度输入框。控件必须是可精细输入小浓度的 number input（min=0、step=any）；每次变化都重新调用求解器并更新读数和 CHEM.solubility 图。",
        "solver_contract": "请求为 {solid_formula:'CaF2',Ksp:4e-11,ions:[{formula:'Ca',charge:2,coefficient:1,initial_concentration_mol_L:0},{formula:'F',charge:-1,coefficient:2,initial_concentration_mol_L:0}]}。离子、整数电荷及系数由知识/页面明确给出，不猜测价态；求解器先检查离子化学计量能否还原固体化学式且电荷和为 0，再按 Q=Π[cᵢ]ᵛⁱ 分类未饱和/饱和/过饱和。未饱和时用对数空间二分法解 Ksp=Π(cᵢ,0+νᵢs)^νⁱ，得到共同离子背景下的额外摩尔溶解度；离子积超过 Ksp 时报告有沉淀倾向，不计算沉淀量。暴露 window.__CHEM_KSP_REQUEST__ / window.__CHEM_KSP_RESULT__；`data-chem-ksp-equation` 只放 result.dissolution_equation，禁止附加 Q 表达式、状态提示或其他文案；补充的 Q 表达式放在独立 `data-chem-ksp-expression`；Q、状态和 s 分别用 data-chem-ksp-ion-product、data-chem-ksp-state、data-chem-ksp-solubility 标记。状态必须显示中文“不饱和/饱和/过饱和”；过饱和时 s 显示“无定义（过饱和）”或“不计算（过饱和）”。同一结果传给 CHEM.solubility(cv,result)。页面变形必须实际提高 Ksp、增加共同离子浓度，并将 Q/Ksp 变形到临界点下方/等于/上方。首版按理想稀溶液、固定温度下给定的 Ksp 工作，不推算温度依赖、活度系数、络合或过饱和后的沉淀终态。",
    },
    {
        "id": "chemistry-redox-electron-balance", "subject": "化学",
        "patterns": r"氧化还原|电子守恒|电子转移|半反应法|氧化数变化|氧化数配平",
        "visual_type": "diagram", "api": "CHEM.redox",
        "solver_api": "CHEMSOLVER.solveRedox",
        "layout": "②演示区只展示氧化数变化与电子转移图；③参数区明确显示酸性/碱性条件和物种顺序验证控件；④结果区显示带电荷的最简离子方程式、氧化/还原元素、失电子/得电子数与守恒结论。",
        "controls": "给定反应物、生成物化学式、电荷、物态和反应介质；每次重算都暴露请求/结果。保留“交换物质顺序验证”按钮：反转反应物及生成物数组后重算，用于真实页面层变形测试。",
        "solver_contract": "输入 {medium:'acidic'|'basic'|'酸性'|'碱性',reactants:[{formula,charge,phase?}],products:[{formula,charge,phase?}]}。反应物/生成物核心物种由教师/需求明确给出，必须提供正确整数电荷；H+ 与 OH- 由求解器按介质自动补入，H2O 可作为显式核心物种（如 H2O2 歧化）。内部枚举仅 9 种固定的 H2O 与 H+/OH- 侧别组合，再调用精确原子/电荷配平；从常见氧化数规则推导氧化数分布，检查每个元素的升降与电子得失相等。输出带电荷和下标的最简方程式、系数、氧化数变化、电子守恒、原子/电荷计数。每次 render 调用 CHEMSOLVER.solveRedox(request)，暴露 window.__CHEM_REDOX_REQUEST__ / window.__CHEM_REDOX_RESULT__，再把同一结果传给 CHEM.redox(cv,result)。方程式、电子数和变化表分别标记 data-chem-redox-equation、data-chem-redox-electrons、data-chem-redox-changes；交换顺序按钮标记 data-chem-redox-reorder，反转两侧物种顺序后同样重新调用求解器。首版只处理常见且氧化数能唯一判定的化学式；不预测产物、不判定反应热力学可行性或动力学；无法唯一识别氧化数、输入物种不足或守恒失败时必须显示错误。",
    },
    {
        "id": "chemistry-precipitation-quantitative", "subject": "化学",
        "patterns": r"沉淀反应|生成沉淀|沉淀质量|沉淀物质的量|硫酸钡|氯化银|碳酸钙沉淀|氢氧化铜|氢氧化铁|氢氧化镁",
        "visual_type": "apparatus", "api": "CHEM.precipitation",
        "solver_api": "CHEMSOLVER.solvePrecipitation",
        "layout": "②演示区只展示混合前后烧杯和固体沉淀颗粒；参数区调整两份溶液浓度、体积、单位和反应进度；结果区展示沉淀化学式/质量、限量试剂、净离子方程式与守恒检查。",
        "controls": "两份溶液分别提供浓度、体积、单位控件，反应进度提供 0–1 控件；所有控件变化都重建 solutions 请求并调用 CHEMSOLVER.solvePrecipitation，使用同一结果更新沉淀质量、离子方程式和 CHEM.precipitation。",
        "solver_contract": "输入 {solutions:[{formula,concentration_mol_L,volume,volume_unit:'mL'|'L'},...两份],progress:0..1}。首版只接受目录中明确列出的 AgNO3/NaCl、BaCl2/Na2SO4、CaCl2/Na2CO3、CuSO4/NaOH、FeCl3/NaOH、MgSO4/NaOH 配对，其他组合必须显示不支持错误，不能猜测产物或判成无沉淀。每次变化调用 CHEMSOLVER.solvePrecipitation(request)，暴露 window.__CHEM_PRECIP_REQUEST__ / window.__CHEM_PRECIP_RESULT__；将原子计量、浓度体积换算、限量试剂、沉淀物质的量与质量、净离子方程式都从同一结果读取。每份溶液控件使用 data-chem-precip-concentration-index、data-chem-precip-volume-index、data-chem-precip-unit-index；进度使用 data-chem-precip-progress；可见分子方程式、净离子方程式、沉淀质量分别使用 data-chem-precip-equation、data-chem-precip-net-ionic、data-chem-precip-mass；沉淀质量以 g 显示至少保留三位小数，或换算为 mg；实验图调用 CHEM.precipitation(cv,result)。模型仅覆盖目录中的定性完全沉淀，不模拟 Ksp/溶解平衡、络合、沉淀纯度或副反应。",
    },
    {
        "id": "chemistry-solution-mixing-stoichiometry", "subject": "化学",
        "patterns": r"溶液混合|混合.{0,12}溶液|溶液.{0,12}(?:混合|浓度|体积|限量试剂|理论产量)|浓度.{0,12}(?:毫升|体积|混合|限量试剂)",
        "visual_type": "apparatus", "api": None,
        "solver_api": "CHEMSOLVER.solveSolutionMixing",
        "layout": "演示区显示混合前的各溶液和混合后的反应现象；参数区调整各反应物溶液的浓度、体积和反应进度；结果区显示限量试剂、剩余量、产物量和守恒。",
        "controls": "每个反应物溶液均提供带索引标记的浓度、体积和单位控件；从控件读取状态，调用 CHEMSOLVER.solveSolutionMixing，所有读数由同一结果更新。",
        "solver_contract": "输入 {reactants:[化学式或对象],products:[化学式或对象],solutions:[{concentration_mol_L,volume,volume_unit:'mL'|'L'}...] 与反应物顺序对应,progress:0..1}。调用 CHEMSOLVER.solveSolutionMixing(request)，暴露 window.__CHEM_MIX_REQUEST__ 与 window.__CHEM_MIX_RESULT__。页面控件分别用 data-chem-mix-concentration-index、data-chem-mix-volume-index、data-chem-mix-unit-index 和 data-chem-mix-progress 标记；每次变化都重建请求并重新求解。求解器用 n=cV 将各溶液换算为 mol，再复用配平与反应计量算法；方程、限量试剂、剩余量、产物量、元素/电荷守恒均读取同一结果。可见方程式标记 data-chem-mix-equation。当前只支持 mol/L 与 mL/L，不预测产物、不从质量换算、不模拟平衡。",
    },
    {
        "id": "chemistry-stoichiometry-limiting-reagent", "subject": "化学",
        "patterns": r"限量试剂|过量试剂|理论产量|反应物剩余|反应进度|反应物用量|化学计量",
        "visual_type": "apparatus", "api": None,
        "solver_api": "CHEMSOLVER.solveStoichiometry",
        "layout": "演示区展示给定反应的反应物、生成物与反应进度；参数区调整反应物物质的量和反应进度；结果区显示限量/过量试剂、剩余量、生成量及元素守恒。",
        "controls": "用 data-chem-stoich-amount-index 标记每种反应物的物质的量控件，用 min=0、max=1 的 input 控件标记 data-chem-stoich-progress；每次控件变化都重建请求并调用 CHEMSOLVER.solveStoichiometry。输入范围应允许对限量试剂临界配比进行下方/等值/上方实测。方程、系数、限量试剂、剩余量、生成量和守恒结果必须从同一返回对象读取。",
        "solver_contract": "输入 {reactants:[化学式或{formula,charge?,phase?}],products:[化学式或对象],initial_amounts_mol:[与反应物顺序对应的初始物质的量],progress:0..1}。调用 CHEMSOLVER.solveStoichiometry(request)，暴露 window.__CHEM_STOICH_REQUEST__ 与 window.__CHEM_STOICH_RESULT__。求解器内部先精确配平给定反应，再以 ξ_max=min(n_i/ν_i)、ξ=progress·ξ_max 计算限量试剂、反应物消耗/剩余、产物生成量，并复核元素/电荷守恒。可见方程式放在 data-chem-stoich-equation 元素中并读取 result.equation；所有读数读取同一结果。质量审查会实际操作数量和进度控件，检查全部物质的量同比缩放、进度 0/0.5/1、限量试剂临界点下方/等值/上方，并用 Python 参考实现复算。物质的量单位为 mol；当前不从质量/浓度推算物质的量，不预测产物，不处理可逆平衡。输入或守恒校验失败时显示错误状态，不回退手写读数。",
    },
    {
        "id": "chemistry-equation-balance", "subject": "化学",
        "patterns": r"化学方程式.{0,30}配平|方程式.{0,12}配平|配平.{0,40}(?:化学)?(?:反应)?方程式|原子守恒",
        "visual_type": "diagram", "api": None,
        "solver_api": "CHEMSOLVER.balanceEquation",
        "layout": "演示区以化学方程式为主体，配套展示反应前后各元素原子数对照；参数/操作区允许逐步尝试系数，结果区显示最简整数系数与独立守恒核验。",
        "controls": "从明确给定的反应物和生成物构造求解请求；化学式、系数、方程式和原子数必须来自 CHEMSOLVER.balanceEquation 的同一结果。逐个输入学生尝试的系数，反应物/生成物输入分别标记 data-chem-balance-coefficient-side 和 data-chem-balance-coefficient-index；每次输入变化调用 CHEMSOLVER.checkCoefficients，并更新 window.__CHEM_BALANCE_STUDENT_COEFFICIENTS__ 与 window.__CHEM_BALANCE_STUDENT_CHECK__。在 data-chem-balance-student-check 输出中同时反映 balanced 和 primitive 状态。不得让模型猜系数、猜生成物或用文字自报守恒。",
        "solver_contract": "输入 {reactants:[化学式或{formula,charge?,phase?}],products:[化学式或对象]}。调用 CHEMSOLVER.balanceEquation(request)，将原始请求和返回结果分别暴露到 window.__CHEM_BALANCE_REQUEST__ 与 window.__CHEM_BALANCE_RESULT__。返回的 coefficients 是反应物/生成物两侧最简正整数系数；equation、atom_counts、charge_counts 和 checks 都必须读取同一 result。可见方程式放在带 data-chem-balance-equation 属性的元素中，并直接以 result.equation 更新。学生系数输入使用 data-chem-balance-coefficient-side='reactants|products' 与 data-chem-balance-coefficient-index 标记；每次变化读取两侧系数数组，调用 CHEMSOLVER.checkCoefficients(request, values)，并暴露 window.__CHEM_BALANCE_STUDENT_COEFFICIENTS__ 和 window.__CHEM_BALANCE_STUDENT_CHECK__。data-chem-balance-student-check 必须同步显示 balanced / primitive 状态，供浏览器将全部系数同时乘以 2 后检查“仍配平但非最简”。支持嵌套括号/中括号、元素下标和水合物点号；离子电荷以对象 charge 整数提供。当前只平衡给定物质，不推断反应产物；多解、无正系数解或求解失败时显示错误状态，禁止回退为模型手写答案。",
    },
    {
        "id": "chemistry-acid-base-titration", "subject": "化学",
        "patterns": r"酸碱中和滴定|酸碱滴定|中和滴定|滴定|当量点",
        "visual_type": "apparatus", "api": "CHEM.titration",
        "solver_api": "CHEMSOLVER.solveAcidBaseTitration",
        "layout": "②区只展示滴定管向锥形瓶逐滴加入滴定液的实验主图；包含铁架台、滴定管刻度、锥形瓶、指示剂颜色和当量点提示。④区单独展示 pH—滴入体积曲线，在曲线上标出理论当量点和当前输入位置。",
        "controls": "控制酸/碱浓度、样品体积和滴定液体积/单位；改变任何一个值都重新调用 CHEMSOLVER.solveAcidBaseTitration，并将同一个结果传给 CHEM.titration 与所有读数。",
        "solver_contract": "首版只适用于强一元酸 HCl/HBr/HI/HNO3/HClO4 与强一元碱 LiOH/NaOH/KOH，按 1:1 完全中和；按 25°C、理想溶液处理，并纳入水的自电离以稳定当量点附近 pH。弱酸弱碱、多元酸碱、活度系数和指示剂误差不在适用范围。请求格式为 {acid:{formula,concentration_mol_L,volume,volume_unit},base:{formula,concentration_mol_L,volume,volume_unit}}；每次参数更新调用 CHEMSOLVER.solveAcidBaseTitration(request)，暴露 window.__CHEM_TITRATION_REQUEST__ / window.__CHEM_TITRATION_RESULT__。体积输入标记 data-chem-titration-acid-volume / data-chem-titration-base-volume，浓度标记 data-chem-titration-acid-concentration / data-chem-titration-base-concentration，单位选择标记 data-chem-titration-acid-unit / data-chem-titration-base-unit。显示方程式用 data-chem-titration-equation；pH、当量体积、过量酸碱量均从 result 读取；绘制装置调用 CHEM.titration(cv,result)，曲线上的每个样本都必须再次调用 CHEMSOLVER.solveAcidBaseTitration 后交给 CHEM.titrationCurve(cv,samples,result)。求解失败时显示错误状态，不得手写回退。",
    },
    {
        "id": "chemistry-gas-collection", "subject": "化学",
        "patterns": r"气体制取|气体收集|排水集气|集气方式|制取氢气|收集氢气|制取二氧化碳|收集二氧化碳|制取氧气|气体体积定量|气体体积|目标气体|理想气体|PV\s*=\s*nRT|制得\s*(?:H2|O2|CO2)",
        "visual_type": "apparatus", "api": "CHEM.gasCollection",
        "solver_api": "CHEMSOLVER.solveGasCollection",
        "layout": "②演示区只展示实验器材图：反应发生器、导气管以及排水集气槽或气体注射器；用器材细节体现玻璃、液面和气泡，不在演示区展示步骤清单。",
        "controls": "控制各反应物物质的量、反应进度、温度、总压强和集气方式；每次改变都调用 CHEMSOLVER.solveGasCollection，以同一个结果更新方程、限量试剂、气体体积、读数与 CHEM.gasCollection。",
        "solver_contract": "请求为 {reactants:[化学式或{formula,phase}],products:[化学式或{formula,phase}],initial_amounts_mol:[与反应物顺序对应],progress:0..1,gas_formula,temperature_c,total_pressure_kpa,collection_method:'dry'|'over_water'}。目标气体必须是唯一一个 phase 为 g/gas/气态的生成物。内部调用 CHEMSOLVER.solveStoichiometry 求限量试剂与实际产气量，再用 PV=nRT 计算体积；R=8.31446261815324 L·kPa·mol⁻¹·K⁻¹。水上集气使用 Antoine 水蒸气压（0–100°C），按 P干气=P总压−P水蒸气修正。暴露 window.__CHEM_GAS_REQUEST__ / window.__CHEM_GAS_RESULT__。各反应物用 data-chem-gas-amount-index，进度/温度/总压/集气方式分别用 data-chem-gas-progress、data-chem-gas-temperature、data-chem-gas-pressure、data-chem-gas-method 标记；可见方程式和气体体积分别用 data-chem-gas-equation / data-chem-gas-volume 标记。所有读数和 CHEM.gasCollection(cv,result) 必须使用同一求解结果；求解失败时显示错误状态。只计算给定反应、指定目标气体和理想气体体积，不预测产物、反应收率、气体溶解或泄漏。",
    },
    {
        "id": "chemistry-reaction-compare", "subject": "化学",
        "patterns": r"置换反应|硫酸铜|金属活动性|酸碱中和|溶液变色|反应前后|化学反应",
        "visual_type": "apparatus", "api": "CHEM.scene",
        "solver_api": "CHEMSOLVER.balanceEquation",
        "layout": "反应前后双烧杯对照 + 关键现象标签 + 方程式条。参数区保留影响反应的变量；结果区显示现象、产物和守恒核验。",
        "controls": "只保留有科学依据的反应物浓度、体积、质量或反应进度；将反应物、生成物交给 CHEMSOLVER.balanceEquation 配平，方程式和原子数不得手写，并将求解器结果与反应前后溶液/固体变化一起传入场景库。",
        "solver_contract": "反应方程必须由明确的反应物和生成物构造请求，调用 CHEMSOLVER.balanceEquation(request)，暴露 window.__CHEM_BALANCE_REQUEST__ 与 window.__CHEM_BALANCE_RESULT__。可见方程式放在带 data-chem-balance-equation 属性的元素中，并直接以 result.equation 更新。方程式、系数、原子数和电荷数都读取同一结果；结果 checks.ok 为 false 或求解失败时显示错误状态，不得回退手写方程。此求解器只配平给定物质，不推断生成物。",
    },
    {
        "id": "chemistry-separation-stages", "subject": "化学",
        "patterns": r"粗盐提纯|过滤|蒸发结晶|溶解.{0,6}过滤|分离提纯|结晶实验|实验室制取",
        "visual_type": "process", "api": "CHEM.stages",
        "layout": "按真实实验顺序显示阶段卡；每阶段使用匹配的烧杯、漏斗或蒸发皿，并标明当前物态/观察现象。",
        "controls": "用步骤切换或逐步推进控制阶段；允许调节的变量必须影响对应阶段，不要将多步骤实验画成反应双烧杯。",
    },
    {
        "id": "chemistry-molecular-model", "subject": "化学",
        "patterns": r"分子|球棍|原子模型|化学键|微观结构|空间构型",
        "visual_type": "molecular", "api": None,
        "layout": "中心分子/粒子模型 + 原子与键图例 + 结构或计数结果；使用球棍或粒子阵列表达微观结构。",
        "controls": "参数控制原子种类、数目、键或构型；不得将反应宏观器材骨架硬套到分子模型。",
    },
    {
        "id": "physics-thin-lens", "subject": "物理",
        "patterns": r"凸透镜",
        "visual_type": "apparatus", "api": "PHYS.optics", "solver_api": "PHYS.solveThinLens",
        "layout": "光具座、凸透镜、物体、光屏和焦点标注，像的位置由成像计算决定。",
        "controls": "提供物距和焦距数值控件。典型状态覆盖物距小于、等于、大于焦距，以及等于两倍焦距；移动光屏不改变理论像距。",
        "solver_contract": "物距和焦距使用 type=number 或 range 的控件，分别标记 data-solver-input=\"u\"、\"f\"。每次 render 从控件读取厘米数值 {u,f}，两者均为 0.000001 至 1000000 的有限数字。先保存 window.__PHYS_LENS_REQUEST__，使用 const result=PHYS.solveThinLens(request)，保存 window.__PHYS_LENS_RESULT__，再调用 PHYS.optics(cv,cfg,result)。可见读数用 data-solver-field=\"image_distance_cm\"（像距，保留正负号）、\"magnification\"（带符号放大率）、\"state\"（直接显示结果原文）标记。每个标记只放值，标签和单位在标记外，非空数值至少保留七位有效数字或直接显示原值。u=f 时前两个字段为 null，读数显示破折号 —。求解失败时清空结果对象、读数和画布，在 data-solver-error 元素中显示错误。仅适用于理想薄凸透镜。",
    },
    # 凸透镜由上面的 physics-thin-lens 专用骨架承载，避免生成重复 scene id。
    *(lesson_skeleton(key, model) for key, model in PHYSICS_MODELS.items() if key != "thinLens"),
    *(lesson_skeleton(key, model, "数学") for key, model in MATH_MODELS.items()),
    {
        "id": "physics-optics-bench", "subject": "物理",
        "patterns": r"凸透镜|光具座|物距|像距|透镜成像",
        "visual_type": "apparatus", "api": "PHYS.optics",
        "layout": "光具座 + 光学元件 + 物/像 + 带方向的光路 + 焦点和物像距标注。平面镜/折射变体需按其原理調整，不可誤用凸透鏡模型。",
        "controls": "物距、焦距、屏位置等控件要与成像位置、光线和公式读数共用状态。",
    },
    {
        "id": "physics-circuit-lab", "subject": "物理",
        "patterns": r"欧姆定律|电路|电压|电流|电阻|串联|并联",
        "visual_type": "apparatus", "api": None,
        "solver_api": "CIRCUIT.solve",
        "layout": "电源、开关、导线、用电器和电表组成可读电路；导线与元件端点必须由求解器模型的节点连接关系绘制。",
        "controls": "电压、电阻、开关或接线状态改变时，每次 render 都调用 CIRCUIT.solve、CIRCUIT.bindMeters 和 CIRCUIT.draw；画面、表头、公式与 __DATA__ 全部从同一个 solverResult 读取。",
        "solver_contract": "模型格式：{ground:'0',layout:{nodes:{'0':{x:.8,y:.8},n1:{x:.15,y:.2},n2:{x:.8,y:.2}}},components:[{id,type:'voltage_source',positive,negative,volts},{id,type:'resistor',from,to,ohms},{id,type:'ammeter',from,to},{id,type:'voltmeter',from,to,inputOhms:1e7},{id,type:'current_source',from,to,amps},{id,type:'switch',from,to,closed}]}。欧姆定律页使用最小清晰拓扑：电源→开关→电流表→被测电阻→电源负极；电压表并联在被测电阻的两个节点上。电源 volts 必须直接取当前电压控件状态，电阻 ohms 必须取当前电阻控件状态；不得同时串入未要求的额外电阻后仍声称 I=U/R。电流表用理想零压降串联支路 ammeter，电压表用 inputOhms 默认 10 MΩ 的并联支路 voltmeter，不得把电流表伪装成 current_source 或把电表只画成文字。layout.nodes 为各节点 0~1 归一化位置，元件节点之间留足绘图距离；求解器绘图器根据 components 的 from/to 端点自动连线并自动避让标签，禁止另写一套与模型分离的电路导线。每次 render 必须执行 var solverResult=CIRCUIT.solve(model)，赋给 window.__CIRCUIT_MODEL__ 与 window.__CIRCUIT_RESULT__，再调用 CIRCUIT.draw(cv,model,solverResult) 和 CIRCUIT.bindMeters(solverResult)。电流表 DOM 的 data-circuit-current-for 绑定到 ammeter 元件 ID；电压表 DOM 的 data-circuit-voltage-for 绑定到被测电阻元件 ID（其两端与 voltmeter 并联），公式、读数和 __DATA__ 中的数值必须调用 CIRCUIT.meter(solverResult,'元件ID','current'/'voltage') 直接读取同一个求解结果，禁止独立手算、缓存旧值或使用其他公式重算。不可手算表读数或求解失败后回退公式/示意图；solverResult.checks.ok 为 false 或抛错时显示清楚的错误状态并清空/禁用正常读数。",
    },
    {
        "id": "math-square-pyramid-section-3d", "subject": "数学",
        "patterns": r"正四棱锥截面|四棱锥截面|平面截.{0,5}(正四棱锥|四棱锥)|截(正)?四棱锥|四棱锥被平面截",
        "visual_type": "geometry", "api": "MATH.squarePyramidSection", "solver_api": "MATH.solveSquarePyramidCut",
        "layout": "可旋转真 3D 正四棱锥 + 截面高亮 + 底面顶点与锥顶标签 + 截面边数、面积和体积比例。",
        "controls": "底面边长、锥高、截平面法向量与偏移量共同驱动图形；复位视角调用 MATH.resetView(cv)。",
        "solver_contract": "当前只支持正四棱锥：正方形底面中心与锥顶垂直对齐。每次 render 先调用 MATH.solveSquarePyramidCut({base,height,n,offset})，再将同一结果传给 MATH.squarePyramidSection(cv,cfg,result)。顶点、截面、边数、面积、体积和 __GEO__ 必须来自同一求解结果；禁止另写截面求交。该立体截面最多为五边形；无交截面时显示无截面。"
    },
    {
        "id": "math-triangular-prism-section-3d", "subject": "数学",
        "patterns": r"三棱柱截面|平面截.{0,5}三棱柱|截三棱柱|三棱柱被平面截",
        "visual_type": "geometry", "api": "MATH.triangularPrismSection", "solver_api": "MATH.solveTriangularPrismCut",
        "layout": "可旋转真 3D 三棱柱 + 截面高亮 + 六个顶点标签 + 截面边数、面积和体积比例。",
        "controls": "底边、底面高、棱柱长、截平面法向量与偏移量共同驱动图形；复位视角调用 MATH.resetView(cv)。",
        "solver_contract": "当前模型为直三棱柱，底面是以底边为水平边、顶点位于中垂线上的等腰三角形。每次 render 先调用 MATH.solveTriangularPrismCut({base,triangleHeight,length,n,offset})，再将同一结果传给 MATH.triangularPrismSection(cv,cfg,result)。计算出的顶点、边数、面积、体积和图示必须共用结果对象；不得另写求交或手工猜截面边数。"
    },
    {
        "id": "math-cuboid-section-3d", "subject": "数学",
        "patterns": r"长方体截面|长方体切面|平面截.{0,5}长方体|截长方体|长方体被平面截",
        "visual_type": "geometry", "api": "MATH.cuboidSection", "solver_api": "MATH.solveCuboidCut",
        "layout": "可旋转真 3D 长方体 + 截面高亮 + 顶点/棱标注 + 截面边数、面积和体积比例。",
        "controls": "长、宽、高与截平面法向量、偏移量共同驱动图形；复位视角必须调用 MATH.resetView(cv)。",
        "solver_contract": "每次 render 先调用 MATH.solveCuboidCut({dimensions:[长,宽,高],n,offset})，再将同一对象传给 MATH.cuboidSection(cv,cfg,result)。坐标原点位于长方体中心，尺寸沿 x/y/z 轴。求解结果含顶点、边数、形状、面积和平面残差；画面、标签、公式、记录和 __GEO__ 必须由同一结果驱动，不得另写截面求交。凸长方体截面最多 6 边；无交截面时应明确显示无截面。"
    },
    {
        "id": "math-solid-volume", "subject": "数学",
        "patterns": r"立体体积|组合体体积|体积计算|体积公式|圆柱体体积|圆锥体体积|球体体积|棱柱体积|棱锥体积|圆柱(?:与圆锥)?的体积|圆锥的体积|体积与表面积",
        "visual_type": "geometry", "api": "MATH.solveSolidVolume", "solver_api": "MATH.solveSolidVolume",
        "layout": "按输入尺寸绘制目标立体，展示体积表达式、数值结果和立方单位；数值来自结构化体积求解结果。",
        "controls": "尺寸参数变化后重新计算；组合体仅对明确声明为互不重叠的组成部分求和。切割问题须用体积分割守恒复核。",
        "solver_contract": "支持 cube/cuboid/triangular_prism/square_pyramid/cylinder/cone/sphere。页面每次 render 调用 MATH.solveSolidVolume(request)，将 request/result 暴露到 window.__MATH_VOLUME_REQUEST__ 和 window.__MATH_VOLUME_RESULT__；体积读数必须读取 result.volume/result.unit。分割问题另外调用 MATH.checkVolumePartition(original,[parts]) 并暴露检查结果。",
    },
    {
        "id": "math-spatial-metrics", "subject": "数学",
        "patterns": r"空间距离|异面直线距离|点到直线距离|点到平面距离|线面角|二面角|线线角|空间角度|线面距离|面面距离",
        "visual_type": "geometry", "api": "MATH.solveSpatialMetrics", "solver_api": "MATH.solveSpatialMetrics",
        "layout": "空间点线面示意图 + 当前距离/角度及计算对象标识；数值结果从结构化空间求解请求读取。",
        "controls": "改变点、方向向量或平面法向量时重新求解；角度按较小角输出并标明单位。",
        "solver_contract": "直线格式为 line_point + line_direction，平面格式为 plane_normal + plane_offset（n·x=offset）。页面每次 render 调用 MATH.solveSpatialMetrics(request)，将请求与结果分别暴露到 window.__MATH_SPATIAL_REQUEST__ 和 window.__MATH_SPATIAL_RESULT__；距离/角度读数必须使用 result.value 和 result.unit，角度在 0°–90°。",
    },
    {
        "id": "math-sphere-section", "subject": "数学",
        "patterns": r"球体截面|球截面|平面截球|球面截面|球被平面截",
        "visual_type": "geometry", "api": "MATH.sphereSection", "solver_api": "MATH.solveSphereCut",
        "layout": "球体主图 + 截面圆高亮 + 截面圆心、半径和面积；使用同一解析求解结果。",
        "controls": "球半径、截平面法向量和偏移量驱动画面；相切与无交状态要有明确呈现。",
        "solver_contract": "模型为球心在原点的球体。每次 render 调用 MATH.solveSphereCut({radius,n,offset})，将同一结果传给 MATH.sphereSection(cv,cfg,result)，并暴露 window.__MATH_SPHERE_RESULT__。截面圆心、半径、面积和边界必须来自该求解结果。",
    },
    {
        "id": "math-cone-net-unfolding", "subject": "数学",
        "patterns": r"圆锥(?:的)?(?:侧面)?(?:展开图|展开|侧面积展开)|圆锥侧面展开图",
        "visual_type": "geometry", "api": None, "solver_api": "MATH.solveConeNet",
        "layout": "左侧展示圆锥侧面扇形与底圆展开图，右侧展示折叠后的圆锥；标注母线、扇形角、底面周长和面积守恒。",
        "controls": "调整底面半径、高或展开图尺寸后重新求解；无效扇形尺寸须明确提示，不得显示成合格圆锥。",
        "solver_contract": "输入 {radius,height,net:{sector_radius,sector_angle_deg,cap_radius},segments}。每次状态更新调用 MATH.solveConeNet(request)，暴露 window.__MATH_CONE_NET_REQUEST__ 与 window.__MATH_CONE_NET_RESULT__。扇形半径须等于母线 sqrt(r²+h²)，扇形弧长须等于底面周长 2πr，扇形角须为 360r/l 度，底圆半径须等于 r；展开前后总面积守恒。有效状态用 result.sector_boundary 绘制扇形、result.base_boundary 绘制底圆，并用 result.side_grid/result.apex 绘制折叠圆锥；result.valid 为 false 时显示错误，不得回退为合格图。",
    },
    {
        "id": "math-cone-section", "subject": "数学",
        "patterns": r"圆锥截面|平面截圆锥|圆锥被平面截|圆锥体截面",
        "visual_type": "geometry", "api": "MATH.coneSection", "solver_api": "MATH.solveConeCut",
        "layout": "直圆锥主图 + 截平面交线高亮 + 截面类型与面积；图形和结果由同一圆锥求解结果驱动。",
        "controls": "底面半径、高度、截平面法向量和偏移量驱动画面；每次改变后重新求解。",
        "solver_contract": "模型为底面 z=-height/2、顶点 z=height/2、轴沿 z 轴的直圆锥。每次 render 调用 MATH.solveConeCut({radius,height,n,offset})，将同一结果传给 MATH.coneSection(cv,cfg,result)，并暴露 window.__MATH_CONE_RESULT__。截面面积和边界不得在页面内另算；无交、相切、过顶点状态须正确表达。",
    },
    {
        "id": "math-cylinder-net-unfolding", "subject": "数学",
        "patterns": r"圆柱(?:的)?(?:侧面)?(?:展开图|展开|表面积展开)|圆柱侧面展开图",
        "visual_type": "geometry", "api": None, "solver_api": "MATH.solveCylinderNet",
        "layout": "左侧展示圆柱侧面矩形与两个底圆的展开图，右侧展示折叠后的圆柱；标明周长、高度和面积守恒。",
        "controls": "调整圆柱半径、高度或展开图尺寸后重新求解；无效尺寸须清楚提示，不得仍显示为正确展开结果。",
        "solver_contract": "输入 {radius,height,net:{lateral_width,lateral_height,cap_radii:[r1,r2]},segments}。每次状态更新调用 MATH.solveCylinderNet(request)，暴露 window.__MATH_CYLINDER_NET_REQUEST__ 与 window.__MATH_CYLINDER_NET_RESULT__。矩形宽须等于 2πr、高须等于 h，两个底圆半径均须等于 r；展开面积须与 2πrh+2πr² 守恒。有效状态下的折叠圆柱用 result.surface_grid 和 result.top_cap/bottom_cap 绘制；result.valid 为 false 时显示错误状态，不得回退为合格图。",
    },
    {
        "id": "math-cylinder-section", "subject": "数学",
        "patterns": r"圆柱截面|平面截圆柱|圆柱被平面截|圆柱体截面",
        "visual_type": "geometry", "api": "MATH.cylinderSection", "solver_api": "MATH.solveCylinderCut",
        "layout": "直圆柱主图 + 截平面交线高亮 + 截面面积与截线类型；演示图必须由圆柱求解结果驱动。",
        "controls": "半径、高度、平面法向量和偏移量驱动画面；参数变化后重新求解，提供复位。",
        "solver_contract": "模型为轴沿 z 轴、中心在原点的直圆柱。每次 render 调用 MATH.solveCylinderCut({radius,height,n,offset})，将同一结果传给 MATH.cylinderSection(cv,cfg,result)，并暴露 window.__MATH_CYLINDER_RESULT__。面积和截面边界不得在页面内另行计算；无交/相切状态必须正确显示。",
    },
    {
        "id": "math-cube-cut-3d", "subject": "数学",
        "patterns": r"正方体截面|平面截.{0,5}(正方体|立方体)|截正方体|截立方体",
        "visual_type": "geometry", "api": "MATH.cubeCut", "solver_api": "MATH.solveCubeCut",
        "layout": "可旋转真 3D 立方体 + 截平面与截面高亮 + 顶点/边标注 + 边数面积结果。",
        "controls": "倾角、方位和偏移映射到 theta/phi/t；提供恢复默认视角按钮时必须调用 MATH.resetView(cv)。",
        "solver_contract": "页面每次 render 用同一组参数先调用 MATH.solveCubeCut({a, n, offset})，将返回对象存入 window.__MATH_CUBE_RESULT__，然后调用 MATH.cubeCut(cv, cfg, result) 绘图。n·x=offset 定义截平面；结果含截面顶点、边数、形状、面积和平面残差。所有标签、边数、面积、公式与 __GEO__ 必须读取该返回对象，禁止页面另写截面求交或用文案猜边数。边数只允许正方体平面截面能形成的 3–6 边；无有效截面时明确显示无截面。"
    },
    {
        "id": "math-quadratic", "subject": "数学",
        "patterns": r"二次函数|抛物线|一元二次方程",
        "visual_type": "graph", "api": "MATH.funcPlot", "solver_api": "MATH.solveQuadratic",
        "layout": "坐标网格、抛物线、顶点、对称轴和坐标轴交点，读数与图像共用同一结果。",
        "controls": "提供 a、b、c 数值控件。a 为零时显示错误；支持开口翻转和零个、一个、两个实根。",
        "solver_contract": "a、b、c 使用 type=number 或 range 的控件，分别标记 data-solver-input=\"a\"、\"b\"、\"c\"。每次 render 从控件读取数值 {a,b,c}，绝对值不得超过 1000000，且 |a| 至少为 0.000001。先保存 window.__MATH_QUADRATIC_REQUEST__，使用 const result=MATH.solveQuadratic(request)，保存 window.__MATH_QUADRATIC_RESULT__，再调用 MATH.funcPlot(cv,cfg,result)。可见读数用 data-solver-field 标记 vertex_x、vertex_y、axis_x、discriminant、roots、y_intercept、opening。每个标记只放值，标签和单位在标记外，数值至少保留七位有效数字或直接显示原值。roots 按升序显示，用逗号分隔，无实根时显示 —；opening 显示结果原文。求解失败时清空结果对象、读数和画布，在 data-solver-error 元素中显示错误。",
    },
    {
        "id": "math-function-exploration", "subject": "数学",
        "patterns": r"一次函数|函数图像|函数曲线|系数与图像",
        "visual_type": "graph", "api": "MATH.funcPlot",
        "layout": "坐标网格 + 函数曲线 + 关键点/对称轴/交点 + 参数变化提示。",
        "controls": "系数滑块应即时改变曲线与对应关键量；公式、图像和数据表来自同一次计算。",
    },
    {
        "id": "math-cuboid-net-folding", "subject": "数学",
        "patterns": r"长方体(?:的)?(?:展开图|展开与折叠|折叠)|(?:展开图|展开与折叠).{0,6}长方体",
        "visual_type": "geometry", "api": None, "solver_api": "MATH.solveCuboidNet",
        "layout": "长方体矩形面展开图 + 折叠后的空间视图；显示长宽高、面尺寸匹配和可折叠判定。",
        "controls": "改变长宽高或矩形面布局后重新求解；有效性提示和六面空间坐标必须由同一求解结果驱动。",
        "solver_contract": "输入 {dimensions:[长,宽,高],faces:[{x,y,width,height},...]}，六个矩形的平面位置和面宽高均须为有限正数。每次状态更新调用 MATH.solveCuboidNet(request)，暴露 window.__MATH_CUBOID_NET_REQUEST__ 与 window.__MATH_CUBOID_NET_RESULT__。求解器检查平面矩形不重叠、公共边完整等长、六面连通且恰有五条铰链，再传播 90° 折叠坐标，校验每个面的边长与其空间轴尺寸相符、六个法向互异、公共棱闭合。绘图、面尺寸提示和判定必须共用结果；不适用于曲面立体展开。",
    },
    {
        "id": "math-cube-net-folding", "subject": "数学",
        "patterns": r"(?:正方体|立方体)(?:的)?(?:展开图|展开与折叠|展开|折叠)|(?:展开图|展开与折叠).{0,6}(?:正方体|立方体)",
        "visual_type": "geometry", "api": None, "solver_api": "MATH.solveCubeNet",
        "layout": "正方体六面展开网格 + 折叠后的六面空间视图；提供有效/无效判定、面法向和公共棱闭合信息。",
        "controls": "拖动或选择六个网格面后重新求解；有效性、六面空间位置与图形必须来自同一 MATH.solveCubeNet 结果。",
        "solver_contract": "输入 {cells:[[x,y],...]}，cells 必须恰有六个不重叠的整数网格正方形。每次状态更新调用 MATH.solveCubeNet({cells,edge_length}) 并暴露 window.__MATH_CUBE_NET_REQUEST__ 与 window.__MATH_CUBE_NET_RESULT__。求解器以邻接图连通性、五条公共棱树结构、90°折叠传播后的六个不同轴向法向及公共棱端点闭合残差判定；绘图、有效性提示和折叠空间坐标均必须使用同一 result.faces。仅支持正方体六方格展开图；不适用于长方体或曲面立体。",
    },
    {
        "id": "math-spatial-geometry", "subject": "数学",
        "patterns": r"空间想象|展开与折叠|外接球|内接球|空间几何|立体几何|长方体",
        "visual_type": "geometry", "api": None,
        "layout": "立体对象主视图 + 可交互视角/步骤 + 关键几何量；图形标记与结果区使用一致的数据。",
        "controls": "旋转、展开或尺寸参数必须影响几何图形；如有视角控制，提供可工作的视角复位。",
    },
    {
        "id": "biology-photosynthesis-leaf", "subject": "生物",
        "patterns": r"光合作用|绿叶在光下制造有机物|叶片淀粉|绿叶制造淀粉",
        "visual_type": "diagram", "api": "BIO.photosynthesis",
        "no_step_flow": True,
        "layout": "只绘制实验对象主图：有自然叶形和叶脉的叶片、光照/遮光或碘液显色结果。画布不得放步骤清单、六步流程、按钮或阶段导航。",
        "controls": "实验阶段切换放在③区，通过 phase='light'|'covered'|'iodine' 更新主图；不得把操作流程画进②演示区。",
    },
    {
        "id": "biology-microscope", "subject": "生物",
        "patterns": r"显微镜|洋葱表皮|细胞观察|显微视野",
        "visual_type": "apparatus", "api": "BIO.microscope",
        "layout": "圆形视野 + 可辨认细胞/组织 + 倍率与标尺信息 + 观察记录。",
        "controls": "倍率、染色或样本参数应改变视野和可见结构；数量/尺寸读数须与图示同源。",
    },
    {
        "id": "biology-process", "subject": "生物",
        "patterns": r"光合作用|遗传|豌豆|性状分离|细胞分裂|生理过程|食物链",
        "visual_type": "diagram", "api": None,
        "layout": "②演示区只显示实验对象/结构/结果图；阶段说明和逐步操作放在③区或⑥区，不能把流程列表塞进图中。",
        "controls": "时间、条件或遗传组合驱动主图/计数；需要逐步操作时放到③区控件，提供复位，不在②区绘制步骤导航。",
    },
    {
        "id": "geography-earth", "subject": "地理",
        "patterns": r"地球自转|地球公转|昼夜交替|四季成因|太阳高度|地球光照",
        "visual_type": "diagram", "api": "GEO.earth",
        "layout": "地球球体 + 经纬网 + 太阳光照方向 + 昼夜线/季节标记。",
        "controls": "日期、倾角或自转时刻同步更新光照、位置与读数。",
    },
    {
        "id": "geography-cross-section", "subject": "地理",
        "patterns": r"地层|地质剖面|地球圈层|地形剖面|等高线",
        "visual_type": "diagram", "api": "GEO.profile",
        "layout": "地表轮廓 + 分层剖面 + 图例/高度或深度标尺。",
        "controls": "图层或剖面参数应更新对应地形/岩层，并在结果区解释空间关系。",
    },
    {
        "id": "informatics-algorithm", "subject": "信息科技",
        "patterns": r"算法|排序|二分查找|数据结构|程序流程|数据流|位串",
        "visual_type": "process", "api": "CS.flow",
        "layout": "步骤节点/数据结构 + 当前状态高亮 + 输入输出和执行次数。",
        "controls": "播放/单步/重置改变算法状态；执行序列须与参考实现一致。",
    },
    {
        "id": "physics-reflection", "subject": "物理",
        "patterns": r"光的反射|反射定律|反射角|平面镜反射|入射角与反射角",
        "visual_type": "diagram", "api": "PHYS.reflection",
        "solver_api": "PHYS.solveReflection",
        "layout": "平面镜 + 法线 + 入射光线与反射光线 + 角度标注；图形由反射定律直接给出，不做材质化渲染。",
        "controls": "提供入射角控件（0–85°），反射角与两光线夹角随同一求解结果更新。",
        "solver_contract": "请求 {incident_angle:0..85}；返回 reflected_angle（等于入射角）、angle_between（2×入射角）与 state。暴露 window.__PHYS_REFLECTION_REQUEST__ / __PHYS_REFLECTION_RESULT__；入射角控件用 data-solver-input=\"incident_angle\"，读数用 data-solver-field 标记；每次变化先调 PHYS.solveReflection，再把同一结果传给 PHYS.reflection(cv, request, result)。",
    },
    {
        "id": "chemistry-dilution", "subject": "化学",
        "patterns": r"稀释|溶质质量分数|溶液浓度|加水稀释",
        "visual_type": "apparatus", "api": "CHEM.dilution",
        "solver_api": "CHEMSOLVER.solveDilution",
        "layout": "稀释前后两只烧杯对照：液面高度表示体积，颜色深浅表示浓度；读数给出稀释后浓度与稀释倍数。",
        "controls": "母液浓度、母液体积、加水体积三个数值控件；每次变化重新求解并更新两只烧杯与读数。",
        "solver_contract": "请求 {stock_concentration_mol_L, stock_volume_ml, added_water_ml}；按 c₁V₁ = c₂V₂ 计算。暴露 window.__CHEM_DILUTION_REQUEST__ / __CHEM_DILUTION_RESULT__；控件标记 data-solver-input，读数标记 data-solver-field；每次先调 CHEMSOLVER.solveDilution，再把同一结果传给 CHEM.dilution(cv, request, result)。",
    },
    {
        "id": "chemistry-mass-conservation", "subject": "化学",
        "patterns": r"质量守恒|质量变化|反应前后质量|密闭与敞口|敞口称量",
        "visual_type": "apparatus", "api": "CHEM.massConservation",
        "solver_api": "CHEMSOLVER.solveMassConservation",
        "layout": "天平对照反应前后总质量；敞口时用箭头标出逸出气体并给出逸出质量。",
        "controls": "碳酸钙质量、分解程度两个数值控件 + 密闭/敞口下拉；每次变化重新求解。",
        "solver_contract": "请求 {calcium_carbonate_g, progress:0..1, vessel:'sealed'|'open'}；按 CaCO₃→CaO+CO₂ 计量（M=100/56/44）计算反应前后总质量、逸出气体与剩余固体。暴露 window.__CHEM_MASS_REQUEST__ / __CHEM_MASS_RESULT__；控件标记 data-solver-input，读数标记 data-solver-field；每次先调 CHEMSOLVER.solveMassConservation，再把同一结果传给 CHEM.massConservation(cv, request, result)。",
    },
    {
        "id": "chemistry-ph-indicator", "subject": "化学",
        "patterns": r"pH|酸碱指示剂|石蕊|酚酞|酸碱性",
        "visual_type": "diagram", "api": "CHEM.phIndicator",
        "solver_api": "CHEMSOLVER.solvePhIndicator",
        "layout": "pH 色卡条 + 紫色石蕊与无色酚酞两支试管；颜色与判定由 pH 唯一确定。",
        "controls": "单个 pH 数值控件（0–14）；变化后重新求解并更新色卡指针、两支试管颜色与判定。",
        "solver_contract": "请求 {ph:0..14}；返回 nature（酸性/中性/碱性）、石蕊颜色、酚酞颜色与 pOH=14−pH。暴露 window.__CHEM_PH_REQUEST__ / __CHEM_PH_RESULT__；控件标记 data-solver-input，读数标记 data-solver-field；每次先调 CHEMSOLVER.solvePhIndicator，再把同一结果传给 CHEM.phIndicator(cv, request, result)。",
    },
    {
        "id": "chemistry-reaction-amounts", "subject": "化学",
        "patterns": r"化学计量|物质的量|摩尔体积|限量试剂|过量判断",
        "visual_type": "diagram", "api": "CHEM.reactionAmounts",
        "solver_api": "CHEMSOLVER.solveReactionAmounts",
        "layout": "反应物剩余与生成物的物质的量条形图 + 限量试剂标注；气体体积按 22.4 L/mol 换算。",
        "controls": "H₂、O₂ 的物质的量与反应进度三个数值控件；每次变化重新求解。",
        "solver_contract": "请求 {hydrogen_mol, oxygen_mol, progress:0..1}；按 2H₂+O₂→2H₂O 判断限量试剂，给出生成水、剩余气体物质的量与标准状况体积。暴露 window.__CHEM_AMOUNT_REQUEST__ / __CHEM_AMOUNT_RESULT__；控件标记 data-solver-input，读数标记 data-solver-field；每次先调 CHEMSOLVER.solveReactionAmounts，再把同一结果传给 CHEM.reactionAmounts(cv, request, result)。",
    },
    {
        "id": "chemistry-solubility-curve", "subject": "化学",
        "patterns": r"溶解度曲线|溶解度与饱和|溶解与饱和|饱和溶液|未溶解",
        "visual_type": "graph", "api": "CHEM.solubilityCurve",
        "solver_api": "CHEMSOLVER.solveSolubilityCurve",
        "layout": "溶解度—温度曲线 + 当前温度点 + 饱和判定 + 未溶解固体示意；曲线为简化线性模型并显式标注。",
        "controls": "温度、加入溶质质量、水的质量三个数值控件；每次变化重新求解并更新曲线上的点与判定。",
        "solver_contract": "请求 {temperature_c:0..100, solute_g, water_g}；按 S=20+0.8T（g/100 g 水）计算该温度溶解度、该水量最多溶解量、已溶解与未溶解质量。暴露 window.__CHEM_SOLUBILITY_REQUEST__ / __CHEM_SOLUBILITY_RESULT__；控件标记 data-solver-input，读数标记 data-solver-field；每次先调 CHEMSOLVER.solveSolubilityCurve，再把同一结果传给 CHEM.solubilityCurve(cv, request, result)。",
    },
    {
        "id": "chemistry-rate-equilibrium", "subject": "化学",
        "patterns": r"反应速率|化学平衡|平衡移动|活化能|催化剂",
        "visual_type": "graph", "api": "CHEM.rateEquilibrium",
        "solver_api": "CHEMSOLVER.solveRateEquilibrium",
        "layout": "速率—时间曲线（当前条件 vs 对比条件）+ 相对速率、平衡转化率、达平衡时间读数。",
        "controls": "温度、反应物浓度两个数值控件 + 催化剂下拉；每次变化重新求解并重绘曲线。",
        "solver_contract": "请求 {temperature_c:0..100, reactant_concentration_mol_L, catalyst:'yes'|'no'}；按 k ∝ 2^((T−25)/10)（催化剂 ×3）与 v=k·c 计算相对速率，按放热反应给出转化率与温度效应。暴露 window.__CHEM_RATE_REQUEST__ / __CHEM_RATE_RESULT__；控件标记 data-solver-input，读数标记 data-solver-field；每次先调 CHEMSOLVER.solveRateEquilibrium，再把同一结果传给 CHEM.rateEquilibrium(cv, request, result)。",
    },
    {
        "id": "chemistry-metal-activity", "subject": "化学",
        "patterns": r"金属活动性|活动性顺序|能否与.*反应|活动性判定",
        "visual_type": "apparatus", "api": "CHEM.metalActivity",
        "solver_api": "CHEMSOLVER.solveMetalActivity",
        "layout": "左侧金属活动性顺序表（高亮当前金属）+ 右侧盛盐溶液的烧杯与金属片；判定结果与方程式、现象同步。",
        "controls": "金属与溶液两个下拉控件；每次切换重新求解并更新判定、方程式与现象。",
        "solver_contract": "请求 {metal:'Mg'|'Zn'|'Fe'|'Cu'|'Ag', salt_solution:'CuSO4'|'AgNO3'|'ZnSO4'|'MgSO4'|'HCl'}；按活动性顺序表比较位置判定能否置换，给出方程式与现象。暴露 window.__CHEM_ACTIVITY_REQUEST__ / __CHEM_ACTIVITY_RESULT__；控件标记 data-solver-input，读数标记 data-solver-field；每次先调 CHEMSOLVER.solveMetalActivity，再把同一结果传给 CHEM.metalActivity(cv, request, result)。",
    },
    {
        "id": "chemistry-change-type", "subject": "化学",
        "patterns": r"物理变化|化学变化|变化类型|是否生成新物质",
        "visual_type": "diagram", "api": "CHEM.changeType",
        "solver_api": "CHEMSOLVER.solveChangeType",
        "layout": "物理变化 / 化学变化两栏对照，当前现象高亮在所属一栏，并给出判断依据与解释。",
        "controls": "现象下拉控件；切换后重新求解并更新高亮栏、依据与解释。",
        "solver_contract": "请求 {phenomenon:'ice_melt'|'alcohol_evaporate'|'water_boil'|'iron_rust'|'candle_burn'|'milk_spoil'}；按是否生成新物质判定物理/化学变化，返回类型、依据与解释。暴露 window.__CHEM_CHANGE_REQUEST__ / __CHEM_CHANGE_RESULT__；控件标记 data-solver-input，读数标记 data-solver-field；每次先调 CHEMSOLVER.solveChangeType，再把同一结果传给 CHEM.changeType(cv, request, result)。",
    },
    {
        "id": "chemistry-galvanic", "subject": "化学",
        "patterns": r"原电池|电极电势|电解池|化学电源|电动势",
        "visual_type": "apparatus", "api": "CHEM.galvanicCell",
        "solver_api": "CHEMSOLVER.solveGalvanicCell",
        "layout": "两只金属电极插入电解液，导线连成回路并标出电子流向；读数给出正负极、电势与电动势。",
        "controls": "电极 A、电极 B 两个下拉控件；切换后重新求解并更新正负极判定与电动势。",
        "solver_contract": "请求 {electrode_a, electrode_b}；按标准电极电势（Zn −0.76 / Fe −0.44 / Cu +0.34 / Ag +0.80 V）判定负极与正极，电动势 = E正 − E负。暴露 window.__CHEM_CELL_REQUEST__ / __CHEM_CELL_RESULT__；控件标记 data-solver-input，读数标记 data-solver-field；每次先调 CHEMSOLVER.solveGalvanicCell，再把同一结果传给 CHEM.galvanicCell(cv, request, result)。",
    },
    {
        "id": "chemistry-isomer", "subject": "化学",
        "patterns": r"同分异构|异构体|碳骨架|结构异构",
        "visual_type": "diagram", "api": "CHEM.isomerCount",
        "solver_api": "CHEMSOLVER.solveIsomerCount",
        "layout": "按分子式列出碳骨架异构体清单，并给出直链/支链计数与总数。",
        "controls": "分子式下拉控件；切换后重新枚举并更新清单与计数。",
        "solver_contract": "请求 {formula:'C4H10'|'C5H12'|'C3H6O'}；返回直链数、支链数、总数与异构体名称清单（不计顺反异构）。暴露 window.__CHEM_ISOMER_REQUEST__ / __CHEM_ISOMER_RESULT__；控件标记 data-solver-input，读数标记 data-solver-field；每次先调 CHEMSOLVER.solveIsomerCount，再把同一结果传给 CHEM.isomerCount(cv, request, result)。",
    },
    {
        "id": "chemistry-crystal", "subject": "化学",
        "patterns": r"晶体结构|配位数|晶胞|离子晶体|共价晶体|分子晶体",
        "visual_type": "diagram", "api": "CHEM.crystalLattice",
        "solver_api": "CHEMSOLVER.solveCrystal",
        "layout": "晶胞示意（顶点与面心粒子）+ 配位数与晶胞粒子数读数 + 结构说明。",
        "controls": "晶体下拉控件；切换后重新求解并更新示意图与读数。",
        "solver_contract": "请求 {crystal:'NaCl'|'CsCl'|'diamond'|'CO2'|'Cu'}；返回晶体类型、配位数、晶胞粒子数与结构说明。暴露 window.__CHEM_CRYSTAL_REQUEST__ / __CHEM_CRYSTAL_RESULT__；控件标记 data-solver-input，读数标记 data-solver-field；每次先调 CHEMSOLVER.solveCrystal，再把同一结果传给 CHEM.crystalLattice(cv, request, result)。",
    },
    {
        "id": "physics-density", "subject": "物理",
        "patterns": r"密度测量|测量.{0,4}密度|测密度|密度的测量|天平.{0,8}量筒|量筒.{0,8}天平",
        "visual_type": "apparatus", "api": "PHYS.density",
        "solver_api": "PHYS.solveDensity",
        "layout": "演示区左侧为托盘天平（物体与砝码），右侧为量筒（水、物块与 mL 刻度），结果区给密度与浮沉判断。",
        "controls": "质量与体积两个数值控件；每次变化重新求解，并同步重绘天平与量筒。",
        "solver_contract": (
            "请求 {mass_g:>0, volume_cm3:>0}；返回 density_g_cm3=m/V（g/cm³）、density_kg_m3=ρ×1000、"
            "water_ratio、state（上浮/悬浮/下沉，与水 1 g/cm³ 比较，相差 0.2% 以内记为悬浮）。"
            "暴露 window.__PHYS_DENSITY_REQUEST__ / window.__PHYS_DENSITY_RESULT__；"
            "控件标记 data-solver-input，读数标记 data-solver-field；"
            "每次先调 PHYS.solveDensity(request)，再把同一结果传给 PHYS.density(cv, request, result)；"
            "体积控件单位 cm³，请求不做单位换算。"
        ),
    },
]


SUBJECT_DEFAULTS = {
    "化学": ("chemistry-lab", "apparatus", "化学实验通用版面：先明确反应器材、物态和观察现象；若命中已注册主题，必须优先使用其专用骨架。"),
    "物理": ("physics-investigation", "apparatus", "物理探究版面：器材/实验对象 + 可操作变量 + 同步测量读数；若命中已注册主题，必须优先使用其专用骨架。"),
    "数学": ("math-exploration", "graph", "数学探究版面：根据对象选函数图、统计图或几何图，展示关键量与可复算依据；若命中已注册主题，必须优先使用其专用骨架。"),
    "生物": ("biology-observation", "diagram", "生物观察/过程版面：②区只呈现实验对象、显微视野、结构图或结果对照；步骤与阶段操作放③区或⑥区。命中已注册主题时优先使用专用骨架。"),
    "地理": ("geography-spatial", "diagram", "地理空间过程版面：地图/球体/剖面与图例配套，突出空间位置或时间演变。"),
    "信息科技": ("informatics-stepper", "process", "信息科技步骤版面：状态序列/节点图 + 逐步执行控件 + 输出。"),
    "信息": ("informatics-stepper", "process", "信息科技步骤版面：状态序列/节点图 + 逐步执行控件 + 输出。"),
}

# On overlap, choose the most specific chemistry interaction before broad
# scene patterns. For example, acid/base titration also mentions solution
# concentration and volume, while gas collection may mention equation balance.
SCENE_PRIORITY = {
    "chemistry-solubility-ksp": 100,
    "chemistry-mass-conservation": 105,
    "chemistry-dilution": 110,
    "chemistry-reaction-amounts": 115,
    "chemistry-solubility-curve": 120,
    "chemistry-rate-equilibrium": 130,
    "chemistry-metal-activity": 140,
    "chemistry-change-type": 150,
    "chemistry-galvanic": 160,
    "chemistry-isomer": 170,
    "chemistry-crystal": 180,
    "chemistry-redox-electron-balance": 95,
    "chemistry-precipitation-quantitative": 90,
    "chemistry-acid-base-titration": 90,
    "chemistry-gas-collection": 90,
    "chemistry-solution-mixing-stoichiometry": 80,
    "chemistry-stoichiometry-limiting-reagent": 75,
    "chemistry-equation-balance": 70,
    "chemistry-separation-stages": 60,
    "chemistry-molecular-model": 60,
    # 铁与硫酸铜这类“现象 + 方程式”需求会同时命中“反应进度/计量”，
    # 但教学重点是置换现象和方程式，不能让纯计量场景压过去。
    "chemistry-reaction-compare": 85,
    # 物理：带求解器的具体场景要压过同关键词的通用版面。
    # 否则“凸透镜成像”会先命中 physics-optics-bench（无求解器），退回大模型自由生成。
    "physics-thin-lens": 90,
    # 密度测量：浮力/压强页也会出现“密度”字样，这里只用专用短语并给高优先级，
    # 避免“测密度”被浮力或液体压强骨架抢走（它们有各自的专用硬校验）。
    "physics-density": 200,
}

SUBJECT_ALIASES = {
    "物理学": "物理", "化学": "化学", "数学": "数学", "生物学": "生物",
    "地理学": "地理", "信息技术": "信息科技", "信息": "信息科技",
    "计算机": "信息科技", "编程": "信息科技", "算法": "信息科技",
}


def select_page_skeleton(req):
    """Return the highest-priority topic skeleton, else the subject default."""
    req = req or {}
    subject = str(req.get("学科", "")).strip()
    subject = SUBJECT_ALIASES.get(subject, subject)
    topic = str(req.get("实验主题", ""))
    haystack = " ".join(str(req.get(k, "")) for k in
                        ("实验名称", "实验主题", "技术要点", "学习目标", "交互要求"))
    if isinstance(req.get("交互要求"), list):
        haystack += " " + " ".join(map(str, req["交互要求"]))
    matches = []
    for index, item in enumerate(SCENE_SKELETONS):
        if item["subject"] == subject and re.search(item["patterns"], haystack, re.I):
            priority = SCENE_PRIORITY.get(item["id"], 0)
            topic_match = subject == "数学" and bool(re.search(item["patterns"], topic, re.I))
            if subject == "物理":
                label = (item.get("lesson_model") or {}).get("title", "")
                if label and label in topic:
                    topic_match = len(label)
                else:
                    topic_match = max((len(match[0]) for match in re.finditer(item["patterns"], topic, re.I)), default=0)
            matches.append((priority, topic_match, -index, item))
    if matches:
        return dict(max(matches, key=lambda match: match[:3])[3])
    if subject == "数学" and re.search(r"概率|统计|平均数|方差|抽样", haystack):
        return {"id": "math-statistics", "subject": subject,
                "visual_type": "graph", "api": None,
                "layout": "数据样本/分布图 + 可调整样本或参数 + 统计量结果与计算依据。",
                "controls": "样本变更必须同步更新图表、均值/方差等统计量和记录表。"}
    key, visual_type, layout = SUBJECT_DEFAULTS.get(
        subject, ("general-investigation", "diagram", "按教学对象选择清晰的图示、操作与结果布局。"))
    return {"id": key, "subject": subject, "visual_type": visual_type,
            "api": None, "layout": layout,
            "controls": "每个控件都应改变教学对象或结果；显示公式、读数与图形须共用同一状态。"}


def required_scene_call(req):
    """Compatibility helper used by hard validation."""
    skeleton = select_page_skeleton(req)
    api = skeleton.get("api")
    if not api:
        return None
    return re.escape(api).replace(r"\.", r"\s*\.\s*") + r"\s*\(", api


def required_solver_call(req):
    """Return required numerical solver API and call pattern for a topic."""
    solver = select_page_skeleton(req).get("solver_api")
    if not solver:
        return None
    return re.escape(solver).replace(r"\.", r"\s*\.\s*") + r"\s*\(", solver
