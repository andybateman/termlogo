"""Control structures, variables, procedures, input and output."""

import time

from . import values as V
from .errors import Bye, LogoError, Output, Stop, Throw
from .lexer import tokenize
from .registry import PRIMS, prim


def _list(x, who):
    if not isinstance(x, list):
        raise LogoError(f"{who} doesn't like {V.fmt(x)} as input")
    return x


# ---- control -------------------------------------------------------------
@prim('repeat', 2)
def repeat(it, n, body):
    n = V.intval(n, 'repeat')
    _list(body, 'repeat')
    it.repcounts.append(0)
    try:
        for i in range(1, n + 1):
            it.repcounts[-1] = i
            it.run_list(body)
    finally:
        it.repcounts.pop()


@prim('forever', 1)
def forever(it, body):
    it.repcounts.append(0)
    try:
        while True:
            it.repcounts[-1] += 1
            it.run_list(_list(body, 'forever'))
    finally:
        it.repcounts.pop()


@prim('repcount #', 0)
def repcount(it):
    return it.repcounts[-1] if it.repcounts else -1


@prim('if', 2, 2, 3)
def if_(it, cond, then, other=None):
    if V.truth(_cond(it, cond), 'if'):
        return it.run_list(_list(then, 'if'), True)
    if other is not None:
        return it.run_list(_list(other, 'if'), True)
    return None


@prim('ifelse', 3)
def ifelse(it, cond, a, b):
    branch = a if V.truth(_cond(it, cond), 'ifelse') else b
    return it.run_list(_list(branch, 'ifelse'), True)


def _cond(it, c):
    return it.run_list(c, True) if isinstance(c, list) else c


@prim('test', 1)
def test(it, cond):
    it.scopes[-1]['%test'] = V.truth(_cond(it, cond), 'test')


@prim('iftrue ift', 1)
def iftrue(it, body):
    t = it.scopes[-1].get('%test', it.scopes[0].get('%test'))
    if t is None:
        raise LogoError('IFTRUE without TEST')
    if t:
        return it.run_list(_list(body, 'iftrue'), True)


@prim('iffalse iff', 1)
def iffalse(it, body):
    t = it.scopes[-1].get('%test', it.scopes[0].get('%test'))
    if t is None:
        raise LogoError('IFFALSE without TEST')
    if not t:
        return it.run_list(_list(body, 'iffalse'), True)


@prim('while', 2)
def while_(it, cond, body):
    while V.truth(_cond(it, cond), 'while'):
        it.run_list(_list(body, 'while'))


@prim('until', 2)
def until(it, cond, body):
    while not V.truth(_cond(it, cond), 'until'):
        it.run_list(_list(body, 'until'))


@prim('do.while', 2)
def do_while(it, body, cond):
    while True:
        it.run_list(_list(body, 'do.while'))
        if not V.truth(_cond(it, cond), 'do.while'):
            break


@prim('do.until', 2)
def do_until(it, body, cond):
    while True:
        it.run_list(_list(body, 'do.until'))
        if V.truth(_cond(it, cond), 'do.until'):
            break


@prim('for', 2)
def for_(it, spec, body):
    spec = _list(spec, 'for')
    if len(spec) < 3:
        raise LogoError("for doesn't like " + V.fmt(spec) + ' as input')
    name = V.word(spec[0])
    start = V.num(
        it.run_list(spec[1:2], True) if isinstance(spec[1], list) else _eval_item(it, spec[1]),
        'for',
    )
    limit = V.num(_eval_item(it, spec[2]), 'for')
    step = V.num(_eval_item(it, spec[3]), 'for') if len(spec) > 3 else (1 if limit >= start else -1)
    if step == 0:
        raise LogoError("for doesn't like 0 as step")
    it.scopes.append({name.lower(): start})
    try:
        v = start
        while (v <= limit) if step > 0 else (v >= limit):
            it.scopes[-1][name.lower()] = v
            it.run_list(_list(body, 'for'))
            v += step
    finally:
        it.scopes.pop()


def _eval_item(it, tok):
    if isinstance(tok, list):
        return it.run_list(tok, True)
    return it.run_list([tok], True)


@prim('stop', 0)
def stop(it):
    raise Stop()


@prim('output op', 1)
def output(it, v):
    raise Output(v)


@prim('bye', 0)
def bye(it):
    raise Bye()


@prim('run', 1)
def run(it, x):
    return it.run_list(x, True)


