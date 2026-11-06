/* 单次交互后连续取样：如果静止之后画面又变一次，说明有人在「事后补画」= 闪动源 */
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

(async () => {
  const b = await chromium.launch({ executablePath: CHROME });
  const p = await b.newPage({ viewport: { width: 1500, height: 1000 } });
  await p.goto(pathToFileURL(path.resolve(file)).href);
  await p.waitForTimeout(1800);

  // 标记：看看各个库有没有真的收手
  const flags = await p.evaluate(() => ({
    __PHYS_DRAWN__: !!window.__PHYS_DRAWN__,
    __CHEM_DRAWN__: !!window.__CHEM_DRAWN__,
    __CHEM_AUTO__: !!window.__CHEM_AUTO__,
    __MATH_DRAWN__: !!window.__MATH_DRAWN__,
    __BIO_DRAWN__: !!window.__BIO_DRAWN__,
    __GEO_DRAWN__: !!window.__GEO_DRAWN__,
    画布数: document.querySelectorAll('canvas').length
  }));
  console.log('库占用标记:', JSON.stringify(flags));

  const stage = await p.$('.exp-canvas-box') || await p.$('canvas');
  const shoot = () => stage.screenshot().then(b => b.toString('base64'));

  const base = await shoot();
  // 拨一次滑块
  const el = (await p.$$('input[type=range]'))[0];
  await el.evaluate(e => {
    const st = parseFloat(e.step) || 1;
    let v = parseFloat(e.value) + st * 6;
    if (v > parseFloat(e.max)) v = parseFloat(e.min);
    e.value = String(v);
    e.dispatchEvent(new Event('input', { bubbles: true }));
  });
  await p.waitForTimeout(40);

  const seq = [await shoot()];
  for (let i = 0; i < 14; i++) {
    await p.waitForTimeout(60);
    seq.push(await shoot());
  }

  const r = await p.evaluate(async ([a, list]) => {
    async function load(b64) {
      const im = new Image(); im.src = 'data:image/png;base64,' + b64; await im.decode();
      const c = document.createElement('canvas');
      c.width = im.width; c.height = im.height;
      const g = c.getContext('2d'); g.drawImage(im, 0, 0);
      return g.getImageData(0, 0, c.width, c.height).data;
    }
    const base = await load(a);
    const out = [];
    let prev = null;
    for (const s of list) {
      const cur = await load(s);
      let vsBase = 0, vsPrev = 0;
      for (let k = 0; k < base.length; k += 16) {
        const d1 = (Math.abs(base[k] - cur[k]) + Math.abs(base[k + 1] - cur[k + 1]) + Math.abs(base[k + 2] - cur[k + 2])) / 3;
        if (d1 > 18) vsBase++;
        if (prev) {
          const d2 = (Math.abs(prev[k] - cur[k]) + Math.abs(prev[k + 1] - cur[k + 1]) + Math.abs(prev[k + 2] - cur[k + 2])) / 3;
          if (d2 > 18) vsPrev++;
        }
      }
      const n = base.length / 16;
      out.push({ vsBase: +(vsBase / n * 100).toFixed(1), vsPrev: prev ? +(vsPrev / n * 100).toFixed(1) : null });
      prev = cur;
    }
    return out;
  }, [base, seq]);

  console.log('\n单次拨动之后，每 60ms 取一帧（静止后应连续 0 次变化）：');
  r.forEach((x, i) => {
    console.log('  +' + String(i * 60 + 40).padStart(3) + 'ms  与拨动前差异 ' +
      String(x.vsBase).padStart(5) + '%   与上一帧差异 ' +
      String(x.vsPrev === null ? '-' : x.vsPrev).padStart(5) + '%');
  });
  const tail = r.slice(3).filter(x => x.vsPrev > 0.3).length;
  console.log('\n结论：' + (tail === 0
    ? '静止后无二次变化 → 无事后补画，不闪'
    : '静止后仍有 ' + tail + ' 次变化 → 存在事后补画（闪动源）'));
  await b.close();
})();
