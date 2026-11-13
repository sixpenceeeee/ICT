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
const fs = require('fs');
const physicsModels = require('../03_generator_agent/solvers/physics/lesson_models.json');
const mathModels = require('../03_generator_agent/solvers/mathematics/lesson_models.json');
const presetLessonModels = { ...physicsModels, ...mathModels };

const FILE = process.argv[2];
// 第三个参数是审查端生成的变形计划（JSON）。没有计划时保持原有行为。
const PLAN = process.argv[3] ? JSON.parse(fs.readFileSync(process.argv[3], 'utf8')) : null;

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
    numberInputs: { count: 0, responsive: 0, details: [] },
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
    metamorphic: { samples: [], solverGlobals: [], summary: {} },
    mr: { plan: null, scenes: [], errors: [] },
    circuit: { initial: null, samples: [] },
    cubeCut: { initial: null, samples: [] },
  cylinderCut: { initial: null, samples: [] },
  coneCut: { initial: null, samples: [] },
  sphereCut: { initial: null, samples: [] },
  spatialMetric: { initial: null, samples: [] },
  solidVolume: { initial: null, samples: [] },
    cubeNet: { initial: null, samples: [] },
    cuboidNet: { initial: null, samples: [] },
    cylinderNet: { initial: null, samples: [] },
    coneNet: { initial: null, samples: [] },
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
  const captureCubeCut = async label => {
    const state = await page.evaluate(() => {
      const clone = v => { try { return JSON.parse(JSON.stringify(v)); } catch (e) { return null; } };
      return { result: clone(window.__MATH_POLYHEDRON_RESULT__ || window.__MATH_CUBE_RESULT__), geo: clone(window.__GEO__),
        drawSignature: window.__MATH_POLYHEDRON_DRAW_SIGNATURE__ || window.__MATH_CUBE_DRAW_SIGNATURE__ || null };
    });
    if (state.result) result.cubeCut.samples.push({ label, ...state });
    return state.result ? state : null;
  };
  result.cubeCut.initial = await captureCubeCut('initial');
  const captureCylinderCut = async label => {
    const state = await page.evaluate(() => {
      const clone = v => { try { return JSON.parse(JSON.stringify(v)); } catch (e) { return null; } };
      return { result: clone(window.__MATH_CYLINDER_RESULT__), geo: clone(window.__GEO__),
        drawSignature: window.__MATH_CYLINDER_DRAW_SIGNATURE__ || null };
    });
    if (state.result) result.cylinderCut.samples.push({ label, ...state });
    return state.result ? state : null;
  };
  result.cylinderCut.initial = await captureCylinderCut('initial');
  const captureConeCut = async label => {
    const state = await page.evaluate(() => {
      const clone = v => { try { return JSON.parse(JSON.stringify(v)); } catch (e) { return null; } };
      return { result: clone(window.__MATH_CONE_RESULT__), geo: clone(window.__GEO__),
        drawSignature: window.__MATH_CONE_DRAW_SIGNATURE__ || null };
    });
    if (state.result) result.coneCut.samples.push({ label, ...state });
    return state.result ? state : null;
  };
  result.coneCut.initial = await captureConeCut('initial');
  const captureSphereCut = async label => {
    const state = await page.evaluate(() => {
      const clone = v => { try { return JSON.parse(JSON.stringify(v)); } catch (e) { return null; } };
      return { result: clone(window.__MATH_SPHERE_RESULT__), geo: clone(window.__GEO__),
        drawSignature: window.__MATH_SPHERE_DRAW_SIGNATURE__ || null };
    });
    if (state.result) result.sphereCut.samples.push({ label, ...state });
    return state.result ? state : null;
  };
  result.sphereCut.initial = await captureSphereCut('initial');
  const captureSpatialMetric = async label => {
    const state = await page.evaluate(() => {
      const clone = v => { try { return JSON.parse(JSON.stringify(v)); } catch (e) { return null; } };
      return { request: clone(window.__MATH_SPATIAL_REQUEST__), result: clone(window.__MATH_SPATIAL_RESULT__) };
    });
    if (state.request && state.result) result.spatialMetric.samples.push({ label, ...state });
    return state.request && state.result ? state : null;
  };
  result.spatialMetric.initial = await captureSpatialMetric('initial');
  const captureSolidVolume = async label => {
    const state = await page.evaluate(() => {
      const clone = v => { try { return JSON.parse(JSON.stringify(v)); } catch (e) { return null; } };
      return { request: clone(window.__MATH_VOLUME_REQUEST__), result: clone(window.__MATH_VOLUME_RESULT__),
        partition: clone(window.__MATH_VOLUME_PARTITION_CHECK__) };
    });
    if (state.request && state.result) result.solidVolume.samples.push({ label, ...state });
    return state.request && state.result ? state : null;
  };
  result.solidVolume.initial = await captureSolidVolume('initial');
  const captureCubeNet = async label => {
    const state = await page.evaluate(() => {
      const clone = v => { try { return JSON.parse(JSON.stringify(v)); } catch (e) { return null; } };
      return { request: clone(window.__MATH_CUBE_NET_REQUEST__), result: clone(window.__MATH_CUBE_NET_RESULT__) };
    });
    if (state.request && state.result) result.cubeNet.samples.push({ label, ...state });
    return state.request && state.result ? state : null;
  };
  result.cubeNet.initial = await captureCubeNet('initial');
  const captureCuboidNet = async label => {
    const state = await page.evaluate(() => {
      const clone = v => { try { return JSON.parse(JSON.stringify(v)); } catch (e) { return null; } };
      return { request: clone(window.__MATH_CUBOID_NET_REQUEST__), result: clone(window.__MATH_CUBOID_NET_RESULT__) };
    });
    if (state.request && state.result) result.cuboidNet.samples.push({ label, ...state });
    return state.request && state.result ? state : null;
  };
  result.cuboidNet.initial = await captureCuboidNet('initial');
  const captureCylinderNet = async label => {
    const state = await page.evaluate(() => {
      const clone = v => { try { return JSON.parse(JSON.stringify(v)); } catch (e) { return null; } };
      return { request: clone(window.__MATH_CYLINDER_NET_REQUEST__), result: clone(window.__MATH_CYLINDER_NET_RESULT__) };
    });
    if (state.request && state.result) result.cylinderNet.samples.push({ label, ...state });
    return state.request && state.result ? state : null;
  };
  result.cylinderNet.initial = await captureCylinderNet('initial');
  const captureConeNet = async label => {
    const state = await page.evaluate(() => {
      const clone = v => { try { return JSON.parse(JSON.stringify(v)); } catch (e) { return null; } };
      return { request: clone(window.__MATH_CONE_NET_REQUEST__), result: clone(window.__MATH_CONE_NET_RESULT__) };
    });
    if (state.request && state.result) result.coneNet.samples.push({ label, ...state });
    return state.request && state.result ? state : null;
  };
  result.coneNet.initial = await captureConeNet('initial');

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

  // Record whether real page controls change the solver's live request/result.
  // Domain-specific verifiers below independently recompute every captured
  // transformed state; this layer proves the page actually reached that state.
  const captureSolverState = () => page.evaluate(() => {
    const clone = value => { try { return JSON.parse(JSON.stringify(value)); } catch (_) { return null; } };
    const names = Object.keys(window).filter(name =>
      name === '__GEO__' || name === '__DATA__' ||
      (/^__(?:CIRCUIT_|MATH_|CHEM_|PHYS_)/.test(name) &&
       /(?:REQUEST|RESULT|MODEL|STUDENT_CHECK|STUDENT_COEFFICIENTS|DRAW_SIGNATURE)__+$/.test(name)));
    const globals = {};
    for (const name of names) globals[name] = clone(window[name]);
    return globals;
  });
  const lessonSolvers = {
    quadratic: 'MATH_QUADRATIC', thinLens: 'PHYS_LENS',
    ...Object.fromEntries(Object.entries(presetLessonModels).map(([key, model]) => [key, model.prefix]))
  };
  result.lessonSolvers = {};
  const captureLessonSolvers = async (label, active, control) => {
    for (const [key, prefix] of Object.entries(lessonSolvers)) {
      if (!active.includes(prefix)) continue;
      const sample = await page.evaluate(name => {
        const fields = Object.create(null);
        for (const el of document.querySelectorAll('[data-solver-field]')) {
          if (el.getClientRects().length && getComputedStyle(el).visibility === 'visible') {
            const key = el.dataset.solverField;
            (fields[key] ??= []).push(el.innerText.trim());
          }
        }
        const error = document.querySelector('[data-solver-error]');
        return { request: window[`__${name}_REQUEST__`] ?? null,
          result: window[`__${name}_RESULT__`] ?? null, fields,
          error: error?.getClientRects().length && getComputedStyle(error).visibility === 'visible'
            ? error.innerText.trim() : '' };
      }, prefix);
      (result.lessonSolvers[key] ??= []).push({ label, control, ...sample });
    }
  };
  const metaBaseline = await captureSolverState();
  const activeLessonSolvers = Object.values(lessonSolvers).filter(prefix =>
    `__${prefix}_REQUEST__` in metaBaseline || `__${prefix}_RESULT__` in metaBaseline);
  await captureLessonSolvers('initial', activeLessonSolvers);
  const applyLessonControls = values => page.evaluate(async target => {
    const controls = [];
    const errors = [];
    const find = field => document.querySelectorAll(`[data-solver-input="${field}"]`);
    // The mode can enable/disable other controls, so set it first.
    const entries = Object.entries(target).sort((a, b) =>
      Number(typeof b[1] === 'string') - Number(typeof a[1] === 'string'));
    for (const [field, value] of entries) {
      const elements = find(field);
      const element = elements[0];
      const numeric = typeof value === 'number';
      const validType = numeric ? ['range', 'number'].includes(element?.type) : element?.tagName === 'SELECT';
      if (elements.length !== 1 || !validType || !element.getClientRects().length ||
          getComputedStyle(element).visibility !== 'visible') {
        errors.push(`缺少唯一可见的 ${field} 控件`);
        continue;
      }
      const oldValue = element.value;
      if (oldValue !== String(value) && !element.matches(':disabled')) {
        element.value = String(value);
        element.dispatchEvent(new Event('input', { bubbles: true }));
        element.dispatchEvent(new Event('change', { bubbles: true }));
      }
      controls.push({ field, oldValue });
    }
    await new Promise(resolve => setTimeout(resolve, 180));
    for (const control of controls) {
      const { field } = control;
      const elements = find(field);
      const element = elements[0];
      const value = target[field];
      const actual = element?.value ?? '';
      if (elements.length !== 1 || !element.validity?.valid ||
          (typeof value === 'number' ? actual === '' || Number(actual) !== value : actual !== value)) {
        errors.push(`${field} 控件无法取值 ${value}`);
      }
      control.newValue = actual;
    }
    return { controls, errors };
  }, values);
  for (const model of Object.values(presetLessonModels)) {
    if (!activeLessonSolvers.includes(model.prefix)) continue;
    const initialValues = await page.evaluate(fields => {
      return Object.fromEntries(fields.flatMap(field => {
        const el = document.querySelector(`[data-solver-input="${field}"]`);
        if (!el || el.value === '') return [];
        return [[field, el.tagName === 'SELECT' ? el.value : Number(el.value)]];
      }));
    }, Object.keys(model.inputs));
    const solverScales = await page.evaluate(() => window.__SOLVER_SCALES__ || {});
    for (const [name, values] of Object.entries(model.cases)) {
      // lesson_models 的 case 是 SI 值；页面控件显示的可能换过单位（如 cm³）。
      // 取证必须按 scale 折算成控件显示值，否则会填出越界值把页面打回错误态。
      const displayValues = Object.fromEntries(Object.entries(values).map(([key, value]) =>
        [key, typeof value === 'number' && solverScales[key]
          ? Number((value / solverScales[key]).toPrecision(12)) : value]));
      const evidence = await applyLessonControls(displayValues);
      await captureLessonSolvers('preset:' + name, [model.prefix], evidence);
    }
    await applyLessonControls(initialValues);
  }
  result.metamorphic.solverGlobals = Object.keys(metaBaseline);
  const recordMetaMutation = (kind, info, before, after) => {
    const keys = new Set([...Object.keys(before || {}), ...Object.keys(after || {})]);
    const changedKeys = Array.from(keys).filter(key => JSON.stringify(before?.[key]) !== JSON.stringify(after?.[key]));
    const changedInputs = changedKeys.filter(key => /REQUEST|MODEL|STUDENT_COEFFICIENTS|GEO__|DATA__/.test(key));
    const changedResponses = changedKeys.filter(key => /RESULT|STUDENT_CHECK|STUDENT_COEFFICIENTS/.test(key));
    const inputChanged = String(info?.oldValue) !== String(info?.newValue);
    const sample = { kind, index: info?.index, control: info?.control || kind,
      oldValue: info?.oldValue, newValue: info?.newValue, inputChanged,
      changedKeys, changedInputs, changedResponses };
    result.metamorphic.samples.push(sample);
    if (inputChanged) result.metamorphic.summary.controlsChanged = (result.metamorphic.summary.controlsChanged || 0) + 1;
    if (changedInputs.length) result.metamorphic.summary.solverInputsChanged = (result.metamorphic.summary.solverInputsChanged || 0) + 1;
    if (changedResponses.length) result.metamorphic.summary.solverResponsesChanged = (result.metamorphic.summary.solverResponsesChanged || 0) + 1;
  };

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
  result.machine = await page.evaluate(async () => {
    const clone = v => { try { return JSON.parse(JSON.stringify(v)); } catch (e) { return null; } };
    const m = { has: false, keys: [] };
    const stoichSnapshot = () => {
      const inputs = Array.from(document.querySelectorAll('[data-chem-stoich-amount-index]'))
        .map(el => ({ el, index: Number(el.getAttribute('data-chem-stoich-amount-index')), value: el.valueAsNumber }))
        .sort((a,b) => a.index - b.index);
      const progress = document.querySelector('[data-chem-stoich-progress]');
      if (!inputs.length || !progress) return null;
      const visible = el => !el.disabled && el.getClientRects().length > 0 &&
        getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none';
      if (!inputs.every(item => visible(item.el)) || !visible(progress)) return null;
      return {
        request: clone(window.__CHEM_STOICH_REQUEST__),
        result: clone(window.__CHEM_STOICH_RESULT__),
        controls: { indices: inputs.map(item => item.index),
          initial_amounts_mol: inputs.map(item => item.value),
          amount_min: inputs.map(item => item.el.min === '' ? 0 : Number(item.el.min)),
          amount_max: inputs.map(item => item.el.max === '' ? 1000000 : Number(item.el.max)),
          progress: progress.valueAsNumber },
        displayed_equation: (document.querySelector('[data-chem-stoich-equation]')?.textContent || '')
          .replace(/[₀₁₂₃₄₅₆₇₈₉]/g, ch => '₀₁₂₃₄₅₆₇₈₉'.indexOf(ch)).replace(/\s+/g, '')
      };
    };
    const mixSnapshot = () => {
      const indexed = (selector, attribute) => Array.from(document.querySelectorAll(selector))
        .map(el => ({ el, index: Number(el.getAttribute(attribute)), value: el.valueAsNumber }))
        .sort((a,b) => a.index - b.index);
      const concentrations = indexed('[data-chem-mix-concentration-index]', 'data-chem-mix-concentration-index');
      const volumes = indexed('[data-chem-mix-volume-index]', 'data-chem-mix-volume-index');
      const units = Array.from(document.querySelectorAll('[data-chem-mix-unit-index]'))
        .map(el => ({ el, index: Number(el.getAttribute('data-chem-mix-unit-index')), value: el.value }))
        .sort((a,b) => a.index - b.index);
      const progress = document.querySelector('[data-chem-mix-progress]');
      if (!concentrations.length || concentrations.length !== volumes.length ||
          volumes.length !== units.length || !progress) return null;
      const visible = el => !el.disabled && el.getClientRects().length > 0 &&
        getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none';
      if (![...concentrations, ...volumes, ...units].every(item => visible(item.el)) || !visible(progress)) return null;
      return {
        request: clone(window.__CHEM_MIX_REQUEST__),
        result: clone(window.__CHEM_MIX_RESULT__),
        controls: {
          concentration_indices: concentrations.map(item => item.index),
          concentrations_mol_L: concentrations.map(item => item.value),
          volume_indices: volumes.map(item => item.index), volumes: volumes.map(item => item.value),
          unit_indices: units.map(item => item.index), volume_units: units.map(item => item.value),
          progress: progress.valueAsNumber,
        },
        displayed_equation: (document.querySelector('[data-chem-mix-equation]')?.textContent || '')
          .replace(/[₀₁₂₃₄₅₆₇₈₉]/g, ch => '₀₁₂₃₄₅₆₇₈₉'.indexOf(ch)).replace(/\s+/g, '')
      };
    };
    const titrationSnapshot = () => {
      const one = selector => document.querySelector(selector);
      const acidC = one('[data-chem-titration-acid-concentration]');
      const acidV = one('[data-chem-titration-acid-volume]');
      const acidU = one('[data-chem-titration-acid-unit]');
      const baseC = one('[data-chem-titration-base-concentration]');
      const baseV = one('[data-chem-titration-base-volume]');
      const baseU = one('[data-chem-titration-base-unit]');
      const controls = [acidC, acidV, acidU, baseC, baseV, baseU];
      const visible = el => el && !el.disabled && el.getClientRects().length > 0 &&
        getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none';
      if (!controls.every(visible)) return null;
      return {
        request: clone(window.__CHEM_TITRATION_REQUEST__),
        result: clone(window.__CHEM_TITRATION_RESULT__),
        controls: {
          acid_concentration_mol_L: acidC.valueAsNumber,
          acid_volume: acidV.valueAsNumber, acid_volume_unit: acidU.value,
          base_concentration_mol_L: baseC.valueAsNumber,
          base_volume: baseV.valueAsNumber, base_volume_unit: baseU.value,
        },
        displayed_equation: (one('[data-chem-titration-equation]')?.textContent || '')
          .replace(/[₀₁₂₃₄₅₆₇₈₉]/g, ch => '₀₁₂₃₄₅₆₇₈₉'.indexOf(ch)).replace(/\s+/g, ''),
        displayed_ph: (one('[data-chem-titration-ph]')?.textContent || '').trim(),
      };
    };
    const gasCollectionSnapshot = () => {
      const indexed = Array.from(document.querySelectorAll('[data-chem-gas-amount-index]'))
        .map(el => ({ el, index: Number(el.getAttribute('data-chem-gas-amount-index')),
          value: el.valueAsNumber }))
        .sort((a,b) => a.index - b.index);
      const progress = document.querySelector('[data-chem-gas-progress]');
      const temperature = document.querySelector('[data-chem-gas-temperature]');
      const pressure = document.querySelector('[data-chem-gas-pressure]');
      const method = document.querySelector('[data-chem-gas-method]');
      const controls = [...indexed.map(item => item.el), progress, temperature, pressure, method];
      const visible = el => el && !el.disabled && el.getClientRects().length > 0 &&
        getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none';
      if (!indexed.length || !controls.every(visible)) return null;
      const volumeText = (document.querySelector('[data-chem-gas-volume]')?.textContent || '').trim();
      return {
        request: clone(window.__CHEM_GAS_REQUEST__), result: clone(window.__CHEM_GAS_RESULT__),
        controls: { amount_indices: indexed.map(item => item.index), amounts_mol: indexed.map(item => item.value),
          progress: progress.valueAsNumber, temperature_c: temperature.valueAsNumber,
          total_pressure_kpa: pressure.valueAsNumber, collection_method: method.value },
        displayed_equation: (document.querySelector('[data-chem-gas-equation]')?.textContent || '')
          .replace(/[₀₁₂₃₄₅₆₇₈₉]/g, ch => '₀₁₂₃₄₅₆₇₈₉'.indexOf(ch)).replace(/\s+/g, ''),
        displayed_volume: volumeText,
      };
    };
    const precipitationSnapshot = () => {
      const concentrations = Array.from(document.querySelectorAll('[data-chem-precip-concentration-index]'))
        .map(el => ({ el, index: Number(el.getAttribute('data-chem-precip-concentration-index')),
          value: el.valueAsNumber })).sort((a,b) => a.index - b.index);
      const volumes = Array.from(document.querySelectorAll('[data-chem-precip-volume-index]'))
        .map(el => ({ el, index: Number(el.getAttribute('data-chem-precip-volume-index')),
          value: el.valueAsNumber })).sort((a,b) => a.index - b.index);
      const units = Array.from(document.querySelectorAll('[data-chem-precip-unit-index]'))
        .map(el => ({ el, index: Number(el.getAttribute('data-chem-precip-unit-index')),
          value: el.value })).sort((a,b) => a.index - b.index);
      const progress = document.querySelector('[data-chem-precip-progress]');
      const controls = [...concentrations.map(item => item.el), ...volumes.map(item => item.el),
        ...units.map(item => item.el), progress];
      const visible = el => el && !el.disabled && el.getClientRects().length > 0 &&
        getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none';
      if (concentrations.length !== 2 || volumes.length !== 2 || units.length !== 2 || !controls.every(visible)) return null;
      const text = selector => (document.querySelector(selector)?.textContent || '').trim();
      return {
        request: clone(window.__CHEM_PRECIP_REQUEST__), result: clone(window.__CHEM_PRECIP_RESULT__),
        controls: {
          concentration_indices: concentrations.map(item => item.index),
          concentrations_mol_L: concentrations.map(item => item.value),
          volume_indices: volumes.map(item => item.index), volumes: volumes.map(item => item.value),
          unit_indices: units.map(item => item.index), volume_units: units.map(item => item.value),
          progress: progress.valueAsNumber,
        },
        displayed_equation: text('[data-chem-precip-equation]')
          .replace(/[₀₁₂₃₄₅₆₇₈₉]/g, ch => '₀₁₂₃₄₅₆₇₈₉'.indexOf(ch)).replace(/\s+/g, ''),
        displayed_net_ionic: text('[data-chem-precip-net-ionic]').replace(/\s+/g, ''),
        displayed_mass: text('[data-chem-precip-mass]'),
      };
    };
    const redoxSnapshot = () => {
      const medium = document.querySelector('[data-chem-redox-medium]');
      const reorder = document.querySelector('[data-chem-redox-reorder]');
      const equation = document.querySelector('[data-chem-redox-equation]');
      const electrons = document.querySelector('[data-chem-redox-electrons]');
      const changes = document.querySelector('[data-chem-redox-changes]');
      const visible = el => el && el.getClientRects().length > 0 &&
        getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none';
      if (![medium, reorder, equation, electrons, changes].every(visible)) return null;
      return {
        request: clone(window.__CHEM_REDOX_REQUEST__), result: clone(window.__CHEM_REDOX_RESULT__),
        controls: { medium: (medium.value || medium.textContent || '').trim(),
          reorder_button_visible: !reorder.disabled },
        displayed_equation: (equation.textContent || '').replace(/\s+/g, ''),
        displayed_electrons: (electrons.textContent || '').trim(),
        displayed_changes: (changes.innerText || changes.textContent || '').replace(/\s+/g, ' ').trim(),
      };
    };
    const kspSnapshot = () => {
      const ksp = document.querySelector('[data-chem-ksp-value]');
      const ionInputs = Array.from(document.querySelectorAll('[data-chem-ksp-ion-index]'))
        .sort((a,b) => Number(a.getAttribute('data-chem-ksp-ion-index')) -
          Number(b.getAttribute('data-chem-ksp-ion-index')));
      const equation = document.querySelector('[data-chem-ksp-equation]');
      const q = document.querySelector('[data-chem-ksp-ion-product]');
      const state = document.querySelector('[data-chem-ksp-state]');
      const solubility = document.querySelector('[data-chem-ksp-solubility]');
      const visible = el => el && el.getClientRects().length > 0 &&
        getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none';
      if (![ksp, equation, q, state, solubility].every(visible) || ionInputs.length < 2 ||
          !ionInputs.every(visible)) return null;
      return {
        request: clone(window.__CHEM_KSP_REQUEST__), result: clone(window.__CHEM_KSP_RESULT__),
        controls: { Ksp: ksp.valueAsNumber,
          ion_indices: ionInputs.map(el => Number(el.getAttribute('data-chem-ksp-ion-index'))),
          initial_concentrations_mol_L: ionInputs.map(el => el.valueAsNumber) },
        displayed_equation: equation.textContent || '', displayed_q: q.textContent || '',
        displayed_state: state.textContent || '', displayed_solubility: solubility.textContent || '',
      };
    };
    const balanceSnapshot = () => {
      const indexed = Array.from(document.querySelectorAll('[data-chem-balance-coefficient-side]'))
        .map(el => ({ side: el.getAttribute('data-chem-balance-coefficient-side'),
          index: Number(el.getAttribute('data-chem-balance-coefficient-index')), value: el.valueAsNumber }))
        .sort((a,b) => a.side.localeCompare(b.side) || a.index - b.index);
      const values = { reactants: [], products: [] };
      for (const item of indexed) if (values[item.side]) values[item.side][item.index] = item.value;
      const output = document.querySelector('[data-chem-balance-student-check]');
      return {
        request: clone(window.__CHEM_BALANCE_REQUEST__),
        result: clone(window.__CHEM_BALANCE_RESULT__),
        student_coefficients: clone(window.__CHEM_BALANCE_STUDENT_COEFFICIENTS__) || values,
        student_check: clone(window.__CHEM_BALANCE_STUDENT_CHECK__),
        controls: indexed,
        displayed_check: output ? { text: (output.textContent || '').trim(),
          balanced: output.getAttribute('data-balanced'), primitive: output.getAttribute('data-primitive') } : null,
      };
    };
    [['DATA', window.__DATA__], ['GEO', window.__GEO__],
     ['CONFIG', window.__CONFIG__], ['EXP', window.__EXP__],
     ['CHEM_BALANCE_REQUEST', window.__CHEM_BALANCE_REQUEST__],
     ['CHEM_BALANCE_RESULT', window.__CHEM_BALANCE_RESULT__],
     ['CHEM_BALANCE_STUDENT_COEFFICIENTS', window.__CHEM_BALANCE_STUDENT_COEFFICIENTS__],
     ['CHEM_BALANCE_STUDENT_CHECK', window.__CHEM_BALANCE_STUDENT_CHECK__],
     ['CHEM_BALANCE_STUDENT_CONTROLS', balanceSnapshot().controls.length ? balanceSnapshot().controls : null],
     ['CHEM_BALANCE_DISPLAYED_EQUATION', (document.querySelector('[data-chem-balance-equation]')?.textContent || '')
       .replace(/[₀₁₂₃₄₅₆₇₈₉]/g, ch => '₀₁₂₃₄₅₆₇₈₉'.indexOf(ch)).replace(/\s+/g, '') || null],
     ['CHEM_STOICH_REQUEST', window.__CHEM_STOICH_REQUEST__],
     ['CHEM_STOICH_RESULT', window.__CHEM_STOICH_RESULT__],
     ['CHEM_STOICH_CONTROLS', (stoichSnapshot() || {}).controls],
     ['CHEM_STOICH_DISPLAYED_EQUATION', (document.querySelector('[data-chem-stoich-equation]')?.textContent || '')
       .replace(/[₀₁₂₃₄₅₆₇₈₉]/g, ch => '₀₁₂₃₄₅₆₇₈₉'.indexOf(ch)).replace(/\s+/g, '') || null],
     ['CHEM_MIX_REQUEST', window.__CHEM_MIX_REQUEST__],
     ['CHEM_MIX_RESULT', window.__CHEM_MIX_RESULT__],
     ['CHEM_MIX_CONTROLS', (mixSnapshot() || {}).controls],
     ['CHEM_MIX_DISPLAYED_EQUATION', (document.querySelector('[data-chem-mix-equation]')?.textContent || '')
       .replace(/[₀₁₂₃₄₅₆₇₈₉]/g, ch => '₀₁₂₃₄₅₆₇₈₉'.indexOf(ch)).replace(/\s+/g, '') || null],
     ['CHEM_TITRATION_REQUEST', window.__CHEM_TITRATION_REQUEST__],
     ['CHEM_TITRATION_RESULT', window.__CHEM_TITRATION_RESULT__],
     ['CHEM_TITRATION_CONTROLS', (titrationSnapshot() || {}).controls],
     ['CHEM_TITRATION_DISPLAYED_EQUATION', titrationSnapshot()?.displayed_equation || null],
     ['CHEM_TITRATION_DISPLAYED_PH', titrationSnapshot()?.displayed_ph || null],
     ['CHEM_GAS_REQUEST', window.__CHEM_GAS_REQUEST__],
     ['CHEM_GAS_RESULT', window.__CHEM_GAS_RESULT__],
     ['CHEM_GAS_CONTROLS', (gasCollectionSnapshot() || {}).controls],
     ['CHEM_GAS_DISPLAYED_EQUATION', gasCollectionSnapshot()?.displayed_equation || null],
     ['CHEM_GAS_DISPLAYED_VOLUME', gasCollectionSnapshot()?.displayed_volume || null],
     ['CHEM_PRECIP_REQUEST', window.__CHEM_PRECIP_REQUEST__],
     ['CHEM_PRECIP_RESULT', window.__CHEM_PRECIP_RESULT__],
     ['CHEM_PRECIP_CONTROLS', (precipitationSnapshot() || {}).controls],
     ['CHEM_PRECIP_DISPLAYED_EQUATION', precipitationSnapshot()?.displayed_equation || null],
     ['CHEM_PRECIP_DISPLAYED_NET_IONIC', precipitationSnapshot()?.displayed_net_ionic || null],
     ['CHEM_PRECIP_DISPLAYED_MASS', precipitationSnapshot()?.displayed_mass || null],
     ['CHEM_REDOX_REQUEST', window.__CHEM_REDOX_REQUEST__],
     ['CHEM_REDOX_RESULT', window.__CHEM_REDOX_RESULT__],
     ['CHEM_REDOX_CONTROLS', (redoxSnapshot() || {}).controls],
     ['CHEM_REDOX_DISPLAYED_EQUATION', redoxSnapshot()?.displayed_equation || null],
     ['CHEM_REDOX_DISPLAYED_ELECTRONS', redoxSnapshot()?.displayed_electrons || null],
     ['CHEM_REDOX_DISPLAYED_CHANGES', redoxSnapshot()?.displayed_changes || null],
     ['CHEM_KSP_REQUEST', window.__CHEM_KSP_REQUEST__],
     ['CHEM_KSP_RESULT', window.__CHEM_KSP_RESULT__],
     ['CHEM_KSP_CONTROLS', kspSnapshot()?.controls || null],
     ['CHEM_KSP_DISPLAYED_EQUATION', kspSnapshot()?.displayed_equation || null],
     ['CHEM_KSP_DISPLAYED_Q', kspSnapshot()?.displayed_q || null],
     ['CHEM_KSP_DISPLAYED_STATE', kspSnapshot()?.displayed_state || null],
     ['CHEM_KSP_DISPLAYED_SOLUBILITY', kspSnapshot()?.displayed_solubility || null]].forEach(([k, v]) => {
      if (v !== undefined && v !== null) { m[k] = clone(v); m.keys.push(k); m.has = true; }
    });

    // Metamorphic probes for the actual browser-bundled balancing solver.
    // They preserve the reaction while changing notation/order, so the
    // primitive coefficients and atom-count relations are independently testable.
    const balanceRequest = clone(window.__CHEM_BALANCE_REQUEST__);
    const balanceResult = clone(window.__CHEM_BALANCE_RESULT__);
    if (balanceRequest && balanceResult && window.CHEMSOLVER && typeof window.CHEMSOLVER.balanceEquation === 'function') {
      const samples = [];
      const mapSpecies = (request, transform) => ({
        reactants: request.reactants.map(transform), products: request.products.map(transform),
      });
      const getFormula = item => typeof item === 'string' ? item : item.formula;
      const replaceFormula = (item, formula) => typeof item === 'string' ? formula : { ...item, formula };
      const transformations = [
        ['uniform-formula-scaling', request => mapSpecies(request, item =>
          replaceFormula(item, '(' + getFormula(item) + ')2'))],
        ['unicode-subscript-equivalence', request => mapSpecies(request, item =>
          replaceFormula(item, getFormula(item).replace(/[0-9]/g, digit => '₀₁₂₃₄₅₆₇₈₉'[Number(digit)])))],
        ['species-reordering', request => ({
          reactants: request.reactants.slice().reverse(), products: request.products.slice().reverse(),
        })],
      ];
      for (const [kind, transform] of transformations) {
        const request = transform(clone(balanceRequest));
        try { samples.push({ kind, request, result: clone(window.CHEMSOLVER.balanceEquation(request)) }); }
        catch (error) { samples.push({ kind, request, error: String(error && error.message || error) }); }
      }

      const coefficientInputs = Array.from(document.querySelectorAll('[data-chem-balance-coefficient-side]'));
      const coefficients = balanceResult.coefficients || {};
      const hasBothSides = ['reactants', 'products'].every(side =>
        coefficientInputs.some(el => el.getAttribute('data-chem-balance-coefficient-side') === side));
      if (coefficientInputs.length && hasBothSides) {
        const originals = coefficientInputs.map(el => el.value);
        for (const input of coefficientInputs) {
          const side = input.getAttribute('data-chem-balance-coefficient-side');
          const index = Number(input.getAttribute('data-chem-balance-coefficient-index'));
          const expected = coefficients[side]?.[index];
          if (Number.isFinite(Number(expected))) input.value = String(Number(expected) * 2);
          input.dispatchEvent(new Event('input', { bubbles: true }));
          input.dispatchEvent(new Event('change', { bubbles: true }));
        }
        await new Promise(resolve => setTimeout(resolve, 30));
        const snapshot = balanceSnapshot();
        samples.push({ kind: 'student-coefficients-common-scale', ...snapshot });
        coefficientInputs.forEach((input, index) => {
          input.value = originals[index];
          input.dispatchEvent(new Event('input', { bubbles: true }));
          input.dispatchEvent(new Event('change', { bubbles: true }));
        });
        await new Promise(resolve => setTimeout(resolve, 20));
      }
      m.CHEM_BALANCE_SAMPLES = samples;
      m.keys.push('CHEM_BALANCE_SAMPLES');
    } else {
      m.CHEM_BALANCE_SAMPLES = [];
      m.keys.push('CHEM_BALANCE_SAMPLES');
    }
    const amountInputs = Array.from(document.querySelectorAll('[data-chem-stoich-amount-index]'))
      .sort((a,b) => Number(a.getAttribute('data-chem-stoich-amount-index')) -
        Number(b.getAttribute('data-chem-stoich-amount-index')));
    const progressInput = document.querySelector('[data-chem-stoich-progress]');
    if (m.CHEM_STOICH_REQUEST && m.CHEM_STOICH_RESULT && amountInputs.length && progressInput) {
      const samples = [];
      for (const input of amountInputs) {
        const original = input.value;
        const current = input.valueAsNumber;
        const min = input.min !== '' && Number.isFinite(Number(input.min)) ? Number(input.min) : 0;
        const max = input.max !== '' && Number.isFinite(Number(input.max)) ? Number(input.max) : 1000000;
        const step = input.step !== '' && input.step !== 'any' && Number.isFinite(Number(input.step)) && Number(input.step) > 0
          ? Number(input.step) : 0.01;
        let changed = current === max ? Math.max(min, current - Math.max(step, Math.abs(current) * 0.1))
          : Math.min(max, Math.max(min, current + Math.max(step, Math.abs(current) * 0.1, 0.01)));
        if (changed === current) continue;
        input.value = String(changed);
        input.dispatchEvent(new Event('input', { bubbles: true }));
        await new Promise(resolve => setTimeout(resolve, 20));
        const snapshot = stoichSnapshot();
        if (snapshot) { snapshot.kind = 'amount-change'; snapshot.changed_index = Number(input.dataset.chemStoichAmountIndex); samples.push(snapshot); }
        input.value = original;
        input.dispatchEvent(new Event('input', { bubbles: true }));
        await new Promise(resolve => setTimeout(resolve, 20));
      }
      const originalProgress = progressInput.value;
      const progressMin = progressInput.min === '' ? 0 : Number(progressInput.min);
      const progressMax = progressInput.max === '' ? 1 : Number(progressInput.max);
      const progressStates = [['progress-zero', 0], ['progress-half', 0.5], ['progress-complete', 1]];
      for (const [kind, value] of progressStates) {
        if (value < progressMin || value > progressMax) continue;
        progressInput.value = String(value);
        progressInput.dispatchEvent(new Event('input', { bubbles: true }));
        await new Promise(resolve => setTimeout(resolve, 20));
        const snapshot = stoichSnapshot();
        if (snapshot) { snapshot.kind = kind; samples.push(snapshot); }
      }
      progressInput.value = originalProgress;
      progressInput.dispatchEvent(new Event('input', { bubbles: true }));
      await new Promise(resolve => setTimeout(resolve, 20));

      // Common scaling is a true stoichiometric metamorphism: reaction ratios
      // and limiting reagents stay fixed while every amount scales together.
      const originalAmounts = amountInputs.map(input => input.value);
      const currentAmounts = amountInputs.map(input => input.valueAsNumber);
      let minScale = 0, maxScale = Infinity;
      currentAmounts.forEach((value, index) => {
        const min = amountInputs[index].min === '' ? 0 : Number(amountInputs[index].min);
        const max = amountInputs[index].max === '' ? 1000000 : Number(amountInputs[index].max);
        if (value > 0) { minScale = Math.max(minScale, min / value); maxScale = Math.min(maxScale, max / value); }
        else if (min > 0) { minScale = Infinity; maxScale = -Infinity; }
      });
      let scaleFactor = null;
      if (minScale <= maxScale) {
        if (maxScale >= 2) scaleFactor = 2;
        else if (minScale <= 0.5) scaleFactor = 0.5;
        else if (maxScale > 1 + 1e-6) scaleFactor = maxScale;
        else if (minScale < 1 - 1e-6) scaleFactor = minScale;
      }
      if (scaleFactor !== null) {
        amountInputs.forEach((input, index) => {
          input.value = String(currentAmounts[index] * scaleFactor);
          input.dispatchEvent(new Event('input', { bubbles: true }));
        });
        await new Promise(resolve => setTimeout(resolve, 30));
        const scaledSnapshot = stoichSnapshot();
        if (scaledSnapshot) {
          scaledSnapshot.kind = 'common-scaling';
          scaledSnapshot.scale_factor = scaleFactor;
          samples.push(scaledSnapshot);
        }
        amountInputs.forEach((input, index) => {
          input.value = originalAmounts[index];
          input.dispatchEvent(new Event('input', { bubbles: true }));
        });
        await new Promise(resolve => setTimeout(resolve, 20));
      }

      // Find an actually reachable ratio boundary and exercise below / exact /
      // above it through the visible numeric input (not by calling the solver).
      const coefficients = (m.CHEM_STOICH_RESULT.coefficients || {}).reactants || [];
      const baselineValues = amountInputs.map(input => input.valueAsNumber);
      let thresholdIndex = -1, threshold = 0, epsilon = 0;
      if (amountInputs.length > 1 && baselineValues.every(value => value > 0)) {
        for (let index = 0; index < amountInputs.length; index++) {
          const otherExtent = Math.min(...baselineValues.filter((_, other) => other !== index)
            .map((value, offset) => value / coefficients[offset < index ? offset : offset + 1]));
          const candidate = otherExtent * coefficients[index];
          const delta = Math.min(candidate * 0.02, candidate * 0.25);
          const min = amountInputs[index].min === '' ? 0 : Number(amountInputs[index].min);
          const max = amountInputs[index].max === '' ? 1000000 : Number(amountInputs[index].max);
          if (candidate > 0 && candidate - delta >= min && candidate + delta <= max) {
            thresholdIndex = index; threshold = candidate; epsilon = delta; break;
          }
        }
      }
      if (thresholdIndex >= 0) {
        const original = amountInputs[thresholdIndex].value;
        for (const [kind, value] of [
          ['limiting-threshold-below', threshold - epsilon],
          ['limiting-threshold-at', threshold],
          ['limiting-threshold-above', threshold + epsilon],
        ]) {
          amountInputs[thresholdIndex].value = String(value);
          amountInputs[thresholdIndex].dispatchEvent(new Event('input', { bubbles: true }));
          await new Promise(resolve => setTimeout(resolve, 25));
          const thresholdSnapshot = stoichSnapshot();
          if (thresholdSnapshot) {
            thresholdSnapshot.kind = kind;
            thresholdSnapshot.threshold_index = thresholdIndex;
            thresholdSnapshot.threshold_mol = threshold;
            samples.push(thresholdSnapshot);
          }
        }
        amountInputs[thresholdIndex].value = original;
        amountInputs[thresholdIndex].dispatchEvent(new Event('input', { bubbles: true }));
        await new Promise(resolve => setTimeout(resolve, 20));
      }
      m.CHEM_STOICH_SAMPLES = samples;
      m.keys.push('CHEM_STOICH_SAMPLES');
    }
    const mixConcentrations = Array.from(document.querySelectorAll('[data-chem-mix-concentration-index]'));
    const mixVolumes = Array.from(document.querySelectorAll('[data-chem-mix-volume-index]'));
    const mixUnits = Array.from(document.querySelectorAll('[data-chem-mix-unit-index]'));
    const mixProgress = document.querySelector('[data-chem-mix-progress]');
    if (m.CHEM_MIX_REQUEST && m.CHEM_MIX_RESULT && mixConcentrations.length &&
        mixConcentrations.length === mixVolumes.length && mixVolumes.length === mixUnits.length && mixProgress) {
      const samples = [];
      const mutateNumeric = async (input, kind) => {
        const original = input.value, current = input.valueAsNumber;
        const min = input.min !== '' && Number.isFinite(Number(input.min)) ? Number(input.min) : 0;
        const max = input.max !== '' && Number.isFinite(Number(input.max)) ? Number(input.max) : 1000000;
        const step = input.step !== '' && input.step !== 'any' && Number.isFinite(Number(input.step)) && Number(input.step) > 0
          ? Number(input.step) : 0.01;
        const changed = current === max ? Math.max(min, current - Math.max(step, Math.abs(current) * 0.1))
          : Math.min(max, Math.max(min, current + Math.max(step, Math.abs(current) * 0.1, 0.01)));
        if (!Number.isFinite(current) || changed === current) return;
        input.value = String(changed);
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
        await new Promise(resolve => setTimeout(resolve, 20));
        const snapshot = mixSnapshot();
        if (snapshot) { snapshot.kind = kind; samples.push(snapshot); }
        input.value = original;
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
        await new Promise(resolve => setTimeout(resolve, 20));
      };
      for (const input of mixConcentrations) await mutateNumeric(input, 'concentration-change');
      for (const input of mixVolumes) await mutateNumeric(input, 'volume-change');
      const volume0 = mixVolumes[0], unit0 = mixUnits[0];
      const originalVolume = volume0.value, originalUnit = unit0.value;
      if (originalVolume && (originalUnit.toLowerCase() === 'ml' || originalUnit.toLowerCase() === 'l')) {
        const equivalentVolume = originalUnit.toLowerCase() === 'ml' ? Number(originalVolume) / 1000 : Number(originalVolume) * 1000;
        const targetUnit = originalUnit.toLowerCase() === 'ml' ? 'L' : 'mL';
        const withinBounds = Number.isFinite(equivalentVolume) &&
          (volume0.min === '' || equivalentVolume >= Number(volume0.min)) &&
          (volume0.max === '' || equivalentVolume <= Number(volume0.max));
        if (withinBounds && Array.from(unit0.options || []).some(option => option.value === targetUnit)) {
          volume0.value = String(equivalentVolume); unit0.value = targetUnit;
          volume0.dispatchEvent(new Event('input', { bubbles: true }));
          volume0.dispatchEvent(new Event('change', { bubbles: true }));
          unit0.dispatchEvent(new Event('input', { bubbles: true }));
          unit0.dispatchEvent(new Event('change', { bubbles: true }));
          await new Promise(resolve => setTimeout(resolve, 20));
          const snapshot = mixSnapshot();
          if (snapshot) { snapshot.kind = 'equivalent-volume-unit'; samples.push(snapshot); }
          volume0.value = originalVolume; unit0.value = originalUnit;
          volume0.dispatchEvent(new Event('input', { bubbles: true }));
          volume0.dispatchEvent(new Event('change', { bubbles: true }));
          unit0.dispatchEvent(new Event('input', { bubbles: true }));
          unit0.dispatchEvent(new Event('change', { bubbles: true }));
          await new Promise(resolve => setTimeout(resolve, 20));
        }
      }
      await mutateNumeric(mixProgress, 'progress-change');
      m.CHEM_MIX_SAMPLES = samples;
      m.keys.push('CHEM_MIX_SAMPLES');
    }
    const titrationRequest = m.CHEM_TITRATION_REQUEST;
    const titrationControls = {
      acidC: document.querySelector('[data-chem-titration-acid-concentration]'),
      acidV: document.querySelector('[data-chem-titration-acid-volume]'),
      acidU: document.querySelector('[data-chem-titration-acid-unit]'),
      baseC: document.querySelector('[data-chem-titration-base-concentration]'),
      baseV: document.querySelector('[data-chem-titration-base-volume]'),
      baseU: document.querySelector('[data-chem-titration-base-unit]'),
    };
    if (titrationRequest && m.CHEM_TITRATION_RESULT && Object.values(titrationControls).every(Boolean)) {
      const samples = [];
      const snapshotTitration = (kind, label) => {
        const snap = titrationSnapshot();
        if (snap) { snap.kind = kind; snap.label = label || kind; samples.push(snap); }
      };
      const mutateTitrationValue = async (input, kind) => {
        const original = input.value, current = input.valueAsNumber;
        const min = input.min !== '' && Number.isFinite(Number(input.min)) ? Number(input.min) : 0;
        const max = input.max !== '' && Number.isFinite(Number(input.max)) ? Number(input.max) : 1000000;
        const step = input.step !== '' && input.step !== 'any' && Number.isFinite(Number(input.step)) && Number(input.step) > 0
          ? Number(input.step) : 0.001;
        const next = current === max ? Math.max(min, current - Math.max(step, Math.abs(current) * 0.1))
          : Math.min(max, Math.max(min, current + Math.max(step, Math.abs(current) * 0.1, 0.001)));
        if (!Number.isFinite(current) || next === current) return;
        input.value = String(next);
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
        await new Promise(resolve => setTimeout(resolve, 30));
        snapshotTitration(kind);
        input.value = original;
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
        await new Promise(resolve => setTimeout(resolve, 25));
      };
      for (const input of [titrationControls.acidC, titrationControls.acidV,
                           titrationControls.baseC, titrationControls.baseV]) {
        await mutateTitrationValue(input, 'input-change');
      }

      // Convert both actual volume controls to equivalent L values and verify
      // the rendered pH/result is invariant under the unit representation.
      const volumePairs = [[titrationControls.acidV, titrationControls.acidU],
                           [titrationControls.baseV, titrationControls.baseU]];
      const originals = volumePairs.map(([volume, unit]) => [volume.value, unit.value]);
      let canConvert = true;
      for (const [volume, unit] of volumePairs) {
        if (unit.value.toLowerCase() !== 'ml' ||
            !Array.from(unit.options || []).some(option => option.value.toLowerCase() === 'l')) canConvert = false;
        const liters = volume.valueAsNumber / 1000;
        if ((volume.min !== '' && liters < Number(volume.min)) || (volume.max !== '' && liters > Number(volume.max))) canConvert = false;
      }
      if (canConvert) {
        for (const [volume, unit] of volumePairs) {
          volume.value = String(volume.valueAsNumber / 1000);
          unit.value = Array.from(unit.options).find(option => option.value.toLowerCase() === 'l').value;
          volume.dispatchEvent(new Event('input', { bubbles: true }));
          volume.dispatchEvent(new Event('change', { bubbles: true }));
          unit.dispatchEvent(new Event('input', { bubbles: true }));
          unit.dispatchEvent(new Event('change', { bubbles: true }));
        }
        await new Promise(resolve => setTimeout(resolve, 30));
        snapshotTitration('equivalent-volume-units');
        volumePairs.forEach(([volume, unit], index) => {
          volume.value = originals[index][0]; unit.value = originals[index][1];
          volume.dispatchEvent(new Event('input', { bubbles: true }));
          volume.dispatchEvent(new Event('change', { bubbles: true }));
          unit.dispatchEvent(new Event('input', { bubbles: true }));
          unit.dispatchEvent(new Event('change', { bubbles: true }));
        });
        await new Promise(resolve => setTimeout(resolve, 25));
      }

      // Probe the threshold using the visible titrant-volume control itself.
      const baseVolume = titrationControls.baseV;
      const baseUnit = titrationControls.baseU;
      const originalVolume = baseVolume.value, originalUnit = baseUnit.value;
      const eqInUnit = Number(titrationRequest.acid.concentration_mol_L) *
        Number(titrationRequest.acid.volume) *
        (String(titrationRequest.acid.volume_unit).toLowerCase() === 'ml' ? 0.001 : 1) /
        Number(titrationRequest.base.concentration_mol_L) /
        (String(baseUnit.value).toLowerCase() === 'ml' ? 0.001 : 1);
      const delta = Math.max(Math.abs(eqInUnit) * 0.01, Number(baseVolume.step) || 0.001);
      for (const [kind, target] of [['below-equivalence', eqInUnit - delta],
                                    ['at-equivalence', eqInUnit],
                                    ['above-equivalence', eqInUnit + delta]]) {
        const min = baseVolume.min !== '' ? Number(baseVolume.min) : 0;
        const max = baseVolume.max !== '' ? Number(baseVolume.max) : 1000000;
        if (!Number.isFinite(target) || target < min || target > max) continue;
        baseVolume.value = String(target);
        baseVolume.dispatchEvent(new Event('input', { bubbles: true }));
        baseVolume.dispatchEvent(new Event('change', { bubbles: true }));
        await new Promise(resolve => setTimeout(resolve, 30));
        snapshotTitration(kind);
      }
      baseVolume.value = originalVolume; baseUnit.value = originalUnit;
      baseVolume.dispatchEvent(new Event('input', { bubbles: true }));
      baseVolume.dispatchEvent(new Event('change', { bubbles: true }));
      baseUnit.dispatchEvent(new Event('input', { bubbles: true }));
      baseUnit.dispatchEvent(new Event('change', { bubbles: true }));
      await new Promise(resolve => setTimeout(resolve, 25));
      m.CHEM_TITRATION_SAMPLES = samples;
      m.keys.push('CHEM_TITRATION_SAMPLES');
    } else {
      m.CHEM_TITRATION_SAMPLES = [];
      m.keys.push('CHEM_TITRATION_SAMPLES');
    }
    const precipRequest = m.CHEM_PRECIP_REQUEST;
    const precipControls = {
      concentrations: Array.from(document.querySelectorAll('[data-chem-precip-concentration-index]'))
        .sort((a,b) => Number(a.getAttribute('data-chem-precip-concentration-index')) - Number(b.getAttribute('data-chem-precip-concentration-index'))),
      volumes: Array.from(document.querySelectorAll('[data-chem-precip-volume-index]'))
        .sort((a,b) => Number(a.getAttribute('data-chem-precip-volume-index')) - Number(b.getAttribute('data-chem-precip-volume-index'))),
      units: Array.from(document.querySelectorAll('[data-chem-precip-unit-index]'))
        .sort((a,b) => Number(a.getAttribute('data-chem-precip-unit-index')) - Number(b.getAttribute('data-chem-precip-unit-index'))),
      progress: document.querySelector('[data-chem-precip-progress]'),
    };
    if (precipRequest && m.CHEM_PRECIP_RESULT && precipControls.concentrations.length === 2 &&
        precipControls.volumes.length === 2 && precipControls.units.length === 2 && precipControls.progress) {
      const samples = [];
      const waitPrecip = () => new Promise(resolve => setTimeout(resolve, 30));
      const firePrecip = el => {
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
      };
      const recordPrecip = async (kind, extra) => {
        await waitPrecip();
        const snap = precipitationSnapshot();
        if (snap && snap.request && snap.result) { snap.kind = kind; Object.assign(snap, extra || {}); samples.push(snap); }
      };
      const volumeOriginals = precipControls.volumes.map(el => el.value);
      const concentrationOriginals = precipControls.concentrations.map(el => el.value);
      const unitOriginals = precipControls.units.map(el => el.value);
      const progressOriginal = precipControls.progress.value;
      const inRange = (input, value) => Number.isFinite(value) &&
        value >= (input.min !== '' ? Number(input.min) : -Infinity) &&
        value <= (input.max !== '' ? Number(input.max) : Infinity);
      const setVolume = async (index, value, kind, extra) => {
        const input = precipControls.volumes[index];
        if (!inRange(input, value) || value === input.valueAsNumber) return false;
        input.value = String(value); firePrecip(input); await recordPrecip(kind, extra);
        input.value = volumeOriginals[index]; firePrecip(input); await waitPrecip();
        return true;
      };
      const volumeFactor = unit => ['mL', 'ml', '毫升'].includes(String(unit)) ? 0.001 : 1;

      // Scaling both solution volumes at fixed concentrations scales all moles and precipitate yield.
      let scale = 2;
      let scaledVolumes = precipControls.volumes.map(el => el.valueAsNumber * scale);
      if (!precipControls.volumes.every((el, i) => inRange(el, scaledVolumes[i]))) {
        scale = 0.5;
        scaledVolumes = precipControls.volumes.map(el => el.valueAsNumber * scale);
      }
      if (precipControls.volumes.every((el, i) => inRange(el, scaledVolumes[i]) && scaledVolumes[i] > 0)) {
        precipControls.volumes.forEach((el, i) => { el.value = String(scaledVolumes[i]); firePrecip(el); });
        await recordPrecip('common-volume-scale');
        precipControls.volumes.forEach((el, i) => { el.value = volumeOriginals[i]; firePrecip(el); });
        await waitPrecip();
      }

      // Express the same first-solution volume in the other supported unit.
      const unit0 = precipControls.units[0], volume0 = precipControls.volumes[0];
      const alternateUnit = unit0.value === 'L' ? 'mL' : 'L';
      const alternateOptions = Array.from(unit0.options || []).some(option => option.value === alternateUnit);
      const equivalentVolume = volume0.valueAsNumber * (alternateUnit === 'L' ? 0.001 : 1000);
      if (alternateOptions && inRange(volume0, equivalentVolume)) {
        unit0.value = alternateUnit; volume0.value = String(equivalentVolume);
        firePrecip(unit0); firePrecip(volume0); await recordPrecip('equivalent-unit');
        unit0.value = unitOriginals[0]; volume0.value = volumeOriginals[0];
        firePrecip(unit0); firePrecip(volume0); await waitPrecip();
      }

      // Concentration and reaction-progress changes must update the same solver result.
      const concentration0 = precipControls.concentrations[0];
      const requestedSolutions = precipRequest.solutions || [];
      const coeffFor = formula => {
        const normalized = String(formula || '').replace(/[₀₁₂₃₄₅₆₇₈₉]/g,
          ch => '₀₁₂₃₄₅₆₇₈₉'.indexOf(ch));
        const index = (m.CHEM_PRECIP_RESULT.reactants || []).findIndex(item => item.formula === normalized);
        return index >= 0 ? (m.CHEM_PRECIP_RESULT.coefficients.reactants || [])[index] : 0;
      };
      const n1AtBaseline = Number(requestedSolutions[1]?.concentration_mol_L) *
        Number(requestedSolutions[1]?.volume) * volumeFactor(requestedSolutions[1]?.volume_unit);
      const v0AtBaselineL = Number(requestedSolutions[0]?.volume) * volumeFactor(requestedSolutions[0]?.volume_unit);
      const targetConcentration0 = (n1AtBaseline / coeffFor(requestedSolutions[1]?.formula) *
        coeffFor(requestedSolutions[0]?.formula)) / v0AtBaselineL;
      let concentrationNext = targetConcentration0 * 0.9;
      if (!inRange(concentration0, concentrationNext)) concentrationNext = concentration0.valueAsNumber * 0.8;
      if (inRange(concentration0, concentrationNext)) {
        concentration0.value = String(concentrationNext); firePrecip(concentration0);
        await recordPrecip('concentration-change');
        concentration0.value = concentrationOriginals[0]; firePrecip(concentration0); await waitPrecip();
      }
      const progress = precipControls.progress, progressNext = progress.valueAsNumber < 0.95
        ? Math.min(1, progress.valueAsNumber + 0.1) : Math.max(0, progress.valueAsNumber - 0.1);
      if (inRange(progress, progressNext) && progressNext !== progress.valueAsNumber) {
        progress.value = String(progressNext); firePrecip(progress); await recordPrecip('progress-change');
        progress.value = progressOriginal; firePrecip(progress); await waitPrecip();
      }

      // Move one solution around the exact stoichiometric ratio, checking both limiting-reagent sides.
      const inputs = precipRequest.solutions || [], coeffs = (m.CHEM_PRECIP_RESULT.coefficients || {}).reactants || [];
      const coefficientFor = formula => {
        const index = (m.CHEM_PRECIP_RESULT.reactants || []).findIndex(item => item.formula === formula);
        return index >= 0 ? coeffs[index] : 0;
      };
      if (inputs.length === 2 && inputs.every(item => Number(item.concentration_mol_L) > 0)) {
        const amounts = inputs.map((item, i) => Number(item.concentration_mol_L) *
          Number(item.volume) * volumeFactor(item.volume_unit));
        const nu = inputs.map(item => coefficientFor(String(item.formula || '').replace(/[₀₁₂₃₄₅₆₇₈₉]/g,
          ch => '₀₁₂₃₄₅₆₇₈₉'.indexOf(ch))));
        let index = 1;
        let targetL = (amounts[0] / nu[0]) * nu[1] / Number(inputs[1].concentration_mol_L);
        let targetInput = targetL / volumeFactor(unitOriginals[1]);
        if (!inRange(precipControls.volumes[1], targetInput)) {
          index = 0;
          targetL = (amounts[1] / nu[1]) * nu[0] / Number(inputs[0].concentration_mol_L);
          targetInput = targetL / volumeFactor(unitOriginals[0]);
        }
        const targetControl = precipControls.volumes[index];
        if (nu.every(value => value > 0) && inRange(targetControl, targetInput)) {
          const changedAtThreshold = await setVolume(index, targetInput, 'stoichiometric-threshold-at',
            { threshold_input_index: index });
          if (!changedAtThreshold) await recordPrecip('stoichiometric-threshold-at', { threshold_input_index: index });
          const belowFactor = index === 1 ? 0.98 : 0.98;
          const aboveFactor = 1.02;
          await setVolume(index, targetInput * belowFactor, 'stoichiometric-threshold-below', { threshold_input_index: index });
          await setVolume(index, targetInput * aboveFactor, 'stoichiometric-threshold-above', { threshold_input_index: index });
        }
      }
      m.CHEM_PRECIP_SAMPLES = samples;
      m.keys.push('CHEM_PRECIP_SAMPLES');
    } else {
      m.CHEM_PRECIP_SAMPLES = [];
      m.keys.push('CHEM_PRECIP_SAMPLES');
    }

    const redoxRequest = m.CHEM_REDOX_REQUEST;
    const redoxButton = document.querySelector('[data-chem-redox-reorder]');
    if (redoxRequest && m.CHEM_REDOX_RESULT && redoxButton && !redoxButton.disabled) {
      const samples = [];
      redoxButton.click();
      await new Promise(resolve => setTimeout(resolve, 50));
      const snap = redoxSnapshot();
      if (snap && snap.request && snap.result) {
        snap.kind = 'species-reordering';
        samples.push(snap);
      }
      // Restore the lesson's initial order before the remaining browser checks.
      redoxButton.click();
      await new Promise(resolve => setTimeout(resolve, 50));
      const mediumControl = document.querySelector('[data-chem-redox-medium]');
      if (mediumControl instanceof HTMLSelectElement) {
        const beforeMedium = mediumControl.value;
        const alternative = Array.from(mediumControl.options).find(option =>
          !option.disabled && option.value !== beforeMedium);
        if (alternative) {
          mediumControl.value = alternative.value;
          mediumControl.dispatchEvent(new Event('input', { bubbles: true }));
          mediumControl.dispatchEvent(new Event('change', { bubbles: true }));
          await new Promise(resolve => setTimeout(resolve, 80));
          const mediumSnap = redoxSnapshot();
          if (mediumSnap && mediumSnap.request && mediumSnap.result) {
            mediumSnap.kind = 'medium-change';
            samples.push(mediumSnap);
          }
          mediumControl.value = beforeMedium;
          mediumControl.dispatchEvent(new Event('input', { bubbles: true }));
          mediumControl.dispatchEvent(new Event('change', { bubbles: true }));
          await new Promise(resolve => setTimeout(resolve, 80));
        }
      }
      m.CHEM_REDOX_SAMPLES = samples;
      m.keys.push('CHEM_REDOX_SAMPLES');
    } else {
      m.CHEM_REDOX_SAMPLES = [];
      m.keys.push('CHEM_REDOX_SAMPLES');
    }

    // Ksp metamorphic probes mutate the actual page controls, then capture
    // the request, solver result and visible readings produced by the page.
    const kspRequest = m.CHEM_KSP_REQUEST;
    const kspControls = {
      Ksp: document.querySelector('[data-chem-ksp-value]'),
      ions: Array.from(document.querySelectorAll('[data-chem-ksp-ion-index]'))
        .sort((a,b) => Number(a.getAttribute('data-chem-ksp-ion-index')) -
          Number(b.getAttribute('data-chem-ksp-ion-index'))),
    };
    if (kspRequest && m.CHEM_KSP_RESULT && window.CHEMSOLVER &&
        typeof window.CHEMSOLVER.solveSolubilityEquilibrium === 'function' &&
        kspControls.Ksp && kspControls.ions.length >= 2) {
      const samples = [];
      const originals = [kspControls.Ksp.value, ...kspControls.ions.map(el => el.value)];
      const waitKsp = () => new Promise(resolve => setTimeout(resolve, 40));
      const fireKsp = el => {
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
      };
      const recordKsp = async (kind, extra = {}) => {
        await waitKsp();
        const snap = kspSnapshot();
        if (snap && snap.request && snap.result) {
          Object.assign(snap, extra, { kind });
          samples.push(snap);
        }
      };
      const inRangeKsp = (el, value) => Number.isFinite(value) &&
        value >= (el.min !== '' ? Number(el.min) : 0) &&
        value <= (el.max !== '' ? Number(el.max) : 1e6);
      const baseResult = m.CHEM_KSP_RESULT;
      const baseSolubility = baseResult.molar_solubility_mol_L;
      const kspInput = kspControls.Ksp;
      const baseKspValue = kspInput.valueAsNumber;
      const kspMax = kspInput.max !== '' ? Number(kspInput.max) : 1e6;
      let increasedKsp = Math.min(kspMax, baseKspValue * 2);
      if (!(increasedKsp > baseKspValue)) increasedKsp = (baseKspValue + kspMax) / 2;
      if (inRangeKsp(kspInput, increasedKsp) && increasedKsp > baseKspValue) {
        kspInput.value = String(increasedKsp); fireKsp(kspInput);
        await recordKsp('ksp-increase');
        kspInput.value = originals[0]; fireKsp(kspInput); await waitKsp();
      }

      // Search for a valid increase that keeps the solution unsaturated and
      // lowers s; every candidate is previewed with the bundled solver.
      if (baseSolubility !== null && Number.isFinite(baseSolubility)) {
        const requestIons = kspRequest.ions || [];
        const totalExponent = requestIons.reduce((sum, ion) => sum + Number(ion.coefficient), 0);
        const characteristic = Math.pow(Number(kspRequest.Ksp || kspRequest.ksp), 1 / totalExponent);
        let commonCandidate = null, commonIndex = -1;
        for (let index = 0; index < Math.min(requestIons.length, kspControls.ions.length) && commonCandidate === null; index++) {
          const input = kspControls.ions[index];
          const current = input.valueAsNumber;
          const scale = Math.max(current, baseSolubility, characteristic * 0.1, 1e-12);
          for (const factor of [1.25, 2, 5, 10, 100]) {
            const candidate = current + scale * (factor - 1);
            if (!inRangeKsp(input, candidate) || !(candidate > current)) continue;
            const trial = clone(kspRequest);
            trial.ions[index].initial_concentration_mol_L = candidate;
            try {
              const trialResult = window.CHEMSOLVER.solveSolubilityEquilibrium(trial);
              if (trialResult.saturation_state !== 'supersaturated' &&
                  trialResult.molar_solubility_mol_L !== null &&
                  trialResult.molar_solubility_mol_L < baseSolubility) {
                commonCandidate = candidate; commonIndex = index; break;
              }
            } catch (_) {}
          }
        }
        if (commonCandidate !== null) {
          const input = kspControls.ions[commonIndex];
          input.value = String(commonCandidate); fireKsp(input);
          await recordKsp('common-ion-increase', { ion_index: commonIndex });
          input.value = originals[commonIndex + 1]; fireKsp(input); await waitKsp();
        }
      }

      // Put every dissolved ion at the equal-concentration saturation
      // threshold, then move one real concentration just below/at/above it.
      const thresholdRequest = clone(kspRequest);
      const thresholdIons = thresholdRequest.ions || [];
      const exponentTotal = thresholdIons.reduce((sum, ion) => sum + Number(ion.coefficient), 0);
      const thresholdKsp = Number(thresholdRequest.Ksp || thresholdRequest.ksp);
      const thresholdConcentration = Math.pow(thresholdKsp, 1 / exponentTotal);
      const thresholdFits = thresholdIons.length === kspControls.ions.length &&
        kspControls.ions.every(input => inRangeKsp(input, thresholdConcentration));
      if (thresholdFits && exponentTotal > 0 && Number.isFinite(thresholdConcentration)) {
        for (let index = 0; index < kspControls.ions.length; index++) {
          kspControls.ions[index].value = String(thresholdConcentration);
          fireKsp(kspControls.ions[index]);
        }
        await waitKsp();
        for (const [kind, factor] of [['saturation-below', 0.95], ['saturation-at', 1], ['saturation-above', 1.05]]) {
          const input = kspControls.ions[0], value = thresholdConcentration * factor;
          if (!inRangeKsp(input, value)) continue;
          input.value = String(value); fireKsp(input);
          await recordKsp(kind, { threshold_index: 0 });
          input.value = String(thresholdConcentration); fireKsp(input); await waitKsp();
        }
      }
      // Restore all physical controls and let the page return to its baseline.
      kspControls.Ksp.value = originals[0]; fireKsp(kspControls.Ksp);
      kspControls.ions.forEach((el, index) => { el.value = originals[index + 1]; fireKsp(el); });
      await waitKsp();
      m.CHEM_KSP_SAMPLES = samples;
      m.keys.push('CHEM_KSP_SAMPLES');
    } else {
      m.CHEM_KSP_SAMPLES = [];
      m.keys.push('CHEM_KSP_SAMPLES');
    }

    const gasRequest = m.CHEM_GAS_REQUEST;
    const gasControls = {
      amounts: Array.from(document.querySelectorAll('[data-chem-gas-amount-index]'))
        .sort((a,b) => Number(a.getAttribute('data-chem-gas-amount-index')) - Number(b.getAttribute('data-chem-gas-amount-index'))),
      progress: document.querySelector('[data-chem-gas-progress]'),
      temperature: document.querySelector('[data-chem-gas-temperature]'),
      pressure: document.querySelector('[data-chem-gas-pressure]'),
      method: document.querySelector('[data-chem-gas-method]'),
    };
    if (gasRequest && m.CHEM_GAS_RESULT && gasControls.amounts.length &&
        gasControls.progress && gasControls.temperature && gasControls.pressure && gasControls.method) {
      const samples = [];
      const waitGas = () => new Promise(resolve => setTimeout(resolve, 30));
      const fireGas = el => {
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
      };
      const recordGas = async kind => {
        await waitGas();
        const snap = gasCollectionSnapshot();
        if (snap && snap.request && snap.result) { snap.kind = kind; samples.push(snap); }
      };
      const amountOriginals = gasControls.amounts.map(el => el.value);
      const amountDoubles = gasControls.amounts.map(el => el.valueAsNumber * 2);
      const canScaleAmounts = gasControls.amounts.every((el, i) => Number.isFinite(amountDoubles[i]) &&
        amountDoubles[i] <= (el.max !== '' ? Number(el.max) : 1000000) &&
        amountDoubles[i] >= (el.min !== '' ? Number(el.min) : 0));
      if (canScaleAmounts) {
        gasControls.amounts.forEach((el, i) => { el.value = String(amountDoubles[i]); fireGas(el); });
        await recordGas('common-amount-scale');
        gasControls.amounts.forEach((el, i) => { el.value = amountOriginals[i]; fireGas(el); });
        await waitGas();
      }

      const mutateGasNumeric = async (input, kind, delta, semanticMin, semanticMax) => {
        const original = input.value, current = input.valueAsNumber;
        const min = Math.max(input.min !== '' ? Number(input.min) : -Infinity, semanticMin);
        const max = Math.min(input.max !== '' ? Number(input.max) : Infinity, semanticMax);
        const next = Number.isFinite(current + delta) && current + delta <= max ? current + delta : current - delta;
        if (!Number.isFinite(current) || next < min || next > max || next === current) return;
        input.value = String(next); fireGas(input);
        await recordGas(kind);
        input.value = original; fireGas(input); await waitGas();
      };
      await mutateGasNumeric(gasControls.progress, 'progress-change', 0.1, 0, 1);
      await mutateGasNumeric(gasControls.temperature, 'temperature-change', 5, 0, 100);
      await mutateGasNumeric(gasControls.pressure, 'pressure-change',
        Math.max(1, gasControls.pressure.valueAsNumber * 0.25), 1e-9, 100000);

      const originalMethod = gasControls.method.value;
      const methodOption = Array.from(gasControls.method.options || []).find(option =>
        !option.disabled && option.value !== originalMethod && ['dry', 'over_water'].includes(option.value));
      if (methodOption) {
        gasControls.method.value = methodOption.value; fireGas(gasControls.method);
        await recordGas('method-toggle');
        gasControls.method.value = originalMethod; fireGas(gasControls.method); await waitGas();
      }
      m.CHEM_GAS_SAMPLES = samples;
      m.keys.push('CHEM_GAS_SAMPLES');
    } else {
      m.CHEM_GAS_SAMPLES = [];
      m.keys.push('CHEM_GAS_SAMPLES');
    }
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

  // ---- 变形测试计划 ----
  // 审查端按 mr_catalog.py 生成 baseline / transformed 两组控件值；
  // 这里真实操作控件，并在两个状态各采一次快照（控件值、读数、机读全局量）。
  // 关系是否成立由 mr_engine.py 判定，浏览器只负责“把状态做出来并留下证据”。
  if (PLAN && Array.isArray(PLAN.scenes)) {
    result.mr.plan = PLAN;
    const captureMrSnapshot = () => page.evaluate(() => {
      const clone = value => { try { return JSON.parse(JSON.stringify(value)); } catch (e) { return null; } };
      const controls = {};
      document.querySelectorAll('[data-solver-input], [data-mr-control], [data-key]').forEach(el => {
        const key = el.dataset.mrControl || el.dataset.solverInput || el.dataset.key;
        if (!key || key in controls) return;
        if (el.type === 'checkbox') controls[key] = el.checked ? 1 : 0;
        else if (el.tagName === 'SELECT') controls[key] = el.value;
        else controls[key] = Number.isFinite(el.valueAsNumber) ? el.valueAsNumber : el.value;
      });
      const readouts = {};
      const put = (key, el) => {
        if (!key || key in readouts) return;
        if (!el.getClientRects().length || getComputedStyle(el).visibility === 'hidden') return;
        const text = (el.textContent || '').trim();
        const value = parseFloat(text.replace(/,/g, ''));
        readouts[key] = { text, value: Number.isFinite(value) ? value : null };
      };
      document.querySelectorAll('[data-circuit-current-for]').forEach(el => put('circuit:current', el));
      document.querySelectorAll('[data-circuit-voltage-for]').forEach(el => put('circuit:voltage', el));
      document.querySelectorAll('[data-solver-field]').forEach(el => put('field:' + el.dataset.solverField, el));
      document.querySelectorAll('.exp-read').forEach(el => {
        const label = el.querySelector('.k'), value = el.querySelector('.v');
        if (label && value) put('label:' + (label.textContent || '').trim(), value);
      });
      const globals = {};
      Object.keys(window).filter(name => /^__(?:CIRCUIT|MATH|CHEM|PHYS|GEO|DATA)/.test(name)).forEach(name => {
        try { globals[name] = clone(window[name]); } catch (e) { /* 忽略不可序列化对象 */ }
      });
      return { controls, readouts, globals };
    });
    const applyMrControl = (name, spec, value) => page.evaluate(({ name, selectors, value }) => {
      for (const selector of selectors || []) {
        const el = document.querySelector(selector);
        if (!el || el.disabled || el.readOnly || !el.getClientRects().length ||
            getComputedStyle(el).visibility === 'hidden') continue;
        // 把计划里的逻辑名写到 DOM 上，后续快照就能按 voltage/resistance 取值，
        // 不必猜页面原来用的是 data-key="U" 还是 data-solver-input="voltage"。
        el.setAttribute('data-mr-control', name);
        if (el.type === 'checkbox') el.checked = Boolean(Number(value));
        else el.value = String(value);
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
        return { ok: true, selector, actual: el.type === 'checkbox' ? (el.checked ? 1 : 0) : el.value };
      }
      return { ok: false };
    }, { name, selectors: spec.selectors, value });
    const initialMrValues = await page.evaluate(() => {
      const values = {};
      document.querySelectorAll('[data-solver-input], [data-mr-control], [data-key]').forEach(el => {
        const key = el.dataset.mrControl || el.dataset.solverInput || el.dataset.key;
        if (!key || key in values) return;
        values[key] = el.type === 'checkbox' ? (el.checked ? '1' : '0') : el.value;
      });
      return values;
    });
    for (const scene of PLAN.scenes) {
      const record = { id: scene.id, title: scene.title || scene.id, a: null, b: null, errors: [] };
      for (const phase of ['baseline', 'transformed']) {
        for (const [name, spec] of Object.entries(scene.controls || {})) {
          const outcome = await applyMrControl(name, spec, spec[phase]);
          if (!outcome.ok) record.errors.push('缺少可用控件：' + name);
        }
        await page.waitForTimeout(260);
        record[phase === 'baseline' ? 'a' : 'b'] = await captureMrSnapshot();
      }
      result.mr.scenes.push(record);
    }
    // 恢复初始值，避免影响后面的通用滑块检查与“重置回初态”判定。
    await page.evaluate(initial => {
      document.querySelectorAll('[data-solver-input], [data-mr-control], [data-key]').forEach(el => {
        // 计划会临时写 data-mr-control；恢复时优先找原始 key（data-key / data-solver-input），
        // 否则 tagged 元素的 voltage/u 在 initial 里不存在，会恢复失败。
        const keys = [el.dataset.mrControl, el.dataset.solverInput, el.dataset.key].filter(Boolean);
        const key = keys.find(name => name in initial);
        if (!key) return;
        if (el.type === 'checkbox') el.checked = initial[key] === '1';
        else el.value = initial[key];
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
      });
    }, initialMrValues);
    await page.waitForTimeout(220);
  }

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
    const beforeMeta = await captureSolverState();
    const info = await page.evaluate(async i => {
      const el = document.querySelectorAll('input[type=range]')[i];
      const min = parseFloat(el.min || '0'), max = parseFloat(el.max || '100');
      const oldValue = el.value;
      const target = el.value === String(max) ? min : max;
      el.value = String(target);
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
      await new Promise(r => setTimeout(r, 250));
      return { index: i, control: 'range', field: el.dataset.solverInput, oldValue, newValue: el.value };
    }, idx);
    const afterMeta = await captureSolverState();
    recordMetaMutation('range', info, beforeMeta, afterMeta);
    if (info.oldValue !== info.newValue) await captureLessonSolvers('range-' + idx, activeLessonSolvers, info);
    info.changed = before !== await visualSig();
    result.ranges.details.push(info);
    if (info.changed) result.ranges.responsive++;
    await captureCircuit('range-' + idx);
    await captureCubeCut('range-' + idx);
    await captureCylinderCut('range-' + idx);
    await captureConeCut('range-' + idx);
    await captureSphereCut('range-' + idx);
    await captureSpatialMetric('range-' + idx);
    await captureSolidVolume('range-' + idx);
    await captureCubeNet('range-' + idx);
    await captureCuboidNet('range-' + idx);
    await captureCylinderNet('range-' + idx);
    await captureConeNet('range-' + idx);
  }

  // Number inputs are common in chemistry and geometry pages; exercise them
  // too, so metamorphic coverage does not silently depend on sliders only.
  result.numberInputs.count = await page.locator('input[type="number"]').count();
  result.numberInputs.details = [];
  for (let idx = 0; idx < result.numberInputs.count; idx++) {
    const beforeMeta = await captureSolverState();
    const info = await page.evaluate(async i => {
      const el = document.querySelectorAll('input[type="number"]')[i];
      const current = el.valueAsNumber;
      const min = el.min !== '' && Number.isFinite(Number(el.min)) ? Number(el.min) : 0;
      const max = el.max !== '' && Number.isFinite(Number(el.max)) ? Number(el.max) : 1000000;
      const step = el.step !== '' && el.step !== 'any' && Number.isFinite(Number(el.step)) && Number(el.step) > 0
        ? Number(el.step) : 0.01;
      const oldValue = el.value;
      const changed = current === max
        ? Math.max(min, current - Math.max(step, Math.abs(current) * 0.1))
        : Math.min(max, Math.max(min, current + Math.max(step, Math.abs(current) * 0.1, 0.01)));
      if (!Number.isFinite(current) || changed === current) return { index: i, control: 'number', oldValue, newValue: oldValue, applicable: false };
      el.value = String(changed);
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
      await new Promise(resolve => setTimeout(resolve, 250));
      return { index: i, control: 'number', field: el.dataset.solverInput, oldValue, newValue: el.value, applicable: true };
    }, idx);
    const afterMeta = await captureSolverState();
    if (info.applicable) {
      recordMetaMutation('number', info, beforeMeta, afterMeta);
      await captureLessonSolvers('number-' + idx, activeLessonSolvers, info);
      result.numberInputs.details.push(info);
      await captureCircuit('number-' + idx);
      await captureCubeCut('number-' + idx);
      await captureCylinderCut('number-' + idx);
      await captureConeCut('number-' + idx);
      await captureSphereCut('number-' + idx);
      await captureSpatialMetric('number-' + idx);
      await captureSolidVolume('number-' + idx);
      await captureCubeNet('number-' + idx);
      await captureCuboidNet('number-' + idx);
      await captureCylinderNet('number-' + idx);
      await captureConeNet('number-' + idx);
    }
    await page.evaluate(({ i, value }) => {
      const el = document.querySelectorAll('input[type="number"]')[i];
      el.value = value;
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
    }, { i: idx, value: info.oldValue });
    await page.waitForTimeout(120);
  }

  // ---- 6b. 离散选择器：确认切换选项确实切换实验状态 ----
  result.selects.count = await page.locator('select').count();
  for (let idx = 0; idx < result.selects.count; idx++) {
    const before = await visualSig();
    const beforeMeta = await captureSolverState();
    const info = await page.evaluate(async i => {
      const el = document.querySelectorAll('select')[i];
      const original = el.value;
      const option = Array.from(el.options).find(o => !o.disabled && o.value !== original);
      if (!option) return { index: i, applicable: false, reason: '没有其他可选项' };
      el.value = option.value;
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
      await new Promise(r => setTimeout(r, 250));
      return { index: i, control: 'select', oldValue: original, newValue: el.value,
        applicable: true, selectedChanged: el.value === option.value, selected: option.value, original };
    }, idx);
    if (!info.applicable) {
      result.selects.details.push(info);
      continue;
    }
    info.updatedView = before !== await visualSig();
    info.changed = !!info.selectedChanged && info.updatedView;
    const afterMeta = await captureSolverState();
    recordMetaMutation('select', info, beforeMeta, afterMeta);
    if (info.oldValue !== info.newValue) await captureLessonSolvers('select-' + idx, activeLessonSolvers);
    await captureCircuit('select-' + idx);
    await captureCubeCut('select-' + idx);
    await captureCylinderCut('select-' + idx);
    await captureConeCut('select-' + idx);
    await captureSphereCut('select-' + idx);
    await captureSpatialMetric('select-' + idx);
    await captureSolidVolume('select-' + idx);
    await captureCubeNet('select-' + idx);
    await captureCuboidNet('select-' + idx);
    await captureCylinderNet('select-' + idx);
    await captureConeNet('select-' + idx);
    await page.evaluate(({ i, value }) => {
      const el = document.querySelectorAll('select')[i];
      el.value = value;
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
    }, { i: idx, value: info.original });
    await page.waitForTimeout(180);
    result.selects.details.push(info);
    if (info.changed) result.selects.responsive++;
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
    if (info.有响应 !== false) {
      const resetAlreadyVerified = result.reset.restored && /重置|复位|恢复初始|reset/i.test(info.按钮);
      info.有响应 = resetAlreadyVerified || before !== await visualSig();
    }
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
