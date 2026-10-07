import math
import os
import sys
import tempfile
import unittest
from contextlib import nullcontext
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from termlogo.canvas import Canvas
from termlogo.errors import Incomplete, LogoError
from termlogo.interp import Interp
from termlogo.lexer import to_number, tokenize
from termlogo.primitives_ext import _close_all as closeall
from termlogo.turtle import Turtle

EXAMPLES = os.path.join(os.path.dirname(__file__), '..', 'examples')


def run(src, size=(60, 20)):
    out = []
    c = Canvas(*size)
    t = Turtle(c)
    it = Interp(out=out.append)
    it.attach_turtle(t)
    it.eval_source(src)
    return ''.join(out), it, t, c


def out(src):
    return run(src)[0]


class LexerTests(unittest.TestCase):
    def test_numeric_conversion_preserves_types_and_large_integers(self):
        for token, expected in (
            ('12', 12),
            ('-12', -12),
            ('9007199254740993', 9007199254740993),
            ('1.25', 1.25),
            ('1e2', 100.0),
            ('-1e-2', -0.01),
        ):
            with self.subTest(token=token):
                value = to_number(token)
                self.assertEqual(value, expected)
                self.assertIs(type(value), type(expected))

    def test_overflowing_number_reports_logo_error(self):
        for token in ('1e999', '-1e999', '9' * 400 + '.0'):
            with self.subTest(token=token), self.assertRaises(LogoError):
                to_number(token)

    def test_basic(self):
        self.assertEqual(tokenize('fd 10 + 5'), ['fd', '10', '+', '5'])

    def test_unary_minus_rules(self):
        self.assertEqual(tokenize('3-4'), ['3', '-', '4'])
        self.assertEqual(tokenize('3 - 4'), ['3', '-', '4'])
        self.assertEqual(tokenize('fd -10'), ['fd', '-10'])
        self.assertEqual(tokenize('-:x'), ['u-', ':x'])

    def test_nested_lists_and_comments(self):
        self.assertEqual(tokenize('print [a [b c]] ; note'), ['print', ['a', ['b', 'c']]])

    def test_pipe_words(self):
        self.assertEqual(tokenize('print "|a b|'), ['print', '"a b'])

    def test_incomplete(self):
        with self.assertRaises(Incomplete):
            tokenize('repeat 3 [fd 1')
        with self.assertRaises(Incomplete):
            run('to foo\nfd 1')

    def test_execution_start_callback_waits_for_complete_nonempty_source(self):
        events = []
        it = Interp(out=events.append)
        it.on_start = lambda: events.append('start')
        for source in ('', '  ; comment'):
            it.eval_source(source)
        for source in ('repeat 1 [', 'to answer\noutput 42'):
            with self.assertRaises(Incomplete):
                it.eval_source(source)
        self.assertEqual(events, [])
        it.eval_source('to answer output 42 end')
        self.assertEqual(events, ['start'])
        it.eval_source('print answer')
        self.assertEqual(events, ['start', 'start', '42\n'])


class ArithmeticTests(unittest.TestCase):
    def test_grouped_zero_input_reporters_support_infix(self):
        self.assertEqual(out('repeat 3 [print (repcount + 1)]'), '2\n3\n4\n')
        self.assertEqual(out('print (heading + 90)'), '90\n')
        self.assertEqual(out('to answer output 40 end print (answer + 2)'), '42\n')
        self.assertEqual(out('print ((sum 1 2 3) * 2)'), '12\n')

    def test_negative_base_power_in_turtle_input(self):
        self.assertEqual(
            out('repeat 4 [right (-1) ^ (repcount + 1) print heading]'), '1\n0\n1\n0\n'
        )
        self.assertEqual(out('print (-1) ^ (2 + 1)'), '-1\n')
        self.assertEqual(out('print 2 ^ 3 ^ 2'), '512\n')

    def test_precedence(self):
        self.assertEqual(out('print 2+3*4'), '14\n')
        self.assertEqual(out('print (2+3)*4'), '20\n')

    def test_division(self):
        self.assertEqual(out('print 7/2'), '3.5\n')
        self.assertEqual(out('print 6/2'), '3\n')

    def test_prefix_and_variadic(self):
        self.assertEqual(out('print sum 1 2'), '3\n')
        self.assertEqual(out('print (sum 1 2 3 4)'), '10\n')
        self.assertEqual(out('print (product 2 3 4)'), '24\n')

    def test_remainder_modulo(self):
        self.assertEqual(out('print remainder -7 3'), '-1\n')
        self.assertEqual(out('print modulo -7 3'), '2\n')

    def test_trig_degrees(self):
        self.assertEqual(out('print sin 90'), '1\n')
        self.assertEqual(out('print cos 90'), '0\n')
        self.assertEqual(out('print arctan 1'), '45\n')

    def test_comparison_and_equality(self):
        self.assertEqual(out('print 3 = 3.0'), 'true\n')
        self.assertEqual(out('print "a = "A'), 'true\n')
        self.assertEqual(out('print [1 2] = [1 2]'), 'true\n')
        self.assertEqual(out('print 3 <> 4'), 'true\n')

    def test_divide_by_zero(self):
        with self.assertRaises(LogoError):
            run('print 1/0')

    def test_float_formatting(self):
        self.assertEqual(out('print 0.1+0.2'), '0.3\n')


class DataTests(unittest.TestCase):
    def test_selectors(self):
        self.assertEqual(out('print first [a b c]'), 'a\n')
        self.assertEqual(out('print last [a b c]'), 'c\n')
        self.assertEqual(out('print butfirst "hello'), 'ello\n')
        self.assertEqual(out('print butlast [1 2 3]'), '1 2\n')
        self.assertEqual(out('print item 2 [x y z]'), 'y\n')

    def test_constructors(self):
        self.assertEqual(out('print fput 1 [2 3]'), '1 2 3\n')
        self.assertEqual(out('print lput 3 [1 2]'), '1 2 3\n')
        self.assertEqual(out('print sentence [a b] [c]'), 'a b c\n')
        self.assertEqual(out('print word "ab "cd'), 'abcd\n')
        self.assertEqual(out('show (list 1 [2 3])'), '[1 [2 3]]\n')

    def test_predicates(self):
        self.assertEqual(out('print memberp 2 [1 2 3]'), 'true\n')
        self.assertEqual(out('print emptyp []'), 'true\n')
        self.assertEqual(out('print listp [1]'), 'true\n')
        self.assertEqual(out('print numberp "12'), 'true\n')

    def test_count_reverse(self):
        self.assertEqual(out('print count [1 2 3]'), '3\n')
        self.assertEqual(out('print reverse [1 2 3]'), '3 2 1\n')
        self.assertEqual(out('print reverse "abc'), 'cba\n')

    def test_variables_dynamic_scope(self):
        src = """make "x 1
to show.x print :x end
to try local "x make "x 2 show.x end
try show.x"""
        self.assertEqual(out(src), '2\n1\n')


