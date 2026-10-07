// The page: editor, command line, canvas and buttons. The Logo engine itself runs in
// worker.js; this file sends it programs and draws what comes back.
const $ = (id) => document.getElementById(id);
const params = new URLSearchParams(location.search);

// Where Pyodide comes from: ?pyodide=URL, else the copy beside the page if the build bundled
// one (see config.json), else the jsDelivr copy of the npm package.
const DEFAULT_PYODIDE_VERSION = '314.0.7';
async function pyodideBase() {
  let config = {};
  try {
    config = await (await fetch('config.json')).json();
  } catch { /* no config: use the defaults */ }
  const version = config.pyodideVersion || DEFAULT_PYODIDE_VERSION;
  const base = params.get('pyodide')
    || (config.bundled ? './pyodide/' : `https://cdn.jsdelivr.net/npm/pyodide@${version}/`);
  return new URL(base, location.href).href.replace(/\/?$/, '/');
}

const SIZE = { width: 800, height: 600 };
const STORE_CODE = 'termlogo.code';
const STORE_NO_COI = 'termlogo.nocoi'; // set when shared memory stopped Python from starting
const DEFAULT_CODE = `; Press Run, or Ctrl+Enter.
to flower :size
  repeat 36 [
    setpc 1 + remainder repcount 15
    repeat 4 [fd :size rt 90]
    rt 10
  ]
end
cs ht
flower 140
`;

const stage = $('stage');
const ctx = stage.getContext('2d');
const log = $('log');
const ui = {
  run: $('run'), stop: $('stop'), clear: $('clear'), reset: $('reset'), share: $('share'),
  line: $('line'), code: $('code'), status: $('status'),
  exports: [...document.querySelectorAll('.export')],
};

let worker = null;
let ready = false;
let running = false;
let shared = null; // shared memory with the worker, when the page is cross-origin isolated
const commandHistory = [];
let historyAt = 0;

// ---- small helpers ---------------------------------------------------------
function remember(key, value) {
  try { localStorage.setItem(key, value); } catch { /* private mode: fine */ }
}
function recall(key) {
  try { return localStorage.getItem(key); } catch { return null; }
}
function say(text, className) {
  const span = document.createElement('span');
  if (className) span.className = className;
  span.textContent = text;
  log.append(span);
  while (log.childNodes.length > 1500) log.firstChild.remove();
  log.scrollTop = log.scrollHeight;
}
function setStatus(text) { ui.status.textContent = text; }
function refreshButtons() {
  const idle = ready && !running;
  ui.run.disabled = ui.clear.disabled = ui.reset.disabled = !idle;
  ui.line.disabled = !(idle || (running && shared));
  ui.exports.forEach((b) => { b.disabled = !idle; });
  ui.stop.disabled = !running;
}
function saveBlob(blob, name) {
  const url = URL.createObjectURL(blob);
  const link = Object.assign(document.createElement('a'), { href: url, download: name });
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}

// ---- the picture --------------------------------------------------------------
// The engine keeps the drawing as pixels. It sends only the rows that changed; they are
// patched into `layer`, which holds the picture without the turtle. The turtle and any
// LABEL text are drawn over a copy of it for display, and over another copy for PNG
// downloads (without the turtle).
const layer = Object.assign(document.createElement('canvas'), SIZE);
const layerCtx = layer.getContext('2d');
let labels = [];
let marker = [];
let paintQueued = false;

