import contextlib
import io
import json
import os
import re
import select
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from termlogo import __author__, __version__
from termlogo.__main__ import main
from termlogo.canvas import Canvas
from termlogo.errors import LogoError
from termlogo.interp import Interp
from termlogo.repl import (
    HISTORY_HEADER,
    PASTE_END,
    PASTE_OFF,
    PASTE_ON,
    PASTE_START,
    Display,
    DrawingControls,
    _load_history,
    _save_history,
    drawing_controls,
)
from termlogo.turtle import Turtle

ROOT = Path(__file__).resolve().parents[1]
ANSI = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')
CIRCLE_PROGRAM = """clearscreen
make "dist 1
repeat 4 [
    make "circle repcount
    setcolor random 16
    repeat 360 [
        fd :dist
        right (-1) ^ (:circle + 1)
    ]
    if :circle = 2 [make "dist :dist + 1]
]"""


class TextScreen:
    """Text cells and cursor movement; graphics packets deliberately have no text effect."""

    escapes = re.compile(r'\x1b_.*?\x1b\\|\x1b\[[0-?]*[ -/]*[@-~]', re.S)

    def __init__(self, cols=80, rows=24):
        self.cols, self.height = cols, rows
        self.lines = [[' '] * cols for _ in range(rows)]
        self.x = self.y = self.scrolls = 0

    def feed(self, text):
        if isinstance(text, bytes):
            text = text.decode('utf-8')
        end = 0
        for match in self.escapes.finditer(text):
            self.write(text[end : match.start()])
            sequence = match.group()
            if sequence.startswith('\x1b['):
                self.control(sequence)
            end = match.end()
        self.write(text[end:])

    def newline(self):
        self.x = 0
        if self.y == self.height - 1:
            self.lines.pop(0)
            self.lines.append([' '] * self.cols)
            self.scrolls += 1
        else:
            self.y += 1

    def write(self, text):
        for char in text:
            if char == '\r':
                self.x = 0
            elif char == '\n':
                self.newline()
            else:
                if self.x == self.cols:
                    self.newline()
                self.lines[self.y][self.x] = char
                self.x += 1

    def control(self, sequence):
        parameters, code = sequence[2:-1], sequence[-1]
        if parameters.startswith('?'):
            return
        values = [int(v or 0) for v in parameters.split(';')]
        if code == 'H':
            self.y = min(self.height - 1, max(0, values[0] - 1))
            self.x = min(self.cols - 1, max(0, (values[1] if len(values) > 1 else 1) - 1))
        elif code == 'C':
            self.x = min(self.cols - 1, self.x + (values[0] or 1))
        elif code == 'K':
            self.x = min(self.cols - 1, self.x)
            start = 0 if values[0] == 2 else self.x
            self.lines[self.y][start:] = [' '] * (self.cols - start)
        elif code == 'J':
            if values[0] == 2:
                self.lines = [[' '] * self.cols for _ in range(self.height)]
            else:
                self.x = min(self.cols - 1, self.x)
                self.lines[self.y][self.x :] = [' '] * (self.cols - self.x)
                for row in range(self.y + 1, self.height):
                    self.lines[row] = [' '] * self.cols

    def row(self, index):
        return ''.join(self.lines[index])


