"""Interactive REPL: canvas on top, text log beneath, prompt at the bottom."""

import codecs
import json
import os
import select
import shutil
import sys
import tempfile
import textwrap
import time
import unicodedata
from bisect import bisect_right
from collections import deque

from . import renderers
from .errors import Bye, Incomplete, LogoError
from .interp import Interp
from .registry import PRIMS
from .turtle import DEFAULT_SPEED

LOG_LINES = 5
HISTORY = os.path.expanduser('~/.termlogo_history')
HISTORY_HEADER = '# termlogo history v1\n'
SYNC_ON, SYNC_OFF = '\x1b[?2026h', '\x1b[?2026l'  # atomic screen updates
HIDE, SHOW = '\x1b[?25l', '\x1b[?25h'
MOUSE_ON, MOUSE_OFF = '\x1b[?1002h\x1b[?1006h', '\x1b[?1002l\x1b[?1006l'
PASTE_ON, PASTE_OFF = '\x1b[?2004h', '\x1b[?2004l'
PASTE_START, PASTE_END = b'\x1b[200~', b'\x1b[201~'
# Alt+Enter, and Shift+Enter in terminals that report it (Ghostty, Kitty, xterm):
# these add a line break to the command where Enter alone would run it.
NEWLINE_KEYS = (b'\x1b\r', b'\x1b\n', b'\x1b[13;2u', b'\x1b[27;2;13~')


def _terminal_size(stream=None):
    try:
        return os.get_terminal_size((stream or sys.stdout).fileno())
    except (AttributeError, OSError):
        return shutil.get_terminal_size((80, 24))


def _columns(text, initial_column=0):
    offsets = [0]
    for char in text:
        width = (
            8 - (initial_column + offsets[-1]) % 8
            if char == '\t'
            else 0
            if unicodedata.category(char) in ('Mn', 'Me', 'Cf')
            else 2
            if unicodedata.east_asian_width(char) in ('W', 'F')
            else 1
        )
        offsets.append(offsets[-1] + width)
    return offsets


def _expand_tabs(text):
    columns = _columns(text)
    return ''.join(
        ' ' * (columns[index + 1] - columns[index]) if char == '\t' else char
        for index, char in enumerate(text)
    )


def _wrapped_lines(text, cols):
    lines = text.split('\n')[:-1] if text.endswith('\n') else text.split('\n')
    return [
        wrapped
        for line in lines
        for wrapped in (
            textwrap.wrap(line, max(1, cols), replace_whitespace=False, break_on_hyphens=False)
            or ['']
        )
    ]


def _input_lines(prompt, text, cols):
    """Map wrapped display rows back to offsets in the original command."""
    rows = []
    start, used = 0, 0
    continuation = '> ' if prompt and cols >= 4 else ''
    if cols < 4:
        prompt = ''
    prefix = prompt
    width = max(1, cols - _columns(prefix)[-1] - 1)
    for index, char in enumerate(text):
        if char == '\n':
            rows.append((start, index, prefix))
            start, used, prefix = index + 1, 0, continuation
        else:
            cells = _columns(char, _columns(prefix)[-1] + used)[-1]
            if used + cells > width and index > start:
                rows.append((start, index, prefix))
                start, used, prefix = index, 0, continuation
                cells = _columns(char, _columns(prefix)[-1])[-1]
            used += cells
    rows.append((start, len(text), prefix))
    return rows


