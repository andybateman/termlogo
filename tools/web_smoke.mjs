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
// It starts Python in the page and works through the page as a person would: the turtle at
// start, every example, the command line, labels, downloads, Open and Save, sharing, the
// canvas following the window, coordinates, Help, typing into a running program, Stop and
// Escape, runaway recursion and the Terrapin colours. Then it repeats the essentials with
// shared memory switched off (?nocoi), and checks a page whose Python cannot start. It exits
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

async function open(query = '', viewport = { width: 1280, height: 860 }) {
  const context = await browser.newContext({ viewport, acceptDownloads: true });
  await context.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: new URL(base).origin });
  const page = await context.newPage();
  const problems = [];
  page.on('console', (m) => { if (m.type() === 'error') problems.push('console: ' + m.text()); });
  page.on('pageerror', (e) => problems.push('pageerror: ' + e.message));
  page.on('dialog', (dialog) => dialog.accept()); // "replace your program?" questions
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
      await page.waitForTimeout(300);
    },
    async type(line) { await page.fill('#line', line); await page.press('#line', 'Enter'); },
    log: () => page.textContent('#log'),
    status: () => page.textContent('#status'),
    size: () => page.evaluate(() => [document.getElementById('stage').width, document.getElementById('stage').height]),
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
async function downloadText(download) {
  const chunks = [];
  for await (const chunk of await download.createReadStream()) chunks.push(chunk);
  return Buffer.concat(chunks);
}

