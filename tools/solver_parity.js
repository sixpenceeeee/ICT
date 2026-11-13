#!/usr/bin/env node
/* solver_parity.js —— 把页面端 JS 求解器与 Python 参考实现逐字段对拍。
 *
 * 为什么需要：同一个场景有两套实现（frame 下的 js 与 solvers 下的 py）。
 * 只靠浏览器审查时对拍，改一行 JS 要等到下次生成页面才暴露。
 * 这里用 Node 直接加载 frame 场景库，输出所有 cases 的结果，
 * 由 tests/test_solver_js_parity.py 与 Python 参考实现比较。
 *
 * 用法（在项目根目录）：
 *   node tools/solver_parity.js
 * 输出：JSON 到 stdout，形如 {"PHYS.solveBuoyancy": [{case, ok, result|error}]}
 */
'use strict';

const fs = require('fs');
const path = require('path');

const root = process.cwd();
const solverRoot = path.join(root, '03_generator_agent', 'solvers');

global.window = {
  addEventListener() {},
  removeEventListener() {},
  devicePixelRatio: 1,
};

function load(relative) {
  const code = fs.readFileSync(path.join(root, relative), 'utf8');
  // frame 下的 js 是 IIFE，只依赖 window；用一个最小 document 兜住加载期访问。
  // readyState 故意不是 complete，避免触发页面自检动画。
  new Function('window', 'document', code)(global.window, { readyState: 'loading' });
}

for (const file of ['frame/phys.js', 'frame/math.js']) {
  load(file);
}

const families = [
  ['physics', 'PHYS', 'physics'],
  ['mathematics', 'MATH', 'mathematics'],
];

const output = {};
for (const [directory, namespace] of families) {
  const modelsPath = path.join(solverRoot, directory, 'lesson_models.json');
  const models = JSON.parse(fs.readFileSync(modelsPath, 'utf8'));
  for (const model of Object.values(models)) {
    const api = model.api;
    const target = global.window[namespace] && global.window[namespace][api];
    const key = namespace + '.' + api;
    output[key] = Object.entries(model.cases).map(([caseName, request]) => {
      if (typeof target !== 'function') {
        return { case: caseName, ok: false, error: '页面端未导出 ' + api };
      }
      try {
        return { case: caseName, ok: true, result: target(Object.assign({}, request)) };
      } catch (error) {
        return { case: caseName, ok: false, error: String((error && error.message) || error) };
      }
    });
  }
}

const payload = JSON.stringify(output);
const outPath = process.argv[2];
if (outPath) {
  fs.writeFileSync(outPath, payload, 'utf8');
} else {
  process.stdout.write(payload);
}
