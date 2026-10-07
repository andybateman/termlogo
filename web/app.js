// The page: editor, command line, canvas and buttons. The Logo engine itself runs in
// worker.js; this file sends it programs and draws what comes back.
const $ = (id) => document.getElementById(id);
const params = new URLSearchParams(location.search);

// Where Pyodide comes from: ?pyodide=URL, else the copy beside the page if the build bundled
// one (see config.json), else the jsDelivr copy of the npm package.
const DEFAULT_PYODIDE_VERSION = '314.0.7';
async function loadConfig() {
  try {
    return await (await fetch('config.json', { cache: 'no-cache' })).json();
  } catch {
    return {}; // no config: use the defaults
  }
}
async function pyodideBase(config) {
  const version = config.pyodideVersion || DEFAULT_PYODIDE_VERSION;
  const base = params.get('pyodide')
    || (config.bundled ? './pyodide/' : `https://cdn.jsdelivr.net/npm/pyodide@${version}/`);
  return new URL(base, location.href).href.replace(/\/?$/, '/');
}

const STORE = {
  code: 'termlogo.code',
  noCoi: 'termlogo.nocoi', // set when shared memory stopped Python from starting
  speed: 'termlogo.speed',
  colours: 'termlogo.colours',
  expanded: 'termlogo.expanded',
  editorWidth: 'termlogo.editor-width',
  history: 'termlogo.history',
};
const DEFAULT_CODE = `; Press Run, or Ctrl+Enter
to flower :size
  repeat 36 [
    setpc 1 + remainder repcount 15
    repeat 4 [fd :size rt 90]
    rt 10
  ]
end
fitwindow 440 ; zoom so 440 steps fit
cs ht
flower 140
`;

const ui = {
  run: $('run'), stop: $('stop'), clear: $('clear'), reset: $('reset'),
  share: $('share'), open: $('open'), save: $('save'), openFile: $('open-file'),
  examples: $('examples'), speed: $('speed'), colours: $('colours'), expand: $('expand'),
  code: $('code'), line: $('line'), log: $('log'), status: $('status'), coords: $('coords'),
  zoom: $('zoom'), fullscreen: $('fullscreen'), splitter: $('splitter'),
  overlay: $('overlay'), stageWrap: $('stage-wrap'),
  workspace: document.querySelector('.workspace'), codePane: $('code-pane'),
  canvasPane: document.querySelector('.canvas-pane'),
  exports: [...document.querySelectorAll('.export')],
};

let worker = null;
let ready = false;
let running = false;
let shared = null; // memory shared with the worker, when the page is cross-origin isolated
let activeColours = 'ucblogo'; // the colour mode the engine is using now
const knownPrograms = new Set([DEFAULT_CODE]); // examples and the default: safe to replace

