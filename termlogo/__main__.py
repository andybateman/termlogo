"""Command line: python3 -m termlogo [file.logo] [-e CODE] [-i] [-o out.svg]"""

import argparse
import math
import shutil
import sys

from . import __author__, __version__, renderers
from .colours import COLOUR_MODES
from .errors import Bye, Incomplete, LogoError, Output, Stop, Throw
from .repl import SHOW, SYNC_OFF, Display, build, drawing_controls, repl
from .turtle import DEFAULT_SPEED


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog='termlogo', description='Logo with turtle graphics in the terminal.'
    )
    ap.add_argument('files', nargs='*', help='Logo source files to run')
    ap.add_argument(
        '-e',
        '--eval',
        action='append',
        default=[],
        metavar='CODE',
        help='run this Logo code (repeatable)',
    )
    ap.add_argument(
        '-i', '--interactive', action='store_true', help='enter the REPL after running files'
    )
    ap.add_argument('--size', metavar='COLSxROWS', help='canvas size in terminal cells')
    ap.add_argument(
        '--scale',
        type=float,
        default=1.0,
        help='pixels per turtle step (default 1; try 0.5 for big drawings)',
    )
    ap.add_argument(
        '-o',
        '--output',
        metavar='FILE',
        help='export after running: .svg, .png, .txt, or .stl for a 3D-printable stencil',
    )
    ap.add_argument(
        '--render',
        choices=renderers.CHOICES,
        default=None,
        help='braille (2x4 dots per cell), half (solid half blocks), kitty '
        '(real pixels in Ghostty, Kitty, WezTerm) or auto (default; '
        'env TERMLOGO_RENDER also works)',
    )
    ap.add_argument(
        '--speed',
        type=float,
        default=DEFAULT_SPEED,
        metavar='0-10',
        help='watch it draw: 0 is instant, 1 slow, 5 default, 10 fast',
    )
    ap.add_argument(
        '--stencil-opt',
        action='append',
        default=[],
        metavar='KEY=VALUE',
        help='option for -o file.stl (repeatable): thickness, margin, bridge, '
        'bridges, width, minwidth, mirror, pitch, mm, maxgap',
    )
    ap.add_argument(
        '--no-color', '--no-colour', action='store_true', help='plain Braille without colour'
    )
    ap.add_argument(
        '--colour-mode',
        '--color-mode',
        choices=COLOUR_MODES,
        default='ucblogo',
        help='colour rules: ucblogo (default, RGB 0-100) or terrapin (Web colours, RGB 0-255, alpha)',
    )
    ap.add_argument('--no-canvas', action='store_true', help="don't print the canvas at the end")
    ap.add_argument(
        '--version', action='version', version=f'termlogo {__version__} by {__author__}'
    )
    a = ap.parse_args(argv)

    cols = rows = None
    if a.size:
        try:
            cols, rows = (int(v) for v in a.size.lower().split('x'))
        except ValueError:
            ap.error('--size must look like 100x30')
        if cols <= 0 or rows <= 0:
            ap.error('--size dimensions must be positive')
    if not math.isfinite(a.scale) or a.scale <= 0:
        ap.error('--scale must be a finite positive number')
    if not 0 <= a.speed <= 10:
        ap.error('--speed must be between 0 and 10')

    if not a.files and not a.eval:
        return repl(
            cols, rows, a.scale, not a.no_color, a.render, a.speed, colour_mode=a.colour_mode
        )

    sz = shutil.get_terminal_size((80, 24))
    tty = sys.stdout.isatty() and sys.stdin.isatty()
    try:
        render, cell_px = renderers.choose(a.render, tty)
    except ValueError as e:
        ap.error(str(e))
    animate = tty and not a.no_canvas and not a.output
    log = []
    display = None

    def out(text):
        if display is not None:
            display.log_text(text)
        else:
            sys.stdout.write(text)

    sources = []
    for path in a.files:
        try:
            with open(path) as f:
                sources.append((path, f.read()))
        except OSError as e:
            print(f'termlogo: {e}', file=sys.stderr)
            return 2
    sources += [('-e', code) for code in a.eval]

    it, canvas, turtle = build(
        cols or sz.columns,
        rows or max(1, sz.lines - (8 if animate else 3)),
        a.scale,
        out,
        render,
        cell_px,
        a.colour_mode,
    )
    turtle.speed = a.speed
    if animate:
        display = Display(
            it,
            canvas,
            turtle,
            render,
            not a.no_color,
            log,
            auto_size=a.size is None,
            cell_px=cell_px,
        )
        display.running = True
        display.draw()
    status = 0

    def report_error(message):
        print(message, file=sys.stderr)
        if display is not None:
            log.append(message)

    try:
        for name, text in sources:
            try:
                with drawing_controls(turtle, animate, it, display):
                    it.eval_source(text)
            except Bye:
                break
            except Incomplete:
                report_error(f'{name}: unfinished list or TO definition')
                status = 1
                break
            except LogoError as e:
                report_error(f'{name}: {e.message}')
                status = 1
                break
            except KeyboardInterrupt:
                report_error(f'{name}: stopped')
                status = 130
                break
            except (Output, Stop, Throw):
                report_error(f'{name}: OUTPUT, STOP or THROW used outside a procedure')
                status = 1
                break
    finally:
        if display is not None:
            display.running = False
            try:
                display.draw()
            finally:
                sys.stdout.write(SHOW + SYNC_OFF)
                sys.stdout.flush()
    if display is not None:
        if a.interactive and status == 0:
            return repl(cols, rows, a.scale, not a.no_color, render, turtle.speed, interpreter=it)
        return status
    if a.output and a.output.lower().endswith('.stl'):
        from . import stencil as S

        pairs = []
        for item in a.stencil_opt:
            key, _, val = item.partition('=')
            pairs += [key, val]
        try:
            lines = S.export(turtle, a.output, pairs or None)
        except LogoError as e:
            print(f'termlogo: {e.message}', file=sys.stderr)
            return 1
        for line in lines:
            print(line, file=sys.stderr)
    elif a.output:
        try:
            canvas.save(a.output)
        except OSError as e:
            print(f"termlogo: Can't write {a.output}: {e.strerror}", file=sys.stderr)
            return 1
    if not a.no_canvas and not a.output:
        sys.stdout.write(
            renderers.frame(render, canvas, turtle, color=not a.no_color and tty, standalone=True)
        )
    if a.interactive and status == 0:
        return repl(cols, rows, a.scale, not a.no_color, render, turtle.speed, interpreter=it)
    return status


if __name__ == '__main__':
    sys.exit(main())
