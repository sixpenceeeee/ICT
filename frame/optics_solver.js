/* frame/optics_solver.js — 凸透镜（理想薄透镜）求解器。
 *
 * 与 frame/circuit_solver.js 同一角色：模型进、结果出，不做任何渲染。
 * 页面必须调用这里的 solve()，并同时暴露 __OPTICS_MODEL__ / __OPTICS_RESULT__；
 * 审查侧用 03_generator_agent/solvers/optics_solver.py 独立复算后对拍。
 *
 * 约定：单位 cm；光心在 x=0，物体在 x=-u，光屏在 x=+s；物体高度 h>0，正立。
 * 薄透镜高斯公式：1/f = 1/u + 1/v ⇒ v = uf/(u-f)；放大率 m = -v/u（负号表示倒立）。
 */
(function (global) {
  'use strict';

  var REL_TOL = 1e-6;          // u=f / u=2f 的分类阈值（相对 f）
  var CHECK_TOL = 1e-12;       // 高斯公式与放大率自检

  function finite(value, name) {
    if (typeof value !== 'number' || !isFinite(value)) {
      throw new Error(name + ' 必须是有限数');
    }
    return value;
  }

  function screenOf(model) {
    var s = model.screen;
    if (s && typeof s === 'object') return finite(s.s, 'screen.s');
    return finite(s == null ? 0 : s, 'screen.s');
  }

  function classify(u, f) {
    var tol = REL_TOL * Math.max(1, f);
    if (Math.abs(u - f) <= tol) return 'u=f';
    if (Math.abs(u - 2 * f) <= tol) return 'u=2f';
    if (u > 2 * f) return 'u>2f';
    if (u > f) return 'f<u<2f';
    return 'u<f';
  }

  function kindText(kind, m) {
    if (kind === 'none') return '不成像';
    var size = Math.abs(m) > 1.0005 ? '放大' : (Math.abs(m) < 0.9995 ? '缩小' : '等大');
    var pose = m < 0 ? '倒立' : '正立';
    return pose + '·' + size + '·' + (kind === 'real' ? '实像' : '虚像');
  }

  /* 三条特殊光线的折线端点（cm，z=0 平面）。虚像时 dashed 段是反向延长线。 */
  function buildRays(f, u, h, v, m, xRight) {
    var rays = [];
    var P = [-u, h];
    var L = [0, h];
    var O = [0, 0];

    // ① 平行于主光轴的光线：过透镜后过像方焦点 F'(f,0)
    rays.push({
      id: 'parallel',
      solid: [[P[0], P[1], 0], [L[0], L[1], 0], [xRight, h - h * xRight / f, 0]],
      dashed: []
    });
    // ② 过光心的光线：方向不变
    rays.push({
      id: 'center',
      solid: [[P[0], P[1], 0], [O[0], O[1], 0], [xRight, -h * xRight / u, 0]],
      dashed: []
    });
    // ③ 过物方焦点 F(-f,0) 的光线：过透镜后平行于主光轴（u=f 时退化，不画）
    if (Math.abs(u - f) > REL_TOL * Math.max(1, f)) {
      var yC = -h * f / (u - f);
      rays.push({
        id: 'focus',
        solid: [[P[0], P[1], 0], [0, yC, 0], [xRight, yC, 0]],
        dashed: []
      });
    }
    if (v != null && v < 0) {
      var I = [v, m * h];
      rays.forEach(function (ray) {
        ray.dashed = [[ray.solid[1][0], ray.solid[1][1], 0], [I[0], I[1], 0]];
      });
    }
    return rays;
  }

  function solve(model) {
    if (!model || typeof model !== 'object') throw new Error('模型必须是对象');
    var f = finite(model.f, 'f');
    var u = finite(model.u, 'u');
    var h = finite(model.h == null ? 2 : model.h, 'h');
    var s = screenOf(model);
    if (f <= 0) throw new Error('f 必须大于 0');
    if (u <= 0) throw new Error('u 必须大于 0');
    if (h <= 0) throw new Error('h 必须大于 0');
    if (s < 0) throw new Error('screen.s 不能为负');

    var uClass = classify(u, f);
    var xRight = Math.min(400, Math.max(s, 2 * f, 40) + 10);
    var result = {
      schema_version: 1,
      scene_id: 'lens_imaging',
      f: f, u: u, h: h, s: s,
      kind: 'none', uClass: uClass,
      v: null, m: null, kindText: '不成像',
      image: null,
      onScreen: { s: s, sharp: false, blur: null, reason: '' },
      rays: [],
      checks: { gauss: null, magnification: null, ok: false }
    };

    if (uClass === 'u=f') {
      result.onScreen.reason = 'u=f：折射光平行射出，不成像';
      result.rays = buildRays(f, u, h, null, null, xRight);
      result.checks = { gauss: 0, magnification: 0, ok: true };
      return result;
    }

    var v = u * f / (u - f);
    var m = -v / u;
    result.v = v;
    result.m = m;
    result.kind = v > 0 ? 'real' : 'virtual';
    result.kindText = kindText(result.kind, m);
    result.image = {
      x: v,
      y: m * h,
      h: Math.abs(m * h),
      inverted: m < 0,
      offscene: Math.abs(v) > xRight
    };

    if (result.kind === 'real') {
      var blur = Math.abs(s - v);
      var sharpTol = Math.max(0.5, 0.01 * Math.abs(v));
      result.onScreen.blur = blur;
      result.onScreen.sharp = blur <= sharpTol;
      result.onScreen.reason = result.onScreen.sharp
        ? '光屏在像距处，像清晰'
        : '光屏偏离像距 ' + blur.toFixed(2) + ' cm，像模糊';
    } else {
      result.onScreen.reason = '虚像：光屏上接不到，需从透镜另一侧观察';
    }

    var gaussResidual = Math.abs(1 / v - (1 / f - 1 / u)) * Math.abs(f);
    var magResidual = Math.abs(m + v / u);
    result.checks = {
      gauss: gaussResidual,
      magnification: magResidual,
      ok: gaussResidual <= CHECK_TOL && magResidual <= CHECK_TOL
    };
    result.rays = buildRays(f, u, h, v, m, xRight);
    return result;
  }

  function signature(model) {
    return ['lens_imaging', model.f, model.u, model.h == null ? 2 : model.h, screenOf(model)].join('|');
  }

  function meter(result, key) {
    var fmt = function (value, digits) {
      return isFinite(value) ? Number(value.toFixed(digits == null ? 2 : digits)).toString() : '—';
    };
    switch (key) {
      case 'v': return result.v == null ? '—' : fmt(result.v) + ' cm';
      case 'm': return result.m == null ? '—' : fmt(result.m) + '×';
      case 'kind': return result.kindText || '—';
      case 'sharp': return result.onScreen && result.onScreen.sharp ? '清晰' : '不清晰';
      case 'screen': return result.onScreen ? fmt(result.onScreen.s) + ' cm' : '—';
      case 'f': return fmt(result.f) + ' cm';
      case 'u': return fmt(result.u) + ' cm';
      case 'h': return fmt(result.h) + ' cm';
      case 'uClass': {
        var labels = {
          'u>2f': '物距大于二倍焦距（u>2f）：倒立、缩小的实像',
          'u=2f': '物距等于二倍焦距（u=2f）：倒立、等大的实像',
          'f<u<2f': '物距在一倍与二倍焦距之间（f<u<2f）：倒立、放大的实像',
          'u=f': '物距等于焦距（u=f）：折射光平行射出，不成像',
          'u<f': '物距小于焦距（u<f）：正立、放大的虚像，光屏上接不到'
        };
        return labels[result.uClass] || result.uClass || '—';
      }
      default: return '—';
    }
  }

  function bindReadouts(result, root) {
    var host = root || (typeof document !== 'undefined' ? document : null);
    if (!host || !host.querySelectorAll) return 0;
    var nodes = host.querySelectorAll('[data-optics-readout]');
    var count = 0;
    for (var i = 0; i < nodes.length; i += 1) {
      var node = nodes[i];
      node.textContent = meter(result, node.getAttribute('data-optics-readout'));
      node.setAttribute('data-optics-bound', 'true');
      count += 1;
    }
    return count;
  }

  global.OPTICS = {
    solve: solve,
    signature: signature,
    meter: meter,
    bindReadouts: bindReadouts,
    kindText: kindText,
    classify: classify
  };
  if (typeof window !== 'undefined') window.OPTICS = global.OPTICS;
}(typeof window !== 'undefined' ? window : globalThis));
