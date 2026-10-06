"""The Logo array type, kept apart so the lexer can build array literals."""


class LogoArray:
    """A Logo array: mutable, fixed size, indexed from `origin` (default 1).
    Arrays are equal only to themselves."""

    __slots__ = ('items', 'origin')

    def __init__(self, items, origin=1):
        self.items, self.origin = items, origin

    def __str__(self):
        from .values import fmt

        return fmt(self)

    __repr__ = __str__
