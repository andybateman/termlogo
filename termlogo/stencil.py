"""3D-printable stencil export: pen strokes become slots cut through a flat plate.

Pipeline (standard library only):
  1. Strokes -> signed-distance field on a fine grid (negative inside a slot).
  2. Islands that would fall out of the plate (the centre of an O) are found and
     tied back with bridges, which are added to the field.
  3. Marching squares traces smooth outlines from the field.
  4. Outlines are simplified, nested, triangulated (earcut) and extruded into a
     watertight triangle mesh, written as binary STL.
One turtle step is one millimetre by default, and pen size is the slot width.
"""

import math
import struct
from collections import Counter, deque

from .earcut import triangulate
from .errors import LogoError

DEFAULTS = {
    'thickness': 1.2,  # plate thickness, mm
    'margin': 8.0,  # border around the drawing, mm
    'pitch': 0.2,  # grid resolution, mm (finer is smoother but slower)
    'bridge': 1.6,  # width of each bridge, mm
    'bridges': 2,  # bridges per island (where there is room)
    'width': None,  # force every slot to this width, mm (default: the pen size)
    'minwidth': 0.8,  # narrowest slot printable with a 0.4 mm nozzle, mm
    'mm': 1.0,  # millimetres per turtle step
    'mirror': False,  # flip left-right, for use with the printed face down
    'plate': None,  # [width height] in mm; default fits the drawing plus margin
    'maxgap': 15.0,  # longest slot a bridge may span, mm
}
FAR = 1e9
MIN_ISLAND_MM2 = 1.0


def parse_options(spec):
    """Turn a Logo list like [thickness 1.6 mirror true plate [100 80]] into options."""
    opts = dict(DEFAULTS)
    if spec is None:
        return opts
    if not isinstance(spec, list) or len(spec) % 2:
        raise LogoError('stencil options must be pairs: [thickness 1.2 margin 8]')
    for key, val in zip(spec[::2], spec[1::2], strict=True):
        k = str(key).lower()
        if k not in DEFAULTS:
            raise LogoError(f"stencil doesn't know the option {key} (try {', '.join(DEFAULTS)})")
        try:
            if k == 'mirror':
                opts[k] = str(val).lower() in ('true', '1', 'yes')
            elif k == 'plate':
                if not (isinstance(val, list) and len(val) == 2):
                    raise ValueError
                opts[k] = (float(val[0]), float(val[1]))
            elif k == 'bridges':
                opts[k] = int(float(val))
            else:
                opts[k] = float(val)
        except (TypeError, ValueError) as e:
            raise LogoError(f"stencil doesn't like {val} for {key}") from e
    for k in ('thickness', 'pitch', 'bridge', 'minwidth', 'mm', 'maxgap'):
        if opts[k] <= 0:
            raise LogoError(f'stencil needs {k} to be above zero')
    if opts['width'] is not None and opts['width'] <= 0:
        raise LogoError('stencil needs width to be above zero')
    if opts['margin'] < 0 or opts['bridges'] < 0:
        raise LogoError("stencil margin and bridges can't be negative")
    return opts


# ---- 1. signed-distance field ---------------------------------------------------
def _carve(f, nx, ny, p, seg, hw):
    """Lower the field near one segment to (distance to segment - half width)."""
    x0, y0, x1, y1 = seg
    dx, dy = x1 - x0, y1 - y0
    l2 = dx * dx + dy * dy
    reach = hw + 2 * p
    ext = reach * 1.5
    by_col = abs(dx) >= abs(dy)
    if by_col:
        a_lo, a_hi = min(x0, x1) - reach, max(x0, x1) + reach
    else:
        a_lo, a_hi = min(y0, y1) - reach, max(y0, y1) + reach
    for a in range(max(0, int(a_lo / p)), min((nx if by_col else ny) - 1, int(a_hi / p) + 1) + 1):
        if by_col:
            x = a * p
            t = 0.0 if dx == 0 else min(1.0, max(0.0, (x - x0) / dx))
            c = y0 + dy * t
            lo, hi = max(0, int((c - ext) / p)), min(ny - 1, int((c + ext) / p) + 1)
        else:
            y = a * p
            t = 0.0 if dy == 0 else min(1.0, max(0.0, (y - y0) / dy))
            c = x0 + dx * t
            lo, hi = max(0, int((c - ext) / p)), min(nx - 1, int((c + ext) / p) + 1)
        for b in range(lo, hi + 1):
            if by_col:
                i, j = a, b
            else:
                i, j = b, a
            px, py = i * p, j * p
            if l2 == 0:
                d = math.hypot(px - x0, py - y0)
            else:
                u = ((px - x0) * dx + (py - y0) * dy) / l2
                u = 0.0 if u < 0 else 1.0 if u > 1 else u
                d = math.hypot(px - x0 - dx * u, py - y0 - dy * u)
            d -= hw
            k = j * nx + i
            if d < f[k]:
                f[k] = d


