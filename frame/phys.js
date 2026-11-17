/* phys.js —— 物理学科场景库（基于 vis.js 原语，外壳注入，离线可用）
 *
 * 解决的问题：物理页最容易退化成「方框 + 箭头」的示意图。
 * 这里把两类高频实验的「版面 + 光影 + 标注」固化成函数，页面只传状态量：
 *
 *   PHYS.floating(cv, {              // 浮力：阿基米德原理 / 浮沉条件
 *     objRho: 0.6,                   // 物体密度 g/cm³
 *     liqRho: 1.0,                   // 液体密度 g/cm³
 *     side: 10,                      // 正方体边长 cm
 *     level: 0.72,                   // 液面高度（占容器高度比例）
 *     mode: 'hang' | 'free',         // 悬挂测力计 / 自由漂浮
 *     sub: 0.6,                      // 悬挂时的浸没比例 0~1
 *     t: 0                           // 时间（秒），驱动波纹与气泡
 *   })
 *
 *   PHYS.optics(cv, {                // 凸透镜成像：光具座实景
 *     u: 30, f: 10, scr: 15,         // 物距 / 焦距 / 光屏位置（cm）
 *     lensAt: 45                     // 透镜在导轨上的位置 cm
 *   })
 *
 * 两个函数都会把装置描述写进 canvas 的 aria-label 与 #tip，
 * 保证「烧杯 / 物块 / 透镜 / 光屏」这些词出现在页面文字里。
 */
