/* 逐帧差分：定位「闪动」发生在画面哪个区域、变化幅度多大 */
const home = process.env.HOME || process.env.USERPROFILE || '';
[require('path').join(home, '.workbuddy/binaries/node/workspace/node_modules')].forEach(p => {
  if (!module.paths.includes(p)) module.paths.push(p);
});
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');
const CHROME = 'C:/Users/wangq/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe';

(async () => {
  const dir = process.argv[2];
  const files = fs.readdirSync(dir).filter(f => /\.png$/i.test(f)).sort();
  const imgs = files.map(f => ({ n: f, b64: fs.readFileSync(path.join(dir, f)).toString('base64') }));
  const b = await chromium.launch({ executablePath: CHROME });
  const p = await b.newPage({ viewport: { width: 1200, height: 800 } });
  await p.goto('about:blank');

  const res = await p.evaluate(async (imgs) => {
    async function load(b64) {
      const im = new Image(); im.src = 'data:image/png;base64,' + b64; await im.decode();
      const c = document.createElement('canvas');
      c.width = im.width; c.height = im.height;
      const g = c.getContext('2d'); g.drawImage(im, 0, 0);
      return g.getImageData(0, 0, c.width, c.height);
    }
    const frames = [];
    for (const o of imgs) frames.push({ n: o.n, d: await load(o.b64) });
    const W = frames[0].d.width, H = frames[0].d.height;
    const out = [];
    // 把画面切成 12 列 x 8 行，统计每格的平均变化，便于定位闪动区域
    const CX = 12, CY = 8;
    for (let i = 1; i < frames.length; i++) {
      const A = frames[i - 1].d.data, B = frames[i].d.data;
      let diff = 0;
      const grid = Array.from({ length: CY }, () => new Array(CX).fill(0));
      const cnt = Array.from({ length: CY }, () => new Array(CX).fill(0));
      // 每 4 个像素采一个，够统计且快
      for (let y = 0; y < H; y += 2) {
        for (let x = 0; x < W; x += 2) {
          const idx = (y * W + x) * 4;
          const dr = Math.abs(A[idx] - B[idx]);
          const dg = Math.abs(A[idx + 1] - B[idx + 1]);
          const db = Math.abs(A[idx + 2] - B[idx + 2]);
          const ch = (dr + dg + db) / 3;
          const gy = Math.min(CY - 1, Math.floor(y / H * CY));
          const gx = Math.min(CX - 1, Math.floor(x / W * CX));
          grid[gy][gx] += ch; cnt[gy][gx]++;
          if (ch > 18) diff++;
        }
      }
      const cells = grid.map((row, gy) => row.map((v, gx) => Math.round(v / Math.max(1, cnt[gy][gx]))));
      out.push({
        帧对: frames[i - 1].n + ' → ' + frames[i].n,
        变化像素占比: +(diff / (W * H / 4) * 100).toFixed(1),
        格子均值: cells
      });
    }
    return { W, H, out };
  }, imgs);

  console.log('原始分辨率', res.W + 'x' + res.H);
  console.log('\n逐帧变化占比：');
  res.out.forEach(o => {
    const bar = '█'.repeat(Math.min(40, Math.round(o.变化像素占比 / 2)));
    console.log(o.帧对.padEnd(32), String(o.变化像素占比).padStart(5) + '%  ' + bar);
  });
  // 找出变化最猛的 3 对，打印它的网格热力图
  const top = res.out.slice().sort((a, b) => b.变化像素占比 - a.变化像素占比).slice(0, 3);
  top.forEach(o => {
    console.log('\n【变化最猛】' + o.帧对 + '  区域热力图（数字=平均色差 0~255）');
    o.格子均值.forEach(row => console.log('  ' + row.map(v => String(v).padStart(4)).join('')));
  });
  await b.close();
})();
