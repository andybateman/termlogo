# Terminal Logo Turtle

**Keywords:** Logo, turtle graphics, terminal, REPL, Python, interpreter, Braille graphics, Kitty graphics, Ghostty, UCBLogo, tail recursion, animation, 3D printing, stencil, STL, SVG export, education, Terrapin Logo, RGBA, colours
**Status:** Active (v0.5.0; as at 2026-10-06)
**Start Date:** 2026-10-06
**Last Updated:** 2026-10-06

## Overview
A Logo interpreter with turtle graphics that runs entirely in the terminal. Python's built-in `turtle` needs a Tk window and PythonTurtle needs wxPython, so neither works over SSH or in a plain terminal. This one draws with Unicode Braille characters (2x4 dots per cell) in 24-bit colour, uses only the Python standard library (Python 3.10 or later), and follows UCBLogo behaviour by default. A selectable Terrapin colour mode supports its colour tutorial without changing existing programs.

## Usage
```bash
./bin/termlogo                      # interactive REPL (canvas above, text log below)
./bin/termlogo examples/tree.logo   # run a file, print the canvas
./bin/termlogo -e 'repeat 36 [fd 30 rt 100]'
./bin/termlogo prog.logo -i         # continue in the REPL with the same workspace/picture
./bin/termlogo prog.logo -o out.svg # export (.svg, .png, .txt or .stl)
./bin/termlogo examples/flower.logo  # watch it draw (default speed 5)
./bin/termlogo examples/flower.logo --speed 0 # draw instantly
./bin/termlogo --render half         # braille | half | kitty | auto
./bin/termlogo --colour-mode terrapin # Terrapin tutorial colours and RGBA
python3 -m unittest discover -s tests
```
Options: `--render`, `--speed 0-10` (default 5; 0 draws instantly), `--colour-mode`/`--color-mode ucblogo|terrapin` (default `ucblogo`), `--stencil-opt KEY=VALUE`, `--size COLSxROWS`, `--scale S` (pixels per turtle step, default 1; use 0.5 for drawings built for a 400x400 screen), `--no-color`/`--no-colour`, `--no-canvas`. REPL: Tab completes names, history is kept in `~/.termlogo_history`, `BYE` or Ctrl-D leaves.

Inside the REPL, `HELP` lists every command by category, `HELP fd` or `HELP "turtle` explains one, and Tab completes command names, your own procedures and `:variables`. `PRINT VERSION` (or `--version`) shows the version and author.

**Renderers** (`--render`, or `TERMLOGO_RENDER`; `auto` is the default):
- `kitty`: one real-pixel image per frame with anti-aliased lines, for terminals that speak the Kitty graphics protocol (Ghostty, Kitty, WezTerm). `auto` picks it when the terminal reports its pixel size; it is not used inside tmux or screen.
- `half`: solid half-block characters, 1x2 pixels per cell. Works in any terminal and has no gaps, but is a quarter of Braille's resolution.
- `braille`: 2x4 dots per cell. The most detail without graphics support, but lines look dotted.

A drawing keeps the same physical size in every renderer (one step is half a cell wide).

**Speed and input:** `SETSPEED 0-10` (or `--speed`) lets you watch it draw. The default is 5; 0 is instant and each step doubles the speed. Piped runs and exports do not animate, but `SPEED` still reports the chosen setting. Moves, turns and arcs are paced, with redraws at up to about 30 frames a second. Escape or Ctrl-C stops the current program, including `WAIT` and loops; at the prompt it cancels the input line. On macOS/Linux in a mouse-reporting terminal, click or left-drag on the canvas to reposition the turtle, including while idle. During drawing, its current movement ends there without drawing a connector, and the next Logo command continues from that point.

The macOS/Linux command pane accepts cursor keys, Home/End, Backspace/Delete, Tab completion and Up/Down history. It grows to display the whole command: source newlines occupy separate rows, and long lines wrap without changing the source. The startup version, help and mouse-selection guidance stays visible until the first command starts running, including while typing an unfinished multi-line command. Blank lines, comments and cancelled input do not dismiss it. Extra command rows use the output area first, then temporarily reduce the canvas; the picture is restored when editing ends. Commands taller than the terminal scroll to keep the editing cursor visible. `--size` still keeps a fixed canvas.

