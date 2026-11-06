/**
 * Canvas 内文字审计：不需要页面配合，通过 initScript 拦截 2D 上下文调用。
 *
 * 抓三类问题：
 *  1. 覆盖：某个 fillText 之后，还有不透明填充覆盖了它 ≥35% 的面积（文字被图元盖上）
 *  2. 出界：文字包围盒超出画布可见区域（被裁掉）
 *  3. 叠字：两段文字包围盒互相重叠 ≥45%
 *
 * 用法：node tools/canvas_text_audit.js <页面.html> [--json]
 */
const path = require('path');
const { chromium } = require('playwright');

const EXEC = 'C:/Users/wangq/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe';

const HOOK = () => {
  const proto = CanvasRenderingContext2D.prototype;
  const state = { ops: [], seq: 0, texts: [], fills: [], frame: 0 };
  window.__CANVAS_AUDIT__ = state;

  const reset = () => { state.seq = 0; state.texts = []; state.fills = []; state.frame++; };

  const parseColorAlpha = (style, globalAlpha) => {
    if (typeof style !== 'string') return globalAlpha;
    let a = globalAlpha;
    let m = style.match(/rgba?\(([^)]+)\)/);
    if (m) {
      const parts = m[1].split(',').map(s => parseFloat(s));
      if (parts.length === 4) a *= parts[3];
    } else if (style.startsWith('#')) {
      const h = style.slice(1);
      if (h.length === 8) a *= parseInt(h.slice(6, 8), 16) / 255;
    }
    return a;
  };

  // 设计坐标 → 设备像素（页面常用 ctx.scale 把 880 设计宽缩到实际画布）
  const devBox = (ctx, x, y, w, h) => {
    const m = ctx.getTransform();
    const sx = Math.abs(m.a) || 1, sy = Math.abs(m.d) || 1;
    const px = m.a * x + m.c * y + m.e;
    const py = m.b * x + m.d * y + m.f;
    return { x: px, y: py, w: Math.abs(w * sx), h: Math.abs(h * sy) };
  };

  const pushFill = (bbox, ctx, kind) => {
    if (!bbox) return;
    const d = devBox(ctx, bbox.x, bbox.y, bbox.w, bbox.h);
    state.fills.push({
      kind, x: d.x, y: d.y, w: d.w, h: d.h,
      alpha: parseColorAlpha(ctx.fillStyle, ctx.globalAlpha),
      style: typeof ctx.fillStyle === 'string' ? ctx.fillStyle : 'gradient',
      order: state.seq++,
    });
  };

  // --- 路径包围盒累积 ---
  const origBeginPath = proto.beginPath;
  proto.beginPath = function (...a) {
    this.__bbox = null;
    return origBeginPath.apply(this, a);
  };
  const grow = (ctx, x, y) => {
    if (!isFinite(x) || !isFinite(y)) return;
    const b = ctx.__bbox;
    if (!b) ctx.__bbox = { x1: x, y1: y, x2: x, y2: y };
    else {
      b.x1 = Math.min(b.x1, x); b.y1 = Math.min(b.y1, y);
      b.x2 = Math.max(b.x2, x); b.y2 = Math.max(b.y2, y);
    }
  };
  const bboxOf = (ctx) => {
    const b = ctx.__bbox;
    if (!b) return null;
    return { x: b.x1, y: b.y1, w: b.x2 - b.x1, h: b.y2 - b.y1 };
  };

  for (const name of ['moveTo', 'lineTo', 'rect', 'roundRect', 'arc', 'ellipse', 'quadraticCurveTo', 'bezierCurveTo', 'arcTo']) {
    const orig = proto[name];
    proto[name] = function (...a) {
      if (name === 'rect' || name === 'roundRect') { grow(this, a[0], a[1]); grow(this, a[0] + a[2], a[1] + a[3]); }
      else if (name === 'arc' || name === 'ellipse') { grow(this, a[0] - a[2], a[1] - a[3]); grow(this, a[0] + a[2], a[1] + a[3]); }
      else if (name === 'arcTo') { grow(this, a[0], a[1]); grow(this, a[2], a[3]); }
      else { grow(this, a[0], a[1]); }
      return orig.apply(this, a);
    };
  }

  const origFill = proto.fill;
  proto.fill = function (...a) {
    pushFill(a.length ? { x: a[0], y: a[1], w: a[2], h: a[3] } : bboxOf(this), this, 'fill');
    return origFill.apply(this, a);
  };

  const origFillRect = proto.fillRect;
  proto.fillRect = function (x, y, w, h) {
    pushFill({ x, y, w, h }, this, 'fillRect');
    return origFillRect.call(this, x, y, w, h);
  };

  const origClear = proto.clearRect;
  proto.clearRect = function (x, y, w, h) {
    // 全清视为新一帧
    if (x <= 0 && y <= 0 && w >= this.canvas.width - 1) reset();
    return origClear.call(this, x, y, w, h);
  };

  // --- 文字记录 ---
  const origFillText = proto.fillText;
  proto.fillText = function (text, x, y, maxW) {
    try {
      const m = this.measureText(String(text));
      const fs = parseFloat(this.font.match(/(\d+(?:\.\d+)?)px/)?.[1] || '12');
      let w = m.width, h = fs * 1.15;
      const align = this.textAlign, baseline = this.textBaseline;
      let left = x;
      if (align === 'center') left = x - w / 2;
      else if (align === 'right' || align === 'end') left = x - w;
      let top = y - h * 0.78;
      if (baseline === 'middle') top = y - h / 2;
      else if (baseline === 'top' || baseline === 'hanging') top = y;
      else if (baseline === 'bottom' || baseline === 'ideographic') top = y - h;
      if (maxW && w > maxW) w = maxW;
      const d = devBox(this, left, top, w, h);
      state.texts.push({
        text: String(text).slice(0, 40), x: d.x, y: d.y, w: d.w, h: d.h,
        font: this.font, alpha: parseColorAlpha(this.fillStyle, this.globalAlpha),
        order: state.seq++,
        canvas: { w: this.canvas.width, h: this.canvas.height },
      });
    } catch (e) { /* 记录失败不影响页面 */ }
    return origFillText.call(this, text, x, y, maxW);
  };
};

