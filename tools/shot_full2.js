const path = require('path');
const home = process.env.HOME || process.env.USERPROFILE || '';
[path.join(home, '.workbuddy/binaries/node/workspace/node_modules')].forEach(p => { if (!module.paths.includes(p)) module.paths.push(p); });
const { chromium } = require('playwright');
const { pathToFileURL } = require('url');

(async () => {
  const file = process.argv[2];
  const out = process.argv[3] || 'shots/full.png';
  const w = +(process.argv[4] || 1500);
  const b = await chromium.launch({ executablePath: 'C:/Users/wangq/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe' });
  const p = await b.newPage({ viewport: { width: w, height: 1000 } });
  await p.goto(pathToFileURL(path.resolve(file)).href);
  await p.waitForTimeout(1200);
  const info = await p.evaluate(() => {
    const cv = document.querySelector('.exp-canvas-box canvas');
    return cv ? { w: cv.width, h: cv.height, cw: cv.clientWidth, ch: cv.clientHeight } : null;
  });
  console.log('canvas', JSON.stringify(info));
  await p.screenshot({ path: out, fullPage: true });
  await b.close();
})();
