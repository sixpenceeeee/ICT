/**
 * 文字遮挡体检：检查 DOM 文字是否被 canvas / img / svg / video 覆盖。
 *
 * 原理：对每个可见文本元素取 5 个采样点（中心 + 四角内缩），
 * 用 elementsFromPoint 取出该点从顶到底的元素栈；
 * 若在"文字元素所在层"之上还压着图形元素，即判定为被图形遮挡。
 *
 * 用法：
 *   node tools/check_text_overlap.js <页面.html> [--json]
 *   不带 --json 时打印人读报告
 */
const path = require('path');
const { chromium } = require('playwright');

const EXEC = 'C:/Users/wangq/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe';

function fileUrl(p) {
  const abs = path.resolve(p).replace(/\\/g, '/');
  return 'file:///' + encodeURI(abs);
}

const VIEWPORTS = [
  { name: 'desktop', width: 1440, height: 900 },
  { name: 'tablet', width: 900, height: 1000 },
  { name: 'mobile', width: 390, height: 844 },
];

async function scanViewport(page, vp) {
  await page.setViewportSize({ width: vp.width, height: vp.height });
  await page.evaluate(() => new Promise(r => setTimeout(r, 260)));
  // 页面很长时把元素滚到视口内，逐屏测量
  return page.evaluate(() => {
    const GRAPHIC = new Set(['CANVAS', 'IMG', 'SVG', 'VIDEO', 'PICTURE', 'OBJECT', 'IFRAME']);
    const issues = [];
    const seen = new Set();

    const isVisible = (el) => {
      const cs = getComputedStyle(el);
      if (cs.display === 'none' || cs.visibility === 'hidden') return false;
      if (parseFloat(cs.opacity) < 0.05) return false;
      const r = el.getBoundingClientRect();
      return r.width > 1 && r.height > 1;
    };

    // 只取"直接承载文字"的元素：自身有非空文字节点
    const all = Array.from(document.querySelectorAll('body *'));
    for (const el of all) {
      if (GRAPHIC.has(el.tagName)) continue;
      const ownText = Array.from(el.childNodes)
        .filter(n => n.nodeType === 3)
        .map(n => n.textContent.trim())
        .join('');
      if (!ownText) continue;
      if (!isVisible(el)) continue;

      const rect = el.getBoundingClientRect();
      const pts = [
        [rect.left + rect.width / 2, rect.top + rect.height / 2],
        [rect.left + rect.width * 0.15, rect.top + rect.height * 0.25],
        [rect.left + rect.width * 0.85, rect.top + rect.height * 0.25],
        [rect.left + rect.width * 0.15, rect.top + rect.height * 0.75],
        [rect.left + rect.width * 0.85, rect.top + rect.height * 0.75],
      ];

      let coveredBy = null, coveredPts = 0, totalPts = 0;
      for (const [x, y] of pts) {
        if (x < 2 || y < 2 || x > innerWidth - 2 || y > innerHeight - 2) continue;
        totalPts++;
        const stack = document.elementsFromPoint(x, y);
        const idx = stack.indexOf(el);
        if (idx <= 0) continue; // 文字元素本身在最上层，或不在栈里（被完全盖住）
        const above = stack.slice(0, idx).filter(n => {
          if (!GRAPHIC.has(n.tagName)) return false;
          // 文字元素自身内含的图形（如 <button><svg/></button>）不算遮挡
          return !el.contains(n);
        });
        if (above.length) {
          coveredPts++;
          coveredBy = coveredBy || (above[0].tagName.toLowerCase()
            + (above[0].className && typeof above[0].className === 'string'
              ? '.' + above[0].className.trim().split(/\s+/).join('.') : ''));
        }
      }
      if (coveredPts > 0) {
        const key = el.tagName + '|' + ownText.slice(0, 24);
        if (seen.has(key)) continue;
        seen.add(key);
        issues.push({
          tag: el.tagName.toLowerCase(),
          cls: (el.className && typeof el.className === 'string') ? el.className : '',
          text: ownText.slice(0, 40),
          coveredBy,
          coveredPoints: coveredPts + '/' + totalPts,
          rect: {
            x: Math.round(rect.left), y: Math.round(rect.top),
            w: Math.round(rect.width), h: Math.round(rect.height),
          },
        });
      }
    }

    // 另查：文字元素与图形矩形大面积重叠（即使当前没盖住也是隐患，供参考）
    const overlaps = [];
    const graphics = Array.from(document.querySelectorAll('canvas, img, svg, video'))
      .filter(g => isVisible(g) && g.getBoundingClientRect().width > 40);
    for (const el of all) {
      const ownText = Array.from(el.childNodes)
        .filter(n => n.nodeType === 3).map(n => n.textContent.trim()).join('');
      if (!ownText || !isVisible(el) || GRAPHIC.has(el.tagName)) continue;
      const a = el.getBoundingClientRect();
      for (const g of graphics) {
        if (g.contains(el) || el.contains(g)) continue;
        const b = g.getBoundingClientRect();
        const ix = Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left));
        const iy = Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));
        const inter = ix * iy;
        if (inter > 0.35 * (a.width * a.height)) {
          overlaps.push({
            text: ownText.slice(0, 30),
            graphic: g.tagName.toLowerCase() + (g.id ? '#' + g.id : ''),
            ratio: Math.round(inter / (a.width * a.height) * 100) + '%',
          });
        }
      }
    }

    return {
      viewport: { w: innerWidth, h: innerHeight },
      docHeight: document.documentElement.scrollHeight,
      issues, overlaps,
    };
  });
}

(async () => {
  const args = process.argv.slice(2).filter(a => !a.startsWith('--'));
  const asJson = process.argv.includes('--json');
  const target = args[0];
  if (!target) {
    console.error('用法: node tools/check_text_overlap.js <页面.html> [--json]');
    process.exit(2);
  }

  const browser = await chromium.launch({ executablePath: EXEC });
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(String(e)));
  await page.goto(fileUrl(target), { waitUntil: 'load' });
  await page.waitForTimeout(400);

  const result = { page: path.basename(target), viewports: [], errors };
  for (const vp of VIEWPORTS) {
    const r = await scanViewport(page, vp);
    result.viewports.push({ name: vp.name, ...r });
  }
  await browser.close();

  const total = result.viewports.reduce((n, v) => n + v.issues.length, 0);

  if (asJson) {
    console.log(JSON.stringify(result, null, 1));
  } else {
    console.log('页面：' + result.page);
    for (const v of result.viewports) {
      console.log('\n[' + v.name + ' ' + v.viewport.w + 'x' + v.viewport.h + '] 遮挡 ' + v.issues.length + ' 处');
      v.issues.forEach(it => {
        console.log('  ✗ <' + it.tag + (it.cls ? ' class="' + it.cls + '"' : '') + '> 「' + it.text + '」');
        console.log('      被 ' + it.coveredBy + ' 覆盖（' + it.coveredPoints + ' 个采样点）@ ' +
          it.rect.x + ',' + it.rect.y + ' ' + it.rect.w + 'x' + it.rect.h);
      });
    }
    if (errors.length) console.log('\nJS 错误：' + errors.join(' | '));
    console.log('\n合计遮挡：' + total + ' 处');
  }
  process.exit(total > 0 ? 1 : 0);
})();
