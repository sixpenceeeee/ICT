/* vis.js —— 全学科共享的「2.5D 实验室」视觉原语层（外壳注入，离线可用）
 *
 * 为什么要这一层：
 *   化学那版「双烧杯」之所以好看，不是因为画了烧杯，而是因为一套固定的光影规则——
 *   主光从左上来、接触阴影偏右下、玻璃是半透明叠层加内侧阴影、液体上浅下深、
 *   文字最后画且永远带白描边。这些规则对所有学科都成立。
 *   所以把「规则」抽成原语，各学科只组合原语，不再各画各的。
 *
 * 不变量（所有页面自动继承）：
 *   ① 空间：一切立体物用斜投影（正面 + 顶面 + 右侧面），顶面最亮、右侧最暗
 *   ② 光影：每个实体至少 3 处——渐变、高光、接触阴影
 *   ③ 材质：MAT 表里定死，不各页自创
 *   ④ 文字：统一走 VIS.text，白描边 + 包围盒自动收进画布 8px
 *
 * 对外接口（页面脚本直接用，不必自己写 canvas 细节）：
 *   VIS.mount(cv, {DW, DH})        绑定画布（设计坐标 + DPR + 等比缩放）
 *   VIS.clear()                     清屏并应用变换
 *   VIS.wall({tableY})              景深背景：墙面 / 虚化器皿 / 窗光 / 台面
 *   VIS.glass(cfg) VIS.liquid(cfg) VIS.glassFront(cfg)   玻璃容器三段式
 *   VIS.box(cfg) VIS.sphere(cfg) VIS.cyl(cfg)            立体实体
 *   VIS.spring(cfg) VIS.stand(cfg) VIS.rail(cfg) VIS.post(cfg)
 *   VIS.lens(cfg) VIS.ray(cfg) VIS.magnifier(cfg)
 *   VIS.pill(cfg) VIS.leader(cfg) VIS.card(cfg) VIS.panel(cfg)
 *   VIS.arrow(cfg) VIS.ruler(cfg) VIS.hatch(cfg) VIS.text(cfg)
 *   VIS.responsive(cv, draw)        容器变化时重绘
 */
