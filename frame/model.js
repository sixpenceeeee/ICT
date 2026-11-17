/*
 * model.js —— 轻量可执行学科模型运行时
 *
 * 模型负责描述“页面是什么、有哪些输入、输出和验证关系”；
 * 学科求解器负责计算，VIS/PHYS 负责呈现。这个运行时只做三件事：
 * 注册模型、暴露当前状态、把状态交给审查器和教学界面。
 */
(function (root) {
  'use strict';
  var registry = Object.create(null);

  function clone(value) {
    if (value == null || typeof value !== 'object') return value;
    if (Array.isArray(value)) return value.map(clone);
    var out = {};
    Object.keys(value).forEach(function (key) { out[key] = clone(value[key]); });
    return out;
  }

  function validate(model) {
    if (!model || typeof model !== 'object') throw new Error('学科模型必须是对象');
    if (!model.id || !model.subject || !model.topic) throw new Error('学科模型缺少 id、subject 或 topic');
    if (!model.inputs || !model.outputs) throw new Error('学科模型必须声明 inputs 和 outputs');
    return model;
  }

  function define(model) {
    validate(model);
    var copy = clone(model);
    copy.schema = copy.schema || 'edu-model.v1';
    registry[copy.id] = copy;
    return copy;
  }

  function expose(model, params, result, extra) {
    validate(model);
    var state = {
      schema: 'edu-state.v1',
      modelId: model.id,
      subject: model.subject,
      topic: model.topic,
      params: clone(params || {}),
      result: clone(result || null),
      timestamp: new Date().toISOString()
    };
    if (extra && typeof extra === 'object') {
      Object.keys(extra).forEach(function (key) { state[key] = clone(extra[key]); });
    }
    // 时间戳属于运行监控信息，不应混入 __DATA__ 的可复算快照；
    // 否则同一组参数在“重置”前后会被审查器误判为不同状态。
    root.__EDU_STATE__ = state;
    var publicState = clone(state);
    delete publicState.timestamp;
    return publicState;
  }

  function get(id) { return registry[id] || null; }

  function normalize(model, params) {
    var out = clone(params || {});
    (model.constraints || []).forEach(function (rule) {
      if (!rule || !rule.type) return;
      if (rule.type === 'max') {
        var value = Number(out[rule.field]);
        if (isFinite(value)) out[rule.field] = Math.min(value, Number(rule.value));
      }
      if (rule.type === 'maxBy') {
        var current = Number(out[rule.field]);
        var limit = Number(out[rule.by]);
        if (isFinite(current) && isFinite(limit)) out[rule.field] = Math.min(current, limit);
      }
    });
    return out;
  }

  function textOf(node) {
    return String(node && (node.getAttribute('aria-label') || node.textContent || '') || '')
      .replace(/\s+/g, ' ').trim();
  }

  function attrName(node, pattern) {
    if (!node || !node.attributes) return '';
    for (var i = 0; i < node.attributes.length; i++) {
      var name = node.attributes[i].name;
      if (pattern.test(name)) return name;
    }
    return '';
  }

  function labelFor(node) {
    if (!node) return '';
    var explicit = node.getAttribute('aria-label');
    if (explicit) return explicit;
    var field = node.closest && node.closest('.exp-field, label, .exp-read');
    return textOf(field || node).replace(/\s+/g, ' ').slice(0, 80);
  }

  function discoverInputs() {
    var found = [];
    Array.prototype.forEach.call(document.querySelectorAll('input,select,textarea'), function (node) {
      var key = node.getAttribute('data-solver-input');
      if (!key) {
        // 学科专用标记通常是无值布尔属性，例如
        // data-chem-titration-acid-concentration；属性名本身就是字段名。
        var name = attrName(node, /^data-(?:chem|math|bio|geo|cs)-/i);
        if (name && !/range-for|slider/i.test(name)) key = node.getAttribute(name) || name.replace(/^data-/, '');
      }
      if (!key || node.getAttribute('data-solver-range-for')) return;
      found.push({
        id: key,
        label: labelFor(node),
        type: node.tagName.toLowerCase() === 'select' ? 'select' : (node.type || 'text'),
        min: node.min === '' ? null : Number(node.min),
        max: node.max === '' ? null : Number(node.max),
        step: node.step === '' ? null : node.step,
        defaultValue: node.value
      });
    });
    return found;
  }

  function discoverOutputs() {
    var found = [];
    Array.prototype.forEach.call(document.querySelectorAll('[data-solver-field], .exp-read *'), function (node) {
      var key = node.getAttribute('data-solver-field') ||
        attrName(node, /^data-(?:chem|optics|supp|catalog)-.*(?:field|equation|state|value|mass|volume|ph)$/i);
      if (!key) return;
      found.push({id: key, label: labelFor(node), value: textOf(node)});
    });
    return found;
  }

  function inferSubject(topic) {
    var text = (document.body && document.body.innerText || '') + ' ' + (topic || '');
    if (/物理|力学|压强|浮力|透镜|折射|滑轮|电路/.test(text)) return 'physics';
    if (/化学|溶液|反应|滴定|沉淀|氧化|酸碱|离子/.test(text)) return 'chemistry';
    if (/数学|函数|几何|方程|概率|统计|体积/.test(text)) return 'mathematics';
    if (/生物|细胞|生态|呼吸|光合/.test(text)) return 'biology';
    if (/地理|气候|地图|人口|资源/.test(text)) return 'geography';
    if (/信息|算法|二进制|机器人|编程/.test(text)) return 'informatics';
    return 'general';
  }

  function discover() {
    var titleNode = document.querySelector('.pf-page, h1, title');
    var topic = textOf(titleNode) || document.title || '未命名教学页面';
    var canvases = Array.prototype.map.call(document.querySelectorAll('canvas,svg'), function (node) {
      return {id: node.id || null, type: node.getAttribute('data-visual-type') || 'diagram', label: node.getAttribute('aria-label') || ''};
    });
    return {
      schema: 'edu-model.v1',
      id: 'page.' + topic.replace(/[^\w\u4e00-\u9fff]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 60),
      subject: inferSubject(topic),
      topic: topic,
      inputs: discoverInputs(),
      outputs: discoverOutputs(),
      visual: {type: canvases.length ? canvases[0].type : 'none', canvases: canvases},
      source: 'dom-auto-discovery'
    };
  }

  function runtimeData() {
    var data = root.__DATA__;
    if (data && (data.params || data.result)) return data;
    var requestKey = Object.keys(root).find(function (key) { return /_REQUEST__$/.test(key); });
    var resultKey = Object.keys(root).find(function (key) { return /_RESULT__$/.test(key); });
    if (requestKey || resultKey) return {params: requestKey ? root[requestKey] : {}, result: resultKey ? root[resultKey] : null};
    return null;
  }

  function auto() {
    var discovered = discover();
    var existing = root.__EDU_MODEL__;
    var model = existing || define(discovered);
    if (existing) {
      model.inputs = model.inputs || discovered.inputs;
      model.outputs = model.outputs || discovered.outputs;
      model.visual = model.visual || discovered.visual;
      model.autoDiscovery = discovered;
    }
    root.__EDU_MODEL__ = model;
    var data = runtimeData();
    if (data) expose(model, data.params || {}, data.result || null, {source: 'page-data'});
    return model;
  }

  function scheduleAuto() {
    var run = function () { try { auto(); } catch (e) { root.__EDU_MODEL_ERROR__ = String(e && e.message || e); } };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', run, {once: true});
    else setTimeout(run, 0);
    document.addEventListener('input', function () { setTimeout(run, 0); }, false);
    document.addEventListener('change', function () { setTimeout(run, 0); }, false);
  }

  root.EDU_MODEL = {
    define: define,
    expose: expose,
    normalize: normalize,
    discover: discover,
    auto: auto,
    get: get,
    validate: validate,
    registry: registry
  };
  scheduleAuto();
})(window);
