// The page: editor, REPL line, canvas and buttons. The Logo engine itself runs in
// worker.js; this file only sends it programs and draws what comes back.
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
  run: $('run'), stop: $('stop'), clear: $('clear'), reset: $('reset'),
  line: $('line'), code: $('code'), status: $('status'),
  exports: [...document.querySelectorAll('.export')],
};

let worker = null;
let ready = false;
let running = false;
const history = [];
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
  ui.run.disabled = ui.clear.disabled = ui.reset.disabled = ui.line.disabled = !idle;
  ui.exports.forEach((b) => { b.disabled = !idle; });
  ui.stop.disabled = !running;
}

// ---- drawing ---------------------------------------------------------------
let pendingFrame = null;
let drawing = false;
async function drawLoop() {
  drawing = true;
  while (pendingFrame) {
    const { png, labels } = pendingFrame;
    pendingFrame = null;
    const bitmap = await createImageBitmap(new Blob([png], { type: 'image/png' }));
    ctx.drawImage(bitmap, 0, 0);
    bitmap.close();
    ctx.font = '14px ui-monospace, Menlo, Consolas, monospace';
    ctx.textBaseline = 'middle';
    for (const [x, y, text, r, g, b] of labels) {
      ctx.fillStyle = `rgb(${r}, ${g}, ${b})`;
      ctx.fillText(text, x, y);
    }
  }
  drawing = false;
}
function showFrame(png, labels) {
  pendingFrame = { png, labels };
  if (!drawing) drawLoop();
}

// ---- the worker ------------------------------------------------------------
async function startWorker() {
  ready = running = false;
  refreshButtons();
  setStatus('Starting…');
  const base = await pyodideBase();
  worker = new Worker(new URL('worker.js', import.meta.url), { type: 'module' });
  worker.onmessage = ({ data }) => handle(data.kind, data.args);
  worker.onerror = (event) => {
    setStatus('Could not start Python');
    say(`Could not start: ${event.message || 'the worker failed to load'}\n`, 'err');
  };
  worker.postMessage({
    type: 'init', base, colourMode: $('colours').value, ...SIZE,
  });
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
  else if (kind === 'frame') showFrame(args[0], args[1]);
  else if (kind === 'done') {
    running = false;
    if (args[0]) say(args[0] + '\n', 'err');
    setStatus('Ready');
    refreshButtons();
  } else if (kind === 'reset') {
    running = false;
    setStatus('Ready');
    refreshButtons();
  } else if (kind === 'file') download(args[0], args[1], args[2], args[3]);
  else if (kind === 'file-error') say(args[0] + '\n', 'err');
  else if (kind === 'crash' && !ready) {
    // Python never started: most often Pyodide could not be downloaded.
    say(`Could not start Python: ${args[0]}\n`, 'err');
    say('Check your connection, or whether cdn.jsdelivr.net is blocked on this network. '
      + 'A different copy of Pyodide can be used with ?pyodide=URL.\n', 'err');
    setStatus('Could not start Python');
  } else if (kind === 'crash') {
    running = false;
    say(`Internal error: ${args[0]}\n`, 'err');
    setStatus('Ready');
    refreshButtons();
  }
}

function runLogo(code, echo) {
  if (!ready || running) return;
  if (echo) say(`? ${echo}\n`, 'cmd');
  running = true;
  setStatus('Running…');
  refreshButtons();
  worker.postMessage({ type: 'run', code, speed: Number($('speed').value) });
}

function download(name, mime, bytes, notes) {
  const url = URL.createObjectURL(new Blob([bytes], { type: mime }));
  const link = Object.assign(document.createElement('a'), { href: url, download: name });
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
  for (const note of notes) say(note + '\n', 'cmd');
}

// ---- buttons -----------------------------------------------------------------
ui.run.addEventListener('click', () => runLogo(ui.code.value));
ui.clear.addEventListener('click', () => runLogo('cs'));
ui.reset.addEventListener('click', () => {
  if (!ready || running) return;
  log.textContent = '';
  worker.postMessage({ type: 'reset', colourMode: $('colours').value });
});
ui.stop.addEventListener('click', () => {
  // The engine is busy inside Python and cannot be interrupted politely from here,
  // so the worker is replaced. Procedures and variables are lost; the program text stays.
  worker.terminate();
  say('Stopped. The workspace was reset.\n', 'err');
  startWorker();
});
ui.exports.forEach((button) => button.addEventListener('click', () => {
  if (ready && !running) worker.postMessage({ type: 'export', kind: button.dataset.kind });
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

// ---- the command line ---------------------------------------------------------
$('repl').addEventListener('submit', (event) => {
  event.preventDefault();
  const text = ui.line.value.trim();
  if (!text) return;
  history.push(text);
  historyAt = history.length;
  ui.line.value = '';
  runLogo(text, text);
});
ui.line.addEventListener('keydown', (event) => {
  if (event.key === 'ArrowUp' && historyAt > 0) {
    event.preventDefault();
    ui.line.value = history[--historyAt];
  } else if (event.key === 'ArrowDown') {
    event.preventDefault();
    historyAt = Math.min(historyAt + 1, history.length);
    ui.line.value = history[historyAt] || '';
  }
});

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
ctx.fillRect(0, 0, stage.width, stage.height);
loadExamples();
startWorker();
