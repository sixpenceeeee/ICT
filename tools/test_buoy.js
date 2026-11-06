/* 验证自由浮沉动力学：木块上浮漂浮 / 铝块沉底 / 缓慢浸入 */
const { chromium } = require('playwright');
const { pathToFileURL } = require('url');
const EXEC = 'C:/Users/wangq/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe';

(async () => {
  const file = process.argv[2];
  const b = await chromium.launch({ executablePath: EXEC });
  const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  p.on('pageerror', e => errors.push(String(e).slice(0, 200)));
  await p.goto(pathToFileURL(file).href);
  await p.waitForTimeout(600);

  const setRho = async v => {
    await p.evaluate(v => {
      const el = document.getElementById('rg-rho');
      el.value = String(v);
      el.dispatchEvent(new Event('input', { bubbles: true }));
    }, v);
  };
  const snap = () => p.evaluate(() => {
    const d = window.__DATA__;
    return { mode: d.mode, state: d.state, Fb: d.F_buoy, Fs: d.F_spring,
             Vd: d.V_displaced, yb: d.immersion_depth };
  });

  // 1) 自由浮沉：木块 0.6 应上浮至漂浮，V排/V物 = 0.6
  await p.click('#btn-mode');
  await setRho(0.6);
  await p.waitForTimeout(3500);
  const wood = await snap();
  await p.screenshot({ path: 'shots/buoy_free_wood.png', clip: { x: 20, y: 150, width: 680, height: 580 } });

  // 2) 铝块 2.7 沉底
  await setRho(2.7);
  await p.waitForTimeout(2500);
  const alu = await snap();

  // 3) 回悬挂模式，缓慢浸入
  await p.click('#btn-mode');
  await p.click('#btn-soak');
  await p.waitForTimeout(5600);
  const soaked = await snap();
  await p.screenshot({ path: 'shots/buoy_soaked.png', clip: { x: 20, y: 150, width: 680, height: 580 } });

  console.log(JSON.stringify({ errors, wood, alu, soaked }, null, 1));
  await b.close();
})();
