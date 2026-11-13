# -*- coding: utf-8 -*-
"""
generator_agent.py —— 教学工具生成 Agent（六区域版）

输入：需求 JSON（01）+ 知识包 JSON（02）
输出：一个可直接双击打开、离线运行的 HTML 教学实验（已套平台外壳）

和上一版的区别：
    模型不再直接吐完整 HTML，而是吐「六块内容」；外壳由 shell.py 装配。
    这样每个页面的页眉、右侧栏、页脚、弹窗都完全一致，不会因为模型偷懒而缺失。

仍然保留三道关：清洗 → 校验 → 不合格自动修复一次；还不行退回内置兜底片段。

用法：
    python generator_agent.py                     # 自动找最新的需求和知识包
    python generator_agent.py --open              # 生成后直接打开
    python generator_agent.py --template-only     # 不调模型，只用兜底片段
    python generator_agent.py --feedback "读数不刷新"
"""

import argparse
import glob
import json
import os
import re
import shutil
import sys
import time
import zipfile

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT = os.path.dirname(BASE_DIR)
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

# 平台外壳装配器（在项目根目录）
sys.path.append(PARENT)
import shell  # noqa: E402

# 复用 01 阶段的模型调用封装（改 .env 就能换模型）
# 注意用 append 而不是 insert(0)：两个文件夹里都有 prompts.py，
# 追加到末尾才能保证优先导入本目录的 prompts。
sys.path.append(os.path.join(PARENT, "01_single_agent"))
try:
    from llm import call_llm, get_config, load_env
    HAS_LLM = True
except Exception as exc:                      # noqa: BLE001
    HAS_LLM = False
    LLM_ERROR = str(exc)

from prompts import GENERATOR_SYSTEM_PROMPT, build_user_prompt
from scene_registry import required_scene_call, required_solver_call, select_page_skeleton
from solver_templates import (render_solver_template, ksp_template_values, resolve_ksp_config,
                              resolve_acid_base_titration_config, titration_template_values,
                              resolve_precipitation_config, precipitation_template_values,
                              resolve_gas_collection_config, gas_collection_template_values,
                              resolve_redox_config, redox_template_values)
from math_page_plan import MathPlanError


# ============ 1. 找最新的输入文件 ============

def latest_file(folder, pattern):
    files = glob.glob(os.path.join(folder, pattern))
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def load_inputs(req_path, kb_path):
    req_path = req_path or latest_file(os.path.join(PARENT, "01_single_agent", "output"), "需求_*.json")

    if not req_path or not os.path.exists(req_path):
        raise SystemExit("找不到需求 JSON。请先运行 01_single_agent/agent.py")

    # 知识包按"同一个需求"配对，而不是简单取最新的一个
    if not kb_path:
        key = os.path.basename(req_path)
        key = key[len("需求_"):-len(".json")] if key.startswith("需求_") else key
        paired = os.path.join(PARENT, "02_retrieval_agent", "output", "知识包_%s.json" % key)
        if os.path.exists(paired):
            kb_path = paired
        else:
            kb_path = latest_file(os.path.join(PARENT, "02_retrieval_agent", "output"), "知识包_*.json")
            print("   警告：没有找到与需求配对的知识包，改用最新的一个，请确认主题一致")

    if not kb_path or not os.path.exists(kb_path):
        raise SystemExit("找不到知识包 JSON。请先运行 02_retrieval_agent/retrieval_agent.py")

    with open(req_path, "r", encoding="utf-8") as f:
        req_raw = json.load(f)
    with open(kb_path, "r", encoding="utf-8") as f:
        kb_raw = json.load(f)

    req = req_raw.get("output", req_raw)
    if req_raw.get("input"):
        req = dict(req, 原始需求=req_raw["input"])
    pack = kb_raw.get("knowledge_pack", {})
    return req, pack, req_path, kb_path


# ============ 2. 清洗：把模型回复切成六块 ============

def clean_sections(text):
    """从模型回复里取出六块内容。围栏、客套话、外壳标签都削掉。"""
    secs = shell.parse_sections(text)

    # 兜底：模型可能仍吐了完整 HTML，从 shell.parse_sections 的抢救结果里再取一次
    if not secs.get("1"):
        m = re.search(r"<!--\s*1\s*-->(.*?)<!--\s*2\s*-->", text or "", re.S)
        if m:
            secs = shell.parse_sections(text)

    # 去掉模型顺手带上的外壳标签（若它没按要求省略）
    for k in list(secs.keys()):
        if k in ("css", "js"):
            continue
        body = secs[k]
        body = re.sub(r"</?(?:html|head|body|main)[^>]*>", "", body, flags=re.I)
        secs[k] = body.strip()
    return secs


JS_IDENTIFIER = r"[A-Za-z_$][\w$]*"


def solver_result_names(code, solver):
    """Accept initialization and later assignment, including inside try blocks."""
    solver_call = r"\s*\.\s*".join(map(re.escape, solver.split(".")))
    return set(re.findall(
        rf"(?<![\w$.])({JS_IDENTIFIER})\s*=(?!=)\s*{solver_call}\s*\(", code))


def draws_solver_result(code, solver, drawing):
    drawing_call = r"\s*\.\s*".join(map(re.escape, drawing.split(".")))
    drawn = set(re.findall(
        rf"{drawing_call}\s*\(\s*[^,]+,\s*[^,]+,\s*({JS_IDENTIFIER})\s*\)", code))
    return bool(solver_result_names(code, solver) & drawn)