**Up recalls a complete submitted command**, including an entire multi-line `REPEAT` block or `TO ... END` definition. Down restores your unfinished draft. Click any visible command row to edit it, including earlier continuation lines; this does not move the turtle. Mouse positions follow wrapping and window resizing. Canvas clicks and terminal resizes preserve your draft. `READWORD` and `READLIST` use the same mouse-aware input handling. History is saved as versioned JSON in `~/.termlogo_history`; older readline history files still load, although their existing per-line entries remain separate. Long output is wrapped and paged in the REPL, so lists such as `COLOURS` can be read in full.

**Pasting a program:** in a bracketed-paste terminal such as Ghostty, a multi-line paste stays together in the editor. Press Enter to run it. Up then recalls the entire pasted program, including setup commands before a `REPEAT` block, rather than only the final block. Pasted tabs and line breaks are retained in the source; tabs are displayed as spaces. Commands entered separately remain separate history entries and can be reached with further Up presses.

**Text selection:** hold **Shift** while dragging to select terminal text, then use **Cmd+C** to copy on macOS. Ordinary clicks are reported to the app for canvas positioning and command editing; Ctrl-C still stops the program. Ghostty allows Shift-selection by default. If your configuration captures Shift-mouse too, `mouse-shift-capture = never` reserves it for native selection (see the [Ghostty reference](https://ghostty.org/docs/config/reference#mouse-shift-capture)).

### Terrapin tutorial colours
For the [Terrapin colour lesson](https://resources.terrapinlogo.com/weblogo/learning_center/colors), start with `./bin/termlogo --colour-mode terrapin`. The mode applies to scripts, exports and `-i` continuation too.

| Behaviour | UCBLogo mode (default) | Terrapin mode |
|---|---|---|
| Numbered colours | Original palette, initially 0-15 | Live WebLogo palette, 0-138; 138 is transparent |
| Colour names | Original Logo names | Web names, including both `grey` and `gray`, `aqua` and `fuchsia` |
| RGB inputs | `[r g b]`, components 0-100 | `[r g b]`, components 0-255; optional fourth alpha 0-1 |
| `PC` / `PENCOLOR`, `BG` / `BACKGROUND` | Original input | Always `[red green blue alpha]` |
| Standalone reporters | Use `PRINT` or `SHOW` | Values are printed, so `PC`, `BG` and `COLOURS` work on their own |
| `RANDOM n` | 0 through n-1 | 1 through n, matching the lesson's random-colour examples |

The indexed palette was checked against live WebLogo and its published RGB table (as at 2026-10-06). `COLOURS`/`COLORS` lists names in index order; `setpc random 138` selects indices 1-138, and `setpc (random 139)-1` includes 0. Some older manual examples are inconsistent: the live palette's gold is index 59, while 60 is goldenrod.

`SETPEN [penstate colour]` changes the pen state and colour together. Use the full words `PENUP`, `PENDOWN`, `PENERASE` or `PENREVERSE`; `PEN` reports that state. In Terrapin mode, `PD` returns to ordinary painting, and `FILL` only runs with the pen in `PENDOWN`. `(fill 0)` stops at differing colours, default `FILL` crosses pixels with alpha below 0.5, and `(fill 1)` fills the whole canvas.

Alpha is composited over existing strokes and the current background, preserved through resizing, and retained in PNG/SVG exports. `SETBG` does not alter existing artwork. `SETALPHA` changes the default alpha for subsequent pen colour inputs; explicit RGBA inputs override it, while background colours default to alpha 1. The initial Terrapin state is a black pen on transparent white. Terminal renderers display transparency against white when no opaque background is set.

For example, in Terrapin mode:
```logo
setpencolour [255 0 0 0.5]
pencolour
setpen [pendown royalblue]
setbg [240 248 255]
repeat 4 [fd 20 rt 90]
pu setxy 7 7 pd setpc "pink fill
background
colours
```

This is colour-focused compatibility, not a complete Terrapin interpreter. Browser undo controls, background images and patterns are not implemented. UCBLogo's `PALETTE` and `SETPALETTE` remain available only in UCBLogo mode.

**3D-printable stencil:** `STENCIL "plate.stl` (or `(stencil "plate.stl [thickness 1.6 margin 10])`, `SAVEPICT "plate.stl`, or `-o plate.stl`) turns the pen strokes into slots cut through a flat plate and writes a binary STL. One step is 1 mm and pen size is the slot width (`SETPENSIZE 2` cuts 2 mm slots; fractions work). Parts that would fall out, such as the centre of an O, are tied back with bridges automatically. Options: `thickness 1.2`, `margin 8`, `bridge 1.6`, `bridges 2`, `width` (force every slot), `minwidth 0.8`, `plate [w h]`, `mirror true`, `pitch 0.2`, `mm 1`, `maxgap 15`. Try `termlogo examples/stencil_demo.logo -o demo.stl`. Slots narrower than 0.8 mm are widened, and islands smaller than 1 mm2 are filled in, with a warning for each. Only strokes drawn with the pen painting are used: text from `LABEL`, `FILL`, and erased strokes are ignored.

An 80x24 terminal gives the REPL a 160x64 pixel Braille canvas centred on (0,0), so coordinates run about -80..80 across and -32..32 up. The canvas follows terminal resizing, both at the prompt and while running a program. The scale, turtle state, strokes and labels are retained; artwork clipped by a smaller window reappears when it grows again. `--size` fixes the canvas dimensions. Larger terminals or `--scale` give more room. WINDOW mode (the default) lets the turtle roam off-screen, as in UCBLogo.

## What works
- **Language:** `TO ... END` (with optional `[:x default]` and `[:rest]` inputs), variables with dynamic scope (`MAKE`, `LOCAL`, `LOCALMAKE`, `THING`, `NAME`, `GLOBAL`), infix operators `+ - * / ^ = <> < > <= >=` with Logo's unary-minus spacing rule, parenthesised variadic calls, `|word with spaces|`, comments, line continuation with `~`.
- **Control:** `REPEAT FOREVER REPCOUNT IF IFELSE TEST IFTRUE IFFALSE WHILE UNTIL DO.WHILE DO.UNTIL FOR STOP OUTPUT RUN RUNRESULT CATCH THROW ERROR WAIT BYE`, plus `FOREACH MAP FILTER FIND REDUCE APPLY INVOKE` with `?`/`?1`/`?2` slots, procedure names and `[[a b] body]` lambdas.
- **Data:** `WORD LIST SENTENCE FPUT LPUT COMBINE FIRST LAST BUTFIRST BUTLAST ITEM COUNT MEMBER REVERSE REMOVE REMDUP PICK ISEQ RSEQ UPPERCASE LOWERCASE CHAR ASCII` and the predicates (`EMPTYP LISTP WORDP NUMBERP MEMBERP EQUALP BEFOREP NAMEP PROCEDUREP PRIMITIVEP`).
- **Maths:** `SUM DIFFERENCE PRODUCT QUOTIENT REMAINDER MODULO INTQUOTIENT MINUS ABS INT ROUND SQRT POWER EXP LN LOG10 PI SIN COS TAN ARCTAN ARCSIN ARCCOS RANDOM RERANDOM AND OR NOT BITAND BITOR BITXOR ASHIFT` and the comparison words. Trig is in degrees.
- **Turtle:** `FD BK LT RT PU PD HOME CS CLEAN SETPOS SETXY SETX SETY SETH ARC DOT HT ST FILL FILLED LABEL WRAP WINDOW FENCE`, pen modes `PPT PE PX`, `SETPC SETBG SETPEN SETPENSIZE SETPALETTE`, and the queries `POS XCOR YCOR HEADING TOWARDS DISTANCE SHOWNP PENDOWNP PEN PENCOLOR/PENCOLOUR BACKGROUND WRAPP COLOURS/COLORS`. Colour inputs follow the selected mode described above. US and NZ spellings are accepted, including `SETPENCOLOR`/`SETPENCOLOUR` and `SETSCREENCOLOR`/`SETSCREENCOLOUR`.
- **Workspace:** `PO POTS PONS ERASE ERALL DEFINE TEXT SAVE LOAD`, `PRINT TYPE SHOW READWORD READLIST`.
- **Tail calls:** a final call in a procedure (also inside a final `IF`/`IFELSE`, or `OUTPUT proc ...`) runs as a loop, so `to loop ... loop end` runs indefinitely in constant memory. Escape or Ctrl-C stops it in the terminal. Other recursion is capped at 25,000 levels and then reports "Stack overflow".
- **Extensions:** `SETSCALE n` (same as `--scale`), `SETSPEED`/`SPEED`, `STENCIL`, `SAVEPICT "file.svg|png|txt|stl`, `HELP`, `VERSION`.

## Not implemented yet
- Arrays (`ARRAY SETITEM`), property lists (`PPROP GPROP`), file streams (`OPENREAD` and friends), `READCHAR`, text-screen cursor control, `.MAYBEOUTPUT`, `GOTO`/`TAG`.
- Braille and half-block pen sizes are rounded to whole-pixel square brushes. Kitty painting uses anti-aliased, round-capped strokes. `PENREVERSE` toggles dots rather than XOR-ing colours, and each Braille cell shows its most common colour.
- Coordinates are screen-sized, not the 1000x1000 of a typical Logo window, so unscaled programs from textbooks may need `--scale`.

## Files
| File | Purpose |
|---|---|
| `termlogo/lexer.py` | Tokeniser (words, nested lists, unary-minus rule, `\|words\|`) |
| `termlogo/interp.py` | Evaluator: scopes, procedures, infix parsing, templates |
| `termlogo/primitives_core.py` | Control, variables, procedures, I/O, workspace files |
| `termlogo/primitives_data.py` | Words, lists, arithmetic, logic |
| `termlogo/primitives_turtle.py` | Turtle and screen commands |
| `termlogo/turtle.py` | Turtle state, movement, WRAP/WINDOW/FENCE, colour parsing |
| `termlogo/colours.py` | Terrapin's indexed Web colours, RGB/RGBA parsing and alpha compositing |
| `termlogo/canvas.py` | Pixel canvas, anti-aliased lines, Braille, half-block and Kitty renderers, SVG/PNG/text export |
| `termlogo/renderers.py` | Terminal detection, renderer choice, canvas factory, frame composition |
| `termlogo/stencil.py` | Stencil engine: signed-distance field, bridging, marching squares, extrusion, STL |
| `termlogo/earcut.py` | Polygon-with-holes triangulation (port of the earcut algorithm) |
| `termlogo/helptext.py` | Help table (a unit test fails if any command lacks an entry) |
| `termlogo/repl.py`, `__main__.py` | REPL, Tab completion, paging, command line |
| `bin/termlogo` | Launcher that runs from this folder without installing |
| `examples/` | `flower`, `tree`, `koch`, `spiral`, `stars`, `stencil_demo` |
| `tests/test_logo.py` | Unit tests |
| `tests/test_terminal.py` | Resize, input and live pseudo-terminal regression tests |
| `tests/test_colours.py` | Terrapin lesson, palette, transparency and compatibility regressions |
| `ruff.toml`, `requirements-dev.txt` | Project lint/format settings and pinned development tooling |

## Development checks
The interpreter needs no third-party packages. Ruff is a development-only dependency:
```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/python -m unittest discover -s tests
sh -n bin/termlogo
```
The lint rules cover Python errors, unused names, imports and Bugbear checks. Formatting is checked separately. The terminal tests use isolated pseudo-terminals and temporary history files; they do not drive the current terminal.

## Next Steps
1. Recheck Kitty rendering in a restarted Ghostty session after the command-pane and text-overlay repairs; the earlier rendering was observed in the supplied screenshots (as at 2026-10-06)
2. Stencil: filled regions (`FILL`) as cut-out areas, text via a stencil font, rounded plate corners, 3MF output
3. Arrays, property lists and `READCHAR`
4. Check behaviour against UCBLogo with a side-by-side conformance list
5. Decide the install route for the MacBook setup (the `termlogo` link in `~/.oh-my-zsh/oh-my-custom/bin/` is not yet in the repo's setup script)

## Known Issues
- A tail call whose callee does not rebind the caller's variables keeps the caller's frame (Logo scope is dynamic), so an endless loop that hops between differently named procedures grows slowly in memory. Self-recursive loops do not.
- Kitty graphics have been observed in Ghostty (as at 2026-10-06). Redraws now erase stale canvas text before placing the image, while retaining intentional `LABEL` text. The latest repairs still need a visual check in a restarted session. If rendering misbehaves, run with `--render half` or set `TERMLOGO_RENDER=braille`.
- Stencils are checked as watertight meshes, not yet test-printed or opened in a slicer.
- REPL and script interactions are exercised in pseudo-terminals on macOS (Python 3.14), with text-cell checks for scrolling and overlays; these do not replace a physical rendering check.
- `print 3 -4` treats `-4` as a separate number (UCBLogo's spacing rule), which surprises some people. Write `3 - 4`.
