// Browser smoke test for the web version. Not part of the unittest suite: it needs Node,
// a Chromium and the playwright-core package.
//
//   python3 tools/build_web.py [--bundle-pyodide] && (python3 -m http.server 8123 -d dist/web &)
//   npm install playwright-core
//   CHROME=/path/to/chromium node tools/web_smoke.mjs [http://localhost:8123/]
//
// It starts Python in the page, runs every example, uses the command line, label,
// exports, speed, Stop and the Terrapin colour mode, and exits non-zero on any failure.
import { chromium } from 'playwright-core';
const url = process.argv[2] || 'http://localhost:8123/';
let failed = 0;
const browser = await chromium.launch({ executablePath: process.env.CHROME, args: ['--no-sandbox', '--disable-gpu'] });
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, acceptDownloads: true });
const page = await ctx.newPage();
const problems = [];
page.on('console', (m) => { if (m.type() === 'error') problems.push('console: ' + m.text()); });
page.on('pageerror', (e) => problems.push('pageerror: ' + e.message));
const ready = () => page.waitForFunction(() => document.getElementById('status').textContent.startsWith('Ready'), null, { timeout: 120000 });
const idle = async () => { await page.waitForTimeout(200); await page.waitForFunction(() => !document.getElementById('run').disabled, null, { timeout: 120000 }); await page.waitForTimeout(250); };
const lit = () => page.evaluate(() => { const c = document.getElementById('stage'); const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let n = 0; for (let i = 0; i < d.length; i += 4) if (d[i] || d[i+1] || d[i+2]) n++; return n; });
const logText = () => page.textContent('#log');
const step = (name, ok, extra = '') => {
  if (!ok) failed++;
  console.log(ok ? 'PASS' : 'FAIL', name, extra);
};

await page.goto(url); await ready();

// 1. default program, instant
await page.selectOption('#speed', '0'); await page.click('#run'); await idle();
step('default program draws and has no error', (await lit()) > 5000 && (await logText()) === '', `lit=${await lit()} log=${JSON.stringify(await logText())}`);

// 2. every example runs without an error
const examples = await page.$$eval('#examples option', (o) => o.slice(1).map((x) => x.textContent));
for (const name of examples) {
  await page.selectOption('#examples', { label: name });
  await page.click('#clear'); await idle();
  await page.click('#reset'); await idle();
  await page.click('#run'); await idle();
  const text = await logText();
  step('example ' + name, text === '' && (await lit()) > 100, `lit=${await lit()} log=${JSON.stringify(text.slice(0, 80))}`);
}

// 3. REPL line, print, label, history
await page.click('#reset'); await idle();
await page.fill('#line', 'print 6 * 7'); await page.press('#line', 'Enter'); await idle();
step('repl prints', (await logText()).includes('42'), JSON.stringify(await logText()));
await page.fill('#line', 'setpc 4 pu setxy -50 20 label "hello'); await page.press('#line', 'Enter'); await idle();
await page.waitForTimeout(200);
const red = await page.evaluate(() => { const c = document.getElementById('stage'); const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let n = 0; for (let i = 0; i < d.length; i += 4) if (d[i] > 200 && d[i+1] < 60) n++; return n; });
step('label drawn in red text', red > 20, 'red=' + red);
await page.focus('#line'); await page.press('#line', 'ArrowUp');
step('history recalls', (await page.inputValue('#line')).includes('label'));

// 4. errors
await page.fill('#line', 'fd'); await page.press('#line', 'Enter'); await idle();
step('error is shown', (await logText()).includes('Not enough inputs to fd'));

// 5. exports download
for (const kind of ['png', 'svg']) {
  const [dl] = await Promise.all([page.waitForEvent('download'), page.click(`.export[data-kind=${kind}]`)]);
  const path = await dl.path(); const fs = await import('fs'); const size = fs.statSync(path).size;
  step('download ' + kind, dl.suggestedFilename().endsWith(kind) && size > 100, `${dl.suggestedFilename()} ${size} bytes`);
}
await page.click('#clear'); await idle();
await page.click('.export[data-kind=stl]'); await page.waitForTimeout(500);
step('empty stencil refused with a message', (await logText()).includes('Nothing to export'));
await page.fill('#line', 'pd setpensize 3 repeat 4 [fd 40 rt 90]'); await page.press('#line', 'Enter'); await idle();
const [dl] = await Promise.all([page.waitForEvent('download'), page.click('.export[data-kind=stl]')]);
const fs = await import('fs'); step('download stl', fs.statSync(await dl.path()).size > 200, `${fs.statSync(await dl.path()).size} bytes`);

// 6. animation: frames arrive while it runs, and stop works
await page.click('#reset'); await idle();
await page.selectOption('#speed', '5');
await page.fill('#line', 'forever [fd 5 rt 7]'); await page.press('#line', 'Enter');
await page.waitForTimeout(1500);
const midLit = await lit();
step('forever animates (picture grows while running)', midLit > 50 && (await page.isDisabled('#run')), 'lit=' + midLit);
const t = Date.now();
await page.click('#stop'); await ready(); await idle();
step('stop restarts the worker', (await logText()).includes('Stopped'), `back after ${Date.now() - t} ms`);

// 7. after stop, a run still works
await page.selectOption('#speed', '0'); await page.fill('#line', 'print 1 + 1'); await page.press('#line', 'Enter'); await idle();
step('works after stop', (await logText()).includes('2'));

// 8. terrapin colours
await page.selectOption('#colours', 'terrapin'); await page.waitForTimeout(500); await idle();
await page.fill('#line', 'print pencolour'); await page.press('#line', 'Enter'); await idle();
step('terrapin mode', (await logText()).includes('0 0 0 1'), JSON.stringify((await logText()).slice(-40)));

// 9. timing for a heavy animation frame rate
await page.selectOption('#colours', 'ucblogo'); await page.waitForTimeout(500); await idle();
await page.selectOption('#speed', '8');
await page.fill('#line', 'repeat 360 [fd 2 rt 1]'); const t2 = Date.now(); await page.press('#line', 'Enter'); await idle();
console.log('INFO circle at fast speed took', Date.now() - t2, 'ms');
step('no console errors', problems.length === 0, problems.join('; '));
await browser.close();
process.exit(failed ? 1 : 0);
