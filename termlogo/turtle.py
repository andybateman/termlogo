"""Turtle state and movement, drawing onto a Canvas."""

import math
import time
from contextlib import contextmanager

from .canvas import COLOUR_NAMES, PALETTE
from .colours import COLOUR_MODES, parse_web_colour
from .errors import LogoError

TURN_FACTOR = 6.0  # degrees per second = steps per second x this
FRAME = 1 / 30.0  # redraw at most ~30 times a second while animating
DEFAULT_SPEED = 5


def speed_to_rate(speed):
    """Turtle steps per second for a speed setting 1-10 (doubles with each step)."""
    return 15.0 * 2 ** (speed - 1)


class Turtle:
    def __init__(self, canvas, clock=time.monotonic, sleep=time.sleep, colour_mode='ucblogo'):
        if colour_mode not in COLOUR_MODES:
            raise ValueError(f'colour mode must be one of {", ".join(COLOUR_MODES)}')
        self.canvas = canvas
        self.colour_mode = colour_mode
        self.alpha = 1
        self._painted = None
        self.speed = DEFAULT_SPEED  # 0 = instant, 1 (slow) to 10 (fast)
        self.frame_cb = None  # called to redraw while animating
        self.input_cb = None  # polls interactive controls while animating
        self.clock, self.sleep = clock, sleep
        self._due = self._last = 0.0
        self.strokes = []  # (x0, y0, x1, y1, width) painted with the pen
        self.unrecorded = 0  # erase/reverse segments the stencil cannot use
        # Filled areas, for the stencil: ('flood', x, y, n) or ('poly', points, n),
        # where n is how many strokes had been drawn when the fill happened.
        self.fills = []
        self._sealed = 0  # strokes that bounded a FILL and so must not grow
        self.trace = None  # points visited while FILLED runs its instructions
        self.pen_colour_spec = 7  # as set by SETPENCOLOR (number, name or rgb list)
        self.rgb = PALETTE[7]
        self.bg_spec = 0
        if colour_mode == 'terrapin':
            canvas.alpha = True
            self.pen_colour_spec = 0
            self.rgb = (0, 0, 0, 1)
            canvas.bg = (255, 255, 255, 0)
            self.bg_spec = list(canvas.bg)
        self.pen_down = True
        self.pen_mode = 'paint'
        self.pen_size = 1
        self.visible = True
        self.boundary = 'window'  # window | wrap | fence
        self.home()

    def home(self):
        self.x = self.y = 0.0
        self.heading = 0.0

    # ---- animation pacing ------------------------------------------------
    @property
    def animating(self):
        return self.speed > 0 and self.frame_cb is not None

    def pace(self, seconds):
        """Hold the animation to its set speed: redraw (at most ~30 fps) and sleep
        until `seconds` of drawing time have elapsed since the last piece."""
        now = self.clock()
        self._due = max(self._due, now) + seconds
        if now - self._last >= FRAME:
            self.frame_cb()
            self._last = self.clock()
        delay = self._due - self.clock()
        if self.input_cb is not None:
            return self.input_cb(max(0, delay))
        elif delay > 0.001:
            self.sleep(delay)
        return False

    def beat(self, seconds=0.05):
        """A short pause after an instant action (fill, label, dot) when animating."""
        if self.animating:
            self.pace(seconds * 10 / max(self.speed, 1) if self.speed < 10 else seconds)

    def finish_frame(self):
        if self.animating:
            self.frame_cb()
            self._last = self.clock()

    # ---- movement --------------------------------------------------------
    def forward(self, d):
        r = math.radians(self.heading)
        self.move_to(self.x + d * math.sin(r), self.y + d * math.cos(r))

    def move_to(self, nx, ny):
        with self._painting():
            return self._move_to(nx, ny)

    @contextmanager
    def _painting(self):
        previous = self._painted
        self._painted = {} if len(self.rgb) == 4 and self.pen_mode == 'paint' else None
        try:
            yield
        finally:
            self._painted = previous

    def _move_to(self, nx, ny):
        if not self.animating:
            self._move_now(nx, ny)
            return True
        c = self.canvas
        if self.boundary == 'fence' and (abs(nx) > c.half_w or abs(ny) > c.half_h):
            raise LogoError('Turtle out of bounds')  # refuse before moving at all
        x0, y0 = self.x, self.y
        dist = math.hypot(nx - x0, ny - y0)
        rate = speed_to_rate(self.speed)
        pieces = max(1, int(math.ceil(dist / (rate * FRAME))))
        for k in range(1, pieces + 1):
            if self.boundary == 'wrap':
                self._move_now(self.x + (nx - x0) / pieces, self.y + (ny - y0) / pieces)
            elif k == pieces:
                self._move_now(nx, ny)
            else:
                self._move_now(x0 + (nx - x0) * k / pieces, y0 + (ny - y0) * k / pieces)
            if self.pace(dist / rate / pieces):
                return False
        return True

    def _move_now(self, nx, ny):
        c = self.canvas
        if self.boundary == 'fence':
            if abs(nx) > c.half_w or abs(ny) > c.half_h:
                raise LogoError('Turtle out of bounds')
            self._segment(self.x, self.y, nx, ny)
        elif self.boundary == 'wrap':
            self._wrapped(nx, ny)
        else:
            self._segment(self.x, self.y, nx, ny)
            self.x, self.y = nx, ny

    def forget(self):
        """Drop everything remembered for stencil export (CLEARSCREEN, CLEAN)."""
        self.strokes.clear()
        self.fills.clear()
        self.unrecorded = self._sealed = 0

    def record(self, p, q):
        """Remember a painted stroke as vectors, for stencil export."""
        if self.pen_mode != 'paint':
            self.unrecorded += 1
            return
        w = self.pen_size
        if len(self.strokes) > self._sealed:
            x0, y0, x1, y1, lw = self.strokes[-1]
            if lw == w and (x1, y1) == tuple(p) and p != q:
                ax, ay, bx, by = x1 - x0, y1 - y0, q[0] - p[0], q[1] - p[1]
                if (
                    abs(ax * by - ay * bx) < 1e-9 * (abs(ax * by) + abs(ay * bx) + 1e-12)
                    and ax * bx + ay * by > 0
                    and (ax or ay)
                ):
                    self.strokes[-1] = (x0, y0, q[0], q[1], w)  # same line: extend it
                    return
        self.strokes.append((p[0], p[1], q[0], q[1], w))

    def _line(self, p, q):
        """Draw between two logo points with the current pen."""
        if self.pen_mode == 'paint' and len(self.rgb) == 4 and self.rgb[3] == 0:
            return
        self.record(p, q)
        self._draw(p, q, self.pen_mode)

    def _draw(self, p, q, mode):
        c = self.canvas
        width = self.pen_size * c.unit
        if c.aa and mode == 'paint':
            a, b = c.to_pixel_f(*p), c.to_pixel_f(*q)
            c.aa_line(a[0], a[1], b[0], b[1], self.rgb, max(1.0, width), self._painted)
        else:
            a, b = c.to_pixel(*p), c.to_pixel(*q)
            c.line(
                a[0],
                a[1],
                b[0],
                b[1],
                self.rgb,
                mode,
                max(1, int(round(width))),
                self._painted,
            )

    def _segment(self, x0, y0, x1, y1):
        if self.pen_down:
            self._line((x0, y0), (x1, y1))
        self.x, self.y = x1, y1
        if self.trace is not None:
            self.trace.append((x1, y1))

    # ---- filling ---------------------------------------------------------
    def flood(self, tolerance=None):
        """FILL: flood the canvas from the turtle with the pen colour."""
        c = self.canvas
        c.fill(*c.to_pixel(self.x, self.y), self.rgb, tolerance)
        # (FILL 1) paints the whole canvas and a clear pen paints nothing, so
        # neither is an area the stencil could cut out.
        if tolerance != 1 and not (len(self.rgb) == 4 and self.rgb[3] == 0):
            self.fills.append(('flood', self.x, self.y, len(self.strokes)))
            self._sealed = len(self.strokes)

    def fill_shape(self, points, rgb):
        """FILLED: fill the polygon through `points`, then outline it with the pen
        colour whatever the pen state, as UCBLogo does."""
        if len(set(points)) < 3:
            return
        self.canvas.fill_polygon(points, rgb)
        with self._painting():
            for p, q in zip(points, points[1:] + points[:1], strict=True):
                if p != q:
                    self._draw(p, q, 'paint')
        self.fills.append(('poly', tuple(points), len(self.strokes)))

    def _wrapped(self, nx, ny):
        hw, hh = self.canvas.half_w, self.canvas.half_h
        x, y = self.x, self.y
        dx, dy = nx - x, ny - y
        for _ in range(10000):
            # parametric time to leave the box along each axis
            ts = []
            if dx > 0:
                ts.append((hw - x) / dx)
            elif dx < 0:
                ts.append((-hw - x) / dx)
            if dy > 0:
                ts.append((hh - y) / dy)
            elif dy < 0:
                ts.append((-hh - y) / dy)
            t = min(ts) if ts else 2.0
            if t >= 1.0:
                self._segment(x, y, x + dx, y + dy)
                return
            ex, ey = x + dx * t, y + dy * t
            self._segment(x, y, ex, ey)
            dx, dy = dx * (1 - t), dy * (1 - t)
            if abs(abs(ex) - hw) < 1e-9 and dx != 0 and (ex > 0) == (dx > 0):
                ex = -ex
            if abs(abs(ey) - hh) < 1e-9 and dy != 0 and (ey > 0) == (dy > 0):
                ey = -ey
            x, y = ex, ey
            self.x, self.y = x, y
        self.x, self.y = x, y

    def turn(self, deg):
        if not self.animating or deg == 0:
            self.heading = (self.heading + deg) % 360.0
            return True
        rate = speed_to_rate(self.speed) * TURN_FACTOR  # degrees per second
        pieces = max(1, int(math.ceil(abs(deg) / (rate * FRAME))))
        for _ in range(pieces):
            self.heading = (self.heading + deg / pieces) % 360.0
            if self.pace(abs(deg) / rate / pieces):
                return False
        return True

    def set_heading(self, target):
        """Face an absolute heading, rotating the short way round when animating."""
        target %= 360.0
        if self.animating:
            if not self.turn((target - self.heading + 180.0) % 360.0 - 180.0):
                return
        self.heading = target

    def towards(self, x, y):
        return math.degrees(math.atan2(x - self.x, y - self.y)) % 360.0

    def arc(self, angle, radius):
        """Draw an arc centred on the turtle, starting at its heading, clockwise."""
        with self._painting():
            self._arc(angle, radius)

    def _arc(self, angle, radius):
        if not self.pen_down or radius == 0 or angle == 0:
            return
        c = self.canvas
        steps = max(8, int(abs(angle) / 360.0 * 2 * math.pi * abs(radius) * c.scale / 2) + 1)
        pts = []
        for i in range(steps + 1):
            a = math.radians(self.heading + angle * i / steps)
            pts.append((self.x + radius * math.sin(a), self.y + radius * math.cos(a)))
        for p, q in zip(pts, pts[1:], strict=False):
            self._line(p, q)
            if self.animating:
                if self.pace(math.hypot(q[0] - p[0], q[1] - p[1]) / speed_to_rate(self.speed)):
                    return

    # ---- colour ----------------------------------------------------------
    def parse_colour(self, spec, who='setpencolour', alpha=1):
        """Interpret a colour using the selected Logo colour rules."""
        if self.colour_mode == 'terrapin':
            return parse_web_colour(spec, who, alpha)
        if isinstance(spec, list):
            if len(spec) != 3:
                raise LogoError('Colour list needs three numbers')
            try:
                vals = [max(0, min(100, float(v))) for v in spec]
            except (TypeError, ValueError) as e:
                raise LogoError('Colour list needs three numbers') from e
            return tuple(int(round(v * 255 / 100)) for v in vals)
        s = str(spec).lower()
        if s in COLOUR_NAMES:
            return PALETTE[COLOUR_NAMES[s]]
        try:
            n = int(float(s))
        except (ValueError, OverflowError) as e:
            raise LogoError(f"setpencolor doesn't like {spec} as input") from e
        if not 0 <= n < len(PALETTE):
            raise LogoError(f"setpencolor doesn't like {spec} as input")
        return PALETTE[n]

    def set_pen_colour(self, spec):
        self.rgb = self.parse_colour(spec, alpha=self.alpha)
        self.pen_colour_spec = spec

    def set_background(self, spec):
        self.canvas.bg = self.parse_colour(spec, 'setbackground')
        self.bg_spec = spec
