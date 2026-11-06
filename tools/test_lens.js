// 验证凸透镜成像三种特殊状态 + 截图
const { chromium } = require('playwright');
const path = require('path');

(async () => {
  const html = path.resolve(process.argv[2]);
  const b = await chromium.launch({ executablePath: 'C:/Users/wangq/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe' });
  const pg = await b.newPage({ viewport: { width: 1440, height: 1100 } });
  const errs = [];
  pg.on('pageerror', e => errs.push(String(e)));
  await pg.goto('file:///' + html.replace(/\\/g, '/'));
  await pg.waitForTimeout(400);

  const shot = async n => pg.screenshot({ path: 'shots/' + n });

  // 1. u<f 虚像
  await pg.evaluate(() => {
    const rg = document.getElementById('rg-u');
    rg.value = '8'; rg.dispatchEvent(new Event('input', { bubbles: true }));
  });
  await pg.waitForTimeout(150);
  let d = await pg.evaluate(() => window.__DATA__);
  console.log('虚像: v=' + d.v, 'm=' + d.magnification, d.image_type, d.screen_state);
  await shot('lens_virtual.png');

  // 2. u=f 不成像
  await pg.evaluate(() => {
    const rg = document.getElementById('rg-u');
    rg.value = '10'; rg.dispatchEvent(new Event('input', { bubbles: true }));
  });
  await pg.waitForTimeout(150);
  d = await pg.evaluate(() => window.__DATA__);
  console.log('不成像: v=' + d.v, d.image_type, d.screen_state);

  // 3. u 略大于 f：像超出量程
  await pg.evaluate(() => {
    const rg = document.getElementById('rg-u');
    rg.value = '11'; rg.dispatchEvent(new Event('input', { bubbles: true }));
  });
  await pg.waitForTimeout(150);
  d = await pg.evaluate(() => window.__DATA__);
  console.log('超量程: v=' + d.v, d.image_type, d.screen_state);
  await shot('lens_over.png');

  // 4. u=2f 等大
  await pg.evaluate(() => {
    const rg = document.getElementById('rg-u');
    rg.value = '20'; rg.dispatchEvent(new Event('input', { bubbles: true }));
    document.getElementById('btn-snap').click();
  });
  await pg.waitForTimeout(150);
  d = await pg.evaluate(() => window.__DATA__);
  console.log('等大: v=' + d.v, 'm=' + d.magnification, d.image_type, d.screen_state);
  await shot('lens_equal.png');

  // 5. 模糊状态：拖走光屏
  await pg.evaluate(() => {
    const rg = document.getElementById('rg-scr');
    rg.value = '70'; rg.dispatchEvent(new Event('input', { bubbles: true }));
  });
  await pg.waitForTimeout(150);
  d = await pg.evaluate(() => window.__DATA__);
  console.log('模糊: screen=' + d.screen_pos, d.screen_state);
  await shot('lens_blur.png');

  console.log('JS错误:', errs.length ? errs : '无');
  await b.close();
})();
