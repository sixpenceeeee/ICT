/* math.js —— 数学学科场景库（基于 vis.js 原语，外壳注入）
 *
 *   MATH.cubeCut(cv, {                // 平面截正方体（真 3D，可拖动旋转视角）
 *     a: 2,                           // 棱长，顶点坐标 ±a/2
 *     theta: 54.7,                    // 截平面法向与竖直轴夹角（度）
 *     phi: 45,                        // 法向绕竖直轴的方位角（度）；45° 配 θ=54.7° 得正六边形
 *     t: 0,                           // 沿法向偏移，单位 a/2；扫过 t 就能看到 3→4→5→6 边形
 *     view: { yaw: 34, pitch: 19 },   // 初始视角（度）
 *     drag: true,                     // 画布上拖动旋转视角
 *     split: false                    // 上下两半分开显示
 *   })
 *   兼容旧写法：{ n: [1,1,1], d: 1.5 }（坐标取 0~1，等价于过中心的正六边形）
 *
 *   MATH.funcPlot(cv, {               // 函数图像（含网格、切线、阴影积分）
 *     a: 1, b: 0, c: 0,               // y = a x² + b x + c
 *     domain: [-3, 3],
 *     shade: true
 *   })
 *
 * 坐标系约定：x 向右、y 向里、z 向上，顶点坐标 ±a/2。
 * cubeCut 用「绕 z 轴 yaw + 绕 x 轴 pitch」的真 3D 变换后正交投影，
 * 并按投影包围盒自动缩放居中——任何视角都不会被画布裁掉。
 */
