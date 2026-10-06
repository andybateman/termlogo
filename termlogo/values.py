"""Logo data helpers. Words are str, numbers are int/float, lists are list."""

from .errors import LogoError
from .lexer import is_number_token, to_number

TRUE, FALSE = 'true', 'false'


def fmt(x, top=False):
    """Format a value as PRINT (top=True, outer brackets dropped) or SHOW would."""
    if isinstance(x, list):
        inner = ' '.join(fmt(i) for i in x)
        return inner if top else '[' + inner + ']'
    if isinstance(x, bool):
        return TRUE if x else FALSE
    if isinstance(x, float):
        if abs(x) < 1e15 and x == int(x):
            return str(int(x))
        return format(x, '.12g')
    return str(x)


def is_num(x):
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        return True
    return isinstance(x, str) and is_number_token(x)


def num(x, who='?'):
    if isinstance(x, bool):
        raise LogoError(f"{who} doesn't like {fmt(x)} as input")
    if isinstance(x, (int, float)):
        return x
    if isinstance(x, str) and is_number_token(x):
        return to_number(x)
    raise LogoError(f"{who} doesn't like {fmt(x)} as input")


def intval(x, who='?'):
    n = num(x, who)
    if n != int(n):
        raise LogoError(f"{who} doesn't like {fmt(x)} as input")
    return int(n)


def truth(x, who='?'):
    if isinstance(x, bool):
        return x
    if isinstance(x, str):
        if x.lower() == TRUE:
            return True
        if x.lower() == FALSE:
            return False
    raise LogoError(f"{who} doesn't like {fmt(x)} as input")


def boolword(b):
    return TRUE if b else FALSE


def word(x, who='?'):
    if isinstance(x, list):
        raise LogoError(f"{who} doesn't like {fmt(x)} as input")
    return fmt(x)


def equal(a, b):
    if isinstance(a, list) or isinstance(b, list):
        return (
            isinstance(a, list)
            and isinstance(b, list)
            and len(a) == len(b)
            and all(equal(x, y) for x, y in zip(a, b, strict=True))
        )
    if is_num(a) and is_num(b):
        return num(a) == num(b)
    return fmt(a).lower() == fmt(b).lower()
