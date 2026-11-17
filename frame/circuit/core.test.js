'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
// A missing implementation is a feature assertion, so the first red run is explicit.
let CIRCUIT;
try { CIRCUIT = require('./core.js'); } catch (error) {
  if (error.code !== 'MODULE_NOT_FOUND') throw error;
  CIRCUIT = {};
}
const near = (actual, expected, epsilon = 1e-9) => {
  assert.equal(typeof actual, 'number');
  assert.ok(Math.abs(actual - expected) <= epsilon, `${actual} ≠ ${expected}`);
};
const component = (config, id) => config.components.find(item => item.id === id);
const errorCode = (config, code) => {
  const result = CIRCUIT.solve(config);
  assert.equal(result.ok, false);
  assert.equal(result.status, 'error');
  assert.ok(result.errors.some(error => error.code === code), JSON.stringify(result.errors));
  assert.equal(result.totalCurrent, null);
  return result;
};

test('exports the browser-compatible experiment and solver API', () => {
  assert.equal(typeof CIRCUIT.createExperiment, 'function');
  assert.equal(typeof CIRCUIT.solve, 'function');
});

test('the ohm preset builds real apparatus with explicit ports and wires', () => {
  const config = CIRCUIT.createExperiment('ohm');
  assert.equal(config.schema_version, 1);
  assert.equal(config.recipe, 'ohm');
  assert.deepEqual(config.components.map(item => item.id), ['V1', 'A1', 'M1', 'R1', 'S1']);
  assert.equal(component(config, 'V1').params.voltage, 6);
  assert.equal(component(config, 'R1').params.resistance, 10);
  assert.equal(component(config, 'S1').params.closed, true);
  assert.ok(config.wires.every(wire => wire.id && wire.from.includes('.') && wire.to.includes('.')));
});

test('ohm gives analytic current, voltage, resistance and terminal potentials', () => {
  const result = CIRCUIT.solve(CIRCUIT.createExperiment('ohm'));
  assert.equal(result.ok, true);
  assert.equal(result.status, 'ok');
  assert.deepEqual(result.errors, []);
  near(result.totalCurrent, 0.6);
  near(result.sourceVoltage, 6);
  near(result.equivalentResistance, 10);
  near(result.components.A1.current, 0.6);
  near(result.components.A1.value, 0.6);
  near(result.components.M1.value, 6);
  near(result.components.R1.voltage, 6);
  near(result.nodeVoltages['V1.negative'], 0);
  near(result.nodeVoltages['R1.a'], 6);
});

test('series has equal current and the correct resistor voltage division', () => {
  const result = CIRCUIT.solve(CIRCUIT.createExperiment('series'));
  assert.equal(result.ok, true);
  near(result.totalCurrent, 0.2);
  near(result.equivalentResistance, 30);
  near(result.components.R1.current, 0.2);
  near(result.components.R2.current, 0.2);
  near(result.components.R1.voltage, 2);
  near(result.components.R2.voltage, 4);
  near(result.components.M1.value, 2);
});

test('parallel adds independent branch currents and does not load the voltmeter', () => {
  const result = CIRCUIT.solve(CIRCUIT.createExperiment('parallel'));
  assert.equal(result.ok, true);
  near(result.totalCurrent, 0.9);
  near(result.equivalentResistance, 20 / 3);
  near(result.components.R1.current, 0.6);
  near(result.components.R2.current, 0.3);
  near(result.components.M1.current, 0);
  near(result.components.M1.value, 6);
});

test('parallel starts on the 3 A range and honors an explicit lower range', () => {
  const defaultConfig = CIRCUIT.createExperiment('parallel');
  assert.equal(component(defaultConfig, 'A1').params.range, 3);
  assert.equal(CIRCUIT.solve(defaultConfig).components.A1.overrange, false);
  const lowRange = CIRCUIT.createExperiment('parallel', { ammeterRange: 0.6 });
  assert.equal(component(lowRange, 'A1').params.range, 0.6);
  assert.equal(CIRCUIT.solve(lowRange).components.A1.overrange, true);
  assert.equal(component(CIRCUIT.createExperiment('ohm'), 'A1').params.range, 0.6);
});

test('resistance measurement includes the rheostat series resistance', () => {
  const config = CIRCUIT.createExperiment('resistance');
  const result = CIRCUIT.solve(config);
  assert.equal(result.ok, true);
  near(result.equivalentResistance, 20);
  near(result.totalCurrent, 0.3);
  near(result.components.RH1.value, 10);
  near(result.components.RH1.current, 0.3);
  near(result.components.RH1.voltage, 3);
  near(result.components.M1.value / result.components.A1.value, 10);
  near(result.nodeVoltages['RH1.b'], result.nodeVoltages['RH1.slider']);
});