class DrawingControls:
    """Read terminal keys and mouse reports without interfering with Logo input."""

    def __init__(self, turtle, fd, display=None):
        self.turtle, self.fd, self.display = turtle, fd, display
        self._last_poll = 0.0
        self.pending = display.pending_input if display is not None else deque()

    def read_event(self, timeout):
        if not select.select([self.fd], [], [], timeout)[0]:
            return None
        data = os.read(self.fd, 1)
        if not data:
            raise EOFError
        if data != b'\x1b':
            return data
        seq = bytearray(data)
        while len(seq) < 64:
            if not select.select([self.fd], [], [], 0.05)[0]:
                return bytes(seq)
            byte = os.read(self.fd, 1)
            if not byte:
                raise EOFError
            seq.extend(byte)
            if len(seq) == 2 and byte not in (b'[', b'O'):
                return bytes(seq)
            if len(seq) > 2 and 0x40 <= byte[0] <= 0x7E:
                return bytes(seq)
        return bytes(seq)

    def read_paste(self):
        data = bytearray()
        while True:
            event = self.pending.popleft() if self.pending else self.read_event(1 / 30)
            if self.display is not None:
                self.display.refresh()
            if event == PASTE_END:
                break
            if event is not None:
                data.extend(event)
        try:
            text = data.decode(sys.stdin.encoding or 'utf-8')
        except UnicodeDecodeError as error:
            raise LogoError('Pasted text is not valid for the terminal encoding') from error
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        if any(unicodedata.category(char) == 'Cc' and char not in '\n\t' for char in text):
            raise LogoError('Pasted text contains unsupported control characters')
        return text

    def __call__(self, timeout):
        deadline = time.monotonic() + timeout
        while True:
            remaining = max(0, deadline - time.monotonic())
            try:
                event = self.read_event(min(remaining, 1 / 30))
            except EOFError:
                raise KeyboardInterrupt from None
            if self.display is not None:
                self.display.refresh()
            if event in (b'\x1b', b'\x03'):
                raise KeyboardInterrupt
            if event and event.startswith(b'\x1b[<') and self._mouse(event[3:]):
                if self.display is not None:
                    self.display.draw()
                return True
            if event and not event.startswith(b'\x1b'):
                self.pending.append(event)
            if event is None and time.monotonic() >= deadline:
                return False

    def readchar(self):
        """READCHAR: wait for one key and return it ('' at end of input).
        Escape or Ctrl-C stops the program; arrow keys and mouse reports are skipped."""
        while True:
            if self.pending:
                data = self.pending.popleft()
            else:
                try:
                    data = self.read_event(1 / 30)
                except EOFError:
                    return ''
                if self.display is not None:
                    self.display.refresh()
                if data is None:
                    continue
            if data in (b'\x1b', b'\x03'):
                raise KeyboardInterrupt
            if data.startswith(b'\x1b'):
                if data.startswith(b'\x1b[<') and self._mouse(data[3:]) and self.display:
                    self.display.draw()
                continue
            if data == b'\r':
                return '\n'
            if data[0] >= 0xC0:  # the start of a multi-byte character
                more = 1 if data[0] < 0xE0 else 2 if data[0] < 0xF0 else 3
                while more:
                    try:
                        data += os.read(self.fd, 1)
                    except OSError:
                        break
                    more -= 1
            return data.decode(sys.stdin.encoding or 'utf-8', 'replace')

    def keyp(self):
        """KEYP: has a key been pressed that READCHAR has not yet returned?"""
        self(0)
        return any(not event.startswith(b'\x1b') for event in self.pending)

    def poll(self):
        now = time.monotonic()
        if now - self._last_poll >= 1 / 30:
            self._last_poll = now
            self(0)

    def wait(self, seconds):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            self(max(0, deadline - time.monotonic()))

    def _mouse(self, seq):
        event = self._left_mouse(seq)
        if event is None:
            return False
        _, col, row = event
        c = self.turtle.canvas
        if not (1 <= col <= c.cols and 1 <= row <= c.rows):
            return False
        px, py = (col - 0.5) * c.cell[0], (row - 0.5) * c.cell[1]
        self.turtle.x, self.turtle.y = c.from_pixel(px, py)
        return True

    @staticmethod
    def _left_mouse(seq):
        try:
            code, col, row = (int(n) for n in seq[:-1].split(b';'))
        except ValueError:
            return None
        # Leave Shift-mouse to the terminal's native text selection.
        if code not in (0, 8, 16, 24, 32, 40, 48, 56) or seq[-1:] != b'M':
            return None
        if col < 1 or row < 1:
            return None
        return code, col, row

    def readline(self, prompt, it=None, initial=''):
        """Small terminal editor, with history and completion from the REPL."""
        try:
            import readline
        except ImportError:
            readline = None
        history = (
            [
                readline.get_history_item(n)
                for n in range(1, readline.get_current_history_length() + 1)
            ]
            if readline is not None and it is not None
            else []
        )
        entries = [*history, initial]  # the last entry is the unfinished draft
        line, pos, hist = initial, len(initial), len(history)
        goal = None  # display column kept while moving up and down
        view_start = 0
        rows = []
        decoder = codecs.getincrementaldecoder(sys.stdin.encoding or 'utf-8')()

        def cursor_row():
            return bisect_right([row[0] for row in rows], pos) - 1

        def position_at(row, cell):
            """Offset in the command for a display row and a 0-based screen column."""
            start, end, prefix = rows[row]
            indent = _columns(prefix)[-1]
            offset = bisect_right(_columns(line[start:end], indent), max(0, cell - indent)) - 1
            if row + 1 < len(rows) and rows[row + 1][0] == end:
                offset = min(offset, end - start - 1)  # a wrapped row ends before the next
            return start + offset

        def move_row(step):
            """Move the cursor one display row. False at the first or last row."""
            nonlocal pos, goal
            current = cursor_row()
            if not 0 <= current + step < len(rows):
                return False
            if goal is None:
                start, _, prefix = rows[current]
                goal = _columns(prefix + line[start:pos])[-1]
            pos = position_at(current + step, goal)
            return True

        def recall(step):
            """Step through history, keeping edits made to each entry on the way."""
            nonlocal line, pos, hist
            target = max(0, min(len(history), hist + step))
            if target != hist:
                entries[hist] = line
                hist = target
                line = entries[hist]
                pos = len(line)

        def show_prompt():
            nonlocal view_start, rows
            cols = self.display.cols if self.display else _terminal_size().columns
            rows = _input_lines(prompt, line, cols)
            cursor_row = bisect_right([row[0] for row in rows], pos) - 1
            height = 1
            if self.display is not None:
                previous = (
                    self.display.canvas.rows,
                    self.display.log_rows,
                    self.display.input_rows,
                )
                self.display.command_rows = len(rows)
                self.display.resize_to_terminal()
                height = self.display.input_rows
                if (
                    previous != (self.display.canvas.rows, self.display.log_rows, height)
                    or self.display.fresh
                ):
                    self.display._draw()
            view_start = min(view_start, max(0, len(rows) - height))
            if cursor_row < view_start:
                view_start = cursor_row
            elif cursor_row >= view_start + height:
                view_start = cursor_row - height + 1
            sys.stdout.write(SYNC_ON + HIDE)
            for offset, (start, end, prefix) in enumerate(rows[view_start : view_start + height]):
                if self.display is not None:
                    sys.stdout.write(f'\x1b[{self.display.prompt_row + offset};1H')
                visible = _expand_tabs(prefix + line[start:end])
                limit = bisect_right(_columns(visible), max(1, cols - 1)) - 1
                sys.stdout.write('\r\x1b[K' + visible[:limit])
            start, _, prefix = rows[cursor_row]
            cursor = min(cols - 1, _columns(prefix + line[start:pos])[-1])
            if self.display is not None:
                sys.stdout.write(f'\x1b[{self.display.prompt_row + cursor_row - view_start};1H')
            sys.stdout.write('\r' + (f'\x1b[{cursor}C' if cursor else '') + SHOW)
            sys.stdout.write(SYNC_OFF)
            sys.stdout.flush()

        if self.display is not None:
            self.display.prompt_cb = show_prompt
        try:
            sys.stdout.write(PASTE_ON)
            show_prompt()
            while True:
                event = self.pending.popleft() if self.pending else self.read_event(1 / 30)
                if self.display is not None:
                    self.display.refresh()
                if event is None:
                    continue
                if event.startswith(b'\x1b[<'):
                    mouse = self._left_mouse(event[3:])
                    if mouse is not None and self.display is not None:
                        code, col, row = mouse
                        if (
                            self.display.prompt_row
                            <= row
                            < self.display.prompt_row + self.display.input_rows
                            and col <= self.display.cols
                        ):
                            if not code & 32:
                                pos = position_at(
                                    view_start + row - self.display.prompt_row, col - 1
                                )
                                goal = None
                                show_prompt()
                        elif self._mouse(event[3:]):
                            self.display.draw()
                    continue
                if event in (b'\r', b'\n'):
                    sys.stdout.write('\r' if self.display is not None else '\n')
                    return line
                if event in (b'\x03', b'\x1b'):
                    raise KeyboardInterrupt
                line_start = line.rfind('\n', 0, pos) + 1
                line_end = line.find('\n', pos)
                line_end = len(line) if line_end < 0 else line_end
                moved_row = False
                if event == PASTE_START:
                    text = self.read_paste()
                    line = line[:pos] + text + line[pos:]
                    pos += len(text)
                elif event in NEWLINE_KEYS:
                    line = line[:pos] + '\n' + line[pos:]
                    pos += 1
                elif event == b'\x04':
                    if not line:
                        raise EOFError
                    line = line[:pos] + line[pos + 1 :]
                elif event in (b'\x7f', b'\x08'):
                    if pos:
                        line = line[: pos - 1] + line[pos:]
                        pos -= 1
                elif event in (b'\x1b[D', b'\x02'):
                    pos = max(0, pos - 1)
                elif event in (b'\x1b[C', b'\x06'):
                    pos = min(len(line), pos + 1)
                elif event in (b'\x1b[H', b'\x1bOH', b'\x1b[1~', b'\x01'):
                    # Start of this line; a second press goes to the start of the command.
                    pos = 0 if pos == line_start else line_start
                elif event in (b'\x1b[F', b'\x1bOF', b'\x1b[4~', b'\x05'):
                    pos = len(line) if pos == line_end else line_end
                elif event == b'\x1b[3~':
                    line = line[:pos] + line[pos + 1 :]
                elif event == b'\x15':
                    line, pos = line[:line_start] + line[pos:], line_start
                elif event == b'\x0b':
                    # To the end of this line, or the line break itself when already there.
                    line = line[:pos] + line[line_end if pos < line_end else pos + 1 :]
                elif event in (b'\x1b[A', b'\x1b[B'):
                    # Inside a multi-line command the arrows move between its rows;
                    # from the first or last row they step through history.
                    step = -1 if event == b'\x1b[A' else 1
                    moved_row = move_row(step)
                    if not moved_row:
                        recall(step)
                elif event in (b'\x10', b'\x1b[5~'):
                    recall(-1)
                elif event in (b'\x0e', b'\x1b[6~'):
                    recall(1)
                elif event == b'\t' and it is not None:
                    start = pos
                    while start and line[start - 1] not in ' \t\n[]()"':
                        start -= 1
                    hits = completions(it, line[start:pos])
                    if hits:
                        replacement = os.path.commonprefix(hits)
                        line = line[:start] + replacement + line[pos:]
                        pos = start + len(replacement)
                elif not event.startswith(b'\x1b') and event[0] >= 32:
                    text = decoder.decode(event)
                    line = line[:pos] + text + line[pos:]
                    pos += len(text)
                if not moved_row:
                    goal = None
                show_prompt()
        finally:
            sys.stdout.write(PASTE_OFF)
            sys.stdout.flush()
            if self.display is not None:
                self.display.prompt_cb = None


