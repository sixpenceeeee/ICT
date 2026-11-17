/* Run: node --test sgrz/frame/circuit/apparatus.test.js */
'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

class SvgElement {
  constructor(name, document) { this.nodeName = name; this.ownerDocument = document; this.children = []; this.attributes = {}; this.listeners = {}; this.style = {}; }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  getAttribute(name) { return this.attributes[name] || null; }
  appendChild(child) { this.children.push(child); child.parentNode = this; return child; }
  replaceChildren(...children) { this.children = []; children.forEach(child => this.appendChild(child)); }
  addEventListener(name, listener) { (this.listeners[name] ||= []).push(listener); }
  setPointerCapture() {}
  releasePointerCapture() {}
  createSVGPoint() { return { x: 0, y: 0, matrixTransform() { return { x: this.x, y: this.y }; } }; }
  getScreenCTM() { return { inverse() { return {}; } }; }
  emit(name, event) { (this.listeners[name] || []).forEach(listener => listener(event)); }
}
function boot() {
  const document = { createElementNS(ns, name) { return new SvgElement(name, document); } };
  const context = { document, console };
  vm.createContext(context);
  const source = path.join(__dirname, 'apparatus.js');
  if (fs.existsSync(source)) vm.runInContext(fs.readFileSync(source, 'utf8'), context);
  return { view: context.CIRCUIT_VIEW, svg: new SvgElement('svg', document) };
}
function descendants(node, predicate) {
  return node.children.flatMap(child => [ ...(predicate(child) ? [child] : []), ...descendants(child, predicate) ]);
}
const fixture = () => ({
  schema_version: 1, recipe: 'resistance',
  components: [
    { id: 'V1', type: 'power_supply', x: 40, y: 440, params: { voltage: 6 } },
    { id: 'A1', type: 'ammeter', x: 110, y: 80, params: { range: 0.6 } },
    { id: 'M1', type: 'voltmeter', x: 690, y: 70, params: { range: 3 } },
    { id: 'R1', type: 'resistor', x: 680, y: 360, params: { resistance: 10 } },
    { id: 'RH1', type: 'rheostat', x: 380, y: 270, params: { maxResistance: 20, position: 0.25 } },
    { id: 'S1', type: 'switch', x: 430, y: 450, params: { closed: true } }
  ],
  wires: [ { id: 'W1', from: 'V1.positive', to: 'A1.positive' }, { id: 'W2', from: 'R1.a', to: 'RH1.slider' } ]
});

test('exports the renderer and reports physical ports translated with the housing', () => {
  const { view } = boot();
  assert.ok(view, 'CIRCUIT_VIEW is available');
  const config = fixture(), before = view.terminals(config);
  assert.ok(before['A1.positive']); assert.ok(before['A1.negative']);
  config.components.find(component => component.id === 'A1').x += 75;
  config.components.find(component => component.id === 'A1').y += 25;
  const after = view.terminals(config);
  assert.equal(after['A1.positive'].x - before['A1.positive'].x, 75);
  assert.equal(after['A1.negative'].y - before['A1.negative'].y, 25);
  assert.equal(after['V1.positive'].x, before['V1.positive'].x);
});

test('rheostat contact terminal follows the slider position', () => {
  const { view } = boot(); assert.ok(view, 'CIRCUIT_VIEW is available');
  const config = fixture(), before = view.terminals(config);
  config.components.find(component => component.id === 'RH1').params.position = 0.75;
  const after = view.terminals(config);
  assert.ok(after['RH1.slider'].x > before['RH1.slider'].x);
  assert.equal(after['RH1.a'].x, before['RH1.a'].x);
  assert.equal(after['RH1.b'].x, before['RH1.b'].x);
});

