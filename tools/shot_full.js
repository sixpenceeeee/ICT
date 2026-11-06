const { chromium } = require('playwright');
const { pathToFileURL } = require('url');
(async () => {
  const file = process.argv[2], out = process.argv[3] || 'shots/full.png';
  const b = await chromium.launch({ executablePath: 'C:/Users/wangq/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe' });
  const p = await b.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1.25 });
  const errs = [];
  p.on('pageerror', e => errs.push(String(e)));
  p.on('console', m => { if (m.type() === 'error') errs.push('console:' + m.text()); });
  await p.goto(pathToFileURL(file).href);
  await p.waitForTimeout(900);
  const ok = await p.evaluate(() => !!window.__GALLERY_READY__);
  await p.screenshot({ path: out, fullPage: true });
  console.log(JSON.stringify({ ok, errs }));
  await b.close();
})();
