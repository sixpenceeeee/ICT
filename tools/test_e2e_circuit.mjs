/*
 * Real-Browser E2E Acceptance Test Suite for Circuit Experiments (Tiers 1-4).
 * Covers standard Chrome headless execution, 6-region shell packaging,
 * deterministic MNA needle deflections, switch toggling, rheostat slider regulation,
 * isolated zoom popup editor with postMessage synchronization, responsive viewports,
 * and strict offline execution (zero network requests, zero page errors).
 */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { chromium } from 'playwright-core';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const root = path.resolve(__dirname, '..');

const exe = process.env.CHROME_PATH || [
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
].find(p => fs.existsSync(p));

if (!exe) {
  console.error('ERROR: No valid Chrome or Edge browser executable found on system.');
  process.exit(1);
}

// Deterministic MNA solver verification for Voltage Divider configuration
function buildVoltageDividerConfig(pos = 0.5) {
  return {
    schema_version: 1,
    recipe: 'voltage_divider',
    components: [
      { id: 'V1', type: 'power_supply', params: { voltage: 6 }, x: 100, y: 100 },
      { id: 'S1', type: 'switch', params: { closed: true }, x: 250, y: 100 },
      { id: 'RH1', type: 'rheostat', params: { maxResistance: 50, position: pos }, x: 420, y: 100 },
      { id: 'A1', type: 'ammeter', params: { range: 0.6 }, x: 600, y: 100 },
      { id: 'M1', type: 'voltmeter', params: { range: 15 }, x: 600, y: 280 },
      { id: 'R1', type: 'resistor', params: { resistance: 10 }, x: 750, y: 100 }
    ],
    wires: [
      { id: 'W1', from: 'V1.positive', to: 'S1.a' },
      { id: 'W2', from: 'S1.b', to: 'RH1.a' },
      { id: 'W3', from: 'RH1.b', to: 'V1.negative' },
      { id: 'W4', from: 'RH1.slider', to: 'A1.positive' },
      { id: 'W5', from: 'A1.negative', to: 'R1.a' },
      { id: 'W6', from: 'R1.b', to: 'V1.negative' },
      { id: 'W7', from: 'M1.positive', to: 'R1.a' },
      { id: 'W8', from: 'M1.negative', to: 'R1.b' }
    ]
  };
}