(async () => {
  const args = process.argv.slice(2).filter(a => !a.startsWith('--'));
  const asJson = process.argv.includes('--json');
  const target = args[0];
  if (!target) { console.error('用法: node tools/canvas_text_audit.js <页面.html> [--json]'); process.exit(2); }

  const browser = await chromium.launch({ executablePath: EXEC });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await page.addInitScript(HOOK);
  const errors = [];
  page.on('pageerror', e => errors.push(String(e)));
  await page.goto('file:///' + encodeURI(path.resolve(target).replace(/\\/g, '/')), { waitUntil: 'load' });
  await page.waitForTimeout(900);

  // 在几种参数状态下各取一帧
  const states = [null, 'min', 'max'];
  const report = { page: path.basename(target), frames: [], errors };

  for (const st of states) {
    if (st) {
      await page.evaluate((mode) => {
        document.querySelectorAll('input[type=range]').forEach(el => {
          const a = parseFloat(el.min || '0'), b = parseFloat(el.max || '100');
          el.value = String(mode === 'min' ? a : b);
          el.dispatchEvent(new Event('input', { bubbles: true }));
        });
      }, st);
      await page.waitForTimeout(500);
    }
    const snap = await page.evaluate(() => {
      const s = window.__CANVAS_AUDIT__;
      return { texts: s.texts.slice(), fills: s.fills.slice(), frame: s.frame };
    });
    report.frames.push({ state: st || 'default', ...snap });
  }
  await browser.close();

  const inter = (a, b) => {
    const ix = Math.max(0, Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x));
    const iy = Math.max(0, Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y));
    return ix * iy;
  };

  let total = 0;
  const outFrames = [];
  for (const f of report.frames) {
    const covered = [], outOfBounds = [], collide = [];
    for (const t of f.texts) {
      const area = Math.max(1, t.w * t.h);
      // 1. 被后画的填充覆盖
      let worst = 0, by = null;
      for (const fl of f.fills) {
        if (fl.order <= t.order) continue;
        if (fl.alpha < 0.45) continue;
        const r = inter(t, fl) / area;
        if (r > worst) { worst = r; by = fl; }
      }
      if (worst >= 0.35) covered.push({ text: t.text, ratio: Math.round(worst * 100) + '%', by: by && by.kind + ' ' + by.style });
      // 2. 出界（画布坐标，允许 1px 误差）
      if (t.x < -1 || t.y < -1 || t.x + t.w > t.canvas.w + 1 || t.y + t.h > t.canvas.h + 1) {
        outOfBounds.push({ text: t.text, box: [Math.round(t.x), Math.round(t.y), Math.round(t.w), Math.round(t.h)], canvas: [t.canvas.w, t.canvas.h] });
      }
    }
    // 3. 文字互相重叠
    for (let i = 0; i < f.texts.length; i++) {
      for (let j = i + 1; j < f.texts.length; j++) {
        const a = f.texts[i], b = f.texts[j];
        if (a.text === b.text) continue;
        const r = inter(a, b) / Math.min(a.w * a.h, b.w * b.h);
        if (r >= 0.45) collide.push({ a: a.text, b: b.text, ratio: Math.round(r * 100) + '%' });
      }
    }
    total += covered.length + outOfBounds.length;
    outFrames.push({ state: f.state, textCount: f.texts.length, covered, outOfBounds, collide });
  }

  if (asJson) console.log(JSON.stringify({ page: report.page, frames: outFrames, errors: report.errors }, null, 1));
  else {
    console.log('页面：' + report.page);
    for (const f of outFrames) {
      console.log('\n[' + f.state + '] 画布文字 ' + f.textCount + ' 段，覆盖 ' + f.covered.length +
        ' 处，出界 ' + f.outOfBounds.length + ' 处，叠字 ' + f.collide.length + ' 处');
      f.covered.forEach(c => console.log('  ✗ 覆盖「' + c.text + '」 ' + c.ratio + ' ← ' + c.by));
      f.outOfBounds.forEach(c => console.log('  ✗ 出界「' + c.text + '」 box=' + c.box.join(',') + ' canvas=' + c.canvas.join(',')));
      f.collide.slice(0, 8).forEach(c => console.log('  · 叠字「' + c.a + '」×「' + c.b + '」 ' + c.ratio));
    }
    if (report.errors.length) console.log('\nJS 错误：' + report.errors.join(' | '));
    console.log('\n严重问题合计（覆盖+出界）：' + total);
  }
  process.exit(total > 0 ? 1 : 0);
})();
