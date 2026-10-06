"""Terrapin's indexed Web colours and alpha compositing.

Indices follow the live WebLogo palette (as at 2026-10-06); RGB values are
standard CSS colour values. Index 138 is transparent.
"""

from . import values as V
from .errors import LogoError

COLOUR_MODES = ('ucblogo', 'terrapin')

_WEB_COLOURS = """
black 000000
navy 000080
green 008000
teal 008080
maroon 800000
purple 800080
olive 808000
lightgray d3d3d3
gray 808080
blue 0000ff
lime 00ff00
cyan 00ffff
red ff0000
magenta ff00ff
yellow ffff00
white ffffff
aliceblue f0f8ff
antiquewhite faebd7
aquamarine 7fffd4
azure f0ffff
beige f5f5dc
bisque ffe4c4
blanchedalmond ffebcd
blueviolet 8a2be2
brown a52a2a
burlywood deb887
cadetblue 5f9ea0
chartreuse 7fff00
chocolate d2691e
coral ff7f50
cornflowerblue 6495ed
cornsilk fff8dc
crimson dc143c
darkblue 00008b
darkcyan 008b8b
darkgoldenrod b8860b
darkgray a9a9a9
darkgreen 006400
darkkhaki bdb76b
darkmagenta 8b008b
darkolivegreen 556b2f
darkorange ff8c00
darkorchid 9932cc
darkred 8b0000
darksalmon e9967a
darkseagreen 8fbc8f
darkslateblue 483d8b
darkslategray 2f4f4f
darkturquoise 00ced1
darkviolet 9400d3
deeppink ff1493
deepskyblue 00bfff
dimgray 696969
dodgerblue 1e90ff
firebrick b22222
floralwhite fffaf0
forestgreen 228b22
gainsboro dcdcdc
ghostwhite f8f8ff
gold ffd700
goldenrod daa520
greenyellow adff2f
honeydew f0fff0
hotpink ff69b4
indianred cd5c5c
indigo 4b0082
ivory fffff0
khaki f0e68c
lavender e6e6fa
lavenderblush fff0f5
lawngreen 7cfc00
lemonchiffon fffacd
lightblue add8e6
lightcoral f08080
lightcyan e0ffff
lightgoldenrodyellow fafad2
lightgreen 90ee90
lightpink ffb6c1
lightsalmon ffa07a
lightseagreen 20b2aa
lightskyblue 87cefa
lightslategray 778899
lightsteelblue b0c4de
lightyellow ffffe0
limegreen 32cd32
linen faf0e6
mediumaquamarine 66cdaa
mediumblue 0000cd
mediumorchid ba55d3
mediumpurple 9370db
mediumseagreen 3cb371
mediumslateblue 7b68ee
mediumspringgreen 00fa9a
mediumturquoise 48d1cc
mediumvioletred c71585
midnightblue 191970
mintcream f5fffa
mistyrose ffe4e1
moccasin ffe4b5
navajowhite ffdead
oldlace fdf5e6
olivedrab 6b8e23
orange ffa500
orangered ff4500
orchid da70d6
palegoldenrod eee8aa
palegreen 98fb98
paleturquoise afeeee
palevioletred db7093
papayawhip ffefd5
peachpuff ffdab9
peru cd853f
pink ffc0cb
plum dda0dd
powderblue b0e0e6
rosybrown bc8f8f
royalblue 4169e1
saddlebrown 8b4513
salmon fa8072
sandybrown f4a460
seagreen 2e8b57
seashell fff5ee
sienna a0522d
silver c0c0c0
skyblue 87ceeb
slateblue 6a5acd
slategray 708090
snow fffafa
springgreen 00ff7f
steelblue 4682b4
tan d2b48c
thistle d8bfd8
tomato ff6347
turquoise 40e0d0
violet ee82ee
wheat f5deb3
whitesmoke f5f5f5
yellowgreen 9acd32
transparent 000000
"""

WEB_NAMES = tuple(line.split()[0] for line in _WEB_COLOURS.strip().splitlines())
WEB_PALETTE = tuple(
    (*bytes.fromhex(line.split()[1]), 0 if line.startswith('transparent ') else 1)
    for line in _WEB_COLOURS.strip().splitlines()
)
WEB_INDICES = {name: i for i, name in enumerate(WEB_NAMES)}
WEB_INDICES.update(
    {name.replace('gray', 'grey'): index for name, index in WEB_INDICES.copy().items()}
)
WEB_INDICES.update(aqua=11, fuchsia=13)


def parse_web_colour(spec, who='setpencolour', alpha=1):
    message = f"{who} doesn't like {V.fmt(spec)} as input"
    if isinstance(spec, list):
        if len(spec) not in (3, 4):
            raise LogoError(message + ' (use [red green blue] or [red green blue alpha])')
        components = [V.num(v, who) for v in spec]
        if any(not 0 <= v <= 255 for v in components[:3]):
            raise LogoError(message + ' (RGB components must be between 0 and 255)')
        opacity = components[3] if len(components) == 4 else alpha
        if not 0 <= opacity <= 1:
            raise LogoError(message + ' (alpha must be between 0 and 1)')
        return (*(int(round(v)) for v in components[:3]), opacity)
    if isinstance(spec, str) and spec.lower() in WEB_INDICES:
        index = WEB_INDICES[spec.lower()]
    elif V.is_num(spec):
        value = V.num(spec, who)
        if not 0 <= value < len(WEB_PALETTE):
            raise LogoError(message + ' (use a colour number from 0 to 138)')
        index = V.intval(value, who)
    else:
        raise LogoError(message)
    rgb = WEB_PALETTE[index]
    return (*rgb[:3], alpha if rgb[3] else 0)


def rgba(colour):
    if colour is None:
        return (0, 0, 0, 0)
    return (*colour, 1) if len(colour) == 3 else colour


def composite(foreground, background):
    """Source-over compositing without flattening transparency into the background."""
    fg, bg = rgba(foreground), rgba(background)
    if fg[3] == 0:
        return bg
    if fg[3] == 1 or bg[3] == 0:
        return fg
    alpha = fg[3] + bg[3] * (1 - fg[3])
    if alpha == 0:
        return fg
    channels = tuple(
        int(round((fg[i] * fg[3] + bg[i] * bg[3] * (1 - fg[3])) / alpha)) for i in range(3)
    )
    return (*channels, alpha)
