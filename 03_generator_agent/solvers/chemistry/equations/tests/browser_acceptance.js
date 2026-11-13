const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const project = path.resolve(__dirname, '../../../../../');
const solverPath = path.join(project, 'frame', 'chem_solver.js');
const chromePath = process.env.CHROME_PATH || [
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  'C:/Users/wangq/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe',
].find(candidate => fs.existsSync(candidate));

(async () => {
  if (!chromePath) throw new Error('未找到 Chrome、Edge 或 Playwright Chromium');
  const browser = await chromium.launch({ headless: true, executablePath: chromePath });
  try {
    const page = await browser.newPage({ viewport: { width: 1000, height: 720 } });
    const pageErrors = [];
    page.on('pageerror', error => pageErrors.push(error.message));
    await page.setContent('<main><output data-chem-balance-equation></output>' +
      '<input type="number" data-chem-balance-coefficient-side="reactants" data-chem-balance-coefficient-index="0" value="1">' +
      '<input type="number" data-chem-balance-coefficient-side="reactants" data-chem-balance-coefficient-index="1" value="1">' +
      '<input type="number" data-chem-balance-coefficient-side="products" data-chem-balance-coefficient-index="0" value="1">' +
      '<input type="number" data-chem-balance-coefficient-side="products" data-chem-balance-coefficient-index="1" value="1">' +
      '<output data-chem-balance-student-check></output><pre id="result"></pre></main>');
    await page.addScriptTag({ path: solverPath });
    const state = await page.evaluate(() => {
      const request = { reactants: ['Fe', 'CuSO4'], products: ['FeSO4', 'Cu'] };
      const result = CHEMSOLVER.balanceEquation(request);
      window.__CHEM_BALANCE_REQUEST__ = request;
      window.__CHEM_BALANCE_RESULT__ = result;
      document.querySelector('[data-chem-balance-equation]').textContent = result.equation;
      const renderStudentCheck = () => {
        const coefficients = { reactants: [], products: [] };
        document.querySelectorAll('[data-chem-balance-coefficient-side]').forEach(input => {
          coefficients[input.dataset.chemBalanceCoefficientSide][Number(input.dataset.chemBalanceCoefficientIndex)] = input.valueAsNumber;
        });
        window.__CHEM_BALANCE_STUDENT_COEFFICIENTS__ = coefficients;
        window.__CHEM_BALANCE_STUDENT_CHECK__ = CHEMSOLVER.checkCoefficients(request, coefficients);
        const output = document.querySelector('[data-chem-balance-student-check]');
        output.dataset.balanced = String(window.__CHEM_BALANCE_STUDENT_CHECK__.balanced);
        output.dataset.primitive = String(window.__CHEM_BALANCE_STUDENT_CHECK__.primitive);
        output.textContent = output.dataset.balanced + ':' + output.dataset.primitive;
      };
      document.querySelectorAll('[data-chem-balance-coefficient-side]').forEach(input => {
        input.addEventListener('input', renderStudentCheck);
        input.addEventListener('change', renderStudentCheck);
      });
      renderStudentCheck();
      const scaledFormula = CHEMSOLVER.balanceEquation({
        reactants: ['(Fe)2', '(CuSO4)2'], products: ['(FeSO4)2', '(Cu)2']
      });
      const unicodeFormula = CHEMSOLVER.balanceEquation({
        reactants: ['Fe', 'CuSO₄'], products: ['FeSO₄', 'Cu']
      });
      const reordered = CHEMSOLVER.balanceEquation({
        reactants: ['CuSO4', 'Fe'], products: ['Cu', 'FeSO4']
      });
      document.querySelectorAll('[data-chem-balance-coefficient-side]').forEach(input => {
        input.value = String(input.valueAsNumber * 2);
        input.dispatchEvent(new Event('input', { bubbles: true }));
      });
      const studentScaledCheck = window.__CHEM_BALANCE_STUDENT_CHECK__;
      const studentScaledDisplay = {
        balanced: document.querySelector('[data-chem-balance-student-check]').dataset.balanced,
        primitive: document.querySelector('[data-chem-balance-student-check]').dataset.primitive,
      };
      const learnerCheck = CHEMSOLVER.checkCoefficients(request,
        { reactants: [1, 1], products: [1, 1] });
      const coefficientBoundary = CHEMSOLVER.balanceEquation({
        reactants: ['H', 'O500000'], products: ['H2O']
      });
      let invalidFormulaRejected = false;
      try { CHEMSOLVER.balanceEquation({ reactants: ['Xx'], products: ['Xx'] }); }
      catch (_) { invalidFormulaRejected = true; }
      let aboveCoefficientLimitRejected = false;
      try {
        CHEMSOLVER.balanceEquation({ reactants: ['H', 'O500001'], products: ['H2O'] });
      } catch (_) { aboveCoefficientLimitRejected = true; }
      return {
        equation: result.equation,
        coefficients: result.coefficients,
        atomCounts: result.atom_counts,
        chargeCounts: result.charge_counts,
        checks: result.checks,
        learnerCheck: learnerCheck,
        displayedEquation: document.querySelector('[data-chem-balance-equation]').textContent,
        studentScaledCheck,
        studentScaledDisplay,
        metamorphicCoefficients: {
          original: result.coefficients,
          scaledFormula: scaledFormula.coefficients,
          unicodeFormula: unicodeFormula.coefficients,
          reordered: reordered.coefficients,
        },
        exposed: !!window.__CHEM_BALANCE_REQUEST__ && !!window.__CHEM_BALANCE_RESULT__,
        invalidFormulaRejected: invalidFormulaRejected,
        coefficientBoundary: coefficientBoundary.coefficients,
        coefficientBoundaryChecks: coefficientBoundary.checks,
        aboveCoefficientLimitRejected: aboveCoefficientLimitRejected,
      };
    });
    assert.strictEqual(state.equation, 'Fe + CuSO4 → FeSO4 + Cu');
    assert.deepStrictEqual(state.coefficients, { reactants: [1, 1], products: [1, 1] });
    assert.deepStrictEqual(state.atomCounts.left, state.atomCounts.right);
    assert.strictEqual(state.chargeCounts.left, state.chargeCounts.right);
    assert.strictEqual(state.checks.ok, true);
    assert.strictEqual(state.learnerCheck.balanced, true);
    assert.strictEqual(state.displayedEquation, state.equation);
    assert.deepStrictEqual(state.metamorphicCoefficients.scaledFormula, state.metamorphicCoefficients.original);
    assert.deepStrictEqual(state.metamorphicCoefficients.unicodeFormula, state.metamorphicCoefficients.original);
    assert.deepStrictEqual(state.metamorphicCoefficients.reordered, { reactants: [1, 1], products: [1, 1] });
    assert.strictEqual(state.studentScaledCheck.balanced, true);
    assert.strictEqual(state.studentScaledCheck.primitive, false);
    assert.deepStrictEqual(state.studentScaledDisplay, { balanced: 'true', primitive: 'false' });
    assert.strictEqual(state.exposed, true);
    assert.strictEqual(state.invalidFormulaRejected, true);
    assert.deepStrictEqual(state.coefficientBoundary, {
      reactants: [1000000, 1], products: [500000]
    });
    assert.strictEqual(state.coefficientBoundaryChecks.ok, true);
    assert.strictEqual(state.aboveCoefficientLimitRejected, true);
    assert.deepStrictEqual(pageErrors, []);
    console.log('PASS: browser solver, visible equation, learner check, and invalid formula handling');
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
