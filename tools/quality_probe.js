// 质感探针 v2：把「2.5D 实验室标准」量成可对照的分项指标
// 用法：node quality_probe.js <页面.html> [--base] [--json]
//   --base 以“基准模式”输出（只打印分项，供人工设阈值）
// 指标全部是帧内比率，动画循环多帧不会把数字冲淡
const { chromium } = require('playwright');
const { pathToFileURL } = require('url');

// 阈值：从已验收的化学双烧杯页反推，再留 15% 余量
const STD = {
  grad: 0.085,   // 渐变填充占比（玻璃/液体/金属的立体感来源）
  alpha: 0.055,  // 半透明叠层占比（玻璃质感）
  solid: 0.10,   // 立体件密度：径向渐变 + 椭圆 + 柔光阴影 / 填充数
  curve: 0.55,   // 曲线占比（圆角、弯月面、弧线；扁平矩形堆砌会很低）
  color: 22,     // 色彩种类（24 色以下容易显灰）
  flat: 0.06,    // 扁平色块占比，越小越好
};

const INSTRUMENT = () => {
  const P = CanvasRenderingContext2D.prototype;
  const boxes = new WeakMap();
  window.__FRAMES__ = 0;
  const _raf = window.requestAnimationFrame.bind(window);
  window.requestAnimationFrame = cb => _raf(t => { window.__FRAMES__++; return cb(t); });

  const rec = c => {
    let o = boxes.get(c);
    if (o) return o;
    o = {
      w: c.canvas.width, h: c.canvas.height,
      fills: 0, gradFills: 0, alphaFills: 0, flatBlocks: 0,
      strokes: 0, blur: 0, radial: 0, ellipse: 0,
      curves: 0, rectOps: 0, text: 0, colors: {}, path: []
    };
    boxes.set(c, o);
    (window.__Q__ = window.__Q__ || []).push(o);
    return o;
  };
  const bboxArea = p => {
    if (!p.length) return 0;
    const xs = p.map(q => q.x), ys = p.map(q => q.y);
    return (Math.max(...xs) - Math.min(...xs)) * (Math.max(...ys) - Math.min(...ys));
  };
  const wrap = (name, fn) => {
    const orig = P[name];
    P[name] = function (...a) { try { fn(rec(this), this, a); } catch (e) { } return orig.apply(this, a); };
  };
  // kind: 'f' 填充 / 's' 描边 —— 分子分母必须同源，否则比率会超过 100%
  const track = (o, v, kind) => {
    const k = kind === 's' ? 'Stroke' : '';
    if (typeof v === 'object') o['grad' + (k || 'Fills')] = (o['grad' + (k || 'Fills')] || 0) + 1;
    else {
      const s = String(v);
      o.colors[s] = (o.colors[s] || 0) + 1;
      if (/rgba\([^)]*,\s*0?\.\d+\)/.test(s)) o['alpha' + (k || 'Fills')] = (o['alpha' + (k || 'Fills')] || 0) + 1;
    }
  };

  wrap('beginPath', o => { o.path = []; });
  wrap('rect', (o, c, a) => { o.path.push({ t: 'r', x: a[0], y: a[1] }); o.rectOps++; });
  wrap('fillRect', (o, c, a) => {
    o.fills++; o.rectOps++; o.path = [];
    track(o, c.fillStyle, 'f');
    // 大块纯色矩形 = 扁平色块
    if (typeof c.fillStyle !== 'object' && a[2] * a[3] > 6000) o.flatBlocks++;
  });
  wrap('strokeRect', o => { o.strokes++; o.rectOps++; });
  wrap('moveTo', (o, c, a) => { o.path.push({ t: 'm', x: a[0], y: a[1] }); });
  wrap('lineTo', (o, c, a) => { o.path.push({ t: 'l', x: a[0], y: a[1] }); });
  wrap('arc', (o, c, a) => { o.path.push({ t: 'a', x: a[0], y: a[1] }); o.curves++; });
  wrap('ellipse', (o, c, a) => { o.path.push({ t: 'e', x: a[0], y: a[1] }); o.curves++; o.ellipse++; });
  wrap('quadraticCurveTo', (o, c, a) => { o.path.push({ t: 'q', x: a[2], y: a[3] }); o.curves++; });
  wrap('bezierCurveTo', (o, c, a) => { o.path.push({ t: 'b', x: a[4], y: a[5] }); o.curves++; });
  wrap('fill', (o, c) => {
    o.fills++;
    track(o, c.fillStyle, 'f');
    const onlyRects = o.path.length && o.path.every(q => q.t === 'r' || q.t === 'l' || q.t === 'm');
    if (typeof c.fillStyle !== 'object' && onlyRects && bboxArea(o.path) > 6000) o.flatBlocks++;
    o.path = [];
  });
  wrap('stroke', (o, c) => { o.strokes++; track(o, c.strokeStyle, 's'); o.path = []; });
  wrap('fillText', o => { o.text++; });
  wrap('strokeText', o => { o.text++; });
  wrap('createRadialGradient', o => { o.radial++; });

  // 柔光阴影：ctx.shadowBlur 与径向渐变都算（本项目的 VIS.shadow 走径向渐变）
  ['fill', 'stroke', 'fillRect', 'fillText'].forEach(n => {
    const orig = P[n];
    P[n] = function (...a) {
      try { if (this.shadowBlur > 0) rec(this).blur++; } catch (e) { }
      return orig.apply(this, a);
    };
  });
};

