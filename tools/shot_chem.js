const { chromium } = require('playwright');
const { pathToFileURL } = require('url');

(async () => {
  const file = process.argv[2];
  const out = process.argv[3] || 'shots/chem.png';
  const b = await chromium.launch({
    executablePath: 'C:/Users/wangq/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe'
  });
  const p = await b.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 2 });
  const errs = [];
  p.on('pageerror', e => errs.push(String(e)));
  p.on('console', m => { if (m.type() === 'error') errs.push('console:' + m.text()); });
  await p.goto(pathToFileURL(file).href);
  await p.waitForTimeout(700);

  const box = await p.evaluate(() => {
    const b = document.querySelector('.exp-canvas-box') || document.querySelector('canvas').parentNode;
    const r = b.getBoundingClientRect();
    return { x: r.x, y: r.y, width: r.width, height: r.height };
  });
  await p.screenshot({ path: out, clip: box });
  await p.screenshot({ path: out.replace(/\.png$/, '_full.png'), fullPage: true });

  const info = await p.evaluate(() => ({
    data: window.__DATA__,
    cfg: window.__CONFIG__,
    fml: (document.getElementById('fml') || {}).innerText,
    reads: Array.from(document.querySelectorAll('.exp-read')).map(e => e.innerText.replace(/\s+/g, ' ')),
    state: (document.getElementById('state') || {}).innerText,
    alertHidden: (document.getElementById('alert') || {}).hidden
  }));
  console.log(JSON.stringify({ errs, info }, null, 1));
  await b.close();
})();
