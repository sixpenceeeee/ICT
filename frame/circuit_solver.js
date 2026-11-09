/* circuit_solver.js — 页面运行时直流电阻网络求解器（改进节点电压法）
 * 支持电阻、理想电压源、理想电流源、理想开关。节点名用字符串，ground 默认为 "0"。
 * 页面应在每次状态更新时调用 CIRCUIT.solve(model)，并用返回值更新全部读数。
 */
(function () {
  'use strict';

  function fail(message) { throw new Error('电路求解失败：' + message); }
  function num(c, key, fallback) {
    var x = c[key] == null ? fallback : c[key];
    x = Number(x);
    if (!Number.isFinite(x)) fail('元件 ' + (c.id || '?') + ' 的 ' + key + ' 不是有限数值');
    return x;
  }
  function gaussian(a, b) {
    var n = b.length, m = a.map(function (row, i) { return row.slice().concat([b[i]]); });
    var scale = 1;
    for (var r = 0; r < n; r++) for (var c = 0; c < n; c++) scale = Math.max(scale, Math.abs(a[r][c]));
    var eps = scale * 1e-12;
    for (var col = 0; col < n; col++) {
      var p = col;
      for (var rr = col + 1; rr < n; rr++) if (Math.abs(m[rr][col]) > Math.abs(m[p][col])) p = rr;
      if (Math.abs(m[p][col]) <= eps) fail('方程奇异，可能有浮空节点、矛盾电压源或不可求解拓扑');
      var tmp = m[col]; m[col] = m[p]; m[p] = tmp;
      var div = m[col][col];
      for (var j = col; j <= n; j++) m[col][j] /= div;
      for (var i = 0; i < n; i++) {
        if (i === col) continue;
        var f = m[i][col];
        if (Math.abs(f) <= eps) continue;
        for (var k = col; k <= n; k++) m[i][k] -= f * m[col][k];
      }
    }
    return m.map(function (row) { return row[n]; });
  }
  function kvlResidual(components, branches) {
    var parent = Object.create(null), tree = Object.create(null);
    function find(n) { parent[n] = parent[n] == null ? n : parent[n]; if (parent[n] !== n) parent[n] = find(parent[n]); return parent[n]; }
    function add(n, item) { (tree[n] || (tree[n] = [])).push(item); }
    function pathDrop(start, end) {
      var queue = [start], prev = Object.create(null); prev[start] = null;
      for (var q = 0; q < queue.length; q++) {
        var n = queue[q]; if (n === end) break;
        (tree[n] || []).forEach(function (edge) {
          if (prev[edge.node] === undefined) { prev[edge.node] = { node: n, id: edge.id, sign: edge.sign }; queue.push(edge.node); }
        });
      }
      if (prev[end] === undefined) return null;
      var sum = 0, cur = end;
      while (cur !== start) { var p = prev[cur]; sum += p.sign * branches[p.id].voltage; cur = p.node; }
      return sum;
    }
    var max = 0;
    components.forEach(function (c) {
      if (!c.active) return;
      var a = c.from, b = c.to, ra = find(a), rb = find(b);
      if (ra !== rb) {
        parent[ra] = rb;
        add(a, { node: b, id: c.id, sign: 1 }); add(b, { node: a, id: c.id, sign: -1 });
      } else {
        var rest = pathDrop(b, a);
        if (rest != null) max = Math.max(max, Math.abs(branches[c.id].voltage + rest));
      }
    });
    return max;
  }

  function solve(model) {
    if (!model || !Array.isArray(model.components) || !model.components.length) fail('components 必须是非空数组');
    if (model.components.length > 80) fail('第一版最多支持 80 个元件');
    var ground = String(model.ground == null ? '0' : model.ground), nodes = new Set([ground]), ids = new Set(), comps = [];
    model.components.forEach(function (raw) {
      if (!raw || typeof raw !== 'object') fail('元件必须是对象');
      var id = String(raw.id || '').trim();
      if (!id || ids.has(id)) fail('元件 id 必须存在且唯一');
      ids.add(id);
      var type = String(raw.type || '').toLowerCase().replace(/-/g, '_');
      if (type === 'voltagesource') type = 'voltage_source';
      if (type === 'currentsource') type = 'current_source';
      if (['resistor', 'voltage_source', 'current_source', 'switch', 'ammeter', 'voltmeter'].indexOf(type) < 0) fail('不支持的元件类型 ' + raw.type);
      var from = raw.from == null ? raw.positive : raw.from, to = raw.to == null ? raw.negative : raw.to;
      if (from == null || to == null) fail('元件 ' + id + ' 缺少 from/to 节点');
      from = String(from); to = String(to); nodes.add(from); nodes.add(to);
      var x = { id: id, type: type, from: from, to: to, active: !(type === 'switch' && !raw.closed) };
      if (type === 'resistor') {
        x.ohms = num(raw, 'ohms', raw.resistance);
        if (x.ohms < 0) fail('电阻不能为负值：' + id);
        if (x.ohms === 0) { x.type = 'voltage_source'; x.volts = 0; }
      } else if (type === 'voltage_source') x.volts = num(raw, 'volts', raw.value);
      else if (type === 'ammeter') x.volts = 0;
      else if (type === 'voltmeter') x.ohms = num(raw, 'inputOhms', raw.ohms == null ? 1e7 : raw.ohms);
      else if (type === 'current_source') x.amps = num(raw, 'amps', raw.value);
      else if (type === 'switch' && raw.closed) { x.type = 'voltage_source'; x.volts = 0; }
      comps.push(x);
    });

    var ordered = Array.from(nodes).filter(function (n) { return n !== ground; }).sort();
    if (nodes.size > 80) fail('第一版最多支持 80 个节点');
    var ni = Object.create(null); ordered.forEach(function (n, i) { ni[n] = i; });
    var srcs = comps.filter(function (c) { return c.active && (c.type === 'voltage_source' || c.type === 'ammeter'); });
    var N = ordered.length + srcs.length, A = Array.from({ length: N }, function () { return Array(N).fill(0); });
    var z = Array(N).fill(0), si = Object.create(null);
    function ix(name) { return name === ground ? -1 : ni[name]; }
    function stamp(i, j, g) {
      if (i >= 0) A[i][i] += g;
      if (j >= 0) A[j][j] += g;
      if (i >= 0 && j >= 0) { A[i][j] -= g; A[j][i] -= g; }
    }
    comps.forEach(function (c) {
      if (!c.active) return;
      var i = ix(c.from), j = ix(c.to);
      if (c.type === 'resistor' || c.type === 'voltmeter') {
        if (!(c.ohms > 0)) fail('电阻必须大于 0 Ω：' + c.id);
        stamp(i, j, 1 / c.ohms);
      } else if (c.type === 'current_source') {
        if (i >= 0) z[i] -= c.amps;
        if (j >= 0) z[j] += c.amps;
      } else if (c.type === 'voltage_source' || c.type === 'ammeter') {
        var k = ordered.length + Object.keys(si).length; si[c.id] = k;
        if (i >= 0) { A[i][k] += 1; A[k][i] += 1; }
        if (j >= 0) { A[j][k] -= 1; A[k][j] -= 1; }
        z[k] = c.volts;
      }
    });
    if (!N) fail('电路没有可求解节点或元件');
    var x = gaussian(A, z), nodeVoltages = Object.create(null); nodeVoltages[ground] = 0;
    ordered.forEach(function (n, i) { nodeVoltages[n] = x[i]; });
    var branches = Object.create(null), kcl = Object.create(null), totalPower = 0, sourceResidual = 0;
    Array.from(nodes).forEach(function (n) { kcl[n] = 0; });
    comps.forEach(function (c) {
      var voltage = nodeVoltages[c.from] - nodeVoltages[c.to], current = 0;
      if (c.active) {
        if (c.type === 'resistor' || c.type === 'voltmeter') current = voltage / c.ohms;
        else if (c.type === 'current_source') current = c.amps;
        else { current = x[si[c.id]]; sourceResidual = Math.max(sourceResidual, Math.abs(voltage - (c.volts || 0))); }
      }
      var power = voltage * current;
      kcl[c.from] += current; kcl[c.to] -= current; totalPower += power;
      branches[c.id] = { type: c.type, voltage: voltage, current: current, power: power, active: c.active };
    });
    var kclMax = Math.max.apply(null, Object.keys(kcl).map(function (n) { return Math.abs(kcl[n]); }).concat([0]));
    var siScale = Math.max.apply(null, Object.keys(branches).map(function (id) { return Math.abs(branches[id].current); }).concat([1]));
    var pScale = Math.max.apply(null, Object.keys(branches).map(function (id) { return Math.abs(branches[id].power); }).concat([1]));
    var kvlMax = kvlResidual(comps, branches);
    var vScale = Math.max.apply(null, Object.keys(branches).map(function (id) { return Math.abs(branches[id].voltage); }).concat([1]));
    var checks = { kclMaxResidual: kclMax, kvlMaxResidual: kvlMax, voltageSourceMaxResidual: sourceResidual,
      powerBalanceResidual: totalPower, kcl: kclMax <= 1e-9 * siScale,
      kvl: kvlMax <= 1e-9 * vScale, voltageSources: sourceResidual <= 1e-9,
      powerBalance: Math.abs(totalPower) <= 1e-9 * pScale,
      ground: ground };
    checks.ok = checks.kcl && checks.kvl && checks.voltageSources && checks.powerBalance;
    return { nodes: nodeVoltages, branches: branches, checks: checks };
  }

  function meter(result, componentId, quantity) {
    if (!result || !result.branches || !result.branches[componentId]) fail('找不到表计绑定支路 ' + componentId);
    if (quantity !== 'current' && quantity !== 'voltage') fail('meter quantity 必须是 current 或 voltage');
    var value = result.branches[componentId][quantity];
    if (!Number.isFinite(value)) fail('支路 ' + componentId + ' 的 ' + quantity + ' 不可用');
    return value;
  }

  function signature(model) {
    var parts = (model.components || []).map(function (c) {
      var type = String(c.type || '').toLowerCase().replace(/-/g, '_');
      if (type === 'voltagesource') type = 'voltage_source';
      if (type === 'currentsource') type = 'current_source';
      var from = c.from == null ? c.positive : c.from, to = c.to == null ? c.negative : c.to;
      return [String(c.id || ''), type, String(from), String(to), type === 'switch' ? (c.closed ? '1' : '0') : '-'].join('|');
    }).sort();
    return parts.join(';');
  }

  // 由求解结果写表计数值；DOM 只提供“测哪条支路”，不再由生成代码手算读数。
  function bindMeters(result, root) {
    root = root || document;
    var bindings = [];
    Array.from(root.querySelectorAll('[data-circuit-current-for], [data-circuit-voltage-for]')).forEach(function (el) {
      var kind = el.hasAttribute('data-circuit-current-for') ? 'current' : 'voltage';
      var id = el.getAttribute(kind === 'current' ? 'data-circuit-current-for' : 'data-circuit-voltage-for');
      var value = meter(result, id, kind);
      var decimalsAttr = el.getAttribute('data-decimals');
      var decimals = decimalsAttr == null || decimalsAttr === '' ? 2 : Number(decimalsAttr);
      if (!Number.isInteger(decimals) || decimals < 0 || decimals > 8) decimals = 2;
      el.textContent = value.toFixed(decimals);
      el.setAttribute('data-circuit-bound', 'true');
      bindings.push({ component: id, kind: kind, value: value, elementId: el.id || '' });
    });
    if (!bindings.length) fail('页面没有配置 data-circuit-current-for / data-circuit-voltage-for 表计绑定');
    window.__CIRCUIT_BINDINGS__ = bindings;
    return bindings;
  }

  // 根据模型元件端点和布局节点绘制原理图；导线连接只从同一个 netlist 读取。
  function draw(cv, model, result) {
    if (!cv || !model || !model.layout || !model.layout.nodes) fail('绘图需要 canvas 与 model.layout.nodes');
    if (!result || !result.checks || !result.checks.ok) fail('电路未通过守恒检查，拒绝绘制正常状态');
    var nodes = model.layout.nodes, ctx = cv.getContext('2d');
    if (!ctx) fail('canvas 2D context 不可用');
    var box = cv.parentElement, w = box && box.clientWidth || cv.clientWidth || 780, h = box && box.clientHeight || cv.clientHeight || 420;
    var dpr = window.devicePixelRatio || 1;
    cv.width = Math.max(1, Math.round(w * dpr)); cv.height = Math.max(1, Math.round(h * dpr));
    cv.style.width = w + 'px'; cv.style.height = h + 'px';
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, w, h);
    var pad = Math.min(64, Math.max(30, Math.min(w, h) * .12));
    var xy = Object.create(null);
    Object.keys(nodes).forEach(function (id) {
      var p = nodes[id], x = Number(Array.isArray(p) ? p[0] : p.x), y = Number(Array.isArray(p) ? p[1] : p.y);
      if (!Number.isFinite(x) || !Number.isFinite(y) || x < 0 || x > 1 || y < 0 || y > 1) fail('节点布局坐标必须是 0~1 之间的比例：' + id);
      xy[id] = { x: pad + x * (w - 2 * pad), y: pad + y * (h - 2 * pad) };
    });
    ctx.fillStyle = '#fbfdff'; ctx.fillRect(0, 0, w, h);
    ctx.lineCap = 'round'; ctx.lineJoin = 'round'; ctx.strokeStyle = '#40566c'; ctx.fillStyle = '#24384c';
    ctx.font = '13px sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    var labels = [];
    model.components.forEach(function (c) {
      var from = c.from == null ? c.positive : c.from, to = c.to == null ? c.negative : c.to;
      from = String(from); to = String(to);
      if (!xy[from] || !xy[to]) fail('布局缺少元件端点节点：' + c.id);
      var a = xy[from], b = xy[to], dx = b.x - a.x, dy = b.y - a.y, len = Math.hypot(dx, dy);
      var angle = Math.atan2(dy, dx), cx = (a.x + b.x) / 2, cy = (a.y + b.y) / 2;
      var half = Math.min(43, len * .22), x1 = cx - Math.cos(angle) * half, y1 = cy - Math.sin(angle) * half;
      var x2 = cx + Math.cos(angle) * half, y2 = cy + Math.sin(angle) * half;
      ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(x1, y1); ctx.moveTo(x2, y2); ctx.lineTo(b.x, b.y); ctx.stroke();
      ctx.save(); ctx.translate(cx, cy); ctx.rotate(angle); ctx.strokeStyle = '#31536f'; ctx.fillStyle = '#fbfdff'; ctx.lineWidth = 2.5;
      var type = String(c.type || '').toLowerCase().replace(/-/g, '_');
      if (type === 'resistor' || type === 'voltmeter') {
        if (type === 'voltmeter') {
          ctx.beginPath(); ctx.arc(0, 0, Math.min(15, Math.max(6, len * .16)), 0, Math.PI * 2); ctx.fill(); ctx.stroke();
          ctx.fillStyle = '#24384c'; ctx.font = 'bold 10px sans-serif'; ctx.fillText('V', 0, 0);
        } else {
        ctx.beginPath(); ctx.moveTo(-half, 0);
        for (var i = 0; i < 8; i++) ctx.lineTo(-half + (i + 1) * (half * 2 / 8), i === 7 ? 0 : (i % 2 ? -10 : 10));
        ctx.stroke();
        }
      } else if (type === 'voltage_source' || type === 'voltagesource') {
        ctx.beginPath(); ctx.moveTo(-half, 0); ctx.lineTo(-10, 0); ctx.moveTo(10, 0); ctx.lineTo(half, 0); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(-7, -13); ctx.lineTo(-7, 13); ctx.moveTo(7, -8); ctx.lineTo(7, 8); ctx.stroke();
      } else if (type === 'ammeter') {
        ctx.beginPath(); ctx.arc(0, 0, Math.min(15, Math.max(6, len * .16)), 0, Math.PI * 2); ctx.fill(); ctx.stroke();
        ctx.fillStyle = '#24384c'; ctx.font = 'bold 10px sans-serif'; ctx.fillText('A', 0, 0);
      } else if (type === 'current_source' || type === 'currentsource') {
        ctx.beginPath(); ctx.moveTo(-half, 0); ctx.lineTo(-16, 0); ctx.moveTo(16, 0); ctx.lineTo(half, 0); ctx.stroke();
        ctx.beginPath(); ctx.arc(0, 0, 16, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(-8, 0); ctx.lineTo(8, 0); ctx.moveTo(8, 0); ctx.lineTo(3, -5); ctx.moveTo(8, 0); ctx.lineTo(3, 5); ctx.stroke();
      } else if (type === 'switch') {
        ctx.beginPath(); ctx.arc(-10, 0, 2.7, 0, Math.PI * 2); ctx.arc(10, 0, 2.7, 0, Math.PI * 2); ctx.fill();
        ctx.moveTo(-half, 0); ctx.lineTo(-10, 0); ctx.moveTo(10, 0); ctx.lineTo(half, 0);
        ctx.moveTo(-10, 0); ctx.lineTo(c.closed ? 10 : 7, c.closed ? 0 : -10); ctx.stroke();
      } else fail('绘图器不支持元件类型：' + c.type);
      ctx.restore();
      labels.push({ text: String(c.id) + (c.type === 'resistor' ? '  ' + Number(c.ohms).toFixed(1) + ' Ω' : ''), x: cx, y: cy - 24, size: 13 });
    });
    Object.keys(xy).forEach(function (id) {
      var p = xy[id]; ctx.beginPath(); ctx.arc(p.x, p.y, 4.2, 0, Math.PI * 2); ctx.fillStyle = '#24384c'; ctx.fill();
      labels.push({ text: id, x: p.x, y: p.y + 17, size: 12 });
    });
    // Place every canvas label after all circuit geometry. Try nearby anchors
    // until its measured text box clears earlier labels and canvas edges.
    var placed = [], offsets = [[0,0],[0,-20],[0,20],[-26,0],[26,0],[-26,-18],[26,-18],[-26,18],[26,18],
      [0,-40],[0,40],[-48,0],[48,0],[-48,-24],[48,-24],[-48,24],[48,24]];
    labels.forEach(function (item) {
      ctx.font = item.size + 'px sans-serif';
      var tw = ctx.measureText(item.text).width, th = item.size + 5, chosen = null;
      for (var oi = 0; oi < offsets.length && !chosen; oi++) {
        var lx = item.x + offsets[oi][0], ly = item.y + offsets[oi][1];
        var box = { l: lx - tw/2 - 4, r: lx + tw/2 + 4, t: ly - th/2 - 3, b: ly + th/2 + 3 };
        if (box.l < 4 || box.r > w-4 || box.t < 4 || box.b > h-4) continue;
        if (placed.some(function (p) { return !(box.r < p.l || box.l > p.r || box.b < p.t || box.t > p.b); })) continue;
        chosen = { x: lx, y: ly, box: box };
      }
      if (!chosen) {
        for (var step = 1; step <= 8 && !chosen; step++) {
          var ly2 = Math.min(h-th, Math.max(th, item.y + step*18));
          var b2 = { l: item.x-tw/2-4, r: item.x+tw/2+4, t: ly2-th/2-3, b: ly2+th/2+3 };
          if (b2.l >= 4 && b2.r <= w-4 && !placed.some(function (p) { return !(b2.r < p.l || b2.l > p.r || b2.b < p.t || b2.t > p.b); }))
            chosen = { x: item.x, y: ly2, box: b2 };
        }
      }
      if (!chosen) chosen = { x: Math.max(tw/2+4, Math.min(w-tw/2-4, item.x)), y: Math.max(th/2+4, Math.min(h-th/2-4, item.y)), box: null };
      if (chosen.box) placed.push(chosen.box);
      ctx.fillStyle = 'rgba(255,255,255,0.92)';
      ctx.fillRect(chosen.x-tw/2-4, chosen.y-th/2-3, tw+8, th+6);
      ctx.fillStyle = '#24384c'; ctx.font = item.size + 'px sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText(item.text, chosen.x, chosen.y);
    });
    var sig = signature(model);
    window.__CIRCUIT_DRAW_SIGNATURE__ = sig;
    cv.setAttribute('data-circuit-signature', sig);
    return sig;
  }

  window.CIRCUIT = { solve: solve, meter: meter, bindMeters: bindMeters, draw: draw, signature: signature };
})();
