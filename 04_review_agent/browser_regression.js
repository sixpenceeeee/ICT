'use strict';

// Run this separately from the original page so probes do not change its evidence.
async function probeInteractions(context, url, plan) {
  const page = await context.newPage();
  const runtime = [];
  page.on('pageerror', error => runtime.push(error.message));
  try {
    await page.goto(url, {waitUntil: 'load'});
    const controls = await page.evaluate(({mode, boundaries}) => {
      const nodes = [...document.querySelectorAll('#sec-control input, #sec-control select')];
      const supported = ['range', 'number', 'checkbox', 'select-one'];
      return nodes.flatMap((el, index) => {
        if (!supported.includes(el.type) || !el.getClientRects().length || el.disabled ||
            el.readOnly || getComputedStyle(el).visibility !== 'visible') return [];
        // A paired slider already exercises this number input through its normal event path.
        if (el.type === 'number' && el.id && nodes.some(node =>
          node.dataset.solverRangeFor === el.id && !node.disabled && node.getClientRects().length)) return [];
        const name = el.getAttribute('data-solver-input') || el.dataset.opticsControl ||
            el.dataset.solverRangeFor || el.id || el.name || el.getAttribute('aria-label');
        const primary = el.dataset.solverRangeFor ? document.getElementById(el.dataset.solverRangeFor) : el;
        const field = primary?.dataset.solverInput;
        const scale = Number((window.__SOLVER_SCALES__ || {})[field]) || 1;
        let targets;
        let domain;
        if (el.type === 'checkbox') {
          targets = ['false', 'true'];
          domain = targets;
        } else if (el.type === 'select-one') {
          domain = [...el.options].filter(option => !option.disabled && !option.closest('optgroup[disabled]'))
            .map(option => option.value);
          targets = domain.length <= 4 ? domain : [domain[0], domain[1], domain.at(-2), domain.at(-1)];
        } else {
          if (el.type === 'number' && (el.min === '' || el.max === '')) return [];
          const min = Number(el.min || 0), max = Number(el.max || 100);
          if (!Number.isFinite(min) || !Number.isFinite(max) || min >= max) return [];
          const step = el.step === 'any' ? 0 : Number(el.step) || 1;
          domain = [min, max, step];
          const base = el.min !== '' ? Number(el.min) : Number(el.getAttribute('value')) || 0;
          const clone = el.cloneNode();
          const fractions = mode === 'deep' ? [0, 0.25, 0.375, 0.625, 0.75, 1] : [0, 0.25, 0.75, 1];
          const values = fractions.map(fraction => min + (max - min) * fraction);
          const anchors = [...(min < 0 && max > 0 ? [0] : []),
            ...(boundaries[field] || []).map(value => value / scale)];
          // Use the closest legal grid value strictly on each side of the boundary.
          for (const anchor of [...new Set(anchors)].filter(value => value >= min && value <= max).slice(0, 3)) {
            const tick = step ? (anchor - base) / step : null;
            const offset = Math.min((max - min) / 100, Math.max(Math.abs(anchor), 1) / 100);
            values.push(anchor,
              step ? base + (Math.ceil(tick - 1e-9) - 1) * step : anchor - offset,
              step ? base + (Math.floor(tick + 1e-9) + 1) * step : anchor + offset);
          }
          targets = values.filter(raw => raw >= min && raw <= max).flatMap(raw => {
            const tick = step && Math.round((raw - base) / step);
            const target = step ? base + Math.max(Math.ceil((min - base) / step - 1e-9),
              Math.min(tick, Math.floor((max - base) / step + 1e-9))) * step : raw;
            clone.value = String(Number(target.toPrecision(14)));
            return clone.value !== '' && clone.validity.valid ? [clone.value] : [];
          });
        }
        const key = name ? JSON.stringify([el.type, name, domain]) : null;
        return [{index, type: el.type, name, field, scale, key, targets: [...new Set(targets)]}];
      });
    }, plan);
    const counts = new Map();
    for (const control of controls) counts.set(control.key, (counts.get(control.key) || 0) + 1);
    const snapshot = () => page.evaluate(() =>
      [...document.querySelectorAll('#sec-result [data-solver-field], #sec-result [data-optics-readout], ' +
        '#sec-result .exp-read .v')].filter(el => el.getClientRects().length && getComputedStyle(el).visibility === 'visible')
        .map(el => el.innerText.trim()).filter(value =>
          /^NaN(?:\s+[A-Za-zΩ%°/·²³]+)?$/i.test(value)));
    const initialInvalid = await snapshot();
    const samples = [];
    const skipped = [];
    for (const [index, control] of controls.slice(0, 12).entries()) {
      // Reload between controls so dependent parameters cannot inherit a prior probe's state.
      if (index) await page.reload({waitUntil: 'load'});
      const key = counts.get(control.key) === 1 ? control.key : null;
      const targets = new Map(control.targets.map(value => [value, '主动']));
      for (const entry of plan.cases.filter(entry => key && entry.control === key).slice(0, 8)) {
        targets.set(entry.value, entry.confirmed ? '历史' : '待确认');
      }
      const locator = page.locator('#sec-control input, #sec-control select').nth(control.index);
      const apply = value => locator.evaluate((el, value) => {
        if (el.disabled || el.readOnly || !el.getClientRects().length) return false;
        if (el.type === 'checkbox') el.checked = value === 'true';
        else el.value = value;
        if (!el.validity.valid || (el.type !== 'checkbox' && el.value !== value)) return false;
        el.dispatchEvent(new Event('input', {bubbles: true}));
        el.dispatchEvent(new Event('change', {bubbles: true}));
        return true;
      }, value, {timeout: 750});
      for (const [value, source] of targets) {
        const start = runtime.length;
        if (!await apply(value)) {
          skipped.push({control: control.name || control.type, value, source});
          continue;
        }
        await page.waitForTimeout(65);
        const invalid = (await snapshot()).filter(item => !initialInvalid.includes(item));
        const observed = plan.prefix && control.field ? await page.evaluate(prefix => {
          const fields = {};
          for (const node of document.querySelectorAll('#sec-result [data-solver-field]')) {
            if (node.getClientRects().length && getComputedStyle(node).visibility === 'visible') {
              (fields[node.dataset.solverField] ??= []).push(node.innerText.trim());
            }
          }
          const error = document.querySelector('[data-solver-error]');
          return {request: window['__' + prefix + '_REQUEST__'] ?? null,
            result: window['__' + prefix + '_RESULT__'] ?? null, fields,
            error: error?.getClientRects().length ? error.innerText.trim() : ''};
        }, plan.prefix) : null;
        samples.push({control: key, name: control.name || control.type, value, source,
          field: control.field, type: control.type, scale: control.scale, observed,
          errors: [...runtime.slice(start), ...invalid.map(item => '结果区出现 ' + item)]});
      }
    }
    return {samples, skipped, controls: controls.length, testedControls: Math.min(controls.length, 12)};
  } catch (error) {
    return {samples: [], skipped: [], error: error.message};
  } finally {
    await page.close();
  }
}

module.exports = probeInteractions;
