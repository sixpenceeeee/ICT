const { chromium } = require('playwright');
const { pathToFileURL } = require('url');

(async () => {
  const file = process.argv[2];
  const out = process.argv[3] || 'shot.png';
  const b = await chromium.launch({
    executablePath: 'C:/Users/wangq/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe'
  });
  const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
  const errs = [];
  p.on('pageerror', e => errs.push(String(e)));
  p.on('console', m => { if (m.type() === 'error') errs.push('console:' + m.text()); });
  await p.goto(pathToFileURL(file).href);
  await p.waitForTimeout(600);
  await p.screenshot({ path: out, fullPage: true });

  const geo = await p.evaluate(() => window.__GEO__ || null);
  const dom = await p.evaluate(() => ({
    n: (document.getElementById('r-n') || {}).textContent,
    s: (document.getElementById('r-s') || {}).textContent,
    v1: (document.getElementById('r-v1') || {}).textContent,
    v2: (document.getElementById('r-v2') || {}).textContent,
    fml: (document.getElementById('fml') || {}).textContent,
    rows: (document.getElementById('rows') || {}).children.length
  }));

  // 拖一下滑块，验证交互后数值确实变化
  await p.fill('#rg-theta', '55');
  await p.dispatchEvent('#rg-theta', 'input');
  await p.waitForTimeout(200);
  const geo2 = await p.evaluate(() => window.__GEO__);

  await p.click('#btn-record');
  await p.waitForTimeout(150);
  const rowsAfter = await p.evaluate(() => document.getElementById('rows').children.length);
  await p.screenshot({ path: out.replace('.png', '_2.png'), fullPage: false });

  console.log(JSON.stringify({ errs, geo, dom, geo2, rowsAfter }, null, 2));
  await b.close();
})();