(function () {
  'use strict';

  // 底部公式面板已移除，设计高度收回 640，图形在画布里占得更满
  var DW = 900, DH = 640;
  var G = 10;                     // 取 g = 10 N/kg，与初中教材一致

  function V() { return window.VIS; }
  function say(cv, txt) {
    cv.setAttribute('aria-label', txt);
    var tip = document.getElementById('tip');
    if (tip) tip.textContent = txt;
  }

  // 杠杆专用绘图器：保留旧版“真实器材示意”的视觉语言，
  // 不再让杠杆场景落入通用的方块/箭头绘图器。
  function n(value, digits) {
    if (value === null || value === undefined || !isFinite(value)) return '—';
    var d = digits == null ? 2 : digits;
    var text = Number(value).toFixed(d);
    if (text.indexOf('.') >= 0) text = text.replace(/\.?0+$/, '');
    return text || '0';
  }

  function lessonLabel(v, text, x, y, opt) {
    opt = opt || {};
    var cfg = {text: String(text), x: x, y: y,
      size: opt.size || 12, weight: opt.weight || 500,
      align: opt.align || 'center', color: opt.color || '#2b3a4a'};
    if (opt.stroke === false) cfg.stroke = false;
    if (opt.pad) cfg.pad = opt.pad;
    return v.text(cfg);
  }

  function label(v, text, x, y, opt) {
    return lessonLabel(v, text, x, y, opt);
  }

  function arrowTo(ctx, x, y, dx, dy, color, width) {
    if (!isFinite(dx) || !isFinite(dy) || (Math.abs(dx) < 0.5 && Math.abs(dy) < 0.5)) return;
    var len = Math.sqrt(dx * dx + dy * dy);
    var ux = dx / len, uy = dy / len;
    var head = Math.min(12, len * 0.45);
    ctx.save(); ctx.strokeStyle = color; ctx.fillStyle = color;
    ctx.lineWidth = width || 3; ctx.lineCap = 'round';
    ctx.beginPath(); ctx.moveTo(x, y);
    ctx.lineTo(x + dx - ux * head * 0.7, y + dy - uy * head * 0.7); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(x + dx, y + dy);
    ctx.lineTo(x + dx - ux * head - uy * head * 0.42, y + dy - uy * head + ux * head * 0.42);
    ctx.lineTo(x + dx - ux * head + uy * head * 0.42, y + dy - uy * head - ux * head * 0.42);
    ctx.closePath(); ctx.fill(); ctx.restore();
  }

  function groundBand(v, y) {
    var ctx = v.S.ctx;
    ctx.save();
    var g = ctx.createLinearGradient(0, y, 0, y + 14);
    g.addColorStop(0, '#e8edf3'); g.addColorStop(0.35, '#c6ced8'); g.addColorStop(1, '#9aa4b0');
    ctx.fillStyle = g; ctx.fillRect(36, y, DW - 72, 12);
    ctx.strokeStyle = 'rgba(90,105,120,0.35)'; ctx.lineWidth = 1;
    for (var x = 44; x < DW - 44; x += 14) {
      ctx.beginPath(); ctx.moveTo(x, y + 13); ctx.lineTo(x + 7, y + 22); ctx.stroke();
    }
    ctx.restore();
  }

  function lever(cv, req, result) {
    var v = V();
    if (!v.mount(cv, {DW: DW, DH: DH})) return;
    v.clear();
    var ctx = v.S.ctx;
    v.wall({tableY: 566});
    groundBand(v, 560);
    var la = Math.max(0.01, Number(req.left_arm) || 0.01);
    var ra = Math.max(0.01, Number(req.right_arm) || 0.01);
    var net = result ? Number(result.net_torque) || 0 : 0;
    var pivotX = 450, pivotY = 300;
    var perMetre = v.clamp(280 / Math.max(la, ra), 90, 300);
    var tilt = v.clamp(net / 12, -1, 1) * 8 * Math.PI / 180;
    v.post({x: pivotX, y: pivotY + 6, base: 556});
    ctx.save(); ctx.translate(pivotX, pivotY); ctx.rotate(tilt);
    var beam = ctx.createLinearGradient(0, -10, 0, 10);
    beam.addColorStop(0, '#e4eaf1'); beam.addColorStop(0.35, '#b9c4d1');
    beam.addColorStop(0.7, '#8d99a7'); beam.addColorStop(1, '#5f6b78');
    ctx.fillStyle = beam;
    var halfW = Math.max(la, ra) * perMetre + 24;
    ctx.beginPath(); ctx.moveTo(-halfW, -8); ctx.lineTo(halfW, -8);
    ctx.lineTo(halfW, 8); ctx.lineTo(-halfW, 8); ctx.closePath(); ctx.fill();
    ctx.strokeStyle = 'rgba(70,84,98,0.4)'; ctx.lineWidth = 1; ctx.stroke();
    ctx.strokeStyle = 'rgba(70,84,98,0.5)';
    var step = perMetre * 0.1;
    for (var s = -halfW + 20; s < halfW - 12; s += step) {
      ctx.beginPath(); ctx.moveTo(s, -8); ctx.lineTo(s, -2); ctx.stroke();
    }
    function weight(xPos, force, color) {
      var side = v.clamp(Math.abs(force) / 40, 0.18, 1);
      var w = 26 + 14 * side, h = 26 + 20 * side;
      var grad = ctx.createLinearGradient(xPos - w / 2, 0, xPos + w / 2, 0);
      grad.addColorStop(0, color[0]); grad.addColorStop(0.45, color[1]); grad.addColorStop(1, color[2]);
      ctx.fillStyle = grad; ctx.beginPath();
      if (ctx.roundRect) ctx.roundRect(xPos - w / 2, 8, w, h, 5);
      else ctx.rect(xPos - w / 2, 8, w, h);
      ctx.fill(); ctx.strokeStyle = 'rgba(60,74,88,0.35)'; ctx.lineWidth = 1; ctx.stroke();
      ctx.strokeStyle = 'rgba(70,84,98,0.45)'; ctx.beginPath();
      ctx.moveTo(xPos, 8); ctx.lineTo(xPos, 8 + h); ctx.stroke();
    }
    weight(-la * perMetre, Number(req.left_force) || 0, ['#e9eff6', '#b8c6d6', '#7d8b9b']);
    weight(ra * perMetre, Number(req.right_force) || 0, ['#f2e7d8', '#d3b795', '#9b7d58']);
    ctx.restore();
    lessonLabel(v, '左力臂 ' + n(la) + ' m', pivotX - la * perMetre, 372, {size: 12});
    lessonLabel(v, '右力臂 ' + n(ra) + ' m', pivotX + ra * perMetre, 372, {size: 12});
    lessonLabel(v, '左侧 ' + n(req.left_force) + ' N', pivotX - la * perMetre, 316, {size: 12, color: '#1b62b0'});
    lessonLabel(v, '右侧 ' + n(req.right_force) + ' N', pivotX + ra * perMetre, 316, {size: 12, color: '#a3622b'});
    if (result) {
      v.pill({text: '左力矩 ' + n(result.left_torque) + ' N·m', x: 150, y: 470, size: 11});
      v.pill({text: '右力矩 ' + n(result.right_torque) + ' N·m', x: 700, y: 470, size: 11, bg: '#a3622b'});
      lessonLabel(v, String(result.state), pivotX, 214, {size: 14, weight: 600});
    }
    lessonLabel(v, '支点', pivotX, pivotY + 34, {size: 11, color: '#5b6875'});
    say(cv, '杠杆与两侧砝码，支点在中间，两侧力矩决定杠杆状态');
  }

  /* ============================================================
   * 浮力：烧杯 + 液体 + 斜投影物块 + 弹簧测力计 + 铁架台
   * ============================================================ */
  var FL = {
    cx: 380, base: 498, hw: 150, h: 298,   // 烧杯
    px: 12.2,                               // 每 cm 像素
    standX: 706, armY: 82
  };

  function floating(cv, cfg, result) {
    var v = V();
    cfg = cfg || {};
    if (!v.mount(cv, { DW: DW, DH: DH })) return;
    v.clear();
    var ctx = v.S.ctx;

    var objRho = cfg.objRho == null ? 0.60 : cfg.objRho;
    var liqRho = cfg.liqRho == null ? 1.00 : cfg.liqRho;
    var side = cfg.side == null ? 8 : cfg.side;
    var level = v.clamp(cfg.level == null ? 0.58 : cfg.level, 0.12, 0.96);
    var mode = cfg.mode === 'free' ? 'free' : 'hang';
    var t = cfg.t || 0;

    // ---- 物理量 ----
    var sub, reading;
    if (result) {
      objRho = cfg.object_density / 1000;
      liqRho = cfg.liquid_density / 1000;
      side = v.clamp(100 * Math.cbrt(cfg.volume), 1, 16);
      sub = result.fraction;
      reading = result.tension ?? 0;
    } else {
      var Vcm3 = side * side * side;
      var subFree = v.clamp(objRho / liqRho, 0, 1);
      var subCap = Math.min(1, liqRho > 0 ? objRho / liqRho : 1);
      sub = mode === 'free' ? subFree
        : v.clamp(cfg.sub == null ? 0.55 : cfg.sub, 0, Math.max(0.08, subCap));
      reading = Math.max(0, (objRho - liqRho * sub) * Vcm3 * G / 1000);
    }

    var apo = side * FL.px;
    var ySurf = FL.base - FL.h * level;
    var bottom = ySurf + sub * apo;
    var top = bottom - apo;

    // ---- 背景 ----
    v.wall({ tableY: FL.base + 2 });

    // ---- 铁架台 ----
    v.stand({ x: FL.standX, baseY: FL.base + 2, topY: 62 });
    var ag = ctx.createLinearGradient(0, FL.armY - 5, 0, FL.armY + 5);
    ag.addColorStop(0, '#d6dde5'); ag.addColorStop(0.4, '#aab6c2'); ag.addColorStop(1, '#7b8792');
    ctx.fillStyle = ag;
    v.rr(FL.cx - 7, FL.armY - 5, FL.standX - FL.cx + 7, 10, 4);
    ctx.fill();
    ctx.strokeStyle = 'rgba(80,95,110,0.35)';
    ctx.lineWidth = 1;
    ctx.stroke();

    // ---- 烧杯（背面） ----
    v.glass({ x: FL.cx, base: FL.base, hw: FL.hw, h: FL.h, kind: 'beaker', pour: true });

    // ---- 液体 ----
    var lc = cfg.liquid || {};
    v.liquid({
      level: level,
      top: lc.top || '#63c0ed',
      bot: lc.bot || '#0f63a3',
      t: t,
      ripple: true,
      bubbles: cfg.bubbles == null ? (mode === 'free' ? 5 : 0) : cfg.bubbles
    });

    // ---- 物块（斜投影，水线上下分段绘制） ----
    var mat = cfg.material || (objRho < 0.35 ? v.MAT.wood.rgb
      : objRho < 0.75 ? v.MAT.plastic.rgb
        : objRho < 1.6 ? v.MAT.glass.rgb : v.MAT.iron.rgb);
    var ox = apo * 0.28, oy = apo * 0.2;

    if (mode === 'free') v.shadow(FL.cx + 4, FL.base - 8, apo * 0.58, 7, 0.14);

    function drawBlock(tint) {
      v.box({
        x: FL.cx, y: top, w: apo, h: apo,
        ox: ox, oy: oy, color: mat, tint: tint, tintColor: '#2f8fc4',
        r: 2
      });
    }
    ctx.save();
    ctx.beginPath();
    ctx.rect(0, 0, DW, ySurf);
    ctx.clip();
    drawBlock(0);
    ctx.restore();
    ctx.save();
    ctx.beginPath();
    ctx.rect(0, ySurf, DW, DH - ySurf);
    ctx.clip();
    ctx.translate(2.2, 0);
    drawBlock(0.28);
    ctx.restore();
    ctx.beginPath();
    ctx.moveTo(FL.cx - apo / 2 - 2, ySurf);
    ctx.lineTo(FL.cx + apo / 2 + 2, ySurf);
    ctx.strokeStyle = 'rgba(255,255,255,0.82)';
    ctx.lineWidth = 1.6;
    ctx.stroke();

    // ---- 弹簧测力计（0 在上，刻度向下增大） ----
    var sTop = 100, sBot = 214;
    if (mode === 'hang') {
      ctx.beginPath();
      ctx.moveTo(FL.cx, sBot + 8);
      ctx.lineTo(FL.cx, top - oy * 0.35);
      ctx.strokeStyle = '#8a97a3';
      ctx.lineWidth = 1.6;
      ctx.stroke();
    }
    // 挂环：吊在横臂下沿（armY + 5）
    ctx.beginPath();
    ctx.arc(FL.cx, FL.armY + 10, 7, 0, Math.PI * 2);
    ctx.strokeStyle = '#8a97a3';
    ctx.lineWidth = 2.4;
    ctx.stroke();

    var sg = ctx.createLinearGradient(FL.cx - 26, 0, FL.cx + 26, 0);
    sg.addColorStop(0, '#9fb0be'); sg.addColorStop(0.22, '#eef4f9');
    sg.addColorStop(0.62, '#dbe5ee'); sg.addColorStop(1, '#9aa9b7');
    v.rr(FL.cx - 27, sTop, 54, sBot - sTop, 9);
    ctx.fillStyle = sg;
    ctx.fill();
    ctx.strokeStyle = 'rgba(110,130,148,0.75)';
    ctx.lineWidth = 1.2;
    ctx.stroke();

    // 透明观察窗
    var winTop = sTop + 9, winBot = sBot - 8;
    v.rr(FL.cx - 19, winTop, 38, winBot - winTop, 6);
    ctx.fillStyle = 'rgba(255,255,255,0.94)';
    ctx.fill();
    ctx.strokeStyle = 'rgba(150,175,196,0.7)';
    ctx.lineWidth = 1;
    ctx.stroke();

    // 刻度数字（只标 0 / 4 / 8，避免糊）
    [0, 4, 8].forEach(function (vn) {
      var vy = winTop + 5 + (vn / maxN) * (winBot - winTop - 10);
      v.text({
        x: FL.cx + 15, y: vy, text: String(vn),
        size: 8.5, weight: 700, color: '#5b7791', align: 'right', stroke: false
      });
    });

    // 刻度 0~8 N：0 在窗顶，向下增大
    var maxN = 8;
    for (var n = 0; n <= maxN * 4; n++) {
      var val = n / 4;
      var yy = winTop + 5 + (val / maxN) * (winBot - winTop - 10);
      var major = Math.abs(val - Math.round(val)) < 0.001;
      ctx.beginPath();
      ctx.moveTo(FL.cx - 18, yy);
      ctx.lineTo(FL.cx - 18 + (major ? 10 : 5), yy);
      ctx.strokeStyle = major ? 'rgba(70,92,112,0.85)' : 'rgba(70,92,112,0.32)';
      ctx.lineWidth = major ? 1.1 : 0.8;
      ctx.stroke();
    }
    // 内部弹簧：上端固定，随示数伸长
    var spTopY = winTop + 8;
    var spBotY = winTop + 5 + ((maxN - Math.min(reading, maxN)) / maxN) * (winBot - winTop - 10);
    v.spring({ x: FL.cx + 4, y1: spTopY, y2: spBotY, r: 7, coils: 12 });
    // 指针（红色三角，指向刻度）
    ctx.beginPath();
    ctx.moveTo(FL.cx - 20, spBotY);
    ctx.lineTo(FL.cx - 5, spBotY - 4);
    ctx.lineTo(FL.cx - 5, spBotY + 4);
    ctx.closePath();
    ctx.fillStyle = '#d9534f';
    ctx.fill();

    // ---- 玻璃前壁与刻度 ----
    v.glassFront({ tick: { max: 1000, step: 200, unit: '', side: 'inside', fill: 0.86 } });

    // ---- 底部公式面板：不放画布 ----
    // 演示区只留实物与图形。代入式与结论在 ④ 区（.exp-formula）已经完整给出，
    // 画布底部再铺一块公式面板属于重复，故移除。

    // ---- 读数卡：不放画布 ----
    // 字号按平台规范放大一倍后，5 行读数卡在 900×700 的设计空间里会盖住量筒左半侧；
    // 这些读数 ④ 区（.exp-reads）已经完整给出，画布上再放一份纯属重复，故移除。

    // ---- 状态标题（杯顶上方靠左，避开测力计） ----
    v.text({
      x: 226, y: 150,
      text: result ? result.state : mode === 'free' ? '自由漂浮' : '悬挂测力',
      size: 14, weight: 700, color: '#134f96'
    });

    // ---- 标注（全部最后画，绝不与器材或彼此重叠） ----
    // 物块：引线伸到杯外左侧
    // 引线走物块下半部，避开杯壁上的 800 刻度数字
    var midY = bottom - apo * 0.26;
    var blockRight = FL.cx + apo / 2 + ox;
    v.leader({ x1: 170, y1: midY, x2: FL.cx - apo / 2 - 6, y2: midY });
    v.pill({ x: 104, y: midY, text: '物块 ρ=' + objRho.toFixed(2), bg: '#3d6c92', size: 12 });

    // 液面：右侧留白处（物块右缘之外），引线落到液面
    var surfX = Math.max(blockRight + 30, FL.cx + 60);
    v.leader({ x1: surfX + 6, y1: ySurf - 44, x2: surfX - 24, y2: ySurf - 6 });
    v.pill({ x: surfX + 62, y: ySurf - 50, text: '液面 ρ=' + liqRho.toFixed(2), bg: '#1877b8', size: 12 });

    // 测力计：右侧，高度取测力计中段
    if (mode === 'hang') {
      var gy = (sTop + sBot) / 2;
      v.leader({ x1: FL.cx + 30, y1: gy, x2: 500, y2: gy });
      v.pill({ x: 592, y: gy, text: '测力计 ' + reading.toFixed(2) + ' N', bg: '#5f7183', size: 12 });
    }

    say(cv, '装置：烧杯（内装 ' + (lc.name || '液体') + '）· 物块 ρ=' + objRho.toFixed(2) +
      ' · ' + (result ? result.state : mode === 'free' ? '自由漂浮' : '弹簧测力计（0~8 N）') + ' · 液体 ρ=' + liqRho.toFixed(2));
  }

  /* ============================================================
   * 凸透镜成像：光具座实景
   * ============================================================ */
  var OP = {
    x0: 56, x1: 852, railY: 470, railH: 20,
    axisY: 300, f: 10, lensAt: 45, objH: 58
  };

  function solveThinLens(request) {
    var { u, f } = request || {};
    if (![u, f].every(value => Number.isFinite(value) && value >= 1e-6 && value <= 1e6)) {
      throw new Error('物距和焦距必须在 0.000001 至 1000000 cm 之间');
    }
    var distance = null, magnification = null, state = '无有限像';
    if (u !== f) {
      distance = u * f / (u - f);
      magnification = -distance / u;
      if (u < f) state = '正立放大的虚像';
      else if (u < 2 * f) state = '倒立放大的实像';
      else if (u === 2 * f) state = '倒立等大的实像';
      else state = '倒立缩小的实像';
    }
    return { version: 1, u: u, f: f, image_distance_cm: distance, magnification: magnification, state: state };
  }

  function optics(cv, cfg, result) {
    var v = V();
    cfg = cfg || {};
    if (!v.mount(cv, { DW: DW, DH: DH })) return;
    v.clear();
    var ctx = v.S.ctx;

    result = result || solveThinLens({ u: cfg.u ?? 30, f: cfg.f ?? OP.f });
    var { u, f, state } = result;
    var lensAt = cfg.lensAt == null ? OP.lensAt : cfg.lensAt;
    var px = (OP.x1 - OP.x0 - 16) / 80;            // 80 cm 导轨
    function X(cm) { return OP.x0 + 8 + cm * px; }

    var vImg = result.image_distance_cm;
    var hasImage = vImg !== null;
    var isReal = vImg > 0;
    var mag = Math.abs(result.magnification);
    var objTop = OP.axisY - OP.objH;

    v.wall({ tableY: OP.railY + 34, tone: 'warm' });
    v.rail({ x0: OP.x0, x1: OP.x1, y: OP.railY, h: OP.railH, px: px });

    // ---- 主光轴（点划线） ----
    ctx.save();
    ctx.beginPath();
    ctx.moveTo(30, OP.axisY);
    ctx.lineTo(866, OP.axisY);
    ctx.setLineDash([9, 6]);
    ctx.strokeStyle = 'rgba(150,190,225,0.95)';
    ctx.lineWidth = 1.3;
    ctx.stroke();
    ctx.restore();

    var objX = X(lensAt - u);
    var lensX = X(lensAt);
    var scrCm = v.clamp(cfg.scr == null ? (isReal ? lensAt + vImg : lensAt + 20) : cfg.scr, 1, 79);
    var scrX = X(scrCm);
    var imageX = hasImage ? X(lensAt + vImg) : null;
    var imageOnRail = hasImage && imageX >= X(0) && imageX <= X(80);
    var fL = X(lensAt - f), fR = X(lensAt + f);

    /* ---- 三条特殊光线（先算，画在器材之下） ----
     * ① 平行主光轴入射 → 过右侧焦点 F'
     * ② 过光心 → 方向不变
     * ③ 过左侧焦点 F → 出射平行主光轴
     */
    var rays = [];
    // ① 平行入射 → 过 F'，延长到导轨右端
    rays.push({ pts: [[objX, objTop], [lensX, objTop], [fR, OP.axisY]], extend: true, color: '#f08a1e' });
    // ② 过光心 → 方向不变，延长到导轨右端
    rays.push({ pts: [[objX, objTop], [lensX, OP.axisY]], extend: true, color: '#e07b12' });
    // ③ 过 F → 出射平行主光轴（水平段必须显式给出，不能沿用前面的斜率）
    if (objX < fL - 2) {
      var y3 = objTop + (OP.axisY - objTop) * (lensX - objX) / (fL - objX);
      if (Math.abs(y3 - OP.axisY) <= 86) {
        rays.push({
          pts: [[objX, objTop], [fL, OP.axisY], [lensX, y3], [OP.x1, y3]],
          extend: false, color: 'rgba(236,140,50,0.88)'
        });
      }
    }

    var drawn = rays.map(function (r) {
      var out = r.pts.slice();
      if (!r.extend) return out;
      var a = out[out.length - 2], b = out[out.length - 1];
      var dx = b[0] - a[0], dy = b[1] - a[1];
      if (Math.abs(dx) < 1e-6) return out;
      var t = (OP.x1 - b[0]) / dx;
      if (t > 0) out.push([b[0] + dx * t, b[1] + dy * t]);
      return out;
    });
    drawn.forEach(function (pts, i) {
      v.ray({ pts: pts, color: rays[i].color, width: i === 2 ? 1.6 : 1.9 });
    });

    // ---- 物：立体箭头（柱 + 三角头） ----
    v.post({ x: objX, y: OP.axisY, base: OP.railY + 4 });
    var headH = 18, headW = 15, shaftW = 9;
    ctx.save();
    var og = ctx.createLinearGradient(objX - headW, 0, objX + headW, 0);
    og.addColorStop(0, '#d97a06'); og.addColorStop(0.42, '#ffb04d'); og.addColorStop(1, '#c26500');
    ctx.fillStyle = og;
    ctx.shadowColor = 'rgba(255,150,40,0.38)';
    ctx.shadowBlur = 7;
    ctx.beginPath();
    ctx.moveTo(objX - shaftW / 2, OP.axisY);
    ctx.lineTo(objX - shaftW / 2, objTop);
    ctx.lineTo(objX - headW, objTop);
    ctx.lineTo(objX, objTop - headH);
    ctx.lineTo(objX + headW, objTop);
    ctx.lineTo(objX + shaftW / 2, objTop);
    ctx.lineTo(objX + shaftW / 2, OP.axisY);
    ctx.closePath();
    ctx.fill();
    ctx.restore();
    // 底座
    ctx.fillStyle = '#8a6a45';
    v.rr(objX - 14, OP.axisY - 2, 28, 8, 2);
    ctx.fill();

    // ---- 透镜 ----
    v.post({ x: lensX, y: OP.axisY, base: OP.railY + 4 });
    v.lens({ x: lensX, y: OP.axisY, h: 172, bulge: 22 });
    ctx.fillStyle = '#3a444e';
    v.rr(lensX - 10, OP.axisY - 96, 20, 11, 3); ctx.fill();
    v.rr(lensX - 10, OP.axisY + 85, 20, 11, 3); ctx.fill();

    // ---- 光屏 ----
    v.post({ x: scrX, y: OP.axisY - 98, base: OP.railY + 4 });
    var pg = ctx.createLinearGradient(scrX - 5, 0, scrX + 5, 0);
    pg.addColorStop(0, '#ffffff'); pg.addColorStop(1, '#e6edf4');
    ctx.fillStyle = pg;
    v.rr(scrX - 5, OP.axisY - 98, 10, 196, 3);
    ctx.fill();
    ctx.strokeStyle = 'rgba(150,172,192,0.9)';
    ctx.lineWidth = 1.1;
    ctx.stroke();

    // 像的位置由求解器决定。光屏移动时只改变能否接到实像。
    if (imageOnRail) {
      var imgH = OP.objH * mag * (isReal ? 1 : -1);
      var tip = OP.axisY + imgH;
      var head = Math.min(Math.abs(imgH) / 2, 12) * (isReal ? -1 : 1);
      var iw = v.clamp(9 * mag, 6, 15);
      ctx.save();
      ctx.fillStyle = '#db861f';
      ctx.strokeStyle = '#db861f';
      if (!isReal) {
        ctx.setLineDash([5, 4]);
        ctx.beginPath();
        ctx.moveTo(lensX, objTop);
        ctx.lineTo(imageX, OP.axisY - OP.objH * mag);
        ctx.moveTo(lensX, OP.axisY);
        ctx.lineTo(imageX, OP.axisY - OP.objH * mag);
        ctx.stroke();
      }
      ctx.beginPath();
      ctx.moveTo(imageX - iw * 0.42, OP.axisY);
      ctx.lineTo(imageX - iw * 0.42, tip + head);
      ctx.lineTo(imageX - iw, tip + head);
      ctx.lineTo(imageX, tip);
      ctx.lineTo(imageX + iw, tip + head);
      ctx.lineTo(imageX + iw * 0.42, tip + head);
      ctx.lineTo(imageX + iw * 0.42, OP.axisY);
      ctx.closePath();
      if (isReal) ctx.fill();
      else ctx.stroke();
      ctx.restore();
    }

    // ---- F / 2F 标记点 ----
    var marks = [];
    [[lensAt - 2 * f, '2F'], [lensAt - f, 'F'], [lensAt + f, "F'"], [lensAt + 2 * f, "2F'"]].forEach(function (m) {
      if (m[0] < 0.5 || m[0] > 79.5) return;
      v.dot({ x: X(m[0]), y: OP.axisY, r: 3.8, color: '#2e6fd8', ring: true });
      marks.push([X(m[0]), m[1]]);
    });

    // ---- 距离标注（导轨下方，文字在线的上方） ----
    var dY = OP.railY + 58;
    function dim(xa, xb, label, color) {
      ctx.save();
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.3;
      ctx.beginPath();
      ctx.moveTo(xa, dY); ctx.lineTo(xb, dY);
      ctx.stroke();
      [[xa, 1], [xb, -1]].forEach(function (p) {
        ctx.beginPath();
        ctx.moveTo(p[0], dY);
        ctx.lineTo(p[0] + p[1] * 6, dY - 4);
        ctx.lineTo(p[0] + p[1] * 6, dY + 4);
        ctx.closePath();
        ctx.fillStyle = color;
        ctx.fill();
      });
      ctx.strokeStyle = 'rgba(160,180,200,0.55)';
      ctx.setLineDash([3, 3]);
      [[xa], [xb]].forEach(function (p) {
        ctx.beginPath();
        ctx.moveTo(p[0], OP.railY + OP.railH);
        ctx.lineTo(p[0], dY + 6);
        ctx.stroke();
      });
      ctx.restore();
      v.text({ x: (xa + xb) / 2, y: dY - 15, text: label, size: 12.5, weight: 700, color: color });
    }
    dim(objX, lensX, 'u = ' + u.toFixed(1) + ' cm', '#1b62b0');
    if (imageOnRail) dim(lensX, imageX, 'v = ' + vImg.toFixed(1) + ' cm', '#157a55');

    // ---- 读数卡 ----
    v.card({
      x: 16, y: 14, w: 168, title: '成像参数',
      rows: [
        ['物距 u', u.toFixed(1) + ' cm'],
        ['焦距 f', f.toFixed(1) + ' cm'],
        ['像距 v', hasImage ? vImg.toFixed(1) + ' cm' : '∞'],
        ['放大率', hasImage ? result.magnification.toFixed(2) + '×' : '—'],
        ['性质', state,
          isReal ? '#157a55' : '#c0392b']
      ]
    });

    // ---- 文字层（最后画） ----
    marks.forEach(function (m) {
      v.text({ x: m[0], y: OP.axisY + 20, text: m[1], size: 13, weight: 700, color: '#2e6fd8' });
    });
    v.text({ x: 44, y: OP.axisY - 15, text: '主光轴', size: 12, weight: 600, color: '#7ba9d4', align: 'left' });
    v.pill({ x: objX, y: objTop - headH - 24, text: '物（' + u.toFixed(0) + ' cm）', bg: '#b8690a', size: 12 });
    v.pill({ x: lensX, y: OP.axisY - 122, text: '凸透镜 f=' + f.toFixed(0) + 'cm', bg: '#1b62b0', size: 12 });
    v.pill({ x: scrX, y: OP.axisY - 120, text: '光屏', bg: '#5f7183', size: 12 });

    v.text({
      x: 450, y: OP.railY + 104,
      text: hasImage ? state + (imageOnRail ? '' : '（像在导轨范围外）') : 'u = f：无有限像（出射光平行）',
      size: 15, weight: 700, color: '#134f96'
    });

    say(cv, '装置：光具座（0~80 cm）· 凸透镜 f=' + f.toFixed(0) + ' cm · 光屏 · 蜡烛，物距 ' +
      u.toFixed(1) + ' cm，' + state);
  }

  /* ============================================================
   * 兜底：物理页没调场景库时，按正文关键词补一版标准画面
   * ============================================================ */
  // 取第一个有数值的参数：页面给参数用的键名各页不同（rhoObj / objRho / rho…）
  function num() {
    for (var i = 0; i < arguments.length; i++) {
      var v = arguments[i];
      if (v !== null && v !== undefined && v !== '' && isFinite(v)) return +v;
    }
    return null;
  }

  /* 画布上到底有没有东西。
   *
   * 库的兜底和页面自己的 draw() 用的是**同一张画布**（不是各画一张），
   * 两边都在画 = 每次交互产生两幅互斥的版面，谁排在最后谁露脸，
   * 顺序还会逐帧漂移 → 学生看到画面闪动、背景来回换。
   * 所以只要页面已经自己画了东西，库就必须彻底收手：不画、也不挂监听。
   */
  function isBlank(cv0) {
    try {
      var w = cv0 && cv0.width, h = cv0 && cv0.height;
      if (!w || !h) return true;
      var c2 = cv0.getContext('2d');
      if (!c2) return true;
      var d = c2.getImageData(0, 0, w, h).data;
      var rowBytes = w * 4;
      // 每 16 行采一行，采到的行整行扫完：横竖线条都不会漏
      for (var y = 0; y < h; y += 16) {
        var base = y * rowBytes;
        for (var x = 0; x < w; x++) {
          var i = base + x * 4;
          if (d[i + 3] < 8) continue;                                  // 全透明 = 没画
          if (d[i] > 246 && d[i + 1] > 246 && d[i + 2] > 246) continue; // 白/近白底
          return false;
        }
      }
      return true;
    } catch (e) {
      return true;
    }
  }

  function auto() {
    if (window.__PHYS_DRAWN__ || window.__PHYS_BUOYANCY_REQUEST__ || window.__PHYS_PLANE_MIRROR_REQUEST__) return;
    var cv = document.querySelector('.exp-canvas-box canvas') || document.querySelector('canvas');
    if (!cv) return;
    var txt = (document.body ? document.body.innerText : '') + ' ' + (document.title || '');
    var cfg = window.__CONFIG__ || {};
    var sid = String(cfg.scene_id || '');
    var st = window.__DATA__ || {};
    var pr = st.params || {}, rs = st.result || {};

    // 页面自己画得出来就必须让位，否则两套版面抢同一张画布（见 isBlank 注释）
    if (!isBlank(cv)) { window.__PHYS_DRAWN__ = true; return; }

    if (/浮力|浮沉|阿基米德|排开/.test(txt) || /buoy|float/.test(sid)) {
      // ④区当前状态是「漂浮/上浮」时不该画测力计（那是悬挂法）
      var secRes = document.getElementById('sec-result');
      var stt = secRes ? String(secRes.innerText || '') : '';
      var floats = /上浮|漂浮|悬浮/.test(stt.slice(0, 120));
      var mode = (!floats && /测力计|弹簧秤/.test(txt)) ? 'hang' : 'free';

      // 参数每次现读页面自己的 __DATA__：页面改了状态就按新值重画，
      // 画布上的读数才会和 ④区 一致（不能只用库的默认边长 8 cm）
      var cfgF = function () {
        var d = window.__DATA__ || {}, p2 = d.params || {}, r2 = d.result || {};
        var o = num(p2.rhoObj, p2.objRho, p2.rho, r2.rhoObj);
        var l = num(p2.rhoLiq, p2.liqRho, p2.rhoL, r2.rhoLiq);
        var fb = num(r2.Fbuoy, r2.Fb, r2.F, r2.F浮);
        var fr = num(r2.frac, r2.subRatio, r2.sub, p2.sub, p2.frac);
        var sd = num(p2.side, p2.a, p2.edge, r2.side);
        // 体积反推：V物 → V排/浸没比 → F浮/(ρ液·浸没比·g)
        var vb = num(r2.Vobj, r2.V, r2.volume, p2.volume, p2.Vobj);
        var vs = num(r2.vsub, r2.Vsub, r2.vSub);
        if (vb == null && vs != null && fr) vb = vs / fr;
        if (vb == null && fb != null && l && fr) vb = fb * 1000 / (l * fr * G);
        if (sd == null && vb) sd = Math.pow(vb, 1 / 3);
        return {
          objRho: o == null ? 0.6 : o,
          liqRho: l == null ? 1.0 : l,
          side: sd == null ? 8 : sd,
          level: 0.62,
          mode: mode,
          sub: fr == null ? (o != null && l ? Math.min(1, o / l) : 0.6) : fr
        };
      };
      var drawF = function () { floating(cv, cfgF()); };
      drawF();
      window.__PHYS_DRAWN__ = true;
      // 页面自己的重绘（通常在 input/click 里）会盖掉库的版面，这里排在它之后补画
      var later = function () { setTimeout(drawF, 0); };
      document.addEventListener('input', later, true);
      document.addEventListener('click', later, true);
      window.addEventListener('load', function () { setTimeout(drawF, 60); });
      return;
    }
    if (/凸透镜|光具座|成像/.test(txt) || /lens|optics/.test(sid)) {
      optics(cv, { u: 30, f: 10 });
      window.__PHYS_DRAWN__ = true;
    }
  }

  /* 时机同样关键：必须等页面自己的脚本跑完、画完第一帧再判断。
   * 以前挂在 DOMContentLoaded+setTimeout(0)，页面可能还没画 → 误判空白 → 抢画布。
   * 改成 load 之后再等两帧。 */
  function scheduleAuto() {
    var run = function () {
      requestAnimationFrame(function () {
        requestAnimationFrame(function () {
          try { auto(); } catch (e) { }
        });
      });
    };
    if (document.readyState === 'complete') setTimeout(run, 60);
    else window.addEventListener('load', function () { setTimeout(run, 60); });
  }
  scheduleAuto();

  const LESSON_G = 9.8;

  function quantity(request, field, min = -1e9) {
    const value = request?.[field];
    if (!Number.isFinite(value) || value < min || value > 1e9) {
      throw new Error('参数超出模型范围：' + field);
    }
    return value;
  }

  function solveBuoyancy(request) {
    const obj = quantity(request, 'object_density', 1e-9);
    const liquid = quantity(request, 'liquid_density', 1e-9);
    const volume = quantity(request, 'volume', 1e-9);
    let fraction = quantity(request, 'fraction', 0);
    const { mode } = request;
    if (fraction > 1 || !['hang', 'free'].includes(mode)) {
      throw new Error('浸没比须在 0 至 1 之间，模式须为 hang 或 free');
    }
    const free = mode === 'free';
    if (free) fraction = Math.min(obj / liquid, 1);
    const displaced = volume * fraction;
    const weight = obj * volume * LESSON_G;
    const buoyancy = liquid * LESSON_G * displaced;
    const state = free ? (obj < liquid ? '上浮后漂浮' : obj > liquid ? '下沉' : '悬浮')
      : (fraction > obj / liquid ? '绳松弛' : '悬挂');
    return { version: 1, fraction, displaced_volume: displaced, weight, buoyancy,
      tension: free ? null : Math.max(0, weight - buoyancy), state };
  }

  function solveLever(request) {
    const left = quantity(request, 'left_force', 0) * quantity(request, 'left_arm', 0);
    const right = quantity(request, 'right_force', 0) * quantity(request, 'right_arm', 0);
    const delta = left - right;
    const net = Math.abs(delta) <= 1e-12 * Math.max(left, right) ? 0 : delta;
    return { version: 1, left_torque: left, right_torque: right, net_torque: net,
      state: net > 0 ? '左侧下沉' : net < 0 ? '右侧下沉' : '平衡' };
  }

  function solveLiquidPressure(request) {
    const density = quantity(request, 'density', 1e-9);
    const depth = quantity(request, 'depth', 0);
    return { version: 1, pressure: LESSON_G * (density * depth) };
  }

  function solveSpecificHeat(request) {
    const heat = quantity(request, 'heat');
    const initial = quantity(request, 'initial_temperature', -273.15);
    const mass = quantity(request, 'mass', 1e-9);
    const specificHeat = quantity(request, 'specific_heat', 1e-9);
    const change = heat / (mass * specificHeat);
    const final = initial + change;
    if (final < -273.15) throw new Error('温度不能低于绝对零度');
    return { version: 1, temperature_change: change, final_temperature: final };
  }

  function solveUniformAcceleration(request) {
    const v0 = quantity(request, 'initial_velocity');
    const a = quantity(request, 'acceleration');
    const duration = quantity(request, 'time', 0);
    const sample = t => [t, t * (v0 + a * t / 2), v0 + a * t];
    const trajectory = Array.from({ length: 5 }, (_, i) => sample(duration * i / 4));
    const [, displacement, velocity] = trajectory[4];
    let distance = Math.abs(displacement);
    if (v0 * velocity < 0) {
      const turningPoint = sample(-v0 / a)[1];
      distance = Math.abs(turningPoint) + Math.abs(displacement - turningPoint);
    }
    return { version: 1, velocity, displacement, distance, trajectory };
  }

  function solveHorizontalProjectile(request) {
    const speed = quantity(request, 'speed', 0);
    const height = quantity(request, 'height', 0);
    const time = quantity(request, 'time', 0);
    const flightTime = Math.sqrt(2 * height / LESSON_G);
    const elapsed = Math.min(time, flightTime);
    const sample = t => [t, speed * t, t >= flightTime ? 0 : Math.max(0, height - LESSON_G * t * t / 2)];
    const [, x, y] = sample(elapsed);
    const trajectory = Array.from({ length: 5 }, (_, i) => sample(flightTime * i / 4));
    return { version: 1, x, y, vx: speed, vy: -LESSON_G * elapsed,
      flight_time: flightTime, range: speed * flightTime,
      state: time >= flightTime ? '已到落点' : '飞行中', trajectory };
  }

  function solveRefraction(request) {
    const n1 = quantity(request, 'n1', 1);
    const n2 = quantity(request, 'n2', 1);
    const incident = quantity(request, 'incident_angle', 0);
    if (incident > 90) throw new Error('入射角须在 0 至 90 度之间');
    const radiansPerDegree = Math.PI / 180;
    const critical = n1 > n2 ? Math.asin(n2 / n1) / radiansPerDegree : null;
    let state = '折射', refracted;
    if (critical !== null && Math.abs(incident - critical) <= 1e-10) {
      state = '临界折射';
      refracted = 90;
    } else if (critical !== null && incident > critical) {
      state = '全反射';
      refracted = null;
    } else {
      const sine = n1 * Math.sin(incident * radiansPerDegree) / n2;
      refracted = n1 === n2 ? incident : Math.asin(Math.min(1, sine)) / radiansPerDegree;
    }
    return { version: 1, reflected_angle: incident, refracted_angle: refracted, critical_angle: critical, state };
  }

  function solveHorizontalForce(request) {
    const mass = quantity(request, 'mass', 1e-9);
    const applied = quantity(request, 'applied_force');
    const velocity = quantity(request, 'velocity');
    const staticMu = quantity(request, 'static_coefficient', 0);
    const kineticMu = quantity(request, 'kinetic_coefficient', 0);
    if (kineticMu > staticMu || staticMu > 1000) {
      throw new Error('摩擦系数须满足 0 ≤ 动摩擦系数 ≤ 静摩擦系数 ≤ 1000');
    }
    const weight = mass * LESSON_G;
    const normal = weight;
    const limit = staticMu * normal;
    const magnitude = Math.abs(applied);
    const tolerance = 1e-12 * Math.max(magnitude, limit);
    const atLimit = limit > 0 && Math.abs(magnitude - limit) <= tolerance;
    const atRest = velocity === 0 && (magnitude <= limit || atLimit);
    const direction = velocity === 0 ? applied : velocity;
    const friction = atRest ? -applied : -Math.sign(direction) * kineticMu * normal;
    const net = applied + friction;
    const acceleration = net / mass;
    const scale = Math.max(1, magnitude, Math.abs(friction));
    const validFriction = atRest
      ? net === 0 && Math.abs(friction) <= limit + tolerance
      : friction * Math.sign(direction) <= 0 && Math.abs(friction) === kineticMu * normal;
    if (normal - weight !== 0 || Math.abs(mass * acceleration - net) > 1e-12 * scale || !validFriction) {
      throw new Error('受力结果未通过平衡或摩擦自检');
    }
    const state = atRest ? (atLimit ? '临界静止' : '静止') : velocity === 0 ? '开始滑动' : '滑动中';
    return { version: 1, weight, normal_force: normal, static_limit: limit, friction,
      net_force: net, acceleration, state };
  }

  function solveWorkPower(request) {
    const force = quantity(request, 'force', 0);
    const distance = quantity(request, 'distance', 0);
    const angle = quantity(request, 'angle', 0);
    const duration = quantity(request, 'duration', 1e-9);
    if (angle > 180 || (force > 0 && force < 1e-9) || (distance > 0 && distance < 1e-9)) {
      throw new Error('夹角须在 0 至 180 度之间；非零力和位移至少为 1e-9');
    }
    const radiansPerDegree = Math.PI / 180;
    // Use the complementary angle near 90° to avoid cancellation.
    const projection = Math.abs(90 - angle) < 30
      ? Math.sin((90 - angle) * radiansPerDegree) : Math.cos(angle * radiansPerDegree);
    const parallelForce = force * projection;
    const work = parallelForce * distance;
    const power = work / duration;
    const expectedSign = force === 0 || distance === 0 ? 0 : Math.sign(90 - angle);
    if (Math.sign(work) !== expectedSign ||
        Math.abs(work) > force * distance * (1 + 1e-12) ||
        Math.abs(power * duration - work) > 1e-12 * Math.abs(work)) {
      throw new Error('功与功率未通过方向、大小或时间关系自检');
    }
    return { version: 1, parallel_force: parallelForce, work, average_power: power,
      state: work > 0 ? '正功' : work < 0 ? '负功' : '零功' };
  }

  // Preserve small energy transfers when two larger terms nearly cancel.
  function sumEnergyTerms(...terms) {
    let sum = 0, correction = 0;
    for (const term of terms) {
      const next = sum + term;
      correction += Math.abs(sum) >= Math.abs(term) ? (sum - next) + term : (term - next) + sum;
      sum = next;
    }
    return sum + correction;
  }

  function solveMechanicalEnergy(request) {
    const mass = quantity(request, 'mass', 1e-9);
    const speed = quantity(request, 'initial_speed', 0);
    const startHeight = quantity(request, 'start_height');
    const endHeight = quantity(request, 'end_height');
    const work = quantity(request, 'nonconservative_work');
    const weight = mass * LESSON_G;
    const initialKinetic = 0.5 * mass * (speed * speed);
    const initialPotential = weight * startHeight;
    const potentialChange = weight * (endHeight - startHeight);
    const scale = Math.max(initialKinetic, Math.abs(work), Math.abs(potentialChange));
    const available = sumEnergyTerms(initialKinetic, work, -potentialChange);
    const finalKinetic = Math.abs(available) <= 1e-12 * scale ? 0 : available;
    const possible = finalKinetic >= 0;
    const finalPotential = possible ? weight * endHeight : null;
    if (possible && Math.abs(sumEnergyTerms(finalKinetic, -initialKinetic, potentialChange, -work)) > 2e-12 * scale) {
      throw new Error('机械能变化与非保守力做功不一致');
    }
    return {
      version: 1, initial_kinetic: initialKinetic, initial_potential: initialPotential,
      initial_energy: initialKinetic + initialPotential,
      final_kinetic: possible ? finalKinetic : null, final_potential: finalPotential,
      final_energy: possible ? finalKinetic + finalPotential : null,
      energy_change: possible ? work : null,
      final_speed: possible ? Math.sqrt(finalKinetic) * Math.sqrt(2 / mass) : null,
      energy_shortfall: Math.max(0, -finalKinetic),
      state: finalKinetic > 0 ? '末速度非零' : possible ? '末速度为零' : '能量不足',
    };
  }

  function solveInclinedPlane(request) {
    const mass = quantity(request, 'mass', 1e-9);
    const length = quantity(request, 'length', 1e-9);
    const height = quantity(request, 'height', 0);
    const coefficient = quantity(request, 'friction_coefficient', 0);
    if (height > length || (height > 0 && height < 1e-9) ||
        (coefficient > 0 && coefficient < 1e-9)) {
      throw new Error('高度不能超过斜面长度，非零高度和摩擦系数至少为 1e-9');
    }
    const run = Math.sqrt((length - height) * (length + height));
    const weight = mass * LESSON_G;
    const normal = weight * (run / length);
    const friction = coefficient * normal;
    const pull = weight * (height / length) + friction;
    const useful = weight * height;
    const loss = friction * length;
    const total = pull * length;
    if (Math.abs(total - (useful + loss)) > 1e-12 * total) {
      throw new Error('斜面输入功与有用功、摩擦耗能不平衡');
    }
    return {
      version: 1, horizontal_run: run, angle_deg: Math.atan2(height, run) * (180 / Math.PI),
      normal_force: normal, friction_force: friction, pull_force: pull, useful_work: useful,
      friction_loss: loss, input_work: total, efficiency: total > 0 ? 100 * (useful / total) : null,
    };
  }

  const PULLEY_LAYOUTS = {
    fixed: { strands: 1, route: ['lower_anchor', 'fixed_pulley', 'free_end'] },
    two_fixed: { strands: 1, route: ['lower_anchor', 'fixed_pulley', 'fixed_pulley', 'free_end'] },
    two_strands: { strands: 2, route: ['upper_anchor', 'moving_pulley', 'fixed_pulley', 'free_end'] },
    three_strands: { strands: 3, route: ['lower_anchor', 'fixed_pulley', 'moving_pulley', 'free_end'] },
    four_strands: {
      strands: 4, route: ['upper_anchor', 'moving_pulley', 'fixed_pulley', 'moving_pulley', 'fixed_pulley', 'free_end'],
    },
  };

  function solvePulleySystem(request) {
    const load = quantity(request, 'load_mass', 1e-9);
    const moving = quantity(request, 'moving_mass', 0);
    const height = quantity(request, 'lift_height', 0);
    const drag = quantity(request, 'rope_loss_force', 0);
    const { layout } = request;
    if (typeof layout !== 'string' || !Object.hasOwn(PULLEY_LAYOUTS, layout)) {
      throw new Error('滑轮组绳路不在支持范围内');
    }
    if ([moving, height, drag].some(value => value > 0 && value < 1e-9)) {
      throw new Error('非零动滑轮组件质量、提升高度和绳端阻力至少为 1e-9');
    }
    const { strands, route } = PULLEY_LAYOUTS[layout];
    const loadWeight = load * LESSON_G;
    const movingWeight = moving * LESSON_G;
    const pull = (loadWeight + movingWeight) / strands + drag;
    const draw = strands * height;
    const useful = loadWeight * height;
    const carrierWork = movingWeight * height;
    const loss = drag * draw;
    const work = pull * draw;
    if (Math.abs(work - (useful + carrierWork + loss)) > 1e-12 * work) {
      throw new Error('滑轮组输入功与提升功、摩擦耗能不平衡');
    }
    return {
      version: 1, rope_route: route.slice(), supporting_strands: strands,
      fixed_pulleys: route.filter(node => node === 'fixed_pulley').length,
      moving_pulleys: route.filter(node => node === 'moving_pulley').length,
      pull_distance: draw, pull_force: pull, useful_work: useful,
      carrier_work: carrierWork, friction_loss: loss, input_work: work,
      efficiency: work > 0 ? Math.min(100, 100 * (useful / work)) : null,
    };
  }

  function drawLessonModel(canvas, request, result) {
    const vis = V();
    if (!vis.mount(canvas, {DW, DH})) return;
    vis.clear();
    const ctx = vis.S.ctx;
    const scene = request.__scene || '';
    const centerX = DW / 2;
    const centerY = DH / 2;
    const tableY = vis.wall({tableY: DH * 0.66, props: true});
    const label = (text, x, y, size = 13, color = '#1f3a52', pad = false) =>
      vis.text({text, x, y, size, color, pad});
    const tag = (text, x, y, bg = '#1b62b0') => vis.pill({text, x, y, bg, size: 12});
    const shadow = (x, y, rx, ry, alpha = 0.18) => vis.shadow(x, y, rx, ry, alpha);
    tag({lever: '杠杆平衡', pressure: '液体压强', heat: '比热容', motion: '匀变速运动',
      projectile: '平抛运动', refraction: '光的折射', horizontalForce: '受力与摩擦',
      workPower: '功与功率', mechanicalEnergy: '机械能', inclinedPlane: '斜面'}[scene] || '物理场景', 104, 38,
      scene === 'heat' ? '#b8690a' : '#1b62b0');
    const line = (x1, y1, x2, y2, color = '#35677c', width = 3, dashed = false) => {
      ctx.beginPath();
      ctx.setLineDash(dashed ? [7, 5] : []);
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.strokeStyle = color;
      ctx.lineWidth = width;
      ctx.stroke();
      ctx.setLineDash([]);
    };
    const block = (x, y, width, height, color = '#d68a68', tint = 0) =>
      vis.box({x: x + width / 2, y, w: width, h: height, color, tint});
    const forceArrow = (x1, x2, y, text, color = '#c45c2e') => {
      vis.arrow({x1, x2, y, h: 10, color});
      label(text, (x1 + x2) / 2, y - 16, 12, color, true);
    };
    if (scene === 'lever') {
      const beamY = tableY - 150;
      shadow(centerX, tableY - 10, 230, 14);
      block(centerX, beamY - 12, 610, 24, '#b77a46');
      ctx.fillStyle = '#71879a';
      ctx.beginPath(); ctx.moveTo(centerX, beamY + 12); ctx.lineTo(centerX - 34, beamY + 64);
      ctx.lineTo(centerX + 34, beamY + 64); ctx.closePath(); ctx.fill();
      ctx.strokeStyle = '#486176'; ctx.stroke();
      vis.arrow({x1: 145, x2: 270, y: beamY - 74, h: 12, color: '#c45c2e'});
      vis.arrow({x1: DW - 270, x2: DW - 145, y: beamY - 74, h: 12, color: '#2e79a4'});
      vis.box({x: 145, y: beamY - 54, w: 34, h: 42, color: '#d68767'});
      vis.box({x: DW - 145, y: beamY - 54, w: 34, h: 42, color: '#6da4c3'});
      tag('动力臂', 220, beamY - 106, '#c45c2e');
      tag('阻力臂', DW - 220, beamY - 106, '#2e79a4');
      label('支点', centerX, beamY + 82, 12, '#486176', true);
    } else if (scene === 'pressure') {
      const vessel = {x: centerX - 100, base: tableY + 4, hw: 116, h: 320, kind: 'cylinder', pour: false};
      vis.glass(vessel); vis.liquid({level: 0.74, top: '#7fd8f7', bot: '#147bb3', bubbles: 4, t: 1});
      vis.glassFront({tick: {max: 100, step: 20, unit: 'cm', fill: 0.86}});
      vis.ruler({x: centerX + 125, y: 125, h: 290, max: 1, value: Number(request.depth) || 0.5});
      label('深度 h', centerX - 172, tableY - 125, 12, '#b34d3c', true);
      vis.leader({x1: centerX - 24, y1: tableY - 100, x2: centerX - 94, y2: tableY - 152, color: '#b34d3c'});
    } else if (scene === 'heat') {
      const beaker = {x: centerX - 28, base: tableY + 4, hw: 122, h: 250, kind: 'beaker', pour: true};
      vis.glass(beaker); vis.liquid({level: 0.56, top: '#ffd08a', bot: '#d86b35', bubbles: 6, t: 2});
      vis.glassFront({tick: {max: 100, step: 20, unit: 'mL', fill: 0.8}});
      vis.stand({x: centerX + 160, baseY: tableY + 6, topY: 96});
      vis.spring({x: centerX + 160, y1: 132, y2: tableY - 50, r: 7, coils: 12});
      vis.cyl({x: centerX + 160, base: tableY - 40, rw: 12, h: 96, color: '#d9534f'});
      // 把热量箭头移到烧杯右上方，避开刻度组件在左侧绘制的「mL」单位。
      // 这样既保留“吸热”方向提示，又不会让后绘制的器材图元盖住文字。
      forceArrow(centerX + 35, centerX + 125, tableY - 200, '吸热', '#c65343');
      tag('温度变化', centerX - 54, 105, '#b8690a');
    } else if (scene === 'motion' || scene === 'projectile') {
      const railY = tableY - 22;
      vis.rail({x0: 80, x1: DW - 80, y: railY, h: 18, px: 7});
      ctx.beginPath();
      const trajectory = result.trajectory || [];
      const points = trajectory.map(item => scene === 'projectile'
        ? [90 + item[1] * 38, railY - 20 - item[2] * 28]
        : [90 + item[0] * 68, railY - 20 - item[1] * 28]);
      for (const [index, [x, y]] of points.entries()) index ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
      ctx.strokeStyle = '#2e7890'; ctx.lineWidth = 3; ctx.shadowColor = 'rgba(46,120,144,0.25)'; ctx.shadowBlur = 5; ctx.stroke(); ctx.shadowBlur = 0;
      if (points.length) { const [x, y] = points[points.length - 1]; vis.box({x, y: y - 16, w: 34, h: 34, color: '#d68767'}); vis.arrow({x1: x - 55, x2: x - 10, y, h: 10, color: '#c45c2e'}); }
      if (scene === 'projectile') tag('水平初速度', 160, 100, '#2e79a4');
      else tag('位移—时间轨迹', 170, 100, '#2e79a4');
    } else if (scene === 'refraction') {
      const boundary = centerY + 30;
      ctx.fillStyle = 'rgba(113,190,220,0.20)'; ctx.fillRect(60, boundary, DW - 120, DH - boundary - 35);
      vis.hatch({poly: [[60, boundary], [DW - 60, boundary], [DW - 60, DH - 35], [60, DH - 35]], gap: 12, color: 'rgba(46,111,216,0.14)'});
      line(60, boundary, DW - 60, boundary, '#4e7890', 2);
      line(centerX, 82, centerX, DH - 44, '#6c8791', 1.5, true);
      vis.ray({pts: [[110, 92], [centerX, boundary], [DW - 110, DH - 102]], color: '#f08a1e', width: 2.5});
      tag(result.state || '折射', centerX + 120, 100, '#1b62b0');
      label('法线', centerX + 18, 92, 12, '#5c7891', true);
    } else if (scene === 'horizontalForce' || scene === 'workPower') {
      const blockY = tableY - 78;
      vis.rail({x0: 72, x1: DW - 72, y: tableY - 18, h: 16, px: 8});
      shadow(centerX, tableY - 20, 84, 10);
      vis.box({x: centerX, y: blockY, w: 92, h: 58, color: '#d68767'});
      forceArrow(centerX + 50, centerX + 180, blockY + 26, scene === 'workPower' ? '外力 F' : '拉力 F', '#c45c2e');
      forceArrow(centerX - 180, centerX - 52, blockY + 58, scene === 'workPower' ? '位移 s' : '摩擦力 f', '#2e79a4');
      tag(scene === 'workPower' ? '功 W = F·s' : '合力与摩擦', 150, 100, '#2e79a4');
    } else if (scene === 'mechanicalEnergy') {
      const values = [result.initial_kinetic || 0, result.initial_potential || 0, result.final_kinetic || 0, result.final_potential || 0];
      const max = Math.max(1, ...values.map(value => Math.abs(value)));
      values.forEach((value, index) => {
        const height = Math.min(180, Math.abs(value) / max * 180);
        const x = 90 + index * 100;
        const y = DH - 70 - height;
        const g = ctx.createLinearGradient(x, y, x + 58, DH - 70);
        g.addColorStop(0, index < 2 ? '#cfe9f7' : '#ffd0af');
        g.addColorStop(1, index < 2 ? '#478fba' : '#c15c37');
        ctx.fillStyle = g; vis.S.ctx.fillRect(x, y, 58, height);
        ctx.strokeStyle = 'rgba(38,58,78,0.35)'; ctx.strokeRect(x, y, 58, height);
        label(['初动能', '初势能', '末动能', '末势能'][index], x + 29, DH - 44, 11, '#36566d', true);
      });
      tag('能量分配', 142, 100, '#1b62b0');
    } else if (scene === 'inclinedPlane') {
      const rampGradient = ctx.createLinearGradient(82, DH - 74, DW - 80, 112);
      rampGradient.addColorStop(0, '#dcecf2');
      rampGradient.addColorStop(0.55, '#b2c9d4');
      rampGradient.addColorStop(1, '#6f9aaa');
      ctx.fillStyle = rampGradient;
      ctx.beginPath(); ctx.moveTo(82, DH - 74); ctx.lineTo(DW - 80, DH - 74); ctx.lineTo(DW - 80, 112); ctx.closePath(); ctx.fill();
      ctx.strokeStyle = '#476978'; ctx.stroke();
      vis.hatch({poly: [[82, DH - 74], [DW - 80, DH - 74], [DW - 80, 112]], gap: 14, color: 'rgba(46,111,216,0.20)'});
      vis.box({x: centerX + 8, y: centerY - 22, w: 52, h: 38, color: '#d68767'});
      forceArrow(centerX - 50, centerX + 92, centerY - 20, '拉力 F', '#c45c2e');
      label('h', DW - 92, 150, 12, '#2e79a4', true);
      label('l', centerX + 80, DH - 92, 12, '#2e79a4', true);
      tag('有用功 / 额外功', 170, 100, '#2e79a4');
    } else {
      shadow(centerX, tableY - 18, 96, 10);
      vis.box({x: centerX, y: centerY - 36, w: 92, h: 48, color: '#7ca9c1'});
      vis.sphere({x: centerX - 116, y: centerY - 10, r: 22, color: '#d68767'});
      vis.arrow({x1: centerX - 88, x2: centerX - 48, y: centerY - 10, h: 10, color: '#c45c2e'});
      tag('物理模型', 120, 100, '#1b62b0');
    }
    const state = Object.values(result).find(value => typeof value === 'string');
    if (state) label(state, DW - 92, DH - 24, 12, '#36566d', true);
  }

  function drawPulleySystem(canvas, request, result) {
    const vis = V();
    if (!vis.mount(canvas, {DW, DH})) return;
    vis.clear();
    const ctx = vis.S.ctx;
    const tableY = vis.wall({tableY: DH * 0.72, props: true});
    const height = Number(request.lift_height) || 0;
    const top = 58;
    const bottom = Math.min(DH - 42, tableY - 18);
    const lift = Math.min(Math.max(height, 0), 8) / 8 * Math.min(150, DH * 0.28);
    const movingY = bottom - lift;
    const fixedY = top + 72;
    const anchorX = 92;
    const freeX = DW - 92;
    const pulleyRadius = Math.max(18, Math.min(30, DW / 18));
    const movingXs = result.rope_route.filter(node => node === 'moving_pulley')
      .map((_, index, items) => DW * (0.34 + (index + 1) * 0.12 / (items.length + 1)));
    const fixedXs = result.rope_route.filter(node => node === 'fixed_pulley')
      .map((_, index, items) => DW * (0.55 + (index + 1) * 0.12 / (items.length + 1)));
    let movingIndex = 0;
    let fixedIndex = 0;
    const nodes = result.rope_route.map(node => {
      if (node === 'upper_anchor') return [anchorX, top, node];
      if (node === 'lower_anchor') return [anchorX, movingY, node];
      if (node === 'free_end') return [freeX, bottom, node];
      if (node === 'moving_pulley') return [movingXs[movingIndex++], movingY, node];
      return [fixedXs[fixedIndex++], fixedY, node];
    });
    const line = (x1, y1, x2, y2, color, width, dashed = false) => {
      ctx.beginPath();
      ctx.setLineDash(dashed ? [7, 5] : []);
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.strokeStyle = color;
      ctx.lineWidth = width;
      ctx.stroke();
      ctx.setLineDash([]);
    };
    ctx.save();
    const beamGradient = ctx.createLinearGradient(46, top - 14, 46, top);
    beamGradient.addColorStop(0, '#64839a');
    beamGradient.addColorStop(0.45, '#324b61');
    beamGradient.addColorStop(1, '#1c2e3e');
    ctx.fillStyle = beamGradient;
    ctx.fillRect(46, top - 14, Math.max(120, DW - 92), 14);
    ctx.globalAlpha = 0.28;
    ctx.fillStyle = '#dcecf4';
    ctx.fillRect(46, top - 12, Math.max(120, DW - 92), 3);
    ctx.globalAlpha = 1;
    line(anchorX, top, anchorX, fixedY - pulleyRadius, '#66798b', 2, true);
    for (let index = 0; index < nodes.length - 1; index++) {
      line(nodes[index][0], nodes[index][1], nodes[index + 1][0], nodes[index + 1][1], '#c37b2b', 4);
    }
    for (const [x, y, node] of nodes) {
      if (node === 'fixed_pulley' || node === 'moving_pulley') {
        ctx.beginPath();
        ctx.arc(x, y, pulleyRadius, 0, Math.PI * 2);
        const pulleyGradient = ctx.createRadialGradient(x - pulleyRadius * 0.35, y - pulleyRadius * 0.4, 2,
          x, y, pulleyRadius);
        if (node === 'moving_pulley') {
          pulleyGradient.addColorStop(0, '#e3f5ff');
          pulleyGradient.addColorStop(0.55, '#8ab6d8');
          pulleyGradient.addColorStop(1, '#477493');
        } else {
          pulleyGradient.addColorStop(0, '#eef9e8');
          pulleyGradient.addColorStop(0.55, '#a9c4a5');
          pulleyGradient.addColorStop(1, '#5e8065');
        }
        ctx.fillStyle = pulleyGradient;
        ctx.fill();
        ctx.strokeStyle = '#36566d';
        ctx.lineWidth = 3;
        ctx.stroke();
        ctx.beginPath();
        ctx.arc(x, y, 5, 0, Math.PI * 2);
        ctx.fillStyle = '#36566d';
        ctx.fill();
      }
    }
    const loadX = movingXs.length ? movingXs[0] : anchorX;
    const loadTop = Math.min(DH - 62, movingY + pulleyRadius + 12);
    const loadGradient = ctx.createLinearGradient(loadX - 30, loadTop, loadX + 30, loadTop + 42);
    loadGradient.addColorStop(0, '#f2b08e');
    loadGradient.addColorStop(0.5, '#d9785c');
    loadGradient.addColorStop(1, '#994e46');
    ctx.fillStyle = loadGradient;
    ctx.fillRect(loadX - 30, loadTop, 60, 42);
    ctx.globalAlpha = 0.35;
    ctx.fillStyle = '#ffe6d8';
    ctx.fillRect(loadX - 26, loadTop + 4, 52, 7);
    ctx.globalAlpha = 1;
    ctx.fillStyle = '#20384d';
    ctx.font = '14px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('载荷', loadX, loadTop + 27);
    ctx.textAlign = 'left';
    ctx.fillText('上固定点', 50, 20);
    ctx.fillText('自由端', Math.max(54, freeX - 48), Math.min(DH - 24, bottom + 24));
    ctx.fillText('h = ' + (Number(request.lift_height) || 0) + ' m', 54, DH - 12);
    ctx.fillText('n = ' + result.supporting_strands + ' 承重绳段', Math.min(210, DW - 180), DH - 12);
    ctx.restore();
  }

  function solvePlaneMirror(request) {
    const distance = quantity(request, 'object_distance', 1e-9);
    const height = quantity(request, 'object_height', 0);
    const observer = quantity(request, 'observer_distance', 1e-9);
    const observerHeight = quantity(request, 'observer_height');
    const half = quantity(request, 'mirror_half_height', 1e-9);
    const imageX = -distance;
    const separation = observer - imageX;
    // Intersect the observer-to-virtual-image line with the mirror at x = 0.
    const hitAt = source => (observer * source - imageX * observerHeight) / separation;
    const baseHit = hitAt(0), tipHit = hitAt(height);
    const tolerance = 1e-12 * half;
    const full = baseHit >= -half - tolerance && tipHit <= half + tolerance;
    const overlap = baseHit <= half + tolerance && tipHit >= -half - tolerance;
    const sourceAt = edge => Math.max(0, Math.min(height, (edge * separation + imageX * observerHeight) / observer));
    const from = full ? 0 : overlap ? sourceAt(-half) : null;
    const to = full ? height : overlap ? sourceAt(half) : null;
    const rays = overlap ? Array.from(new Set([from, to]), source =>
      [source, Math.max(-half, Math.min(half, hitAt(source)))]) : [];
    for (const [source, hit] of rays) {
      const incoming = observer * (hit - source);
      const outgoing = distance * (observerHeight - hit);
      const scale = Math.max(1, separation * half, observer * source, Math.abs(distance * observerHeight));
      if (Math.abs(incoming - outgoing) > 2e-12 * scale) {
        throw new Error('光路未通过平面镜反射定律自检');
      }
    }
    return {
      version: 1, object_distance: distance, image_distance: -imageX,
      image_x: imageX, image_height: height, magnification: 1, base_hit_y: baseHit, tip_hit_y: tipHit,
      image_kind: '正立等大虚像',
      visibility: full ? '整段可见' : overlap ? '部分可见' : '不可见',
      visible_from: from, visible_to: to, visible_rays: rays,
    };
  }

  function drawPlaneMirror(canvas, request, result) {
    const vis = V();
    if (!vis.mount(canvas, {DW, DH})) return;
    vis.clear();
    const ctx = vis.S.ctx;
    vis.wall({tableY: DH * 0.72, props: true});
    const {object_distance: distance, observer_distance: eyeX,
      observer_height: eyeY, mirror_half_height: half} = request;
    const height = result.image_height;
    const xMin = result.image_x, xMax = Math.max(distance, eyeX);
    const yMin = Math.min(-half, eyeY), yMax = Math.max(half, eyeY, height);
    const scale = Math.min((DW - 80) / (xMax - xMin), (DH - 80) / (yMax - yMin));
    const x = value => DW / 2 + (value - (xMin + xMax) / 2) * scale;
    const y = value => DH / 2 - (value - (yMin + yMax) / 2) * scale;
    function line(points, color, width, dashed = false) {
      ctx.beginPath();
      ctx.setLineDash(dashed ? [7, 5] : []);
      ctx.strokeStyle = color;
      ctx.lineWidth = width;
      for (const [index, [px, py]] of points.entries()) {
        if (index === 0) ctx.moveTo(x(px), y(py));
        else ctx.lineTo(x(px), y(py));
      }
      ctx.stroke();
    }
    function point(px, py, color) {
      const cx = x(px), cy = y(py);
      const light = ctx.createRadialGradient(cx - 1.5, cy - 1.5, 0, cx, cy, 5);
      light.addColorStop(0, '#fff');
      light.addColorStop(1, color);
      ctx.beginPath();
      ctx.arc(cx, cy, 5, 0, 2 * Math.PI);
      ctx.fillStyle = light;
      ctx.fill();
    }
    ctx.save();
    const glass = ctx.createLinearGradient(x(0) - 8, 0, x(0) + 8, 0);
    glass.addColorStop(0, '#d2e0e5');
    glass.addColorStop(0.55, '#f8feff');
    glass.addColorStop(1, '#81a7b0');
    ctx.fillStyle = glass;
    ctx.fillRect(x(0) - 7, y(half), 14, y(-half) - y(half));
    for (const [source, hit] of result.visible_rays) {
      line([[distance, source], [0, hit], [eyeX, eyeY]], '#c66014', 2);
      line([[0, hit], [result.image_x, source]], '#c66014', 1.5, true);
    }
    line([[0, -half], [0, half]], '#306765', 2);
    line([[distance, 0], [distance, height]], '#1b62b0', 4);
    line([[result.image_x, 0], [result.image_x, height]], '#8653a0', 3, true);
    point(distance, height, '#1b62b0');
    point(result.image_x, height, '#8653a0');
    point(eyeX, eyeY, '#a3362b');
    ctx.restore();
  }

  function solveWavePropagation(request) {
    const frequency = quantity(request, 'frequency', 1e-9);
    const detector = quantity(request, 'detector_distance', 1e-9);
    const travel = quantity(request, 'travel_time', 1e-9);
    const observation = quantity(request, 'observation_time', 0);
    if (observation > 0 && observation < 1e-9) {
      throw new Error('非零观察时间至少为 1e-9 秒');
    }
    const speed = detector / travel;
    const period = 1 / frequency;
    const wavelength = speed / frequency;
    const front = speed * observation;
    const progress = observation / travel;
    const state = Math.abs(progress - 1) <= 1e-12 ? '刚到达' : progress < 1 ? '尚未到达' : '已到达';
    const crests = [front];
    for (let i = 1; i < 3; i++) {
      const age = observation - i * period;
      if (age >= 0) crests.push(speed * age);
    }
    const frontTolerance = 2e-12 * Math.max(front, detector);
    const validArrival = state === '刚到达' ? Math.abs(front - detector) <= frontTolerance
      : state === '尚未到达' ? front <= detector : front >= detector;
    if (!validArrival || Math.abs(wavelength * frequency - speed) > 1e-12 * speed) {
      throw new Error('波长、声速或波前到达状态未通过自检');
    }
    return {
      version: 1, frequency, speed, period, wavelength, arrival_time: travel,
      next_crest_arrival: travel + period, front_distance: front,
      arrival_state: state, crest_positions: crests,
    };
  }

  function drawWavePropagation(canvas, request, result) {
    const vis = V();
    if (!vis.mount(canvas, {DW, DH})) return;
    vis.clear();
    const ctx = vis.S.ctx;
    vis.wall({tableY: DH * 0.72, props: true});
    const detector = request.detector_distance;
    const front = result.front_distance;
    const extent = Math.max(detector, front);
    const x = distance => 55 + distance / extent * (DW - 110);
    const mid = DH / 2;
    function line(x1, y1, x2, y2, color, width) {
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.strokeStyle = color;
      ctx.lineWidth = width;
      ctx.stroke();
    }
    ctx.save();
    line(x(0), mid, x(extent), mid, '#a1aab5', 1);
    line(x(detector), mid - 130, x(detector), mid + 105, '#306765', 3);
    if (front > 0 && front / result.wavelength <= 40) {
      ctx.beginPath();
      for (let index = 0; index <= 480; index++) {
        const distance = front * index / 480;
        const height = mid - 68 * Math.cos(2 * Math.PI * (front - distance) / result.wavelength);
        if (index === 0) ctx.moveTo(x(distance), height);
        else ctx.lineTo(x(distance), height);
      }
      ctx.strokeStyle = '#1b62b0';
      ctx.lineWidth = 3;
      ctx.stroke();
    }
    for (const crest of result.crest_positions) {
      line(x(crest), mid - 69, x(crest), mid - 51, '#1b62b0', 2);
    }
    line(x(0), mid - 125, x(0), mid + 105, '#1b62b0', 4);
    line(x(front), mid - 105, x(front), mid + 45, '#b65315', 3);
    ctx.restore();
  }

  function specificHeat(cv, req, result) {
    var v = V();
    if (!v.mount(cv, {DW: DW, DH: DH})) return;
    v.clear();
    var ctx = v.S.ctx;
    v.wall({tableY: 566});
    groundBand(v, 560);
    var mass = Math.max(0.01, Number(req.mass) || 1);
    var temp = result ? Number(result.final_temperature) : Number(req.initial_temperature);
    var tempStart = Number(req.initial_temperature) || 0;
    var cx = 400, base = 540, hw = 132, h = 300;
    v.glass({x: cx, base: base, hw: hw, h: h, kind: 'beaker', pour: true});
    v.liquid({level: 0.62, t: 0,
      top: temp > 45 ? '#f0a45a' : '#7fd8f7',
      bot: temp > 45 ? '#c4632a' : '#2a86c0',
      ripple: true, bubbles: temp > 55 ? 6 : 0});

    var tx = cx + 62;
    ctx.save();
    var tube = ctx.createLinearGradient(tx - 9, 0, tx + 9, 0);
    tube.addColorStop(0, '#f4f8fc'); tube.addColorStop(0.45, '#d5dde6'); tube.addColorStop(1, '#a7b2be');
    ctx.fillStyle = tube; ctx.beginPath();
    if (ctx.roundRect) ctx.roundRect(tx - 9, 150, 18, 330, 8); else ctx.rect(tx - 9, 150, 18, 330);
    ctx.fill(); ctx.strokeStyle = 'rgba(70,84,98,0.35)'; ctx.lineWidth = 1; ctx.stroke();
    var frac = v.clamp((temp + 10) / 110, 0.02, 1);
    var topY = 470 - frac * 300;
    var merc = ctx.createLinearGradient(0, topY, 0, 480);
    merc.addColorStop(0, '#d8412f'); merc.addColorStop(1, '#8e1f14');
    ctx.fillStyle = merc; ctx.beginPath();
    if (ctx.roundRect) ctx.roundRect(tx - 4.5, topY, 9, 480 - topY, 4); else ctx.rect(tx - 4.5, topY, 9, 480 - topY);
    ctx.fill(); ctx.restore();

    v.box({x: 170, y: 500, w: 90, h: 40, color: '#7a8490'});
    arrowTo(ctx, 212, 494, 0, -54, '#d8412f', 4);
    arrowTo(ctx, 286, 494, 0, -54, '#d8412f', 4);
    label(v, '质量 ' + n(mass) + ' kg', cx - hw, 92, {size: 12, align: 'left'});
    label(v, '比热容 ' + n(req.specific_heat, 0) + ' J/(kg·K)', cx, 62, {size: 13, weight: 600});
    label(v, '热源', 215, 492, {size: 11, color: '#a3362b'});
    label(v, '末温 ' + n(temp) + ' °C', tx + 26, topY, {size: 12, align: 'left', color: '#a3362b'});
    label(v, '初温 ' + n(tempStart) + ' °C', tx - 24, 480, {size: 11, align: 'right'});
    if (result) {
      v.pill({text: 'ΔT = ' + n(result.temperature_change) + ' K', x: 700, y: 250, size: 12});
      v.pill({text: '吸热 ' + n(req.heat, 0) + ' J', x: 700, y: 300, size: 12, bg: '#a3362b'});
    }
    say(cv, '量热容器、液体、温度计与热源，显示初温与末温');
  }

  window.PHYS = { floating, optics, lever, specificHeat, solveThinLens, solveBuoyancy, solveLever, solveLiquidPressure,
    solveSpecificHeat, solveUniformAcceleration, solveHorizontalProjectile, solveRefraction,
    solveHorizontalForce, solveWorkPower, solveMechanicalEnergy, solveInclinedPlane, solvePulleySystem,
    drawLessonModel, drawPulleySystem, solvePlaneMirror, drawPlaneMirror, solveWavePropagation, drawWavePropagation, auto };
})();
