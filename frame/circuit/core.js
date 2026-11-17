/*
 * 教学直流器材内核。MNA 电阻/理想电压源盖章与部分主元消元改编自仓库内
 * code/eduforge/tools/labkit/circuit/core.mjs；端口图、器材模型和固定实验为本项目实现。
 * 此文件不加载 CircuitJS，也不需要第三方运行库。
 */
(function (root, factory) {
  'use strict';
  const api = factory();
  root.CIRCUIT = api;
  if (typeof module === 'object' && module.exports) module.exports = api;
})(typeof globalThis !== 'undefined' ? globalThis : window, function () {
  'use strict';

  const PORTS = Object.freeze({
    power_supply: ['positive', 'negative'],
    ammeter: ['positive', 'negative'],
    voltmeter: ['positive', 'negative'],
    resistor: ['a', 'b'],
    rheostat: ['a', 'slider', 'b'],
    switch: ['a', 'b']
  });
  const RECIPES = ['ohm', 'resistance', 'series', 'parallel'];
  const finite = value => typeof value === 'number' && Number.isFinite(value);
  const positive = value => finite(value) && value > 0;
  const normalized = value => Object.is(value, -0) ? 0 : value;
  const blankMeasurement = () => ({ current: null, voltage: null, value: null, range: null, overrange: false });

  function createExperiment(recipe, params) {
    if (!RECIPES.includes(recipe)) {
      const error = new Error('未知实验：' + recipe);
      error.code = 'UNKNOWN_RECIPE';
      throw error;
    }
    const p = Object.assign({ voltage: 6, resistance: 10, resistance2: 20,
      maxResistance: 50, position: 0.2, closed: true, ammeterRange: recipe === 'parallel' ? 3 : 0.6, voltmeterRange: 15 }, params || {});
    const components = [
      { id: 'V1', type: 'power_supply', params: { voltage: p.voltage } },
      { id: 'A1', type: 'ammeter', params: { range: p.ammeterRange } },
      { id: 'M1', type: 'voltmeter', params: { range: p.voltmeterRange } },
      { id: 'R1', type: 'resistor', params: { resistance: p.resistance } },
      { id: 'S1', type: 'switch', params: { closed: p.closed } }
    ];
    const wires = [];
    const wire = (from, to) => wires.push({ id: 'W' + (wires.length + 1), from, to });
    wire('V1.positive', 'S1.a');
    wire('S1.b', 'A1.positive');
    wire('M1.positive', 'R1.a');
    wire('M1.negative', 'R1.b');
    if (recipe === 'resistance') {
      components.push({ id: 'RH1', type: 'rheostat', params: { maxResistance: p.maxResistance, position: p.position } });
      wire('A1.negative', 'RH1.a');
      wire('RH1.slider', 'R1.a');
      wire('R1.b', 'V1.negative');
    } else if (recipe === 'series') {
      components.push({ id: 'R2', type: 'resistor', params: { resistance: p.resistance2 } });
      wire('A1.negative', 'R1.a');
      wire('R1.b', 'R2.a');
      wire('R2.b', 'V1.negative');
    } else {
      wire('A1.negative', 'R1.a');
      wire('R1.b', 'V1.negative');
      if (recipe === 'parallel') {
        components.push({ id: 'R2', type: 'resistor', params: { resistance: p.resistance2 } });
        wire('R1.a', 'R2.a');
        wire('R1.b', 'R2.b');
      }
    }
    return { schema_version: 1, recipe, components, wires };
  }

  function unionFind(items) {
    const parents = new Map(items.map(item => [item, item]));
    function find(item) {
      let top = item;
      while (parents.get(top) !== top) top = parents.get(top);
      while (item !== top) {
        const next = parents.get(item);
        parents.set(item, top);
        item = next;
      }
      return top;
    }
    return { find, union(a, b) { parents.set(find(a), find(b)); } };
  }

  function validate(config) {
    const errors = [];
    const add = (code, message) => errors.push({ code, message });
    const endpoints = [];
    const components = new Map();
    if (!config || config.schema_version !== 1 || !Array.isArray(config.components) || !Array.isArray(config.wires)) {
      add('INVALID_CONFIG', '需要 schema_version: 1、components 数组与 wires 数组。');
      return { errors, endpoints, components };
    }
    const ids = new Set();
    function checkId(item, label) {
      if (!item || typeof item !== 'object' || typeof item.id !== 'string' || !/^[A-Za-z][A-Za-z0-9_-]*$/.test(item.id)) {
        add('INVALID_ID', label + '需要由字母开头的唯一 id。');
        return false;
      }
      if (ids.has(item.id)) { add('DUPLICATE_ID', '重复 id：' + item.id); return false; }
      ids.add(item.id);
      return true;
    }
    for (const component of config.components) {
      if (!checkId(component, '器材')) continue;
      if (!Object.hasOwn(PORTS, component.type)) { add('UNKNOWN_COMPONENT_TYPE', component.id + '：未知器材类型。'); continue; }
      components.set(component.id, component);
      for (const port of PORTS[component.type]) endpoints.push(component.id + '.' + port);
      const p = component.params;
      if (!p || typeof p !== 'object' || Array.isArray(p)) { add('INVALID_PARAMETER', component.id + '：缺少 params 对象。'); continue; }
      let valid = true;
      switch (component.type) {
        case 'power_supply': valid = finite(p.voltage) && p.voltage >= 0; break;
        case 'resistor': valid = positive(p.resistance); break;
        case 'rheostat': valid = positive(p.maxResistance) && finite(p.position) && p.position >= 0 && p.position <= 1; break;
        case 'switch': valid = typeof p.closed === 'boolean'; break;
        case 'ammeter': case 'voltmeter':
          if (!positive(p.range)) add('INVALID_RANGE', component.id + '：量程必须是大于 0 的有限数值。');
          break;
      }
      if (!valid) add('INVALID_PARAMETER', component.id + '：物理参数不合法。');
    }
    const endpointSet = new Set(endpoints);
    for (const wire of config.wires) {
      if (!checkId(wire, '导线')) continue;
      if (!endpointSet.has(wire.from) || !endpointSet.has(wire.to)) add('INVALID_ENDPOINT', wire.id + '：导线端点不存在。');
    }
    const sources = [...components.values()].filter(component => component.type === 'power_supply');
    if (!sources.length) add('MISSING_SOURCE', '电路缺少直流电源。');
    if (sources.length > 1) add('MULTIPLE_SOURCES', '第一阶段仅支持一个直流电源。');
    return { errors, endpoints, components, source: sources[0] };
  }

  // 部分主元高斯消元，算法来自内部 MNA 内核；奇异/数值溢出显式报错。
  function solveLinear(matrix, rhs) {
    const n = rhs.length;
    const rows = matrix.map((row, index) => [...row, rhs[index]]);
    for (let col = 0; col < n; col += 1) {
      let pivot = col;
      for (let row = col + 1; row < n; row += 1) if (Math.abs(rows[row][col]) > Math.abs(rows[pivot][col])) pivot = row;
      if (!Number.isFinite(rows[pivot][col]) || Math.abs(rows[pivot][col]) < 1e-14) throw new Error('SINGULAR_MATRIX');
      [rows[col], rows[pivot]] = [rows[pivot], rows[col]];
      const divisor = rows[col][col];
      for (let index = col; index <= n; index += 1) rows[col][index] /= divisor;
      for (let row = 0; row < n; row += 1) {
        if (row === col) continue;
        const factor = rows[row][col];
        if (!factor) continue;
        for (let index = col; index <= n; index += 1) rows[row][index] -= factor * rows[col][index];
      }
    }
    const result = rows.map(row => row[n]);
    if (!result.every(Number.isFinite)) throw new Error('NUMERIC_ERROR');
    return result;
  }

  function solve(config) {
    const checked = validate(config);
    const measurements = Object.create(null);
    const nodeVoltages = Object.create(null);
    for (const [id, component] of checked.components) {
      measurements[id] = blankMeasurement();
      if (component.type === 'ammeter' || component.type === 'voltmeter') measurements[id].range = component.params && component.params.range;
    }
    for (const endpoint of checked.endpoints) nodeVoltages[endpoint] = null;
    const result = { ok: false, status: 'error', errors: checked.errors, components: measurements,
      totalCurrent: null, sourceVoltage: null, equivalentResistance: null, nodeVoltages };
    const fail = (code, message) => { result.errors.push({ code, message }); return result; };
    if (result.errors.length) return result;

    const uf = unionFind(checked.endpoints);
    for (const wire of config.wires) uf.union(wire.from, wire.to);
    for (const component of checked.components.values()) {
      if (component.type === 'switch' && component.params.closed) uf.union(component.id + '.a', component.id + '.b');
    }
    const sources = [];
    const resistors = [];
    const branch = (id, from, to, resistance) => {
      if (resistance === 0) sources.push({ id, from: uf.find(from), to: uf.find(to), v: 0 });
      else resistors.push({ id, from: uf.find(from), to: uf.find(to), r: resistance });
    };
    for (const component of checked.components.values()) {
      const id = component.id;
      const p = component.params;
      if (component.type === 'power_supply') sources.unshift({ id, from: uf.find(id + '.positive'), to: uf.find(id + '.negative'), v: p.voltage });
      if (component.type === 'ammeter') sources.push({ id, from: uf.find(id + '.positive'), to: uf.find(id + '.negative'), v: 0 });
      if (component.type === 'resistor') branch(id, id + '.a', id + '.b', p.resistance);
      if (component.type === 'rheostat') {
        branch(id + ':a', id + '.a', id + '.slider', p.maxResistance * p.position);
        branch(id + ':b', id + '.slider', id + '.b', p.maxResistance * (1 - p.position));
      }
    }
    const supply = sources.find(source => source.id === checked.source.id);
    const roots = [...new Set(checked.endpoints.map(endpoint => uf.find(endpoint)))];
    const conductive = unionFind(roots);
    for (const source of sources) if (source !== supply) conductive.union(source.from, source.to);
    if (conductive.find(supply.from) === conductive.find(supply.to)) return fail('SOURCE_SHORT', '电源正负端经导线、闭合开关或理想电流表短接。');

    // 连通性包含电阻、电源和电流表，不包含无限内阻的电压表及断开开关。
    const connected = unionFind(roots);
    for (const branch of [...sources, ...resistors]) connected.union(branch.from, branch.to);
    const floating = roots.filter(node => connected.find(node) !== connected.find(supply.to));
    if (floating.length) return fail('FLOATING_SUBCIRCUIT', '存在未参考电源负端的悬空端口/子电路：' + floating.join('、'));

    const loadConnected = unionFind(roots);
    for (const branch of [...sources.filter(source => source !== supply), ...resistors]) loadConnected.union(branch.from, branch.to);
    const open = loadConnected.find(supply.from) !== loadConnected.find(supply.to);
    const nodes = roots.filter(node => node !== supply.to);
    const nodeIndices = new Map(nodes.map((node, index) => [node, index]));
    // 完全被导线旁路的理想表支路电流不可辨识；不为其制造任意电流。
    const activeSources = sources.filter(source => source.from !== source.to);
    const size = nodes.length + activeSources.length;
    const matrix = Array.from({ length: size }, () => Array(size).fill(0));
    const rhs = Array(size).fill(0);
    const index = node => nodeIndices.get(node);
    for (const resistor of resistors) {
      const a = index(resistor.from), b = index(resistor.to), g = 1 / resistor.r;
      if (a !== undefined) matrix[a][a] += g;
      if (b !== undefined) matrix[b][b] += g;
      if (a !== undefined && b !== undefined) { matrix[a][b] -= g; matrix[b][a] -= g; }
    }
    for (const [k, source] of activeSources.entries()) {
      const branchIndex = nodes.length + k;
      const a = index(source.from), b = index(source.to);
      if (a !== undefined) { matrix[a][branchIndex] += 1; matrix[branchIndex][a] += 1; }
      if (b !== undefined) { matrix[b][branchIndex] -= 1; matrix[branchIndex][b] -= 1; }
      rhs[branchIndex] = source.v;
    }
    let solution;
    let equivalent;
    const supplyIndex = nodes.length + activeSources.indexOf(supply);
    try {
      solution = solveLinear(matrix, rhs);
      if (open) equivalent = Infinity;
      else if (supply.v !== 0) equivalent = supply.v / -solution[supplyIndex];
      else {
        const unitRhs = rhs.slice();
        unitRhs[supplyIndex] = 1;
        equivalent = 1 / -solveLinear(matrix, unitRhs)[supplyIndex];
      }
    } catch (error) {
      return fail(error.message === 'NUMERIC_ERROR' ? 'NUMERIC_ERROR' : 'UNSOLVABLE_TOPOLOGY', '电路约束冲突、理想支路电流不唯一，或参数超出数值求解范围。');
    }
    const potential = node => node === supply.to ? 0 : solution[index(node)];
    const voltage = (id, a, b) => normalized(potential(uf.find(id + '.' + a)) - potential(uf.find(id + '.' + b)));
    const sourceCurrent = id => {
      const i = activeSources.findIndex(source => source.id === id);
      return i < 0 ? null : normalized(solution[nodes.length + i]);
    };
    for (const endpoint of checked.endpoints) nodeVoltages[endpoint] = normalized(potential(uf.find(endpoint)));
    for (const component of checked.components.values()) {
      const id = component.id, p = component.params, reading = measurements[id];
      switch (component.type) {
        case 'power_supply':
          reading.voltage = voltage(id, 'positive', 'negative');
          reading.current = sourceCurrent(id); // 电流流入正端为正，供电时为负。
          reading.value = reading.voltage;
          break;
        case 'ammeter':
          reading.voltage = voltage(id, 'positive', 'negative');
          reading.current = sourceCurrent(id);
          reading.value = reading.current;
          break;
        case 'voltmeter':
          reading.voltage = voltage(id, 'positive', 'negative');
          reading.current = 0;
          reading.value = reading.voltage;
          break;
        case 'resistor':
          reading.voltage = voltage(id, 'a', 'b');
          reading.current = normalized(reading.voltage / p.resistance);
          reading.value = p.resistance;
          break;
        case 'rheostat':
          reading.voltage = voltage(id, 'a', 'slider');
          reading.value = p.maxResistance * p.position;
          reading.current = reading.value === 0 ? sourceCurrent(id + ':a') : normalized(reading.voltage / reading.value);
          break;
        case 'switch':
          reading.voltage = voltage(id, 'a', 'b');
          reading.current = p.closed ? null : 0;
          reading.value = p.closed ? 1 : 0;
          break;
      }
      if (reading.range !== null && reading.value !== null) {
        reading.overrange = Math.abs(reading.value) - reading.range > Number.EPSILON * Math.max(1, reading.range) * 8;
      }
    }
    result.ok = true;
    result.status = open ? 'open' : 'ok';
    result.totalCurrent = open ? 0 : normalized(-solution[supplyIndex]);
    result.sourceVoltage = supply.v;
    result.equivalentResistance = equivalent;
    return result;
  }

  return Object.freeze({ createExperiment, solve });
});