// ---- small helpers ---------------------------------------------------------------
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
  ui.log.append(span);
  while (ui.log.childNodes.length > 1500) ui.log.firstChild.remove();
  ui.log.scrollTop = ui.log.scrollHeight;
}
function setStatus(text, isError = false) {
  ui.status.textContent = text;
  ui.status.title = text; // the whole text, if a narrow bar cuts it short
  ui.status.classList.toggle('err', isError);
}
function showOverlay(text) {
  ui.overlay.textContent = text;
  ui.overlay.hidden = false;
}
function refreshControls() {
  const idle = ready && !running;
  ui.run.disabled = ui.clear.disabled = ui.reset.disabled = ui.colours.disabled = !idle;
  ui.line.disabled = !(idle || (running && shared));
  ui.exports.forEach((button) => { button.disabled = !idle; });
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
const finePointer = matchMedia('(pointer: fine)').matches;

// ---- the picture --------------------------------------------------------------------
// The engine keeps the drawing as pixels and sends only the rows that changed. They are
// patched into `layer`, which holds the picture without the turtle. The turtle and any
// LABEL text are drawn over a copy of it for display, and over another copy for PNG
// downloads (without the turtle). `view` is [width, height, origin x, origin y, scale].
const stage = $('stage');
const ctx = stage.getContext('2d');
const layer = document.createElement('canvas');
const layerCtx = layer.getContext('2d');
let labels = [];
let marker = [];
let view = null;
let paintQueued = false;

function setPictureSize(width, height) {
  for (const canvas of [stage, layer]) {
    // Setting a canvas size clears it, even to the same size, so only when it changed.
    if (canvas.width !== width || canvas.height !== height) Object.assign(canvas, { width, height });
  }
}
function applyRows(rgba, first, last) {
  if (!rgba.length || last < first) return;
  const pixels = new Uint8ClampedArray(rgba.buffer, rgba.byteOffset, rgba.byteLength);
  layerCtx.putImageData(new ImageData(pixels, layer.width, last - first + 1), 0, first);
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
  // terminal does. The UCBLogo background is opaque and covers this.
  ctx.fillStyle = activeColours === 'terrapin' ? '#fff' : '#000';
  ctx.fillRect(0, 0, stage.width, stage.height);
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
function showZoom(scale) {
  // One pixel per turtle step is normal; anything else came from FITWINDOW or SETSCALE.
  const normal = Math.abs(scale - 1) < 0.005;
  ui.zoom.hidden = normal;
  if (!normal) ui.zoom.textContent = `Zoom ×${scale >= 10 ? Math.round(scale) : scale.toFixed(scale < 1 ? 2 : 1)}`;
}
function showFrame(rgba, first, last, newLabels, newMarker, newView) {
  if (newView) {
    view = newView;
    setPictureSize(view[0], view[1]);
    showZoom(view[4]);
  }
  applyRows(rgba, first, last);
  labels = newLabels;
  marker = newMarker;
  schedulePaint();
}
function clearPicture() {
  layerCtx.clearRect(0, 0, layer.width, layer.height);
  labels = [];
  marker = [];
  schedulePaint();
}
function savePng() {
  const copy = Object.assign(document.createElement('canvas'), { width: layer.width, height: layer.height });
  const copyCtx = copy.getContext('2d');
  copyCtx.drawImage(layer, 0, 0);
  drawLabels(copyCtx);
  copy.toBlob((blob) => saveBlob(blob, 'termlogo.png'), 'image/png');
}

// Turtle coordinates under the pointer. The canvas is drawn "contained" in its box, so
// work out where the picture actually sits first.
function logoPoint(event) {
  if (!view) return null;
  const box = stage.getBoundingClientRect();
  const fit = Math.min(box.width / stage.width, box.height / stage.height);
  const left = box.left + (box.width - stage.width * fit) / 2;
  const top = box.top + (box.height - stage.height * fit) / 2;
  const px = (event.clientX - left) / fit;
  const py = (event.clientY - top) / fit;
  if (px < 0 || py < 0 || px > stage.width || py > stage.height) return null;
  const [, , originX, originY, scale] = view;
  return { x: (px - originX) / scale, y: (originY - py) / scale };
}
const whole = (n) => String(Math.round(n) || 0); // no "-0"
stage.addEventListener('pointermove', (event) => {
  const point = logoPoint(event);
  ui.coords.textContent = point ? `x ${whole(point.x)}   y ${whole(point.y)}` : '';
});
stage.addEventListener('pointerleave', () => { ui.coords.textContent = ''; });

// ---- the canvas follows the size of its box -------------------------------------------
// The engine draws one pixel per turtle step, so a bigger box gives more room to draw.
// Sizes are sent between runs, one at a time, newest last.
let wantedSize = null;
let requestedSize = null;
let resizing = false;
let resizeTimer = null;
function measureStage() {
  const box = ui.stageWrap.getBoundingClientRect();
  return { width: Math.max(2, Math.floor(box.width)), height: Math.max(2, Math.floor(box.height)) };
}
function sendSize() {
  if (!ready || running || resizing || !wantedSize) return;
  if (requestedSize && wantedSize.width === requestedSize.width
      && wantedSize.height === requestedSize.height) return;
  resizing = true;
  requestedSize = wantedSize;
  worker.postMessage({ type: 'resize', ...wantedSize });
}
new ResizeObserver(() => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => {
    wantedSize = measureStage();
    sendSize();
  }, 150);
}).observe(ui.stageWrap);

// ---- cross-origin isolation, for typing into a running program and a gentle Stop -------------
// Browsers only share memory with a worker on an "isolated" page. GitHub Pages cannot send
// the headers that make one, so coi-sw.js (a service worker) adds them, which needs one
// reload the first time. Where that is not possible the page still works, but programs
// cannot wait for typing and Stop restarts Python.
const WAKE = 0, LINE_READY = 1, LINE_LEN = 2, KEY_HEAD = 3, KEY_TAIL = 4, KEY_SLOTS = 64;

