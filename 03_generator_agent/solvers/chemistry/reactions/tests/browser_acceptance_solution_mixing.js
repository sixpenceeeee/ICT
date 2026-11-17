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
      '<input type="number" data-chem-mix-concentration-index="0" value="0.2">' +
      '<input type="number" data-chem-mix-volume-index="0" value="50">' +
      '<select data-chem-mix-unit-index="0"><option>mL</option><option>L</option></select>' +
      '<input type="number" data-chem-mix-concentration-index="1" value="0.15">' +
      '<input type="number" data-chem-mix-volume-index="1" value="100">' +
      '<select data-chem-mix-unit-index="1"><option>mL</option><option>L</option></select>' +
      '<input type="range" min="0" max="1" step="0.01" value="0.5" data-chem-mix-progress>' +
      '<output data-chem-mix-equation></output><output id="reading"></output></main>');
    await page.addScriptTag({ path: solverPath });
    const state = await page.evaluate(() => {
      const c = Array.from(document.querySelectorAll('[data-chem-mix-concentration-index]'));
      const v = Array.from(document.querySelectorAll('[data-chem-mix-volume-index]'));
      const u = Array.from(document.querySelectorAll('[data-chem-mix-unit-index]'));
      const progress = document.querySelector('[data-chem-mix-progress]');
      const render = () => {
        const byIndex = (items, attr) => items.sort((a,b) =>
          Number(a.getAttribute(attr)) - Number(b.getAttribute(attr)));
        const concentrations = byIndex(c.slice(), 'data-chem-mix-concentration-index');
        const volumes = byIndex(v.slice(), 'data-chem-mix-volume-index');
        const units = byIndex(u.slice(), 'data-chem-mix-unit-index');
        const request = {
          reactants: ['BaCl2', 'Na2SO4'], products: ['BaSO4', 'NaCl'],
          solutions: concentrations.map((input,i) => ({ concentration_mol_L: input.valueAsNumber,
            volume: volumes[i].valueAsNumber, volume_unit: units[i].value })),
          progress: progress.valueAsNumber
        };
        const result = CHEMSOLVER.solveSolutionMixing(request);
        window.__CHEM_MIX_REQUEST__ = request;
        window.__CHEM_MIX_RESULT__ = result;
        document.querySelector('[data-chem-mix-equation]').textContent = result.equation;
        document.querySelector('#reading').textContent =
          result.limiting_reactants.map(item => item.formula).join('+') + ':' + result.extent_mol.toFixed(3);
        return result;
      };
      document.querySelectorAll('[data-chem-mix-concentration-index], [data-chem-mix-volume-index], [data-chem-mix-unit-index], [data-chem-mix-progress]')
        .forEach(input => { input.addEventListener('input', render); input.addEventListener('change', render); });
      const initial = render();
      const initialAmounts = initial.initial_amounts_mol.slice();
      v[0].value = '0.05'; u[0].value = 'L';
      v[0].dispatchEvent(new Event('input', { bubbles: true }));
      u[0].dispatchEvent(new Event('change', { bubbles: true }));
      const unitEquivalent = window.__CHEM_MIX_RESULT__;
      const equationAfterUnitChange = document.querySelector('[data-chem-mix-equation]').textContent;
      progress.value = '1';
      progress.dispatchEvent(new Event('input', { bubbles: true }));
      const afterProgress = window.__CHEM_MIX_RESULT__;
      const thresholdCases = [66, 100 / 1.5, 67].map(volume =>
        CHEMSOLVER.solveSolutionMixing({
          ...window.__CHEM_MIX_REQUEST__,
          solutions: [window.__CHEM_MIX_REQUEST__.solutions[0],
            { concentration_mol_L: 0.15, volume, volume_unit: 'mL' }], progress: 1
        }).limiting_reactants.map(item => item.formula));
      let invalidUnitRejected = false;
      try {
        CHEMSOLVER.solveSolutionMixing({ ...window.__CHEM_MIX_REQUEST__,
          solutions: [{ ...window.__CHEM_MIX_REQUEST__.solutions[0], volume_unit: 'g' },
            window.__CHEM_MIX_REQUEST__.solutions[1]] });
      } catch (_) { invalidUnitRejected = true; }
      return {
        initial, initialAmounts, unitEquivalent, equationAfterUnitChange, afterProgress,
        exposed: !!window.__CHEM_MIX_REQUEST__ && !!window.__CHEM_MIX_RESULT__,
        thresholdCases, invalidUnitRejected
      };
    });
    assert.strictEqual(state.initial.schema, 'chem-solution-mixing.v1');
    assert.deepStrictEqual(state.initialAmounts, [0.010000000000000002, 0.015]);
    assert.deepStrictEqual(state.unitEquivalent.initial_amounts_mol, state.initialAmounts);
    assert.strictEqual(state.unitEquivalent.checks.ok, true);
    assert.strictEqual(state.equationAfterUnitChange, 'BaCl2 + Na2SO4 → BaSO4 + 2NaCl');
    assert.ok(Math.abs(state.afterProgress.extent_mol - 0.01) < 1e-12);
    assert.ok(Math.abs(state.afterProgress.products[0].produced_mol - 0.01) < 1e-12);
    assert.ok(Math.abs(state.afterProgress.products[1].produced_mol - 0.02) < 1e-12);
    assert.deepStrictEqual(state.thresholdCases, [['Na2SO4'], ['BaCl2', 'Na2SO4'], ['BaCl2']]);
    assert.strictEqual(state.invalidUnitRejected, true);
    assert.strictEqual(state.exposed, true);
    assert.deepStrictEqual(pageErrors, []);
    console.log('PASS: concentration-volume conversion, mL/L equivalence, progress, limiting threshold, conservation');
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
