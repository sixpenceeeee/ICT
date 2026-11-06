// 截正方体四状态回归：六边形/四边形/三角形/五边形
// 断言：边数正确、上下体积和 = a³、画面不越界、无 JS 报错
const { chromium } = require('playwright');
const { pathToFileURL } = require('url');

(async () => {
  const file = 'tools/cube_states.html';
  const b = await chromium.launch({
    executablePath: 'C:/Users/wangq/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe'
  });
  const p = await b.newPage({ viewport: { width: 1000, height: 800 }, deviceScaleFactor: 1.4 });
  const errs = [];
  p.on('pageerror', e => errs.push(String(e)));

  const want = { hex: 6, quad: 4, tri: 3, penta: 5 };
  let pass = 0, fail = 0;

  for (const s of ['hex', 'quad', 'tri', 'penta']) {
    await p.goto(pathToFileURL(file).href + '?s=' + s);
    await p.waitForTimeout(450);
    const r = await p.evaluate(() => window.__RES__ || { err: window.__ERR__ });
    const g = (r && r.geo) || {};
    const okSide = r.sides === want[s];
    const okVol = Math.abs((g.v_sum || 0) - 1) < 0.005;
    const okBox = g.in_bounds === true;
    const line = [
      s.padEnd(6),
      ('边数 ' + r.sides + (okSide ? '' : '（应为 ' + want[s] + '）')).padEnd(16),
      'V上+V下=' + (g.v_sum == null ? '—' : g.v_sum.toFixed(3)),
      '越界=' + (okBox ? '否' : '是'),
      'bbox=[' + (g.screen_bbox || []).map(x => Math.round(x)).join(',') + ']'
    ].join('  ');
    if (okSide && okVol && okBox) { pass++; console.log('  OK   ' + line); }
    else { fail++; console.log('  FAIL ' + line); }
    await p.screenshot({ path: `shots/cube_${s}.png`, clip: { x: 0, y: 0, width: 940, height: 760 } });
  }
  console.log(`\n通过 ${pass} / ${pass + fail}` + (errs.length ? '  报错：' + JSON.stringify(errs.slice(0, 3)) : ''));
  await b.close();
})();
