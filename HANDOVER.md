# Handover - Terminal Logo Turtle

**As at:** 2026-10-07 (v1.1.0, plus unreleased changes on `main`)

## Purpose
A Logo interpreter with turtle graphics that runs entirely in the terminal, using only the Python standard library. It follows UCBLogo by default, has a Terrapin colour mode for the colour tutorial, and can export a drawing as a 3D-printable stencil. `README.md` is the user guide; this file is the list of what is still to do and how to pick it up.

## Current state
- Version 1.1.0 is the latest release, from the public GitHub repository `andybateman/termlogo`. `main` has moved on since, unreleased: the Python 3.10 and 3.11 recursion crash fix, review fixes (browser recursion limit, file streams, `PPS`), and the redesigned browser page, whose canvas fills the window. The live page at www.andybateman.com/termlogo/ is published from `main` and shows the commit it was built from.
- Ruff lint and format are clean, and the 343 unit and pseudo-terminal tests pass on Python 3.10, 3.11, 3.12 and 3.13. The browser smoke test passes all 72 checks in headless Chromium (as at 2026-10-07; run the commands under "How to pick it up" for the live result).
- Added on 2026-10-07 (later): nested `FILLED` repaint, arrays, property lists, file streams, `READCHAR`/`KEYP`, `CURSOR`/`SETCURSOR`, `GOTO`/`TAG`, `.MAYBEOUTPUT`, round pens, XOR `PENREVERSE`, `--fit`.
- Added on 2026-10-07: keyboard editing of multi-line commands recalled from history, `.stl` added to `STENCIL` names, `FILL` and `FILLED` areas cut out of the stencil, and a repaired `FILLED`.
- Not yet checked by hand: the later additions (item 13), the new command-pane keys in a real Ghostty window, and the fill cut-outs in a slicer or on the printer. Both are covered only by automated tests so far.

## Decisions made
| Decision | Why |
|---|---|
| Up and Down move between the lines of a multi-line command, and step through history only from its first or last line | Matches zsh and IPython, so a recalled block can be edited without the mouse. Ctrl-P/Ctrl-N and PageUp/PageDown still step whole entries |
| Alt+Enter adds a line break; Enter always runs | Enter and Ctrl-J are the same byte in the current terminal mode, so a separate key was needed |
| `FILLED` fills the polygon through every point the turtle visits and always outlines it in the pen colour | This is what the UCBLogo manual describes. The old flood fill from the start point only recoloured the outline |
| Where a `FILLED` path crosses itself, alternate regions are filled (even-odd rule) | Matches the usual UCBLogo result for a five-pointed star |
| A `FILL` in the stencil is bounded only by lines drawn before it | Same order of events as on screen. Lines drawn afterwards do not split the cut-out |
| An unenclosed `FILL` is left out of the stencil with a warning | On screen the canvas edge can bound a fill; on the plate it would remove everything |
| Only `STENCIL` adds a missing `.stl` | `SAVEPICT` and `-o` pick the format from the extension |
| Generated `*.stl` files are git-ignored | They are build output |
| `SETCURSOR` works inside the REPL's five-row text area and lasts one command | The text area is a scrolling log, not a full text screen. Outside the REPL it does nothing |
| `--fit N` scales the drawing, not pen sizes | Pen size is in pixels. Scaling it would change stencil widths, which are in millimetres |
| A Braille cell keeps showing its most common colour | A Braille character has one foreground colour; `half` and `kitty` give per-pixel colour |
| Repository name `termlogo`, public under the MIT licence | Name chosen by Andy (2026-10-07); made public the same day so it can be installed with Homebrew |
| One `README.md` for GitHub and the Quests project tools, with the `Keywords`, `Status` and date lines inside an HTML comment | GitHub hides comments; `projects.py`, the session hook and the skills still find the lines. Next steps live in this file, not the README |
| The page's canvas follows the size of its pane at one pixel per turtle step (up to 1920x1200, stretched beyond), rather than a fixed 800x600 scaled to fit | A bigger window gives more room to draw, with crisp pixels. `FITWINDOW` gives textbook coordinates when a program wants them |
| The examples start with `FITWINDOW` | They then fill any canvas, in the browser and the terminal. The stencil examples still export at 1 step = 1 mm |
| In the browser, Python may recurse 2,000 frames | An exception unwinding through about 3,000 frames kills Pyodide (measured in Chromium), and Logo errors, `STOP`, `OUTPUT` and Stop are all exceptions |
| The status bar under the canvas repeats the last error | The output is out of sight when the canvas is expanded or full screen |

