# Changelog - Terminal Logo Turtle

## [2026-10-07] - Removed a one-off release script
- Removed `docs/release-pyz-instructions.txt`, which added the `termlogo.pyz` instructions to the v1.0.0 release notes and has been run. Release notes now live in `docs/release-notes-vX.Y.Z.md` and carry those instructions

## [2026-10-07] - v1.2.0
- Released the redesigned browser page (the canvas fills the window and follows its size, with a divider, Expand and full screen for more room, a searchable Help panel, Open and Save), the fix for deep recursion crashing Python 3.10 and 3.11, the review fixes (browser recursion limit, file streams, `PPS`, faster resizing), `SETSCALE` ending a `FITWINDOW`, examples that fit themselves to the canvas, and the browser screenshots in the README. The CLI, startup banner, `VERSION` reporter and README now use version 1.2.0. Release notes: `docs/release-notes-v1.2.0.md`
- Published on GitHub with `termlogo.pyz`, which runs on Python 3.10 and 3.13 and reports `Stack overflow` for runaway recursion on 3.10 and 3.11. The Homebrew formula now installs 1.2.0: its checksum matches the tag's archive, and the formula's install steps and test pass when run by hand. `brew upgrade` then installed 1.2.0 on a Mac

## [2026-10-07] - Screenshots of the browser version in the docs
- The README's Browser version section now shows the page in a laptop window and on a phone (`docs/images/browser.png` and `docs/images/browser-phone.png`), and the GitHub front page shows the laptop view beside a terminal drawing
- `tools/web_screenshots.mjs` retakes both after the page changes, with the same setup as `tools/web_smoke.mjs`: the default program at Instant speed, in light mode and a fresh browser profile

## [2026-10-07] - Browser page redesign: more room for the canvas
- The page now fills the window: the editor, the `?` command line and the output on the left, and the canvas filling the rest. The canvas follows its pane's size (one pixel per turtle step, up to 1920x1200 pixels, stretched beyond that) instead of a fixed 800x600. The divider between the editor and the canvas can be dragged, or moved with the arrow keys; double-clicking it puts it back, and its place is remembered. **Expand canvas** hides the editor, and a full-screen button shows the canvas alone. On phones the canvas comes first and the toolbar is one row that scrolls sideways
- The toolbar stays on one row from 1024 pixels wide (below 1180 the Expand button shows just its icon), and the bar under the canvas tightens as its pane narrows (a CSS container query)
- New on the page: **Help** (getting started, the keys, a searchable list of all 226 commands built into `help.json` from the `HELP` table, and a sample that runs in a fresh workspace); **Open** and **Save** for `.logo` files; the turtle coordinates under the pointer; the turtle shown before anything runs; examples run when picked; a **Zoom** chip when `FITWINDOW` or `SETSCALE` has changed the scale (click it for `SETSCALE 1`); the last error repeated in the status bar, for when the editor is hidden; command history kept between visits
- Fixes: on phones the editor covered the status bar and the download buttons; a hidden button could still show (a `display` rule beat the `hidden` attribute); a Stop pressed just as a program ended restarted Python instead of finishing the run; and `SETSCALE` after `FITWINDOW` was undone by the next resize, because the fit was kept (`SETSCALE` now ends it)
- The examples start with `FITWINDOW`, so they fill any canvas: `koch` is now centred instead of clipped, and `tree` fits without `--size`. The gallery images are re-rendered at `--size 100x40`
- Validation (as at 2026-10-07): 343 unit tests pass on Python 3.10, 3.11, 3.12 and 3.13, and ruff is clean. `tools/web_smoke.mjs` passes all 72 checks in headless Chromium: the desktop page, a 1024-pixel laptop, a phone, the fallback without shared memory, and a failed start, with Pyodide from a local server standing in for the CDN. Not yet tried in Safari or Firefox, or on a real phone

## [2026-10-07] - Review fixes: browser recursion limit, file streams, PPS, resizing
- In the browser, an exception unwinding through more than about 3,000 Python frames kills Pyodide ("Maximum call stack size exceeded"), and errors, `STOP`, `OUTPUT`, `THROW` and the Stop button all travel as exceptions. The recursion limit there is now 2,000 frames (`python_frame_limit` for the `emscripten` platform), so runaway recursion reports `Stack overflow`. That allows about 140 levels of Logo recursion when the call is inside an expression, and about 400 otherwise; tail calls are unaffected. If Python stops anyway, the page restarts it and says so
- File streams open as UTF-8, and bytes that are not UTF-8 read as a replacement character instead of stopping the program. `SETREAD` and `SETWRITE` refuse a file opened the other way. Files still open at exit are closed by one handler, registered once (it was registered again each time the first file was opened)
- `PPS` quotes words (`pprop "name "prop "value`, with `|...|` around spaces and brackets), so its output can be run to rebuild the property lists
- The browser glue can resize the canvas without losing the drawing (`Session.resize`: Logo coordinates are kept, and parts clipped by a smaller canvas return when it grows) and can resend the whole picture (`refresh`). The final picture of a run carries only the changed rows, unless the background changed. Resizing at an unchanged scale now copies whole rows rather than single pixels, which the terminal uses too
- Tests: browser recursion limit, every example within it, `PPS` read-back, stream direction, non-UTF-8 input, the exit handler, resize and refresh, the size cap, and row copying matching the pixel-by-pixel result

