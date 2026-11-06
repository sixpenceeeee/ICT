/* 把一批帧拼成一张接触表（浏览器 canvas 合成，避免引入图像库） */
const home = process.env.HOME || process.env.USERPROFILE || '';
[require('path').join(home, '.workbuddy/binaries/node/workspace/node_modules')].forEach(p => {
  if (!module.paths.includes(p)) module.paths.push(p);
});
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');
const CHROME = 'C:/Users/wangq/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe';

const dir = process.argv[2];
const out = process.argv[3];
const cols = +(process.argv[4] || 5);
const cw = +(process.argv[5] || 520);

(async () => {
  const files = fs.readdirSync(dir).filter(f => /\.png$/i.test(f)).sort();
  const imgs = files.map(f => ({
    name: f, b64: fs.readFileSync(path.join(dir, f)).toString('base64')
  }));
  const b = await chromium.launch({ executablePath: CHROME });
  const p = await b.newPage({ viewport: { width: 1200, height: 800 } });
  await p.goto('about:blank');
  const data = await p.evaluate(async ([imgs, cols, cw]) => {
    async function load(b64) {
      const im = new Image(); im.src = 'data:image/png;base64,' + b64; await im.decode();
      return im;
    }
    const loaded = [];
    for (const o of imgs) loaded.push({ n: o.name, im: await load(o.b64) });
    const rows = Math.ceil(loaded.length / cols);
    const rh = Math.round(cw * loaded[0].im.height / loaded[0].im.width);
    const LABEL = 26;
    const c = document.createElement('canvas');
    c.width = cols * cw; c.height = rows * (rh + LABEL);
    const g = c.getContext('2d');
    g.fillStyle = '#111'; g.fillRect(0, 0, c.width, c.height);
    loaded.forEach((o, i) => {
      const cx = (i % cols) * cw, cy = Math.floor(i / cols) * (rh + LABEL);
      g.drawImage(o.im, cx, cy + LABEL, cw, rh);
      g.fillStyle = '#ffd400'; g.font = 'bold 20px sans-serif'; g.textBaseline = 'top';
      g.fillText(o.n.replace('.png', ''), cx + 6, cy + 3);
      g.strokeStyle = '#444'; g.lineWidth = 1;
      g.strokeRect(cx, cy + LABEL, cw, rh);
    });
    return c.toDataURL('image/png');
  }, [imgs, cols, cw]);
  fs.writeFileSync(out, Buffer.from(data.split(',')[1], 'base64'));
  console.log('接触表已生成:', out, files.length, '帧');
  await b.close();
})();