class drawing_controls:
    """Temporarily enable immediate key and mouse input while drawing on a TTY."""

    def __init__(self, turtle, enabled, it=None, display=None):
        self.turtle, self.it, self.display = turtle, it, display
        self.enabled = enabled and os.name == 'posix'
        self.controls = None

    def __enter__(self):
        if self.enabled:
            import termios
            import tty

            self.fd = sys.stdin.fileno()
            self.termios = termios
            self.settings = termios.tcgetattr(self.fd)
            self.previous_input = self.turtle.input_cb
            if self.it is not None:
                self.previous_poll, self.previous_wait = self.it.on_poll, self.it.on_wait
                self.previous_readline = self.it.readline
                self.previous_keys = self.it.readchar, self.it.keyp
            try:
                tty.setcbreak(self.fd, termios.TCSANOW)
                active = termios.tcgetattr(self.fd)
                active[3] &= ~(termios.ECHO | termios.ECHONL)
                termios.tcsetattr(self.fd, termios.TCSADRAIN, active)
                self.controls = DrawingControls(self.turtle, self.fd, self.display)
                self.turtle.input_cb = self.controls
                if self.it is not None:
                    self.it.on_poll, self.it.on_wait = self.controls.poll, self.controls.wait
                    self.it.readline = self.readline
                    self.it.readchar, self.it.keyp = self.controls.readchar, self.controls.keyp
                sys.stdout.write(MOUSE_ON)
                sys.stdout.flush()
            except BaseException:
                self.__exit__(None, None, None)
                raise
        return self

    def readline(self, prompt):
        running = self.display.running if self.display is not None else False
        if self.display is not None:
            self.display.running = False
            self.display.draw()
        try:
            return self.controls.readline(prompt)
        finally:
            if self.display is not None:
                self.display.running = running
                self.display.command_rows = 1
                self.display.draw()

    def __exit__(self, *_):
        if self.enabled:
            try:
                sys.stdout.write(MOUSE_OFF)
                sys.stdout.flush()
            finally:
                self.turtle.input_cb = self.previous_input
                if self.it is not None:
                    self.it.on_poll, self.it.on_wait = self.previous_poll, self.previous_wait
                    self.it.readline = self.previous_readline
                    self.it.readchar, self.it.keyp = self.previous_keys
                self.termios.tcsetattr(self.fd, self.termios.TCSADRAIN, self.settings)


