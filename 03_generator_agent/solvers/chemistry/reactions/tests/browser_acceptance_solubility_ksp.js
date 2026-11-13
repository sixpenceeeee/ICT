const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const project = path.resolve(__dirname, '../../../../../');
const solverPath = path.join(project, 'frame', 'chem_solver.js');
const visualPath = path.join(project, 'frame', 'chem.js');
const chromePath = process.env.CHROME_PATH || [
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  'C:/Users/wangq/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe',
].find(candidate => fs.existsSync(candidate));

(async () => {
  if (!chromePath) throw new Error('未找到 Chrome、Edge 或 Playwright Chromium');
  const browser = await chromium.launch({ headless: true, executablePath: chromePath });
  try {
    const page = await browser.newPage({ viewport: { width: 1100, height: 850 } });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.setContent(`<!doctype html><html lang="zh-CN"><meta charset="utf-8">
      <style>body{font:18px sans-serif}#scene{width:820px;height:680px}canvas{width:100%;height:100%}
      output{display:block;margin:8px}</style><body>
      <label>Ksp <input type="number" min="1e-80" max="1e6" step="any" data-chem-ksp-value value="4e-11"></label>
      <label>Ca²⁺ <input type="number" min="0" max="1000" step="any" data-chem-ksp-ion-index="0" value="0"></label>
      <label>F⁻ <input type="number" min="0" max="1000" step="any" data-chem-ksp-ion-index="1" value="0"></label>
      <output data-chem-ksp-equation></output><output data-chem-ksp-ion-product></output>
      <output data-chem-ksp-state></output><output data-chem-ksp-solubility></output>
      <div id="scene"><canvas id="diagram"></canvas></div><div id="tip"></div></body></html>`);
    await page.addScriptTag({ path: solverPath });
    await page.addScriptTag({ path: visualPath });
    await page.evaluate(() => {
      const inputKsp = document.querySelector('[data-chem-ksp-value]');
      const ionInputs = Array.from(document.querySelectorAll('[data-chem-ksp-ion-index]'));
      window.renderKsp = () => {
        const request = { solid_formula: 'CaF2', Ksp: inputKsp.valueAsNumber, ions: [
          { formula: 'Ca', charge: 2, coefficient: 1, initial_concentration_mol_L: ionInputs[0].valueAsNumber },
          { formula: 'F', charge: -1, coefficient: 2, initial_concentration_mol_L: ionInputs[1].valueAsNumber },
        ] };
        const result = CHEMSOLVER.solveSolubilityEquilibrium(request);
        window.__CHEM_KSP_REQUEST__ = request;
        window.__CHEM_KSP_RESULT__ = result;
        document.querySelector('[data-chem-ksp-equation]').textContent = result.dissolution_equation;
        document.querySelector('[data-chem-ksp-ion-product]').textContent =
          `Q=${result.initial_ion_product.toExponential(4)}; Ksp=${result.Ksp.toExponential(4)}`;
        document.querySelector('[data-chem-ksp-state]').textContent = ({
          unsaturated: '未饱和 · 可继续溶解', saturated: '饱和 · 动态平衡',
          supersaturated: '过饱和 · 有沉淀倾向',
        })[result.saturation_state];
        document.querySelector('[data-chem-ksp-solubility]').textContent =
          result.molar_solubility_mol_L === null ? '过饱和，当前不计算溶解度解' :
            `s=${result.molar_solubility_mol_L.toExponential(5)} mol/L`;
        CHEM.solubility(document.querySelector('#diagram'), result);
      };
      document.querySelectorAll('input').forEach(input => input.addEventListener('input', window.renderKsp));
      window.renderKsp();
    });

    const read = () => page.evaluate(() => ({
      request: window.__CHEM_KSP_REQUEST__, result: window.__CHEM_KSP_RESULT__,
      equation: document.querySelector('[data-chem-ksp-equation]').textContent,
      q: document.querySelector('[data-chem-ksp-ion-product]').textContent,
      state: document.querySelector('[data-chem-ksp-state]').textContent,
      solubility: document.querySelector('[data-chem-ksp-solubility]').textContent,
      canvasState: window.__CHEM_KSP_STATE__, aria: document.querySelector('canvas').getAttribute('aria-label'),
    }));
    const initial = await read();
    assert.strictEqual(initial.result.checks.ok, true);
    assert.strictEqual(initial.result.saturation_state, 'unsaturated');
    assert.ok(initial.equation.includes('CaF₂(s)') && initial.equation.includes('2F⁻(aq)'));
    assert.ok(initial.q.includes('Q=0.0000e+0') || initial.q.includes('Q=0.0000e+00'));
    assert.ok(initial.solubility.includes('mol/L'));
    assert.strictEqual(initial.canvasState.saturation_state, 'unsaturated');
    assert.ok(initial.aria.includes('Ksp='));

    await page.locator('[data-chem-ksp-value]').fill('8e-11');
    const higherKsp = await read();
    assert.ok(higherKsp.result.molar_solubility_mol_L > initial.result.molar_solubility_mol_L);
    assert.strictEqual(higherKsp.request.Ksp, 8e-11);
    await page.locator('[data-chem-ksp-value]').fill('4e-11');

    await page.locator('[data-chem-ksp-ion-index="0"]').fill('0.001');
    const commonIon = await read();
    assert.ok(commonIon.result.molar_solubility_mol_L < initial.result.molar_solubility_mol_L);
    assert.strictEqual(commonIon.request.ions[0].initial_concentration_mol_L, 0.001);
    await page.locator('[data-chem-ksp-ion-index="0"]').fill('0');

    const threshold = Math.pow(4e-11, 1 / 3);
    await page.locator('[data-chem-ksp-ion-index="0"]').fill(String(threshold * 0.95));
    await page.locator('[data-chem-ksp-ion-index="1"]').fill(String(threshold));
    const below = await read();
    assert.strictEqual(below.result.saturation_state, 'unsaturated');
    await page.locator('[data-chem-ksp-ion-index="0"]').fill(String(threshold));
    const at = await read();
    assert.strictEqual(at.result.saturation_state, 'saturated');
    assert.strictEqual(at.result.molar_solubility_mol_L, 0);
    await page.locator('[data-chem-ksp-ion-index="0"]').fill(String(threshold * 1.05));
    const above = await read();
    assert.strictEqual(above.result.saturation_state, 'supersaturated');
    assert.strictEqual(above.result.molar_solubility_mol_L, null);
    assert.ok(above.solubility.includes('不计算'));
    assert.deepStrictEqual(errors, []);
    console.log('PASS: Ksp/common-ion/saturation-threshold real controls, solver/display parity and equilibrium canvas render');
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
