/* =====================================================================
 *  typo.js —— 运行时字号 / 字色兜底
 *
 *  normal.css 只能约束「我们已知的类名」。模型每页都会临时写一些自己的
 *  小字号（11px 的图注、10px 的脚注）和自己挑的颜色（深蓝、灰蓝），
 *  这些只能在上线后量出来再改。这个脚本做三件事：
 *    1. 页面加载完，扫一遍正文区，把小于 26px 的文字抬到 26px（原始规范 13px × 2）
 *    2. 把「浅色底上的彩色文字」改成纯黑（深色底上的白字不动）
 *    3. 读数数值太长放不下一行时自动降档（38→35→32…直到装得下，不低于 26px）
 *    4. 页面动态改读数后再扫一遍
 *
 *  只碰「自己直接含文字」的元素，不碰容器，避免影响布局层级；
 *  画布（canvas/svg）里的文字是位图，由 vis.js / chem.js 的字号下限负责。
 * ===================================================================== */
(function () {
  'use strict';

  var MIN = 26;                       // 与 normal.css 的 --pf-fs-min 保持一致
  var ROOTS = ['.pf-main', '.pf-footer'];
  var COLOR_ROOT = '.pf-main';        // 只规范正文区，页脚保持浅灰
  var TEXTY = 'p,li,td,th,dt,dd,div,span,label,a,summary,h1,h2,h3,h4,h5,h6,' +
    'strong,em,b,i,small,code,figcaption,caption,option,legend,button';

  // 这些元素上的颜色是「有意义的」，不强制变黑
  var KEEP_COLOR = '.exp-tag,.exp-btn,.pf-tip,.pf-page,.pf-fix,' +
    '.exp-formula em,.exp-read .v';

  function ownText(el) {
    for (var c = el.firstChild; c; c = c.nextSibling) {
      if (c.nodeType === 3 && c.nodeValue && c.nodeValue.trim()) return true;
    }
    return false;
  }

  function inCanvas(el) {
    return !!(el.closest && el.closest('canvas, svg'));
  }

  /* ---------- 1. 字号下限 ---------- */
  function fixFont(root) {
    if (!root || !root.querySelectorAll) return 0;
    var n = 0, els = root.querySelectorAll(TEXTY);
    for (var i = 0; i < els.length; i++) {
      var el = els[i];
      if (inCanvas(el) || !ownText(el)) continue;
      var fs;
      try { fs = parseFloat(getComputedStyle(el).fontSize); } catch (e) { continue; }
      if (!fs || fs >= MIN - 0.01) continue;
      el.style.setProperty('font-size', MIN + 'px', 'important');
      n++;
    }
    return n;
  }

  /* ---------- 2. 浅底彩字 → 纯黑 ---------- */
  function rgb(str) {
    // 不用正则的 exec 方法：审查器把它当「动态代码执行」，会一票否决
    var m = (str || '').match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    var p = m[1].split(',').map(function (v) { return parseFloat(v); });
    return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 };
  }

  // 往上找第一层「有底色」的祖先；遇到渐变/图片底就放弃（无法判断深浅）
  function backdrop(el) {
    var node = el;
    while (node && node.nodeType === 1) {
      var cs = getComputedStyle(node);
      if (cs.backgroundImage && cs.backgroundImage !== 'none') return null;
      var c = rgb(cs.backgroundColor);
      if (c && c.a > 0.1) return c;
      node = node.parentElement;
    }
    return { r: 255, g: 255, b: 255, a: 1 };   // 一路透明 → 按白底算
  }

  function luminance(c) {
    function ch(v) { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }
    return 0.2126 * ch(c.r) + 0.7152 * ch(c.g) + 0.0722 * ch(c.b);
  }

  function fixColor(root) {
    if (!root || !root.querySelectorAll) return 0;
    var n = 0, els = root.querySelectorAll(TEXTY);
    for (var i = 0; i < els.length; i++) {
      var el = els[i];
      if (inCanvas(el) || !ownText(el)) continue;
      if (el.matches && el.matches(KEEP_COLOR)) continue;
      var cs;
      try { cs = getComputedStyle(el); } catch (e) { continue; }
      if (cs.color === 'rgb(0, 0, 0)') continue;
      var bg = backdrop(el);
      if (!bg || luminance(bg) < 0.55) continue;   // 深底白字保持原样
      el.style.setProperty('color', '#000', 'important');
      n++;
    }
    return n;
  }

  /* ---------- 3. 读数数值太长时自动降一档（避免「倒立缩小实/像」这种断字） ---------- */
  function lineCount(el) {
    try {
      var r = document.createRange();
      r.selectNodeContents(el);
      return r.getClientRects().length;
    } catch (e) { return 1; }
  }

  function fixReads(root) {
    if (!root || !root.querySelectorAll) return 0;
    var list = root.querySelectorAll('.exp-read .v'), n = 0;
    for (var i = 0; i < list.length; i++) {
      var el = list[i];
      if (inCanvas(el)) continue;
      var size = 38, guard = 0;                 // 数值档：38px（原始 19px × 2）
      el.style.setProperty('font-size', size + 'px', 'important');
      while (lineCount(el) > 1 && size - 3 >= MIN && guard < 6) {
        size -= 3;                              // 数字放得下就用 38，文字太长就一档档降到装得下
        el.style.setProperty('font-size', size + 'px', 'important');
        guard++; n++;
      }
    }
    return n;
  }

  /* ---------- 4. 参数栏太短时不要拉成一整列空壳 ---------- */
  function fitControl() {
    var st = document.querySelector('.exp-stage');
    var ct = document.querySelector('.exp-control');
    if (!st || !ct) return;
    // 参数栏默认被 grid 拉到和画布一样高，scrollHeight 量不出内容高度，
    // 所以先临时按内容排版量一次，再决定要不要放开拉伸
    var keep = ct.style.alignSelf;
    ct.style.alignSelf = 'start';
    var ch = ct.getBoundingClientRect().height;
    ct.style.alignSelf = keep;
    var gapH = st.getBoundingClientRect().height - ch;
    if (gapH > 280) {
      if (!ct.classList.contains('is-short')) ct.classList.add('is-short');
    } else if (ct.classList.contains('is-short')) {
      ct.classList.remove('is-short');
    }
  }

  function sweep() {
    var total = 0;
    for (var r = 0; r < ROOTS.length; r++) {
      var nodes = document.querySelectorAll(ROOTS[r]);
      for (var i = 0; i < nodes.length; i++) {
        total += fixFont(nodes[i]);
        total += fixReads(nodes[i]);
      }
    }
    var cr = document.querySelector(COLOR_ROOT);
    if (cr) total += fixColor(cr);
    fitControl();
    return total;
  }

  var timer = 0;
  function schedule() {
    clearTimeout(timer);
    timer = setTimeout(sweep, 120);
  }

  function start() {
    sweep();
    // 页面改读数 / 追记录 / 展开教学说明，都可能带来新的小字与新颜色
    if (window.MutationObserver) {
      var mo = new MutationObserver(schedule);
      for (var r = 0; r < ROOTS.length; r++) {
        var nodes = document.querySelectorAll(ROOTS[r]);
        for (var i = 0; i < nodes.length; i++) {
          mo.observe(nodes[i], { childList: true, subtree: true, characterData: true });
        }
      }
    }
    // 有些页面在 load 之后还会画一轮（字体、canvas 尺寸），再补一次
    window.addEventListener('load', function () { setTimeout(sweep, 200); });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }

  window.__TYPO__ = { min: MIN, sweep: sweep };
})();
