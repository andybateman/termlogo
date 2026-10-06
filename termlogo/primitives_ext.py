"""Arrays, property lists, GOTO/TAG, .MAYBEOUTPUT, file streams, keys and the text cursor."""

import atexit
import os
import sys

from . import values as V
from .arrays import LogoArray
from .errors import Goto, LogoError, Output, Stop
from .registry import prim


# ---- arrays ---------------------------------------------------------------
def _origin(origin, who):
    return 1 if origin is None else V.intval(origin, who)


def _size(n, who):
    size = V.intval(n, who)
    if size < 0:
        raise LogoError(f"{who} doesn't like {V.fmt(n)} as input")
    return size


def _array(x, who):
    if not isinstance(x, LogoArray):
        raise LogoError(f"{who} doesn't like {V.fmt(x)} as input")
    return x


def array_slot(arr, n, who):
    """Position in arr.items of Logo index n (which counts from arr.origin)."""
    i = V.intval(n, who) - arr.origin
    if not 0 <= i < len(arr.items):
        raise LogoError(f"{who} doesn't like {V.fmt(n)} as input")
    return i


@prim('array', 1, 1, 2)
def array(it, size, origin=None):
    return LogoArray([[] for _ in range(_size(size, 'array'))], _origin(origin, 'array'))


@prim('mdarray', 1, 1, 2)
def mdarray(it, sizes, origin=None):
    if not isinstance(sizes, list) or not sizes:
        raise LogoError(f"mdarray doesn't like {V.fmt(sizes)} as input")
    dims = [_size(n, 'mdarray') for n in sizes]
    first = _origin(origin, 'mdarray')

    def build(level):
        if level == len(dims) - 1:
            return LogoArray([[] for _ in range(dims[level])], first)
        return LogoArray([build(level + 1) for _ in range(dims[level])], first)

    return build(0)


@prim('listtoarray', 1, 1, 2)
def listtoarray(it, lst, origin=None):
    if not isinstance(lst, list):
        raise LogoError(f"listtoarray doesn't like {V.fmt(lst)} as input")
    return LogoArray(list(lst), _origin(origin, 'listtoarray'))


@prim('arraytolist', 1)
def arraytolist(it, arr):
    return list(_array(arr, 'arraytolist').items)


@prim('arrayp array?', 1)
def arrayp(it, x):
    return V.boolword(isinstance(x, LogoArray))


@prim('setitem', 3)
def setitem(it, n, arr, value):
    arr = _array(arr, 'setitem')
    arr.items[array_slot(arr, n, 'setitem')] = value


def _walk(indexes, arr, who):
    if not isinstance(indexes, list) or not indexes:
        raise LogoError(f"{who} doesn't like {V.fmt(indexes)} as input")
    for n in indexes[:-1]:
        arr = _array(arr.items[array_slot(arr, n, who)], who)
    return arr, array_slot(arr, indexes[-1], who)


@prim('mditem', 2)
def mditem(it, indexes, arr):
    arr, i = _walk(indexes, _array(arr, 'mditem'), 'mditem')
    return arr.items[i]


@prim('mdsetitem', 3)
def mdsetitem(it, indexes, arr, value):
    arr, i = _walk(indexes, _array(arr, 'mdsetitem'), 'mdsetitem')
    arr.items[i] = value


# ---- property lists -------------------------------------------------------
def _name(x, who):
    return V.word(x, who).lower()


@prim('pprop', 3)
def pprop(it, plist, prop, value):
    it.plists.setdefault(_name(plist, 'pprop'), {})[_name(prop, 'pprop')] = value


@prim('gprop', 2)
def gprop(it, plist, prop):
    return it.plists.get(_name(plist, 'gprop'), {}).get(_name(prop, 'gprop'), [])


@prim('remprop', 2)
def remprop(it, plist, prop):
    name = _name(plist, 'remprop')
    props = it.plists.get(name, {})
    props.pop(_name(prop, 'remprop'), None)
    if not props:
        it.plists.pop(name, None)


@prim('plist', 1)
def plist(it, name):
    out = []
    for prop, value in it.plists.get(_name(name, 'plist'), {}).items():
        out += [prop, value]
    return out


@prim('plists', 0)
def plists(it):
    return list(it.plists)


@prim('pps', 0)
def pps(it):
    for name, props in it.plists.items():
        for prop, value in props.items():
            it.write(f'pprop "{name} "{prop} {V.fmt(value)}\n')


@prim('erps', 0)
def erps(it):
    it.plists.clear()


# ---- GOTO, TAG and .MAYBEOUTPUT --------------------------------------------
@prim('goto', 1)
def goto(it, tag):
    raise Goto(V.word(tag, 'goto'))


@prim('tag', 1)
def tag(it, name):
    """A GOTO target. Does nothing when run."""


@prim('.maybeoutput', 1)
def maybeoutput(it, value):
    """Output the value if the input made one; otherwise act like STOP."""
    if value is None:
        raise Stop
    raise Output(value)