def build(cols, rows, scale, out, render='braille', cell_px=None, colour_mode='ucblogo', fit=None):
    from .turtle import Turtle

    canvas = renderers.make_canvas(render, cols, rows, scale, cell_px, fit)
    turtle = Turtle(canvas, colour_mode=colour_mode)
    it = Interp(out=out)
    it.attach_turtle(turtle)
    return it, canvas, turtle


class Display:
    """Draws canvas, status line and the last few lines of text output in place.

    Redraws overwrite text cells inside a synchronised update. Kitty's image
    does not overwrite those cells, so its canvas text layer is cleared first."""

    def __init__(
        self, it, canvas, turtle, render, color, log, stream=None, auto_size=False, cell_px=None
    ):
        self.it, self.canvas, self.turtle = it, canvas, turtle
        self.render, self.color, self.log = render, color, log
        self.stream = stream or sys.stdout
        self.cols = canvas.cols
        self.auto_size, self.cell_px = auto_size, cell_px
        self.screen_lines = None
        self.command_rows = 1
        self.banner = ''
        self.prompt_cb = None
        self.pending_input = deque()
        self.fresh = True
        self.running = False
        it.on_frame = self.draw
        turtle.frame_cb = self.draw
        self.cursor = None  # [col, row in the log] once SETCURSOR has been used
        self.cursor_base = 0  # log index of the text pane's top row
        it.cursor_get, it.cursor_set, it.text_clear = (
            self.get_cursor,
            self.set_cursor,
            self.clear_text,
        )

    def log_text(self, text):
        if self.cursor is None:
            self.log.extend(_wrapped_lines(text, self.cols))
        else:
            self._put_text(text)

    # ---- text cursor (CURSOR, SETCURSOR, CLEARTEXT) --------------------------
    # The text pane under the canvas shows the last LOG_LINES lines of the log, so
    # cursor positions are (column, row) within those rows, counted from the top.
    def get_cursor(self):
        if self.cursor is None:
            return [0, min(len(self.log) - max(0, len(self.log) - LOG_LINES), LOG_LINES - 1)]
        return [self.cursor[0], self.cursor[1] - self.cursor_base]

    def set_cursor(self, col, row):
        if row >= LOG_LINES or col >= self.cols:
            raise LogoError(
                f'SETCURSOR is limited to {self.cols} columns and {LOG_LINES} rows here'
            )
        if self.cursor is None:
            self.cursor_base = max(0, len(self.log) - LOG_LINES)
        self.cursor = [col, self.cursor_base + row]
        while len(self.log) <= self.cursor[1]:
            self.log.append('')

    def clear_text(self):
        self.log.clear()
        self.cursor_base = 0
        if self.cursor is not None:
            self.cursor = [0, 0]
            self.log.append('')

    def _put_text(self, text):
        """Write text at the cursor, over what is already there."""
        col, row = self.cursor
        for index, piece in enumerate(text.split('\n')):
            if index:
                col, row = 0, row + 1
            while piece:
                if col >= self.cols:
                    col, row = 0, row + 1
                room = piece[: self.cols - col]
                while len(self.log) <= row:
                    self.log.append('')
                line = self.log[row].ljust(col)
                self.log[row] = line[:col] + room + line[col + len(room) :]
                col += len(room)
                piece = piece[len(room) :]
            if row >= self.cursor_base + LOG_LINES:  # scrolled off the bottom
                self.cursor_base = row - LOG_LINES + 1
        while len(self.log) <= row:
            self.log.append('')
        self.cursor = [col, row]

    @property
    def banner_lines(self):
        return _wrapped_lines(self.banner, self.cols) if self.banner else []

    def _startup_rows(self, cols):
        return (
            len(_wrapped_lines(self.banner, cols)) + min(LOG_LINES, len(self.log))
            if self.banner
            else 0
        )

    def resize_to_terminal(self):
        size = _terminal_size(self.stream)
        height_changed = self.screen_lines != size.lines
        self.screen_lines = size.lines
        if not self.auto_size:
            return height_changed
        cols = max(1, size.columns)
        rows = max(
            1,
            min(
                size.lines - LOG_LINES - 3,
                size.lines - self.command_rows - self._startup_rows(cols) - 2,
            ),
        )
        cell_px = None
        if self.render == 'kitty':
            try:
                fd = self.stream.fileno()
            except (AttributeError, OSError, ValueError):
                fd = 1
            cell_px = renderers.cell_pixels(fd) or self.cell_px
        if (cols, rows) == (self.canvas.cols, self.canvas.rows) and cell_px == self.cell_px:
            return height_changed
        user_scale = self.canvas.scale / self.canvas.base_scale
        canvas = renderers.make_canvas(self.render, cols, rows, user_scale, cell_px)
        self.canvas.copy_to(canvas)
        self.canvas = self.turtle.canvas = canvas
        self.cols, self.cell_px = cols, cell_px
        self.fresh = True
        return True

    def refresh(self):
        if self.resize_to_terminal():
            self.draw()

    def draw(self, clear=False):
        self.resize_to_terminal()
        self._draw(clear)
        if self.prompt_cb is not None:
            self.prompt_cb()

    @property
    def input_rows(self):
        lines = self.screen_lines or self.canvas.rows + LOG_LINES + 3
        return min(
            self.command_rows,
            max(1, lines - self.canvas.rows - self._startup_rows(self.cols) - 2),
        )

    @property
    def log_rows(self):
        lines = self.screen_lines or self.canvas.rows + LOG_LINES + 3
        return min(
            max(LOG_LINES, self._startup_rows(self.cols)),
            max(0, lines - self.canvas.rows - self.input_rows - 2),
        )

    @property
    def prompt_row(self):
        return self.canvas.rows + self.log_rows + 2

    def _draw(self, clear=False):
        t = self.turtle
        status = (
            f' pos [{_f(t.x)} {_f(t.y)}]  heading {_f(t.heading)}'
            f'  pen {"down" if t.pen_down else "up"} {t.pen_mode}  {t.boundary}'
            f'  speed {_f(t.speed)}'
        )
        log_lines = self.log_rows
        remaining = min(LOG_LINES, len(self.log), log_lines)
        tail = self.banner_lines[: log_lines - remaining]
        tail += self.log[-remaining:] if remaining else []
        tail = tail + [''] * (log_lines - len(tail))
        parts = [
            SYNC_ON,
            HIDE,
            '\x1b[0m',
            '\x1b[2J\x1b[H' if (clear or self.fresh) else '\x1b[H',
        ]
        if self.render == 'kitty':
            parts.extend(f'\x1b[{row};1H\x1b[2K' for row in range(1, self.canvas.rows + 1))
            parts.append('\x1b[H')
        parts.extend(
            [
                renderers.frame(self.render, self.canvas, t, self.color),
                '\x1b[7m' + status.ljust(self.cols)[: self.cols] + '\x1b[0m\x1b[K\n',
            ]
        )
        parts.extend(line[: self.cols] + '\x1b[K\n' for line in tail)
        parts.append('\x1b[J')
        if not self.running:
            parts.append(SHOW)
        parts.append(SYNC_OFF)
        self.stream.write(''.join(parts))
        self.stream.flush()
        self.fresh = False