class ControlTests(unittest.TestCase):
    def test_repeat_repcount(self):
        self.assertEqual(out('repeat 3 [type repcount]'), '123')

    def test_nested_repcount(self):
        self.assertEqual(out('repeat 2 [repeat 2 [type repcount] type "|-|]'), '12-12-')

    def test_if_ifelse(self):
        self.assertEqual(out('if 1 < 2 [print "a]'), 'a\n')
        self.assertEqual(out('print ifelse 1 > 2 ["a] ["b]'), 'b\n')
        self.assertEqual(out('ifelse 1 > 2 [print "a] [print "b]'), 'b\n')

    def test_test_iftrue_iffalse(self):
        self.assertEqual(out('test 1 = 1 iftrue [print "y] iffalse [print "n]'), 'y\n')

    def test_while_until_for(self):
        self.assertEqual(out('make "i 0 while [:i < 3] [type :i make "i :i + 1]'), '012')
        self.assertEqual(out('make "i 0 until [:i = 3] [type :i make "i :i + 1]'), '012')
        self.assertEqual(out('for [i 1 5 2] [type :i]'), '135')
        self.assertEqual(out('for [i 3 1] [type :i]'), '321')

    def test_procedures_and_recursion(self):
        src = """to fact :n
  if :n < 2 [output 1]
  output :n * fact :n - 1
end
print fact 10"""
        self.assertEqual(out(src), '3628800\n')

    def test_stop(self):
        src = """to down :n
  if :n = 0 [print "go stop]
  print :n
  down :n - 1
end
down 2"""
        self.assertEqual(out(src), '2\n1\ngo\n')

    def test_optional_and_rest_inputs(self):
        src = """to greet :a [:b "world]
  print sentence :a :b
end
greet "hello
(greet "hi "there)"""
        self.assertEqual(out(src), 'hello world\nhi there\n')
        src = 'to all [:xs] print :xs end\n(all 1 2 3)'
        self.assertEqual(out(src), '1 2 3\n')

    def test_templates(self):
        self.assertEqual(out('print map [? * 2] [1 2 3]'), '2 4 6\n')
        self.assertEqual(out('print filter [? > 1] [1 2 3]'), '2 3\n')
        self.assertEqual(out('print reduce [?1 + ?2] [1 2 3 4]'), '10\n')
        self.assertEqual(out('foreach [a b] [type ?]'), 'ab')
        self.assertEqual(out('to dbl :x output :x * 2 end print map "dbl [1 2]'), '2 4\n')

    def test_run_and_runresult(self):
        self.assertEqual(out('print run [sum 1 2]'), '3\n')
        self.assertEqual(out('run [print "hi]'), 'hi\n')

    def test_catch_throw(self):
        self.assertEqual(out('print catch "t [(throw "t 5) print "no]'), '5\n')
        self.assertEqual(out('catch "error [print 1/0] print "after'), 'after\n')

    def test_deep_recursion(self):
        depth = 1500 if sys.version_info >= (3, 11) else 300  # 3.10 stops sooner; see interp
        self.assertEqual(
            out(f'to d :n if :n = 0 [output 0] output 1 + d :n - 1 end print d {depth}'),
            f'{depth}\n',
        )

    def test_runaway_recursion_through_any_command_is_a_stack_overflow_not_a_crash(self):
        # Before Python 3.12 these crashed the interpreter outright (C stack exhausted), so
        # there they run to the full depth. Newer versions cannot crash, so a lower Logo
        # depth limit keeps the test quick.
        quick = (
            patch('termlogo.interp.MAX_DEPTH', 3000)
            if sys.version_info >= (3, 12)
            else nullcontext()
        )
        for body in (
            'output 1 + r :n + 1',
            'repeat 1 [r :n + 1]',
            'run [r :n + 1]',
            'catch "x [r :n + 1]',
            'foreach [1] [r :n + 1]',
            'output first map [r :n + 1] [1]',
        ):
            with self.subTest(body=body), quick, self.assertRaises(LogoError) as caught:
                run(f'to r :n {body} end print r 1')
            self.assertEqual(caught.exception.message, 'Stack overflow')

    def test_python_frame_limit_follows_the_python_version(self):
        from termlogo.interp import python_frame_limit

        self.assertEqual(python_frame_limit((3, 10, 20), 'linux'), 5000)
        self.assertEqual(python_frame_limit((3, 11, 0), 'darwin'), 150000)
        self.assertEqual(python_frame_limit((3, 13, 1), 'linux'), 400000)
        self.assertEqual(python_frame_limit((3, 14, 2), 'emscripten'), 2000)  # browser

    def test_examples_and_moderate_recursion_fit_the_browser_limit(self):
        # The browser allows only 2,000 Python frames (see python_frame_limit). Every
        # example, and 100 levels of non-tail recursion, must still run within it.
        limit = sys.getrecursionlimit()
        examples = sorted(name for name in os.listdir(EXAMPLES) if name.endswith('.logo'))
        self.assertGreaterEqual(len(examples), 8)
        try:
            sys.setrecursionlimit(2000)
            with patch('termlogo.interp.python_frame_limit', lambda: 2000):
                for name in examples:
                    with self.subTest(example=name), open(os.path.join(EXAMPLES, name)) as f:
                        _, _, turtle, _ = run(f.read(), size=(100, 50))
                        self.assertGreater(len(turtle.strokes) + len(turtle.fills), 0)
                self.assertEqual(sys.getrecursionlimit(), 2000)
                self.assertEqual(
                    out('to d :n if :n = 0 [output 0] output 1 + d :n - 1 end print d 100'),
                    '100\n',
                )
        finally:
            sys.setrecursionlimit(limit)

    def test_runaway_recursion_is_an_error(self):
        with self.assertRaises(LogoError):
            run('to boom boom print 1 end boom')

    def test_tail_call_loops_run_in_constant_stack(self):
        self.assertEqual(
            out('to loop :n if :n = 0 [print "done stop] loop :n - 1 end loop 200000'), 'done\n'
        )

    def test_tail_call_in_ifelse_and_output(self):
        self.assertEqual(out('to c :n ifelse :n = 0 [print "ok] [c :n - 1] end c 100000'), 'ok\n')
        src = 'to f :n :a if :n < 2 [output :a] output f :n - 1 :a * :n end print f 20 1'
        self.assertEqual(out(src), '2432902008176640000\n')
        self.assertEqual(
            out('to f :n :a if :n = 0 [output :a] output f :n - 1 :a + 1 end print f 100000 0'),
            '100000\n',
        )

    def test_mutual_tail_recursion(self):
        src = (
            'to ping :n if :n = 0 [print "end stop] pong :n - 1 end\n'
            'to pong :n ping :n end\nping 100000'
        )
        self.assertEqual(out(src), 'end\n')

    def test_tail_call_keeps_dynamic_scope(self):
        src = 'to show.x print :x end\nto try local "x make "x 2 show.x end\nmake "x 1\ntry show.x'
        self.assertEqual(out(src), '2\n1\n')

    def test_tail_command_must_not_output(self):
        with self.assertRaises(LogoError):
            run('to v output 5 end\nto w v end\nw')

    def test_non_tail_recursion_still_capped(self):
        with self.assertRaises(LogoError):
            run('to boom :n boom :n + 1 print :n end boom 1')

    def test_errors(self):
        for bad in ('foo', 'print :nope', 'fd', 'print "a + 1', 'to'):
            with self.assertRaises((LogoError, Incomplete), msg=bad):
                run(bad)

    def test_dont_say_what_to_do(self):
        with self.assertRaises(LogoError):
            run('3')


