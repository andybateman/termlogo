# Changelog - Terminal Logo Turtle

## [2026-10-07] - Homebrew formula
- Added `Formula/termlogo.rb` so the repository can be tapped by URL (`brew tap andybateman/termlogo https://github.com/andybateman/termlogo`, then `brew install termlogo`). It installs the v1.0.0 source with Homebrew's Python 3.13. The formula and its checksum were prepared without a Mac and have not yet been run through `brew install` or `brew test`

## [2026-10-07] - Public repository and MIT licence
- Added the MIT `LICENSE` and a Licence section in the README, and changed the repository to public so the release can be downloaded and installed through a Homebrew tap. HANDOVER.md and the README no longer call it private. History above that mentions the private repository is left as it was written

## [2026-10-07] - Single-file build
- Added `tools/build_pyz.sh`, which builds `dist/termlogo.pyz`: the whole package as one executable zip that runs wherever Python 3.10+ is installed. `dist/` is git-ignored. A test builds the archive and runs it from another directory. Standalone binaries (PyInstaller or Nuitka, one per platform) are not built yet

## [2026-10-07] - v1.0.0
- Released the arrays, property lists, file streams, keys, text cursor, `GOTO`, round pens, XOR `PENREVERSE` and `--fit` work below, and the nested `FILLED` fix. The CLI, startup banner, `VERSION` reporter and README now use version 1.0.0

## [2026-10-07] - Arrays, property lists, files, keys, text cursor, GOTO, round pens and textbook coordinates
- Fixed nested `FILLED`: the inner shape was painted first and then cleared wherever the outer polygon overlapped it. Inner shapes are now painted again on top of the outer one, in order, and the stencil still records each once
- Added arrays: `{a b c}` literals (with `@origin`), `ARRAY MDARRAY LISTTOARRAY ARRAYTOLIST ARRAYP SETITEM MDITEM MDSETITEM`, and array support in `ITEM COUNT FIRST LAST PICK MEMBERP`. The tokeniser now treats `{` and `}` as delimiters
- Added property lists (`PPROP GPROP REMPROP PLIST PLISTS PPS ERPS`; `ERALL` clears them), `GOTO` and `TAG`, and `.MAYBEOUTPUT`
- Added file streams: `OPENREAD OPENWRITE OPENAPPEND OPENUPDATE CLOSE CLOSEALL ALLOPEN SETREAD SETWRITE READER WRITER READPOS SETREADPOS WRITEPOS SETWRITEPOS EOFP FILEP ERASEFILE`. `READWORD READLIST` and `PRINT TYPE SHOW` follow `SETREAD` and `SETWRITE`. Open files are closed when Logo ends
- Added `READCHAR`, `READCHARS` and `KEYP`: immediate key input in the REPL (Escape and Ctrl-C stop the program), character reads from piped input and from files
- Added `CURSOR`, `SETCURSOR` and a working `CLEARTEXT` for the REPL's text area (five rows, per command). Outside the REPL `SETCURSOR` is accepted and does nothing
- Braille and half-block pens are now round brushes of the true width instead of whole-pixel squares
- `PENREVERSE` now XORs colours, so drawing a line twice restores what was under it, and a wide reversed stroke flips each pixel once. It used to toggle a pixel between the pen colour and empty
- Added `--fit N` and `FITWINDOW N`: scale so an N x N Logo window (1000 for textbook programs) fits the canvas; the fit survives terminal resizing
- Not changed: a Braille cell still shows one colour (its most common), because a Braille character has a single foreground colour
- Added the demo screenshots under `docs/images/` and a Gallery section in the README
- Validation (as at 2026-10-07): 302 tests passing, including a live pseudo-terminal test of `READCHAR` and `SETCURSOR`; Ruff lint/format and launcher syntax checks clean. Not tried by hand in Ghostty

## [2026-10-07] - v0.6.0
- Released keyboard editing of multi-line commands, stencil cut-outs for `FILL` and `FILLED`, the `FILLED` fix and the export and colour error fixes. The CLI, startup banner, `VERSION` reporter and README now use version 0.6.0