test('renders actual solver readings and wires end at their named terminals', () => {
  const { view, svg } = boot(); assert.ok(view, 'CIRCUIT_VIEW is available');
  const config = fixture();
  view.render(svg, config, { ok: true, components: { A1: { current: 0.23 }, M1: { voltage: 4.2, overrange: true } } });
  assert.equal(svg.getAttribute('viewBox'), '0 0 1000 650');
  assert.equal(svg.getAttribute('role'), 'img');
  assert.ok(descendants(svg, node => node.nodeName === 'text' && node.textContent === '0.23 A').length);
  assert.ok(descendants(svg, node => node.nodeName === 'text' && node.textContent === '4.2 V').length);
  assert.ok(descendants(svg, node => node.nodeName === 'text' && node.textContent === '超出量程').length);
  const ports = view.terminals(config);
  for (const wire of config.wires) {
    const wirePath = descendants(svg, node => node.getAttribute('data-wire-id') === wire.id && node.getAttribute('data-wire-layer') === 'sheath')[0];
    assert.ok(wirePath, wire.id);
    const coordinates = wirePath.getAttribute('d').match(/-?\d+(?:\.\d+)?/g).map(Number);
    assert.equal(coordinates[0], ports[wire.from].x); assert.equal(coordinates[1], ports[wire.from].y);
    assert.equal(coordinates.at(-2), ports[wire.to].x); assert.equal(coordinates.at(-1), ports[wire.to].y);
  }
});

test('pointer drag updates only the moved housing, redraws wires, and reports the same configuration', () => {
  const { view, svg } = boot(); assert.ok(view, 'CIRCUIT_VIEW is available');
  const config = fixture(); let moved;
  view.render(svg, config, { components: {} }, { editable: true, onMove(next) { moved = next; } });
  const housing = descendants(svg, node => node.getAttribute('data-component-id') === 'A1')[0];
  housing.emit('pointerdown', { button: 0, clientX: 120, clientY: 90, pointerId: 1, preventDefault() {}, stopPropagation() {} });
  svg.emit('pointermove', { clientX: 180, clientY: 130, pointerId: 1, preventDefault() {} });
  svg.emit('pointerup', { pointerId: 1 });
  assert.equal(config.components[1].x, 170); assert.equal(config.components[1].y, 120);
  assert.equal(config.components[0].x, 40); assert.equal(moved, config);
  const ports = view.terminals(config);
  const wire = descendants(svg, node => node.getAttribute('data-wire-id') === 'W1' && node.getAttribute('data-wire-layer') === 'sheath')[0];
  assert.ok(wire.getAttribute('d').endsWith(`${ports['A1.positive'].x} ${ports['A1.positive'].y}`));
});

test('failed solves hide stale readings and null values are not displayed as zero', () => {
  const { view, svg } = boot();
  const config = fixture();
  view.render(svg, config, { ok: false, components: { A1: { current: 0.23 }, M1: { voltage: 4.2 } } });
  assert.equal(descendants(svg, node => node.getAttribute('data-needle-id')).length, 0);
  const failed = descendants(svg, node => node.getAttribute('data-meter-id'));
  assert.ok(failed.every(node => node.getAttribute('data-value') === null));
  view.render(svg, config, { ok: true, components: { A1: { current: null }, M1: { voltage: null } } });
  assert.equal(descendants(svg, node => node.getAttribute('data-needle-id')).length, 0);
  assert.ok(descendants(svg, node => node.getAttribute('data-reading-id')).every(node => node.textContent === '—'));
});

test('keyboard movement is clamped to the bench and preserves connected wire endpoints', () => {
  const { view, svg } = boot();
  const config = fixture();
  config.components[1].x = 18;
  view.render(svg, config, { components: {} }, { editable: true });
  const housing = descendants(svg, node => node.getAttribute('data-component-id') === 'A1')[0];
  housing.emit('keydown', { key: 'ArrowLeft', shiftKey: true, preventDefault() {} });
  assert.equal(config.components[1].x, 18);
  assert.equal((svg.listeners.pointermove || []).length, 1, 'redrawing does not duplicate root listeners');
  const updated = descendants(svg, node => node.getAttribute('data-component-id') === 'A1')[0];
  updated.emit('keydown', { key: 'ArrowRight', shiftKey: true, preventDefault() {} });
  assert.equal(config.components[1].x, 28);
  const ports = view.terminals(config);
  const wire = descendants(svg, node => node.getAttribute('data-wire-id') === 'W1' && node.getAttribute('data-wire-layer') === 'sheath')[0];
  assert.ok(wire.getAttribute('d').endsWith(`${ports['A1.positive'].x} ${ports['A1.positive'].y}`));
});