def hard_validate(secs, req=None, *, managed_readouts=False):
    """生成阶段的硬校验比审查宽松些，只卡"装配不出来"的问题。"""
    problems = []

    missing = [k for k, _ in shell.SECTIONS if not (secs.get(k) or "").strip()]
    if missing:
        problems.append("缺少区域标记：%s（必须是 <!--1--> 到 <!--6-->）"
                        % "、".join("<!--%s-->" % m for m in missing))

    if not (secs.get("js") or "").strip():
        problems.append("缺少 <!--JS--> 脚本块")

    visual = secs.get("2") or ""
    skeleton = select_page_skeleton(req or {})
    required_scene = required_scene_call(req or {})
    required_solver = required_solver_call(req or {})
    js_code = re.sub(r"/\*.*?\*/|//[^\r\n]*", "", secs.get("js") or "", flags=re.S)
    composite_volume = (skeleton.get("solver_api") == "MATH.solveSolidVolume"
                        and bool(re.search(r"MATH\s*\.\s*solveCompositeVolume\s*\(", js_code)))
    if required_scene and not composite_volume and not re.search(required_scene[0], js_code, re.I):
        problems.append("选定骨架 %s 要求页面脚本实际调用 %s，不能只在注释中提及或另写简化手绘"
                        % (skeleton["id"], required_scene[1]))
    if required_solver:
        if not composite_volume and not re.search(required_solver[0], js_code, re.I):
            problems.append("选定骨架 %s 必须在 render 中调用学科求解器 %s" % (skeleton["id"], required_solver[1]))
        if skeleton.get("solver_api") == "CHEMSOLVER.balanceEquation":
            for marker in ("__CHEM_BALANCE_REQUEST__", "__CHEM_BALANCE_RESULT__"):
                if marker not in js_code:
                    problems.append("化学方程式配平页必须暴露 %s，供质量审查独立复算" % marker)
            if "data-chem-balance-equation" not in ((secs.get("2") or "") + js_code):
                problems.append("可见配平结果必须标记 data-chem-balance-equation，供审查器核对实际显示内容")
            if not re.search(r"\.\s*equation\b", js_code, re.I) or not re.search(r"\.\s*atom_counts\b", js_code, re.I):
                problems.append("配平后的方程式和原子数对照必须读取求解器返回结果，不能手写系数或计数")
            if not re.search(r"\.\s*checks\s*\.\s*ok\b", js_code, re.I):
                problems.append("只有求解器 checks.ok 为 true 时才能显示配平成功；失败时必须呈现错误状态")
            if skeleton.get("id") == "chemistry-equation-balance":
                controls_html = "\n".join((secs.get("3") or "", secs.get("4") or "", visual))
                for marker in ("data-chem-balance-coefficient-side", "data-chem-balance-coefficient-index",
                               "data-chem-balance-student-check"):
                    if marker not in controls_html:
                        problems.append("方程式配平交互必须标记学生系数输入和校验结果 %s，供浏览器变形测试" % marker)
                for token in ("checkCoefficients", "__CHEM_BALANCE_STUDENT_COEFFICIENTS__",
                              "__CHEM_BALANCE_STUDENT_CHECK__"):
                    if token not in js_code:
                        problems.append("方程式配平交互必须调用/暴露 %s，供浏览器核验学生系数变形" % token)
        if skeleton.get("solver_api") == "CHEMSOLVER.solveStoichiometry":
            for marker in ("__CHEM_STOICH_REQUEST__", "__CHEM_STOICH_RESULT__"):
                if marker not in js_code:
                    problems.append("反应计量页面必须暴露 %s，供质量审查独立复算" % marker)
            if "data-chem-stoich-equation" not in ((secs.get("2") or "") + js_code):
                problems.append("可见反应方程式必须标记 data-chem-stoich-equation，供审查器核对实际显示内容")
            controls_html = "\n".join((secs.get("3") or "", secs.get("4") or "", visual))
            if "data-chem-stoich-amount-index" not in controls_html or "data-chem-stoich-progress" not in controls_html:
                problems.append("限量试剂页面必须标记可见物质的量与反应进度控件，供审查器核对控件值和计算请求")
            progress_control = re.search(
                r'<input\b[^>]*\bdata-chem-stoich-progress\b[^>]*>', controls_html, re.I)
            if not progress_control or not re.search(r'\bmin=["\']0(?:\.0+)?["\']', progress_control.group(0), re.I) or not re.search(
                    r'\bmax=["\']1(?:\.0+)?["\']', progress_control.group(0), re.I):
                problems.append("反应进度控件必须是可操作的 input，范围覆盖 min=0 到 max=1，页面变形测试需要验证起点/中点/终点")
            for field in ("max_extent_mol", "extent_mol", "limiting_reactants", "remaining_mol", "produced_mol", "element_balance"):
                if not re.search(r"\.\s*%s\b" % re.escape(field), js_code, re.I):
                    problems.append("反应计量页面必须从求解结果读取 %s，不能手写理论量" % field)
            if not re.search(r"\.\s*checks\s*\.\s*ok\b", js_code, re.I):
                problems.append("只有求解器 checks.ok 为 true 时才能显示反应计量结果；失败时必须呈现错误状态")
        if skeleton.get("solver_api") == "CHEMSOLVER.solveSolutionMixing":
            for marker in ("__CHEM_MIX_REQUEST__", "__CHEM_MIX_RESULT__"):
                if marker not in js_code:
                    problems.append("溶液混合反应页面必须暴露 %s，供质量审查独立复算" % marker)
            if "data-chem-mix-equation" not in ((secs.get("2") or "") + js_code):
                problems.append("可见反应方程式必须标记 data-chem-mix-equation，供审查器核对实际显示内容")
            controls_html = "\n".join((secs.get("3") or "", secs.get("4") or "", visual))
            control_markers = ("data-chem-mix-concentration-index", "data-chem-mix-volume-index",
                               "data-chem-mix-unit-index", "data-chem-mix-progress")
            if any(marker not in controls_html for marker in control_markers):
                problems.append("溶液混合页必须标记浓度、体积、单位和反应进度控件，供审查器验证输入联动")
            for field in ("solution_inputs", "initial_amounts_mol", "limiting_reactants",
                          "max_extent_mol", "remaining_mol", "produced_mol", "element_balance"):
                if not re.search(r"\.\s*%s\b" % re.escape(field), js_code, re.I):
                    problems.append("溶液混合页面必须从求解结果读取 %s，不能手写换算或理论量" % field)
            if not re.search(r"\.\s*checks\s*\.\s*ok\b", js_code, re.I):
                problems.append("只有求解器 checks.ok 为 true 时才能显示溶液混合计算结果")
        if skeleton.get("solver_api") == "CHEMSOLVER.solvePrecipitation":
            for marker in ("__CHEM_PRECIP_REQUEST__", "__CHEM_PRECIP_RESULT__"):
                if marker not in js_code:
                    problems.append("沉淀反应页面必须暴露 %s，供变形测试和独立审查复算" % marker)
            content_html = "\n".join((secs.get("2") or "", secs.get("3") or "",
                                       secs.get("4") or "", secs.get("5") or "", visual, js_code))
            for marker in ("data-chem-precip-equation", "data-chem-precip-net-ionic",
                           "data-chem-precip-mass"):
                if marker not in content_html:
                    problems.append("沉淀反应页面必须标记可见输出 %s，供审查器核验" % marker)
            controls_html = "\n".join((secs.get("3") or "", secs.get("4") or "", visual))
            for marker in ("data-chem-precip-concentration-index", "data-chem-precip-volume-index",
                           "data-chem-precip-unit-index", "data-chem-precip-progress"):
                if marker not in controls_html:
                    problems.append("沉淀反应页面必须提供并标记真实控件 %s，供页面变形测试" % marker)
            if not re.search(r"CHEM\s*\.\s*precipitation\s*\(", js_code, re.I):
                problems.append("沉淀反应演示必须调用 CHEM.precipitation(cv,result)，由求解结果绘制沉淀")
            for field in ("precipitate_formula", "precipitate_moles", "precipitate_mass_g",
                          "limiting_reactants", "net_ionic_equation"):
                if not re.search(r"\.\s*%s\b" % re.escape(field), js_code, re.I):
                    problems.append("沉淀反应页面必须从求解结果读取 %s，不能手写计算" % field)
            if not re.search(r"\.\s*checks\s*\.\s*ok\b", js_code, re.I):
                problems.append("只有求解器 checks.ok 为 true 时才能显示沉淀质量；失败时须显示错误状态")
        if skeleton.get("solver_api") == "CHEMSOLVER.solveSolubilityEquilibrium":
            for marker in ("__CHEM_KSP_REQUEST__", "__CHEM_KSP_RESULT__"):
                if marker not in js_code:
                    problems.append("Ksp 页面必须暴露 %s，供页面变形测试和独立复算" % marker)
            content_html = "\n".join((secs.get("2") or "", secs.get("3") or "",
                                       secs.get("4") or "", secs.get("5") or "", visual, js_code))
            for marker in ("data-chem-ksp-equation", "data-chem-ksp-expression", "data-chem-ksp-ion-product",
                           "data-chem-ksp-state", "data-chem-ksp-solubility"):
                if marker not in content_html:
                    problems.append("Ksp 页面必须标记可见结果 %s，供审查器核验" % marker)
            controls_html = "\n".join((secs.get("3") or "", secs.get("4") or "", visual))
            ksp_control = re.search(r'<input\b[^>]*\bdata-chem-ksp-value\b[^>]*>', controls_html, re.I)
            if not ksp_control or not re.search(r'\btype=["\']number["\']', ksp_control.group(0), re.I) or not re.search(
                    r'\bstep=["\']any["\']', ksp_control.group(0), re.I):
                problems.append("Ksp 必须使用 step=any 的 number 控件，支持溶度积数量级输入和页面变形")
            ion_controls = re.findall(
                r'<input\b[^>]*\bdata-chem-ksp-ion-index=["\'][^"\']+["\'][^>]*>', controls_html, re.I)
            if len(ion_controls) < 2 or any(
                    not re.search(r'\btype=["\']number["\']', tag, re.I) or
                    not re.search(r'\bmin=["\']0(?:\.0+)?["\']', tag, re.I) or
                    not re.search(r'\bstep=["\']any["\']', tag, re.I) for tag in ion_controls):
                problems.append("Ksp 页面至少需要两个 min=0、step=any 的 number 离子浓度控件")
            if not re.search(r"CHEM\s*\.\s*solubility\s*\(", js_code, re.I):
                problems.append("Ksp 演示必须调用 CHEM.solubility(cv,result)，图示与求解结果同源")
            for field in ("dissolution_equation", "initial_ion_product", "saturation_state",
                          "molar_solubility_mol_L", "checks"):
                if not re.search(r"\.\s*%s\b" % re.escape(field), js_code, re.I):
                    problems.append("Ksp 页面必须从求解结果读取 %s，不得手写平衡结论" % field)
            equation_rhs = [rhs.strip() for rhs in re.findall(
                r"(?:\.textContent|\.innerText|\.innerHTML)\s*=\s*([^;\n]+)", js_code, re.I)
                if re.search(r"\.\s*dissolution_equation\b", rhs, re.I)]
            if not equation_rhs or not any(re.fullmatch(
                    r"[A-Za-z_$][\w$]*\s*\.\s*dissolution_equation", rhs, re.I)
                    for rhs in equation_rhs) or any("+" in rhs for rhs in equation_rhs):
                problems.append("Ksp 方程元素必须只显示 result.dissolution_equation；Q 表达式等内容须放入独立元素")
            if not re.search(r"\.\s*checks\s*\.\s*ok\b", js_code, re.I):
                problems.append("只有 Ksp 求解器 checks.ok 为 true 时才能显示数值结论；失败时必须显示错误状态")
        if skeleton.get("solver_api") == "CHEMSOLVER.solveRedox":
            for marker in ("__CHEM_REDOX_REQUEST__", "__CHEM_REDOX_RESULT__"):
                if marker not in js_code:
                    problems.append("氧化还原页面必须暴露 %s，供页面变形测试和独立复算" % marker)
            content_html = "\n".join((secs.get("2") or "", secs.get("3") or "",
                                       secs.get("4") or "", secs.get("5") or "", visual, js_code))
            for marker in ("data-chem-redox-equation", "data-chem-redox-electrons",
                           "data-chem-redox-changes"):
                if marker not in content_html:
                    problems.append("氧化还原页面必须标记可见结果 %s，供审查器核验" % marker)
            controls_html = "\n".join((secs.get("3") or "", secs.get("4") or "", visual))
            for marker in ("data-chem-redox-medium", "data-chem-redox-reorder"):
                if marker not in controls_html:
                    problems.append("氧化还原页面必须提供并标记真实控件 %s，供页面变形测试" % marker)
            medium_select = re.search(
                r'<select\b[^>]*\bdata-chem-redox-medium\b[^>]*>(.*?)</select>',
                controls_html, re.I | re.S)
            if not medium_select:
                problems.append("氧化还原介质必须用带 acidic/basic 两种选项的 select，供页面变形测试")
            else:
                option_values = re.findall(r'<option\b[^>]*\bvalue=["\']([^"\']+)',
                                           medium_select.group(1), re.I)
                normalized_values = {value.strip().lower() for value in option_values}
                if not (normalized_values & {"acidic", "acid", "酸性"} and
                        normalized_values & {"basic", "base", "碱性", "鹼性"}):
                    problems.append("氧化还原介质选择器必须同时提供酸性和碱性选项")
            if not re.search(r"CHEM\s*\.\s*redox\s*\(", js_code, re.I):
                problems.append("氧化数变化图必须调用 CHEM.redox(cv,result)，并与求解结果同源")
            for field in ("equation", "oxidation_changes", "electron_balance", "transferred_electrons"):
                if not re.search(r"\.\s*%s\b" % re.escape(field), js_code, re.I):
                    problems.append("氧化还原页面必须从求解结果读取 %s，不得手写配平或电子数" % field)
            if not re.search(r"\.\s*checks\s*\.\s*ok\b", js_code, re.I):
                problems.append("只有求解器 checks.ok 为 true 时才能显示氧化还原结论；失败时必须显示错误状态")
        if skeleton.get("solver_api") == "CHEMSOLVER.solveAcidBaseTitration":
            for marker in ("__CHEM_TITRATION_REQUEST__", "__CHEM_TITRATION_RESULT__"):
                if marker not in js_code:
                    problems.append("酸碱滴定页面必须暴露 %s，供浏览器变形测试和质量审查独立复算" % marker)
            if "data-chem-titration-equation" not in ((secs.get("2") or "") + js_code):
                problems.append("酸碱滴定方程式必须标记 data-chem-titration-equation，供审查器核对实际显示内容")
            if not re.search(r"CHEM\s*\.\s*titration\s*\(", js_code, re.I):
                problems.append("酸碱滴定演示必须调用 CHEM.titration(cv, result)，让滴定器材和液体状态使用求解结果绘制")
            if not re.search(r"CHEM\s*\.\s*titrationCurve\s*\(", js_code, re.I):
                problems.append("pH—滴入体积图必须调用共享滴定曲线组件绘制")
            controls_html = "\n".join((secs.get("3") or "", secs.get("4") or "", visual))
            for marker in ("data-chem-titration-acid-concentration", "data-chem-titration-acid-volume",
                           "data-chem-titration-acid-unit", "data-chem-titration-base-concentration",
                           "data-chem-titration-base-volume", "data-chem-titration-base-unit"):
                if marker not in controls_html:
                    problems.append("酸碱滴定页必须提供并标记可见参数控件 %s" % marker)
            for field in ("equivalence_volume_ml", "acid_moles_remaining", "base_moles_remaining", "pH", "state"):
                if not re.search(r"\.\s*%s\b" % re.escape(field), js_code, re.I):
                    problems.append("酸碱滴定页面必须从求解结果读取 %s，不能独立手算" % field)
            if not re.search(r"\.\s*checks\s*\.\s*ok\b", js_code, re.I):
                problems.append("只有求解器 checks.ok 为 true 时才能显示滴定读数；失败时必须显示错误状态")
            if "data-chem-titration-curve" not in "\n".join(
                    (secs.get(key) or "") for key in ("2", "3", "4", "5", "6", "js")):
                problems.append("酸碱滴定页面必须包含可见 pH—滴入体积曲线")
            if "__CHEM_TITRATION_CURVE_SAMPLES__" not in js_code or len(re.findall(
                    r"CHEMSOLVER\s*\.\s*solveAcidBaseTitration\s*\(", js_code, re.I)) < 2:
                problems.append("滴定曲线采样点必须逐点调用同一滴定求解器，不能用手写公式另算")
        if skeleton.get("solver_api") == "CHEMSOLVER.solveGasCollection":
            for marker in ("__CHEM_GAS_REQUEST__", "__CHEM_GAS_RESULT__"):
                if marker not in js_code:
                    problems.append("气体制取页面必须暴露 %s，供变形测试和独立审查复算" % marker)
            if "data-chem-gas-equation" not in ((secs.get("2") or "") + js_code):
                problems.append("可见化学方程式必须标记 data-chem-gas-equation，供审查器核验")
            if "data-chem-gas-volume" not in ("\n".join((secs.get("2") or "", secs.get("3") or "",
                                                               secs.get("4") or "", visual, js_code))):
                problems.append("可见气体体积读数必须标记 data-chem-gas-volume，供审查器核验")
            controls_html = "\n".join((secs.get("3") or "", secs.get("4") or "", visual))
            for marker in ("data-chem-gas-amount-index", "data-chem-gas-progress",
                           "data-chem-gas-temperature", "data-chem-gas-pressure", "data-chem-gas-method"):
                if marker not in controls_html:
                    problems.append("气体制取页面必须提供并标记可见控件 %s，供页面变形测试" % marker)
            if not re.search(r"CHEM\s*\.\s*gasCollection\s*\(", js_code, re.I):
                problems.append("气体制取演示必须调用 CHEM.gasCollection(cv, result)，且使用求解结果绘图")
            for field in ("gas_moles", "gas_volume_l", "dry_gas_partial_pressure_kpa", "limiting_reactants"):
                if not re.search(r"\.\s*%s\b" % re.escape(field), js_code, re.I):
                    problems.append("气体制取页面必须从求解结果读取 %s，不能另行手算" % field)
            if not re.search(r"\.\s*checks\s*\.\s*ok\b", js_code, re.I):
                problems.append("只有求解器 checks.ok 为 true 时才能显示气体体积；失败时必须显示错误状态")
        if skeleton.get("solver_api") == "CIRCUIT.solve":
            if not re.search(r"CIRCUIT\s*\.\s*bindMeters\s*\(", js_code, re.I):
                problems.append("电路表计读数必须由 CIRCUIT.bindMeters 从求解器结果直接写入，不能使用手写公式")
            if not re.search(r"CIRCUIT\s*\.\s*draw\s*\(", js_code, re.I):
                problems.append("电路图必须调用 CIRCUIT.draw(cv, model, solverResult)，确保导线拓扑来自求解模型")
            if re.search(r"drawFallback\s*\(|\b(?:U|I)\s*=\s*6\s*(?:\*|/)\s*state\.", js_code, re.I):
                problems.append("电路页仍有手写公式/绘图回退；求解失败时必须停止显示正常结果，不能用另一套算法代替求解器")
            if not re.search(r"CIRCUIT\s*\.\s*meter\s*\(", js_code, re.I):
                problems.append("电路页的公式与机读数据必须从 CIRCUIT.meter(solverResult, 元件ID, current/voltage) 取值，不能另算一遍")
            if not re.search(r"type\s*:\s*['\"]voltage[_-]?source['\"]", js_code, re.I):
                problems.append("电路网表缺少真实电源元件（voltage_source），不能只在文字或画布中标注电源")
            if not re.search(r"type\s*:\s*['\"]ammeter['\"]", js_code, re.I):
                problems.append("电路网表必须包含串联理想电流表元件 ammeter；不能用 current_source 冒充电流表")
            if not re.search(r"volts\s*:\s*state\.[A-Za-z_$][\w$]*", js_code, re.I):
                problems.append("电源电压必须从当前控件状态写入 voltage_source.volts；不能让滑块只改标签、不改仿真")
            if not re.search(r"ohms\s*:\s*state\.[A-Za-z_$][\w$]*", js_code, re.I):
                problems.append("被测电阻必须从当前控件状态写入 resistor.ohms；不能让参数控件与仿真脱节")
            vm_ids = set(re.findall(r"id\s*:\s*['\"]([^'\"]+)['\"]\s*,\s*type\s*:\s*['\"]voltmeter['\"]", js_code, re.I))
            voltage_binding = re.search(r"data-circuit-voltage-for\s*=\s*['\"]([^'\"]+)",
                                        "\n".join((secs.get("3") or "", visual, secs.get("4") or "")), re.I)
            if voltage_binding and voltage_binding.group(1) in vm_ids:
                problems.append("电压表读数应绑定被测电阻支路（与 voltmeter 两端并联），不能绑定电压表自身元件")
            if voltage_binding:
                component_rows = []
                for row in re.findall(r"\{[^{}]*\bid\s*:\s*['\"][^'\"]+['\"][^{}]*\}", js_code, re.S):
                    def field(name):
                        m = re.search(r"\b%s\s*:\s*['\"]([^'\"]+)['\"]" % name, row, re.I)
                        return m.group(1) if m else None
                    comp_id, comp_type = field("id"), field("type")
                    if not comp_id or not comp_type:
                        continue
                    ends = field("from"), field("to")
                    if not all(ends): ends = field("positive"), field("negative")
                    component_rows.append((comp_id, comp_type.lower().replace("-", "_"), frozenset(ends)))
                bound_id = voltage_binding.group(1)
                target = next((x for x in component_rows if x[0] == bound_id and x[1] == "resistor"), None)
                meters = [x for x in component_rows if x[1] == "voltmeter"]
                if target and meters and not any(x[2] == target[2] for x in meters):
                    problems.append("voltmeter 元件必须与 data-circuit-voltage-for 所指的被测电阻并联（两端节点完全相同）")
            for marker in ("__CIRCUIT_MODEL__", "__CIRCUIT_RESULT__"):
                if marker not in js_code:
                    problems.append("电路页必须暴露 %s，供独立审查器复算和对拍" % marker)
            if not re.search(r"data-circuit-current-for=[\"']", "\n".join((secs.get("3") or "", visual, secs.get("4") or "")), re.I):
                problems.append("电路页面必须用 data-circuit-current-for 标记绑定到求解器支路的电流表读数")
            if not re.search(r"data-circuit-voltage-for=[\"']", "\n".join((secs.get("3") or "", visual, secs.get("4") or "")), re.I):
                problems.append("电路页面必须用 data-circuit-voltage-for 标记绑定到求解器支路的电压表读数")
        lesson_model = skeleton.get("lesson_model")
        if lesson_model or skeleton.get("solver_api") in ("MATH.solveQuadratic", "PHYS.solveThinLens"):
            api = required_solver[1]
            if lesson_model:
                prefix, draw_api = lesson_model["prefix"], lesson_model.get("draw")
                inputs, outputs = lesson_model["inputs"], lesson_model["fields"]
            elif api == "MATH.solveQuadratic":
                prefix, draw_api, inputs = "MATH_QUADRATIC", "MATH.funcPlot", ("a", "b", "c")
                outputs = ("vertex_x", "vertex_y", "axis_x", "discriminant", "roots", "y_intercept", "opening")
            else:
                prefix, draw_api, inputs = "PHYS_LENS", "PHYS.optics", ("u", "f")
                outputs = ("image_distance_cm", "magnification", "state")
            for suffix in ("REQUEST", "RESULT"):
                if f"__{prefix}_{suffix}__" not in js_code:
                    problems.append(f"{api} 页面必须暴露 __{prefix}_{suffix}__ 供独立复算")
            if draw_api and not draws_solver_result(js_code, api, draw_api):
                problems.append(f"必须将 {api} 返回的结果传给 {draw_api}(cv, cfg, result)")
            if lesson_model and managed_readouts:
                bound = set(re.findall(
                    rf"VIS\s*\.\s*bindSolverReadouts\s*\(\s*({JS_IDENTIFIER})\s*[,)]", js_code))
                if not solver_result_names(js_code, api) & bound:
                    problems.append(f"必须调用 VIS.bindSolverReadouts(result)，直接绑定 {api} 的同一求解结果")
            markup = "\n".join(secs.get(key) or "" for key in ("2", "3", "4")) + "\n" + js_code
            for attr, fields in (("data-solver-input", inputs), ("data-solver-field", outputs)):
                for field in fields:
                    if not re.search(rf'{attr}\s*=\s*["\']{field}["\']', markup):
                        problems.append(f'求解器页面缺少 {attr}="{field}"')
        if skeleton.get("solver_api") == "MATH.solveCubeCut":
            if not draws_solver_result(js_code, "MATH.solveCubeCut", "MATH.cubeCut"):
                problems.append("正方体截面绘图必须把 MATH.solveCubeCut 的结果传给 MATH.cubeCut，禁止绘图和结果各算一套")
            if "__MATH_CUBE_RESULT__" not in js_code:
                problems.append("正方体截面页必须暴露 window.__MATH_CUBE_RESULT__，供独立审查器复算")
            if not re.search(r"MATH\s*\.\s*solveCubeCut\s*\(", js_code, re.I):
                problems.append("每次参数更新都必须先调用 MATH.solveCubeCut")
        if skeleton.get("solver_api") == "MATH.solveCuboidCut":
            if not draws_solver_result(js_code, "MATH.solveCuboidCut", "MATH.cuboidSection"):
                problems.append("长方体截面绘图必须使用 MATH.solveCuboidCut 的同一结果对象")
            if "__MATH_POLYHEDRON_RESULT__" not in js_code:
                problems.append("长方体截面页必须暴露 window.__MATH_POLYHEDRON_RESULT__，供独立审查器复算")
        if skeleton.get("solver_api") == "MATH.solveTriangularPrismCut":
            if not draws_solver_result(js_code, "MATH.solveTriangularPrismCut", "MATH.triangularPrismSection"):
                problems.append("三棱柱截面绘图必须使用 MATH.solveTriangularPrismCut 的同一结果对象")
            if "__MATH_POLYHEDRON_RESULT__" not in js_code:
                problems.append("三棱柱截面页必须暴露 window.__MATH_POLYHEDRON_RESULT__，供独立审查器复算")
        if skeleton.get("solver_api") == "MATH.solveSquarePyramidCut":
            if not draws_solver_result(js_code, "MATH.solveSquarePyramidCut", "MATH.squarePyramidSection"):
                problems.append("正四棱锥截面绘图必须使用 MATH.solveSquarePyramidCut 的同一结果对象")
            if "__MATH_POLYHEDRON_RESULT__" not in js_code:
                problems.append("正四棱锥截面页必须暴露 window.__MATH_POLYHEDRON_RESULT__，供独立审查器复算")
        if skeleton.get("solver_api") == "MATH.solveCylinderCut":
            if not draws_solver_result(js_code, "MATH.solveCylinderCut", "MATH.cylinderSection"):
                problems.append("圆柱截面图示必须使用 MATH.solveCylinderCut 的同一结果对象")
            if "__MATH_CYLINDER_RESULT__" not in js_code:
                problems.append("圆柱截面页必须暴露 window.__MATH_CYLINDER_RESULT__，供独立审查器复算")
            if not re.search(r"MATH\s*\.\s*solveCylinderCut\s*\(", js_code, re.I):
                problems.append("每次参数更新都必须调用 MATH.solveCylinderCut")
        if skeleton.get("solver_api") == "MATH.solveConeCut":
            if not draws_solver_result(js_code, "MATH.solveConeCut", "MATH.coneSection"):
                problems.append("圆锥截面图示必须使用 MATH.solveConeCut 的同一结果对象")
            if "__MATH_CONE_RESULT__" not in js_code:
                problems.append("圆锥截面页必须暴露 window.__MATH_CONE_RESULT__，供独立审查器复算")
        if skeleton.get("solver_api") == "MATH.solveSphereCut":
            if not draws_solver_result(js_code, "MATH.solveSphereCut", "MATH.sphereSection"):
                problems.append("球体截面图示必须使用 MATH.solveSphereCut 的同一结果对象")
            if "__MATH_SPHERE_RESULT__" not in js_code:
                problems.append("球体截面页必须暴露 window.__MATH_SPHERE_RESULT__，供独立审查器复算")
        if skeleton.get("solver_api") == "MATH.solveSpatialMetrics":
            if not re.search(r"MATH\s*\.\s*solveSpatialMetrics\s*\(", js_code, re.I):
                problems.append("空间距离/角度页面必须调用 MATH.solveSpatialMetrics")
            if "__MATH_SPATIAL_REQUEST__" not in js_code or "__MATH_SPATIAL_RESULT__" not in js_code:
                problems.append("空间距离/角度页面必须暴露求解请求和结果，供独立审查器复算")
        if skeleton.get("solver_api") == "MATH.solveSolidVolume":
            if not composite_volume and not re.search(r"MATH\s*\.\s*solveSolidVolume\s*\(", js_code, re.I):
                problems.append("立体体积页面必须调用 MATH.solveSolidVolume")
            if "__MATH_VOLUME_REQUEST__" not in js_code or "__MATH_VOLUME_RESULT__" not in js_code:
                problems.append("立体体积页面必须暴露求解请求和结果，供独立审查器复算")
        if skeleton.get("solver_api") == "MATH.solveCubeNet":
            if not re.search(r"MATH\s*\.\s*solveCubeNet\s*\(", js_code, re.I):
                problems.append("正方体展开折叠页面必须调用 MATH.solveCubeNet")
            if "__MATH_CUBE_NET_REQUEST__" not in js_code or "__MATH_CUBE_NET_RESULT__" not in js_code:
                problems.append("正方体展开折叠页面必须暴露求解请求和结果，供独立审查器复算")
            if not re.search(r"\.\s*faces\b|MATHPAGE\.drawCubeNet\(", js_code, re.I):
                problems.append("正方体折叠空间图必须使用 MATH.solveCubeNet 返回的六面坐标")
        if skeleton.get("solver_api") == "MATH.solveCuboidNet":
            if not re.search(r"MATH\s*\.\s*solveCuboidNet\s*\(", js_code, re.I):
                problems.append("长方体展开折叠页面必须调用 MATH.solveCuboidNet")
            if "__MATH_CUBOID_NET_REQUEST__" not in js_code or "__MATH_CUBOID_NET_RESULT__" not in js_code:
                problems.append("长方体展开折叠页面必须暴露求解请求和结果，供独立审查器复算")
            if not re.search(r"\.\s*faces\b|MATHPAGE\.drawCuboidNet\(", js_code, re.I):
                problems.append("长方体折叠空间图必须使用 MATH.solveCuboidNet 返回的六面坐标")
        if skeleton.get("solver_api") == "MATH.solveCylinderNet":
            if not re.search(r"MATH\s*\.\s*solveCylinderNet\s*\(", js_code, re.I):
                problems.append("圆柱展开页面必须调用 MATH.solveCylinderNet")
            if "__MATH_CYLINDER_NET_REQUEST__" not in js_code or "__MATH_CYLINDER_NET_RESULT__" not in js_code:
                problems.append("圆柱展开页面必须暴露求解请求和结果，供独立审查器复算")
            if not re.search(r"\.\s*surface_grid\b|MATHPAGE\.drawCylinderNet\(", js_code, re.I):
                problems.append("折叠圆柱图必须使用 MATH.solveCylinderNet 返回的 surface_grid")
        if skeleton.get("solver_api") == "MATH.solveConeNet":
            if not re.search(r"MATH\s*\.\s*solveConeNet\s*\(", js_code, re.I):
                problems.append("圆锥展开页面必须调用 MATH.solveConeNet")
            if "__MATH_CONE_NET_REQUEST__" not in js_code or "__MATH_CONE_NET_RESULT__" not in js_code:
                problems.append("圆锥展开页面必须暴露求解请求和结果，供独立审查器复算")
            if not re.search(r"\.\s*(?:side_grid|sector_boundary)\b|MATHPAGE\.drawConeNet\(", js_code, re.I):
                problems.append("圆锥展开图和折叠图必须使用 MATH.solveConeNet 返回的几何数据")
    expected_visual = skeleton["visual_type"]
    visual_match = re.search(r'<(?:canvas|svg)\b[^>]*\bdata-visual-type=["\']([^"\']+)', visual, re.I)
    if visual_match and visual_match.group(1).lower() != expected_visual:
        problems.append("选定骨架 %s 的演示类型应为 %s，当前写成 %s"
                        % (skeleton["id"], expected_visual, visual_match.group(1)))
    if skeleton.get("no_step_flow") and re.search(
            r"实验六步流程|步骤\s*[1-6]\s*[.、:]|暗处理.{0,28}遮光|遮光.{0,28}光照",
            visual, re.I | re.S):
        problems.append("生物光合作用骨架要求②区只显示实验图，不能在演示区放步骤流程；请把步骤控件移到③区")
    if (required_scene and required_scene[1] in ("MATH.cubeCut", "MATH.cuboidSection", "MATH.triangularPrismSection", "MATH.squarePyramidSection", "MATH.cylinderSection")
            and re.search(r"恢复.{0,4}视角|默认视角|重置视角", (secs.get("3") or "") + "\n" + js_code)
            and not re.search(r"MATH\s*\.\s*resetView\s*\(", js_code, re.I)):
        problems.append("页面提供了恢复视角按钮，但没有调用 MATH.resetView(canvas)；必须恢复 yaw/pitch 初始值并重绘，不能只调用 render()")
    if not re.search(r'<(?:canvas|svg)\b[^>]*\bdata-visual-type=["\'](?:apparatus|graph|geometry|process|molecular|diagram)["\']',
                     visual, re.I):
        problems.append("②区 canvas/svg 缺少有效的 data-visual-type（apparatus/graph/geometry/process/molecular/diagram）")
    if re.search(r'<(?:img|image|picture|video)\b|url\s*\(|background-image\s*:',
                 visual + "\n" + (secs.get("css") or ""), re.I):
        problems.append("②演示区不得嵌入图片或 CSS 图片；请改为状态驱动的 Canvas/SVG 矢量绘制")

    # 关键容器类名，缺了页面会错位
    for key, must in [("3", "exp-field"), ("4", "exp-formula"), ("5", "exp-table")]:
        if key not in missing and must not in (secs.get(key) or ""):
            problems.append("区域 <!--%s--> 里缺少平台类名 .%s" % (key, must))

    js = secs.get("js") or ""
    full = "\n".join(secs.get(k, "") for k, _ in shell.SECTIONS) + "\n" + js
    urls = re.findall(r"https?://[^\s\"'<>)]+", full)
    urls = [u for u in urls if "w3.org" not in u]
    if urls:
        problems.append("内容里出现外部链接（离线会失效）：%s" % "、".join(urls[:3]))

    if "__data__" not in full.lower() and "__geo__" not in full.lower():
        problems.append("没有暴露机读数据（window.__DATA__ 或 window.__GEO__），审查无法复算")

    if len(full) > 16000:
        problems.append("内容过长（%d 字符），超过 16000 字符上限" % len(full))

    return problems