## [2026-10-07] - Keyboard editing of multi-line commands, stencil cut-outs and fixes
- Put the project under git, with each change below as its own commit, and published it as the private GitHub repository `andybateman/termlogo`. Generated `.stl` files are git-ignored
- README keywords reviewed for the new editing and cut-out features
- Added `HANDOVER.md`: current state, decisions made, open items with owners and outstanding questions. The README files table now lists it and the `values.py`, `errors.py` and `registry.py` modules it had missed
- The README now serves GitHub and the Quests project tools from one file: the `Keywords`, `Status` and date lines sit inside an HTML comment, which GitHub hides and the tools still read. Next Steps became a pointer to `HANDOVER.md`. The repository stays private
- Up and Down now move between the lines of a multi-line command, so a recalled `REPEAT` block or `TO ... END` definition can be edited from the keyboard. They step through history only from the first or last line; Ctrl-P/Ctrl-N and PageUp/PageDown always step through history. This changes one earlier behaviour: Up on a recalled multi-line command no longer jumps straight to the older entry
- Alt+Enter adds a line break at the cursor (Shift+Enter too where the terminal reports it). Home, End, Ctrl-U and Ctrl-K act on the current line; a second Home or End goes to the start or end of the command. Edits to recalled entries are kept while moving through history. A click past the end of a wrapped row no longer lands on the next row
- `STENCIL "name` adds `.stl` when the name does not end with it
- Filled areas are cut out of the stencil. `FILL` removes the area enclosed by the pen lines drawn before it; `FILLED` removes the polygon the turtle traces. Islands left inside are bridged. A `FILL` that is not enclosed, or that starts on a pen line, is left out with a warning. Added `examples/stencil_fill.logo`
- Fixed `FILLED`: it flood-filled from its start point, which is on the outline, so it recoloured the outline and left the shape empty. It now fills the polygon through every point visited (even-odd rule) and outlines it in the pen colour, as UCBLogo does
- Fixed a stale "erased or reversed segment(s)" stencil warning after `CLEARSCREEN` or `CLEAN`; `-o file.stl` now gives the same warnings as `STENCIL`
- `SAVEPICT` and `-o` to a path that cannot be written report an error instead of a Python traceback. Colour errors name the command used (`setbackground doesn't like 99`) rather than always `setpencolor`
- Validation (as at 2026-10-07): 261 tests passing; Ruff lint/format and launcher syntax checks clean. Fill cut-outs were checked by area and as watertight meshes, not in a slicer. Keyboard editing was exercised in pseudo-terminals, not yet by hand in Ghostty: Shift+Enter there relies on Ghostty sending `CSI 27;2;13~`, which is unconfirmed

## [2026-10-06] - v0.5.0
- Released the command-pane, whole-program history, bracketed-paste and startup-guidance improvements. The CLI, startup banner, `VERSION` reporter and README now use version 0.5.0

## [2026-10-06] - Temporary startup guidance and complete pasted-program history
- Restored version, help and mouse-selection guidance until the first command starts executing. It remains visible during incomplete multi-line input, blank/comment lines and cancellation, then clears without discarding command output or returning after the command stops
- Startup guidance wraps with the window and retains space while the command pane grows
- Added bracketed paste so a whole pasted program is one editable buffer and history entry, including setup commands such as `CLEARSCREEN` and `MAKE` before a `REPEAT` block. Paste requires Enter to execute; separately submitted commands remain separate entries
- Pasted tabs retain their source values while displaying as spaces with matching mouse positions. Invalid paste encoding and terminal control characters produce explicit errors; paste mode is restored on leaving the editor
- Validation (as at 2026-10-06): 233 tests passing, including the supplied circle program pasted and recalled with its setup commands intact; 75 terminal tests repeated successfully. Ruff lint/format, compilation, launcher syntax and piped-input checks clean