def completions(it, text):
    """Names matching `text`: primitives, procedures, help topics, or :variables."""
    t = text.lower()
    if t.startswith(':'):
        seen = {k for sc in it.scopes for k in sc if not k.startswith('%')}
        return sorted(':' + k for k in seen if (':' + k).startswith(t))
    from .helptext import TOPICS

    names = set(PRIMS) | set(it.procs) | TOPICS | {'help'}
    return sorted(n for n in names if n.startswith(t))


def _setup_readline(it):
    try:
        import readline
    except ImportError:
        return
    try:
        _load_history(readline)
    except FileNotFoundError:
        pass
    except (OSError, ValueError) as e:
        it.write(f'termlogo: Could not load command history: {e}\n')
    readline.set_auto_history(False)
    import atexit

    atexit.register(lambda: _save_history(readline))

    def complete(text, state):
        hits = completions(it, text)
        return hits[state] if state < len(hits) else None

    readline.set_completer(complete)
    readline.set_completer_delims(' \t\n[]()"')
    if 'libedit' in (readline.__doc__ or ''):  # macOS system and Homebrew builds
        readline.parse_and_bind('bind ^I rl_complete')
    else:
        readline.parse_and_bind('tab: complete')


def _load_history(readline):
    with open(HISTORY, encoding='utf-8') as history_file:
        if history_file.readline() != HISTORY_HEADER:
            legacy = True
        else:
            legacy = False
            commands = json.load(history_file)
            if not isinstance(commands, list) or any(not isinstance(c, str) for c in commands):
                raise ValueError('history must contain a list of command strings')
    if legacy:
        readline.read_history_file(HISTORY)
    else:
        for command in commands:
            readline.add_history(command)


