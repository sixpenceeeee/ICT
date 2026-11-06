/* ============================================================
 *  ui_audit.js —— 页面 UI 规范体检
 *
 *  量三件在截图里看不出来的事：
 *    1. 蓝色条是不是只放了实验名字（字数 + 实际文本）
 *    2. ① 区还有没有重复的实验名称（.exp-name）
 *    3. 正文里还有没有「非黑」和「小于 MIN_FONT」的文字
 *
 *  用法：
 *    node tools/ui_audit.js 页面.html [--shot 输出.png]
 * ============================================================ */
const path = require('path');
const { pathToFileURL } = require('url');

// 自己找 playwright，不依赖调用方先 export NODE_PATH（reviewer.py 里是同一套候选目录）
(function ensurePlaywright() {
  const home = process.env.HOME || process.env.USERPROFILE || '';
  [path.join(home, '.workbuddy/binaries/node/workspace/node_modules'),
   path.join(home, '.workbuddy/binaries/node/lib/node_modules')].forEach(p => {
    if (!module.paths.includes(p)) module.paths.push(p);
  });
})();
const { chromium } = require('playwright');

// 门槛跟着 normal.css 的 --pf-fs-min 走；页面没注入规范时退回 13
let MIN_FONT = 13;

// 这些元素上的彩色是「语义色」，不算违反「正文纯黑」
const ACCENT = [
  '.exp-tag', '.exp-btn', '.exp-read .v', '.exp-field .exp-val',
  '.exp-formula em', '.exp-alert', '.pf-tip', '.pf-fix', '.pf-page',
  '.exp-goals li::before',
];

(async () => {
  const file = process.argv[2];
  const shotIdx = process.argv.indexOf('--shot');
  const shot = shotIdx > 0 ? process.argv[shotIdx + 1] : '';

  const b = await chromium.launch({
    executablePath: 'C:/Users/wangq/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe',
  });
  const p = await b.newPage({ viewport: { width: 1500, height: 1000 }, deviceScaleFactor: 1 });
  const errs = [];
  p.on('pageerror', (e) => errs.push(String(e).slice(0, 120)));
  await p.goto(pathToFileURL(path.resolve(file)).href);
  await p.waitForTimeout(900);

  const MIN = await p.evaluate(() => {
    const v = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--pf-fs-min'));
    return v > 0 ? v : 13;
  });
  MIN_FONT = MIN;

  const r = await p.evaluate((MIN) => {
    const out = { title: '', titleLen: 0, hasName: false, small: [], colored: [], minFs: 99 };
    const t = document.querySelector('.pf-page');
    if (t) { out.title = t.textContent.trim(); out.titleLen = out.title.length; }
    const info = document.getElementById('sec-info');
    out.hasName = !!(info && info.querySelector('.exp-name'));

    const ACC = ['.exp-tag', '.exp-btn', '.exp-read .v', '.exp-field .exp-val',
      '.exp-formula em', '.exp-alert', '.pf-tip', '.pf-fix', '.pf-page'];
    document.querySelectorAll('.pf-main *, .pf-footer').forEach((el) => {
      let txt = '';
      for (const c of el.childNodes) if (c.nodeType === 3) txt += c.nodeValue.trim();
      if (!txt) return;
      if (el.closest('canvas, svg')) return;
      const s = getComputedStyle(el);
      const fs = parseFloat(s.fontSize);
      if (fs < out.minFs) out.minFs = fs;
      const isAcc = ACC.some((sel) => el.matches(sel));
      if (fs < MIN - 0.01) {
        out.small.push({ cls: (el.className || el.tagName).toString().slice(0, 26), fs: +fs.toFixed(1), txt: txt.slice(0, 14) });
      }
      if (!isAcc && s.color !== 'rgb(0, 0, 0)') {
        out.colored.push({ cls: (el.className || el.tagName).toString().slice(0, 26), color: s.color, txt: txt.slice(0, 14) });
      }
    });
    return out;
  }, MIN_FONT);

  if (shot) await p.screenshot({ path: shot, fullPage: false });
  await b.close();

  console.log('页面        ' + path.basename(file));
  console.log('蓝色条      ' + JSON.stringify(r.title) + '  (' + r.titleLen + ' 字)' + (r.titleLen <= 18 ? '  ✔' : '  ✘ 过长'));
  console.log('①区重复名称  ' + (r.hasName ? '✘ 还有 .exp-name' : '✔ 已删除'));
  console.log('最小字号    ' + r.minFs + 'px' + (r.minFs >= MIN_FONT - 0.01 ? '  ✔' : '  ✘ 低于 ' + MIN_FONT));
  console.log(('小于' + MIN_FONT + 'px').padEnd(9, ' ') + '  ' + r.small.length + ' 处' + (r.small.length ? '  ' + JSON.stringify(r.small.slice(0, 6)) : '  ✔'));
  console.log('非黑正文     ' + r.colored.length + ' 处' + (r.colored.length ? '  ' + JSON.stringify(r.colored.slice(0, 6)) : '  ✔'));
  console.log('JS 报错      ' + (errs.length ? JSON.stringify(errs.slice(0, 3)) : '无  ✔'));
})();