# ============ 3. 兜底：给一个能过校验的最小实验 ============

FALLBACK = {
    "1": """<h2 class="exp-name">{topic}</h2>
<div class="exp-tags">
  <span class="exp-tag">{subject}</span>
  <span class="exp-tag">{grade}</span>
  <span class="exp-tag is-plain">兜底演示（模型输出未通过校验）</span>
</div>
<div class="exp-goals-title">学习目标</div>
<ul class="exp-goals">
  <li>能通过调节参数观察结果的变化趋势</li>
  <li>能读出一组参数对应的数值结果</li>
  <li>能记录多组数据并比较差异</li>
</ul>""",

    "2": """<canvas id="cv" data-visual-type="graph"></canvas>
<span class="exp-canvas-tip">拖动滑块可改变参数</span>""",

    "3": """<div class="exp-field">
  <div class="exp-label"><span>自变量 x</span><span class="exp-val"><b id="v-x">2.0</b></span></div>
  <input type="range" id="rg-x" min="0" max="10" step="0.5" value="2" data-key="x">
</div>
<div class="exp-field">
  <div class="exp-label"><span>系数 k</span><span class="exp-val"><b id="v-k">1.5</b></span></div>
  <input type="range" id="rg-k" min="0.5" max="3" step="0.1" value="1.5" data-key="k">
</div>
<div class="exp-btns">
  <button class="exp-btn is-primary" id="btn-record" type="button">记录当前数据</button>
  <button class="exp-btn" id="btn-reset" type="button">重置</button>
</div>""",

    "4": """<div class="exp-reads">
  <div class="exp-read"><span class="k">自变量 x</span><span class="v"><b id="r-x">2.0</b></span></div>
  <div class="exp-read"><span class="k">结果 y</span><span class="v"><b id="r-y">3.00</b></span></div>
</div>
<div class="exp-formula" id="fml"></div>
<p class="exp-note" id="hint">拖动滑块，观察 y 随 x 的变化。</p>
<div class="exp-alert" id="alert" hidden></div>""",

    "5": """<table class="exp-table">
  <thead><tr><th>序号</th><th>x</th><th>k</th><th>y</th><th>y ÷ x</th></tr></thead>
  <tbody id="rows"></tbody>
</table>""",

    "6": """<h3>原理</h3>
<ul><li>本页为兜底演示：结果由 y = kx 计算得出，改变 k 会改变直线斜率。</li></ul>
<h3>易错点</h3>
<ul><li>k 为常数时 y 与 x 成正比，比值 y ÷ x 保持不变。</li></ul>
<h3>探究问题</h3>
<ol><li>固定 k，改变 x，y ÷ x 是否改变？</li><li>改变 k，直线的倾斜程度如何变化？</li></ol>
<h3>结论</h3>
<p>k 不变时 y 与 x 成正比，比值恒为 k；改变 k 只改变斜率，不改变正比关系。</p>
<h3>注意事项</h3>
<ul><li>兜底页只保证"能打开、能操作、数值自洽"，学科内容需重新生成。</li></ul>""",

    "js": """(function () {
  var state = { x: 2, k: 1.5 };
  var cv = document.getElementById('cv');
  var ctx = cv.getContext('2d');

  function draw() {
    var box = cv.parentElement;
    var dpr = window.devicePixelRatio || 1;
    var w = box.clientWidth || 600, h = box.clientHeight || 360;
    cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr);
    cv.style.width = w + 'px'; cv.style.height = h + 'px';
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    var L = 46, R = 18, T = 18, B = 34;
    var pw = w - L - R, ph = h - T - B;
    var ymax = 30;
    ctx.strokeStyle = '#cfe2f5'; ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(L, T); ctx.lineTo(L, T + ph); ctx.lineTo(L + pw, T + ph);
    ctx.stroke();
    ctx.fillStyle = '#6b7f96'; ctx.font = '12px sans-serif';
    ctx.fillText('y', L - 12, T + 6);
    ctx.fillText('x', L + pw - 4, T + ph + 18);
    ctx.beginPath();
    ctx.moveTo(L, T + ph - (state.k * 10 / ymax) * ph);
    ctx.lineTo(L + pw, T + ph - (state.k * 10 / ymax) * ph);
    ctx.strokeStyle = '#3b86c9'; ctx.lineWidth = 2.2; ctx.stroke();
    var px = L + (state.x / 10) * pw;
    var py = T + ph - (state.k * state.x / ymax) * ph;
    ctx.beginPath(); ctx.arc(px, py, 5, 0, Math.PI * 2);
    ctx.fillStyle = '#b5561b'; ctx.fill();
  }

  function render() {
    var y = state.k * state.x;
    document.getElementById('v-x').textContent = state.x.toFixed(1);
    document.getElementById('v-k').textContent = state.k.toFixed(1);
    document.getElementById('r-x').textContent = state.x.toFixed(1);
    document.getElementById('r-y').textContent = y.toFixed(2);
    document.getElementById('fml').innerHTML =
      'y = k × x = ' + state.k.toFixed(1) + ' × ' + state.x.toFixed(1) + ' = <em>' + y.toFixed(2) + '</em>';
    draw();
    window.__DATA__ = {
      params: { x: state.x, k: state.k },
      result: { y: y },
      checks: { ratio_stable: Math.abs(y - state.k * state.x) < 1e-9 }
    };
  }

  document.querySelectorAll('input[type=range]').forEach(function (el) {
    el.addEventListener('input', function () {
      state[el.dataset.key] = +el.value; render();
    });
  });

  document.getElementById('btn-reset').addEventListener('click', function () {
    state.x = 2; state.k = 1.5;
    document.getElementById('rg-x').value = 2;
    document.getElementById('rg-k').value = 1.5;
    document.getElementById('rows').innerHTML = '';
    render();
  });

  document.getElementById('btn-record').addEventListener('click', function () {
    var rows = document.getElementById('rows');
    var tr = document.createElement('tr');
    var y = state.k * state.x;
    var cells = [rows.children.length + 1, state.x.toFixed(1), state.k.toFixed(1),
                 y.toFixed(2), (y / state.x).toFixed(2)];
    for (var i = 0; i < cells.length; i++) {
      var td = document.createElement('td');
      td.textContent = cells[i];
      tr.appendChild(td);
    }
    rows.appendChild(tr);
  });

  window.addEventListener('resize', draw);
  render();
})();""",
}


