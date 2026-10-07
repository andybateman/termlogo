// Runs Python (Pyodide) and the termlogo engine off the page's main thread, so a long
// drawing never freezes the page. Python calls `post` to send pictures and text back.
//
// When the page is cross-origin isolated it also shares memory with this worker, which lets
// a running program wait for typing (READWORD, READCHAR) and lets Stop interrupt Python
// without throwing the workspace away.
let session = null;
let pyodide = null;

const post = (kind, ...args) => self.postMessage({ kind, args });

// Shared memory layout; keep in step with app.js.
const WAKE = 0, LINE_READY = 1, LINE_LEN = 2, KEY_HEAD = 3, KEY_TAIL = 4, KEY_SLOTS = 64;
let ctrl = null, keys = null, line = null;

function pause(ms) {
  // Sleep until the page wakes us (a key, a line, or Stop) or the time is up, then let a
  // pending Stop raise KeyboardInterrupt inside Python.
  Atomics.wait(ctrl, WAKE, Atomics.load(ctrl, WAKE), ms);
  pyodide.checkInterrupt();
}

const host = {
  read_line() {
    post('input', 'line');
    for (;;) {
      if (Atomics.load(ctrl, LINE_READY)) {
        const text = new TextDecoder().decode(line.slice(0, Atomics.load(ctrl, LINE_LEN)));
        Atomics.store(ctrl, LINE_READY, 0);
        post('line-taken');
        return text;
      }
      pause(250);
    }
  },
  read_char() {
    post('input', 'key');
    for (;;) {
      const tail = Atomics.load(ctrl, KEY_TAIL);
      if (tail !== Atomics.load(ctrl, KEY_HEAD)) {
        const code = keys[tail];
        Atomics.store(ctrl, KEY_TAIL, (tail + 1) % KEY_SLOTS);
        return String.fromCodePoint(code);
      }
      pause(250);
    }
  },
  key_ready() {
    return Atomics.load(ctrl, KEY_TAIL) !== Atomics.load(ctrl, KEY_HEAD);
  },
  sleep(seconds) {
    const end = performance.now() + seconds * 1000;
    for (let left = end - performance.now(); left > 0; left = end - performance.now()) {
      pause(Math.min(left, 50));
    }
    pyodide.checkInterrupt();
  },
};

async function init({ base, colourMode, width, height, shared }) {
  post('status', 'Loading Python (about 12 MB the first time)…');
  const { loadPyodide } = await import(base + 'pyodide.mjs');
  pyodide = await loadPyodide({ indexURL: base });
  post('status', 'Loading termlogo…');
  const response = await fetch(new URL('termlogo.zip', self.location));
  if (!response.ok) throw new Error('termlogo.zip: HTTP ' + response.status);
  pyodide.unpackArchive(await response.arrayBuffer(), 'zip', { extractDir: '/termlogo_pkg' });
  pyodide.runPython("import sys; sys.path.insert(0, '/termlogo_pkg')");
  if (shared) {
    ctrl = new Int32Array(shared.sab, 0, 32);
    keys = new Int32Array(shared.sab, 128, KEY_SLOTS);
    line = new Uint8Array(shared.sab, 512, 8192);
    pyodide.setInterruptBuffer(new Uint8Array(shared.intr));
  }
  const web = pyodide.pyimport('termlogo.web');
  session = shared
    ? web.Session(post, width, height, colourMode, host)
    : web.Session(post, width, height, colourMode);
  post('ready', pyodide.runPython('import termlogo; termlogo.__version__'), Boolean(shared));
}

self.onmessage = async ({ data }) => {
  try {
    if (data.type === 'init') await init(data);
    else if (data.type === 'run') session.run(data.code, data.speed);
    else if (data.type === 'reset') {
      session.reset(data.colourMode);
      post('reset');
    } else if (data.type === 'export') session.export(data.kind);
  } catch (error) {
    post('crash', String(error && error.message ? error.message : error));
  }
};
