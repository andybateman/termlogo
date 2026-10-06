"""Polygon triangulation with holes: a port of the earcut ear-clipping algorithm
(Mapbox, ISC licence) with its z-order hashing, so large outlines stay fast.

`triangulate(outer, holes)` takes rings as lists of (x, y) and returns a list of
(i, j, k) index triples into the flat vertex list `outer + holes[0] + holes[1] + ...`.
"""


class _Node:
    __slots__ = ('i', 'x', 'y', 'prev', 'next', 'z', 'prev_z', 'next_z', 'steiner')

    def __init__(self, i, x, y):
        self.i, self.x, self.y = i, x, y
        self.prev = self.next = None
        self.z = 0
        self.prev_z = self.next_z = None
        self.steiner = False


def triangulate(outer, holes=()):
    pts = list(outer)
    hole_starts = []
    for h in holes:
        hole_starts.append(len(pts))
        pts.extend(h)
    outer_len = len(outer)
    node = _linked_list(pts, 0, outer_len, True)
    triangles = []
    if node is None or node.next is node.prev:
        return triangles
    if hole_starts:
        node = _eliminate_holes(pts, hole_starts, node)
    min_x = min_y = inv = None
    if len(pts) > 80:
        xs = [p[0] for p in pts[:outer_len]]
        ys = [p[1] for p in pts[:outer_len]]
        min_x, min_y = min(xs), min(ys)
        size = max(max(xs) - min_x, max(ys) - min_y)
        inv = 32767.0 / size if size else 0
    _earcut_linked(node, triangles, min_x, min_y, inv, 0)
    return triangles


def _linked_list(pts, start, end, clockwise):
    last = None
    if clockwise == (_signed_area(pts, start, end) > 0):
        for i in range(start, end):
            last = _insert(i, pts[i][0], pts[i][1], last)
    else:
        for i in range(end - 1, start - 1, -1):
            last = _insert(i, pts[i][0], pts[i][1], last)
    if last is not None and _equals(last, last.next):
        _remove(last)
        last = last.next
    return last


def _signed_area(pts, start, end):
    s = 0.0
    j = end - 1
    for i in range(start, end):
        s += (pts[j][0] - pts[i][0]) * (pts[i][1] + pts[j][1])
        j = i
    return s


def _filter_points(start, end=None):
    if start is None:
        return start
    if end is None:
        end = start
    p = start
    while True:
        again = False
        if not p.steiner and (_equals(p, p.next) or _area(p.prev, p, p.next) == 0):
            _remove(p)
            p = end = p.prev
            if p is p.next:
                break
            again = True
        else:
            p = p.next
        if not (again or p is not end):
            break
    return end


def _earcut_linked(ear, triangles, min_x, min_y, inv, passno):
    if ear is None:
        return
    if not passno and inv:
        _index_curve(ear, min_x, min_y, inv)
    stop = ear
    while ear.prev is not ear.next:
        prev, nxt = ear.prev, ear.next
        if _is_ear_hashed(ear, min_x, min_y, inv) if inv else _is_ear(ear):
            triangles.append((prev.i, ear.i, nxt.i))
            _remove(ear)
            ear = stop = nxt.next
            continue
        ear = nxt
        if ear is stop:
            if not passno:
                _earcut_linked(_filter_points(ear), triangles, min_x, min_y, inv, 1)
            elif passno == 1:
                ear = _cure_local_intersections(_filter_points(ear), triangles)
                _earcut_linked(ear, triangles, min_x, min_y, inv, 2)
            elif passno == 2:
                _split_earcut(ear, triangles, min_x, min_y, inv)
            break


def _is_ear(ear):
    a, b, c = ear.prev, ear, ear.next
    if _area(a, b, c) >= 0:
        return False
    x0, x1 = min(a.x, b.x, c.x), max(a.x, b.x, c.x)
    y0, y1 = min(a.y, b.y, c.y), max(a.y, b.y, c.y)
    p = c.next
    while p is not a:
        if (
            x0 <= p.x <= x1
            and y0 <= p.y <= y1
            and _in_tri(a.x, a.y, b.x, b.y, c.x, c.y, p.x, p.y)
            and _area(p.prev, p, p.next) >= 0
        ):
            return False
        p = p.next
    return True


