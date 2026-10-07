## What's new in 1.2.0

**More room to draw in the browser: https://www.andybateman.com/termlogo/**
The page is redesigned around the canvas. It fills the space beside the editor and follows the size of your window, so a bigger window gives a bigger drawing. Drag the divider to share the width, press **Expand canvas** to hide the editor, or go full screen. There is a **Help** panel with a searchable list of every command, **Open** and **Save** for `.logo` files, the turtle's coordinates under the pointer, and a tidier layout on phones. Picking an example runs it, and the examples now fit themselves to any canvas with `FITWINDOW`.

**Fixes**
- Deep recursion no longer crashes Python 3.10 and 3.11; it reports `Stack overflow` instead. This affected `termlogo.pyz` on those versions.
- In the browser, runaway recursion reports `Stack overflow` instead of stopping Python. If Python does stop, the page restarts it and says so.
- Pressing Stop just as a program ends no longer resets the workspace.
- `SETSCALE` after `FITWINDOW` is no longer undone when the window is resized.
- File streams use UTF-8, and bytes that are not UTF-8 no longer stop a program. `SETREAD` and `SETWRITE` refuse a file opened the other way, and `PPS` prints property lists in a form that reads back.

**Install or upgrade**
- Homebrew: `brew update && brew upgrade termlogo`. First time: `brew tap andybateman/termlogo https://github.com/andybateman/termlogo`, then `brew trust --formula andybateman/termlogo/termlogo` and `brew install termlogo`
- `termlogo.pyz` below: one file for any machine with Python 3.10 or later (`chmod +x termlogo.pyz && ./termlogo.pyz`)

The full list is in the [changelog](https://github.com/andybateman/termlogo/blob/main/CHANGELOG.md).

## Using `termlogo.pyz`
One executable file that runs wherever Python 3.10 or later is installed. There is nothing else to install.

```bash
chmod +x termlogo.pyz
./termlogo.pyz                           # interactive REPL
./termlogo.pyz program.logo              # run a Logo program
./termlogo.pyz -e 'repeat 36 [fd 30 rt 100]'
./termlogo.pyz program.logo -o out.png   # export .svg, .png, .txt or .stl

# optional: put it on your PATH as `termlogo`
mkdir -p ~/bin && mv termlogo.pyz ~/bin/termlogo
```

- If you have no `python3` on your PATH, run it as `python3.11 termlogo.pyz` (any version 3.10+).
- On macOS, a downloaded file may be quarantined. If it will not run, use `xattr -d com.apple.quarantine termlogo.pyz`.
- It is a Python archive, not a compiled binary. Type `HELP` in the REPL for every command, or see the [README](https://github.com/andybateman/termlogo#readme).
