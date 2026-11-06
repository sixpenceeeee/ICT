const { chromium } = require('playwright');
const { pathToFileURL } = require('url');
(async () => {
  const file = process.argv[2];
  const b = await chromium.launch({ executablePath: 'C:/Users/wangq/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe' });
  const p = await b.newPage({ viewport: { width: 1200, height: 900 }, deviceScaleFactor: 1 });
  const errs = [];
  p.on('pageerror', e => errs.push(String(e)));
  await p.goto(pathToFileURL(file).href);
  await p.waitForTimeout(800);
  const before = await p.evaluate(() => ({
    hasCHEM: !!window.CHEM,
    drawn: !!window.__CHEM_DRAWN__,
    auto: !!window.__CHEM_AUTO__,
    cvInBox: !!document.querySelector('.exp-canvas-box canvas'),
  }));
  const after = await p.evaluate(() => { try { window.CHEM.auto(); return { ok: true, drawn: !!window.__CHEM_DRAWN__ }; } catch (e) { return { ok: false, err: String(e) }; } });
  await p.waitForTimeout(300);
  await p.screenshot({ path: 'shots/dbg_after_auto.png', fullPage: false });
  console.log(JSON.stringify({ errs, before, after }, null, 1));
  await b.close();
})();
