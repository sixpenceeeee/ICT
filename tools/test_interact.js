/*
 * 交互联动体检：拖动 / 点击参数控件后，②区演示画面到底变没变。
 *
 * 判定方式（两条独立证据，任一成立即算「有联动」）：
 *   1) 像素级：对 ②区画布截图做逐像素差异统计，统计变化像素占比；
 *   2) 数据级：window.__GEO__ / window.__DATA__ 的关键字段发生变化。
 *
 * 用法：node tools/test_interact.js <html文件> [输出目录]
 */
const path = require('path');
const fs = require('fs');
const home = process.env.HOME || process.env.USERPROFILE || '';
[path.join(home, '.workbuddy/binaries/node/workspace/node_modules')].forEach(p => {
  if (!module.paths.includes(p)) module.paths.push(p);
});
const { chromium } = require('playwright');
const { pathToFileURL } = require('url');

const file = process.argv[2];
const outDir = process.argv[3] || 'shots';
const CHROME = 'C:/Users/wangq/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe';

// 逐像素比较两张 PNG 的原始 RGBA（借助浏览器解码，避免引入图像库）
async function diffRatio(page, a, b) {
  const ab = fs.readFileSync(a).toString('base64');
  const bb = fs.readFileSync(b).toString('base64');
  return await page.evaluate(async ([ab, bb]) => {
    async function load(b64) {
      const img = new Image();
      img.src = 'data:image/png;base64,' + b64;
      await img.decode();
      const c = document.createElement('canvas');
      c.width = img.width; c.height = img.height;
      const x = c.getContext('2d');
      x.drawImage(img, 0, 0);
      return x.getImageData(0, 0, c.width, c.height);
    }
    const A = await load(ab), B = await load(bb);
    if (A.width !== B.width || A.height !== B.height) return 1;
    let diff = 0, total = A.width * A.height;
    for (let i = 0; i < A.data.length; i += 4) {
      const dr = Math.abs(A.data[i] - B.data[i]);
      const dg = Math.abs(A.data[i + 1] - B.data[i + 1]);
      const db = Math.abs(A.data[i + 2] - B.data[i + 2]);
      if (dr + dg + db > 24) diff++;
    }
    return diff / total;
  }, [ab, bb]);
}

(async () => {
  fs.mkdirSync(outDir, { recursive: true });
  const b = await chromium.launch({ executablePath: CHROME });
  const p = await b.newPage({ viewport: { width: 1500, height: 1000 } });
  const errs = [];
  p.on('pageerror', e => errs.push(String(e.message || e)));
  await p.goto(pathToFileURL(path.resolve(file)).href);
  await p.waitForTimeout(1500);

  // 可见的那张画布（库接管后会新建节点，旧节点被 display:none）
  const box = await p.$('.exp-canvas-box');
  const stage = box || (await p.$('canvas'));

  const snapState = () => p.evaluate(() => {
    const g = window.__GEO__ || {}, d = window.__DATA__ || {};
    return JSON.stringify({ g: g, dp: d.params || null, dr: d.result || null });
  });

  const s0 = await snapState();
  await stage.screenshot({ path: path.join(outDir, 'it_before.png') });

  // 逐个拨动 range 控件
  const sliders = await p.$$('input[type=range]');
  const results = [];
  for (let i = 0; i < sliders.length; i++) {
    const el = sliders[i];
    const info = await el.evaluate(e => ({
      id: e.id, key: e.dataset.key || '', min: e.min, max: e.max,
      step: e.step, value: e.value
    }));
    const mn = parseFloat(info.min), mx = parseFloat(info.max);
    // 拨到一个明显不同的值（约 70% 量程处）
    let target = mn + (mx - mn) * 0.7;
    const st = parseFloat(info.step) || 1;
    target = Math.round(target / st) * st;
    if (Math.abs(target - parseFloat(info.value)) < 1e-9) {
      target = mn + (mx - mn) * 0.3;
      target = Math.round(target / st) * st;
    }
    await p.evaluate(([e, v]) => {
      e.value = String(v);
      e.dispatchEvent(new Event('input', { bubbles: true }));
      e.dispatchEvent(new Event('change', { bubbles: true }));
    }, [el, target]);
    await p.waitForTimeout(320);

    await stage.screenshot({ path: path.join(outDir, 'it_after_' + i + '.png') });
    const ratio = await diffRatio(p, path.join(outDir, 'it_before.png'),
                                      path.join(outDir, 'it_after_' + i + '.png'));
    const s1 = await snapState();
    results.push({
      控件: info.id || ('#' + i), key: info.key,
      原值: info.value, 新值: String(target),
      画布变化: (ratio * 100).toFixed(1) + '%',
      数据变化: s1 !== s0
    });
    // 复位，避免后续滑块叠加影响
    await p.evaluate(([e, v]) => {
      e.value = String(v);
      e.dispatchEvent(new Event('input', { bubbles: true }));
    }, [el, info.value]);
    await p.waitForTimeout(200);
    await stage.screenshot({ path: path.join(outDir, 'it_before.png') });
  }

  // 顺带看看有几个画布、哪张是可见的（判断库有没有抢画布）
  const canvases = await p.evaluate(() => {
    return [].slice.call(document.querySelectorAll('.exp-canvas-box canvas, canvas'))
      .map(c => ({
        id: c.id, w: c.width, h: c.height,
        可见: !!(c.offsetWidth || c.offsetHeight) && getComputedStyle(c).display !== 'none'
      }));
  });

  console.log('文件:', file);
  console.log('画布:', JSON.stringify(canvases));
  console.table(results);
  if (errs.length) console.log('页面报错:', errs.slice(0, 5));
  await b.close();
})();