class TurtleTests(unittest.TestCase):
    def test_square_returns_home(self):
        _, _, t, _ = run('repeat 4 [fd 20 rt 90]')
        self.assertAlmostEqual(t.x, 0, places=6)
        self.assertAlmostEqual(t.y, 0, places=6)
        self.assertAlmostEqual(t.heading % 360, 0, places=6)

    def test_heading_and_position(self):
        self.assertEqual(out('rt 90 fd 10 print pos print heading'), '10 0\n90\n')
        self.assertEqual(out('lt 90 print heading'), '270\n')
        self.assertEqual(out('setpos [3 4] print towards [3 10]'), '0\n')
        self.assertEqual(out('setxy 10 0 print towards [0 0]'), '270\n')
        self.assertEqual(out('setxy 3 4 print distance [0 0]'), '5\n')

    def test_home_cs_clean(self):
        _, _, t, c = run('fd 10 rt 30 home')
        self.assertEqual((t.x, t.y, t.heading), (0, 0, 0))
        _, _, t, c = run('fd 10 clean')
        self.assertTrue(all(p is None for row in c.pix for p in row))
        self.assertEqual(t.y, 10)
        _, _, t, c = run('fd 10 cs')
        self.assertEqual(t.y, 0)

    def test_pen_up_draws_nothing(self):
        _, _, _, c = run('pu fd 20')
        self.assertTrue(all(p is None for row in c.pix for p in row))

    def test_pen_down_draws_line(self):
        _, _, _, c = run('fd 20')
        cx, cy = c.to_pixel(0, 0)
        self.assertIsNotNone(c.pix[cy][cx])
        self.assertIsNotNone(c.pix[cy - 20][cx])
        self.assertIsNone(c.pix[cy - 21][cx])

    def test_erase_and_reverse(self):
        _, _, _, c = run('fd 20 pe bk 20')
        self.assertTrue(all(p is None for row in c.pix for p in row))
        _, _, _, c = run('fd 20 px bk 20 print 1')
        self.assertTrue(all(p is None for row in c.pix for p in row))

    def test_colour(self):
        _, _, _, c = run('setpc 4 fd 5')
        cx, cy = c.to_pixel(0, 2)
        self.assertEqual(c.pix[cy][cx], (255, 0, 0))
        _, _, _, c = run('setpc [100 0 0] fd 5')
        self.assertEqual(c.pix[cy][cx], (255, 0, 0))
        _, _, _, c = run('setpc "blue fd 5')
        self.assertEqual(c.pix[cy][cx], (0, 0, 255))

    def test_nz_colour_command_spellings(self):
        _, _, t, c = run('setpencolour "red fd 5 setcolour "blue setbackgroundcolour "green')
        self.assertEqual(c.pix[c.to_pixel(0, 2)[1]][c.to_pixel(0, 2)[0]], (255, 0, 0))
        self.assertEqual(t.rgb, (0, 0, 255))
        self.assertEqual(c.bg, (0, 255, 0))
        self.assertEqual(out('setpencolour "red print pencolour'), 'red\n')
        self.assertEqual(out('setbackgroundcolour "green print backgroundcolour'), 'green\n')

    def test_fence(self):
        with self.assertRaises(LogoError):
            run('fence fd 1000')

    def test_wrap(self):
        _, _, t, c = run('wrap fd 100', size=(20, 10))  # 40x40 px, half = 20
        self.assertLess(abs(t.y), 20.0001)
        self.assertEqual(out('wrap print wrapp'), 'true\n')

    def test_window_allows_offscreen(self):
        _, _, t, _ = run('window fd 1000', size=(20, 10))
        self.assertEqual(t.y, 1000)

    def test_fill(self):
        _, _, _, c = run('repeat 4 [fd 20 rt 90] rt 45 pu fd 5 pd setpc 2 fill')
        cx, cy = c.to_pixel(7, 7)
        self.assertEqual(c.pix[cy][cx], (0, 255, 0))
        self.assertIsNone(c.pix[c.to_pixel(30, 30)[1]][c.to_pixel(30, 30)[0]])

    def test_filled_fills_the_polygon_and_keeps_the_outline(self):
        from termlogo.renderers import make_canvas

        for render in ('braille', 'half', 'kitty'):
            with self.subTest(render=render):
                c = make_canvas(render, 60, 20, cell_px=(10, 20))
                t = Turtle(c)
                it = Interp(out=lambda s: None)
                it.attach_turtle(t)
                it.eval_source('setpc 4 filled 2 [repeat 4 [fd 16 rt 90]]')

                def at(x, y, c=c):
                    px, py = c.to_pixel(x, y)
                    return c.pix[py][px]

                self.assertEqual(at(8, 8), (0, 255, 0))
                self.assertEqual(at(2, 14), (0, 255, 0))
                for edge in ((0, 8), (16, 8), (8, 16)):
                    self.assertEqual(at(*edge), (255, 0, 0))
                self.assertIsNone(at(20, 8))
                self.assertIsNone(at(-4, 8))
                self.assertEqual(t.pen_colour_spec, 4)

    def test_filled_counts_pen_up_moves_and_uses_the_even_odd_rule(self):
        _, _, t, c = run('setpc 4 pu filled 2 [setxy 0 16 setxy 16 16 setxy 16 0]')
        self.assertEqual(c.pix[c.to_pixel(8, 8)[1]][c.to_pixel(8, 8)[0]], (0, 255, 0))
        self.assertEqual(c.pix[c.to_pixel(16, 8)[1]][c.to_pixel(16, 8)[0]], (255, 0, 0))
        self.assertEqual(t.strokes, [])
        self.assertEqual((t.x, t.y), (16, 0))
        _, _, _, c = run('pu filled 2 [repeat 5 [fd 40 rt 144]]', size=(100, 30))
        self.assertIsNone(c.pix[c.to_pixel(19, 14)[1]][c.to_pixel(19, 14)[0]])  # the middle
        self.assertEqual(c.pix[c.to_pixel(2, 30)[1]][c.to_pixel(2, 30)[0]], (0, 255, 0))

    def test_filled_without_a_shape_changes_nothing(self):
        for body in ('[]', '[fd 10]', '[fd 10 bk 10]'):
            with self.subTest(body=body):
                _, _, t, _ = run('pu filled 2 ' + body)
                self.assertEqual(t.fills, [])

    def test_nested_filled_counts_inner_moves_in_the_outer_shape(self):
        _, _, t, c = run(
            'pu filled 2 [fd 20 rt 90 fd 20 filled 4 [repeat 4 [fd 6 rt 90]] rt 90 fd 20]'
        )
        self.assertEqual(c.pix[c.to_pixel(10, 10)[1]][c.to_pixel(10, 10)[0]], (0, 255, 0))
        self.assertEqual([fill[0] for fill in t.fills], ['poly', 'poly'])
        self.assertEqual([len(fill[1]) for fill in t.fills], [5, 8])
        self.assertIsNone(t.trace)

    def test_nested_filled_is_painted_on_top_of_the_outer_shape(self):
        # The inner square lies wholly inside the outer one's polygon, where the
        # even-odd rule would otherwise clear it again.
        _, _, t, c = run(
            'pu filled 2 [fd 30 rt 90 fd 30 rt 90 fd 30 rt 90 fd 30 '
            'setxy 10 10 filled 4 [repeat 4 [fd 6 rt 90]]]'
        )
        px, py = c.to_pixel(7, 13)
        self.assertEqual(c.pix[py][px], (255, 0, 0))
        self.assertEqual([fill[0] for fill in t.fills], ['poly', 'poly'])
        self.assertIsNone(t.inner)

    def test_colour_errors_name_the_command_that_was_used(self):
        for source, who in (
            ('setbg 99', 'setbackground'),
            ('setpc "nosuchcolour', 'setpencolour'),
            ('filled 99 [repeat 3 [fd 5 rt 120]]', 'filled'),
            ('setpen [pendown 99]', 'setpen'),
            ('setpalette 300 [0 0 0]', 'setpalette'),
            ('setpalette 9 [0 0]', 'setpalette'),
        ):
            with self.subTest(source=source):
                with self.assertRaisesRegex(LogoError, f"^{who} doesn't like"):
                    run(source)
        from termlogo.canvas import PALETTE

        self.assertEqual(len(PALETTE), 16)

    def test_arc_label_dot(self):
        _, _, _, c = run('arc 360 10')
        self.assertTrue(any(p is not None for row in c.pix for p in row))
        _, _, _, c = run('label "hi')
        self.assertEqual(c.labels[0][2], 'hi')
        _, _, _, c = run('dot [5 5]')
        self.assertIsNotNone(c.pix[c.to_pixel(5, 5)[1]][c.to_pixel(5, 5)[0]])

    def test_visibility_queries(self):
        self.assertEqual(out('ht print shownp st print shownp'), 'false\ntrue\n')
        self.assertEqual(out('pu print pendownp pd print pendownp'), 'false\ntrue\n')

    def test_pensize(self):
        _, _, _, c = run('setpensize 3 fd 5')
        cx, cy = c.to_pixel(0, 2)
        self.assertIsNotNone(c.pix[cy][cx + 1])


class HelpTests(unittest.TestCase):
    def test_every_primitive_has_help(self):
        from termlogo import helptext
        from termlogo.registry import PRIMS

        run('')
        self.assertEqual(sorted({p.name for p in PRIMS.values()} - set(helptext.ENTRIES)), [])

    def test_help_command(self):
        self.assertIn('forward n', out('help fd'))
        self.assertIn('forward n', out('help "forward'))
        self.assertIn('Turtle movement:', out('help "turtle'))
        self.assertIn('Control:', out('help'))
        with self.assertRaises(LogoError):
            run('help nonsense')

    def test_version_and_author(self):
        from termlogo import __version__

        self.assertEqual(out('print version'), f'termlogo {__version__} by Andy Bateman\n')

    def test_completions(self):
        from termlogo.repl import completions

        _, it, _, _ = run('make "total 3\nto triangle repeat 3 [fd 1 rt 120] end')
        self.assertIn('forward', completions(it, 'forw'))
        self.assertIn('triangle', completions(it, 'tri'))
        self.assertEqual(completions(it, ':to'), [':total'])
        self.assertIn('help', completions(it, 'he'))


