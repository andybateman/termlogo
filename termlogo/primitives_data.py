"""Words, lists, arithmetic, logic and comparison."""

import math
import random

from . import values as V
from .arrays import LogoArray
from .errors import LogoError
from .registry import prim


def _items(x, who, arrays=False):
    if isinstance(x, list):
        return x
    if arrays and isinstance(x, LogoArray):
        return x.items
    if isinstance(x, (int, float)):
        x = V.fmt(x)
    if isinstance(x, str):
        return list(x)
    raise LogoError(f"{who} doesn't like {V.fmt(x)} as input")


def _same_kind(orig, items):
    return items if isinstance(orig, list) else ''.join(items)


# ---- constructors ---------------------------------------------------------
@prim('word', 2, 0, -1)
def word(it, *args):
    return ''.join(V.word(a, 'word') for a in args)


@prim('list', 2, 0, -1)
def list_(it, *args):
    return list(args)


@prim('sentence se', 2, 0, -1)
def sentence(it, *args):
    out = []
    for a in args:
        out.extend(a if isinstance(a, list) else [a])
    return out


@prim('fput', 2)
def fput(it, x, lst):
    if isinstance(lst, list):
        return [x] + lst
    return V.word(x, 'fput') + V.word(lst, 'fput')


@prim('lput', 2)
def lput(it, x, lst):
    if isinstance(lst, list):
        return lst + [x]
    return V.word(lst, 'lput') + V.word(x, 'lput')


@prim('combine', 2)
def combine(it, a, b):
    if isinstance(b, list):
        return [a] + b
    return V.word(a, 'combine') + V.word(b, 'combine')


@prim('reverse', 1)
def reverse(it, x):
    return _same_kind(x, list(reversed(_items(x, 'reverse'))))


@prim('remove', 2)
def remove(it, x, lst):
    return _same_kind(lst, [i for i in _items(lst, 'remove') if not V.equal(i, x)])


@prim('remdup', 1)
def remdup(it, lst):
    out = []
    for i in _items(lst, 'remdup'):
        if not any(V.equal(i, o) for o in out):
            out.append(i)
    return _same_kind(lst, out)


@prim('iseq', 2)
def iseq(it, a, b):
    a, b = V.intval(a, 'iseq'), V.intval(b, 'iseq')
    return list(range(a, b + 1)) if a <= b else list(range(a, b - 1, -1))


@prim('rseq', 3)
def rseq(it, a, b, n):
    a, b, n = V.num(a, 'rseq'), V.num(b, 'rseq'), V.intval(n, 'rseq')
    if n == 1:
        return [a]
    return [a + (b - a) * i / (n - 1) for i in range(n)]


# ---- selectors ------------------------------------------------------------
@prim('first', 1)
def first(it, x):
    s = _items(x, 'first', True)
    if not s:
        raise LogoError(f"first doesn't like {V.fmt(x)} as input")
    return s[0]


@prim('last', 1)
def last(it, x):
    s = _items(x, 'last', True)
    if not s:
        raise LogoError(f"last doesn't like {V.fmt(x)} as input")
    return s[-1]


@prim('butfirst bf', 1)
def butfirst(it, x):
    s = _items(x, 'butfirst')
    if not s:
        raise LogoError(f"butfirst doesn't like {V.fmt(x)} as input")
    return _same_kind(x, s[1:])


@prim('butlast bl', 1)
def butlast(it, x):
    s = _items(x, 'butlast')
    if not s:
        raise LogoError(f"butlast doesn't like {V.fmt(x)} as input")
    return _same_kind(x, s[:-1])


@prim('item', 2)
def item(it, n, x):
    s = _items(x, 'item', True)
    i = V.intval(n, 'item') - (x.origin if isinstance(x, LogoArray) else 1)
    if not 0 <= i < len(s):
        raise LogoError(f"item doesn't like {V.fmt(n)} as input")
    return s[i]


@prim('pick', 1)
def pick(it, x):
    s = _items(x, 'pick', True)
    if not s:
        raise LogoError("pick doesn't like [] as input")
    return random.choice(s)


@prim('count', 1)
def count(it, x):
    return len(_items(x, 'count', True))


