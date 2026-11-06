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

  /* ============================================================
   * 浮力：烧杯 + 液体 + 斜投影物块 + 弹簧测力计 + 铁架台
   * ============================================================ */
  var FL = {
    cx: 380, base: 498, hw: 150, h: 298,   // 烧杯
    px: 12.2,                               // 每 cm 像素
    standX: 706, armY: 82
  };

  function floating(cv, cfg) {
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
    var Vcm3 = side * side * side;
    var Gwt = objRho * Vcm3 * G / 1000;                 // 重力 N
    var subFree = v.clamp(objRho / liqRho, 0, 1);       // 自由漂浮的浸没比
    // 悬挂时浸没比不能超过「浮力 = 重力」的临界值，否则绳子会松弛（物理上不成立）
    var subCap = Math.min(1, liqRho > 0 ? objRho / liqRho : 1);
    var sub = mode === 'free' ? subFree
      : v.clamp(cfg.sub == null ? 0.55 : cfg.sub, 0, Math.max(0.08, subCap));
    var Fb = liqRho * Vcm3 * sub * G / 1000;            // 浮力 N
    var reading = Math.max(0, Gwt - Fb);                // 测力计示数 N

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
      text: mode === 'free' ? '自由漂浮' : '悬挂测力',
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
      ' · ' + (mode === 'free' ? '自由漂浮' : '弹簧测力计（0~8 N）') + ' · 液体 ρ=' + liqRho.toFixed(2));
  }

  /* ============================================================
   * 凸透镜成像：光具座实景
   * ============================================================ */
  var OP = {
    x0: 56, x1: 852, railY: 470, railH: 20,
    axisY: 300, f: 10, lensAt: 45, objH: 58
  };

  function optics(cv, cfg) {
    var v = V();
    cfg = cfg || {};
    if (!v.mount(cv, { DW: DW, DH: DH })) return;
    v.clear();
    var ctx = v.S.ctx;

    var f = cfg.f == null ? OP.f : cfg.f;
    var u = cfg.u == null ? 30 : cfg.u;
    var lensAt = cfg.lensAt == null ? OP.lensAt : cfg.lensAt;
    var px = (OP.x1 - OP.x0 - 16) / 80;            // 80 cm 导轨
    function X(cm) { return OP.x0 + 8 + cm * px; }

    // 成像公式：1/u + 1/v = 1/f
    var vImg = (Math.abs(u - f) < 1e-6) ? Infinity : (u * f) / (u - f);
    var isReal = isFinite(vImg) && vImg > 0;
    var mag = isFinite(vImg) ? Math.abs(vImg / u) : 0;
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
    var fL = X(lensAt - f), fR = X(lensAt + f);

    /* ---- 三条特殊光线（先算，画在器材之下） ----
     * ① 平行主光轴入射 → 过右侧焦点 F'
     * ② 过光心 → 方向不变
     * ③ 过左侧焦点 F → 出射平行主光轴
     */
    var rays = [];
    // ① 平行入射 → 过 F'，延长到光屏
    rays.push({ pts: [[objX, objTop], [lensX, objTop], [fR, OP.axisY]], extend: true, color: '#f08a1e' });
    // ② 过光心 → 方向不变，延长到光屏
    rays.push({ pts: [[objX, objTop], [lensX, OP.axisY]], extend: true, color: '#e07b12' });
    // ③ 过 F → 出射平行主光轴（水平段必须显式给出，不能沿用前面的斜率）
    var k3 = (OP.axisY - objTop) / Math.max(1, (fL - objX));
    var y3 = objTop + k3 * (lensX - objX);
    if (objX < fL - 2) {
      rays.push({
        pts: [[objX, objTop], [fL, OP.axisY], [lensX, y3], [scrX, y3]],
        extend: false, color: 'rgba(236,140,50,0.88)'
      });
    }

    var drawn = rays.map(function (r) {
      var out = r.pts.slice();
      if (!r.extend) return out;
      var a = out[out.length - 2], b = out[out.length - 1];
      var dx = b[0] - a[0], dy = b[1] - a[1];
      if (Math.abs(dx) < 1e-6) return out;
      var t = (scrX - b[0]) / dx;
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

    // 光屏上的像（倒立）
    if (isReal && Math.abs(vImg) > 0.05) {
      var imgH = OP.objH * mag;
      var iw = v.clamp(9 * mag, 6, 15);
      ctx.save();
      var ig = ctx.createLinearGradient(scrX - iw, 0, scrX + iw, 0);
      ig.addColorStop(0, 'rgba(255,170,60,0.95)');
      ig.addColorStop(0.5, 'rgba(255,214,130,0.98)');
      ig.addColorStop(1, 'rgba(220,130,20,0.92)');
      ctx.fillStyle = ig;
      ctx.shadowColor = 'rgba(255,160,40,0.55)';
      ctx.shadowBlur = 10;
      ctx.beginPath();
      ctx.moveTo(scrX - iw * 0.42, OP.axisY);
      ctx.lineTo(scrX - iw * 0.42, OP.axisY + imgH);
      ctx.lineTo(scrX - iw, OP.axisY + imgH);
      ctx.lineTo(scrX, OP.axisY + imgH + 15);
      ctx.lineTo(scrX + iw, OP.axisY + imgH);
      ctx.lineTo(scrX + iw * 0.42, OP.axisY + imgH);
      ctx.lineTo(scrX + iw * 0.42, OP.axisY);
      ctx.closePath();
      ctx.fill();
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
    if (isReal && isFinite(vImg)) dim(lensX, scrX, 'v = ' + Math.abs(vImg).toFixed(1) + ' cm', '#157a55');

    // ---- 读数卡 ----
    v.card({
      x: 16, y: 14, w: 168, title: '成像参数',
      rows: [
        ['物距 u', u.toFixed(1) + ' cm'],
        ['焦距 f', f.toFixed(1) + ' cm'],
        ['像距 v', isFinite(vImg) ? Math.abs(vImg).toFixed(1) + ' cm' : '∞'],
        ['放大率', isFinite(mag) ? mag.toFixed(2) + '×' : '—'],
        ['性质', isReal ? '倒立实像' : (Math.abs(u - f) < 0.05 ? '不成像' : '正立虚像'),
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
      text: isFinite(vImg)
        ? (u > 2 * f ? 'u > 2f：倒立、缩小的实像'
          : Math.abs(u - 2 * f) < 0.05 ? 'u = 2f：倒立、等大的实像'
            : u > f ? 'f < u < 2f：倒立、放大的实像'
              : Math.abs(u - f) < 0.05 ? 'u = f：不成像（出射光平行）'
                : 'u < f：正立、放大的虚像（光屏上接不到）')
        : 'u = f：不成像',
      size: 15, weight: 700, color: '#134f96'
    });

    say(cv, '装置：光具座（0~80 cm）· 凸透镜 f=' + f.toFixed(0) + ' cm · 光屏 · 蜡烛，物距 ' +
      u.toFixed(1) + ' cm，' + (isReal ? '成倒立实像' : '成正立虚像'));
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
    if (window.__PHYS_DRAWN__) return;
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

  window.PHYS = { floating: floating, optics: optics, auto: auto };
})();