class ResizeTests(unittest.TestCase):
    def build(self, render='braille', cell_px=None):
        from termlogo.renderers import make_canvas

        canvas = make_canvas(render, 80, 16, cell_px=cell_px)
        turtle = Turtle(canvas)
        it = Interp(out=lambda text: None)
        it.attach_turtle(turtle)
        stream = io.StringIO()
        display = Display(
            it, canvas, turtle, render, False, [], stream, auto_size=True, cell_px=cell_px
        )
        return it, turtle, display

    def test_resize_keeps_scale_position_pen_and_strokes(self):
        it, turtle, display = self.build()
        it.eval_source('setscale 0.5 setpencolour "red fd 10 rt 90')
        strokes = list(turtle.strokes)
        with patch('termlogo.repl._terminal_size', return_value=os.terminal_size((100, 30))):
            display.draw()
        self.assertEqual((display.canvas.cols, display.canvas.rows), (100, 22))
        self.assertEqual(display.canvas.scale, 0.5)
        self.assertEqual((turtle.x, turtle.y, turtle.heading), (0, 10, 90))
        self.assertEqual(turtle.strokes, strokes)
        self.assertEqual(turtle.rgb, (255, 0, 0))
        px, py = display.canvas.to_pixel(0, 5)
        self.assertEqual(display.canvas.pix[py][px], turtle.rgb)

    def test_shrink_then_grow_restores_picture_and_labels(self):
        for cell in ((2, 4), (1, 2), (10, 20)):
            with self.subTest(cell=cell):
                large = Canvas(80, 16, cell=cell)
                large.plot(*large.to_pixel(60, 0), (255, 0, 0))
                large.label(*large.to_pixel(60, 0), 'edge', (255, 0, 0))
                small = Canvas(20, 8, cell=cell)
                large.copy_to(small)
                restored = Canvas(80, 16, cell=cell)
                small.copy_to(restored)
                px, py = restored.to_pixel(60, 0)
                self.assertEqual(restored.pix[py][px], (255, 0, 0))
                self.assertEqual(restored.labels, large.labels)

    def test_clean_does_not_restore_old_clipped_picture(self):
        large = Canvas(80, 16)
        large.plot(*large.to_pixel(60, 0), (255, 0, 0))
        small = Canvas(20, 8)
        large.copy_to(small)
        small.clear()
        large = Canvas(80, 16)
        small.copy_to(large)
        self.assertTrue(all(pixel is None for row in large.pix for pixel in row))

    def test_tiny_terminal_does_not_overflow_canvas_and_log(self):
        _, _, display = self.build()
        display.log[:] = ['a', 'b', 'c', 'd', 'e']
        with patch('termlogo.repl._terminal_size', return_value=os.terminal_size((20, 5))):
            display.draw()
        self.assertEqual((display.canvas.cols, display.canvas.rows), (20, 1))
        self.assertLessEqual(display.stream.getvalue().count('\n'), 4)

    def test_explicit_size_is_not_resized(self):
        _, _, display = self.build()
        display.auto_size = False
        with patch('termlogo.repl._terminal_size', return_value=os.terminal_size((100, 30))):
            display.draw()
        self.assertEqual((display.canvas.cols, display.canvas.rows), (80, 16))

    def test_kitty_resize_keeps_fallback_pixel_dimensions(self):
        _, _, display = self.build('kitty', (9, 18))
        with (
            patch('termlogo.repl._terminal_size', return_value=os.terminal_size((100, 30))),
            patch('termlogo.repl.renderers.cell_pixels', return_value=None),
        ):
            display.draw()
        self.assertEqual(display.canvas.cell, (9, 18))

    def test_kitty_redraw_removes_stale_text_but_preserves_logo_labels(self):
        _, turtle, display = self.build('kitty', (2, 4))
        display.auto_size = False
        display.fresh = False
        display.canvas.label(10, 12, 'label', turtle.rgb)
        screen = TextScreen()
        for row in range(display.canvas.rows):
            screen.lines[row][:10] = list('old prompt')
        display.draw()
        frame = display.stream.getvalue()
        self.assertNotIn('\x1b[2J', frame)
        screen.feed(frame)
        for row in range(display.canvas.rows):
            self.assertEqual(screen.row(row).strip(), 'label' if row == 3 else '')
        self.assertTrue(screen.row(display.canvas.rows).startswith(' pos ['))
        self.assertEqual(screen.scrolls, 0)
        display.canvas.clear()
        display.stream.seek(0)
        display.stream.truncate()
        display.draw()
        screen.feed(display.stream.getvalue())
        self.assertTrue(all(not screen.row(row).strip() for row in range(display.canvas.rows)))

    def test_input_pane_uses_log_space_then_shrinks_and_restores_canvas(self):
        it, turtle, display = self.build()
        it.eval_source('setspeed 0 fd 10 label "kept')
        original = [list(row) for row in display.canvas.pix]
        labels = list(display.canvas.labels)
        with patch('termlogo.repl._terminal_size', return_value=os.terminal_size((80, 24))):
            display.command_rows = 4
            display.draw()
            self.assertEqual(
                (display.canvas.rows, display.log_rows, display.input_rows), (16, 2, 4)
            )
            self.assertEqual(display.prompt_row, 20)
            display.command_rows = 10
            display.draw()
            self.assertEqual(
                (display.canvas.rows, display.log_rows, display.input_rows), (12, 0, 10)
            )
            display.command_rows = 1
            display.draw()
        self.assertEqual(display.canvas.pix, original)
        self.assertEqual(display.canvas.labels, labels)
        self.assertEqual((turtle.x, turtle.y), (0, 10))

    def test_oversized_input_is_bounded_by_terminal_height(self):
        _, _, display = self.build()
        display.command_rows = 50
        with patch('termlogo.repl._terminal_size', return_value=os.terminal_size((80, 24))):
            display.draw()
        self.assertEqual((display.canvas.rows, display.log_rows, display.input_rows), (1, 0, 21))
        self.assertEqual(display.prompt_row + display.input_rows, 24)

    def test_long_output_is_wrapped_without_losing_words(self):
        _, _, display = self.build()
        text = ' '.join(f'colour{n}' for n in range(50))
        display.log_text(text + '\n')
        self.assertGreater(len(display.log), 5)
        self.assertTrue(all(len(line) <= display.cols for line in display.log))
        self.assertEqual(' '.join(display.log), text)

    def test_pixel_resampling_does_not_leave_gaps(self):
        old = Canvas(4, 2, cell=(2, 4))
        old.plot(*old.to_pixel(0, 0), (255, 0, 0))
        bigger = Canvas(4, 2, cell=(4, 8))
        old.copy_to(bigger)
        self.assertEqual(sum(pixel is not None for row in bigger.pix for pixel in row), 4)

    def test_repeated_odd_width_resizes_do_not_shift_half_block_drawing(self):
        canvas = Canvas(80, 16, cell=(1, 2))
        canvas.plot(*canvas.to_pixel(0, 0), (255, 0, 0))
        original = [list(row) for row in canvas.pix]
        for _ in range(5):
            for cols in (81, 80):
                resized = Canvas(cols, 16, cell=(1, 2))
                canvas.copy_to(resized)
                canvas = resized
        self.assertEqual(canvas.pix, original)

    def test_filled_uses_logo_coordinates_after_resize(self):
        it, turtle, display = self.build()
        it.eval_source('setspeed 0 pu setpos [-10 -10] pd')
        original_run = it.run_list
        with patch('termlogo.repl._terminal_size', return_value=os.terminal_size((100, 30))):

            def run_and_resize(body, *args):
                result = original_run(body, *args)
                display.resize_to_terminal()
                return result

            with patch.object(it, 'run_list', side_effect=run_and_resize):
                it.eval_source('filled "red [repeat 4 [fd 20 rt 90]]')
        self.assertEqual(display.canvas.cols, 100)
        self.assertIsNone(display.canvas.pix[0][0])
        px, py = display.canvas.to_pixel(0, 0)
        self.assertEqual(display.canvas.pix[py][px], (255, 0, 0))
        px, py = display.canvas.to_pixel(-10, 0)
        self.assertEqual(display.canvas.pix[py][px], (255, 255, 255))
        self.assertAlmostEqual(turtle.x, -10)
        self.assertAlmostEqual(turtle.y, -10)


class HistoryTests(unittest.TestCase):
    def test_multiline_commands_round_trip_without_losing_newlines(self):
        commands = ['print 1', 'repeat 2 [\n print 42 ; keep this comment\n]', 'bye']
        source = Mock()
        source.get_current_history_length.return_value = len(commands)
        source.get_history_item.side_effect = commands
        target = Mock()
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / 'history')
            with patch('termlogo.repl.HISTORY', path):
                _save_history(source)
                _load_history(target)
            self.assertEqual([call.args[0] for call in target.add_history.call_args_list], commands)
            self.assertEqual(list(Path(directory).iterdir()), [Path(path)])

    def test_legacy_history_files_still_use_readline_loader(self):
        target = Mock()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'history'
            path.write_text('print 1\nprint 2\n')
            with patch('termlogo.repl.HISTORY', str(path)):
                _load_history(target)
            target.read_history_file.assert_called_once_with(str(path))
            target.add_history.assert_not_called()

    def test_invalid_new_history_is_not_silently_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'history'
            for contents in ('{broken', '[1]'):
                path.write_text(HISTORY_HEADER + contents)
                with patch('termlogo.repl.HISTORY', str(path)), self.assertRaises(ValueError):
                    _load_history(Mock())

    def test_failed_history_save_preserves_existing_file_and_reports_error(self):
        source = Mock()
        source.get_current_history_length.return_value = 0
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'history'
            path.write_text('existing history')
            with patch('termlogo.repl.HISTORY', str(path)):
                with patch('termlogo.repl.os.replace', side_effect=OSError('write failed')):
                    stderr = io.StringIO()
                    with contextlib.redirect_stderr(stderr):
                        _save_history(source)
            self.assertIn('Could not save command history', stderr.getvalue())
            self.assertEqual(path.read_text(), 'existing history')
            self.assertEqual(list(Path(directory).iterdir()), [path])