# ---- 2. islands and bridges --------------------------------------------------------
def _label(f, nx, ny):
    """Connected components of solid nodes (field >= 0). Returns labels and sizes."""
    lab = [0] * (nx * ny)
    sizes = [0]
    n = 0
    for start in range(nx * ny):
        if lab[start] or f[start] < 0:
            continue
        n += 1
        lab[start] = n
        q = deque([start])
        count = 0
        while q:
            k = q.popleft()
            count += 1
            i = k % nx
            for m in ((k - 1) if i > 0 else -1, (k + 1) if i < nx - 1 else -1, k - nx, k + nx):
                if 0 <= m < nx * ny and not lab[m] and f[m] >= 0:
                    lab[m] = n
                    q.append(m)
        sizes.append(count)
    return lab, sizes


def _box_sdf(x, y, cx, cy, ex, ey):
    qx, qy = abs(x - cx) - ex, abs(y - cy) - ey
    return math.hypot(max(qx, 0.0), max(qy, 0.0)) + min(max(qx, qy), 0.0)


def _apply_bridge(f, nx, ny, p, node, direction, steps, width):
    """Make a solid rectangle across a slot, from `node` for `steps` nodes along
    `direction` (an axis step), `width` mm thick."""
    i0, j0 = node % nx, node // nx
    di, dj = direction
    i1, j1 = i0 + di * steps, j0 + dj * steps
    x0, y0, x1, y1 = i0 * p, j0 * p, i1 * p, j1 * p
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    if di:
        ex, ey = abs(x1 - x0) / 2 + p * 1.5, width / 2
    else:
        ex, ey = width / 2, abs(y1 - y0) / 2 + p * 1.5
    r = max(ex, ey) + 3 * p
    for j in range(max(0, int((cy - r) / p)), min(ny - 1, int((cy + r) / p) + 1) + 1):
        for i in range(max(0, int((cx - r) / p)), min(nx - 1, int((cx + r) / p) + 1) + 1):
            g = _box_sdf(i * p, j * p, cx, cy, ex, ey)
            k = j * nx + i
            if -g > f[k]:
                f[k] = -g


DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))


