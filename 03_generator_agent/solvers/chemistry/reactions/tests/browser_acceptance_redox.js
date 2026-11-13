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
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.setContent(`<!doctype html><html lang="zh-CN"><meta charset="utf-8">
      <style>body{font:18px sans-serif}#scene{width:1000px;height:700px}
      canvas{width:100%;height:100%}output{display:block;margin:8px}</style>
      <body><select data-chem-redox-medium><option value="acidic">酸性介质</option>
      <option value="basic">碱性介质</option></select>
      <button type="button" data-chem-redox-reorder>交换物质顺序验证</button>
      <output data-chem-redox-equation></output><output data-chem-redox-electrons></output>
      <output data-chem-redox-changes></output><div id="scene"><canvas id="diagram"></canvas></div><div id="tip"></div>
      </body></html>`);
    await page.addScriptTag({ path: solverPath });
    await page.addScriptTag({ path: visualPath });
    await page.evaluate(() => {
      const source = {
        medium: document.querySelector('[data-chem-redox-medium]').value,
        reactants: [
          { formula: 'MnO4', charge: -1, phase: 'aq' },
          { formula: 'Fe', charge: 2, phase: 'aq' },
        ],
        products: [
          { formula: 'Mn', charge: 2, phase: 'aq' },
          { formula: 'Fe', charge: 3, phase: 'aq' },
        ],
      };
      let reversed = false;
      window.renderRedox = () => {
        const request = {
          medium: source.medium,
          reactants: reversed ? source.reactants.slice().reverse() : source.reactants.slice(),
          products: reversed ? source.products.slice().reverse() : source.products.slice(),
        };
        const result = CHEMSOLVER.solveRedox(request);
        window.__CHEM_REDOX_REQUEST__ = request;
        window.__CHEM_REDOX_RESULT__ = result;
        document.querySelector('[data-chem-redox-equation]').textContent = result.equation;
        document.querySelector('[data-chem-redox-electrons]').textContent =
          `${result.electron_balance.lost_electrons} e⁻ = ${result.electron_balance.gained_electrons} e⁻`;
        document.querySelector('[data-chem-redox-changes]').textContent = result.oxidation_changes.map(row =>
          `${row.element} ${row.before > 0 ? '+' : ''}${row.before} → ${row.after > 0 ? '+' : ''}${row.after}; ` +
          `失 ${row.electrons_lost} e⁻，得 ${row.electrons_gained} e⁻`).join('；');
        CHEM.redox(document.querySelector('#diagram'), result);
      };
      document.querySelector('[data-chem-redox-reorder]').addEventListener('click', () => {
        reversed = !reversed;
        window.renderRedox();
      });
      document.querySelector('[data-chem-redox-medium]').addEventListener('change', event => {
        source.medium = event.currentTarget.value;
        window.renderRedox();
      });
      window.renderRedox();
    });

    const initial = await page.evaluate(() => ({
      request: window.__CHEM_REDOX_REQUEST__, result: window.__CHEM_REDOX_RESULT__,
      equation: document.querySelector('[data-chem-redox-equation]').textContent,
      electrons: document.querySelector('[data-chem-redox-electrons]').textContent,
      changes: document.querySelector('[data-chem-redox-changes]').textContent,
      state: window.__CHEM_REDOX_STATE__, aria: document.querySelector('canvas').getAttribute('aria-label'),
    }));
    assert.strictEqual(initial.result.checks.ok, true);
    assert.strictEqual(initial.equation,
      'MnO₄⁻(aq) + 5Fe²⁺(aq) + 8H⁺(aq) → Mn²⁺(aq) + 5Fe³⁺(aq) + 4H₂O(l)');
    assert.ok(initial.electrons.includes('5 e⁻'));
    assert.ok(initial.changes.includes('Mn') && initial.changes.includes('Fe'));
    assert.strictEqual(initial.state.lost_electrons, 5);
    assert.ok(initial.aria.includes('失电子') && initial.aria.includes('得电子'));

    await page.locator('[data-chem-redox-medium]').selectOption('basic');
    const basic = await page.evaluate(() => ({ request: window.__CHEM_REDOX_REQUEST__, result: window.__CHEM_REDOX_RESULT__ }));
    assert.strictEqual(basic.result.medium, 'basic');
    assert.strictEqual(basic.result.electron_balance.transferred_electrons, 5);
    assert.ok(basic.result.equation.includes('OH⁻'));
    await page.locator('[data-chem-redox-medium]').selectOption('acidic');

    await page.locator('[data-chem-redox-reorder]').click();
    const transformed = await page.evaluate(() => ({
      request: window.__CHEM_REDOX_REQUEST__, result: window.__CHEM_REDOX_RESULT__,
      equation: document.querySelector('[data-chem-redox-equation]').textContent,
    }));
    assert.deepStrictEqual(transformed.request.reactants.map(item => item.formula), ['Fe', 'MnO4']);
    assert.deepStrictEqual(transformed.request.products.map(item => item.formula), ['Fe', 'Mn']);
    assert.deepStrictEqual(transformed.result.coefficients.reactants.slice(0, 2), [5, 1]);
    assert.deepStrictEqual(transformed.result.coefficients.products.slice(0, 2), [5, 1]);
    assert.strictEqual(transformed.result.electron_balance.transferred_electrons,
      initial.result.electron_balance.transferred_electrons);
    assert.notStrictEqual(transformed.equation, initial.equation);
    await page.locator('[data-chem-redox-reorder]').click();
    assert.deepStrictEqual(errors, []);
    console.log('PASS: acid/base medium changes, charge/atom/electron checks, Unicode display, diagram redraw and real species-order metamorphic control');
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