class CLITests(unittest.TestCase):
    def test_speed_default_is_five_without_animation(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(['-e', 'print speed', '--no-canvas']), 0)
        self.assertEqual(output.getvalue(), '5\n')

    def test_validation_precedes_repl(self):
        for args in (
            ['--speed', '-1'],
            ['--speed', 'nan'],
            ['--scale', '0'],
            ['--scale', 'inf'],
            ['--size', '0x10'],
            ['--size', '-1x4'],
        ):
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()):
                with patch('termlogo.__main__.repl') as enter_repl:
                    with self.assertRaises(SystemExit) as raised:
                        main(args)
                    self.assertEqual(raised.exception.code, 2)
                    enter_repl.assert_not_called()

    def test_interactive_script_retains_interpreter(self):
        with patch('termlogo.__main__.repl', return_value=0) as enter_repl:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(['-e', 'make "value 42 fd 5', '--no-canvas', '-i']), 0)
        it = enter_repl.call_args.kwargs['interpreter']
        self.assertEqual(it.lookup('value'), 42)
        self.assertEqual(it.turtle.y, 5)
        self.assertEqual(it.turtle.speed, 5)

    def test_non_finite_turtle_inputs_are_logo_errors(self):
        it = Interp(out=lambda text: None)
        it.attach_turtle(Turtle(Canvas(10, 5)))
        for source in ('fd 1e999', 'setscale 1e999', 'setpensize 1e999'):
            with self.subTest(source=source), self.assertRaises(LogoError):
                it.eval_source(source)