def _bridge_islands(f, nx, ny, p, opts, report):
    lab, sizes = _label(f, nx, ny)
    if len(sizes) <= 2:
        return
    main = max(range(1, len(sizes)), key=lambda c: sizes[c])
    # Specks under 1 mm2 are too small to print or to hold a bridge: fill them in.
    specks = {c for c in range(1, len(sizes)) if c != main and sizes[c] * p * p < MIN_ISLAND_MM2}
    if specks:
        for k in range(nx * ny):
            if lab[k] in specks:
                f[k] = -p
        report['specks'] = len(specks)
    islands = [c for c in range(1, len(sizes)) if c != main and c not in specks]
    report['islands'] = len(islands)
    if not islands:
        return
    max_k = int(opts['maxgap'] / p)
    cands = {c: [] for c in islands}  # island -> [(steps, node, dir, other)]
    island_set = set(islands)
    for k in range(nx * ny):
        a = lab[k]
        if a not in island_set:
            continue
        i = k % nx
        for di, dj in DIRS:
            ni, nj = i + di, k // nx + dj
            if not (0 <= ni < nx and 0 <= nj < ny) or f[nj * nx + ni] >= 0:
                continue
            s = 1
            while True:
                ci, cj = i + di * s, k // nx + dj * s
                if not (0 <= ci < nx and 0 <= cj < ny) or s > max_k:
                    break
                m = cj * nx + ci
                if f[m] >= 0:
                    if lab[m] != a:
                        cands[a].append((s, k, (di, dj), lab[m]))
                    break
                s += 1
    parent = {c: c for c in range(1, len(sizes))}

    def find(c):
        while parent[c] != c:
            parent[c] = parent[parent[c]]
            c = parent[c]
        return c

    edges = sorted(
        ((s, a, b, k, d) for a, lst in cands.items() for s, k, d, b in lst), key=lambda e: e[0]
    )
    chosen = {}  # island -> [(steps, node, dir)]
    for s, a, b, k, d in edges:
        if find(a) != find(b):
            parent[find(a)] = find(b)
            chosen.setdefault(a, []).append((s, k, d))
    unreachable = [c for c in islands if find(c) != find(main)]
    report['unbridged'] = len(unreachable)
    pitch_sep = max(4 * opts['bridge'], 6.0) / p
    for a, picks in chosen.items():
        base = picks[0][0]
        pool = [(s, k, d) for s, k, d, _ in cands[a] if s <= base * 1.5 + 2]
        for _ in range(max(0, opts['bridges'] - 1)):

            def far(c, picks=picks):
                return min(
                    math.hypot(c[1] % nx - q[1] % nx, c[1] // nx - q[1] // nx) for q in picks
                )

            best = max(pool, key=far, default=None)
            if best is None or far(best) < pitch_sep:
                break
            picks.append(best)
    for picks in chosen.values():
        for s, k, d in picks:
            _apply_bridge(f, nx, ny, p, k, d, s, opts['bridge'])
            report['bridges'] += 1


# ---- 3. marching squares ----------------------------------------------------------
# Segments per cell case, as (from_edge, to_edge) with the cut region on the right
# (so solid is on the left). Edges: 0 bottom, 1 right, 2 top, 3 left. Corners are
# 0=(i,j) 1=(i+1,j) 2=(i+1,j+1) 3=(i,j+1) and a set bit means "cut".
_CASES = {
    1: ((3, 0),),
    2: ((0, 1),),
    3: ((3, 1),),
    4: ((1, 2),),
    6: ((0, 2),),
    7: ((3, 2),),
    8: ((2, 3),),
    9: ((2, 0),),
    11: ((2, 1),),
    12: ((1, 3),),
    13: ((1, 0),),
    14: ((0, 3),),
}


def _outlines(f, nx, ny, p):
    cross = {}
    nxt = {}

    def edge(i, j, e):
        if e == 0:
            return (j * nx + i) * 2
        if e == 1:
            return (j * nx + i + 1) * 2 + 1
        if e == 2:
            return ((j + 1) * nx + i) * 2
        return (j * nx + i) * 2 + 1

    def point(key):
        pt = cross.get(key)
        if pt is None:
            node, vertical = key >> 1, key & 1
            i, j = node % nx, node // nx
            a = f[node]
            b = f[node + nx] if vertical else f[node + 1]
            t = a / (a - b)
            pt = (i * p, (j + t) * p) if vertical else ((i + t) * p, j * p)
            cross[key] = pt
        return pt

    for j in range(ny - 1):
        row = j * nx
        for i in range(nx - 1):
            k = row + i
            v0, v1, v2, v3 = f[k], f[k + 1], f[k + nx + 1], f[k + nx]
            idx = (v0 < 0) | ((v1 < 0) << 1) | ((v2 < 0) << 2) | ((v3 < 0) << 3)
            if idx == 0 or idx == 15:
                continue
            if idx == 5 or idx == 10:
                centre_cut = (v0 + v1 + v2 + v3) < 0
                if idx == 5:
                    segs = ((1, 0), (3, 2)) if centre_cut else ((3, 0), (1, 2))
                else:
                    segs = ((0, 3), (2, 1)) if centre_cut else ((0, 1), (2, 3))
            else:
                segs = _CASES[idx]
            for a, b in segs:
                nxt[edge(i, j, a)] = edge(i, j, b)
    loops = []
    seen = set()
    for start in nxt:
        if start in seen:
            continue
        ring, cur = [], start
        while cur not in seen:
            seen.add(cur)
            ring.append(point(cur))
            cur = nxt.get(cur)
            if cur is None:
                ring = None
                break
        if ring and cur == start and len(ring) >= 3:
            loops.append(ring)
    return loops


def _simplify(ring, tol):
    """Douglas-Peucker on a closed ring, anchored at the point farthest from point 0."""
    n = len(ring)
    if n <= 6:
        return ring
    x0, y0 = ring[0]
    far = max(range(n), key=lambda i: (ring[i][0] - x0) ** 2 + (ring[i][1] - y0) ** 2)
    keep = [False] * n
    keep[0] = keep[far] = True
    stack = [(0, far), (far, n)]
    while stack:
        a, b = stack.pop()
        if b - a < 2:
            continue
        ax, ay = ring[a]
        bx, by = ring[b % n]
        dx, dy = bx - ax, by - ay
        norm = math.hypot(dx, dy)
        worst, wi = -1.0, -1
        for i in range(a + 1, b):
            px, py = ring[i]
            d = (
                abs((px - ax) * dy - (py - ay) * dx) / norm
                if norm
                else math.hypot(px - ax, py - ay)
            )
            if d > worst:
                worst, wi = d, i
        if worst > tol:
            keep[wi] = True
            stack.append((a, wi))
            stack.append((wi, b))
    return [pt for pt, k in zip(ring, keep, strict=True) if k]


def _area(ring):
    return (
        sum(
            ring[i][0] * ring[(i + 1) % len(ring)][1] - ring[(i + 1) % len(ring)][0] * ring[i][1]
            for i in range(len(ring))
        )
        / 2.0
    )


def _inside(pt, ring):
    x, y = pt
    c = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            c = not c
        j = i
    return c


# ---- 4. mesh -----------------------------------------------------------------------
def _extrude(solids, thickness):
    """solids: list of (outer CCW ring, [hole rings CW]). Returns 3D triangles."""
    tris = []
    z0, z1 = 0.0, thickness
    for outer, holes in solids:
        verts = list(outer)
        for h in holes:
            verts.extend(h)
        idx = triangulate(outer, holes)
        used = {i for t in idx for i in t}
        for i, j, k in idx:
            a, b, c = verts[i], verts[j], verts[k]
            if (b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1]) < 0:
                b, c = c, b
            tris.append(((a[0], a[1], z1), (b[0], b[1], z1), (c[0], c[1], z1)))
            tris.append(((a[0], a[1], z0), (c[0], c[1], z0), (b[0], b[1], z0)))
        base = 0
        for ring in [outer] + holes:
            ids = [base + n for n in range(len(ring))]
            base += len(ring)
            keep = [ring[n] for n, vid in enumerate(ids) if vid in used]
            for n in range(len(keep)):
                a, b = keep[n], keep[(n + 1) % len(keep)]
                tris.append(((a[0], a[1], z0), (b[0], b[1], z0), (b[0], b[1], z1)))
                tris.append(((a[0], a[1], z0), (b[0], b[1], z1), (a[0], a[1], z1)))
    return tris