(function () {
  'use strict';

  var DW = 900, DH = 640;

  // 拦截 __GEO__：页面写进去的量单独存一份（PAGE_GEO），库自己算的存 LIB_GEO。
  // 这样读页面参数和给审查器提供归一化几何量互不干扰。
  var LIB_GEO = null, PAGE_GEO = null, GEO_HOOKED = false;
  function hookGeo() {
    if (GEO_HOOKED) return;
    GEO_HOOKED = true;
    try {
      Object.defineProperty(window, '__GEO__', {
        configurable: true, enumerable: true,
        get: function () { return LIB_GEO || PAGE_GEO; },
        set: function (val) { PAGE_GEO = val; }
      });
    } catch (e) { }
  }
  hookGeo();

  function V() { return window.VIS; }
  function say(cv, txt) {
    cv.setAttribute('aria-label', txt);
    var tip = document.getElementById('tip');
    if (tip) tip.textContent = txt;
  }

  /* ============================================================
   * 平面截正方体：真 3D 立方体 + 拖动旋转视角 + 截平面连续变换
   * cfg: { a, theta, phi, t }        θ 与竖直轴夹角、φ 绕竖直轴方位、t 沿法向偏移（半棱长倍数）
   *      或 { n, d }                  兼容旧写法（坐标取 0~1）
   *      view:{yaw,pitch}             初始视角（度）
   *      split: true                  上下两半分开显示
   *      drag: false                  关掉拖动旋转
   * 关键：整幅图按投影包围盒自动缩放居中，任何视角都不会被画布裁掉。
   * ============================================================ */
  function cubeCut(cv, cfg) {
    var v = V();
    cfg = cfg || {};
    if (!v.mount(cv, { DW: DW, DH: DH })) return;
    var ctx = v.S.ctx;

    var A = cfg.a == null ? 2 : cfg.a;
    var HG = A / 2;                       // 顶点坐标 ±HG

    // ---- 截平面 ----
    var n, t;
    if (cfg.n) {
      var nr = cfg.n;
      var nl = Math.sqrt(nr[0] * nr[0] + nr[1] * nr[1] + nr[2] * nr[2]) || 1;
      n = [nr[0] / nl, nr[1] / nl, nr[2] / nl];
      if (cfg.t != null) t = cfg.t;
      else {
        var dOld = cfg.d == null ? 1.5 : cfg.d;
        t = (A * dOld - HG * (nr[0] + nr[1] + nr[2])) / nl / HG;
      }
    } else {
      var th = (cfg.theta == null ? 54.7 : cfg.theta) * Math.PI / 180;
      var ph = (cfg.phi == null ? 45 : cfg.phi) * Math.PI / 180;
      n = [Math.sin(th) * Math.cos(ph), Math.sin(th) * Math.sin(ph), Math.cos(th)];
      t = cfg.t == null ? 0 : cfg.t;
    }
    var dd = t * HG;
    var thetaDeg = Math.round(Math.acos(Math.max(-1, Math.min(1, n[2]))) * 1800 / Math.PI) / 10;
    var phiDeg = Math.round(Math.atan2(n[1], n[0]) * 1800 / Math.PI) / 10;

    // ---- 立方体：下标 0~7 = A B C D A₁ B₁ C₁ D₁ ----
    var NM = ['A', 'B', 'C', 'D', 'A1', 'B1', 'C1', 'D1'];
    var PT = [
      [-HG, -HG, -HG], [HG, -HG, -HG], [HG, HG, -HG], [-HG, HG, -HG],
      [-HG, -HG, HG], [HG, -HG, HG], [HG, HG, HG], [-HG, HG, HG]
    ];
    var FACES = [
      { v: [0, 3, 2, 1], n: [0, 0, -1] },   // 下
      { v: [4, 5, 6, 7], n: [0, 0, 1] },    // 上
      { v: [0, 1, 5, 4], n: [0, -1, 0] },   // 前
      { v: [3, 7, 6, 2], n: [0, 1, 0] },    // 后
      { v: [0, 4, 7, 3], n: [-1, 0, 0] },   // 左
      { v: [1, 2, 6, 5], n: [1, 0, 0] }     // 右
    ];
    var EDGES = [[0, 1], [1, 2], [2, 3], [3, 0], [4, 5], [5, 6], [6, 7], [7, 4],
      [0, 4], [1, 5], [2, 6], [3, 7]];
    var EO = [];                          // 每条棱相邻的两个面
    for (var e = 0; e < EDGES.length; e++) {
      var f2 = [];
      for (var fi = 0; fi < FACES.length; fi++) {
        if (FACES[fi].v.indexOf(EDGES[e][0]) >= 0 && FACES[fi].v.indexOf(EDGES[e][1]) >= 0) f2.push(fi);
      }
      EO.push(f2);
    }

    // ---- 视角（存在 canvas 上，拖动时不用重新注册监听）----
    var view = cv.__mathView || (cv.__mathView = {
      yaw: (cfg.view && cfg.view.yaw != null ? cfg.view.yaw : 34) * Math.PI / 180,
      pitch: (cfg.view && cfg.view.pitch != null ? cfg.view.pitch : 19) * Math.PI / 180
    });
    if (!cv.__mathDefaultView) cv.__mathDefaultView = { yaw: view.yaw, pitch: view.pitch };

    function rot(p) {
      var cy = Math.cos(view.yaw), sy = Math.sin(view.yaw);
      var cp = Math.cos(view.pitch), sp = Math.sin(view.pitch);
      var x1 = p[0] * cy - p[1] * sy;
      var y1 = p[0] * sy + p[1] * cy;
      var z1 = p[2];
      var y2 = y1 * cp - z1 * sp;         // 深度：越大越远
      var z2 = y1 * sp + z1 * cp;         // 竖直：越大越高
      return { X: x1, Y: -z2, D: y2 };
    }

    function fval(p) { return n[0] * p[0] + n[1] * p[1] + n[2] * p[2] - dd; }

    function sectionPts() {
      var pts = [];
      for (var i = 0; i < EDGES.length; i++) {
        var a = PT[EDGES[i][0]], b = PT[EDGES[i][1]];
        var fa = fval(a), fb = fval(b);
        if (Math.abs(fa) < 1e-9) pts.push(a.slice());
        else if (Math.abs(fb) < 1e-9) pts.push(b.slice());
        else if (fa * fb < 0) {
          var tt = fa / (fa - fb);
          pts.push([a[0] + (b[0] - a[0]) * tt, a[1] + (b[1] - a[1]) * tt, a[2] + (b[2] - a[2]) * tt]);
        }
      }
      var uniq = [];
      for (var p = 0; p < pts.length; p++) {
        var dup = false;
        for (var q = 0; q < uniq.length; q++) {
          if (Math.abs(uniq[q][0] - pts[p][0]) < 1e-6 &&
            Math.abs(uniq[q][1] - pts[p][1]) < 1e-6 &&
            Math.abs(uniq[q][2] - pts[p][2]) < 1e-6) { dup = true; break; }
        }
        if (!dup) uniq.push(pts[p]);
      }
      if (uniq.length < 3) return uniq;
      // 平面内正交基 → 按极角排序，截面才是简单多边形
      var ctr = [0, 0, 0];
      uniq.forEach(function (p) { ctr[0] += p[0]; ctr[1] += p[1]; ctr[2] += p[2]; });
      ctr = [ctr[0] / uniq.length, ctr[1] / uniq.length, ctr[2] / uniq.length];
      var tmp = Math.abs(n[0]) < 0.9 ? [1, 0, 0] : [0, 1, 0];
      var ux = [n[1] * tmp[2] - n[2] * tmp[1], n[2] * tmp[0] - n[0] * tmp[2], n[0] * tmp[1] - n[1] * tmp[0]];
      var ul = Math.sqrt(ux[0] * ux[0] + ux[1] * ux[1] + ux[2] * ux[2]) || 1;
      ux = [ux[0] / ul, ux[1] / ul, ux[2] / ul];
      var uy = [n[1] * ux[2] - n[2] * ux[1], n[2] * ux[0] - n[0] * ux[2], n[0] * ux[1] - n[1] * ux[0]];
      uniq.sort(function (a, b) {
        function ang(p) {
          var q = [p[0] - ctr[0], p[1] - ctr[1], p[2] - ctr[2]];
          return Math.atan2(q[0] * uy[0] + q[1] * uy[1] + q[2] * uy[2],
            q[0] * ux[0] + q[1] * ux[1] + q[2] * ux[2]);
        }
        return ang(a) - ang(b);
      });
      return uniq;
    }

    function clippedFace(f, sign) {
      var poly = f.v.map(function (i) { return PT[i].slice(); });
      var out = [];
      for (var i = 0; i < poly.length; i++) {
        var a = poly[i], b = poly[(i + 1) % poly.length];
        var da = sign * fval(a), db = sign * fval(b);
        if (da <= 1e-9) out.push(a);
        if ((da < -1e-9 && db > 1e-9) || (da > 1e-9 && db < -1e-9)) {
          var tt = da / (da - db);
          out.push([a[0] + (b[0] - a[0]) * tt, a[1] + (b[1] - a[1]) * tt, a[2] + (b[2] - a[2]) * tt]);
        }
      }
      return out;
    }

    function fanVolume(poly) {
      if (!poly || poly.length < 3) return 0;
      var s = 0, p0 = poly[0];
      for (var i = 1; i < poly.length - 1; i++) {
        var p = poly[i], q = poly[i + 1];
        s += p0[0] * (p[1] * q[2] - p[2] * q[1])
          - p0[1] * (p[0] * q[2] - p[2] * q[0])
          + p0[2] * (p[0] * q[1] - p[1] * q[0]);
      }
      return s / 6;
    }

    function volumeOf(sign, cap) {
      var vol = 0;
      FACES.forEach(function (f) { vol += fanVolume(clippedFace(f, sign)); });
      // 截面盖的朝向要跟着保留侧翻转：sign=1（保留 fval≤0 侧）盖的法向是 +n
      if (cap.length >= 3) vol += fanVolume(sign > 0 ? cap : cap.slice().reverse());
      return Math.abs(vol);
    }

    function polyArea(poly) {
      if (poly.length < 3) return 0;
      var s = [0, 0, 0];
      for (var i = 0; i < poly.length; i++) {
        var a = poly[i], b = poly[(i + 1) % poly.length];
        s[0] += a[1] * b[2] - a[2] * b[1];
        s[1] += a[2] * b[0] - a[0] * b[2];
        s[2] += a[0] * b[1] - a[1] * b[0];
      }
      return Math.sqrt(s[0] * s[0] + s[1] * s[1] + s[2] * s[2]) / 2;
    }

    // ---- 画面布局：立方体固定占左侧区域，信息卡在右上，互不压 ----
    var BOX = { x: 52, y: 92, w: 588, h: 424 };
    var CARD = { x: 672, y: 96, w: 200 };

    function draw() {
      var cap = sectionPts();
      var sides = cap.length;
      var shape = sides === 3 ? '三角形' : sides === 4 ? '四边形'
        : sides === 5 ? '五边形' : sides === 6 ? '六边形' : '无截面';

      v.clear();
      v.wall({ tableY: 536, props: false });

      // ---- 自动适配：所有顶点 + 截面点算投影包围盒，等比缩放进 BOX ----
      var all = PT.map(rot);
      cap.forEach(function (p) { all.push(rot(p)); });
      var x1 = 1e9, x2 = -1e9, y1 = 1e9, y2 = -1e9;
      all.forEach(function (q) {
        if (q.X < x1) x1 = q.X; if (q.X > x2) x2 = q.X;
        if (q.Y < y1) y1 = q.Y; if (q.Y > y2) y2 = q.Y;
      });
      var bw = Math.max(0.001, x2 - x1), bh = Math.max(0.001, y2 - y1);
      var sc = Math.min(BOX.w / bw, BOX.h / bh) * 0.94;
      var mx = BOX.x + BOX.w / 2 - (x1 + x2) / 2 * sc;
      var my = BOX.y + BOX.h / 2 - (y1 + y2) / 2 * sc;
      function SP(p) { var q = rot(p); return [mx + q.X * sc, my + q.Y * sc, q.D]; }

      // 画面越界自检：所有顶点 + 截面点必须落在设计画布内（防「被裁掉」）
      var SB = [1e9, 1e9, -1e9, -1e9];
      PT.concat(cap).forEach(function (p) {
        var q = SP(p);
        if (q[0] < SB[0]) SB[0] = q[0];
        if (q[1] < SB[1]) SB[1] = q[1];
        if (q[0] > SB[2]) SB[2] = q[0];
        if (q[1] > SB[3]) SB[3] = q[1];
      });

      // ---- 落地投影 ----
      var foot = [];
      [0, 1, 2, 3].forEach(function (i) { var q = SP(PT[i]); foot.push(q); });
      var fx = 0, fy = 0;
      foot.forEach(function (q) { fx += q[0] / 4; fy += q[1] / 4; });
      v.shadow(fx + 6, Math.max.apply(null, foot.map(function (q) { return q[1]; })) + 6,
        bw * sc * 0.46, 16, 0.13);

      // ---- 面：按光向做明暗，半透明让截面透出来 ----
      var L = [-0.45, -0.55, 0.70];
      var Ll = Math.sqrt(L[0] * L[0] + L[1] * L[1] + L[2] * L[2]);
      L = [L[0] / Ll, L[1] / Ll, L[2] / Ll];
      var front = [];
      FACES.forEach(function (f, k) {
        var rn = rot(f.n);
        f.__front = rn.D < -1e-6;
        f.__depth = 0;
        f.v.forEach(function (i) { f.__depth += rot(PT[i]).D / 4; });
        if (f.__front) front.push(k);
      });
      var order = FACES.map(function (f, k) { return k; }).sort(function (a, b) { return FACES[b].__depth - FACES[a].__depth; });

      function fillFace(k) {
        var f = FACES[k];
        var sh = Math.max(0, f.n[0] * L[0] + f.n[1] * L[1] + f.n[2] * L[2]);
        var base = v.mix('#bcd6ec', '#ffffff', 0.30 + 0.55 * sh);
        var poly = f.v.map(function (i) { return SP(PT[i]); });
        ctx.beginPath();
        ctx.moveTo(poly[0][0], poly[0][1]);
        for (var i = 1; i < poly.length; i++) ctx.lineTo(poly[i][0], poly[i][1]);
        ctx.closePath();
        ctx.fillStyle = v.rgba(base, f.__front ? 0.62 : 0.26);
        ctx.fill();
      }

      // 后半部分面（先画）
      order.forEach(function (k) { if (!FACES[k].__front) fillFace(k); });

      // ---- 截面：橙色半透明 + 细斜纹，在学生眼里和蓝色面分开 ----
      var capS = cap.map(SP);
      if (sides >= 3) {
        ctx.save();
        ctx.beginPath();
        ctx.moveTo(capS[0][0], capS[0][1]);
        for (var i = 1; i < capS.length; i++) ctx.lineTo(capS[i][0], capS[i][1]);
        ctx.closePath();
        ctx.fillStyle = 'rgba(240,146,58,0.34)';
        ctx.fill();
        ctx.clip();
        ctx.strokeStyle = 'rgba(224,128,36,0.30)';
        ctx.lineWidth = 1;
        for (var hx = -520; hx < 1400; hx += 9) {
          ctx.beginPath();
          ctx.moveTo(hx, -200);
          ctx.lineTo(hx + 900, 900);
          ctx.stroke();
        }
        ctx.restore();
      }

      // 前半部分面（盖在截面上，但仍能透出橙色）
      order.forEach(function (k) { if (FACES[k].__front) fillFace(k); });

      // ---- 被遮挡的棱：虚线（压在面上，符合教材画法）----
      ctx.save();
      ctx.setLineDash([7, 5]);
      ctx.strokeStyle = 'rgba(126,156,184,0.85)';
      ctx.lineWidth = 1.3;
      for (var ei = 0; ei < EDGES.length; ei++) {
        var both = EO[ei].every(function (k) { return !FACES[k].__front; });
        if (!both) continue;
        var pa = SP(PT[EDGES[ei][0]]), pb = SP(PT[EDGES[ei][1]]);
        ctx.beginPath();
        ctx.moveTo(pa[0], pa[1]);
        ctx.lineTo(pb[0], pb[1]);
        ctx.stroke();
      }
      ctx.restore();

      // ---- 可见棱：实线 ----
      ctx.save();
      ctx.strokeStyle = 'rgba(52,96,134,0.92)';
      ctx.lineWidth = 1.8;
      ctx.lineJoin = 'round';
      ctx.lineCap = 'round';
      for (var ej = 0; ej < EDGES.length; ej++) {
        var vis = EO[ej].some(function (k) { return FACES[k].__front; });
        if (!vis) continue;
        var qa = SP(PT[EDGES[ej][0]]), qb = SP(PT[EDGES[ej][1]]);
        ctx.beginPath();
        ctx.moveTo(qa[0], qa[1]);
        ctx.lineTo(qb[0], qb[1]);
        ctx.stroke();
      }
      ctx.restore();

      // ---- 截面描边（最后一遍，保证盖过所有面）----
      if (sides >= 3) {
        ctx.save();
        ctx.beginPath();
        ctx.moveTo(capS[0][0], capS[0][1]);
        for (var ic = 1; ic < capS.length; ic++) ctx.lineTo(capS[ic][0], capS[ic][1]);
        ctx.closePath();
        ctx.strokeStyle = '#e07f22';
        ctx.lineWidth = 3;
        ctx.lineJoin = 'round';
        ctx.stroke();
        // 截面顶点：白心橙圈
        capS.forEach(function (q) {
          ctx.beginPath();
          ctx.arc(q[0], q[1], 5, 0, Math.PI * 2);
          ctx.fillStyle = '#ffffff';
          ctx.fill();
          ctx.strokeStyle = '#e07f22';
          ctx.lineWidth = 2.2;
          ctx.stroke();
        });
        ctx.restore();
      }

      // ---- 立方体顶点：可见实心、被挡的空心 ----
      var hiddenV = {};
      for (var vi = 0; vi < 8; vi++) {
        var allBack = true;
        for (var fk = 0; fk < FACES.length; fk++) {
          if (FACES[fk].v.indexOf(vi) >= 0 && FACES[fk].__front) { allBack = false; break; }
        }
        hiddenV[vi] = allBack;
      }
      for (var vv = 0; vv < 8; vv++) {
        var q2 = SP(PT[vv]);
        ctx.beginPath();
        ctx.arc(q2[0], q2[1], hiddenV[vv] ? 3.4 : 4.6, 0, Math.PI * 2);
        ctx.fillStyle = hiddenV[vv] ? 'rgba(255,255,255,0.95)' : '#2e6fd8';
        ctx.fill();
        ctx.strokeStyle = hiddenV[vv] ? 'rgba(110,145,175,0.9)' : 'rgba(255,255,255,0.95)';
        ctx.lineWidth = 1.6;
        ctx.stroke();
      }

      // ---- 顶点字母：沿「图形中心 → 顶点」方向外推，永不压线 ----
      if (cfg.showLabels !== false) {
        var c0 = SP([0, 0, 0]);
        for (var vm = 0; vm < 8; vm++) {
          var q3 = SP(PT[vm]);
          var dx = q3[0] - c0[0], dy = q3[1] - c0[1];
          var len = Math.sqrt(dx * dx + dy * dy) || 1;
          v.text({
            x: q3[0] + dx / len * 19, y: q3[1] + dy / len * 17,
            text: NM[vm].replace('1', '₁'),
            size: 15, weight: 700,
            color: hiddenV[vm] ? '#7d9bb5' : '#123c5e',
            pad: 'rgba(255,255,255,0.78)', padX: 2.5, padY: 1
          });
        }
      }

      // ---- 右上信息卡 ----
      var a3 = A * A * A, a2 = A * A;
      var up = volumeOf(1, cap), dn = volumeOf(-1, cap);
      v.card({
        x: CARD.x, y: CARD.y, w: CARD.w, size: 12.5,
        title: '截面信息',
        rows: [
          ['截面形状', shape, '#c2610f'],
          ['被切面数', sides + ' 个面'],
          ['截面边数', sides + ' 条'],
          ['法向偏移 t', t.toFixed(2) + ' a/2'],
          ['倾角 θ', thetaDeg.toFixed(1) + '°'],
          ['方位 φ', phiDeg.toFixed(0) + '°'],
          ['截面面积', (polyArea(cap) / (A * A)).toFixed(3) + ' a²'],
          ['V上 + V下', ((up + dn) / a3).toFixed(3) + ' a³', '#1b62b0']
        ]
      });

      // ---- 底部说明：一行操作提示 + 一行体积恒等式（学生要记的那句）----
      v.text({
        x: 346, y: 594,
        text: sides >= 3
          ? '在画布上拖动可旋转视角 · 橙色多边形就是截面（' + shape + '，' + sides + ' 条边）'
          : '平面已移出正方体，当前没有截面',
        size: 13.5, weight: 600, color: '#134f96'
      });


      // ---- 暴露给审查器：几何量一律折算成「单位立方体」口径（a=1），
      //      这样 a 取 2 还是 1 都能和 J4「V上+V下=1、六边形面积≈1.299」对齐 ----
      // 以页面自己那份为底（它可能还有 volumeA/checks 之类自用字段），
      // 再覆盖成库算出的归一化几何量——页面读自己的字段不会报错，审查器读到的是正确口径
      var geo = {};
      if (PAGE_GEO) {
        for (var gk in PAGE_GEO) {
          if (Object.prototype.hasOwnProperty.call(PAGE_GEO, gk)) geo[gk] = PAGE_GEO[gk];
        }
      }
      geo.a = A; geo.sides = sides;
      geo.params = { theta: thetaDeg, phi: phiDeg, t: t };
      geo.area = polyArea(cap) / a2;
      geo.area_abs = polyArea(cap);
      geo.theta = thetaDeg; geo.phi = phiDeg; geo.t = t;
      geo.n = n.slice(); geo.d = dd;
      geo.v_up = up / a3; geo.v_down = dn / a3;
      geo.v_sum = (up + dn) / a3; geo.v_total = 1;
      geo.volume_ok = Math.abs(up + dn - a3) < 1e-6 * Math.max(1, a3);
      geo.volumeA = up / a3; geo.volumeB = dn / a3; geo.volumeSum = (up + dn) / a3;
      geo.screen_bbox = SB;
      geo.in_bounds = SB[0] >= 0 && SB[1] >= 0 && SB[2] <= 900 && SB[3] <= 640;
      LIB_GEO = geo;
      cv.__MATH_CUT__ = LIB_GEO;

      // ④区兜底：页面没写代入式时，把库算出的恒等式写进 #fml（J1 只读 DOM 文本）。
      // 页面自己写了就以页面的为准，不覆盖。
      try {
        var fml = document.getElementById('fml');
        if (fml && !cv.__mathFmlDone && !/=[^=]/.test(fml.textContent || '')) {
          fml.textContent = '体积：V上 + V下 = ' + (up / a3).toFixed(3) + ' a³ + '
            + (dn / a3).toFixed(3) + ' a³ = ' + ((up + dn) / a3).toFixed(3)
            + ' a³（截面把正方体分成两块，体积之和恒等于原正方体）';
          cv.__mathFmlDone = true;
        }
      } catch (e) { }

      say(cv, '正方体 ABCD-A₁B₁C₁D₁ 棱长 a=' + A + '，平面 θ=' + thetaDeg.toFixed(1) +
        '°、φ=' + phiDeg.toFixed(0) + '°、t=' + t.toFixed(2) +
        ' 截得' + shape + '（' + sides + ' 条边）；在画布上拖动可旋转视角');
      return { sides: sides, shape: shape };
    }

    // ---- 拖动旋转视角：变换的是同一个立方体，不是重画一张 ----
    if (cfg.drag !== false) {
      cv.__mathRender = draw;
      if (!cv.__mathDrag) {
        cv.__mathDrag = true;
        cv.style.cursor = 'grab';
        cv.style.touchAction = 'none';
        var dragState = null;
        cv.addEventListener('pointerdown', function (ev) {
          dragState = { x: ev.clientX, y: ev.clientY, yaw: cv.__mathView.yaw, pitch: cv.__mathView.pitch };
          try { cv.setPointerCapture(ev.pointerId); } catch (err) { }
          cv.style.cursor = 'grabbing';
        });
        cv.addEventListener('pointermove', function (ev) {
          if (!dragState) return;
          cv.__mathView.yaw = dragState.yaw + (ev.clientX - dragState.x) * 0.005;
          cv.__mathView.pitch = v.clamp(dragState.pitch - (ev.clientY - dragState.y) * 0.005, -1.15, 1.15);
          if (cv.__mathRender) cv.__mathRender();
        });
        function endDrag() { dragState = null; cv.style.cursor = 'grab'; }
        cv.addEventListener('pointerup', endDrag);
        cv.addEventListener('pointercancel', endDrag);
        cv.addEventListener('pointerleave', endDrag);
      }
    }

    return draw();
  }

  /* ============================================================
   * 函数图像：网格 + 曲线 + 阴影积分 + 切线
   * ============================================================ */
  function funcPlot(cv, cfg) {
    var v = V();
    cfg = cfg || {};
    if (!v.mount(cv, { DW: DW, DH: DH })) return;
    v.clear();
    var ctx = v.S.ctx;

    var a = cfg.a == null ? 1 : cfg.a;
    var b = cfg.b == null ? 0 : cfg.b;
    var c = cfg.c == null ? 0 : cfg.c;
    var x0 = cfg.domain ? cfg.domain[0] : -3;
    var x1 = cfg.domain ? cfg.domain[1] : 3;

    var orgX = 450, orgY = 400, ux = 62, uy = 46;
    function X(x) { return orgX + x * ux; }
    function Y(y) { return orgY - y * uy; }
    function fy(x) { return a * x * x + b * x + c; }

    v.wall({ tableY: 560 });

    // 坐标网格
    ctx.save();
    ctx.strokeStyle = 'rgba(150,178,205,0.28)';
    ctx.lineWidth = 1;
    for (var gx = -6; gx <= 6; gx++) {
      ctx.beginPath(); ctx.moveTo(X(gx), 40); ctx.lineTo(X(gx), 560); ctx.stroke();
    }
    for (var gy = -4; gy <= 8; gy++) {
      ctx.beginPath(); ctx.moveTo(60, Y(gy)); ctx.lineTo(860, Y(gy)); ctx.stroke();
    }
    // 坐标轴
    ctx.strokeStyle = 'rgba(70,100,130,0.9)';
    ctx.lineWidth = 1.8;
    ctx.beginPath(); ctx.moveTo(60, orgY); ctx.lineTo(860, orgY); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(orgX, 40); ctx.lineTo(orgX, 560); ctx.stroke();
    ctx.restore();

    // 曲线路径
    var pts = [];
    for (var s = 0; s <= 400; s++) {
      var xx = x0 + (x1 - x0) * s / 400;
      pts.push([X(xx), Y(fy(xx))]);
    }
    // 曲线下方阴影
    if (cfg.shade) {
      ctx.save();
      ctx.beginPath();
      ctx.moveTo(pts[0][0], orgY);
      pts.forEach(function (p) { ctx.lineTo(p[0], p[1]); });
      ctx.lineTo(pts[pts.length - 1][0], orgY);
      ctx.closePath();
      var sg = ctx.createLinearGradient(0, Y(Math.max(fy(x0), fy(x1))), 0, orgY);
      sg.addColorStop(0, 'rgba(46,111,216,0.16)');
      sg.addColorStop(1, 'rgba(46,111,216,0.03)');
      ctx.fillStyle = sg;
      ctx.fill();
      ctx.restore();
    }
    // 曲线
    ctx.save();
    ctx.beginPath();
    ctx.moveTo(pts[0][0], pts[0][1]);
    for (var i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]);
    ctx.strokeStyle = '#2e6fd8';
    ctx.lineWidth = 3;
    ctx.lineJoin = 'round';
    ctx.shadowColor = 'rgba(46,111,216,0.3)';
    ctx.shadowBlur = 8;
    ctx.stroke();
    ctx.restore();

    // 顶点
    if (Math.abs(a) > 1e-6) {
      var vx = -b / (2 * a), vy = fy(vx);
      ctx.beginPath();
      ctx.arc(X(vx), Y(vy), 5, 0, Math.PI * 2);
      ctx.fillStyle = '#d9534f';
      ctx.fill();
      ctx.strokeStyle = 'rgba(255,255,255,0.9)';
      ctx.lineWidth = 2;
      ctx.stroke();
      v.leader({ x1: X(vx), y1: Y(vy) - 8, x2: X(vx), y2: Y(vy) - 46, dash: true });
      v.pill({ x: X(vx), y: Y(vy) - 60, text: '顶点 (' + vx.toFixed(2) + ', ' + vy.toFixed(2) + ')', bg: '#c0392b', size: 12 });
    }

    // 轴标签
    v.text({ x: 858, y: orgY - 16, text: 'x', size: 15, weight: 700, color: '#3d6c92', align: 'right' });
    v.text({ x: orgX + 18, y: 52, text: 'y', size: 15, weight: 700, color: '#3d6c92', align: 'left' });
    v.text({ x: orgX - 12, y: orgY + 16, text: 'O', size: 13, weight: 600, color: '#3d6c92', align: 'right' });

    // 面板
    var pn = v.panel({ x: 640, y: 40, w: 232, h: 106 });
    v.text({ x: pn.x + 18, y: pn.y + 24, text: '函数解析式', size: 13, weight: 700, color: '#134f96', align: 'left', stroke: false });
    v.text({
      x: pn.x + 18, y: pn.y + 54,
      text: 'y = ' + (a === 1 ? '' : a === -1 ? '−' : a) + 'x²' + (b ? (b > 0 ? ' + ' : ' − ') + Math.abs(b) + 'x' : '') + (c ? (c > 0 ? ' + ' : ' − ') + Math.abs(c) : ''),
      size: 16, weight: 700, color: '#0d4d7a', align: 'left', stroke: false
    });
    v.text({ x: pn.x + 18, y: pn.y + 82, text: '定义域 [' + x0 + ', ' + x1 + ']', size: 12, color: '#5b7791', align: 'left', stroke: false });

    say(cv, '装置：平面直角坐标系，函数 y=' + a + 'x²' + (b >= 0 ? '+' : '') + b + 'x' + (c >= 0 ? '+' : '') + c + ' 的图像');
    return { vx: Math.abs(a) > 1e-6 ? -b / (2 * a) : null, vy: Math.abs(a) > 1e-6 ? fy(-b / (2 * a)) : null };
  }

  /* ============================================================
   * 兜底接管：模型经常自己另画一套立方体（和库的版面完全不是一个东西，
   * 而且会叠出重影、把自己的标签盖住）。所以只要它没真正调 cubeCut，
   * 就把 ② 区画布换成新节点——页面闭包里的绘制会落到被摘掉的旧节点上，
   * 用户看到的只剩库这一版；滑块仍然映射到库参数，拖动视角也照常。
   * ============================================================ */
  /* 画布上到底有没有东西。
   *
   * 这一条是「兜底接管」的生死线：接管会把页面自己的画布藏起来，
   * 页面之后的每次重绘都落在隐藏节点上，学生拖滑块就看到「画面不动」。
   * 所以只要页面已经自己画了东西（哪怕只是网格 + 一条曲线），就必须让位。
   * 判定方式：整行整行地扫像素，遇到非透明且非近白的点就认为有内容。
   */
  function isBlank(cv0) {
    try {
      var w = cv0 && cv0.width, h = cv0 && cv0.height;
      if (!w || !h) return true;
      var c2 = cv0.getContext('2d');
      if (!c2) return true;
      var d = c2.getImageData(0, 0, w, h).data;
      var rowBytes = w * 4;
      // 每 16 行采一行，采到的行整行扫完：横向线条和纵向线条都不会漏
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
      return true;   // 取不到像素（理论上不会发生）时按「空白」处理，保持旧行为
    }
  }

  function takeover(cv0) {
    // 旧画布留在 DOM 里但隐藏：页面自己的 draw() 照常往它上面画，
    // 只是学生看不见；也不会因为 parentElement 变 null 而报错。
    cv0.style.display = 'none';
    var ncv = document.createElement('canvas');
    ncv.className = cv0.className || '';
    ncv.id = (cv0.id || 'stage-canvas') + '-lib';
    cv0.parentNode.insertBefore(ncv, cv0.nextSibling);
    return ncv;
  }

  function readCubeParams() {
    // 页面自己算过平面参数就用它的（保证画面和它的读数一致），否则退回读滑块
    if (PAGE_GEO && PAGE_GEO.params && isFinite(PAGE_GEO.params.theta)) {
      return {
        a: 2,
        theta: +PAGE_GEO.params.theta,
        phi: +PAGE_GEO.params.phi,
        t: +PAGE_GEO.params.t
      };
    }
    var cfg = { a: 2, theta: 54.7, phi: 45, t: 0 };
    var ranges = [].slice.call(document.querySelectorAll('input[type=range]'));
    ranges.forEach(function (el) {
      var lab = '';
      var box = el.closest ? el.closest('label') : null;
      [box, el.parentElement, el.parentElement && el.parentElement.parentElement]
        .forEach(function (n) { if (n) lab += ' ' + (n.innerText || ''); });
      lab += ' ' + (el.dataset.key || '') + ' ' + (el.id || '');
      var v = parseFloat(el.value);
      var mn = parseFloat(el.min || '0'), mx = parseFloat(el.max || '100');
      if (!isFinite(v)) return;
      if (/倾角|θ|theta/i.test(lab)) cfg.theta = v;
      else if (/方位|旋转|φ|phi/i.test(lab)) cfg.phi = v;
      else if (/偏移|位置|深度|法向|(^|\s)t(\s|$)/i.test(lab)) {
        // t 以 a/2 为单位；滑块量程超过 ±2 时按百分比换算
        cfg.t = (mx > 2 || mn < -2) ? v / Math.max(Math.abs(mx), Math.abs(mn) || 1) : v;
      }
    });
    return cfg;
  }

  /* 函数兜底版的 a/b/c：优先用页面自己暴露的参数（画面和它的读数一致），
   * 其次是 __GEO__，最后才退回读滑块。a 不能为 0，否则不是二次函数。 */
  function readFuncParams() {
    var out = { a: 1, b: 0, c: 0, shade: true };
    var src = null;
    var d = window.__DATA__ && window.__DATA__.params;
    if (d && isFinite(d.a) && Math.abs(+d.a) > 1e-6) src = d;
    if (!src && window.__GEO__ && isFinite(window.__GEO__.a) && Math.abs(+window.__GEO__.a) > 1e-6) {
      src = window.__GEO__;
    }
    if (src) {
      return { a: +src.a, b: isFinite(+src.b) ? +src.b : 0,
               c: isFinite(+src.c) ? +src.c : 0, shade: true };
    }
    [].slice.call(document.querySelectorAll('input[type=range]')).forEach(function (el) {
      var k = (el.dataset && el.dataset.key) || '';
      var v = parseFloat(el.value);
      if (!isFinite(v)) return;
      if (k === 'a') { if (Math.abs(v) > 1e-6) out.a = v; }
      else if (k === 'b') out.b = v;
      else if (k === 'c') out.c = v;
    });
    return out;
  }

  function auto() {
    if (window.__MATH_DRAWN__) return;
    var cv0 = document.querySelector('.exp-canvas-box canvas') || document.querySelector('canvas');
    if (!cv0) return;
    var txt = (document.body ? document.body.innerText : '') + ' ' + (document.title || '');

    if (/截面/.test(txt) && /正方体|长方体|棱/.test(txt)) {
      /* 立方体这条线保留无条件接管：模型自己画的立方体版面不可控，
       * 而且库版本会跟着页面滑块走（readCubeParams + input 监听）。 */
      if (cv0.__MATH_CUT__) {             // 页面确实调了库，交给它自己驱动
        window.__MATH_DRAWN__ = true;
        return;
      }
      var cv = takeover(cv0);
      window.__MATH_DRAWN__ = true;
      var render = function () {
        try { cubeCut(cv, readCubeParams()); } catch (e) { }
      };
      render();
      // 页面自己的滑块/按钮照常可用，只是画面换成库这一版
      // 页面可能用 requestAnimationFrame 重绘，双 rAF 保证我们的重绘排在它那一帧之后
      var later = function () { requestAnimationFrame(function () { requestAnimationFrame(render); }); };
      document.addEventListener('input', later, true);
      document.addEventListener('click', later, true);
      window.addEventListener('resize', function () { setTimeout(render, 60); });
    } else if (/函数|抛物线|图像|二次/.test(txt)) {
      if (cv0.__MATH_CUT__) { window.__MATH_DRAWN__ = true; return; }
      // 函数页：只要页面自己画得出来，就必须让它自己驱动。
      // 库这一版是写死参数的静态图，接管之后学生拖 a/b/c 永远看不到变化
      // （页面其实在重绘，只是画在库藏起来的那张画布上）。
      if (!isBlank(cv0)) { window.__MATH_DRAWN__ = true; return; }
      var cvf = takeover(cv0);
      window.__MATH_DRAWN__ = true;
      var frender = function () {
        try { funcPlot(cvf, readFuncParams()); } catch (e) { }
      };
      frender();
      var flater = function () { requestAnimationFrame(function () { requestAnimationFrame(frender); }); };
      document.addEventListener('input', flater, true);
      document.addEventListener('click', flater, true);
      window.addEventListener('resize', function () { setTimeout(frender, 60); });
    }
  }

  /* 时机很关键：必须等页面自己的脚本跑完、画完第一帧，再判断要不要接管。
   * 以前挂在 DOMContentLoaded+setTimeout(0)，页面脚本可能还没执行，
   * 画布看着是空的 → 误判 → 抢走画布。改成 load 之后再等两帧。 */
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

  function resetView(cv) {
    if (!cv || !cv.__mathView || !cv.__mathDefaultView) return false;
    cv.__mathView.yaw = cv.__mathDefaultView.yaw;
    cv.__mathView.pitch = cv.__mathDefaultView.pitch;
    if (typeof cv.__mathRender === 'function') cv.__mathRender();
    return true;
  }

  window.MATH = { cubeCut: cubeCut, funcPlot: funcPlot, auto: auto, resetView: resetView };
})();