@prim('member', 2)
def member(it, x, lst):
    s = _items(lst, 'member')
    for i, v in enumerate(s):
        if V.equal(x, v):
            return _same_kind(lst, s[i:])
    return [] if isinstance(lst, list) else ''


@prim('memberp member?', 2)
def memberp(it, x, lst):
    return V.boolword(any(V.equal(x, v) for v in _items(lst, 'memberp', True)))


@prim('emptyp empty?', 1)
def emptyp(it, x):
    return V.boolword(x == [] or x == '')


@prim('listp list?', 1)
def listp(it, x):
    return V.boolword(isinstance(x, list))


@prim('wordp word?', 1)
def wordp(it, x):
    return V.boolword(not isinstance(x, (list, LogoArray)))


@prim('numberp number?', 1)
def numberp(it, x):
    return V.boolword(V.is_num(x))


@prim('equalp equal?', 2)
def equalp(it, a, b):
    return V.boolword(V.equal(a, b))


@prim('notequalp notequal?', 2)
def notequalp(it, a, b):
    return V.boolword(not V.equal(a, b))


@prim('beforep before?', 2)
def beforep(it, a, b):
    return V.boolword(V.fmt(a).lower() < V.fmt(b).lower())


@prim('uppercase', 1)
def uppercase(it, x):
    return V.word(x, 'uppercase').upper()


@prim('lowercase', 1)
def lowercase(it, x):
    return V.word(x, 'lowercase').lower()


@prim('char', 1)
def char(it, n):
    return chr(V.intval(n, 'char'))


@prim('ascii', 1)
def ascii_(it, c):
    w = V.word(c, 'ascii')
    if len(w) != 1:
        raise LogoError(f"ascii doesn't like {w} as input")
    return ord(w)


# ---- logic ----------------------------------------------------------------
@prim('and', 2, 1, -1)
def and_(it, *args):
    return V.boolword(
        all(V.truth(it.run_list(a, True) if isinstance(a, list) else a, 'and') for a in args)
    )


@prim('or', 2, 1, -1)
def or_(it, *args):
    return V.boolword(
        any(V.truth(it.run_list(a, True) if isinstance(a, list) else a, 'or') for a in args)
    )


@prim('not', 1)
def not_(it, x):
    return V.boolword(not V.truth(it.run_list(x, True) if isinstance(x, list) else x, 'not'))


# ---- arithmetic -----------------------------------------------------------
def _n(x, who):
    return V.num(x, who)


@prim('sum', 2, 0, -1)
def sum_(it, *args):
    return sum((_n(a, 'sum') for a in args), 0)


@prim('difference', 2)
def difference(it, a, b):
    return _n(a, 'difference') - _n(b, 'difference')


@prim('product', 2, 0, -1)
def product(it, *args):
    r = 1
    for a in args:
        r *= _n(a, 'product')
    return r


@prim('quotient', 2, 1, 2)
def quotient(it, a, b=None):
    if b is None:
        a, b = 1, a
    a, b = _n(a, 'quotient'), _n(b, 'quotient')
    if b == 0:
        raise LogoError("Can't divide by zero")
    r = a / b
    return int(r) if r == int(r) and isinstance(a, int) and isinstance(b, int) else r


@prim('remainder', 2)
def remainder(it, a, b):
    a, b = _n(a, 'remainder'), _n(b, 'remainder')
    if b == 0:
        raise LogoError("Can't divide by zero")
    return math.fmod(a, b) if isinstance(a, float) or isinstance(b, float) else int(math.fmod(a, b))


@prim('modulo', 2)
def modulo(it, a, b):
    a, b = _n(a, 'modulo'), _n(b, 'modulo')
    if b == 0:
        raise LogoError("Can't divide by zero")
    return a % b


@prim('intquotient', 2)
def intquotient(it, a, b):
    b = V.intval(b, 'intquotient')
    if b == 0:
        raise LogoError("Can't divide by zero")
    return int(V.intval(a, 'intquotient') / b)


@prim('minus', 1)
def minus(it, a):
    return -_n(a, 'minus')


