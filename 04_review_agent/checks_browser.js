/**
 * checks_browser.js —— 第四关「浏览器测试」的取证脚本
 *
 * 规范（《界面设计+审查判据》3.4 第4关）要求：加载、点击、参数变化、重置、离线运行。
 * 所以这里不只是"能打开"，还要真的：
 *   1. 记录六个区域是否渲染出内容
 *   2. 抓 window.__DATA__ / __GEO__（第三关 J1–J8 的独立复算原料）
 *   3. 拖滑块到极值，看读数/图像/代入式是否跟着变
 *   4. 点「重置」，比对是否回到与首屏一致的状态（规范 2.3 必做项）
 *   5. 点「单步/下一步」，看状态序列是否卡住
 *   6. 点「记录」，看表格是否真的追加行
 *   7. 统计运行时有没有 file:// 之外的请求（离线运行）
 *
 * 用法：node checks_browser.js <html路径>
 * 输出：一行 JSON（stdout），供 Python 侧解析
 */

const { chromium } = require('playwright');
const { pathToFileURL } = require('url');

const FILE = process.argv[2];

/**
 * 画布绘制取证：记录文字、填充和矩形描边的设备像素包围盒。
 * 除了后绘制填充遮字，也检查文字是否撞到卡片边框或另一段文字。
 */
const CANVAS_HOOK = () => {
  const proto = CanvasRenderingContext2D.prototype;
  const st = { seq: 0, texts: [], fills: [], strokes: [], frames: [] };
  // 质感取证：只记帧内比率，动画多帧不会把数字冲淡
  st.q = { fills: 0, grad: 0, alpha: 0, flat: 0, rect: 0, curve: 0, radial: 0, ellipse: 0, blur: 0 };
  window.__CANVAS_AUDIT__ = st;

  const alphaOf = (style, ga) => {
    let a = ga;
    if (typeof style === 'string') {
      const m = style.match(/rgba?\(([^)]+)\)/);
      if (m) {
        const p = m[1].split(',').map(parseFloat);
        if (p.length === 4) a *= p[3];
      } else if (style.startsWith('#') && style.length === 9) {
        a *= parseInt(style.slice(7, 9), 16) / 255;
      }
    }
    return a;
  };

  // 被隐藏的画布（例如被库兜底接管后留在 DOM 里的旧渲染层）学生看不见，
  // 它的文字和填充不参与取证，否则会把「页面上根本看不到」的字判成被遮挡。
  const shown = c => !(c && c.style && c.style.display === 'none');

  const dev = (ctx, x, y, w, h) => {
    const m = ctx.getTransform();
    return {
      x: m.a * x + m.c * y + m.e,
      y: m.b * x + m.d * y + m.f,
      w: Math.abs(w * (Math.abs(m.a) || 1)),
      h: Math.abs(h * (Math.abs(m.d) || 1)),
    };
  };

  const origBegin = proto.beginPath;
  proto.beginPath = function (...a) { this.__bb = null; return origBegin.apply(this, a); };
  const grow = (ctx, x, y) => {
    if (!isFinite(x) || !isFinite(y)) return;
    const b = ctx.__bb;
    if (!b) ctx.__bb = { x1: x, y1: y, x2: x, y2: y };
    else {
      b.x1 = Math.min(b.x1, x); b.y1 = Math.min(b.y1, y);
      b.x2 = Math.max(b.x2, x); b.y2 = Math.max(b.y2, y);
    }
  };
  ['moveTo', 'lineTo', 'rect', 'roundRect', 'arc', 'ellipse', 'quadraticCurveTo', 'bezierCurveTo', 'arcTo']
    .forEach(name => {
      const orig = proto[name];
      proto[name] = function (...a) {
        try {
          if (!shown(this.canvas)) return orig.apply(this, a);
          if (name === 'arc' || name === 'ellipse' || name === 'quadraticCurveTo' || name === 'bezierCurveTo' || name === 'arcTo') st.q.curve++;
          if (name === 'rect' || name === 'roundRect') st.q.rect++;
          if (name === 'ellipse') st.q.ellipse++;
        } catch (e) { }
        if (name === 'rect' || name === 'roundRect') { grow(this, a[0], a[1]); grow(this, a[0] + a[2], a[1] + a[3]); }
        else if (name === 'arc' || name === 'ellipse') { grow(this, a[0] - a[2], a[1] - a[3]); grow(this, a[0] + a[2], a[1] + a[3]); }
        else if (name === 'arcTo') { grow(this, a[0], a[1]); grow(this, a[2], a[3]); }
        else grow(this, a[0], a[1]);
        return orig.apply(this, a);
      };
    });

  const push = (ctx, box, kind) => {
    if (!box) return;
    if (!shown(ctx.canvas)) return;
    try {
      const q = st.q, solid = typeof ctx.fillStyle !== 'object';
      const a = alphaOf(ctx.fillStyle, ctx.globalAlpha);
      q.fills++;
      if (!solid) q.grad++;
      if (a < 0.92) q.alpha++;
      if (solid && a >= 0.92 && box.w * box.h > 6000 && (kind === 'fillRect' || kind === 'fill')) q.flat++;
      if (ctx.shadowBlur > 0) q.blur++;
    } catch (e) { }
    const d = dev(ctx, box.x, box.y, box.w, box.h);
    st.fills.push({ kind, ...d, alpha: alphaOf(ctx.fillStyle, ctx.globalAlpha), order: st.seq++ });
  };
  const origFill = proto.fill;
  proto.fill = function (...a) {
    if (a.length) push(this, { x: a[0], y: a[1], w: a[2], h: a[3] }, 'fill');
    else if (this.__bb) {
      const b = this.__bb;
      push(this, { x: b.x1, y: b.y1, w: b.x2 - b.x1, h: b.y2 - b.y1 }, 'fill');
    }
    return origFill.apply(this, a);
  };
  const origFR = proto.fillRect;
  proto.fillRect = function (x, y, w, h) {
    try { st.q.rect++; } catch (e) { }
    push(this, { x, y, w, h }, 'fillRect');
    return origFR.call(this, x, y, w, h);
  };
  const origSR = proto.strokeRect;
  proto.strokeRect = function (x, y, w, h) {
    try { st.q.rect++; } catch (e) { }
    if (shown(this.canvas)) {
      const d = dev(this, x, y, w, h);
      const m = this.getTransform();
      st.strokes.push({ ...d, lineWidth: this.lineWidth * Math.max(Math.abs(m.a), Math.abs(m.d)), order: st.seq++ });
    }
    return origSR.call(this, x, y, w, h);
  };

  // 柔光阴影两种画法都算：ctx.shadowBlur 与径向渐变（vis.js 的 VIS.shadow 走后者）
  const origRG = proto.createRadialGradient;
  proto.createRadialGradient = function (...a) {
    try { st.q.radial++; } catch (e) { }
    return origRG.apply(this, a);
  };

  const origClear = proto.clearRect;
  proto.clearRect = function (x, y, w, h) {
    // 整帧重绘前归档上一帧，保留最近 12 帧（动画中只有部分帧会暴露遮挡）
    if (x <= 0 && y <= 0 && w >= this.canvas.width - 1) {
      if (st.texts.length) {
        st.frames.push({ texts: st.texts.slice(), fills: st.fills.slice(), strokes: st.strokes.slice() });
        if (st.frames.length > 12) st.frames.shift();
      }
      st.seq = 0; st.texts = []; st.fills = []; st.strokes = [];
    }
    return origClear.call(this, x, y, w, h);
  };

  const origText = proto.fillText;
  proto.fillText = function (text, x, y, maxW) {
    if (!shown(this.canvas)) return origText.call(this, text, x, y, maxW);
    try {
      const mt = this.measureText(String(text));
      const fs = parseFloat((this.font.match(/(\d+(?:\.\d+)?)px/) || [0, 12])[1]);
      let w = mt.width, h = fs * 1.15;
      let left = x;
      if (this.textAlign === 'center') left = x - w / 2;
      else if (this.textAlign === 'right' || this.textAlign === 'end') left = x - w;
      let top = y - h * 0.78;
      if (this.textBaseline === 'middle') top = y - h / 2;
      else if (this.textBaseline === 'top' || this.textBaseline === 'hanging') top = y;
      else if (this.textBaseline === 'bottom' || this.textBaseline === 'ideographic') top = y - h;
      if (maxW && w > maxW) w = maxW;
      const d = dev(this, left, top, w, h);
      st.texts.push({
        text: String(text).slice(0, 40), ...d, order: st.seq++,
        canvas: { w: this.canvas.width, h: this.canvas.height },
      });
    } catch (e) { /* 取证失败不影响页面 */ }
    return origText.call(this, text, x, y, maxW);
  };
};

