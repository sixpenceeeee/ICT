const { chromium } = require('playwright');
const { pathToFileURL } = require('url');

(async () => {
  const file = process.argv[2];
  const scenes = process.argv.slice(3);
  const list = scenes.length ? scenes : ['float', 'optics', 'cube', 'bio', 'geo', 'cs'];
  const b = await chromium.launch({
    executablePath: 'C:/Users/wangq/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe'
  });
  const p = await b.newPage({ viewport: { width: 1100, height: 810 }, deviceScaleFactor: 1.4 });
  const errs = [];
  p.on('pageerror', e => errs.push(String(e)));
  p.on('console', m => { if (m.type() === 'error') errs.push('console:' + m.text()); });

  for (const s of list) {
    await p.goto(pathToFileURL(file).href + '?s=' + s);
    await p.waitForTimeout(420);
    const info = await p.evaluate(() => ({ ok: !!window.__OK__, err: window.__ERR__ || null }));
    await p.screenshot({ path: `shots/lib_${s}.png`, clip: { x: 0, y: 0, width: 1086, height: 772 } });
    console.log(s, JSON.stringify(info));
  }
  console.log('errs', JSON.stringify(errs));
  await b.close();
})();
