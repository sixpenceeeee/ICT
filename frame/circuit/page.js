/* Shared main-page controls and standalone editor transport. */
(function (global) {
  'use strict';
  const clone = value => JSON.parse(JSON.stringify(value));
  const fmt = (value, digits = 3) => Number.isFinite(value) ? Number(value.toFixed(digits)).toString() : '—';
  function node(tag, attrs, text) {
    const element = document.createElement(tag);
    Object.entries(attrs || {}).forEach(([k, v]) => element.setAttribute(k, v));
    if (text !== undefined) element.textContent = text;
    return element;
  }
  function fields(config, host, onChange, options) {
    host.replaceChildren();
    const advanced = options && options.advanced;
    function field(c, key, label, min, max, step, unit, choices) {
      const box = node('div', {class: 'exp-field'});
      const id = 'c-' + c.id + '-' + key;
      const labelRow = node('label', {class: 'exp-label', for: id}, label + ' ');
      const output = node('span', {class: 'exp-val'}, fmt(c.params[key]) + ' ' + unit);
      labelRow.append(output);
      const input = node(choices ? 'select' : 'input', {id, 'aria-label': label, 'data-key': c.id + '.' + key});
      if (choices) {
        choices.forEach(v => input.append(node('option', {value: v}, v + ' ' + unit)));
        if (!choices.includes(c.params[key])) input.append(node('option', {value: c.params[key]}, c.params[key] + ' ' + unit));
      } else {
        Object.entries({type: 'range', min: Math.min(min, c.params[key]), max: Math.max(max, c.params[key]), step}).forEach(([k, v]) => input.setAttribute(k, v));
      }
      input.value = c.params[key];
      input.addEventListener(choices ? 'change' : 'input', () => {
        c.params[key] = Number(input.value);
        output.textContent = fmt(c.params[key]) + ' ' + unit;
        onChange();
      });
      box.append(labelRow, input);host.append(box);
    }
    config.components.forEach(c => {
      if (c.type === 'power_supply') field(c, 'voltage', '电源电压', 0, 12, .1, 'V');
      if (c.type === 'resistor' && (config.recipe !== 'resistance' || advanced)) field(c, 'resistance', c.id === 'R2' ? '电阻 R₂' : (c.id === 'R_load' ? '负载电阻' : (config.recipe === 'voltage_divider' ? '负载电阻 R₁' : '电阻 R₁')), 1, 100, 1, 'Ω');
      if (c.type === 'rheostat') {
        field(c, 'position', '滑动变阻器位置', 0, 1, .01, '');
        if (advanced) field(c, 'maxResistance', '滑动变阻器总阻值', 1, 200, 1, 'Ω');
      }
      if (advanced && c.type === 'ammeter') field(c, 'range', '电流表量程', 0, 0, 0, 'A', [.06, .6, 3]);
      if (advanced && c.type === 'voltmeter') field(c, 'range', '电压表量程', 0, 0, 0, 'V', [3, 15, 30]);
    });
  }
  function editorDocument(config, token) {
    const ids = ['catalog', 'core', 'apparatus', 'editor', 'page'];
    const scripts = ids.map(id => {
      const source = document.getElementById('circuit-' + id);
      if (!source) throw new Error('缺少电路编辑器运行资源：' + id);
      return '<scr' + 'ipt>' + source.textContent.replace(/<\/script/gi, '<\\/script') + '</scr' + 'ipt>';
    }).join('\n');
    const data = JSON.stringify({config, token}).replace(/</g, '\\u003c');
    return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
      + '<title>实物电路 · 精细调整</title><body><div id="circuit-editor-root"></div>' + scripts
      + '<scr' + 'ipt>CIRCUIT_EDITOR.boot(' + data + ');</scr' + 'ipt></body></html>';
  }
  function mount(svg, initial) {
    let config = clone(initial);
    let solution;
    const original = clone(initial);
    const records = [];
    const $ = id => document.getElementById(id);
    const editors = new Map();
    const stageHint = $('pf-stage-hint');
    if (stageHint) {
      const enlarge = $('btn-enlarge');
      const tools = enlarge.parentElement;
      stageHint.replaceWith(enlarge);
      tools.remove();
    }
    function paint() {
      solution = global.CIRCUIT.solve(config);
      // Expose the exact model/result pair used by the component.  Browser
      // review and the Python oracle can now inspect the same state without
      // reverse-engineering the SVG or the editor snapshot.
      global.__CIRCUIT_MODEL__ = clone(config);
      global.__CIRCUIT_RESULT__ = clone(solution);
      global.CIRCUIT_VIEW.render(svg, config, solution);
      const ammeter = config.components.find(c => c.type === 'ammeter');
      const voltmeter = config.components.find(c => c.type === 'voltmeter');
      const a = ammeter ? (solution.components[ammeter.id] || {}) : {};
      const v = voltmeter ? (solution.components[voltmeter.id] || {}) : {};
      const i = a.current !== undefined ? a.current : null;
      const u = v.voltage !== undefined ? v.voltage : null;
      $('read-current').textContent = fmt(i, 4);
      $('read-voltage').textContent = fmt(u, 4);
      $('read-resistance').textContent = (i !== null && Math.abs(i) > 1e-12) ? fmt(u / i, 2) : '—';
      const r = config.components.find(c => c.id === 'R1') || config.components.find(c => c.id === 'R_load') || config.components.find(c => c.type === 'resistor');
      const r2 = config.components.find(c => c.id === 'R2');
      if (config.recipe === 'parallel') {
        const r1Curr = solution.components.R1 ? solution.components.R1.current : 0;
        const r2Curr = solution.components.R2 ? solution.components.R2.current : 0;
        if ($('read-branch-1')) $('read-branch-1').textContent = fmt(r1Curr, 4);
        if ($('read-branch-2')) $('read-branch-2').textContent = fmt(r2Curr, 4);
      } else if (config.recipe === 'series') {
        const r2Volt = solution.components.R2 ? solution.components.R2.voltage : 0;
        if ($('read-branch-2')) $('read-branch-2').textContent = fmt(r2Volt, 4);
      }
      $('fml').textContent = !solution.ok ? '电路配置有误，请检查接线。' : solution.status === 'open' ? '开关断开：I = 0 A；U/I 暂无定义。'
        : config.recipe === 'parallel' ? fmt(solution.components.R1 ? solution.components.R1.current : 0, 4) + ' + ' + fmt(solution.components.R2 ? solution.components.R2.current : 0, 4) + ' = ' + fmt(i, 4) + ' A'
        : config.recipe === 'voltage_divider' ? '分压输出：U = ' + fmt(u, 4) + ' V；负载 I = ' + fmt(i, 4) + ' A'
        : r ? fmt(u, 4) + ' ÷ ' + fmt(r.params.resistance) + ' = ' + fmt(i, 4) + ' A' : 'U = ' + fmt(u, 4) + ' V, I = ' + fmt(i, 4) + ' A';
      const over = config.components.filter(c => (solution.components[c.id] || {}).overrange).map(c => c.type === 'ammeter' ? '电流表' : '电压表');
      const errors = (solution.errors || []).map(e => e.message);
      $('alert').hidden = !(over.length || errors.length);
      $('alert').textContent = errors.length ? errors.join('；') : over.join('、') + '超出量程，请点击放大调整并选择合适量程。';
      $('hint').textContent = solution.status === 'open' ? '电路已断开。闭合开关后再记录数据。'
        : config.recipe === 'voltage_divider' ? '滑动变阻器接成分压式电路，调节滑片可连续改变负载两端电压。'
        : '电流表串联，电压表测量被测电阻两端电压。所有示数由实际接线计算。';
      const sw = config.components.find(c => c.type === 'switch');
      $('btn-switch').textContent = sw.params.closed ? '断开开关' : '闭合开关';
      $('btn-record').disabled = !solution.ok || solution.status === 'open' || over.length > 0;
      global.__DATA__ = {scene_id: config.recipe === 'resistance' ? 'voltmeter_ammeter_resistance' : (config.recipe === 'voltage_divider' ? 'voltage_divider' : 'ohm'),
        U: u, I: i, R: r ? r.params.resistance : (i !== null && Math.abs(i) > 1e-12 ? u / i : 0), circuit: {config: clone(config), solution: clone(solution)}};
      global.__CIRCUIT_STATE__ = {config: clone(config), solution: clone(solution)};
    }
    function rebuild() { fields(config, $('circuit-controls'), paint);paint(); }
    $('btn-switch').addEventListener('click', () => {
      const sw = config.components.find(c => c.type === 'switch');sw.params.closed = !sw.params.closed;paint();
    });
    $('btn-reset').addEventListener('click', () => {config = clone(original);records.length = 0;$('rows').replaceChildren();rebuild();});
    $('btn-record').addEventListener('click', () => {
      if ($('btn-record').disabled) return;
      const ammeter = config.components.find(c => c.type === 'ammeter');
      const voltmeter = config.components.find(c => c.type === 'voltmeter');
      const i = ammeter ? (solution.components[ammeter.id] || {}).current : 0;
      const u = voltmeter ? (solution.components[voltmeter.id] || {}).voltage : 0;
      const row = [records.length + 1, solution.sourceVoltage, u, i, Math.abs(i) > 1e-12 ? u / i : null];
      records.push(row);
      const tr = node('tr');row.forEach(v => tr.append(node('td', {}, fmt(v, 4))));$('rows').append(tr);
    });
    function download(text, mime, name) {
      const url = URL.createObjectURL(new Blob([text], {type: mime}));
      const a = node('a', {href: url, download: name});a.click();setTimeout(() => URL.revokeObjectURL(url), 1000);
    }
    $('btn-csv').addEventListener('click', () => download('\ufeff序号,电源(V),被测电压(V),电流(A),电阻(Ω)\r\n' + records.map(r => r.join(',')).join('\r\n'), 'text/csv;charset=utf-8', '电路实验记录.csv'));
    document.querySelectorAll('[data-circuit-download]').forEach(a => a.addEventListener('click', e => {
      e.preventDefault();
      // Export a clean original DOM with the edited initial configuration, not a transient form snapshot.
      const doc = document.documentElement.cloneNode(true);
      doc.querySelector('#rows').replaceChildren();
      const entry = doc.querySelector('#circuit-entry');
      entry.textContent = entry.textContent.replace(/window\.__CIRCUIT_INITIAL__=[\s\S]*?;\s*\nCIRCUIT_PAGE\.mount/, 'window.__CIRCUIT_INITIAL__=' + JSON.stringify(config).replace(/</g, '\\u003c') + ';\nCIRCUIT_PAGE.mount');
      download('<!doctype html>\n' + doc.outerHTML, 'text/html;charset=utf-8', document.title.replace(/[<>:"/\\|?*]/g, '_') + '.html');
      if ($('pf-dl')) $('pf-dl').checked = false;
    }));
    $('btn-enlarge').addEventListener('click', () => {
      const token = global.crypto && global.crypto.randomUUID ? global.crypto.randomUUID() : Date.now() + '-' + Math.random();
      const url = URL.createObjectURL(new Blob([editorDocument(config, token)], {type: 'text/html;charset=utf-8'}));
      const editor = global.open(url, '_blank');
      if (!editor) {$('hint').textContent = '浏览器拦截了放大页，请允许此页面弹出窗口后重试。';URL.revokeObjectURL(url);return;}
      editors.set(editor, {token, url});
      const cleanup = global.setInterval(() => {if (editor.closed) {const entry = editors.get(editor);if (entry) URL.revokeObjectURL(entry.url);editors.delete(editor);clearInterval(cleanup);}}, 1500);
    });
    global.addEventListener('message', e => {
      const entry = editors.get(e.source);
      if (!entry || !e.data || e.data.type !== 'circuit-apply' || e.data.token !== entry.token) return;
      const next = clone(e.data.config);
      const result = global.CIRCUIT.solve(next);
      if (!result.ok) {$('hint').textContent = '调整后的电路无有效解，未应用。';return;}
      config = next;rebuild();$('hint').textContent = '已应用放大页中的调整。';
    });
    rebuild();
  }
  global.CIRCUIT_PAGE = {mount, fields, editorDocument};
})(window);
