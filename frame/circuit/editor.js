/* Independent, offline apparatus editor; edits remain a private draft until Apply. */
(function (global) {
  'use strict';
  function boot(payload) {
    const config = JSON.parse(JSON.stringify(payload.config));
    const root = document.getElementById('circuit-editor-root');
    const style = document.createElement('style');
    style.textContent = 'body{margin:0;color:#142531;background:#edf1f4;font:16px "Microsoft YaHei",sans-serif}*{box-sizing:border-box}header{display:flex;gap:20px;align-items:center;justify-content:space-between;background:#fff;border-bottom:1px solid #d8e0e6;padding:18px 26px}h1{font-size:22px;margin:0}header p{margin:6px 0 0;color:#526574;font-size:14px}.editor-layout{display:grid;grid-template-columns:minmax(0,1fr) 290px;gap:18px;padding:20px}.bench{background:white;border:1px solid #d8e0e6;border-radius:8px;align-self:start;overflow:hidden}.bench svg{width:100%;height:auto;display:block;touch-action:none}aside{background:#fff;padding:20px;border:1px solid #d8e0e6;border-radius:8px}.exp-field{margin-bottom:20px}.exp-label{display:flex;justify-content:space-between;gap:12px;margin-bottom:8px;font-size:14px}.exp-val{font-variant-numeric:tabular-nums}input[type=range],select{width:100%;accent-color:#1973b8}select{padding:9px;border:1px solid #bccbd6;background:#fff;border-radius:4px}button{font:inherit;font-size:14px;cursor:pointer;padding:10px 16px;background:#fff;border:1px solid #bccbd6;border-radius:5px;color:#173b53}.primary{background:#1a75b9;border-color:#1a75b9;color:white}.actions{display:flex;gap:9px;flex-wrap:wrap}#editor-status{font-size:14px;line-height:1.7;color:#455c6b;padding:0 20px 14px}#editor-selection{font-size:14px;color:#526574;margin:12px 0;min-height:24px}h2{font-size:17px;margin:0 0 18px}@media(max-width:760px){header{padding:14px;align-items:flex-start;flex-wrap:wrap}.editor-layout{grid-template-columns:1fr;padding:10px}.bench{min-width:0}aside{padding:16px}}';
    document.head.append(style);
    root.innerHTML = '<header><div><h1>实物电路 · 精细调整</h1><p>拖动器件调整位置；参数与量程修改仅在应用后回传原页面。</p></div><div class="actions"><button id="editor-cancel" type="button">取消并返回</button><button id="editor-apply" class="primary" type="button">应用并返回</button></div></header>'
      + '<main class="editor-layout"><section class="bench"><svg id="editor-cv" viewBox="0 0 1000 650" aria-label="可移动器件的实物电路编辑区" role="img"></svg><p id="editor-status" aria-live="polite"></p></section>'
      + '<aside><h2>器件参数与量程</h2><div id="editor-controls"></div><button id="editor-switch" type="button"></button><p id="editor-selection">点击器件后，可用方向键微调位置，Shift 加速。</p><button id="editor-layout-reset" type="button">恢复器件默认位置</button></aside></main>';
    let selectedId = null;
    let solved;
    const $ = id => document.getElementById(id);
    function paint() {
      solved = global.CIRCUIT.solve(config);
      global.CIRCUIT_VIEW.render($('editor-cv'), config, solved, {editable: true, selectedId,
        onMove: () => {global.__EDITOR_CONFIG__ = config;},
        onSelect: id => {selectedId = id;$('editor-selection').textContent = '已选中 ' + id + '，可拖动或使用方向键移动。';}});
      const sw = config.components.find(c => c.type === 'switch');
      $('editor-switch').textContent = sw.params.closed ? '断开开关' : '闭合开关';
      const over = config.components.filter(c => (solved.components[c.id] || {}).overrange);
      $('editor-status').textContent = !solved.ok ? (solved.errors || []).map(e => e.message).join('；')
        : over.length ? '电表超出量程，请选择更大量程。' : '总电流 ' + Number(solved.totalCurrent.toFixed(4)) + ' A。移动位置不改变电气连接。';
      $('editor-apply').disabled = !solved.ok;
      global.__EDITOR_CONFIG__ = config;
    }
    global.CIRCUIT_PAGE.fields(config, $('editor-controls'), paint, {advanced: true});
    $('editor-switch').addEventListener('click', () => {const sw = config.components.find(c => c.type === 'switch');sw.params.closed = !sw.params.closed;paint();});
    $('editor-layout-reset').addEventListener('click', () => {config.components.forEach(c => {delete c.x;delete c.y;});paint();});
    $('editor-cancel').addEventListener('click', () => global.close());
    $('editor-apply').addEventListener('click', () => {
      if (!global.opener || global.opener.closed) {$('editor-status').textContent = '原页面已关闭，请保留原页面后再进入编辑。';return;}
      if (!global.CIRCUIT.solve(config).ok) return;
      global.opener.postMessage({type: 'circuit-apply', token: payload.token, config}, '*');
      global.close();
    });
    paint();
  }
  global.CIRCUIT_EDITOR = {boot};
})(window);
