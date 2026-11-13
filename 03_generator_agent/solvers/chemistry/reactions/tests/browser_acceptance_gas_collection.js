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
      <label>锌物质的量 <input type="number" min="0.001" max="1" step="0.001" value="0.02" data-chem-gas-amount-index="0"></label>
      <label>盐酸物质的量 <input type="number" min="0.001" max="1" step="0.001" value="0.05" data-chem-gas-amount-index="1"></label>
      <label>反应进度 <input type="range" min="0" max="1" step="0.01" value="0.6" data-chem-gas-progress></label>
      <label>温度 <input type="number" min="0" max="100" step="1" value="25" data-chem-gas-temperature></label>
      <label>总压强 <input type="number" min="10" max="200" step="0.1" value="101.325" data-chem-gas-pressure></label>
      <select data-chem-gas-method><option value="dry">干燥集气</option><option value="over_water">排水集气</option></select>
      <output data-chem-gas-equation></output><output data-chem-gas-volume></output>
      <div id="scene" style="width:1000px;height:700px"><canvas id="apparatus"></canvas></div>
      <div id="tip"></div>
    </body></html>`);
    await page.addScriptTag({ path: solverPath });
    await page.addScriptTag({ path: visualPath });
    await page.evaluate(() => {
      const one = selector => document.querySelector(selector);
      const amounts = [...document.querySelectorAll('[data-chem-gas-amount-index]')]
        .sort((a, b) => Number(a.dataset.chemGasAmountIndex) - Number(b.dataset.chemGasAmountIndex));
      const progress = one('[data-chem-gas-progress]');
      const temperature = one('[data-chem-gas-temperature]');
      const pressure = one('[data-chem-gas-pressure]');
      const method = one('[data-chem-gas-method]');
      window.renderGas = () => {
        const request = {
          reactants: [{ formula: 'Zn', phase: 's' }, { formula: 'HCl', phase: 'aq' }],
          products: [{ formula: 'ZnCl2', phase: 'aq' }, { formula: 'H2', phase: 'g' }],
          initial_amounts_mol: amounts.map(el => el.valueAsNumber),
          progress: progress.valueAsNumber, gas_formula: 'H2',
          temperature_c: temperature.valueAsNumber,
          total_pressure_kpa: pressure.valueAsNumber,
          collection_method: method.value,
        };
        const result = CHEMSOLVER.solveGasCollection(request);
        window.__CHEM_GAS_REQUEST__ = request;
        window.__CHEM_GAS_RESULT__ = result;
        one('[data-chem-gas-equation]').textContent = result.equation;
        one('[data-chem-gas-volume]').textContent = result.gas_volume_l.toFixed(2) + ' L';
        CHEM.gasCollection(one('#apparatus'), result);
      };
      [...amounts, progress, temperature, pressure, method].forEach(control => {
        control.addEventListener('input', window.renderGas);
        control.addEventListener('change', window.renderGas);
      });
      window.renderGas();
    });

    const initial = await page.evaluate(() => ({
      request: window.__CHEM_GAS_REQUEST__, result: window.__CHEM_GAS_RESULT__,
      equation: document.querySelector('[data-chem-gas-equation]').textContent,
      volume: document.querySelector('[data-chem-gas-volume]').textContent,
      scene: window.__CHEM_GAS_COLLECTION_STATE__, aria: document.querySelector('canvas').getAttribute('aria-label'),
    }));
    assert.strictEqual(initial.result.checks.ok, true);
    assert.strictEqual(initial.result.equation, 'Zn(s) + 2HCl(aq) → ZnCl2(aq) + H2(g)');
    assert.strictEqual(initial.equation, initial.result.equation);
    assert.ok(initial.volume.includes(initial.result.gas_volume_l.toFixed(2)));
    assert.strictEqual(initial.scene.gas_formula, 'H2');
    assert.ok(initial.aria.includes('H2'));

    await page.locator('[data-chem-gas-amount-index="0"]').fill('0.04');
    await page.locator('[data-chem-gas-amount-index="1"]').fill('0.10');
    const scaled = await page.evaluate(() => window.__CHEM_GAS_RESULT__);
    assert.ok(Math.abs(scaled.gas_moles - initial.result.gas_moles * 2) < 1e-12);
    assert.ok(Math.abs(scaled.gas_volume_l - initial.result.gas_volume_l * 2) < 1e-12);
    assert.deepStrictEqual(scaled.limiting_reactants, initial.result.limiting_reactants);

    await page.locator('[data-chem-gas-progress]').fill('0.3');
    const progressed = await page.evaluate(() => window.__CHEM_GAS_RESULT__);
    assert.ok(Math.abs(progressed.gas_moles - scaled.gas_moles / 2) < 1e-12);

    await page.locator('[data-chem-gas-temperature]').fill('30');
    const hot = await page.evaluate(() => window.__CHEM_GAS_RESULT__);
    assert.ok(Math.abs(hot.gas_volume_l / progressed.gas_volume_l - 303.15 / 298.15) < 1e-10);

    await page.locator('[data-chem-gas-pressure]').fill('120');
    const highPressure = await page.evaluate(() => window.__CHEM_GAS_RESULT__);
    assert.ok(highPressure.gas_volume_l < hot.gas_volume_l);
    assert.ok(Math.abs(highPressure.gas_volume_l * highPressure.dry_gas_partial_pressure_kpa -
      hot.gas_volume_l * hot.dry_gas_partial_pressure_kpa) < 1e-12);

    await page.locator('[data-chem-gas-method]').selectOption('over_water');
    const wet = await page.evaluate(() => ({
      result: window.__CHEM_GAS_RESULT__, volume: document.querySelector('[data-chem-gas-volume]').textContent,
      scene: window.__CHEM_GAS_COLLECTION_STATE__, aria: document.querySelector('canvas').getAttribute('aria-label'),
    }));
    assert.strictEqual(wet.result.collection_method, 'over_water');
    assert.ok(Math.abs(wet.result.dry_gas_partial_pressure_kpa + wet.result.water_vapor_pressure_kpa -
      wet.result.total_pressure_kpa) < 1e-10);
    assert.ok(wet.result.gas_volume_l > highPressure.gas_volume_l);
    assert.ok(wet.volume.includes(wet.result.gas_volume_l.toFixed(2)));
    assert.strictEqual(wet.scene.collection_method, 'over_water');
    assert.ok(wet.aria.includes('排水集气'));
    assert.deepStrictEqual(pageErrors, []);
    console.log('PASS: controls drive stoichiometry and gas-volume display; temperature/pressure and dry/wet collection update the apparatus and remain consistent');
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
