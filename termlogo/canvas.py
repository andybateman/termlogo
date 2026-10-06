"""Pixel canvas with several terminal renderers.

The drawing engine works on a grid of pixels. How many pixels make up one terminal
cell depends on the renderer (`cell`): Braille 2x4, half-block 1x2, or the real pixel
size of a cell for graphics-protocol terminals. One turtle step is always half a
cell wide, so a drawing keeps its physical size whichever renderer is used.
"""

import base64
import math
import struct
import zlib

from .colours import composite, rgba

# UCBLogo's palette 0-15
PALETTE = [
    (0, 0, 0),
    (0, 0, 255),
    (0, 255, 0),
    (0, 255, 255),
    (255, 0, 0),
    (255, 0, 255),
    (255, 255, 0),
    (255, 255, 255),
    (155, 96, 59),
    (197, 136, 18),
    (100, 162, 64),
    (120, 187, 187),
    (255, 149, 119),
    (144, 113, 208),
    (255, 163, 0),
    (183, 183, 183),
]
COLOUR_NAMES = {
    'black': 0,
    'blue': 1,
    'green': 2,
    'cyan': 3,
    'red': 4,
    'magenta': 5,
    'yellow': 6,
    'white': 7,
    'brown': 8,
    'tan': 9,
    'forest': 10,
    'aqua': 11,
    'salmon': 12,
    'purple': 13,
    'orange': 14,
    'grey': 15,
    'gray': 15,
}
BIT = [[0x01, 0x02, 0x04, 0x40], [0x08, 0x10, 0x20, 0x80]]
TURTLE_RGB = (0, 255, 0)


def bresenham(x0, y0, x1, y1, limit=400000):
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    x, y = x0, y0
    for _ in range(limit):
        yield x, y
        if x == x1 and y == y1:
            return
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x += sx
        if e2 <= dx:
            err += dx
            y += sy


class _Bytes(dict):
    """Colour -> repeated RGB bytes, built on demand."""

    def __init__(self, bg, pixel, alpha=False):
        super().__init__()
        self.bg, self.pixel = bg, pixel
        self.alpha = alpha

    def __missing__(self, colour):
        if self.alpha:
            rgba = composite(colour, self.bg)
            b = bytes((*rgba[:3], int(round(rgba[3] * 255)))) * self.pixel
        else:
            b = bytes(colour if colour is not None else self.bg) * self.pixel
        self[colour] = b
        return b


