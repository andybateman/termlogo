# Handover - Terminal Logo Turtle

**As at:** 2026-10-07 (v1.1.0)

## Purpose
A Logo interpreter with turtle graphics that runs entirely in the terminal, using only the Python standard library. It follows UCBLogo by default, has a Terrapin colour mode for the colour tutorial, and can export a drawing as a 3D-printable stencil. `README.md` is the user guide; this file is the list of what is still to do and how to pick it up.

## Current state
- Version 1.1.0, on `main`, pushed to the public GitHub repository `andybateman/termlogo`.
- Ruff lint and format are clean and the unit and pseudo-terminal tests pass (as at 2026-10-07; run the commands under "How to pick it up" for the live result).
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
| 16 | Browser version (live at www.andybateman.com/termlogo/, published with `tools/publish_site.sh`, which builds into the `andybateman.github.io` checkout, commits and pushes; Pyodide loads from the jsDelivr CDN). Done: animation by changed rows, `LABEL` in PNG/SVG, share links, typing into programs, interruptible Stop (service worker for shared memory, with a fallback). Next: open the live page in Safari, Firefox and on a phone, and check the isolated mode against the real CDN (the page retries without shared memory if Python will not start); then a surface interface so the turtle no longer draws straight into the terminal pixel grid | Next session | Small |
| 14 | Standalone per-platform binaries (PyInstaller or Nuitka via a GitHub Actions matrix on release tags). Needs a token with workflow scope, and `readline` history checked on macOS and Linux. macOS needs signing and notarising to avoid the Gatekeeper warning | Next session | Medium |
| 13 | Try the new REPL features by hand in Ghostty: `READCHAR` and `KEYP` while a program runs, `SETCURSOR`, `--fit 1000` after resizing the window, and the round Braille pen. | Andy | Small |

Can wait: 7, 8, 9 and 11.

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
