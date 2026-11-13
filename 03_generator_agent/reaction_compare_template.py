# -*- coding: utf-8 -*-
"""reaction_compare_template.py —— 置换反应「现象 + 方程式 + 反应计量」确定性页面。

为什么单独建这个模板：
    铁与硫酸铜是“看得见现象 + 写得出方程式 + 算得清限量试剂”的典型页。
    以前这类页面交给大模型自由写，容易出现三个问题：
      1. 只画图，不暴露 __CHEM_BALANCE_* / __CHEM_STOICH_*，审查端无法复算；
      2. 方程式和计量各算一套，读数与画面不一致；
      3. 画布里的标签撞边、被裁切。
    这里把三件事固定成一条链路：
      CHEMSOLVER.balanceEquation → CHEMSOLVER.solveStoichiometry → CHEM.scene
    读数、记录表、方程式、画面全部读同一份 result。

适用范围：
    首版只做 Fe + CuSO4 → FeSO4 + Cu 这一个已核验反应；其他置换反应不猜产物，
    由上层选择别的场景或明确拒绝。
"""

import html


REACTION = {"reactants": ["Fe", "CuSO4"], "products": ["FeSO4", "Cu"]}
DEFAULT_IRON_MOL = 0.05
DEFAULT_COPPER_MOL = 0.04
DEFAULT_VOLUME_ML = 100


def _fmt(value, digits=4):
    try:
        return ("%." + str(digits) + "f") % float(value)
    except (TypeError, ValueError):
        return "—"