// ============================== shared memory on ==============================
{
  const app = await open();
  const { page } = app;
  step('page is cross-origin isolated (service worker)', await page.evaluate(() => self.crossOriginIsolated));
  const build = await page.textContent('#build');
  step('the page shows its version', /^v\d+\.\d+\.\d+ · /.test(build), build);

  // the canvas fills its box, and the turtle is there before anything runs
  const [w, h] = await app.size();
  const box = await page.evaluate(() => { const r = document.getElementById('stage-wrap').getBoundingClientRect(); return [Math.floor(r.width), Math.floor(r.height)]; });
  step('the canvas matches its box', Math.abs(w - box[0]) <= 2 && Math.abs(h - box[1]) <= 2, `canvas ${w}x${h}, box ${box}`);
  const turtle = await page.evaluate(() => {
    const c = document.getElementById('stage');
    const d = c.getContext('2d').getImageData(c.width / 2 - 12, c.height / 2 - 12, 24, 24).data;
    let green = 0;
    for (let i = 0; i < d.length; i += 4) if (d[i + 1] > 150 && d[i] < 80) green++;
    return green;
  });
  step('the turtle is shown before anything runs', turtle > 10, `green pixels ${turtle}`);
  step('no zoom chip at one step per pixel', !(await page.isVisible('#zoom')));

  await page.selectOption('#speed', '0');
  await page.click('#run'); await app.idle();
  step('default program draws, no error', (await app.lit()) > 5000 && (await app.log()) === '', `lit=${await app.lit()}`);

  // examples run when chosen
  const examples = await page.$$eval('#examples option', (o) => o.slice(1).map((x) => x.textContent));
  step('the example menu is filled', examples.length >= 8, examples.join(', '));
  for (const name of examples) {
    await page.click('#reset'); await app.idle();
    await page.selectOption('#examples', { label: name }); await app.idle();
    const text = await app.log();
    step('example ' + name, text.startsWith(`Running the ${name} example.`) && !/error|doesn't|not/i.test(text) && (await app.lit()) > 300,
      `lit=${await app.lit()} ${JSON.stringify(text.slice(0, 80))}`);
  }

  // the zoom chip shows a FITWINDOW scale, and a click puts one step per pixel back
  step('the zoom chip shows after an example', await page.isVisible('#zoom'), await page.textContent('#zoom'));
  await page.click('#zoom'); await app.idle();
  step('the zoom chip goes back to SETSCALE 1', !(await page.isVisible('#zoom')) && (await app.log()).includes('SETSCALE 1'));

  await page.click('#reset'); await app.idle();
  await app.type('print 6 * 7'); await app.idle();
  step('command line prints', (await app.log()).includes('42'));
  await app.type('fd'); await app.idle();
  step('errors are shown', (await app.log()).includes('Not enough inputs to fd'));
  step('the status bar repeats the error', (await app.status()).includes('Not enough inputs to fd')
    && (await page.getAttribute('#status', 'class')).includes('err'), await app.status());
  await page.focus('#line'); await page.press('#line', 'ArrowUp');
  step('history recalls', (await page.inputValue('#line')) === 'fd');
  await page.click('#clear-output');
  step('Clear empties the output', (await app.log()) === '');

  // coordinates under the pointer
  const stageBox = await page.locator('#stage').boundingBox();
  await page.mouse.move(stageBox.x + stageBox.width / 2, stageBox.y + stageBox.height / 2);
  const coords = await page.textContent('#coords');
  step('pointer coordinates at the centre', /^x -?[01]\s+y -?[01]$/.test(coords.trim()), JSON.stringify(coords));

  // labels reach the PNG and SVG downloads; the turtle does not
  await page.click('#reset'); await app.idle();
  await app.type('setpc 4 pu setxy -50 20 label "hello'); await app.idle();
  const [png] = await Promise.all([page.waitForEvent('download'), page.click('.export[data-kind=png]')]);
  const counts = await page.evaluate(async (b64) => {
    const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
    const bitmap = await createImageBitmap(new Blob([bytes], { type: 'image/png' }));
    const c = new OffscreenCanvas(bitmap.width, bitmap.height); const x = c.getContext('2d'); x.drawImage(bitmap, 0, 0);
    const d = x.getImageData(0, 0, c.width, c.height).data; let red = 0, green = 0;
    for (let i = 0; i < d.length; i += 4) { if (d[i] > 200 && d[i + 1] < 60) red++; if (d[i + 1] > 200 && d[i] < 60) green++; }
    return { red, green, width: c.width };
  }, (await downloadText(png)).toString('base64'));
  step('PNG download has the label and no turtle', counts.red > 20 && counts.green === 0, JSON.stringify(counts));
  const [svg] = await Promise.all([page.waitForEvent('download'), page.click('.export[data-kind=svg]')]);
  step('SVG download has the label text', (await downloadText(svg)).toString().includes('>hello</text>'));
  await page.click('#clear'); await app.idle();
  await page.click('.export[data-kind=stl]'); await page.waitForTimeout(500);
  step('empty stencil refused with a message', (await app.log()).includes('Nothing to export'));
  await app.type('pd setpensize 3 repeat 4 [fd 40 rt 90]'); await app.idle();
  const [stl] = await Promise.all([page.waitForEvent('download'), page.click('.export[data-kind=stl]')]);
  step('STL download', stl.suggestedFilename().endsWith('.stl'));

  // Save and Open
  await page.fill('#code', 'to sq repeat 4 [fd 40 rt 90] end\nsq\n');
  const [saved] = await Promise.all([page.waitForEvent('download'), page.click('#save')]);
  step('Save downloads the program', saved.suggestedFilename() === 'program.logo'
    && (await downloadText(saved)).toString() === 'to sq repeat 4 [fd 40 rt 90] end\nsq\n');
  await page.setInputFiles('#open-file', { name: 'mine.logo', mimeType: 'text/plain', buffer: Buffer.from('print "opened\n') });
  await page.waitForTimeout(300);
  step('Open loads a file into the editor', (await page.inputValue('#code')) === 'print "opened\n' && (await app.log()).includes('Opened mine.logo'));

  // the canvas follows the window and the Expand button
  const before = await app.size();
  await page.setViewportSize({ width: 1500, height: 940 }); await page.waitForTimeout(700); await app.idle();
  const after = await app.size();
  step('the canvas grows with the window', after[0] > before[0] && after[1] > before[1], `${before} -> ${after}`);
  await page.click('#expand'); await page.waitForTimeout(700); await app.idle();
  const expanded = await app.size();
  step('Expand gives the canvas the whole width', expanded[0] >= 1490 && (await page.textContent('#expand')).includes('Show editor'), `${expanded}`);
  await page.click('#expand'); await page.waitForTimeout(700); await app.idle();
  step('Show editor brings the editor back', await page.isVisible('#code'));

  // the divider between the editor and the canvas
  const narrow = await app.size();
  const bar = await page.locator('#splitter').boundingBox();
  await page.mouse.move(bar.x + bar.width / 2, bar.y + bar.height / 2);
  await page.mouse.down();
  await page.mouse.move(bar.x - 150, bar.y + bar.height / 2, { steps: 5 });
  await page.mouse.up();
  await page.waitForTimeout(700); await app.idle();
  const wider = await app.size();
  step('dragging the divider gives the canvas more room', wider[0] >= narrow[0] + 140, `${narrow} -> ${wider}`);
  const kept = await page.evaluate(() => localStorage.getItem('termlogo.editor-width'));
  await page.focus('#splitter'); await page.keyboard.press('ArrowRight');
  const nudged = await page.evaluate(() => localStorage.getItem('termlogo.editor-width'));
  step('the divider remembers its place and moves with the arrow keys', Number(kept) > 10 && Number(nudged) > Number(kept), `${kept} -> ${nudged}`);
  await page.dblclick('#splitter'); await page.waitForTimeout(700); await app.idle();
  step('double-clicking the divider puts it back', Math.abs((await app.size())[0] - narrow[0]) <= 2, `${await app.size()}`);

  // full screen
  await page.click('#fullscreen'); await page.waitForTimeout(700); await app.idle();
  const full = await app.size();
  step('full screen fills the window with the canvas', await page.evaluate(() => document.fullscreenElement?.classList.contains('canvas-pane')) && full[0] >= 1490, `${full}`);
  await page.click('#fullscreen'); await page.waitForTimeout(700); await app.idle();
  step('the same button leaves full screen', await page.evaluate(() => !document.fullscreenElement));

  // Help
  await page.click('#help-open');
  await page.waitForFunction(() => document.querySelectorAll('#help-list dt').length > 100);
  const all = await page.locator('#help-list dt').count();
  await page.fill('#help-filter', 'colour');
  const some = await page.locator('#help-list dt').count();
  step('Help lists commands and the search narrows them', all > 200 && some > 3 && some < 40, `${all} -> ${some}`);
  await page.click('#try-sample'); await app.idle();
  step('the Help sample runs in the editor', !(await page.isVisible('#help')) && (await page.inputValue('#code')).startsWith('repeat 4 [forward 100'));

  // typing into a running program
  await page.click('#reset'); await app.idle();
  await app.type('print readword');
  step('READWORD waits for a line', await waitStatus(app, 'Waiting for you to type'));
  await page.fill('#line', 'hello there'); await page.press('#line', 'Enter'); await app.idle();
  step('READWORD returns what was typed', (await app.log()).includes('hello there\n'));
  await app.type('show readlist');
  await waitStatus(app, 'Waiting for you to type');
  await page.fill('#line', 'a b [c d]'); await page.press('#line', 'Enter'); await app.idle();
  step('READLIST returns a list', (await app.log()).includes('[a b [c d]]'));
  await app.type('print readchar');
  step('READCHAR waits for a key', await waitStatus(app, 'Waiting for a key'));
  await page.keyboard.press('k'); await app.idle();
  step('READCHAR returns the key', (await app.log()).endsWith('k\n'));
  await app.type('print keyp'); await app.idle();
  step('KEYP is false with nothing pressed', (await app.log()).endsWith('false\n'));

  // Stop keeps the workspace; Escape stops too
  await app.type('make "keep 42'); await app.idle();
  await page.selectOption('#speed', '5');
  await app.type('forever [fd 5 rt 7]');
  await page.waitForTimeout(1500);
  step('forever animates', (await app.lit()) > 50 && (await page.isDisabled('#run')));
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
  // runaway recursion is an error, not a dead page
  for (const prog of ['to r1 :n output 1 + r1 :n + 1 end print r1 1', 'to r2 repeat 1 [r2] end r2']) {
    await app.type(prog); await app.idle();
    step(`runaway recursion: ${prog.slice(0, 18)}…`, (await app.log()).trim().endsWith('Stack overflow'));
  }
  await app.type('print 1 + 1'); await app.idle();
  step('Python still works after a stack overflow', (await app.log()).endsWith('2\n'));

  // sharing
  await page.fill('#code', 'to sq fd 30 rt 90 end\nrepeat 4 [sq]\nprint "shared');
  await page.click('#share'); await page.waitForTimeout(300);
  const link = await page.evaluate(() => navigator.clipboard.readText()).catch(() => null)
    ?? (await app.log()).match(/https?:\S+#z=\S+/)?.[0];
  step('Share makes a link holding the program', /#z=/.test(link || ''), (link || '').slice(-30));
  const other = await open('');
  await other.page.goto(link.replace('#', '&y=1#')); await other.ready();
  step('a shared link opens the same program', (await other.page.inputValue('#code')).includes('repeat 4 [sq]') && (await other.log()).includes('Loaded a shared program'));
  step('the shared program leaves the address', !other.page.url().includes('#z='), other.page.url());
  await other.page.context().close();

  // Terrapin and speed
  await page.selectOption('#colours', 'terrapin'); await page.waitForTimeout(500); await app.idle();
  await app.type('print pencolour'); await app.idle();
  step('Terrapin mode', (await app.log()).includes('0 0 0 1'));
  await page.selectOption('#colours', 'ucblogo'); await page.waitForTimeout(500); await app.idle();
  await page.selectOption('#speed', '8');
  let started = Date.now();
  await app.type('cs repeat 360 [fd 2 rt 1]'); await app.idle();
  console.log('INFO speed-8 circle took', Date.now() - started - 500, 'ms');
  await page.selectOption('#speed', '5');
  started = Date.now();
  await app.type('cs repeat 4 [fd 100 rt 90]'); await app.idle();
  console.log('INFO speed-5 square took', Date.now() - started - 500, 'ms (about 1900 ms at the set pace)');
  step('no console errors', app.problems.length === 0, app.problems.join('; '));
  await page.context().close();
}

// ============================== a small laptop ==============================
{
  const app = await open('', { width: 1024, height: 700 });
  const toolbar = await app.page.evaluate(() => document.querySelector('.toolbar').getBoundingClientRect().height);
  step('small laptop: the toolbar is one row', toolbar < 60, `${toolbar}px`);
  step('small laptop: the Expand button keeps its name', (await app.page.getAttribute('#expand', 'aria-label')) === 'Expand canvas');
  await app.page.context().close();
}

// ============================== a phone-sized screen ==============================
{
  const app = await open('', { width: 390, height: 844 });
  const { page } = app;
  const [w] = await app.size();
  const toolbar = await page.evaluate(() => document.querySelector('.toolbar').getBoundingClientRect().height);
  const masthead = await page.evaluate(() => document.querySelector('.masthead').getBoundingClientRect().height);
  step('phone: the canvas spans the screen; header and toolbar are a row each', w >= 380 && toolbar < 60 && masthead < 50, `canvas width ${w}, toolbar ${toolbar}px, header ${masthead}px`);
  const uncovered = await page.evaluate(() => [...document.querySelectorAll('.statusbar .export')].every((button) => {
    button.scrollIntoView({ block: 'center' });
    const r = button.getBoundingClientRect();
    return document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2) === button;
  }));
  step('phone: nothing covers the bar under the canvas', uncovered);
  await page.selectOption('#speed', '0');
  await page.click('#run'); await app.idle();
  step('phone: the default program fits', (await app.lit()) > 2000);
  step('phone: no console errors', app.problems.length === 0, app.problems.join('; '));
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
  const context = await browser.newContext({ viewport: { width: 1280, height: 860 } });
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