test('rheostat slider can reach both endpoints without a singular circuit', () => {
  for (const [position, expected] of [[0, 10], [1, 60]]) {
    const result = CIRCUIT.solve(CIRCUIT.createExperiment('resistance', { position }));
    assert.equal(result.ok, true, JSON.stringify(result.errors));
    near(result.equivalentResistance, expected);
    near(result.totalCurrent, 6 / expected);
    near(result.components.RH1.current, 6 / expected);
  }
});

test('all presets become open with zero current and zero load voltmeter voltage', () => {
  for (const recipe of ['ohm', 'resistance', 'series', 'parallel']) {
    const result = CIRCUIT.solve(CIRCUIT.createExperiment(recipe, { closed: false }));
    assert.equal(result.ok, true, `${recipe}: ${JSON.stringify(result.errors)}`);
    assert.equal(result.status, 'open');
    near(result.totalCurrent, 0);
    near(result.components.A1.value, 0);
    near(result.components.M1.value, 0);
    near(result.components.S1.voltage, 6);
    near(result.components.S1.current, 0);
    assert.equal(result.equivalentResistance, Infinity);
  }
});

test('an open switch read by the voltmeter retains the complete source voltage', () => {
  const config = CIRCUIT.createExperiment('ohm', { closed: false });
  config.wires = config.wires.filter(wire => !wire.from.startsWith('M1.') && !wire.to.startsWith('M1.'));
  config.wires.push({ id: 'WM1', from: 'M1.positive', to: 'S1.a' });
  config.wires.push({ id: 'WM2', from: 'M1.negative', to: 'S1.b' });
  near(CIRCUIT.solve(config).components.M1.value, 6);
});

test('meters retain sign and flag only magnitude beyond their configured range', () => {
  const config = CIRCUIT.createExperiment('ohm', { ammeterRange: 0.3, voltmeterRange: 3 });
  config.wires = config.wires.map(wire => ({ ...wire,
    from: wire.from.replace('A1.positive', 'A1.temp').replace('A1.negative', 'A1.positive').replace('A1.temp', 'A1.negative')
      .replace('M1.positive', 'M1.temp').replace('M1.negative', 'M1.positive').replace('M1.temp', 'M1.negative'),
    to: wire.to.replace('A1.positive', 'A1.temp').replace('A1.negative', 'A1.positive').replace('A1.temp', 'A1.negative')
      .replace('M1.positive', 'M1.temp').replace('M1.negative', 'M1.positive').replace('M1.temp', 'M1.negative')
  }));
  const result = CIRCUIT.solve(config);
  near(result.components.A1.value, -0.6);
  near(result.components.M1.value, -6);
  assert.equal(result.components.A1.overrange, true);
  assert.equal(result.components.M1.overrange, true);
  const boundary = CIRCUIT.solve(CIRCUIT.createExperiment('ohm', { ammeterRange: 0.6, voltmeterRange: 6 }));
  assert.equal(boundary.components.A1.overrange, false);
  assert.equal(boundary.components.M1.overrange, false);
});

test('convenience parameters and zero source voltage are used without mutating config', () => {
  const config = CIRCUIT.createExperiment('series', { voltage: 12, resistance: 20, resistance2: 40 });
  const original = JSON.stringify(config);
  near(CIRCUIT.solve(config).totalCurrent, 0.2);
  assert.equal(JSON.stringify(config), original);
  const zero = CIRCUIT.solve(CIRCUIT.createExperiment('series', { voltage: 0 }));
  assert.equal(zero.ok, true);
  near(zero.totalCurrent, 0);
  near(zero.equivalentResistance, 30);
  assert.equal(zero.status, 'ok');
});

test('unknown recipes fail explicitly', () => {
  assert.throws(() => CIRCUIT.createExperiment('invented'), error => error.code === 'UNKNOWN_RECIPE');
});

test('invalid component types and endpoints return validation errors', () => {
  const type = CIRCUIT.createExperiment('ohm');
  component(type, 'R1').type = 'magic';
  errorCode(type, 'UNKNOWN_COMPONENT_TYPE');
  const endpoint = CIRCUIT.createExperiment('ohm');
  endpoint.wires[0].to = 'R1.positive';
  errorCode(endpoint, 'INVALID_ENDPOINT');
});