class Canvas:
    def __init__(self, cols=80, rows=24, scale=1.0, cell=(2, 4), unit=1, aa=False):
        self.cols, self.rows = cols, rows
        self.cell = cell
        self.width, self.height = cols * cell[0], rows * cell[1]
        self.origin_x, self.origin_y = self.width / 2, self.height / 2
        self.base_scale = cell[0] / 2.0  # one turtle step = half a cell wide
        self.scale = self.base_scale * scale
        self.unit = unit  # pixels per pen-size unit
        self.aa = aa  # anti-aliased paint lines
        self.alpha = False
        self.marker_r = 1.5 * cell[1] if cell[1] <= 4 else 0.5 * cell[1]
        self.bg = PALETTE[0]
        self.pix = [[None] * self.width for _ in range(self.height)]
        self._cropped = {}
        self.labels = []  # (col, row, text, rgb)
        self.dirty = True

    def set_scale(self, user_scale):
        new_scale = self.base_scale * user_scale
        ratio = self.scale / new_scale
        self._cropped = {
            (wx * ratio, wy * ratio): (rgb, span * ratio)
            for (wx, wy), (rgb, span) in self._cropped.items()
        }
        self.scale = new_scale

    def copy_to(self, target):
        """Copy picture contents to a resized canvas, preserving Logo coordinates."""
        target.bg = self.bg
        target.alpha = self.alpha
        if target.scale == self.scale:
            # Keep the pixel-grid phase when an odd number of half-block cells changes.
            target.origin_x = self.origin_x + round(target.origin_x - self.origin_x)
            target.origin_y = self.origin_y + round(target.origin_y - self.origin_y)

        def copy_pixel(wx, wy, rgb, span):
            px = target.origin_x + wx * target.scale
            py = target.origin_y - wy * target.scale
            radius = span * target.scale / 2
            left, right = math.ceil(px - radius), math.ceil(px + radius)
            top, bottom = math.ceil(py - radius), math.ceil(py + radius)
            if right <= 0 or bottom <= 0 or left >= target.width or top >= target.height:
                target._cropped[(wx, wy)] = (rgb, span)
                return
            for ny in range(max(0, top), min(target.height, bottom)):
                row = target.pix[ny]
                for nx in range(max(0, left), min(target.width, right)):
                    row[nx] = rgb

        for (wx, wy), (rgb, span) in self._cropped.items():
            copy_pixel(wx, wy, rgb, span)
        for y, row in enumerate(self.pix):
            wy = (self.origin_y - y) / self.scale
            for x, rgb in enumerate(row):
                if rgb is None:
                    continue
                wx = (x - self.origin_x) / self.scale
                copy_pixel(wx, wy, rgb, 1 / self.scale)
        for col, row, text, rgb in self.labels:
            wx = (col * self.cell[0] + self.cell[0] / 2 - self.origin_x) / self.scale
            wy = (self.origin_y - row * self.cell[1] - self.cell[1] / 2) / self.scale
            px = target.origin_x + wx * target.scale
            py = target.origin_y - wy * target.scale
            ncol, nrow = int(px // target.cell[0]), int(py // target.cell[1])
            target.labels.append((ncol, nrow, text, rgb))
        target.dirty = True

    # ---- coordinates -----------------------------------------------------
    def to_pixel(self, x, y):
        return (
            round(self.origin_x + x * self.scale),
            round(self.origin_y - y * self.scale),
        )

    def to_pixel_f(self, x, y):
        """Continuous pixel coordinates; pixel i is centred on integer i."""
        return (self.origin_x + x * self.scale - 0.5, self.origin_y - y * self.scale - 0.5)

    def from_pixel(self, px, py):
        return (px - self.origin_x) / self.scale, (self.origin_y - py) / self.scale

    @property
    def half_w(self):
        return self.width / 2 / self.scale

    @property
    def half_h(self):
        return self.height / 2 / self.scale

    # ---- drawing ---------------------------------------------------------
    def clear(self):
        self.pix = [[None] * self.width for _ in range(self.height)]
        self._cropped.clear()
        self.labels = []
        self.dirty = True

    def _paint(self, x, y, rgb, coverage=1, painted=None):
        if len(rgb) == 3:
            self.pix[y][x] = rgb
            return
        if rgb[3] == 0:
            return
        base = self.pix[y][x]
        if painted is not None:
            key = self.from_pixel(x, y)
            if key in painted:
                base, previous = painted[key]
                if coverage <= previous:
                    return
            painted[key] = (base, coverage)
        self.pix[y][x] = composite((*rgb[:3], rgb[3] * coverage), base)

    def display_colour(self, colour):
        if colour is not None and len(colour) == 3:
            return colour
        if colour is None and len(self.bg) == 3:
            return self.bg
        bg = composite(self.bg, (255, 255, 255))[:3]
        return composite(colour, bg)[:3]

    def plot(self, x, y, rgb, mode='paint', size=1, painted=None):
        if mode != 'erase' and len(rgb) == 4 and rgb[3] == 0:
            return
        off = size // 2
        for dy in range(size):
            for dx in range(size):
                px, py = x - off + dx, y - off + dy
                if 0 <= px < self.width and 0 <= py < self.height:
                    if mode == 'erase':
                        self.pix[py][px] = None
                    elif mode == 'reverse':
                        self.pix[py][px] = None if self.pix[py][px] is not None else rgb
                    else:
                        self._paint(px, py, rgb, painted=painted)
        self.dirty = True

    def line(self, x0, y0, x1, y1, rgb, mode='paint', size=1, painted=None):
        if len(rgb) == 4 and painted is None:
            painted = {}
        for x, y in bresenham(x0, y0, x1, y1):
            self.plot(x, y, rgb, mode, size, painted)

    def blend(self, x, y, rgb, alpha, painted=None):
        if 0 <= x < self.width and 0 <= y < self.height and alpha > 0.004:
            if len(rgb) == 4:
                self._paint(x, y, rgb, alpha, painted)
            elif alpha >= 0.996:
                self.pix[y][x] = rgb
            else:
                base = self.pix[y][x] or self.bg
                self.pix[y][x] = (
                    int(base[0] + (rgb[0] - base[0]) * alpha),
                    int(base[1] + (rgb[1] - base[1]) * alpha),
                    int(base[2] + (rgb[2] - base[2]) * alpha),
                )

    def aa_line(self, x0, y0, x1, y1, rgb, width=1.0, painted=None):
        """Anti-aliased round-capped line of `width` pixels between float points.

        Walks the major axis and gives each pixel in a strip coverage from its true
        distance to the segment, so every pixel is visited once."""
        if len(rgb) == 4 and painted is None:
            painted = {}
        hw = max(width, 1.0) / 2.0
        steep = abs(y1 - y0) > abs(x1 - x0)
        if steep:
            a0, b0, a1, b1 = y0, x0, y1, x1
        else:
            a0, b0, a1, b1 = x0, y0, x1, y1
        da, db = a1 - a0, b1 - b0
        length2 = da * da + db * db
        reach = hw * 1.5 + 1
        start = int(math.floor(min(a0, a1) - hw - 1))
        stop = int(math.ceil(max(a0, a1) + hw + 1))
        if stop - start > 200000:
            return
        for a in range(start, stop + 1):
            if da == 0:
                bc = b0
            else:
                t = min(1.0, max(0.0, (a - a0) / da))
                bc = b0 + db * t
            for b in range(int(math.floor(bc - reach)), int(math.ceil(bc + reach)) + 1):
                if length2 == 0:
                    d = math.hypot(a - a0, b - b0)
                else:
                    t = ((a - a0) * da + (b - b0) * db) / length2
                    t = 0.0 if t < 0 else 1.0 if t > 1 else t
                    d = math.hypot(a - (a0 + da * t), b - (b0 + db * t))
                alpha = hw + 0.5 - d
                if alpha > 0:
                    if steep:
                        self.blend(b, a, rgb, min(1.0, alpha), painted)
                    else:
                        self.blend(a, b, rgb, min(1.0, alpha), painted)
        self.dirty = True

    def fill(self, x, y, rgb, tolerance=None):
        if not (0 <= x < self.width and 0 <= y < self.height):
            return
        target = self.pix[y][x]
        if target == rgb and tolerance is None:
            return
        stack = [(x, y)]
        visited = bytearray(self.width * self.height)
        while stack:
            cx, cy = stack.pop()
            if not (0 <= cx < self.width and 0 <= cy < self.height):
                continue
            index = cy * self.width + cx
            if visited[index]:
                continue
            visited[index] = 1
            pixel = self.pix[cy][cx]
            if pixel != target and not (
                tolerance is not None and (tolerance == 1 or rgba(pixel)[3] < tolerance)
            ):
                continue
            self._paint(cx, cy, rgb)
            stack.extend(((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)))
        self.dirty = True

    def label(self, px, py, text, rgb):
        if len(rgb) == 4 and rgb[3] == 0:
            return
        self.labels.append((px // self.cell[0], py // self.cell[1], text, rgb))
        self.dirty = True

    # ---- turtle marker ---------------------------------------------------
    def _overlay(self, turtle):
        """Pixel set for the turtle marker (a triangle pointing along the heading)."""
        if turtle is None or not turtle.visible or (len(turtle.rgb) == 4 and turtle.rgb[3] == 0):
            return set()
        px, py = self.to_pixel(turtle.x, turtle.y)
        h = math.radians(turtle.heading)
        r = self.marker_r
        pts = []
        for ang, k in ((0, 1.0), (140, 0.85), (-140, 0.85)):
            a = h + math.radians(ang)
            pts.append((int(round(px + r * k * math.sin(a))), int(round(py - r * k * math.cos(a)))))
        out = set()
        thick = max(1, self.unit)
        for i in range(3):
            a, b = pts[i], pts[(i + 1) % 3]
            for x, y in bresenham(a[0], a[1], b[0], b[1]):
                for dx in range(thick):
                    for dy in range(thick):
                        if 0 <= x + dx < self.width and 0 <= y + dy < self.height:
                            out.add((x + dx, y + dy))
        return out

    def _label_cells(self):
        cells = {}
        for col, row, text, rgb in self.labels:
            for i, ch in enumerate(text):
                cells[(col + i, row)] = (ch, self.display_colour(rgb))
        return cells

    def _marker_colour(self, turtle):
        return turtle.rgb if turtle is not None and self.alpha else TURTLE_RGB

    def _colour_at(self, x, y, over, marker=TURTLE_RGB):
        if (x, y) in over:
            return self.display_colour(composite(marker, self.pix[y][x]))
        c = self.pix[y][x]
        return self.display_colour(c)

    # ---- renderers: terminal text ------------------------------------------
    def render(self, turtle=None, color=True, mode=None):
        """The canvas as a list of strings, one per terminal row."""
        mode = mode or ('half' if self.cell == (1, 2) else 'braille')
        if mode == 'half':
            return self.render_half(turtle, color)
        return self.render_braille(turtle, color)

    def _dot(self, c, r, i, j, over):
        """Is Braille dot (i, j) of cell (c, r) lit? Returns the colour or None."""
        pw, ph = self.cell
        x0, x1 = c * pw + (i * pw) // 2, c * pw + max(((i + 1) * pw) // 2, (i * pw) // 2 + 1)
        y0, y1 = r * ph + (j * ph) // 4, r * ph + max(((j + 1) * ph) // 4, (j * ph) // 4 + 1)
        found = None
        for y in range(y0, y1):
            row = self.pix[y]
            for x in range(x0, x1):
                if (x, y) in over:
                    return 'T'
                if row[x] is not None and found is None:
                    found = self.display_colour(row[x])
        return found

    def render_braille(self, turtle=None, color=True):
        over = self._overlay(turtle)
        marker = self.display_colour(self._marker_colour(turtle))
        label_cells = self._label_cells()
        bg = self.display_colour(None)
        bgcode = '' if bg == PALETTE[0] else '\x1b[48;2;%d;%d;%dm' % bg
        reset = '\x1b[0m' + bgcode
        lines = []
        for r in range(self.rows):
            parts, cur = [bgcode if color else ''], None
            for c in range(self.cols):
                if (c, r) in label_cells:
                    ch, rgb = label_cells[(c, r)]
                else:
                    mask, counts = 0, {}
                    for i in range(2):
                        for j in range(4):
                            col = self._dot(c, r, i, j, over)
                            if col is not None:
                                mask |= BIT[i][j]
                                counts[col] = counts.get(col, 0) + 1
                    if mask == 0:
                        ch, rgb = ' ', None
                    else:
                        ch = chr(0x2800 + mask)
                        rgb = marker if 'T' in counts else max(counts, key=counts.get)
                if color:
                    if rgb != cur:
                        parts.append(reset if rgb is None else '\x1b[38;2;%d;%d;%dm' % rgb)
                        cur = rgb
                parts.append(ch)
            if color and (cur is not None or bgcode):
                parts.append('\x1b[0m')
            lines.append(''.join(parts))
        return lines

    def render_half(self, turtle=None, color=True):
        """Solid half-block rendering: each cell is two stacked pixels."""
        over = self._overlay(turtle)
        marker = self._marker_colour(turtle)
        bg = self.display_colour(None)
        label_cells = self._label_cells()
        lines = []
        for r in range(self.rows):
            parts, cur = [], None
            for c in range(self.cols):
                x = c * self.cell[0]
                top = self._colour_at(x, r * 2, over, marker)
                bot = self._colour_at(x, r * 2 + 1, over, marker)
                if (c, r) in label_cells:
                    ch, fg = label_cells[(c, r)]
                    top = bot = bg
                elif color:
                    ch, fg = '▀', top
                else:
                    t, b = top != bg, bot != bg
                    ch = '█' if t and b else '▀' if t else '▄' if b else ' '
                    fg = None
                if color:
                    state = (fg, bot)
                    if state != cur:
                        parts.append('\x1b[38;2;%d;%d;%d;48;2;%d;%d;%dm' % (*fg, *bot))
                        cur = state
                parts.append(ch)
            if color:
                parts.append('\x1b[0m')
            lines.append(''.join(parts))
        return lines

    # ---- renderer: terminal graphics protocol ---------------------------------
    def kitty_image(self, turtle=None, standalone=False):
        """Escape sequence that draws the canvas as one real-pixel image (Kitty
        graphics protocol: Ghostty, Kitty, WezTerm). Text such as labels is left to
        the caller, since the image sits beneath the text layer (z=-1)."""
        png = self.to_png(
            overlay=self._overlay(turtle), pixel=1, overlay_colour=self._marker_colour(turtle)
        )
        data = base64.b64encode(png).decode('ascii')
        chunks = [data[i : i + 4096] for i in range(0, len(data), 4096)] or ['']
        head = 'a=T,f=100,t=d,i=1,c=%d,r=%d,C=1,z=-1,q=2' % (self.cols, self.rows)
        out = ['\x1b_Ga=d,d=A,q=2\x1b\\']
        for n, chunk in enumerate(chunks):
            more = 1 if n < len(chunks) - 1 else 0
            keys = f'{head},m={more}' if n == 0 else f'm={more},q=2'
            out.append(f'\x1b_G{keys};{chunk}\x1b\\')
        return ''.join(out)

    def kitty_label_text(self, color=True):
        """Labels as positioned terminal text, drawn over the image."""
        out = []
        for col, row, text, rgb in self.labels:
            if 0 <= row < self.rows and col < self.cols and col + len(text) > 0:
                text = text[max(0, -col) : max(0, -col) + self.cols - max(0, col)]
                col = max(0, col)
                code = '\x1b[38;2;%d;%d;%dm' % self.display_colour(rgb) if color else ''
                out.append(f'\x1b[{row + 1};{col + 1}H{code}{text}\x1b[0m')
        return ''.join(out)

    # ---- export ----------------------------------------------------------
    def to_text(self):
        return '\n'.join(line.rstrip() for line in self.render_braille(color=False)) + '\n'

    def _auto_pixel(self):
        return max(1, 800 // max(1, self.width))

    def to_svg(self, pixel=None):
        pixel = pixel or self._auto_pixel() or 1
        w, h = self.width * pixel, self.height * pixel
        bg = '#%02x%02x%02x' % self.bg[:3]
        opacity = f' fill-opacity="{self.bg[3]:g}"' if len(self.bg) == 4 else ''
        out = [
            '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
            'viewBox="0 0 %d %d">' % (w, h, w, h),
            '<rect width="100%%" height="100%%" fill="%s"%s/>' % (bg, opacity),
        ]
        for y in range(self.height):
            x = 0
            row = self.pix[y]
            while x < self.width:
                col = row[x]
                if col is None:
                    x += 1
                    continue
                x2 = x
                while x2 < self.width and row[x2] == col:
                    x2 += 1
                opacity = f' fill-opacity="{col[3]:g}"' if len(col) == 4 else ''
                out.append(
                    '<rect x="%d" y="%d" width="%d" height="%d" fill="#%02x%02x%02x"%s/>'
                    % (x * pixel, y * pixel, (x2 - x) * pixel, pixel, *col[:3], opacity)
                )
                x = x2
        out.append('</svg>')
        return '\n'.join(out) + '\n'

    def to_png(self, pixel=None, overlay=None, overlay_colour=TURTLE_RGB):
        pixel = pixel or self._auto_pixel()
        w, h = self.width * pixel, self.height * pixel
        lut = _Bytes(self.bg, pixel, self.alpha)
        by_row = {}
        for x, y in overlay or ():
            by_row.setdefault(y, []).append(x)
        raw = bytearray()
        for y in range(self.height):
            cells = list(map(lut.__getitem__, self.pix[y]))
            for x in by_row.get(y, ()):
                if self.alpha:
                    cells[x] = lut[composite(overlay_colour, self.pix[y][x])]
                else:
                    cells[x] = lut[overlay_colour]
            line = b'\x00' + b''.join(cells)
            raw += line * pixel

        def chunk(tag, body):
            c = struct.pack('>I', len(body)) + tag + body
            return c + struct.pack('>I', zlib.crc32(tag + body) & 0xFFFFFFFF)

        return (
            b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6 if self.alpha else 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(bytes(raw), 1))
            + chunk(b'IEND', b'')
        )

    def save(self, path):
        p = str(path).lower()
        if p.endswith('.svg'):
            with open(path, 'w') as f:
                f.write(self.to_svg())
        elif p.endswith('.png'):
            with open(path, 'wb') as f:
                f.write(self.to_png())
        else:
            with open(path, 'w') as f:
                f.write(self.to_text())
