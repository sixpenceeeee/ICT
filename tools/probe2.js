const { chromium } = require('playwright');
const { pathToFileURL } = require('url');
(async () => {
  const b = await chromium.launch({ executablePath: 'C:/Users/wangq/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe' });
  for (const [w, h, dpr, tag] of [[900, 640, 1, 'exact'], [1086, 772, 1, 'scaled'], [1086, 772, 2, 'scaled2']]) {
    const p = await b.newPage({ viewport: { width: w + 20, height: h + 20 }, deviceScaleFactor: dpr });
    await p.goto(pathToFileURL(process.argv[2]).href + '?s=float');
    await p.evaluate(([w, h]) => {
      const box = document.getElementById('box');
      box.style.width = w + 'px'; box.style.height = h + 'px';
    }, [w, h]);
    await p.waitForTimeout(500);
    await p.screenshot({ path: `shots/probe_${tag}.png`, clip: { x: 0, y: 0, width: w, height: h } });
    await p.close();
  }
  await b.close();
})();