class RendererTests(unittest.TestCase):
    def _build(self, name, cols=40, rows=10, cell_px=(10, 20)):
        from termlogo.renderers import make_canvas

        out = []
        c = make_canvas(name, cols, rows, 1.0, cell_px)
        t = Turtle(c)
        it = Interp(out=out.append)
        it.attach_turtle(t)
        return it, c, t

    def test_same_physical_size_in_every_renderer(self):
        # ten turtle steps should span five cells whichever renderer draws them
        for name, cell in (('braille', 2), ('half', 1), ('kitty', 10)):
            _, c, _ = self._build(name)
            dx = c.to_pixel(10, 0)[0] - c.to_pixel(0, 0)[0]
            self.assertEqual(dx / cell, 5, name)

    def test_half_block_is_solid(self):
        it, c, t = self._build('half')
        it.eval_source('ht pu setxy -10 0 pd rt 90 fd 20')
        text = '\n'.join(c.render(t, color=False, mode='half'))
        self.assertTrue(set(text) <= set(' \n\u2580\u2584\u2588'))
        self.assertTrue(any(ch in text for ch in '\u2580\u2584\u2588'))
        self.assertEqual(len(c.render(t, color=False)), 10)

    def test_half_colour_output_sets_fg_and_bg(self):
        it, c, t = self._build('half')
        it.eval_source('setpc 4 fd 5')
        line = c.render_half(t, color=True)[len(c.render_half(t)) // 2 - 1]
        self.assertIn('\x1b[38;2;', line)
        self.assertIn(';48;2;', line)

    def test_aa_line_has_soft_edges_and_solid_core(self):
        from termlogo.canvas import Canvas

        c = Canvas(20, 5, cell=(10, 20), unit=2, aa=True)
        c.aa_line(10.0, 50.0, 150.0, 50.0, (255, 255, 255), 4)
        cores = [c.pix[50][x] for x in range(20, 140)]
        self.assertTrue(all(p == (255, 255, 255) for p in cores))  # no seams
        edge = [c.pix[y][80] for y in range(44, 57) if c.pix[y][80] not in (None, (255, 255, 255))]
        self.assertTrue(edge)  # grey edge pixels

    def test_aa_diagonal_has_intermediate_shades(self):
        from termlogo.canvas import Canvas

        c = Canvas(20, 10, cell=(10, 20), unit=2, aa=True)
        c.aa_line(5.0, 5.0, 150.0, 90.0, (255, 0, 0), 3)
        shades = {p[0] for row in c.pix for p in row if p}
        self.assertGreater(len(shades), 4)

    def test_kitty_frame_is_a_valid_png_sequence(self):
        import base64
        import re
        import struct

        it, c, t = self._build('kitty')
        it.eval_source('repeat 4 [fd 30 rt 90] label "hi')
        from termlogo.renderers import frame

        seq = frame('kitty', c, t, True)
        self.assertTrue(seq.startswith('\x1b_Ga=d,d=A'))
        parts = re.findall(r'\x1b_G([^;\x1b]*);([^\x1b]*)\x1b\\', seq)
        self.assertIn('a=T,f=100', parts[0][0])
        self.assertIn('c=40,r=10', parts[0][0])
        self.assertTrue(parts[-1][0].startswith('m=0') or ',m=0' in parts[-1][0])
        png = b''.join(base64.b64decode(p[1]) for p in parts if p[1])
        self.assertEqual(png[:8], b'\x89PNG\r\n\x1a\n')
        self.assertEqual(struct.unpack('>II', png[16:24]), (400, 200))
        self.assertIn('hi', seq)  # label drawn as text

    def test_kitty_standalone_reserves_space(self):
        it, c, t = self._build('kitty')
        from termlogo.renderers import frame

        seq = frame('kitty', c, t, True, standalone=True)
        self.assertTrue(seq.startswith('\n' * 10))

    def test_choose_auto(self):
        from termlogo.renderers import choose

        ghostty = {'TERM_PROGRAM': 'ghostty', 'TERM': 'xterm-ghostty'}
        self.assertEqual(choose('auto', True, ghostty, (9, 18)), ('kitty', (9, 18)))
        self.assertEqual(choose('auto', True, {'TERM': 'xterm-256color'}, (9, 18))[0], 'braille')
        self.assertEqual(choose('auto', False, ghostty, None)[0], 'braille')  # piped
        self.assertEqual(choose('auto', True, dict(ghostty, TMUX='1'), (9, 18))[0], 'braille')
        self.assertEqual(choose('auto', True, ghostty, None)[0], 'braille')  # size unknown
        self.assertEqual(choose('half', True, {}, None)[0], 'half')
        self.assertEqual(choose('kitty', True, {}, None), ('kitty', (10, 20)))
        self.assertEqual(choose(None, True, {'TERMLOGO_RENDER': 'half'}, None)[0], 'half')
        with self.assertRaises(ValueError):
            choose('sixel', True, {}, None)

    def test_pixel_grid_is_capped_on_huge_terminals(self):
        from termlogo.renderers import MAX_PIXELS, make_canvas

        c = make_canvas('kitty', 300, 80, 1.0, (18, 36))
        self.assertLessEqual(c.width * c.height, MAX_PIXELS)
        self.assertEqual(c.scale, c.cell[0] / 2)

    def test_exports_work_from_every_renderer(self):
        for name in ('braille', 'half', 'kitty'):
            it, c, t = self._build(name, 20, 6)
            it.eval_source('repeat 4 [fd 20 rt 90]')
            self.assertTrue(c.to_text().strip(), name)
            self.assertEqual(c.to_png()[:4], b'\x89PNG')
            self.assertIn('<svg', c.to_svg())

    def test_fill_and_erase_work_on_kitty_canvas(self):
        it, c, t = self._build('kitty')
        it.eval_source('repeat 4 [fd 20 rt 90] rt 45 pu fd 4 pd setpc 2 fill')
        self.assertIn((0, 255, 0), {p for row in c.pix for p in row})
        it.eval_source('cs pe repeat 4 [fd 20 rt 90]')
        self.assertTrue(all(p is None for row in c.pix for p in row))


class SpeedTests(unittest.TestCase):
    """Animation timing, using a fake clock so the tests are instant and exact."""

    def _build(self, speed, boundary=None):
        class Clock:
            now = 0.0
            slept = 0.0

        clock = Clock()

        def sleep(d):
            clock.now += d
            clock.slept += d

        c = Canvas(60, 20)
        t = Turtle(c, clock=lambda: clock.now, sleep=sleep)
        frames = []
        t.frame_cb = lambda: frames.append((t.x, t.y, t.heading))
        t.speed = speed
        it = Interp(out=lambda s: None)
        it.attach_turtle(t)
        return it, t, clock, frames

    def test_turtle_defaults_to_speed_five(self):
        self.assertEqual(Turtle(Canvas(10, 5)).speed, 5)

    def test_speed_zero_is_instant(self):
        it, t, clock, frames = self._build(0)
        it.eval_source('fd 100 rt 90')
        self.assertEqual((clock.slept, frames), (0.0, []))

    def test_forward_takes_distance_over_rate(self):
        from termlogo.turtle import speed_to_rate

        it, t, clock, frames = self._build(5)
        it.eval_source('fd 120')
        self.assertAlmostEqual(clock.slept, 120 / speed_to_rate(5), places=3)
        self.assertAlmostEqual(t.y, 120)

    def test_each_speed_step_doubles_rate(self):
        from termlogo.turtle import speed_to_rate

        for s in range(1, 10):
            self.assertAlmostEqual(speed_to_rate(s + 1), 2 * speed_to_rate(s))

    def test_turning_is_animated(self):
        from termlogo.turtle import TURN_FACTOR, speed_to_rate

        it, t, clock, frames = self._build(5)
        it.eval_source('rt 360')
        self.assertAlmostEqual(clock.slept, 360 / (speed_to_rate(5) * TURN_FACTOR), places=3)
        self.assertEqual(t.heading % 360, 0)
        it, t, clock, frames = self._build(2)
        it.eval_source('rt 360')
        self.assertGreater(len({f[2] for f in frames}), 20)  # the turtle visibly rotates

    def test_frames_are_throttled_to_about_30_per_second(self):
        it, t, clock, frames = self._build(10)
        it.eval_source('repeat 2000 [fd 1 rt 1]')
        self.assertGreater(len(frames), 1)
        self.assertLessEqual(len(frames), clock.slept * 30 + 5)

    def test_slow_drawing_shows_intermediate_positions(self):
        it, t, clock, frames = self._build(1)
        it.eval_source('fd 60')
        ys = [f[1] for f in frames]
        self.assertGreater(len(set(round(y) for y in ys)), 10)
        self.assertEqual(ys, sorted(ys))

    def test_animated_result_matches_instant_result(self):
        src = 'repeat 5 [fd 30 rt 144] setpos [10 -5] seth 90 arc 90 12'
        it, t, clock, frames = self._build(6)
        it.eval_source(src)
        it2, t2, _, _ = self._build(0)
        it2.eval_source(src)
        self.assertAlmostEqual(t.x, t2.x, places=6)
        self.assertAlmostEqual(t.y, t2.y, places=6)
        self.assertAlmostEqual(t.heading, t2.heading, places=6)
        mine = sum(p is not None for row in t.canvas.pix for p in row)
        theirs = sum(p is not None for row in t2.canvas.pix for p in row)
        self.assertLess(abs(mine - theirs), 0.03 * theirs)

    def test_setheading_turns_the_short_way(self):
        it, t, clock, frames = self._build(5)
        it.eval_source('seth 350')
        self.assertTrue(all(h > 300 or h == 0 for _, _, h in frames))
        self.assertEqual(t.heading, 350)

    def test_fence_refuses_before_animating(self):
        it, t, clock, frames = self._build(5)
        with self.assertRaises(LogoError):
            it.eval_source('fence fd 1000')
        self.assertEqual((t.y, clock.slept), (0.0, 0.0))

    def test_wrap_still_wraps_when_animated(self):
        it, t, clock, frames = self._build(10)
        it.eval_source('wrap fd 100')
        self.assertLess(abs(t.y), t.canvas.half_h + 1e-6)

    def test_animated_wrap_does_not_repeat_strokes_after_crossing_edge(self):
        it, t, _, _ = self._build(5)
        it.eval_source('wrap fd 100')
        length = sum(math.hypot(x1 - x0, y1 - y0) for x0, y0, x1, y1, _ in t.strokes)
        self.assertAlmostEqual(length, 100)
        self.assertAlmostEqual(t.y, 20)

    def test_setspeed_and_speed_commands(self):
        it, t, _, _ = self._build(0)
        out_ = []
        it.out = out_.append
        it.eval_source('setspeed 3 print speed setspeed 0 print speed')
        self.assertEqual(''.join(out_), '3\n0\n')
        for bad in ('setspeed 11', 'setspeed -1', 'setspeed "x'):
            with self.assertRaises(LogoError):
                it.eval_source(bad)

    def test_no_callback_means_no_animation(self):
        it, t, clock, frames = self._build(5)
        t.frame_cb = None
        it.eval_source('fd 100')
        self.assertEqual(clock.slept, 0.0)

    def test_interrupt_leaves_a_valid_state(self):
        it, t, clock, frames = self._build(1)
        calls = []

        def boom(d):
            calls.append(d)
            if len(calls) == 3:
                raise KeyboardInterrupt

        t.sleep = boom
        with self.assertRaises(KeyboardInterrupt):
            it.eval_source('fd 100')
        self.assertTrue(0 < t.y < 100)
        it.eval_source('fd 1')  # still usable


class InteractiveInputTests(unittest.TestCase):
    def setUp(self):
        from termlogo.repl import DrawingControls

        self.canvas = Canvas(20, 10)
        self.turtle = Turtle(self.canvas)
        self.read_fd, self.write_fd = os.pipe()
        self.controls = DrawingControls(self.turtle, self.read_fd)

    def tearDown(self):
        os.close(self.read_fd)
        os.close(self.write_fd)

    def test_mouse_click_moves_turtle_without_drawing(self):
        os.write(self.write_fd, b'\x1b[<0;11;6M')
        self.assertTrue(self.controls(0.1))
        self.assertAlmostEqual(self.turtle.x, 1)
        self.assertAlmostEqual(self.turtle.y, -2)
        self.assertTrue(all(p is None for row in self.canvas.pix for p in row))

    def test_mouse_reposition_stops_current_move_without_connecting_stroke(self):
        def reposition(_):
            self.turtle.x, self.turtle.y = 1, -2
            return True

        self.turtle.speed = 5
        self.turtle.frame_cb = lambda: None
        self.turtle.input_cb = reposition
        self.turtle.move_to(0, 100)
        self.assertEqual((self.turtle.x, self.turtle.y), (1, -2))
        px, py = self.canvas.to_pixel(1, -2)
        self.assertIsNone(self.canvas.pix[py][px])

    def test_escape_interrupts_drawing(self):
        os.write(self.write_fd, b'\x1b')
        with self.assertRaises(KeyboardInterrupt):
            self.controls(0.1)

    def test_display_resizes_and_preserves_drawing_coordinates(self):
        from io import StringIO
        from unittest.mock import patch

        from termlogo.repl import Display

        old, new_turtle = self.canvas, self.turtle
        old.plot(*old.to_pixel(3, 4), (255, 0, 0))
        display = Display(
            Interp(), old, new_turtle, 'braille', False, [], stream=StringIO(), auto_size=True
        )
        with patch('termlogo.repl._terminal_size', return_value=os.terminal_size((40, 16))):
            self.assertTrue(display.resize_to_terminal())
        self.assertEqual((display.canvas.cols, display.canvas.rows), (40, 8))
        self.assertIs(new_turtle.canvas, display.canvas)
        px, py = display.canvas.to_pixel(3, 4)
        self.assertEqual(display.canvas.pix[py][px], (255, 0, 0))


class EarcutTests(unittest.TestCase):
    @staticmethod
    def _area(poly):
        n = len(poly)
        return (
            sum(
                poly[i][0] * poly[(i + 1) % n][1] - poly[(i + 1) % n][0] * poly[i][1]
                for i in range(n)
            )
            / 2
        )

    def _covered(self, outer, holes):
        from termlogo.earcut import triangulate

        pts = list(outer) + [p for h in holes for p in h]
        tris = triangulate(outer, holes)
        total = 0.0
        for i, j, k in tris:
            a, b, c = pts[i], pts[j], pts[k]
            total += abs((b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])) / 2
        return total, len(tris)

    def test_square_with_square_hole(self):
        total, n = self._covered(
            [(0, 0), (10, 0), (10, 10), (0, 10)], [[(3, 3), (3, 7), (7, 7), (7, 3)]]
        )
        self.assertAlmostEqual(total, 84.0)
        self.assertEqual(n, 8)

    def test_concave_star(self):
        import math

        star = [
            (
                math.cos(2 * math.pi * i / 20) * (10 if i % 2 == 0 else 4),
                math.sin(2 * math.pi * i / 20) * (10 if i % 2 == 0 else 4),
            )
            for i in range(20)
        ]
        total, n = self._covered(star, [])
        self.assertAlmostEqual(total, abs(self._area(star)), places=6)
        self.assertEqual(n, 18)

    def test_many_holes_uses_z_order_path(self):
        import math

        outer = [
            (100 * math.cos(2 * math.pi * i / 2000), 100 * math.sin(2 * math.pi * i / 2000))
            for i in range(2000)
        ]
        holes = [
            [
                (cx + 5 * math.cos(-2 * math.pi * i / 40), cy + 5 * math.sin(-2 * math.pi * i / 40))
                for i in range(40)
            ]
            for cx in range(-60, 61, 30)
            for cy in range(-60, 61, 30)
        ]
        total, _ = self._covered(outer, holes)
        expected = abs(self._area(outer)) - sum(abs(self._area(h)) for h in holes)
        self.assertAlmostEqual(total, expected, places=6)


