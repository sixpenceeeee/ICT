/* frame/optics3d.js — 3D 光具座（凸透镜成像）。
 *
 * 依赖（由 shell.py 按顺序内联，见 render()）：window.THREE（r118 UMD）→
 * frame/optics_solver.js（window.OPTICS）→ 本文件。
 *
 * 单一入口纪律：任何模型变化都走 paint() —— solve → 更新网格 → 绑定读数 →
 * 写快照（__OPTICS_MODEL__ / __OPTICS_RESULT__ / __OPTICS_VIEW__ / canvas.__mathView）。
 * 页面脚本只负责控件，不自己算光学量。
 *
 * 视角：yaw/pitch 轨道旋转由本文件维护；canvas.__mathView 与审查端
 * checks_browser.js 的「拖动后复位」判据同名同形状，勿改名。
 */
(function (global) {
  'use strict';

  var DEFAULT_VIEW = { yaw: -0.75, pitch: 0.5 };
  var PITCH_MIN = 0.08;
  var PITCH_MAX = 1.35;
  var SNAP_CM = 1;

  var LENS_RADIUS = 5.8;
  var SCREEN_SIZE = 14.0;
  var RAIL_TOP_Y = -10.0;
  var SADDLE_Y = -9.75;
  var SADDLE_TOP_Y = -9.5;

  function clamp(v, lo, hi) { return Math.min(hi, Math.max(lo, v)); }
  function clone(o) { return JSON.parse(JSON.stringify(o)); }

  function unavailable(cv, reason) {
    /* WebGL 不可用时：不伪造 3D 画面，把事实暴露给审查端，读数仍由求解器给出。 */
    global.__OPTICS_RENDER3D__ = 'unavailable';
    if (cv && cv.dataset) cv.dataset.optics3d = 'unavailable';
    var ctx = cv && cv.getContext ? cv.getContext('2d') : null;
    if (ctx) {
      ctx.fillStyle = '#111';
      ctx.font = '14px sans-serif';
      ctx.fillText('当前环境无法启用 WebGL：' + reason, 16, 28);
    }
  }

  function makeLabelSprite(THREE, text, opts) {
    opts = opts || {};
    var padX = opts.padX || 12;
    var fontSize = opts.fontSize || 24;
    var canvas = document.createElement('canvas');
    canvas.style.display = 'none';
    var ctx = canvas.getContext('2d');
    var font = (opts.bold ? '700 ' : '600 ') + fontSize + 'px "PingFang SC","Microsoft YaHei",sans-serif';
    ctx.font = font;
    var textW = Math.ceil(ctx.measureText(text).width);
    canvas.width = Math.max(64, textW + padX * 2);
    canvas.height = Math.ceil(fontSize * 1.6);

    ctx.font = font;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    if (opts.bg) {
      var r = 10;
      var w = canvas.width - 2;
      var h = canvas.height - 2;
      ctx.fillStyle = opts.bg;
      ctx.beginPath();
      ctx.moveTo(1 + r, 1);
      ctx.lineTo(1 + w - r, 1);
      ctx.quadraticCurveTo(1 + w, 1, 1 + w, 1 + r);
      ctx.lineTo(1 + w, 1 + h - r);
      ctx.quadraticCurveTo(1 + w, 1 + h, 1 + w - r, 1 + h);
      ctx.lineTo(1 + r, 1 + h);
      ctx.quadraticCurveTo(1, 1 + h, 1, 1 + h - r);
      ctx.lineTo(1, 1 + r);
      ctx.quadraticCurveTo(1, 1, 1 + r, 1);
      ctx.closePath();
      ctx.fill();
      if (opts.border) {
        ctx.strokeStyle = opts.border;
        ctx.lineWidth = 2;
        ctx.stroke();
      }
    }
    ctx.fillStyle = opts.color || '#1e293b';
    ctx.fillText(text, canvas.width / 2, canvas.height / 2 + 1);

    var tex = new THREE.CanvasTexture(canvas);
    tex.minFilter = THREE.LinearFilter;
    var mat = new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false });
    var sprite = new THREE.Sprite(mat);
    var worldH = opts.worldH || 2.6;
    sprite.scale.set(worldH * (canvas.width / canvas.height), worldH, 1);
    sprite.renderOrder = 3;
    return sprite;
  }

  function createArrowParts(THREE, mat, radius, stemRadius) {
    var pivot = new THREE.Group();
    var stem = new THREE.Mesh(new THREE.CylinderGeometry(stemRadius, stemRadius, 1, 12), mat);
    var head = new THREE.Mesh(new THREE.ConeGeometry(radius, 1, 18), mat);
    pivot.add(stem, head);
    return { pivot: pivot, stem: stem, head: head };
  }

  function syncArrowParts(parts, height, inverted) {
    var h = Math.max(0.25, height);
    var headH = Math.min(1.05, Math.max(0.22, h * 0.34));
    var stemH = Math.max(0.02, h - headH);
    parts.stem.scale.set(1, stemH, 1);
    parts.stem.position.y = stemH / 2;
    parts.head.scale.set(1, headH, 1);
    parts.head.position.y = stemH + headH / 2;
    parts.pivot.rotation.z = inverted ? Math.PI : 0;
  }

  function createScreenTexture(THREE) {
    var canvas = document.createElement('canvas');
    canvas.style.display = 'none';
    canvas.width = 256;
    canvas.height = 256;
    var ctx = canvas.getContext('2d');
    var tex = new THREE.CanvasTexture(canvas);
    tex.minFilter = THREE.LinearFilter;

    function draw(result) {
      var S = 256;
      var C = S / 2;
      var pxPerCm = S / SCREEN_SIZE;
      ctx.clearRect(0, 0, S, S);
      ctx.fillStyle = '#f8f7f2';
      ctx.fillRect(0, 0, S, S);

      /* 屏面十字光轴准星 */
      ctx.save();
      ctx.strokeStyle = 'rgba(100, 116, 139, 0.28)';
      ctx.lineWidth = 1.5;
      ctx.setLineDash([6, 5]);
      ctx.beginPath();
      ctx.moveTo(0, C); ctx.lineTo(S, C);
      ctx.moveTo(C, 0); ctx.lineTo(C, S);
      ctx.stroke();
      ctx.restore();

      if (!result) { tex.needsUpdate = true; return; }

      if (result.kind === 'none') {
        var rBeam = LENS_RADIUS * pxPerCm * 0.72;
        var gNone = ctx.createRadialGradient(C, C, 4, C, C, rBeam);
        gNone.addColorStop(0, 'rgba(245, 158, 11, 0.35)');
        gNone.addColorStop(0.75, 'rgba(245, 158, 11, 0.14)');
        gNone.addColorStop(1, 'rgba(245, 158, 11, 0)');
        ctx.fillStyle = gNone;
        ctx.beginPath();
        ctx.arc(C, C, rBeam, 0, Math.PI * 2);
        ctx.fill();
        tex.needsUpdate = true;
        return;
      }

      if (result.kind === 'virtual') {
        var rHalo = Math.min(S * 0.46, LENS_RADIUS * pxPerCm * 0.95);
        var gVirt = ctx.createRadialGradient(C, C, 6, C, C, rHalo);
        gVirt.addColorStop(0, 'rgba(245, 158, 11, 0.16)');
        gVirt.addColorStop(1, 'rgba(245, 158, 11, 0)');
        ctx.fillStyle = gVirt;
        ctx.beginPath();
        ctx.arc(C, C, rHalo, 0, Math.PI * 2);
        ctx.fill();
        tex.needsUpdate = true;
        return;
      }

      /* 实像在光屏上的投影：按 |s - v| 计算弥散圆大小与透明度 */
      var vAbs = Math.max(2, Math.abs(result.v));
      var blurCm = Math.abs(result.s - result.v) * (LENS_RADIUS / vAbs);
      var sharp = !!(result.onScreen && result.onScreen.sharp);
      var imgTipY = clamp(-result.image.y * pxPerCm, -C + 14, C - 14);
      var blurPx = sharp ? 0 : clamp(blurCm * pxPerCm * 0.65, 3, 56);

      if (sharp) {
        /* 清晰倒立实像 + 轻微发光外晕 */
        ctx.save();
        ctx.shadowColor = 'rgba(22, 163, 74, 0.55)';
        ctx.shadowBlur = 10;
        ctx.strokeStyle = '#16a34a';
        ctx.fillStyle = '#16a34a';
        ctx.lineWidth = 6;
        ctx.lineCap = 'round';
        var dir = imgTipY >= 0 ? 1 : -1;
        var headLen = Math.min(18, Math.max(8, Math.abs(imgTipY) * 0.34));
        var stemEnd = imgTipY - dir * headLen * 0.7;
        ctx.beginPath();
        ctx.moveTo(C, C);
        ctx.lineTo(C, C + stemEnd);
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(C, C + imgTipY);
        ctx.lineTo(C - 11, C + imgTipY - dir * headLen);
        ctx.lineTo(C + 11, C + imgTipY - dir * headLen);
        ctx.closePath();
        ctx.fill();
        ctx.restore();
      } else {
        /* 偏离像距：像弥散为柔和渐变光斑 */
        var alpha = clamp(0.62 - blurPx / 95, 0.14, 0.58);
        var centerY = C + imgTipY * 0.55;
        var spotR = clamp(blurPx * 1.15 + 12, 14, S * 0.46);
        var grad = ctx.createRadialGradient(C, centerY, 2, C, centerY, spotR);
        grad.addColorStop(0, 'rgba(34, 197, 94, ' + alpha.toFixed(2) + ')');
        grad.addColorStop(0.55, 'rgba(234, 179, 8, ' + (alpha * 0.45).toFixed(2) + ')');
        grad.addColorStop(1, 'rgba(234, 179, 8, 0)');
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(C, centerY, spotR, 0, Math.PI * 2);
        ctx.fill();
      }
      tex.needsUpdate = true;
    }

    return { texture: tex, draw: draw };
  }

  function mount(cv, initialModel, options) {
    options = options || {};
    var domRoot = options.root || document;
    var isolated = !!options.isolated;
    var THREE = global.THREE;
    if (!THREE) throw new Error('缺少 THREE（shell.py 未内联 vendor/three.r118.js）');
    if (!global.OPTICS) throw new Error('缺少 OPTICS 求解器（shell.py 未内联 frame/optics_solver.js）');

    var model = clone(initialModel);
    var view = {
      yaw: (model.view && model.view.yaw) || DEFAULT_VIEW.yaw,
      pitch: (model.view && model.view.pitch) || DEFAULT_VIEW.pitch,
      dist: (model.view && model.view.dist) || 0
    };
    var defaultView = { yaw: view.yaw, pitch: view.pitch };

    var renderer;
    try {
      renderer = new THREE.WebGLRenderer({
        canvas: cv, antialias: true, alpha: false,
        preserveDrawingBuffer: true   // visualSig 用 toDataURL 取像素，必须保留缓冲
      });
    } catch (err) {
      unavailable(cv, (err && err.message) || String(err));
      return null;
    }
    renderer.setPixelRatio(Math.min(global.devicePixelRatio || 1, 2));

    var scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf6f8fb);
    var camera = new THREE.PerspectiveCamera(45, 1, 0.5, 4000);
    var target = new THREE.Vector3(0, -1.2, 0);

    scene.add(new THREE.AmbientLight(0xffffff, 0.85));
    var key = new THREE.DirectionalLight(0xffffff, 0.72);
    key.position.set(60, 120, 90);
    scene.add(key);

    /* ---------- 静态布景：主光轴、金属导轨、刻度与数字 ---------- */
    var axisMat = new THREE.LineBasicMaterial({ color: 0x64748b });
    var axisGeo = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(-150, 0, 0), new THREE.Vector3(170, 0, 0)
    ]);
    scene.add(new THREE.Line(axisGeo, axisMat));

    var railBodyMat = new THREE.MeshPhongMaterial({ color: 0x64748b });
    var railTopMat = new THREE.MeshPhongMaterial({ color: 0xdbe3ee });
    var postMat = new THREE.MeshPhongMaterial({ color: 0x94a3b8 });
    var saddleMat = new THREE.MeshPhongMaterial({ color: 0x334155 });

    var rail = new THREE.Mesh(new THREE.BoxGeometry(320, 0.9, 6.2), railBodyMat);
    rail.position.set(10, RAIL_TOP_Y - 0.45, 0);
    scene.add(rail);

    var railTop = new THREE.Mesh(new THREE.BoxGeometry(320, 0.14, 5.4), railTopMat);
    railTop.position.set(10, RAIL_TOP_Y + 0.02, 0);
    scene.add(railTop);

    var tickMat = new THREE.LineBasicMaterial({ color: 0x475569 });
    for (var tick = -140; tick <= 160; tick += 10) {
      var big = tick % 50 === 0;
      var zSpan = big ? 2.55 : 1.5;
      var geo = new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(tick, RAIL_TOP_Y + 0.11, -zSpan),
        new THREE.Vector3(tick, RAIL_TOP_Y + 0.11, zSpan)
      ]);
      scene.add(new THREE.Line(geo, tickMat));
      if (big && tick >= -100 && tick <= 150) {
        var tickLabel = makeLabelSprite(THREE, tick + ' cm', {
          color: '#475569', fontSize: 22, worldH: 2.3
        });
        tickLabel.position.set(tick, RAIL_TOP_Y - 2.3, 3.6);
        scene.add(tickLabel);
      }
    }

    /* ---------- 焦距标桩（2F / F / O / F' / 2F'） ---------- */
    var focalMarkers = {};
    var markerMat = new THREE.MeshPhongMaterial({ color: 0x2563eb });
    var markerDefs = [
      ['2F', '#eff6ff', '#1d4ed8'],
      ['F', '#eff6ff', '#1d4ed8'],
      ['O', '#e0f2fe', '#0369a1'],
      ['F′', '#eff6ff', '#1d4ed8'],
      ['2F′', '#eff6ff', '#1d4ed8']
    ];
    markerDefs.forEach(function (def) {
      var g = new THREE.Group();
      var dot = new THREE.Mesh(new THREE.SphereGeometry(0.42, 12, 12), markerMat);
      var lbl = makeLabelSprite(THREE, def[0], {
        bg: def[1], border: '#93c5fd', color: def[2], bold: true, fontSize: 24, worldH: 2.4
      });
      lbl.position.set(0, -2.3, 1.8);
      g.add(dot, lbl);
      scene.add(g);
      focalMarkers[def[0]] = g;
    });

    /* ---------- 透镜（底座 + 支架只连到镜框底缘，不穿玻璃） ---------- */
    var lensGroup = new THREE.Group();
    var lensGlass = new THREE.Mesh(
      new THREE.CylinderGeometry(LENS_RADIUS, LENS_RADIUS, 0.72, 48, 1, false),
      new THREE.MeshPhongMaterial({
        color: 0x7dd3fc, transparent: true, opacity: 0.30, depthWrite: false,
        shininess: 95, side: THREE.DoubleSide
      })
    );
    lensGlass.rotation.z = Math.PI / 2;
    var lensRim = new THREE.Mesh(
      new THREE.TorusGeometry(LENS_RADIUS, 0.28, 12, 48),
      new THREE.MeshPhongMaterial({ color: 0x2563eb })
    );
    lensRim.rotation.y = Math.PI / 2;
    var lensSpan = -SADDLE_TOP_Y - LENS_RADIUS;
    var lensPost = new THREE.Mesh(new THREE.CylinderGeometry(0.45, 0.55, lensSpan, 16), postMat);
    lensPost.position.y = SADDLE_TOP_Y + lensSpan / 2;
    var lensSaddle = new THREE.Mesh(new THREE.BoxGeometry(2.6, 0.6, 5.8), saddleMat);
    lensSaddle.position.y = SADDLE_Y;
    var lensLabel = makeLabelSprite(THREE, '凸透镜', {
      bg: '#eff6ff', border: '#60a5fa', color: '#1d4ed8', bold: true, fontSize: 22, worldH: 2.5
    });
    lensLabel.position.set(0, LENS_RADIUS + 2.1, 0);
    lensGroup.add(lensGlass, lensRim, lensPost, lensSaddle, lensLabel);
    scene.add(lensGroup);

    /* ---------- 物体（底座 + 细立柱 + 主光轴以上的发光箭头） ---------- */
    var objectGroup = new THREE.Group();
    var objectMat = new THREE.MeshPhongMaterial({ color: 0xd9483b, emissive: 0x45120e });
    var objectParts = createArrowParts(THREE, objectMat, 0.72, 0.24);
    var objStemSpan = -SADDLE_TOP_Y;
    var objectSupport = new THREE.Mesh(new THREE.CylinderGeometry(0.32, 0.42, objStemSpan, 14), postMat);
    objectSupport.position.y = SADDLE_TOP_Y + objStemSpan / 2;
    var objectSaddle = new THREE.Mesh(new THREE.BoxGeometry(2.4, 0.6, 5.6), saddleMat);
    objectSaddle.position.y = SADDLE_Y;
    var objectLabel = makeLabelSprite(THREE, '物', {
      bg: '#fef2f2', border: '#fca5a5', color: '#b91c1c', bold: true, fontSize: 22, worldH: 2.4
    });
    objectGroup.userData.draggable = 'object';
    objectGroup.add(objectParts.pivot, objectSupport, objectSaddle, objectLabel);
    scene.add(objectGroup);

    /* ---------- 光屏（居中于光轴 y=0，底部严丝合缝连到底座，带动态投影纹理） ---------- */
    var screenGroup = new THREE.Group();
    var screenTex = createScreenTexture(THREE);
    var screenPanel = new THREE.Mesh(
      new THREE.PlaneGeometry(SCREEN_SIZE, SCREEN_SIZE),
      new THREE.MeshPhongMaterial({
        map: screenTex.texture, transparent: true, opacity: 0.78, depthWrite: false, side: THREE.DoubleSide
      })
    );
    screenPanel.rotation.y = Math.PI / 2;
    screenPanel.position.y = 0;
    var screenFrame = new THREE.LineSegments(
      new THREE.EdgesGeometry(new THREE.PlaneGeometry(SCREEN_SIZE, SCREEN_SIZE)),
      new THREE.LineBasicMaterial({ color: 0x334155 })
    );
    screenFrame.rotation.y = Math.PI / 2;
    screenFrame.position.y = 0;
    var screenSpan = -SADDLE_TOP_Y - SCREEN_SIZE / 2; // 9.5 - 7.0 = 2.5
    var screenPost = new THREE.Mesh(new THREE.CylinderGeometry(0.45, 0.55, screenSpan, 14), postMat);
    screenPost.position.y = SADDLE_TOP_Y + screenSpan / 2;
    var screenSaddle = new THREE.Mesh(new THREE.BoxGeometry(2.6, 0.6, 5.8), saddleMat);
    screenSaddle.position.y = SADDLE_Y;
    var screenLabel = makeLabelSprite(THREE, '光屏', {
      bg: '#f1f5f9', border: '#94a3b8', color: '#334155', bold: true, fontSize: 22, worldH: 2.5
    });
    screenLabel.position.set(0, SCREEN_SIZE / 2 + 1.9, 0);
    screenGroup.userData.draggable = 'screen';
    screenGroup.add(screenPanel, screenFrame, screenPost, screenSaddle, screenLabel);
    scene.add(screenGroup);

    /* ---------- 像（实像翠绿，虚像紫色线框 + 标签） ---------- */
    var imageGroup = new THREE.Group();
    var imageMat = new THREE.MeshPhongMaterial({ color: 0x16a34a, transparent: true, opacity: 0.94 });
    var imageParts = createArrowParts(THREE, imageMat, 0.68, 0.22);
    var realImageLabel = makeLabelSprite(THREE, '实像', {
      bg: '#f0fdf4', border: '#86efac', color: '#15803d', bold: true, fontSize: 22, worldH: 2.4
    });
    var virtualImageLabel = makeLabelSprite(THREE, '虚像', {
      bg: '#faf5ff', border: '#d8b4fe', color: '#7e22ce', bold: true, fontSize: 22, worldH: 2.4
    });
    imageGroup.add(imageParts.pivot, realImageLabel, virtualImageLabel);
    scene.add(imageGroup);

    /* ---------- 光线容器 + 传播方向小箭头 ---------- */
    var raysGroup = new THREE.Group();
    scene.add(raysGroup);

    var solidMat = new THREE.LineBasicMaterial({ color: 0xe09b25 });
    var dashedMat = new THREE.LineDashedMaterial({ color: 0xa855f7, dashSize: 3, gapSize: 2 });
    var rayArrowMat = new THREE.MeshBasicMaterial({ color: 0xd97706 });
    var rayArrowGeo = new THREE.ConeGeometry(0.24, 0.78, 10);
    var upVec = new THREE.Vector3(0, 1, 0);

    function clearRays() {
      while (raysGroup.children.length) {
        var child = raysGroup.children.pop();
        if (child.isLine && child.geometry) child.geometry.dispose();
      }
    }

    function addRayArrow(a, b) {
      var p1 = new THREE.Vector3(a[0], a[1], a[2] || 0);
      var p2 = new THREE.Vector3(b[0], b[1], b[2] || 0);
      var dir = p2.clone().sub(p1);
      var len = dir.length();
      if (len < 4) return;
      dir.normalize();
      var cone = new THREE.Mesh(rayArrowGeo, rayArrowMat);
      cone.position.copy(p1).addScaledVector(dir, Math.min(len * 0.42, 16));
      cone.quaternion.setFromUnitVectors(upVec, dir);
      raysGroup.add(cone);
    }

    function addRay(points, dashed) {
      var vectors = points.map(function (p) { return new THREE.Vector3(p[0], p[1], p[2] || 0); });
      var geo = new THREE.BufferGeometry().setFromPoints(vectors);
      var line = new THREE.Line(geo, dashed ? dashedMat : solidMat);
      if (dashed) line.computeLineDistances();
      raysGroup.add(line);
      if (!dashed && points.length >= 3) {
        addRayArrow(points[0], points[1]);
        addRayArrow(points[1], points[2]);
      }
    }

    /* ---------- 视角 ---------- */
    function defaultDist() {
      return clamp((model.u + (model.screen ? model.screen.s : 0)) * 0.9 + 42, 90, 900);
    }
    if (!view.dist) view.dist = defaultDist();

    function applyView() {
      view.pitch = clamp(view.pitch, PITCH_MIN, PITCH_MAX);
      /* 把视点对到「物—屏」的中点，物距很大时光具座不会跑出画面 */
      target.x = ((model.screen ? model.screen.s : 0) - model.u) / 2;
      var cp = Math.cos(view.pitch);
      camera.position.set(
        target.x + view.dist * cp * Math.sin(view.yaw),
        target.y + view.dist * Math.sin(view.pitch),
        target.z + view.dist * cp * Math.cos(view.yaw)
      );
      camera.lookAt(target);
      /* 审查端 checks_browser.js 的「拖动后复位」读的就是这两个字段 */
      cv.__mathView = { yaw: view.yaw, pitch: view.pitch };
      if (!isolated) global.__OPTICS_VIEW__ = { yaw: view.yaw, pitch: view.pitch, dist: view.dist };
    }

    /* ---------- 求解 + 同步 ---------- */
    var lastResult = null;

    function syncMeshes(result) {
      objectGroup.position.x = -model.u;
      syncArrowParts(objectParts, model.h, false);
      objectLabel.position.set(0, Math.max(0.5, model.h) + 1.8, 0);

      screenGroup.position.x = model.screen ? model.screen.s : 0;
      screenTex.draw(result);

      focalMarkers['2F'].position.x = -2 * model.f;
      focalMarkers['F'].position.x = -model.f;
      focalMarkers['O'].position.x = 0;
      focalMarkers['F′'].position.x = model.f;
      focalMarkers['2F′'].position.x = 2 * model.f;

      clearRays();
      (result.rays || []).forEach(function (ray) {
        if (ray.solid && ray.solid.length > 1) addRay(ray.solid, false);
        if (ray.dashed && ray.dashed.length > 1) addRay(ray.dashed, true);
      });

      var visible = result.kind !== 'none' && result.image && !result.image.offscene;
      imageGroup.visible = !!visible;
      if (visible) {
        imageGroup.position.x = result.image.x;
        syncArrowParts(imageParts, result.image.h, result.image.inverted);
        imageMat.color.setHex(result.kind === 'real' ? 0x16a34a : 0x9333ea);
        imageMat.wireframe = result.kind === 'virtual';
        imageMat.opacity = result.kind === 'real' ? 0.94 : 0.65;
        realImageLabel.visible = result.kind === 'real';
        virtualImageLabel.visible = result.kind === 'virtual';
        var tipOffset = result.image.inverted ? -(result.image.h + 1.6) : (result.image.h + 1.8);
        realImageLabel.position.set(0, tipOffset, 2.8);
        virtualImageLabel.position.set(0, tipOffset, 0);
      }
    }

    function writeSnapshots(result) {
      if (isolated) return;
      global.__OPTICS_MODEL__ = clone(model);
      global.__OPTICS_RESULT__ = clone(result);
      global.__OPTICS_VIEW__ = { yaw: view.yaw, pitch: view.pitch, dist: view.dist };
      if (cv.dataset) cv.dataset.opticsSig = global.OPTICS.signature(model);
    }

    function writeFormula(result) {
      /* 代入式写进 .exp-formula：审查端会按「a op b op c = d」复算，
         所以这里必须写实际代入的数字，而不是符号化的公式。 */
      var nodes = domRoot.querySelectorAll('[data-optics-formula]');
      if (!nodes.length) return;
      var text;
      if (result.kind === 'none') {
        text = 'u = f：1/u + 1/v = 1/f 无有限解，折射光平行射出，不成像。';
      } else {
        var denom = model.u - model.f;
        if (denom > 0) {
          text = 'v = u·f ÷ (u − f) = ' + model.u.toFixed(1) + ' × ' + model.f.toFixed(1)
            + ' ÷ ' + denom.toFixed(1) + ' = ' + result.v.toFixed(1) + ' cm；';
        } else {
          /* 虚像：分母为负。写成「−(u·f ÷ (f−u))」，让代入式括号内仍是三数正数运算，
             否则审查端的链式复算会把负号丢掉、算出 +10 却看到 −10。 */
          text = 'v = −u·f ÷ (f − u) = −(' + model.u.toFixed(1) + ' × ' + model.f.toFixed(1)
            + ' ÷ ' + (model.f - model.u).toFixed(1) + ') = ' + result.v.toFixed(1) + ' cm；';
        }
        text += 'm = −v ÷ u = ' + result.m.toFixed(2) + '×（' + result.kindText + '）';
      }
      nodes.forEach(function (node) { node.textContent = text; });
    }

    function paint() {
      lastResult = global.OPTICS.solve(model);
      syncMeshes(lastResult);
      var bound = global.OPTICS.bindReadouts(lastResult, domRoot);
      writeFormula(lastResult);
      applyView();
      renderer.render(scene, camera);
      writeSnapshots(lastResult);
      if (cv.dataset) cv.dataset.opticsBound = String(bound);
      domRoot.querySelectorAll('[data-optics-snap-screen]').forEach(function (btn) {
        btn.disabled = lastResult.kind !== 'real';
      });
      if (options.onPaint) options.onPaint(clone(model), clone(lastResult));
      return lastResult;
    }

    /* ---------- 尺寸 ---------- */
    function resize() {
      var rect = cv.getBoundingClientRect();
      var w = Math.max(320, Math.round(rect.width || cv.clientWidth || 960));
      var h = Math.max(260, Math.round(rect.height || cv.clientHeight || 460));
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.render(scene, camera);
    }
    if (global.ResizeObserver) new global.ResizeObserver(resize).observe(cv);

    /* ---------- 交互：轨道旋转 + 沿轴拖拽 ---------- */
    var raycaster = new THREE.Raycaster();
    var pointer = new THREE.Vector2();
    var mode = null;
    var dragKind = null;
    var lastX = 0, lastY = 0;

    function toPointer(event) {
      var rect = cv.getBoundingClientRect();
      pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    }

    function pickAxisTarget() {
      raycaster.setFromCamera(pointer, camera);
      var hits = raycaster.intersectObjects([objectGroup, screenGroup], true);
      if (!hits.length) return null;
      var node = hits[0].object;
      while (node && !node.userData.draggable) node = node.parent;
      return node ? node.userData.draggable : null;
    }

    function axisPosition() {
      raycaster.setFromCamera(pointer, camera);
      /* 拖拽在水平面 y=0 上求交；俯仰角下限 0.08 保证该平面不被视线平行切过 */
      var plane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
      var hit = new THREE.Vector3();
      if (!raycaster.ray.intersectPlane(plane, hit)) return null;
      return hit.x;
    }

    function onPointerDown(event) {
      toPointer(event);
      dragKind = pickAxisTarget();
      mode = dragKind ? 'axis' : 'orbit';
      lastX = event.clientX;
      lastY = event.clientY;
      if (cv.setPointerCapture) { try { cv.setPointerCapture(event.pointerId); } catch (e) {} }
    }

    function onPointerMove(event) {
      if (!mode) return;
      if (mode === 'orbit') {
        var dx = event.clientX - lastX;
        var dy = event.clientY - lastY;
        lastX = event.clientX; lastY = event.clientY;
        view.yaw -= dx * 0.006;
        view.pitch = clamp(view.pitch - dy * 0.005, PITCH_MIN, PITCH_MAX);
        applyView();
        renderer.render(scene, camera);
        if (!isolated) global.__OPTICS_VIEW__ = { yaw: view.yaw, pitch: view.pitch, dist: view.dist };
        return;
      }
      toPointer(event);
      var x = axisPosition();
      if (x == null) return;
      if (dragKind === 'object') {
        model.u = clamp(Math.round(-x / SNAP_CM) * SNAP_CM, 5, 120);
      } else if (dragKind === 'screen') {
        var s = clamp(Math.round(x / SNAP_CM) * SNAP_CM, 0, 150);
        model.screen = { s: s };
      }
      paint();
      syncControls();
    }

    function onPointerUp() { mode = null; dragKind = null; }

    cv.addEventListener('pointerdown', onPointerDown);
    cv.addEventListener('pointermove', onPointerMove);
    cv.addEventListener('pointerup', onPointerUp);
    cv.addEventListener('pointercancel', onPointerUp);
    cv.addEventListener('wheel', function (event) {
      event.preventDefault();
      view.dist = clamp(view.dist * Math.exp(event.deltaY * 0.001), 60, 900);
      applyView();
      renderer.render(scene, camera);
      if (!isolated) global.__OPTICS_VIEW__ = { yaw: view.yaw, pitch: view.pitch, dist: view.dist };
    }, { passive: false });

    /* ---------- 控件与记录：页面只放空壳，绑定在这里 ---------- */
    function syncControls() {
      domRoot.querySelectorAll('[data-optics-control]').forEach(function (input) {
        if (document.activeElement === input) return;
        var key = input.getAttribute('data-optics-control');
        if (key === 'f') input.value = model.f;
        if (key === 'u') input.value = model.u;
        if (key === 'h') input.value = model.h;
        if (key === 's' && model.screen) input.value = model.screen.s;
      });
    }

    domRoot.addEventListener('input', function (event) {
      var input = event.target;
      if (!input || !input.getAttribute) return;
      var key = input.getAttribute('data-optics-control');
      if (!key) return;
      var value = Number(input.value);
      if (!isFinite(value)) return;
      if (key === 'f') model.f = clamp(value, 5, 20);
      if (key === 'u') model.u = clamp(value, 5, 120);
      if (key === 'h') model.h = clamp(value, 0.5, 8);
      if (key === 's') model.screen = { s: clamp(value, 0, 150) };
      paint();
      syncControls();
    });

    domRoot.querySelectorAll('[data-optics-record-btn]').forEach(function (btn) {
      btn.addEventListener('click', function () { api.record(); });
    });
    domRoot.querySelectorAll('[data-optics-reset-view]').forEach(function (btn) {
      btn.addEventListener('click', function () { api.resetView(); });
    });

    var api = {
      paint: paint,
      setModel: function (next) { model = clone(next); paint(); syncControls(); return lastResult; },
      getModel: function () { return clone(model); },
      getView: function () { return { yaw: view.yaw, pitch: view.pitch, dist: view.dist }; },
      resetView: function () {
        view.yaw = defaultView.yaw;
        view.pitch = defaultView.pitch;
        view.dist = defaultDist();
        applyView();
        renderer.render(scene, camera);
        if (!isolated) global.__OPTICS_VIEW__ = { yaw: view.yaw, pitch: view.pitch, dist: view.dist };
      },
      record: function () {
        var body = domRoot.querySelector('[data-optics-record]');
        if (!body || !lastResult) return null;
        var r = lastResult;
        var row = document.createElement('tr');
        [
          model.f.toFixed(0), model.u.toFixed(0), model.screen ? model.screen.s.toFixed(0) : '—',
          r.v == null ? '—' : r.v.toFixed(1), r.m == null ? '—' : r.m.toFixed(2),
          r.kindText, r.onScreen.sharp ? '清晰' : '不清晰'
        ].forEach(function (text) {
          var cell = document.createElement('td');
          cell.textContent = text;
          row.appendChild(cell);
        });
        body.appendChild(row);
        return row;
      }
    };

    if (!options.isEditor && domRoot === document) {
      wireMainPageEnlarge(api, clone(initialModel));
    }

    resize();
    paint();
    syncControls();
    if (cv.dataset) cv.dataset.optics3d = 'ready';
    if (!isolated) global.__OPTICS_RENDER3D__ = 'ready';
    return api;
  }

  /* ---------- 放大自主调节工作台（独立页 + 弹窗被拦时自动页内全屏兜底） ---------- */
  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (k) {
        if (k === 'text') node.textContent = attrs[k];
        else if (k === 'className') node.className = attrs[k];
        else node.setAttribute(k, attrs[k]);
      });
    }
    if (children) {
      children.forEach(function (ch) {
        if (ch == null) return;
        node.appendChild(typeof ch === 'string' ? document.createTextNode(ch) : ch);
      });
    }
    return node;
  }

  function editorStyles() {
    return [
      'body{margin:0;color:#142531;background:#edf1f4;font:15px "PingFang SC","Microsoft YaHei",sans-serif}',
      '.oe-wrap{position:relative;display:flex;flex-direction:column;min-height:100vh;background:#edf1f4}',
      '.oe-overlay{position:fixed;inset:0;z-index:10000;overflow:auto}',
      '.oe-head{display:flex;gap:16px;align-items:center;justify-content:space-between;background:#fff;border-bottom:1px solid #d8e0e6;padding:14px 24px;flex-wrap:wrap}',
      '.oe-head h1{font-size:20px;margin:0;color:#142531}',
      '.oe-head p{margin:4px 0 0;color:#526574;font-size:13px}',
      '.oe-actions{display:flex;gap:9px;flex-wrap:wrap}',
      '.oe-btn{font:inherit;font-size:14px;cursor:pointer;padding:8px 14px;background:#fff;border:1px solid #bccbd6;border-radius:6px;color:#173b53}',
      '.oe-btn:hover{background:#f8fafc}',
      '.oe-btn:disabled{opacity:.45;cursor:not-allowed}',
      '.oe-btn.is-primary{background:#1a75b9;border-color:#1a75b9;color:#fff}',
      '.oe-btn.is-primary:hover{background:#1565a2}',
      '.oe-btn.is-sm{padding:6px 10px;font-size:13px}',
      '.oe-layout{display:grid;grid-template-columns:minmax(0,1fr) 360px;gap:16px;padding:16px;flex:1;min-height:0}',
      '.oe-bench{background:#fff;border:1px solid #d8e0e6;border-radius:10px;display:flex;flex-direction:column;overflow:hidden;min-height:520px}',
      '.oe-bench canvas{width:100%;height:calc(100vh - 155px);min-height:460px;display:block;flex:1}',
      '.oe-status{font-size:13px;line-height:1.6;color:#455c6b;padding:10px 16px;margin:0;border-top:1px solid #e6ecf1;background:#fafbfd}',
      '.oe-side{background:#fff;padding:16px 18px;border:1px solid #d8e0e6;border-radius:10px;display:flex;flex-direction:column;gap:14px;overflow:auto}',
      '.oe-side h2{font-size:16px;margin:0;color:#142531}',
      '.oe-presets{display:flex;flex-wrap:wrap;gap:6px}',
      '.oe-field{display:flex;flex-direction:column;gap:6px}',
      '.oe-field-top{display:flex;align-items:center;justify-content:space-between;gap:8px;font-size:14px}',
      '.oe-field-num{display:flex;align-items:center;gap:4px}',
      '.oe-num{width:74px;padding:4px 6px;border:1px solid #bccbd6;border-radius:4px;font:inherit;font-size:13px;text-align:right;font-variant-numeric:tabular-nums}',
      '.oe-range{width:100%;accent-color:#1973b8}',
      '.oe-reads{display:grid;grid-template-columns:1fr 1fr;gap:8px}',
      '.oe-read{background:#f5f8fb;border:1px solid #e1e8ef;border-radius:6px;padding:8px 10px}',
      '.oe-read-k{display:block;font-size:12px;color:#526574}',
      '.oe-read-v{display:block;font-size:15px;font-weight:700;color:#142531;font-variant-numeric:tabular-nums;margin-top:2px}',
      '.oe-formula{background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:8px 10px;font-size:13px;color:#1e293b;line-height:1.5}',
      '.oe-note{margin:0;font-size:13px;color:#1d4ed8;line-height:1.5}',
      '@media(max-width:900px){.oe-layout{grid-template-columns:1fr;padding:10px}.oe-bench canvas{height:380px;min-height:320px}}'
    ].join('\n');
  }

  function renderEditorInto(hostRoot, initialModel, onApply, onCancel, options) {
    options = options || {};
    var baseline = clone(initialModel);
    if (!document.getElementById('optics-editor-style')) {
      var style = el('style', { id: 'optics-editor-style', text: editorStyles() });
      document.head.appendChild(style);
    }

    var wrap = el('div', { className: options.overlay ? 'oe-wrap oe-overlay' : 'oe-wrap' });
    var btnCancel = el('button', { className: 'oe-btn', id: 'optics-editor-cancel', type: 'button', text: '取消并返回' });
    var btnApply = el('button', { className: 'oe-btn is-primary', id: 'optics-editor-apply', type: 'button', text: '应用并返回' });
    var header = el('header', { className: 'oe-head' }, [
      el('div', null, [
        el('h1', { text: '3D 光具座 · 放大自主调节' }),
        el('p', { text: '大画布支持自由旋转、缩放与沿导轨拖拽蜡烛/光屏；右侧可精确输入数值或切换五种成像情形，点击应用后回传原页面。' })
      ]),
      el('div', { className: 'oe-actions' }, [btnCancel, btnApply])
    ]);

    var canvas = el('canvas', { id: 'optics-editor-cv', 'aria-label': '放大版 3D 光具座自主调节画布', role: 'img' });
    var statusEl = el('p', { className: 'oe-status', id: 'optics-editor-status', 'aria-live': 'polite' });
    var bench = el('section', { className: 'oe-bench' }, [canvas, statusEl]);

    var presetSpecs = [
      ['u > 2f', function (m) { m.u = clamp(Math.round(m.f * 2.5), 5, 120); }],
      ['u = 2f', function (m) { m.u = clamp(m.f * 2, 5, 120); }],
      ['f < u < 2f', function (m) { m.u = clamp(Math.round(m.f * 1.5), 5, 120); }],
      ['u = f', function (m) { m.u = clamp(m.f, 5, 120); }],
      ['u < f', function (m) { m.u = clamp(Math.max(5, Math.round(m.f * 0.5)), 5, 120); }]
    ];
    var presetBtns = presetSpecs.map(function (item) {
      return el('button', { className: 'oe-btn is-sm', type: 'button', text: item[0] });
    });
    var snapScreenBtn = el('button', {
      className: 'oe-btn is-sm', type: 'button', 'data-optics-snap-screen': 'true', text: '光屏移至像距 (s=v)'
    });
    presetBtns.push(snapScreenBtn);

    var sliderSpecs = [
      ['f', '焦距 f', 5, 20, 0.5, 'cm'],
      ['u', '物距 u', 5, 120, 0.5, 'cm'],
      ['h', '物高 h', 0.5, 8, 0.5, 'cm'],
      ['s', '光屏位置 s', 0, 150, 0.5, 'cm']
    ];
    var fieldNodes = sliderSpecs.map(function (sp) {
      var key = sp[0], title = sp[1], lo = sp[2], hi = sp[3], step = sp[4], unit = sp[5];
      var numInput = el('input', {
        className: 'oe-num', type: 'number', min: String(lo), max: String(hi),
        step: String(step), 'data-optics-control': key, 'aria-label': title + '数值'
      });
      var rangeInput = el('input', {
        className: 'oe-range', type: 'range', min: String(lo), max: String(hi),
        step: String(step), 'data-optics-control': key, 'aria-label': title
      });
      return el('div', { className: 'oe-field' }, [
        el('div', { className: 'oe-field-top' }, [
          el('span', { text: title }),
          el('span', { className: 'oe-field-num' }, [numInput, el('span', { text: unit })])
        ]),
        rangeInput
      ]);
    });

    var readItems = [
      ['像距 v', 'v'],
      ['放大率 m', 'm'],
      ['成像性质', 'kind'],
      ['光屏清晰度', 'sharp']
    ].map(function (pair) {
      return el('div', { className: 'oe-read' }, [
        el('span', { className: 'oe-read-k', text: pair[0] }),
        el('b', { className: 'oe-read-v', 'data-optics-readout': pair[1], text: '—' })
      ]);
    });

    var formulaEl = el('div', { className: 'oe-formula', 'data-optics-formula': 'true' });
    var noteEl = el('p', { className: 'oe-note', 'data-optics-readout': 'uClass', 'aria-live': 'polite' });
    var btnViewReset = el('button', { className: 'oe-btn is-sm', type: 'button', 'data-optics-reset-view': 'true', text: '恢复默认视角' });
    var btnParamReset = el('button', { className: 'oe-btn is-sm', type: 'button', text: '恢复进入前参数' });

    var aside = el('aside', { className: 'oe-side' }, [
      el('h2', { text: '典型情形一键切换' }),
      el('div', { className: 'oe-presets' }, presetBtns),
      el('h2', { text: '参数精细调节' }),
      el('div', null, fieldNodes),
      el('h2', { text: '实时成像结果' }),
      el('div', { className: 'oe-reads' }, readItems),
      formulaEl,
      noteEl,
      el('div', { className: 'oe-actions' }, [btnViewReset, btnParamReset])
    ]);

    var main = el('main', { className: 'oe-layout' }, [bench, aside]);
    wrap.appendChild(header);
    wrap.appendChild(main);
    hostRoot.appendChild(wrap);

    var editorApi = mount(canvas, clone(baseline), {
      root: wrap,
      isolated: !!options.isolated,
      isEditor: true,
      onPaint: function (m, r) {
        global.__OPTICS_EDITOR_MODEL__ = m;
        statusEl.textContent = r.onScreen.reason + '（拖动空白处旋转，滚轮缩放，直接拖蜡烛或光屏沿轴移动）';
      }
    });

    presetSpecs.forEach(function (item, idx) {
      presetBtns[idx].addEventListener('click', function () {
        if (!editorApi) return;
        var next = editorApi.getModel();
        item[1](next);
        editorApi.setModel(next);
      });
    });
    snapScreenBtn.addEventListener('click', function () {
      if (!editorApi) return;
      var next = editorApi.getModel();
      var res = global.OPTICS.solve(next);
      if (res.kind === 'real' && res.v != null) {
        next.screen = { s: clamp(Number(res.v.toFixed(1)), 0, 150) };
        editorApi.setModel(next);
      }
    });
    btnParamReset.addEventListener('click', function () {
      if (editorApi) editorApi.setModel(clone(baseline));
    });
    btnCancel.addEventListener('click', function () {
      onCancel(wrap);
    });
    btnApply.addEventListener('click', function () {
      var next = editorApi ? editorApi.getModel() : clone(baseline);
      onApply(next, wrap, statusEl);
    });
    return { wrap: wrap, api: editorApi };
  }

  function editorDocument(model, token) {
    var ids = ['optics-vendor', 'optics-solver', 'optics3d'];
    var scripts = ids.map(function (id) {
      var source = document.getElementById(id);
      if (!source) throw new Error('缺少 3D 光学放大页运行资源：' + id);
      return '<scr' + 'ipt id="' + id + '">' + source.textContent.replace(/<\/script/gi, '<\\/script') + '</scr' + 'ipt>';
    }).join('\n');
    var data = JSON.stringify({ model: model, token: token }).replace(/</g, '\\u003c');
    return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
      + '<title>3D 光具座 · 放大自主调节</title><body><div id="optics-editor-root"></div>' + scripts
      + '<scr' + 'ipt>OPTICS3D.bootEditor(' + data + ');</scr' + 'ipt></body></html>';
  }

  function bootEditor(payload) {
    var root = document.getElementById('optics-editor-root');
    if (!root) return;
    renderEditorInto(root, payload.model, function (next, _wrap, statusEl) {
      if (!global.opener || global.opener.closed) {
        statusEl.textContent = '原页面已关闭，请保留原页面后再点击应用；当前页仍可继续调节演示。';
        return;
      }
      global.opener.postMessage({ type: 'optics-apply', token: payload.token, model: next }, '*');
      global.close();
    }, function () {
      global.close();
    }, { overlay: false, isolated: false });
  }

  function wireMainPageEnlarge(api, initialModel) {
    var stageHint = document.getElementById('pf-stage-hint');
    var enlargeBtns = Array.prototype.slice.call(document.querySelectorAll('[data-optics-enlarge]'));
    if (stageHint && enlargeBtns.length) {
      var primaryBtn = enlargeBtns[0];
      var parent = primaryBtn.parentElement;
      stageHint.replaceWith(primaryBtn);
      if (parent && parent.classList && parent.classList.contains('optics-stage-tools') && !parent.children.length) {
        parent.remove();
      }
    }

    var editors = new Map();
    var activeOverlay = null;
    var stageTip = document.querySelector('#sec-stage .exp-canvas-tip');
    var statusNote = document.querySelector('[data-optics-status]');
    var defaultStageTip = stageTip ? stageTip.textContent : '';
    var resetBtn = document.getElementById('btn-reset-params');
    function setStatus(msg) {
      if (stageTip) stageTip.textContent = msg || defaultStageTip;
      if (statusNote) {
        statusNote.textContent = msg || '';
        statusNote.hidden = !msg;
      }
    }
    if (resetBtn) {
      resetBtn.addEventListener('click', function () { setStatus(''); });
    }

    function openFallbackOverlay() {
      if (activeOverlay) return;
      var res = renderEditorInto(document.body, api.getModel(), function (next, wrap) {
        api.setModel(next);
        setStatus('已应用放大调节页中的参数设置');
        wrap.remove();
        activeOverlay = null;
      }, function (wrap) {
        wrap.remove();
        activeOverlay = null;
      }, { overlay: true, isolated: true });
      activeOverlay = res.wrap;
    }

    enlargeBtns.forEach(function (btn) {
      btn.addEventListener('click', function () {
        var current = api.getModel();
        current.view = api.getView();
        try {
          var token = global.crypto && global.crypto.randomUUID
            ? global.crypto.randomUUID()
            : Date.now() + '-' + Math.random();
          var html = editorDocument(current, token);
          var url = URL.createObjectURL(new Blob([html], { type: 'text/html;charset=utf-8' }));
          var win = global.open(url, '_blank');
          if (!win) {
            URL.revokeObjectURL(url);
            openFallbackOverlay();
            return;
          }
          setStatus('已打开独立放大调节页，调整后点击「应用并返回」即可同步参数');
          editors.set(win, { token: token, url: url });
          var cleanup = global.setInterval(function () {
            if (win.closed) {
              var entry = editors.get(win);
              if (entry) URL.revokeObjectURL(entry.url);
              editors.delete(win);
              global.clearInterval(cleanup);
            }
          }, 1500);
        } catch (_err) {
          openFallbackOverlay();
        }
      });
    });

    global.addEventListener('message', function (e) {
      var entry = editors.get(e.source);
      if (!entry || !e.data || e.data.type !== 'optics-apply' || e.data.token !== entry.token) return;
      try {
        global.OPTICS.solve(e.data.model);
        api.setModel(e.data.model);
        setStatus('已应用放大调节页中的参数设置');
      } catch (_err) { /* ignore invalid payload */ }
    });

    document.querySelectorAll('[data-optics-download]').forEach(function (a) {
      a.addEventListener('click', function (e) {
        e.preventDefault();
        var doc = document.documentElement.cloneNode(true);
        var rec = doc.querySelector('[data-optics-record]');
        if (rec) rec.replaceChildren();
        var entry = doc.querySelector('#optics-entry');
        if (entry) {
          var current = api.getModel();
          entry.textContent = entry.textContent.replace(
            /window\.__OPTICS_INITIAL__=[\s\S]*?;\s*\n/,
            'window.__OPTICS_INITIAL__=' + JSON.stringify(current).replace(/</g, '\\u003c') + ';\n'
          );
        }
        var blobUrl = URL.createObjectURL(new Blob(['<!doctype html>\n' + doc.outerHTML], { type: 'text/html;charset=utf-8' }));
        var link = document.createElement('a');
        link.href = blobUrl;
        link.download = (document.title || '凸透镜成像3D').replace(/[<>:"/\\|?*]/g, '_') + '.html';
        link.click();
        global.setTimeout(function () { URL.revokeObjectURL(blobUrl); }, 1000);
        var dlCheck = document.getElementById('pf-dl');
        if (dlCheck) dlCheck.checked = false;
      });
    });

    void initialModel;
  }

  global.OPTICS3D = { mount: mount, bootEditor: bootEditor, editorDocument: editorDocument };
  if (typeof window !== 'undefined') window.OPTICS3D = global.OPTICS3D;
}(typeof window !== 'undefined' ? window : globalThis));