## Open items
Low-effort checks first. "Next session" means follow-up work in a later session.

| # | Item | Owner | Effort |
|---|---|---|---|
| 1 | Try the command-pane keys by hand in Ghostty: Up/Down inside a recalled block, Option+Enter, Home/End twice. Confirm whether Shift+Enter adds a line (it relies on Ghostty sending `CSI 27;2;13~`) | Andy | Small |
| 2 | Recheck Kitty rendering in a restarted Ghostty session (carried over from 2026-10-06) | Andy | Small |
| 3 | Open `examples/stencil_fill.logo` output in a slicer, then test-print one stencil | Andy | Small, then a print |
| 4 | Stencil: detect joins too thin to print. A pen-up `FILLED` star leaves its centre held at five points and is not flagged | Next session | Medium |
| 5 | A newline key that works in every terminal: make Ctrl-J insert a line by clearing `ICRNL`. About 60 test inputs change from `\n` to `\r` | Next session | Medium, mechanical |
| 7 | Stencil extras: text from `LABEL` via a stencil font, rounded plate corners, 3MF output | Next session | Large |
| 8 | Language gaps that remain: `DRIBBLE`, directory commands, `EDIT`, text windows beyond `SETCURSOR` | Next session | Medium |
| 9 | Side-by-side conformance list against UCBLogo | Next session | Medium |
| 10 | Install route for the MacBook setup: the `termlogo` link in `~/.oh-my-zsh/oh-my-custom/bin/` is not in the setup script | Andy | Small |
| 11 | Wider Ruff rules (`UP`, `SIM`, `RUF`): roughly 160 style points, none of them bugs (as at 2026-10-07) | Next session | Small |
| 15 | After each release: run `tools/update_formula.sh VERSION` (needs the tag to exist), commit, then check `brew install` on a Mac. The formula was checked on a Mac for v1.0.0; 1.1.0 not yet | Andy | Small, each release |
| 16 | Browser version (live at www.andybateman.com/termlogo/, published with `tools/publish_site.sh`, which builds into the `andybateman.github.io` checkout, commits and pushes; Pyodide loads from the jsDelivr CDN). Done: animation by changed rows, `LABEL` in PNG/SVG, share links, typing into programs, interruptible Stop (service worker for shared memory, with a fallback), and the 2026-10-07 redesign (the canvas fills the window; divider, Expand and full screen; Help; Open and Save). Next: suggestions 2 and 5 to 10 below | Next session | Small |
| 14 | Standalone per-platform binaries (PyInstaller or Nuitka via a GitHub Actions matrix on release tags). Needs a token with workflow scope, and `readline` history checked on macOS and Linux. macOS needs signing and notarising to avoid the Gatekeeper warning | Next session | Medium |
| 13 | Try the new REPL features by hand in Ghostty: `READCHAR` and `KEYP` while a program runs, `SETCURSOR`, `--fit 1000` after resizing the window, and the round Braille pen. | Andy | Small |

Can wait: 7, 8, 9 and 11.

## Suggestions
From the review on 2026-10-07, in priority order. Items already in the table above are not repeated.