class StencilTests(unittest.TestCase):
    SQUARE = 'setpensize 2 repeat 4 [fd 30 rt 90] '
    # A 30 mm square drawn with a 2 mm pen, to the outside of its rounded corners.
    SQUARE_AREA = 32 * 32 - (4 - math.pi)

    def _make(self, src, options=None, size=(60, 20)):
        from termlogo import stencil as S

        _, it, t, _ = run(src, size)
        tris, rep = S.make_stencil(t.strokes, options, t.fills)
        return tris, rep, S

    def test_straight_slot_is_watertight_with_exact_volume(self):
        tris, rep, S = self._make('setpensize 2 pu setxy -20 0 pd setxy 20 0')
        open_edges, vol = S.check_mesh(tris)
        self.assertEqual(open_edges, 0)
        W, H, T = rep['size']
        slot = 40 * 2 + math.pi * 1.0**2  # rectangle plus two half-discs
        self.assertAlmostEqual(vol, T * (W * H - slot), delta=0.01 * W * H * T)
        self.assertEqual((rep['islands'], rep['bridges']), (0, 0))

    def test_island_is_bridged_and_mesh_stays_watertight(self):
        tris, rep, S = self._make('setpensize 2 repeat 4 [fd 30 rt 90]')
        self.assertEqual(rep['islands'], 1)
        self.assertGreaterEqual(rep['bridges'], 1)
        self.assertEqual(S.check_mesh(tris)[0], 0)
        self.assertEqual(rep['warnings'], [])

    def test_bridge_count_option(self):
        _, rep1, _ = self._make('setpensize 2 repeat 4 [fd 30 rt 90]', ['bridges', '1'])
        _, rep2, _ = self._make('setpensize 2 repeat 4 [fd 30 rt 90]', ['bridges', '2'])
        self.assertEqual(rep1['bridges'], 1)
        self.assertEqual(rep2['bridges'], 2)

    def test_open_shape_needs_no_bridges(self):
        _, rep, _ = self._make('setpensize 2 pu fd 30 pd rt 90 fd 30 rt 90 fd 30 rt 90 fd 30')
        self.assertEqual((rep['islands'], rep['bridges']), (0, 0))

    def test_every_island_in_a_star_is_tied(self):
        tris, rep, S = self._make('setpensize 2 repeat 5 [fd 60 rt 144]', size=(80, 30))
        self.assertGreaterEqual(rep['islands'], 1)
        self.assertEqual(rep['unbridged'], 0)
        self.assertEqual(S.check_mesh(tris)[0], 0)

    def test_plate_too_small_is_an_error(self):
        with self.assertRaises(LogoError):
            self._make('setpensize 2 repeat 4 [fd 30 rt 90]', ['plate', ['20', '20']])

    def test_fixed_plate_size(self):
        _, rep, _ = self._make('setpensize 2 fd 20', ['plate', ['100', '80']])
        self.assertEqual(rep['size'][:2], (100.0, 80.0))

    def test_thin_pen_is_widened_to_minimum(self):
        tris, rep, S = self._make('setpensize 0.3 fd 30')
        self.assertEqual(rep['widened'], 1)
        self.assertTrue(any('widened' in w for w in rep['warnings']))

    def test_width_option_overrides_pen(self):
        _, narrow, S = self._make('setpensize 1 fd 30', ['width', '1'])
        t1, r1, _ = self._make('setpensize 1 fd 30', ['width', '1'])
        t2, r2, _ = self._make('setpensize 1 fd 30', ['width', '4', 'margin', '8'])
        self.assertLess(
            S.check_mesh(t2)[1] / (r2['size'][0] * r2['size'][1]),
            S.check_mesh(t1)[1] / (r1['size'][0] * r1['size'][1]),
        )

    def test_mirror_flips_left_right(self):
        t1, r1, S = self._make('setpensize 2 pu setxy -30 0 pd setxy -10 0')
        t2, r2, _ = self._make('setpensize 2 pu setxy -30 0 pd setxy -10 0', ['mirror', 'true'])
        W = r1['size'][0]
        x1 = sorted({round(v[0], 3) for tri in t1 for v in tri})
        x2 = sorted({round(W - v[0], 3) for tri in t2 for v in tri})
        self.assertEqual(x1, x2)
        self.assertEqual(S.check_mesh(t2)[0], 0)
        self.assertGreater(S.check_mesh(t2)[1], 0)

    def test_scale_option_mm_per_step(self):
        _, a, _ = self._make('setpensize 2 fd 20')
        _, b, _ = self._make('setpensize 2 fd 20', ['mm', '2', 'width', '2'])
        self.assertGreater(b['size'][1], a['size'][1])

    def test_unknown_or_bad_options(self):
        for bad in (
            ['colour', 'red'],
            ['thickness'],
            ['thickness', '-1'],
            ['mirror', 'maybe', 'x'],
        ):
            with self.assertRaises(LogoError, msg=str(bad)):
                self._make('setpensize 2 fd 20', bad)

    def test_nothing_drawn_is_an_error(self):
        with self.assertRaises(LogoError):
            self._make('pu fd 10')

    def test_stl_file_format(self):
        import struct

        tris, rep, S = self._make('setpensize 2 fd 20')
        data = S.to_stl(tris)
        self.assertEqual(len(data), 84 + 50 * len(tris))
        self.assertEqual(struct.unpack('<I', data[80:84])[0], len(tris))
        self.assertTrue(data.startswith(b'termlogo stencil'))
        v = struct.unpack('<12f', data[84:132])
        self.assertAlmostEqual(sum(c * c for c in v[:3]), 1.0, places=4)  # unit normal

    def test_normals_point_outward(self):
        tris, rep, S = self._make('setpensize 2 fd 20')
        self.assertGreater(S.check_mesh(tris)[1], 0)  # positive volume

    def test_fine_pitch_is_still_watertight(self):
        tris, rep, S = self._make('setpensize 2 repeat 36 [fd 4 rt 10]', ['pitch', '0.1'])
        self.assertEqual(S.check_mesh(tris)[0], 0)

    def test_fill_cuts_out_the_enclosed_area(self):
        _, outline, _ = self._make(self.SQUARE)
        tris, rep, S = self._make(self.SQUARE + 'pu setxy 15 15 pd fill')
        self.assertEqual((rep['fills'], rep['holes']), (1, 1))
        self.assertEqual((rep['islands'], rep['bridges']), (0, 0))
        self.assertEqual(rep['warnings'], [])
        self.assertAlmostEqual(rep['cut_area'], self.SQUARE_AREA, delta=1)
        self.assertGreater(rep['cut_area'], 4 * outline['cut_area'])
        open_edges, volume = S.check_mesh(tris)
        self.assertEqual(open_edges, 0)
        W, H, T = rep['size']
        self.assertAlmostEqual(volume, T * (W * H - self.SQUARE_AREA), delta=T)
        self.assertIn('1 filled area(s) cut out', S.describe(rep)[0])

    def test_fill_that_is_not_enclosed_or_starts_on_a_line_is_left_out(self):
        _, outline, _ = self._make(self.SQUARE)
        for source, message in (
            ('pu setxy -5 -5 fill', 'not enclosed'),
            ('pu setxy 500 500 fill', 'not enclosed'),
            ('fill', 'on a pen line'),
        ):
            with self.subTest(source=source):
                tris, rep, S = self._make(self.SQUARE + source)
                self.assertEqual(rep['fills'], 0)
                self.assertAlmostEqual(rep['cut_area'], outline['cut_area'])
                self.assertEqual(len(rep['warnings']), 1)
                self.assertIn(message, rep['warnings'][0])
                self.assertEqual(S.check_mesh(tris)[0], 0)

    def test_filling_the_same_area_twice_is_not_reported(self):
        _, rep, _ = self._make(self.SQUARE + 'pu setxy 15 15 fill setxy 5 5 fill')
        self.assertEqual((rep['fills'], rep['warnings']), (1, []))

    def test_fill_is_bounded_only_by_lines_drawn_before_it(self):
        across = 'pu setxy 0 15 pd seth 90 fd 30 '
        _, after, _ = self._make(self.SQUARE + 'pu setxy 15 22 fill ' + across)
        self.assertAlmostEqual(after['cut_area'], self.SQUARE_AREA, delta=1)
        self.assertEqual(after['islands'], 0)
        tris, before, S = self._make(self.SQUARE + across + 'pu setxy 15 22 fill')
        self.assertLess(before['cut_area'], 0.7 * self.SQUARE_AREA)
        self.assertEqual((before['fills'], before['islands'], before['unbridged']), (1, 1, 0))
        self.assertGreaterEqual(before['bridges'], 1)
        self.assertEqual(S.check_mesh(tris)[0], 0)

    def test_a_line_continued_after_a_fill_does_not_divide_the_filled_area(self):
        source = (
            self.SQUARE
            + 'pu setxy 0 10 pd seth 90 fd 5 pu setxy 10 15 fill pu setxy 5 10 pd seth 90 fd 25'
        )
        _, it, t, _ = run(source)
        self.assertEqual(len(t.strokes), 6)
        _, rep, _ = self._make(source)
        self.assertEqual(rep['islands'], 0)
        self.assertAlmostEqual(rep['cut_area'], self.SQUARE_AREA, delta=1)

    def test_island_inside_a_filled_area_is_bridged(self):
        tris, rep, S = self._make(
            self.SQUARE + 'pu setxy 10 10 pd repeat 4 [fd 10 rt 90] pu setxy 5 5 fill'
        )
        self.assertEqual((rep['fills'], rep['islands'], rep['unbridged']), (1, 1, 0))
        self.assertGreaterEqual(rep['bridges'], 1)
        self.assertEqual(S.check_mesh(tris)[0], 0)

    def test_filled_cuts_out_its_polygon_with_or_without_an_outline(self):
        tris, rep, S = self._make('pu filled 4 [repeat 4 [fd 30 rt 90]]')
        self.assertEqual((rep['fills'], rep['holes'], rep['islands']), (1, 1, 0))
        self.assertAlmostEqual(rep['cut_area'], 900, delta=1)
        self.assertAlmostEqual(rep['size'][0], 46)
        self.assertAlmostEqual(rep['size'][1], 46)
        self.assertEqual(S.check_mesh(tris)[0], 0)
        tris, rep, S = self._make('setpensize 2 filled 4 [repeat 4 [fd 30 rt 90]]')
        self.assertEqual((rep['fills'], rep['holes'], rep['islands']), (1, 1, 0))
        self.assertAlmostEqual(rep['cut_area'], self.SQUARE_AREA, delta=1)
        self.assertEqual(S.check_mesh(tris)[0], 0)
        tris, rep, S = self._make('pu filled 4 [repeat 3 [fd 40 rt 120]]', ['mirror', 'true'])
        self.assertAlmostEqual(rep['cut_area'], math.sqrt(3) / 4 * 1600, delta=2)
        self.assertEqual(S.check_mesh(tris)[0], 0)

    def test_filled_star_keeps_its_middle_as_a_bridged_island(self):
        tris, rep, S = self._make('setpensize 2 filled 4 [repeat 5 [fd 60 rt 144]]', size=(80, 30))
        self.assertGreaterEqual(rep['islands'], 1)
        self.assertEqual(rep['unbridged'], 0)
        self.assertEqual(S.check_mesh(tris)[0], 0)

    def test_fills_follow_the_mm_option(self):
        _, rep, _ = self._make(
            self.SQUARE + 'pu setxy 15 15 fill setxy 40 0 filled 4 [repeat 4 [fd 10 rt 90]]',
            ['mm', '2'],
        )
        self.assertEqual((rep['fills'], rep['warnings']), (2, []))
        self.assertAlmostEqual(rep['cut_area'], 64 * 64 - 4 * (4 - math.pi) + 400, delta=4)

    def test_erased_strokes_are_not_in_the_stencil(self):
        _, it, t, _ = run('setpensize 2 fd 20 pe bk 10')
        self.assertEqual(len(t.strokes), 1)
        self.assertEqual(t.unrecorded, 1)

    def test_cs_and_clean_forget_fills_and_erased_strokes(self):
        drawing = (
            'repeat 4 [fd 9 rt 90] pu setxy 4 4 pd fill pe fd 3 ppt '
            'filled 2 [repeat 3 [fd 9 rt 120]] '
        )
        for command in ('cs', 'clean'):
            with self.subTest(command=command), tempfile.TemporaryDirectory() as d:
                _, _, t, _ = run(drawing + command)
                self.assertEqual((t.strokes, t.fills, t.unrecorded), ([], [], 0))
                text, *_ = run(
                    drawing
                    + command
                    + ' pu home pd setpensize 2 fd 20 stencil "'
                    + os.path.join(d, 'x')
                )
                self.assertIn('Stencil', text)
                self.assertNotIn('Warning', text)
                self.assertNotIn('filled area', text)

    def test_cs_clean_clear_strokes_and_dots_are_recorded(self):
        _, it, t, _ = run('fd 10 cs')
        self.assertEqual(t.strokes, [])
        _, it, t, _ = run('fd 10 clean')
        self.assertEqual(t.strokes, [])
        _, it, t, _ = run('dot [5 5]')
        self.assertEqual(t.strokes, [(5, 5, 5, 5, 1)])

    def test_collinear_moves_coalesce_into_one_stroke(self):
        _, it, t, _ = run('repeat 10 [fd 10]')
        self.assertEqual(len(t.strokes), 1)
        _, it, t, _ = run('repeat 4 [fd 10 rt 90]')
        self.assertEqual(len(t.strokes), 4)

    def test_animated_drawing_records_same_stroke(self):
        clock = [0.0]
        c = Canvas(60, 20)
        t = Turtle(c, clock=lambda: clock[0], sleep=lambda d: clock.__setitem__(0, clock[0] + d))
        t.frame_cb = lambda: None
        t.speed = 4
        it = Interp(out=lambda s: None)
        it.attach_turtle(t)
        it.eval_source('fd 100')
        self.assertEqual(len(t.strokes), 1)
        self.assertAlmostEqual(t.strokes[0][3], 100)

    def test_stencil_command_writes_a_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 's.stl')
            text, it, t, c = run('setpensize 2 repeat 4 [fd 30 rt 90] stencil "' + path)
            self.assertIn('Stencil', text)
            self.assertIn('bridge', text)
            self.assertGreater(os.path.getsize(path), 84)
            text, *_ = run('setpensize 2 fd 20 (stencil "' + path + ' [thickness 2 margin 5])')
            self.assertIn('x 2 mm', text)
            text, *_ = run(self.SQUARE + 'pu setxy 15 15 fill pe fd 5 stencil "' + path)
            self.assertIn('1 filled area(s) cut out', text)
            self.assertIn('Warning: 1 erased or reversed segment(s)', text)

    def test_stencil_command_adds_a_missing_stl_extension(self):
        with tempfile.TemporaryDirectory() as d:
            for name, written in (
                ('plate', 'plate.stl'),
                ('Upper.STL', 'Upper.STL'),
                ('v1.2', 'v1.2.stl'),
                ('drawing.svg', 'drawing.svg.stl'),
            ):
                with self.subTest(name=name):
                    text, *_ = run('setpensize 2 fd 20 stencil "' + os.path.join(d, name))
                    self.assertIn(os.path.join(d, written), text)
                    self.assertGreater(os.path.getsize(os.path.join(d, written)), 84)
            self.assertEqual(
                sorted(os.listdir(d)), ['Upper.STL', 'drawing.svg.stl', 'plate.stl', 'v1.2.stl']
            )

    def test_unwritable_exports_are_reported_not_raised(self):
        import contextlib
        import io

        from termlogo.__main__ import main

        with tempfile.TemporaryDirectory() as d:
            for name in (
                'missing/out.svg',
                'missing/out.png',
                'missing/out.txt',
                'missing/out.stl',
            ):
                path = os.path.join(d, name)
                with self.subTest(name=name):
                    with self.assertRaisesRegex(LogoError, "Can't write .*out"):
                        run('setpensize 2 fd 20 savepict "' + path)
                    messages = io.StringIO()
                    with contextlib.redirect_stderr(messages):
                        rc = main(['-e', 'setpensize 2 fd 20', '-o', path, '--size', '20x5'])
                    self.assertEqual(rc, 1)
                    self.assertIn("termlogo: Can't write " + path, messages.getvalue())

    def test_savepict_stl_routes_to_the_stencil(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'p.stl')
            run('setpensize 2 fd 20 savepict "' + path)
            self.assertGreater(os.path.getsize(path), 84)

    def test_command_line_stl_export(self):
        from termlogo.__main__ import main

        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'cli.stl')
            rc = main(
                [
                    '-e',
                    'setpensize 2 repeat 4 [fd 30 rt 90]',
                    '-o',
                    path,
                    '--stencil-opt',
                    'thickness=2',
                    '--stencil-opt',
                    'bridges=1',
                    '--size',
                    '40x10',
                ]
            )
            self.assertEqual(rc, 0)
            self.assertGreater(os.path.getsize(path), 84)
            self.assertEqual(
                main(['-e', 'pu fd 5', '-o', os.path.join(d, 'x.stl'), '--size', '20x5']), 1
            )

    def test_command_line_stl_export_reports_fills_and_erased_strokes(self):
        import contextlib
        import io

        from termlogo.__main__ import main

        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'filled.stl')
            messages = io.StringIO()
            with contextlib.redirect_stderr(messages):
                rc = main(
                    [
                        '-e',
                        self.SQUARE + 'pu setxy 15 15 fill pe fd 5',
                        '-o',
                        path,
                        '--size',
                        '40x10',
                    ]
                )
            self.assertEqual(rc, 0)
            self.assertIn('1 filled area(s) cut out', messages.getvalue())
            self.assertIn('Warning: 1 erased or reversed segment(s)', messages.getvalue())
            self.assertGreater(os.path.getsize(path), 84)

    def test_help_documents_stencil_and_speed(self):
        self.assertIn('Options:', out('help stencil'))
        self.assertIn('setspeed', out('help setspeed'))


