"""Build the browser version into dist/web: the page, the termlogo package and Pyodide.

    python3 tools/build_web.py                  # fetches Pyodide with `npm pack`
    python3 tools/build_web.py --pyodide-dir D  # or copies it from a folder you already have
    python3 -m http.server -d dist/web          # then open http://localhost:8000

The page needs a web server (it loads a module worker and fetches files), so opening
index.html from disk will not work.
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYODIDE_VERSION = '314.0.7'
# What loadPyodide needs at run time (not the type definitions, source maps or demo pages).
PYODIDE_FILES = (
    'pyodide.mjs',
    'pyodide.asm.mjs',
    'pyodide.asm.wasm',
    'python_stdlib.zip',
    'pyodide-lock.json',
)
TERMINAL_ONLY = {'repl.py', '__main__.py'}


def build_package(target):
    """termlogo.zip: the package without the terminal front end."""
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted((ROOT / 'termlogo').glob('*.py')):
            if path.name not in TERMINAL_ONLY:
                archive.write(path, f'termlogo/{path.name}')


def build_examples(target):
    examples = [
        {'name': path.stem.replace('_', ' '), 'code': path.read_text(encoding='utf-8')}
        for path in sorted((ROOT / 'examples').glob('*.logo'))
    ]
    target.write_text(json.dumps(examples, indent=1), encoding='utf-8')


def fetch_pyodide(version, folder):
    """Download Pyodide from npm into `folder` and return the folder holding its files."""
    subprocess.run(
        ['npm', 'pack', f'pyodide@{version}', '--silent'],
        cwd=folder,
        check=True,
        capture_output=True,
    )
    tarball = next(Path(folder).glob('pyodide-*.tgz'))
    shutil.unpack_archive(tarball, folder, filter='data')
    return Path(folder) / 'package'


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('--pyodide-dir', type=Path, help='copy Pyodide from this folder, not npm')
    parser.add_argument('--out', type=Path, default=ROOT / 'dist' / 'web')
    args = parser.parse_args()

    out = args.out
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for page in sorted((ROOT / 'web').iterdir()):
        if page.is_file():
            shutil.copy(page, out / page.name)
    build_package(out / 'termlogo.zip')
    build_examples(out / 'examples.json')

    with tempfile.TemporaryDirectory() as scratch:
        source = args.pyodide_dir or fetch_pyodide(PYODIDE_VERSION, scratch)
        (out / 'pyodide').mkdir()
        for name in PYODIDE_FILES:
            if not (source / name).is_file():
                sys.exit(f'{source / name} is missing; is this a Pyodide {PYODIDE_VERSION} folder?')
            shutil.copy(source / name, out / 'pyodide' / name)
    total = sum(f.stat().st_size for f in out.rglob('*') if f.is_file())
    print(f'Built {out} ({total / 1e6:.1f} MB). Serve it: python3 -m http.server -d {out}')


if __name__ == '__main__':
    main()