(async () => {
  const file = process.argv[2];
  if (!file) { console.error('用法: node quality_probe.js <页面.html> [--json]'); process.exit(1); }
  const b = await chromium.launch({
    executablePath: 'C:/Users/wangq/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe'
  });
  const p = await b.newPage({ viewport: { width: 1200, height: 900 } });
  const errs = [];
  p.on('pageerror', e => errs.push(String(e)));
  await p.addInitScript(INSTRUMENT);
  await p.goto(pathToFileURL(file).href, { waitUntil: 'load' });
  await p.waitForTimeout(600);
  await p.evaluate(() => {
    const s = document.querySelector('input[type=range]');
    if (s) { s.value = String((+s.value + +s.max) / 2); s.dispatchEvent(new Event('input', { bubbles: true })); }
  });
  await p.waitForTimeout(900);

  const out = await p.evaluate(() => {
    const frames = Math.max(1, window.__FRAMES__);
    return {
      frames,
      list: (window.__Q__ || []).map(o => ({
        w: o.w, h: o.h, fills: o.fills, gradFills: o.gradFills, alphaFills: o.alphaFills,
        flatBlocks: o.flatBlocks, strokes: o.strokes, blur: o.blur, radial: o.radial,
        ellipse: o.ellipse, curves: o.curves, rectOps: o.rectOps, text: o.text,
        colors: Object.keys(o.colors).length
      }))
    };
  });

  const rows = out.list.filter(o => o.fills + o.strokes > 20).map(o => {
    const f = o.fills || 1, t = o.fills + o.strokes;
    const m = {
      grad: o.gradFills / f,
      alpha: o.alphaFills / f,
      solid: (o.radial + o.ellipse + o.blur) / f,
      curve: o.curves / (o.curves + o.rectOps || 1),
      color: o.colors,
      flat: o.flatBlocks / f
    };
    const hit = [
      Math.min(1, m.grad / STD.grad),
      Math.min(1, m.alpha / STD.alpha),
      Math.min(1, m.solid / STD.solid),
      Math.min(1, m.curve / STD.curve),
      Math.min(1, m.color / STD.color),
      1 - Math.min(1, m.flat / STD.flat)
    ];
    return { ...o, m, draw: t, perFrame: +(t / out.frames).toFixed(1), score: Math.round(100 * hit.reduce((a, c) => a + c, 0) / hit.length) };
  });

  const best = rows.sort((a, b) => b.draw - a.draw)[0];
  const name = file.split(/[\\/]/).pop();
  if (!best) { console.log(name, '未捕获到绘制', JSON.stringify(errs.slice(0, 2))); await b.close(); return; }

  const pct = x => (x * 100).toFixed(1).padStart(5) + '%';
  const ok = (x, th) => x >= th ? '达标' : '偏低';
  console.log('【' + name + '】  画布 ' + best.w + '×' + best.h + ' · 帧数 ' + out.frames + ' · 每帧绘制 ' + best.perFrame + ' 次');
  console.log('  渐变填充  ' + pct(best.m.grad) + '  (标准 ≥' + (STD.grad * 100) + '%)  ' + ok(best.m.grad, STD.grad));
  console.log('  半透明叠层 ' + pct(best.m.alpha) + '  (标准 ≥' + (STD.alpha * 100) + '%)  ' + ok(best.m.alpha, STD.alpha));
  console.log('  立体件密度 ' + pct(best.m.solid) + '  (标准 ≥' + (STD.solid * 100) + '%)  ' + ok(best.m.solid, STD.solid) + '   径向渐变 ' + best.radial + ' · 椭圆 ' + best.ellipse + ' · 柔光 ' + best.blur);
  console.log('  曲线占比  ' + pct(best.m.curve) + '  (标准 ≥' + (STD.curve * 100) + '%)  ' + ok(best.m.curve, STD.curve));
  console.log('  色彩种类  ' + String(best.m.color).padStart(5) + '   (标准 ≥' + STD.color + ')      ' + (best.m.color >= STD.color ? '达标' : '偏低'));
  console.log('  扁平色块  ' + pct(best.m.flat) + '  (标准 ≤' + (STD.flat * 100) + '%)  ' + (best.m.flat <= STD.flat ? '达标' : '偏多'));
  console.log('  >>> 质感分 ' + best.score + ' / 100');
  if (errs.length) console.log('  errs ' + JSON.stringify(errs.slice(0, 3)));
  if (process.argv.includes('--json')) console.log(JSON.stringify(rows, null, 1));
  await b.close();
})();
