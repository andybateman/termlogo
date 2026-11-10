# Terminal Logo Turtle

<!-- Project metadata for the Quests project tools. GitHub does not show this block.
**Keywords:** termlogo, Logo interpreter, turtle graphics, UCBLogo, Terrapin Logo, terminal REPL, multi-line command editing, Braille graphics, Kitty graphics, Ghostty, 3D-printable stencil, STL, FILL and FILLED cut-outs, Pyodide browser version, Homebrew formula, SVG export, RGBA colours, tail recursion, animation, Python
**Status:** Active
**Dashboard:** [Web demo](web/index.html)
**Start Date:** 2026-10-06
**Last Updated:** 2026-11-11
**Repository:** https://github.com/andybateman/termlogo (public)
-->

A Logo interpreter with turtle graphics that runs in the terminal, with a browser version.

## Why
Python's `turtle` needs Tk and PythonTurtle needs wxPython, so neither works over SSH or in a plain terminal. This draws in Braille, uses only the standard library, and follows UCBLogo.

## Status
Active (as at 2026-11-10). Open items: [HANDOVER.md](HANDOVER.md).

## Where things live
- User guide, usage, command list, browser build, files table, known issues: [.github/README.md](.github/README.md) (the GitHub front page)
- Changes: [CHANGELOG.md](CHANGELOG.md)
- Web demo: <https://www.andybateman.com/termlogo/>
- Code: `termlogo/`, `web/`, `tools/`, `tests/`, `examples/`
