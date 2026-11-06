/* 量一下 ②区演示容器和画布的真实尺寸，定位画布被压扁的原因。 */
const path = require('path');
const home = process.env.HOME || process.env.USERPROFILE || '';
[path.join(home, '.workbuddy/binaries/node/workspace/node_modules')].forEach(p => {
  if (!module.paths.includes(p)) module.paths.push(p);
});
const { chromium } = require('playwright');
const { pathToFileURL } = require('url');
const CHROME = 'C:/Users/wangq/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe';

(async () => {
  const b = await chromium.launch({ executablePath: CHROME });
  const p = await b.newPage({ viewport: { width: 1500, height: 1000 } });
  await p.goto(pathToFileURL(path.resolve(process.argv[2])).href);
  await p.waitForTimeout(1500);
  const r = await p.evaluate(() => {
    function box(sel) {
      const e = document.querySelector(sel);
      if (!e) return null;
      const cs = getComputedStyle(e);
      const rc = e.getBoundingClientRect();
      return {
        sel: sel, w: Math.round(rc.width), h: Math.round(rc.height),
        display: cs.display, position: cs.position,
        height: cs.height, minHeight: cs.minHeight, flex: cs.flex,
        aspect: cs.aspectRatio, padding: cs.padding
      };
    }
    const out = [];
    ['.exp-wrap', '.exp-grid', '.exp-stage', '.exp-canvas-box', 'canvas',
     '.exp-control', '.exp-result'].forEach(s => out.push(box(s)));
    return out;
  });
  r.forEach(x => console.log(x ? JSON.stringify(x) : 'null'));
  await b.close();
})();