@unittest.skipUnless(os.name == 'posix', 'requires a POSIX terminal')
class ControlTests(unittest.TestCase):
    def test_session_restores_terminal_and_callbacks_after_interrupt(self):
        import pty
        import termios

        master, slave = pty.openpty()
        turtle = Turtle(Canvas(10, 5))
        it = Interp()
        before = termios.tcgetattr(slave)
        try:
            with os.fdopen(os.dup(slave), 'r') as stream:
                with patch('sys.stdin', stream), contextlib.redirect_stdout(io.StringIO()):
                    with self.assertRaises(KeyboardInterrupt):
                        with drawing_controls(turtle, True, it):
                            active = termios.tcgetattr(slave)
                            self.assertFalse(active[3] & (termios.ECHO | termios.ICANON))
                            raise KeyboardInterrupt
            after = termios.tcgetattr(slave)
            # macOS sets PENDIN when canonical input is restored.
            pending = getattr(termios, 'PENDIN', 0)
            after[3] &= ~pending
            before[3] &= ~pending
            self.assertEqual(after, before)
            self.assertIsNone(turtle.input_cb)
            self.assertIsNone(it.on_poll)
            self.assertIsNone(it.on_wait)
        finally:
            os.close(master)
            os.close(slave)

    def test_arrow_keys_do_not_cancel_or_leave_sequence_bytes(self):
        read_fd, write_fd = os.pipe()
        try:
            controls = DrawingControls(Turtle(Canvas(20, 10)), read_fd)
            os.write(write_fd, b'\x1b[A\x1b[3~\x1bOP')
            self.assertFalse(controls(0))
            self.assertFalse(select.select([read_fd], [], [], 0)[0])
        finally:
            os.close(read_fd)
            os.close(write_fd)

    def test_mouse_mapping_and_filtering_in_every_renderer(self):
        for cell in ((2, 4), (1, 2), (9, 18)):
            turtle = Turtle(Canvas(20, 10, scale=0.5, cell=cell))
            controls = DrawingControls(turtle, -1)
            with self.subTest(cell=cell):
                for invalid in (
                    b'0;11;6m',
                    b'64;11;6M',
                    b'2;11;6M',
                    b'0;21;6M',
                    b'0;11;11M',
                    b'bad',
                    b'4;11;6M',
                    b'36;11;6M',
                    b'12;11;6M',
                ):
                    self.assertFalse(controls._mouse(invalid))
                self.assertTrue(controls._mouse(b'32;11;6M'))
                self.assertEqual(turtle.x, 2)
                self.assertEqual(turtle.y, -cell[1] / turtle.canvas.scale / 2)
                self.assertTrue(turtle.pen_down)
                self.assertEqual(turtle.strokes, [])

    def edit_line(self, events, cols=20, prompt='? ', initial='', history=()):
        turtle = Turtle(Canvas(cols, 10))
        turtle.x, turtle.y = 3, 4
        it = Interp()
        it.attach_turtle(turtle)
        display = Display(it, turtle.canvas, turtle, 'braille', False, [], io.StringIO())
        controls = DrawingControls(turtle, -1, display)
        output = io.StringIO()
        with patch.object(controls, 'read_event', side_effect=events):
            with (
                patch('readline.get_current_history_length', return_value=len(history)),
                patch('readline.get_history_item', side_effect=lambda index: history[index - 1]),
                patch('termlogo.repl._terminal_size', return_value=os.terminal_size((cols, 18))),
                contextlib.redirect_stdout(output),
            ):
                result = controls.readline(prompt, it, initial)
        self.assertEqual((turtle.x, turtle.y), (3, 4))
        self.assertEqual(turtle.strokes, [])
        return result, output.getvalue()

    def test_prompt_click_moves_editing_cursor_without_moving_turtle(self):
        result, output = self.edit_line([b'print 42', b'\x1b[<0;9;17M', b'9', b'\r'])
        self.assertEqual(result, 'print 942')
        self.assertNotIn('\n', output)
        self.assertIn('\x1b[17;1H', output)

    def test_history_newlines_are_rendered_without_scrolling(self):
        result, output = self.edit_line([b'\x1b[A', b'\r'], history=['a\nb'])
        self.assertEqual(result, 'a\nb')
        self.assertIn('? a', output)
        self.assertIn('\x1b[17;1H\r\x1b[K> b', output)
        self.assertNotIn('\n', output)

    def test_multiline_history_down_restores_the_whole_draft(self):
        draft = 'repeat 1 [\nprint 9\n'
        result, output = self.edit_line(
            [b'\x1b[A', b'\x1b[A', b'\x1b[A', b'\x1b[B', b']', b'\r'],
            initial=draft,
            history=['print 42'],
        )
        self.assertIn('? print 42', output)
        self.assertEqual(result, draft + ']')

    def test_arrows_move_between_rows_of_a_recalled_multiline_command(self):
        command = 'repeat 2 [\n  fd 10\n  rt 90\n]'
        result, _ = self.edit_line(
            [b'\x1b[A', b'\x1b[A', b'\x05', b'\x7f', b'\x7f', b'45', b'\x1b[B', b' ', b'\r'],
            history=[command],
        )
        self.assertEqual(result, 'repeat 2 [\n  fd 10\n  rt 45\n] ')

    def test_up_from_the_first_row_and_down_from_the_last_step_through_history(self):
        result, _ = self.edit_line(
            [b'\x1b[A', b'\x1b[A', b'\x1b[A', b'\r'], history=['print 1', 'a\nb']
        )
        self.assertEqual(result, 'print 1')
        result, _ = self.edit_line(
            [b'\x1b[A', b'\x1b[A', b'\x1b[B', b'\x1b[B', b'draft', b'\r'],
            history=['print 1', 'a\nb'],
        )
        self.assertEqual(result, 'draft')

    def test_history_keys_skip_the_rows_of_a_multiline_command(self):
        history = ['print 1', 'a\nb']
        result, _ = self.edit_line([b'\x1b[A', b'\x10', b'\r'], history=history)
        self.assertEqual(result, 'print 1')
        result, _ = self.edit_line([b'\x1b[5~', b'\x1b[5~', b'\x1b[6~', b'\r'], history=history)
        self.assertEqual(result, 'a\nb')
        result, _ = self.edit_line([b'\x10', b'\x10', b'\x0e', b'\x0e', b'\r'], history=history)
        self.assertEqual(result, '')

    def test_edits_to_recalled_commands_survive_moving_through_history(self):
        result, _ = self.edit_line(
            [b'draft', b'\x1b[A', b'2', b'\x1b[B', b'!', b'\x1b[A', b'\r'], history=['print 1']
        )
        self.assertEqual(result, 'print 12')

    def test_vertical_moves_keep_their_column_across_a_short_row(self):
        result, _ = self.edit_line(
            [b'\x1b[A', b'\x1b[A', b'X', b'\r'], initial='abcdef\nxy\nabcdef'
        )
        self.assertEqual(result, 'abcdefX\nxy\nabcdef')
        result, _ = self.edit_line([b'\x1b[A', b'X', b'\r'], initial='abcdef\nxy\nabcdef')
        self.assertEqual(result, 'abcdef\nxyX\nabcdef')

    def test_arrows_move_between_wrapped_rows_without_sticking(self):
        line = '0123456789012345678901234567890123'
        result, _ = self.edit_line([line.encode(), b'\x1b[A', b'\x1b[A', b'X', b'\r'])
        self.assertEqual(result, line[:16] + 'X' + line[16:])
        result, _ = self.edit_line([line[:30].encode(), b'\x1b[A', b'\x1b[B', b'X', b'\r'])
        self.assertEqual(result, line[:30] + 'X')

    def test_alt_and_shift_enter_add_a_line_instead_of_running(self):
        for key in (b'\x1b\r', b'\x1b\n', b'\x1b[13;2u', b'\x1b[27;2;13~'):
            with self.subTest(key=key):
                result, output = self.edit_line([b'fd 10rt 90', b'\x1b[<0;8;17M', key, b'\r'])
                self.assertEqual(result, 'fd 10\nrt 90')
                self.assertIn('> rt 90', output)

    def test_home_and_end_work_by_line_then_by_command(self):
        events = [b'\x01', b'X', b'\x01', b'\x01', b'Y', b'\x05', b'Z', b'\x05', b'W', b'\r']
        result, _ = self.edit_line(events, initial='ab\ncd')
        self.assertEqual(result, 'YabZ\nXcdW')

    def test_kill_keys_stay_within_the_current_line(self):
        result, _ = self.edit_line([b'\x1b[A', b'\x15', b'\r'], initial='ab\ncd\nef')
        self.assertEqual(result, 'ab\n\nef')
        result, _ = self.edit_line([b'\x1b[A', b'\x15', b'\x0b', b'\r'], initial='ab\ncd\nef')
        self.assertEqual(result, 'ab\nef')
        result, _ = self.edit_line([b'\x1b[A', b'\x02', b'\x0b', b'\r'], initial='ab\ncd\nef')
        self.assertEqual(result, 'ab\nc\nef')

    def test_mouse_edits_earlier_line_of_multiline_command(self):
        result, output = self.edit_line(
            [b'\x1b[<0;9;16M', b'9', b'\r'], initial='print 42\nprint 8'
        )
        self.assertEqual(result, 'print 942\nprint 8')
        self.assertIn('? print 942', output)
        self.assertIn('> print 8', output)

    def test_completion_stops_at_a_source_newline(self):
        result, _ = self.edit_line([b'\t', b'\r'], initial='print\nspe')
        self.assertEqual(result, 'print\nspeed')

    def test_oversized_command_scrolls_to_the_editing_cursor(self):
        source = '\n'.join(f'print {number}' for number in range(36))
        result, output = self.edit_line([b'\x01', b'\x01', b'X', b'\r'], initial=source)
        self.assertEqual(result, 'X' + source)
        screen = TextScreen()
        screen.feed(output)
        self.assertEqual(screen.scrolls, 0)
        self.assertEqual(screen.row(11).strip(), '? Xprint 0')
        self.assertEqual(screen.row(16).strip(), '> print 5')

    def test_mouse_edits_a_wrapped_row_without_inserting_newlines(self):
        line = '012345678901234567890123456789'
        result, output = self.edit_line([line.encode(), b'\x1b[<0;6;17M', b'X', b'\r'])
        self.assertEqual(result, line[:20] + 'X' + line[20:])
        self.assertIn('> ' + line[17:20] + 'X' + line[20:], output)
        self.assertIn('\x1b[6C', output)

    def test_paste_preserves_newlines_and_inserts_at_the_cursor(self):
        result, output = self.edit_line(
            [b'\x01', PASTE_START, b'clearscreen\r\n', PASTE_END, b'\r'],
            initial='print 42',
        )
        self.assertEqual(result, 'clearscreen\nprint 42')
        self.assertIn(PASTE_ON, output)
        self.assertTrue(output.endswith(PASTE_OFF))

    def test_pasted_tabs_keep_source_and_mouse_columns_correct(self):
        result, output = self.edit_line(
            [
                PASTE_START,
                'a\u754c\tb'.encode(),
                PASTE_END,
                b'\x1b[<0;9;17M',
                b'X',
                b'\r',
            ]
        )
        self.assertEqual(result, 'a\u754c\tXb')
        self.assertIn('? a\u754c   Xb', output)
        self.assertNotIn('\t', output)

    def test_paste_rejects_terminal_control_sequences(self):
        with self.assertRaisesRegex(LogoError, 'control characters'):
            self.edit_line([PASTE_START, b'print 42\x1b]52;;clipboard\x07', PASTE_END])

    def test_paste_rejects_invalid_terminal_encoding(self):
        with self.assertRaisesRegex(LogoError, 'terminal encoding'):
            self.edit_line([PASTE_START, b'\xff', PASTE_END])

    def test_pasted_tabs_do_not_overflow_a_narrow_window(self):
        result, output = self.edit_line([PASTE_START, b'\tword', PASTE_END, b'\r'], cols=4)
        self.assertEqual(result, '\tword')
        screen = TextScreen(cols=4, rows=18)
        screen.feed(output)
        self.assertEqual(screen.scrolls, 0)

    def test_prompt_prefix_and_blank_space_clicks_clamp_to_input(self):
        result, _ = self.edit_line([b'ab', b'\x1b[<0;1;17M', b'X', b'\x1b[<0;20;17M', b'Y', b'\r'])
        self.assertEqual(result, 'XabY')

    def test_logs_shift_drag_releases_and_other_buttons_do_not_edit_input(self):
        ignored = [
            b'\x1b[<0;3;12M',
            b'\x1b[<0;3;18M',
            b'\x1b[<0;21;17M',
            b'\x1b[<4;3;17M',
            b'\x1b[<36;3;17M',
            b'\x1b[<32;3;17M',
            b'\x1b[<0;3;17m',
            b'\x1b[<2;3;17M',
            b'\x1b[<64;3;17M',
        ]
        result, _ = self.edit_line([b'print 42', *ignored, b'9', b'\r'])
        self.assertEqual(result, 'print 429')

    def test_mouse_cursor_uses_wide_and_combining_character_cells(self):
        for line, col, expected in (
            ('a\u754cb', 6, 'a\u754cXb'),
            ('ae\u0301b', 5, 'ae\u0301Xb'),
        ):
            with self.subTest(line=line):
                result, _ = self.edit_line(
                    [line.encode(), f'\x1b[<0;{col};17M'.encode(), b'X', b'\r']
                )
                self.assertEqual(result, expected)

    def test_shift_mouse_does_not_interrupt_or_reposition_drawing(self):
        read_fd, write_fd = os.pipe()
        try:
            turtle = Turtle(Canvas(20, 10))
            controls = DrawingControls(turtle, read_fd)
            os.write(write_fd, b'\x1b[<4;11;6M\x1b[<36;12;6M')
            self.assertFalse(controls(0))
            self.assertEqual((turtle.x, turtle.y), (0, 0))
        finally:
            os.close(read_fd)
            os.close(write_fd)

    def test_mouse_reposition_is_not_overwritten_by_home_or_setheading(self):
        for command in ('home', 'seth 0'):
            turtle = Turtle(Canvas(20, 10))
            turtle.x, turtle.y, turtle.heading = 10, 10, 180
            turtle.frame_cb = lambda: None

            def clicked(_seconds, turtle=turtle):
                turtle.x, turtle.y = 1, -2
                return True

            turtle.input_cb = clicked
            it = Interp()
            it.attach_turtle(turtle)
            it.eval_source(command)
            self.assertEqual((turtle.x, turtle.y), (1, -2))
            self.assertNotEqual(turtle.heading, 0)


