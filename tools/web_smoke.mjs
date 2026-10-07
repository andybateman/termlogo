// Browser smoke test for the web version. Not part of the unittest suite: it needs Node,
// a Chromium and the playwright-core package.
//
//   python3 tools/build_web.py [--bundle-pyodide] && (python3 -m http.server 8123 -d dist/web &)
//   npm install playwright-core
//   CHROME=/path/to/chromium node tools/web_smoke.mjs [http://localhost:8123/] [more query]
//
// A second argument is added to the address as a query string, for example
// `pyodide=http://localhost:8124/` to load Pyodide from another server.
//
// It starts Python in the page, runs every example, uses the command line, label, exports,
// speed, sharing, typing into a running program, Stop and Escape, and the Terrapin colour
// mode, and then repeats the essentials with shared memory switched off (?nocoi). It exits
// non-zero on any failure.
import { chromium } from 'playwright-core';

const base = process.argv[2] || 'http://localhost:8123/';
const extra = process.argv[3] ? `&${process.argv[3]}` : '';
let failed = 0;
const step = (name, ok, detail = '') => {
  if (!ok) failed++;
  console.log(ok ? 'PASS' : 'FAIL', name, detail);
};

const browser = await chromium.launch({
  executablePath: process.env.CHROME,
  args: ['--no-sandbox', '--disable-gpu'],
});

async function open(query = '') {
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, acceptDownloads: true });
  const page = await context.newPage();
  const problems = [];
  page.on('console', (m) => { if (m.type() === 'error') problems.push('console: ' + m.text()); });
  page.on('pageerror', (e) => problems.push('pageerror: ' + e.message));
  const api = {
    page, problems,
    async ready() {
      for (let attempt = 0; attempt < 4; attempt++) {
        try {
          await page.waitForFunction(() => document.getElementById('status').textContent.startsWith('Ready'), null, { timeout: 120000 });
          return;
        } catch (error) { // the first visit reloads once so the service worker can take over
          if (!/destroyed|navigat|closed/i.test(String(error))) throw error;
          await page.waitForLoadState();
        }
      }
    },
    async idle() {
      await page.waitForTimeout(200);
      await page.waitForFunction(() => !document.getElementById('run').disabled, null, { timeout: 120000 });
      await page.waitForTimeout(250);
    },
    async type(line) { await page.fill('#line', line); await page.press('#line', 'Enter'); },
    log: () => page.textContent('#log'),
    status: () => page.textContent('#status'),
    lit: () => page.evaluate(() => {
      const c = document.getElementById('stage');
      const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
      let n = 0;
      for (let i = 0; i < d.length; i += 4) if (d[i] || d[i + 1] || d[i + 2]) n++;
      return n;
    }),
  };
  await page.goto(`${base}?x=1${extra}${query}`);
  await api.ready();
  return api;
}
const waitStatus = (app, prefix) => app.page.waitForFunction(
  (p) => document.getElementById('status').textContent.startsWith(p), prefix, { timeout: 20000 },
).then(() => true, () => false);