## [2026-10-07] - Fix: deep recursion crashed Python 3.10 and 3.11
- Runaway or very deep recursion could crash the whole interpreter (segmentation fault) instead of reporting `Stack overflow`: on Python 3.10 beyond about 600 levels of ordinary recursion, and on 3.11 when the recursion went through `REPEAT`, `RUN`, `CATCH` or `FOREACH`. The interpreter raised Python's recursion limit to 400,000, which only Python 3.12 and later can survive (they check the C stack themselves). The limit now follows the Python version (`interp.python_frame_limit`): 400,000 from 3.12, 150,000 on 3.11 and 5,000 on 3.10, each well inside the measured crash point on an 8 MB stack. On 3.10 that means `Stack overflow` after a few hundred levels of non-tail recursion; tail calls are unaffected
- Validation (as at 2026-10-07): the full suite (329 tests) passes on Python 3.10.20, 3.11.17, 3.12.3 and 3.13.16; it had never been run on 3.10 before. A new test drives runaway recursion through six different commands and expects `Stack overflow`

## [2026-10-07] - Browser version: no stale files after an update
- A browser that had visited before could run an old `termlogo.zip` (the Python engine) against a new page, because GitHub Pages lets files be kept for ten minutes. Every file the page loads (`app.js`, `worker.js`, `style.css`, `termlogo.zip`, `examples.json`) is now requested as `name?v=STAMP`, where STAMP is a hash of the built contents (also in `config.json` as `build`, which is always fetched fresh). A changed build can no longer be paired with old files; the one thing left is the page's own `index.html`, which a browser may keep for up to ten minutes
- Tests: the stamp is in every reference, and changes when the content does

## [2026-10-07] - Browser version shows its version; one-command publishing
- The page now shows the version, commit and date it was built from under its title (for example `v1.1.0 · 4391b23 · 2026-10-07`, with `+changes` if the working tree differed from the commit), and `config.json` carries the same, so a stale live copy is easy to spot
- `tools/publish_site.sh` builds into the `andybateman.github.io` checkout, commits and pushes (`--no-push` stops before the push; it refuses a site checkout with other uncommitted changes). The build is now reproducible: the package zip uses fixed file dates and the stamp uses the commit's own date, so the same commit gives the same bytes and publishing twice commits nothing
- Tests: build and publish tests in `tests/test_build.py` (a throwaway git repository stands in for the site), and a browser check that the page shows the version Python reports

