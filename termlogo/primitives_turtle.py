"""Turtle graphics primitives."""

import math

from . import values as V
from .canvas import COLOUR_NAMES, PALETTE
from .colours import WEB_NAMES
from .errors import LogoError
from .registry import prim


def _t(it):
    if it.turtle is None:
        raise LogoError('No turtle available')
    return it.turtle


def _num(x, who):
    value = V.num(x, who)
    if isinstance(value, float) and not math.isfinite(value):
        raise LogoError(f"{who} doesn't like {V.fmt(x)} as input")
    return value


def _pair(v, who):
    if not (isinstance(v, list) and len(v) == 2):
        raise LogoError(f"{who} doesn't like {V.fmt(v)} as input")
    return _num(v[0], who), _num(v[1], who)


# ---- movement -------------------------------------------------------------
@prim('forward fd', 1)
def forward(it, d):
    _t(it).forward(_num(d, 'forward'))


@prim('back bk backward', 1)
def back(it, d):
    _t(it).forward(-_num(d, 'back'))


@prim('left lt', 1)
def left(it, a):
    _t(it).turn(-_num(a, 'left'))


@prim('right rt', 1)
def right(it, a):
    _t(it).turn(_num(a, 'right'))


@prim('home', 0)
def home(it):
    t = _t(it)
    if t.boundary == 'wrap':
        t._segment(t.x, t.y, 0.0, 0.0)
    else:
        if not t.move_to(0.0, 0.0):
            return
    t.x = t.y = 0.0
    t.set_heading(0.0)


@prim('setpos', 1)
def setpos(it, p):
    x, y = _pair(p, 'setpos')
    _t(it).move_to(x, y)


@prim('setxy', 2)
def setxy(it, x, y):
    _t(it).move_to(_num(x, 'setxy'), _num(y, 'setxy'))


@prim('setx', 1)
def setx(it, x):
    t = _t(it)
    t.move_to(_num(x, 'setx'), t.y)


@prim('sety', 1)
def sety(it, y):
    t = _t(it)
    t.move_to(t.x, _num(y, 'sety'))


@prim('setheading seth', 1)
def setheading(it, a):
    _t(it).set_heading(_num(a, 'setheading'))


@prim('arc', 2)
def arc(it, angle, radius):
    _t(it).arc(_num(angle, 'arc'), _num(radius, 'arc'))


@prim('dot', 1)
def dot(it, p):
    x, y = _pair(p, 'dot')
    t = _t(it)
    if len(t.rgb) == 4 and t.rgb[3] == 0 and t.pen_mode != 'erase':
        return
    px, py = t.canvas.to_pixel(x, y)
    t.canvas.plot(px, py, t.rgb, t.pen_mode, max(1, int(round(t.pen_size * t.canvas.unit))))
    t.record((x, y), (x, y))
    t.beat()


# ---- queries --------------------------------------------------------------
@prim('pos', 0)
def pos(it):
    t = _t(it)
    return [_clean(t.x), _clean(t.y)]


def _clean(v):
    v = round(v, 10)
    return int(v) if v == int(v) else v


@prim('xcor', 0)
def xcor(it):
    return _clean(_t(it).x)


@prim('ycor', 0)
def ycor(it):
    return _clean(_t(it).y)


@prim('heading', 0)
def heading(it):
    return _clean(_t(it).heading)


@prim('towards', 1)
def towards(it, p):
    x, y = _pair(p, 'towards')
    return _clean(_t(it).towards(x, y))


@prim('distance', 1)
def distance(it, p):
    import math

    x, y = _pair(p, 'distance')
    t = _t(it)
    return _clean(math.hypot(x - t.x, y - t.y))


@prim('scrunch', 0)
def scrunch(it):
    return [1, 1]


@prim('shownp shown?', 0)
def shownp(it):
    return V.boolword(_t(it).visible)


@prim('pendownp pendown?', 0)
def pendownp(it):
    return V.boolword(_t(it).pen_down)


@prim('penmode', 0)
def penmode(it):
    return {'paint': 'paint', 'erase': 'erase', 'reverse': 'reverse'}[_t(it).pen_mode]


@prim('pen', 0)
def pen(it):
    t = _t(it)
    if not t.pen_down:
        return 'penup'
    return {'paint': 'pendown', 'erase': 'penerase', 'reverse': 'penreverse'}[t.pen_mode]


