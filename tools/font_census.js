/* ============================================================
 *  font_census.js —— 字号普查：页面里到底用了哪几档字、各多少处
 *
 *  ui_audit.js 只回答「有没有小于门槛的字」，这个回答「现在分别是多大」，
 *  用来核对 frame/normal.css 的档位有没有被页面自带样式顶掉。
 *
 *  用法：node tools/font_census.js 页面.html
 * ============================================================ */
const path = require('path');
const home = process.env.HOME || process.env.USERPROFILE || '';
[path.join(home, '.workbuddy/binaries/node/workspace/node_modules')].forEach(p => { if (!module.paths.includes(p)) module.paths.push(p); });
const { chromium } = require('playwright');
const { pathToFileURL } = require('url');

(async () => {
  const b = await chromium.launch({ executablePath: 'C:/Users/wangq/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe' });
  const p = await b.newPage({ viewport: { width: 1500, height: 1000 } });
  await p.goto(pathToFileURL(path.resolve(process.argv[2])).href);
  await p.waitForTimeout(800);
  const r = await p.evaluate(() => {
    const map = {};
    document.querySelectorAll('.pf-main *, .pf-footer *').forEach((el) => {
      let txt = '';
      for (const c of el.childNodes) if (c.nodeType === 3) txt += c.nodeValue.trim();
      if (!txt || txt.length < 2) return;
      if (el.closest('canvas, svg')) return;
      const st = getComputedStyle(el);
      const fs = +parseFloat(st.fontSize).toFixed(1);
      const key = fs;
      map[key] = map[key] || { n: 0, rows: [] };
      map[key].n++;
      if (map[key].rows.length < 3) {
        map[key].rows.push((el.className || el.tagName).toString().split(' ')[0].slice(0, 22) + '  «' + txt.slice(0, 12) + '»');
      }
    });
    return map;
  });
  const keys = Object.keys(r).map(Number).sort((a, b) => b - a);
  console.log('字号分布（' + process.argv[2].split(/[\\/]/).pop() + '）');
  keys.forEach((k) => {
    console.log('  ' + k + 'px  ×' + r[k].n + ' 处');
    r[k].rows.forEach((x) => console.log('        ' + x));
  });
  console.log('最小字号：' + keys[keys.length - 1] + 'px');
  await b.close();
})();
