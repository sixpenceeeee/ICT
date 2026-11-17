/* Python/Node boundary: data only, never evaluate model output. */
'use strict';
const core = require('../frame/circuit/core.js');
let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => { input += chunk; });
process.stdin.on('end', () => {
  try {
    const plan = JSON.parse(input);
    if (!plan || typeof plan !== 'object' || Array.isArray(plan)) throw new Error('电路配置必须是对象');
    const config = Array.isArray(plan.components) ? plan : core.createExperiment(plan.recipe, plan.params || {});
    const solution = core.solve(config);
    if (!solution.ok) throw new Error((solution.errors || []).map(e => e.message || e.code).join('；') || '电路求解失败');
    process.stdout.write(JSON.stringify({config, solution}));
  } catch (error) {
    process.stdout.write(JSON.stringify({error: error.message}));
    process.exitCode = 1;
  }
});