## [2026-10-06] - Command pane, history and text-overlay repairs
- Removed the three-line startup banner. The command pane grows to show complete multi-line commands and wraps long lines without adding source newlines. It uses output rows before temporarily reducing the canvas, preserving artwork and labels; commands taller than the window scroll with the editing cursor
- Mouse editing works on every visible command row, including earlier continuation lines, wrapped input and recalled procedure definitions. Resizing reflows the source and updates click positions. Long `READWORD` input restores the canvas before execution resumes
- Up recalls whole submitted commands rather than separate continuation lines; Down restores the unfinished draft. Versioned JSON history preserves source newlines and comments, saves atomically, reports load/save errors and still loads legacy readline files
- Fixed Kitty text ghosts by erasing stale canvas text before drawing each image and restoring intentional labels. Input is anchored to its allocated rows instead of scrolling old prompts and status lines into the picture
- Fixed grouped reporter expressions such as `right (-1) ^ (repcount + 1)` while retaining variadic calls and right-associated powers
- Added text-cell and live pseudo-terminal regressions for overlays, large input, whole-command history, mouse editing, reflow, procedure recall and history-file errors
- Validation (as at 2026-10-06): 221 tests passing, including 64 terminal tests repeated successfully; Ruff lint/format, compilation and launcher syntax checks clean. Earlier Kitty rendering is visible in the supplied Ghostty screenshots; the latest repairs still need a visual check after restarting the app

## [2026-10-06] - v0.4.0: interactive controls, NZ spellings and Terrapin colours
- The default drawing speed is now 5 (0 remains instant); `--speed`, the REPL, and `SETSPEED`'s reported initial state use the same default
- Escape stops drawing, `WAIT`, empty loops and tail calls, even after changing from speed 0. Arrow-key escape sequences no longer stop drawing by mistake
- Left-click/drag repositions the turtle at the idle prompt or during drawing without a connector; movement, `HOME` and turns respect the new position. Prompt text, history, completion and Logo input remain usable
- Clicking command input now places its editing cursor without moving the turtle, including scrolled input, terminal resizing and Logo read prompts. Shift-mouse is left to native terminal text selection; the startup hint and help explain Shift-drag and macOS copying
- The interactive canvas follows terminal resizes during input and execution; it retains the current scale, turtle state and labels, restores clipped artwork on enlargement, and avoids accumulating pixel shifts in the half-block renderer. `--size` keeps a fixed canvas
- Added NZ/UK colour spellings for pen/background commands and queries, plus `--no-colour`, alongside the existing US spellings
- Added `--colour-mode terrapin` (also `--color-mode`) for the Terrapin colour lesson without changing UCBLogo defaults. Verified every indexed colour against live WebLogo and the published RGB table; supports Web names, NZ grey aliases, RGB 0-255, optional alpha, RGBA queries, `COLORS`/`COLOURS`, `PEN` and `SETPEN`
- Terrapin mode supports standalone reporters and the lesson's one-based `RANDOM n` range; `FILL` requires a painting pen and supports transparency tolerance. Alpha is preserved through resizing and PNG/SVG export, and brush/animation joins no longer darken a single translucent stroke
- Long REPL output is wrapped before paging, so the complete colour-name list is visible rather than clipped to one terminal row
- Fixed animated WRAP repeating strokes after crossing an edge, overflowing number literals raising internal errors, integer precision loss, and `FILLED` leaving its reported pen colour inconsistent with its actual colour
- `-i` retains the script's procedures, variables and picture. CLI arguments are validated before starting the REPL; piped execution still reports the selected speed
- Added project-local Ruff lint/format settings, pinned development tooling and Git ignores; applied consistent Python formatting and corrected lint findings
- Added persistent resize/input regression tests, including isolated live pseudo-terminal scenarios for scripts and the REPL
- Validation (as at 2026-10-06): 195 tests passing; Ruff lint and formatting clean; live terminal regressions repeated, including command-input clicks, scrolling, resizing and `READWORD`; all existing examples, Python compilation, Python 3.10 syntax compatibility and launcher shell syntax checked. Physical Ghostty rendering remains unverified