def render_reaction_compare_template(req=None):
    """返回六区域内容；由 shell.py 套外壳、由生成器硬校验。"""
    req = req or {}
    req = req or {}
    # 这个模板只服务已核验的 Fe + CuSO4 反应；其他置换反应不能套用同一套
    # 产物和现象，宁可返回 None 交给上层（大模型/拒绝），也不能生成错反应。
    probe = " ".join(str(req.get(key) or "") for key in
                     ("实验名称", "实验主题", "原始需求", "学习目标"))
    if "铁" not in probe or "硫酸铜" not in probe:
        return None
    grade = html.escape(str(req.get("年级") or "初中九年级"))
    goals = req.get("学习目标") or [
        "能描述铁与硫酸铜溶液反应的现象：蓝色变浅绿色，铁钉表面析出红色铜。",
        "能写出 Fe + CuSO₄ → FeSO₄ + Cu，并用原子守恒说明系数。",
        "能判断限量试剂，读出剩余铁、生成铜和反应进度。",
    ]
    if isinstance(goals, str):
        goals = [goals]
    goal_html = "".join("<li>%s</li>" % html.escape(str(item)) for item in goals if str(item).strip())

    sections = {
        "1": (
            '<div class="exp-tags"><span class="exp-tag">化学</span>'
            '<span class="exp-tag">%s</span>'
            '<span class="exp-tag is-plain">教学演示（虚拟仿真）</span></div>'
            '<p>实验性质：虚拟仿真，按理想溶液、完全反应模型计算，不作为真实实验操作指导。</p>'
            '<div class="exp-goals-title">学习目标</div><ul class="exp-goals">%s</ul>'
            % (grade, goal_html)
        ),
        "2": (
            '<canvas id="fe-scene" data-visual-type="apparatus" '
            'aria-label="铁与硫酸铜溶液反应前后的双烧杯对比"></canvas>'
            '<p class="exp-formula" id="fe-equation" data-chem-balance-equation '
            'data-chem-stoich-equation>Fe + CuSO4 → FeSO4 + Cu</p>'
            '<p class="exp-note">左：反应前烧杯中的蓝色 CuSO₄ 溶液与铁钉；右：反应后烧杯中的浅绿色 FeSO₄ 溶液与析出的红色铜。</p>'
        ),
        "3": (
            '<label class="exp-field"><span class="exp-label"><span>铁粉的量 n(Fe)</span>'
            '<span class="exp-val"><b id="fe-amount-label">%s</b> mol</span></span>'
            '<input id="fe-amount" type="number" min="0.001" max="0.2" step="any" value="%s" '
            'data-chem-stoich-amount-index="0" aria-label="铁粉物质的量"></label>'
            '<label class="exp-field"><span class="exp-label"><span>硫酸铜的量 n(CuSO₄)</span>'
            '<span class="exp-val"><b id="fe-cuso4-label">%s</b> mol</span></span>'
            '<input id="fe-cuso4" type="number" min="0.001" max="0.2" step="any" value="%s" '
            'data-chem-stoich-amount-index="1" aria-label="硫酸铜物质的量"></label>'
            '<label class="exp-field"><span class="exp-label"><span>反应进度</span>'
            '<span class="exp-val"><b id="fe-progress-label">0%%</b></span></span>'
            '<input id="fe-progress" type="range" min="0" max="1" step="0.01" value="0" '
            'data-chem-stoich-progress aria-label="反应进度"></label>'
            '<div class="exp-btns">'
            '<button class="exp-btn is-primary" id="btn-record" type="button">记录当前数据</button>'
            '<button class="exp-btn" id="btn-reset" type="button">重置</button>'
            '</div>'
            % (_fmt(DEFAULT_IRON_MOL), DEFAULT_IRON_MOL, _fmt(DEFAULT_COPPER_MOL), DEFAULT_COPPER_MOL)
        ),
        "4": (
            '<div class="exp-reads">'
            '<div class="exp-read"><span class="k">反应进度</span><span class="v"><b data-solver-field="progress">0%</b></span></div>'
            '<div class="exp-read"><span class="k">限量试剂</span><span class="v"><b data-solver-field="limiting">—</b></span></div>'
            '<div class="exp-read"><span class="k">剩余铁</span><span class="v"><b data-solver-field="remaining_fe">—</b> mol</span></div>'
            '<div class="exp-read"><span class="k">生成铜</span><span class="v"><b data-solver-field="produced_cu">—</b> mol</span></div>'
            '</div>'
            '<div class="exp-formula" id="fe-formula">—</div>'
            '<p class="exp-note" id="fe-state">调整铁的量和硫酸铜的量，观察谁是限量试剂。</p>'
            '<p class="exp-alert" data-solver-error hidden></p>'
        ),
        "5": (
            '<div class="exp-table-wrap"><table class="exp-table"><thead><tr>'
            '<th>序号</th><th>n(Fe)/mol</th><th>n(CuSO₄)/mol</th><th>进度</th>'
            '<th>限量试剂</th><th>剩余铁/mol</th><th>生成铜/mol</th>'
            '</tr></thead><tbody id="fe-rows"></tbody></table></div>'
        ),
        "6": (
            '<h3>原理</h3><p>铁把铜从硫酸铜溶液里置换出来：Fe + CuSO₄ → FeSO₄ + Cu。'
            '溶液中的 Cu²⁺ 被消耗，蓝色变浅；Fe²⁺ 进入溶液，呈浅绿色；铜在铁表面析出，呈红色。</p>'
            '<h3>易错点</h3><p>方程式要配平：1 个 Fe 置换 1 个 Cu²⁺，生成 1 个 Fe²⁺ 和 1 个 Cu。'
            '限量试剂不是“量少的那个”，而是按化学计量比先被消耗完的那个。</p>'
            '<h3>探究问题</h3><p>保持硫酸铜的量不变，逐步增加铁粉的量。剩余铁、生成铜和反应进度怎样变化？'
            '哪一刻铁刚好不过量？</p>'
            '<h3>结论</h3><p>反应按 1:1 的物质的量比进行；限量试剂决定最大反应进度，'
            '生成铜的量由实际反应进度和硫酸铜的量共同决定。</p>'
            '<h3>注意事项</h3><p>本页为虚拟仿真，不给出真实药品用量或操作步骤；'
            '真实实验应在教师指导下进行，注意硫酸铜溶液的安全使用。</p>'
        ),
        "css": (
            '#fe-scene{display:block;width:100%;height:600px;max-width:100%}'
            '#sec-stage .exp-canvas-box{height:600px;min-height:600px;max-height:600px}'
            '.exp-field input[type="number"]{width:100%;max-width:100%;box-sizing:border-box}'
            '.exp-field input[type="range"]{width:100%;max-width:100%}'
            '#fe-equation{font-size:1.05em;font-weight:600;letter-spacing:.02em}'
            '@media(max-width:700px){#fe-scene{height:380px}'
            '#sec-stage .exp-canvas-box{height:380px;min-height:380px;max-height:380px}}'
        ),
    }
    sections["js"] = _script()
    return sections