class WorkspaceTests(unittest.TestCase):
    def test_save_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'w.logo')
            run(
                'to sq :n repeat 4 [fd :n rt 90] end\nto g :a [:b 2] output :a + :b end\n'
                'make "k 7\nsave "' + path
            )
            self.assertEqual(out('load "' + path + '\nprint g 1 print :k'), '3\n7\n')

    def test_po(self):
        self.assertIn('to sq :n', out('to sq :n fd :n end po "sq'))

    def test_savepict(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'p.svg')
            run('fd 10 savepict "' + path)
            self.assertGreater(os.path.getsize(path), 0)


class RenderTests(unittest.TestCase):
    def test_braille_cell_mapping(self):
        c = Canvas(2, 1)
        c.plot(0, 0, (255, 255, 255))
        self.assertEqual(c.render(color=False)[0][0], chr(0x2801))
        c.plot(1, 3, (255, 255, 255))
        self.assertEqual(c.render(color=False)[0][0], chr(0x2881))

    def test_render_dimensions(self):
        c = Canvas(30, 8)
        lines = c.render(color=False)
        self.assertEqual(len(lines), 8)
        self.assertTrue(all(len(line) == 30 for line in lines))

    def test_turtle_marker_drawn_and_hideable(self):
        _, _, t, c = run('')
        shown = ''.join(c.render(t, color=False))
        self.assertTrue(shown.strip())
        t.visible = False
        self.assertFalse(''.join(c.render(t, color=False)).strip())

    def test_exports(self):
        _, _, _, c = run('repeat 4 [fd 10 rt 90]')
        with tempfile.TemporaryDirectory() as d:
            for name in ('a.svg', 'a.png', 'a.txt'):
                c.save(os.path.join(d, name))
                self.assertGreater(os.path.getsize(os.path.join(d, name)), 0)
            with open(os.path.join(d, 'a.png'), 'rb') as f:
                self.assertEqual(f.read(8), b'\x89PNG\r\n\x1a\n')