def render_fallback(req):
    """模型不可用或输出不合格时的兜底：返回六块内容（不是完整 HTML）。"""
    topic = req.get("实验主题") or "参数与结果演示"
    secs = {}
    for k, tpl in FALLBACK.items():
        secs[k] = tpl
    secs["1"] = FALLBACK["1"].format(topic=topic,
                                     subject=req.get("学科") or "通用",
                                     grade=req.get("年级") or "初中")
    secs["css"] = ""
    return secs


# ============ 4. 生成主流程 ============

def render_deterministic(req, skeleton, meta, started):
    """确定性渲染 + 教学闭环补齐（结论 / 注意事项只在缺失时追加）。"""
    result = _render_deterministic_impl(req, skeleton, meta, started)
    if result is None:
        return None
    sections, info = result
    try:
        import page_fill
        filled = page_fill.ensure_teaching(sections, (skeleton or {}).get("subject"))
        if filled:
            info["补齐项"] = filled
    except Exception:  # noqa: BLE001 - 补齐失败不应阻断出页
        pass
    return sections, info


def _render_deterministic_impl(req, skeleton, meta, started):
    """按 scene_catalog 的调度做确定性渲染。

    返回 (secs, meta)；返回 None 表示"该场景没有确定性渲染器"，调用方转大模型。

    三类场景共用这一条路径：
    * 化学组件模板 —— 先解析配置（物种/条件超范围就直接判不可交付，不猜）
    * 通用 PageSpec 场景 —— scene_catalog 用 UI 元数据拼出 PageSpec，组件树渲染
    * 数学 / 早期物理模板 —— scene_catalog 分发到既有装配代码
    """
    import scene_catalog
    import solver_templates as st
    scene_id = (skeleton or {}).get("id")
    subject = (skeleton or {}).get("subject") or ""

    chem = scene_catalog.CHEM_TEMPLATES.get(scene_id)
    if chem:
        try:
            config = getattr(st, chem["resolve"])(req or {})
        except ValueError as exc:
            problem = chem["error"] % exc
            secs = render_fallback(req or {})
            meta.update({"来源": chem["fallback"], "模型": "未调用",
                         "生成契约通过": False, "问题": [problem]})
            meta["生成尝试"].append({"来源": chem["fallback"] + "参数检查",
                                     "问题数": 1, "问题": [problem]})
            meta["耗时秒"] = round(time.time() - started, 2)
            return secs, meta
        secs = getattr(st, chem["render"])(req or {}, config=config)
        problems = hard_validate(secs, req, managed_readouts=True)
        meta.update({"来源": chem["label"], "模型": "未调用（组件装配与确定性求解）",
                     "生成契约通过": not problems, "问题": problems})
        meta["生成尝试"].append({"来源": chem["label"], "问题数": len(problems),
                                 "问题": problems})
        if chem.get("values"):
            meta[chem["meta"]] = getattr(st, chem["values"])(req)
        meta["耗时秒"] = round(time.time() - started, 2)
        return secs, meta

    if not scene_catalog.has_renderer(skeleton):
        return None
    try:
        secs = st.render_solver_template(req or {}, skeleton)
    except MathPlanError as exc:
        problem = "%s页面参数或组件超出当前范围：%s" % (subject or "该", exc)
        meta.update({"来源": (subject or "场景") + "配置待补齐", "模型": "未调用",
                     "问题": [problem], "耗时秒": round(time.time() - started, 2)})
        meta["生成尝试"].append({"来源": (subject or "场景") + "配置检查",
                                 "问题数": 1, "问题": [problem]})
        return render_fallback(req or {}), meta
    if secs is None:
        return None
    problems = hard_validate(secs, req, managed_readouts=True)
    source = scene_catalog.renderer_label(scene_id, subject)
    meta.update({"来源": source, "模型": "未调用（固定模板渲染）",
                 "生成契约通过": not problems, "问题": problems,
                 "耗时秒": round(time.time() - started, 2)})
    meta["生成尝试"].append({"来源": source, "问题数": len(problems), "问题": problems})
    return secs, meta


