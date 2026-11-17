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
    const page = await browser.newPage({ viewport: { width: 960, height: 640 } });
    const pageErrors = [];
    page.on('pageerror', error => pageErrors.push(error.message));
    await page.setContent('<main>' +
      '<input type="number" data-chem-stoich-amount-index="0" value="0.1">' +
      '<input type="number" data-chem-stoich-amount-index="1" value="0.099">' +
      '<input type="range" min="0" max="1" step="0.01" value="0.5" data-chem-stoich-progress>' +
      '<output data-chem-stoich-equation></output><output id="reading"></output></main>');
    await page.addScriptTag({ path: solverPath });
    const state = await page.evaluate(() => {
      const amountInputs = Array.from(document.querySelectorAll('[data-chem-stoich-amount-index]'));
      const progressInput = document.querySelector('[data-chem-stoich-progress]');
      const render = () => {
        const request = {
          reactants: ['Fe', 'CuSO4'], products: ['FeSO4', 'Cu'],
          initial_amounts_mol: amountInputs.map(input => input.valueAsNumber),
          progress: progressInput.valueAsNumber
        };
        const result = CHEMSOLVER.solveStoichiometry(request);
        window.__CHEM_STOICH_REQUEST__ = request;
        window.__CHEM_STOICH_RESULT__ = result;
        document.querySelector('[data-chem-stoich-equation]').textContent = result.equation;
        document.querySelector('#reading').textContent =
          result.limiting_reactants.map(item => item.formula).join('+') + ':' + result.reactants[1].remaining_mol.toFixed(3);
        return result;
      };
      document.querySelectorAll('[data-chem-stoich-amount-index], [data-chem-stoich-progress]')
        .forEach(input => input.addEventListener('input', render));
      const result = render();
      const initialExtent = result.extent_mol;
      progressInput.value = '1';
      progressInput.dispatchEvent(new Event('input', { bubbles: true }));
      const afterControlChange = {
        request: window.__CHEM_STOICH_REQUEST__,
        result: window.__CHEM_STOICH_RESULT__,
        reading: document.querySelector('#reading').textContent
      };
      const progressPageStates = [0, 0.5, 1].map(progress => {
        progressInput.value = String(progress);
        progressInput.dispatchEvent(new Event('input', { bubbles: true }));
        const result = render();
        return { progress, request: window.__CHEM_STOICH_REQUEST__, result };
      });
      progressInput.value = '1';
      progressInput.dispatchEvent(new Event('input', { bubbles: true }));
      render();
      const requestTemplate = window.__CHEM_STOICH_REQUEST__;
      const beforeScale = amountInputs.map(input => input.value);
      amountInputs.forEach(input => { input.value = String(input.valueAsNumber * 2); });
      amountInputs[0].dispatchEvent(new Event('input', { bubbles: true }));
      amountInputs[1].dispatchEvent(new Event('input', { bubbles: true }));
      const commonScale = { request: window.__CHEM_STOICH_REQUEST__, result: window.__CHEM_STOICH_RESULT__ };
      amountInputs.forEach((input, index) => { input.value = beforeScale[index]; });
      amountInputs[0].dispatchEvent(new Event('input', { bubbles: true }));
      amountInputs[1].dispatchEvent(new Event('input', { bubbles: true }));
      const thresholdPageStates = [0.099, 0.1, 0.101].map((amount, index) => {
        amountInputs[0].value = '0.1';
        amountInputs[1].value = String(amount);
        amountInputs[0].dispatchEvent(new Event('input', { bubbles: true }));
        amountInputs[1].dispatchEvent(new Event('input', { bubbles: true }));
        const result = render();
        return { kind: ['below', 'at', 'above'][index], request: window.__CHEM_STOICH_REQUEST__, result };
      });
      amountInputs.forEach((input, index) => { input.value = beforeScale[index]; });
      amountInputs[0].dispatchEvent(new Event('input', { bubbles: true }));
      amountInputs[1].dispatchEvent(new Event('input', { bubbles: true }));
      const thresholdCases = [0.099, 0.1, 0.101].map(amount =>
        CHEMSOLVER.solveStoichiometry({ ...requestTemplate, initial_amounts_mol: [0.1, amount], progress: 1 })
          .limiting_reactants.map(item => item.formula));
      let invalidRejected = false;
      try { CHEMSOLVER.solveStoichiometry({ ...requestTemplate, progress: 1.01 }); }
      catch (_) { invalidRejected = true; }
      const malformedValuesRejected = [null, [], '0x1'].every(value => {
        try { CHEMSOLVER.solveStoichiometry({ ...requestTemplate, progress: value }); return false; }
        catch (_) { return true; }
      });
      return {
        result, initialExtent, afterControlChange, progressPageStates, commonScale, thresholdPageStates,
        displayedEquation: document.querySelector('[data-chem-stoich-equation]').textContent,
        exposed: !!window.__CHEM_STOICH_REQUEST__ && !!window.__CHEM_STOICH_RESULT__,
        thresholdCases, invalidRejected, malformedValuesRejected
      };
    });
    assert.strictEqual(state.result.equation, 'Fe + CuSO4 → FeSO4 + Cu');
    assert.strictEqual(state.initialExtent, 0.0495);
    assert.strictEqual(state.afterControlChange.request.progress, 1);
    assert.strictEqual(state.afterControlChange.result.extent_mol, 0.099);
    assert.strictEqual(state.afterControlChange.result.reactants[1].remaining_mol, 0);
    assert.deepStrictEqual(state.progressPageStates.map(item => item.request.progress), [0, 0.5, 1]);
    assert.strictEqual(state.progressPageStates[0].result.extent_mol, 0);
    assert.strictEqual(state.progressPageStates[1].result.extent_mol,
      state.progressPageStates[1].result.max_extent_mol * 0.5);
    assert.strictEqual(state.progressPageStates[2].result.extent_mol,
      state.progressPageStates[2].result.max_extent_mol);
    assert.strictEqual(state.result.checks.ok, true);
    assert.strictEqual(state.result.element_balance.ok, true);
    assert.strictEqual(state.result.charge_balance.ok, true);
    assert.strictEqual(state.displayedEquation, state.result.equation);
    assert.strictEqual(state.afterControlChange.reading, 'CuSO4:0.000');
    assert.strictEqual(state.commonScale.request.initial_amounts_mol[0], 0.2);
    assert.strictEqual(state.commonScale.request.initial_amounts_mol[1], 0.198);
    assert.strictEqual(state.commonScale.result.max_extent_mol, 2 * state.afterControlChange.result.max_extent_mol);
    assert.strictEqual(state.commonScale.result.extent_mol, 2 * state.afterControlChange.result.extent_mol);
    assert.deepStrictEqual(state.thresholdPageStates.map(item => item.result.limiting_reactants.map(row => row.formula)),
      [['CuSO4'], ['Fe', 'CuSO4'], ['Fe']]);
    assert.strictEqual(state.exposed, true);
    assert.deepStrictEqual(state.thresholdCases, [['CuSO4'], ['Fe', 'CuSO4'], ['Fe']]);
    assert.strictEqual(state.invalidRejected, true);
    assert.strictEqual(state.malformedValuesRejected, true);
    assert.deepStrictEqual(pageErrors, []);
    console.log('PASS: browser stoichiometry, visible readings, limiting-reagent threshold, conservation, invalid input');
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
