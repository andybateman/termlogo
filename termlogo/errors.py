"""Exceptions used for Logo errors and non-local control flow."""


class LogoError(Exception):
    """A Logo runtime error. `tag` is the CATCH tag it is raised under."""

    def __init__(self, message, value=None):
        super().__init__(message)
        self.message = message
        self.value = value


class Incomplete(Exception):
    """Source ends inside a list or a TO definition; more input is needed."""


class Stop(Exception):
    pass


class Output(Exception):
    def __init__(self, value):
        super().__init__()
        self.value = value


class Throw(Exception):
    def __init__(self, tag, value=None):
        super().__init__(tag)
        self.tag = tag
        self.value = value


class Bye(Exception):
    pass


class Goto(Exception):
    """GOTO "tag: the running procedure resumes after TAG "tag."""

    def __init__(self, tag):
        super().__init__(tag)
        self.tag = tag
