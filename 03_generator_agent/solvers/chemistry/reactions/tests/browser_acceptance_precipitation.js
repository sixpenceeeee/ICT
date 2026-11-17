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
      <label>氯化钡浓度 <input type="number" min="0.001" max="1" step="0.001" value="0.2" data-chem-precip-concentration-index="0"></label>
      <label>氯化钡体积 <input type="number" min="1" max="500" step="0.1" value="50" data-chem-precip-volume-index="0"></label>
      <select data-chem-precip-unit-index="0"><option value="mL">mL</option><option value="L">L</option></select>
      <label>硫酸钠浓度 <input type="number" min="0.001" max="1" step="0.001" value="0.1" data-chem-precip-concentration-index="1"></label>
      <label>硫酸钠体积 <input type="number" min="1" max="500" step="0.1" value="90" data-chem-precip-volume-index="1"></label>
      <select data-chem-precip-unit-index="1"><option value="mL">mL</option><option value="L">L</option></select>
      <label>反应进度 <input type="range" min="0" max="1" step="0.01" value="0.8" data-chem-precip-progress></label>
      <output data-chem-precip-equation></output><output data-chem-precip-net-ionic></output>
      <output data-chem-precip-mass></output>
      <div id="scene" style="width:1000px;height:700px"><canvas id="apparatus"></canvas></div>
      <div id="tip"></div>
    </body></html>`);
    await page.addScriptTag({ path: solverPath });
    await page.addScriptTag({ path: visualPath });
    await page.evaluate(() => {
      const one = selector => document.querySelector(selector);
      const concentrations = [...document.querySelectorAll('[data-chem-precip-concentration-index]')]
        .sort((a, b) => Number(a.dataset.chemPrecipConcentrationIndex) - Number(b.dataset.chemPrecipConcentrationIndex));
      const volumes = [...document.querySelectorAll('[data-chem-precip-volume-index]')]
        .sort((a, b) => Number(a.dataset.chemPrecipVolumeIndex) - Number(b.dataset.chemPrecipVolumeIndex));
      const units = [...document.querySelectorAll('[data-chem-precip-unit-index]')]
        .sort((a, b) => Number(a.dataset.chemPrecipUnitIndex) - Number(b.dataset.chemPrecipUnitIndex));
      const progress = one('[data-chem-precip-progress]');
      window.renderPrecipitation = () => {
        const request = {
          solutions: [
            { formula: 'BaCl2', concentration_mol_L: concentrations[0].valueAsNumber,
              volume: volumes[0].valueAsNumber, volume_unit: units[0].value },
            { formula: 'Na2SO4', concentration_mol_L: concentrations[1].valueAsNumber,
              volume: volumes[1].valueAsNumber, volume_unit: units[1].value },
          ],
          progress: progress.valueAsNumber,
        };
        const result = CHEMSOLVER.solvePrecipitation(request);
        window.__CHEM_PRECIP_REQUEST__ = request;
        window.__CHEM_PRECIP_RESULT__ = result;
        one('[data-chem-precip-equation]').textContent = result.equation;
        one('[data-chem-precip-net-ionic]').textContent = result.net_ionic_equation;
        one('[data-chem-precip-mass]').textContent = result.precipitate_mass_g.toFixed(4) + ' g';
        CHEM.precipitation(one('#apparatus'), result);
      };
      [...concentrations, ...volumes, ...units, progress].forEach(control => {
        control.addEventListener('input', window.renderPrecipitation);
        control.addEventListener('change', window.renderPrecipitation);
      });
      window.renderPrecipitation();
    });

    const initial = await page.evaluate(() => ({
      request: window.__CHEM_PRECIP_REQUEST__, result: window.__CHEM_PRECIP_RESULT__,
      equation: document.querySelector('[data-chem-precip-equation]').textContent,
      net: document.querySelector('[data-chem-precip-net-ionic]').textContent,
      mass: document.querySelector('[data-chem-precip-mass]').textContent,
      scene: window.__CHEM_PRECIPITATION_STATE__, aria: document.querySelector('canvas').getAttribute('aria-label'),
    }));
    assert.strictEqual(initial.result.checks.ok, true);
    assert.strictEqual(initial.result.reaction_id, 'barium-sulfate');
    assert.strictEqual(initial.equation, 'BaCl2(aq) + Na2SO4(aq) → BaSO4(s) + 2NaCl(aq)');
    assert.strictEqual(initial.net, 'Ba²⁺(aq) + SO₄²⁻(aq) → BaSO₄(s)');
    assert.ok(initial.mass.includes(initial.result.precipitate_mass_g.toFixed(4)));
    assert.strictEqual(initial.scene.precipitate_formula, 'BaSO4');
    assert.ok(initial.scene.sediment_fraction > 0);
    assert.ok(initial.aria.includes('BaSO4'));

    await page.locator('[data-chem-precip-volume-index="0"]').fill('100');
    await page.locator('[data-chem-precip-volume-index="1"]').fill('180');
    const scaled = await page.evaluate(() => window.__CHEM_PRECIP_RESULT__);
    assert.ok(Math.abs(scaled.precipitate_mass_g - initial.result.precipitate_mass_g * 2) < 1e-10);
    assert.deepStrictEqual(scaled.limiting_reactants, initial.result.limiting_reactants);

    await page.locator('[data-chem-precip-volume-index="0"]').fill('50');
    await page.locator('[data-chem-precip-volume-index="1"]').fill('90');
    await page.locator('[data-chem-precip-unit-index="0"]').selectOption('L');
    await page.locator('[data-chem-precip-volume-index="0"]').fill('0.05');
    const unitEquivalent = await page.evaluate(() => window.__CHEM_PRECIP_RESULT__);
    assert.ok(Math.abs(unitEquivalent.precipitate_mass_g - initial.result.precipitate_mass_g) < 1e-12);
    await page.locator('[data-chem-precip-unit-index="0"]').selectOption('mL');
    await page.locator('[data-chem-precip-volume-index="0"]').fill('50');

    await page.locator('[data-chem-precip-progress]').fill('0.4');
    const partial = await page.evaluate(() => window.__CHEM_PRECIP_RESULT__);
    assert.ok(Math.abs(partial.precipitate_mass_g - initial.result.precipitate_mass_g / 2) < 1e-10);
    await page.locator('[data-chem-precip-progress]').fill('0.8');

    await page.locator('[data-chem-precip-volume-index="1"]').fill('100');
    const exact = await page.evaluate(() => window.__CHEM_PRECIP_RESULT__);
    assert.strictEqual(exact.stoichiometric_mix, true);
    assert.strictEqual(exact.limiting_reactants.length, 2);
    await page.locator('[data-chem-precip-volume-index="1"]').fill('98');
    const below = await page.evaluate(() => window.__CHEM_PRECIP_RESULT__);
    assert.deepStrictEqual(below.limiting_reactants, [{ index: 1, formula: 'Na2SO4' }]);
    await page.locator('[data-chem-precip-volume-index="1"]').fill('102');
    const above = await page.evaluate(() => window.__CHEM_PRECIP_RESULT__);
    assert.deepStrictEqual(above.limiting_reactants, [{ index: 0, formula: 'BaCl2' }]);

    await page.locator('[data-chem-precip-concentration-index="0"]').fill('0.18');
    const concentrationChanged = await page.evaluate(() => window.__CHEM_PRECIP_RESULT__);
    assert.ok(Math.abs(concentrationChanged.precipitate_mass_g - above.precipitate_mass_g) > 1e-6);
    assert.deepStrictEqual(pageErrors, []);
    console.log('PASS: controls update precipitate mass, solution units, reaction progress and limiting reagent at/below/above stoichiometric ratio; apparatus redraws without page errors');
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
