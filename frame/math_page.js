(() => {
  'use strict';
  function advancedExplanation(key, q, r, divide, product, absolute) {
    if (key.endsWith('section') || key.endsWith('-3d')) {
      const norm = Math.hypot(q.nx, q.ny, q.nz);
      return '截面由平面与立体相交得到。' + divide('原点到截平面的距离', q.offset, norm, Math.abs(r.offset)) +
        '；截面积 = ' + r.area + '。';
    }
    if (key === 'solid-volume') {
      const part = r.volume * q.fraction ** 3;
      const remaining = r.volume - part;
      return '相似小立体的体积 = ' + absolute(r.volume) + ' × ' + absolute(q.fraction ** 3) +
        ' ≈ ' + absolute(part) + '；其余部分 = ' + absolute(remaining) + '。';
    }
    if (key === 'composite-volume') {
      const first = r.components[0].volume;
      const rest = r.components.slice(1).reduce((sum, part) => sum + part.volume, 0);
      return '各部分的体积相加。' + absolute(first) + ' + ' + absolute(rest) + ' ≈ ' + absolute(r.volume, 8) + '。';
    }
    if (key === 'spatial-metrics') {
      if (q.operation === 'point_plane_distance') {
        const norm = Math.hypot(q.vx, q.vy, q.vz);
        const numerator = q.ax*q.vx + q.ay*q.vy + q.az*q.vz - q.d;
        return divide('点到平面的距离', numerator, norm, r.value);
      }
      return '以空间坐标轴为参照，按点、方向向量或平面法向计算。' +
        product(r.unit === 'degree' ? '较小夹角（度）' : '距离（长度单位）', r.value, 1, r.value);
    }
    if (key === 'cube-net-folding') {
      return product('六个正方形面积之和', 6, q.edge_length ** 2, 6*q.edge_length ** 2) + '。' + r.reason;
    }
    if (key === 'cuboid-net-folding') {
      return product('六个矩形面积之和', 2, q.a*q.b+q.b*q.c+q.a*q.c,
        2*(q.a*q.b+q.b*q.c+q.a*q.c)) + '。' + r.reason;
    }
    if (key === 'cylinder-net-unfolding') {
      return product('圆柱侧面积', r.circumference, q.height, r.lateral_area) + '。' + r.reason;
    }
    return product('圆锥侧面积', Math.PI*q.radius, r.slant_height, r.lateral_area) + '。' + r.reason;
  }

  function spatialRequest(q) {
    const a = [q.ax,q.ay,q.az], b = [q.bx,q.by,q.bz], u = [q.ux,q.uy,q.uz], v = [q.vx,q.vy,q.vz];
    return {operation:q.operation,p:a,q:b,point:a,line_point:b,line_direction:u,plane_normal:v,plane_offset:q.d,
      line1_point:a,line2_point:b,line1_direction:u,line2_direction:v,
      plane1_normal:u,plane2_normal:v,plane1_offset:q.d,plane2_offset:q.e};
  }

  const vecAdd = (a, b) => a.map((value, i) => value + b[i]);
  const vecScale = (a, k) => a.map(value => value * k);
  const vecDot = (a, b) => a.reduce((total, value, i) => total + value * b[i], 0);
  const vecCross = (a, b) => [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]];

  function plotGeometry(canvas, paths, marks = []) {
    if (!VIS.mount(canvas, {DW: 900, DH: 560})) return;
    VIS.clear();
    const ctx = VIS.S.ctx;
    const project = ([x,y,z]) => [x - 0.62*y, -0.35*x - 0.35*y - z];
    const points = [...paths.flatMap(item => item[0]), ...marks.map(item => item[0])].map(project);
    const x = points.map(p => p[0]), y = points.map(p => p[1]);
    const left = Math.min(...x), right = Math.max(...x), top = Math.min(...y), bottom = Math.max(...y);
    const factor = Math.min(690 / (right-left || 1), 400 / (bottom-top || 1));
    const at = point => {
      const [a,b] = project(point);
      return [450+(a-(left+right)/2)*factor, 280+(b-(top+bottom)/2)*factor];
    };
    ctx.lineWidth = 3;
    for (const [vertices, color, closed] of paths) {
      ctx.beginPath();
      ctx.moveTo(...at(vertices[0]));
      for (const point of vertices.slice(1)) ctx.lineTo(...at(point));
      if (closed) {
        ctx.closePath();
        ctx.fillStyle = color + '22';
        ctx.fill();
      }
      ctx.strokeStyle = color;
      ctx.stroke();
    }
    ctx.font = '22px sans-serif';
    ctx.fillStyle = '#24384c';
    for (const [point, label] of marks) {
      const [a,b] = at(point);
      ctx.beginPath();
      ctx.arc(a,b,5,0,2*Math.PI);
      ctx.fill();
      ctx.fillText(label,a+8,b-8);
    }
  }

  function planePolygon(n, d, span) {
    const norm = Math.hypot(...n);
    const unit = vecScale(n, 1/norm);
    const origin = vecScale(unit,d/norm);
    const first = vecCross(unit, Math.abs(unit[2]) < 0.8 ? [0,0,1] : [1,0,0]);
    const u = vecScale(first,span/Math.hypot(...first));
    const v = vecCross(unit,u);
    return [[-1,-1],[1,-1],[1,1],[-1,1]].map(([x,y]) => vecAdd(origin,vecAdd(vecScale(u,x),vecScale(v,y))));
  }

  function drawSpatial(canvas, q, result) {
    const unit = Math.max(2, ...[...q.p,...q.q,q.plane_offset,q.plane2_offset].map(Math.abs));
    const paths = [[[[-unit,0,0],[unit,0,0]],'#91a4b7'], [[[0,-unit,0],[0,unit,0]],'#91a4b7'],
      [[[0,0,-unit],[0,0,unit]],'#91a4b7']];
    const marks = [];
    function line(p, direction, color) {
      const vector = vecScale(direction,unit/Math.hypot(...direction));
      paths.push([[vecAdd(p,vecScale(vector,-1)),vecAdd(p,vector)],color]);
    }
    function plane(n, d, color) { paths.push([planePolygon(n,d,unit),color,true]); }
    switch (result.operation) {
      case 'point_point_distance':
        marks.push([q.p,'A'],[q.q,'B']);
        paths.push([[q.p,q.q],'#d17132']);
        break;
      case 'point_line_distance':
        marks.push([q.point,'A']);
        line(q.line_point,q.line_direction,'#3576b6');
        break;
      case 'point_plane_distance': {
        plane(q.plane_normal,q.plane_offset,'#3576b6');
        const normal = q.plane_normal;
        const foot = vecAdd(q.point,vecScale(normal,(q.plane_offset-vecDot(normal,q.point))/vecDot(normal,normal)));
        marks.push([q.point,'A'],[foot,'H']);
        paths.push([[q.point,foot],'#d17132']);
        break;
      }
      case 'line_line_distance':
      case 'line_line_angle':
        line(q.line1_point,q.line1_direction,'#3576b6');
        line(q.line2_point,q.line2_direction,'#d17132');
        break;
      case 'line_plane_distance':
      case 'line_plane_angle':
        plane(q.plane_normal,q.plane_offset,'#3576b6');
        line(q.line_point,q.line_direction,'#d17132');
        break;
      default:
        plane(q.plane1_normal,q.plane1_offset,'#3576b6');
        plane(q.plane2_normal,q.plane2_offset,'#d17132');
    }
    plotGeometry(canvas,paths,marks);
  }

  function solidOutlines(result) {
    const d = result.dimensions;
    const ring = (radius,z) => Array.from({length:48}, (_,i) => {
      const a = 2*Math.PI*i/48;
      return [radius*Math.cos(a),radius*Math.sin(a),z];
    });
    if (result.solid === 'sphere') return [ring(d.radius,0),ring(d.radius,0).map(([x,y])=>[x,0,y]),
      ring(d.radius,0).map(([x,y])=>[0,x,y])];
    if (result.solid === 'cylinder' || result.solid === 'cone') {
      const base = ring(d.radius,0);
      const upper = result.solid === 'cone' ? base.map(()=>[0,0,d.height]) : ring(d.radius,d.height);
      return [base,upper,...[0,12,24,36].map(i=>[base[i],upper[i]])];
    }
    if (result.solid === 'triangular_prism') {
      const base = [[0,0,0],[d.base,0,0],[d.base/2,d.triangle_height,0]];
      const top = base.map(([x,y])=>[x,y,d.length]);
      return [base,top,...base.map((p,i)=>[p,top[i]])];
    }
    const w = d.edge ?? d.length ?? d.base;
    const depth = d.edge ?? d.width ?? d.base;
    const height = d.edge ?? d.height;
    const base = [[0,0,0],[w,0,0],[w,depth,0],[0,depth,0]];
    const top = result.solid === 'square_pyramid' ? base.map(()=>[w/2,depth/2,height]) : base.map(([x,y])=>[x,y,height]);
    return [base,top,...base.map((p,i)=>[p,top[i]])];
  }

  function drawVolume(canvas, cfg, result) {
    const outlines = solidOutlines(result);
    const part = result.volume * cfg.fraction ** 3;
    window.__MATH_VOLUME_PARTITION_CHECK__ = MATH.checkVolumePartition(result.volume,[part,result.volume-part]);
    plotGeometry(canvas, [
      ...outlines.map(points=>[points,'#3576b6',points.length>2]),
      ...outlines.map(points=>[points.map(point=>vecScale(point,cfg.fraction)),'#d17132',points.length>2]),
    ]);
  }

  function compositeRequest(cfg, base) {
    if (!(cfg.scale >= 0.01 && cfg.scale <= 10)) throw new Error('长度缩放须在 0.01 到 10 之间');
    return {operation:'sum_disjoint_components',components:base.map(part => {
      const {solid,...dimensions} = part;
      return {solid,...Object.fromEntries(Object.entries(dimensions).map(([key,value])=>[key,value*cfg.scale]))};
    })};
  }

  function drawComposite(canvas, request, result) {
    let position = 0;
    const paths = [];
    const colors = ['#3576b6','#c06632','#397d62'];
    result.components.forEach((part,i) => {
      const outlines = solidOutlines(part);
      const x = outlines.flat().map(point=>point[0]);
      const left = Math.min(...x), right = Math.max(...x);
      outlines.forEach(points => paths.push([
        points.map(([a,b,c])=>[a-left+position,b,c]),colors[i%colors.length],points.length>2
      ]));
      position += (right-left)*1.8;
    });
    plotGeometry(canvas,paths);
  }

  function cubeNetRequest(q) {
    return {edge_length:q.edge_length,cells:[[0,0],[-1,0],[1,0],[0,-1],[0,1],[q.layout==='offset'?2:0,2]]};
  }

  function cuboidNetRequest(q) {
    const {a,b,c,layout} = q;
    return {dimensions:[a,b,c],faces:[
      {x:0,y:0,width:a,height:b},{x:-c,y:0,width:c,height:b},{x:a,y:0,width:c,height:b},
      {x:0,y:-c,width:a,height:c},{x:0,y:b,width:a,height:c},
      {x:layout==='offset'?a+c:0,y:b+c,width:a,height:b},
    ]};
  }

  function cylinderNetRequest(q) {
    return {radius:q.radius,height:q.height,net:{
      lateral_width:2*Math.PI*q.radius*q.stretch,lateral_height:q.height,cap_radii:[q.radius,q.radius]
    }};
  }

  function coneNetRequest(q) {
    const slant = Math.hypot(q.radius,q.height);
    return {radius:q.radius,height:q.height,net:{
      sector_radius:slant*q.stretch,sector_angle_deg:360*q.radius/slant,cap_radius:q.radius
    }};
  }

  function rectangle(x,y,w,h) { return [[x,y],[x+w,y],[x+w,y+h],[x,y+h]]; }
  function circlePoints(r,x,y) {
    return Array.from({length:48},(_,i) => [x+r*Math.cos(i*Math.PI/24),y+r*Math.sin(i*Math.PI/24)]);
  }

  function drawNetPanels(canvas, flatPaths, foldedPaths) {
    if (!VIS.mount(canvas, {DW: 900, DH: 560})) return;
    VIS.clear();
    const ctx = VIS.S.ctx;
    function panel(paths, center, color) {
      if (!paths.length) return;
      const pts = paths.flat();
      const xs = pts.map(p=>p[0]), ys = pts.map(p=>p[1]);
      const left = Math.min(...xs), right = Math.max(...xs), top = Math.min(...ys), bottom = Math.max(...ys);
      const scale = Math.min(340/(right-left||1),360/(bottom-top||1));
      for (const path of paths) {
        ctx.beginPath();
        path.forEach(([x,y],i) => {
          const px = center+(x-(left+right)/2)*scale;
          const py = 290+(y-(top+bottom)/2)*scale;
          if (i) ctx.lineTo(px,py); else ctx.moveTo(px,py);
        });
        if (path.length > 2) {
          ctx.closePath();
          ctx.fillStyle = color+'20';
          ctx.fill();
        }
        ctx.strokeStyle = color;
        ctx.lineWidth = 2.5;
        ctx.stroke();
      }
    }
    panel(flatPaths,230,'#3576b6');
    panel(foldedPaths,670,'#c06632');
    ctx.font = '22px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillStyle = '#24384c';
    ctx.fillText('平面展开图',230,70);
    ctx.fillText(foldedPaths.length ? '折叠后的立体' : '当前展开图无法折叠',670,70);
    ctx.textAlign = 'start';
  }

  function netProjection(paths) {
    return paths.map(path=>path.map(([x,y,z])=>[x-0.62*y,-0.35*x-0.35*y-z]));
  }

  function drawCubeNet(canvas, request, result) {
    drawNetPanels(canvas, request.cells.map(([x,y])=>rectangle(x,y,1,1)),
      result.valid ? netProjection(result.faces.map(face=>face.vertices)) : []);
  }

  function drawCuboidNet(canvas, request, result) {
    drawNetPanels(canvas, request.faces.map(f=>rectangle(f.x,f.y,f.width,f.height)),
      result.valid ? netProjection(result.faces.map(face=>face.vertices)) : []);
  }

  function drawCylinderNet(canvas, request, result) {
    const {lateral_width:w,lateral_height:h,cap_radii:[r1,r2]} = request.net;
    const flat = [rectangle(0,0,w,h),circlePoints(r1,w/2,-r1),circlePoints(r2,w/2,h+r2)];
    const grid = result.surface_grid;
    const folded = [grid[0],grid[1],...[0,8,16,24].map(i=>[grid[0][i],grid[1][i]])];
    drawNetPanels(canvas,flat,result.valid ? netProjection(folded) : []);
  }

  function drawConeNet(canvas, request, result) {
    const cap = result.base_boundary.map(([x,y])=>[
      x*request.net.cap_radius/request.radius,
      y*request.net.cap_radius/request.radius+request.net.sector_radius+request.net.cap_radius
    ]);
    const grid = result.side_grid;
    const folded = [grid[0],...[0,12,24,36].map(i=>[grid[0][i],result.apex])];
    drawNetPanels(canvas,[result.sector_boundary,cap],result.valid ? netProjection(folded) : []);
  }

  function mount(config, adapter) {
    window.__MATH_DRAWN__ = true;
    const cv = document.getElementById('math-graph');
    const baselineCanvas = document.getElementById('math-baseline-graph');
    const controls = [...document.querySelectorAll('[data-solver-input]')];
    const initialControlValues = Object.fromEntries(
      controls.map(input => [input.dataset.solverInput, input.value])
    );
    const formula = document.getElementById('math-formula');
    const derivation = document.getElementById('math-derivation');
    const error = document.querySelector('[data-solver-error]');
    const current = document.getElementById('math-current');
    const records = [];
    let baseline = null;
    let baselineState = null;
    let latest = null;
    const shown = value => value == null || (Array.isArray(value) && !value.length) ? '—' : String(value);
    const absolute = (value, precision = 12) => Math.abs(value).toLocaleString('en-US', {
      useGrouping: false, maximumSignificantDigits: precision,
    });
    const divide = (label, left, right, answer) =>
      label + '的绝对值 = ' + absolute(left) + ' ÷ ' + absolute(right) + ' ≈ ' + absolute(answer, 8);
    const product = (label, left, right, answer) =>
      label + '的绝对值 = ' + absolute(left) + ' × ' + absolute(right) + ' ≈ ' + absolute(answer, 8);

    function explanation(q, r) {
      switch (config.key) {
        case 'linearSystem': {
          const lines = '直线一 y = ' + q.k1 + 'x + (' + q.b1 + ')；直线二 y = ' + q.k2 + 'x + (' + q.b2 + ')。';
          if (r.x !== null) return lines + ' ' + divide('交点横坐标', q.b2 - q.b1, q.k1 - q.k2, r.x) +
            '。交点 (' + r.x + ', ' + r.y + ') 是方程组的唯一解。';
          const k = absolute(q.k1);
          return lines + ' 斜率差为 ' + k + ' - ' + k + ' = 0。' +
            (r.status === '平行' ? '截距不同，方程组无解。' : '截距相同，方程组有无穷多解。');
        }
        case 'quadratic':
          return 'Δ = b² − 4ac；' + divide('对称轴横坐标', q.b, 2 * q.a, r.axis_x);
        case 'rightTriangle':
          return '面积 = 对边 × 邻边 ÷ 2；' + divide('正弦', q.opposite, r.hypotenuse, r.sine);
        case 'descriptiveStats':
          return divide('均值', q.x1 + q.x2 + q.x3 + q.x4 + q.x5, 5, r.mean);
        case 'sequences':
          return product('等差数列前 n 项和', q.count, (q.first + r.arithmetic_term) / 2, r.arithmetic_sum);
        case 'reciprocal':
          return divide('纵坐标', q.k, q.x, r.y);
        case 'sinusoid':
          return divide('周期', Math.PI * 2, q.omega, r.period);
        case 'expLog':
          return '指数值 = ' + q.base + ' 的 ' + q.x + ' 次幂，反函数复合值 = ' + r.inverse +
            '；' + divide('对数值', Math.log(q.x), Math.log(q.base), r.logarithm);
        case 'functionTransform':
          return '图像使用 y = a f(x−h)+k；' + product('去掉纵向平移后的函数值', q.a,
            q.family === 'quadratic' ? (q.x - q.h) ** 2 : Math.abs(q.x - q.h), r.y - q.k);
        case 'derivative':
          return '切线斜率 = 2ax+b；' + product('切线斜率与 b 的差', 2 * q.a, q.x, r.slope - q.b);
        case 'similarTriangles':
          return product('对应边 a′', q.a, q.scale, r.a2);
        case 'circle':
          return product('弦长', r.half_chord, 2, r.chord);
        case 'polygonArea':
          return product('面积', r.equivalent_base, q.height, r.area);
        case 'constructions':
          return divide('平分后角度', q.angle, 2, r.bisector);
        case 'ellipse':
          return divide('离心率', r.focus, q.a, r.eccentricity);
        case 'sampling':
          return '期望命中次数 = 抽取次数 × 首次命中率；' +
            product('期望命中次数', q.draws, q.good / (q.good + q.bad), r.expected);
        case 'binomial':
          return product('期望', q.trials, q.p, r.mean);
        case 'regression': {
          const meanX = (q.x1 + q.x2 + q.x3) / 3;
          const meanY = (q.y1 + q.y2 + q.y3) / 3;
          return '最小二乘直线过样本中心；' + product('平均纵坐标与截距之差', r.slope, meanX, meanY - r.intercept);
        }
        case 'dotProduct':
          return '数量积 = 两组对应分量乘积之和；' + product('第一组分量的乘积', q.ax, q.bx, q.ax * q.bx);
        case 'fractions':
          return product('第一个通分分子', q.n1, r.common / q.d1, r.left);
        case 'amgm':
          return divide('算术平均', q.a + q.b, 2, r.arithmetic);
        case 'orthographic':
          return product('俯视投影面积', q.width, q.depth, r.top);
        case 'sphereContact':
          return divide('最大内含球半径', Math.min(q.a, q.b, q.c), 2, r.inside_radius);
        case 'surfacePath':
          return '展开后比较三条对角线；' + product('第一种展开矩形的面积', q.a + q.b, q.c, (q.a + q.b) * q.c);
        case 'cavalieri':
          return product('斜棱柱体积', r.section, q.height, r.slanted);
        case 'travel':
          return r.time == null || r.time === 0 ? product('初始位置差', q.gap, 1, q.gap)
            : divide('相遇时间', q.gap, r.closing, r.time);
        default:
          return advancedExplanation(config.key, q, r, divide, product, absolute);
      }
    }

    function addRow(table, values) {
      const row = table.insertRow();
      for (const value of values) row.insertCell().textContent = value;
    }

    function syncTable(result) {
      current.replaceChildren();
      for (const [field, label] of Object.entries(config.fields)) {
        const values = config.comparison ? [shown(baseline?.[field]), shown(result?.[field])] : [shown(result?.[field])];
        addRow(current, [label, ...values]);
      }
    }

    function render() {
      const cfg = Object.fromEntries(controls.map(input => [input.dataset.solverInput,
        input.tagName === 'SELECT' ? input.value : input.valueAsNumber]));
      for (const input of controls) {
        const label = document.getElementById(input.id + '-label');
        if (label) label.textContent = input.value || '—';
      }
      let request, result;
      try {
        request = adapter.request ? adapter.request(cfg) : cfg;
        window[config.requestKey] = request;
        result = adapter.solve(request);
      } catch (failure) {
        window[config.requestKey] = request ?? null;
        window[config.resultKey] = null;
        window.__GEO__ = null;
        adapter.publish(cfg, null);
        latest = null;
        VIS.bindSolverReadouts(null);
        cv.getContext('2d').clearRect(0, 0, cv.width, cv.height);
        formula.textContent = '—';
        derivation.hidden = true;
        error.textContent = failure.message;
        error.hidden = false;
        syncTable(null);
        return;
      }
      error.hidden = true;
      window[config.resultKey] = result;
      adapter.publish(cfg, result);
      latest = {cfg, result};
      if (baseline === null) {
        baseline = result;
        baselineState = {cfg, request, result};
      }
      if (baselineCanvas) {
        adapter.draw(baselineCanvas, baselineState.cfg, baselineState.request, baselineState.result);
      }
      adapter.draw(cv, cfg, request, result);
      formula.textContent = explanation(cfg, result);
      derivation.hidden = !config.derivation;
      if (config.derivation) {
        const inputs = controls.map(input =>
          input.closest('label').querySelector('span')?.textContent.trim() + ' = ' +
          (input.selectedOptions?.[0]?.textContent ?? input.value));
        const outputs = Object.entries(config.fields).map(([field,label]) => label + ' = ' + shown(result[field]));
        derivation.textContent = '① 取值：' + inputs.join('，') + '。② 将当前数值代入上式。③ 核对结果：' +
          outputs.join('，') + '。';
      }
      syncTable(result);
    }

    function setInputs(values) {
      controls.forEach(input => { input.value = values[input.dataset.solverInput]; });
      render();
    }
    controls.forEach(input => input.addEventListener('input', render));
    document.getElementById('btn-reset').addEventListener('click', () => {
      setInputs(initialControlValues);
      const action = document.getElementById('math-action');
      if (action) action.textContent = '';
    });
    for (const [button, values] of Object.entries(config.presets)) {
      const preset = document.getElementById(button);
      preset.addEventListener('click', () => {
        setInputs(values);
        document.getElementById('math-action').textContent = '当前案例：' + preset.textContent;
      });
    }
    document.getElementById('btn-record')?.addEventListener('click', () => {
      if (!latest) return;
      const params = controls.map(input => {
        const value = input.tagName === 'SELECT' ? input.selectedOptions[0]?.textContent : input.value;
        return input.closest('label').querySelector('span')?.textContent.trim() + ' ' + value;
      }).join('；');
      const row = [params, ...Object.keys(config.fields).map(field => shown(latest.result[field]))];
      records.push(row);
      addRow(document.getElementById('math-records'), row);
    });
    document.getElementById('math-csv')?.addEventListener('click', () => {
      const lines = [['操作参数', ...Object.values(config.fields)], ...records];
      const csv = lines.map(line => line.map(value => '"' + value.replaceAll('"', '""') + '"').join(',')).join('\r\n');
      const url = URL.createObjectURL(new Blob(['\ufeff' + csv], {type: 'text/csv;charset=utf-8'}));
      const link = document.createElement('a');
      link.href = url;
      link.download = '数学探究记录.csv';
      link.click();
      document.getElementById('math-action').textContent = '已导出 ' + records.length + ' 条记录';
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    });
    window.addEventListener('resize', render);
    render();
  }

  window.MATHPAGE = {mount, spatialRequest, cubeNetRequest, cuboidNetRequest, cylinderNetRequest,
    coneNetRequest, compositeRequest, drawSpatial, drawVolume, drawComposite, drawCubeNet,
    drawCuboidNet, drawCylinderNet, drawConeNet};
})();