function applyRows(rgba, first, last) {
  if (!rgba.length || last < first) return;
  const pixels = new Uint8ClampedArray(rgba.buffer, rgba.byteOffset, rgba.byteLength);
  layerCtx.putImageData(new ImageData(pixels, SIZE.width, last - first + 1), 0, first);
}
function drawLabels(target) {
  target.font = '14px ui-monospace, Menlo, Consolas, monospace';
  target.textBaseline = 'middle';
  for (const [x, y, text, r, g, b] of labels) {
    target.fillStyle = `rgb(${r}, ${g}, ${b})`;
    target.fillText(text, x, y);
  }
}
function drawTurtle(target) {
  if (!marker.length) return;
  const [x, y, heading, r, g, b] = marker;
  const radius = 10;
  target.beginPath();
  [[0, 1], [140, 0.85], [-140, 0.85]].forEach(([degrees, scale], i) => {
    const angle = ((heading + degrees) * Math.PI) / 180;
    const px = x + radius * scale * Math.sin(angle);
    const py = y - radius * scale * Math.cos(angle);
    if (i) target.lineTo(px, py); else target.moveTo(px, py);
  });
  target.closePath();
  target.fillStyle = `rgba(${r}, ${g}, ${b}, 0.35)`;
  target.strokeStyle = `rgb(${r}, ${g}, ${b})`;
  target.lineWidth = 1.5;
  target.fill();
  target.stroke();
}
function paint() {
  paintQueued = false;
  // Terrapin pictures are transparent where nothing is drawn; show them on white, as the
  // terminal does. The UCBLogo background is opaque black and covers this.
  ctx.fillStyle = $('colours').value === 'terrapin' ? '#fff' : '#000';
  ctx.fillRect(0, 0, SIZE.width, SIZE.height);
  ctx.drawImage(layer, 0, 0);
  drawLabels(ctx);
  drawTurtle(ctx);
}
function schedulePaint() {
  if (!paintQueued) {
    paintQueued = true;
    requestAnimationFrame(paint);
  }
}
function showFrame(rgba, first, last, newLabels, newMarker) {
  applyRows(rgba, first, last);
  labels = newLabels;
  marker = newMarker;
  schedulePaint();
}
function savePng() {
  const copy = Object.assign(document.createElement('canvas'), SIZE);
  const copyCtx = copy.getContext('2d');
  copyCtx.drawImage(layer, 0, 0);
  drawLabels(copyCtx);
  copy.toBlob((blob) => saveBlob(blob, 'termlogo.png'), 'image/png');
}

// ---- cross-origin isolation, for typing into a running program and a gentler Stop ----------
// Browsers only share memory with a worker on an "isolated" page. GitHub Pages cannot send
// the headers that make one, so coi-sw.js (a service worker) adds them, which needs one
// reload the first time. Where that is not possible the page still works, but programs
// cannot wait for typing and Stop restarts Python.
const WAKE = 0, LINE_READY = 1, LINE_LEN = 2, KEY_HEAD = 3, KEY_TAIL = 4, KEY_SLOTS = 64;

async function setUpSharedMemory() {
  if (!self.crossOriginIsolated) {
    if (params.has('nocoi') || recall(STORE_NO_COI) === '1') return false;
    if (!('serviceWorker' in navigator) || !isSecureContext) return false;
    try {
      await navigator.serviceWorker.register('coi-sw.js');
      await navigator.serviceWorker.ready;
      if (sessionStorage.getItem('termlogo.reloaded') !== '1') {
        sessionStorage.setItem('termlogo.reloaded', '1');
        location.reload();
        return 'reloading';
      }
    } catch { /* service workers blocked: carry on without */ }
    return false;
  }
  const sab = new SharedArrayBuffer(16384);
  shared = {
    sab,
    intr: new SharedArrayBuffer(1),
    ctrl: new Int32Array(sab, 0, 32),
    keys: new Int32Array(sab, 128, KEY_SLOTS),
    line: new Uint8Array(sab, 512, 8192),
  };
  shared.interrupt = new Uint8Array(shared.intr);
  return true;
}
function wakeWorker() {
  Atomics.add(shared.ctrl, WAKE, 1);
  Atomics.notify(shared.ctrl, WAKE);
}
const lineQueue = [];
function flushLines() {
  while (lineQueue.length && !Atomics.load(shared.ctrl, LINE_READY)) {
    const bytes = new TextEncoder().encode(lineQueue.shift()).slice(0, shared.line.length);
    shared.line.set(bytes);
    Atomics.store(shared.ctrl, LINE_LEN, bytes.length);
    Atomics.store(shared.ctrl, LINE_READY, 1);
    wakeWorker();
  }
}
function sendKey(code) {
  const head = Atomics.load(shared.ctrl, KEY_HEAD);
  const next = (head + 1) % KEY_SLOTS;
  if (next === Atomics.load(shared.ctrl, KEY_TAIL)) return; // full: drop it
  shared.keys[head] = code;
  Atomics.store(shared.ctrl, KEY_HEAD, next);
  wakeWorker();
}
function clearInput() {
  lineQueue.length = 0;
  Atomics.store(shared.ctrl, LINE_READY, 0);
  Atomics.store(shared.ctrl, KEY_TAIL, Atomics.load(shared.ctrl, KEY_HEAD));
}
let stopTimer = null;
function interrupt() {
  Atomics.store(shared.interrupt, 0, 2); // 2 is SIGINT: Python raises KeyboardInterrupt
  wakeWorker();
  // If Python does not answer (stuck somewhere it cannot be interrupted), start afresh.
  stopTimer = setTimeout(() => { if (running) restart('Python did not answer Stop, so it was restarted.'); }, 4000);
}