def make_stencil(strokes, options=None):
    """Build the stencil mesh. Returns (triangles, report)."""
    opts = parse_options(options) if not isinstance(options, dict) else {**DEFAULTS, **options}
    if not strokes:
        raise LogoError('Nothing to export: draw something with the pen down first')
    mm, p = opts['mm'], opts['pitch']
    report = {'islands': 0, 'bridges': 0, 'unbridged': 0, 'widened': 0, 'specks': 0, 'warnings': []}
    segs = []
    for x0, y0, x1, y1, w in strokes:
        width = opts['width'] if opts['width'] is not None else w * mm
        if width < opts['minwidth']:
            width = opts['minwidth']
            report['widened'] += 1
        segs.append((x0 * mm, y0 * mm, x1 * mm, y1 * mm, width))
    xs = [
        v
        for s in segs
        for v in (s[0] - s[4] / 2, s[2] - s[4] / 2, s[0] + s[4] / 2, s[2] + s[4] / 2)
    ]
    ys = [
        v
        for s in segs
        for v in (s[1] - s[4] / 2, s[3] - s[4] / 2, s[1] + s[4] / 2, s[3] + s[4] / 2)
    ]
    bw, bh = max(xs) - min(xs), max(ys) - min(ys)
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    if opts['plate']:
        W, H = opts['plate']
        if W < bw + 2 * 2 * p or H < bh + 2 * 2 * p:
            raise LogoError(
                f'The drawing is {bw:.1f} x {bh:.1f} mm but the plate is only {W:g} x {H:g} mm'
            )
    else:
        W, H = bw + 2 * opts['margin'], bh + 2 * opts['margin']
    W, H = max(W, bw + 4 * p), max(H, bh + 4 * p)
    ox, oy = cx - W / 2, cy - H / 2
    nx, ny = int(W / p) + 2, int(H / p) + 2
    if nx * ny > 6_000_000:
        raise LogoError('Plate is too big for this pitch: raise pitch or lower the size')
    f = [FAR] * (nx * ny)
    for x0, y0, x1, y1, w in segs:
        _carve(f, nx, ny, p, (x0 - ox, y0 - oy, x1 - ox, y1 - oy), w / 2)
    _bridge_islands(f, nx, ny, p, opts, report)
    rings = []
    for ring in _outlines(f, nx, ny, p):
        ring = _simplify(ring, p * 0.1)
        if len(ring) >= 3 and abs(_area(ring)) > p * p:
            rings.append(ring)
    plate = [(0.0, 0.0), (W, 0.0), (W, H), (0.0, H)]
    items = [(plate, W * H, 'plate')] + [
        (r, abs(_area(r)), 'ccw' if _area(r) > 0 else 'cw') for r in rings
    ]
    items.sort(key=lambda it: -it[1])
    solids = {0: (plate, [])}
    for n, (ring, _area_size, kind) in enumerate(items[1:], 1):
        parent = None
        for m in range(n - 1, -1, -1):  # smallest container first
            if _inside(ring[0], items[m][0]):
                parent = m
                break
        if kind == 'ccw':
            solids[n] = (ring, [])
            report['warnings'].append('an island is not tied to the plate and may fall out')
        elif parent in solids:
            solids[parent][1].append(ring)
    tris = _extrude(list(solids.values()), opts['thickness'])
    if opts['mirror']:
        tris = [
            ((W - a[0], a[1], a[2]), (W - c[0], c[1], c[2]), (W - b[0], b[1], b[2]))
            for a, b, c in tris
        ]
    if report['unbridged']:
        report['warnings'].append(
            f'{report["unbridged"]} island(s) are further than '
            f'{opts["maxgap"]:g} mm from the plate and were not bridged'
        )
    if report['specks']:
        report['warnings'].append(
            f'{report["specks"]} sliver(s) under {MIN_ISLAND_MM2:g} mm2 '
            'were too small to print and were filled in'
        )
    if report['widened']:
        report['warnings'].append(
            f'{report["widened"]} stroke(s) were narrower than '
            f'{opts["minwidth"]:g} mm and were widened to print'
        )
    report.update(
        size=(W, H, opts['thickness']),
        triangles=len(tris),
        slot_area=W * H
        - sum(abs(_area(r)) for r in rings if _area(r) < 0) * 0
        - sum(abs(_area(r)) for r in rings if _area(r) > 0) * 0,
        holes=sum(1 for r in rings if _area(r) < 0),
        unrecorded=0,
    )
    report['cut_area'] = sum(abs(_area(r)) for r in rings if _area(r) < 0) - sum(
        abs(_area(r)) for r in rings if _area(r) > 0
    )
    return tris, report