## [2026-10-06] - v0.3.0: renderers, speed, stencil export
- Renderers: `--render auto|braille|half|kitty` (and `TERMLOGO_RENDER`). `kitty` draws a real-pixel, anti-aliased image per frame via the Kitty graphics protocol (Ghostty, Kitty, WezTerm; not inside tmux). `half` gives solid half-block lines in any terminal. `auto` uses kitty when the terminal reports its pixel size. Drawings keep the same physical size in every renderer; the pixel grid is capped at 2.5 million for very large terminals
- Anti-aliased round-capped line rasteriser (every pixel visited once, true distance coverage)
- `SETSPEED 0-10` / `SPEED` / `--speed`: paced animation of moves, turns, arcs and fills, redrawn in place at up to about 30 fps inside synchronised-update escapes. Each speed step doubles the rate; turns run six times the step rate in degrees per second. Fence refusals happen before any movement, and Ctrl-C leaves a valid state
- `STENCIL "file.stl [options]` (also `SAVEPICT "x.stl` and `-o x.stl` with `--stencil-opt`): the turtle now records vector strokes (collinear pieces coalesced); the engine builds a signed-distance field, finds islands and ties them back with bridges, traces smooth outlines with marching squares, triangulates with a pure-Python earcut port and extrudes a watertight binary STL. One step is 1 mm and pen size is the slot width (fractions allowed). Slivers under 1 mm2 are filled in and slots under 0.8 mm are widened, each with a warning
- `Display` class shared by the REPL and script mode; in-place redraw, banner shows the renderer
- Fixed during build: a splice that matched the wrong `if name == 'kitty'` mangled `renderers.py`; tests caught a primitive missing from the help table twice
- Verified: STL meshes have zero open edges and positive volume, with volumes matching the geometry (a 40 x 2 mm slot cuts 99.7 mm3 at 1.2 mm thick); timed animation in a pseudo-terminal; 115 unit tests (all passing)

## [2026-10-06] - v0.2.0: help, Tab completion, tail calls
- Version 0.2.0; `--version`, the REPL banner and `VERSION` now show "by Andy Bateman"
- `HELP` command: full list by category, `HELP fd` / `HELP "fd` for one command, `HELP "turtle` for a group, plus topics (`to`, `operators`, `words`, `templates`, `colours`, `keys`). Long output is paged. A unit test fails if any primitive lacks an entry
- Tab completion fixed for macOS `libedit` (the `tab: complete` binding is ignored there); completes primitives, user procedures, help topics and `:variables`
- Tail-call optimisation: a final user-procedure call (also inside a final `IF`/`IFELSE`, or `OUTPUT proc ...`) runs in `call_user`'s loop. A caller's frame is dropped only when every variable in it is shadowed, so Logo's dynamic scope is preserved. One million iterations ran in constant memory (14 MB peak); Ctrl-C stops an endless loop
- Fixed during build: tail-call frame dropping first lost a caller's `LOCAL` variable that the callee should still see
- 64 unit tests (all passing)

## [2026-10-06] - v0.1.0: interpreter, turtle, canvas, REPL
- Added the `termlogo` package (standard library only): lexer, evaluator with dynamic scope and optional/rest inputs, and about 250 primitives covering control flow, templates, words and lists, maths, and the full UCBLogo turtle set
- Braille canvas (2x4 dots per cell) with 24-bit colour, turtle marker, labels, flood fill, pen modes, WRAP/WINDOW/FENCE, and SVG/PNG/text export
- Interactive REPL (canvas above, log below, Tab completion, history, multi-line `TO`), script mode, `-e`, `-i`, `-o`, `--size`, `--scale`
- Workspace commands `SAVE`, `LOAD`, `PO`; `SAVEPICT` exports the picture. `SETSCALE` is a non-standard extension
- Recursion limit raised to 25,000 levels with a clean "Stack overflow" error; no tail-call optimisation yet
- Five example programs and 54 unit tests (all passing)
- Fixed during build: procedures with optional inputs consumed all inputs when called without parentheses; `|word with spaces|` literals were not tokenised

## [2026-10-06] - Project created
- Project created after PythonTurtle proved GUI-only (wxPython) and the stdlib `turtle` needs Tk
- Seed files: README.md, CHANGELOG.md