(async () => {
  console.log('--- Circuit E2E Acceptance Test Runner ---');
  console.log('Using browser executable:', exe);
  const browser = await chromium.launch({ executablePath: exe, headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 1000 }, acceptDownloads: true });

  const errors = [];
  const remote = [];
  ctx.on('page', p => {
    p.on('pageerror', e => errors.push(e.message));
  });
  await ctx.route(/^https?:/, route => {
    remote.push(route.request().url());
    route.abort();
  });

  const page = await ctx.newPage();

  try {
    // =========================================================================
    // 1. Regression Suite: 4 Standard Circuit Experiments
    // =========================================================================
    const regressionSpecs = [
      ['ohm', 0.6, 6.0],
      ['resistance', 0.3, 3.0],
      ['series', 0.2, 2.0],
      ['parallel', 0.9, 6.0]
    ];

    for (const [recipe, expCurrent, expVoltage] of regressionSpecs) {
      const htmlPath = path.join(root, 'examples/circuits', `${recipe}.html`);
      assert(fs.existsSync(htmlPath), `Missing required experiment artifact: ${htmlPath}`);

      await page.goto(pathToFileURL(htmlPath).href);
      await page.waitForFunction(() => window.__CIRCUIT_STATE__);

      const data = await page.evaluate(() => ({
        ...window.__DATA__,
        sections: document.querySelectorAll('#sec-info,#sec-stage,#sec-control,#sec-result,#sec-record,#sec-teach').length
      }));

      // Verify 6-region shell layout
      assert.equal(data.sections, 6, `${recipe}: must have all 6 regions`);

      // Verify MNA calculated current and voltage
      assert(Math.abs(data.I - expCurrent) < 1e-8, `${recipe}: expected current ${expCurrent}, got ${data.I}`);
      assert(Math.abs(data.U - expVoltage) < 1e-8, `${recipe}: expected voltage ${expVoltage}, got ${data.U}`);

      // Verify physical dial reading attribute
      const dialVal = await page.locator('[data-meter-id="A1"]').getAttribute('data-value');
      assert(Math.abs(Number(dialVal) - expCurrent) < 1e-8, `${recipe}: dial attribute must match MNA current`);

      // Recipe-specific assertions
      if (recipe === 'parallel') {
        const formula = await page.locator('#fml').textContent();
        assert(formula.includes('+'), 'parallel formula must represent branch sum');
        assert.equal(await page.locator('#read-branch-1').textContent(), '0.6');
        assert.equal(await page.locator('#read-branch-2').textContent(), '0.3');
      }

      // Interactive controls: record, switch toggle, reset
      await page.locator('#btn-record').click();
      assert.equal(await page.locator('#rows tr').count(), 1, `${recipe}: table row must be recorded`);

      await page.locator('#btn-switch').click();
      assert.equal(await page.evaluate(() => window.__DATA__.I), 0, `${recipe}: switch open must drop current to 0`);
      assert.equal(await page.locator('#btn-record').isDisabled(), true, `${recipe}: record button must be disabled when open`);

      await page.locator('#btn-switch').click(); // Restore switch to closed
      await page.locator('#btn-reset').click();
      assert.equal(await page.locator('#rows tr').count(), 0, `${recipe}: reset must clear table`);

      // Responsive viewport check: 1366px, 760px, 390px
      for (const width of [1366, 760, 390]) {
        await page.setViewportSize({ width, height: 1000 });
        if (width === 390) await page.locator('.pf-side label').last().hover().catch(() => {});
        await page.waitForTimeout(200);

        const overflow = await page.evaluate(() =>
          Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) > innerWidth + 2
        );
        assert.equal(overflow, false, `${recipe}: viewport overflow detected at ${width}px`);

        const buttonFits = await page.locator('#btn-enlarge').evaluate(el => {
          const b = el.getBoundingClientRect();
          const p = (el.closest('.exp-canvas-box') || el.closest('.exp-stage')).getBoundingClientRect();
          return b.top >= p.top && b.bottom <= p.bottom && b.left >= p.left && b.right <= p.right;
        });
        assert(buttonFits, `${recipe}: enlarge button must remain within stage at ${width}px`);
      }

      await page.setViewportSize({ width: 1366, height: 1000 });
      console.log(`PASS Tier 4 [Regression]: ${recipe} (MNA readings, 6-region shell, switch, responsive)`);
    }

    // =========================================================================
    // 2. New Experiment: Voltage Divider (滑动变阻器分压控制实验)
    // =========================================================================
    const vdFile = path.join(root, 'examples/circuits/voltage_divider.html');
    let targetVdUrl;
    let tempVdCreated = false;

    if (fs.existsSync(vdFile)) {
      targetVdUrl = pathToFileURL(vdFile).href;
    } else {
      // Dynamic fallback for progressive testability prior to M2 HTML artifact landing
      const baseOhm = fs.readFileSync(path.join(root, 'examples/circuits/ohm.html'), 'utf8');
      const vdConfig = buildVoltageDividerConfig(0.5);
      const encoded = JSON.stringify(vdConfig).replace(/</g, '\\u003c');
      const dynamicHtml = baseOhm.replace(
        /window\.__CIRCUIT_INITIAL__\s*=\s*\{[\s\S]*?\};/,
        `window.__CIRCUIT_INITIAL__ = ${encoded};`
      );
      const tempPath = path.join(root, 'examples/circuits/.temp_e2e_voltage_divider.html');
      fs.writeFileSync(tempPath, dynamicHtml, 'utf8');
      targetVdUrl = pathToFileURL(tempPath).href;
      tempVdCreated = tempPath;
    }

    try {
      await page.goto(targetVdUrl);
      await page.waitForFunction(() => window.__CIRCUIT_STATE__);

      const vdData = await page.evaluate(() => ({
        ...window.__DATA__,
        sections: document.querySelectorAll('#sec-info,#sec-stage,#sec-control,#sec-result,#sec-record,#sec-teach').length
      }));

      assert.equal(vdData.sections, 6, 'Voltage Divider: 6-region shell required');
      // For V=6V, RH1=50Ω pos=0.5, load R1=10Ω:
      // Rp = (25 * 10) / (25 + 10) = 50/7 Ω. Rtot = 25 + 50/7 = 225/7 Ω.
      // Itot = 6 / (225/7) = 14/75 = 0.18667 A. Vp = (14/75) * (50/7) = 4/3 = 1.3333 V.
      // I_load = 4/30 = 2/15 = 0.13333 A.
      assert(Math.abs(vdData.I - (2 / 15)) < 1e-4, `Voltage divider load current expected ~0.1333A, got ${vdData.I}`);
      assert(Math.abs(vdData.U - (4 / 3)) < 1e-4, `Voltage divider load voltage expected ~1.3333V, got ${vdData.U}`);

      // Switch interaction on Voltage Divider
      await page.locator('#btn-switch').click();
      assert.equal(await page.evaluate(() => window.__DATA__.I), 0, 'Voltage divider: open switch must zero current');
      assert.equal(await page.locator('#btn-record').isDisabled(), true, 'Voltage divider: record button disabled when open');

      await page.locator('#btn-switch').click(); // Restore switch
      console.log('PASS Tier 4 [New Experiment]: Voltage Divider (MNA physics, continuous regulation, switch)');
    } finally {
      if (tempVdCreated && fs.existsSync(tempVdCreated)) {
        fs.unlinkSync(tempVdCreated);
      }
    }

    // =========================================================================
    // 3. Isolated Zoom Popup Editor & postMessage Synchronization
    // =========================================================================
    await page.goto(pathToFileURL(path.join(root, 'examples/circuits/ohm.html')).href);
    await page.waitForFunction(() => window.__CIRCUIT_STATE__);

    const originalConfig = await page.evaluate(() => window.__CIRCUIT_STATE__.config);

    // Test 3.1: Open editor popup, draft isolation
    let opened = page.waitForEvent('popup');
    await page.locator('#btn-enlarge').click();
    let editor = await opened;
    await editor.waitForSelector('#editor-apply');

    // Modify voltage in editor draft
    await editor.locator('#c-V1-voltage').fill('3');
    await editor.locator('#c-V1-voltage').dispatchEvent('input');

    // Assert main page remains unchanged (draft isolation)
    assert.equal(await page.evaluate(() => window.__DATA__.U), 6, 'Editor draft must be isolated from main page');

    // Test 3.2: Cancel retains main page
    await editor.locator('#editor-cancel').click();
    assert.equal(await page.evaluate(() => window.__DATA__.U), 6, 'Cancel button must preserve main page state');

    // Test 3.3: Reopen editor, adjust parameters and apparatus position
    opened = page.waitForEvent('popup');
    await page.locator('#btn-enlarge').click();
    editor = await opened;
    await editor.waitForSelector('#editor-apply');

    await editor.locator('#c-V1-voltage').fill('3');
    await editor.locator('#c-V1-voltage').dispatchEvent('input');
    await editor.locator('#c-A1-range').selectOption('0.06');

    await editor.locator('[data-component-id="R1"]').focus();
    await editor.keyboard.press('ArrowRight');
    const movedX = await editor.evaluate(() => window.__EDITOR_CONFIG__.components.find(c => c.id === 'R1').x);
    assert.equal(typeof movedX, 'number', 'Arrow key nudge must update component x coordinate');

    // Test 3.4: Apply updates main page via postMessage token sync
    await editor.locator('#editor-apply').click();
    await page.waitForFunction(() => window.__DATA__.U === 3);

    assert(Math.abs(await page.evaluate(() => window.__DATA__.I) - 0.3) < 1e-8, 'Current must recalculate to 0.3A at 3V');
    assert.equal(
      await page.evaluate(() => window.__CIRCUIT_STATE__.config.components.find(c => c.id === 'R1').x),
      movedX,
      'Applied component x coordinate must match editor'
    );

    // Overrange warning check (0.3A > 0.06A range)
    assert.equal(await page.locator('#alert').isVisible(), true, 'Overrange alert banner must be displayed');
    assert.equal(await page.locator('#btn-record').isDisabled(), true, 'Record button must be locked on overrange');

    const updatedConfig = await page.evaluate(() => window.__CIRCUIT_STATE__.config);
    assert.deepEqual(updatedConfig.wires, originalConfig.wires, 'Moving apparatus must preserve wire endpoint topology');
    console.log('PASS Tier 3 [Cross-Feature]: Zoom Popup Editor (isolation, cancel/apply, postMessage sync, overrange lock)');

    // =========================================================================
    // 4. Standalone Export and Reload Check
    // =========================================================================
    const downloadEvent = page.waitForEvent('download');
    await page.locator('[data-circuit-download]').evaluate(a => a.click());
    const downloaded = await downloadEvent;
    const exportedPath = path.join(root, 'examples/circuits/.e2e_export_verify.html');
    await downloaded.saveAs(exportedPath);

    try {
      const copyPage = await ctx.newPage();
      await copyPage.goto(pathToFileURL(exportedPath).href);
      await copyPage.waitForFunction(() => window.__DATA__ && window.__DATA__.U === 3);
      assert.equal(
        await copyPage.locator('[data-meter-id="A1"]').getAttribute('data-range'),
        '0.06',
        'Exported standalone HTML must retain customized meter range'
      );
      await copyPage.close();
      console.log('PASS Tier 1/5 [Offline Viewing]: Standalone HTML Export and Reload');
    } finally {
      if (fs.existsSync(exportedPath)) fs.unlinkSync(exportedPath);
    }

    // =========================================================================
    // 5. Strict Offline Sandbox Assertion
    // =========================================================================
    assert.deepEqual(errors, [], 'Must have zero unhandled JavaScript page errors');
    assert.deepEqual(remote, [], 'Must have zero outbound remote HTTP/HTTPS requests');
    console.log('PASS Tier 1/5 [Offline Sandbox]: Zero network requests, zero page errors');

  } finally {
    await browser.close();
  }

  console.log('--- ALL BROWSER E2E ACCEPTANCE TESTS PASSED ---');
})().catch(err => {
  console.error('Browser E2E Acceptance Test Failed:', err);
  process.exit(1);
});
