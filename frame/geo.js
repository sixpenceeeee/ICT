/* geo.js —— 地理学科场景库（基于 vis.js 原语，外壳注入）
 *
 *   GEO.earth(cv, {                   // 地球光照 / 经纬网
 *     tilt: 23.5,                     // 地轴倾角（度）
 *     season: 'summer'|'winter'|'equinox',
 *     spin: 0.35,                     // 自转相位 0~1
 *     sun: true                       // 是否画太阳平行光
 *   })
 *
 *   GEO.profile(cv, {                 // 地层剖面（等高线/岩层）
 *     layers: [{c:'#d9c9a8', name:'砂岩'}, ...]
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

  function earth(cv, cfg) {
    var v = V();
    cfg = cfg || {};
    if (!v.mount(cv, { DW: DW, DH: DH })) return;
    v.clear();
    var ctx = v.S.ctx;

    var tilt = (cfg.tilt == null ? 23.5 : cfg.tilt) * Math.PI / 180;
    var spin = cfg.spin == null ? 0.35 : cfg.spin;
    var cx = 452, cy = 300, R = 176;

    v.wall({ tableY: 600 });
    // 宇宙底色覆盖（地理页用深色星空更真实，但保持浅色平台一致性：用深蓝渐变 + 星点）
    var sky = ctx.createLinearGradient(0, 0, 0, DH);
    sky.addColorStop(0, '#0d2438');
    sky.addColorStop(0.55, '#14344d');
    sky.addColorStop(1, '#0a1d2e');
    ctx.fillStyle = sky;
    ctx.fillRect(-420, -420, DW + 840, DH + 840);
    // 星点（确定性）
    for (var s = 0; s < 130; s++) {
      var sx = v.spk(s) * DW, sy = v.spk(s + 200) * DH;
      ctx.beginPath();
      ctx.arc(sx, sy, 0.4 + v.spk(s + 400) * 1.1, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(220,238,255,' + (0.18 + v.spk(s + 600) * 0.5) + ')';
      ctx.fill();
    }

    // ---- 大气辉光 ----
    var halo = ctx.createRadialGradient(cx, cy, R * 0.88, cx, cy, R * 1.24);
    halo.addColorStop(0, 'rgba(120,190,255,0.34)');
    halo.addColorStop(0.5, 'rgba(90,160,235,0.14)');
    halo.addColorStop(1, 'rgba(70,140,220,0)');
    ctx.beginPath();
    ctx.arc(cx, cy, R * 1.24, 0, Math.PI * 2);
    ctx.fillStyle = halo;
    ctx.fill();

    // ---- 地球本体 ----
    var globe = ctx.createRadialGradient(cx - R * 0.4, cy - R * 0.42, R * 0.1, cx, cy, R);
    globe.addColorStop(0, '#8fd0f0');
    globe.addColorStop(0.32, '#4a9fd4');
    globe.addColorStop(0.72, '#1d6ba3');
    globe.addColorStop(1, '#0a3a60');
    ctx.save();
    ctx.beginPath();
    ctx.arc(cx, cy, R, 0, Math.PI * 2);
    ctx.fillStyle = globe;
    ctx.fill();
    ctx.clip();

    // 陆地（简化大陆轮廓：用多边形近似，教学示意足够）
    function land(pts, col) {
      ctx.beginPath();
      ctx.moveTo(cx + pts[0][0] * R, cy + pts[0][1] * R);
      for (var i = 1; i < pts.length; i++) {
        ctx.quadraticCurveTo(
          cx + pts[i][0] * R * 1.03, cy + pts[i][1] * R * 1.03,
          cx + pts[i][0] * R, cy + pts[i][1] * R
        );
      }
      ctx.closePath();
      ctx.fillStyle = col;
      ctx.fill();
    }
    land([[-0.62, -0.34], [-0.3, -0.48], [-0.08, -0.3], [-0.14, -0.06], [-0.36, 0.08], [-0.48, 0.36], [-0.62, 0.2], [-0.7, -0.06]], 'rgba(108,160,96,0.82)');
    land([[0.02, -0.42], [0.34, -0.46], [0.56, -0.2], [0.42, 0.06], [0.2, 0.12], [0.06, -0.08]], 'rgba(122,170,104,0.82)');
    land([[0.12, 0.16], [0.32, 0.1], [0.36, 0.4], [0.22, 0.56], [0.06, 0.38]], 'rgba(126,174,106,0.78)');
    land([[-0.42, -0.66], [-0.12, -0.7], [0.06, -0.56], [-0.3, -0.54]], 'rgba(226,240,248,0.9)');
    land([[-0.1, 0.66], [0.3, 0.62], [0.34, 0.86], [-0.06, 0.88]], 'rgba(232,244,250,0.92)');

    // 经纬网
    ctx.save();
    ctx.strokeStyle = 'rgba(220,240,255,0.34)';
    ctx.lineWidth = 1;
    for (var lat = -60; lat <= 60; lat += 30) {
      var yy = cy - R * Math.sin(lat * Math.PI / 180);
      var rx = R * Math.cos(lat * Math.PI / 180);
      ctx.beginPath();
      ctx.ellipse(cx, yy, rx, rx * 0.16, 0, 0, Math.PI * 2);
      ctx.stroke();
    }
    for (var lon = 0; lon < 180; lon += 30) {
      var ph = lon * Math.PI / 180 + spin * Math.PI;
      ctx.beginPath();
      ctx.ellipse(cx, cy, Math.abs(Math.cos(ph)) * R, R, 0, 0, Math.PI * 2);
      ctx.stroke();
    }
    ctx.restore();

    // 光照：太阳方向的亮面渐变
    var lit = ctx.createLinearGradient(cx - R, cy - R, cx + R, cy + R);
    lit.addColorStop(0, 'rgba(255,248,220,0.34)');
    lit.addColorStop(0.46, 'rgba(255,248,220,0.06)');
    lit.addColorStop(0.62, 'rgba(6,24,44,0.42)');
    lit.addColorStop(1, 'rgba(4,16,32,0.72)');
    ctx.fillStyle = lit;
    ctx.fillRect(cx - R, cy - R, R * 2, R * 2);
    ctx.restore();

    // 晨昏线
    ctx.save();
    ctx.beginPath();
    ctx.arc(cx, cy, R, 0, Math.PI * 2);
    ctx.clip();
    // 晨昏线：昼夜分界是一段弧，不是闭合椭圆
    ctx.beginPath();
    ctx.ellipse(cx - R * 0.12, cy, R * 0.34, R, 0, -Math.PI * 0.52, Math.PI * 0.52);
    ctx.strokeStyle = 'rgba(255,214,140,0.9)';
    ctx.lineWidth = 2.2;
    ctx.shadowColor = 'rgba(255,200,110,0.55)';
    ctx.shadowBlur = 8;
    ctx.stroke();
    ctx.shadowBlur = 0;
    ctx.restore();

    // 地球边缘高光
    ctx.beginPath();
    ctx.arc(cx, cy, R, 0, Math.PI * 2);
    ctx.strokeStyle = 'rgba(180,225,255,0.6)';
    ctx.lineWidth = 1.6;
    ctx.stroke();

    // ---- 地轴 ----
    var axLen = R * 1.3;
    var ax = Math.sin(tilt) * axLen, ay = Math.cos(tilt) * axLen;
    ctx.save();
    ctx.setLineDash([9, 6]);
    ctx.beginPath();
    ctx.moveTo(cx - ax, cy + ay);
    ctx.lineTo(cx + ax, cy - ay);
    ctx.strokeStyle = 'rgba(255,235,180,0.75)';
    ctx.lineWidth = 1.6;
    ctx.stroke();
    ctx.restore();

    // ---- 太阳与平行光 ----
    if (cfg.sun !== false) {
      var sunX = 96, sunY = 128, sunR = 34;
      var sg = ctx.createRadialGradient(sunX - 8, sunY - 8, 4, sunX, sunY, sunR);
      sg.addColorStop(0, '#fffbe8');
      sg.addColorStop(0.5, '#ffd75e');
      sg.addColorStop(1, '#f0a020');
      ctx.beginPath();
      ctx.arc(sunX, sunY, sunR, 0, Math.PI * 2);
      ctx.fillStyle = sg;
      ctx.fill();
      // 光晕
      var glow = ctx.createRadialGradient(sunX, sunY, sunR, sunX, sunY, sunR * 2.4);
      glow.addColorStop(0, 'rgba(255,214,110,0.34)');
      glow.addColorStop(1, 'rgba(255,214,110,0)');
      ctx.beginPath();
      ctx.arc(sunX, sunY, sunR * 2.4, 0, Math.PI * 2);
      ctx.fillStyle = glow;
      ctx.fill();
      // 平行光
      for (var r2 = 0; r2 < 4; r2++) {
        var ly = sunY + 26 + r2 * 46;
        v.ray({
          pts: [[sunX + sunR + 10, ly], [sunX + 250, ly]],
          color: 'rgba(255,214,120,0.85)', width: 1.8, glow: false
        });
      }
    }

    // ---- 文字（最后） ----
    v.text({ x: cx - ax - 16, y: cy + ay + 20, text: 'N', size: 15, weight: 700, color: '#ffe9b0', onDark: true });
    v.text({ x: cx + ax + 16, y: cy - ay - 20, text: 'S', size: 15, weight: 700, color: '#ffe9b0', onDark: true });
    v.text({ x: 100, y: 176, text: '太阳光', size: 13, weight: 700, color: '#ffe0a0', onDark: true });
    v.text({ x: cx, y: 54, text: '地球的光照与经纬网', size: 16, weight: 700, color: '#dff0ff', onDark: true });

    var seasonTxt = cfg.season === 'summer' ? '北半球夏季：太阳直射北回归线（23.5°N）'
      : cfg.season === 'winter' ? '北半球冬季：太阳直射南回归线（23.5°S）'
        : '春秋分：太阳直射赤道';
    var pn = v.panel({
      x: 620, y: 480, w: 256, h: 96,
      fill: 'rgba(16,42,64,0.86)', stroke: 'rgba(120,180,230,0.5)'
    });
    v.text({ x: pn.x + 16, y: pn.y + 28, text: seasonTxt, size: 13, weight: 700, color: '#dff0ff', align: 'left', stroke: false });
    v.text({ x: pn.x + 16, y: pn.y + 56, text: '地轴倾角 ' + (tilt * 180 / Math.PI).toFixed(1) + '°', size: 12, color: '#a9cbe6', align: 'left', stroke: false });
    v.text({ x: pn.x + 16, y: pn.y + 78, text: '晨昏线把地球分为昼半球与夜半球', size: 11.5, color: '#8fb4d0', align: 'left', stroke: false });

    say(cv, '装置：地球仪（地轴倾角 ' + (tilt * 180 / Math.PI).toFixed(1) + '°）· 太阳平行光 · 经纬网 · 晨昏线');
  }

  /* 地层剖面：多层岩层 + 断层 + 地表植被 */
  function profile(cv, cfg) {
    var v = V();
    cfg = cfg || {};
    if (!v.mount(cv, { DW: DW, DH: DH })) return;
    v.clear();
    var ctx = v.S.ctx;

    var layers = cfg.layers || [
      { c: '#d9c9a8', name: '砂岩' },
      { c: '#c0a887', name: '页岩' },
      { c: '#a89078', name: '石灰岩' },
      { c: '#8d7b6c', name: '花岗岩' }
    ];
    v.wall({ tableY: 86, tone: 'warm' });

    var x0 = 70, x1 = 830, top = 150, bottom = 540;
    var hEach = (bottom - top) / layers.length;
    // 地表起伏
    function surfY(x) {
      return top + Math.sin((x - x0) / 120) * 9 + Math.sin((x - x0) / 47) * 3.5;
    }
    layers.forEach(function (ly, i) {
      var yTop = top + i * hEach, yBot = top + (i + 1) * hEach;
      ctx.beginPath();
      ctx.moveTo(x0, i === 0 ? surfY(x0) : yTop);
      for (var x = x0; x <= x1; x += 6) {
        ctx.lineTo(x, i === 0 ? surfY(x) : yTop + Math.sin(x / 90 + i) * 3);
      }
      for (var x2 = x1; x2 >= x0; x2 -= 6) {
        ctx.lineTo(x2, yBot + Math.sin(x2 / 90 + i) * 3);
      }
      ctx.closePath();
      var g = ctx.createLinearGradient(0, yTop, 0, yBot);
      g.addColorStop(0, v.shade(ly.c, 0.12));
      g.addColorStop(1, v.shade(ly.c, -0.12));
      ctx.fillStyle = g;
      ctx.fill();
      ctx.strokeStyle = 'rgba(90,74,58,0.5)';
      ctx.lineWidth = 1.2;
      ctx.stroke();
      ly._y = (yTop + yBot) / 2;
    });

    // 地表草皮
    ctx.beginPath();
    ctx.moveTo(x0, surfY(x0));
    for (var sx = x0; sx <= x1; sx += 6) ctx.lineTo(sx, surfY(sx));
    ctx.strokeStyle = '#5f8f4d';
    ctx.lineWidth = 4;
    ctx.stroke();

    v.text({ x: 450, y: 110, text: '地层剖面（自地表向下）', size: 16, weight: 700, color: '#134f96' });
    layers.forEach(function (ly, i) {
      v.pill({ x: 760, y: ly._y, text: ly.name, bg: '#7a6550', size: 12 });
      v.leader({ x1: 700, y1: ly._y, x2: 736, y2: ly._y, dash: true });
    });
    say(cv, '装置：地层剖面，自上而下为 ' + layers.map(function (l) { return l.name; }).join('、'));
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
    if (window.__GEO_DRAWN__) return;
    var cv = document.querySelector('.exp-canvas-box canvas') || document.querySelector('canvas');
    if (!cv) return;
    // 页面自己画得出来就必须让位，否则两套版面抢同一张画布（见 isBlank 注释）
    if (!isBlank(cv)) { window.__GEO_DRAWN__ = true; return; }
    var txt = (document.body ? document.body.innerText : '') + ' ' + (document.title || '');
    if (/地球|经纬|晨昏|太阳直射|公转|自转/.test(txt)) {
      earth(cv, { tilt: 23.5, season: /夏至|夏季/.test(txt) ? 'summer' : /冬至|冬季/.test(txt) ? 'winter' : 'equinox' });
      window.__GEO_DRAWN__ = true;
    } else if (/地层|岩层|剖面|土壤/.test(txt)) {
      profile(cv, {});
      window.__GEO_DRAWN__ = true;
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

  window.GEO = { earth: earth, profile: profile, auto: auto };
})();
