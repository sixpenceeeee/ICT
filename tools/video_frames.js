/* 借 Chromium 自带的解码器把 mp4 抽帧（本机 ffmpeg 是精简版，解不了） */
const path = require('path');
const fs = require('fs');
const home = process.env.HOME || process.env.USERPROFILE || '';
[path.join(home, '.workbuddy/binaries/node/workspace/node_modules')].forEach(p => {
  if (!module.paths.includes(p)) module.paths.push(p);
});
const { chromium } = require('playwright');
const { pathToFileURL } = require('url');
const CHROME = 'C:/Users/wangq/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe';

const video = process.argv[2];
const outDir = process.argv[3] || 'shots/vframes';
const every = parseFloat(process.argv[4] || '0.4');   // 每隔几秒抽一帧

/* 用本地 HTTP 提供视频：file:// 会被 Chromium 的 URL 安全检查拒掉 */
const http = require('http');
function serve(file) {
  return new Promise(resolve => {
    const buf = fs.readFileSync(file);
    const srv = http.createServer((req, res) => {
      res.writeHead(200, {
        'Content-Type': 'video/mp4', 'Accept-Ranges': 'bytes',
        'Content-Length': buf.length
      });
      res.end(req.method === 'HEAD' ? undefined : buf);
    });
    srv.listen(0, '127.0.0.1', () => resolve({ port: srv.address().port, close: () => srv.close() }));
  });
}

(async () => {
  fs.mkdirSync(outDir, { recursive: true });
  const svr = await serve(path.resolve(video));
  const src = 'http://127.0.0.1:' + svr.port + '/v.mp4';
  const b = await chromium.launch({ executablePath: CHROME });
  const p = await b.newPage({ viewport: { width: 900, height: 700 } });
  await p.goto('http://127.0.0.1:' + svr.port + '/');

  const meta = await p.evaluate(async ([src, step]) => {
    const v = document.createElement('video');
    v.src = src; v.muted = true; v.playsInline = true;
    document.body.appendChild(v);
    await new Promise((res, rej) => {
      v.onloadedmetadata = res;
      v.onerror = () => rej(new Error('解码失败：' + (v.error && v.error.message)));
      setTimeout(() => rej(new Error('加载超时')), 15000);
    });
    return { dur: v.duration, w: v.videoWidth, h: v.videoHeight };
  }, [src, every]);
  console.log('时长', meta.dur.toFixed(2), '秒', meta.w + 'x' + meta.h);

  const stamps = [];
  for (let t = 0.2; t < meta.dur; t += every) stamps.push(+t.toFixed(2));

  const frames = await p.evaluate(async ([src, list]) => {
    const v = document.createElement('video');
    v.src = src; v.muted = true; v.playsInline = true;
    document.body.appendChild(v);
    await new Promise(res => { v.onloadedmetadata = res; });
    const c = document.createElement('canvas');
    c.width = v.videoWidth; c.height = v.videoHeight;
    const g = c.getContext('2d');
    const out = [];
    for (const t of list) {
      v.currentTime = t;
      await new Promise(res => { v.onseeked = res; });
      g.drawImage(v, 0, 0);
      out.push({ t: t, data: c.toDataURL('image/png') });
    }
    return out;
  }, [src, stamps]);

  frames.forEach((f, i) => {
    const name = path.join(outDir, 'f' + String(i).padStart(3, '0') + '_' + f.t + 's.png');
    fs.writeFileSync(name, Buffer.from(f.data.split(',')[1], 'base64'));
  });
  console.log('已抽取', frames.length, '帧 →', outDir);
  await b.close();
  svr.close();
})();