test('floating point noise at full range does not contradict the solver range result', () => {
  const { view, svg } = boot();
  const config = fixture();
  view.render(svg, config, { ok: true, components: { A1: { current: 0.6000000000000001, overrange: false } } });
  assert.equal(descendants(svg, node => node.getAttribute('data-overrange') === 'true').length, 0);
  assert.equal(descendants(svg, node => node.nodeName === 'text' && node.textContent === '超出量程').length, 0);
  const needle = descendants(svg, node => node.getAttribute('data-needle-id') === 'A1')[0];
  assert.equal(needle.getAttribute('data-value'), '0.6000000000000001', 'the measured value is preserved');
  view.render(svg, config, { ok: true, components: { A1: { current: 0.6000000000000001 } } });
  assert.equal(descendants(svg, node => node.getAttribute('data-overrange') === 'true').length, 0, 'missing flags use solver-equivalent tolerance');
  view.render(svg, config, { ok: true, components: { A1: { current: 0.61 } } });
  assert.equal(descendants(svg, node => node.getAttribute('data-overrange') === 'true').length, 1, 'a genuine overrange still warns');
});

test('default power supply leaves bottom space and its title has a wire-blocking label plate', () => {
  const { view, svg } = boot();
  const config = fixture();
  delete config.components[0].x; delete config.components[0].y;
  view.render(svg, config, { ok: true, components: {} });
  const supply = descendants(svg, node => node.getAttribute('data-component-id') === 'V1')[0];
  assert.equal(supply.getAttribute('data-y'), '440');
  assert.ok(descendants(supply, node => node.getAttribute('data-label-plate') === 'V1').length);
  const title = descendants(supply, node => node.nodeName === 'text' && node.textContent === '直流电源 V1')[0];
  assert.ok(Number(supply.getAttribute('data-y')) + Number(title.getAttribute('y')) <= 610);
});

test('initial out-of-bounds positions use the drag bounds without changing config or electrical ports', () => {
  const { view, svg } = boot();
  const config = fixture();
  config.components[1].x = 1e9; config.components[1].y = 1e9;
  config.components[4].x = -1e9; config.components[4].y = -1e9;
  const original = JSON.stringify(config);
  view.render(svg, config, { ok: true, components: {} });
  const meter = descendants(svg, node => node.getAttribute('data-component-id') === 'A1')[0];
  assert.equal(meter.getAttribute('data-x'), '762');
  assert.equal(meter.getAttribute('data-y'), '396');
  const rheostat = descendants(svg, node => node.getAttribute('data-component-id') === 'RH1')[0];
  assert.equal(rheostat.getAttribute('data-x'), '18');
  assert.equal(rheostat.getAttribute('data-y'), '32');
  assert.equal(JSON.stringify(config), original, 'rendering does not rewrite the input configuration');
  const ports = view.terminals(config);
  assert.equal(ports['A1.positive'].x, 762 + 172);
  assert.equal(ports['A1.positive'].y, 396 + 174);
  assert.equal(ports['RH1.a'].x, 18 + 23);
  assert.equal(ports['RH1.a'].y, 32 + 99);
  for (const wire of config.wires) {
    const rendered = descendants(svg, node => node.getAttribute('data-wire-id') === wire.id && node.getAttribute('data-wire-layer') === 'sheath')[0];
    const numbers = rendered.getAttribute('d').match(/-?\d+(?:\.\d+)?/g).map(Number);
    assert.equal(numbers[0], ports[wire.from].x); assert.equal(numbers[1], ports[wire.from].y);
    assert.equal(numbers.at(-2), ports[wire.to].x); assert.equal(numbers.at(-1), ports[wire.to].y);
  }
});