@prim('pencolor pencolour pcolor pcolour pc', 0)
def pencolor(it):
    t = _t(it)
    return list(t.rgb) if t.colour_mode == 'terrapin' else t.pen_colour_spec


@prim('background backgroundcolor backgroundcolour bgcolor bgcolour bg', 0)
def background(it):
    t = _t(it)
    return list(t.canvas.bg) if t.colour_mode == 'terrapin' else t.bg_spec


@prim('colors colours', 0)
def colours(it):
    t = _t(it)
    names = WEB_NAMES if t.colour_mode == 'terrapin' else tuple(COLOUR_NAMES)
    return [name.upper() for name in names]


@prim('pensize', 0)
def pensize(it):
    return [_t(it).pen_size, _t(it).pen_size]


@prim('wrapp wrap?', 0)
def wrapp(it):
    return V.boolword(_t(it).boundary == 'wrap')


# ---- pen ------------------------------------------------------------------
@prim('penup pu', 0)
def penup(it):
    _t(it).pen_down = False


@prim('pendown pd', 0)
def pendown(it):
    t = _t(it)
    t.pen_down = True
    if t.colour_mode == 'terrapin':
        t.pen_mode = 'paint'


@prim('penpaint ppt', 0)
def penpaint(it):
    t = _t(it)
    t.pen_mode, t.pen_down = 'paint', True


@prim('penerase pe', 0)
def penerase(it):
    t = _t(it)
    t.pen_mode, t.pen_down = 'erase', True


@prim('penreverse px', 0)
def penreverse(it):
    t = _t(it)
    t.pen_mode, t.pen_down = 'reverse', True


@prim('setpen', 1)
def setpen(it, spec):
    states = {
        'penup': (False, None),
        'pendown': (True, 'paint'),
        'penerase': (True, 'erase'),
        'penreverse': (True, 'reverse'),
    }
    if (
        not isinstance(spec, list)
        or len(spec) != 2
        or not isinstance(spec[0], str)
        or spec[0].lower() not in states
    ):
        raise LogoError(f"setpen doesn't like {V.fmt(spec)} as input (use [penstate colour])")
    t = _t(it)
    colour = t.parse_colour(spec[1], 'setpen', t.alpha)
    down, mode = states[spec[0].lower()]
    t.rgb, t.pen_colour_spec, t.pen_down = colour, spec[1], down
    if mode is not None:
        t.pen_mode = mode


@prim('setalpha', 1)
def setalpha(it, value):
    alpha = _num(value, 'setalpha')
    if not 0 <= alpha <= 1:
        raise LogoError(f"setalpha doesn't like {V.fmt(value)} as input (use 0 to 1)")
    t = _t(it)
    if t.colour_mode != 'terrapin':
        raise LogoError('SETALPHA needs --colour-mode terrapin')
    t.alpha = alpha


@prim('alpha', 0)
def alpha(it):
    return _t(it).alpha


@prim('setpencolor setpencolour setpc setcolor setcolour', 1)
def setpencolor(it, c):
    _t(it).set_pen_colour(c)


@prim(
    'setbackground setbackgroundcolor setbackgroundcolour setbg setscreencolor '
    'setscreencolour setsc',
    1,
)
def setbackground(it, c):
    _t(it).set_background(c)


@prim('setpensize setwidth', 1)
def setpensize(it, n):
    v = _num(n[0] if isinstance(n, list) and n else n, 'setpensize')
    if v <= 0:
        raise LogoError(f"setpensize doesn't like {V.fmt(n)} as input")
    _t(it).pen_size = v if v != int(v) else int(v)


@prim('setpalette', 2)
def setpalette(it, idx, rgb):
    if _t(it).colour_mode != 'ucblogo':
        raise LogoError('SETPALETTE uses the UCBLogo palette; use --colour-mode ucblogo')
    i = V.intval(idx, 'setpalette')
    if not 0 <= i < 256 or not (isinstance(rgb, list) and len(rgb) == 3):
        raise LogoError(f"setpalette doesn't like {V.fmt(idx)} as input")
    while len(PALETTE) <= i:
        PALETTE.append((0, 0, 0))
    PALETTE[i] = _t(it).parse_colour(rgb)


@prim('palette', 1)
def palette(it, idx):
    if _t(it).colour_mode != 'ucblogo':
        raise LogoError('PALETTE uses the UCBLogo palette; use --colour-mode ucblogo')
    i = V.intval(idx, 'palette')
    if not 0 <= i < len(PALETTE):
        raise LogoError(f"palette doesn't like {i} as input")
    return [round(v * 100 / 255) for v in PALETTE[i]]