def _record_history(command):
    if not command.strip():
        return
    try:
        import readline
    except ImportError:
        return
    readline.add_history(command)


def _save_history(readline):
    temporary = None
    try:
        commands = [
            readline.get_history_item(n)
            for n in range(1, readline.get_current_history_length() + 1)
        ]
        with tempfile.NamedTemporaryFile(
            mode='w',
            encoding='utf-8',
            dir=os.path.dirname(HISTORY),
            prefix='.termlogo-history-',
            delete=False,
        ) as history_file:
            temporary = history_file.name
            history_file.write(HISTORY_HEADER)
            json.dump(commands, history_file)
            history_file.write('\n')
        os.replace(temporary, HISTORY)
        temporary = None
    except (OSError, ValueError) as e:
        print(f'termlogo: Could not save command history: {e}', file=sys.stderr)
    finally:
        if temporary is not None:
            os.unlink(temporary)


def repl(
    cols=None,
    rows=None,
    scale=1.0,
    color=True,
    render=None,
    speed=DEFAULT_SPEED,
    interpreter=None,
    colour_mode='ucblogo',
    fit=None,
):
    tty = sys.stdin.isatty() and sys.stdout.isatty()
    auto_size = cols is None and rows is None
    size = _terminal_size()
    cols = cols or size.columns
    rows = rows or max(1, size.lines - LOG_LINES - 3)
    log = []
    display = None
    try:
        render, cell_px = renderers.choose(render, tty)
    except ValueError as e:
        print(f'termlogo: {e}', file=sys.stderr)
        return 2

    def out(s):
        if tty and display is not None:
            display.log_text(s)
        else:
            log.extend(s.split('\n')[:-1] if s.endswith('\n') else s.split('\n'))
        if not tty:
            sys.stdout.write(s)
            sys.stdout.flush()

    if interpreter is None:
        it, canvas, turtle = build(cols, rows, scale, out, render, cell_px, colour_mode, fit)
        turtle.speed = speed
    else:
        it, turtle = interpreter, interpreter.turtle
        canvas = turtle.canvas
        it.out = out
    display = Display(it, canvas, turtle, render, color, log, auto_size=auto_size, cell_px=cell_px)
    if tty:
        from . import __author__, __version__

        display.banner = (
            f'termlogo {__version__} by {__author__}\n'
            f'HELP for commands, Tab to complete, BYE to leave '
            f'({render}, {turtle.colour_mode} colours)\n'
            'Click canvas to move turtle; click commands to edit; Shift-drag selects text'
        )

        def dismiss_banner():
            display.banner = ''
            it.on_start = None
            display.draw()

        it.on_start = dismiss_banner
        _setup_readline(it)
        display.draw()
    else:
        turtle.frame_cb = None  # nothing to animate on when piped
    buf = ''
    try:
        while True:
            try:
                prompt = '? ' if not buf else '> '
                if tty and os.name == 'posix':
                    with drawing_controls(turtle, True, display=display) as session:
                        line = session.controls.readline('? ', it, buf + '\n' if buf else '')
                else:
                    line = input(prompt) if tty else sys.stdin.readline()
                if not tty and line == '':
                    break
            except EOFError:
                break
            except KeyboardInterrupt:
                buf = ''
                if tty:
                    display.draw()
                continue
            except LogoError as error:
                out(error.message + '\n')
                if tty:
                    display.command_rows = 1
                    display.draw()
                continue
            if tty and os.name == 'posix':
                buf = line
            else:
                buf = (buf + '\n' + line) if buf else line
            mark = len(log)
            display.cursor = None  # SETCURSOR lasts for one command
            display.running = True
            if tty:
                display.command_rows = 1
                display.resize_to_terminal()
            complete = True
            try:
                with drawing_controls(turtle, tty, it, display):
                    it.eval_source(buf)
            except Incomplete:
                complete = False
                display.running = False
                continue
            except Bye:
                break
            except KeyboardInterrupt:
                out('Stopped!\n')
            except LogoError as e:
                out(e.message + '\n')
            except Exception as e:  # never let a Logo program kill the REPL
                out(_report(it, e))
            finally:
                if tty and complete:
                    _record_history(buf)
            display.running = False
            buf = ''
            if tty and len(log) - mark > LOG_LINES:
                _page(log[mark:])
                display.fresh = True
            if tty:
                display.draw()
    finally:
        it.on_start = None
        it.on_poll = it.on_wait = None
        if tty:
            sys.stdout.write(SHOW)
            print()
    return 0


def _page(lines):
    """Show long output (such as HELP) full screen, a screenful at a time."""
    rows = max(5, shutil.get_terminal_size((80, 24)).lines - 2)
    sys.stdout.write('\x1b[H\x1b[2J')
    for i in range(0, len(lines), rows):
        sys.stdout.write('\n'.join(lines[i : i + rows]) + '\n')
        more = i + rows < len(lines)
        try:
            input('-- more, Enter to continue --' if more else '-- Enter to return --')
        except (EOFError, KeyboardInterrupt):
            break
        if more:
            sys.stdout.write('\x1b[H\x1b[2J')


def _report(it, e):
    from .errors import Goto, Output, Stop, Throw

    if isinstance(e, Goto):
        return f"Can't find tag {e.tag}\n"
    if isinstance(e, Throw):
        return f"Can't find catch tag for {e.tag}\n"
    if isinstance(e, Output):
        return 'OUTPUT can only be used inside a procedure\n'
    if isinstance(e, Stop):
        return 'STOP can only be used inside a procedure\n'
    return f'Internal error: {type(e).__name__}: {e}\n'


def _f(v):
    v = round(v, 2)
    return int(v) if v == int(v) else v
