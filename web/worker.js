// Runs Python (Pyodide) and the termlogo engine off the page's main thread, so a long
// drawing never freezes the page. Python calls `post` to send pictures and text back.
let session = null;

const post = (kind, ...args) => self.postMessage({ kind, args });

async function init({ base, colourMode, width, height }) {
  post('status', 'Loading Python (about 12 MB the first time)…');
  const { loadPyodide } = await import(base + 'pyodide.mjs');
  const pyodide = await loadPyodide({ indexURL: base });
  post('status', 'Loading termlogo…');
  const response = await fetch(new URL('termlogo.zip', self.location));
  if (!response.ok) throw new Error('termlogo.zip: HTTP ' + response.status);
  pyodide.unpackArchive(await response.arrayBuffer(), 'zip', { extractDir: '/termlogo_pkg' });
  pyodide.runPython("import sys; sys.path.insert(0, '/termlogo_pkg')");
  const web = pyodide.pyimport('termlogo.web');
  session = web.Session(post, width, height, colourMode);
  post('ready', pyodide.runPython('import termlogo; termlogo.__version__'));
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