# ---- file streams -----------------------------------------------------------
def _open(it, name, mode, who):
    key = V.word(name, who)
    if key in it.streams:
        raise LogoError(f'File {key} is already open')
    try:
        if mode == 'r+' and not os.path.exists(key):
            open(key, 'w').close()
        stream = open(key, mode)
    except OSError as e:
        raise LogoError(f"Can't open {key}: {e.strerror}") from None
    it.streams[key] = stream
    if len(it.streams) == 1:
        atexit.register(_close_all, it)


def _close_all(it):
    for stream in it.streams.values():
        try:
            stream.close()
        except OSError:
            pass
    it.streams.clear()
    it.reader = it.writer = None


def _stream(it, name, who):
    key = V.word(name, who)
    if key not in it.streams:
        raise LogoError(f'{key} is not open')
    return it.streams[key]


def _stream_name(it, stream):
    for key, value in it.streams.items():
        if value is stream:
            return key
    return []


@prim('openread', 1)
def openread(it, name):
    _open(it, name, 'r', 'openread')


@prim('openwrite', 1)
def openwrite(it, name):
    _open(it, name, 'w', 'openwrite')


@prim('openappend', 1)
def openappend(it, name):
    _open(it, name, 'a', 'openappend')


@prim('openupdate', 1)
def openupdate(it, name):
    _open(it, name, 'r+', 'openupdate')


@prim('close', 1)
def close(it, name):
    stream = _stream(it, name, 'close')
    if it.reader is stream:
        it.reader = None
    if it.writer is stream:
        it.writer = None
    stream.close()
    del it.streams[V.word(name)]


@prim('closeall', 0)
def closeall(it):
    _close_all(it)


@prim('allopen', 0)
def allopen(it):
    return list(it.streams)


@prim('setread', 1)
def setread(it, name):
    it.reader = None if name == [] else _stream(it, name, 'setread')


@prim('setwrite', 1)
def setwrite(it, name):
    it.writer = None if name == [] else _stream(it, name, 'setwrite')


@prim('reader', 0)
def reader(it):
    return _stream_name(it, it.reader) if it.reader is not None else []


@prim('writer', 0)
def writer(it):
    return _stream_name(it, it.writer) if it.writer is not None else []


@prim('readpos', 0)
def readpos(it):
    if it.reader is None:
        raise LogoError('No file is chosen for reading')
    return it.reader.tell()


@prim('setreadpos', 1)
def setreadpos(it, pos):
    if it.reader is None:
        raise LogoError('No file is chosen for reading')
    it.reader.seek(V.intval(pos, 'setreadpos'))


@prim('writepos', 0)
def writepos(it):
    if it.writer is None:
        raise LogoError('No file is chosen for writing')
    return it.writer.tell()


@prim('setwritepos', 1)
def setwritepos(it, pos):
    if it.writer is None:
        raise LogoError('No file is chosen for writing')
    it.writer.seek(V.intval(pos, 'setwritepos'))


@prim('eofp eof?', 0)
def eofp(it):
    if it.reader is None:
        return V.FALSE  # a keyboard cannot be peeked
    here = it.reader.tell()
    more = it.reader.read(1)
    it.reader.seek(here)
    return V.boolword(not more)


@prim('filep file?', 1)
def filep(it, name):
    return V.boolword(os.path.isfile(V.word(name, 'filep')))


@prim('erasefile erf', 1)
def erasefile(it, name):
    path = V.word(name, 'erasefile')
    try:
        os.remove(path)
    except OSError as e:
        raise LogoError(f"Can't erase {path}: {e.strerror}") from None


# ---- keys -------------------------------------------------------------------
def _keyboard_char(it):
    ch = it.readchar() if it.readchar is not None else sys.stdin.read(1)
    return ch if ch else []


@prim('readchar rc', 0, 0, 0)
def readchar(it):
    if it.reader is not None:
        return it.reader.read(1) or []
    return _keyboard_char(it)


@prim('readchars rcs', 1)
def readchars(it, n):
    count = _size(n, 'readchars')
    if it.reader is not None:
        return it.reader.read(count) or []
    out = ''
    while len(out) < count:
        ch = _keyboard_char(it)
        if ch == []:
            break
        out += ch
    return out or []


@prim('keyp key?', 0)
def keyp(it):
    if it.reader is not None:
        return V.boolword(eofp(it) == V.FALSE)
    if it.keyp is not None:
        return V.boolword(it.keyp())
    try:
        import select

        return V.boolword(bool(select.select([sys.stdin], [], [], 0)[0]))
    except (ImportError, OSError, ValueError):
        return V.FALSE


# ---- text screen --------------------------------------------------------------
@prim('cursor', 0)
def cursor(it):
    return list(it.cursor_get()) if it.cursor_get is not None else [0, 0]


@prim('setcursor', 1)
def setcursor(it, pos):
    if not (isinstance(pos, list) and len(pos) == 2):
        raise LogoError(f"setcursor doesn't like {V.fmt(pos)} as input")
    col, row = (V.intval(n, 'setcursor') for n in pos)
    if col < 0 or row < 0:
        raise LogoError(f"setcursor doesn't like {V.fmt(pos)} as input")
    if it.cursor_set is not None:
        it.cursor_set(col, row)
