"""The Logo evaluator: procedures, scopes, expression parsing and control flow."""

import sys

from . import values as V
from .arrays import LogoArray
from .errors import Goto, Incomplete, LogoError, Output, Stop, Throw
from .lexer import INFIX, is_number_token, to_number, tokenize
from .registry import PRIMS

UNSET = object()
MAX_DEPTH = 25000


class Procedure:
    def __init__(self, name, params, body, defaults=None, rest=None, min_args=None):
        self.name, self.params, self.body = name, params, body
        self.defaults = defaults or {}
        self.rest = rest
        self.min = len(params) if min_args is None else min_args
        self.default = self.min  # without parentheses, only required inputs
        self.max = -1 if rest else len(params)


class TailCall:
    """A user-procedure call in tail position, run by call_user's loop instead of
    nesting. `command` is True when the call stood as a statement, so the callee
    must not output a value."""

    __slots__ = ('proc', 'args', 'command')

    def __init__(self, proc, args, command):
        self.proc, self.args, self.command = proc, args, command


class Cursor:
    __slots__ = ('toks', 'i')

    def __init__(self, toks):
        self.toks, self.i = toks, 0

    def done(self):
        return self.i >= len(self.toks)

    def peek(self, offset=0):
        index = self.i + offset
        return self.toks[index] if 0 <= index < len(self.toks) else None

    def next(self):
        t = self.toks[self.i]
        self.i += 1
        return t