// ---- the worker ---------------------------------------------------------------
async function startWorker() {
  ready = running = false;
  refreshButtons();
  setStatus('Starting…');
  const isolation = await setUpSharedMemory();
  if (isolation === 'reloading') return;
  const base = await pyodideBase();
  worker = new Worker(new URL('worker.js', import.meta.url), { type: 'module' });
  worker.onmessage = ({ data }) => handle(data.kind, data.args);
  worker.onerror = (event) => {
    if (retryWithoutSharedMemory()) return;
    setStatus('Could not start Python');
    say(`Could not start: ${event.message || 'the worker failed to load'}\n`, 'err');
  };
  worker.postMessage({
    type: 'init', base, colourMode: $('colours').value, ...SIZE,
    shared: shared ? { sab: shared.sab, intr: shared.intr } : null,
  });
}
// If Python will not start on an isolated page (a network or browser that dislikes the extra
// headers), try once more the plain way, and remember to do so on later visits.
function retryWithoutSharedMemory() {
  if (!shared || ready) return false;
  remember(STORE_NO_COI, '1');
  setStatus('Retrying without shared memory…');
  navigator.serviceWorker.getRegistrations()
    .then((all) => Promise.all(all.map((registration) => registration.unregister())))
    .finally(() => {
      const next = new URL(location.href);
      next.searchParams.set('nocoi', '1');
      location.replace(next);
    });
  return true;
}
function restart(message) {
  clearTimeout(stopTimer);
  worker.terminate();
  say(message + '\n', 'err');
  if (shared) clearInput();
  startWorker();
}

function finishRun(error) {
  clearTimeout(stopTimer);
  running = false;
  if (error) say(error + '\n', 'err');
  setStatus('Ready');
  refreshButtons();
}

function handle(kind, args) {
  if (kind === 'status') setStatus(args[0]);
  else if (kind === 'ready') {
    ready = true;
    setStatus(`Ready (termlogo ${args[0]})`);
    refreshButtons();
    ui.code.focus();
  } else if (kind === 'out') say(args[0]);
  else if (kind === 'clear') log.textContent = '';
  else if (kind === 'frame') showFrame(...args);
  else if (kind === 'done') finishRun(args[0]);
  else if (kind === 'reset') {
    running = false;
    setStatus('Ready');
    refreshButtons();
  } else if (kind === 'input') {
    if (args[0] === 'line') {
      setStatus('Waiting for you to type a line in the box below…');
      ui.line.focus();
    } else {
      setStatus('Waiting for a key: click the canvas, then press one…');
      stage.focus();
    }
  } else if (kind === 'line-taken') {
    setStatus('Running…');
    flushLines();
  } else if (kind === 'file') {
    saveBlob(new Blob([args[2]], { type: args[1] }), args[0]);
    for (const note of args[3]) say(note + '\n', 'cmd');
  } else if (kind === 'file-error') say(args[0] + '\n', 'err');
  else if (kind === 'crash' && !ready) {
    if (retryWithoutSharedMemory()) return;
    // Python never started: most often Pyodide could not be downloaded.
    say(`Could not start Python: ${args[0]}\n`, 'err');
    say('Check your connection, or whether cdn.jsdelivr.net is blocked on this network. '
      + 'A different copy of Pyodide can be used with ?pyodide=URL.\n', 'err');
    setStatus('Could not start Python');
  } else if (kind === 'crash') finishRun(`Internal error: ${args[0]}`);
}

function runLogo(code, echo) {
  if (!ready || running) return;
  if (echo) say(`? ${echo}\n`, 'cmd');
  running = true;
  setStatus('Running…');
  refreshButtons();
  worker.postMessage({ type: 'run', code, speed: Number($('speed').value) });
}

// ---- buttons -----------------------------------------------------------------
ui.run.addEventListener('click', () => runLogo(ui.code.value));
ui.clear.addEventListener('click', () => runLogo('cs'));
ui.reset.addEventListener('click', () => {
  if (!ready || running) return;
  log.textContent = '';
  worker.postMessage({ type: 'reset', colourMode: $('colours').value });
});
function stop() {
  if (!running) return;
  if (shared) interrupt();
  else restart('Stopped. The workspace was reset.');
}
ui.stop.addEventListener('click', stop);
ui.exports.forEach((button) => button.addEventListener('click', () => {
  if (!ready || running) return;
  if (button.dataset.kind === 'png') savePng();
  else worker.postMessage({ type: 'export', kind: button.dataset.kind });
}));
$('colours').addEventListener('change', () => {
  if (ready && !running) {
    log.textContent = '';
    worker.postMessage({ type: 'reset', colourMode: $('colours').value });
  }
});
ui.code.addEventListener('input', () => remember(STORE_CODE, ui.code.value));
ui.code.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
    event.preventDefault();
    runLogo(ui.code.value);
  }
});

