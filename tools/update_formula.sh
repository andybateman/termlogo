#!/bin/sh
# Point Formula/termlogo.rb at a release that already exists on GitHub (so its tag exists):
#   tools/update_formula.sh 1.1.0
# It downloads the tag's source archive, works out its sha256, and rewrites the formula's
# url, sha256 and test. Then commit the change. Needs curl and python3.
set -eu
version="${1:?usage: tools/update_formula.sh VERSION   (for example 1.1.0)}"
here="$(cd "$(dirname "$0")/.." && pwd)"
url="https://github.com/andybateman/termlogo/archive/refs/tags/v$version.tar.gz"
sha="$(curl -fsSL "$url" | python3 -c 'import hashlib,sys; print(hashlib.sha256(sys.stdin.buffer.read()).hexdigest())')"
[ "${#sha}" -eq 64 ] || { echo "Could not fetch $url" >&2; exit 1; }
python3 - "$here/Formula/termlogo.rb" "$url" "$sha" "$version" <<'PY'
import re
import sys

path, url, sha, version = sys.argv[1:]
text = open(path).read()
text = re.sub(r'(?m)^(\s*url )".*"$', lambda m: f'{m.group(1)}"{url}"', text)
text = re.sub(r'(?m)^(\s*sha256 )".*"$', lambda m: f'{m.group(1)}"{sha}"', text)
text = re.sub(r'assert_match "termlogo [^"]*"', f'assert_match "termlogo {version}"', text)
open(path, 'w').write(text)
PY
echo "Formula now points at v$version (sha256 $sha). Review with git diff, then commit."