// ============================== shared memory on ==============================
{
  const app = await open();
  const { page } = app;
  step('page is cross-origin isolated (service worker)', await page.evaluate(() => self.crossOriginIsolated));

  await page.selectOption('#speed', '0');
  await page.click('#run'); await app.idle();
  step('default program draws, no error', (await app.lit()) > 5000 && (await app.log()) === '', `lit=${await app.lit()}`);

  const examples = await page.$$eval('#examples option', (o) => o.slice(1).map((x) => x.textContent));
  for (const name of examples) {
    await page.selectOption('#examples', { label: name });
    await page.click('#reset'); await app.idle();
    await page.click('#run'); await app.idle();
    const text = await app.log();
    step('example ' + name, text === '' && (await app.lit()) > 100, `lit=${await app.lit()} ${text.slice(0, 60)}`);
  }

  await page.click('#reset'); await app.idle();
  await app.type('print 6 * 7'); await app.idle();
  step('command line prints', (await app.log()).includes('42'));
  await app.type('fd'); await app.idle();
  step('errors are shown', (await app.log()).includes('Not enough inputs to fd'));
  await page.focus('#line'); await page.press('#line', 'ArrowUp');
  step('history recalls', (await page.inputValue('#line')).includes('fd'));

  // labels reach the PNG and SVG downloads; the turtle does not
  await page.click('#reset'); await app.idle();
  await app.type('setpc 4 pu setxy -50 20 label "hello'); await app.idle();
  const [png] = await Promise.all([page.waitForEvent('download'), page.click('.export[data-kind=png]')]);
  const chunks = []; for await (const chunk of await png.createReadStream()) chunks.push(chunk);
  const counts = await page.evaluate(async (b64) => {
    const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
    const bitmap = await createImageBitmap(new Blob([bytes], { type: 'image/png' }));
    const c = new OffscreenCanvas(bitmap.width, bitmap.height); const x = c.getContext('2d'); x.drawImage(bitmap, 0, 0);
    const d = x.getImageData(0, 0, c.width, c.height).data; let red = 0, green = 0;
    for (let i = 0; i < d.length; i += 4) { if (d[i] > 200 && d[i + 1] < 60) red++; if (d[i + 1] > 200 && d[i] < 60) green++; }
    return { red, green, width: c.width };
  }, Buffer.concat(chunks).toString('base64'));
  step('PNG download has the label and no turtle', counts.red > 20 && counts.green === 0, JSON.stringify(counts));
  const [svg] = await Promise.all([page.waitForEvent('download'), page.click('.export[data-kind=svg]')]);
  const svgText = Buffer.concat(await (async () => { const out = []; for await (const c of await svg.createReadStream()) out.push(c); return out; })()).toString();
  step('SVG download has the label text', svgText.includes('>hello</text>'), `${svgText.length} bytes`);

  await page.click('#clear'); await app.idle();
  await page.click('.export[data-kind=stl]'); await page.waitForTimeout(500);
  step('empty stencil refused with a message', (await app.log()).includes('Nothing to export'));
  await app.type('pd setpensize 3 repeat 4 [fd 40 rt 90]'); await app.idle();
  const [stl] = await Promise.all([page.waitForEvent('download'), page.click('.export[data-kind=stl]')]);
  step('STL download', stl.suggestedFilename().endsWith('.stl'));

  // typing into a running program
  await page.click('#reset'); await app.idle();
  await app.type('print readword');
  step('READWORD waits for a line', await waitStatus(app, 'Waiting for you to type'));
  await page.fill('#line', 'hello there'); await page.press('#line', 'Enter'); await app.idle();
  step('READWORD returns what was typed', (await app.log()).includes('hello there\n'), JSON.stringify((await app.log()).slice(-30)));
  await app.type('show readlist');
  await waitStatus(app, 'Waiting for you to type');
  await page.fill('#line', 'a b [c d]'); await page.press('#line', 'Enter'); await app.idle();
  step('READLIST returns a list', (await app.log()).includes('[a b [c d]]'));
  await app.type('print readchar');
  step('READCHAR waits for a key', await waitStatus(app, 'Waiting for a key'));
  await page.keyboard.press('k'); await app.idle();
  step('READCHAR returns the key', (await app.log()).endsWith('k\n'), JSON.stringify((await app.log()).slice(-12)));
  await app.type('print keyp'); await app.idle();
  step('KEYP is false with nothing pressed', (await app.log()).endsWith('false\n'));

  // Stop keeps the workspace; Escape stops too
  await app.type('make "keep 42'); await app.idle();
  await page.selectOption('#speed', '5');
  await app.type('forever [fd 5 rt 7]');
  await page.waitForTimeout(1500);
  const mid = await app.lit();
  step('forever animates', mid > 50 && (await page.isDisabled('#run')), `lit=${mid}`);
  const t = Date.now();
  await page.click('#stop'); await app.idle();
  step('Stop interrupts quickly and says so', (await app.log()).includes('Stopped!') && Date.now() - t < 3000, `${Date.now() - t} ms`);
  await page.selectOption('#speed', '0');
  await app.type('print :keep'); await app.idle();
  step('the workspace survives Stop', (await app.log()).endsWith('42\n'));
  await page.selectOption('#speed', '5');
  await app.type('forever [fd 5 rt 7]'); await page.waitForTimeout(800);
  await page.evaluate(() => document.activeElement.blur());
  await page.keyboard.press('Escape'); await app.idle();
  step('Escape stops a program', (await app.log()).split('Stopped!').length === 3);
  await page.selectOption('#speed', '0');
  await app.type('wait 30 print "after'); await app.idle();
  step('WAIT works and can finish', (await app.log()).endsWith('after\n'));

  // sharing
  await page.fill('#code', 'to sq fd 30 rt 90 end\nrepeat 4 [sq]\nprint "shared');
  await page.click('#share'); await page.waitForTimeout(300);
  const url = page.url();
  step('Share puts the program in the address', /#z=/.test(url), url.slice(-30));
  const other = await open('');
  await other.page.goto(url.replace('#', '&y=1#')); await other.ready();
  step('a shared link opens the same program', (await other.page.inputValue('#code')).includes('repeat 4 [sq]') && (await other.log()).includes('Loaded a shared program'));
  await other.page.context().close();

  // Terrapin and speed
  await page.selectOption('#colours', 'terrapin'); await page.waitForTimeout(500); await app.idle();
  await app.type('print pencolour'); await app.idle();
  step('Terrapin mode', (await app.log()).includes('0 0 0 1'));
  await page.selectOption('#colours', 'ucblogo'); await page.waitForTimeout(500); await app.idle();
  await page.selectOption('#speed', '8');
  let started = Date.now();
  await app.type('cs repeat 360 [fd 2 rt 1]'); await app.idle();
  console.log('INFO speed-8 circle took', Date.now() - started - 450, 'ms');
  await page.selectOption('#speed', '5');
  started = Date.now();
  await app.type('cs repeat 4 [fd 100 rt 90]'); await app.idle();
  console.log('INFO speed-5 square took', Date.now() - started - 450, 'ms (about 1900 ms at the set pace)');
  step('no console errors', app.problems.length === 0, app.problems.join('; '));
  await page.context().close();
}

// ============================== shared memory off ==============================
{
  const app = await open('&nocoi');
  const { page } = app;
  step('fallback: not isolated', !(await page.evaluate(() => self.crossOriginIsolated)));
  await page.selectOption('#speed', '0');
  await app.type('print readword'); await app.idle();
  step('fallback: input commands see the end of input', (await app.log()) === '? print readword\n\n');
  await page.selectOption('#speed', '5');
  await app.type('forever [fd 5 rt 7]'); await page.waitForTimeout(800);
  await page.click('#stop'); await app.ready(); await app.idle();
  step('fallback: Stop restarts Python', (await app.log()).includes('Stopped. The workspace was reset.'));
  await page.selectOption('#speed', '0');
  await app.type('print 1 + 1'); await app.idle();
  step('fallback: works after Stop', (await app.log()).endsWith('2\n'));
  step('fallback: no console errors', app.problems.length === 0, app.problems.join('; '));
  await page.context().close();
}

// ============================== Python cannot start ==============================
{
  // With nowhere to get Pyodide from, the page should try once more without shared memory,
  // remember that, and then say plainly that Python could not start (no endless reloads).
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();
  await page.goto(`${base}?pyodide=http://127.0.0.1:1/`);
  let message = '';
  for (let attempt = 0; attempt < 8 && !message.includes('Could not start Python'); attempt++) {
    await page.waitForTimeout(2500);
    try { message = await page.textContent('#status'); } catch { /* mid-reload */ }
  }
  step('failure to start is reported', message.includes('Could not start Python'), message);
  step('the retry dropped shared memory for good',
    page.url().includes('nocoi=1') && (await page.evaluate(() => localStorage.getItem('termlogo.nocoi'))) === '1', page.url());
  step('buttons stay disabled', await page.isDisabled('#run'));
  await context.close();
}

await browser.close();
process.exit(failed ? 1 : 0);
