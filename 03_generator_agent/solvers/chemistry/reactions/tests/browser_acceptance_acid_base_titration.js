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
    const page = await browser.newPage({ viewport: { width: 1120, height: 820 } });
    const pageErrors = [];
    page.on('pageerror', error => pageErrors.push(error.message));
    await page.setContent(`<!doctype html><html lang="zh-CN"><meta charset="utf-8"><body>
      <label>酸浓度 <input type="number" min="0.001" max="1" step="0.001" value="0.1" data-chem-titration-acid-concentration></label>
      <label>酸体积 <input type="number" min="0" max="1000" step="0.01" value="25" data-chem-titration-acid-volume></label>
      <select data-chem-titration-acid-unit><option value="mL">mL</option><option value="L">L</option></select>
      <label>碱浓度 <input type="number" min="0.001" max="1" step="0.001" value="0.1" data-chem-titration-base-concentration></label>
      <label>滴定体积 <input type="number" min="0" max="1000" step="0.01" value="24" data-chem-titration-base-volume></label>
      <select data-chem-titration-base-unit><option value="mL">mL</option><option value="L">L</option></select>
      <output data-chem-titration-equation></output><output data-chem-titration-ph></output>
      <canvas id="apparatus" width="880" height="680" style="width:880px;height:680px"></canvas>
      <div id="tip"></div>
    </body></html>`);
    await page.addScriptTag({ path: solverPath });
    await page.addScriptTag({ path: visualPath });
    await page.evaluate(() => {
      const one = selector => document.querySelector(selector);
      const controls = {
        acidC: one('[data-chem-titration-acid-concentration]'),
        acidV: one('[data-chem-titration-acid-volume]'),
        acidU: one('[data-chem-titration-acid-unit]'),
        baseC: one('[data-chem-titration-base-concentration]'),
        baseV: one('[data-chem-titration-base-volume]'),
        baseU: one('[data-chem-titration-base-unit]'),
      };
      window.renderTitration = () => {
        const request = {
          acid: { formula: 'HCl', concentration_mol_L: controls.acidC.valueAsNumber,
            volume: controls.acidV.valueAsNumber, volume_unit: controls.acidU.value },
          base: { formula: 'NaOH', concentration_mol_L: controls.baseC.valueAsNumber,
            volume: controls.baseV.valueAsNumber, volume_unit: controls.baseU.value },
        };
        const result = CHEMSOLVER.solveAcidBaseTitration(request);
        window.__CHEM_TITRATION_REQUEST__ = request;
        window.__CHEM_TITRATION_RESULT__ = result;
        one('[data-chem-titration-equation]').textContent = result.equation;
        one('[data-chem-titration-ph]').textContent = 'pH = ' + result.pH.toFixed(2);
        CHEM.titration(one('#apparatus'), result);
      };
      Object.values(controls).forEach(control => {
        control.addEventListener('input', window.renderTitration);
        control.addEventListener('change', window.renderTitration);
      });
      window.renderTitration();
    });

    const before = await page.evaluate(() => ({
      request: window.__CHEM_TITRATION_REQUEST__, result: window.__CHEM_TITRATION_RESULT__,
      equation: document.querySelector('[data-chem-titration-equation]').textContent,
      ph: document.querySelector('[data-chem-titration-ph]').textContent,
      canvasState: window.__CHEM_TITRATION_STATE__, aria: document.querySelector('canvas').getAttribute('aria-label'),
    }));
    assert.strictEqual(before.result.state, 'acidic');
    assert.strictEqual(before.result.checks.ok, true);
    assert.strictEqual(before.equation, 'HCl(aq) + NaOH(aq) → NaCl(aq) + H2O(l)');
    assert.ok(before.ph.includes(before.result.pH.toFixed(2)));
    assert.strictEqual(before.canvasState.state, 'acidic');
    assert.ok(before.aria.includes('酸性'));

    await page.locator('[data-chem-titration-base-volume]').fill('25');
    const atEquivalence = await page.evaluate(() => window.__CHEM_TITRATION_RESULT__);
    assert.strictEqual(atEquivalence.state, 'equivalence');
    assert.ok(Math.abs(atEquivalence.pH - 7) < 1e-9);

    await page.locator('[data-chem-titration-base-volume]').fill('26');
    const above = await page.evaluate(() => window.__CHEM_TITRATION_RESULT__);
    assert.strictEqual(above.state, 'basic');
    assert.ok(before.result.pH < atEquivalence.pH && atEquivalence.pH < above.pH);

    await page.locator('[data-chem-titration-base-volume]').fill('24');
    const initialPH = await page.evaluate(() => window.__CHEM_TITRATION_RESULT__.pH);
    await page.locator('[data-chem-titration-acid-volume]').fill('0.025');
    await page.locator('[data-chem-titration-acid-unit]').selectOption('L');
    await page.locator('[data-chem-titration-base-volume]').fill('0.024');
    await page.locator('[data-chem-titration-base-unit]').selectOption('L');
    const unitEquivalent = await page.evaluate(() => window.__CHEM_TITRATION_RESULT__);
    assert.ok(Math.abs(unitEquivalent.pH - initialPH) < 1e-10);
    assert.strictEqual(unitEquivalent.state, 'acidic');
    assert.strictEqual(unitEquivalent.checks.ok, true);
    assert.deepStrictEqual(pageErrors, []);
    console.log('PASS: visible controls drive equation/pH/canvas; state crosses equivalence; mL/L preserves result');
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