async function setUpSharedMemory() {
  if (!self.crossOriginIsolated) {
    if (params.has('nocoi') || recall(STORE.noCoi) === '1') return false;
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
  clearTimeout(stopTimer);
  stopTimer = setTimeout(() => {
    if (running) restart('Python did not answer Stop, so it was restarted.');
  }, 4000);
}

// ---- the worker -----------------------------------------------------------------------
async function startWorker() {
  ready = running = resizing = false;
  refreshControls();
  setStatus('Starting…');
  showOverlay('Starting…');
  const isolation = await setUpSharedMemory();
  if (isolation === 'reloading') return;
  const base = await pyodideBase(await loadConfig());
  const size = measureStage();
  requestedSize = wantedSize = size;
  activeColours = ui.colours.value;
  worker = new Worker(new URL('worker.js?v=__BUILD__', import.meta.url), { type: 'module' });
  worker.onmessage = ({ data }) => handle(data.kind, data.args);
  worker.onerror = (event) => {
    if (retryWithoutSharedMemory()) return;
    cannotStart(event.message || 'the worker failed to load');
  };
  worker.postMessage({
    type: 'init', base, colourMode: activeColours, ...size,
    shared: shared ? { sab: shared.sab, intr: shared.intr } : null,
  });
}
// If Python will not start on an isolated page (a network or browser that dislikes the extra
// headers), try once more the plain way, and remember to do so on later visits.
function retryWithoutSharedMemory() {
  if (!shared || ready) return false;
  remember(STORE.noCoi, '1');
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
function cannotStart(reason) {
  say(`Could not start Python: ${reason}\n`, 'err');
  say('Check your connection, or whether cdn.jsdelivr.net is blocked on this network. '
    + 'A different copy of Pyodide can be used with ?pyodide=URL.\n', 'err');
  setStatus('Could not start Python');
  showOverlay('Python could not start. The Output box says why.');
}
function restart(message) {
  clearTimeout(stopTimer);
  if (worker) worker.terminate();
  worker = null;
  runAfterReset = null;
  say(message + '\n', 'err');
  if (shared) clearInput();
  clearPicture();
  startWorker();
}
function finishRun(error) {
  clearTimeout(stopTimer);
  running = false;
  if (error) say(error + '\n', 'err');
  // The error shows beside the canvas too, for when the editor and output are hidden.
  setStatus(error ? `Ready. Last run: ${error}` : 'Ready', Boolean(error));
  refreshControls();
  sendSize();
}

function handle(kind, args) {
  switch (kind) {
    case 'status':
      setStatus(args[0]);
      showOverlay(args[0]);
      break;
    case 'ready':
      ready = true;
      ui.overlay.hidden = true;
      setStatus('Ready');
      refreshControls();
      if (finePointer) ui.code.focus({ preventScroll: true });
      sendSize();
      break;
    case 'out':
      say(args[0]);
      break;
    case 'clear':
      ui.log.textContent = '';
      break;
    case 'frame':
      showFrame(...args);
      break;
    case 'done':
      finishRun(args[0]);
      break;
    case 'reset':
      running = false;
      setStatus('Ready');
      refreshControls();
      if (runAfterReset) {
        const code = runAfterReset;
        runAfterReset = null;
        runLogo(code);
      }
      break;
    case 'resized':
      resizing = false;
      sendSize();
      break;
    case 'input':
      if (args[0] === 'line') {
        setStatus('Waiting for you to type a line in the ? box…');
        ui.line.focus();
      } else {
        setStatus('Waiting for a key: click the canvas, then press one…');
        stage.focus();
      }
      break;
    case 'line-taken':
      setStatus('Running…');
      flushLines();
      break;
    case 'file':
      saveBlob(new Blob([args[2]], { type: args[1] }), args[0]);
      for (const note of args[3]) say(note + '\n', 'cmd');
      break;
    case 'file-error':
      say(args[0] + '\n', 'err');
      break;
    case 'crash':
      if (!ready) {
        // Python never started: most often Pyodide could not be downloaded.
        if (!retryWithoutSharedMemory()) cannotStart(args[0]);
      } else {
        running = false;
        restart(`Python stopped unexpectedly (${args[0]}), so it was restarted. `
          + 'Procedures and variables were reset; your program is still in the editor.');
      }
      break;
    default:
      break;
  }
}

let runAfterReset = null;
function resetThenRun(code) {
  if (!ready || running) return;
  runAfterReset = code;
  running = true; // until the reset is done
  refreshControls();
  worker.postMessage({ type: 'reset', colourMode: activeColours });
}
function runLogo(code, echo) {
  if (!ready || running) return;
  if (echo) say(`? ${echo}\n`, 'cmd');
  if (shared) {
    // Forget a Stop that arrived just as the last program ended, and anything typed then.
    Atomics.store(shared.interrupt, 0, 0);
    clearInput();
  }
  running = true;
  setStatus('Running…');
  refreshControls();
  worker.postMessage({ type: 'run', code, speed: Number(ui.speed.value) });
}
function stop() {
  if (!running) return;
  if (shared) interrupt();
  else restart('Stopped. The workspace was reset.');
}

// ---- toolbar ----------------------------------------------------------------------------
ui.run.addEventListener('click', () => runLogo(ui.code.value));
ui.stop.addEventListener('click', stop);
ui.clear.addEventListener('click', () => runLogo('cs'));
ui.reset.addEventListener('click', () => {
  if (!ready || running) return;
  ui.log.textContent = '';
  activeColours = ui.colours.value;
  worker.postMessage({ type: 'reset', colourMode: activeColours });
});
ui.colours.addEventListener('change', () => {
  remember(STORE.colours, ui.colours.value);
  if (!ready || running) return;
  activeColours = ui.colours.value;
  ui.log.textContent = '';
  say(`${ui.colours.selectedOptions[0].textContent} colours. The workspace was reset.\n`, 'cmd');
  worker.postMessage({ type: 'reset', colourMode: activeColours });
});
ui.speed.addEventListener('change', () => remember(STORE.speed, ui.speed.value));
ui.zoom.addEventListener('click', () => {
  if (!ready || running) return;
  say('Back to one pixel per turtle step (SETSCALE 1). It applies to what is drawn next.\n', 'cmd');
  runLogo('setscale 1');
});
ui.exports.forEach((button) => button.addEventListener('click', () => {
  if (!ready || running) return;
  if (button.dataset.kind === 'png') savePng();
  else worker.postMessage({ type: 'export', kind: button.dataset.kind });
}));

function setExpanded(on) {
  document.body.classList.toggle('expanded', on);
  const label = on ? 'Show editor' : 'Expand canvas';
  ui.expand.querySelector('span').textContent = label;
  ui.expand.setAttribute('aria-label', label); // the text is hidden on small screens
  ui.expand.title = on ? 'Bring back the editor and output'
    : 'Hide the editor and give the canvas the whole width';
  remember(STORE.expanded, on ? '1' : '0');
  if (!on) showEditorShare();
}
ui.expand.addEventListener('click', () => setExpanded(!document.body.classList.contains('expanded')));

// The divider between the editor and the canvas: drag it, or focus it and use the arrow keys.
// Its place is kept as the editor's share of the width, so it suits any window size.
function editorShare() {
  return (ui.codePane.getBoundingClientRect().width / ui.workspace.clientWidth) * 100;
}
function showEditorShare() {
  ui.splitter.setAttribute('aria-valuenow', String(Math.round(editorShare())));
}
function setEditorShare(percent, save) {
  const share = Math.min(75, Math.max(15, percent));
  ui.workspace.style.setProperty('--editor-width', `${share.toFixed(1)}%`);
  showEditorShare();
  if (save) remember(STORE.editorWidth, editorShare().toFixed(1)); // as the page clamped it
}
ui.splitter.addEventListener('pointerdown', (event) => {
  if (event.button !== 0) return;
  event.preventDefault();
  ui.splitter.setPointerCapture(event.pointerId);
  ui.splitter.classList.add('dragging');
  document.body.classList.add('dragging');
});
ui.splitter.addEventListener('pointermove', (event) => {
  if (!ui.splitter.classList.contains('dragging')) return;
  const box = ui.workspace.getBoundingClientRect();
  setEditorShare(((event.clientX - box.left) / box.width) * 100, false);
});
function endDrag() {
  if (!ui.splitter.classList.contains('dragging')) return;
  ui.splitter.classList.remove('dragging');
  document.body.classList.remove('dragging');
  setEditorShare(editorShare(), true);
}
ui.splitter.addEventListener('pointerup', endDrag);
ui.splitter.addEventListener('pointercancel', endDrag);
ui.splitter.addEventListener('lostpointercapture', endDrag);
ui.splitter.addEventListener('dblclick', () => {
  ui.workspace.style.removeProperty('--editor-width');
  remember(STORE.editorWidth, '');
  showEditorShare();
});
ui.splitter.addEventListener('keydown', (event) => {
  const step = event.shiftKey ? 10 : 2;
  const to = { ArrowLeft: editorShare() - step, ArrowRight: editorShare() + step, Home: 0, End: 100 }[event.key];
  if (to === undefined) return;
  event.preventDefault();
  setEditorShare(to, true);
});

// Full screen shows the canvas and the bar under it, where the browser allows it.
if (document.fullscreenEnabled) {
  ui.fullscreen.hidden = false;
  ui.fullscreen.addEventListener('click', () => {
    if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
    else ui.canvasPane.requestFullscreen().catch(() => {});
  });
  document.addEventListener('fullscreenchange', () => {
    const on = document.fullscreenElement === ui.canvasPane;
    ui.fullscreen.setAttribute('aria-label', on ? 'Leave full screen' : 'Full screen');
    ui.fullscreen.title = on ? 'Leave full screen (Esc)' : 'Show the canvas full screen';
  });
}

// ---- the editor ---------------------------------------------------------------------------
// Replacing the editor's text asks first when it holds your own work (not an example).
function loadProgram(text, note) {
  const current = ui.code.value;
  if (current.trim() && current !== text && !knownPrograms.has(current)
      && !confirm('Replace the program in the editor? Your changes there will be lost.')) return false;
  ui.code.value = text;
  remember(STORE.code, text);
  if (note) say(note + '\n', 'cmd');
  return true;
}
ui.code.addEventListener('input', () => remember(STORE.code, ui.code.value));

// Tab indents (two spaces), Shift+Tab outdents, and Esc then Tab leaves the editor, so
// keyboard users are never trapped.
let tabLeaves = false;
function typeText(text) {
  if (!document.execCommand('insertText', false, text)) { // keeps undo where it works
    ui.code.setRangeText(text, ui.code.selectionStart, ui.code.selectionEnd, 'end');
    remember(STORE.code, ui.code.value);
  }
}
function shiftLines(outdent) {
  const value = ui.code.value;
  const start = value.lastIndexOf('\n', ui.code.selectionStart - 1) + 1;
  let end = ui.code.selectionEnd;
  if (end > start && value[end - 1] === '\n') end -= 1;
  const lineEnd = value.indexOf('\n', end);
  const stopAt = lineEnd === -1 ? value.length : lineEnd;
  const block = value.slice(start, stopAt);
  const changed = outdent ? block.replace(/^ {1,2}/gm, '') : block.replace(/^/gm, '  ');
  if (changed === block) return;
  ui.code.setSelectionRange(start, stopAt);
  typeText(changed);
  ui.code.setSelectionRange(start, start + changed.length);
}
ui.code.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
    event.preventDefault();
    runLogo(ui.code.value);
    return;
  }
  if (event.key === 'Escape') {
    tabLeaves = true;
    return;
  }
  if (event.key === 'Tab' && !event.ctrlKey && !event.metaKey && !event.altKey) {
    if (tabLeaves) {
      tabLeaves = false;
      return; // let the browser move on
    }
    event.preventDefault();
    const { selectionStart, selectionEnd, value } = ui.code;
    const severalLines = value.slice(selectionStart, selectionEnd).includes('\n');
    if (event.shiftKey || severalLines) shiftLines(event.shiftKey);
    else typeText('  ');
    return;
  }
  tabLeaves = false;
});