def generate(req, pack, feedback=None, template_only=False):
    started = time.time()
    selected_skeleton = select_page_skeleton(req or {})
    meta = {"来源": "兜底片段", "模型": "-", "是否修复过": False, "续写次数": 0,
            "问题": [], "模型输出问题": [], "生成契约通过": False,
            "生成尝试": [], "外壳校验": [],
            "页面骨架": {"id": selected_skeleton["id"],
                         "画布类型": selected_skeleton["visual_type"],
                         "场景库API": selected_skeleton.get("api"),
                         "学科求解器": selected_skeleton.get("solver_api")}}

    # ---------- 确定性渲染（调度表唯一来源：scene_catalog） ----------
    # 以前这里有 5 段几乎逐字重复的化学分支，外加一个写死三个 physics id 的元组，
    # 加场景要同时改这里、scene_registry 和 solver_templates 三处。
    # 现在只有一次调用：场景能确定性渲染就用模板，不能就交给大模型。
    deterministic = render_deterministic(req, selected_skeleton, meta, started)
    if deterministic is not None:
        return deterministic

    if template_only or not HAS_LLM or not get_config()["api_key"]:
        if not template_only and HAS_LLM and not get_config()["api_key"]:
            print("   未检测到 API Key，使用兜底片段生成（效果同样可演示）")
        secs = render_solver_template(req or {}, selected_skeleton)
        if secs is not None:
            problems = hard_validate(secs, req)
            meta["来源"] = "场景库确定性模板"
            meta["生成契约通过"] = not problems
            meta["问题"] = problems
            meta["生成尝试"].append({"来源": "场景库确定性模板", "问题数": len(problems), "问题": problems})
        else:
            secs = render_fallback(req)
            problems = hard_validate(secs, req) if selected_skeleton.get("solver_api") else []
            meta["来源"] = ("兜底片段（求解器契约未满足）"
                            if selected_skeleton.get("solver_api") else "兜底片段")
            meta["生成契约通过"] = not problems and not selected_skeleton.get("solver_api")
            meta["问题"] = problems
        meta["耗时秒"] = round(time.time() - started, 2)
        return secs, meta

    messages = [
        {"role": "system", "content": GENERATOR_SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(req, pack, feedback)},
    ]

    print("   正在调用模型生成六块内容 ...")
    raw, _ = call_llm(messages, temperature=0.7, timeout=300, max_tokens=8192)
    secs = clean_sections(raw)
    meta["来源"] = "大模型"
    meta["模型"] = get_config()["model"]

    problems = hard_validate(secs, req, managed_readouts=True)
    best_secs, best_problems = secs, problems
    meta["生成尝试"].append({"来源": "大模型首轮", "问题数": len(problems), "问题": problems})

    # 不合格 → 带着问题清单让模型自己修一次
    if problems:
        print("   校验未通过（%d 项），触发自动修复 ..." % len(problems))
        messages.append({"role": "assistant", "content": raw})
        messages.append({
            "role": "user",
            "content": (
                "本页的生成器硬校验未通过。请按清单逐项修复，尤其不能遗漏求解器接线、"
                "可见输出标记和可操作控件；不得用手算结果、静态文案或仅在注释里提及 API 来代替调用。\n"
                "选中骨架：%s\n必需求解器：%s\n场景契约：%s\n\n"
                "未通过项：\n- %s\n\n"
                "请保留满足要求的教学内容，输出修复后的完整八块内容"
                "（<!--1--> 到 <!--6-->、<!--CSS-->、<!--JS-->），只输出内容，不要解释。"
                % (selected_skeleton.get("id"), selected_skeleton.get("solver_api") or "无",
                   selected_skeleton.get("solver_contract") or "无专用求解器契约",
                   "\n- ".join(problems))
            ),
        })
        raw2, _ = call_llm(messages, temperature=0.3, timeout=300, max_tokens=8192)
        secs2 = clean_sections(raw2)
        problems2 = hard_validate(secs2, req, managed_readouts=True)
        meta["是否修复过"] = True
        meta["生成尝试"].append({"来源": "大模型自动修复", "问题数": len(problems2), "问题": problems2})

        if not problems2:
            best_secs, best_problems = secs2, []
        elif len(problems2) < len(best_problems):
            best_secs, best_problems = secs2, problems2

    if best_problems:
        # Solver pages must not silently degrade into an unrelated generic demo.
        # Use a deterministic scene template when available; otherwise retain
        # the best model candidate and mark it unpublishable in metadata.
        template_secs = render_solver_template(req or {}, selected_skeleton)
        template_problems = hard_validate(template_secs, req) if template_secs is not None else None
        if template_secs is not None and not template_problems:
            secs = template_secs
            meta["来源"] = "场景库确定性模板（模型输出未通过校验）"
            meta["模型输出问题"] = best_problems
            meta["生成契约通过"] = True
            meta["问题"] = []
        elif selected_skeleton.get("solver_api"):
            secs = best_secs
            meta["来源"] = "大模型候选（求解器契约未通过）"
            meta["生成契约通过"] = False
            meta["问题"] = best_problems
        else:
            secs = render_fallback(req)
            fallback_problems = hard_validate(secs, req)
            meta["来源"] = "兜底片段（模型输出未通过校验）"
            meta["生成契约通过"] = not fallback_problems
            meta["问题"] = best_problems
    else:
        secs = best_secs
        meta["生成契约通过"] = True
        meta["问题"] = []

    meta["耗时秒"] = round(time.time() - started, 2)
    return secs, meta


