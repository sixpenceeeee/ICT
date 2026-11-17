#!/usr/bin/env node
/**
 * optics_bridge.js — 把 model JSON 从 stdin 喂给页面侧求解器，结果 JSON 打到 stdout。
 *
 * 用法（仓库根）：
 *   echo '{"f":10,"u":30,"h":2,"screen":{"s":15}}' | node tools/optics_bridge.js
 *
 * 存在的意义：让 Python 侧（tests/test_optics_bridge.py）能拿同一份模型
 * 与 frame/optics_solver.js 对拍，而不是各自相信自己的实现。
 */
'use strict';

const fs = require('node:fs');
const path = require('node:path');

require(path.resolve(__dirname, '..', 'frame', 'optics_solver.js'));

function main() {
  const raw = fs.readFileSync(0, 'utf8').trim();
  const model = raw ? JSON.parse(raw) : { f: 10, u: 30, h: 2, screen: { s: 15 } };
  let result;
  try {
    result = globalThis.OPTICS.solve(model);
  } catch (error) {
    process.stdout.write(JSON.stringify({ error: String(error && error.message || error) }));
    process.exit(2);
  }
  process.stdout.write(JSON.stringify(result));
}

main();
