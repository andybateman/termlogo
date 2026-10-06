#!/bin/sh
# Build a single-file termlogo.pyz that runs anywhere Python 3.10+ is installed.
# Usage: tools/build_pyz.sh [output]   (default: dist/termlogo.pyz)
set -eu
here="$(cd "$(dirname "$0")/.." && pwd)"
out="${1:-$here/dist/termlogo.pyz}"
stage="$(mktemp -d)"
trap 'rm -rf "$stage"' EXIT
mkdir -p "$stage/app" "$(dirname "$out")"
cp -R "$here/termlogo" "$stage/app/termlogo"
find "$stage/app" -name __pycache__ -type d -prune -exec rm -rf {} +
python3 -m zipapp "$stage/app" -m "termlogo.__main__:main" -p "/usr/bin/env python3" -o "$out"
chmod +x "$out"
echo "Built $out ($(wc -c <"$out" | tr -d ' ') bytes)"