# ============ 5. 存盘（装配 + 资源 + zip） ============

def save(secs, req, meta):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    # 页眉/文件名都用「实验名字」，不用整句主题（名字只出现在蓝色条上一次）
    title = req.get("实验名称") or req.get("实验主题") or "教学资源"
    name = shell.safe_name(shell.short_title(title))
    if not meta.get("生成契约通过", True):
        name += "_待修复不可交付"
    html = shell.render(name, secs, slug=name)

    html_path = os.path.join(OUTPUT_DIR, "教学资源_%s.html" % name)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    # 外壳资源必须与 html 同目录，否则双击打开会没有样式
    for res in ("frame.css", "exp.css", "logo.png"):
        shutil.copy2(os.path.join(shell.FRAME_DIR, res),
                     os.path.join(OUTPUT_DIR, res))

    # The shell's download dialog links to ``<slug>.zip``. Keep the historical
    # prefixed archive as an alias for existing scripts, but make the linked
    # archive the canonical metadata/CLI result.
    zip_path = os.path.join(OUTPUT_DIR, "%s.zip" % name)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(html_path, "%s.html" % name)
        for res in ("frame.css", "exp.css", "logo.png"):
            z.write(os.path.join(OUTPUT_DIR, res), res)
    legacy_zip_path = os.path.join(OUTPUT_DIR, "教学资源_%s.zip" % name)
    if legacy_zip_path != zip_path:
        shutil.copy2(zip_path, legacy_zip_path)

    meta_path = os.path.join(OUTPUT_DIR, "教学资源_%s.meta.json" % name)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({"实验主题": title, "生成信息": meta,
                   "字符数": len(html), "内容字符数": sum(len(secs.get(k, ""))
                                                    for k in ("1", "2", "3", "4", "5", "6", "js")),
                   "文件": os.path.basename(html_path),
                   "压缩包": os.path.basename(zip_path)},
                  f, ensure_ascii=False, indent=2)

    return html_path, meta_path, zip_path