(function () {
  'use strict';

  var S = {
    cv: null, ctx: null, DW: 900, DH: 640,
    w: 0, h: 0, s: 1, ox: 0, oy: 0, dpr: 1,
    cur: null            // 当前容器几何（glass → liquid → glassFront 之间传递）
  };

  /* ============================ 基础工具 ============================ */

  function clamp(v, a, b) { return v < a ? a : (v > b ? b : v); }
  function lerp(a, b, t) { return a + (b - a) * t; }

  function parseColor(c) {
    if (typeof c !== 'string') return [0, 0, 0];
    if (c.charAt(0) === '#') {
      var hx = c.substr(1);
      if (hx.length === 3) hx = hx[0] + hx[0] + hx[1] + hx[1] + hx[2] + hx[2];
      return [parseInt(hx.substr(0, 2), 16), parseInt(hx.substr(2, 2), 16), parseInt(hx.substr(4, 2), 16)];
    }
    var m = String(c).match(/(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)/);
    return m ? [+m[1], +m[2], +m[3]] : [0, 0, 0];
  }
  function rgba(c, a) {
    var p = parseColor(c);
    return 'rgba(' + p[0] + ',' + p[1] + ',' + p[2] + ',' + a + ')';
  }
  function mix(c1, c2, t) {
    var a = parseColor(c1), b = parseColor(c2);
    return 'rgb(' + Math.round(lerp(a[0], b[0], t)) + ',' +
      Math.round(lerp(a[1], b[1], t)) + ',' + Math.round(lerp(a[2], b[2], t)) + ')';
  }
  function shade(c, k) {
    var p = parseColor(c);
    if (k >= 0) return 'rgb(' + [0, 1, 2].map(function (i) { return Math.round(lerp(p[i], 255, k)); }).join(',') + ')';
    return 'rgb(' + [0, 1, 2].map(function (i) { return Math.round(lerp(p[i], 0, -k)); }).join(',') + ')';
  }
  function rr(x, y, w, h, r) {
    r = Math.min(r, Math.abs(w) / 2, Math.abs(h) / 2);
    var ctx = S.ctx;
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

  /* 材质表：全学科同一套，避免每页自创颜色 */
  var MAT = {
    iron:     { rgb: '#9aa6b2', name: '铁' },
    steel:    { rgb: '#b7c2cd', name: '钢' },
    aluminum: { rgb: '#c8d2dc', name: '铝' },
    copper:   { rgb: '#c1702f', name: '铜' },
    brass:    { rgb: '#c9a227', name: '黄铜' },
    wood:     { rgb: '#c99a63', name: '木' },
    plastic:  { rgb: '#5b9bd5', name: '塑料' },
    rubber:   { rgb: '#4a5560', name: '橡胶' },
    glass:    { rgb: '#d7ecfa', name: '玻璃' },
    stone:    { rgb: '#a8a29b', name: '石' },
    ice:      { rgb: '#cfe8f7', name: '冰' },
    liquid:   { rgb: '#5fb3e0', name: '液体' },
    orange:   { rgb: '#f0a03c', name: '橙色' },
    green:    { rgb: '#57a97e', name: '绿色' }
  };

  /* 确定性伪随机：纹理每次重绘一致（不能用 Math.random，否则画面会闪） */
  var SPK = [];
  (function () {
    var s = 20240;
    for (var i = 0; i < 512; i++) { s = (s * 9301 + 49297) % 233280; SPK.push(s / 233280); }
  })();
  function spk(i) { return SPK[((i % 512) + 512) % 512]; }

  /* ============================ 画布与背景 ============================ */

  function mount(cv, opt) {
    opt = opt || {};
    S.cv = cv;
    S.ctx = cv.getContext('2d');
    S.DW = opt.DW || 900;
    S.DH = opt.DH || 640;
    return resize();
  }

  function resize() {
    if (!S.cv) return false;
    var box = S.cv.parentNode || S.cv;
    var w = box.clientWidth || 720;
    var h = box.clientHeight || 480;
    if (w < 4 || h < 4) return false;
    S.w = w; S.h = h;
    S.dpr = window.devicePixelRatio || 1;
    S.cv.width = Math.max(1, Math.round(w * S.dpr));
    S.cv.height = Math.max(1, Math.round(h * S.dpr));
    S.cv.style.width = w + 'px';
    S.cv.style.height = h + 'px';
    S.s = Math.min(w / S.DW, h / S.DH);
    S.ox = (w - S.DW * S.s) / 2;
    S.oy = (h - S.DH * S.s) / 2;
    return true;
  }

  function clear() {
    var ctx = S.ctx;
    ctx.setTransform(S.dpr, 0, 0, S.dpr, 0, 0);
    ctx.clearRect(0, 0, S.w, S.h);
    ctx.translate(S.ox, S.oy);
    ctx.scale(S.s, S.s);
    // 视觉边界（供 text 自动收边使用）
    S.margin = 8;
  }

  /* 背景：墙面渐变 + 虚化器材剪影 + 窗格光带 + 台面（景深的来源） */
  function wall(cfg) {
    cfg = cfg || {};
    var ctx = S.ctx;
    var tableY = cfg.tableY == null ? S.DH * 0.52 : cfg.tableY;
    var warm = cfg.tone === 'warm';
    var topC = warm ? '#fdfaf4' : '#f9fcfe';
    var midC = warm ? '#f4ecdf' : '#eaf2f9';
    var botC = warm ? '#e8ddca' : '#dfe9f3';

    var g = ctx.createLinearGradient(0, 0, 0, S.DH);
    g.addColorStop(0, topC);
    g.addColorStop(0.55, midC);
    g.addColorStop(1, botC);
    ctx.fillStyle = g;
    // 外扩 ±420：等比缩放后不会在上下留白
    ctx.fillRect(-420, -420, S.DW + 840, S.DH + 840);

    // 左上方向光
    var rg = ctx.createRadialGradient(S.DW * 0.24, S.DH * 0.1, 20, S.DW * 0.24, S.DH * 0.1, S.DW * 0.8);
    rg.addColorStop(0, 'rgba(255,255,255,0.85)');
    rg.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = rg;
    ctx.fillRect(-420, -420, S.DW + 840, S.DH + 840);

    // 虚化器皿剪影：制造景深，别让背景是纯色
    if (cfg.props !== false) {
      ctx.save();
      ctx.filter = 'blur(3px)';
      ctx.globalAlpha = 0.4;
      var cols = ['#cbdbe9', '#d6e4f0', '#c4d6e6'];
      for (var i = 0; i < 8; i++) {
        var bx = 8 + i * (S.DW / 8);
        var bh = 40 + spk(i + 3) * 34;
        rr(bx, tableY - bh - 44, 15 + spk(i + 20) * 9, bh, 4);
        ctx.fillStyle = cols[i % 3];
        ctx.fill();
      }
      for (var k = 0; k < 3; k++) {
        rr(S.DW * 0.08 + k * S.DW * 0.33, tableY - 96, 34, 44, 5);
        ctx.fillStyle = 'rgba(224,236,246,0.8)';
        ctx.fill();
      }
      ctx.filter = 'none';
      ctx.globalAlpha = 0.5;
      ctx.fillStyle = '#d7e4f0';
      ctx.fillRect(-420, tableY - 56, S.DW + 840, 5);
      ctx.restore();
    }

    // 窗格光带
    ctx.save();
    var lg = ctx.createLinearGradient(0, 0, S.DW, 0);
    lg.addColorStop(0, 'rgba(255,255,255,0)');
    lg.addColorStop(0.4, 'rgba(255,255,255,0.5)');
    lg.addColorStop(0.64, 'rgba(255,255,255,0)');
    ctx.fillStyle = lg;
    ctx.fillRect(-420, 0, S.DW + 840, tableY);
    ctx.restore();

    // 台面
    var tg = ctx.createLinearGradient(0, tableY, 0, S.DH);
    if (warm) {
      tg.addColorStop(0, '#f0e8d9'); tg.addColorStop(0.3, '#e4d9c6'); tg.addColorStop(1, '#cfc2ad');
    } else {
      tg.addColorStop(0, '#f2f7fb'); tg.addColorStop(0.4, '#e3ecf5'); tg.addColorStop(1, '#d2dfeb');
    }
    ctx.fillStyle = tg;
    ctx.fillRect(-420, tableY, S.DW + 840, S.DH + 420);
    ctx.strokeStyle = warm ? 'rgba(176,161,140,0.8)' : 'rgba(176,198,218,0.85)';
    ctx.lineWidth = 1.4;
    ctx.beginPath();
    ctx.moveTo(-420, tableY + 0.5);
    ctx.lineTo(S.DW + 420, tableY + 0.5);
    ctx.stroke();
    // 台面反光
    var rg2 = ctx.createLinearGradient(0, tableY + 2, 0, tableY + 110);
    rg2.addColorStop(0, 'rgba(255,255,255,0.7)');
    rg2.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = rg2;
    ctx.fillRect(-420, tableY + 2, S.DW + 840, 108);

    return tableY;
  }

  /* 接触阴影：主光左上 → 影子偏右下，这是全库统一的光照约定 */
  function shadow(x, y, rx, ry, a) {
    var ctx = S.ctx;
    var g = ctx.createRadialGradient(x + 6, y + 2, 2, x + 6, y + 2, Math.max(rx, ry) * 1.5);
    g.addColorStop(0, 'rgba(26,54,84,' + (a == null ? 0.24 : a) + ')');
    g.addColorStop(0.6, 'rgba(26,54,84,' + (a == null ? 0.24 : a) * 0.4 + ')');
    g.addColorStop(1, 'rgba(26,54,84,0)');
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.ellipse(x + 6, y + 2, rx, ry, 0, 0, Math.PI * 2);
    ctx.fill();
  }

  /* ============================ 玻璃容器 ============================ */
  /* 三段式：glass（背）→ liquid（液体）→ glassFront（前壁/刻度）
   * cfg: { x, base, hw, h, r, kind:'beaker'|'cylinder'|'tube', tick, mouth, pour }
   */

  function glassBodyPath(cfg) {
    var ctx = S.ctx;
    var hw = cfg.hw, h = cfg.h, r = cfg.r == null ? 14 : cfg.r;
    var kind = cfg.kind || 'beaker';
    ctx.beginPath();
    if (kind === 'tube') {
      ctx.moveTo(-hw, 0);
      ctx.lineTo(-hw, -h + hw);
      ctx.arc(0, -h + hw, hw, Math.PI, 0, false);
      ctx.lineTo(hw, 0);
      ctx.closePath();
    } else if (kind === 'cylinder') {
      ctx.moveTo(-hw, 0);
      ctx.lineTo(-hw, -h + r);
      ctx.quadraticCurveTo(-hw, -h, -hw + r, -h);
      ctx.lineTo(hw - r, -h);
      ctx.quadraticCurveTo(hw, -h, hw, -h + r);
      ctx.lineTo(hw, 0);
      ctx.closePath();
    } else {
      ctx.moveTo(-hw, -h);
      ctx.lineTo(-hw, -r);
      ctx.quadraticCurveTo(-hw, 0, -hw + r, 0);
      ctx.lineTo(hw - r, 0);
      ctx.quadraticCurveTo(hw, 0, hw, -r);
      ctx.lineTo(hw, -h);
      ctx.closePath();
    }
  }

  function glass(cfg) {
    var ctx = S.ctx;
    var base = cfg.base, x = cfg.x, hw = cfg.hw, h = cfg.h;
    var ry = cfg.ry == null ? Math.max(4, hw * 0.19) : cfg.ry;
    var kind = cfg.kind || 'beaker';

    ctx.save();
    ctx.translate(x, base);

    // 台面投影 + 杯体倒影
    shadow(0, 8, hw * 1.32, 14, 0.22);
    var rf = ctx.createLinearGradient(0, 2, 0, 58);
    rf.addColorStop(0, 'rgba(255,255,255,0.5)');
    rf.addColorStop(0.45, 'rgba(198,226,244,0.26)');
    rf.addColorStop(1, 'rgba(198,226,244,0)');
    ctx.fillStyle = rf;
    ctx.beginPath();
    ctx.moveTo(-hw + 5, 3);
    ctx.lineTo(hw - 5, 3);
    ctx.lineTo(hw - 16, 54);
    ctx.lineTo(-hw + 16, 54);
    ctx.closePath();
    ctx.fill();

    // 玻璃杯体
    var gg = ctx.createLinearGradient(-hw, 0, hw, 0);
    gg.addColorStop(0, 'rgba(224,239,249,0.62)');
    gg.addColorStop(0.16, 'rgba(255,255,255,0.34)');
    gg.addColorStop(0.62, 'rgba(238,247,253,0.20)');
    gg.addColorStop(1, 'rgba(203,224,241,0.58)');
    glassBodyPath({ hw: hw, h: h, r: cfg.r, kind: kind });
    ctx.fillStyle = gg;
    ctx.fill();
    ctx.strokeStyle = 'rgba(146,180,208,0.95)';
    ctx.lineWidth = 1.8;
    ctx.stroke();

    // 倾倒口（只给烧杯）
    if (cfg.pour) {
      ctx.beginPath();
      ctx.moveTo(-hw + 9, -h - 2);
      ctx.quadraticCurveTo(-hw - 6, -h - 1, -hw - 11, -h + 9);
      ctx.quadraticCurveTo(-hw - 6, -h + 6, -hw + 3, -h + 7);
      ctx.quadraticCurveTo(-hw + 7, -h + 4, -hw + 9, -h - 2);
      ctx.closePath();
      ctx.fillStyle = 'rgba(240,249,254,0.92)';
      ctx.fill();
      ctx.strokeStyle = 'rgba(150,182,206,0.8)';
      ctx.lineWidth = 1.3;
      ctx.stroke();
    }

    // 杯口后缘（前缘在 glassFront 画）
    if (kind !== 'tube') {
      ctx.beginPath();
      ctx.ellipse(0, -h, hw, ry, 0, Math.PI, Math.PI * 2);
      ctx.strokeStyle = 'rgba(146,182,210,0.9)';
      ctx.lineWidth = 2.2;
      ctx.stroke();
    }
    ctx.restore();

    S.cur = {
      x: x, base: base, hw: hw, h: h, ry: ry, kind: kind,
      top: base - h, cfg: cfg,
      clipPath: function () {
        S.ctx.save();
        S.ctx.translate(base === base ? 0 : 0, 0);
      }
    };
    return S.cur;
  }

  /* 液体：clip 到容器内壁，上浅下深，加波纹 / 弯月面 / 悬浮颗粒 / 气泡 */
  function liquid(cfg) {
    var ctx = S.ctx;
    var g0 = S.cur;
    if (!g0) return null;
    var lv = cfg.level == null ? 0.6 : clamp(cfg.level, 0, 1);
    var top = typeof cfg.top === 'string' ? cfg.top : '#7fd8f7';
    var bot = typeof cfg.bot === 'string' ? cfg.bot : '#0b6aa8';
    var hw = g0.hw, h = g0.h, base = g0.base, x = g0.x;
    var ySurf = base - Math.max(6, h * lv);

    ctx.save();
    ctx.translate(x, base);
    glassBodyPath({ hw: hw - 1.5, h: h - 1.5, r: g0.cfg.r, kind: g0.kind });
    ctx.clip();

    var lg = ctx.createLinearGradient(0, -h * lv, 0, 0);
    lg.addColorStop(0, rgba(top, 0.94));
    lg.addColorStop(0.6, rgba(mix(top, bot, 0.55), 0.95));
    lg.addColorStop(1, rgba(bot, 0.97));
    ctx.fillStyle = lg;
    ctx.fillRect(-hw, -(h * lv), hw * 2, h * lv);

    // 后壁折射亮带
    ctx.fillStyle = 'rgba(255,255,255,0.16)';
    ctx.fillRect(-hw + 7, -(h * lv), 10, h * lv);

    // 悬浮颗粒
    for (var i = 0; i < 24; i++) {
      var px = (spk(i + 11) - 0.5) * hw * 1.7;
      var py = -6 - spk(i + 61) * (h * lv - 10);
      ctx.beginPath();
      ctx.arc(px, py, 0.5 + spk(i + 111) * 1.1, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(255,255,255,' + (0.08 + spk(i + 151) * 0.16) + ')';
      ctx.fill();
    }
    // 杯底折射加深
    var lb = ctx.createLinearGradient(0, 0, 0, -18);
    lb.addColorStop(0, 'rgba(20,70,110,0.22)');
    lb.addColorStop(1, 'rgba(20,70,110,0)');
    ctx.fillStyle = lb;
    ctx.fillRect(-hw, -18, hw * 2, 18);

    // 气泡（由状态驱动相位，非随机）
    var bub = cfg.bubbles || 0;
    for (var b = 0; b < bub; b++) {
      var ph = ((cfg.t || 0) * 0.32 + b * 0.31) % 1;
      var bx = (spk(b + 5) - 0.5) * hw * 1.3;
      var by = -6 - ph * (h * lv - 12);
      ctx.beginPath();
      ctx.arc(bx + Math.sin((cfg.t || 0) * 1.4 + b) * 2.5, by, 1 + (b % 3) * 0.7, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(255,255,255,' + (0.34 * (1 - ph)) + ')';
      ctx.fill();
    }
    ctx.restore();

    // 液面椭圆
    ctx.save();
    ctx.translate(x, ySurf);
    ctx.beginPath();
    ctx.ellipse(0, 0, hw - 1, g0.ry, 0, 0, Math.PI * 2);
    var sg = ctx.createLinearGradient(-hw, -g0.ry, hw, g0.ry);
    sg.addColorStop(0, 'rgba(255,255,255,0.96)');
    sg.addColorStop(0.55, rgba(mix(top, '#ffffff', 0.45), 0.95));
    sg.addColorStop(1, rgba(top, 0.96));
    ctx.fillStyle = sg;
    ctx.fill();
    ctx.strokeStyle = 'rgba(116,170,206,0.9)';
    ctx.lineWidth = 1.2;
    ctx.stroke();

    // 弯月面
    ctx.beginPath();
    ctx.ellipse(0, 1.4, hw - 4, Math.max(2, g0.ry * 0.78), 0, 0, Math.PI * 2);
    ctx.strokeStyle = 'rgba(255,255,255,0.85)';
    ctx.lineWidth = 1.5;
    ctx.stroke();

    // 波纹
    if (cfg.ripple !== false) {
      var t = cfg.t || 0;
      for (var w = 0; w < 3; w++) {
        ctx.beginPath();
        for (var sx = -hw + 8; sx <= hw - 8; sx += 4) {
          var yy = 3 + w * 3.2 + Math.sin(sx * 0.16 + t * 1.7 + w) * (0.5 + w * 0.25);
          if (sx === -hw + 8) ctx.moveTo(sx, yy); else ctx.lineTo(sx, yy);
        }
        ctx.strokeStyle = 'rgba(255,255,255,' + (0.32 - w * 0.08) + ')';
        ctx.lineWidth = 1;
        ctx.stroke();
      }
    }
    ctx.restore();

    return { y: ySurf, hw: hw, ry: g0.ry };
  }

  /* 玻璃前壁：内侧阴影 + 杯口前缘 + 厚底亮弧 + 刻度 */
  function glassFront(cfg) {
    var ctx = S.ctx;
    var g0 = S.cur;
    if (!g0) return;
    cfg = cfg || {};
    var hw = g0.hw, h = g0.h, base = g0.base, x = g0.x, ry = g0.ry;

    ctx.save();
    ctx.translate(x, base);

    // 内侧阴影（玻璃厚度）
    var shl = ctx.createLinearGradient(-hw, 0, -hw + 15, 0);
    shl.addColorStop(0, 'rgba(108,150,182,0.28)');
    shl.addColorStop(1, 'rgba(108,150,182,0)');
    ctx.fillStyle = shl;
    ctx.fillRect(-hw, -h, 15, h);
    var shr = ctx.createLinearGradient(hw, 0, hw - 15, 0);
    shr.addColorStop(0, 'rgba(108,150,182,0.24)');
    shr.addColorStop(1, 'rgba(108,150,182,0)');
    ctx.fillStyle = shr;
    ctx.fillRect(hw - 15, -h, 15, h);

    // 左侧垂直高光带
    var hg = ctx.createLinearGradient(-hw + 12, 0, -hw + 30, 0);
    hg.addColorStop(0, 'rgba(255,255,255,0)');
    hg.addColorStop(0.5, 'rgba(255,255,255,0.55)');
    hg.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = hg;
    ctx.fillRect(-hw + 12, -h + 16, 20, h - 40);
    var hg2 = ctx.createLinearGradient(hw - 26, 0, hw - 14, 0);
    hg2.addColorStop(0, 'rgba(255,255,255,0)');
    hg2.addColorStop(0.5, 'rgba(255,255,255,0.3)');
    hg2.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = hg2;
    ctx.fillRect(hw - 26, -h + 30, 12, h - 60);

    // 杯口前缘
    if (g0.kind !== 'tube') {
      ctx.beginPath();
      ctx.ellipse(0, -h, hw, ry, 0, 0, Math.PI);
      ctx.strokeStyle = 'rgba(255,255,255,0.95)';
      ctx.lineWidth = 2.2;
      ctx.stroke();
      ctx.beginPath();
      ctx.ellipse(0, -h, hw, ry, 0, 0, Math.PI);
      ctx.strokeStyle = 'rgba(146,182,210,0.55)';
      ctx.lineWidth = 1;
      ctx.stroke();
    }

    // 厚底亮弧
    if (g0.kind !== 'tube') {
      ctx.beginPath();
      ctx.moveTo(-hw + 6, -5);
      ctx.quadraticCurveTo(0, Math.max(2, ry * 0.5), hw - 6, -5);
      ctx.strokeStyle = 'rgba(255,255,255,0.75)';
      ctx.lineWidth = 2.4;
      ctx.stroke();
    }

    // 刻度（竖直，从底往上，0 在底）
    var tk = cfg.tick;
    if (tk) {
      var max = tk.max || 100, step = tk.step || 20;
      var unit = tk.unit === undefined ? 'mL' : tk.unit;
      var inside = tk.side !== 'outside';
      ctx.font = '600 ' + fs(12) + 'px "Microsoft YaHei", system-ui, sans-serif';
      ctx.textBaseline = 'middle';
      for (var v = 0; v <= max; v += step) {
        if (v === 0) continue;
        var y = -Math.max(6, h * (v / max) * (tk.fill == null ? 0.92 : tk.fill));
        var major = (v % (step * 2) === 0);
        ctx.beginPath();
        ctx.moveTo(-hw + 2, y);
        ctx.lineTo(-hw + (major ? 20 : 13), y);
        ctx.strokeStyle = major ? 'rgba(86,124,150,0.85)' : 'rgba(86,124,150,0.45)';
        ctx.lineWidth = major ? 1.2 : 0.9;
        ctx.stroke();
        if (major) {
          ctx.fillStyle = 'rgba(58,94,120,0.9)';
          ctx.textAlign = 'left';
          if (inside) ctx.fillText(String(v), -hw + 23, y);
          else ctx.fillText(String(v), -hw - 26, y);
        }
      }
      if (unit) {
        ctx.fillStyle = 'rgba(58,94,120,0.8)';
        ctx.textAlign = 'left';
        ctx.font = '600 ' + fs(12) + 'px "Microsoft YaHei", system-ui, sans-serif';
        ctx.fillText(unit, -hw + 23, -Math.max(6, h * (tk.fill == null ? 0.92 : tk.fill)) - 12);
      }
    }
    ctx.restore();
  }

  /* ============================ 立体实体 ============================ */
  /* 斜投影立方体：正面 + 顶面 + 右侧面，顶面提亮 0.34、右侧压暗 0.28 */
  function box(cfg) {
    var ctx = S.ctx;
    var x = cfg.x, yTop = cfg.y, w = cfg.w, h = cfg.h;
    var ox = cfg.ox == null ? w * 0.26 : cfg.ox;
    var oy = cfg.oy == null ? w * 0.2 : cfg.oy;
    var col = cfg.color || MAT.wood.rgb;
    var tint = cfg.tint || 0;
    var tintC = cfg.tintColor || '#3fa4d6';
    var x0 = x - w / 2, x1 = x + w / 2, y1 = yTop + h;

    function paint(pathFn, base, light) {
      pathFn();
      var c = light ? shade(base, light) : base;
      if (tint) c = mix(c, tintC, tint);
      ctx.fillStyle = c;
      ctx.fill();
      ctx.strokeStyle = 'rgba(38,58,78,' + (tint ? 0.3 : 0.42) + ')';
      ctx.lineWidth = 1.1;
      ctx.stroke();
    }

    // 右侧面
    paint(function () {
      ctx.beginPath();
      ctx.moveTo(x1, yTop); ctx.lineTo(x1 + ox, yTop - oy);
      ctx.lineTo(x1 + ox, y1 - oy); ctx.lineTo(x1, y1); ctx.closePath();
    }, col, -0.28);
    // 顶面
    paint(function () {
      ctx.beginPath();
      ctx.moveTo(x0, yTop); ctx.lineTo(x1, yTop);
      ctx.lineTo(x1 + ox, yTop - oy); ctx.lineTo(x0 + ox, yTop - oy); ctx.closePath();
    }, col, 0.34);
    // 正面
    var g = ctx.createLinearGradient(x0, yTop, x1, y1);
    var c1 = shade(col, 0.15), c2 = shade(col, -0.13);
    if (tint) { c1 = mix(c1, tintC, tint); c2 = mix(c2, tintC, tint); }
    g.addColorStop(0, c1);
    g.addColorStop(1, c2);
    ctx.fillStyle = g;
    rr(x0, yTop, w, h, cfg.r == null ? 1.5 : cfg.r);
    ctx.fill();
    ctx.strokeStyle = 'rgba(38,58,78,' + (tint ? 0.32 : 0.45) + ')';
    ctx.lineWidth = 1.1;
    ctx.stroke();
    // 正面高光
    var hgd = ctx.createLinearGradient(x0, yTop, x0, yTop + h * 0.62);
    hgd.addColorStop(0, 'rgba(255,255,255,0.26)');
    hgd.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = hgd;
    ctx.fillRect(x0 + 1, yTop + 1, w - 2, h * 0.6);

    return { top: yTop - oy, bottom: y1, cx: x + ox / 2 };
  }

  /* 球体：径向渐变 + 环境反光 + 高光点 */
  function sphere(cfg) {
    var ctx = S.ctx;
    var x = cfg.x, y = cfg.y, r = cfg.r;
    var col = cfg.color || MAT.plastic.rgb;
    shadow(x, y + r * 0.94, r * 1.1, r * 0.24, 0.2);
    var g = ctx.createRadialGradient(x - r * 0.36, y - r * 0.4, r * 0.1, x, y, r * 1.05);
    g.addColorStop(0, shade(col, 0.7));
    g.addColorStop(0.42, shade(col, 0.14));
    g.addColorStop(1, shade(col, -0.36));
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fillStyle = g;
    ctx.fill();
    ctx.strokeStyle = 'rgba(38,58,78,0.28)';
    ctx.lineWidth = 1;
    ctx.stroke();
    // 高光
    ctx.beginPath();
    ctx.ellipse(x - r * 0.34, y - r * 0.4, r * 0.26, r * 0.18, -0.5, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(255,255,255,0.72)';
    ctx.fill();
    // 底部环境反光
    ctx.beginPath();
    ctx.ellipse(x + r * 0.16, y + r * 0.52, r * 0.5, r * 0.2, 0.1, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(255,255,255,0.18)';
    ctx.fill();
    return { top: y - r, bottom: y + r };
  }

  /* 圆柱：上椭圆 + 侧面渐变 + 下弧 */
  function cyl(cfg) {
    var ctx = S.ctx;
    var x = cfg.x, base = cfg.base, rw = cfg.rw, h = cfg.h;
    var ry = cfg.ry == null ? rw * 0.22 : cfg.ry;
    var col = cfg.color || MAT.steel.rgb;
    shadow(x, base + 3, rw * 1.1, ry * 0.9, 0.2);
    var g = ctx.createLinearGradient(x - rw, 0, x + rw, 0);
    g.addColorStop(0, shade(col, -0.3));
    g.addColorStop(0.22, shade(col, 0.3));
    g.addColorStop(0.55, shade(col, 0.04));
    g.addColorStop(1, shade(col, -0.34));
    ctx.beginPath();
    ctx.moveTo(x - rw, base - h);
    ctx.lineTo(x - rw, base);
    ctx.ellipse(x, base, rw, ry, 0, Math.PI, 0, true);
    ctx.lineTo(x + rw, base - h);
    ctx.closePath();
    ctx.fillStyle = g;
    ctx.fill();
    ctx.strokeStyle = 'rgba(60,74,88,0.35)';
    ctx.lineWidth = 1;
    ctx.stroke();
    // 顶面
    ctx.beginPath();
    ctx.ellipse(x, base - h, rw, ry, 0, 0, Math.PI * 2);
    ctx.fillStyle = shade(col, 0.42);
    ctx.fill();
    ctx.strokeStyle = 'rgba(60,74,88,0.3)';
    ctx.stroke();
    return { top: base - h - ry, bottom: base };
  }

  /* 弹簧：分段螺旋，可伸长 */
  function spring(cfg) {
    var ctx = S.ctx;
    var x = cfg.x, y1 = cfg.y1, y2 = cfg.y2;
    var r = cfg.r == null ? 9 : cfg.r;
    var coils = cfg.coils || 14;
    ctx.beginPath();
    var n = coils * 12;
    for (var i = 0; i <= n; i++) {
      var t = i / n;
      var y = lerp(y1, y2, t);
      var px = x + Math.sin(t * Math.PI * 2 * coils) * r;
      if (i === 0) ctx.moveTo(px, y); else ctx.lineTo(px, y);
    }
    ctx.strokeStyle = 'rgba(120,134,148,0.95)';
    ctx.lineWidth = 2.2;
    ctx.stroke();
    ctx.strokeStyle = 'rgba(255,255,255,0.55)';
    ctx.lineWidth = 0.8;
    ctx.stroke();
  }

  /* 铁架台：底座 + 立柱 + 横杆 */
  function stand(cfg) {
    var ctx = S.ctx;
    var x = cfg.x, baseY = cfg.baseY, topY = cfg.topY;
    // 底座
    var bg = ctx.createLinearGradient(0, baseY - 10, 0, baseY + 8);
    bg.addColorStop(0, '#a8b3be'); bg.addColorStop(0.45, '#7f8b98'); bg.addColorStop(1, '#5f6a76');
    ctx.fillStyle = bg;
    rr(x - 62, baseY - 8, 124, 17, 5);
    ctx.fill();
    ctx.strokeStyle = 'rgba(60,72,84,0.5)';
    ctx.lineWidth = 1;
    ctx.stroke();
    ctx.fillStyle = 'rgba(255,255,255,0.32)';
    rr(x - 56, baseY - 5, 108, 3, 1.5);
    ctx.fill();
    // 立柱
    var rg = ctx.createLinearGradient(x - 5, 0, x + 5, 0);
    rg.addColorStop(0, '#9aa6b2'); rg.addColorStop(0.35, '#e3e9ef');
    rg.addColorStop(0.7, '#b3bec9'); rg.addColorStop(1, '#78848f');
    ctx.fillStyle = rg;
    rr(x - 5, topY, 10, baseY - topY - 6, 4);
    ctx.fill();
    ctx.strokeStyle = 'rgba(80,95,110,0.32)';
    ctx.lineWidth = 1;
    ctx.stroke();
    return { x: x, topY: topY };
  }

  /* 光具座导轨（铝合金 + cm 刻度 + 黑色支脚） */
  function rail(cfg) {
    var ctx = S.ctx;
    var x0 = cfg.x0, x1 = cfg.x1, y = cfg.y, h = cfg.h || 18;
    var px = cfg.px;              // 每 cm 像素
    // 支脚
    ctx.fillStyle = '#2b323a';
    [x0 + 30, x1 - 30].forEach(function (fx) {
      ctx.beginPath();
      ctx.moveTo(fx - 24, y + h);
      ctx.lineTo(fx + 24, y + h);
      ctx.lineTo(fx + 16, y + h + 15);
      ctx.lineTo(fx - 16, y + h + 15);
      ctx.closePath();
      ctx.fill();
    });
    // 导轨主体
    var g = ctx.createLinearGradient(0, y, 0, y + h);
    g.addColorStop(0, '#eef2f7'); g.addColorStop(0.35, '#cbd5df');
    g.addColorStop(0.7, '#dee5ec'); g.addColorStop(1, '#b7c2cd');
    ctx.fillStyle = g;
    rr(x0, y, x1 - x0, h, 4);
    ctx.fill();
    ctx.strokeStyle = '#8b99a7';
    ctx.lineWidth = 1.2;
    ctx.stroke();
    ctx.strokeStyle = 'rgba(90,104,118,0.45)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x0 + 6, y + 4.5); ctx.lineTo(x1 - 6, y + 4.5);
    ctx.stroke();
    // 刻度
    var cmMax = Math.round((x1 - x0 - 16) / px);
    ctx.font = '600 ' + fs(12) + 'px "Microsoft YaHei", system-ui, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'alphabetic';
    for (var cm = 0; cm <= cmMax; cm++) {
      var cx = x0 + 8 + cm * px;
      var major = cm % 10 === 0;
      ctx.beginPath();
      ctx.moveTo(cx, y + (major ? 7 : 10));
      ctx.lineTo(cx, y + h - 3);
      ctx.strokeStyle = major ? '#57656f' : 'rgba(87,101,111,0.35)';
      ctx.lineWidth = major ? 1.1 : 0.8;
      ctx.stroke();
      if (major) {
        ctx.fillStyle = '#42505c';
        ctx.fillText(String(cm), cx, y + h + 15);
        ctx.strokeStyle = 'rgba(87,101,111,0.28)';
        ctx.beginPath();
        ctx.moveTo(cx, y + h + 19); ctx.lineTo(cx, y + h + 26);
        ctx.stroke();
      }
    }
    return { cmToX: function (cm) { return x0 + 8 + cm * px; }, y: y };
  }

  /* 黑色立柱支架（光学器材通用底座） */
  function post(cfg) {
    var ctx = S.ctx;
    var x = cfg.x, yTop = cfg.y, yBase = cfg.base;
    var g = ctx.createLinearGradient(x - 3.5, 0, x + 3.5, 0);
    g.addColorStop(0, '#1f262e'); g.addColorStop(0.4, '#4a545e'); g.addColorStop(1, '#171c22');
    ctx.fillStyle = g;
    rr(x - 3.5, yTop, 7, yBase - yTop, 2.5);
    ctx.fill();
    // 滑块底座
    var bg = ctx.createLinearGradient(0, yBase - 8, 0, yBase + 6);
    bg.addColorStop(0, '#5a646e'); bg.addColorStop(1, '#232a31');
    ctx.fillStyle = bg;
    rr(x - 15, yBase - 8, 30, 13, 3);
    ctx.fill();
    ctx.fillStyle = 'rgba(255,255,255,0.2)';
    rr(x - 12, yBase - 6, 24, 2.4, 1.2);
    ctx.fill();
  }

  /* ============================ 光学 ============================ */

  /* 双凸 / 平凸透镜：玻璃质感 + 高光弧 */
  function lens(cfg) {
    var ctx = S.ctx;
    var x = cfg.x, y = cfg.y, h = cfg.h, bulge = cfg.bulge == null ? 16 : cfg.bulge;
    ctx.save();
    // 玻璃体
    ctx.beginPath();
    ctx.moveTo(x, y - h / 2);
    ctx.quadraticCurveTo(x + bulge, y, x, y + h / 2);
    ctx.quadraticCurveTo(x - bulge, y, x, y - h / 2);
    ctx.closePath();
    var g = ctx.createLinearGradient(x - bulge, 0, x + bulge, 0);
    g.addColorStop(0, 'rgba(208,232,250,0.9)');
    g.addColorStop(0.4, 'rgba(246,253,255,0.95)');
    g.addColorStop(1, 'rgba(196,224,246,0.88)');
    ctx.fillStyle = g;
    ctx.fill();
    ctx.strokeStyle = 'rgba(118,164,198,0.9)';
    ctx.lineWidth = 1.5;
    ctx.stroke();
    // 左缘高光弧
    ctx.beginPath();
    ctx.moveTo(x - 1, y - h / 2 + 6);
    ctx.quadraticCurveTo(x - bulge * 0.72, y, x - 1, y + h / 2 - 6);
    ctx.strokeStyle = 'rgba(255,255,255,0.95)';
    ctx.lineWidth = 2.4;
    ctx.stroke();
    // 中轴细线
    ctx.beginPath();
    ctx.moveTo(x, y - h / 2);
    ctx.lineTo(x, y + h / 2);
    ctx.strokeStyle = 'rgba(160,196,220,0.5)';
    ctx.lineWidth = 1;
    ctx.stroke();
    ctx.restore();
    return { x: x, y: y, h: h };
  }

  /* 光线：折线 + 中点箭头，橙色系 */
  function ray(cfg) {
    var ctx = S.ctx;
    var pts = cfg.pts || [];
    if (pts.length < 2) return;
    ctx.save();
    ctx.beginPath();
    ctx.moveTo(pts[0][0], pts[0][1]);
    for (var i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]);
    if (cfg.glow !== false) {
      ctx.shadowColor = 'rgba(255,150,40,0.4)';
      ctx.shadowBlur = 6;
    }
    ctx.strokeStyle = cfg.color || '#f08a1e';
    ctx.lineWidth = cfg.width || 1.9;
    ctx.setLineDash(cfg.dash || []);
    ctx.stroke();
    ctx.restore();
    // 箭头
    if (cfg.arrow !== false) {
      for (var k = 1; k < pts.length; k++) {
        var ax = pts[k - 1][0], ay = pts[k - 1][1], bx = pts[k][0], by = pts[k][1];
        var ang = Math.atan2(by - ay, bx - ax);
        var mx = lerp(ax, bx, 0.52), my = lerp(ay, by, 0.52);
        ctx.save();
        ctx.translate(mx, my);
        ctx.rotate(ang);
        ctx.beginPath();
        ctx.moveTo(5, 0); ctx.lineTo(-3.5, 3.2); ctx.lineTo(-3.5, -3.2);
        ctx.closePath();
        ctx.fillStyle = cfg.color || '#f08a1e';
        ctx.fill();
        ctx.restore();
      }
    }
  }

  /* 圆形放大镜：白环 + 深底 + 内部纹理回调 */
  function magnifier(cfg) {
    var ctx = S.ctx;
    var x = cfg.x, y = cfg.y, r = cfg.r;
    ctx.save();
    // 外环
    var ring = ctx.createLinearGradient(x - r, y - r, x + r, y + r);
    ring.addColorStop(0, '#ffffff');
    ring.addColorStop(0.5, '#dbe7f1');
    ring.addColorStop(1, '#a9bacb');
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fillStyle = ring;
    ctx.fill();
    // 视野
    ctx.save();
    ctx.beginPath();
    ctx.arc(x, y, r - 6, 0, Math.PI * 2);
    ctx.clip();
    var inner = ctx.createRadialGradient(x - r * 0.3, y - r * 0.3, 2, x, y, r);
    inner.addColorStop(0, cfg.bgLight || '#f5fafd');
    inner.addColorStop(1, cfg.bgDark || '#d8e6f1');
    ctx.fillStyle = inner;
    ctx.fillRect(x - r, y - r, r * 2, r * 2);
    if (typeof cfg.draw === 'function') cfg.draw(ctx, x, y, r - 6);
    ctx.restore();
    // 玻璃反光
    ctx.beginPath();
    ctx.ellipse(x - r * 0.34, y - r * 0.42, r * 0.34, r * 0.16, -0.6, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(255,255,255,0.55)';
    ctx.fill();
    ctx.restore();
  }

  /* 画布最小字号：画布是位图，9~10px 的中文缩到屏幕上根本认不出。
     所有走 text/pill/card 的文字都会被抬到这个下限，刻度数字也一并抬。 */
  var FS_MIN = 25;      // 画布内最小字号 = 原始 12.5px × 2
  var TYPE_SCALE = 2;   // 画布内所有字号统一放大倍数
  function fs(v) { v = (+v || 0) * TYPE_SCALE; return v < FS_MIN ? FS_MIN : v; }

  /* ============================ 标注系统 ============================ */
  /* 所有文字统一走这里：白描边 + 自动收进画布 8px，保证不被图元压住、不出界 */

  /* 演示区只留实物与图形：长句说明、带句读的提示一律不画。
     允许的是器材名、顶点名、刻度、公式符号这类 ≤14 字的短标注。 */
  var LABEL_MAX = 14;
  var SENTENCE = /[，。；：、？！]/;
  function isLabel(t) {
    t = t == null ? '' : String(t);
    if (!t) return false;
    if (t.length > LABEL_MAX) return false;
    if (SENTENCE.test(t)) return false;
    return true;
  }

  function text(cfg) {
    if (!isLabel(cfg.text)) return { left: cfg.x || 0, right: cfg.x || 0, w: 0 };
    var ctx = S.ctx;
    var size = fs(cfg.size || 13);
    var weight = cfg.weight || 500;
    var align = cfg.align || 'center';
    var baseline = cfg.baseline || 'middle';
    var col = cfg.color || '#1f3a52';
    ctx.save();
    ctx.font = weight + ' ' + size + 'px "Microsoft YaHei", system-ui, sans-serif';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'alphabetic';

    var tx = cfg.x, ty = cfg.y;
    var w = ctx.measureText(cfg.text).width;
    var half = align === 'center' ? w / 2 : (align === 'right' ? w : 0);
    var left = tx - half;
    var right = left + w;
    // 自动收边
    var m = S.margin == null ? 8 : S.margin;
    if (left < m) { tx += m - left; left = m; right = left + w; }
    if (right > S.DW - m) { tx -= right - (S.DW - m); left = S.DW - m - w; right = S.DW - m; }

    // 底衬（可选）
    if (cfg.pad) {
      var padX = cfg.padX == null ? 6 : cfg.padX;
      var padY = cfg.padY == null ? 4 : cfg.padY;
      rr(left - padX, ty - size * 0.72 - padY, w + padX * 2, size * 1.44 + padY * 2, 6);
      ctx.fillStyle = cfg.pad === true ? 'rgba(255,255,255,0.82)' : cfg.pad;
      ctx.fill();
    }
    // 描边：浅色场景用白描边，深色场景（星空/夜景）必须换成深色描边，
    // 否则白边会把字糊成一个白块
    if (cfg.stroke !== false) {
      ctx.lineWidth = cfg.strokeWidth || Math.max(2.6, size * 0.24);
      ctx.strokeStyle = cfg.strokeColor
        || (cfg.onDark ? 'rgba(6,22,38,0.88)' : 'rgba(255,255,255,0.92)');
      ctx.lineJoin = 'round';
      ctx.strokeText(cfg.text, tx, ty + size * 0.35);
    }
    ctx.fillStyle = col;
    ctx.fillText(cfg.text, tx, ty + size * 0.35);
    ctx.restore();
    return { left: left, right: right, w: w };
  }

  /* 胶囊标签（统一版式：实底圆角 + 白字 + 1.2px 描边） */
  function pill(cfg) {
    var ctx = S.ctx;
    var text0 = cfg.text || '';
    var size = fs(cfg.size || 14);
    var bg = cfg.bg || '#1b62b0';
    var padX = size * 0.72, padY = size * 0.42;
    ctx.save();
    ctx.font = '700 ' + size + 'px "Microsoft YaHei", system-ui, sans-serif';
    var tw = ctx.measureText(text0).width;
    var h = size + padY * 2;
    var w = tw + padX * 2;
    var x = cfg.x - w / 2, y = cfg.y - h / 2;
    // 收边
    var m = S.margin == null ? 8 : S.margin;
    if (x < m) x = m;
    if (x + w > S.DW - m) x = S.DW - m - w;
    // 投影
    ctx.shadowColor = 'rgba(20,44,70,0.18)';
    ctx.shadowBlur = 5;
    ctx.shadowOffsetY = 1.5;
    rr(x, y, w, h, h / 2);
    ctx.fillStyle = bg;
    ctx.fill();
    ctx.shadowColor = 'transparent';
    ctx.shadowBlur = 0;
    ctx.shadowOffsetY = 0;
    ctx.strokeStyle = 'rgba(255,255,255,0.5)';
    ctx.lineWidth = 1;
    ctx.stroke();
    ctx.fillStyle = '#ffffff';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(text0, x + w / 2, y + h / 2 + 0.5);
    ctx.restore();
    return { x: x, y: y, w: w, h: h, cx: x + w / 2, cy: y + h / 2 };
  }

  /* 引线：端点圆点 + 细线（虚线可选） */
  function leader(cfg) {
    var ctx = S.ctx;
    ctx.save();
    ctx.beginPath();
    ctx.moveTo(cfg.x1, cfg.y1);
    ctx.lineTo(cfg.x2, cfg.y2);
    ctx.strokeStyle = cfg.color || 'rgba(70,100,130,0.55)';
    ctx.lineWidth = cfg.width || 1.2;
    if (cfg.dash) ctx.setLineDash([4, 3]);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.beginPath();
    ctx.arc(cfg.x2, cfg.y2, 2.6, 0, Math.PI * 2);
    ctx.fillStyle = cfg.dotColor || cfg.color || 'rgba(70,100,130,0.75)';
    ctx.fill();
    ctx.restore();
  }

  /* 圆形端点（F、2F 之类的标记点） */
  function dot(cfg) {
    var ctx = S.ctx;
    ctx.beginPath();
    ctx.arc(cfg.x, cfg.y, cfg.r || 3.6, 0, Math.PI * 2);
    ctx.fillStyle = cfg.color || '#2e6fd8';
    ctx.fill();
    if (cfg.ring) {
      ctx.strokeStyle = 'rgba(255,255,255,0.9)';
      ctx.lineWidth = 1.4;
      ctx.stroke();
    }
  }

  /* 读数卡：平台规范要求「演示区只留实物与图形」。
     这些读数 ④ 区已经完整给出，画布上再画一张信息卡属于重复铺陈 → 不再绘制。
     函数和返回值保留，老页面的调用不会报错。 */
  function card(cfg) {
    cfg = cfg || {};
    return { x: cfg.x == null ? 16 : cfg.x, y: cfg.y == null ? 14 : cfg.y, w: 0, h: 0 };
  }

  /* 底部公式/结论面板：同样是文字块，公式在 ④ 区与教学说明里都有，
     画布上不再铺一层底板 → 不再绘制（保留函数签名）。 */
  function panel(cfg) {
    cfg = cfg || {};
    return { x: cfg.x, y: cfg.y, w: cfg.w, h: cfg.h };
  }

  /* 粗箭头（过程指示） */
  function arrow(cfg) {
    var ctx = S.ctx;
    var x1 = cfg.x1, x2 = cfg.x2, y = cfg.y, h = cfg.h || 13;
    var col = cfg.color || '#1b62b0';
    ctx.save();
    var g = ctx.createLinearGradient(x1, 0, x2, 0);
    g.addColorStop(0, rgba(col, 0.55));
    g.addColorStop(1, rgba(col, 0.98));
    ctx.fillStyle = g;
    var headL = h * 1.5;
    ctx.beginPath();
    ctx.moveTo(x1, y - h / 2);
    ctx.lineTo(x2 - headL, y - h / 2);
    ctx.lineTo(x2 - headL, y - h);
    ctx.lineTo(x2, y);
    ctx.lineTo(x2 - headL, y + h);
    ctx.lineTo(x2 - headL, y + h / 2);
    ctx.lineTo(x1, y + h / 2);
    ctx.closePath();
    ctx.fill();
    ctx.restore();
  }

  /* 刻度尺（竖直，读数指针） */
  function ruler(cfg) {
    var ctx = S.ctx;
    var x = cfg.x, y = cfg.y, h = cfg.h, max = cfg.max, value = cfg.value;
    var w = cfg.w || 34;
    ctx.save();
    var g = ctx.createLinearGradient(x, 0, x + w, 0);
    g.addColorStop(0, '#fdfefe'); g.addColorStop(0.6, '#f0f5fa'); g.addColorStop(1, '#dde6ef');
    rr(x, y, w, h, 4);
    ctx.fillStyle = g;
    ctx.fill();
    ctx.strokeStyle = 'rgba(150,172,192,0.8)';
    ctx.lineWidth = 1;
    ctx.stroke();
    // 刻度：0 在下，max 在上
    ctx.strokeStyle = 'rgba(90,112,132,0.5)';
    for (var v = 0; v <= max; v += max / 20) {
      var yy = y + h - (v / max) * h;
      var major = Math.abs(v % (max / 4)) < 0.001 || Math.abs(v % (max / 4) - max / 4) < 0.001;
      ctx.beginPath();
      ctx.moveTo(x + w, yy);
      ctx.lineTo(x + w - (major ? 12 : 6), yy);
      ctx.lineWidth = major ? 1 : 0.7;
      ctx.stroke();
    }
    // 指针
    var py = y + h - clamp(value / max, 0, 1) * h;
    ctx.beginPath();
    ctx.moveTo(x + w, py);
    ctx.lineTo(x + w + 9, py - 4);
    ctx.lineTo(x + w + 9, py + 4);
    ctx.closePath();
    ctx.fillStyle = '#d9534f';
    ctx.fill();
    ctx.restore();
    return { y: py };
  }

  /* 剖面斜线填充（数学截面、地理岩层） */
  function hatch(cfg) {
    var ctx = S.ctx;
    ctx.save();
    if (cfg.poly) {
      ctx.beginPath();
      ctx.moveTo(cfg.poly[0][0], cfg.poly[0][1]);
      for (var i = 1; i < cfg.poly.length; i++) ctx.lineTo(cfg.poly[i][0], cfg.poly[i][1]);
      ctx.closePath();
      ctx.clip();
    }
    var gap = cfg.gap || 8;
    var col = cfg.color || 'rgba(46,111,216,0.35)';
    var x0 = cfg.x0 == null ? -200 : cfg.x0;
    var x1 = cfg.x1 == null ? S.DW + 200 : cfg.x1;
    var y0 = cfg.y0 == null ? -200 : cfg.y0;
    var y1 = cfg.y1 == null ? S.DH + 200 : cfg.y1;
    ctx.strokeStyle = col;
    ctx.lineWidth = cfg.width || 1;
    for (var k = y0 - (x1 - x0); k < y1; k += gap) {
      ctx.beginPath();
      ctx.moveTo(x0, k);
      ctx.lineTo(x1, k + (x1 - x0));
      ctx.stroke();
    }
    ctx.restore();
  }

  /* 容器尺寸变化时重绘 */
  function responsive(cv, draw) {
    function run() {
      if (resize()) draw();
    }
    window.addEventListener('resize', run);
    if (window.ResizeObserver) {
      try { new ResizeObserver(run).observe(cv.parentNode || cv); } catch (e) { /* 老浏览器忽略 */ }
    }
    return run;
  }

  window.VIS = {
    /* 状态 */
    S: S,
    /* 基础 */
    mount: mount, resize: resize, clear: clear, responsive: responsive,
    wall: wall, shadow: shadow,
    /* 容器 */
    glass: glass, liquid: liquid, glassFront: glassFront,
    /* 实体 */
    box: box, sphere: sphere, cyl: cyl, spring: spring, stand: stand,
    post: post, rail: rail,
    /* 光学 */
    lens: lens, ray: ray, magnifier: magnifier,
    /* 标注 */
    text: text, pill: pill, leader: leader, dot: dot, card: card, panel: panel,
    arrow: arrow, ruler: ruler, hatch: hatch,
    /* 工具 */
    MAT: MAT, mix: mix, shade: shade, rgba: rgba, parseColor: parseColor, rr: rr,
    clamp: clamp, lerp: lerp, spk: spk
  };
})();