**Do next (small)**
1. **Release 1.2.0.** `main` carries a crash fix that matters to anyone running `termlogo.pyz` on Python 3.10 or 3.11 (deep recursion could kill the interpreter), plus the review fixes and the new page. Then run `tools/update_formula.sh 1.2.0` (open item 15).
2. **Open the live page in Safari, Firefox and on a phone.** The page has only been checked in headless Chromium. Worth trying: dragging the divider with a trackpad, full screen (iPhone Safari cannot show one element full screen, so the button hides itself there), the one-time reload for the service worker, typing a line for `READWORD`, and runaway recursion (`to r :n output 1 + r :n + 1 end print r 1` should say `Stack overflow`; the 2,000-frame limit was measured in Chromium, and other browsers have different stack sizes).
3. **Add continuous integration.** A GitHub Actions workflow that runs ruff and the unit tests on Python 3.10 to 3.13 for every push. Python 3.10 was first tested on 2026-10-07 and turned up a crash that this would have caught. Pushing a workflow needs a token with the `workflow` scope (as for `docs/pages-workflow.yml`).
4. **Tidy up.** Delete the leftover remote branch from an earlier session (`git branch -r` lists it; `git push origin --delete NAME`). Remove `docs/release-pyz-instructions.txt`, a one-off that added notes to the v1.0.0 release and has been run. Settle outstanding question 1 with `gh auth setup-git`.

**Worth doing (medium)**
5. **Sharper pictures on high-DPI screens.** The page gives each canvas pixel one CSS pixel, so on a Retina screen lines look slightly soft. Either draw at `devicePixelRatio` (up to four times the pixels for Python to fill, so check the speed and `MAX_PIXELS`), or have the engine send line segments for the page to draw as vectors (`FILL` would still need pixels).
6. **A better editor.** Line numbers, bracket matching and Logo colouring, for example CodeMirror 6 from the CDN (about 150 KB). Error messages could then point at the line.
7. **Speed and resizing during a run.** Both take effect only between runs; a resize during an animation stretches the old picture until it ends. Both could reach a running program through the shared memory that already carries keys and Stop.
8. **Click or drag to move the turtle** on the canvas, as the terminal REPL does.
9. **`SAVEPICT` as a download** in the browser, instead of writing to the hidden in-memory folder.

**Later (large)**
10. **Offline use.** Let the service worker cache the page and Pyodide, so the page works without a connection once visited (a progressive web app).
11. **Deeper recursion everywhere.** To avoid a crash, non-tail recursion stops after about 140 to 400 levels in the browser and 350 to 1,000 on Python 3.10 (each level takes 5 to 14 Python frames), against 25,000 elsewhere. Requiring Python 3.11 in a future major version would lift the 3.10 limit; an evaluator that keeps its own stack instead of Python's would remove both limits.

## Outstanding questions
1. **Git credentials.** Plain `git push` fails because git uses the macOS keychain login rather than the active `gh` account. `gh auth setup-git` fixes it for good but edits the global git config.
2. **`balls.stl`** in the project root is an earlier export, ignored by git. Keep or delete?
3. **Older CHANGELOG entries** (the tail-call and first-build entries) describe Logo's variable scoping with a term from the banned-word list. Reword the history or leave it?

## Key files
| File | Why it matters |
|---|---|
| `README.md` | User guide, command-pane key table, stencil options, known issues |
| `CHANGELOG.md` | What changed and how it was validated, newest first |
| `termlogo/repl.py` | Command pane and editor (`DrawingControls.readline`), display, history |
| `termlogo/stencil.py` | Stencil engine: strokes, fill cut-outs, bridging, mesh, STL |
| `termlogo/turtle.py` | Turtle state; records strokes and fills for the stencil |
| `termlogo/primitives_turtle.py` | `FILL`, `FILLED`, `STENCIL`, `SAVEPICT` |
| `tests/test_terminal.py` | Editor and live pseudo-terminal tests |
| `tests/test_logo.py` | Language, turtle and stencil tests |

## How to pick it up
```bash
cd ~/Documents/Quests/Projects/20261006_Terminal_Logo_Turtle
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/python -m unittest discover -s tests
./bin/termlogo                                        # REPL
./bin/termlogo examples/stencil_fill.logo -o fill.stl # stencil with cut-outs
```
- If `.venv` is missing: `python3 -m venv .venv && .venv/bin/python -m pip install -r requirements-dev.txt`.
- Commit each change separately.
- Before pushing, check `gh auth status` shows the personal account, then push with `git -c credential.helper= -c credential.helper='!gh auth git-credential' push` until question 1 is settled.
- After a change: update `README.md` and `CHANGELOG.md` (`/wrapup`), and this file if an open item is finished or added.
