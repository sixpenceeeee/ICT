/*
 * Reusable, dependency-free SVG bench apparatus for the sgrz teaching pages.
 * CIRCUIT_VIEW.render(svg, config, solution, { editable, selectedId, onMove, onSelect })
 * Config x/y are the top-left of each instrument; electrical values come only
 * from solution.components. No circuit solving or parameter editing occurs here.
 *
 * PhET adaptations (MIT, exact license in LICENSE-PHET.txt):
 * - BatteryNode.ts, Copyright 2024-2026 University of Colorado Boulder:
 *   the small cell on the DC supply retains the 40% copper cap / 30% terminal
 *   proportions and the original three-stop vertical metal/copper gradients.
 * - WireNode.ts, Copyright 2018-2025 University of Colorado Boulder:
 *   endpoint + outward-normal cubic geometry, translated to native SVG paths.
 * Source: source/upstream/phet/libs/scenery-phet/js/{BatteryNode,WireNode}.ts.
 * The analog bench instruments, resistor, rheostat and knife switch are original
 * project SVG drawings, not copied PhET screenshots or bundled simulation code.
 */
(function (global) {
  'use strict';
  var NS = 'http://www.w3.org/2000/svg';
  var WIDTH = 1000, HEIGHT = 650, serial = 0;
  var states = new WeakMap();
  var NAMES = { power_supply: '直流电源', ammeter: '电流表', voltmeter: '电压表', resistor: '定值电阻', rheostat: '滑动变阻器', switch: '开关' };
  var SIZES = { power_supply: [224, 142], ammeter: [220, 196], voltmeter: [220, 196], resistor: [190, 94], rheostat: [245, 120], switch: [165, 100] };
  var PALETTE = { ink: '#31352f', soft: '#72776f', red: '#b8493c', black: '#333b3c', brass: '#ad844b', border: '#8e9286' };

  function finite(value) { return typeof value === 'number' && Number.isFinite(value); }
  function clamp(value, min, max) { return Math.max(min, Math.min(max, value)); }
  function format(value) {
    if (!finite(value)) return '—';
    if (value === 0) return '0';
    return Number(value.toFixed(Math.abs(value) < 0.01 ? 4 : Math.abs(value) < 1 ? 3 : 2)).toString();
  }
  function el(parent, name, attributes, text) {
    var node = parent.ownerDocument.createElementNS(NS, name);
    Object.keys(attributes || {}).forEach(function (key) { node.setAttribute(key, attributes[key]); });
    if (text !== undefined) node.textContent = text;
    parent.appendChild(node);
    return node;
  }
  function rect(parent, x, y, width, height, fill, radius, extra) {
    return el(parent, 'rect', Object.assign({ x: x, y: y, width: width, height: height, rx: radius || 0, fill: fill }, extra || {}));
  }
  function line(parent, x1, y1, x2, y2, stroke, width, extra) {
    return el(parent, 'line', Object.assign({ x1: x1, y1: y1, x2: x2, y2: y2, stroke: stroke, 'stroke-width': width || 1, 'stroke-linecap': 'round' }, extra || {}));
  }
  function text(parent, x, y, content, size, extra) {
    return el(parent, 'text', Object.assign({ x: x, y: y, fill: PALETTE.ink, 'font-size': size || 18, 'text-anchor': 'middle', 'font-family': 'Arial, Microsoft YaHei, sans-serif' }, extra || {}), content);
  }
  function circle(parent, cx, cy, r, fill, extra) { return el(parent, 'circle', Object.assign({ cx: cx, cy: cy, r: r, fill: fill }, extra || {})); }
  function path(parent, d, fill, stroke, width, extra) {
    return el(parent, 'path', Object.assign({ d: d, fill: fill || 'none', stroke: stroke || 'none', 'stroke-width': width || 1, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, extra || {}));
  }
  function screw(parent, x, y) {
    circle(parent, x, y, 3.6, '#a8ac9e', { stroke: '#747c70', 'stroke-width': 1 });
    line(parent, x - 1.8, y + 1.8, x + 1.8, y - 1.8, '#677064', 1);
  }
  function terminal(parent, x, y, kind, label, prefix) {
    circle(parent, x, y + 2, 14.5, '#4b5149');
    circle(parent, x, y, 12, 'url(#' + prefix + '-terminal)', { stroke: '#555c54', 'stroke-width': 1.5 });
    circle(parent, x, y, 8.5, kind === 'red' ? PALETTE.red : PALETTE.black, { stroke: kind === 'red' ? '#90352d' : '#202729', 'stroke-width': 1.4 });
    circle(parent, x - 1, y - 1.5, 3.6, '#deded0', { stroke: '#777d71', 'stroke-width': 1 });
    circle(parent, x, y, 1.4, '#4d524a');
    if (label) text(parent, x, y - 19, label, 16, { fill: kind === 'red' ? '#a33d31' : '#495149', 'font-weight': 600 });
  }

  function dimensions(type) { var size = SIZES[type] || [170, 100]; return { width: size[0], height: size[1] }; }
  function boundedPosition(type, x, y) {
    var size = dimensions(type);
    return {
      x: clamp(x, 18, WIDTH - size.width - 18),
      y: clamp(y, type === 'rheostat' ? 32 : 18, HEIGHT - size.height - 58)
    };
  }
  function defaultPosition(component, config, index) {
    var recipe = config.recipe || 'ohm';
    var defaults = { V1: [75, 440], A1: [75, 92], M1: [700, 75], S1: [430, 460], R1: [700, 350], RH1: [370, 285], R2: [690, 485] };
    if (recipe === 'series') { defaults.R1 = [415, 315]; defaults.R2 = [715, 360]; }
    if (recipe === 'parallel') { defaults.R1 = [590, 340]; defaults.R2 = [590, 490]; defaults.S1 = [350, 475]; }
    var fallback = { power_supply: defaults.V1, ammeter: defaults.A1, voltmeter: defaults.M1, resistor: index % 2 ? defaults.R1 : defaults.R2, rheostat: defaults.RH1, switch: defaults.S1 };
    return defaults[component.id] || fallback[component.type] || [60 + index % 3 * 290, 90 + Math.floor(index / 3) * 240];
  }
  function layout(config) {
    return (config.components || []).map(function (component, index) {
      var fallback = defaultPosition(component, config, index);
      var position = boundedPosition(component.type, finite(component.x) ? component.x : fallback[0], finite(component.y) ? component.y : fallback[1]);
      // Clamp only the drawing position; caller-owned config and port names stay
      // intact. Terminals and wires use this same layout on every render.
      return { component: component, x: position.x, y: position.y };
    });
  }
  function localPorts(component) {
    switch (component.type) {
      case 'power_supply': return { positive: [50, 119, -0.25, 1], negative: [174, 119, 0.25, 1] };
      case 'ammeter': case 'voltmeter': return { negative: [48, 174, -0.4, 1], positive: [172, 174, 0.4, 1] };
      case 'resistor': return { a: [20, 62, -1, 0.25], b: [170, 62, 1, 0.25] };
      case 'rheostat': {
        var position = component.params && finite(component.params.position) ? clamp(component.params.position, 0, 1) : 0.5;
        return { a: [23, 99, -0.6, 1], b: [222, 99, 0.6, 1], slider: [38 + 170 * position, 19, 0, -1] };
      }
      case 'switch': return { a: [22, 70, -0.7, 1], b: [143, 70, 0.7, 1] };
      default: return {};
    }
  }
  function terminalDetails(config) {
    var result = {};
    layout(config).forEach(function (placed) {
      var ports = localPorts(placed.component);
      Object.keys(ports).forEach(function (port) {
        var point = ports[port];
        result[placed.component.id + '.' + port] = { x: placed.x + point[0], y: placed.y + point[1], nx: point[2], ny: point[3] };
      });
    });
    return result;
  }
  function terminals(config) {
    var detail = terminalDetails(config), result = {};
    Object.keys(detail).forEach(function (id) { result[id] = { x: detail[id].x, y: detail[id].y }; });
    return result;
  }

  function definitions(svg, prefix) {
    var defs = el(svg, 'defs');
    var gradients = {
      terminal: [[0.05, 'rgb(150,150,150)'], [0.3, 'rgb(244,244,244)'], [0.7, 'rgb(170,170,170)']],
      cell: [[0.05, 'rgb(102,102,102)'], [0.3, 'rgb(173,173,173)'], [0.7, 'rgb(40,40,40)']],
      copper: [[0.05, 'rgb(182,103,48)'], [0.3, 'rgb(222,218,215)'], [0.7, 'rgb(200,99,38)']],
      casing: [[0, '#eeeede'], [0.48, '#dedfd0'], [1, '#c9cebe']],
      glass: [[0, '#fffef3'], [0.6, '#fbfaf1'], [1, '#e9eadd']],
      coil: [[0, '#b89c74'], [0.32, '#e8d7ad'], [0.6, '#b59667'], [1, '#836e53']]
    };
    Object.keys(gradients).forEach(function (name) {
      var gradient = el(defs, 'linearGradient', { id: prefix + '-' + name, x1: '0%', y1: '0%', x2: '0%', y2: '100%' });
      gradients[name].forEach(function (stop) { el(gradient, 'stop', { offset: stop[0], 'stop-color': stop[1] }); });
    });
    return defs;
  }
  function shadow(parent, x, y, width) { el(parent, 'ellipse', { cx: x, cy: y, rx: width, ry: 9, fill: '#686d56', opacity: 0.12 }); }
  function label(parent, width, y, title, detail) {
    text(parent, width / 2, y, title, 20, { 'font-weight': 600 });
    if (detail) text(parent, width / 2, y + 22, detail, 17, { fill: '#6f776b' });
  }

  function meter(parent, component, solved, prefix, valid) {
    var ammeter = component.type === 'ammeter', unit = ammeter ? 'A' : 'V';
    var params = component.params || {};
    var range = finite(params.range) && params.range > 0 ? params.range : ammeter ? 0.6 : 3;
    var value = valid && solved && finite(ammeter ? solved.current : solved.voltage) ? (ammeter ? solved.current : solved.voltage) : null;
    // The solver owns range status. For standalone readings without that flag,
    // use the same eight-ULP tolerance as core.js rather than a strict > test.
    var overrange = finite(value) && (typeof solved.overrange === 'boolean' ? solved.overrange :
      Math.abs(value) - range > Number.EPSILON * Math.max(1, range) * 8);
    parent.setAttribute('data-meter-id', component.id);
    parent.setAttribute('data-value', finite(value) ? value : '');
    parent.setAttribute('data-range', range);
    shadow(parent, 111, 200, 111);
    rect(parent, 0, 6, 220, 190, '#a9b29f', 16, { stroke: '#7e8977', 'stroke-width': 1.5 });
    rect(parent, 0, 0, 220, 190, 'url(#' + prefix + '-casing)', 15, { stroke: '#808b77', 'stroke-width': 2 });
    rect(parent, 13, 14, 194, 123, '#75806e', 12);
    rect(parent, 17, 18, 186, 115, 'url(#' + prefix + '-glass)', 9, { stroke: '#747c69', 'stroke-width': 1 });
    path(parent, 'M 28 48 Q 110 6 192 48', 'none', '#fff', 6, { opacity: 0.48 });
    var cx = 110, cy = 121, radius = 80;
    for (var tick = 0; tick <= 30; tick++) {
      var angle = (-155 + tick / 30 * 130) * Math.PI / 180;
      var major = tick % 5 === 0, inner = radius - (major ? 13 : 6);
      line(parent, cx + Math.cos(angle) * inner, cy + Math.sin(angle) * inner, cx + Math.cos(angle) * radius, cy + Math.sin(angle) * radius, '#464d42', major ? 1.8 : 0.9);
      if (major) text(parent, cx + Math.cos(angle) * 94, cy + Math.sin(angle) * 94 + 5, format(range * tick / 30), 12, { fill: '#464d42' });
    }
    text(parent, 110, 83, unit, 29, { 'font-family': 'Georgia, serif', 'font-weight': 700 });
    text(parent, 110, 104, '直流', 10, { fill: '#74796b', 'letter-spacing': 2 });
    if (finite(value)) {
      var needleAngle = (-155 + clamp(value / range, -0.045, 1.045) * 130) * Math.PI / 180;
      line(parent, cx, cy, cx + Math.cos(needleAngle) * 77, cy + Math.sin(needleAngle) * 77, overrange ? '#c0392b' : '#b14b3e', 2, { 'data-needle-id': component.id, 'data-value': value });
    }
    circle(parent, cx, cy, 5.5, '#555e50', { stroke: '#293528', 'stroke-width': 1 });
    circle(parent, cx - 1, cy - 1, 1.8, '#a7ad9b');
    text(parent, 110, 154, finite(value) ? format(value) + ' ' + unit : '—', 19, { 'font-family': 'Consolas, monospace', 'font-weight': 600, fill: overrange ? '#ad392e' : '#3d4938', 'data-reading-id': component.id });
    terminal(parent, 48, 174, 'black', '−', prefix);
    terminal(parent, 172, 174, 'red', format(range) + ' ' + unit, prefix);
    screw(parent, 9, 10); screw(parent, 211, 10);
    label(parent, 220, 225, NAMES[component.type] + ' ' + component.id, overrange ? '超出量程' : '量程 0–' + format(range) + ' ' + unit);
    if (overrange) parent.setAttribute('data-overrange', 'true');
  }

  function powerSupply(parent, component, solved, prefix, valid) {
    var value = valid && solved && finite(solved.voltage) ? solved.voltage : null;
    shadow(parent, 112, 146, 115);
    rect(parent, 0, 7, 224, 135, '#697363', 10);
    rect(parent, 0, 0, 224, 134, '#aeb9a1', 10, { stroke: '#6e7d64', 'stroke-width': 2 });
    rect(parent, 7, 7, 210, 120, '#e3e6d7', 7, { stroke: '#9ca58e' });
    text(parent, 112, 25, '直 流 稳 压 电 源', 16, { 'font-weight': 700, fill: '#59664e' });
    // BatteryNode's end-cap and terminal geometry, rendered directly in SVG.
    rect(parent, 19, 46, 42, 24, 'url(#' + prefix + '-cell)', 0, { stroke: '#5f6259' });
    rect(parent, 44.2, 46, 16.8, 24, 'url(#' + prefix + '-copper)', 0, { stroke: '#6f675b' });
    rect(parent, 60, 54.4, 4, 7.2, 'url(#' + prefix + '-terminal)', 0, { stroke: '#666d61' });
    text(parent, 40, 89, 'DC', 13, { fill: '#637259', 'font-weight': 700 });
    rect(parent, 80, 36, 125, 42, '#404f3a', 4);
    rect(parent, 84, 40, 117, 34, '#d1dec1', 2);
    text(parent, 145, 64, finite(value) ? format(value) + ' V' : '—', 22, { 'font-family': 'Consolas, monospace', 'data-reading-id': component.id, fill: '#34472e' });
    circle(parent, 112, 101, 13, '#6c7960', { stroke: '#4e6044', 'stroke-width': 2 });
    circle(parent, 112, 101, 9, '#7f8d70'); line(parent, 112, 101, 118, 95, '#e8ecdc', 2);
    text(parent, 112, 123, '输出', 10, { fill: '#596a4b' });
    terminal(parent, 50, 119, 'red', '+', prefix); terminal(parent, 174, 119, 'black', '−', prefix);
    screw(parent, 15, 17); screw(parent, 208, 17);
    // Outgoing cables may loop behind the supply; an opaque label plate keeps
    // the title legible without changing the connection geometry.
    rect(parent, 34, 148, 156, 28, '#f5f2e9', 5, { 'data-label-plate': component.id });
    label(parent, 224, 169, '直流电源 ' + component.id);
  }

  function resistor(parent, component, solved, prefix, valid) {
    var params = component.params || {}, resistance = params.resistance;
    shadow(parent, 95, 96, 97);
    rect(parent, 7, 49, 176, 38, '#8c7760', 7, { stroke: '#6f6250', 'stroke-width': 2 });
    rect(parent, 8, 46, 174, 31, '#d4c5a8', 6, { stroke: '#97866a' });
    rect(parent, 31, 39, 14, 27, 'url(#' + prefix + '-terminal)', 2, { stroke: '#797b6e' });
    rect(parent, 145, 39, 14, 27, 'url(#' + prefix + '-terminal)', 2, { stroke: '#797b6e' });
    line(parent, 20, 62, 48, 52, '#777e70', 5); line(parent, 142, 52, 170, 62, '#777e70', 5);
    rect(parent, 43, 24, 104, 40, '#e7e4d0', 5, { stroke: '#a4a489', 'stroke-width': 1.5 });
    for (var rib = 0; rib < 9; rib++) line(parent, 52 + rib * 10, 28, 52 + rib * 10, 61, '#c6c9ae', 2);
    rect(parent, 64, 29, 63, 27, '#eae8d5', 2);
    text(parent, 95, 49, format(resistance) + ' Ω', 18, { 'font-weight': 600 });
    terminal(parent, 20, 62, 'black', '', prefix); terminal(parent, 170, 62, 'red', '', prefix);
    var detail = valid && solved && finite(solved.voltage) ? 'U = ' + format(solved.voltage) + ' V' : '';
    label(parent, 190, 116, '定值电阻 ' + component.id, detail);
  }

  function rheostat(parent, component, solved, prefix) {
    var params = component.params || {}, position = finite(params.position) ? clamp(params.position, 0, 1) : 0.5;
    var slider = 38 + 170 * position;
    shadow(parent, 122, 121, 124);
    rect(parent, 5, 84, 235, 29, '#89755d', 6, { stroke: '#70604d', 'stroke-width': 2 });
    rect(parent, 5, 80, 235, 27, '#d2b98e', 6, { stroke: '#9c835f' });
    rect(parent, 25, 37, 17, 51, '#9caa92', 2, { stroke: '#75836c' });
    rect(parent, 207, 37, 17, 51, '#9caa92', 2, { stroke: '#75836c' });
    rect(parent, 38, 42, 170, 30, 'url(#' + prefix + '-coil)', 7, { stroke: '#927655', 'stroke-width': 1.2 });
    for (var turn = 0; turn <= 33; turn++) line(parent, 41 + turn * 4.9, 44, 41 + turn * 4.9, 70, '#8a775a', 1.4);
    line(parent, 30, 29, 216, 29, '#727d68', 7); line(parent, 30, 27, 216, 27, '#d9ded0', 2);
    rect(parent, slider - 11, 21, 22, 20, '#6f7866', 3, { stroke: '#4c5c43' });
    path(parent, 'M ' + (slider - 3) + ' 38 L ' + (slider - 3) + ' 52 L ' + slider + ' 58 L ' + (slider + 3) + ' 52 L ' + (slider + 3) + ' 38 Z', '#a8ac9b', '#6a7861', 1.3);
    terminal(parent, 23, 99, 'black', 'a', prefix); terminal(parent, 222, 99, 'red', 'b', prefix);
    terminal(parent, slider, 19, 'red', '', prefix);
    text(parent, 122, 101, '0–' + format(params.maxResistance) + ' Ω', 15, { fill: '#63543e', 'font-weight': 600 });
    label(parent, 245, 145, '滑动变阻器 ' + component.id, '滑片位置 ' + Math.round(position * 100) + '%');
  }

  function knifeSwitch(parent, component, solved, prefix) {
    var closed = !!(component.params && component.params.closed);
    shadow(parent, 83, 103, 83);
    rect(parent, 0, 39, 165, 55, '#6d5947', 9, { stroke: '#574737', 'stroke-width': 1.5 });
    rect(parent, 0, 34, 165, 51, '#a88d67', 8, { stroke: '#786043', 'stroke-width': 1.5 });
    screw(parent, 9, 43); screw(parent, 156, 76);
    rect(parent, 17, 48, 18, 29, '#bca46f', 3, { stroke: '#87723f' });
    rect(parent, 129, 48, 19, 29, '#bca46f', 3, { stroke: '#87723f' });
    line(parent, 132, 46, 132, 63, '#927536', 4); line(parent, 145, 46, 145, 63, '#927536', 4);
    var endX = closed ? 140 : 104, endY = closed ? 53 : 4;
    line(parent, 27, 55, endX, endY, '#605e4c', 9);
    line(parent, 27, 53, endX, endY - 2, '#d0c195', 5);
    var handleX = closed ? 94 : 80, handleY = closed ? 52 : 15;
    rect(parent, handleX - 17, handleY - 9, 35, 16, '#9b3e30', 4, { stroke: '#763426', 'stroke-width': 1.5, transform: closed ? '' : 'rotate(-31 ' + handleX + ' ' + handleY + ')' });
    circle(parent, 27, 54, 5, '#6e6e58');
    terminal(parent, 22, 70, 'black', '', prefix); terminal(parent, 143, 70, 'red', '', prefix);
    label(parent, 165, 123, '开关 ' + component.id, closed ? '已闭合' : '已断开');
    parent.setAttribute('data-closed', closed ? 'true' : 'false');
  }

  function wireCurve(from, to, index) {
    // Native-SVG adaptation of WireNode's endpoint-plus-normal cubic curve.
    var distance = Math.hypot(to.x - from.x, to.y - from.y);
    var bend = clamp(distance * 0.28, 36, 100) + index % 3 * 4;
    return 'M ' + from.x + ' ' + from.y + ' C ' + (from.x + from.nx * bend) + ' ' + (from.y + from.ny * bend) + ' ' + (to.x + to.nx * bend) + ' ' + (to.y + to.ny * bend) + ' ' + to.x + ' ' + to.y;
  }
  function drawWires(parent, config) {
    var ports = terminalDetails(config);
    (config.wires || []).forEach(function (wire, index) {
      var from = ports[wire.from], to = ports[wire.to];
      if (!from || !to) return;
      var d = wireCurve(from, to, index);
      var red = /\.positive$/.test(wire.from) || /\.positive$/.test(wire.to);
      var black = /\.negative$/.test(wire.from) || /\.negative$/.test(wire.to);
      var color = red ? '#ae5142' : black ? '#424c48' : index % 2 ? '#58746b' : '#a47e4c';
      path(parent, d, 'none', '#4c493e', 8, { opacity: 0.15, transform: 'translate(0 3)' });
      path(parent, d, 'none', '#364039', 7, { 'data-wire-id': wire.id || 'wire-' + index, 'data-from': wire.from, 'data-to': wire.to, 'data-wire-layer': 'outline' });
      path(parent, d, 'none', color, 4.8, { 'data-wire-id': wire.id || 'wire-' + index, 'data-from': wire.from, 'data-to': wire.to, 'data-wire-layer': 'sheath' });
      path(parent, d, 'none', '#fff', 1, { opacity: 0.21, transform: 'translate(0 -0.8)', 'pointer-events': 'none' });
    });
  }

  function point(svg, event) {
    var matrix = svg.getScreenCTM && svg.getScreenCTM();
    if (matrix && svg.createSVGPoint) {
      var p = svg.createSVGPoint(); p.x = event.clientX; p.y = event.clientY;
      return p.matrixTransform(matrix.inverse());
    }
    var bounds = svg.getBoundingClientRect();
    return { x: (event.clientX - bounds.left) * WIDTH / bounds.width, y: (event.clientY - bounds.top) * HEIGHT / bounds.height };
  }
  function move(svg, state, id, x, y) {
    var component = (state.config.components || []).find(function (candidate) { return candidate.id === id; });
    if (!component) return;
    var position = boundedPosition(component.type, x, y);
    component.x = Math.round(position.x);
    component.y = Math.round(position.y);
    var config = state.config, options = state.options;
    render(svg, config, state.solution, options);
    if (typeof options.onMove === 'function') options.onMove(config);
  }
  function listeners(svg, state) {
    svg.addEventListener('pointermove', function (event) {
      if (!state.drag || !state.options.editable || state.drag.pointerId !== event.pointerId) return;
      var p = point(svg, event);
      event.preventDefault();
      move(svg, state, state.drag.id, p.x - state.drag.offsetX, p.y - state.drag.offsetY);
    });
    function finish(event) {
      if (!state.drag || state.drag.pointerId !== event.pointerId) return;
      state.drag = null;
      if (svg.releasePointerCapture) { try { svg.releasePointerCapture(event.pointerId); } catch (_) { /* A browser may already release capture on cancellation. */ } }
    }
    svg.addEventListener('pointerup', finish); svg.addEventListener('pointercancel', finish);
  }
  function editableGroup(svg, group, placed, state) {
    group.setAttribute('tabindex', '0');
    group.setAttribute('role', 'group');
    group.setAttribute('aria-label', (NAMES[placed.component.type] || placed.component.type) + ' ' + placed.component.id + '，可拖动，方向键移动，Shift 加速');
    group.setAttribute('aria-roledescription', '可移动实验器材');
    group.style.cursor = 'grab';
    group.addEventListener('pointerdown', function (event) {
      if (event.button !== undefined && event.button !== 0) return;
      event.preventDefault(); event.stopPropagation();
      var p = point(svg, event);
      state.drag = { id: placed.component.id, pointerId: event.pointerId, offsetX: p.x - placed.x, offsetY: p.y - placed.y };
      if (svg.setPointerCapture) svg.setPointerCapture(event.pointerId);
      if (typeof state.options.onSelect === 'function') state.options.onSelect(placed.component.id, state.config);
    });
    group.addEventListener('keydown', function (event) {
      var direction = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[event.key];
      if (!direction) return;
      event.preventDefault();
      var step = event.shiftKey ? 10 : 2;
      move(svg, state, placed.component.id, placed.x + direction[0] * step, placed.y + direction[1] * step);
      // Re-render replaces the focused group; preserve keyboard focus by id.
      if (svg.querySelectorAll) {
        Array.prototype.forEach.call(svg.querySelectorAll('[data-component-id]'), function (node) {
          if (node.getAttribute('data-component-id') === placed.component.id && node.focus) node.focus();
        });
      }
    });
    group.addEventListener('focus', function () {
      if (typeof state.options.onSelect === 'function') state.options.onSelect(placed.component.id, state.config);
    });
  }

  function render(svg, config, solution, options) {
    if (!svg || !config) throw new TypeError('CIRCUIT_VIEW.render requires an SVG element and a configuration');
    options = options || {}; solution = solution || {};
    var state = states.get(svg);
    if (!state) { state = { prefix: 'circuit-apparatus-' + (++serial) }; states.set(svg, state); listeners(svg, state); }
    state.config = config; state.solution = solution; state.options = options;
    if (!options.editable) state.drag = null;
    svg.replaceChildren();
    svg.setAttribute('viewBox', '0 0 ' + WIDTH + ' ' + HEIGHT);
    svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
    svg.setAttribute('role', options.editable ? 'group' : 'img');
    svg.setAttribute('aria-label', options.editable ? '实物电路编辑区，可选择并拖动仪器' : '实物电路实验装置，包含电源、指针式仪表、电阻与开关');
    svg.style.touchAction = options.editable ? 'none' : 'auto';
    el(svg, 'title', {}, options.editable ? '实物电路编辑' : '实物电路实验');
    el(svg, 'desc', {}, '彩色导线连接真实接线柱；红色为正接线柱，黑色为负接线柱。仪表读数来自电路求解结果。');
    definitions(svg, state.prefix);
    rect(svg, 8, 8, WIDTH - 16, HEIGHT - 16, '#f5f2e9', 18, { stroke: '#e1dfd2', 'stroke-width': 1.5 });
    [150, 310, 470, 610].forEach(function (y) { line(svg, 23, y, 977, y, '#d6d2c2', 0.6, { opacity: 0.15 }); });
    var wires = el(svg, 'g', { 'data-layer': 'wires', 'pointer-events': 'none' }); drawWires(wires, config);
    var apparatus = el(svg, 'g', { 'data-layer': 'apparatus' });
    layout(config).forEach(function (placed) {
      var component = placed.component, solved = solution.components && solution.components[component.id];
      var group = el(apparatus, 'g', { transform: 'translate(' + placed.x + ' ' + placed.y + ')', 'data-component-id': component.id, 'data-component-type': component.type, 'data-x': placed.x, 'data-y': placed.y });
      if (options.selectedId === component.id) {
        var size = dimensions(component.type);
        rect(group, -9, -10, size.width + 18, size.height + 18, 'none', 19, { stroke: '#6c8c68', 'stroke-width': 2.5, 'stroke-dasharray': '6 5', 'pointer-events': 'none' });
      }
      var valid = solution.ok !== false && solution.status !== 'error';
      if (component.type === 'ammeter' || component.type === 'voltmeter') meter(group, component, solved, state.prefix, valid);
      else if (component.type === 'power_supply') powerSupply(group, component, solved, state.prefix, valid);
      else if (component.type === 'resistor') resistor(group, component, solved, state.prefix, valid);
      else if (component.type === 'rheostat') rheostat(group, component, solved, state.prefix);
      else if (component.type === 'switch') knifeSwitch(group, component, solved, state.prefix);
      if (options.editable) editableGroup(svg, group, placed, state);
    });
    return svg;
  }

  global.CIRCUIT_VIEW = { render: render, terminals: terminals, dimensions: dimensions, width: WIDTH, height: HEIGHT };
})(typeof window !== 'undefined' ? window : globalThis);
