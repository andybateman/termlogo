"""Glue for the browser version (Pyodide): runs Logo and hands pictures to JavaScript.

Nothing here touches a terminal. A page creates a `Session` with a `post(kind, *args)`
function and calls `run`, `export` and `reset`; the session sends back what to show:

    post('out', text)                     text printed by the program
    post('clear')                         CLEARTEXT
    post('frame', rgba, first, last, labels, marker)
                                          the rows first..last of the picture as RGBA
                                          bytes (an empty `rgba` when none changed),
                                          LABEL texts as [x, y, text, r, g, b] in
                                          pixels, and the turtle as
                                          [x, y, heading, r, g, b] ([] when hidden)
    post('done', error)                   the run finished; error is '' when it went well
    post('file', name, mime, data, notes) the result of `export`
"""

import os
import tempfile
import time
from xml.sax.saxutils import escape

from .canvas import Canvas
from .errors import Bye, Goto, Incomplete, LogoError, Output, Stop, Throw
from .interp import Interp
from .turtle import Turtle

FRAME_GAP = 0.08  # seconds between pictures sent while a program animates
EXPORTS = {
    'png': ('termlogo.png', 'image/png'),
    'svg': ('termlogo.svg', 'image/svg+xml'),
    'stl': ('termlogo.stl', 'model/stl'),
}


def _js(value):
    """A value as plain JavaScript data under Pyodide (bytes become a Uint8Array and
    lists become arrays, so they can be posted between threads); unchanged anywhere else."""
    try:
        from pyodide.ffi import to_js
    except ImportError:
        return value
    return to_js(value)


def _no_input(prompt=''):
    raise EOFError  # a page cannot stop and wait for typing: READWORD and READLIST see the end


class Session:
    """One Logo workspace with a pixel canvas, driven from a web page."""

    def __init__(self, post, width=800, height=600, colour_mode='ucblogo', host=None):
        self.post = post
        self.host = host
        self.colour_mode = colour_mode
        self.width, self.height = width - width % 2, height - height % 2
        self._sent = 0.0
        self._full = True  # the next picture carries every row
        self.canvas = Canvas(self.width // 2, self.height // 2, cell=(2, 2), aa=True)
        self.turtle = Turtle(self.canvas, colour_mode=colour_mode)
        self.it = Interp(out=lambda text: self.post('out', text))
        self.it.attach_turtle(self.turtle)
        self.it.on_frame = self.turtle.frame_cb = self._frame
        self.it.text_clear = lambda: self.post('clear')
        if host is None:  # nothing can wait for typing: input commands see the end of input
            self.it.readline = _no_input
            self.it.readchar = lambda: ''
            self.it.keyp = lambda: False
        else:  # the page lent us a way to wait for keys, and to sleep so Stop can interrupt
            self.it.readline = lambda prompt='': str(host.read_line())
            self.it.readchar = lambda: str(host.read_char())
            self.it.keyp = lambda: bool(host.key_ready())
            self.turtle.sleep = self.it.on_wait = host.sleep

    # ---- pictures ----------------------------------------------------------
    def _frame(self, force=False, full=False):
        """Send the picture: only the rows that changed since the last one sent, unless
        `full`. Frames asked for by a moving turtle are spaced out; `force` ignores that."""
        now = time.monotonic()
        if not force and now - self._sent < FRAME_GAP:
            return
        self._sent = now
        c = self.canvas
        rows = c.take_dirty_rows()
        if full or self._full:
            rows, self._full = (0, c.height - 1), False
        rgba = c.rgba_rows(*rows) if rows else b''
        first, last = rows or (0, -1)
        labels = [
            [col * c.cell[0], row * c.cell[1] + c.cell[1] // 2, text, *c.display_colour(rgb)]
            for col, row, text, rgb in c.labels
        ]
        self.post('frame', _js(rgba), first, last, _js(labels), _js(self._marker()))

    def _marker(self):
        """Where to draw the turtle: [x, y, heading, red, green, blue], or [] if hidden."""
        t, c = self.turtle, self.canvas
        if not t.visible or (len(t.rgb) == 4 and t.rgb[3] == 0):
            return []
        x, y = c.origin_x + t.x * c.scale, c.origin_y - t.y * c.scale
        return [x, y, t.heading, *c._marker_colour(t)[:3]]

    # ---- running -----------------------------------------------------------
    def run(self, source, speed=None):
        """Run Logo text. Reports through `post('done', error)` and returns the error."""
        if speed is not None:
            self.turtle.speed = speed
        error = ''
        try:
            self.it.eval_source(source)
        except Incomplete:
            error = 'Unfinished list or TO definition'
        except Bye:
            pass
        except KeyboardInterrupt:
            error = 'Stopped!'
        except LogoError as e:
            error = e.message
        except Throw as t:
            error = f"Can't find catch tag for {t.tag}"
        except Goto as g:
            error = f"Can't find tag {g.tag}"
        except Output:
            error = 'OUTPUT can only be used inside a procedure'
        except Stop:
            error = 'STOP can only be used inside a procedure'
        except RecursionError:
            error = 'Stack overflow'
        except Exception as e:  # never let a program take the page down
            error = f'Internal error: {type(e).__name__}: {e}'
        self._frame(force=True, full=True)
        self.post('done', error)
        return error

    def reset(self, colour_mode=None):
        """Start again with an empty workspace and canvas."""
        speed = self.turtle.speed
        self.__init__(
            self.post, self.width, self.height, colour_mode or self.colour_mode, self.host
        )
        self.turtle.speed = speed
        self._frame(force=True, full=True)

    # ---- exports -----------------------------------------------------------
    def _svg(self):
        """The canvas as SVG, with LABEL texts added (the pixel canvas does not hold them)."""
        c = self.canvas
        texts = [
            '<text x="%d" y="%d" fill="#%02x%02x%02x" font-family="monospace" font-size="14" '
            'dominant-baseline="middle">%s</text>'
            % (
                col * c.cell[0],
                row * c.cell[1] + c.cell[1] // 2,
                *c.display_colour(rgb),
                escape(text),
            )
            for col, row, text, rgb in c.labels
        ]
        svg = c.to_svg()
        return svg.replace('</svg>', '\n'.join(texts) + '\n</svg>') if texts else svg

    def export(self, kind):
        """Send the drawing as a file: png, svg or stl (a 3D-printable stencil)."""
        if kind not in EXPORTS:
            raise ValueError(f'export kind must be one of {", ".join(EXPORTS)}')
        name, mime = EXPORTS[kind]
        notes = []
        try:
            if kind == 'png':
                data = self.canvas.to_png()
            elif kind == 'svg':
                data = self._svg().encode('utf-8')
            else:
                from . import stencil

                with tempfile.TemporaryDirectory() as folder:
                    path = os.path.join(folder, name)
                    notes = [line.replace(path, name) for line in stencil.export(self.turtle, path)]
                    with open(path, 'rb') as f:
                        data = f.read()
        except LogoError as e:
            self.post('file-error', e.message)
            return
        self.post('file', name, mime, _js(data), _js(notes))
