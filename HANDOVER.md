# Handover - Terminal Logo Turtle

**As at:** 2026-10-07 (v0.6.0)

## Purpose
A Logo interpreter with turtle graphics that runs entirely in the terminal, using only the Python standard library. It follows UCBLogo by default, has a Terrapin colour mode for the colour tutorial, and can export a drawing as a 3D-printable stencil. `README.md` is the user guide; this file is the list of what is still to do and how to pick it up.

## Current state
- Version 0.6.0, on `main`, pushed to the private GitHub repository `andybateman/termlogo`.
- Ruff lint and format are clean and the unit and pseudo-terminal tests pass (as at 2026-10-07; run the commands under "How to pick it up" for the live result).
- Added on 2026-10-07: keyboard editing of multi-line commands recalled from history, `.stl` added to `STENCIL` names, `FILL` and `FILLED` areas cut out of the stencil, and a repaired `FILLED`.
- Not yet checked by hand: the new command-pane keys in a real Ghostty window, and the fill cut-outs in a slicer or on the printer. Both are covered only by automated tests so far.

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
| Repository name `termlogo`, created private | Name chosen by Andy. Private was the cautious default and has not been confirmed |

## Open items
Low-effort checks first. "Next session" means work for Claude with Andy.

| # | Item | Owner | Effort |
|---|---|---|---|
| 1 | Try the command-pane keys by hand in Ghostty: Up/Down inside a recalled block, Option+Enter, Home/End twice. Confirm whether Shift+Enter adds a line (it relies on Ghostty sending `CSI 27;2;13~`) | Andy | Small |
| 2 | Recheck Kitty rendering in a restarted Ghostty session (carried over from 2026-10-06) | Andy | Small |
| 3 | Open `examples/stencil_fill.logo` output in a slicer, then test-print one stencil | Andy | Small, then a print |
| 4 | Decide how the README serves both GitHub and the Quests project system (see Outstanding questions) | Andy | Small |
| 5 | Stencil: detect joins too thin to print. A pen-up `FILLED` star leaves its centre held at five points and is not flagged | Next session | Medium |
| 6 | A newline key that works in every terminal: make Ctrl-J insert a line by clearing `ICRNL`. About 60 test inputs change from `\n` to `\r` | Next session | Medium, mechanical |
| 7 | Nested `FILLED`: the inner shape is painted first and then covered by the outer one. Decide the intended result, then repaint inner shapes last | Next session | Small |
| 8 | Stencil extras: text from `LABEL` via a stencil font, rounded plate corners, 3MF output | Next session | Large |
| 9 | Language gaps: arrays, property lists, `READCHAR` | Next session | Medium |
| 10 | Side-by-side conformance list against UCBLogo | Next session | Medium |
| 11 | Install route for the MacBook setup: the `termlogo` link in `~/.oh-my-zsh/oh-my-custom/bin/` is not in the setup script | Andy | Small |
| 12 | Wider Ruff rules (`UP`, `SIM`, `RUF`): roughly 160 style points, none of them bugs (as at 2026-10-07) | Next session | Small |
| 13 | Tag the release (`v0.6.0`) if tags are wanted | Andy | Small |

Can wait: 8, 9, 10 and 12.

## Outstanding questions
1. **README for GitHub.** The `Keywords`, `Status`, `Start Date` and `Last Updated` lines exist for the Quests project system and look odd on GitHub. Recommended: keep one `README.md` and wrap those lines in an HTML comment. GitHub hides comments, while the projects tool, the session hook and the skills still find the lines. The alternatives are a second `.github/README.md` (GitHub shows it in preference, but the two files drift) or a local-only extra file (the project tooling reads `README.md` only, so it would need changing).
2. **Public or private?** If it goes public it needs a licence file first, and the "(private)" note in the README removed.
3. **Git credentials.** Plain `git push` fails because git uses the macOS keychain login rather than the active `gh` account. `gh auth setup-git` fixes it for good but edits the global git config.
4. **`balls.stl`** in the project root is an earlier export, ignored by git. Keep or delete?
5. **Older CHANGELOG entries** (the tail-call and first-build entries) describe Logo's variable scoping with a term from the banned-word list. Reword the history or leave it?

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
- Commit each change separately, with no `Co-Authored-By` trailer.
- Before pushing, check `gh auth status` shows the personal account, then push with `git -c credential.helper= -c credential.helper='!gh auth git-credential' push` until question 3 is settled.
- After a change: update `README.md` and `CHANGELOG.md` (`/wrapup`), and this file if an open item is finished or added.
