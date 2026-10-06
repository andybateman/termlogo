"""Primitive registry. `@prim("name", nargs)` registers a function.

The function receives (interp, *args). `max_args=-1` means variadic in parentheses.
`raw=True` lets a bare word follow the name unevaluated (used by HELP).
"""

PRIMS = {}


class Prim:
    __slots__ = ('name', 'fn', 'default', 'min', 'max', 'raw')

    def __init__(self, name, fn, default, min_args, max_args, raw=False):
        self.name, self.fn, self.default = name, fn, default
        self.raw = raw
        self.min, self.max = min_args, max_args


def prim(names, default, min_args=None, max_args=None, raw=False):
    names = names.split()

    def deco(fn):
        lo = default if min_args is None else min_args
        hi = default if max_args is None else max_args
        for n in names:
            PRIMS[n] = Prim(names[0], fn, default, lo, hi, raw)
        return fn

    return deco