# ============ 入口 ============

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--req", help="需求 JSON 路径")
    parser.add_argument("--kb", help="知识包 JSON 路径")
    parser.add_argument("--feedback", help="上一版被打回时的修改意见")
    parser.add_argument("--template-only", action="store_true", help="不调模型，只用兜底片段")
    parser.add_argument("--open", action="store_true", help="生成后用浏览器打开")
    parser.add_argument("--show-prompt", action="store_true", help="只打印最终提示词，不调用模型")
    args = parser.parse_args()

    load_env()
    req, pack, req_path, kb_path = load_inputs(args.req, args.kb)

    print("\n[1/3] 读取输入")
    print("   需求：%s" % os.path.basename(req_path))
    print("   知识：%s（%d 个类别）" % (os.path.basename(kb_path), len(pack)))
    print("   主题：%s" % req.get("实验主题"))

    if args.show_prompt:
        print("\n===== SYSTEM =====")
        print(GENERATOR_SYSTEM_PROMPT)
        print("\n===== USER =====")
        print(build_user_prompt(req, pack, args.feedback))
        return

    print("[2/3] 生成六块内容")
    secs, meta = generate(req, pack, args.feedback, args.template_only)

    print("[3/3] 装配外壳与校验")
    shell_problems = shell.validate(shell.render("预览", secs))
    meta["外壳校验"] = shell_problems
    path, report_path, zip_path = save(secs, req, meta)

    print("")
    print("=" * 58)
    print("生成来源   %s" % meta["来源"])
    print("耗时       %.2fs" % meta["耗时秒"])
    print("生成契约   %s" % ("通过" if meta.get("生成契约通过") else "未通过（不可交付）"))
    print("内容字符   %d" % sum(len(secs.get(k, "")) for k in ("1", "2", "3", "4", "5", "6", "js")))
    print("外壳校验   %s" % ("通过" if not shell_problems else "未通过：" + "；".join(shell_problems)))
    if meta["问题"]:
        print("内容问题   %s" % "；".join(meta["问题"]))
    print("HTML       %s" % path)
    print("压缩包     %s" % zip_path)
    print("元信息     %s" % report_path)
    print("=" * 58)

    if args.open and os.name == "nt":
        os.startfile(path)

    print("\n提示：直接双击 HTML 就能在浏览器里操作，不需要联网、不需要服务器。")


if __name__ == "__main__":
    main()
