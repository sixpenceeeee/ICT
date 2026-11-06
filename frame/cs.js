/* cs.js —— 信息科技场景库（基于 vis.js 原语，外壳注入）
 *
 *   CS.flow(cv, {                     // 算法流程 / 数据流 / 网络拓扑
 *     nodes: [{ id:'A', label:'输入数据', x:120, y:120, kind:'io' }, ...],
 *     edges: [{ from:'A', to:'B', label:'n 个数' }, ...],
 *     packet: 0.4                     // 数据包在边上的位置 0~1
 *   })
 *
 * 节点按 kind 着色：io 蓝 / process 白 / decision 琥珀 / store 绿 / net 紫
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

  var KIND = {
    io:       { fill: '#e8f2fd', line: '#4a90d9', text: '#134f96', icon: '▤' },
    process:  { fill: '#ffffff', line: '#8aa4bb', text: '#22405a', icon: '⚙' },
    decision: { fill: '#fdf3e0', line: '#e0a13a', text: '#8a5a10', icon: '◇' },
    store:    { fill: '#e9f6ee', line: '#4a9d6e', text: '#1d6042', icon: '▮' },
    net:      { fill: '#f0ecfb', line: '#7c6bd0', text: '#43357f', icon: '◈' }
  };

  /* 一张「斜投影卡片」：正面圆角 + 顶面 + 右侧面 + 接触阴影 */
  function card3d(ctx, x, y, w, h, kind) {
    var k = KIND[kind] || KIND.process;
    var d = 7;
    // 投影
    ctx.save();
    ctx.shadowColor = 'rgba(24,52,80,0.16)';
    ctx.shadowBlur = 10;
    ctx.shadowOffsetY = 4;
    ctx.fillStyle = k.fill;
    ctx.beginPath();
    var r = 9;
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + r);
    ctx.lineTo(x + w, y + h - r);
    ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    ctx.lineTo(x + r, y + h);
    ctx.quadraticCurveTo(x, y + h, x, y + h - r);
    ctx.lineTo(x, y + r);
    ctx.quadraticCurveTo(x, y, x + r, y);
    ctx.fill();
    ctx.restore();
    // 顶面 / 右侧面（等距厚度）
    ctx.beginPath();
    ctx.moveTo(x, y);
    ctx.lineTo(x + d, y - d);
    ctx.lineTo(x + w + d, y - d);
    ctx.lineTo(x + w, y);
    ctx.closePath();
    ctx.fillStyle = V().shade(k.fill, -0.1);
    ctx.fill();
    ctx.beginPath();
    ctx.moveTo(x + w, y);
    ctx.lineTo(x + w + d, y - d);
    ctx.lineTo(x + w + d, y + h - d);
    ctx.lineTo(x + w, y + h);
    ctx.closePath();
    ctx.fillStyle = V().shade(k.fill, -0.2);
    ctx.fill();
    // 正面描边
    ctx.strokeStyle = k.line;
    ctx.lineWidth = 1.5;
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
    ctx.stroke();
    // 顶部高光
    var hg = ctx.createLinearGradient(0, y, 0, y + h * 0.5);
    hg.addColorStop(0, 'rgba(255,255,255,0.7)');
    hg.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = hg;
    ctx.fillRect(x + 1, y + 1, w - 2, h * 0.5);
  }

  function flow(cv, cfg) {
    var v = V();
    cfg = cfg || {};
    if (!v.mount(cv, { DW: DW, DH: DH })) return;
    v.clear();
    var ctx = v.S.ctx;

    var nodes = (cfg.nodes || defaultNodes()).map(function (n) {
      return { id: n.id, label: n.label, x: n.x, y: n.y, kind: n.kind || 'process', w: n.w || 152, h: n.h || 58 };
    });
    var edges = cfg.edges || defaultEdges(nodes);
    var packet = cfg.packet == null ? 0.4 : cfg.packet;
    var byId = {};
    nodes.forEach(function (n) { byId[n.id] = n; });

    v.wall({ tableY: 560 });

    // ---- 连线（先画，永远在卡片下） ----
    edges.forEach(function (e) {
      var a = byId[e.from], b = byId[e.to];
      if (!a || !b) return;
      // 接线点：谁在右边就从右缘出，谁在下面就从上缘/下缘出，避免线穿卡片
      var dxa = b.x - a.x, dya = b.y - a.y;
      var horiz = Math.abs(dxa) >= Math.abs(dya) * 0.9;
      var x1, y1, x2, y2;
      if (horiz) {
        x1 = a.x + (dxa > 0 ? a.w / 2 : -a.w / 2); y1 = a.y;
        x2 = b.x - (dxa > 0 ? b.w / 2 : -b.w / 2); y2 = b.y;
      } else {
        x1 = a.x; y1 = a.y + (dya > 0 ? a.h / 2 : -a.h / 2);
        x2 = b.x; y2 = b.y - (dya > 0 ? b.h / 2 : -b.h / 2);
      }
      // 三次贝塞尔：按方向给控制点，横向走横向切线、纵向走纵向切线
      var c1x, c1y, c2x, c2y;
      if (horiz) {
        c1x = x1 + (x2 - x1) * 0.5; c1y = y1;
        c2x = x2 - (x2 - x1) * 0.5; c2y = y2;
      } else {
        c1x = x1; c1y = y1 + (y2 - y1) * 0.5;
        c2x = x2; c2y = y2 - (y2 - y1) * 0.5;
      }
      ctx.save();
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.bezierCurveTo(c1x, c1y, c2x, c2y, x2, y2);
      ctx.strokeStyle = 'rgba(90,130,170,0.55)';
      ctx.lineWidth = 2.2;
      ctx.stroke();
      // 箭头（按终点切线方向，纵向连线才不会歪）
      var ang = Math.atan2(y2 - c2y, x2 - c2x);
      ctx.beginPath();
      ctx.moveTo(x2, y2);
      ctx.lineTo(x2 - 9 * Math.cos(ang - 0.42), y2 - 9 * Math.sin(ang - 0.42));
      ctx.lineTo(x2 - 9 * Math.cos(ang + 0.42), y2 - 9 * Math.sin(ang + 0.42));
      ctx.closePath();
      ctx.fillStyle = 'rgba(90,130,170,0.75)';
      ctx.fill();
      ctx.restore();
      // 数据包
      if (packet > 0) {
        var t = v.clamp(packet, 0, 1);
        var px = bez(x1, c1x, c2x, x2, t), py = bez(y1, c1y, c2y, y2, t);
        var pg = ctx.createRadialGradient(px, py, 1, px, py, 7);
        pg.addColorStop(0, '#ffffff');
        pg.addColorStop(0.45, '#7fc4f5');
        pg.addColorStop(1, 'rgba(80,170,235,0)');
        ctx.beginPath();
        ctx.arc(px, py, 7, 0, Math.PI * 2);
        ctx.fillStyle = pg;
        ctx.fill();
        ctx.beginPath();
        ctx.arc(px, py, 2.6, 0, Math.PI * 2);
        ctx.fillStyle = '#1b62b0';
        ctx.fill();
      }
      // 连线标签
      if (e.label) {
        var mx = bez(x1, c1x, c2x, x2, 0.5), my = bez(y1, c1y, c2y, y2, 0.5);
        v.text({ x: mx + (horiz ? 0 : 20), y: my - (horiz ? 12 : 0), text: e.label, size: 11.5, color: '#42688a', pad: 'rgba(255,255,255,0.9)' });
      }
    });

    // ---- 卡片 ----
    nodes.forEach(function (n) {
      var x = n.x - n.w / 2, y = n.y - n.h / 2;
      card3d(ctx, x, y, n.w, n.h, n.kind);
      var k = KIND[n.kind] || KIND.process;
      // 图标
      ctx.font = '600 15px "Microsoft YaHei", system-ui, sans-serif';
      ctx.fillStyle = k.line;
      ctx.textAlign = 'left';
      ctx.textBaseline = 'middle';
      ctx.fillText(k.icon, x + 14, n.y + 1);
      // 文本（走 VIS.text 保证收边与描边规则一致）
      v.text({
        x: x + 30, y: n.y, text: n.label,
        size: 13.5, weight: 700, color: k.text, align: 'left', stroke: false
      });
    });

    // ---- 标题与图例 ----
    v.text({ x: 450, y: 44, text: cfg.title || '算法流程与数据流', size: 17, weight: 700, color: '#134f96' });
    var pn = v.panel({ x: 640, y: 470, w: 240, h: 116 });
    v.text({ x: pn.x + 16, y: pn.y + 24, text: '图例', size: 13, weight: 700, color: '#134f96', align: 'left', stroke: false });
    var legend = [['io', '输入 / 输出'], ['process', '处理步骤'], ['decision', '判断分支'], ['store', '数据存储']];
    legend.forEach(function (lg, i) {
      var ly = pn.y + 48 + i * 18;
      ctx.beginPath();
      ctx.arc(pn.x + 22, ly, 4, 0, Math.PI * 2);
      ctx.fillStyle = KIND[lg[0]].line;
      ctx.fill();
      v.text({ x: pn.x + 34, y: ly, text: lg[1], size: 11.5, color: '#3d6c92', align: 'left', stroke: false });
    });

    say(cv, '装置：算法流程图，共 ' + nodes.length + ' 个节点、' + edges.length + ' 条数据流');
  }

  function bez(p0, p1, p2, p3, t) {
    var mt = 1 - t;
    return mt * mt * mt * p0 + 3 * mt * mt * t * p1 + 3 * mt * t * t * p2 + t * t * t * p3;
  }

  function defaultNodes() {
    return [
      { id: 'A', label: '输入数据', x: 152, y: 168, kind: 'io' },
      { id: 'B', label: '遍历与比较', x: 392, y: 168, kind: 'process' },
      { id: 'C', label: '是否满足条件', x: 392, y: 320, kind: 'decision' },
      { id: 'D', label: '存入结果集', x: 392, y: 472, kind: 'store' },
      { id: 'E', label: '输出结果', x: 706, y: 320, kind: 'io' }
    ];
  }
  function defaultEdges() {
    return [
      { from: 'A', to: 'B', label: 'n 个元素' },
      { from: 'B', to: 'C' },
      { from: 'C', to: 'D', label: '是' },
      { from: 'D', to: 'E' },
      { from: 'C', to: 'E', label: '否' }
    ];
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
    if (window.__CS_DRAWN__) return;
    var cv = document.querySelector('.exp-canvas-box canvas') || document.querySelector('canvas');
    if (!cv) return;
    // 页面自己画得出来就必须让位，否则两套版面抢同一张画布（见 isBlank 注释）
    if (!isBlank(cv)) { window.__CS_DRAWN__ = true; return; }
    var txt = (document.body ? document.body.innerText : '') + ' ' + (document.title || '');
    if (/算法|流程|程序|数据|网络|循环|排序/.test(txt)) {
      flow(cv, {});
      window.__CS_DRAWN__ = true;
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

  window.CS = { flow: flow, auto: auto };
})();