def _is_ear_hashed(ear, min_x, min_y, inv):
    a, b, c = ear.prev, ear, ear.next
    if _area(a, b, c) >= 0:
        return False
    x0, x1 = min(a.x, b.x, c.x), max(a.x, b.x, c.x)
    y0, y1 = min(a.y, b.y, c.y), max(a.y, b.y, c.y)
    min_z = _z_order(x0, y0, min_x, min_y, inv)
    max_z = _z_order(x1, y1, min_x, min_y, inv)

    def hit(q):
        return (
            q is not a
            and q is not c
            and x0 <= q.x <= x1
            and y0 <= q.y <= y1
            and _in_tri(a.x, a.y, b.x, b.y, c.x, c.y, q.x, q.y)
            and _area(q.prev, q, q.next) >= 0
        )

    p, n = ear.prev_z, ear.next_z
    while p is not None and p.z >= min_z and n is not None and n.z <= max_z:
        if hit(p):
            return False
        p = p.prev_z
        if hit(n):
            return False
        n = n.next_z
    while p is not None and p.z >= min_z:
        if hit(p):
            return False
        p = p.prev_z
    while n is not None and n.z <= max_z:
        if hit(n):
            return False
        n = n.next_z
    return True


def _cure_local_intersections(start, triangles):
    p = start
    while True:
        a, b = p.prev, p.next.next
        if (
            not _equals(a, b)
            and _intersects(a, p, p.next, b)
            and _locally_inside(a, b)
            and _locally_inside(b, a)
        ):
            triangles.append((a.i, p.i, b.i))
            _remove(p)
            _remove(p.next)
            p = start = b
        p = p.next
        if p is start:
            break
    return _filter_points(p)


def _split_earcut(start, triangles, min_x, min_y, inv):
    a = start
    while True:
        b = a.next.next
        while b is not a.prev:
            if a.i != b.i and _valid_diagonal(a, b):
                c = _split_polygon(a, b)
                a = _filter_points(a, a.next)
                c = _filter_points(c, c.next)
                _earcut_linked(a, triangles, min_x, min_y, inv, 0)
                _earcut_linked(c, triangles, min_x, min_y, inv, 0)
                return
            b = b.next
        a = a.next
        if a is start:
            break


def _eliminate_holes(pts, starts, outer):
    queue = []
    for k, s in enumerate(starts):
        e = starts[k + 1] if k < len(starts) - 1 else len(pts)
        lst = _linked_list(pts, s, e, False)
        if lst is None:
            continue
        if lst is lst.next:
            lst.steiner = True
        queue.append(_leftmost(lst))
    queue.sort(key=lambda n: n.x)
    for hole in queue:
        outer = _eliminate_hole(hole, outer)
    return outer


def _eliminate_hole(hole, outer):
    bridge = _find_hole_bridge(hole, outer)
    if bridge is None:
        return outer
    reverse = _split_polygon(bridge, hole)
    _filter_points(reverse, reverse.next)
    return _filter_points(bridge, bridge.next)


def _find_hole_bridge(hole, outer):
    p = outer
    hx, hy = hole.x, hole.y
    qx = float('-inf')
    m = None
    while True:
        if hy <= p.y and hy >= p.next.y and p.next.y != p.y:
            x = p.x + (hy - p.y) * (p.next.x - p.x) / (p.next.y - p.y)
            if hx >= x > qx:
                qx = x
                m = p if p.x < p.next.x else p.next
                if x == hx:
                    return m
        p = p.next
        if p is outer:
            break
    if m is None:
        return None
    stop = m
    mx, my = m.x, m.y
    tan_min = float('inf')
    p = m
    while True:
        if (
            hx >= p.x >= mx
            and hx != p.x
            and _in_tri(hx if hy < my else qx, hy, mx, my, qx if hy < my else hx, hy, p.x, p.y)
        ):
            tan = abs(hy - p.y) / (hx - p.x)
            if _locally_inside(p, hole) and (
                tan < tan_min
                or (tan == tan_min and (p.x > m.x or (p.x == m.x and _sector_contains(m, p))))
            ):
                m = p
                tan_min = tan
        p = p.next
        if p is stop:
            break
    return m


def _sector_contains(m, p):
    return _area(m.prev, m, p.prev) < 0 and _area(p.next, m, m.next) < 0


def _index_curve(start, min_x, min_y, inv):
    p = start
    while True:
        if p.z == 0:
            p.z = _z_order(p.x, p.y, min_x, min_y, inv)
        p.prev_z, p.next_z = p.prev, p.next
        p = p.next
        if p is start:
            break
    p.prev_z.next_z = None
    p.prev_z = None
    _sort_linked(p)


def _sort_linked(lst):
    in_size = 1
    while True:
        p = lst
        lst = tail = None
        merges = 0
        while p is not None:
            merges += 1
            q = p
            p_size = 0
            for _ in range(in_size):
                p_size += 1
                q = q.next_z
                if q is None:
                    break
            q_size = in_size
            while p_size > 0 or (q_size > 0 and q is not None):
                if p_size != 0 and (q_size == 0 or q is None or p.z <= q.z):
                    e, p = p, p.next_z
                    p_size -= 1
                else:
                    e, q = q, q.next_z
                    q_size -= 1
                if tail is not None:
                    tail.next_z = e
                else:
                    lst = e
                e.prev_z = tail
                tail = e
            p = q
        tail.next_z = None
        in_size *= 2
        if merges <= 1:
            return lst


