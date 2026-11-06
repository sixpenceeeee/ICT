const { chromium } = require('playwright');
const { pathToFileURL } = require('url');
(async () => {
  const file = process.argv[2], out = process.argv[3] || 'shots/any.png';
  const b = await chromium.launch({ executablePath: 'C:/Users/wangq/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe' });
  const p = await b.newPage({ viewport: { width: 1200, height: 1040 }, deviceScaleFactor: 1 });
  const errs = [];
  p.on('pageerror', e => errs.push(String(e)));
  p.on('console', m => { if (m.type() === 'error') errs.push('console:' + m.text()); });
  await p.goto(pathToFileURL(file).href);
  await p.waitForTimeout(500);
  await p.screenshot({ path: out, fullPage: true });
  console.log(JSON.stringify({ errs }));
  await b.close();
})();