@prim('abs', 1)
def abs_(it, a):
    return abs(_n(a, 'abs'))


@prim('int', 1)
def int_(it, a):
    return int(_n(a, 'int'))


@prim('round', 1)
def round_(it, a):
    x = _n(a, 'round')
    return int(math.floor(x + 0.5))


@prim('sqrt', 1)
def sqrt(it, a):
    x = _n(a, 'sqrt')
    if x < 0:
        raise LogoError(f"sqrt doesn't like {V.fmt(a)} as input")
    r = math.sqrt(x)
    return int(r) if r == int(r) else r


@prim('power', 2)
def power(it, a, b):
    return _n(a, 'power') ** _n(b, 'power')


@prim('exp', 1)
def exp(it, a):
    return math.exp(_n(a, 'exp'))


@prim('ln', 1)
def ln(it, a):
    x = _n(a, 'ln')
    if x <= 0:
        raise LogoError(f"ln doesn't like {V.fmt(a)} as input")
    return math.log(x)


@prim('log10', 1)
def log10(it, a):
    x = _n(a, 'log10')
    if x <= 0:
        raise LogoError(f"log10 doesn't like {V.fmt(a)} as input")
    return math.log10(x)


@prim('pi', 0)
def pi(it):
    return math.pi


@prim('sin', 1)
def sin(it, a):
    return _clean(math.sin(math.radians(_n(a, 'sin'))))


@prim('cos', 1)
def cos(it, a):
    return _clean(math.cos(math.radians(_n(a, 'cos'))))


@prim('tan', 1)
def tan(it, a):
    return math.tan(math.radians(_n(a, 'tan')))


@prim('arctan', 1, 1, 2)
def arctan(it, a, b=None):
    if b is None:
        return math.degrees(math.atan(_n(a, 'arctan')))
    return math.degrees(math.atan2(_n(b, 'arctan'), _n(a, 'arctan')))


@prim('arcsin', 1)
def arcsin(it, a):
    return math.degrees(math.asin(_n(a, 'arcsin')))


@prim('arccos', 1)
def arccos(it, a):
    return math.degrees(math.acos(_n(a, 'arccos')))


def _clean(x):
    return 0 if abs(x) < 1e-15 else x


@prim('random', 1, 1, 2)
def random_(it, a, b=None):
    if b is None:
        n = V.intval(a, 'random')
        if n <= 0:
            raise LogoError(f"random doesn't like {n} as input")
        if it.turtle is not None and it.turtle.colour_mode == 'terrapin':
            return random.randint(1, n)
        return random.randrange(n)
    lo, hi = V.intval(a, 'random'), V.intval(b, 'random')
    return random.randint(lo, hi)


@prim('rerandom', 0, 0, 1)
def rerandom(it, seed=0):
    random.seed(V.num(seed, 'rerandom'))


@prim('lessp less?', 2)
def lessp(it, a, b):
    return V.boolword(_n(a, 'lessp') < _n(b, 'lessp'))


@prim('greaterp greater?', 2)
def greaterp(it, a, b):
    return V.boolword(_n(a, 'greaterp') > _n(b, 'greaterp'))


@prim('lessequalp lessequal?', 2)
def lessequalp(it, a, b):
    return V.boolword(_n(a, 'lessequalp') <= _n(b, 'lessequalp'))


@prim('greaterequalp greaterequal?', 2)
def greaterequalp(it, a, b):
    return V.boolword(_n(a, 'greaterequalp') >= _n(b, 'greaterequalp'))


@prim('bitand', 2, 0, -1)
def bitand(it, *args):
    r = -1
    for a in args:
        r &= V.intval(a, 'bitand')
    return r


@prim('bitor', 2, 0, -1)
def bitor(it, *args):
    r = 0
    for a in args:
        r |= V.intval(a, 'bitor')
    return r


@prim('bitxor', 2, 0, -1)
def bitxor(it, *args):
    r = 0
    for a in args:
        r ^= V.intval(a, 'bitxor')
    return r


@prim('ashift', 2)
def ashift(it, a, b):
    a, b = V.intval(a, 'ashift'), V.intval(b, 'ashift')
    return a << b if b >= 0 else a >> -b
