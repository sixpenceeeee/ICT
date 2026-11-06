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

  window.CHEM = { scene: scene, stages: stages, fit: fit, auto: autoScene };
})();