class ArrayTests(unittest.TestCase):
    def test_literals_print_with_origin_and_nest(self):
        self.assertEqual(out('print {1 2 [3 4]}'), '{1 2 [3 4]}\n')
        self.assertEqual(out('show {a b}@0'), '{a b}@0\n')
        self.assertEqual(out('show {a {b c}}'), '{a {b c}}\n')

    def test_unbalanced_braces_are_reported(self):
        for source in ('{1 2]', '[1 2}', '}'):
            with self.subTest(source=source), self.assertRaises(LogoError):
                tokenize(source)
        with self.assertRaises(Incomplete):
            tokenize('{1 2')

    def test_array_item_setitem_count_and_origin(self):
        self.assertEqual(out('make "a array 3 setitem 2 :a "hi show :a'), '{[] hi []}\n')
        self.assertEqual(out('print item 0 (array 2 0)'), '\n')
        self.assertEqual(out('print item 0 {a b}@0'), 'a\n')
        self.assertEqual(out('print count {a b c} print first {x y} print last {x y}'), '3\nx\ny\n')
        for bad in ('item 3 {a b}', 'item 0 {a b}', 'setitem 5 array 2 "x', 'setitem 1 [a] "x'):
            with self.subTest(bad=bad), self.assertRaises(LogoError):
                run(bad)

    def test_arrays_are_shared_and_equal_only_to_themselves(self):
        self.assertEqual(
            out('make "a {1 2} make "b :a setitem 1 :b 9 print item 1 :a'),
            '9\n',
        )
        self.assertEqual(out('make "a {1} print equalp :a :a print equalp :a {1}'), 'true\nfalse\n')

    def test_conversion_and_predicates(self):
        self.assertEqual(out('show listtoarray [a b c]'), '{a b c}\n')
        self.assertEqual(out('show (listtoarray [a b] 0)'), '{a b}@0\n')
        self.assertEqual(out('show arraytolist {1 2 3}'), '[1 2 3]\n')
        self.assertEqual(
            out('print arrayp {1} print arrayp [1] print listp {1} print wordp {1}'),
            'true\nfalse\nfalse\nfalse\n',
        )

    def test_multi_dimensional_arrays(self):
        self.assertEqual(
            out('make "m mdarray [2 3] mdsetitem [2 3] :m 99 print mditem [2 3] :m'), '99\n'
        )
        self.assertEqual(out('print mditem [1 1] mdarray [2 2]'), '\n')
        with self.assertRaises(LogoError):
            run('print mditem [3 1] mdarray [2 2]')

    def test_butfirst_of_an_array_is_an_error(self):
        with self.assertRaises(LogoError):
            run('print butfirst {1 2}')


class PropertyListTests(unittest.TestCase):
    def test_set_get_remove(self):
        self.assertEqual(
            out('pprop "me "age 42 print gprop "me "age print gprop "me "none'), '42\n\n'
        )
        self.assertEqual(out('pprop "Me "Age 1 print gprop "me "age'), '1\n')
        self.assertEqual(
            out('pprop "me "a 1 pprop "me "b 2 remprop "me "a show plist "me show plists'),
            '[b 2]\n[me]\n',
        )
        self.assertEqual(out('pprop "me "a 1 remprop "me "a show plists'), '[]\n')

    def test_pps_and_erase(self):
        self.assertEqual(out('pprop "me "a [1 2] pps'), 'pprop "me "a [1 2]\n')
        self.assertEqual(out('pprop "me "a 1 erps show plists'), '[]\n')
        self.assertEqual(out('pprop "me "a 1 erall show plists'), '[]\n')