@prim('runresult', 1)
def runresult(it, x):
    v = it.run_list(x, True)
    return [] if v is None else [v]


@prim('wait', 1)
def wait(it, n):
    seconds = max(0, V.num(n, 'wait')) / 60.0
    if it.on_frame:
        it.on_frame()
    if it.on_wait is not None:
        it.on_wait(seconds)
    else:
        time.sleep(seconds)


@prim('catch', 2)
def catch(it, tag, body):
    tag = V.word(tag, 'catch').lower()
    depth, nscopes = it.depth, len(it.scopes)
    try:
        return it.run_list(_list(body, 'catch'), True)
    except Throw as t:
        if t.tag != tag:
            raise
        del it.scopes[nscopes:]
        it.depth = depth
        return t.value
    except LogoError as e:
        if tag != 'error':
            raise
        del it.scopes[nscopes:]
        it.depth = depth
        it.last_error = e
        return None


@prim('throw', 1, 1, 2)
def throw(it, tag, value=None):
    raise Throw(V.word(tag, 'throw').lower(), value)


@prim('error', 0)
def error(it):
    e = getattr(it, 'last_error', None)
    it.last_error = None
    if e is None:
        return []
    return [0, e.message, 'logo', 'toplevel']


# ---- variables and procedures -------------------------------------------
@prim('make', 2)
def make(it, name, value):
    it.set_var(V.word(name, 'make'), value)


@prim('name', 2)
def name_(it, value, name):
    it.set_var(V.word(name, 'name'), value)


@prim('thing', 1)
def thing(it, name):
    return it.lookup(V.word(name, 'thing'))


@prim('local', 1, 1, -1)
def local(it, *names):
    for n in names:
        for x in n if isinstance(n, list) else [n]:
            it.declare_local(V.word(x, 'local'))


@prim('localmake', 2)
def localmake(it, name, value):
    it.scopes[-1][V.word(name, 'localmake').lower()] = value


@prim('global', 1, 1, -1)
def global_(it, *names):
    for n in names:
        for x in n if isinstance(n, list) else [n]:
            it.scopes[0].setdefault(V.word(x, 'global').lower(), None)


@prim('namep name?', 1)
def namep(it, name):
    try:
        it.lookup(V.word(name, 'namep'))
        return V.boolword(True)
    except LogoError:
        return V.boolword(False)


@prim('procedurep procedure? definedp defined?', 1)
def procedurep(it, name):
    return V.boolword(V.word(name, 'procedurep').lower() in it.procs)


@prim('primitivep primitive?', 1)
def primitivep(it, name):
    return V.boolword(V.word(name, 'primitivep').lower() in PRIMS)


@prim('erase er', 1)
def erase(it, what):
    names = what if isinstance(what, list) else [what]
    for n in names:
        it.procs.pop(V.word(n, 'erase').lower(), None)


@prim('erall', 0)
def erall(it):
    it.procs.clear()
    it.scopes[0].clear()


@prim('define', 2)
def define(it, name, body):
    from .interp import Procedure

    if not (isinstance(body, list) and body and all(isinstance(line, list) for line in body)):
        raise LogoError("define doesn't like " + V.fmt(body) + ' as input')
    params = [V.word(p).lstrip(':').lower() for p in body[0]]
    toks = []
    for line in body[1:]:
        toks.extend(line)
    it.procs[V.word(name).lower()] = Procedure(V.word(name).lower(), params, toks)


@prim('text', 1)
def text(it, name):
    p = it.procs.get(V.word(name, 'text').lower())
    if p is None:
        raise LogoError(f"I don't know how to {V.fmt(name)}")
    return [[':' + n for n in p.params], p.body]


@prim('pots', 0)
def pots(it):
    for p in it.procs.values():
        it.write('to ' + p.name + ''.join(' :' + x for x in p.params) + '\n')


@prim('pons', 0)
def pons(it):
    for k, v in it.scopes[0].items():
        if not k.startswith('%'):
            it.write(f'make "{k} {V.fmt(v)}\n')


# ---- template iteration ---------------------------------------------------
@prim('foreach', 2)
def foreach(it, data, tpl):
    items = list(data) if isinstance(data, list) else list(V.fmt(data))
    for i, x in enumerate(items, 1):
        it.repcounts.append(i)
        try:
            it.apply_template(tpl, [x])
        finally:
            it.repcounts.pop()