test('duplicate component and wire IDs cannot silently replace objects', () => {
  const components = CIRCUIT.createExperiment('ohm');
  components.components.push({ ...components.components[0] });
  errorCode(components, 'DUPLICATE_ID');
  const wires = CIRCUIT.createExperiment('ohm');
  wires.wires.push({ ...wires.wires[0] });
  errorCode(wires, 'DUPLICATE_ID');
});

test('nonfinite, negative and incorrectly typed physical parameters are rejected', () => {
  for (const resistance of [-10, 0, Infinity, NaN, '10']) {
    errorCode(CIRCUIT.createExperiment('ohm', { resistance }), 'INVALID_PARAMETER');
  }
  for (const voltage of [-1, Infinity, NaN]) {
    errorCode(CIRCUIT.createExperiment('ohm', { voltage }), 'INVALID_PARAMETER');
  }
  for (const position of [-0.1, 1.1, NaN]) {
    errorCode(CIRCUIT.createExperiment('resistance', { position }), 'INVALID_PARAMETER');
  }
  for (const range of [0, -1, Infinity, '0.6']) {
    errorCode(CIRCUIT.createExperiment('ohm', { ammeterRange: range }), 'INVALID_RANGE');
    errorCode(CIRCUIT.createExperiment('ohm', { voltmeterRange: range }), 'INVALID_RANGE');
  }
  errorCode(CIRCUIT.createExperiment('ohm', { closed: 'false' }), 'INVALID_PARAMETER');
});

test('missing sources and source shorts have explicit errors without fake readings', () => {
  const missing = CIRCUIT.createExperiment('ohm');
  missing.components = missing.components.filter(item => item.id !== 'V1');
  missing.wires = missing.wires.filter(wire => !wire.from.startsWith('V1.') && !wire.to.startsWith('V1.'));
  errorCode(missing, 'MISSING_SOURCE');
  const short = CIRCUIT.createExperiment('ohm');
  short.wires.push({ id: 'SHORT', from: 'V1.positive', to: 'V1.negative' });
  const result = errorCode(short, 'SOURCE_SHORT');
  assert.equal(result.components.A1.value, null);
  assert.equal(result.components.M1.value, null);
});

test('an ammeter across the power supply is recognized as an ideal source short', () => {
  const config = CIRCUIT.createExperiment('ohm');
  config.wires.push({ id: 'AMMETER_SHORT', from: 'A1.negative', to: 'V1.negative' });
  errorCode(config, 'SOURCE_SHORT');
});

test('floating resistors and floating voltmeter terminals never acquire invented voltages', () => {
  const config = CIRCUIT.createExperiment('ohm');
  config.components.push({ id: 'FLOAT', type: 'resistor', params: { resistance: 10 } });
  const result = errorCode(config, 'FLOATING_SUBCIRCUIT');
  assert.equal(result.nodeVoltages['FLOAT.a'], null);
  const meter = CIRCUIT.createExperiment('ohm');
  meter.wires = meter.wires.filter(wire => !wire.from.startsWith('M1.') && !wire.to.startsWith('M1.'));
  errorCode(meter, 'FLOATING_SUBCIRCUIT');
});

test('malformed schemas produce structured errors instead of exceptions', () => {
  for (const config of [null, {}, { schema_version: 2, components: [], wires: [] }, { schema_version: 1, components: [null], wires: [] }]) {
    const result = CIRCUIT.solve(config);
    assert.equal(result.ok, false);
    assert.equal(result.status, 'error');
    assert.ok(result.errors.length);
  }
});

test('browser script exposes CIRCUIT without requiring module or external libraries', () => {
  const fs = require('node:fs');
  const vm = require('node:vm');
  const context = { window: {} };
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(require.resolve('./core.js'), 'utf8'), context);
  assert.equal(typeof context.CIRCUIT.createExperiment, 'function');
  near(context.CIRCUIT.solve(context.CIRCUIT.createExperiment('parallel')).totalCurrent, 0.9);
});

test('catalog records component terminals, recipe scope and honest provenance', () => {
  const catalog = require('./catalog.json');
  assert.equal(catalog.schema_version, 1);
  assert.deepEqual(catalog.components.map(item => item.type).sort(), ['ammeter', 'power_supply', 'resistor', 'rheostat', 'switch', 'voltmeter']);
  assert.deepEqual(catalog.recipes.map(item => item.id).sort(), ['ohm', 'parallel', 'resistance', 'series']);
  for (const item of catalog.components) {
    assert.ok(item.ports.length >= 2);
    assert.ok(item.parameters);
    assert.ok(item.source);
  }
  assert.ok(catalog.provenance.solver.includes('core.mjs'));
  assert.equal(catalog.capabilities.free_wiring, false);
});
