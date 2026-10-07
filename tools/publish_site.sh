#!/bin/sh
# Build the browser version into the andybateman.github.io checkout, commit it and push it,
# which publishes it at https://www.andybateman.com/termlogo/ a minute later.
#
#   tools/publish_site.sh [path/to/andybateman.github.io] [--no-push]
#
# The site checkout defaults to ../andybateman.github.io. It must have no other uncommitted
# changes. Commit and push your termlogo changes first: the page shows the commit it was
# built from. With --no-push the commit is made but not pushed, so you can look first.
# When `gh` is installed, its login is used for the pull and push (plain git sometimes
# picks up the wrong saved credentials).
set -eu
here="$(cd "$(dirname "$0")/.." && pwd)"
site=""
push=1
for argument in "$@"; do
  case "$argument" in
    --no-push) push=0 ;;
    *) site="$argument" ;;
  esac
done
site="${site:-$here/../andybateman.github.io}"
[ -d "$site/.git" ] || { echo "$site is not a git checkout of andybateman.github.io" >&2; exit 1; }
site="$(cd "$site" && pwd)"

remote_git() {
  if command -v gh >/dev/null 2>&1; then
    git -C "$site" -c credential.helper= -c credential.helper='!gh auth git-credential' "$@"
  else
    git -C "$site" "$@"
  fi
}

if [ -n "$(git -C "$site" status --porcelain)" ]; then
  echo "$site has uncommitted changes; commit or stash them first" >&2
  exit 1
fi
if git -C "$site" remote get-url origin >/dev/null 2>&1; then
  remote_git pull --ff-only
fi

python3 "$here/tools/build_web.py" --out "$site/termlogo"
git -C "$site" add termlogo
if git -C "$site" diff --cached --quiet; then
  echo "The site already has this version. Nothing to publish."
  exit 0
fi

label="$(python3 -c "import json,sys; c=json.load(open(sys.argv[1])); print('v%s (%s)' % (c['version'], c['commit']))" "$site/termlogo/config.json")"
git -C "$site" commit -q -m "Update /termlogo/ to $label"
echo "Committed: Update /termlogo/ to $label"
if [ "$push" -eq 1 ]; then
  remote_git push
  echo "Pushed. The live page updates in about a minute: https://www.andybateman.com/termlogo/"
else
  echo "Not pushed (--no-push). Push with: git -C $site push"
fi
