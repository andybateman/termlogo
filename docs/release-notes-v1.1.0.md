## What's new in 1.1.0

**Try it in your browser, with nothing to install: https://www.andybateman.com/termlogo/**
The same engine runs in a web page through Pyodide. It has an editor, a command line, examples, a speed control, UCBLogo and Terrapin colours, and PNG, SVG and STL stencil downloads. Programs can read typed lines and keys, **Stop** and **Esc** keep your workspace, and **Share link** puts a program in an address so no server ever sees it. Smoother animation, and `LABEL` text now appears in PNG and SVG downloads.

**More ways to run it**
- `brew tap andybateman/termlogo https://github.com/andybateman/termlogo`, then `brew trust --formula andybateman/termlogo/termlogo` and `brew install termlogo`
- `termlogo.pyz` below: one file for any machine with Python 3.10 or later (`chmod +x termlogo.pyz && ./termlogo.pyz`)

**Language and drawing** (added since 1.0.0 in the terminal version too): arrays, property lists, file streams, `READCHAR`, `GOTO`, round pens, XOR `PENREVERSE` and `--fit`. The full list is in the [changelog](https://github.com/andybateman/termlogo/blob/main/CHANGELOG.md).

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