# ---- output and checks ---------------------------------------------------------------
def to_stl(tris, name='termlogo stencil'):
    out = bytearray(name.encode('ascii', 'replace')[:80].ljust(80, b' '))
    out += struct.pack('<I', len(tris))
    for a, b, c in tris:
        ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
        nx_, ny_, nz_ = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
        ln = math.sqrt(nx_ * nx_ + ny_ * ny_ + nz_ * nz_) or 1.0
        out += struct.pack('<12fH', nx_ / ln, ny_ / ln, nz_ / ln, *a, *b, *c, 0)
    return bytes(out)


def write_stl(path, tris):
    try:
        with open(path, 'wb') as fh:
            fh.write(to_stl(tris))
    except OSError as e:
        raise LogoError(f"Can't write {path}: {e.strerror}") from e


def check_mesh(tris, places=5):
    """Return (open_edges, volume). A watertight, consistently wound mesh has zero
    open edges (every directed edge has its reverse) and a positive volume."""

    def key(v):
        return (round(v[0], places), round(v[1], places), round(v[2], places))

    edges = Counter()
    vol = 0.0
    for a, b, c in tris:
        ka, kb, kc = key(a), key(b), key(c)
        edges[(ka, kb)] += 1
        edges[(kb, kc)] += 1
        edges[(kc, ka)] += 1
        vol += (
            a[0] * (b[1] * c[2] - b[2] * c[1])
            - a[1] * (b[0] * c[2] - b[2] * c[0])
            + a[2] * (b[0] * c[1] - b[1] * c[0])
        ) / 6.0
    open_edges = sum(1 for (a, b), n in edges.items() if edges.get((b, a), 0) != n or n != 1)
    return open_edges, vol


def describe(report, path=None):
    W, H, T = report['size']
    line = f'Stencil {W:.1f} x {H:.1f} x {T:g} mm, {report["triangles"]:,} triangles'
    if report['bridges']:
        line += f', {report["bridges"]} bridge(s) across {report["islands"]} island(s)'
    if path:
        line += f' -> {path}'
    return [line] + ['Warning: ' + w for w in report['warnings']]
