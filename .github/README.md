# Terminal Logo Turtle

A Logo interpreter with turtle graphics that runs entirely in the terminal, so it works over SSH and in any plain terminal window. It follows UCBLogo, uses only the Python standard library, and can turn a drawing into a 3D-printable stencil.

**[Try it in your browser](https://www.andybateman.com/termlogo/)**, with nothing to install, or run it in your terminal as below.

![A flower drawn in the terminal](../docs/images/flower.png)

## Get started
You need Python 3.10 or later. There is nothing to install. Each [release](https://github.com/andybateman/termlogo/releases) also has `termlogo.pyz`, a single file you can download, `chmod +x` and run.

```bash
git clone https://github.com/andybateman/termlogo.git
cd termlogo
./bin/termlogo                       # interactive REPL
./bin/termlogo examples/flower.logo  # run a program
./bin/termlogo -e 'repeat 36 [fd 30 rt 100]'
./bin/termlogo prog.logo -o out.png  # export .svg, .png, .txt or .stl
```

On macOS or Linux with Homebrew:

```bash
brew tap andybateman/termlogo https://github.com/andybateman/termlogo
brew trust --formula andybateman/termlogo/termlogo   # newer Homebrew refuses untrusted taps
brew install termlogo
```

In the REPL, type `HELP` for every command, `HELP fd` for one, and `BYE` to leave. Press Tab to complete names, Up to recall a command, and Escape to stop a running program.

Useful options: `--speed 0` draws instantly, `--render braille|half|kitty` picks the renderer, `--colour-mode terrapin` switches to Terrapin colours, and `--fit 1000` fits a textbook 1000x1000 window to the canvas.

## Find out more
- [README.md](../README.md): full user guide, key bindings, colour modes, stencils, what works and known issues
- [Run it in your browser](https://www.andybateman.com/termlogo/): the same engine through Pyodide, with an editor, examples and PNG/SVG/STL downloads (how it is built is in the README's Browser version section)
- [examples/](../examples): sample programs to run and change
- [CHANGELOG.md](../CHANGELOG.md): what changed in each version
- [HANDOVER.md](../HANDOVER.md): open items and how to pick the project up
- [LICENSE](../LICENSE): MIT
