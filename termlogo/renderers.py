"""Choose a renderer for the terminal, build the matching canvas, compose frames."""

import os
import struct

from .canvas import Canvas

CHOICES = ('auto', 'braille', 'half', 'kitty')
MAX_PIXELS = 2_500_000  # keep the pixel grid affordable on huge retina terminals


def cell_pixels(fd=1):
    """(width, height) in pixels of one terminal cell, or None if unknown."""
    try:
        import fcntl
        import termios

        rows, cols, xp, yp = struct.unpack('HHHH', fcntl.ioctl(fd, termios.TIOCGWINSZ, b'\0' * 8))
        if rows and cols and xp and yp:
            return max(1, xp // cols), max(1, yp // rows)
    except (ImportError, OSError, ValueError):
        pass
    return None


def supports_kitty(env=None):
    """Terminals known to implement the Kitty graphics protocol."""
    env = os.environ if env is None else env
    if env.get('TMUX') or env.get('STY'):  # multiplexers swallow the sequences
        return False
    term, prog = env.get('TERM', ''), env.get('TERM_PROGRAM', '').lower()
    return (
        'kitty' in term
        or 'ghostty' in term
        or bool(env.get('KITTY_WINDOW_ID'))
        or prog in ('ghostty', 'wezterm')
        or bool(env.get('GHOSTTY_RESOURCES_DIR'))
    )


def choose(requested=None, tty=True, env=None, cell_px=None):
    """Return (name, cell_px). `auto` picks kitty when the terminal supports it and
    reports its pixel size, otherwise braille."""
    env = os.environ if env is None else env
    requested = (requested or env.get('TERMLOGO_RENDER') or 'auto').lower()
    if requested not in CHOICES:
        raise ValueError(f'render must be one of {", ".join(CHOICES)}')
    px = cell_px if cell_px is not None else (cell_pixels() if tty else None)
    if requested == 'kitty' and px is None:
        px = (10, 20)  # forced on: assume a typical cell
    if requested == 'auto':
        requested = 'kitty' if tty and px and supports_kitty(env) else 'braille'
    return requested, px


def make_canvas(name, cols, rows, scale=1.0, cell_px=None):
    if name == 'half':
        return Canvas(cols, rows, scale, cell=(1, 2))
    if name == 'kitty':
        cw, ch = cell_px or (10, 20)
        while cols * cw * rows * ch > MAX_PIXELS and cw > 2:
            cw, ch = max(2, cw // 2), max(2, ch // 2)
        return Canvas(cols, rows, scale, cell=(cw, ch), unit=max(1, round(ch / 12)), aa=True)
    return Canvas(cols, rows, scale)


def frame(name, canvas, turtle, color=True, standalone=False):
    """Text to print for the canvas region. Leaves the cursor on the line below it.

    standalone=True draws at the cursor (script mode); otherwise the REPL has already
    cleared the screen and homed the cursor."""
    if name == 'kitty':
        rows = canvas.rows
        labels = canvas.kitty_label_text(color)
        if standalone:
            # make room, step back up, place the image, then step down past it
            return (
                '\n' * rows
                + f'\x1b[{rows}A'
                + canvas.kitty_image(turtle)
                + labels
                + f'\x1b[{rows}B\r'
            )
        return canvas.kitty_image(turtle) + labels + f'\x1b[{rows + 1};1H'
    return '\n'.join(canvas.render(turtle, color, mode=name)) + '\n'
