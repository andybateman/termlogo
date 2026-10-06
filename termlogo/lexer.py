"""Tokeniser. Words are str, lists are nested Python lists of tokens.

Prefix forms are kept on the token: `"word` is quoted, `:name` is a variable.
A unary minus is folded into a number literal (`-5`) or emitted as `u-`.
"""

import math
import re

from .arrays import LogoArray
from .errors import Incomplete, LogoError

NUMBER_RE = re.compile(r'(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?')
INFIX = {'=': 1, '<>': 1, '<': 1, '>': 1, '<=': 1, '>=': 1, '+': 2, '-': 2, '*': 3, '/': 3, '^': 4}
OPS1 = set('+-*/=<>^')
DELIMS = set('[]{}()') | OPS1
OPENER = {']': '[', '}': '{'}
ORIGIN_RE = re.compile(r'@(-?\d+)')


def is_number_token(tok):
    if not isinstance(tok, str):
        return False
    body = tok[1:] if tok[:1] == '-' else tok
    m = NUMBER_RE.fullmatch(body)
    return m is not None


def to_number(tok):
    if '.' not in tok and 'e' not in tok.lower():
        return int(tok)
    f = float(tok)
    if not math.isfinite(f):
        raise LogoError(f'Number out of range: {tok}')
    return f


def tokenize(text):
    """Return a list of tokens. Raises Incomplete if brackets are unbalanced."""
    stack = [[]]
    kinds = ['[']  # what opened each level: '[' for a list, '{' for an array
    i, n = 0, len(text)
    prev_ws = True

    def prev_tok():
        cur = stack[-1]
        return cur[-1] if cur else None

    while i < n:
        c = text[i]
        if c == ';':
            while i < n and text[i] != '\n':
                i += 1
            continue
        if c == '~' and i + 1 < n and text[i + 1] == '\n':
            i += 2
            continue
        if c.isspace():
            i += 1
            prev_ws = True
            continue
        cur = stack[-1]
        if c in '[{':
            new = []
            cur.append(new)
            stack.append(new)
            kinds.append(c)
            i += 1
        elif c in ']}':
            if len(stack) == 1 or kinds[-1] != OPENER[c]:
                raise LogoError(f"Unexpected '{c}'")
            items = stack.pop()
            kinds.pop()
            i += 1
            if c == '}':
                origin = ORIGIN_RE.match(text, i)
                if origin:
                    i = origin.end()
                stack[-1][-1] = LogoArray(items, int(origin.group(1)) if origin else 1)
        elif c in '()':
            cur.append(c)
            i += 1
        elif c in OPS1:
            two = text[i : i + 2]
            if two in ('<=', '>=', '<>'):
                cur.append(two)
                i += 2
            elif c == '-':
                last = prev_tok()
                after = text[i + 1 : i + 2]
                unary = (
                    (
                        prev_ws
                        or last is None
                        or last == '('
                        or (isinstance(last, str) and last in INFIX)
                    )
                    and after
                    and not after.isspace()
                )
                if unary:
                    m = NUMBER_RE.match(text, i + 1)
                    if m:
                        cur.append('-' + m.group())
                        i = m.end()
                    else:
                        cur.append('u-')
                        i += 1
                else:
                    cur.append('-')
                    i += 1
            else:
                cur.append(c)
                i += 1
        elif c == '|' or (c == '"' and text[i + 1 : i + 2] == '|'):
            start = i + (2 if c == '"' else 1)
            end = text.find('|', start)
            if end < 0:
                raise Incomplete()
            cur.append('"' + text[start:end])
            i = end + 1
        elif c == '"':
            j = i + 1
            while j < n and not text[j].isspace() and text[j] not in '[]{}()':
                j += 1
            cur.append(text[i:j])
            i = j
        else:
            m = NUMBER_RE.match(text, i) if (c.isdigit() or c == '.') else None
            if m and (m.end() >= n or text[m.end()].isspace() or text[m.end()] in DELIMS):
                cur.append(m.group())
                i = m.end()
            else:
                j = i
                if c == ':':
                    j += 1
                while j < n and not text[j].isspace() and text[j] not in DELIMS and text[j] != ';':
                    j += 1
                if j == i:
                    j = i + 1
                cur.append(text[i:j])
                i = j
        prev_ws = False
    if len(stack) > 1:
        raise Incomplete()
    return stack[0]