@prim('map', 2)
def map_(it, tpl, data):
    items = list(data) if isinstance(data, list) else list(V.fmt(data))
    return [it.apply_template(tpl, [x]) for x in items]


@prim('filter', 2)
def filter_(it, tpl, data):
    items = list(data) if isinstance(data, list) else list(V.fmt(data))
    return [x for x in items if V.truth(it.apply_template(tpl, [x]), 'filter')]


@prim('find', 2)
def find(it, tpl, data):
    for x in data if isinstance(data, list) else list(V.fmt(data)):
        if V.truth(it.apply_template(tpl, [x]), 'find'):
            return x
    return []


@prim('reduce', 2)
def reduce_(it, tpl, data):
    items = list(data) if isinstance(data, list) else list(V.fmt(data))
    if not items:
        raise LogoError("reduce doesn't like [] as input")
    acc = items[0]
    for x in items[1:]:
        acc = it.apply_template(tpl, [acc, x])
    return acc


@prim('apply', 2)
def apply_(it, tpl, args):
    return it.apply_template(tpl, _list(args, 'apply'))


@prim('invoke', 2, 2, -1)
def invoke(it, tpl, *args):
    return it.apply_template(tpl, list(args))


# ---- input and output -----------------------------------------------------
@prim('print pr', 1, 1, -1)
def print_(it, *args):
    it.write(' '.join(V.fmt(a, top=True) for a in args) + '\n')


@prim('type', 1, 1, -1)
def type_(it, *args):
    it.write(''.join(V.fmt(a, top=True) for a in args))


@prim('show', 1, 1, -1)
def show(it, *args):
    it.write(' '.join(V.fmt(a) for a in args) + '\n')


@prim('readword rw', 0, 0, 0)
def readword(it):
    try:
        return it.readline('')
    except EOFError:
        return []


@prim('readlist rl', 0, 0, 0)
def readlist(it):
    try:
        return tokenize(it.readline(''))
    except EOFError:
        return []


@prim('cleartext ct', 0)
def cleartext(it):
    it.write('\x1b[2J\x1b[H' if getattr(it, 'ansi_text', False) else '')


# ---- workspace files ------------------------------------------------------
def _src(tok):
    if isinstance(tok, list):
        return '[' + ' '.join(_src(t) for t in tok) + ']'
    return str(tok)


def procedure_source(p):
    head = 'to ' + p.name
    for n in p.params:
        if n in p.defaults:
            head += ' [:' + n + ' ' + ' '.join(_src(t) for t in p.defaults[n]) + ']'
        else:
            head += ' :' + n
    if p.rest:
        head += ' [:' + p.rest + ']'
    body = ' '.join(_src(t) for t in p.body)
    return head + '\n  ' + body + '\nend\n'


@prim('po', 1)
def po(it, what):
    for n in what if isinstance(what, list) else [what]:
        p = it.procs.get(V.word(n, 'po').lower())
        if p is None:
            raise LogoError(f"I don't know how to {V.fmt(n)}")
        it.write(procedure_source(p))


@prim('load', 1)
def load(it, name):
    path = V.word(name, 'load')
    try:
        with open(path) as f:
            text = f.read()
    except OSError as e:
        raise LogoError(f"Can't open {path}: {e.strerror}") from e
    it.eval_source(text)


@prim('save', 1)
def save(it, name):
    """Write all procedures (and global variables) to a file that LOAD can read back."""
    path = V.word(name, 'save')
    try:
        with open(path, 'w') as f:
            for p in it.procs.values():
                f.write(procedure_source(p) + '\n')
            for k, v in it.scopes[0].items():
                if not k.startswith('%') and v is not None:
                    f.write(f'make "{k} {_src(v) if isinstance(v, list) else V.fmt(v)}\n')
    except OSError as e:
        raise LogoError(f"Can't write {path}: {e.strerror}") from e


# ---- help and version -----------------------------------------------------
@prim('help', 1, 0, 1, raw=True)
def help_(it, what=None):
    """HELP, HELP "name, HELP fd, HELP "turtle"""
    import shutil

    from . import helptext

    width = max(40, min(100, shutil.get_terminal_size((80, 24)).columns - 2))
    text = helptext.lookup('' if what is None else V.word(what, 'help'), width)
    if text is None:
        raise LogoError(f'No help for {V.fmt(what)}. Try HELP for the full list')
    it.write(text + '\n')


@prim('version', 0)
def version(it):
    from . import __author__, __version__

    return f'termlogo {__version__} by {__author__}'