class Interp:
    def __init__(self, out=None, readline=None):
        # Importing here registers the primitives.
        from . import primitives_core, primitives_data, primitives_ext  # noqa: F401

        self.out = out or sys.stdout.write
        self.readline = readline or (lambda prompt='': input(prompt))
        self.procs = {}
        self.scopes = [{}]
        self.repcounts = []
        self.slots = []
        self.depth = 0
        self.turtle = None  # set by attach_turtle
        self.on_frame = None  # called by WAIT so a front end can redraw
        self.on_start = None
        self.on_poll = None
        self.on_wait = None
        self.plists = {}  # property lists: name -> {property: value}
        self.streams = {}  # open files by name: name -> file object
        self.reader = self.writer = None  # current SETREAD / SETWRITE streams
        # Terminal front ends fill these in; the defaults suit plain stdin/stdout.
        self.readchar = self.keyp = None
        self.cursor_get = self.cursor_set = self.text_clear = None
        sys.setrecursionlimit(max(sys.getrecursionlimit(), 400000))

    # ---- variables -------------------------------------------------------
    def lookup(self, name):
        name = name.lower()
        for s in reversed(self.scopes):
            if name in s:
                v = s[name]
                if v is UNSET:
                    break
                return v
        raise LogoError(f'{name} has no value')

    def set_var(self, name, value):
        name = name.lower()
        for s in reversed(self.scopes):
            if name in s:
                s[name] = value
                return
        self.scopes[0][name] = value

    def declare_local(self, name):
        self.scopes[-1][name.lower()] = UNSET

    # ---- running source --------------------------------------------------
    def eval_source(self, text):
        """Run program text: handles TO ... END definitions, then instructions."""
        toks = tokenize(text)
        rest = self._extract_defs(toks)
        if toks and self.on_start is not None:
            self.on_start()
        self.run_tokens(rest)

    def _extract_defs(self, toks):
        out, i = [], 0
        while i < len(toks):
            t = toks[i]
            if isinstance(t, str) and t.lower() == 'to':
                i = self._define(toks, i + 1)
            else:
                out.append(t)
                i += 1
        return out

    def _define(self, toks, i):
        if i >= len(toks) or not isinstance(toks[i], str):
            raise LogoError('TO needs a procedure name')
        name = toks[i].lower()
        i += 1
        params, defaults, rest, min_args = [], {}, None, None
        while i < len(toks):
            t = toks[i]
            if isinstance(t, str) and t.startswith(':'):
                params.append(t[1:].lower())
            elif isinstance(t, list) and t and isinstance(t[0], str) and t[0].startswith(':'):
                if len(t) == 1:
                    rest = t[0][1:].lower()  # [:rest]
                else:
                    if min_args is None:
                        min_args = len(params)
                    params.append(t[0][1:].lower())
                    defaults[params[-1]] = t[1:]
            else:
                break
            i += 1
        body = []
        while i < len(toks):
            t = toks[i]
            if isinstance(t, str) and t.lower() == 'end':
                if name in PRIMS and name not in self.procs:
                    raise LogoError(f'{name} is a primitive')
                p = Procedure(name, params, body, defaults, rest, min_args)
                self.procs[name] = p
                return i + 1
            body.append(t)
            i += 1
        raise Incomplete()

    def run_tokens(self, toks):
        report_values = self.turtle is not None and self.turtle.colour_mode == 'terrapin'
        self.run_statements(toks, False, report_values=report_values)

    def run_statements(self, toks, tail=False, report_values=False):
        """Run instructions. With tail=True the last statement may come back as a
        TailCall for call_user to run in its loop."""
        cur = Cursor(toks)
        if self.on_poll is not None:
            self.on_poll()
        while not cur.done():
            v = self.statement(cur, tail)
            if isinstance(v, TailCall):
                return v
            if v is not None:
                if report_values:
                    self.write(V.fmt(v) + '\n')
                else:
                    raise LogoError(f"You don't say what to do with {V.fmt(v)}")
        return None

    def statement(self, cur, tail):
        """One instruction. In tail position, spots a final user-procedure call,
        `output call ...`, or an `if`/`ifelse` whose branch may end in one."""
        t = cur.peek()
        if (
            not tail
            or not isinstance(t, str)
            or t[0] in '"(:?-'
            or t in INFIX
            or is_number_token(t)
        ):
            return self.expr(cur)
        name = t.lower()
        p = self.procs.get(name)
        if isinstance(p, Procedure):
            cur.next()
            args = self.collect_args(p, name, cur)
            if cur.done():
                return TailCall(p, args, True)
            return self.expr_rest(cur, self.call(name, args))
        if name in ('output', 'op') and name not in self.procs:
            i = cur.i
            cur.next()
            nxt = cur.peek()
            q = self.procs.get(nxt.lower()) if isinstance(nxt, str) else None
            if isinstance(q, Procedure):
                cur.next()
                args = self.collect_args(q, nxt.lower(), cur)
                if cur.done():
                    return TailCall(q, args, False)
                raise Output(self.expr_rest(cur, self.call(nxt.lower(), args)))
            cur.i = i
            return self.expr(cur)
        if name in ('if', 'ifelse') and name not in self.procs:
            cur.next()
            prim = PRIMS[name]
            nargs = 2 if name == 'if' else 3
            args = []
            for _ in range(nargs):
                if cur.done():
                    raise LogoError(f'Not enough inputs to {name}')
                args.append(self.expr(cur))
            if cur.done() and all(isinstance(a, list) for a in args[1:]):
                c = args[0]
                if isinstance(c, list):
                    c = self.run_list(c, True)
                branch = args[1] if V.truth(c, name) else (args[2] if name == 'ifelse' else None)
                return self.run_statements(branch, True) if branch is not None else None
            return self.expr_rest(cur, prim.fn(self, *args))
        return self.expr(cur)

    def run_list(self, toks, want_value=False):
        """RUN semantics: a list may end in an expression whose value is returned."""
        if not isinstance(toks, list):
            toks = tokenize(V.word(toks, 'run'))
        cur = Cursor(toks)
        if self.on_poll is not None:
            self.on_poll()
        last = None
        while not cur.done():
            last = self.expr(cur)
            if last is not None and not cur.done():
                raise LogoError(f"You don't say what to do with {V.fmt(last)}")
        return last if want_value else None

    # ---- expression parsing ----------------------------------------------
    def expr(self, cur, minprec=1):
        if self.on_poll is not None:
            self.on_poll()
        return self.expr_rest(cur, self.primary(cur), minprec)

    def expr_rest(self, cur, left, minprec=1):
        while True:
            t = cur.peek()
            if not isinstance(t, str) or t not in INFIX:
                return left
            prec = INFIX[t]
            if prec < minprec:
                return left
            cur.next()
            right = self.expr(cur, prec + 1 if t != '^' else prec)
            left = self.infix(t, left, right)

    def infix(self, op, a, b):
        if op == '=':
            return V.boolword(V.equal(a, b))
        if op == '<>':
            return V.boolword(not V.equal(a, b))
        x, y = V.num(a, op), V.num(b, op)
        if op == '+':
            return x + y
        if op == '-':
            return x - y
        if op == '*':
            return x * y
        if op == '/':
            if y == 0:
                raise LogoError("Can't divide by zero")
            r = x / y
            return int(r) if r == int(r) and isinstance(x, int) and isinstance(y, int) else r
        if op == '^':
            return x**y
        if op == '<':
            return V.boolword(x < y)
        if op == '>':
            return V.boolword(x > y)
        if op == '<=':
            return V.boolword(x <= y)
        return V.boolword(x >= y)

    def primary(self, cur):
        if cur.done():
            raise LogoError('Not enough inputs')
        t = cur.next()
        if isinstance(t, (list, LogoArray)):
            return t
        if t == 'u-':
            return -V.num(self.primary(cur), '-')
        if t == '(':
            nxt = cur.peek()
            following = cur.peek(1)
            grouped_reporter = isinstance(following, str) and following in INFIX
            if isinstance(nxt, str) and self._is_callable_name(nxt) and not grouped_reporter:
                cur.next()
                args = []
                while cur.peek() != ')':
                    if cur.done():
                        raise LogoError("Missing ')'")
                    args.append(self.expr(cur))
                cur.next()
                return self.call(nxt.lower(), args)
            v = self.expr(cur)
            if cur.peek() != ')':
                raise LogoError("Missing ')'")
            cur.next()
            return v
        if t == ')':
            raise LogoError("Unexpected ')'")
        if t[0] == '"':
            return t[1:]
        if t[0] == ':':
            return self.lookup(t[1:])
        if is_number_token(t):
            return to_number(t)
        if t == '?' or (t[0] == '?' and t[1:].isdigit()):
            return self._slot(t)
        return self.call_by_name(t.lower(), cur)

    def _slot(self, t):
        if not self.slots:
            raise LogoError('? used outside a template')
        idx = int(t[1:]) - 1 if len(t) > 1 else 0
        try:
            return self.slots[-1][idx]
        except IndexError:
            raise LogoError(f'No input {idx + 1} for {t}') from None

    def _is_callable_name(self, t):
        if (
            t in ('(', ')')
            or t in INFIX
            or t[0] in '":'
            or is_number_token(t)
            or t == 'u-'
            or t.startswith('?')
        ):
            return False
        return t.lower() in self.procs or t.lower() in PRIMS

    def call_by_name(self, name, cur):
        p = self.procs.get(name) or PRIMS.get(name)
        if p is None:
            raise LogoError(f"I don't know how to {name}")
        if getattr(p, 'raw', False):
            nxt = cur.peek()
            if (
                isinstance(nxt, str)
                and nxt not in INFIX
                and nxt not in ('(', ')')
                and nxt[0] not in ':?'
                and not is_number_token(nxt)
            ):
                cur.next()
                return self.call(name, [nxt.lstrip('"')])
        return self.call(name, self.collect_args(p, name, cur))

    def collect_args(self, p, name, cur):
        args = []
        for _ in range(p.default):
            if cur.done() or cur.peek() == ')':
                if len(args) >= p.min:
                    break
                raise LogoError(f'Not enough inputs to {name}')
            args.append(self.expr(cur))
        return args

    def call(self, name, args):
        p = self.procs.get(name) or PRIMS.get(name)
        if p is None:
            raise LogoError(f"I don't know how to {name}")
        if len(args) < p.min:
            raise LogoError(f'Not enough inputs to {name}')
        if p.max != -1 and len(args) > p.max:
            raise LogoError(f'Too many inputs to {name}')
        if isinstance(p, Procedure):
            return self.call_user(p, args)
        return p.fn(self, *args)

    def call_user(self, p, args):
        if self.depth >= MAX_DEPTH:
            raise LogoError('Stack overflow')
        self.depth += 1
        base = len(self.scopes)
        strict = False  # a statement-style tail call means no value may come back
        try:
            while True:
                scope = {}
                for i, pname in enumerate(p.params):
                    if i < len(args):
                        scope[pname] = args[i]
                    else:
                        scope[pname] = self.run_list(p.defaults[pname], True)
                if p.rest:
                    scope[p.rest] = list(args[len(p.params) :])
                self._drop_shadowed(base, scope)
                self.scopes.append(scope)
                try:
                    result = self.run_body(p.body)
                except Output as o:
                    result = o.value
                except Stop:
                    result = None
                except RecursionError:
                    raise LogoError('Stack overflow') from None
                if isinstance(result, TailCall):
                    strict = strict or result.command
                    p, args = result.proc, result.args
                    continue
                if strict and result is not None:
                    raise LogoError(f"You don't say what to do with {V.fmt(result)}")
                return result
        finally:
            del self.scopes[base:]
            self.depth -= 1

    def run_body(self, body):
        """Run a procedure body. GOTO "tag, from anywhere inside it, resumes just
        after the matching TAG "tag among the body's own instructions."""
        start = 0
        while True:
            try:
                return self.run_statements(body[start:], True)
            except Goto as g:
                for i in range(len(body) - 1):
                    if (
                        isinstance(body[i], str)
                        and body[i].lower() == 'tag'
                        and isinstance(body[i + 1], str)
                        and body[i + 1][:1] == '"'
                        and body[i + 1][1:].lower() == g.tag.lower()
                    ):
                        start = i + 2
                        break
                else:
                    raise LogoError(f"Can't find tag {g.tag}") from None

    def _drop_shadowed(self, base, new_scope):
        """Tail calls reuse the Python stack, but Logo scope is dynamic: the callee
        can see its caller's variables. So a frame from an earlier hop is dropped
        only when every variable in it is shadowed by newer frames, which makes it
        unobservable. Self-recursive loops therefore run in constant memory."""
        shadow = set(new_scope)
        for i in range(len(self.scopes) - 1, base - 1, -1):
            keys = set(self.scopes[i])
            if keys <= shadow:
                del self.scopes[i]
            else:
                shadow |= keys

    def apply_template(self, tpl, args):
        """Apply a procedure name or a ?-slot template list to args."""
        if isinstance(tpl, list):
            if len(tpl) == 2 and isinstance(tpl[0], list):  # [[a b] body] lambda
                names, body = tpl
                scope = {n.lstrip(':').lower(): a for n, a in zip(names, args, strict=False)}
                self.scopes.append(scope)
                try:
                    return self.run_list(body, True)
                finally:
                    self.scopes.pop()
            self.slots.append(list(args))
            try:
                return self.run_list(tpl, True)
            finally:
                self.slots.pop()
        return self.call(V.word(tpl).lower(), list(args))

    # ---- helpers for primitives ------------------------------------------
    def write(self, s):
        self.out(s)

    def emit(self, s):
        """Output from PRINT, TYPE and SHOW: the SETWRITE file if one is chosen."""
        if self.writer is None:
            self.out(s)
        else:
            self.writer.write(s)

    def attach_turtle(self, turtle):
        from . import primitives_turtle  # noqa: F401

        self.turtle = turtle

    def run_safely(self, text):
        """Run text, printing Logo errors rather than raising. Returns False on error."""
        try:
            self.eval_source(text)
            return True
        except LogoError as e:
            self.write(f'{e.message}\n')
        except Throw as t:
            self.write(f"Can't find catch tag for {t.tag}\n")
        except Output:
            self.write('OUTPUT can only be used inside a procedure\n')
        except Stop:
            self.write('STOP can only be used inside a procedure\n')
        except Goto as g:
            self.write(f"Can't find tag {g.tag}\n")
        return False