class TerminalProcess:
    def __init__(self, *args, history=None):
        import pty

        self.master, self.slave = pty.openpty()
        self.home = tempfile.TemporaryDirectory()
        if history is not None:
            (Path(self.home.name) / '.termlogo_history').write_text(history, encoding='utf-8')
        self.resize(80, 24)
        env = dict(
            os.environ,
            HOME=self.home.name,
            TERM='xterm-256color',
            COLUMNS='80',
            LINES='24',
            TERMLOGO_RENDER='braille',
        )
        self.process = subprocess.Popen(
            [sys.executable, '-m', 'termlogo', '--render', 'braille', '--no-colour', *args],
            stdin=self.slave,
            stdout=self.slave,
            stderr=self.slave,
            cwd=ROOT,
            env=env,
            close_fds=True,
        )
        self.output = b''
        self.buffer = bytearray()

    def resize(self, cols, rows):
        import fcntl
        import struct
        import termios

        fcntl.ioctl(self.master, termios.TIOCSWINSZ, struct.pack('HHHH', rows, cols, 0, 0))

    def send(self, data):
        os.write(self.master, data if isinstance(data, bytes) else data.encode('utf-8'))

    def expect_prompt(self, row=23):
        return self.expect(f'\x1b[{row};1H\r\x1b[K? \x1b[{row};1H\r\x1b[2C\x1b[?25h'.encode())

    def expect(self, needle, timeout=3):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            index = self.buffer.find(needle)
            if index >= 0:
                end = index + len(needle)
                result = bytes(self.buffer[:end])
                del self.buffer[:end]
                return result
            if select.select([self.master], [], [], 0.05)[0]:
                try:
                    chunk = os.read(self.master, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                self.buffer.extend(chunk)
                self.output += chunk
        raise AssertionError(f'No {needle!r} in terminal output: {bytes(self.buffer[-2000:])!r}')

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=2)
        os.close(self.master)
        os.close(self.slave)
        self.home.cleanup()

    def wait(self, timeout=3):
        deadline = time.monotonic() + timeout
        while self.process.poll() is None and time.monotonic() < deadline:
            if select.select([self.master], [], [], 0.05)[0]:
                self.output += os.read(self.master, 65536)
        return self.process.wait(timeout=max(0.1, deadline - time.monotonic()))


