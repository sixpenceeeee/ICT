/* bio.js —— 生物学科场景库（基于 vis.js 原语，外壳注入）
 *
 *   BIO.microscope(cv, {              // 显微镜视野（装片观察）
 *     mag: 400,                       // 放大倍数
 *     cells: 7,                       // 视野内细胞数
 *     stain: 'onion' | 'blood' | 'leaf',
 *     labels: true
 *   })
 *   BIO.photosynthesis(cv, {           // 绿叶光照/遮光与碘液检验主图，不含步骤清单
 *     phase: 'light' | 'iodine', light: 510
 *   })
 */
(function () {
  'use strict';

  var DW = 900, DH = 640;

  function V() { return window.VIS; }
  function say(cv, txt) {
    cv.setAttribute('aria-label', txt);
    var tip = document.getElementById('tip');
    if (tip) tip.textContent = txt;
  }

  var STAIN = {
    onion: { wall: '#c9a6d8', wallDark: '#9a74b0', cyto: '#e6d3ee', nucleus: '#8e5aa8', name: '洋葱表皮细胞' },
    blood: { wall: '#e8b6b6', wallDark: '#c1797c', cyto: '#f6dede', nucleus: '#8f3f47', name: '人血涂片' },
    leaf:  { wall: '#9fc98a', wallDark: '#6d9a58', cyto: '#dcebc8', nucleus: '#4f7a3c', name: '叶肉细胞' }
  };

  function microscope(cv, cfg) {
    var v = V();
    cfg = cfg || {};
    if (!v.mount(cv, { DW: DW, DH: DH })) return;
    v.clear();
    var ctx = v.S.ctx;

    var mag = cfg.mag == null ? 400 : cfg.mag;
    var n = cfg.cells == null ? 7 : cfg.cells;
    var st = STAIN[cfg.stain || 'onion'] || STAIN.onion;

    v.wall({ tableY: 520 });

    // ---- 视野：圆形亮场 ----
    var cx = 398, cy = 306, R = 214;
    // 目镜外圈（金属镜筒）
    var ring = ctx.createRadialGradient(cx - 60, cy - 70, R * 0.5, cx, cy, R + 26);
    ring.addColorStop(0, '#eef3f8');
    ring.addColorStop(0.72, '#b8c6d4');
    ring.addColorStop(1, '#77899b');
    ctx.beginPath();
    ctx.arc(cx, cy, R + 22, 0, Math.PI * 2);
    ctx.fillStyle = ring;
    ctx.fill();
    ctx.strokeStyle = 'rgba(90,110,130,0.6)';
    ctx.lineWidth = 1.5;
    ctx.stroke();
    // 螺纹高光
    ctx.save();
    ctx.beginPath();
    ctx.arc(cx, cy, R + 12, 0, Math.PI * 2);
    ctx.strokeStyle = 'rgba(255,255,255,0.5)';
    ctx.lineWidth = 2.2;
    ctx.stroke();
    ctx.restore();

    // 视野内部
    ctx.save();
    ctx.beginPath();
    ctx.arc(cx, cy, R, 0, Math.PI * 2);
    ctx.clip();

    // 亮场：中心最亮，边缘渐暗（真实显微镜照明）
    var field = ctx.createRadialGradient(cx - 30, cy - 40, 20, cx, cy, R);
    field.addColorStop(0, '#ffffff');
    field.addColorStop(0.55, '#fbfdff');
    field.addColorStop(0.86, '#eaf2fa');
    field.addColorStop(1, '#cfdeec');
    ctx.fillStyle = field;
    ctx.fillRect(cx - R, cy - R, R * 2, R * 2);

    // 细胞：按黄金角排布，大小略随机（确定性）
    var GOLD = 2.399963;
    var CELL = [];
    for (var i = 0; i < n; i++) {
      var rr0 = Math.sqrt((i + 0.6) / n) * R * 0.74;
      var ang = i * GOLD;
      var px = cx + Math.cos(ang) * rr0;
      var py = cy + Math.sin(ang) * rr0 * 0.92;
      var rw = (28 + v.spk(i + 7) * 12) * (1 - rr0 / R * 0.35);
      var rh = rw * (0.72 + v.spk(i + 31) * 0.26);
      var rot = v.spk(i + 51) * Math.PI;
      CELL.push({ x: px, y: py, r: rw });

      ctx.save();
      ctx.translate(px, py);
      ctx.rotate(rot);
      // 细胞外轮廓（不规则多边形，像真实细胞而非完美椭圆）
      var N = 18, poly = [];
      for (var k = 0; k < N; k++) {
        var a2 = k / N * Math.PI * 2;
        var wob = 1 + Math.sin(a2 * 3 + i) * 0.045 + v.spk(i * 20 + k) * 0.05;
        poly.push([Math.cos(a2) * rw * wob, Math.sin(a2) * rh * wob]);
      }
      function path() {
        ctx.beginPath();
        ctx.moveTo(poly[0][0], poly[0][1]);
        for (var q = 1; q < poly.length; q++) ctx.lineTo(poly[q][0], poly[q][1]);
        ctx.closePath();
      }
      // 细胞质
      path();
      var cg = ctx.createRadialGradient(-rw * 0.3, -rh * 0.35, 4, 0, 0, rw * 1.1);
      cg.addColorStop(0, v.shade(st.cyto, 0.35));
      cg.addColorStop(1, st.cyto);
      ctx.fillStyle = cg;
      ctx.fill();
      // 细胞壁（双层线）
      path();
      ctx.strokeStyle = st.wallDark;
      ctx.lineWidth = 3.2;
      ctx.stroke();
      path();
      ctx.strokeStyle = v.rgba(st.wall, 0.95);
      ctx.lineWidth = 1.4;
      ctx.stroke();
      // 细胞核
      var nr = rw * 0.3;
      var nx = -rw * 0.16, ny = -rh * 0.1;
      var ng = ctx.createRadialGradient(nx - nr * 0.3, ny - nr * 0.35, 2, nx, ny, nr);
      ng.addColorStop(0, v.shade(st.nucleus, 0.45));
      ng.addColorStop(1, v.shade(st.nucleus, -0.18));
      ctx.beginPath();
      ctx.ellipse(nx, ny, nr, nr * 0.86, 0.3, 0, Math.PI * 2);
      ctx.fillStyle = ng;
      ctx.fill();
      ctx.strokeStyle = v.shade(st.nucleus, -0.4);
      ctx.lineWidth = 1.2;
      ctx.stroke();
      // 核仁
      ctx.beginPath();
      ctx.arc(nx + nr * 0.26, ny + nr * 0.2, nr * 0.24, 0, Math.PI * 2);
      ctx.fillStyle = v.shade(st.nucleus, -0.35);
      ctx.fill();
      // 液泡（洋葱/叶肉）
      if (cfg.stain !== 'blood') {
        ctx.beginPath();
        ctx.ellipse(rw * 0.34, rh * 0.22, rw * 0.3, rh * 0.34, 0.4, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(255,255,255,0.55)';
        ctx.fill();
        ctx.strokeStyle = 'rgba(255,255,255,0.8)';
        ctx.lineWidth = 1;
        ctx.stroke();
      }
      ctx.restore();
    }

    // 视野边缘暗角（vignette）
    var vg = ctx.createRadialGradient(cx, cy, R * 0.62, cx, cy, R);
    vg.addColorStop(0, 'rgba(20,40,60,0)');
    vg.addColorStop(1, 'rgba(20,40,60,0.26)');
    ctx.fillStyle = vg;
    ctx.fillRect(cx - R, cy - R, R * 2, R * 2);
    ctx.restore();

    // 视野边框
    ctx.beginPath();
    ctx.arc(cx, cy, R, 0, Math.PI * 2);
    ctx.strokeStyle = 'rgba(70,95,120,0.8)';
    ctx.lineWidth = 3;
    ctx.stroke();

    // ---- 目镜测微尺（十字 + 刻度，只在刻度尺线上） ----
    ctx.save();
    ctx.beginPath();
    ctx.moveTo(cx - R + 18, cy);
    ctx.lineTo(cx + R - 18, cy);
    ctx.moveTo(cx, cy - R + 18);
    ctx.lineTo(cx, cy + R - 18);
    ctx.strokeStyle = 'rgba(30,60,90,0.26)';
    ctx.lineWidth = 1;
    ctx.stroke();
    for (var t = -10; t <= 10; t++) {
      var tx = cx + t * 16;
      if (Math.abs(tx - cx) > R - 30) continue;
      ctx.beginPath();
      ctx.moveTo(tx, cy - (t % 5 === 0 ? 8 : 4));
      ctx.lineTo(tx, cy + (t % 5 === 0 ? 8 : 4));
      ctx.strokeStyle = 'rgba(30,60,90,0.34)';
      ctx.stroke();
    }
    ctx.restore();

    // ---- 右侧信息面板 ----
    var pn = v.panel({ x: 646, y: 132, w: 232, h: 168 });
    v.text({ x: pn.x + 18, y: pn.y + 26, text: '观察记录', size: 15, weight: 700, color: '#134f96', align: 'left', stroke: false });
    v.text({ x: pn.x + 18, y: pn.y + 58, text: '标本：' + st.name, size: 13, color: '#3d6c92', align: 'left', stroke: false });
    v.text({ x: pn.x + 18, y: pn.y + 84, text: '放大倍数：' + mag + '×', size: 13, color: '#3d6c92', align: 'left', stroke: false });
    v.text({ x: pn.x + 18, y: pn.y + 110, text: '视野直径：约 ' + (n > 5 ? '0.45' : '0.9') + ' mm', size: 13, color: '#3d6c92', align: 'left', stroke: false });
    v.text({ x: pn.x + 18, y: pn.y + 138, text: '细胞数：' + n + ' 个', size: 13, weight: 700, color: '#0d4d7a', align: 'left', stroke: false });

    // ---- 标注（最后画）：引线端点吸附到真实细胞边缘，不悬空 ----
    function annotate(idx, label, bg, lx, ly) {
      var c = CELL[idx % CELL.length];
      if (!c) return;
      var dx = lx - c.x, dy = ly - c.y;
      var len = Math.sqrt(dx * dx + dy * dy) || 1;
      v.leader({
        x1: lx - dx / len * 46, y1: ly - dy / len * 22,
        x2: c.x + dx / len * c.r * 0.92, y2: c.y + dy / len * c.r * 0.92
      });
      v.pill({ x: lx, y: ly, text: label, bg: bg, size: 12 });
    }
    annotate(4, '细胞壁', '#7a5a92', cx - 232, cy - 96);
    annotate(3, '细胞核', '#8e5aa8', cx + 176, cy + 128);
    annotate(5, '液泡', '#4f8a6d', cx + 172, cy - 118);

    v.text({ x: cx, y: 46, text: '显微镜视野（' + mag + '×）', size: 15, weight: 700, color: '#134f96' });
    v.text({
      x: cx, y: 566,
      text: '视野亮度均匀、边缘略暗；细胞壁呈双层结构，细胞核染色最深',
      size: 13, color: '#3d6c92'
    });

    say(cv, '装置：显微镜（' + mag + '×）· 载玻片装片 · ' + st.name + '，视野内可见 ' + n + ' 个细胞');
  }

  // 光合作用探究主图：有机叶形、分叉叶脉、透射光影与真实实验的局部遮光/显色。
  // 仅绘制实验对象，不在演示画布里绘制实验步骤、步骤列表或操作按钮。
  function photosynthesis(cv, cfg) {
    var v = V();
    cfg = cfg || {};
    if (!v.mount(cv, { DW: DW, DH: DH })) return;
    v.clear();
    var ctx = v.S.ctx;
    var phase = cfg.phase || 'light';
    var light = v.clamp(Number(cfg.light == null ? 510 : cfg.light), 0, 1200);
    var result = phase === 'iodine';

    // 柔和实验室背景与台面，减弱矢量贴纸感。
    var bg = ctx.createLinearGradient(0, 0, 0, DH);
    bg.addColorStop(0, '#f8fbff'); bg.addColorStop(0.72, '#edf4fa'); bg.addColorStop(1, '#dbe7f1');
    ctx.fillStyle = bg; ctx.fillRect(0, 0, DW, DH);
    ctx.fillStyle = 'rgba(255,255,255,.62)'; ctx.fillRect(0, 0, DW, 300);
    ctx.fillStyle = '#d3e0ea'; ctx.fillRect(0, 510, DW, 130);
    ctx.fillStyle = 'rgba(82,111,137,.18)';
    ctx.beginPath(); ctx.ellipse(473, 492, 267, 24, 0, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = 'rgba(255,255,255,.62)'; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(0, 511); ctx.lineTo(DW, 511); ctx.stroke();

    // 光源与可见光束，只表示照射方向和强弱，不画实验步骤。
    var lx = 174, ly = 147;
    var glow = ctx.createRadialGradient(lx, ly, 7, lx, ly, 116);
    glow.addColorStop(0, 'rgba(255,221,112,.48)'); glow.addColorStop(1, 'rgba(255,221,112,0)');
    ctx.fillStyle = glow; ctx.beginPath(); ctx.arc(lx, ly, 116, 0, Math.PI * 2); ctx.fill();
    var sun = ctx.createRadialGradient(lx - 8, ly - 9, 2, lx, ly, 28);
    sun.addColorStop(0, '#fff7cc'); sun.addColorStop(.55, '#ffd45e'); sun.addColorStop(1, '#efa92e');
    ctx.fillStyle = sun; ctx.beginPath(); ctx.arc(lx, ly, 26, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = 'rgba(225,160,43,.8)'; ctx.lineWidth = 2; ctx.stroke();
    if (!result) {
      var beamAlpha = .10 + Math.min(light, 1200) / 1200 * .14;
      ctx.save(); ctx.globalAlpha = beamAlpha;
      var beam = ctx.createLinearGradient(185, 160, 450, 410);
      beam.addColorStop(0, '#fff2ae'); beam.addColorStop(1, 'rgba(255,235,169,0)');
      ctx.fillStyle = beam; ctx.beginPath(); ctx.moveTo(193, 160); ctx.lineTo(292, 201); ctx.lineTo(520, 439); ctx.lineTo(430, 461); ctx.closePath(); ctx.fill();
      ctx.restore();
    }

    // 叶柄与自然弯曲的叶片轮廓。
    ctx.save();
    ctx.translate(474, 337); ctx.rotate(-.16);
    ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    ctx.strokeStyle = '#557b42'; ctx.lineWidth = 17;
    ctx.beginPath(); ctx.moveTo(-214, 8); ctx.quadraticCurveTo(-270, 39, -308, 104); ctx.stroke();
    ctx.strokeStyle = '#a8c27a'; ctx.lineWidth = 5;
    ctx.beginPath(); ctx.moveTo(-214, 3); ctx.quadraticCurveTo(-266, 35, -304, 96); ctx.stroke();

    function leafPath() {
      ctx.beginPath();
      ctx.moveTo(-225, 0);
      ctx.bezierCurveTo(-169, -84, -45, -143, 73, -126);
      ctx.bezierCurveTo(145, -116, 202, -54, 229, -8);
      ctx.bezierCurveTo(177, 65, 81, 119, -25, 128);
      ctx.bezierCurveTo(-126, 137, -192, 75, -225, 0);
      ctx.closePath();
    }
    // 底部投影，随后裁切并填叶片材质。
    ctx.save(); ctx.translate(9, 13); leafPath(); ctx.fillStyle = 'rgba(35,63,35,.22)'; ctx.shadowColor = 'rgba(30,48,35,.22)'; ctx.shadowBlur = 20; ctx.fill(); ctx.restore();
    leafPath(); ctx.save(); ctx.clip();
    var leafGrad = ctx.createLinearGradient(-80, -130, 105, 135);
    if (result) {
      leafGrad.addColorStop(0, '#667044'); leafGrad.addColorStop(.48, '#d6bd57'); leafGrad.addColorStop(1, '#e6d78a');
    } else {
      leafGrad.addColorStop(0, '#6c963f'); leafGrad.addColorStop(.38, '#80ad4d'); leafGrad.addColorStop(.72, '#4f813c'); leafGrad.addColorStop(1, '#2d6638');
    }
    ctx.fillStyle = leafGrad; ctx.fillRect(-240, -150, 490, 310);
    // 不规则次级色泽区与细小斑点，模拟叶片表面纹理。
    for (var s = 0; s < 42; s++) {
      var sx = -207 + v.spk(s + 801) * 407, sy = -103 + v.spk(s + 911) * 206;
      ctx.fillStyle = result ? 'rgba(65,54,31,.10)' : 'rgba(219,239,151,' + (.06 + v.spk(s + 31) * .10) + ')';
      ctx.beginPath(); ctx.ellipse(sx, sy, 2 + v.spk(s + 51) * 5, 1.2 + v.spk(s + 91) * 2.4, v.spk(s + 111) * 3.14, 0, Math.PI * 2); ctx.fill();
    }
    // 碘液显色区：见光部分呈蓝黑色，遮光部分保留黄褐色。
    if (result) {
      ctx.save(); ctx.beginPath(); ctx.rect(-225, -150, 228, 300); ctx.clip();
      var stain = ctx.createLinearGradient(-225, -90, 8, 90);
      stain.addColorStop(0, 'rgba(25,35,76,.97)'); stain.addColorStop(.72, 'rgba(28,43,92,.96)'); stain.addColorStop(1, 'rgba(42,56,101,.88)');
      ctx.fillStyle = stain; ctx.fillRect(-225, -150, 230, 300); ctx.restore();
    } else if (phase === 'covered') {
      // 黑纸片只覆盖叶片中段，外形与叶片保持透视一致。
      var cover = ctx.createLinearGradient(-22, -70, 24, 72);
      cover.addColorStop(0, '#30343a'); cover.addColorStop(.5, '#171a1f'); cover.addColorStop(1, '#42464b');
      ctx.fillStyle = cover; ctx.fillRect(-22, -102, 45, 204);
      ctx.strokeStyle = 'rgba(255,255,255,.24)'; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.moveTo(-16, -92); ctx.lineTo(-16, 90); ctx.stroke();
    }
    // 主脉与羽状侧脉，越靠叶缘线越细、越淡。
    ctx.strokeStyle = result ? 'rgba(218,210,160,.86)' : 'rgba(218,235,177,.78)';
    ctx.lineCap = 'round'; ctx.beginPath(); ctx.moveTo(-220, 0); ctx.bezierCurveTo(-88, -3, 76, 4, 220, -7); ctx.lineWidth = 5; ctx.stroke();
    for (var j = 0; j < 9; j++) {
      var vx = -177 + j * 43;
      var upper = (j % 2 ? -1 : 1);
      var endY = upper * (96 - Math.abs(vx) * .25);
      ctx.beginPath(); ctx.moveTo(vx, 0); ctx.quadraticCurveTo(vx + 28, endY * .34, vx + 54, endY);
      ctx.lineWidth = 1.3 + (1 - Math.abs(vx) / 225) * 1.2; ctx.globalAlpha = .78 - Math.abs(vx) / 700; ctx.stroke();
      ctx.beginPath(); ctx.moveTo(vx + 40, endY * .66); ctx.quadraticCurveTo(vx + 62, endY * .75, vx + 76, endY * .91); ctx.lineWidth = .75; ctx.stroke();
    }
    ctx.globalAlpha = 1; ctx.restore();
    leafPath(); ctx.strokeStyle = result ? '#77704c' : '#3f7040'; ctx.lineWidth = 3; ctx.stroke();
    // 叶片表面一条柔和反光，避免塑料质感。
    ctx.strokeStyle = result ? 'rgba(255,245,197,.24)' : 'rgba(240,255,208,.25)'; ctx.lineWidth = 7;
    ctx.beginPath(); ctx.moveTo(-156, -42); ctx.bezierCurveTo(-88, -104, 14, -117, 88, -91); ctx.stroke();
    ctx.restore();

    // 简洁实验对象提示，画面内不出现步骤卡片和流程导航。
    ctx.fillStyle = 'rgba(255,255,255,.86)'; ctx.beginPath();
    ctx.moveTo(623, 100); ctx.lineTo(805, 100); ctx.quadraticCurveTo(821, 100, 821, 116);
    ctx.lineTo(821, 170); ctx.quadraticCurveTo(821, 186, 805, 186); ctx.lineTo(623, 186);
    ctx.quadraticCurveTo(607, 186, 607, 170); ctx.lineTo(607, 116);
    ctx.quadraticCurveTo(607, 100, 623, 100); ctx.closePath(); ctx.fill();
    ctx.strokeStyle = 'rgba(121,153,180,.24)'; ctx.lineWidth = 1; ctx.stroke();
    ctx.fillStyle = '#315b7f'; ctx.font = '600 17px sans-serif'; ctx.textAlign = 'left';
    ctx.fillText(result ? '碘液检验结果' : '叶片光照实验', 626, 132);
    ctx.fillStyle = '#5c748a'; ctx.font = '14px sans-serif';
    ctx.fillText(result ? '见光区蓝黑 · 遮光区黄褐' : ('光照强度  ' + Math.round(light) + ' lx'), 626, 160);
    if (result) {
      ctx.fillStyle = '#293452'; ctx.beginPath(); ctx.arc(630, 177, 4, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = '#8a7740'; ctx.beginPath(); ctx.arc(789, 177, 4, 0, Math.PI * 2); ctx.fill();
    }
    ctx.textAlign = 'center';
    ctx.fillStyle = '#486780'; ctx.font = '13px sans-serif';
    ctx.fillText(result ? '同一叶片的见光区与遮光区对照' : '叶片接受光照，局部遮光用于对照', 450, 570);
    say(cv, result ? '绿叶光合作用实验图：同一叶片见光区经碘液呈蓝黑色，遮光区呈黄褐色；画面仅展示实验对象与结果图示。'
                   : '绿叶光合作用实验图：叶片接受光照，局部遮光作为对照；画面仅展示实验对象图示。');
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

  function auto() {
    if (window.__BIO_DRAWN__) return;
    var cv = document.querySelector('.exp-canvas-box canvas') || document.querySelector('canvas');
    if (!cv) return;
    // 页面自己画得出来就必须让位，否则两套版面抢同一张画布（见 isBlank 注释）
    if (!isBlank(cv)) { window.__BIO_DRAWN__ = true; return; }
    var txt = (document.body ? document.body.innerText : '') + ' ' + (document.title || '');
    if (/显微镜|细胞|装片|观察|染色/.test(txt)) {
      microscope(cv, {
        mag: /1000|100/.test(txt) ? 1000 : 400,
        cells: 7,
        stain: /血/.test(txt) ? 'blood' : /叶|绿|光合/.test(txt) ? 'leaf' : 'onion'
      });
      window.__BIO_DRAWN__ = true;
    }
  }
  /* 时机同样关键：必须等页面自己的脚本跑完、画完第一帧再判断是否兜底。
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

  window.BIO = { microscope: microscope, photosynthesis: photosynthesis, auto: auto };
})();