class PropertyListPrintTests(unittest.TestCase):
    def test_pps_output_reads_back_as_the_same_property_lists(self):
        source = (
            'pprop "me "colour "red pprop "me "age 42 pprop "me "pets [cat [dog]] '
            'pprop "me "motto "|two words|'
        )
        text, first, _, _ = run(source + ' pps')
        self.assertIn('pprop "me "colour "red\n', text)
        self.assertIn('pprop "me "age 42\n', text)
        self.assertIn('pprop "me "motto "|two words|\n', text)
        _, again, _, _ = run(text)
        self.assertEqual(again.plists, first.plists)


class GotoTests(unittest.TestCase):
    def test_goto_loops_within_a_procedure(self):
        source = (
            'to count5 make "i 0 tag "top make "i :i + 1 if :i < 5 [goto "top] output :i end '
            'print count5'
        )
        self.assertEqual(out(source), '5\n')

    def test_goto_jumps_forward_and_works_inside_repeat(self):
        source = 'to skip print 1 goto "end print 2 tag "end print 3 end skip'
        self.assertEqual(out(source), '1\n3\n')
        source = 'to f repeat 3 [print repcount if repcount = 2 [goto "done]] print "never tag "done print "ok end f'
        self.assertEqual(out(source), '1\n2\nok\n')

    def test_goto_without_a_tag_is_an_error(self):
        with self.assertRaises(LogoError):
            run('to f goto "nowhere end f')

    def test_tag_names_ignore_case(self):
        self.assertEqual(out('to f goto "ABC print 1 tag "abc print 2 end f'), '2\n')


class MaybeOutputTests(unittest.TestCase):
    def test_outputs_a_value_or_stops(self):
        self.assertEqual(out('to f :x .maybeoutput :x end print f 7'), '7\n')
        self.assertEqual(out('to g .maybeoutput print "side print "after end g'), 'side\n')


class StreamTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = os.path.join(self.dir.name, 'data.txt')

    def logo(self, source):
        text, it, _, _ = run(source.replace('FILE', self.path))
        self.addCleanup(closeall, it)
        return text

    def test_write_then_read_back(self):
        text = self.logo(
            'openwrite "FILE setwrite "FILE print "hello print [a b c] type "xy '
            'setwrite [] print writer close "FILE '
            'openread "FILE setread "FILE print reader print readword show readlist '
            'print readchar print readchar print eofp print readword'
        )
        self.assertEqual(text, f'\n{self.path}\nhello\n[a b c]\nx\ny\ntrue\n\n')
        with open(self.path) as f:
            self.assertEqual(f.read(), 'hello\na b c\nxy')

    def test_eof_and_readchars(self):
        with open(self.path, 'w') as f:
            f.write('ab')
        text = self.logo(
            'openread "FILE setread "FILE print eofp print readchars 5 print eofp '
            'print readchar print readword print keyp'
        )
        self.assertEqual(text, 'false\nab\ntrue\n\n\nfalse\n')

    def test_append_update_and_positions(self):
        with open(self.path, 'w') as f:
            f.write('one\n')
        self.logo('openappend "FILE setwrite "FILE print "two close "FILE')
        with open(self.path) as f:
            self.assertEqual(f.read(), 'one\ntwo\n')
        text = self.logo(
            'openread "FILE setread "FILE print readword print readpos setreadpos 0 print readword'
        )
        self.assertEqual(text, 'one\n4\none\n')
        self.logo('openupdate "FILE setwrite "FILE type "ONE closeall')
        with open(self.path) as f:
            self.assertEqual(f.read(), 'ONE\ntwo\n')

    def test_close_resets_the_current_stream_and_allopen_lists_streams(self):
        text = self.logo(
            'openwrite "FILE print allopen setwrite "FILE close "FILE print writer print allopen'
        )
        self.assertEqual(text, '%s\n\n\n' % self.path)

    def test_errors(self):
        missing = os.path.join(self.dir.name, 'missing.txt')
        for source in (
            f'openread "{missing}',
            f'setread "{missing}',
            f'close "{missing}',
            f'openwrite "{self.path} openwrite "{self.path}',
        ):
            with self.subTest(source=source), self.assertRaises(LogoError):
                self.logo(source)

    def test_filep_and_erasefile(self):
        text = self.logo(
            'print filep "FILE openwrite "FILE closeall print filep "FILE erasefile "FILE '
            'print filep "FILE'
        )
        self.assertEqual(text, 'false\ntrue\nfalse\n')

    def test_streams_must_suit_setread_and_setwrite(self):
        with self.assertRaises(LogoError) as caught:
            self.logo('openwrite "FILE setread "FILE')
        self.assertIn('not open for reading', caught.exception.message)
        closeall(run('')[1])
        with open(self.path, 'w') as f:
            f.write('x')
        with self.assertRaises(LogoError) as caught:
            self.logo('openread "FILE setwrite "FILE')
        self.assertIn('not open for writing', caught.exception.message)

    def test_bytes_that_are_not_utf8_do_not_stop_a_program(self):
        with open(self.path, 'wb') as f:
            f.write(b'caf\xe9\n')
        self.assertEqual(self.logo('openread "FILE setread "FILE print readword'), 'caf\ufffd\n')

    def test_files_are_closed_at_exit_by_one_registration(self):
        with patch('termlogo.primitives_ext.atexit.register') as register:
            self.logo('openwrite "FILE close "FILE openwrite "FILE close "FILE')
        self.assertEqual(register.call_count, 1)

    def test_keyboard_hooks_are_used_without_a_stream(self):
        lines = []
        it = Interp(out=lines.append)
        keys = iter('ab')
        it.readchar = lambda: next(keys, '')
        it.keyp = lambda: True
        it.eval_source('print readchar print readchars 2 print keyp')
        self.assertEqual(lines, ['a\n', 'b\n', 'true\n'])


class BrushAndReverseTests(unittest.TestCase):
    def test_brushes_are_round_and_sized_by_width(self):
        self.assertEqual([len(Canvas.brush(w)) for w in (1, 2, 3, 4, 5)], [1, 4, 9, 12, 21])
        self.assertEqual(len(Canvas.brush(0.4)), 1)

    def test_thick_lines_have_round_ends_and_even_widths_are_centred(self):
        _, _, _, c = run('setpensize 5 pu setxy -10 0 pd fd 0 setxy 10 0', size=(40, 10))
        px, py = c.to_pixel(-10, 0)
        self.assertIsNotNone(c.pix[py][px - 2])
        self.assertIsNone(c.pix[py - 2][px - 2])  # the corner of a square brush
        self.assertIsNotNone(c.pix[py + 2][px])
        _, _, _, c = run('setpensize 2 setxy 10 0', size=(40, 10))
        px, py = c.to_pixel(5, 0)
        self.assertEqual(sum(c.pix[y][px] is not None for y in range(c.height)), 2)

    def test_penreverse_xors_and_drawing_twice_restores(self):
        _, _, t, c = run('setpc 4 pu setxy -20 5 pd penreverse setxy 20 5', size=(60, 20))
        px, py = c.to_pixel(0, 5)
        self.assertEqual(c.pix[py][px], (255, 0, 0))  # black background xor red
        t.canvas.line(*c.to_pixel(-20, 5), *c.to_pixel(20, 5), (255, 0, 0), 'reverse')
        self.assertIsNone(c.pix[py][px])

    def test_penreverse_over_a_colour_xors_the_colours(self):
        _, _, _, c = run('setpc 4 setxy 20 0 penreverse setpc 1 setxy 0 0', size=(60, 20))
        px, py = c.to_pixel(10, 0)
        self.assertEqual(c.pix[py][px], (255, 0, 255))  # red xor blue

    def test_wide_reversed_strokes_xor_each_pixel_once(self):
        _, _, _, c = run('setpc 7 setpensize 4 penreverse setxy 30 0', size=(60, 20))
        px, py = c.to_pixel(15, 0)
        column = [c.pix[y][px] for y in range(c.height)]
        self.assertEqual(column.count((255, 255, 255)), 4)


class FitWindowTests(unittest.TestCase):
    def test_fitwindow_scales_the_window_to_the_canvas(self):
        _, _, _, c = run('fitwindow 1000', size=(80, 24))
        self.assertAlmostEqual(c.scale, min(c.width, c.height) / 1000)
        self.assertEqual(c.fit, 1000)

    def test_a_resized_canvas_keeps_the_fit(self):
        _, _, _, c = run('fitwindow 1000', size=(80, 24))
        bigger = Canvas(120, 40)
        c.copy_to(bigger)
        self.assertAlmostEqual(bigger.scale, min(bigger.width, bigger.height) / 1000)

    def test_fitwindow_needs_a_positive_size(self):
        for bad in ('0', '-5', '"x'):
            with self.subTest(bad=bad), self.assertRaises(LogoError):
                run('fitwindow ' + bad)


if __name__ == '__main__':
    unittest.main()
