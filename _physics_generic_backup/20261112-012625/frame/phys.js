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

  function drawPulleySystem(canvas, request, result) {
    const vis = V();
    if (!vis.mount(canvas, {DW, DH})) return;
    vis.clear();
    const ctx = vis.S.ctx;
    const height = Number(request.lift_height) || 0;
    const top = 58;
    const bottom = DH - 42;
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

/* ============================================================
 * 通用实验版面（2026-11 补齐）：受力 / 能量 / 运动 / 光路 / 换算
 *
 * 每个函数都是 (cv, request, result) 签名，与 PHYS.floating / PHYS.optics 一致，
 * 页面把它们当"共享绘图组件"直接调用，因此读数与图形必然同源。
 *
 * 版面约定：
 *   · 画布 900×640，所有坐标留 ≥24px 边距；文字最后绘制，保证不被图元压住
 *   · 器材用 VIS 的 glass / box / cyl / stand / spring，材质与既有页面一致
 *   · 力、光、速度用自绘箭头（带箭头头部），箭头旁只放短标签（≤8 字）
 * ============================================================ */

var GW = 900, GH = 640;

function n(value, digits) {
  if (value === null || value === undefined || !isFinite(value)) return '—';
  var d = digits == null ? 2 : digits;
  var text = Number(value).toFixed(d);
  if (text.indexOf('.') >= 0) text = text.replace(/\.?0+$/, '');
  return text || '0';
}

/* 统一的文字入口：短标签 + 可关闭描边（深底白字时关闭，否则会糊成一团白块） */
function label(v, text, x, y, opt) {
  opt = opt || {};
  var cfg = {
    text: String(text), x: x, y: y,
    size: opt.size || 12, weight: opt.weight || 500,
    align: opt.align || 'center', color: opt.color || '#2b3a4a'
  };
  if (opt.stroke === false) cfg.stroke = false;
  if (opt.pad) cfg.pad = opt.pad;
  return v.text(cfg);
}

/* 任意方向的箭头（力、速度、光线） */
function arrowTo(ctx, x, y, dx, dy, color, width) {
  if (!isFinite(dx) || !isFinite(dy) || (Math.abs(dx) < 0.5 && Math.abs(dy) < 0.5)) return;
  var len = Math.sqrt(dx * dx + dy * dy);
  var ux = dx / len, uy = dy / len;
  var head = Math.min(12, len * 0.45);
  ctx.save();
  ctx.strokeStyle = color; ctx.fillStyle = color;
  ctx.lineWidth = width || 3; ctx.lineCap = 'round';
  ctx.beginPath();
  ctx.moveTo(x, y);
  ctx.lineTo(x + dx - ux * head * 0.7, y + dy - uy * head * 0.7);
  ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(x + dx, y + dy);
  ctx.lineTo(x + dx - ux * head - uy * head * 0.42, y + dy - uy * head + ux * head * 0.42);
  ctx.lineTo(x + dx - ux * head + uy * head * 0.42, y + dy - uy * head - ux * head * 0.42);
  ctx.closePath(); ctx.fill();
  ctx.restore();
}

/* 地面 / 桌面：渐变带 + 阴影线，避免大面积纯色块 */
function groundBand(v, y) {
  var ctx = v.S.ctx;
  ctx.save();
  var g = ctx.createLinearGradient(0, y, 0, y + 14);
  g.addColorStop(0, '#e8edf3'); g.addColorStop(0.35, '#c6ced8'); g.addColorStop(1, '#9aa4b0');
  ctx.fillStyle = g;
  ctx.fillRect(36, y, GW - 72, 12);
  ctx.strokeStyle = 'rgba(90,105,120,0.35)'; ctx.lineWidth = 1;
  for (var x = 44; x < GW - 44; x += 14) {
    ctx.beginPath(); ctx.moveTo(x, y + 13); ctx.lineTo(x + 7, y + 22); ctx.stroke();
  }
  ctx.restore();
}

/* 直角坐标框：返回像素映射函数 */
function axes(v, box, ranges, titles) {
  var ctx = v.S.ctx;
  ctx.save();
  ctx.strokeStyle = '#9aa6b3'; ctx.lineWidth = 1.4;
  ctx.strokeRect(box.x, box.y, box.w, box.h);
  ctx.strokeStyle = 'rgba(150,165,180,0.5)'; ctx.lineWidth = 1;
  for (var i = 1; i < 5; i++) {
    var gx = box.x + (box.w * i) / 5, gy = box.y + (box.h * i) / 5;
    ctx.beginPath(); ctx.moveTo(gx, box.y); ctx.lineTo(gx, box.y + box.h); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(box.x, gy); ctx.lineTo(box.x + box.w, gy); ctx.stroke();
  }
  ctx.restore();
  var fx = function (value) {
    var span = ranges.x[1] - ranges.x[0] || 1;
    return box.x + ((value - ranges.x[0]) / span) * box.w;
  };
  var fy = function (value) {
    var span = ranges.y[1] - ranges.y[0] || 1;
    return box.y + box.h - ((value - ranges.y[0]) / span) * box.h;
  };
  return { x: fx, y: fy };
}

/* ------------------------------------------------------------ 杠杆 */

function lever(cv, req, result) {
  var v = V();
  if (!v.mount(cv, { DW: GW, DH: GH })) return;
  v.clear();
  var ctx = v.S.ctx;
  v.wall({ tableY: 566 });
  groundBand(v, 560);

  var la = Math.max(0.01, Number(req.left_arm) || 0.01);
  var ra = Math.max(0.01, Number(req.right_arm) || 0.01);
  var net = result ? Number(result.net_torque) || 0 : 0;
  var pivotX = 450, pivotY = 300;
  var perMetre = v.clamp(280 / Math.max(la, ra), 90, 300);
  var tilt = v.clamp(net / 12, -1, 1) * 8 * Math.PI / 180;

  v.post({ x: pivotX, y: pivotY + 6, base: 556 });

  ctx.save();
  ctx.translate(pivotX, pivotY);
  ctx.rotate(tilt);
  var beam = ctx.createLinearGradient(0, -10, 0, 10);
  beam.addColorStop(0, '#e4eaf1'); beam.addColorStop(0.35, '#b9c4d1');
  beam.addColorStop(0.7, '#8d99a7'); beam.addColorStop(1, '#5f6b78');
  ctx.fillStyle = beam;
  var halfW = Math.max(la, ra) * perMetre + 24;
  ctx.beginPath();
  ctx.moveTo(-halfW, -8); ctx.lineTo(halfW, -8);
  ctx.lineTo(halfW, 8); ctx.lineTo(-halfW, 8); ctx.closePath();
  ctx.fill();
  ctx.strokeStyle = 'rgba(70,84,98,0.4)'; ctx.lineWidth = 1; ctx.stroke();

  ctx.strokeStyle = 'rgba(70,84,98,0.5)';
  var step = perMetre * 0.1;
  for (var s = -halfW + 20; s < halfW - 12; s += step) {
    ctx.beginPath(); ctx.moveTo(s, -8); ctx.lineTo(s, -2); ctx.stroke();
  }

  function weight(xPos, force, color) {
    var side = v.clamp(Math.abs(force) / 40, 0.18, 1);
    var w = 26 + 14 * side, h = 26 + 20 * side;
    var g = ctx.createLinearGradient(xPos - w / 2, 0, xPos + w / 2, 0);
    g.addColorStop(0, color[0]); g.addColorStop(0.45, color[1]); g.addColorStop(1, color[2]);
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.roundRect ? ctx.roundRect(xPos - w / 2, 8, w, h, 5) : ctx.rect(xPos - w / 2, 8, w, h);
    ctx.fill();
    ctx.strokeStyle = 'rgba(60,74,88,0.35)'; ctx.lineWidth = 1; ctx.stroke();
    ctx.strokeStyle = 'rgba(70,84,98,0.45)';
    ctx.beginPath(); ctx.moveTo(xPos, 8); ctx.lineTo(xPos, 8 + h); ctx.stroke();
  }
  weight(-la * perMetre, Number(req.left_force) || 0, ['#e9eff6', '#b8c6d6', '#7d8b9b']);
  weight(ra * perMetre, Number(req.right_force) || 0, ['#f2e7d8', '#d3b795', '#9b7d58']);
  ctx.restore();

  // 力臂标注（画在杆外，避免压住砝码）
  label(v, '左力臂 ' + n(la) + ' m', pivotX - la * perMetre, 372, { size: 12 });
  label(v, '右力臂 ' + n(ra) + ' m', pivotX + ra * perMetre, 372, { size: 12 });
  label(v, '左侧 ' + n(req.left_force) + ' N', pivotX - la * perMetre, 316, { size: 12, color: '#1b62b0' });
  label(v, '右侧 ' + n(req.right_force) + ' N', pivotX + ra * perMetre, 316, { size: 12, color: '#a3622b' });
  if (result) {
    v.pill({ text: '左力矩 ' + n(result.left_torque) + ' N·m', x: 150, y: 470, size: 11 });
    v.pill({ text: '右力矩 ' + n(result.right_torque) + ' N·m', x: 700, y: 470, size: 11, bg: '#a3622b' });
    label(v, String(result.state), pivotX, 214, { size: 14, weight: 600 });
  }
  label(v, '支点', pivotX, pivotY + 34, { size: 11, color: '#5b6875' });
  say(cv, '杠杆与两侧砝码，支点在中间，两侧力矩决定杠杆状态');
}

/* ------------------------------------------------------------ 液体压强 */

function liquidPressure(cv, req, result) {
  var v = V();
  if (!v.mount(cv, { DW: GW, DH: GH })) return;
  v.clear();
  var ctx = v.S.ctx;
  v.wall({ tableY: 566 });
  groundBand(v, 560);

  var depth = Math.max(0, Number(req.depth) || 0);
  var density = Math.max(1, Number(req.density) || 1000);
  var maxDepth = 1.2;
  var cx = 430, base = 540, hw = 156, h = 360;
  v.glass({ x: cx, base: base, hw: hw, h: h, kind: 'beaker', pour: true });
  v.liquid({ level: 0.82, top: '#63c0ed', bot: '#0f63a3', t: 0, ripple: true, bubbles: 0 });

  var ySurf = base - h * 0.82;
  var yDip = ySurf + (depth / maxDepth) * (base - ySurf - 24);
  var plateY = v.clamp(yDip, ySurf + 18, base - 26);

  // 探头：膜片 + 导管
  var pg = ctx.createLinearGradient(cx - 52, 0, cx + 52, 0);
  pg.addColorStop(0, '#dfe7ef'); pg.addColorStop(0.5, '#a8b4c2'); pg.addColorStop(1, '#6f7c8a');
  ctx.save();
  ctx.fillStyle = pg;
  ctx.beginPath();
  if (ctx.roundRect) ctx.roundRect(cx - 54, plateY - 7, 108, 14, 4); else ctx.rect(cx - 54, plateY - 7, 108, 14);
  ctx.fill();
  ctx.strokeStyle = 'rgba(60,74,88,0.35)'; ctx.lineWidth = 1; ctx.stroke();
  ctx.strokeStyle = '#8b98a6'; ctx.lineWidth = 3;
  ctx.beginPath(); ctx.moveTo(cx + 54, plateY); ctx.lineTo(cx + 190, plateY - 120); ctx.stroke();
  ctx.restore();

  // 深度标尺
  ctx.save();
  ctx.strokeStyle = 'rgba(90,105,120,0.55)'; ctx.lineWidth = 1.4;
  ctx.beginPath(); ctx.moveTo(cx - hw - 34, ySurf); ctx.lineTo(cx - hw - 34, base - 20); ctx.stroke();
  for (var d = 0; d <= maxDepth + 0.001; d += 0.2) {
    var yy = ySurf + (d / maxDepth) * (base - ySurf - 24);
    ctx.beginPath(); ctx.moveTo(cx - hw - 40, yy); ctx.lineTo(cx - hw - 28, yy); ctx.stroke();
  }
  ctx.restore();

  ctx.save();
  ctx.strokeStyle = '#a3362b'; ctx.lineWidth = 2; ctx.setLineDash([6, 4]);
  ctx.beginPath(); ctx.moveTo(cx - hw - 24, plateY); ctx.lineTo(cx + 200, plateY); ctx.stroke();
  ctx.restore();

  label(v, '液面', cx + hw - 26, ySurf - 14, { size: 12, color: '#0f63a3' });
  label(v, '深度 ' + n(depth) + ' m', cx - hw - 70, (ySurf + plateY) / 2, { size: 12, align: 'left' });
  label(v, '液体密度 ' + n(density) + ' kg/m³', cx, 62, { size: 13, weight: 600 });
  if (result) {
    v.pill({ text: '表压 ' + n(result.pressure) + ' Pa', x: cx + 300, y: plateY - 6, size: 12, bg: '#a3362b' });
  }
  label(v, '探头膜片', cx, base + 4 < 588 ? base + 4 : 588, { size: 11, color: '#5b6875' });
  say(cv, '烧杯中的液体、深度刻度与压强探头膜片');
}

/* ------------------------------------------------------------ 比热容 */

function specificHeat(cv, req, result) {
  var v = V();
  if (!v.mount(cv, { DW: GW, DH: GH })) return;
  v.clear();
  var ctx = v.S.ctx;
  v.wall({ tableY: 566 });
  groundBand(v, 560);

  var mass = Math.max(0.01, Number(req.mass) || 1);
  var temp = result ? Number(result.final_temperature) : Number(req.initial_temperature);
  var tempStart = Number(req.initial_temperature) || 0;
  var cx = 400, base = 540, hw = 132, h = 300;
  v.glass({ x: cx, base: base, hw: hw, h: h, kind: 'beaker', pour: true });
  v.liquid({
    level: 0.62, t: 0,
    top: temp > 45 ? '#f0a45a' : '#7fd8f7',
    bot: temp > 45 ? '#c4632a' : '#2a86c0',
    ripple: true, bubbles: temp > 55 ? 6 : 0
  });

  // 温度计
  var tx = cx + 62;
  ctx.save();
  var tube = ctx.createLinearGradient(tx - 9, 0, tx + 9, 0);
  tube.addColorStop(0, '#f4f8fc'); tube.addColorStop(0.45, '#d5dde6'); tube.addColorStop(1, '#a7b2be');
  ctx.fillStyle = tube;
  ctx.beginPath();
  if (ctx.roundRect) ctx.roundRect(tx - 9, 150, 18, 330, 8); else ctx.rect(tx - 9, 150, 18, 330);
  ctx.fill();
  ctx.strokeStyle = 'rgba(70,84,98,0.35)'; ctx.lineWidth = 1; ctx.stroke();
  var frac = v.clamp((temp + 10) / 110, 0.02, 1);
  var topY = 470 - frac * 300;
  var merc = ctx.createLinearGradient(0, topY, 0, 480);
  merc.addColorStop(0, '#d8412f'); merc.addColorStop(1, '#8e1f14');
  ctx.fillStyle = merc;
  ctx.beginPath();
  if (ctx.roundRect) ctx.roundRect(tx - 4.5, topY, 9, 480 - topY, 4); else ctx.rect(tx - 4.5, topY, 9, 480 - topY);
  ctx.fill();
  ctx.restore();

  // 加热器（热源）与热流箭头
  v.box({ x: 170, y: 500, w: 90, h: 40, color: '#7a8490' });
  arrowTo(ctx, 212, 494, 0, -54, '#d8412f', 4);
  arrowTo(ctx, 286, 494, 0, -54, '#d8412f', 4);

  label(v, '质量 ' + n(mass) + ' kg', cx - hw, 92, { size: 12, align: 'left' });
  label(v, '比热容 ' + n(req.specific_heat, 0) + ' J/(kg·K)', cx, 62, { size: 13, weight: 600 });
  label(v, '热源', 215, 492, { size: 11, color: '#a3362b' });
  label(v, '末温 ' + n(temp) + ' °C', tx + 26, topY, { size: 12, align: 'left', color: '#a3362b' });
  label(v, '初温 ' + n(tempStart) + ' °C', tx - 24, 480, { size: 11, align: 'right' });
  if (result) {
    v.pill({ text: 'ΔT = ' + n(result.temperature_change) + ' K', x: 700, y: 250, size: 12 });
    v.pill({ text: '吸热 ' + n(req.heat, 0) + ' J', x: 700, y: 300, size: 12, bg: '#a3362b' });
  }
  say(cv, '量热容器、液体、温度计与热源，显示初温与末温');
}

/* ------------------------------------------------------------ 匀变速直线运动（图） */

function uniformAcceleration(cv, req, result) {
  var v = V();
  if (!v.mount(cv, { DW: GW, DH: GH })) return;
  v.clear();
  var ctx = v.S.ctx;
  v.wall({ tone: 'warm', tableY: 566 });

  var v0 = Number(req.initial_velocity) || 0;
  var a = Number(req.acceleration) || 0;
  var t = Math.max(0, Number(req.time) || 0);
  var tMax = Math.max(0.5, t, (Math.abs(a) > 1e-9 ? Math.abs(v0 / a) : 0), 1);
  var vAt = function (x) { return v0 + a * x; };
  var vList = [vAt(0), vAt(tMax)];
  var vHigh = Math.max(1, vAt(0), vAt(tMax));
  var vLow = Math.min(0, vAt(0), vAt(tMax));

  var box = { x: 120, y: 90, w: 660, h: 380 };
  var map = axes(v, box, { x: [0, tMax], y: [vLow, vHigh] }, null);

  // v-t 曲线
  ctx.save();
  var grad = ctx.createLinearGradient(box.x, 0, box.x + box.w, 0);
  grad.addColorStop(0, '#63b3e8'); grad.addColorStop(1, '#1b62b0');
  ctx.strokeStyle = grad; ctx.lineWidth = 3.5; ctx.lineCap = 'round';
  ctx.beginPath();
  for (var k = 0; k <= 60; k++) {
    var tt = (tMax * k) / 60;
    var px = map.x(tt), py = map.y(vAt(tt));
    if (k === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
  }
  ctx.stroke();
  // t 时刻竖线
  if (t > 0) {
    ctx.strokeStyle = 'rgba(163,54,43,0.75)'; ctx.lineWidth = 2; ctx.setLineDash([6, 4]);
    ctx.beginPath(); ctx.moveTo(map.x(t), box.y); ctx.lineTo(map.x(t), box.y + box.h); ctx.stroke();
    ctx.setLineDash([]);
  }
  // 位移阴影（曲线下面积）
  ctx.globalAlpha = 0.16; ctx.fillStyle = '#1b62b0';
  ctx.beginPath(); ctx.moveTo(map.x(0), map.y(0));
  for (var m = 0; m <= 60; m++) {
    var t2 = (t * m) / 60;
    ctx.lineTo(map.x(t2), map.y(vAt(t2)));
  }
  ctx.lineTo(map.x(t), map.y(0)); ctx.closePath(); ctx.fill();
  ctx.globalAlpha = 1;
  ctx.restore();

  v.dot({ x: map.x(t), y: map.y(vAt(t)), r: 5.5, color: '#a3362b' });

  label(v, 'v /(m·s⁻¹)', box.x, box.y - 16, { size: 12, align: 'left' });
  label(v, 't / s', box.x + box.w - 10, box.y + box.h + 26, { size: 12, align: 'right' });
  label(v, '面积 = 位移', box.x + box.w - 150, box.y + 40, { size: 11, color: '#1b62b0' });
  if (result) {
    v.pill({ text: 'v = ' + n(result.velocity) + ' m/s', x: box.x + 110, y: box.y + box.h + 60, size: 12 });
    v.pill({ text: 'x = ' + n(result.displacement) + ' m', x: box.x + 400, y: box.y + box.h + 60, size: 12, bg: '#a3362b' });
    label(v, '油门 ' + n(v0) + ' m/s、a = ' + n(a) + ' m/s²', box.x, box.y - 42, { size: 12, align: 'left' });
  }
  say(cv, '匀变速直线运动的 v-t 图像，曲线下面积表示位移');
}

/* ------------------------------------------------------------ 平抛运动（图） */

function horizontalProjectile(cv, req, result) {
  var v = V();
  if (!v.mount(cv, { DW: GW, DH: GH })) return;
  v.clear();
  var ctx = v.S.ctx;
  v.wall({ tone: 'warm', tableY: 566 });

  var speed = Math.max(0, Number(req.speed) || 0);
  var height = Math.max(0.1, Number(req.height) || 0.1);
  var flight = result ? Number(result.flight_time) || 0 : Math.sqrt((2 * height) / 9.8);
  var range = result ? Number(result.range) || speed * flight : speed * flight;
  var g = 9.8;

  var box = { x: 110, y: 96, w: 700, h: 400 };
  var sx = Math.max(range, 1), sy = Math.max(height, 1);
  var mapX = function (x) { return box.x + (x / sx) * box.w; };
  var mapY = function (y) { return box.y + box.h - (y / sy) * box.h * 0.92; };

  // 地面
  ctx.save();
  var floor = ctx.createLinearGradient(0, box.y + box.h, 0, box.y + box.h + 16);
  floor.addColorStop(0, '#e8edf3'); floor.addColorStop(0.4, '#c6ced8'); floor.addColorStop(1, '#9aa4b0');
  ctx.fillStyle = floor; ctx.fillRect(box.x - 30, box.y + box.h, box.w + 60, 14);
  ctx.restore();

  // 抛物线
  ctx.save();
  var path = ctx.createLinearGradient(box.x, 0, box.x + box.w, 0);
  path.addColorStop(0, '#63b3e8'); path.addColorStop(1, '#1b62b0');
  ctx.strokeStyle = path; ctx.lineWidth = 3;
  ctx.beginPath();
  for (var k = 0; k <= 80; k++) {
    var tt = (flight * k) / 80;
    var xx = speed * tt, yy = height - 0.5 * g * tt * tt;
    if (k === 0) ctx.moveTo(mapX(xx), mapY(yy)); else ctx.lineTo(mapX(xx), mapY(yy));
  }
  ctx.stroke();
  if (range > 0) {
    ctx.strokeStyle = 'rgba(163,54,43,0.6)'; ctx.setLineDash([5, 5]); ctx.lineWidth = 1.6;
    ctx.beginPath(); ctx.moveTo(mapX(0), mapY(height)); ctx.lineTo(mapX(0), mapY(0)); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(mapX(0), mapY(0)); ctx.lineTo(mapX(range), mapY(0)); ctx.stroke();
    ctx.setLineDash([]);
  }
  ctx.restore();

  // 抛点平台
  v.box({ x: box.x - 46, y: mapY(height) - 8, w: 44, h: 16, color: '#8b98a6' });

  // 当前状态与速度分解
  var time = Math.max(0, Math.min(Number(req.time) || 0, flight));
  var cx = mapX(speed * time), cy = mapY(height - 0.5 * g * time * time);
  v.sphere({ x: cx, y: cy, r: 9, color: '#a3362b' });
  if (result) {
    var vx = Number(result.vx) || 0, vy = Number(result.vy) || 0;
    var scale = 22 / Math.max(1, Math.abs(vx), Math.abs(vy));
    arrowTo(ctx, cx, cy, vx * scale, 0, '#1b62b0', 2.6);
    arrowTo(ctx, cx, cy, 0, vy * scale, '#a3362b', 2.6);
  }

  label(v, 'h = ' + n(height) + ' m', box.x - 90, mapY(height / 2), { size: 12, align: 'left' });
  label(v, '水平距离 / m', box.x + box.w - 20, mapY(0) + 34, { size: 12, align: 'right' });
  label(v, 'v₀ = ' + n(speed) + ' m/s', box.x + 10, box.y - 20, { size: 12, align: 'left', color: '#1b62b0' });
  label(v, 'vx', cx + 8, cy - 14, { size: 11, color: '#1b62b0' });
  label(v, 'vy', cx + 10, cy + 18, { size: 11, color: '#a3362b' });
  if (result) {
    v.pill({ text: '射程 ' + n(result.range) + ' m', x: 220, y: 78, size: 12, bg: '#a3362b' });
    label(v, String(result.state) + '，t = ' + n(result.flight_time) + ' s', 620, 78, { size: 12 });
  }
  say(cv, '平抛运动的抛物线轨迹、水平速度与竖直速度分解');
}

/* ------------------------------------------------------------ 折射与全反射（光路） */

function refraction(cv, req, result) {
  var v = V();
  if (!v.mount(cv, { DW: GW, DH: GH })) return;
  v.clear();
  var ctx = v.S.ctx;
  v.wall({ tableY: 566 });

  var n1 = Math.max(1, Number(req.n1) || 1);
  var n2 = Math.max(1, Number(req.n2) || 1);
  var inc = v.clamp(Number(req.incident_angle) || 0, 0, 89.9);
  var refr = result && typeof result.refracted_angle === 'number' ? result.refracted_angle : null;
  var totalReflect = result ? String(result.state).indexOf('全反射') >= 0 : false;

  var iy = 330;
  v.box({ x: 60, y: iy + 12, w: 800, h: 236, color: '#cfe6f4' });
  ctx.save();
  var media = ctx.createLinearGradient(0, iy + 10, 0, iy + 250);
  media.addColorStop(0, 'rgba(190,225,245,0.55)'); media.addColorStop(1, 'rgba(120,180,220,0.75)');
  ctx.fillStyle = media; ctx.fillRect(60, iy + 12, 800, 236);
  ctx.restore();

  var ox = 450;
  // 法线
  ctx.save();
  ctx.strokeStyle = 'rgba(90,105,120,0.65)'; ctx.lineWidth = 1.6; ctx.setLineDash([7, 5]);
  ctx.beginPath(); ctx.moveTo(ox, 96); ctx.lineTo(ox, 560); ctx.stroke();
  ctx.restore();

  var R = 230;
  var rad = (inc * Math.PI) / 180;
  var inX = ox - R * Math.sin(rad), inY = iy - R * Math.cos(rad);
  arrowTo(ctx, inX, inY, ox - inX, iy - inY, '#e08a1e', 3);

  var reflX = ox + R * Math.sin(rad), reflY = iy - R * Math.cos(rad);
  ctx.save();
  ctx.strokeStyle = 'rgba(27,98,176,0.55)'; ctx.lineWidth = 2; ctx.setLineDash([6, 5]);
  ctx.beginPath(); ctx.moveTo(ox, iy); ctx.lineTo(reflX, reflY); ctx.stroke();
  ctx.restore();

  if (refr !== null && !totalReflect) {
    var rr = (refr * Math.PI) / 180;
    var outX = ox + R * 0.92 * Math.sin(rr), outY = iy + R * 0.92 * Math.cos(rr);
    arrowTo(ctx, ox, iy, outX - ox, outY - iy, '#1b62b0', 3);
    label(v, '折射角 ' + n(refr, 1) + '°', outX + 6, outY - 14, { size: 12, align: 'left', color: '#1b62b0' });
  }

  label(v, '入射角 ' + n(inc, 1) + '°', inX - 8, inY + 18, { size: 12, align: 'right', color: '#a3622b' });
  label(v, '反射角 ' + n(result ? result.reflected_angle : inc, 1) + '°', reflX + 10, reflY + 18, { size: 12, align: 'left' });
  label(v, 'n₁ = ' + n(n1) + '（空气）', 96, 120, { size: 12, align: 'left' });
  label(v, 'n₂ = ' + n(n2) + '（介质）', 96, iy + 60, { size: 12, align: 'left' });
  label(v, '法线', ox + 12, 108, { size: 11, color: '#5b6875' });
  if (result && typeof result.critical_angle === 'number') {
    v.pill({ text: '临界角 ' + n(result.critical_angle, 1) + '°', x: 700, y: 120, size: 11, bg: '#a3362b' });
  }
  if (result) {
    v.pill({ text: String(result.state), x: 620, y: iy + 200, size: 12, bg: totalReflect ? '#a3362b' : '#1b62b0' });
  }
  say(cv, '两种介质分界面、法线、入射光线、反射光线与折射光线');
}

/* ------------------------------------------------------------ 一维受力与摩擦 */

function horizontalForce(cv, req, result) {
  var v = V();
  if (!v.mount(cv, { DW: GW, DH: GH })) return;
  v.clear();
  var ctx = v.S.ctx;
  v.wall({ tableY: 566 });
  groundBand(v, 470);

  var mass = Math.max(0.01, Number(req.mass) || 1);
  var bx = 330, by = 402, bw = 200, bh = 68;

  // 桌面前留出受力空间
  v.box({ x: bx, y: by, w: bw, h: bh, color: '#8fa0b3' });
  label(v, n(mass) + ' kg', bx + bw / 2, by + bh / 2 + 4, { size: 14, weight: 600, color: '#ffffff', stroke: false });

  var cx = bx + bw / 2, cy = by + bh / 2;
  var F = Number(req.applied_force) || 0;
  var scale = 70 / Math.max(1, Math.abs(F), Math.abs(result ? result.static_limit : 0));
  if (F !== 0) {
    arrowTo(ctx, bx + bw, cy - 14, Math.sign(F) * Math.max(28, Math.abs(F) * scale), 0, '#a3362b', 4);
    label(v, 'F = ' + n(F) + ' N', bx + bw + 14, cy - 34, { size: 12, align: 'left', color: '#a3362b' });
  }
  if (result) {
    var fr = Number(result.friction) || 0;
    if (Math.abs(fr) > 1e-9) {
      arrowTo(ctx, bx, cy + 16, -Math.sign(fr) * Math.max(20, Math.abs(fr) * scale), 0, '#1b62b0', 2.6);
      label(v, 'f = ' + n(Math.abs(fr)) + ' N', bx - 8, cy + 40, { size: 12, align: 'right', color: '#1b62b0' });
    }
    arrowTo(ctx, cx, by, 0, -Math.max(28, (result.weight || 0) * scale * 0.5), '#5b6875', 2.6);
    label(v, 'G = ' + n(result.weight) + ' N', cx - 34, by - 20, { size: 12, align: 'right' });
    arrowTo(ctx, cx, by + bh, 0, Math.max(28, (result.normal_force || 0) * scale * 0.5), '#2f7a55', 2.6);
    label(v, 'N = ' + n(result.normal_force) + ' N', cx + 34, by + bh + 26, { size: 12, align: 'left', color: '#2f7a55' });
    v.pill({ text: String(result.state), x: 640, y: 120, size: 12 });
    v.pill({ text: 'a = ' + n(result.acceleration) + ' m/s²', x: 640, y: 168, size: 11, bg: '#2f7a55' });
    v.pill({ text: '最大静摩擦 ' + n(result.static_limit) + ' N', x: 640, y: 216, size: 11, bg: '#5b6875' });
  }
  label(v, '外力方向 ' + (F >= 0 ? '向右' : '向左'), 120, 120, { size: 12, align: 'left' });
  label(v, '动摩擦系数 ' + n(req.kinetic_coefficient, 2), 120, 152, { size: 12, align: 'left' });
  label(v, '静摩擦系数 ' + n(req.static_coefficient, 2), 120, 184, { size: 12, align: 'left' });
  say(cv, '水平面上的物块与外力、摩擦力、重力、支持力四个受力箭头');
}

/* ------------------------------------------------------------ 功与功率 */

function workPower(cv, req, result) {
  var v = V();
  if (!v.mount(cv, { DW: GW, DH: GH })) return;
  v.clear();
  var ctx = v.S.ctx;
  v.wall({ tableY: 566 });
  groundBand(v, 462);

  var angle = v.clamp(Number(req.angle) || 0, 0, 180);
  var bx = 200, by = 396, bw = 150, bh = 62;
  v.box({ x: bx, y: by, w: bw, h: bh, color: '#8fa0b3' });

  var cx = bx + bw / 2, cy = by + bh / 2;
  var rad = (angle * Math.PI) / 180;
  var len = 150;
  arrowTo(ctx, cx, cy, Math.cos(rad) * len, -Math.sin(rad) * len, '#a3362b', 4);
  label(v, 'F = ' + n(req.force) + ' N', cx + Math.cos(rad) * len + 8, cy - Math.sin(rad) * len - 8,
    { size: 12, align: Math.cos(rad) > 0 ? 'left' : 'right', color: '#a3362b' });

  // 位移
  var dx = v.clamp((Number(req.distance) || 0) * 22, 80, 520);
  ctx.save();
  ctx.strokeStyle = '#1b62b0'; ctx.lineWidth = 3; ctx.setLineDash([9, 6]);
  ctx.beginPath(); ctx.moveTo(cx - 40, 400 + bh + 26); ctx.lineTo(cx + dx, 400 + bh + 26); ctx.stroke();
  ctx.restore();
  arrowTo(ctx, cx + dx - 24, 400 + bh + 26, 22, 0, '#1b62b0', 3);
  label(v, 's = ' + n(req.distance) + ' m', cx + dx / 2, 400 + bh + 54, { size: 12 });

  // 角度弧
  ctx.save();
  ctx.strokeStyle = 'rgba(163,54,43,0.6)'; ctx.lineWidth = 1.6;
  ctx.beginPath(); ctx.arc(cx, cy, 54, -rad, 0); ctx.stroke();
  ctx.restore();
  label(v, n(angle) + '°', cx + 66, cy - 14, { size: 11, color: '#a3362b' });

  if (result) {
    v.pill({ text: 'W = ' + n(result.work) + ' J', x: 660, y: 150, size: 12, bg: '#a3362b' });
    v.pill({ text: 'P = ' + n(result.average_power) + ' W', x: 660, y: 198, size: 12 });
    v.pill({ text: 'F∥ = ' + n(result.parallel_force) + ' N', x: 660, y: 246, size: 11, bg: '#5b6875' });
    v.pill({ text: String(result.state), x: 660, y: 294, size: 12, bg: '#2f7a55' });
  }
  label(v, '耗时 ' + n(req.duration) + ' s', 120, 120, { size: 12, align: 'left' });
  say(cv, '恒力与位移成夹角作用在物块上，显示功和平均功率');
}

/* ------------------------------------------------------------ 机械能（能量条） */

function mechanicalEnergy(cv, req, result) {
  var v = V();
  if (!v.mount(cv, { DW: GW, DH: GH })) return;
  v.clear();
  var ctx = v.S.ctx;
  v.wall({ tone: 'warm', tableY: 566 });

  var mass = Math.max(0.01, Number(req.mass) || 1);
  var ek0 = result ? Number(result.initial_kinetic) : 0.5 * mass * Math.pow(Number(req.initial_speed) || 0, 2);
  var ep0 = result ? Number(result.initial_potential) : mass * 9.8 * (Number(req.start_height) || 0);
  var ek1 = result ? Number(result.final_kinetic) : 0;
  var ep1 = result ? Number(result.final_potential) : mass * 9.8 * (Number(req.end_height) || 0);
  var total = Math.max(1, ek0 + ep0, ek1 + ep1);
  var baseY = 470, maxH = 300, barW = 120;

  function bar(x, ek, ep, title) {
    var hk = Math.max(0, (ek / total) * maxH), hp = Math.max(0, (ep / total) * maxH);
    var gk = ctx.createLinearGradient(x, baseY - hk, x + barW, baseY);
    gk.addColorStop(0, '#7fbfe8'); gk.addColorStop(1, '#1b62b0');
    ctx.fillStyle = gk;
    ctx.fillRect(x, baseY - hk, barW, hk);
    var gp = ctx.createLinearGradient(x, baseY - hk - hp, x + barW, baseY - hk);
    gp.addColorStop(0, '#f0c46a'); gp.addColorStop(1, '#a3622b');
    ctx.fillStyle = gp;
    ctx.fillRect(x, baseY - hk - hp, barW, hp);
    ctx.save();
    ctx.strokeStyle = 'rgba(70,84,98,0.4)'; ctx.lineWidth = 1.2;
    ctx.strokeRect(x, baseY - hk - hp, barW, hk + hp);
    ctx.restore();
    label(v, title, x + barW / 2, baseY + 26, { size: 12 });
    if (hk > 24) label(v, 'Ek ' + n(ek) + ' J', x + barW / 2, baseY - hk / 2, { size: 11, color: '#ffffff' });
    if (hp > 24) label(v, 'Ep ' + n(ep) + ' J', x + barW / 2, baseY - hk - hp / 2, { size: 11, color: '#ffffff' });
  }
  bar(200, ek0, ep0, '初态');
  bar(430, ek1, ep1, '末态');
  groundBand(v, baseY + 40 > 560 ? 560 : baseY + 40);

  // 高度示意
  ctx.save();
  ctx.strokeStyle = 'rgba(90,105,120,0.5)'; ctx.lineWidth = 1.4; ctx.setLineDash([6, 5]);
  ctx.beginPath(); ctx.moveTo(640, 200); ctx.lineTo(806, 200); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(640, 380); ctx.lineTo(806, 380); ctx.stroke();
  ctx.restore();
  v.sphere({ x: 720, y: 200, r: 12, color: '#8fa0b3' });
  v.sphere({ x: 720, y: 380, r: 12, color: '#8fa0b3' });
  arrowTo(ctx, 780, 214, 0, 60, '#a3622b', 2.4);
  label(v, 'Δh', 792, 250, { size: 12, align: 'left' });
  label(v, 'h₁ ' + n(req.start_height) + ' m', 660, 192, { size: 11, align: 'right' });
  label(v, 'h₂ ' + n(req.end_height) + ' m', 660, 372, { size: 11, align: 'right' });

  if (result) {
    v.pill({ text: '初机械能 ' + n(result.initial_energy) + ' J', x: 250, y: 96, size: 11 });
    v.pill({ text: '末机械能 ' + n(result.final_energy) + ' J', x: 560, y: 96, size: 11, bg: '#a3622b' });
    label(v, '机械能变化 ' + n(result.energy_change) + ' J', 450, 520, { size: 13, weight: 600 });
    label(v, String(result.state) + '，末速 ' + n(result.final_speed) + ' m/s', 450, 552, { size: 12 });
  }
  say(cv, '初末两态的动能与重力势能堆叠柱，可看出机械能是否守恒');
}

/* ------------------------------------------------------------ 斜面 */

function inclinedPlane(cv, req, result) {
  var v = V();
  if (!v.mount(cv, { DW: GW, DH: GH })) return;
  v.clear();
  var ctx = v.S.ctx;
  v.wall({ tableY: 566 });
  groundBand(v, 500);

  var length = Math.max(0.01, Number(req.length) || 1);
  var height = Math.max(0, Number(req.height) || 0);
  var run = Math.sqrt(Math.max(0.0001, length * length - height * height));
  var ang = Math.atan2(height, run);
  var scl = Math.min(560 / Math.max(run, 1), 340 / Math.max(height, 1), 40);

  var x0 = 220, y0 = 496;
  var ax = run * scl, ay = height * scl;

  ctx.save();
  var ramp = ctx.createLinearGradient(x0, y0, x0 + ax, y0 - ay);
  ramp.addColorStop(0, '#d7e0ea'); ramp.addColorStop(0.5, '#aab7c6'); ramp.addColorStop(1, '#7d8b9b');
  ctx.fillStyle = ramp;
  ctx.beginPath();
  ctx.moveTo(x0, y0); ctx.lineTo(x0 + ax, y0); ctx.lineTo(x0 + ax, y0 - ay); ctx.closePath();
  ctx.fill();
  ctx.strokeStyle = 'rgba(70,84,98,0.45)'; ctx.lineWidth = 1.4; ctx.stroke();
  ctx.restore();

  // 物块（贴合斜面）
  var t = 0.52;
  var bx = x0 + ax * t, by = y0 - ay * t;
  var size = v.clamp(26 + 4 * Math.sqrt(Number(req.mass) || 1), 26, 46);
  ctx.save();
  ctx.translate(bx, by);
  ctx.rotate(-ang);
  var bg = ctx.createLinearGradient(0, -size, 0, 0);
  bg.addColorStop(0, '#eef3f8'); bg.addColorStop(0.45, '#b9c6d4'); bg.addColorStop(1, '#8394a6');
  ctx.fillStyle = bg;
  ctx.beginPath();
  if (ctx.roundRect) ctx.roundRect(-size / 2, -size, size, size, 4); else ctx.rect(-size / 2, -size, size, size);
  ctx.fill();
  ctx.strokeStyle = 'rgba(60,74,88,0.4)'; ctx.lineWidth = 1; ctx.stroke();
  ctx.restore();

  // 沿斜面向上的拉力箭头
  arrowTo(ctx, bx + Math.cos(ang) * 10, by - Math.sin(ang) * 10 - size * 0.5,
    Math.cos(ang) * 90, -Math.sin(ang) * 90, '#a3362b', 3.4);
  label(v, 'F拉 ' + n(result ? result.pull_force : 0) + ' N',
    bx + Math.cos(ang) * 104, by - Math.sin(ang) * 104 - size * 0.5, { size: 12, color: '#a3362b' });

  // 高度与底边标注
  ctx.save();
  ctx.strokeStyle = 'rgba(90,105,120,0.55)'; ctx.lineWidth = 1.4;
  ctx.beginPath(); ctx.moveTo(x0 + ax + 26, y0); ctx.lineTo(x0 + ax + 26, y0 - ay); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(x0 + ax, y0 - ay); ctx.lineTo(x0 + ax + 26, y0 - ay); ctx.stroke();
  ctx.restore();
  label(v, 'h = ' + n(height) + ' m', x0 + ax + 36, y0 - ay / 2, { size: 12, align: 'left' });
  label(v, 'L = ' + n(length) + ' m', x0 + ax / 2, y0 + 30, { size: 12 });
  label(v, n(result ? result.angle_deg : (ang * 180) / Math.PI, 1) + '°', x0 + ax - 46, y0 - 16, { size: 11, color: '#5b6875' });
  label(v, 'f = ' + n(result ? result.friction_force : 0) + ' N', bx - Math.cos(ang) * 40, by + Math.sin(ang) * 40 + 18,
    { size: 11, align: 'right', color: '#1b62b0' });

  if (result) {
    v.pill({ text: 'W有用 ' + n(result.useful_work) + ' J', x: 250, y: 96, size: 11, bg: '#2f7a55' });
    v.pill({ text: 'W总 ' + n(result.input_work) + ' J', x: 520, y: 96, size: 11 });
    v.pill({ text: '效率 ' + (typeof result.efficiency === 'number' ? n(result.efficiency, 1) + ' %' : '—'),
      x: 760, y: 96, size: 11, bg: '#a3622b' });
    label(v, '摩擦损耗 ' + n(result.friction_loss) + ' J', 450, 540, { size: 12 });
  }
  say(cv, '斜面、斜面上的物块、沿斜面向上的拉力，以及高度与长度标注');
}

  window.PHYS = { floating, optics, solveThinLens, solveBuoyancy, solveLever, solveLiquidPressure,
    solveSpecificHeat, solveUniformAcceleration, solveHorizontalProjectile, solveRefraction,
    solveHorizontalForce, solveWorkPower, solveMechanicalEnergy, solveInclinedPlane, solvePulleySystem,
    drawPulleySystem, solvePlaneMirror, drawPlaneMirror, solveWavePropagation, drawWavePropagation, auto,
    lever, liquidPressure, specificHeat, uniformAcceleration, horizontalProjectile, refraction, horizontalForce, workPower, mechanicalEnergy, inclinedPlane };
})();