## [2026-10-07] - v1.1.0
- Released the browser version (live at https://www.andybateman.com/termlogo/) with its smoother animation, `LABEL` text in downloads, share links, typing into running programs and interruptible Stop, plus the Homebrew formula, the single-file `termlogo.pyz`, the redrawn AB monogram example and the MIT licence. The CLI, startup banner, `VERSION` reporter and README now use version 1.1.0. Added `tools/update_formula.sh VERSION`, which points the Homebrew formula at a release once its tag exists

## [2026-10-07] - Browser version: smoother animation, labels in downloads, share links, typing and Stop
- **Animation:** the engine now sends only the rows of the picture that changed (as RGBA bytes) instead of a whole PNG, and the page draws the turtle and `LABEL` text itself. `Canvas` tracks the changed rows (`take_dirty_rows`, `mark_all_dirty`) and can produce them (`rgba_rows`). A speed-8 circle that took about 1.4 seconds now takes about 0.5, and a speed-5 square runs at the set pace
- **Exports:** PNG downloads are made by the page from the drawing plus `LABEL` text, without the turtle marker; SVG downloads now include `LABEL` text as `<text>` elements
- **Share link:** copies an address holding the program, compressed with deflate and kept after the `#` so no server sees it. Opening one loads the program into the editor and does not run it
- **Typing and Stop:** `READWORD`, `READLIST`, `READCHAR` and `KEYP` now work in the page (lines from the box under the editor, keys from the canvas), `WAIT` can be interrupted, and Stop and Esc raise `KeyboardInterrupt` in Python, so the workspace survives. This uses shared memory, which needs a cross-origin isolated page; `web/coi-sw.js`, a small service worker, supplies the headers GitHub Pages cannot (one automatic reload on the first visit). Where that is unavailable, or Python will not start with it, the page falls back to the earlier behaviour and remembers (`localStorage`, or `?nocoi`)
- Tests: 17 for the glue (`tests/test_web.py`, with a fake host for input and Stop) and 43 browser checks in `tools/web_smoke.mjs`, including the fallback and a failed start. All pass in headless Chromium against a local server standing in for the CDN. Not tried in Safari or Firefox, on a phone, or with the real CDN while isolated (the headers the CDN sends should allow it, but this is the one thing that could stop Python starting there; the page then retries without shared memory)

## [2026-10-07] - Link to the live browser version
- The README and the GitHub front page (`.github/README.md`) now link to the live browser version at https://www.andybateman.com/termlogo/, near the top. The repository's website field is a GitHub setting, not a file: `gh repo edit andybateman/termlogo --homepage https://www.andybateman.com/termlogo/`

## [2026-10-07] - Browser version hosted on andybateman.com
- The browser version is published as static files at `/termlogo/` in the `andybateman/andybateman.github.io` repository (live at https://www.andybateman.com/termlogo/). `python3 tools/build_web.py --out ../andybateman.github.io/termlogo` updates it; `build_web.py` now refuses to replace a folder it did not make (one without its `config.json`) unless it is empty, so a mistyped `--out` cannot delete anything. The page has an SVG favicon (`web/favicon.svg`) in place of the empty one, which the site's html-proofer Favicon check wanted
- Checked by building the site with its own Jekyll configuration in production mode (builds cleanly, html-proofer passes all five README checks) and by running the 22 browser checks against `/termlogo/` served from the built site, with Pyodide from a local server standing in for the CDN. The real CDN download was checked separately on macOS (the entry below); the deployed copy at andybateman.com has not been opened yet

## [2026-10-07] - AB monogram example redrawn as an animation
- Rewrote `examples/ab_logo.logo` in 21 lines without comments: white on black, each letter traced with `FD` and `LT` by a visible turtle and then filled with `FILLED`, after which the turtle turns and moves to the bottom-right corner. The outline is the same shape as before; `:k` is folded into the measurements. `docs/images/ab_logo.png` re-rendered to match
- Validation (as at 2026-10-07): 314 unit tests passing. `tools/web_smoke.mjs` passed all 22 checks in headless Chrome on macOS against a fresh `dist/web`, with Pyodide loaded from the real jsDelivr CDN, which the earlier browser entries could not reach. The smoke test runs examples at speed 0, so the animation has not been watched in a browser or a real terminal

## [2026-10-07] - Browser version: Pyodide from the CDN
- The browser version now loads Pyodide 314.0.7 from the jsDelivr CDN (`https://cdn.jsdelivr.net/npm/pyodide@314.0.7/`) by default, so the built site is about 0.1 MB instead of 14 MB. `build_web.py --bundle-pyodide` still copies Pyodide beside the page (the page reads `config.json` to know which), and `?pyodide=URL` overrides both. The Pages workflow no longer needs npm
- Fixed: if Python failed to start (for example the CDN was blocked) the page said "Ready" with every button disabled. It now says "Could not start Python" and explains what to check
- Checked in Chromium against a local server on another origin with CORS headers, standing in for the CDN: all 22 smoke checks pass. The CDN itself could not be reached from the build environment, so the real jsDelivr download has not been tested

## [2026-10-07] - Browser version (first version)
- Added a browser version of the engine: `web/` (page, editor, command line, canvas, example menu, speed and colour-mode controls, PNG/SVG/STL downloads) running the unchanged Python engine through Pyodide in a Web Worker. `termlogo/web.py` is the glue (a `Session` that runs Logo and posts text, pictures and files to the page), `Canvas.frame_png` gives it a picture with the turtle marker, and `tools/build_web.py` builds `dist/web` (page, package zip, examples, Pyodide 314.0.7 fetched with npm). `docs/pages-workflow.yml` is a GitHub Pages workflow to move into `.github/workflows/`
- Known differences: keyboard input commands see an empty keyboard; Stop replaces the worker and so loses the workspace; `LABEL` text is not in PNG/SVG downloads; pictures travel as PNGs, which limits animation to roughly 10 frames a second
- Validation (as at 2026-10-07): 314 unit tests passing (11 new for the glue, run without a browser); a Chromium run of `tools/web_smoke.mjs` passed 22 checks: Python starts in about 4 seconds locally, every example draws, labels, history, errors, PNG/SVG/STL downloads, animation, Stop and restart, and Terrapin mode all work, with no console errors. The CDN was not reachable from the build environment, so Pyodide is self-hosted. Not tried on a phone, in Safari or Firefox, or from GitHub Pages

## [2026-10-07] - Homebrew formula
- Added `Formula/termlogo.rb` so the repository can be tapped by URL (`brew tap andybateman/termlogo https://github.com/andybateman/termlogo`, then `brew install termlogo`). It installs the v1.0.0 source with Homebrew's Python 3.13. The formula installs and runs on macOS (checked by hand with `brew install` and `brew test`). Newer Homebrew refuses third-party taps until they are trusted, so the instructions include `brew trust --formula andybateman/termlogo/termlogo`


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
