const { chromium } = require('playwright');
const { pathToFileURL } = require('url');
(async () => {
  const b = await chromium.launch({ executablePath: 'C:/Users/wangq/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe' });
  const p = await b.newPage({ viewport: { width: 1100, height: 810 }, deviceScaleFactor: 1 });
  await p.goto(pathToFileURL(process.argv[2]).href + '?s=float');
  await p.waitForTimeout(400);
  const out = await p.evaluate(() => {
    const cv = document.getElementById('cv');
    const g = cv.getContext('2d');
    const w = cv.width, h = cv.height;
    const rows = [480, 520, 560, 600];
    const res = {};
    rows.forEach(y => {
      const d = g.getImageData(0, y, w, 1).data;
      const lum = [];
      for (let x = 0; x < w; x++) lum.push(d[x * 4] + d[x * 4 + 1] + d[x * 4 + 2]);
      const edges = [];
      for (let x = 6; x < w; x++) if (Math.abs(lum[x] - lum[x - 3]) > 3) edges.push(x);
      // 合并相邻
      const merged = [];
      edges.forEach(e => { if (!merged.length || e - merged[merged.length - 1] > 4) merged.push(e); });
      res[y] = merged.slice(0, 30);
    });
    return { w, h, res };
  });
  console.log(JSON.stringify(out));
  await b.close();
})();
