/* 化学场景版式体检：拦截 fillText，记录每一次文字绘制的实际包围盒，
 * 判定：① 是否溢出画布；② 两个文字块是否互相重叠（压字）。
 *
 * 用法：node tools/chem_label_audit.js <页面或测试html>
 *
 * 为什么不用肉眼看截图：截图只有一张，而这类版式问题是「同一套代码在不同
 * 画布尺寸下漂移」，必须量出数值才能一次覆盖所有化学页。
 */
const path = require('path');
const home = process.env.USERPROFILE || process.env.HOME || '';
['.workbuddy/binaries/node/workspace/node_modules'].forEach(p => {
  const q = path.join(home, p);
  if (!module.paths.includes(q)) module.paths.push(q);
});
const { chromium } = require('playwright');
const { pathToFileURL } = require('url');

const HOOK = () => {
  window.__TEXTBOXES__ = [];
  const proto = CanvasRenderingContext2D.prototype;
  const orig = proto.fillText;
  proto.fillText = function (text, x, y) {
    try {
      const m = this.measureText(String(text));
      const cw = m.width;
      const fs = parseFloat((this.font.match(/(\d+(?:\.\d+)?)px/) || [0, 12])[1]);
      // 用当前变换矩阵把设计坐标映射到 canvas 像素
      const t = this.getTransform();
      const sx = t.a * x + t.c * y + t.e;
      const sy = t.b * x + t.d * y + t.f;
      const sc = Math.hypot(t.a, t.b);
      const wpx = cw * sc, hpx = fs * sc;
      const align = this.textAlign;
      let left = sx;
      if (align === 'center') left = sx - wpx / 2;
      else if (align === 'right' || align === 'end') left = sx - wpx;
      const base = this.textBaseline;
      let top = sy - hpx * 0.5;
      if (base === 'top' || base === 'hanging') top = sy;
      else if (base === 'bottom' || base === 'alphabetic' || base === 'ideographic') top = sy - hpx;
      window.__TEXTBOXES__.push({
        s: String(text), left: +left.toFixed(1), top: +top.toFixed(1),
        w: +wpx.toFixed(1), h: +hpx.toFixed(1), fs: +(fs * sc).toFixed(1)
      });
    } catch (e) { }
    return orig.apply(this, arguments);
  };
};

(async () => {
  const file = process.argv[2];
  const b = await chromium.launch({
    executablePath: 'C:/Users/wangq/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe'
  });
  const p = await b.newPage({ viewport: { width: 1500, height: 1000 } });
  const errs = [];
  p.on('pageerror', e => errs.push(e.message));
  await p.addInitScript(HOOK);
  await p.goto(pathToFileURL(path.resolve(file)).href);
  await p.waitForTimeout(1300);

  const r = await p.evaluate(() => {
    const cv = document.querySelector('canvas');
    const boxes = window.__TEXTBOXES__ || [];
    // 只保留最后一次绘制产生的文字（重绘会累积）
    const last = [];
    const seen = new Set();
    for (let i = boxes.length - 1; i >= 0; i--) {
      const k = boxes[i].s + '@' + boxes[i].left + ',' + boxes[i].top;
      if (seen.has(k)) continue;
      seen.add(k);
      last.push(boxes[i]);
      if (last.length > 40) break;
    }
    return last.reverse();
  });

  const cw = await p.evaluate(() => {
    const cv = document.querySelector('canvas');
    return { w: cv.clientWidth, h: cv.clientHeight };
  });

  console.log('画布', JSON.stringify(cw), '文字块', r.length, 'pageErrors', JSON.stringify(errs));

  const out = [];   // 溢出
  const ov = [];    // 压字
  const inside = r.filter(t => t.top > -2 && t.top < cw.h - 2 && t.left > -2 && t.left < cw.w - 2);
  inside.forEach(t => {
    if (t.left < 2 || t.top < 2 || t.left + t.w > cw.w - 2 || t.top + t.h > cw.h - 2) {
      out.push(t);
    }
  });
  for (let i = 0; i < inside.length; i++) {
    for (let j = i + 1; j < inside.length; j++) {
      const a = inside[i], c2 = inside[j];
      const ow = Math.min(a.left + a.w, c2.left + c2.w) - Math.max(a.left, c2.left);
      const oh = Math.min(a.top + a.h, c2.top + c2.h) - Math.max(a.top, c2.top);
      if (ow > 4 && oh > 4) {
        const area = ow * oh;
        const ratio = area / Math.min(a.w * a.h, c2.w * c2.h);
        if (ratio > 0.18) ov.push({ a: a.s, b: c2.s, ratio: +ratio.toFixed(2) });
      }
    }
  }

  console.log('\n--- 溢出画布 ---');
  if (!out.length) console.log('  无');
  out.forEach(t => console.log(`  「${t.s}」 框=${t.left},${t.top} ${t.w}x${t.h} 字号=${t.fs}`));

  console.log('\n--- 文字块互相压字 ---');
  if (!ov.length) console.log('  无');
  ov.forEach(o => console.log(`  「${o.a}」 × 「${o.b}」 重叠 ${(o.ratio * 100).toFixed(0)}%`));

  console.log('\n--- 超出画布的文字 ---');
  const far = r.filter(t => t.top < -2 || t.top > cw.h - 2 || t.left < -2 || t.left > cw.w - 2);
  if (!far.length) console.log('  无');
  far.forEach(t => console.log(`  「${t.s}」 框=${t.left},${t.top} 字号=${t.fs}`));

  await b.close();
})();