def _script():
    return r"""
(function () {
  var cv = document.getElementById('fe-scene');
  var rows = document.getElementById('fe-rows');
  var error = document.querySelector('[data-solver-error]');
  var equation = document.getElementById('fe-equation');
  var formula = document.getElementById('fe-formula');
  var stateText = document.getElementById('fe-state');
  var progress = document.getElementById('fe-progress');
  var progressLabel = document.getElementById('fe-progress-label');
  var amountFe = document.getElementById('fe-amount');
  var amountCu = document.getElementById('fe-cuso4');
  var labelFe = document.getElementById('fe-amount-label');
  var labelCu = document.getElementById('fe-cuso4-label');
  var REQUEST = {reactants: ['Fe', 'CuSO4'], products: ['FeSO4', 'Cu']};
  var DEFAULTS = {fe: 0.05, cu: 0.04, progress: 0};
  var latest = null;
  var sequence = 0;

  function number(value, digits) {
    var x = Number(value);
    if (!isFinite(x)) return '—';
    return x.toFixed(digits == null ? 4 : digits);
  }
  function put(selector, text) {
    var el = document.querySelector(selector);
    if (el) el.textContent = text;
  }
  function readNumber(el) {
    var value = Number(el.value);
    if (!isFinite(value)) throw new Error('请填入有效数值。');
    return value;
  }
  function render() {
    var nFe = readNumber(amountFe);
    var nCu = readNumber(amountCu);
    var p = readNumber(progress);
    if (nFe <= 0 || nCu <= 0) throw new Error('铁的量和硫酸铜的量都必须大于 0。');
    if (p < 0 || p > 1) throw new Error('反应进度必须在 0 到 1 之间。');
    window.__CHEM_BALANCE_REQUEST__ = REQUEST;
    var balance = CHEMSOLVER.balanceEquation(REQUEST);
    window.__CHEM_BALANCE_RESULT__ = balance;
    // 硬校验要求读取 atom_counts 与 checks.ok；配平失败必须显示错误态。
    var atoms = balance.atom_counts;
    if (!balance.checks || balance.checks.ok !== true) throw new Error('方程式未配平。');
    var request = {reactants: REQUEST.reactants, products: REQUEST.products,
                   initial_amounts_mol: [nFe, nCu], progress: p};
    window.__CHEM_STOICH_REQUEST__ = request;
    var result = CHEMSOLVER.solveStoichiometry(request);
    window.__CHEM_STOICH_RESULT__ = result;
    window.__DATA__ = {params: {nFe: nFe, nCu: nCu, progress: p}, result: result};
    if (result.checks && result.checks.ok !== true) throw new Error('反应计量未通过守恒校验。');

    equation.textContent = result.equation;
    formula.textContent = 'n(Cu)生成 = n(CuSO₄) × 进度 = ' + number(nCu) + ' × ' + number(p, 2) +
      ' = ' + number(result.products[1].produced_mol) + ' mol';
    progressLabel.textContent = Math.round(p * 100) + '%';
    labelFe.textContent = number(nFe);
    labelCu.textContent = number(nCu);
    put('[data-solver-field="progress"]', Math.round(p * 100) + '%');
    put('[data-solver-field="limiting"]',
        (result.limiting_reactants || []).map(function (item) { return item.formula; }).join('、') || '—');
    put('[data-solver-field="remaining_fe"]', number(result.reactants[0].remaining_mol));
    put('[data-solver-field="produced_cu"]', number(result.products[1].produced_mol));
    stateText.textContent = p <= 0 ? '尚未反应：铁钉表面仍为银白色，溶液为蓝色。'
      : p >= 1 ? '反应结束：蓝色明显变浅，铁钉表面覆盖红色铜。'
      : '反应进行中：蓝色逐渐变浅，铁钉表面开始析出红色铜。';
    var nailLevel = nFe > 0 ? Math.max(0, Math.min(1, result.reactants[0].remaining_mol / nFe)) : 1;
    CHEM.scene(cv, {p: p, V: 100, leftSol: '硫酸铜溶液', rightSol: '硫酸亚铁溶液',
                    nailLevel: nailLevel});
    error.hidden = true;
    latest = {nFe: nFe, nCu: nCu, p: p, result: result};
  }
  function fail(failure) {
    window.__CHEM_STOICH_RESULT__ = null;
    window.__DATA__ = {};
    if (cv) { var ctx = cv.getContext('2d'); if (ctx) ctx.clearRect(0, 0, cv.width, cv.height); }
    if (formula) formula.textContent = '—';
    put('[data-solver-field="progress"]', '—');
    put('[data-solver-field="limiting"]', '—');
    put('[data-solver-field="remaining_fe"]', '—');
    put('[data-solver-field="produced_cu"]', '—');
    if (error) { error.textContent = failure.message; error.hidden = false; }
    latest = null;
  }
  function safeRender() {
    try { render(); } catch (failure) { fail(failure); }
  }
  [amountFe, amountCu, progress].forEach(function (el) {
    el.addEventListener('input', safeRender);
    el.addEventListener('change', safeRender);
  });
  document.getElementById('btn-record').addEventListener('click', function () {
    if (!latest) return;
    sequence += 1;
    var row = rows.insertRow();
    [String(sequence), number(latest.nFe), number(latest.nCu), Math.round(latest.p * 100) + '%',
     (latest.result.limiting_reactants || []).map(function (item) { return item.formula; }).join('、'),
     number(latest.result.reactants[0].remaining_mol), number(latest.result.products[1].produced_mol)]
      .forEach(function (text) { row.insertCell().textContent = text; });
  });
  document.getElementById('btn-reset').addEventListener('click', function () {
    amountFe.value = String(DEFAULTS.fe);
    amountCu.value = String(DEFAULTS.cu);
    progress.value = String(DEFAULTS.progress);
    if (rows) rows.replaceChildren();
    sequence = 0;
    safeRender();
  });
  safeRender();
})();
"""