// Keys for READCHAR and KEYP, and Escape to stop, as in the terminal.
window.addEventListener('keydown', (event) => {
  if (!running) return;
  if (event.key === 'Escape') {
    event.preventDefault();
    stop();
    return;
  }
  if (!shared || event.ctrlKey || event.metaKey || event.altKey) return;
  if (['INPUT', 'TEXTAREA', 'SELECT', 'BUTTON'].includes(event.target.tagName)) return;
  const code = event.key === 'Enter' ? 10 : event.key === 'Backspace' ? 8
    : [...event.key].length === 1 ? event.key.codePointAt(0) : 0;
  if (code) {
    event.preventDefault();
    sendKey(code);
  }
});

// ---- the command line ---------------------------------------------------------
$('repl').addEventListener('submit', (event) => {
  event.preventDefault();
  const text = ui.line.value.trim();
  if (!text && !running) return;
  ui.line.value = '';
  if (running) { // the running program reads it, with READWORD or READLIST
    say(`> ${text}\n`, 'cmd');
    lineQueue.push(text);
    flushLines();
    return;
  }
  commandHistory.push(text);
  historyAt = commandHistory.length;
  runLogo(text, text);
});
ui.line.addEventListener('keydown', (event) => {
  if (event.key === 'ArrowUp' && historyAt > 0) {
    event.preventDefault();
    ui.line.value = commandHistory[--historyAt];
  } else if (event.key === 'ArrowDown') {
    event.preventDefault();
    historyAt = Math.min(historyAt + 1, commandHistory.length);
    ui.line.value = commandHistory[historyAt] || '';
  }
});

// ---- sharing: the program travels in the address, after the # ---------------------------
function toBase64Url(bytes) {
  let text = '';
  for (let i = 0; i < bytes.length; i += 8192) text += String.fromCharCode(...bytes.subarray(i, i + 8192));
  return btoa(text).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
function fromBase64Url(text) {
  const padded = text.replace(/-/g, '+').replace(/_/g, '/').padEnd(Math.ceil(text.length / 4) * 4, '=');
  return Uint8Array.from(atob(padded), (c) => c.charCodeAt(0));
}
async function pipe(bytes, stream) {
  return new Uint8Array(await new Response(new Blob([bytes]).stream().pipeThrough(stream)).arrayBuffer());
}
async function encodeProgram(text) {
  const bytes = new TextEncoder().encode(text);
  if (typeof CompressionStream === 'undefined') return 'p=' + toBase64Url(bytes);
  return 'z=' + toBase64Url(await pipe(bytes, new CompressionStream('deflate-raw')));
}
async function decodeProgram(fragment) {
  const [kind, data] = [fragment.slice(0, 2), fragment.slice(2)];
  if (kind === 'p=') return new TextDecoder().decode(fromBase64Url(data));
  if (kind === 'z=') {
    return new TextDecoder().decode(await pipe(fromBase64Url(data), new DecompressionStream('deflate-raw')));
  }
  throw new Error('not a program link');
}
ui.share.addEventListener('click', async () => {
  const fragment = await encodeProgram(ui.code.value);
  window.history.replaceState(null, '', `#${fragment}`);
  try {
    await navigator.clipboard.writeText(location.href);
    setStatus('Link copied. It holds your program, so anyone with it can open the same one.');
  } catch {
    say(`Copy this link:\n${location.href}\n`, 'cmd');
  }
  if (location.href.length > 8000) say('That link is long; some chat apps may cut it off.\n', 'err');
});
async function loadShared() {
  if (!/^#[zp]=/.test(location.hash)) return false;
  try {
    ui.code.value = await decodeProgram(location.hash.slice(1));
    remember(STORE_CODE, ui.code.value);
    say('Loaded a shared program. Read it, then press Run.\n', 'cmd');
    return true;
  } catch {
    say('That link could not be read as a program.\n', 'err');
    return false;
  }
}

// ---- examples ------------------------------------------------------------------
async function loadExamples() {
  try {
    const response = await fetch('examples.json');
    const examples = await response.json();
    const select = $('examples');
    for (const { name, code } of examples) select.add(new Option(name, code));
    select.addEventListener('change', () => {
      if (!select.value) return;
      ui.code.value = select.value;
      remember(STORE_CODE, ui.code.value);
      select.selectedIndex = 0;
    });
  } catch {
    $('examples').disabled = true;
  }
}

// ---- start ---------------------------------------------------------------------
ui.code.value = recall(STORE_CODE) || DEFAULT_CODE;
ctx.fillStyle = '#000';
ctx.fillRect(0, 0, SIZE.width, SIZE.height);
loadExamples();
loadShared().then(startWorker);