# ---- visibility, screen ---------------------------------------------------
@prim('hideturtle ht', 0)
def hideturtle(it):
    _t(it).visible = False


@prim('showturtle st', 0)
def showturtle(it):
    _t(it).visible = True


@prim('clearscreen cs', 0)
def clearscreen(it):
    t = _t(it)
    t.canvas.clear()
    t.strokes.clear()
    t.home()
    t.finish_frame()


@prim('clean', 0)
def clean(it):
    _t(it).canvas.clear()
    _t(it).strokes.clear()


@prim('wrap', 0)
def wrap(it):
    _t(it).boundary = 'wrap'


@prim('window', 0)
def window(it):
    _t(it).boundary = 'window'


@prim('fence', 0)
def fence(it):
    _t(it).boundary = 'fence'


@prim('fill', 0, 0, 1)
def fill(it, tolerance=None):
    t = _t(it)
    if tolerance is not None:
        tolerance = _num(tolerance, 'fill')
        if not 0 <= tolerance <= 1:
            raise LogoError(f"fill doesn't like {V.fmt(tolerance)} as input (use 0 to 1)")
    if t.colour_mode == 'terrapin':
        if not t.pen_down or t.pen_mode != 'paint':
            return
        tolerance = 0.5 if tolerance is None else tolerance
    elif tolerance is not None:
        raise LogoError('FILL tolerance needs --colour-mode terrapin')
    px, py = t.canvas.to_pixel(t.x, t.y)
    t.canvas.fill(px, py, t.rgb, tolerance)
    t.beat()


@prim('filled', 2)
def filled(it, colour, body):
    """FILLED colour [instructions]: run the instructions, then fill the shape
    they drew from the turtle's start position."""
    t = _t(it)
    if not isinstance(body, list):
        raise LogoError(f"filled doesn't like {V.fmt(body)} as input")
    sx, sy = t.x, t.y
    saved = t.rgb, t.pen_colour_spec
    try:
        it.run_list(body)
        t.canvas.fill(*t.canvas.to_pixel(sx, sy), t.parse_colour(colour, 'filled', t.alpha))
    finally:
        t.rgb, t.pen_colour_spec = saved


@prim('label', 1)
def label(it, text):
    t = _t(it)
    px, py = t.canvas.to_pixel(t.x, t.y)
    t.canvas.label(px, py, V.fmt(text, top=True), t.rgb)
    t.beat()


@prim('setscale', 1)
def setscale(it, s):
    """Extension: pixels per turtle step (default 1). 0.5 halves every drawing."""
    v = _num(s, 'setscale')
    if v <= 0:
        raise LogoError(f"setscale doesn't like {V.fmt(s)} as input")
    _t(it).canvas.set_scale(float(v))


@prim('textscreen ts fullscreen fs splitscreen ss', 0)
def screenmodes(it):
    pass


def export_stencil(it, path, options=None):
    from . import stencil as S

    t = _t(it)
    tris, report = S.make_stencil(t.strokes, options)
    S.write_stl(path, tris)
    for line in S.describe(report, path):
        it.write(line + '\n')
    if t.unrecorded:
        it.write(f'Warning: {t.unrecorded} erased or reversed segment(s) are not in the stencil\n')


@prim('stencil', 1, 1, 2)
def stencil(it, name, options=None):
    """STENCIL "file.stl exports a 3D-printable stencil of what has been drawn."""
    export_stencil(it, V.word(name, 'stencil'), options)


@prim('savepict savepic', 1)
def savepict(it, name):
    """SAVEPICT "file.svg|png|txt|stl exports the canvas (UCBLogo name, extra formats)."""
    path = V.word(name, 'savepict')
    if path.lower().endswith('.stl'):
        export_stencil(it, path)
    else:
        _t(it).canvas.save(path)


@prim('setspeed', 1)
def setspeed(it, n):
    """SETSPEED 0-10 sets how fast the turtle moves so you can watch it draw.
    0 is instant; each step up doubles the speed. Extension (as in Python's turtle)."""
    v = _num(n, 'setspeed')
    if not 0 <= v <= 10:
        raise LogoError(f"setspeed doesn't like {V.fmt(n)} as input (use 0 to 10)")
    t = _t(it)
    t.speed = v
    t.finish_frame()


@prim('speed', 0)
def speed(it):
    v = _t(it).speed
    return int(v) if v == int(v) else v
