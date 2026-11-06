/* 闪烁复现：连续抓演示区画布快照，量化每帧之间的变化；同时统计可见画布数 */
const path = require('path');
const fs = require('fs');
const home = process.env.HOME || process.env.USERPROFILE || '';
[path.join(home, '.workbuddy/binaries/node/workspace/node_modules')].forEach(p => {
  if (!module.paths.includes(p)) module.paths.push(p);
});
const { chromium } = require('playwright');
const { pathToFileURL } = require('url');
const CHROME = 'C:/Users/wangq/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe';

const file = process.argv[2];
const mode = process.argv[3] || 'idle';   // idle = 静置；drag = 拖滑块

(async () => {
  const b = await chromium.launch({ executablePath: CHROME });
  const p = await b.newPage({ viewport: { width: 1500, height: 1000 } });
  const errs = [];
  p.on('pageerror', e => errs.push(e.message));
  await p.goto(pathToFileURL(path.resolve(file)).href);
  await p.waitForTimeout(1600);

  const info = await p.evaluate(() => {
    const cs = [].slice.call(document.querySelectorAll('canvas'));
    return {
      画布数: cs.length,
      明细: cs.map(c => ({
        id: c.id, cls: c.className,
        可见: !!(c.offsetWidth || c.offsetHeight) && getComputedStyle(c).display !== 'none',
        位置: getComputedStyle(c).position,
        z: getComputedStyle(c).zIndex,
        w: c.width, h: c.height
      })),
      滑块数: document.querySelectorAll('input[type=range]').length
    };
  });
  console.log(JSON.stringify(info, null, 1));

  const stage = await p.$('.exp-canvas-box') || await p.$('canvas');

  // 连续抓 14 帧，每帧间隔 70ms
  const shots = [];
  const grab = async () => {
    const buf = await stage.screenshot();
    shots.push(buf.toString('base64'));
  };

  let sliderEl = null;
  if (mode === 'drag') {
    sliderEl = (await p.$$('input[type=range]'))[0];
  }

  await grab();
  for (let i = 0; i < 13; i++) {
    if (mode === 'drag' && sliderEl) {
      // 一格一格拨，模拟真人拖动
      await sliderEl.evaluate(e => {
        const st = parseFloat(e.step) || 1, mx = parseFloat(e.max);
        let v = parseFloat(e.value) + st * 4;
        if (v > mx) v = parseFloat(e.min);
        e.value = String(v);
        e.dispatchEvent(new Event('input', { bubbles: true }));
      });
    }
    await p.waitForTimeout(70);
    await grab();
  }

  const diffs = await p.evaluate(async (list) => {
    async function load(b64) {
      const im = new Image(); im.src = 'data:image/png;base64,' + b64; await im.decode();
      const c = document.createElement('canvas');
      c.width = im.width; c.height = im.height;
      const g = c.getContext('2d'); g.drawImage(im, 0, 0);
      return g.getImageData(0, 0, c.width, c.height);
    }
    const ims = [];
    for (const s of list) ims.push(await load(s));
    const out = [];
    for (let i = 1; i < ims.length; i++) {
      const A = ims[i - 1].data, B = ims[i].data;
      let diff = 0, maxch = 0;
      for (let k = 0; k < A.length; k += 16) {
        const ch = (Math.abs(A[k] - B[k]) + Math.abs(A[k + 1] - B[k + 1]) + Math.abs(A[k + 2] - B[k + 2])) / 3;
        if (ch > 18) diff++;
        if (ch > maxch) maxch = ch;
      }
      out.push({ i: i, diff: +(diff / (A.length / 16) * 100).toFixed(1), maxch: Math.round(maxch) });
    }
    return out;
  }, shots);

  console.log('\n模式:', mode, '| 尺寸', shots.length, '帧');
  console.log('帧间变化占比（静置时应接近 0，拖滑块时应有变化但不该整屏乱跳）：');
  diffs.forEach(d => console.log('  #' + String(d.i).padStart(2),
    String(d.diff).padStart(6) + '%  最大色差', String(d.maxch).padStart(3),
    '  ' + '█'.repeat(Math.min(50, Math.round(d.diff / 2)))));
  if (errs.length) console.log('页面报错:', errs.slice(0, 3));
  await b.close();
})();