def _z_order(x, y, min_x, min_y, inv):
    x = int((x - min_x) * inv)
    y = int((y - min_y) * inv)
    x = (x | (x << 8)) & 0x00FF00FF
    x = (x | (x << 4)) & 0x0F0F0F0F
    x = (x | (x << 2)) & 0x33333333
    x = (x | (x << 1)) & 0x55555555
    y = (y | (y << 8)) & 0x00FF00FF
    y = (y | (y << 4)) & 0x0F0F0F0F
    y = (y | (y << 2)) & 0x33333333
    y = (y | (y << 1)) & 0x55555555
    return x | (y << 1)


def _leftmost(start):
    p = leftmost = start
    while True:
        if p.x < leftmost.x or (p.x == leftmost.x and p.y < leftmost.y):
            leftmost = p
        p = p.next
        if p is start:
            return leftmost


def _in_tri(ax, ay, bx, by, cx, cy, px, py):
    return (
        (cx - px) * (ay - py) >= (ax - px) * (cy - py)
        and (ax - px) * (by - py) >= (bx - px) * (ay - py)
        and (bx - px) * (cy - py) >= (cx - px) * (by - py)
    )


def _valid_diagonal(a, b):
    return (
        a.next.i != b.i
        and a.prev.i != b.i
        and not _intersects_polygon(a, b)
        and (
            (
                _locally_inside(a, b)
                and _locally_inside(b, a)
                and _middle_inside(a, b)
                and (_area(a.prev, a, b.prev) or _area(a, b.prev, b))
            )
            or (_equals(a, b) and _area(a.prev, a, a.next) > 0 and _area(b.prev, b, b.next) > 0)
        )
    )


def _area(p, q, r):
    return (q.y - p.y) * (r.x - q.x) - (q.x - p.x) * (r.y - q.y)


def _equals(a, b):
    return a.x == b.x and a.y == b.y


def _sign(v):
    return 1 if v > 0 else -1 if v < 0 else 0


def _on_segment(p, q, r):
    return min(p.x, r.x) <= q.x <= max(p.x, r.x) and min(p.y, r.y) <= q.y <= max(p.y, r.y)


def _intersects(p1, q1, p2, q2):
    o1, o2 = _sign(_area(p1, q1, p2)), _sign(_area(p1, q1, q2))
    o3, o4 = _sign(_area(p2, q2, p1)), _sign(_area(p2, q2, q1))
    if o1 != o2 and o3 != o4:
        return True
    return (
        (o1 == 0 and _on_segment(p1, p2, q1))
        or (o2 == 0 and _on_segment(p1, q2, q1))
        or (o3 == 0 and _on_segment(p2, p1, q2))
        or (o4 == 0 and _on_segment(p2, q1, q2))
    )


def _intersects_polygon(a, b):
    p = a
    while True:
        if (
            p.i != a.i
            and p.next.i != a.i
            and p.i != b.i
            and p.next.i != b.i
            and _intersects(p, p.next, a, b)
        ):
            return True
        p = p.next
        if p is a:
            return False


def _locally_inside(a, b):
    if _area(a.prev, a, a.next) < 0:
        return _area(a, b, a.next) >= 0 and _area(a, a.prev, b) >= 0
    return _area(a, b, a.prev) < 0 or _area(a, a.next, b) < 0


def _middle_inside(a, b):
    p = a
    inside = False
    px, py = (a.x + b.x) / 2, (a.y + b.y) / 2
    while True:
        if (
            ((p.y > py) != (p.next.y > py))
            and p.next.y != p.y
            and px < (p.next.x - p.x) * (py - p.y) / (p.next.y - p.y) + p.x
        ):
            inside = not inside
        p = p.next
        if p is a:
            return inside


def _split_polygon(a, b):
    a2, b2 = _Node(a.i, a.x, a.y), _Node(b.i, b.x, b.y)
    an, bp = a.next, b.prev
    a.next, b.prev = b, a
    a2.next, an.prev = an, a2
    b2.next, a2.prev = a2, b2
    bp.next, b2.prev = b2, bp
    return b2


def _insert(i, x, y, last):
    p = _Node(i, x, y)
    if last is None:
        p.prev = p.next = p
    else:
        p.next = last.next
        p.prev = last
        last.next.prev = p
        last.next = p
    return p


def _remove(p):
    p.next.prev = p.prev
    p.prev.next = p.next
    if p.prev_z is not None:
        p.prev_z.next_z = p.next_z
    if p.next_z is not None:
        p.next_z.prev_z = p.prev_z
