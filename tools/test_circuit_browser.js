/* Real-browser acceptance: file://, existing shell, actual readings, editor isolation/apply, export. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {chromium} = require('playwright-core');
const root = path.resolve(__dirname, '..');
const exe = process.env.CHROME_PATH || ['C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'].find(p => fs.existsSync(p));

(async () => {
  const browser = await chromium.launch({executablePath: exe, headless: true});
  const ctx = await browser.newContext({viewport: {width: 1366, height: 1000}, acceptDownloads: true});
  const errors = [], remote = [];
  ctx.on('page', p => {p.on('pageerror', e => errors.push(e.message));});
  await ctx.route(/^https?:/, route => {remote.push(route.request().url());route.abort();});
  const page = await ctx.newPage();
  try {
    for (const [recipe, current, voltage] of [['ohm', .6, 6], ['resistance', .3, 3], ['series', .2, 2], ['parallel', .9, 6]]) {
      await page.goto(pathToFileURL(path.join(root, 'examples/circuits', recipe + '.html')).href);
      await page.waitForFunction(() => window.__CIRCUIT_STATE__);
      const value = await page.evaluate(() => ({...window.__DATA__, sections: document.querySelectorAll('#sec-info,#sec-stage,#sec-control,#sec-result,#sec-record,#sec-teach').length}));
      assert.equal(value.sections, 6);
      assert(Math.abs(value.I - current) < 1e-8, recipe + ' current');
      assert(Math.abs(value.U - voltage) < 1e-8, recipe + ' voltage');
      const dial = await page.locator('[data-meter-id="A1"]').getAttribute('data-value');
      assert(Math.abs(Number(dial) - current) < 1e-8, recipe + ' actual dial reading');
      if (recipe === 'parallel') {
        const formula = await page.locator('#fml').textContent();
        assert(formula.includes('+'), 'parallel formula must sum branch currents');
        assert.equal(await page.locator('#resistance-label').textContent(), '等效电阻');
        assert.equal(await page.locator('#read-branch-1').textContent(), '0.6');
        assert.equal(await page.locator('#read-branch-2').textContent(), '0.3');
      }
      await page.locator('#btn-record').click();assert.equal(await page.locator('#rows tr').count(), 1);
      await page.locator('#btn-switch').click();assert.equal(await page.evaluate(() => window.__DATA__.I), 0);
      assert.equal(await page.locator('#btn-record').isDisabled(), true);
      await page.locator('#btn-reset').click();assert.equal(await page.locator('#rows tr').count(), 0);
      for (const width of [1366, 760, 390]) {
        await page.setViewportSize({width, height: 1000});
        if (width === 390) await page.locator('.pf-side label').last().hover();
        await page.waitForTimeout(350);
        const overflow = await page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) > innerWidth + 2);
        assert.equal(overflow, false, recipe + ' overflow at ' + width);
        const buttonFits = await page.locator('#btn-enlarge').evaluate(el => {
          const b = el.getBoundingClientRect(), p = (el.closest('.exp-canvas-box') || el.closest('.exp-stage')).getBoundingClientRect();
          return b.top >= p.top && b.bottom <= p.bottom && b.left >= p.left && b.right <= p.right;
        });
        assert(buttonFits, 'enlarge button must remain inside stage at ' + width);
      }
      await page.setViewportSize({width: 1366, height: 1000});
      console.log('PASS ' + recipe + ': physical dial, circuit math, switch, record/reset, responsive shell');
    }
    await page.goto(pathToFileURL(path.join(root, 'examples/circuits/ohm.html')).href);
    const original = await page.evaluate(() => window.__CIRCUIT_STATE__.config);
    let opened = page.waitForEvent('popup');await page.locator('#btn-enlarge').click();let editor = await opened;
    await editor.waitForSelector('#editor-apply');
    await editor.locator('#c-V1-voltage').fill('3');await editor.locator('#c-V1-voltage').dispatchEvent('input');
    assert.equal(await page.evaluate(() => window.__DATA__.U), 6, 'editor draft must be isolated');
    await editor.locator('#editor-cancel').click();
    assert.equal(await page.evaluate(() => window.__DATA__.U), 6, 'cancel retains main');
    opened = page.waitForEvent('popup');await page.locator('#btn-enlarge').click();editor = await opened;
    await editor.waitForSelector('#editor-apply');
    await editor.locator('#c-V1-voltage').fill('3');await editor.locator('#c-V1-voltage').dispatchEvent('input');
    await editor.locator('#c-A1-range').selectOption('0.06');
    await editor.locator('[data-component-id="R1"]').focus();await editor.keyboard.press('ArrowRight');
    let moved = await editor.evaluate(() => window.__EDITOR_CONFIG__.components.find(c => c.id === 'R1').x);
    assert.equal(typeof moved, 'number');
    const housing = await editor.locator('[data-component-id="R1"]').boundingBox();
    await editor.mouse.move(housing.x + housing.width / 2, housing.y + housing.height / 2);
    await editor.mouse.down();await editor.mouse.move(housing.x + housing.width / 2 + 35, housing.y + housing.height / 2 + 15, {steps: 6});await editor.mouse.up();
    const dragged = await editor.evaluate(() => window.__EDITOR_CONFIG__.components.find(c => c.id === 'R1').x);
    assert(dragged > moved, 'real pointer drag must move the apparatus');moved = dragged;
    await editor.setViewportSize({width: 390, height: 844});await editor.waitForTimeout(200);
    assert.equal(await editor.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) > innerWidth + 2), false, 'editor must fit mobile width');
    await editor.setViewportSize({width: 1366, height: 1000});
    await editor.screenshot({path: path.join(root, 'examples/circuits/editor-preview.png'), fullPage: true});
    await editor.locator('#editor-apply').click();
    await page.waitForFunction(() => window.__DATA__.U === 3);
    assert(Math.abs(await page.evaluate(() => window.__DATA__.I) - .3) < 1e-8);
    assert.equal(await page.evaluate(() => window.__CIRCUIT_STATE__.config.components.find(c => c.id === 'R1').x), moved);
    assert.equal(await page.locator('#alert').isVisible(), true, 'low range must warn');
    assert.equal(await page.locator('#btn-record').isDisabled(), true);
    const after = await page.evaluate(() => window.__CIRCUIT_STATE__.config);
    assert.deepEqual(after.wires, original.wires, 'moving preserves wiring');
    console.log('PASS editor: draft isolation, cancel/apply, meter range, keyboard move, preserved ports');
    const downloadEvent = page.waitForEvent('download');
    await page.locator('[data-circuit-download]').evaluate(a => a.click());
    const downloaded = await downloadEvent;
    const exported = path.join(root, 'examples/circuits/.export-check.html');
    await downloaded.saveAs(exported);
    try {
      const copy = await ctx.newPage();await copy.goto(pathToFileURL(exported).href);
      await copy.waitForFunction(() => window.__DATA__ && window.__DATA__.U === 3);
      assert.equal(await copy.locator('[data-meter-id="A1"]').getAttribute('data-range'), '0.06');
      await copy.close();console.log('PASS edited standalone export reload');
    } finally {fs.unlinkSync(exported);}
    await page.locator('#btn-reset').click();
    // Model/fallback provenance can be longer than the sample tag; it must wrap on phones.
    await page.locator('.exp-tag.is-plain').evaluate(el => {el.textContent = '电路组件预设（模型配置未通过）';});
    await page.setViewportSize({width: 390, height: 1000});await page.waitForTimeout(350);
    assert.equal(await page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) > innerWidth + 2), false, 'long provenance tag must wrap within mobile info area');
    await page.setViewportSize({width: 1366, height: 1000});
    await page.locator('.exp-tag.is-plain').evaluate(el => {el.textContent = '电路组件预设（离线示例）';});
    await page.screenshot({path: path.join(root, 'examples/circuits/ohm-preview.png'), fullPage: true});
    assert.deepEqual(errors, [], 'no JS errors');assert.deepEqual(remote, [], 'no network requests');
    console.log('PASS offline: no network requests, no script errors');
  } finally {await browser.close();}
})().catch(error => {console.error(error);process.exitCode = 1;});
