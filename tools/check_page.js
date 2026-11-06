/**
 * check_page.js —— 交付前用真实浏览器验一遍「壳 + 六区域 + 交互」
 *
 * 检查四件事：
 *   1. 外壳齐不齐（页眉 / 右侧栏 / 页脚 / 三个弹窗 / 两份 css / logo）
 *   2. 六区域在不在、是不是空的
 *   3. 有没有 JS 报错
 *   4. 交互真的动了吗：拖第一个滑块、点「记录当前数据」，看数据和表格变没变
 *
 * 用法：node check_page.js <html路径> [截图路径]
 * 输出：一段 JSON
 */
const { chromium } = require('playwright');
const { pathToFileURL } = require('url');

const EXEC = 'C:/Users/wangq/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe';

(async () => {
  const file = process.argv[2];
  const shot = process.argv[3];
  if (!file) { console.log(JSON.stringify({ ok: false, errors: ['缺少参数 html 路径'] })); return; }

  const b = await chromium.launch({ executablePath: EXEC });
  const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  p.on('pageerror', e => errors.push('JS异常: ' + String(e).slice(0, 200)));
  p.on('console', m => { if (m.type() === 'error') errors.push('console: ' + m.text().slice(0, 160)); });
  p.on('requestfailed', r => {
    const u = r.url();
    if (!u.startsWith('data:')) errors.push('资源加载失败: ' + u.split('/').pop());
  });

  await p.goto(pathToFileURL(file).href);
  await p.waitForTimeout(500);

  const shellState = await p.evaluate(() => ({
    header: !!document.querySelector('.pf-header'),
    side: !!document.querySelector('.pf-side'),
    footer: !!document.querySelector('.pf-footer'),
    modals: document.querySelectorAll('.pf-modal').length,
    title: (document.querySelector('.pf-page') || {}).textContent || '',
    secs: ['info', 'stage', 'control', 'result', 'record', 'teach'].map(id => {
      const el = document.getElementById('sec-' + id);
      const body = el ? el.innerText.replace(/\s+/g, '') : '';
      return { id, exists: !!el, chars: body.length, empty: !el || body.length < 8 };
    }),
    canvas: (() => {
      const c = document.querySelector('#sec-stage canvas, #sec-stage svg');
      if (!c) return { exists: false };
      const r = c.getBoundingClientRect();
      return { exists: true, w: Math.round(r.width), h: Math.round(r.height) };
    })(),
    readouts: Array.from(document.querySelectorAll('.exp-read .v')).map(e => e.innerText.trim()),
    formula: (document.getElementById('fml') || {}).innerText || ''
  }));

  const data1 = await p.evaluate(() => window.__DATA__ || window.__GEO__ || null);

  // 拖第一个滑块到 80% 位置，看数据是否变化
  let moved = null;
  const sliders = await p.$$('input[type=range]');
  if (sliders.length) {
    const box = await sliders[0].boundingBox();
    if (box) {
      await p.mouse.click(box.x + box.width * 0.82, box.y + box.height / 2);
      await p.waitForTimeout(250);
    }
    const data2 = await p.evaluate(() => window.__DATA__ || window.__GEO__ || null);
    moved = JSON.stringify(data1) !== JSON.stringify(data2);
  } else {
    moved = false;
  }

  // 点「记录当前数据」
  let rowsBefore = 0, rowsAfter = 0, recordOk = null;
  const rec = await p.$('#btn-record');
  if (rec) {
    rowsBefore = await p.evaluate(() => (document.getElementById('rows') || { children: [] }).children.length);
    await rec.click();
    await p.waitForTimeout(200);
    rowsAfter = await p.evaluate(() => (document.getElementById('rows') || { children: [] }).children.length);
    recordOk = rowsAfter > rowsBefore;
  }

  if (shot) await p.screenshot({ path: shot, fullPage: true });

  const problems = [];
  if (!shellState.header) problems.push('缺页眉');
  if (!shellState.side) problems.push('缺右侧图标栏');
  if (!shellState.footer) problems.push('缺页脚');
  if (shellState.modals < 3) problems.push('弹窗不足 3 个');
  shellState.secs.forEach(s => { if (!s.exists) problems.push('缺区域 sec-' + s.id); else if (s.empty) problems.push('区域 sec-' + s.id + ' 是空的'); });
  if (!shellState.canvas.exists) problems.push('演示区没有 canvas/svg');
  else if (shellState.canvas.w < 200 || shellState.canvas.h < 150) problems.push('画布尺寸过小 ' + shellState.canvas.w + 'x' + shellState.canvas.h);
  if (!data1) problems.push('没有暴露 window.__DATA__ / __GEO__');
  if (moved === false) problems.push('拖动滑块后数据没有变化');
  if (recordOk === false) problems.push('点「记录当前数据」表格没有新增行');
  problems.push.apply(problems, errors);

  console.log(JSON.stringify({
    ok: problems.length === 0,
    problems,
    shell: shellState,
    data: data1,
    sliderChanged: moved,
    record: { rowsBefore, rowsAfter }
  }, null, 2));

  await b.close();
})();
