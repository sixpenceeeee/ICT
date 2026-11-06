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
    var topC = mix(BLUE_T, GREEN_T, t), botC = mix(BLUE_B, GREEN_B, t);
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

    // 铁钉（钉帽在杯口外，整根先画钢色）
    if (opt.nail) drawNail(44, -BH - 70, -10, -34, 12, 'steel');

    // 浸入液面以下的部分：铜层 + 液体浸润
    ctx.save();
    bodyPath();
    ctx.clip();
    ctx.beginPath();
    ctx.rect(-BW, sy, BW * 2, -sy);
    ctx.clip();
    if (opt.nail && coat > 0.01) drawNail(44, -BH - 70, -10, -34, 14, 'copper');
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

  function label(x, y, text, opt) {
    opt = opt || {};
    ctx.font = (opt.weight || 600) + ' ' + (opt.size || 15) + 'px "Microsoft YaHei", system-ui, sans-serif';
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
    // 刻度数字
    for (var v2 = 20; v2 <= 100; v2 += 20) {
      var y2 = base - 8 - (BH - 52) * (v2 / 100);
      label(cx + BW - 12, y2 + 1, String(v2), {
        size: 11.5, weight: 600, align: 'right', color: '#1f5b7d', strokeWidth: 3
      });
    }
    label(cx + BW - 12, base - BH + 26, 'mL', {
      size: 11, align: 'right', color: '#3d7a99', strokeWidth: 3
    });
    // 液面处的体积与杯容量，两行分层，永不错行
    label(cx - BW + 12, base + surfaceY(V) + 18, 'V = ' + V + ' mL', {
      size: 11.5, align: 'left', color: '#1f5b7d', strokeWidth: 3
    });
    label(cx - BW + 12, base + surfaceY(V) + 34, '容量 100 mL', {
      size: 10.5, align: 'left', color: '#4b83a1', strokeWidth: 3
    });
  }

  function pill(cx, cy, text, bg, size) {
    size = size || 15;
    ctx.font = '600 ' + size + 'px "Microsoft YaHei", system-ui, sans-serif';
    var tw = ctx.measureText(text).width;
    var w = tw + 26, h = size + 17;
    ctx.save();
    ctx.shadowColor = 'rgba(22,52,86,0.2)';
    ctx.shadowBlur = 8;
    ctx.shadowOffsetY = 2;
    rr(cx - w / 2, cy - h / 2, w, h, h / 2);
    ctx.fillStyle = bg;
    ctx.fill();
    ctx.restore();
    label(cx, cy + 0.5, text, { size: size, color: '#ffffff', stroke: false });
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

  function formulaText() {
    var cx = 440, y = 604;
    var segs = [
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
    var total = 0;
    for (var i = 0; i < segs.length; i++) {
      ctx.font = '700 ' + segs[i].s + 'px "Microsoft YaHei", system-ui, sans-serif';
      segs[i].w = ctx.measureText(segs[i].t).width;
      total += segs[i].w;
    }
    var x = cx - total / 2;
    ctx.textAlign = 'left';
    ctx.textBaseline = 'alphabetic';
    for (var j = 0; j < segs.length; j++) {
      ctx.font = '700 ' + segs[j].s + 'px "Microsoft YaHei", system-ui, sans-serif';
      ctx.fillStyle = segs[j].c;
      ctx.fillText(segs[j].t, x, y + (segs[j].dy || 0));
      segs[j].cx = x + segs[j].w / 2;
      x += segs[j].w;
    }
    // 中文名：对齐到对应分子式的中心
    var names = ['铁', '硫酸铜', '硫酸亚铁', '铜'];
    var idx = [0, 2, 5, 8];
    for (var k = 0; k < names.length; k++) {
      label(segs[idx[k]].cx, 640, names[k], { size: 13, color: '#4d6a80', weight: 500, stroke: false });
    }
  }