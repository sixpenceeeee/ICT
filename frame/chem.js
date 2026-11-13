/* chem.js —— 化学溶液反应类页面的共享绘图层（外壳注入，离线可用）
 *
 * 目的：把「两只烧杯、玻璃质感、胶囊标签、放大镜、方程式条」这套版式
 *       从模型输出里搬出来，变成可复用的确定性代码。
 *       模型只负责给数字和文字，版面不会每次重画一遍、也不会漂移。
 *
 * 对外接口（页面脚本里直接用）：
 *   CHEM.scene(canvas, {
 *     p: 0.75,                 // 反应进度 0~1，驱动溶液颜色与铜层厚度
 *     V: 80,                   // 溶液体积 mL（决定液面高度）
 *     leftTitle: '反应前', rightTitle: '反应后',
 *     leftSol: '硫酸铜溶液',
 *     rightSol: '硫酸亚铁溶液（浅绿色）',
 *     nailLabel: '铁钉', depositLabel: '铜析出',
 *     arrowText: '发生置换反应',
 *     formula: { segs: [...], names: [...], nameIdx: [...] }
 *   })
 *   页面自己负责：DOM 读数、代入式、记录表、__DATA__。
 */
(function () {
  'use strict';

  var ctx = null;
  // 画布最小字号：化学版也是位图，10.5px 的中文在页面上认不出来
  var FS_MIN = 24;      // 画布内最小字号 = 原始 12px × 2
  var TYPE_SCALE = 2;   // 画布内所有字号统一放大倍数
  var SC = TYPE_SCALE;  // 几何放大系数：必须与字号同步，否则标签会溢出
  function fs(v) { v = (+v || 0) * TYPE_SCALE; return v < FS_MIN ? FS_MIN : v; }
  // 设计坐标系（几何尺寸）。注意：字号已被 fs() 放大 TYPE_SCALE 倍，
  // 几何必须跟着一起放大，否则文字翻倍、烧杯间距不变 → 标签溢出。
  // 绘制代码里的数字仍按原始 880×700 口径书写，由 begin() 统一乘 SC。
  var DW = 880, DH = 700;
  var BW = 88, BH = 270, BR = 16;          // 烧杯半宽 / 高 / 底圆角
  var IN = { cx: 806, cy: 132, r: 48 };    // 右上放大镜
  var L = { cx: 190, base: 470 };          // 左杯（反应前）
  var R = { cx: 660, base: 470 };          // 右杯（反应后）
  var view = { w: 0, h: 0, s: 1, ox: 0, oy: 0, dpr: 1 };
  var BLUE_T = '#7fd8f7', BLUE_B = '#0b6aa8';
  var GREEN_T = '#cfeade', GREEN_B = '#4fa89a';

  // 确定性伪随机：颗粒纹理每次重绘一致
  var SPK = [];
  (function () {
    var s = 11;
    for (var i = 0; i < 200; i++) { s = (s * 9301 + 49297) % 233280; SPK.push(s / 233280); }
  })();

  function parseColor(c) {
    if (c.charAt(0) === '#') {
      return [parseInt(c.substr(1, 2), 16), parseInt(c.substr(3, 2), 16), parseInt(c.substr(5, 2), 16)];
    }
    var m = String(c).match(/(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/);
    return m ? [+m[1], +m[2], +m[3]] : [0, 0, 0];
  }
  function mix(a, b, t) {
    var A = parseColor(a), Bc = parseColor(b);
    return 'rgb(' + Math.round(A[0] + (Bc[0] - A[0]) * t) + ',' +
      Math.round(A[1] + (Bc[1] - A[1]) * t) + ',' +
      Math.round(A[2] + (Bc[2] - A[2]) * t) + ')';
  }
  function rr(x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + r);
    ctx.lineTo(x + w, y + h - r);
    ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    ctx.lineTo(x + r, y + h);
    ctx.quadraticCurveTo(x, y + h, x, y + h - r);
    ctx.lineTo(x, y + r);
    ctx.quadraticCurveTo(x, y, x + r, y);
    ctx.closePath();
  }


  function surfaceY(V) { return -8 - (BH - 52) * (V / 100); }

  function drawBG() {
    var g = ctx.createLinearGradient(0, 0, 0, DH);
    g.addColorStop(0, '#f8fbfe');
    g.addColorStop(0.55, '#eaf2f9');
    g.addColorStop(1, '#dfe9f3');
    ctx.fillStyle = g;
    ctx.fillRect(-300, -300, DW + 600, DH + 600);

    // 背景墙面：虚化的试剂架与玻璃器皿（低对比，制造景深）
    ctx.save();
    ctx.filter = 'blur(3px)';
    ctx.globalAlpha = 0.42;
    var gt = ['#cbdbe9', '#d6e4f0', '#c4d6e6'];
    for (var q = 0; q < 7; q++) {
      var bx = 12 + q * 128;
      var bh = 42 + (q % 3) * 16;
      rr(bx, 96 - bh, 16 + (q % 2) * 6, bh, 3);
      ctx.fillStyle = gt[q % 3];
      ctx.fill();
    }
    for (var w2 = 0; w2 < 4; w2++) {
      rr(58 + w2 * 232, 58, 34, 40, 4);
      ctx.fillStyle = 'rgba(222,235,245,0.85)';
      ctx.fill();
    }
    ctx.filter = 'none';
    ctx.globalAlpha = 0.55;
    ctx.fillStyle = '#d7e4f0';
    ctx.fillRect(0, 96, DW, 6);
    ctx.fillRect(0, 40, DW, 3);
    var xs = [18, 92, 640, 726, 806];
    for (var i = 0; i < xs.length; i++) {
      var hgt = 30 + (i % 3) * 12;
      rr(xs[i], 96 - hgt, 22 + (i % 2) * 8, hgt, 4);
      ctx.fillStyle = 'rgba(198,216,232,0.75)';
      ctx.fill();
    }
    ctx.globalAlpha = 1;
    // 窗格光带
    var lg = ctx.createLinearGradient(0, 0, DW, 0);
    lg.addColorStop(0, 'rgba(255,255,255,0)');
    lg.addColorStop(0.42, 'rgba(255,255,255,0.55)');
    lg.addColorStop(0.62, 'rgba(255,255,255,0)');
    ctx.fillStyle = lg;
    ctx.fillRect(-300, 0, DW + 600, 330);
    ctx.restore();

    // 实验台面
    var tg = ctx.createLinearGradient(0, 330, 0, DH);
    tg.addColorStop(0, '#f2f7fb');
    tg.addColorStop(0.4, '#e3ecf5');
    tg.addColorStop(1, '#d2dfeb');
    ctx.fillStyle = tg;
    ctx.fillRect(-300, 330, DW + 600, DH + 200);
    ctx.strokeStyle = 'rgba(176,198,218,0.85)';
    ctx.lineWidth = 1.6;
    ctx.beginPath();
    ctx.moveTo(-300, 330.5);
    ctx.lineTo(DW + 300, 330.5);
    ctx.stroke();
    // 台面反光
    ctx.save();
    var rg = ctx.createLinearGradient(0, 332, 0, 452);
    rg.addColorStop(0, 'rgba(255,255,255,0.75)');
    rg.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = rg;
    ctx.fillRect(-300, 332, DW + 600, 120);
    ctx.restore();
  }

  function bodyPath() {
    ctx.beginPath();
    ctx.moveTo(-BW, -BH);
    ctx.lineTo(-BW, -BR);
    ctx.quadraticCurveTo(-BW, 0, -BW + BR, 0);
    ctx.lineTo(BW - BR, 0);
    ctx.quadraticCurveTo(BW, 0, BW, -BR);
    ctx.lineTo(BW, -BH);
    ctx.closePath();
  }

  function drawSediment(coat) {
    var w2 = 22 + 26 * coat;
    var g = ctx.createRadialGradient(-4, -4, 2, -4, -4, w2);
    g.addColorStop(0, 'rgba(176,92,38,0.92)');
    g.addColorStop(0.65, 'rgba(160,80,32,0.55)');
    g.addColorStop(1, 'rgba(150,74,28,0.08)');
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.ellipse(-4, -5, w2, 4 + 2.5 * coat, 0, 0, Math.PI * 2);
    ctx.fill();
    for (var i = 0; i < 44; i++) {
      var px = -4 + (SPK[i] - 0.5) * w2 * 1.8;
      var py = -6 + (SPK[i + 40] - 0.5) * 9;
      ctx.beginPath();
      ctx.arc(px, py, 0.6 + SPK[i + 90] * 1.6, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(146,70,26,' + (0.2 + 0.45 * coat) + ')';
      ctx.fill();
    }
  }

  function drawNail(ax, ay, bx, by, w, mode) {
    var dx = bx - ax, dy = by - ay, len = Math.sqrt(dx * dx + dy * dy), ang = Math.atan2(dy, dx);
    ctx.save();
    ctx.translate(ax, ay);
    ctx.rotate(ang);
    var g = ctx.createLinearGradient(0, -w / 2, 0, w / 2);
    if (mode === 'copper') {
      g.addColorStop(0, '#f2b368'); g.addColorStop(0.3, '#c86a25');
      g.addColorStop(0.68, '#8e3d13'); g.addColorStop(1, '#4f1e08');
    } else {
      g.addColorStop(0, '#e6ecf2'); g.addColorStop(0.32, '#aeb9c4');
      g.addColorStop(0.7, '#7b8691'); g.addColorStop(1, '#4c5560');
    }
    // 钉帽
    ctx.beginPath();
    ctx.ellipse(3, 0, 5.6, w * 0.88, 0, 0, Math.PI * 2);
    ctx.fillStyle = mode === 'copper' ? '#8d481d' : '#9aa5b0';
    ctx.fill();
    // 钉身
    ctx.beginPath();
    ctx.moveTo(0, -w / 2);
    ctx.lineTo(len - 15, -w / 2 + 0.5);
    ctx.lineTo(len, 0);
    ctx.lineTo(len - 15, w / 2 - 0.5);
    ctx.lineTo(0, w / 2);
    ctx.closePath();
    ctx.fillStyle = g;
    ctx.fill();
    // 高光
    ctx.beginPath();
    ctx.moveTo(4, -w * 0.26);
    ctx.lineTo(len - 18, -w * 0.26);
    ctx.strokeStyle = 'rgba(255,255,255,0.45)';
    ctx.lineWidth = Math.max(1, w * 0.18);
    ctx.stroke();
    // 铜层颗粒
    if (mode === 'copper') {
      for (var i = 0; i < 36; i++) {
        var t = SPK[i], u = (SPK[i + 40] - 0.5) * w * 0.92;
        ctx.beginPath();
        ctx.arc(5 + t * (len - 22), u, 0.7 + SPK[i + 80] * 1.7, 0, Math.PI * 2);
        ctx.fillStyle = SPK[i + 120] > 0.45 ? 'rgba(244,178,96,0.55)' : 'rgba(86,38,12,0.45)';
        ctx.fill();
      }
      // 铜层结节：真实析出层是疏松颗粒状，边缘不光滑
      for (var nd = 0; nd < 12; nd++) {
        var tn = SPK[nd + 130], side = nd % 2 ? 1 : -1;
        ctx.beginPath();
        ctx.ellipse(9 + tn * (len - 32), side * w * 0.42,
          2.2 + SPK[nd + 20] * 1.9, 1.5 + SPK[nd + 60] * 1.3, 0, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(118,50,16,0.55)';
        ctx.fill();
      }
    }
    ctx.restore();
  }

  function drawBeaker(cx, base, opt) {
    var V = opt.V, coat = opt.coat || 0, t = opt.t || 0;
    var topC = opt.topColor || mix(BLUE_T, GREEN_T, t), botC = opt.bottomColor || mix(BLUE_B, GREEN_B, t);
    var sy = surfaceY(V);
    ctx.save();
    ctx.translate(cx, base);

    // 台面投影：主光从左上方来，影子落到右下
    var sg = ctx.createRadialGradient(14, 10, 4, 14, 10, BW * 1.45);
    sg.addColorStop(0, 'rgba(26,54,84,0.26)');
    sg.addColorStop(0.6, 'rgba(26,54,84,0.10)');
    sg.addColorStop(1, 'rgba(26,54,84,0)');
    ctx.fillStyle = sg;
    ctx.beginPath();
    ctx.ellipse(14, 10, BW * 1.35, 15, 0, 0, Math.PI * 2);
    ctx.fill();
    // 台面上的玻璃反光（杯体倒影，越往下越淡）
    var rf = ctx.createLinearGradient(0, 0, 0, 62);
    rf.addColorStop(0, 'rgba(255,255,255,0.55)');
    rf.addColorStop(0.45, 'rgba(198,226,244,0.30)');
    rf.addColorStop(1, 'rgba(198,226,244,0)');
    ctx.fillStyle = rf;
    ctx.beginPath();
    ctx.moveTo(-BW + 6, 4);
    ctx.lineTo(BW - 6, 4);
    ctx.lineTo(BW - 18, 58);
    ctx.lineTo(-BW + 18, 58);
    ctx.closePath();
    ctx.fill();

    // 玻璃杯体
    var gg = ctx.createLinearGradient(-BW, 0, BW, 0);
    gg.addColorStop(0, 'rgba(224,239,249,0.62)');
    gg.addColorStop(0.16, 'rgba(255,255,255,0.34)');
    gg.addColorStop(0.6, 'rgba(238,247,253,0.22)');
    gg.addColorStop(1, 'rgba(203,224,241,0.6)');
    bodyPath();
    ctx.fillStyle = gg;
    ctx.fill();
    ctx.strokeStyle = 'rgba(146,180,208,0.95)';
    ctx.lineWidth = 1.8;
    ctx.stroke();

    // 溶液
    ctx.save();
    bodyPath();
    ctx.clip();
    var lg = ctx.createLinearGradient(0, sy, 0, 0);
    lg.addColorStop(0, topC);
    lg.addColorStop(1, botC);
    ctx.fillStyle = lg;
    ctx.fillRect(-BW, sy, BW * 2, -sy);
    // 杯底铜屑
    if (coat > 0.02) drawSediment(coat);
    // 液体中的细微颗粒（真实溶液不完全澄清）
    for (var pi = 0; pi < 26; pi++) {
      var pxp = (SPK[pi + 10] - 0.5) * (BW * 1.7);
      var pyp = sy + 12 + SPK[pi + 60] * (-sy - 20);
      ctx.beginPath();
      ctx.arc(pxp, pyp, 0.6 + SPK[pi + 110] * 1.1, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(255,255,255,' + (0.10 + SPK[pi + 150] * 0.18) + ')';
      ctx.fill();
    }
    // 杯壁内侧阴影（玻璃厚度感）
    var shl = ctx.createLinearGradient(-BW, 0, -BW + 16, 0);
    shl.addColorStop(0, 'rgba(108,150,182,0.30)');
    shl.addColorStop(1, 'rgba(108,150,182,0)');
    ctx.fillStyle = shl;
    ctx.fillRect(-BW, -BH, 16, BH);
    var shr = ctx.createLinearGradient(BW, 0, BW - 16, 0);
    shr.addColorStop(0, 'rgba(108,150,182,0.26)');
    shr.addColorStop(1, 'rgba(108,150,182,0)');
    ctx.fillStyle = shr;
    ctx.fillRect(BW - 16, -BH, 16, BH);
    // 液体底部加深（杯底折射）
    var lb = ctx.createLinearGradient(0, 0, 0, -18);
    lb.addColorStop(0, 'rgba(20,70,110,0.22)');
    lb.addColorStop(1, 'rgba(20,70,110,0)');
    ctx.fillStyle = lb;
    ctx.fillRect(-BW, -18, BW * 2, 18);
    ctx.restore();

    // 铁钉（钉帽在杯口外，整根先画钢色）。
    // 钉身粗细跟「剩余铁量」挂钩：铁片质量是页面上的可调参数，
    // 如果画成固定粗细，拖这个滑块时画面完全不动，学生会以为控件坏了。
    var nw = opt.nailW || 12;
    if (opt.nail) drawNail(44, -BH - 70, -10, -34, nw, 'steel');

    // 浸入液面以下的部分：铜层 + 液体浸润
    ctx.save();
    bodyPath();
    ctx.clip();
    ctx.beginPath();
    ctx.rect(-BW, sy, BW * 2, -sy);
    ctx.clip();
    if (opt.nail && coat > 0.01) drawNail(44, -BH - 70, -10, -34, nw + 2, 'copper');
    var tint = ctx.createLinearGradient(0, sy, 0, 0);
    tint.addColorStop(0, topC);
    tint.addColorStop(1, botC);
    ctx.globalAlpha = 0.16;
    ctx.fillStyle = tint;
    ctx.fillRect(-BW, sy, BW * 2, -sy);
    ctx.globalAlpha = 1;
    ctx.restore();

    // 液面（弯月面）
    ctx.save();
    bodyPath();
    ctx.clip();
    ctx.beginPath();
    ctx.ellipse(0, sy, BW - 5, 8, 0, 0, Math.PI * 2);
    ctx.fillStyle = mix(topC, '#ffffff', 0.42);
    ctx.fill();
    ctx.strokeStyle = 'rgba(255,255,255,0.75)';
    ctx.lineWidth = 1.6;
    ctx.stroke();
    ctx.restore();

    // 杯壁高光 / 暗边 / 底部厚玻璃
    ctx.save();
    bodyPath();
    ctx.clip();
    var hl = ctx.createLinearGradient(-BW + 5, 0, -BW + 34, 0);
    hl.addColorStop(0, 'rgba(255,255,255,0.62)');
    hl.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = hl;
    ctx.fillRect(-BW + 4, -BH + 8, 30, BH - 16);
    var hr = ctx.createLinearGradient(BW - 30, 0, BW - 3, 0);
    hr.addColorStop(0, 'rgba(255,255,255,0)');
    hr.addColorStop(1, 'rgba(255,255,255,0.5)');
    ctx.fillStyle = hr;
    ctx.fillRect(BW - 30, -BH + 8, 26, BH - 16);
    ctx.strokeStyle = 'rgba(255,255,255,0.62)';
    ctx.lineWidth = 3.2;
    ctx.beginPath();
    ctx.moveTo(-BW + 8, -7);
    ctx.quadraticCurveTo(0, 3, BW - 8, -7);
    ctx.stroke();
    ctx.restore();

    // 杯口：玻璃厚度 + 倾倒口 + 前缘高光
    ctx.beginPath();
    ctx.ellipse(0, -BH, BW - 3, 7, 0, 0, Math.PI * 2);
    ctx.strokeStyle = 'rgba(168,196,218,0.6)';
    ctx.lineWidth = 1.2;
    ctx.stroke();
    ctx.beginPath();
    ctx.ellipse(0, -BH, BW, 9, 0, 0, Math.PI);
    ctx.strokeStyle = 'rgba(255,255,255,0.9)';
    ctx.lineWidth = 2.4;
    ctx.stroke();
    ctx.beginPath();
    ctx.ellipse(0, -BH, BW, 9, 0, Math.PI, Math.PI * 2);
    ctx.strokeStyle = 'rgba(150,182,206,0.75)';
    ctx.lineWidth = 1.6;
    ctx.stroke();
    // 倾倒口：与杯口连成一体的小圆弧嘴
    ctx.beginPath();
    ctx.moveTo(-BW + 9, -BH - 2);
    ctx.quadraticCurveTo(-BW - 6, -BH - 1, -BW - 11, -BH + 9);
    ctx.quadraticCurveTo(-BW - 6, -BH + 6, -BW + 3, -BH + 7);
    ctx.quadraticCurveTo(-BW + 7, -BH + 4, -BW + 9, -BH - 2);
    ctx.closePath();
    ctx.fillStyle = 'rgba(240,249,254,0.92)';
    ctx.fill();
    ctx.strokeStyle = 'rgba(150,182,206,0.8)';
    ctx.lineWidth = 1.3;
    ctx.stroke();

    ctx.restore();
  }

  function drawArrow(t) {
    var x1 = 312, x2 = 512, y = 348, h = 13;
    ctx.save();
    ctx.globalAlpha = 0.4 + 0.6 * t;
    var g = ctx.createLinearGradient(x1, 0, x2, 0);
    g.addColorStop(0, 'rgba(58,128,198,0.5)');
    g.addColorStop(1, 'rgba(18,80,158,0.95)');
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.moveTo(x1, y - h / 2);
    ctx.lineTo(x2 - 20, y - h / 2);
    ctx.lineTo(x2 - 20, y - h * 1.55);
    ctx.lineTo(x2, y);
    ctx.lineTo(x2 - 20, y + h * 1.55);
    ctx.lineTo(x2 - 20, y + h / 2);
    ctx.lineTo(x1, y + h / 2);
    ctx.closePath();
    ctx.fill();
    ctx.restore();
  }

  function drawInset(t) {
    // 白色外圈
    ctx.save();
    ctx.beginPath();
    ctx.arc(IN.cx, IN.cy, IN.r + 5, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(255,255,255,0.95)';
    ctx.shadowColor = 'rgba(40,70,100,0.22)';
    ctx.shadowBlur = 12;
    ctx.fill();
    ctx.restore();

    ctx.save();
    ctx.beginPath();
    ctx.arc(IN.cx, IN.cy, IN.r, 0, Math.PI * 2);
    ctx.clip();
    var bg = ctx.createRadialGradient(IN.cx - 12, IN.cy - 14, 3, IN.cx, IN.cy, IN.r);
    bg.addColorStop(0, '#526458');
    bg.addColorStop(1, '#1d2a24');
    ctx.fillStyle = bg;
    ctx.fillRect(IN.cx - IN.r, IN.cy - IN.r, IN.r * 2, IN.r * 2);

    ctx.translate(IN.cx, IN.cy);
    ctx.rotate(-0.62 + 0.05 * (1 - t));
    var g = ctx.createLinearGradient(0, -17, 0, 17);
    if (t > 0.08) {
      g.addColorStop(0, mix('#c9d3dc', '#f2c07a', Math.min(1, t * 1.5)));
      g.addColorStop(0.3, mix('#8c97a2', '#c87a30', Math.min(1, t * 1.5)));
      g.addColorStop(0.68, mix('#68727d', '#8f4419', Math.min(1, t * 1.5)));
      g.addColorStop(1, mix('#4a545e', '#4b2109', Math.min(1, t * 1.5)));
    } else {
      g.addColorStop(0, '#dbe3ea'); g.addColorStop(0.4, '#9aa5b0');
      g.addColorStop(0.75, '#77828d'); g.addColorStop(1, '#4a545e');
    }
    ctx.fillStyle = g;
    ctx.fillRect(-IN.r * 1.35, -16, IN.r * 2.7, 32);
    if (t > 0.08) {
      for (var i = 0; i < 70; i++) {
        var px = -IN.r * 1.3 + SPK[i] * IN.r * 2.6;
        var py = (SPK[i + 50] - 0.5) * 28;
        ctx.beginPath();
        ctx.arc(px, py, 0.8 + SPK[i + 100] * 2.2, 0, Math.PI * 2);
        ctx.fillStyle = SPK[i + 150] > 0.45 ? 'rgba(248,190,112,' + (0.25 + 0.45 * t) + ')'
          : 'rgba(74,32,10,' + (0.25 + 0.4 * t) + ')';
        ctx.fill();
      }
    }
    ctx.fillStyle = 'rgba(255,240,214,0.28)';
    ctx.fillRect(-IN.r * 1.35, -13, IN.r * 2.7, 4);
    ctx.restore();

    ctx.beginPath();
    ctx.arc(IN.cx, IN.cy, IN.r, 0, Math.PI * 2);
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 3.4;
    ctx.stroke();
  }

  function drawPanel() {
    ctx.save();
    ctx.shadowColor = 'rgba(40,70,100,0.12)';
    ctx.shadowBlur = 10;
    ctx.shadowOffsetY = 3;
    rr(60, 556, 760, 108, 16);
    ctx.fillStyle = '#eef6fd';
    ctx.fill();
    ctx.restore();
    ctx.strokeStyle = '#c5dcf0';
    ctx.lineWidth = 1.4;
    rr(60, 556, 760, 108, 16);
    ctx.stroke();
  }

  function safeText(value, fallback) {
    if (typeof value === 'string' || typeof value === 'number') return String(value);
    if (value && typeof value === 'object') {
      var candidate = value.label || value.name || value.title || value.text;
      if (typeof candidate === 'string' || typeof candidate === 'number') return String(candidate);
    }
    return fallback || '';
  }

  function label(x, y, text, opt) {
    text = safeText(text, '');
    opt = opt || {};
    ctx.font = (opt.weight || 600) + ' ' + fs(opt.size || 15) + 'px "Microsoft YaHei", system-ui, sans-serif';
    ctx.textAlign = opt.align || 'center';
    ctx.textBaseline = opt.baseline || 'middle';
    if (opt.stroke !== false) {
      ctx.lineWidth = opt.strokeWidth || 3.2;
      ctx.strokeStyle = opt.strokeColor || 'rgba(255,255,255,0.92)';
      ctx.strokeText(text, x, y);
    }
    ctx.fillStyle = opt.color || '#1c2f42';
    ctx.fillText(text, x, y);
  }

  function scaleText(cx, base, V) {
    ctx.save();
    ctx.translate(cx, base);
    // 刻度线
    for (var v = 20; v <= 100; v += 20) {
      var y = -8 - (BH - 52) * (v / 100);
      ctx.beginPath();
      ctx.moveTo(BW - 38, y);
      ctx.lineTo(BW - 24, y);
      ctx.strokeStyle = 'rgba(38,92,126,0.6)';
      ctx.lineWidth = 1.4;
      ctx.stroke();
    }
    ctx.restore();
    // 刻度数字：只留 20/40/60/80/100，和 mL 单位。
    // 原来还在液面处叠了「V = 80 mL / 容量 100 mL」两行小字，字号被抬到
    // 24px 后必然和刻度数字撞在一起；而液面高度本身已经表达了体积，
    // 这两行属于重复信息，直接删掉最干净，也不影响判据（体积在 DOM 里有）。
    for (var v2 = 20; v2 <= 100; v2 += 20) {
      var y2 = base - 8 - (BH - 52) * (v2 / 100);
      label(cx + BW - 12, y2 + 1, String(v2), {
        size: 11.5, weight: 600, align: 'right', color: '#1f5b7d', strokeWidth: 3
      });
    }
    // mL 单位标在最高刻度之上。距离要按字号算：100 那个刻度数字本身有
    // fs(11.5) 高，写死的 -BH+26 会和小字抬到 24px 后的「100」贴在一起。
    // 单位放在左上侧，避免与右上方的放大镜说明胶囊争用空间。
    label(cx - BW + 14, base - BH + 28, 'mL', {
      size: 11, align: 'left', color: '#3d7a99', strokeWidth: 3
    });
  }

  function pill(cx, cy, text, bg, size) {
    text = safeText(text, '');
    // 关键：这里先 fs() 只是为了让胶囊底框按「放大后的字」量宽高，
    // 传给 label() 的必须是**原始字号**——label 内部还会再 fs() 一次。
    // 直接把 size 传下去（而不是 fs 之后的值），否则字号被放大两遍。
    var raw = size || 15;
    var real = fs(raw);
    ctx.font = '600 ' + real + 'px "Microsoft YaHei", system-ui, sans-serif';
    var tw = ctx.measureText(text).width;
    var w = tw + 26, h = real + 17;
    ctx.save();
    ctx.shadowColor = 'rgba(22,52,86,0.2)';
    ctx.shadowBlur = 8;
    ctx.shadowOffsetY = 2;
    rr(cx - w / 2, cy - h / 2, w, h, h / 2);
    ctx.fillStyle = bg;
    ctx.fill();
    ctx.restore();
    label(cx, cy + 0.5, text, { size: raw, color: '#ffffff', stroke: false });
    return { x: cx - w / 2, y: cy - h / 2, w: w, h: h };
  }

  function leader(x1, y1, x2, y2, dash) {
    ctx.save();
    ctx.strokeStyle = 'rgba(86,118,150,0.8)';
    ctx.lineWidth = 1.2;
    if (dash) ctx.setLineDash([5, 4]);
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.beginPath();
    ctx.arc(x2, y2, 2.8, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(86,118,150,0.9)';
    ctx.fill();
    ctx.restore();
  }

  function formulaText(cfg) {
    if (typeof cfg === 'string') {
      var compact = cfg.replace(/\s/g, '').replace(/₄/g, '4');
      cfg = compact === 'Fe+CuSO4→FeSO4+Cu'
        ? {}
        : { segs: [{ t: cfg, s: 31, c: '#152a3d' }], names: [], nameIdx: [] };
    }
    cfg = cfg || {};
    var cx = 440, y = 604;
    var defaults = [
      { t: 'Fe', s: 31, c: '#152a3d' },
      { t: '  +  ', s: 23, c: '#5d768c' },
      { t: 'CuSO', s: 31, c: '#152a3d' },
      { t: '4', s: 18, c: '#152a3d', dy: 7 },
      { t: '   →   ', s: 23, c: '#1b62b0' },
      { t: 'FeSO', s: 31, c: '#152a3d' },
      { t: '4', s: 18, c: '#152a3d', dy: 7 },
      { t: '  +  ', s: 23, c: '#5d768c' },
      { t: 'Cu', s: 31, c: '#152a3d' }
    ];
    var segs = Array.isArray(cfg.segs) && cfg.segs.length
      ? cfg.segs.map(function (seg) {
        return seg && typeof seg === 'object' && (typeof seg.t === 'string' || typeof seg.t === 'number')
          ? { t: String(seg.t), s: Number.isFinite(+seg.s) ? +seg.s : 23,
            c: typeof seg.c === 'string' ? seg.c : '#152a3d', dy: Number.isFinite(+seg.dy) ? +seg.dy : 0 }
          : null;
      }) : defaults;
    if (segs.some(function (seg) { return !seg; })) segs = defaults;
    var total = 0;
    for (var i = 0; i < segs.length; i++) {
      ctx.font = '700 ' + fs(segs[i].s) + 'px "Microsoft YaHei", system-ui, sans-serif';
      segs[i].w = ctx.measureText(segs[i].t).width;
      total += segs[i].w;
    }
    // 长方程式按比例缩小，保持居中并留出左右安全边距，不让画布裁掉反应物或生成物。
    var fitScale = Math.min(1, 700 / Math.max(1, total));
    total = 0;
    for (var m = 0; m < segs.length; m++) {
      ctx.font = '700 ' + fs(segs[m].s * fitScale) + 'px "Microsoft YaHei", system-ui, sans-serif';
      segs[m].w = ctx.measureText(segs[m].t).width;
      total += segs[m].w;
    }
    var x = cx - total / 2;
    ctx.textAlign = 'left';
    ctx.textBaseline = 'alphabetic';
    for (var j = 0; j < segs.length; j++) {
      ctx.font = '700 ' + fs(segs[j].s * fitScale) + 'px "Microsoft YaHei", system-ui, sans-serif';
      ctx.fillStyle = segs[j].c;
      ctx.fillText(segs[j].t, x, y + (segs[j].dy || 0));
      segs[j].cx = x + segs[j].w / 2;
      x += segs[j].w;
    }
    // 中文名：对齐到对应分子式的中心。
    // 间距要按字号算：分子式 y=604、字号抬到 fs(31) 后字身很高，
    // 写死 640 会让中文名顶到分子式的下沿。
    var names = Array.isArray(cfg.names) ? cfg.names.map(function (n, i) {
      return safeText(n, ['铁', '硫酸铜', '硫酸亚铁', '铜'][i] || '');
    }) : ['铁', '硫酸铜', '硫酸亚铁', '铜'];
    var idx = cfg.nameIdx || [0, 2, 5, 8];
    var nameY = y + fs(31) * 0.78;
    for (var k = 0; k < names.length; k++) {
      if (segs[idx[k]]) label(segs[idx[k]].cx, nameY, names[k], { size: 13 * fitScale, color: '#4d6a80', weight: 500, stroke: false });
    }
  }

  /* ---------------- 自适应与清屏 ----------------
   * 这里有一个容易被忽略的陷阱，记录在此以免再踩：
   *
   * 画布是 16:11 的扁框（742×510），而化学版式是按 880×700 的方构图设计的。
   * 用 min(w/880, h/700) 等比缩放，会因为高度不够而把整幅压小；但字号被
   * fs() 乘过 TYPE_SCALE，压小之后相对比例反而变大 → 胶囊标签互相压字。
   *
   * 正确做法：**先算出「够放下这些字」的最小高度**，如果画布比它矮，
   * 就按「宽度受限」处理，并把画布高度补足（letterbox），宁可上下留白，
   * 也不把版式压扁。这样文字与几何始终同比例，任何画布尺寸都不会压字。
   */
  function fit(cv) {
    var box = cv.parentNode;
    var w = box.clientWidth || 700;
    var h = box.clientHeight || 460;
    view.dpr = window.devicePixelRatio || 1;
    view.w = w; view.h = h;
    cv.width = Math.max(1, Math.round(w * view.dpr));
    cv.height = Math.max(1, Math.round(h * view.dpr));
    cv.style.width = w + 'px';
    cv.style.height = h + 'px';

    // 理想等比：两个方向都尽量铺满
    var s = Math.min(w / (DW * SC), h / (DH * SC));
    // 高度下限：按「宽度铺满」时，字号在屏幕上的实际像素不能小于可读线。
    // 化学版里最小的字是 fs(10.5)=24 设计像素，乘以 s 后至少要有 10px。
    var sByW = w / (DW * SC);
    var minReadable = 10 / fs(10.5);      // 保证最小字 ≥ 10 屏幕像素
    if (sByW < minReadable) s = sByW;     // 太小时只能认了，但版面仍等比
    view.s = s;
    view.ox = (w - DW * SC * s) / 2;
    view.oy = (h - DH * SC * s) / 2;
    // 垂直方向如果没铺满，把背景画满整个画布（不留突兀白边）
    view.padY = Math.max(0, (h - DH * SC * s) / 2);
  }
  function begin() {
    ctx.setTransform(view.dpr, 0, 0, view.dpr, 0, 0);
    ctx.clearRect(0, 0, view.w, view.h);
    ctx.translate(view.ox, view.oy);
    ctx.scale(view.s, view.s);
    // 绘制代码里的数字都按原始 880×700 口径写，这里统一放大
    ctx.scale(SC, SC);
  }

  /* ---------------- 整幅画面 ---------------- */
  function scene(cv, cfg) {
    cfg = cfg || {};
    ['leftTitle', 'rightTitle', 'leftSol', 'rightSol', 'nailLabel', 'depositLabel', 'arrowText', 'tipHint', 'tip']
      .forEach(function (key) {
        if (cfg[key] != null && typeof cfg[key] !== 'string' && typeof cfg[key] !== 'number') {
          cfg[key] = safeText(cfg[key], '');
        }
      });
    ctx = cv.getContext('2d');
    window.__CHEM_DRAWN__ = true;
    window.__CHEM_CV__ = cv;
    var p = typeof cfg.p === 'number' ? Math.max(0, Math.min(1, cfg.p)) : 0.75;
    // CHEM.scene 的 V 单位固定为 mL。旧页面常把 0.1 L 直接传进 V，
    // 会被当成 0.1 mL，液面几乎落在杯底；兼容这类 0~1 的升值输入。
    var explicitMl = cfg.V_mL != null;
    var rawV = Number(explicitMl ? cfg.V_mL : cfg.V);
    var V = Number.isFinite(rawV) && rawV > 0
      ? (!explicitMl && rawV <= 1 ? rawV * 1000 : rawV) : 80;
    V = Math.max(0, Math.min(100, V));
    window.__CHEM_SCENE_STATE__ = { volumeMl: V, fillFraction: V / 100, progress: p };
    // 钉身粗细：nailLevel 0~1 表示「剩余铁量相对初始的多少」，
    // 剩得越少钉越细。页面不给就用满值（保持默认观感）。
    // 幅度取 6~17：铁被大量消耗时要一眼看得出「钉子瘦了」，
    // 否则学生分不清是没反应还是控件坏了。
    var nl = typeof cfg.nailLevel === 'number' ? Math.max(0, Math.min(1, cfg.nailLevel)) : 1;
    var nailW = 6 + 11 * nl;
    fit(cv);
    begin();

    drawBG();
    drawBeaker(L.cx, L.base, { V: V, coat: 0, nail: false, t: 0 });
    drawArrow(p);
    drawBeaker(R.cx, R.base, { V: V, coat: p, nail: true, t: p, nailW: nailW });

    // 台面上直放的铁钉（反应前）
    if (cfg.tableNail !== false) {
      ctx.save();
      ctx.translate(40, 456);
      ctx.rotate(0.176);
      ctx.beginPath();
      ctx.ellipse(60, 9, 64, 6.5, 0, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(26,54,84,0.18)';
      ctx.fill();
      ctx.restore();
      drawNail(38, 452, 168, 476, 12, 'steel');
    }

    drawInset(p);
    drawPanel();

    /* 以下全是文字：最后画，保证不被任何图形压住 */
    scaleText(L.cx, L.base, V);
    scaleText(R.cx, R.base, V);

    var titleY = 86;
    leader(L.cx, titleY + 18, 164, 196);
    leader(R.cx, titleY + 18, 600, 196);
    leader(78, 430 - 17, 46, 456);
    leader(212, 508 - 17, 206, 400);
    leader(R.cx, 508 - 17, 612, 340);

    pill(L.cx, titleY, cfg.leftTitle || '反应前', '#1b62b0', 17);
    pill(R.cx, titleY, cfg.rightTitle || '反应后', '#1b62b0', 17);
    pill(66, 430, cfg.nailLabel || '铁钉', '#5f7183', 15);
    pill(212, 508, cfg.leftSol || '硫酸铜溶液', '#1b62b0', 16);
    var autoSol = p < 0.06 ? '硫酸铜溶液（未反应）'
      : (p < 0.6 ? '硫酸铜与硫酸亚铁混合液' : '硫酸亚铁溶液（浅绿色）');
    var autoBg = p < 0.06 ? '#1b62b0' : (p < 0.6 ? '#186f88' : '#157a55');
    pill(R.cx, 508, cfg.rightSol || autoSol, cfg.rightBg || autoBg, 15);
    // 「铜析出」胶囊挂在放大镜正下方。
    // 原来放 y=210 会压住右烧杯的刻度数字（mL / 100 都在那一片），
    // 现在贴到放大镜下沿之下，并让引导线从胶囊顶指向放大镜底。
    var depY = IN.cy + IN.r + fs(14) * 1.35;
    var depTxt = p < 0.03 ? '铁钉（未析出）' : (cfg.depositLabel || '铜析出');
    var depX = IN.cx - 54;
    pill(depX, depY, depTxt, p < 0.03 ? '#5f7183' : '#9a5423', 14);
    leader(depX, depY - fs(14) * 0.75, IN.cx, IN.cy + IN.r + 3);

    label(412, 316, cfg.arrowText || '发生置换反应', {
      size: 16, color: '#134f96', weight: 700
    });
    formulaText(cfg.formula || null);

    // 装置描述写进 DOM：既给读屏软件，也让「烧杯 / 铁钉 / 溶液」这些词
    // 出现在页面文字里（J6 判据只认页面文本，画布里的字读不到）
    var desc = '装置：两只烧杯（' + (cfg.leftTitle || '反应前') + ' / ' +
      (cfg.rightTitle || '反应后') + '）· ' + (cfg.nailLabel || '铁钉') +
      ' · ' + (cfg.leftSol || '硫酸铜溶液');
    if (cfg.tipHint) desc += '（' + cfg.tipHint + '）';
    cv.setAttribute('aria-label', desc);
    var tipEl = document.getElementById('tip');
    if (tipEl && cfg.tip !== false) tipEl.textContent = cfg.tip || desc;
  }

  // Acid–base titration apparatus. Numerical values are supplied by the
  // deterministic titration solver; this function only maps that result to
  // the shared glassware visual style.
  function titration(cv, result) {
    result = result || {};
    ctx = cv.getContext('2d');
    window.__CHEM_DRAWN__ = true;
    window.__CHEM_CV__ = cv;
    fit(cv); begin(); drawBG();

    // Heavy iron stand and clamp.
    ctx.save();
    ctx.shadowColor = 'rgba(28,52,75,.18)'; ctx.shadowBlur = 9; ctx.shadowOffsetY = 4;
    rr(130, 622, 260, 16, 8);
    var foot = ctx.createLinearGradient(130, 622, 130, 638);
    foot.addColorStop(0, '#8996a3'); foot.addColorStop(.32, '#e7edf2'); foot.addColorStop(1, '#73808c');
    ctx.fillStyle = foot; ctx.fill(); ctx.restore();
    ctx.save();
    rr(242, 118, 18, 508, 8);
    var stand = ctx.createLinearGradient(242, 0, 260, 0);
    stand.addColorStop(0, '#6d7883'); stand.addColorStop(.32, '#f2f5f7');
    stand.addColorStop(.7, '#aab4bd'); stand.addColorStop(1, '#66717d');
    ctx.fillStyle = stand; ctx.fill(); ctx.strokeStyle = '#71808d'; ctx.lineWidth = 1.4; ctx.stroke();
    ctx.restore();

    // Clamp arm and burette body.
    ctx.save(); ctx.lineCap = 'round';
    ctx.strokeStyle = '#778692'; ctx.lineWidth = 12;
    ctx.beginPath(); ctx.moveTo(252, 174); ctx.lineTo(340, 174); ctx.stroke();
    ctx.strokeStyle = 'rgba(255,255,255,.78)'; ctx.lineWidth = 3;
    ctx.beginPath(); ctx.moveTo(255, 170); ctx.lineTo(333, 170); ctx.stroke();
    ctx.restore();
    ctx.save();
    rr(318, 126, 44, 314, 12);
    var glass = ctx.createLinearGradient(318, 126, 362, 126);
    glass.addColorStop(0, 'rgba(184,215,235,.78)'); glass.addColorStop(.2, 'rgba(255,255,255,.66)');
    glass.addColorStop(.75, 'rgba(233,246,252,.38)'); glass.addColorStop(1, 'rgba(142,185,213,.72)');
    ctx.fillStyle = glass; ctx.fill(); ctx.strokeStyle = '#86abc5'; ctx.lineWidth = 2.4; ctx.stroke();
    var eq = Math.max(1e-12, Number(result.equivalence_volume_ml) || 1);
    var added = Math.max(0, Number((result.base || {}).volume_L) || 0) * 1000;
    var used = Math.min(1, added / eq);
    var liquidTop = 158 + 228 * used;
    ctx.save(); rr(323, 132, 34, 298, 8); ctx.clip();
    var titrant = ctx.createLinearGradient(0, liquidTop, 0, 430);
    titrant.addColorStop(0, 'rgba(117,205,238,.58)'); titrant.addColorStop(1, 'rgba(48,137,193,.74)');
    ctx.fillStyle = titrant; ctx.fillRect(323, liquidTop, 34, 280); ctx.restore();
    ctx.strokeStyle = 'rgba(255,255,255,.82)'; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(326, liquidTop + 2); ctx.lineTo(354, liquidTop + 2); ctx.stroke();
    for (var mark = 0; mark <= 10; mark++) {
      var my = 158 + mark * 24;
      ctx.beginPath(); ctx.moveTo(362, my); ctx.lineTo(362 + (mark % 2 ? 8 : 13), my);
      ctx.strokeStyle = 'rgba(62,104,133,.74)'; ctx.lineWidth = 1.5; ctx.stroke();
    }
    ctx.restore();

    // Stopcock and narrow delivery tip.
    ctx.save();
    ctx.fillStyle = '#9aa8b4'; rr(324, 434, 34, 18, 7); ctx.fill();
    ctx.fillStyle = '#596875'; rr(336, 440, 9, 34, 4); ctx.fill();
    ctx.beginPath(); ctx.moveTo(337, 468); ctx.lineTo(344, 468); ctx.lineTo(341, 493); ctx.closePath();
    ctx.fillStyle = '#9ab3c4'; ctx.fill();
    ctx.restore();

    // Drop from the burette into the flask (kept separate from text labels).
    if (added > 0) {
      ctx.save();
      ctx.beginPath(); ctx.moveTo(341, 507); ctx.bezierCurveTo(328, 525, 334, 536, 341, 538);
      ctx.bezierCurveTo(350, 535, 353, 525, 341, 507); ctx.closePath();
      var drop = ctx.createLinearGradient(331, 510, 352, 538);
      drop.addColorStop(0, 'rgba(192,238,251,.95)'); drop.addColorStop(1, 'rgba(57,153,204,.78)');
      ctx.fillStyle = drop; ctx.fill(); ctx.strokeStyle = 'rgba(82,149,187,.68)'; ctx.lineWidth = 1.2; ctx.stroke();
      ctx.restore();
    }

    // Erlenmeyer flask with a real neck, sloped shoulder and rounded base.
    var fx = 600, fy = 520;
    ctx.save();
    ctx.shadowColor = 'rgba(29,57,82,.20)'; ctx.shadowBlur = 17; ctx.shadowOffsetY = 9;
    ctx.beginPath(); ctx.ellipse(fx + 8, fy + 8, 128, 18, 0, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(41,72,98,.12)'; ctx.fill(); ctx.restore();
    ctx.save();
    ctx.beginPath();
    ctx.moveTo(fx - 26, 303); ctx.lineTo(fx + 26, 303); ctx.lineTo(fx + 27, 410);
    ctx.lineTo(fx + 94, 512); ctx.quadraticCurveTo(fx + 105, 534, fx + 84, 548);
    ctx.quadraticCurveTo(fx, 568, fx - 84, 548); ctx.quadraticCurveTo(fx - 105, 534, fx - 94, 512);
    ctx.lineTo(fx - 27, 410); ctx.closePath();
    var flaskGlass = ctx.createLinearGradient(fx - 95, 0, fx + 95, 0);
    flaskGlass.addColorStop(0, 'rgba(174,209,230,.68)'); flaskGlass.addColorStop(.18, 'rgba(255,255,255,.62)');
    flaskGlass.addColorStop(.72, 'rgba(242,250,255,.35)'); flaskGlass.addColorStop(1, 'rgba(150,190,217,.74)');
    ctx.fillStyle = flaskGlass; ctx.fill(); ctx.strokeStyle = '#86abc5'; ctx.lineWidth = 3; ctx.stroke();
    ctx.save();
    ctx.beginPath(); ctx.moveTo(fx - 22, 309); ctx.lineTo(fx + 22, 309); ctx.lineTo(fx + 23, 409);
    ctx.lineTo(fx + 88, 512); ctx.quadraticCurveTo(fx + 96, 530, fx + 78, 540);
    ctx.quadraticCurveTo(fx, 556, fx - 78, 540); ctx.quadraticCurveTo(fx - 96, 530, fx - 88, 512);
    ctx.lineTo(fx - 23, 409); ctx.closePath(); ctx.clip();
    var fillFrac = Math.max(.14, Math.min(.72, .28 + (Number(result.total_volume_l) || .025) * 3.2));
    var surface = 548 - 210 * fillFrac;
    var pink = Number(result.pH) >= 8.2;
    var liquid = ctx.createLinearGradient(fx, surface, fx, 548);
    liquid.addColorStop(0, pink ? 'rgba(250,190,215,.68)' : 'rgba(226,243,250,.58)');
    liquid.addColorStop(1, pink ? 'rgba(219,91,151,.58)' : 'rgba(126,193,220,.58)');
    ctx.fillStyle = liquid; ctx.fillRect(fx - 110, surface, 220, 210);
    ctx.beginPath(); ctx.ellipse(fx, surface, 88, 8, 0, 0, Math.PI * 2);
    ctx.fillStyle = pink ? 'rgba(255,213,230,.83)' : 'rgba(247,253,255,.84)'; ctx.fill();
    ctx.strokeStyle = 'rgba(255,255,255,.85)'; ctx.lineWidth = 1.5; ctx.stroke();
    ctx.restore();
    // Neck rim and glass highlights.
    ctx.beginPath(); ctx.ellipse(fx, 303, 26, 7, 0, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(245,251,255,.82)'; ctx.fill(); ctx.strokeStyle = '#86abc5'; ctx.lineWidth = 2; ctx.stroke();
    ctx.strokeStyle = 'rgba(255,255,255,.82)'; ctx.lineWidth = 5; ctx.lineCap = 'round';
    ctx.beginPath(); ctx.moveTo(fx - 78, 434); ctx.lineTo(fx - 119, 510); ctx.stroke();
    ctx.restore();

    // Labels are drawn last, with enough spacing to avoid glassware overlap.
    label(340, 103, '滴定管 · 标准碱液', { size: 12, color: '#315875', stroke: false });
    label(600, 277, '锥形瓶 · 待测酸液 + 酚酞', { size: 12, color: '#315875', stroke: false });
    var stateText = result.state === 'acidic' ? '酸性' : (result.state === 'basic' ? '碱性' : '当量点');
    pill(704, 124, 'pH ' + (Number.isFinite(Number(result.pH)) ? Number(result.pH).toFixed(2) : '--'), '#1b62b0', 15);
    pill(690, 186, stateText, result.state === 'basic' ? '#b94d82' : '#527b9e', 13);
    label(600, 599, pink ? '酚酞：浅红色' : '酚酞：无色', {
      size: 13, color: pink ? '#9d3769' : '#49677d', weight: 600, stroke: false
    });
    leader(340, 117, 340, 138);
    leader(600, 289, 600, 307);
    var desc = '酸碱滴定装置：铁架台固定滴定管，滴定液逐滴加入锥形瓶；当前 ' +
      stateText + '，pH ' + (Number.isFinite(Number(result.pH)) ? Number(result.pH).toFixed(2) : '未知');
    cv.setAttribute('aria-label', desc);
    var tip = document.getElementById('tip'); if (tip) tip.textContent = desc;
    window.__CHEM_TITRATION_STATE__ = {
      pH: result.pH, state: result.state, addedVolumeMl: added,
      equivalenceVolumeMl: result.equivalence_volume_ml,
      indicator: pink ? 'pale-pink' : 'colorless'
    };
  }

  // Reusable chart component. The caller supplies samples calculated by
  // CHEMSOLVER; this renderer never estimates or modifies pH values itself.
  function titrationCurve(cv, data, currentResult) {
    data = data || {};
    currentResult = currentResult || {};
    var samples = Array.isArray(data.samples) ? data.samples : [];
    if (!cv || !samples.length) return;
    var box = cv.getBoundingClientRect();
    var width = Math.max(320, box.width || 640), height = Math.max(220, box.height || 320);
    var dpr = window.devicePixelRatio || 1;
    cv.width = Math.round(width * dpr); cv.height = Math.round(height * dpr);
    var chart = cv.getContext('2d');
    chart.setTransform(dpr, 0, 0, dpr, 0, 0);
    chart.clearRect(0, 0, width, height);
    var background = chart.createLinearGradient(0, 0, 0, height);
    background.addColorStop(0, '#fbfdff'); background.addColorStop(1, '#edf5fb');
    chart.fillStyle = background; chart.fillRect(0, 0, width, height);
    var pad = { left: 56, right: 22, top: 25, bottom: 43 };
    var plotW = width - pad.left - pad.right, plotH = height - pad.top - pad.bottom;
    var maxX = Math.max(1, Number(data.max_ml) || 1);
    var x = function (value) { return pad.left + Math.max(0, Math.min(maxX, Number(value) || 0)) / maxX * plotW; };
    var y = function (value) { return pad.top + (14 - Math.max(0, Math.min(14, Number(value) || 0))) / 14 * plotH; };
    chart.font = '12px system-ui,"Microsoft YaHei",sans-serif'; chart.lineWidth = 1;
    [0, 7, 14].forEach(function (tick) {
      var py = y(tick); chart.beginPath(); chart.moveTo(pad.left, py); chart.lineTo(width - pad.right, py);
      chart.strokeStyle = tick === 7 ? '#adc5d9' : '#d8e5ef';
      chart.setLineDash(tick === 7 ? [5, 4] : []); chart.stroke(); chart.setLineDash([]);
      chart.fillStyle = '#526a80'; chart.textAlign = 'right'; chart.textBaseline = 'middle';
      chart.fillText(String(tick), pad.left - 10, py);
    });
    chart.beginPath(); chart.moveTo(pad.left, pad.top); chart.lineTo(pad.left, height - pad.bottom);
    chart.lineTo(width - pad.right, height - pad.bottom); chart.strokeStyle = '#647b90';
    chart.lineWidth = 1.5; chart.stroke();
    chart.beginPath();
    samples.forEach(function (point, index) {
      if (index === 0) chart.moveTo(x(point.volume_ml), y(point.pH));
      else chart.lineTo(x(point.volume_ml), y(point.pH));
    });
    chart.strokeStyle = '#e27749'; chart.lineWidth = 3; chart.lineJoin = 'round'; chart.stroke();
    var equivalence = Number(data.equivalence_ml);
    if (Number.isFinite(equivalence) && equivalence <= maxX) {
      var eqX = x(equivalence); chart.beginPath(); chart.moveTo(eqX, pad.top);
      chart.lineTo(eqX, height - pad.bottom); chart.strokeStyle = '#367fc0'; chart.lineWidth = 1.5;
      chart.setLineDash([5, 4]); chart.stroke(); chart.setLineDash([]);
      chart.fillStyle = '#286aa6'; chart.textAlign = 'center'; chart.textBaseline = 'bottom';
      chart.fillText('当量点 ' + Number(equivalence).toPrecision(4) + ' mL', eqX, pad.top - 3);
    } else {
      chart.fillStyle = '#8b5b35'; chart.textAlign = 'right'; chart.textBaseline = 'top';
      chart.fillText('当量点超出当前图示范围', width - pad.right, pad.top + 4);
    }
    chart.beginPath(); chart.arc(x(data.current_ml), y(currentResult.pH), 6, 0, Math.PI * 2);
    chart.fillStyle = '#fff'; chart.fill(); chart.lineWidth = 3; chart.strokeStyle = '#d65f35'; chart.stroke();
    chart.fillStyle = '#405a70'; chart.textAlign = 'center'; chart.textBaseline = 'top';
    chart.fillText('滴入体积（mL）', pad.left + plotW / 2, height - 23);
    chart.save(); chart.translate(17, pad.top + plotH / 2); chart.rotate(-Math.PI / 2);
    chart.textAlign = 'center'; chart.textBaseline = 'middle'; chart.fillText('pH', 0, 0); chart.restore();
    cv.setAttribute('aria-label', '强酸强碱中和滴定曲线；横轴滴入体积，纵轴 pH；蓝色虚线为理论当量点，圆点表示当前状态。');
    window.__CHEM_TITRATION_CURVE__ = {
      sampleCount: samples.length, equivalenceVolumeMl: equivalence,
      currentVolumeMl: Number(data.current_ml), currentPH: Number(currentResult.pH)
    };
  }

  // Oxidation-state and electron-transfer diagram. The equation and numeric
  // electron count remain in the HTML result panel so long equations do not
  // collide with canvas labels.
  function redox(cv, result) {
    result = result || {};
    ctx = cv.getContext('2d');
    window.__CHEM_DRAWN__ = true;
    window.__CHEM_CV__ = cv;
    fit(cv); begin(); drawBG();
    var changes = Array.isArray(result.oxidation_changes) ? result.oxidation_changes : [];
    pill(218, 118, '失电子 · 氧化', '#bd5d3d', 14);
    pill(662, 118, '得电子 · 还原', '#2e78b7', 14);
    var lost = Number((result.electron_balance || {}).lost_electrons) || 0;
    var gained = Number((result.electron_balance || {}).gained_electrons) || 0;
    ctx.save();
    ctx.fillStyle = 'rgba(57,126,190,.78)';
    ctx.beginPath(); ctx.moveTo(370, 187); ctx.lineTo(486, 187); ctx.lineTo(486, 173);
    ctx.lineTo(512, 198); ctx.lineTo(486, 223); ctx.lineTo(486, 209); ctx.lineTo(370, 209);
    ctx.closePath(); ctx.fill(); ctx.restore();
    label(440, 249, '电子守恒  ' + lost + ' e⁻ = ' + gained + ' e⁻',
      { size: 12, color: '#245c91', weight: 700, stroke: false });

    var oxidized = changes.filter(function (row) { return Number(row.electrons_lost) > 0; });
    var reduced = changes.filter(function (row) { return Number(row.electrons_gained) > 0; });
    function drawRows(rows, cx, color, verb) {
      var shown = rows.slice(0, 4);
      if (!shown.length) {
        label(cx, 345, '该方向暂无氧化数变化', { size: 12, color: '#60758a', stroke: false });
        return;
      }
      shown.forEach(function (row, index) {
        var y = 326 + index * 78;
        ctx.save();
        ctx.shadowColor = 'rgba(34,65,91,.10)'; ctx.shadowBlur = 8; ctx.shadowOffsetY = 2;
        rr(cx - 151, y - 26, 302, 54, 14);
        ctx.fillStyle = 'rgba(255,255,255,.93)'; ctx.fill();
        ctx.strokeStyle = 'rgba(122,158,188,.38)'; ctx.lineWidth = 1.2; ctx.stroke();
        ctx.restore();
        var stateText = function (value) { return Number(value) > 0 ? '+' + value : String(value); };
        label(cx - 105, y + 2, row.element, { size: 16, color: color, weight: 700, stroke: false, align: 'center' });
        label(cx + 7, y + 2, stateText(row.before) + ' → ' + stateText(row.after),
          { size: 13, color: '#203c55', weight: 600, stroke: false, align: 'center' });
        label(cx, y + 22, verb + ' ' + (Number(row.electrons_lost) || Number(row.electrons_gained)) + ' e⁻',
          { size: 10.5, color: color, weight: 700, stroke: false, align: 'center' });
      });
    }
    drawRows(oxidized, 218, '#ad4c31', '失去');
    drawRows(reduced, 662, '#236ca7', '得到');
    var desc = '氧化还原电子守恒图：' + oxidized.map(function (row) {
      return row.element + ' 氧化数 ' + row.before + ' 升至 ' + row.after;
    }).join('；') + '；' + reduced.map(function (row) {
      return row.element + ' 氧化数 ' + row.before + ' 降至 ' + row.after;
    }).join('；') + '；失电子和得电子均为 ' + lost + '。';
    cv.setAttribute('aria-label', desc);
    var tip = document.getElementById('tip'); if (tip) tip.textContent = desc;
    window.__CHEM_REDOX_STATE__ = { medium: result.medium, lost_electrons: lost,
      gained_electrons: gained, oxidation_changes: changes };
  }

  // Precipitation experiment: keep the demonstration area as apparatus only.
  // The quantitative mass and net ionic equation remain in the HTML results panel.
  function precipitation(cv, result) {
    result = result || {};
    ctx = cv.getContext('2d');
    window.__CHEM_DRAWN__ = true;
    window.__CHEM_CV__ = cv;
    fit(cv); begin(); drawBG();
    var formula = safeText(result.precipitate_formula, '沉淀');
    var progress = Math.max(0, Math.min(1, Number(result.progress) || 0));
    var sedimentFraction = Number(result.max_extent_mol) > 0
      ? Math.max(0, Math.min(1, Number(result.precipitate_moles) /
        (Number(result.max_extent_mol) * ((result.products || []).find(function (item) {
          return item.formula === formula;
        }) || {}).coefficient))) : 0;
    var sedimentColor = formula === 'Cu(OH)2' ? ['#9bd8ed', '#348eb6']
      : formula === 'Fe(OH)3' ? ['#d8a06c', '#97572f'] : ['#f4f4ed', '#b7c1c8'];

    drawBeaker(190, 470, { V: 72, coat: 0, t: 0.08 });
    drawBeaker(660, 470, { V: 72, coat: 0, t: 0.08 });

    // Granular sediment sits inside the second beaker; grain locations are fixed
    // so re-rendering the same amount produces the same apparatus drawing.
    if (sedimentFraction > 0) {
      ctx.save(); ctx.translate(660, 470); bodyPath(); ctx.clip();
      var bedHeight = 4 + 18 * sedimentFraction;
      ctx.beginPath();
      ctx.moveTo(-64, -7); ctx.quadraticCurveTo(-46, -bedHeight, -22, -bedHeight + 2);
      ctx.quadraticCurveTo(0, -bedHeight - 4, 24, -bedHeight + 1);
      ctx.quadraticCurveTo(47, -bedHeight + 4, 64, -7); ctx.closePath();
      var bed = ctx.createLinearGradient(0, -bedHeight, 0, 0);
      bed.addColorStop(0, sedimentColor[0]); bed.addColorStop(1, sedimentColor[1]);
      ctx.fillStyle = bed; ctx.fill();
      ctx.strokeStyle = 'rgba(255,255,255,.7)'; ctx.lineWidth = 1.4; ctx.stroke();
      var grainCount = Math.round(8 + sedimentFraction * 26);
      for (var grain = 0; grain < grainCount; grain++) {
        var gx = -52 + SPK[grain] * 104;
        var gy = -5 - SPK[grain + 52] * Math.max(2, bedHeight - 2);
        ctx.beginPath(); ctx.ellipse(gx, gy, 1.5 + SPK[grain + 92] * 3,
          1 + SPK[grain + 122] * 2.1, SPK[grain + 152] * Math.PI, 0, Math.PI * 2);
        ctx.fillStyle = grain % 3 ? sedimentColor[0] : sedimentColor[1]; ctx.fill();
        ctx.strokeStyle = 'rgba(255,255,255,.45)'; ctx.lineWidth = .6; ctx.stroke();
      }
      ctx.restore();
    }

    pill(190, 112, '混合前 · 两份溶液', '#527b9e', 13);
    pill(660, 112, '混合后 · ' + formula + (sedimentFraction > 0 ? ' 沉淀' : '待反应'), '#1b62b0', 13);
    label(190, 507, '澄清溶液', { size: 12, color: '#315875', weight: 600, stroke: false });
    label(660, 507, sedimentFraction > 0 ? '沉淀颗粒沉降' : '尚未生成沉淀',
      { size: 12, color: '#315875', weight: 600, stroke: false });
    ctx.save();
    ctx.fillStyle = 'rgba(55,126,190,.78)';
    ctx.beginPath(); ctx.moveTo(386, 320); ctx.lineTo(468, 320); ctx.lineTo(468, 307);
    ctx.lineTo(497, 333); ctx.lineTo(468, 359); ctx.lineTo(468, 346); ctx.lineTo(386, 346);
    ctx.closePath(); ctx.fill(); ctx.restore();
    label(440, 292, progress >= 1 ? '混合反应' : '反应进度 ' + Math.round(progress * 100) + '%',
      { size: 13, color: '#245c91', weight: 700, stroke: false });
    var desc = '沉淀反应装置：左侧为混合前溶液，右侧为反应后溶液；' +
      (sedimentFraction > 0 ? '生成 ' + formula + ' 固体沉淀。' : '当前没有可见沉淀。');
    cv.setAttribute('aria-label', desc);
    var tip = document.getElementById('tip'); if (tip) tip.textContent = desc;
    window.__CHEM_PRECIPITATION_STATE__ = {
      reaction_id: result.reaction_id, precipitate_formula: formula,
      precipitate_moles: result.precipitate_moles, precipitate_mass_g: result.precipitate_mass_g,
      precipitation_occurs: !!result.precipitation_occurs, progress: progress,
      sediment_fraction: sedimentFraction
    };
  }

  // Ksp equilibrium scene: suspended ions, an undissolved crystal and a
  // reversible interface communicate dynamic equilibrium without embedding
  // a bitmap or implying a reaction yield that the solver does not compute.
  function solubility(cv, result) {
    result = result || {};
    ctx = cv.getContext('2d');
    window.__CHEM_DRAWN__ = true;
    window.__CHEM_CV__ = cv;
    fit(cv); begin(); drawBG();
    var state = result.saturation_state || 'unknown';
    var formula = safeText(result.solid_formula, '难溶盐');
    var dissolvedRaw = result.molar_solubility_mol_L;
    var dissolved = typeof dissolvedRaw === 'number' ? dissolvedRaw : Number.NaN;
    var ions = Array.isArray(result.ions) ? result.ions : [];
    drawBeaker(410, 468, { V: 82, coat: 0, t: 0.08 });

    var saturationColor = state === 'supersaturated' ? '#b85b43'
      : state === 'saturated' ? '#8a6a2e' : '#247b72';
    var labelText = state === 'supersaturated' ? '过饱和 · 有沉淀倾向'
      : state === 'saturated' ? '饱和 · 动态平衡' : '未饱和 · 可继续溶解';
    pill(410, 116, formula + ' 溶解平衡', '#1b62b0', 14);
    pill(410, 164, labelText, saturationColor, 13);

    // The crystalline phase rests on the beaker bottom; facets and highlights
    // suggest a granular solid rather than a flat color patch.
    ctx.save();
    ctx.shadowColor = 'rgba(47,62,75,.22)'; ctx.shadowBlur = 10; ctx.shadowOffsetY = 4;
    ctx.beginPath(); ctx.moveTo(357, 535); ctx.lineTo(376, 512); ctx.lineTo(391, 520);
    ctx.lineTo(410, 501); ctx.lineTo(427, 518); ctx.lineTo(443, 508); ctx.lineTo(465, 535);
    ctx.quadraticCurveTo(412, 547, 357, 535); ctx.closePath();
    var crystal = ctx.createLinearGradient(0, 502, 0, 545);
    crystal.addColorStop(0, '#f5f6f2'); crystal.addColorStop(.45, '#c6d0d7'); crystal.addColorStop(1, '#8798a4');
    ctx.fillStyle = crystal; ctx.fill(); ctx.strokeStyle = '#718594'; ctx.lineWidth = 1.5; ctx.stroke();
    ctx.restore();
    ctx.save(); ctx.strokeStyle = 'rgba(255,255,255,.86)'; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(377, 522); ctx.lineTo(389, 529); ctx.lineTo(410, 508);
    ctx.lineTo(426, 526); ctx.lineTo(442, 516); ctx.stroke(); ctx.restore();

    var ionCount = state === 'supersaturated' ? 18 : state === 'saturated' ? 13 : 9;
    for (var i = 0; i < ionCount; i++) {
      var x = 342 + SPK[i + 12] * 135, y = 286 + SPK[i + 42] * 194;
      var ion = ions[i % Math.max(ions.length, 1)] || {};
      var color = (ion.charge || 0) > 0 ? '#4c8bc4' : '#d58b4d';
      ctx.save(); ctx.shadowColor = 'rgba(28,60,88,.15)'; ctx.shadowBlur = 4;
      ctx.beginPath(); ctx.arc(x, y, 7 + (i % 3), 0, Math.PI * 2);
      var bead = ctx.createRadialGradient(x - 2, y - 3, 1, x, y, 9);
      bead.addColorStop(0, '#ffffff'); bead.addColorStop(.25, color); bead.addColorStop(1, '#31536c');
      ctx.fillStyle = bead; ctx.fill(); ctx.strokeStyle = 'rgba(255,255,255,.86)'; ctx.lineWidth = 1; ctx.stroke();
      ctx.restore();
    }
    // Two opposing arrows mark dissolution and crystallization as reversible.
    ctx.save(); ctx.lineWidth = 3; ctx.lineCap = 'round';
    ctx.strokeStyle = 'rgba(44,117,170,.82)';
    ctx.beginPath(); ctx.moveTo(345, 468); ctx.quadraticCurveTo(318, 445, 338, 421); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(338, 421); ctx.lineTo(328, 424); ctx.moveTo(338, 421); ctx.lineTo(339, 432); ctx.stroke();
    ctx.strokeStyle = 'rgba(185,112,59,.82)';
    ctx.beginPath(); ctx.moveTo(470, 421); ctx.quadraticCurveTo(497, 445, 477, 468); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(477, 468); ctx.lineTo(487, 465); ctx.moveTo(477, 468); ctx.lineTo(476, 457); ctx.stroke();
    ctx.restore();
    label(283, 444, '溶解', { size: 12, color: '#2c75aa', weight: 600, stroke: false });
    label(536, 444, '结晶', { size: 12, color: '#a96332', weight: 600, stroke: false });
    label(410, 578, state === 'supersaturated' ? '离子积 Q > Ksp'
      : 'Ksp = 离子浓度幂次乘积', { size: 13, color: '#315875', weight: 700, stroke: false });

    var desc = formula + ' 溶解平衡：' + labelText + '；初始离子积 Q=' +
      (Number.isFinite(Number(result.initial_ion_product)) ? Number(result.initial_ion_product).toExponential(3) : '0') +
      '，Ksp=' + Number(result.Ksp).toExponential(3) +
      (Number.isFinite(dissolved) ? '；摩尔溶解度 s=' + dissolved.toExponential(3) + ' mol/L' : '；不计算过饱和后的沉淀量');
    cv.setAttribute('aria-label', desc);
    var tip = document.getElementById('tip'); if (tip) tip.textContent = desc;
    window.__CHEM_KSP_STATE__ = { solid_formula: formula, saturation_state: state,
      molar_solubility_mol_L: Number.isFinite(dissolved) ? dissolved : null,
      precipitation_expected: !!result.precipitation_expected };
  }

  // Gas preparation and collection. The picture is intentionally a single
  // apparatus scene: state/quantity comes from the solver; this function only
  // visualizes a reaction flask and either a gas syringe or water trough.
  function gasCollection(cv, result) {
    result = result || {};
    ctx = cv.getContext('2d');
    window.__CHEM_DRAWN__ = true;
    window.__CHEM_CV__ = cv;
    fit(cv); begin(); drawBG();
    var progress = Math.max(0, Math.min(1, Number(result.progress) || 0));
    var volume = Math.max(0, Number(result.gas_volume_l) || 0);
    var gas = safeText(result.gas_formula, '气体');
    var wet = result.collection_method === 'over_water';

    // Reaction flask, thick glass, stopper and reagent surface.
    ctx.save();
    ctx.shadowColor = 'rgba(28,52,75,.18)'; ctx.shadowBlur = 13; ctx.shadowOffsetY = 7;
    ctx.beginPath(); ctx.ellipse(205, 574, 132, 19, 0, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(41,72,98,.13)'; ctx.fill(); ctx.restore();
    ctx.save();
    ctx.beginPath(); ctx.moveTo(177, 284); ctx.lineTo(233, 284); ctx.lineTo(237, 392);
    ctx.lineTo(304, 526); ctx.quadraticCurveTo(313, 546, 295, 558);
    ctx.quadraticCurveTo(205, 579, 115, 558); ctx.quadraticCurveTo(97, 546, 106, 526);
    ctx.lineTo(173, 392); ctx.closePath();
    var flask = ctx.createLinearGradient(106, 300, 304, 300);
    flask.addColorStop(0, 'rgba(174,209,230,.72)'); flask.addColorStop(.2, 'rgba(255,255,255,.68)');
    flask.addColorStop(.72, 'rgba(242,250,255,.34)'); flask.addColorStop(1, 'rgba(150,190,217,.72)');
    ctx.fillStyle = flask; ctx.fill(); ctx.strokeStyle = '#86abc5'; ctx.lineWidth = 3; ctx.stroke();
    ctx.save();
    ctx.beginPath(); ctx.moveTo(180, 291); ctx.lineTo(230, 291); ctx.lineTo(233, 392);
    ctx.lineTo(296, 528); ctx.quadraticCurveTo(303, 544, 289, 550);
    ctx.quadraticCurveTo(205, 568, 121, 550); ctx.quadraticCurveTo(108, 544, 115, 528);
    ctx.lineTo(177, 392); ctx.closePath(); ctx.clip();
    var liquidTop = 479 - 24 * progress;
    var liquid = ctx.createLinearGradient(0, liquidTop, 0, 560);
    liquid.addColorStop(0, 'rgba(168,224,240,.62)'); liquid.addColorStop(1, 'rgba(50,133,182,.72)');
    ctx.fillStyle = liquid; ctx.fillRect(100, liquidTop, 210, 100);
    ctx.beginPath(); ctx.ellipse(205, liquidTop, 91, 9, 0, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(239,251,255,.85)'; ctx.fill(); ctx.strokeStyle = 'rgba(255,255,255,.88)'; ctx.stroke();
    for (var bubble = 0; bubble < Math.round(3 + 16 * progress); bubble++) {
      var bx = 168 + SPK[bubble] * 74, by = liquidTop + 16 + SPK[bubble + 22] * 56;
      ctx.beginPath(); ctx.arc(bx, by, 2 + SPK[bubble + 44] * 3, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(238,251,255,.78)'; ctx.fill();
    }
    ctx.restore();
    ctx.beginPath(); ctx.ellipse(205, 284, 29, 7, 0, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(241,248,252,.95)'; ctx.fill(); ctx.strokeStyle = '#748b9c'; ctx.lineWidth = 2; ctx.stroke();
    ctx.fillStyle = '#687986'; rr(194, 268, 22, 24, 5); ctx.fill();
    ctx.restore();

    // Delivery tube with a soft glass highlight and moving-state bubbles.
    ctx.save(); ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    ctx.strokeStyle = '#7896aa'; ctx.lineWidth = 15;
    ctx.beginPath(); ctx.moveTo(205, 270); ctx.lineTo(205, 228); ctx.quadraticCurveTo(205, 210, 224, 210);
    ctx.lineTo(572, 210); ctx.quadraticCurveTo(594, 210, 594, 232); ctx.lineTo(594, wet ? 412 : 348); ctx.stroke();
    ctx.strokeStyle = 'rgba(246,252,255,.86)'; ctx.lineWidth = 5;
    ctx.beginPath(); ctx.moveTo(201, 270); ctx.lineTo(201, 228); ctx.quadraticCurveTo(201, 214, 224, 214);
    ctx.lineTo(572, 214); ctx.quadraticCurveTo(590, 214, 590, 232); ctx.lineTo(590, wet ? 412 : 348); ctx.stroke();
    ctx.restore();
    for (var tb = 0; tb < Math.round(progress * 5); tb++) {
      var tx = 286 + tb * 45;
      ctx.beginPath(); ctx.arc(tx, 210, 4.2, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(103,190,225,.88)'; ctx.fill();
    }

    if (wet) {
      // Water trough and inverted graduated gas jar.
      ctx.save(); ctx.shadowColor = 'rgba(30,58,82,.16)'; ctx.shadowBlur = 12; ctx.shadowOffsetY = 6;
      rr(472, 478, 355, 120, 10);
      var trough = ctx.createLinearGradient(0, 478, 0, 598);
      trough.addColorStop(0, 'rgba(224,245,252,.88)'); trough.addColorStop(1, 'rgba(134,194,220,.74)');
      ctx.fillStyle = trough; ctx.fill(); ctx.strokeStyle = '#8db7ce'; ctx.lineWidth = 2.5; ctx.stroke(); ctx.restore();
      ctx.save(); ctx.beginPath(); ctx.rect(479, 486, 341, 104); ctx.clip();
      var water = ctx.createLinearGradient(0, 490, 0, 596);
      water.addColorStop(0, 'rgba(119,202,232,.45)'); water.addColorStop(1, 'rgba(51,142,190,.68)');
      ctx.fillStyle = water; ctx.fillRect(480, 493, 340, 105); ctx.restore();
      var gasBottom = 490 - 170 * progress;
      ctx.save(); ctx.beginPath(); ctx.moveTo(548, 273); ctx.lineTo(640, 273); ctx.lineTo(640, 492);
      ctx.moveTo(548, 273); ctx.lineTo(548, 492); ctx.strokeStyle = '#85a9c0'; ctx.lineWidth = 4; ctx.stroke();
      ctx.beginPath(); ctx.moveTo(552, gasBottom); ctx.lineTo(636, gasBottom); ctx.strokeStyle = 'rgba(255,255,255,.9)'; ctx.lineWidth = 3; ctx.stroke();
      ctx.beginPath(); ctx.moveTo(552, 280); ctx.lineTo(552, gasBottom); ctx.lineTo(636, gasBottom); ctx.lineTo(636, 280);
      ctx.closePath();
      var gasFill = ctx.createLinearGradient(552, 280, 636, gasBottom);
      gasFill.addColorStop(0, 'rgba(246,252,255,.32)'); gasFill.addColorStop(1, 'rgba(189,219,235,.26)');
      ctx.fillStyle = gasFill; ctx.fill();
      ctx.restore();
      // Collection bubbles rise from the delivery tube into the inverted jar.
      for (var wb = 0; wb < Math.round(2 + 7 * progress); wb++) {
        var wy = 454 - (wb * 21 % Math.max(25, 170 * Math.max(progress, .18)));
        ctx.beginPath(); ctx.arc(594 + Math.sin(wb * 2) * 5, wy, 3 + (wb % 2), 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(235,250,255,.94)'; ctx.fill(); ctx.strokeStyle = '#78b8d5'; ctx.lineWidth = 1; ctx.stroke();
      }
      ctx.save(); ctx.strokeStyle = 'rgba(255,255,255,.75)'; ctx.lineWidth = 5;
      ctx.beginPath(); ctx.moveTo(562, 292); ctx.lineTo(562, 408); ctx.stroke(); ctx.restore();
    } else {
      // Dry collection with a horizontal gas syringe and movable plunger.
      ctx.save(); ctx.shadowColor = 'rgba(30,58,82,.16)'; ctx.shadowBlur = 12; ctx.shadowOffsetY = 6;
      rr(550, 300, 287, 94, 18);
      var syringe = ctx.createLinearGradient(550, 300, 550, 394);
      syringe.addColorStop(0, 'rgba(238,248,253,.86)'); syringe.addColorStop(.45, 'rgba(255,255,255,.54)');
      syringe.addColorStop(1, 'rgba(177,211,231,.72)');
      ctx.fillStyle = syringe; ctx.fill(); ctx.strokeStyle = '#81a8c0'; ctx.lineWidth = 3; ctx.stroke();
      ctx.restore();
      var pistonX = 610 + (1 - progress) * 150;
      ctx.save(); ctx.strokeStyle = '#718493'; ctx.lineWidth = 5;
      ctx.beginPath(); ctx.moveTo(pistonX, 302); ctx.lineTo(pistonX, 392); ctx.stroke();
      ctx.lineWidth = 8; ctx.beginPath(); ctx.moveTo(pistonX, 347); ctx.lineTo(836, 347); ctx.stroke();
      ctx.lineWidth = 10; ctx.beginPath(); ctx.moveTo(836, 326); ctx.lineTo(836, 368); ctx.stroke();
      ctx.restore();
      for (var tick = 0; tick < 7; tick++) {
        ctx.beginPath(); ctx.moveTo(604 + tick * 32, 380); ctx.lineTo(604 + tick * 32, tick % 2 ? 367 : 360);
        ctx.strokeStyle = '#7393a8'; ctx.lineWidth = 1.5; ctx.stroke();
      }
    }

    // All text is painted after glassware and tubing to keep labels readable.
    pill(205, 620, '反应发生器', '#1b62b0', 13);
    pill(wet ? 595 : 690, 252, wet ? '排水集气 · ' + gas : '干燥集气 · ' + gas, '#527b9e', 13);
    pill(wet ? 700 : 690, 430, gas + ' · ' + volume.toFixed(2) + ' L', '#1b62b0', 15);
    label(205, 650, '反应液与气泡', { size: 11, color: '#49677d', stroke: false });
    label(435, 172, '导气管', { size: 11, color: '#49677d', stroke: false });
    // 右下说明文字按右边缘对齐，给不同视口留出画布内安全边距。
    label(868, 586, '温度 ' + Number(result.temperature_c).toFixed(1) + ' °C  ·  干气分压 ' +
      Number(result.dry_gas_partial_pressure_kpa).toFixed(2) + ' kPa',
      { size: 10, align: 'right', color: '#49677d', stroke: false });
    var desc = '气体制取与收集装置：' + gas + '，理论收集体积 ' + volume.toFixed(2) + ' L；' +
      (wet ? '采用排水集气并扣除水蒸气压。' : '采用干燥集气。');
    cv.setAttribute('aria-label', desc);
    var tip = document.getElementById('tip'); if (tip) tip.textContent = desc;
    window.__CHEM_GAS_COLLECTION_STATE__ = {
      gas_formula: result.gas_formula, gas_volume_l: result.gas_volume_l,
      collection_method: result.collection_method, gas_moles: result.gas_moles,
      pressure_kpa: result.dry_gas_partial_pressure_kpa
    };
  }

  // 统一化学实验的阶段版式：所有化学过程共用图一的蓝白实验室、玻璃高光、
  // 蓝色阶段胶囊、柔和投影与底部说明卡；步骤只配置器材和内容，不由模型另画整套风格。
  function stages(cv, cfg) {
    cfg = cfg || {};
    ctx = cv.getContext('2d');
    fit(cv); begin(); drawBG();
    var items = (Array.isArray(cfg.steps) ? cfg.steps : []).slice(0, 3);
    if (!items.length) items = [{ title: '实验过程', vessel: 'beaker', note: cfg.summary || '观察实验现象' }];
    var centers = items.length === 1 ? [440] : items.length === 2 ? [250, 630] : [155, 440, 725];
    var names = [];
    // 阶段卡片和器材先画，文字统一压到最后一层。
    for (var i = 0; i < items.length; i++) {
      var step = items[i] || {}, cx = centers[i], cardW = items.length === 1 ? 620 : 250;
      ctx.save();
      rr(cx - cardW / 2, 118, cardW, 426, 18);
      var card = ctx.createLinearGradient(cx - cardW / 2, 118, cx + cardW / 2, 544);
      card.addColorStop(0, 'rgba(255,255,255,0.74)'); card.addColorStop(1, 'rgba(226,239,250,0.64)');
      ctx.fillStyle = card; ctx.fill(); ctx.strokeStyle = '#c9dff1'; ctx.lineWidth = 1.6; ctx.stroke();
      ctx.restore();
      var vessel = step.vessel || 'beaker';
      if (vessel === 'funnel') {
        drawBeaker(cx, 492, { V: Number(step.volumeMl) || 40, nail: false,
          topColor: step.topColor || '#e8f4fb', bottomColor: step.bottomColor || '#a9d8ed' });
        // 漏斗颈、锥斗与滤纸使用玻璃双边线和暖色滤纸，保持同一光源方向。
        ctx.save(); ctx.shadowColor = 'rgba(37,68,96,.16)'; ctx.shadowBlur = 12; ctx.shadowOffsetY = 6;
        ctx.beginPath(); ctx.moveTo(cx - 66, 265); ctx.lineTo(cx + 66, 265); ctx.lineTo(cx + 21, 354); ctx.lineTo(cx + 10, 354); ctx.lineTo(cx + 7, 408); ctx.lineTo(cx - 7, 408); ctx.lineTo(cx - 10, 354); ctx.closePath();
        var fg = ctx.createLinearGradient(cx - 66, 265, cx + 66, 265); fg.addColorStop(0, 'rgba(196,222,239,.8)'); fg.addColorStop(.45, 'rgba(255,255,255,.82)'); fg.addColorStop(1, 'rgba(157,195,222,.82)');
        ctx.fillStyle = fg; ctx.fill(); ctx.strokeStyle = '#85afd0'; ctx.lineWidth = 3; ctx.stroke(); ctx.restore();
        ctx.beginPath(); ctx.moveTo(cx - 51, 273); ctx.lineTo(cx + 51, 273); ctx.lineTo(cx + 17, 342); ctx.lineTo(cx - 17, 342); ctx.closePath();
        ctx.fillStyle = 'rgba(232,218,177,.82)'; ctx.fill(); ctx.strokeStyle = '#b39d6d'; ctx.lineWidth = 2; ctx.stroke();
        if (step.solid) { ctx.fillStyle = '#b59058'; for (var q = 0; q < 8; q++) { ctx.beginPath(); ctx.arc(cx - 13 + q * 3.7, 327 + (q % 3) * 3, 2.4, 0, Math.PI * 2); ctx.fill(); } }
      } else if (vessel === 'dish') {
        ctx.save(); ctx.shadowColor = 'rgba(30,58,82,.18)'; ctx.shadowBlur = 14; ctx.shadowOffsetY = 7;
        ctx.beginPath(); ctx.ellipse(cx, 430, 96, 26, 0, 0, Math.PI * 2);
        var dg = ctx.createLinearGradient(cx - 90, 405, cx + 80, 452); dg.addColorStop(0, '#fffef7'); dg.addColorStop(.55, '#eee6ce'); dg.addColorStop(1, '#c8b995');
        ctx.fillStyle = dg; ctx.fill(); ctx.strokeStyle = '#ad9a70'; ctx.lineWidth = 2.4; ctx.stroke(); ctx.restore();
        ctx.beginPath(); ctx.ellipse(cx, 423, 82, 17, 0, 0, Math.PI * 2);
        ctx.fillStyle = step.liquid ? (step.liquidColor || 'rgba(125,190,220,.75)') : 'rgba(255,255,255,.78)'; ctx.fill();
        if (step.crystals) for (var c = 0; c < 11; c++) { var xx = cx - 54 + (c * 29 % 108), yy = 417 + (c * 13 % 13); ctx.beginPath(); ctx.moveTo(xx, yy - 5); ctx.lineTo(xx + 4, yy); ctx.lineTo(xx, yy + 5); ctx.lineTo(xx - 4, yy); ctx.closePath(); ctx.fillStyle = 'rgba(255,255,255,.94)'; ctx.fill(); ctx.strokeStyle = '#c6d5df'; ctx.stroke(); }
      } else {
        drawBeaker(cx, 492, { V: Number(step.volumeMl) || 60, nail: false,
          topColor: step.topColor || '#a9e7f5', bottomColor: step.bottomColor || '#2583b4' });
        if (step.solid) { ctx.fillStyle = '#d7dbe0'; for (var z = 0; z < 9; z++) { ctx.beginPath(); ctx.arc(cx - 35 + z * 9, 478 - (z % 2) * 3, 3.2, 0, Math.PI * 2); ctx.fill(); } }
      }
      names.push({ x: cx, title: safeText(step.title, '实验阶段 ' + (i + 1)),
        vessel: safeText(step.equipment || (vessel === 'funnel' ? '漏斗过滤' : vessel === 'dish' ? '蒸发皿' : '烧杯')),
        note: safeText(step.note, '') });
      if (i < items.length - 1) {
        ctx.save(); ctx.fillStyle = 'rgba(58,128,198,.55)';
        ctx.beginPath(); ctx.moveTo(cx + 101, 324); ctx.lineTo(cx + 135, 324); ctx.lineTo(cx + 135, 314); ctx.lineTo(cx + 153, 333); ctx.lineTo(cx + 135, 352); ctx.lineTo(cx + 135, 342); ctx.lineTo(cx + 101, 342); ctx.closePath(); ctx.fill(); ctx.restore();
      }
    }
    // 文本、标题和说明卡后画，保证不会被器材遮挡。
    names.forEach(function (n, i) {
      pill(n.x, 78, n.title, i === 0 ? '#1b62b0' : '#527b9e', 14);
      label(n.x, 515, n.vessel, { size: 12, color: '#315875', weight: 600, stroke: false });
      if (n.note) label(n.x, 552, n.note, { size: 10.5, color: '#39566d', weight: 500, stroke: false });
    });
    ctx.save(); rr(60, 586, 760, 76, 14); ctx.fillStyle = '#eef6fd'; ctx.fill(); ctx.strokeStyle = '#c5dcf0'; ctx.lineWidth = 1.4; ctx.stroke(); ctx.restore();
    label(440, 624, safeText(cfg.summary, '观察各阶段器材、物质状态与实验现象的变化'), { size: 13, color: '#183d5d', weight: 600, stroke: false });
    var desc = '化学实验过程：' + names.map(function (n) { return n.title + '，' + n.vessel; }).join('；');
    cv.setAttribute('aria-label', desc);
    var tip = document.getElementById('tip'); if (tip) tip.textContent = desc;
    window.__CHEM_SCENE_STATE__ = { type: 'stages', count: names.length };
  }

  /* ---------------- 兜底：化学虚拟反应页必须出现标准版面 ----------------
   * 模型偶尔会自己乱画（单只量杯、没有玻璃和标注）。只要页面是「溶液反应类」，
   * 而它没有调用 CHEM.scene，就在初始化后补画一版标准画面，
   * 进度/体积从 __DATA__ 里尽力读，读不到就用默认值。
   * 分子模型、pH 曲线这类非溶液反应页不在此列（engine 不是 virtual_reaction）。
   */
  var REACTION_SCENES = ['fe_cuso4', 'cu_hcl', 'metal_activity', 'zn_cuso4', 'naoh_hcl'];

  function readState() {
    var d = window.__DATA__ || {};
    var cfg = window.__CONFIG__ || {};
    var out = { p: 0.75, V: 80, cross: false };
    var pr = (d.params || {});
    var res = (d.result || {});
    var cand = [pr.p, pr.progress, res.progress, res.p];
    for (var i = 0; i < cand.length; i++) {
      var v = cand[i];
      if (typeof v === 'number' && isFinite(v)) {
        out.p = v > 1 ? Math.max(0, Math.min(1, v / 100)) : Math.max(0, Math.min(1, v));
        break;
      }
    }
    var vv = pr.V || pr.volume || pr.v;
    if (typeof vv === 'number' && vv > 0) out.V = vv;
    if (typeof cfg.cross_check === 'boolean') out.cross = cfg.cross_check;
    return out;
  }
  function isReactionPage() {
    var cfg = window.__CONFIG__ || {};
    var eng = String(cfg.scene_engine || cfg.engine || '');
    var sid = String(cfg.scene_id || '');
    if (eng === 'virtual_reaction') return true;
    if (REACTION_SCENES.indexOf(sid) >= 0) return true;
    // 页面没写 __CONFIG__ 时按正文判断（本库只注入化学页，这里只做二次确认）
    var txt = document.body ? document.body.innerText : '';
    return /溶液/.test(txt) && /(烧杯|试管|铁钉|铜)/.test(txt);
  }
  /* 画布上到底有没有东西。
   *
   * 库的兜底和页面自己的 draw() 用的是**同一张画布**（不是各画一张），
   * 两边都画 = 每次交互产出两幅互斥的版面，谁排在最后谁露脸，顺序还会漂移
   * → 学生看到画面闪动、背景来回换。所以只要页面已经自己画了东西，
   * 库就必须彻底收手：不画，也不挂监听。
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
          if (d[i + 3] < 8) continue;                                   // 全透明 = 没画
          if (d[i] > 246 && d[i + 1] > 246 && d[i + 2] > 246) continue; // 白/近白底
          return false;
        }
      }
      return true;
    } catch (e) {
      return true;
    }
  }

  function autoScene() {
    if (window.__CHEM_DRAWN__) return;
    if (!isReactionPage()) return;
    var cv = document.querySelector('.exp-canvas-box canvas') || document.querySelector('canvas');
    if (!cv) return;
    // 页面自己画得出来就必须让位，否则两套版面抢同一张画布（见 isBlank 注释）
    if (!isBlank(cv)) { window.__CHEM_DRAWN__ = true; return; }
    var st = readState();
    scene(cv, { p: st.p, V: st.V, tipHint: '拖动滑块观察溶液颜色与铁钉表面铜层' });
    window.__CHEM_AUTO__ = true;
    // 兜底模式下，页面自己的滑块回调可能又把画布盖掉：在冒泡末尾再补一帧
    document.addEventListener('input', function () {
      if (!window.__CHEM_AUTO__) return;
      var s2 = readState();
      scene(window.__CHEM_CV__, { p: s2.p, V: s2.V, tipHint: '拖动滑块观察溶液颜色与铁钉表面铜层' });
    }, false);
  }

  /* 时机同样关键：必须等页面自己的脚本跑完、画完第一帧再判断是否兜底。
   * 以前挂在 DOMContentLoaded+setTimeout(0)，页面可能还没画 → 误判空白 → 抢画布。
   * 改成 load 之后再等两帧。 */
  function scheduleAuto() {
    var run = function () {
      requestAnimationFrame(function () {
        requestAnimationFrame(function () {
          try { autoScene(); } catch (e) { }
        });
      });
    };
    if (document.readyState === 'complete') setTimeout(run, 60);
    else window.addEventListener('load', function () { setTimeout(run, 60); });
  }
  scheduleAuto();

  window.CHEM = { scene: scene, titration: titration, titrationCurve: titrationCurve, gasCollection: gasCollection,
    precipitation: precipitation, solubility: solubility, redox: redox,
    stages: stages, fit: fit, auto: autoScene };
})();

/* ===== 稀释前后对照图（追加式注册，2026-11） ===== */
(function () {
  function dilution(cv, request, result) {
    var v = window.VIS;
    if (!v.mount(cv, { DW: 900, DH: 640 })) return;
    v.clear();
    var ctx = v.S.ctx;
    v.wall({ tableY: 566 });
    var c1 = Number(request.stock_concentration_mol_L) || 0.2;
    var v1 = Number(request.stock_volume_ml) || 50;
    var add = Number(request.added_water_ml) || 0;
    var v2 = v1 + add;
    var c2 = result ? Number(result.final_concentration_mol_L) : c1 * v1 / Math.max(v2, 1e-9);

    function beaker(cx, volume, conc, label) {
      var base = 540;
      v.glass({ x: cx, base: base, hw: 120, h: 300, kind: 'beaker', pour: true });
      var level = v.clamp(volume / 400, 0.12, 0.92);
      var deep = v.clamp(conc / Math.max(c1, 1e-9), 0, 1);
      v.liquid({
        level: level,
        top: 'rgba(' + Math.round(90 + 60 * (1 - deep)) + ',' + Math.round(185 - 45 * deep) + ',232,0.95)',
        bot: 'rgba(' + Math.round(20 + 55 * (1 - deep)) + ',' + Math.round(95 - 35 * deep) + ',165,0.95)',
        t: 0, ripple: true, bubbles: 0
      });
      v.text({ text: label, x: cx, y: 200, size: 13, weight: 600 });
      v.text({ text: volume.toFixed(1) + ' mL', x: cx, y: base + 26, size: 12 });
      v.pill({ text: conc.toFixed(3) + ' mol/L', x: cx, y: base + 60, size: 12,
               bg: deep > 0.5 ? '#1b62b0' : '#5b93c4' });
    }
    beaker(280, v1, c1, '稀释前');
    beaker(620, v2, c2, '稀释后');

    ctx.save();
    var g = ctx.createLinearGradient(400, 0, 500, 0);
    g.addColorStop(0, 'rgba(90,170,220,0.15)'); g.addColorStop(0.5, 'rgba(90,170,220,0.75)');
    ctx.strokeStyle = g; ctx.lineWidth = 6; ctx.lineCap = 'round';
    ctx.beginPath(); ctx.moveTo(430, 330); ctx.lineTo(488, 330); ctx.stroke();
    ctx.restore();
    v.text({ text: '加水 ' + add.toFixed(1) + ' mL', x: 459, y: 300, size: 12, color: '#2a86c0' });
    if (result) {
      v.text({ text: '溶质 ' + Number(result.solute_moles_mol).toFixed(4) + ' mol 不变',
               x: 450, y: 96, size: 13, weight: 600 });
      v.text({ text: String(result.state), x: 450, y: 132, size: 12, color: '#5b6875' });
    }
    cv.setAttribute('aria-label', '稀释前后两只烧杯：液面高度表示体积，颜色深浅表示浓度');
  }
  if (window.CHEM) window.CHEM.dilution = dilution;
})();

/* ===== 质量守恒对照（追加式注册，2026-11） ===== */
(function () {
  function massConservation(cv, request, result) {
    var v = window.VIS;
    if (!v.mount(cv, { DW: 900, DH: 640 })) return;
    v.clear();
    var ctx = v.S.ctx;
    v.wall({ tableY: 566 });

    var before = result ? Number(result.before_mass_g) : Number(request.calcium_carbonate_g) || 10;
    var after = result ? Number(result.after_mass_g) : before;
    var gas = result ? Number(result.gas_mass_g) : 0;

    // 天平
    var cx = 450, pivotY = 300;
    v.post({ x: cx, y: pivotY + 6, base: 556 });
    ctx.save();
    ctx.translate(cx, pivotY);
    ctx.rotate(v.clamp((after - before) / Math.max(before, 1e-9) * 6, -0.12, 0.12));
    var beam = ctx.createLinearGradient(0, -9, 0, 9);
    beam.addColorStop(0, '#e4eaf1'); beam.addColorStop(0.4, '#b9c4d1'); beam.addColorStop(1, '#6a7684');
    ctx.fillStyle = beam;
    ctx.beginPath();
    if (ctx.roundRect) ctx.roundRect(-260, -8, 520, 16, 6); else ctx.rect(-260, -8, 520, 16);
    ctx.fill();
    ctx.strokeStyle = 'rgba(70,84,98,0.4)'; ctx.lineWidth = 1; ctx.stroke();
    ctx.restore();

    function pan(x, mass, label) {
      ctx.save();
      var g = ctx.createLinearGradient(x - 90, 0, x + 90, 0);
      g.addColorStop(0, '#dfe7ef'); g.addColorStop(0.5, '#b6c2cf'); g.addColorStop(1, '#8794a2');
      ctx.fillStyle = g;
      ctx.beginPath();
      if (ctx.roundRect) ctx.roundRect(x - 92, 352, 184, 26, 10); else ctx.rect(x - 92, 352, 184, 26);
      ctx.fill();
      ctx.strokeStyle = 'rgba(70,84,98,0.4)'; ctx.lineWidth = 1; ctx.stroke();
      ctx.strokeStyle = 'rgba(90,105,120,0.6)';
      ctx.beginPath(); ctx.moveTo(x, 332); ctx.lineTo(x - 84, 350); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(x, 332); ctx.lineTo(x + 84, 350); ctx.stroke();
      ctx.restore();
      v.pill({ text: mass.toFixed(2) + ' g', x: x, y: 404, size: 13, bg: '#1b62b0' });
      v.text({ text: label, x: x, y: 320, size: 12, weight: 600 });
    }
    pan(300, before, '反应前（密闭容器）');
    pan(600, after, '反应后');

    if (gas > 1e-9) {
      ctx.save();
      ctx.strokeStyle = 'rgba(120,150,175,0.75)'; ctx.lineWidth = 2; ctx.setLineDash([6, 5]);
      for (var i = 0; i < 3; i++) {
        ctx.beginPath();
        ctx.moveTo(600 + (i - 1) * 26, 300);
        ctx.lineTo(600 + (i - 1) * 26 + 12, 244);
        ctx.stroke();
      }
      ctx.restore();
      v.text({ text: '逸出 CO₂ ' + gas.toFixed(2) + ' g', x: 600, y: 206, size: 12, color: '#a3362b' });
    }
    if (result) {
      v.text({ text: '反应前 ' + before.toFixed(2) + ' g，反应后 ' + after.toFixed(2) + ' g',
               x: 450, y: 100, size: 13, weight: 600 });
      v.text({ text: String(result.state), x: 450, y: 134, size: 12, color: '#5b6875' });
      v.text({ text: '剩余固体 ' + Number(result.residue_mass_g).toFixed(2) + ' g，未分解 '
               + Number(result.undecomposed_g).toFixed(2) + ' g', x: 450, y: 470, size: 12 });
    }
    cv.setAttribute('aria-label', '天平对照反应前后总质量，敞口时标出逸出的二氧化碳');
  }
  if (window.CHEM) window.CHEM.massConservation = massConservation;
})();

/* ===== pH 色卡与指示剂（追加式注册，2026-11） ===== */
(function () {
  function phIndicator(cv, request, result) {
    var v = window.VIS;
    if (!v.mount(cv, { DW: 900, DH: 640 })) return;
    v.clear();
    var ctx = v.S.ctx;
    v.wall({ tableY: 566 });

    var pH = result ? Number(result.ph) : Number(request.ph) || 7;
    var x0 = 120, x1 = 780, y = 250, h = 54;
    var grad = ctx.createLinearGradient(x0, 0, x1, 0);
    grad.addColorStop(0.00, '#c0392b');
    grad.addColorStop(0.29, '#e08a1e');
    grad.addColorStop(0.50, '#d8d24a');
    grad.addColorStop(0.57, '#7fb069');
    grad.addColorStop(0.71, '#2f86c4');
    grad.addColorStop(1.00, '#3b3f8f');
    ctx.save();
    ctx.fillStyle = grad;
    ctx.beginPath();
    if (ctx.roundRect) ctx.roundRect(x0, y, x1 - x0, h, 10); else ctx.rect(x0, y, x1 - x0, h);
    ctx.fill();
    ctx.strokeStyle = 'rgba(70,84,98,0.35)'; ctx.lineWidth = 1; ctx.stroke();
    ctx.restore();

    var px = x0 + (pH / 14) * (x1 - x0);
    ctx.save();
    ctx.strokeStyle = '#20384d'; ctx.lineWidth = 3;
    ctx.beginPath(); ctx.moveTo(px, y - 16); ctx.lineTo(px, y + h + 16); ctx.stroke();
    ctx.restore();

    for (var i = 0; i <= 14; i++) {
      var tx = x0 + (i / 14) * (x1 - x0);
      v.text({ text: String(i), x: tx, y: y + h + 30, size: 11, color: '#5b6875' });
    }
    v.text({ text: 'pH 色卡', x: x0, y: y - 34, size: 12, align: 'left', weight: 600 });

    function tube(cx, color, label, sub) {
      var top = 360, hh = 150, w = 54;
      ctx.save();
      var tg = ctx.createLinearGradient(cx - w / 2, 0, cx + w / 2, 0);
      tg.addColorStop(0, '#f4f8fc'); tg.addColorStop(0.5, '#d5dde6'); tg.addColorStop(1, '#a7b2be');
      ctx.fillStyle = tg;
      ctx.beginPath();
      if (ctx.roundRect) ctx.roundRect(cx - w / 2, top, w, hh, 14); else ctx.rect(cx - w / 2, top, w, hh);
      ctx.fill();
      ctx.strokeStyle = 'rgba(70,84,98,0.3)'; ctx.lineWidth = 1; ctx.stroke();
      ctx.fillStyle = color;
      ctx.beginPath();
      if (ctx.roundRect) ctx.roundRect(cx - w / 2 + 6, top + 34, w - 12, hh - 44, 10);
      else ctx.rect(cx - w / 2 + 6, top + 34, w - 12, hh - 44);
      ctx.fill();
      ctx.restore();
      v.text({ text: label, x: cx, y: top + hh + 26, size: 12, weight: 600 });
      if (sub) v.text({ text: sub, x: cx, y: top + hh + 50, size: 11, color: '#5b6875' });
    }
    var litmusColor = '#7b5ea7', phenolColor = '#f2f2f2';
    if (result) {
      litmusColor = result.litmus_color === '红色' ? '#c0392b'
        : result.litmus_color === '蓝色' ? '#2f86c4' : '#7b5ea7';
      var pc = String(result.phenolphthalein_color);
      phenolColor = pc === '无色' ? '#f4f8fc' : pc === '粉红色' ? '#e79bb4' : '#c0392b';
    }
    tube(360, litmusColor, '紫色石蕊', result ? result.litmus_color : '');
    tube(540, phenolColor, '无色酚酞', result ? result.phenolphthalein_color : '');

    if (result) {
      v.pill({ text: String(result.nature), x: 720, y: 400, size: 13,
               bg: result.nature === '酸性' ? '#c0392b' : (result.nature === '碱性' ? '#2f86c4' : '#5b6875') });
      v.text({ text: 'pH = ' + Number(result.ph).toFixed(2) + '，pOH = ' + Number(result.poh).toFixed(2),
               x: 450, y: 96, size: 13, weight: 600 });
      v.text({ text: String(result.state), x: 450, y: 128, size: 12, color: '#5b6875' });
    }
    cv.setAttribute('aria-label', 'pH 色卡与紫色石蕊、无色酚酞在酸碱性下的颜色');
  }
  if (window.CHEM) window.CHEM.phIndicator = phIndicator;
})();

/* ===== 化学计量条形图（追加式注册，2026-11） ===== */
(function () {
  function reactionAmounts(cv, request, result) {
    var v = window.VIS;
    if (!v.mount(cv, { DW: 900, DH: 640 })) return;
    v.clear();
    var ctx = v.S.ctx;
    v.wall({ tableY: 566 });

    var h2 = result ? Number(result.hydrogen_left_mol) : Number(request.hydrogen_mol) || 0;
    var o2 = result ? Number(result.oxygen_left_mol) : Number(request.oxygen_mol) || 0;
    var water = result ? Number(result.water_mol) : 0;
    var top = Math.max(h2, o2, water, 0.001);

    function bar(x, value, label, colorA, colorB) {
      var maxH = 300, baseY = 480, w = 96;
      var h = Math.max(3, (value / top) * maxH);
      var g = ctx.createLinearGradient(x, baseY - h, x + w, baseY);
      g.addColorStop(0, colorA); g.addColorStop(1, colorB);
      ctx.save();
      ctx.fillStyle = g;
      ctx.beginPath();
      if (ctx.roundRect) ctx.roundRect(x, baseY - h, w, h, 8); else ctx.rect(x, baseY - h, w, h);
      ctx.fill();
      ctx.strokeStyle = 'rgba(70,84,98,0.35)'; ctx.lineWidth = 1; ctx.stroke();
      ctx.restore();
      v.text({ text: value.toFixed(3) + ' mol', x: x + w / 2, y: baseY - h - 18, size: 13, weight: 600 });
      v.text({ text: label, x: x + w / 2, y: baseY + 28, size: 12 });
    }
    bar(200, h2, '剩余 H₂', '#9dc7ea', '#2f86c4');
    bar(400, o2, '剩余 O₂', '#f0c9a8', '#c07a34');
    bar(600, water, '生成 H₂O', '#a8d5b5', '#2f7a55');

    ctx.save();
    ctx.strokeStyle = 'rgba(90,105,120,0.55)'; ctx.lineWidth = 1.4;
    ctx.beginPath(); ctx.moveTo(150, 480); ctx.lineTo(750, 480); ctx.stroke();
    ctx.restore();

    if (result) {
      v.pill({ text: '限量试剂：' + result.limiting_reagent, x: 450, y: 96, size: 13, bg: '#a3362b' });
      v.text({ text: '剩余气体 ' + Number(result.gas_left_mol).toFixed(3) + ' mol ≈ '
               + Number(result.gas_volume_L).toFixed(2) + ' L（标准状况）',
               x: 450, y: 140, size: 12, color: '#5b6875' });
      v.text({ text: '2H₂ + O₂ → 2H₂O　' + String(result.state), x: 450, y: 176, size: 12 });
    }
    cv.setAttribute('aria-label', '反应物剩余与生成物的物质的量条形图，标出限量试剂');
  }
  if (window.CHEM) window.CHEM.reactionAmounts = reactionAmounts;
})();

/* ===== 溶解度曲线（追加式注册，2026-11） ===== */
(function () {
  function solubilityCurve(cv, request, result) {
    var v = window.VIS;
    if (!v.mount(cv, { DW: 900, DH: 640 })) return;
    v.clear();
    var ctx = v.S.ctx;
    v.wall({ tone: 'warm', tableY: 566 });

    var box = { x: 130, y: 110, w: 660, h: 360 };
    var S = function (t) { return 20 + 0.8 * t; };
    var maxS = 100;
    var X = function (t) { return box.x + (t / 100) * box.w; };
    var Y = function (s) { return box.y + box.h - (s / maxS) * box.h; };

    ctx.save();
    ctx.strokeStyle = '#9aa6b3'; ctx.lineWidth = 1.4;
    ctx.strokeRect(box.x, box.y, box.w, box.h);
    ctx.strokeStyle = 'rgba(150,165,180,0.5)'; ctx.lineWidth = 1;
    for (var i = 1; i < 5; i++) {
      ctx.beginPath(); ctx.moveTo(box.x + box.w * i / 5, box.y); ctx.lineTo(box.x + box.w * i / 5, box.y + box.h); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(box.x, box.y + box.h * i / 5); ctx.lineTo(box.x + box.w, box.y + box.h * i / 5); ctx.stroke();
    }
    ctx.restore();

    ctx.save();
    var g = ctx.createLinearGradient(box.x, 0, box.x + box.w, 0);
    g.addColorStop(0, '#63b3e8'); g.addColorStop(1, '#1b62b0');
    ctx.strokeStyle = g; ctx.lineWidth = 3.4; ctx.lineCap = 'round';
    ctx.beginPath();
    for (var k = 0; k <= 60; k++) {
      var tt = (100 * k) / 60;
      if (k === 0) ctx.moveTo(X(tt), Y(S(tt))); else ctx.lineTo(X(tt), Y(S(tt)));
    }
    ctx.stroke();
    ctx.restore();

    var t = result ? Number(request.temperature_c) : Number(request.temperature_c) || 40;
    var s = result ? Number(result.solubility_g_per_100g) : S(t);
    var cx = X(t), cy = Y(s);
    ctx.save();
    ctx.strokeStyle = 'rgba(163,54,43,0.7)'; ctx.lineWidth = 1.8; ctx.setLineDash([6, 5]);
    ctx.beginPath(); ctx.moveTo(cx, box.y); ctx.lineTo(cx, box.y + box.h); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(box.x, cy); ctx.lineTo(cx, cy); ctx.stroke();
    ctx.restore();
    v.dot({ x: cx, y: cy, r: 7, color: '#a3362b' });

    // 未溶解固体示意
    if (result && Number(result.undissolved_g) > 1e-9) {
      ctx.save();
      ctx.fillStyle = 'rgba(120,130,142,0.75)';
      for (var j = 0; j < 7; j++) {
        var bx = 730 + (j % 4) * 22, by = 500 + Math.floor(j / 4) * 16;
        ctx.beginPath();
        if (ctx.roundRect) ctx.roundRect(bx, by, 14, 10, 3); else ctx.rect(bx, by, 14, 10);
        ctx.fill();
      }
      ctx.restore();
      v.text({ text: '未溶解 ' + Number(result.undissolved_g).toFixed(2) + ' g', x: 790, y: 570, size: 12, color: '#a3362b' });
    }

    v.text({ text: '溶解度 S /(g·100g⁻¹ 水)', x: box.x, y: box.y - 22, size: 12, align: 'left' });
    v.text({ text: '温度 / °C', x: box.x + box.w - 8, y: box.y + box.h + 26, size: 12, align: 'right' });
    v.text({ text: 'S = 20 + 0.8T（简化模型）', x: box.x + 18, y: box.y + 26, size: 11, align: 'left', color: '#1b62b0' });
    if (result) {
      v.pill({ text: 'S(' + t.toFixed(0) + '°C) = ' + s.toFixed(1) + ' g', x: 450, y: 74, size: 12 });
      v.text({ text: String(result.saturation), x: 450, y: 520, size: 13, weight: 600 });
      v.text({ text: '溶解 ' + Number(result.dissolved_g).toFixed(2) + ' g / 该水量最多溶 '
               + Number(result.capacity_g).toFixed(2) + ' g', x: 450, y: 552, size: 12, color: '#5b6875' });
    }
    cv.setAttribute('aria-label', '溶解度随温度变化的曲线，标出当前温度点与是否饱和');
  }
  if (window.CHEM) window.CHEM.solubilityCurve = solubilityCurve;
})();

/* ===== 速率—时间曲线（追加式注册，2026-11） ===== */
(function () {
  function rateEquilibrium(cv, request, result) {
    var v = window.VIS;
    if (!v.mount(cv, { DW: 900, DH: 640 })) return;
    v.clear();
    var ctx = v.S.ctx;
    v.wall({ tone: 'warm', tableY: 566 });

    var t = result ? Number(request.temperature_c) : Number(request.temperature_c) || 25;
    var c = Number(request.reactant_concentration_mol_L) || 1;
    var catalyst = request.catalyst === 'yes';
    var box = { x: 130, y: 110, w: 640, h: 340 };
    var X = function (x) { return box.x + (x / 10) * box.w; };
    var Y = function (y) { return box.y + box.h - (y / 6) * box.h; };

    ctx.save();
    ctx.strokeStyle = '#9aa6b3'; ctx.lineWidth = 1.4;
    ctx.strokeRect(box.x, box.y, box.w, box.h);
    ctx.strokeStyle = 'rgba(150,165,180,0.5)'; ctx.lineWidth = 1;
    for (var i = 1; i < 5; i++) {
      ctx.beginPath(); ctx.moveTo(box.x + box.w * i / 5, box.y); ctx.lineTo(box.x + box.w * i / 5, box.y + box.h); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(box.x, box.y + box.h * i / 5); ctx.lineTo(box.x + box.w, box.y + box.h * i / 5); ctx.stroke();
    }
    ctx.restore();

    function curve(mult, color, dash) {
      var k = Math.pow(2, (t - 25) / 10) * mult;
      var peak = Math.min(5.5, Math.max(0.6, k * c));
      ctx.save();
      ctx.strokeStyle = color; ctx.lineWidth = 3; ctx.lineCap = 'round';
      if (dash) ctx.setLineDash([8, 6]);
      ctx.beginPath();
      for (var s = 0; s <= 100; s++) {
        var tt = (10 * s) / 100;
        var y = peak * Math.exp(-tt * (0.6 + (dash ? 0.2 : 0)));
        if (s === 0) ctx.moveTo(X(tt), Y(y)); else ctx.lineTo(X(tt), Y(y));
      }
      ctx.stroke();
      ctx.restore();
    }
    curve(1, '#2f86c4', false);
    curve(catalyst ? 3 : 0.55, '#a3362b', true);

    v.text({ text: '反应速率 v（相对值）', x: box.x, y: box.y - 22, size: 12, align: 'left' });
    v.text({ text: '时间 / 相对单位', x: box.x + box.w - 8, y: box.y + box.h + 26, size: 12, align: 'right' });
    v.text({ text: '实线：当前条件', x: box.x + 22, y: box.y + 26, size: 11, align: 'left', color: '#2f86c4' });
    v.text({ text: '虚线：' + (catalyst ? '加催化剂' : '基准条件'), x: box.x + 22, y: box.y + 50, size: 11, align: 'left', color: '#a3362b' });

    if (result) {
      v.pill({ text: '相对速率 ' + Number(result.rate_relative).toFixed(2), x: 450, y: 74, size: 12 });
      v.pill({ text: '平衡转化率 ' + Number(result.conversion_percent).toFixed(1) + ' %', x: 720, y: 74, size: 12, bg: '#2f7a55' });
      v.text({ text: '达平衡约 ' + Number(result.time_to_equilibrium_s).toFixed(2) + ' s（相对时间）',
               x: 450, y: 500, size: 13, weight: 600 });
      v.text({ text: String(result.temperature_effect), x: 450, y: 532, size: 12, color: '#5b6875' });
      v.text({ text: String(result.catalyst_effect), x: 450, y: 558, size: 12, color: '#5b6875' });
    }
    cv.setAttribute('aria-label', '反应速率随时间下降的曲线，对比加催化剂与基准条件');
  }
  if (window.CHEM) window.CHEM.rateEquilibrium = rateEquilibrium;
})();

/* ===== 金属活动性顺序表 + 烧杯（追加式注册，2026-11） ===== */
(function () {
  function metalActivity(cv, request, result) {
    var v = window.VIS;
    if (!v.mount(cv, { DW: 900, DH: 640 })) return;
    v.clear();
    var ctx = v.S.ctx;
    v.wall({ tableY: 566 });

    var ORDER = ['Mg', 'Zn', 'Fe', 'H', 'Cu', 'Ag'];
    var metal = String(request.metal || 'Fe');
    var target = String(request.salt_solution || 'CuSO4');

    // 活动性顺序表（左侧竖排）
    v.text({ text: '金属活动性由强到弱', x: 150, y: 120, size: 12, weight: 600 });
    for (var i = 0; i < ORDER.length; i++) {
      var y = 160 + i * 56;
      var active = ORDER[i] === metal;
      ctx.save();
      var g = ctx.createLinearGradient(96, 0, 204, 0);
      if (ORDER[i] === 'H') { g.addColorStop(0, '#eef1f4'); g.addColorStop(1, '#c8ced6'); }
      else if (active) { g.addColorStop(0, '#f6d9a8'); g.addColorStop(1, '#d99441'); }
      else { g.addColorStop(0, '#e7eef6'); g.addColorStop(1, '#aebdcd'); }
      ctx.fillStyle = g;
      ctx.beginPath();
      if (ctx.roundRect) ctx.roundRect(96, y, 108, 40, 8); else ctx.rect(96, y, 108, 40);
      ctx.fill();
      ctx.strokeStyle = 'rgba(70,84,98,0.35)'; ctx.lineWidth = 1; ctx.stroke();
      ctx.restore();
      v.text({ text: ORDER[i], x: 150, y: y + 26, size: 14, weight: active ? 700 : 500 });
    }

    // 烧杯
    var cx = 560, base = 520, hw = 130, h = 280;
    v.glass({ x: cx, base: base, hw: hw, h: h, kind: 'beaker', pour: true });
    var deep = target === 'CuSO4' ? 1 : 0;
    v.liquid({
      level: 0.62,
      top: deep ? 'rgba(120,190,235,0.95)' : 'rgba(215,230,240,0.95)',
      bot: deep ? 'rgba(40,120,190,0.95)' : 'rgba(180,200,215,0.95)',
      t: 0, ripple: true, bubbles: String(request.salt_solution) === 'HCl' ? 5 : 0
    });
    // 金属片
    ctx.save();
    var mg = ctx.createLinearGradient(cx - 14, 0, cx + 14, 0);
    mg.addColorStop(0, '#e9eef4'); mg.addColorStop(0.5, '#b7c3d1'); mg.addColorStop(1, '#7d8b9b');
    ctx.fillStyle = mg;
    ctx.beginPath();
    if (ctx.roundRect) ctx.roundRect(cx - 14, 300, 28, 180, 4); else ctx.rect(cx - 14, 300, 28, 180);
    ctx.fill();
    ctx.strokeStyle = 'rgba(60,74,88,0.4)'; ctx.lineWidth = 1; ctx.stroke();
    ctx.restore();
    v.text({ text: metal + ' 片', x: cx + 96, y: 320, size: 12, align: 'left' });
    v.text({ text: String(request.salt_solution), x: cx, y: base + 30, size: 12 });

    if (result) {
      v.pill({ text: result.reacts ? '能反应' : '不反应', x: 760, y: 120, size: 13,
               bg: result.reacts ? '#2f7a55' : '#a3362b' });
      v.text({ text: String(result.equation), x: 560, y: 596, size: 13, weight: 600 });
      v.text({ text: String(result.phenomenon), x: 560, y: 626 > 630 ? 624 : 626, size: 12, color: '#5b6875' });
    }
    cv.setAttribute('aria-label', '金属活动性顺序表与盛有盐溶液的烧杯，判定能否发生置换反应');
  }
  if (window.CHEM) window.CHEM.metalActivity = metalActivity;
})();

/* ===== 两类变化对照（追加式注册，2026-11） ===== */
(function () {
  function changeType(cv, request, result) {
    var v = window.VIS;
    if (!v.mount(cv, { DW: 900, DH: 640 })) return;
    v.clear();
    var ctx = v.S.ctx;
    v.wall({ tableY: 566 });

    var isChemical = result ? !!result.is_chemical : false;
    function panel(x, title, color, active) {
      var w = 320, h = 240, y = 200;
      ctx.save();
      var g = ctx.createLinearGradient(x, y, x + w, y + h);
      g.addColorStop(0, active ? color[0] : '#f7fafc');
      g.addColorStop(1, active ? color[1] : '#e6edf4');
      ctx.fillStyle = g;
      ctx.beginPath();
      if (ctx.roundRect) ctx.roundRect(x, y, w, h, 16); else ctx.rect(x, y, w, h);
      ctx.fill();
      ctx.strokeStyle = active ? color[2] : 'rgba(90,105,120,0.35)';
      ctx.lineWidth = active ? 3 : 1.2;
      ctx.stroke();
      ctx.restore();
      v.text({ text: title, x: x + w / 2, y: y + 46, size: 16, weight: 700 });
      v.text({ text: active ? '← 当前现象属于这一类' : ' ', x: x + w / 2, y: y + h - 34, size: 12,
               color: active ? color[2] : '#8b98a6' });
    }
    panel(110, '物理变化', ['#e8f2fb', '#c9dff2', '#2f86c4'], !isChemical);
    panel(470, '化学变化', ['#fbeeee', '#f2d3d0', '#a3362b'], isChemical);

    if (result) {
      v.pill({ text: String(result.phenomenon), x: 450, y: 110, size: 14, bg: isChemical ? '#a3362b' : '#2f86c4' });
      v.text({ text: '判断依据：' + String(result.criterion), x: 450, y: 480, size: 13, weight: 600 });
      v.text({ text: String(result.reason), x: 450, y: 512, size: 12, color: '#5b6875' });
    }
    cv.setAttribute('aria-label', '物理变化与化学变化两栏对照，标出当前现象所属类别');
  }
  if (window.CHEM) window.CHEM.changeType = changeType;
})();

/* ===== 原电池装置（追加式注册，2026-11） ===== */
(function () {
  function galvanicCell(cv, request, result) {
    var v = window.VIS;
    if (!v.mount(cv, { DW: 900, DH: 640 })) return;
    v.clear();
    var ctx = v.S.ctx;
    v.wall({ tableY: 566 });

    var a = String(request.electrode_a || 'Zn');
    var b = String(request.electrode_b || 'Cu');
    var anode = result ? String(result.anode) : (a < b ? a : b);
    var cathode = result ? String(result.cathode) : (a < b ? b : a);

    // 烧杯
    var cx = 450, base = 520, hw = 250, h = 240;
    v.glass({ x: cx, base: base, hw: hw, h: h, kind: 'beaker', pour: true });
    v.liquid({ level: 0.62, top: 'rgba(150,205,235,0.95)', bot: 'rgba(60,140,200,0.95)', t: 0, ripple: true, bubbles: 0 });

    function electrode(x, metal, role) {
      ctx.save();
      var g = ctx.createLinearGradient(x - 18, 0, x + 18, 0);
      if (metal === 'Zn') { g.addColorStop(0, '#eef2f7'); g.addColorStop(0.5, '#bcc6d0'); g.addColorStop(1, '#8b98a4'); }
      else if (metal === 'Fe') { g.addColorStop(0, '#e9e3dc'); g.addColorStop(0.5, '#b3a99e'); g.addColorStop(1, '#847a6f'); }
      else if (metal === 'Cu') { g.addColorStop(0, '#f6dfc9'); g.addColorStop(0.5, '#d99a63'); g.addColorStop(1, '#a2653a'); }
      else { g.addColorStop(0, '#f4f6f8'); g.addColorStop(0.5, '#cfd6dd'); g.addColorStop(1, '#98a3ad'); }
      ctx.fillStyle = g;
      ctx.beginPath();
      if (ctx.roundRect) ctx.roundRect(x - 18, 300, 36, 220, 6); else ctx.rect(x - 18, 300, 36, 220);
      ctx.fill();
      ctx.strokeStyle = 'rgba(60,74,88,0.4)'; ctx.lineWidth = 1; ctx.stroke();
      ctx.restore();
      v.text({ text: metal, x: x, y: 286, size: 14, weight: 700 });
      v.pill({ text: role, x: x, y: 356, size: 11, bg: role === '负极' ? '#a3362b' : '#2f7a55' });
    }
    electrode(300, anode, '负极');
    electrode(600, cathode, '正极');

    // 导线 + 电子方向箭头
    ctx.save();
    ctx.strokeStyle = '#4a545e'; ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(300, 300); ctx.lineTo(300, 190); ctx.lineTo(600, 190); ctx.lineTo(600, 300);
    ctx.stroke();
    ctx.restore();
    ctx.save();
    ctx.strokeStyle = '#1b62b0'; ctx.lineWidth = 3; ctx.lineCap = 'round';
    ctx.beginPath(); ctx.moveTo(390, 190); ctx.lineTo(500, 190); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(500, 190); ctx.lineTo(486, 182); ctx.lineTo(486, 198); ctx.closePath();
    ctx.fillStyle = '#1b62b0'; ctx.fill();
    ctx.restore();
    v.text({ text: 'e⁻', x: 445, y: 172, size: 13, weight: 600, color: '#1b62b0' });

    if (result) {
      v.pill({ text: '电动势 ' + Number(result.emf_v).toFixed(2) + ' V', x: 450, y: 92, size: 14 });
      v.text({ text: '负极：' + String(result.anode_reaction), x: 450, y: 596, size: 12 });
      v.text({ text: '正极：' + String(result.cathode_reaction), x: 450, y: 622, size: 12 });
    }
    cv.setAttribute('aria-label', '原电池装置：两种金属电极、盛电解液的烧杯、导线与电子流向箭头');
  }
  if (window.CHEM) window.CHEM.galvanicCell = galvanicCell;
})();

/* ===== 异构体清单（追加式注册，2026-11） ===== */
(function () {
  function isomerCount(cv, request, result) {
    var v = window.VIS;
    if (!v.mount(cv, { DW: 900, DH: 640 })) return;
    v.clear();
    var ctx = v.S.ctx;
    v.wall({ tableY: 566 });

    var names = result ? result.names : [];
    var formula = result ? String(result.formula) : String(request.formula || 'C5H12');
    v.pill({ text: formula, x: 450, y: 96, size: 15 });

    if (result) {
      v.text({ text: '直链 ' + result.chain_count + ' 种 + 支链 ' + result.branched_count + ' 种 = '
               + result.total + ' 种', x: 450, y: 148, size: 13, weight: 600 });
      v.text({ text: String(result.note), x: 450, y: 180, size: 12, color: '#5b6875' });
      for (var i = 0; i < names.length; i++) {
        var y = 236 + i * 76;
        ctx.save();
        var g = ctx.createLinearGradient(200, y, 700, y + 56);
        g.addColorStop(0, '#f2f8fd'); g.addColorStop(1, '#dbe9f5');
        ctx.fillStyle = g;
        ctx.beginPath();
        if (ctx.roundRect) ctx.roundRect(200, y, 500, 56, 10); else ctx.rect(200, y, 500, 56);
        ctx.fill();
        ctx.strokeStyle = 'rgba(70,120,160,0.35)'; ctx.lineWidth = 1; ctx.stroke();
        ctx.restore();
        v.text({ text: (i + 1) + '. ' + names[i], x: 470, y: y + 34, size: 13, align: 'left' });
      }
    }
    cv.setAttribute('aria-label', '同分异构体清单，逐条列出碳骨架异构体名称');
  }
  if (window.CHEM) window.CHEM.isomerCount = isomerCount;
})();

/* ===== 晶胞示意（追加式注册，2026-11） ===== */
(function () {
  function crystalLattice(cv, request, result) {
    var v = window.VIS;
    if (!v.mount(cv, { DW: 900, DH: 640 })) return;
    v.clear();
    var ctx = v.S.ctx;
    v.wall({ tableY: 566 });

    var n = result ? Number(result.coordination) : 6;
    var ox = 450, oy = 320, size = 150;

    // 晶胞棱
    ctx.save();
    ctx.strokeStyle = 'rgba(90,105,120,0.55)'; ctx.lineWidth = 1.6;
    var pts = [[-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1],
               [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1]];
    function proj(p) { return [ox + p[0] * size * 0.8 + p[2] * size * 0.45,
                               oy + p[1] * size * 0.55 - p[2] * size * 0.35]; }
    var edges = [[0,1],[1,2],[2,3],[3,0],[4,5],[5,6],[6,7],[7,4],[0,4],[1,5],[2,6],[3,7]];
    for (var e = 0; e < edges.length; e++) {
      var a = proj(pts[edges[e][0]]), b = proj(pts[edges[e][1]]);
      ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]); ctx.stroke();
    }
    ctx.restore();

    // 顶点与面心粒子
    var corners = pts.map(proj);
    var faces = [[0,0,-1],[0,0,1],[0,-1,0],[0,1,0],[-1,0,0],[1,0,0]].map(function (f) {
      return proj([f[0] * size / size, f[1], f[2]]);
    });
    function ball(x, y, r, color) {
      ctx.save();
      var g = ctx.createRadialGradient(x - r * 0.35, y - r * 0.4, r * 0.2, x, y, r);
      g.addColorStop(0, '#ffffff'); g.addColorStop(0.45, color[0]); g.addColorStop(1, color[1]);
      ctx.fillStyle = g;
      ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = 'rgba(60,74,88,0.3)'; ctx.lineWidth = 1; ctx.stroke();
      ctx.restore();
    }
    for (var i = 0; i < corners.length; i++) ball(corners[i][0], corners[i][1], 11, ['#9ec6e8', '#3b7bb0']);
    for (var j = 0; j < faces.length; j++) ball(faces[j][0], faces[j][1], 13, ['#f0c9a8', '#b0703a']);

    v.text({ text: '顶点粒子与面心粒子', x: 450, y: 96, size: 12, color: '#5b6875' });
    if (result) {
      v.pill({ text: String(result.name) + ' · ' + String(result.crystal_type), x: 450, y: 520, size: 13 });
      v.pill({ text: '配位数 ' + n + ' · 晶胞粒子数 ' + result.cell_particles, x: 450, y: 560, size: 12, bg: '#2f7a55' });
      v.text({ text: String(result.note), x: 450, y: 604, size: 12, color: '#5b6875' });
    }
    cv.setAttribute('aria-label', '晶胞示意：顶点与面心粒子，标注配位数与晶胞粒子数');
  }
  if (window.CHEM) window.CHEM.crystalLattice = crystalLattice;
})();
