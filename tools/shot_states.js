const { chromium } = require('playwright');
const { pathToFileURL } = require('url');

(async () => {
  const file = process.argv[2];
  const b = await chromium.launch({
    executablePath: 'C:/Users/wangq/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe'
  });
  const p = await b.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 2 });
  const errs = [];
  p.on('pageerror', e => errs.push(String(e)));
  p.on('console', m => { if (m.type() === 'error') errs.push('console:' + m.text()); });
  await p.goto(pathToFileURL(file).href);
  await p.waitForTimeout(500);
  const box = await p.evaluate(() => {
    const b = document.querySelector('.exp-canvas-box');
    const r = b.getBoundingClientRect();
    return { x: r.x, y: r.y, width: r.width, height: r.height };
  });
  const states = [[0, 0.4, 80], [100, 0.4, 80], [100, 0.5, 100], [0, 0.1, 40]];
  for (let i = 0; i < states.length; i++) {
    const [pv, cv, vv] = states[i];
    await p.evaluate(([pv, cv, vv]) => {
      const set = (id, v) => { const el = document.querySelector(id); el.value = String(v); el.dispatchEvent(new Event('input', { bubbles: true })); };
      set('#rg-p', pv); set('#rg-c', cv); set('#rg-v', vv);
    }, [pv, cv, vv]);
    await p.waitForTimeout(220);
    await p.screenshot({ path: `shots/state_${i}_${pv}.png`, clip: box });
    const out = await p.evaluate(() => ({
      color: document.querySelector('#hint').innerText.slice(0, 40),
      cu: document.querySelector('#r-cu').innerText,
      alert: document.querySelector('#alert').hidden ? 'hidden' : document.querySelector('#alert').innerText.slice(0, 30)
    }));
    console.log(i, JSON.stringify(out));
  }
  console.log('errs', JSON.stringify(errs));
  await b.close();
})();
