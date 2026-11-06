const { chromium } = require('playwright');

(async () => {
  const target = process.argv[2];
  const out = process.argv[3];
  const browser = await chromium.launch({
    executablePath: 'C:/Users/wangq/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe',
  });
  const page = await browser.newPage({ viewport: { width: 1280, height: 1000 } });

  const errors = [];
  page.on('pageerror', e => errors.push('PAGEERROR: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') errors.push('CONSOLE: ' + m.text()); });

  await page.goto('file:///' + target.replace(/\\/g, '/'));
  await page.waitForTimeout(600);
  await page.screenshot({ path: out, fullPage: true });

  const state = await page.evaluate(() => ({
    i: document.getElementById('iOut') ? document.getElementById('iOut').textContent : null,
    formula: document.getElementById('formula') ? document.getElementById('formula').textContent : null,
    canvasW: document.getElementById('chart') ? document.getElementById('chart').width : null,
  }));

  console.log(JSON.stringify({ errors, state }, null, 2));
  await browser.close();
})();