@unittest.skipUnless(os.name == 'posix', 'requires a POSIX pseudo-terminal')
class LiveTerminalTests(unittest.TestCase):
    def start(self, *args, history=None):
        terminal = TerminalProcess(*args, history=history)
        self.addCleanup(terminal.close)
        terminal.expect(b'? ')
        return terminal

    def screen_text(self, terminal):
        screen = TextScreen()
        screen.feed(terminal.output)
        return '\n'.join(screen.row(row) for row in range(24))

    def test_startup_banner_is_shown_until_first_command(self):
        terminal = self.start('--render', 'kitty')
        text = self.screen_text(terminal)
        self.assertIn(f'termlogo {__version__} by {__author__}', text)
        self.assertIn('HELP for commands', text)
        self.assertIn('Shift-drag selects text', text)
        terminal.send('print 42\n')
        terminal.expect(b'42\x1b[K')
        terminal.expect_prompt()
        text = self.screen_text(terminal)
        self.assertNotIn(f'termlogo {__version__}', text)
        self.assertNotIn('HELP for commands', text)
        self.assertNotIn('Shift-drag selects text', text)
        self.assertIn('42', text)

    def test_startup_banner_remains_for_blank_and_comment_lines(self):
        terminal = self.start('--render', 'kitty')
        for line in ('', '  ; a comment'):
            terminal.send(line + '\n')
            terminal.expect(b'\x1b[?1002l')
            terminal.expect(b'\x1b[?1002h')
            terminal.expect(b'\x1b[?1002l')
            terminal.expect_prompt()
            self.assertIn('Shift-drag selects text', self.screen_text(terminal))

    def test_startup_banner_remains_during_multiline_input_and_cancellation(self):
        terminal = self.start('--render', 'kitty')
        self.submit_incomplete(terminal, 'to answer')
        for _ in range(8):
            self.submit_incomplete(terminal, '; keep typing')
        text = self.screen_text(terminal)
        self.assertIn(f'termlogo {__version__}', text)
        self.assertIn('Shift-drag selects text', text)
        terminal.send(b'\x1b')
        terminal.expect_prompt()
        self.assertIn('Shift-drag selects text', self.screen_text(terminal))

    def test_startup_banner_clears_when_execution_starts_not_when_it_finishes(self):
        terminal = self.start('--render', 'kitty')
        terminal.send('forever []\n')
        terminal.expect(b'\x1b[?1002l')
        terminal.expect(b'\x1b[?1002h')
        terminal.expect(b'\x1b[?2026l')
        self.assertNotIn('Shift-drag selects text', self.screen_text(terminal))
        terminal.send(b'\x1b')
        terminal.expect(b'Stopped!\x1b[K')
        terminal.expect_prompt()
        self.assertNotIn('Shift-drag selects text', self.screen_text(terminal))

    def test_whole_pasted_circle_program_is_recalled_including_initial_commands(self):
        terminal = self.start('--render', 'kitty', '--speed', '0')
        self.assertIn(PASTE_ON.encode(), terminal.output)
        terminal.send(PASTE_START + CIRCLE_PROGRAM.encode() + PASTE_END)
        terminal.expect(b'? clearscreen')
        terminal.expect(b'> make "dist 1')
        terminal.expect(b'> ]')
        self.assertIn('Shift-drag selects text', self.screen_text(terminal))
        terminal.send('\n')
        terminal.expect_prompt()
        terminal.send(b'\x1b[A')
        terminal.expect(b'? clearscreen')
        terminal.expect(b'> make "dist 1')
        terminal.expect(b'> ]')
        text = self.screen_text(terminal)
        for line in CIRCLE_PROGRAM.splitlines():
            self.assertIn(line, text)
        terminal.send('\n')
        terminal.expect_prompt()
        terminal.send('print :dist\n')
        terminal.expect(b'2\x1b[K')
        terminal.expect_prompt()
        terminal.send('bye\n')
        self.assertEqual(terminal.wait(), 0)
        with open(Path(terminal.home.name) / '.termlogo_history') as history_file:
            self.assertEqual(history_file.readline(), HISTORY_HEADER)
            commands = json.load(history_file)
        self.assertEqual(commands[:2], [CIRCLE_PROGRAM, CIRCLE_PROGRAM])

    def test_invalid_paste_is_reported_without_executing_it(self):
        terminal = self.start('--render', 'kitty')
        terminal.send(PASTE_START + b'print 42\x07' + PASTE_END)
        terminal.expect(b'Pasted text contains unsupported control characters')
        terminal.expect_prompt()
        self.assertIn('Shift-drag selects text', self.screen_text(terminal))
        terminal.send('print 42\n')
        terminal.expect(b'42\x1b[K')

    def test_startup_guidance_does_not_hide_errors_in_a_narrow_window(self):
        terminal = self.start('--render', 'kitty')
        terminal.resize(40, 24)
        terminal.expect(b'\x1b[2J\x1b[H')
        terminal.expect_prompt()
        terminal.send(PASTE_START + b'print 42\x07' + PASTE_END)
        terminal.expect(b'Pasted text contains unsupported')
        terminal.expect(b'characters\x1b[K')
        terminal.expect_prompt()
        text = ' '.join(self.screen_text(terminal).split())
        self.assertIn('Shift-drag selects text', text)
        self.assertIn('Pasted text contains unsupported control characters', text)

    def test_resize_idle_preserves_partially_typed_command(self):
        terminal = self.start()
        terminal.send('print "kept')
        terminal.expect(b'kept')
        terminal.resize(100, 30)
        terminal.expect(b'\x1b[2J\x1b[H')
        redrawn = terminal.expect(b'\x1b[?2026l')
        frame_bytes = redrawn.rsplit(b'\x1b[?2026h', 1)[-1].split(b'\x1b[?2026l', 1)[0]
        frame = ANSI.sub('', frame_bytes.decode('utf-8'))
        self.assertEqual(
            frame.splitlines().index(
                next(line for line in frame.splitlines() if line.startswith(' pos ['))
            ),
            22,
        )
        terminal.send('\n')
        terminal.expect(b'kept\x1b[K')
        terminal.send('bye\n')
        self.assertEqual(terminal.wait(), 0)

    def test_idle_mouse_preserves_typed_command_and_moves_turtle(self):
        terminal = self.start('--speed', '0')
        terminal.send('print pos')
        terminal.expect(b'print pos')
        terminal.send(b'\x1b[<0;40;10M')
        terminal.expect(b' pos [-1 -6]')
        terminal.send('\n')
        terminal.expect(b'-1 -6\x1b[K')

    def test_prompt_click_places_cursor_for_command_editing(self):
        terminal = self.start('--speed', '0')
        terminal.send('print 42')
        terminal.expect(b'print 42')
        terminal.send(b'\x1b[<0;9;23M9\n')
        terminal.expect(b'942\x1b[K')
        terminal.send('print pos\n')
        terminal.expect(b'0 0\x1b[K')

    def test_prompt_click_uses_new_row_after_resize(self):
        terminal = self.start()
        terminal.send('print 42')
        terminal.expect(b'print 42')
        terminal.resize(40, 30)
        terminal.expect(b'\x1b[2J\x1b[H')
        terminal.expect(b'? print 42')
        terminal.send(b'\x1b[<0;9;29M9\n')
        terminal.expect(b'942\x1b[K')

    def submit_incomplete(self, terminal, line):
        terminal.send(line + '\n')
        terminal.expect(b'\x1b[?1002l')
        terminal.expect(b'\x1b[?1002h')
        terminal.expect(b'\x1b[?1002l')
        terminal.expect(b'\x1b[23;1H\r\x1b[K> ')
        terminal.expect(b'\x1b[?25h')

    def test_multiline_input_never_scrolls_text_over_kitty_canvas(self):
        terminal = self.start('--render', 'kitty', '--speed', '0')
        self.submit_incomplete(terminal, 'repeat 1 [')
        for _ in range(30):
            self.submit_incomplete(terminal, 'make "unused 1')
            screen = TextScreen()
            screen.feed(terminal.output)
            self.assertEqual(screen.scrolls, 0)
            status_row = next(row for row in range(24) if screen.row(row).startswith(' pos ['))
            self.assertTrue(all(not screen.row(row).strip() for row in range(status_row)))
            self.assertEqual(screen.row(22).strip(), '>')
        terminal.send(']\n')
        terminal.expect(b'? ')
        terminal.send('bye\n')
        self.assertEqual(terminal.wait(), 0)

    def test_up_recalls_whole_multiline_command_and_keeps_comments(self):
        terminal = self.start('--speed', '0')
        self.submit_incomplete(terminal, 'repeat 1 [')
        self.submit_incomplete(terminal, 'print 42 ; keep this comment')
        terminal.send(']\n')
        terminal.expect(b'42\x1b[K')
        terminal.expect(b'? ')
        terminal.send(b'\x1b[A\x01\x01')
        terminal.expect(b'> print 42 ; keep this comment')
        terminal.expect(b'> ]')
        terminal.expect(b'\x1b[21;1H\r\x1b[2C')
        terminal.send(b'\n')
        terminal.expect(b'42\x1b[K')
        terminal.send('bye\n')
        self.assertEqual(terminal.wait(), 0)
        with open(Path(terminal.home.name) / '.termlogo_history') as history_file:
            self.assertEqual(history_file.readline(), HISTORY_HEADER)
            commands = json.load(history_file)
        command = 'repeat 1 [\nprint 42 ; keep this comment\n]'
        self.assertEqual(commands, [command, command, 'bye'])

    def test_recalled_command_replaces_an_incomplete_input_buffer(self):
        terminal = self.start('--speed', '0')
        terminal.send('print 42\n')
        terminal.expect(b'42\x1b[K')
        terminal.expect(b'? ')
        self.submit_incomplete(terminal, 'repeat 1 [')
        terminal.send(b'\x1b[A\x1b[A')
        terminal.expect(b'\x1b[23;1H\r\x1b[K? print 42')
        terminal.send('\n')
        terminal.expect_prompt()
        self.assertNotIn(b'Internal error', terminal.output)
        terminal.send('bye\n')
        self.assertEqual(terminal.wait(), 0)
        with open(Path(terminal.home.name) / '.termlogo_history') as history_file:
            history_file.readline()
            self.assertEqual(json.load(history_file), ['print 42', 'print 42', 'bye'])

    def test_arrow_keys_edit_an_earlier_line_of_a_recalled_command(self):
        terminal = self.start('--speed', '0')
        self.submit_incomplete(terminal, 'repeat 1 [')
        self.submit_incomplete(terminal, 'print 42')
        terminal.send(']\n')
        terminal.expect(b'42\x1b[K')
        terminal.expect_prompt()
        terminal.send(b'\x1b[A')
        terminal.expect(b'> ]')
        terminal.send(b'\x1b[A\x050')
        terminal.expect(b'\x1b[22;1H\r\x1b[K> print 420')
        terminal.send(b'\x1b\rprint 7')
        terminal.expect(b'\x1b[22;1H\r\x1b[K> print 7')
        terminal.send('\n')
        terminal.expect(b'420\x1b[K')
        terminal.expect(b'7\x1b[K')
        terminal.send('bye\n')
        self.assertEqual(terminal.wait(), 0)
        with open(Path(terminal.home.name) / '.termlogo_history') as history_file:
            history_file.readline()
            commands = json.load(history_file)
        self.assertEqual(commands[1], 'repeat 1 [\nprint 420\nprint 7\n]')

    def test_multiline_history_is_loaded_from_disk_as_one_command(self):
        command = 'repeat 1 [\nprint 42 ; keep this comment\n]'
        terminal = self.start('--speed', '0', history=HISTORY_HEADER + json.dumps([command]))
        terminal.send(b'\x1b[A')
        terminal.expect(b'> print 42 ; keep this comment')
        terminal.send('\n')
        terminal.expect(b'42\x1b[K')

    def test_invalid_history_is_reported_in_the_command_window(self):
        terminal = self.start(history=HISTORY_HEADER + '[1]')
        self.assertIn(b'Could not load command history', terminal.output)
        terminal.send('print 42\n')
        terminal.expect(b'42\x1b[K')

    def test_mouse_edits_a_previous_continuation_line(self):
        terminal = self.start('--speed', '0')
        self.submit_incomplete(terminal, 'repeat 1 [')
        self.submit_incomplete(terminal, 'print 42')
        terminal.send(b'\x1b[<0;9;22M9\x05]\n')
        terminal.expect(b'942\x1b[K')

    def test_up_recalls_and_edits_a_complete_procedure_definition(self):
        terminal = self.start('--speed', '0')
        self.submit_incomplete(terminal, 'to answer')
        for _ in range(6):
            self.submit_incomplete(terminal, '; keep this line')
        self.submit_incomplete(terminal, 'output 42')
        terminal.send('end\n')
        terminal.expect_prompt()
        terminal.send(b'\x1b[A')
        terminal.expect(b'> output 42')
        terminal.expect(b'> end')
        terminal.send(b'\x1b[<0;10;22M9\n')
        terminal.expect_prompt()
        terminal.send('print answer\n')
        terminal.expect(b'942\x1b[K')

    def test_resize_reflows_complete_command_and_keeps_mouse_positions(self):
        terminal = self.start('--speed', '0')
        word = 'abcdefghij' * 10
        terminal.send('print "' + word)
        terminal.expect(b'> ' + word[70:].encode())
        terminal.resize(40, 30)
        terminal.expect(b'\x1b[2J\x1b[H')
        terminal.expect(b'> ' + word[67:].encode())
        terminal.send(b'\x1b[<0;10;27MX\n')
        terminal.expect(b'X' + word[:39].encode() + b'\x1b[K')

    def test_oversized_command_reflows_when_only_available_rows_change(self):
        command = '\n'.join(f'make "unused {number}' for number in range(30))
        terminal = self.start('--render', 'kitty', history=HISTORY_HEADER + json.dumps([command]))
        terminal.send(b'\x1b[A')
        terminal.expect(b'> make "unused 29')
        terminal.expect(b'\x1b[?2026l')
        terminal.resize(80, 25)
        terminal.expect(b'\x1b[24;1H\r\x1b[K> make "unused 29')

    def test_long_readword_restores_canvas_before_execution_resumes(self):
        terminal = self.start('--render', 'kitty', '--speed', '0')
        terminal.send('print count readword\n')
        terminal.expect(b'\x1b[?1002l')
        terminal.expect(b'\x1b[?1002h')
        terminal.expect(b'\x1b[23;1H\r\x1b[K')
        terminal.expect(b'\x1b[?25h')
        terminal.send('a' * 500 + '\n')
        terminal.expect(b'500\x1b[K')
        terminal.expect(b'? ')
        screen = TextScreen()
        screen.feed(terminal.output)
        self.assertTrue(screen.row(16).startswith(' pos ['))

    def test_multiline_continuation_keeps_mouse_editing_on_command_row(self):
        terminal = self.start('--speed', '0')
        self.submit_incomplete(terminal, 'repeat 1 [')
        terminal.send('print 42')
        terminal.expect(b'> print 42')
        terminal.send(b'\x1b[<0;9;23M9\n')
        terminal.expect(b'\x1b[?1002l')
        terminal.expect(b'\x1b[?1002h')
        terminal.expect(b'\x1b[?1002l')
        terminal.expect(b'> ')
        terminal.send(']\n')
        terminal.expect(b'942\x1b[K')

    def test_prompt_click_edits_scrolled_command_without_losing_text(self):
        terminal = self.start()
        word = 'abcdefghij' * 10
        terminal.send('print "' + word)
        terminal.expect(b'> ' + word[70:].encode())
        terminal.send(b'\x1b[<0;3;23MX\n')
        terminal.expect(b'Xabcdefghi\x1b[K')

    def test_readword_input_can_be_edited_with_mouse(self):
        terminal = self.start()
        terminal.send('print readword\n')
        terminal.expect(b'\x1b[?1002l')
        terminal.expect(b'\x1b[?1002h')
        terminal.expect(b'\x1b[23;1H\r\x1b[K')
        terminal.expect(b'\x1b[?25h')
        terminal.send('colour')
        terminal.expect(b'\r\x1b[Kcolour')
        terminal.send(b'\x1b[<0;2;23MAX\n')
        terminal.expect(b'cAXolour\x1b[K')

    def test_escape_stops_moves_waits_empty_loops_and_tail_calls(self):
        commands = ('fd 1000', 'wait 600', 'forever []', 'to spin spin end spin')
        for command in commands:
            with self.subTest(command=command):
                terminal = self.start()
                terminal.send(command + '\n')
                terminal.expect(b'\x1b[?1002h')
                terminal.send(b'\x1b')
                terminal.expect(b'Stopped!\x1b[K')
                terminal.send('print 42\n')
                terminal.expect(b'42\x1b[K')

    def test_escape_still_works_after_changing_speed_from_zero(self):
        terminal = self.start('--speed', '0')
        terminal.send('setspeed 5 fd 1000\n')
        terminal.expect(b' speed 5')
        terminal.send(b'\x1b')
        terminal.expect(b'Stopped!\x1b[K')

    def test_mouse_during_motion_stops_current_segment(self):
        terminal = self.start()
        terminal.send('fd 1000 print pos\n')
        terminal.expect(b' pos [0 8]')
        terminal.send(b'\x1b[<0;40;10M')
        terminal.expect(b'-1 -6\x1b[K')

    def test_completion_history_editing_and_readword(self):
        terminal = self.start()
        terminal.send('print spe\t\n')
        terminal.expect(b'5\x1b[K')
        terminal.send(b'\x1b[A\n')
        terminal.expect(b'5\x1b[K')
        terminal.send('print readword\n')
        terminal.expect(b'\x1b[?1002h')
        terminal.send('colour\n')
        terminal.expect(b'colour\x1b[K')

    def test_resize_during_drawing_and_arrow_keys_do_not_stop_it(self):
        terminal = self.start()
        terminal.send('fd 1000\n')
        terminal.expect(b' pos [0 8]')
        terminal.send(b'\x1b[A')
        terminal.resize(100, 30)
        terminal.expect(b'\x1b[2J\x1b[H')
        terminal.expect(b' speed 5')
        self.assertNotIn(b'Stopped!', terminal.output)
        terminal.send(b'\x1b')
        terminal.expect(b'Stopped!\x1b[K')

    def test_half_renderer_resizes_at_idle_prompt(self):
        terminal = self.start('--render', 'half')
        terminal.resize(101, 30)
        terminal.expect(b'\x1b[2J\x1b[H')
        redrawn = terminal.expect(b'\x1b[?2026l')
        frame = ANSI.sub('', redrawn.decode('utf-8'))
        lines = frame.splitlines()
        status = next(index for index, line in enumerate(lines) if line.startswith(' pos ['))
        self.assertEqual(status, 22)
        self.assertEqual(len(lines[0]), 101)

    def test_script_interactive_keeps_procedures_variables_and_picture(self):
        terminal = self.start(
            '--speed', '0', '-e', 'make "value 42 to answer output :value end fd 5', '-i'
        )
        terminal.send('print answer print pos\n')
        terminal.expect(b'0 5\x1b[K')
        self.assertIn(b'42\x1b[K', terminal.output)

    def test_terrapin_colours_survive_script_resize_and_mouse_controls(self):
        terminal = self.start(
            '--colour-mode',
            'terrapin',
            '--speed',
            '0',
            '-e',
            'setpc [255 0 0 0.5] fd 5',
            '-i',
        )
        terminal.send('pc bg count colours\n')
        terminal.expect(b'139\x1b[K')
        self.assertIn(b'[255 0 0 0.5]\x1b[K', terminal.output)
        self.assertIn(b'[255 255 255 0]\x1b[K', terminal.output)
        terminal.expect(b'? ')
        terminal.resize(100, 30)
        terminal.expect(b'\x1b[2J\x1b[H')
        terminal.expect(b'? ')
        terminal.send('setspeed 5 fd 1000\n')
        while True:
            terminal.expect(b' pos [0 ')
            if float(terminal.expect(b']')[:-1]) > 5:
                break
        terminal.send(b'\x1b[<0;50;10M')
        terminal.expect(b' pos [-1 6]')
        terminal.send('bye\n')
        self.assertEqual(terminal.wait(), 0)

    def test_colours_reporter_pages_all_names_instead_of_clipping_them(self):
        terminal = self.start('--colour-mode', 'terrapin')
        terminal.resize(80, 40)
        terminal.expect(b'\x1b[2J\x1b[H')
        terminal.expect(b'? ')
        terminal.send('colours\n')
        terminal.expect(b'TRANSPARENT')
        terminal.expect(b'-- Enter to return --')
        terminal.send('\n')
        terminal.expect(b'? ')
        terminal.send('bye\n')
        self.assertEqual(terminal.wait(), 0)

    def test_script_escape_returns_interrupted_status(self):
        terminal = TerminalProcess('-e', 'fd 1000')
        self.addCleanup(terminal.close)
        terminal.expect(b'\x1b[?1002h')
        terminal.send(b'\x1b')
        terminal.expect(b'stopped')
        self.assertEqual(terminal.wait(), 130)
