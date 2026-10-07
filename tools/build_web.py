"""Build the browser version into dist/web: the page and the termlogo package.

    python3 tools/build_web.py                          # small; Pyodide comes from the jsDelivr CDN
    python3 tools/build_web.py --bundle-pyodide         # also copies Pyodide (via `npm pack`) so
                                                        # the site works offline and without a CDN
    python3 tools/build_web.py --pyodide-dir D          # bundle from a folder you already have
    python3 -m http.server -d dist/web                  # then open http://localhost:8000

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
    parser.add_argument(
        '--bundle-pyodide', action='store_true', help='copy Pyodide into the site (needs npm)'
    )
    parser.add_argument(
        '--pyodide-dir', type=Path, help='bundle Pyodide from this folder instead of npm'
    )
    parser.add_argument('--out', type=Path, default=ROOT / 'dist' / 'web')
    args = parser.parse_args()

    out = args.out
    if out.exists():
        # Only ever replace a folder this script made (it leaves a config.json) or an empty one,
        # so a mistyped --out cannot wipe something else.
        if any(out.iterdir()) and not (out / 'config.json').is_file():
            sys.exit(f'{out} exists and was not made by this script; choose another --out')
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for page in sorted((ROOT / 'web').iterdir()):
        if page.is_file():
            shutil.copy(page, out / page.name)
    build_package(out / 'termlogo.zip')
    build_examples(out / 'examples.json')

    bundled = args.bundle_pyodide or args.pyodide_dir is not None
    if bundled:
        with tempfile.TemporaryDirectory() as scratch:
            source = args.pyodide_dir or fetch_pyodide(PYODIDE_VERSION, scratch)
            (out / 'pyodide').mkdir()
            for name in PYODIDE_FILES:
                if not (source / name).is_file():
                    sys.exit(
                        f'{source / name} is missing; is this a Pyodide {PYODIDE_VERSION} folder?'
                    )
                shutil.copy(source / name, out / 'pyodide' / name)
    config = {'pyodideVersion': PYODIDE_VERSION, 'bundled': bundled}
    (out / 'config.json').write_text(json.dumps(config), encoding='utf-8')
    total = sum(f.stat().st_size for f in out.rglob('*') if f.is_file())
    print(f'Built {out} ({total / 1e6:.1f} MB). Serve it: python3 -m http.server -d {out}')


if __name__ == '__main__':
    main()