ui.open.addEventListener('click', () => ui.openFile.click());
ui.openFile.addEventListener('change', async () => {
  const [file] = ui.openFile.files;
  ui.openFile.value = '';
  if (!file) return;
  if (file.size > 1_000_000) {
    say(`${file.name} is too big for a Logo program (over 1 MB).\n`, 'err');
    return;
  }
  loadProgram(await file.text(), `Opened ${file.name}.`);
});
ui.save.addEventListener('click', () => {
  saveBlob(new Blob([ui.code.value], { type: 'text/plain' }), 'program.logo');
});

// ---- the command line --------------------------------------------------------------------
let commandHistory = [];
try { commandHistory = JSON.parse(recall(STORE.history) || '[]').slice(-100); } catch { /* ignore */ }
let historyAt = commandHistory.length;
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
  if (commandHistory[commandHistory.length - 1] !== text) commandHistory.push(text);
  commandHistory = commandHistory.slice(-100);
  historyAt = commandHistory.length;
  remember(STORE.history, JSON.stringify(commandHistory));
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
$('clear-output').addEventListener('click', () => { ui.log.textContent = ''; });

// Ctrl+Enter runs from anywhere; while a program runs, Esc stops it and other keys go to
// READCHAR and KEYP (unless you are typing in a box).
window.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
    if (event.target !== ui.code && event.target !== ui.line && !running) {
      event.preventDefault();
      runLogo(ui.code.value);
    }
    return;
  }
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
  const link = new URL(location.href);
  link.hash = await encodeProgram(ui.code.value);
  try {
    await navigator.clipboard.writeText(link.href);
    setStatus('Link copied. It holds your program, so anyone with it can open the same one.');
  } catch {
    say(`Copy this link:\n${link.href}\n`, 'cmd');
  }
  if (link.href.length > 8000) say('That link is long; some chat apps may cut it off.\n', 'err');
});
async function loadShared() {
  if (!/^#[zp]=/.test(location.hash)) return;
  const fragment = location.hash.slice(1);
  // Take the program out of the address, so reloading later keeps your own edits.
  window.history.replaceState(null, '', location.pathname + location.search);
  try {
    loadProgram(await decodeProgram(fragment), 'Loaded a shared program. Read it, then press Run.');
  } catch {
    say('That link could not be read as a program.\n', 'err');
  }
}

// ---- examples -------------------------------------------------------------------------------
async function loadExamples() {
  try {
    const examples = await (await fetch('examples.json?v=__BUILD__')).json();
    for (const { name, code } of examples) {
      ui.examples.add(new Option(name, code));
      knownPrograms.add(code);
    }
    ui.examples.addEventListener('change', () => {
      const name = ui.examples.selectedOptions[0].textContent;
      if (ui.examples.value && loadProgram(ui.examples.value)) {
        if (ready && !running) {
          say(`Running the ${name} example.\n`, 'cmd');
          runLogo(ui.examples.value);
        } else {
          const when = ready ? 'the running program finishes' : 'Python has started';
          say(`Loaded the ${name} example. Press Run once ${when}.\n`, 'cmd');
        }
      }
      ui.examples.selectedIndex = 0;
    });
  } catch {
    ui.examples.disabled = true;
  }
}

// ---- help --------------------------------------------------------------------------------------
const help = $('help');
let helpGroups = null;
function renderHelp() {
  const query = $('help-filter').value.trim().toLowerCase();
  const list = $('help-list');
  list.textContent = '';
  let shown = 0;
  for (const { category, entries } of helpGroups) {
    const matches = entries.filter((e) => !query || e.name.includes(query)
      || e.usage.toLowerCase().includes(query) || e.about.toLowerCase().includes(query));
    if (!matches.length) continue;
    const heading = document.createElement('h4');
    heading.textContent = category;
    const terms = document.createElement('dl');
    for (const entry of matches) {
      const term = document.createElement('dt');
      term.textContent = entry.usage;
      const about = document.createElement('dd');
      about.textContent = entry.about;
      terms.append(term, about);
    }
    list.append(heading, terms);
    shown += matches.length;
  }
  $('help-count').textContent = query ? `${shown} matching` : `${shown} commands. Type HELP name in the ? box for one.`;
}
$('help-open').addEventListener('click', async () => {
  help.showModal();
  if (!helpGroups) {
    try {
      helpGroups = await (await fetch('help.json?v=__BUILD__')).json();
    } catch {
      helpGroups = [];
      $('help-count').textContent = 'The command list could not be loaded; type HELP in the ? box instead.';
      return;
    }
  }
  renderHelp();
});
$('help-filter').addEventListener('input', () => { if (helpGroups) renderHelp(); });
$('try-sample').addEventListener('click', () => {
  const sample = $('sample').textContent + '\n';
  if (!loadProgram(sample)) return;
  help.close();
  resetThenRun(sample); // a fresh workspace, so an earlier FITWINDOW cannot shrink or blow it up
});

// ---- start ---------------------------------------------------------------------------------------
ui.speed.value = recall(STORE.speed) || ui.speed.value;
ui.colours.value = recall(STORE.colours) || ui.colours.value;
if (!ui.speed.value) ui.speed.value = '5';
if (!ui.colours.value) ui.colours.value = 'ucblogo';
setExpanded(recall(STORE.expanded) === '1');
if (Number(recall(STORE.editorWidth))) setEditorShare(Number(recall(STORE.editorWidth)), false);
else showEditorShare();
ui.code.value = recall(STORE.code) ?? DEFAULT_CODE;
loadConfig().then((config) => {
  const parts = [config.version && `v${config.version}`, config.commit, config.built];
  $('build').textContent = parts.filter(Boolean).join(' · ');
});
// Examples first, so a shared link replacing one of them needs no question.
loadExamples().then(loadShared).then(startWorker);
