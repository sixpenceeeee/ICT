#!/usr/bin/env node
/**
 * optics_page_probe.mjs — 3D 光学页的真浏览器冒烟探针（只读，不修页面）。
 *
 * 用法（仓库根）：node tools/optics_page_probe.mjs examples/optics/lens3d.html
 * 输出：一行 JSON（initial / u=15 / u=5 / 视角拖动与复位 / 记录表行数 / 像素哈希 / 控制台错误）。
 *
 * 依赖：playwright-core。解析顺序：$PLAYWRIGHT_CORE → 本仓 node_modules →
 * 上级 node_modules（sgrz 自身没有 node_modules，通常用上级 ICT 根的那份）。
 */
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

function loadPlaywright() {
  const candidates = [
    process.env.PLAYWRIGHT_CORE,
    path.join(process.cwd(), 'node_modules', 'playwright-core'),
    path.resolve(__dirname, '..', '..', 'node_modules', 'playwright-core'),
  ].filter(Boolean);
  for (const candidate of candidates) {
    try {
      return createRequire(path.join(candidate, 'noop.js'))(candidate);
    } catch (error) { /* try next */ }
  }
  throw new Error('找不到 playwright-core（设 PLAYWRIGHT_CORE 指向包目录）');
}

function findChromium() {
  if (process.env.CHROMIUM_PATH && fs.existsSync(process.env.CHROMIUM_PATH)) return process.env.CHROMIUM_PATH;
  const roots = [
    process.env.LOCALAPPDATA ? path.join(process.env.LOCALAPPDATA, 'ms-playwright') : null,
    'D:/temp/ms-playwright',
  ].filter(Boolean);
  const found = [];
  for (const root of roots) {
    if (!fs.existsSync(root)) continue;
    for (const name of fs.readdirSync(root)) {
      const exe = path.join(root, name, 'chrome-win64', 'chrome.exe');
      if (name.startsWith('chromium-') && fs.existsSync(exe)) found.push(exe);
    }
  }
  if (!found.length) throw new Error('本机没有可用的 chromium 构建');
  found.sort();
  return found[found.length - 1];
}

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

async function snapshot(page) {
  return page.evaluate(() => {
    const canvas = document.getElementById('cv');
    let dataUrl = '';
    try { dataUrl = canvas.toDataURL('image/jpeg', 0.6); } catch (error) { dataUrl = 'ERR:' + error.message; }
    const readouts = {};
    document.querySelectorAll('[data-optics-readout]').forEach(node => {
      readouts[node.getAttribute('data-optics-readout')] = node.textContent;
    });
    return {
      model: window.__OPTICS_MODEL__ || null,
      result: window.__OPTICS_RESULT__ || null,
      view: window.__OPTICS_VIEW__ || null,
      mathView: canvas.__mathView || null,
      render3d: window.__OPTICS_RENDER3D__ || null,
      sig: canvas.dataset.opticsSig || null,
      bound: Number(canvas.dataset.opticsBound || 0),
      readouts,
      formula: (document.querySelector('[data-optics-formula]') || {}).textContent || '',
      dataUrl,
      rows: document.querySelectorAll('[data-optics-record] tr').length,
    };
  });
}

function hash(text) {
  return crypto.createHash('sha1').update(text).digest('hex').slice(0, 16);
}

async function setSlider(page, key, value) {
  await page.evaluate(([k, v]) => {
    const input = document.querySelector('[data-optics-control="' + k + '"]');
    if (!input) throw new Error('缺少控件 ' + k);
    input.value = String(v);
    input.dispatchEvent(new Event('input', { bubbles: true }));
  }, [key, value]);
  await sleep(120);
}

async function main() {
  const pagePath = path.resolve(process.argv[2] || 'examples/optics/lens3d.html');
  const { chromium } = loadPlaywright();
  const browser = await chromium.launch({
    executablePath: findChromium(),
    args: ['--use-gl=angle', '--use-angle=swiftshader', '--disable-gpu-sandbox'],
  });
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const errors = [];
  page.on('pageerror', error => errors.push(String(error)));
  page.on('console', msg => { if (msg.type() === 'error') errors.push('console: ' + msg.text()); });

  const out = { page: pagePath.replace(/\\/g, '/'), errors };
  try {
    await page.goto('file:///' + pagePath.replace(/\\/g, '/'));
    await page.waitForFunction(() => window.__OPTICS_RESULT__, null, { timeout: 20000 });
    const initial = await snapshot(page);
    out.initial = { ...initial, pixelHash: hash(initial.dataUrl), dataUrl: undefined };

    await setSlider(page, 'u', 15);
    const u15 = await snapshot(page);
    out.u15 = { ...u15, pixelHash: hash(u15.dataUrl), dataUrl: undefined };

    await setSlider(page, 'u', 5);
    const u5 = await snapshot(page);
    out.u5 = { ...u5, pixelHash: hash(u5.dataUrl), dataUrl: undefined };

    // u = f：必须判「不成像」，不得出现 Infinity 或伪造像点
    const focal = await page.evaluate(() => Number((document.querySelector('[data-optics-control="f"]') || {}).value || 10));
    await setSlider(page, 'u', focal);
    const uf = await snapshot(page);
    out.uf = { ...uf, pixelHash: hash(uf.dataUrl), dataUrl: undefined };

    // 视角拖动：从画布中心拖到右上
    const box = await page.locator('#cv').boundingBox();
    await page.mouse.move(box.x + box.width * 0.5, box.y + box.height * 0.5);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width * 0.62, box.y + box.height * 0.42, { steps: 6 });
    await page.mouse.up();
    await sleep(120);
    const dragged = await snapshot(page);
    out.dragged = { view: dragged.view, mathView: dragged.mathView };

    await page.click('[data-optics-reset-view]');
    await sleep(120);
    const reset = await snapshot(page);
    out.reset = { view: reset.view, mathView: reset.mathView };

    await page.click('[data-optics-record-btn]');
    await page.click('[data-optics-record-btn]');
    await sleep(80);
    out.rowsAfterRecord = (await snapshot(page)).rows;

    // 放大独立调节页：草稿隔离 → 应用回传主页面
    await setSlider(page, 'u', 30);
    const popupPromise = page.waitForEvent('popup');
    await page.click('[data-optics-enlarge]');
    const editorPage = await popupPromise;
    await editorPage.waitForSelector('#optics-editor-apply', { timeout: 15000 });
    await editorPage.waitForFunction(() => window.__OPTICS_EDITOR_MODEL__, null, { timeout: 15000 });
    await editorPage.evaluate(() => {
      const input = document.querySelector('#optics-editor-root [data-optics-control="u"]');
      input.value = '20';
      input.dispatchEvent(new Event('input', { bubbles: true }));
    });
    await sleep(120);
    const mainBeforeApply = (await snapshot(page)).model.u;
    await editorPage.click('#optics-editor-apply');
    await page.waitForFunction(() => window.__OPTICS_MODEL__ && window.__OPTICS_MODEL__.u === 20, null, { timeout: 10000 });
    const afterApply = await snapshot(page);
    out.enlarge = {
      mainBeforeApply,
      appliedU: afterApply.model.u,
      appliedV: afterApply.result.v,
    };
  } catch (error) {
    out.failure = String(error && error.stack || error);
  } finally {
    await browser.close();
  }
  process.stdout.write(JSON.stringify(out));
}

main().catch(error => {
  process.stdout.write(JSON.stringify({ failure: String(error && error.stack || error) }));
  process.exit(1);
});