const SECTION_DEFS = [
  ['sec-info', 'exp-info', '① 实验信息'],
  ['sec-stage', 'exp-stage', '② 实验演示'],
  ['sec-control', 'exp-control', '③ 参数与操作'],
  ['sec-result', 'exp-result', '④ 结果与反馈'],
  ['sec-record', 'exp-record', '⑤ 实验记录'],
  ['sec-teach', 'exp-teach', '⑥ 教学说明'],
];

async function main() {
  const result = {
    ok: false,
    errors: [],
    network: [],
    loadMs: 0,
    canvas: [],
    ranges: { count: 0, responsive: 0, details: [], bounds: [] },
    selects: { count: 0, responsive: 0, details: [] },
    visualType: '',
    viewReset: { applicable: false, rotated: false, restored: false },
    stageImages: [],
    stageBadText: [],
    chemScene: null,
    layout: { viewports: [], unlabeled: [] },
    buttons: 0,
    buttonsClicked: [],
    sections: [],
    machine: { has: false },
    circuit: { initial: null, samples: [] },
    reset: { found: false, restored: null, textDiff: 0, dataDiff: false },
    steps: { found: false, count: 0, stuck: 0, sequence: [] },
    records: { before: 0, after: 0, added: 0 },
    csv: { found: false },
    formula: { found: false, checks: [] },
    tables: [],
    textOverlap: {
      canvas: { textCount: 0, covered: [], outOfBounds: [], borderOverlap: [], textOverlaps: [], badText: [], worst: 0 },
      dom: { checked: 0, issues: [] },
      viewports: [],
    },
  };

  const browser = await chromium.launch({
    executablePath: process.env.CHROME_PATH || undefined,
  });
  const context = await browser.newContext({ viewport: { width: 1366, height: 900 }, acceptDownloads: true });
  await context.addInitScript(CANVAS_HOOK);
  const page = await context.newPage();

  page.on('pageerror', e => result.errors.push('页面异常: ' + e.message));
  page.on('console', m => {
    if (m.type() === 'error') result.errors.push('控制台报错: ' + m.text());
  });
  // 离线运行：file:// 之外的一切请求都记下来（CDN、字体、接口、埋点）
  page.on('request', r => {
    const u = r.url();
    if (!/^(file|data|blob|about):/i.test(u)) result.network.push(u.slice(0, 160));
  });

  const t0 = Date.now();
  await page.goto(pathToFileURL(FILE).href, { waitUntil: 'load' });
  result.loadMs = Date.now() - t0;
  await page.waitForTimeout(400);
  result.ok = true;
  const captureCircuit = async label => {
    const state = await page.evaluate(() => {
      const clone = v => { try { return JSON.parse(JSON.stringify(v)); } catch (e) { return null; } };
      const readings = Array.from(document.querySelectorAll('[data-circuit-current-for], [data-circuit-voltage-for]')).map(el => ({
        kind: el.hasAttribute('data-circuit-current-for') ? 'current' : 'voltage',
        component: el.getAttribute('data-circuit-current-for') || el.getAttribute('data-circuit-voltage-for') || '',
        text: (el.textContent || '').trim(), value: parseFloat((el.textContent || '').replace(/,/g, '')),
        bound: el.getAttribute('data-circuit-bound') === 'true'
      }));
      return { model: clone(window.__CIRCUIT_MODEL__), result: clone(window.__CIRCUIT_RESULT__), readings,
        diagramSignature: window.__CIRCUIT_DRAW_SIGNATURE__ || null };
    });
    if (state.model && state.result) result.circuit.samples.push({ label, ...state });
    return state.model && state.result ? state : null;
  };
  result.circuit.initial = await captureCircuit('initial');

  result.stageImages = await page.evaluate(() => {
    const stage = document.getElementById('sec-stage');
    if (!stage) return [];
    const nodes = [stage, ...stage.querySelectorAll('*')];
    return nodes.filter(el => {
      if (el.tagName === 'IMG' || (el.tagName === 'IMAGE' && el.namespaceURI === 'http://www.w3.org/2000/svg')) return true;
      return /url\s*\(/i.test(getComputedStyle(el).backgroundImage || '');
    }).slice(0, 12).map(el => ({ tag: el.tagName.toLowerCase(), id: el.id || '', background: getComputedStyle(el).backgroundImage.slice(0, 120) }));
  });
  result.stageBadText = await page.evaluate(() => {
    const stage = document.getElementById('sec-stage');
    if (!stage) return [];
    return [...stage.querySelectorAll('*')].filter(el => /\[object\s+(?:Object|[A-Za-z_$][\w$]*)\]/.test(el.textContent || ''))
      .slice(0, 8).map(el => ({ tag: el.tagName.toLowerCase(), text: (el.textContent || '').trim().slice(0, 100) }));
  });
  result.chemScene = await page.evaluate(() => window.__CHEM_SCENE_STATE__ || null);

  // ---- 文字可读性取证（画布内 + DOM 层） ----
  // 画布：后绘制的图元盖住先绘制的文字 = 文字被图像遮住；文字盒超出画布 = 被裁切。
  const scanCanvasText = () => page.evaluate(() => {
    const s = window.__CANVAS_AUDIT__;
    if (!s) return { textCount: 0, covered: [], outOfBounds: [], borderOverlap: [], textOverlaps: [], badText: [] };
    const inter = (a, b) => {
      const ix = Math.max(0, Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x));
      const iy = Math.max(0, Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y));
      return ix * iy;
    };
    const covered = [], outOfBounds = [], borderOverlap = [], textOverlaps = [], badText = [];
    const seen = new Set();
    let textCount = 0;
    // 历史帧 + 当前帧一起看，取每段文字出现过的最严重情况
    const frames = (s.frames || []).concat([{ texts: s.texts || [], fills: s.fills || [], strokes: s.strokes || [] }]);
    // 布局完成前画布还是 DOM 默认的 300×150，这一帧画出来的坐标是「未缩放坐标系」，
    // 拿它跟 300×150 比一定越界。只要页面后面还有正经画布（尺寸不是默认值），
    // 这种短暂的预布局帧就不参与「裁切」判定，否则每页都会误报。
    const sized = frames.some(fr => fr.texts.some(t => t.canvas && t.canvas.w !== 300));
    const transient = t => sized && t.canvas && t.canvas.w === 300 && t.canvas.h === 150;
    const overlapRatio = (a, b) => inter(a, b) / Math.max(1, Math.min(a.w * a.h, b.w * b.h));
    const pairSeen = new Set();
    for (const fr of frames) {
      textCount = Math.max(textCount, fr.texts.length);
      const visibleTexts = fr.texts.filter(t => !transient(t));
      for (let i = 0; i < visibleTexts.length; i++) {
        const t = visibleTexts[i];
        if (transient(t)) continue;
        if (/\[object\s+(?:Object|[A-Za-z_$][\w$]*)\]/.test(t.text)) {
          if (!badText.some(x => x.text === t.text)) badText.push({ text: t.text, box: [Math.round(t.x), Math.round(t.y), Math.round(t.w), Math.round(t.h)] });
        }
        const area = Math.max(1, t.w * t.h);
        let worst = 0, by = null;
        for (const f of fr.fills) {
          if (f.order <= t.order || f.alpha < 0.45) continue;
          const r = inter(t, f) / area;
          if (r > worst) { worst = r; by = f; }
        }
        if (worst >= 0.35 && !seen.has('c:' + t.text)) {
          seen.add('c:' + t.text);
          covered.push({
            text: t.text, ratio: Math.round(worst * 100) / 100, by: by ? by.kind : '',
            textBox: [Math.round(t.x), Math.round(t.y), Math.round(t.w), Math.round(t.h)],
            fillBox: by ? [Math.round(by.x), Math.round(by.y), Math.round(by.w), Math.round(by.h)] : null,
            fillColor: by ? by.style : null,
          });
        }
        if ((t.x < -1 || t.y < -1 || t.x + t.w > t.canvas.w + 1 || t.y + t.h > t.canvas.h + 1)
          && !seen.has('o:' + t.text)) {
          seen.add('o:' + t.text);
          outOfBounds.push({
            text: t.text,
            box: [Math.round(t.x), Math.round(t.y), Math.round(t.w), Math.round(t.h)],
            canvas: [t.canvas.w, t.canvas.h],
          });
        }

        // 框线本身也会压字。只检测矩形边缘带，不把卡片内部的正常文字判成遮挡。
        for (const b of (fr.strokes || [])) {
          const thick = Math.max(1.5, b.lineWidth || 1);
          const bands = [
            { x: b.x - thick, y: b.y - thick, w: b.w + thick * 2, h: thick * 2 },
            { x: b.x - thick, y: b.y + b.h - thick, w: b.w + thick * 2, h: thick * 2 },
            { x: b.x - thick, y: b.y - thick, w: thick * 2, h: b.h + thick * 2 },
            { x: b.x + b.w - thick, y: b.y - thick, w: thick * 2, h: b.h + thick * 2 },
          ];
          const ratio = Math.max(...bands.map(edge => overlapRatio(t, edge)));
          const key = t.text + ':' + Math.round(t.x) + ':' + Math.round(t.y) + ':' + Math.round(b.x) + ':' + Math.round(b.y);
          if (ratio >= 0.06 && !pairSeen.has('b:' + key)) {
            pairSeen.add('b:' + key);
            borderOverlap.push({ text: t.text, ratio: Math.round(ratio * 100) / 100,
              textBox: [Math.round(t.x), Math.round(t.y), Math.round(t.w), Math.round(t.h)],
              borderBox: [Math.round(b.x), Math.round(b.y), Math.round(b.w), Math.round(b.h)] });
          }
        }
        for (let j = i + 1; j < visibleTexts.length; j++) {
          const u = visibleTexts[j];
          if (t.text === u.text) continue;
          const ratio = overlapRatio(t, u);
          const key = [t.text, Math.round(t.x), Math.round(t.y), u.text, Math.round(u.x), Math.round(u.y)].join(':');
          if (ratio >= 0.45 && !pairSeen.has('t:' + key)) {
            pairSeen.add('t:' + key);
            textOverlaps.push({ first: t.text, second: u.text, ratio: Math.round(ratio * 100) / 100,
              firstBox: [Math.round(t.x), Math.round(t.y), Math.round(t.w), Math.round(t.h)],
              secondBox: [Math.round(u.x), Math.round(u.y), Math.round(u.w), Math.round(u.h)] });
          }
        }
      }
    }
    return { textCount, covered, outOfBounds, borderOverlap, textOverlaps, badText };
  });

  // DOM：文字所在位置的最上层若是 canvas/img/svg，就是被图形压住。
  const scanDomText = () => page.evaluate(() => {
    const GRAPHIC = new Set(['CANVAS', 'IMG', 'SVG', 'VIDEO', 'PICTURE', 'OBJECT', 'IFRAME']);
    const issues = [];
    const seen = new Set();
    let checked = 0;
    for (const el of Array.from(document.querySelectorAll('body *'))) {
      if (GRAPHIC.has(el.tagName)) continue;
      const own = Array.from(el.childNodes)
        .filter(n => n.nodeType === 3).map(n => n.textContent.trim()).join('');
      if (!own) continue;
      const cs = getComputedStyle(el);
      if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity) < 0.05) continue;
      const rc = el.getBoundingClientRect();
      if (rc.width < 2 || rc.height < 2) continue;
      checked++;
      const pts = [
        [rc.left + rc.width / 2, rc.top + rc.height / 2],
        [rc.left + rc.width * 0.15, rc.top + rc.height * 0.3],
        [rc.left + rc.width * 0.85, rc.top + rc.height * 0.3],
        [rc.left + rc.width * 0.15, rc.top + rc.height * 0.7],
        [rc.left + rc.width * 0.85, rc.top + rc.height * 0.7],
      ];
      let hit = 0, by = null, total = 0;
      for (const [x, y] of pts) {
        if (x < 2 || y < 2 || x > innerWidth - 2 || y > innerHeight - 2) continue;
        total++;
        const stack = document.elementsFromPoint(x, y);
        const idx = stack.indexOf(el);
        if (idx <= 0) continue;
        const above = stack.slice(0, idx).filter(n => GRAPHIC.has(n.tagName) && !el.contains(n));
        if (above.length) { hit++; by = by || above[0].tagName.toLowerCase(); }
      }
      if (hit > 0 && !seen.has(own.slice(0, 20))) {
        seen.add(own.slice(0, 20));
        issues.push({
          tag: el.tagName.toLowerCase(),
          text: own.slice(0, 40),
          coveredBy: by,
          points: hit + '/' + total,
        });
      }
    }
    return { checked, issues };
  });

  const mergeCanvasText = (r) => {
    const dst = result.textOverlap.canvas;
    dst.textCount = Math.max(dst.textCount, r.textCount);
    for (const c of r.covered) {
      if (!dst.covered.some(x => x.text === c.text)) dst.covered.push(c);
      dst.worst = Math.max(dst.worst, c.ratio);
    }
    for (const o of r.outOfBounds) {
      if (!dst.outOfBounds.some(x => x.text === o.text)) dst.outOfBounds.push(o);
    }
    for (const o of r.borderOverlap || []) {
      if (!dst.borderOverlap.some(x => x.text === o.text && JSON.stringify(x.borderBox) === JSON.stringify(o.borderBox))) dst.borderOverlap.push(o);
    }
    for (const o of r.textOverlaps || []) {
      if (!dst.textOverlaps.some(x => x.first === o.first && x.second === o.second)) dst.textOverlaps.push(o);
    }
    for (const o of r.badText || []) {
      if (!dst.badText.some(x => x.text === o.text)) dst.badText.push(o);
    }
  };

  mergeCanvasText(await scanCanvasText());

  // ---- 0. 首屏快照：后面判断「重置是否回到初态」的基准 ----
  const SNAP = () => page.evaluate(() => {
    const clone = v => { try { return JSON.parse(JSON.stringify(v)); } catch (e) { return null; } };
    return {
      text: (document.body.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 6000),
      data: clone(window.__DATA__ || null),
      geo: clone(window.__GEO__ || null),
    };
  });
  const initial = await SNAP();

  // ---- 1. 六区域是否有内容 ----
  result.sections = await page.evaluate(defs => defs.map(([id, cls, name]) => {
    const el = document.getElementById(id) || document.querySelector('.' + cls);
    if (!el) return { id, name, 存在: false, 字符数: 0, 空: true, text: '' };
    const t = (el.innerText || '').replace(/\s+/g, ' ').trim();
    return { id, name, 存在: true, 字符数: t.length, 空: t.length < 8, text: t.slice(0, 400) };
  }), SECTION_DEFS);

  // ---- 2. canvas 是否真的画了东西 ----
  result.canvas = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('canvas'))
      .filter(c => c.style.display !== 'none')
      .map(c => {
      try {
        const ctx = c.getContext('2d');
        const w = Math.min(c.width, 400), h = Math.min(c.height, 400);
        const data = ctx.getImageData(0, 0, w, h).data;
        let painted = 0;
        for (let i = 3; i < data.length; i += 4) if (data[i] > 0) painted++;
        return { w: c.width, h: c.height, painted };
      } catch (e) {
        return { w: c.width, h: c.height, painted: -1 };
      }
    });
  });

  // ---- 2a. 版式取证：蓝色条只放名字 / ①区不重复 / 正文纯黑 / 最小字号 ----
  //        门槛不写死：从页面的 --pf-fs-min 变量读，规范改成 26px 时这里自动跟着走
  result.typography = await page.evaluate(() => {
    const cssMin = parseFloat(
      getComputedStyle(document.documentElement).getPropertyValue('--pf-fs-min')
    );
    const MIN = cssMin > 0 ? cssMin : 13;
    const out = { fsMin: MIN, title: '', titleLen: 0, hasName: false, minFs: 99, small: 0, colored: 0, samples: [] };
    const t = document.querySelector('.pf-page');
    if (t) { out.title = (t.textContent || '').trim(); out.titleLen = out.title.length; }
    const info = document.getElementById('sec-info');
    out.hasName = !!(info && info.querySelector('.exp-name'));
    // 语义色不算「正文非黑」：标签、按钮、读数数值、公式强调、警示、页眉页脚
    // （与 tools/ui_audit.js 的 ACC 清单保持一致，否则两个工具会给出不同结论）
    const KEEP = '.exp-tag,.exp-btn,.exp-read .v,.exp-field .exp-val,.exp-formula em,.exp-alert,.pf-tip,.pf-fix,.pf-page';
    document.querySelectorAll('.pf-main *, .pf-footer').forEach((el) => {
      let txt = '';
      for (const c of el.childNodes) if (c.nodeType === 3) txt += c.nodeValue.trim();
      if (!txt) return;
      if (el.closest('canvas, svg')) return;
      const st = getComputedStyle(el);
      const fs = parseFloat(st.fontSize) || 0;
      if (fs && fs < out.minFs) out.minFs = fs;
      if (fs && fs < MIN - 0.01) {
        out.small++;
        if (out.samples.length < 5) out.samples.push({ 类: (el.className || el.tagName).toString().slice(0, 20), 字号: +fs.toFixed(1), 文字: txt.slice(0, 12) });
      }
      if (!el.matches(KEEP) && st.color !== 'rgb(0, 0, 0)') out.colored++;
    });
    if (out.minFs === 99) out.minFs = 0;
    return out;
  });

  // ---- 2b. 质感取证：渐变/叠层/立体件/曲线/扁平色块 ----
  result.quality = await page.evaluate(() => {
    const q = (window.__CANVAS_AUDIT__ && window.__CANVAS_AUDIT__.q) || null;
    if (!q || !q.fills) return null;
    const f = q.fills;
    const totalPath = q.rect + q.curve;
    return {
      填充数: f,
      渐变占比: +(q.grad / f).toFixed(3),
      叠层占比: +(q.alpha / f).toFixed(3),
      立体件占比: +((q.radial + q.ellipse + q.blur) / f).toFixed(3),
      曲线占比: +(totalPath ? q.curve / totalPath : 0).toFixed(3),
      扁平色块: q.flat,
      扁平占比: +(q.flat / f).toFixed(3),
      径向渐变: q.radial,
      椭圆: q.ellipse,
      柔光: q.blur,
    };
  });

  // ---- 3. 机读数据：第三关判据的原料 ----
  result.machine = await page.evaluate(() => {
    const clone = v => { try { return JSON.parse(JSON.stringify(v)); } catch (e) { return null; } };
    const m = { has: false, keys: [] };
    [['DATA', window.__DATA__], ['GEO', window.__GEO__],
     ['CONFIG', window.__CONFIG__], ['EXP', window.__EXP__]].forEach(([k, v]) => {
      if (v !== undefined && v !== null) { m[k] = clone(v); m.keys.push(k); m.has = true; }
    });
    return m;
  });

  // ---- 4. 滑块初始范围（J1 检查越界/除零用） ----
  result.ranges.bounds = await page.evaluate(
    () => Array.from(document.querySelectorAll('input[type=range]')).map(el => ({
      名称: (el.dataset.key || el.id || el.name || '').slice(0, 20),
      min: parseFloat(el.min || '0'),
      max: parseFloat(el.max || '100'),
      value: parseFloat(el.value),
      step: parseFloat(el.step || '1'),
    }))
  );
  result.ranges.count = result.ranges.bounds.length;

  // ---- 5. 代入式复算（第一现场：首屏） ----
  const readFormula = () => {
    const SUP = { '⁰': '0', '¹': '1', '²': '2', '³': '3', '⁴': '4', '⁵': '5', '⁶': '6', '⁷': '7', '⁸': '8', '⁹': '9' };
    const normalize = s => s.replace(
      /(\d+(?:\.\d+)?)\s*[×x]\s*10\s*([⁻-]?)\s*([⁰¹²³⁴⁵⁶⁷⁸⁹]{1,3}|\d{1,3})/g,
      (m, base, sign, exp) => {
        const e = parseInt(String(exp).replace(/[⁰¹²³⁴⁵⁶⁷⁸⁹]/g, c => SUP[c]), 10);
        if (!isFinite(e)) return m;
        const v = parseFloat(base) * Math.pow(10, sign ? -e : e);
        return String(Number(v.toPrecision(12)));
      }
    );
    return normalize(document.body.innerText.replace(/\s+/g, ' '));
  };

  // 电路：I = U / R（R 可为多电阻之和）
  const CIRCUIT_RE = /([\d.]+)\s*(?:V|伏)\s*[÷\/]\s*([^=＝]{1,90}?)\s*[=≈]\s*([\d.]+)\s*(?:A|安)/g;
  // 浮力：F浮 = ρ液 g V排，三因子连乘
  const BUOYANCY_RE = /([\d.]+)\s*(?:kg\/m³|kg\/m3|kg\/m\^3|千克每立方米)\s*[×x*·]\s*([\d.]+)\s*(?:N\/kg|牛每千克)\s*[×x*·]\s*([\d.]+)\s*(?:m³|m3|m\^3|立方米)\s*[=≈]\s*([\d.]+)\s*(?:N|牛)/g;

  const toNum = s => parseFloat(s);

  const parseFormula = text => {
    const out = [];
    // 专用公式（电路 / 浮力）已经完整解释过的区间，通用式必须跳过，
    // 否则浮力的三因子连乘会被通用式截成「10 N/kg × 0.0001 m³ = 1.00 N」误判成算错。
    const covered = [];
    let m, re;

    re = new RegExp(CIRCUIT_RE.source, 'g');
    while ((m = re.exec(text)) !== null) {
      const u = toNum(m[1]), shown = toNum(m[3]);
      const ohms = (m[2].match(/([\d.]+)\s*Ω/g) || []).map(toNum);
      if (!ohms.length) continue;
      const r = ohms.reduce((a, b) => a + b, 0);
      const expect = u / r;
      covered.push([m.index, m.index + m[0].length]);
      out.push({
        类型: '电路', text: m[0].trim().slice(0, 80), 显示: shown,
        应为: Number(expect.toFixed(3)),
        ok: r > 0 && isFinite(expect) && Math.abs(expect - shown) <= Math.max(0.002, Math.abs(expect) * 0.02),
      });
    }

    re = new RegExp(BUOYANCY_RE.source, 'g');
    while ((m = re.exec(text)) !== null) {
      const rho = toNum(m[1]), g = toNum(m[2]), vol = toNum(m[3]), shown = toNum(m[4]);
      const expect = rho * g * vol;
      covered.push([m.index, m.index + m[0].length]);
      out.push({
        类型: '浮力', text: m[0].trim().slice(0, 80), 显示: shown,
        应为: Number(expect.toFixed(2)),
        // expect 可以是 0（未浸入时 F浮 = 0 是正确值），只要求复算结果有限且与显示一致
        ok: isFinite(expect) && Math.abs(expect - shown) <= Math.max(0.01, Math.abs(expect) * 0.03),
      });
    }

    // 分式代入式：分子/分母 = 结果。分子分母允许带括号与连乘，比如
    // 「对称轴 x = -(0.0)/(2×1.0) = 0.00」「(4×1.0)/(2×1.0) = 2.00」——
    // 二次函数的对称轴 / 顶点纵坐标、比例类页面全都长这样，
    // 以前只有「两数一次四则运算」一种解析，这类页面会被误判成「没有代入式」。
    const MULEXP = '(-?\\s*[(]?\\s*-?\\d+(?:\\.\\d+)?(?:\\s*[×x*·]\\s*-?\\d+(?:\\.\\d+)?)*[)]?)';
    const FRAC_RE = new RegExp(
      MULEXP + '\\s*\\/\\s*' + MULEXP + '\\s*[=≈]\\s*(-?\\d+(?:\\.\\d+)?)', 'g');
    const evMul = s => {
      // 去掉括号后按乘号拆开逐个 parseFloat 再连乘；"-2×3" 与 "-(2×3)" 结果一致
      const nums = (String(s).replace(/[()（）\s]/g, '').split(/[×x*·]/) || [])
        .map(toNum).filter(v => isFinite(v));
      if (!nums.length) return NaN;
      return nums.reduce((a, b) => a * b, 1);
    };
    re = new RegExp(FRAC_RE.source, 'g');
    while ((m = re.exec(text)) !== null) {
      const gs = m.index, ge = m.index + m[0].length;
      if (covered.some(([s, e]) => gs < e && ge > s)) continue;
      const a = evMul(m[1]), b = evMul(m[2]), shown = toNum(m[3]);
      if (!isFinite(a) || !isFinite(b) || !(b > 0) || !isFinite(shown)) continue;
      const expect = a / b;
      covered.push([gs, ge]);
      out.push({
        类型: '分式', text: m[0].trim().slice(0, 80), 显示: shown,
        应为: Number(expect.toFixed(3)),
        ok: Math.abs(expect - shown) <= Math.max(0.011, Math.abs(expect) * 0.02),
      });
    }

    // 链式三数运算：a op b op c = d（如「1.80 × 10 ÷ 10 = 1.80」）
    // 必须先于两数通用式解析，否则会被截成「10 ÷ 10 = 1.80」误判成算错
    const NUM = '(\\d+(?:\\.\\d+)?)';
    const UNIT = '[A-Za-zΩμρθ°%³²·\\/\\^\\u4e00-\\u9fa5]{0,6}';
    const OP = '([+\\-×x*÷／\\/])';
    const CHAIN_RE = new RegExp(
      NUM + '\\s*' + UNIT + '\\s*' + OP + '\\s*' + NUM + '\\s*' + UNIT + '\\s*' + OP +
      '\\s*' + NUM + '\\s*' + UNIT + '\\s*[=≈]\\s*' + NUM, 'g');    const apply = (x, op, y) => {
      if (op === '+') return x + y;
      if (op === '-') return x - y;
      if (op === '×' || op === 'x' || op === '*') return x * y;
      return y === 0 ? NaN : x / y;
    };
    while ((m = CHAIN_RE.exec(text)) !== null) {
      const a = toNum(m[1]), b = toNum(m[3]), c = toNum(m[5]), shown = toNum(m[6]);
      const mid = apply(a, m[2], b);
      const expect = apply(mid, m[4], c);
      if (!isFinite(expect)) continue;
      covered.push([m.index, m.index + m[0].length]);
      const pre = text.slice(Math.max(0, m.index - 6), m.index);
      const approx = /[≈约]/.test(pre) || /≈/.test(m[0]);
      const dec = (m[6].split('.')[1] || '').length;
      out.push({
        类型: '链式', text: m[0].trim().slice(0, 80), 显示: shown,
        应为: Number(expect.toFixed(3)),
        ok: approx ? Math.abs(expect - shown) <= 0.5 * Math.pow(10, -dec) + 1e-9
                   : Math.abs(expect - shown) <= Math.max(0.011, Math.abs(expect) * 0.02),
      });
    }

    // 通用代入式：任意学科，只需"两数一次四则运算 = 第三数"可复算
    const GENERIC_RE = /(\d+(?:\.\d+)?)\s*[A-Za-zΩμρθ°%³²·\/\^\u4e00-\u9fa5]{0,6}\s*([+\-×x*÷／\/])\s*(\d+(?:\.\d+)?)\s*[A-Za-zΩμρθ°%³²·\/\^\u4e00-\u9fa5]{0,6}\s*[=≈]\s*(\d+(?:\.\d+)?)/g;
    re = new RegExp(GENERIC_RE.source, 'g');
    while ((m = re.exec(text)) !== null) {
      const gs = m.index, ge = m.index + m[0].length;
      if (covered.some(([s, e]) => gs < e && ge > s)) continue;
      // 前面紧挨着运算符 = 只是更长算式的后半截，交给链式解析，别当独立等式复算
      if (/[+\-×x*÷／\/]$/.test(text.slice(0, gs).replace(/\s+$/, ''))) continue;
      const a = toNum(m[1]), b = toNum(m[3]), shown = toNum(m[4]), op = m[2];
      // 允许 0 参与加减（截面退化时体积为 0 是正确值），但除法不允许除数为 0
      if (!(a >= 0) || !(b >= 0)) continue;
      if ((op === '÷' || op === '／' || op === '/') && !(b > 0)) continue;
      let expect;
      if (op === '+') expect = a + b;
      else if (op === '-') expect = a - b;
      else if (op === '×' || op === 'x' || op === '*') expect = a * b;
      else expect = a / b;
      if (!isFinite(expect)) continue;
      const tol = Math.max(0.011, Math.abs(expect) * 0.02);
      // 整句已声明「≈ / 约」时，按显示位数判断是否是该精度的正确四舍五入
      // 例：「一行细胞数 ≈ 800 / 600 = 1.3」——1.3 是 1.3333 保留一位的正确结果，不算错
      const pre = text.slice(Math.max(0, m.index - 6), m.index);
      const approx = /[≈约]/.test(pre) || /≈/.test(m[0]);
      const dec = (String(m[4]).split('.')[1] || '').length;
      const okApprox = Math.abs(expect - shown) <= 0.5 * Math.pow(10, -dec) + 1e-9;
      // 占比类物理量（浸入比、机械效率、浓度…）上限就是 1：ρ物/ρ液 = 3.00/2.00 时
      // 页面写 1.000 是「钳制到 100%」的正确值，不是算错
      const clampedRatio = (op === '÷' || op === '／' || op === '/') &&
        expect > 1.0001 && Math.abs(shown - 1) <= 5e-4;
      out.push({
        类型: clampedRatio ? '通用(占比钳制)' : '通用',
        text: m[0].trim().slice(0, 80), 显示: shown,
        应为: Number(expect.toFixed(3)),
        ok: clampedRatio || (approx ? okApprox : Math.abs(expect - shown) <= tol),
      });
    }
    return out;
  };

  const initialChecks = parseFormula(await page.evaluate(readFormula));
  initialChecks.forEach(c => { c.阶段 = '首屏'; });
  if (initialChecks.length) {
    result.formula.found = true;
    result.formula.checks.push(...initialChecks);
  }

  // ---- 6. 拖滑块到极值，看有没有响应 ----
  const visualSig = () => page.evaluate(() => {
    const text = document.body.innerText.replace(/\s+/g, ' ').slice(0, 3000);
    let hash = 2166136261;
    document.querySelectorAll('canvas').forEach(c => {
      try {
        const ctx = c.getContext('2d');
        const w = Math.min(c.width, 1200), h = Math.min(c.height, 900);
        const d = ctx.getImageData(0, 0, w, h).data;
        const sx = Math.max(1, Math.floor(w / 24)), sy = Math.max(1, Math.floor(h / 24));
        for (let y = 0; y < h; y += sy) for (let x = 0; x < w; x += sx) {
          const i = (y * w + x) * 4;
          for (let ch = 0; ch < 3; ch++) hash = Math.imul(hash ^ d[i + ch], 16777619) >>> 0;
        }
      } catch (e) { /* 跨域或未绘制，忽略 */ }
    });
    const data = JSON.stringify(window.__DATA__ || window.__GEO__ || null);
    return text + '##' + hash + '##' + data;
  });

  result.visualType = await page.evaluate(() => {
    const c = document.querySelector('#sec-stage canvas, #sec-stage svg, canvas, svg');
    return c ? (c.getAttribute('data-visual-type') || '') : '';
  });

  // 3D 视角重置专项：真实拖动旋转后点击“恢复默认视角”，比较视角状态。
  const viewBtn = page.getByRole('button', { name: /恢复默认视角|重置视角|默认视角/ }).first();
  if (await viewBtn.count()) {
    result.viewReset.applicable = true;
    const canvas = page.locator('#sec-stage canvas, canvas').first();
    const box = await canvas.boundingBox();
    const before = await canvas.evaluate(c => c.__mathView ? { yaw: c.__mathView.yaw, pitch: c.__mathView.pitch } : null);
    if (box && before) {
      await page.mouse.move(box.x + box.width * 0.5, box.y + box.height * 0.5);
      await page.mouse.down();
      await page.mouse.move(box.x + box.width * 0.68, box.y + box.height * 0.62, { steps: 6 });
      await page.mouse.up();
      await page.waitForTimeout(100);
      const turned = await canvas.evaluate(c => c.__mathView ? { yaw: c.__mathView.yaw, pitch: c.__mathView.pitch } : null);
      result.viewReset.rotated = !!turned && (Math.abs(turned.yaw - before.yaw) > 1e-4 || Math.abs(turned.pitch - before.pitch) > 1e-4);
      await viewBtn.click();
      await page.waitForTimeout(100);
      const after = await canvas.evaluate(c => c.__mathView ? { yaw: c.__mathView.yaw, pitch: c.__mathView.pitch } : null);
      result.viewReset.restored = !!after && Math.abs(after.yaw - before.yaw) < 1e-4 && Math.abs(after.pitch - before.pitch) < 1e-4;
      result.viewReset.before = before;
      result.viewReset.afterDrag = turned;
      result.viewReset.afterReset = after;
    }
  }

  for (let idx = 0; idx < result.ranges.count; idx++) {
    const before = await visualSig();
    const info = await page.evaluate(async i => {
      const el = document.querySelectorAll('input[type=range]')[i];
      const min = parseFloat(el.min || '0'), max = parseFloat(el.max || '100');
      const target = el.value === String(max) ? min : max;
      el.value = String(target);
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
      await new Promise(r => setTimeout(r, 250));
      return { index: i };
    }, idx);
    info.changed = before !== await visualSig();
    result.ranges.details.push(info);
    if (info.changed) result.ranges.responsive++;
    await captureCircuit('range-' + idx);
  }

  // ---- 6b. 离散选择器：确认切换选项确实切换实验状态 ----
  result.selects.count = await page.locator('select').count();
  for (let idx = 0; idx < result.selects.count; idx++) {
    const before = await visualSig();
    const info = await page.evaluate(async i => {
      const el = document.querySelectorAll('select')[i];
      const original = el.value;
      const option = Array.from(el.options).find(o => !o.disabled && o.value !== original);
      if (!option) return { index: i, applicable: false, reason: '没有其他可选项' };
      el.value = option.value;
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
      await new Promise(r => setTimeout(r, 250));
      return { index: i, applicable: true, selectedChanged: el.value === option.value, selected: option.value, original };
    }, idx);
    if (!info.applicable) {
      result.selects.details.push(info);
      continue;
    }
    info.updatedView = before !== await visualSig();
    info.changed = !!info.selectedChanged && info.updatedView;
    await page.evaluate(({ i, value }) => {
      const el = document.querySelectorAll('select')[i];
      el.value = value;
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
    }, { i: idx, value: info.original });
    await page.waitForTimeout(180);
    result.selects.details.push(info);
    if (info.changed) result.selects.responsive++;
      await captureCircuit('select-' + idx);
  }

  // 极值状态下的代入式（J1「极值下仍自洽」）
  if (result.ranges.count > 0) {
    await page.waitForTimeout(200);
    const after = parseFormula(await page.evaluate(readFormula));
    after.forEach(c => { c.阶段 = '极值'; });
    if (after.length) {
      result.formula.found = true;
      result.formula.checks.push(...after);
    }
  }

  // 极值状态下再查一遍文字遮挡（参数拉满最容易把标注挤出画布/被图元压住）
  mergeCanvasText(await scanCanvasText());

  // ---- 7. 重置：是否回到与首屏一致的状态（规范 2.3 必做） ----
  const clickByText = pattern => page.evaluate(pat => {
    const re = new RegExp(pat);
    const list = Array.from(document.querySelectorAll('button, a, [role=button]'));
    const el = list.find(b => re.test((b.innerText || b.textContent || '').trim()));
    if (!el) return null;
    const label = (el.innerText || el.textContent || '').trim().slice(0, 10);
    el.click();
    return label;
  }, pattern.source);

  const resetLabel = await clickByText(/重置|复位|恢复初始|reset/i);
  if (resetLabel) {
    await page.waitForTimeout(400);
    const afterReset = await SNAP();
    result.reset.found = true;
    result.reset.label = resetLabel;
    result.reset.dataDiff = JSON.stringify(initial.data) !== JSON.stringify(afterReset.data)
      || JSON.stringify(initial.geo) !== JSON.stringify(afterReset.geo);
    result.reset.textDiff = Math.abs((initial.text || '').length - (afterReset.text || '').length);
    result.reset.restored = !result.reset.dataDiff
      && (initial.text === afterReset.text || result.reset.textDiff <= 4);
    if (!result.reset.restored) {
      result.reset.initialText = (initial.text || '').slice(0, 300);
      result.reset.resetText = (afterReset.text || '').slice(0, 300);
    }
  }

  // ---- 8. 逐个点按钮，看有没有"点了没反应" ----
  result.buttons = await page.evaluate(() => document.querySelectorAll('button').length);
  for (let i = 0; i < Math.min(result.buttons, 6); i++) {
    const before = await visualSig();
    const info = await page.evaluate(async idx => {
      const btn = document.querySelectorAll('button')[idx];
      const label = (btn.innerText || btn.textContent || '').trim().slice(0, 10);
      try { btn.click(); } catch (e) { return { 序号: idx, 按钮: label, 有响应: false }; }
      await new Promise(r => setTimeout(r, 180));
      return { 序号: idx, 按钮: label };
    }, i);
    if (info.有响应 !== false) info.有响应 = before !== await visualSig();
    result.buttonsClicked.push(info);
  }

  // ---- 9. 单步 / 下一步：状态是否推进且不卡死（J5 用） ----
  if (resetLabel) await clickByText(/重置|复位|恢复初始|reset/i);
  await page.waitForTimeout(200);
  const stepLabel = await clickByText(/单步|下一步|步进|step|前进/i);
  if (stepLabel) {
    result.steps.found = true;
    const seen = [];
    for (let i = 0; i < 8; i++) {
      const sig = await page.evaluate(() => {
        const clone = v => { try { return JSON.stringify(v); } catch (e) { return ''; } };
        return clone(window.__DATA__ || window.__GEO__ || null) || document.body.innerText.slice(0, 800);
      });
      seen.push(sig);
      await page.evaluate(pat => {
        const re = new RegExp(pat);
        const btn = Array.from(document.querySelectorAll('button, a, [role=button]'))
          .find(b => re.test((b.innerText || b.textContent || '').trim()));
        if (btn) btn.click();
      }, /单步|下一步|步进|step|前进/i.source);
      await page.waitForTimeout(200);
    }
    result.steps.count = seen.length;
    result.steps.stuck = seen.filter((s, i) => i > 0 && s === seen[i - 1]).length;
    // 只保留指纹，避免把整页文本塞进报告
    result.steps.sequence = seen.map((s, i) => ({ 步: i, 指纹: String(s).length + ':' + String(s).slice(0, 40) }));
    result.steps.unique = new Set(seen).size;
  }

  // ---- 10. 记录：连点 3 次「记录」，表格是否追加行 ----
  const countRows = () => page.evaluate(
    () => Array.from(document.querySelectorAll('table')).reduce(
      (n, t) => n + t.querySelectorAll('tbody tr').length, 0)
  );
  result.records.before = await countRows();
  let recordClicked = 0;
  for (let i = 0; i < 3; i++) {
    const label = await clickByText(/记录|添加|保存数据|记一笔/i);
    if (!label) break;
    recordClicked++;
    await page.waitForTimeout(180);
  }
  result.records.after = await countRows();
  result.records.added = result.records.after - result.records.before;
  result.records.clicked = recordClicked;

  // ---- 11. CSV 导出能力 ----
  result.csv = await page.evaluate(() => {
    const html = document.documentElement.outerHTML.toLowerCase();
    const btn = Array.from(document.querySelectorAll('button, a'))
      .some(b => /csv/i.test((b.innerText || b.textContent || '')));
    return { found: /csv/.test(html) && (btn || /blob|download/.test(html)) };
  });

  // ---- 12. 表格数据（J7 独立复算原料） ----
  result.tables = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('table')).slice(0, 3).map(tb =>
      Array.from(tb.querySelectorAll('tr')).slice(0, 40).map(tr =>
        Array.from(tr.querySelectorAll('th,td')).slice(0, 10)
          .map(td => (td.innerText || '').replace(/\s+/g, ' ').trim())
      )
    );
  });

  // ---- 13. DOM 层文字是否被图形层压住（桌面 + 移动端两个视口） ----
  for (const vp of [{ name: 'desktop', width: 1366, height: 900 },
                    { name: 'mobile', width: 390, height: 844 }]) {
    await page.setViewportSize({ width: vp.width, height: vp.height });
    await page.waitForTimeout(320);
    const layout = await page.evaluate(() => ({
      width: innerWidth,
      documentWidth: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth),
      stageWidth: Math.round((document.querySelector('#sec-stage') || {}).getBoundingClientRect?.().width || 0),
    }));
    result.layout.viewports.push({ ...layout, name: vp.name, overflow: layout.documentWidth > layout.width + 2 });
    const dom = await scanDomText();
    result.textOverlap.dom.checked += dom.checked;
    for (const it of dom.issues) {
      if (!result.textOverlap.dom.issues.some(x => x.text === it.text && x.tag === it.tag)) {
        result.textOverlap.dom.issues.push({ ...it, viewport: vp.name });
      }
    }
  }
  result.layout.unlabeled = await page.evaluate(() => Array.from(
    document.querySelectorAll('input:not([type="hidden"]), select, textarea')
  ).filter(el => {
    const aria = el.getAttribute('aria-label') || el.getAttribute('aria-labelledby');
    const local = el.closest('.exp-field')?.querySelector('.exp-label')?.innerText?.trim();
    return !(el.labels && el.labels.length) && !aria && !local;
  }).map(el => ({ tag: el.tagName.toLowerCase(), id: el.id || '', type: el.type || '' })));
  await page.setViewportSize({ width: 1366, height: 900 });

  await browser.close();
  console.log(JSON.stringify(result));
}

main().catch(err => {
  console.error(String(err && err.stack || err));
  console.log(JSON.stringify({ ok: false, fatal: String(err && err.message || err) }));
  process.exit(1);
});
