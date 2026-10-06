import contextlib
import hashlib
import io
import json
import math
import struct
import unittest
import xml.etree.ElementTree as ET
import zlib

from termlogo.__main__ import main
from termlogo.colours import WEB_INDICES, WEB_NAMES, WEB_PALETTE, composite
from termlogo.errors import LogoError
from termlogo.repl import build


class TerrapinColourTests(unittest.TestCase):
    def build(self, render='braille', cols=40, rows=16):
        output = []
        it, canvas, turtle = build(cols, rows, 1, output.append, render, colour_mode='terrapin')
        return it, canvas, turtle, output

    def test_palette_matches_verified_reference(self):
        # Public RGB table and live WebLogo index order, checked as at 2026-10-06.
        fixture = json.dumps(list(zip(WEB_NAMES, WEB_PALETTE, strict=True)), separators=(',', ':'))
        self.assertEqual(
            hashlib.sha256(fixture.encode()).hexdigest(),
            '1a3193b1979df4ebf661662f7c6febdc229b2043347ced31c81b44ed715a2cb9',
        )

    def test_every_colour_name_and_index_is_accepted(self):
        it, canvas, turtle, _ = self.build()
        for index, (name, rgba) in enumerate(zip(WEB_NAMES, WEB_PALETTE, strict=True)):
            with self.subTest(index=index, name=name):
                it.eval_source(f'setpc {index}')
                self.assertEqual(turtle.rgb, rgba)
                it.eval_source(f'setpencolour "{name.upper()}')
                self.assertEqual(turtle.rgb, rgba)
                it.eval_source(f'setbg {index}')
                self.assertEqual(canvas.bg, rgba)
                it.eval_source(f'setbackgroundcolour "{name}')
                self.assertEqual(canvas.bg, rgba)

    def test_grey_and_web_aliases_are_accepted(self):
        _, _, turtle, _ = self.build()
        for name, index in WEB_INDICES.items():
            with self.subTest(name=name):
                self.assertEqual(turtle.parse_colour(name), WEB_PALETTE[index])
        self.assertEqual(turtle.parse_colour('darkslategrey'), (47, 79, 79, 1))
        self.assertEqual(turtle.parse_colour('aqua'), (0, 255, 255, 1))
        self.assertEqual(turtle.parse_colour('fuchsia'), (255, 0, 255, 1))

    def test_initial_state_and_bare_reporters(self):
        it, _, _, output = self.build()
        it.eval_source('pc bg pen speed count colours')
        self.assertEqual(''.join(output), '[0 0 0 1]\n[255 255 255 0]\npendown\n5\n139\n')

    def test_lesson_rgb_rgba_and_reporter_examples(self):
        it, _, turtle, output = self.build()
        it.eval_source(
            'setpc "red pc setpc [0 38 255] pc setpc [255 215 0 0.5] pc '
            'setpc pc setbg "pink bg setbg [0 38 255] bg '
            'setbg [255 0 0 0.25] bg setbg bg'
        )
        self.assertEqual(
            ''.join(output),
            '[255 0 0 1]\n[0 38 255 1]\n[255 215 0 0.5]\n'
            '[255 192 203 1]\n[0 38 255 1]\n[255 0 0 0.25]\n',
        )
        self.assertEqual(turtle.rgb, (255, 215, 0, 0.5))
        with self.assertRaises(LogoError):
            it.eval_source('setpc pc + 1')

    def test_colours_reports_canonical_index_order(self):
        it, _, _, output = self.build()
        it.eval_source('make "names colors')
        names = it.lookup('names')
        self.assertEqual(names, [name.upper() for name in WEB_NAMES])
        it.eval_source('foreach colours [setpc ?]')
        self.assertEqual(output, [])

    def test_random_colour_examples_include_both_endpoints(self):
        from unittest.mock import call, patch

        it, _, turtle, _ = self.build()
        with patch('termlogo.primitives_data.random.randint', side_effect=(1, 138, 1, 139)) as draw:
            expected = ((0, 0, 128, 1), (0, 0, 0, 0), (0, 0, 0, 1), (0, 0, 0, 0))
            for source, colour in zip(
                (
                    'setpc random 138',
                    'setbg random 138',
                    'setpc (random 139)-1',
                    'setbg (random 139)-1',
                ),
                expected,
                strict=True,
            ):
                it.eval_source(source)
                actual = turtle.rgb if source.startswith('setpc') else turtle.canvas.bg
                self.assertEqual(actual, colour)
            self.assertEqual(
                draw.call_args_list, [call(1, 138), call(1, 138), call(1, 139), call(1, 139)]
            )

    def test_bad_colour_inputs_raise_logo_errors(self):
        _, _, turtle, _ = self.build()
        for spec in (
            -1,
            139,
            1.5,
            math.inf,
            math.nan,
            True,
            'notacolour',
            '1e999',
            [],
            [1, 2],
            [1, 2, 3, 1, 5],
            [-1, 0, 0],
            [0, 256, 0],
            [0, math.inf, 0],
            [0, math.nan, 0],
            [0, 'red', 0],
            [0, 0, 0, -0.1],
            [0, 0, 0, 1.1],
            [0, 0, 0, math.nan],
        ):
            with self.subTest(spec=spec), self.assertRaises(LogoError):
                turtle.parse_colour(spec)

    def test_setpen_accepts_all_full_state_names_and_colour_forms(self):
        it, _, turtle, output = self.build()
        for state, down, mode in (
            ('PENUP', False, 'paint'),
            ('PENDOWN', True, 'paint'),
            ('PENERASE', True, 'erase'),
            ('PENREVERSE', True, 'reverse'),
        ):
            for colour, expected in (
                ('RED', (255, 0, 0, 1)),
                ('37', (0, 100, 0, 1)),
                ('[0 128 0 1]', (0, 128, 0, 1)),
            ):
                with self.subTest(state=state, colour=colour):
                    it.eval_source('pd')
                    it.eval_source(f'setpen [{state} {colour}]')
                    self.assertEqual(turtle.pen_down, down)
                    self.assertEqual(turtle.pen_mode, mode)
                    self.assertEqual(turtle.rgb, expected)
                    output.clear()
                    it.eval_source('pen')
                    self.assertEqual(output, [state.lower() + '\n'])

    def test_invalid_setpen_does_not_partially_change_state(self):
        it, _, turtle, _ = self.build()
        it.eval_source('setpen [penreverse red]')
        before = (turtle.rgb, turtle.pen_down, turtle.pen_mode)
        for spec in ('[PU blue]', '[pendown 139]', '[penup [0 0 0 2]]', '[penup]', 'red'):
            with self.subTest(spec=spec), self.assertRaises(LogoError):
                it.eval_source(f'setpen "{spec}' if spec == 'red' else f'setpen {spec}')
            self.assertEqual((turtle.rgb, turtle.pen_down, turtle.pen_mode), before)

    def test_pendown_returns_terrapin_pen_to_paint_mode(self):
        it, _, turtle, _ = self.build()
        it.eval_source('pe pd')
        self.assertTrue(turtle.pen_down)
        self.assertEqual(turtle.pen_mode, 'paint')

    def test_default_alpha_only_affects_subsequent_pen_colours(self):
        it, canvas, turtle, _ = self.build()
        it.eval_source('setalpha 0.5')
        self.assertEqual(turtle.rgb, (0, 0, 0, 1))
        it.eval_source('setpc "red')
        self.assertEqual(turtle.rgb, (255, 0, 0, 0.5))
        it.eval_source('setpc [0 38 255]')
        self.assertEqual(turtle.rgb, (0, 38, 255, 0.5))
        it.eval_source('setpen [pendown [255 0 0 0.3]]')
        self.assertEqual(turtle.rgb, (255, 0, 0, 0.3))
        it.eval_source('setbg "red')
        self.assertEqual(canvas.bg, (255, 0, 0, 1))
        it.eval_source('setpc 138')
        self.assertEqual(turtle.rgb, (0, 0, 0, 0))

    def test_transparency_composites_over_strokes_and_changing_background(self):
        it, canvas, _, _ = self.build()
        it.eval_source('setpc [255 0 0 0.5] dot [0 0]')
        px, py = canvas.to_pixel(0, 0)
        pixel = canvas.pix[py][px]
        self.assertEqual(pixel, (255, 0, 0, 0.5))
        self.assertEqual(canvas.display_colour(pixel), (255, 128, 128))
        it.eval_source('setbg "blue')
        self.assertEqual(canvas.pix[py][px], pixel)
        self.assertEqual(canvas.display_colour(pixel), (128, 0, 128))
        it.eval_source('setpc [0 0 255 0.5] dot [0 0]')
        self.assertEqual(canvas.pix[py][px], (85, 0, 170, 0.75))

    def test_invisible_colour_does_not_draw_or_show_a_marker(self):
        it, canvas, turtle, _ = self.build()
        it.eval_source('setpc 138 fd 5 dot [0 0]')
        self.assertEqual(turtle.y, 5)
        self.assertEqual(turtle.strokes, [])
        self.assertTrue(all(pixel is None for row in canvas.pix for pixel in row))
        self.assertEqual(canvas._overlay(turtle), set())

    def test_filled_restores_colour_queries_even_when_body_fails(self):
        for mode in ('ucblogo', 'terrapin'):
            output = []
            it, _, turtle = build(10, 5, 1, output.append, colour_mode=mode)
            it.eval_source('setpc "red')
            before = turtle.rgb, turtle.pen_colour_spec
            it.eval_source('filled "blue [setpc "green]')
            self.assertEqual((turtle.rgb, turtle.pen_colour_spec), before)
            with self.assertRaises(LogoError):
                it.eval_source('filled "blue [setpc "green notacommand]')
            self.assertEqual((turtle.rgb, turtle.pen_colour_spec), before)

    def test_ucblogo_palette_commands_cannot_change_terrapin_indices(self):
        it, _, _, _ = self.build()
        for source in ('setpalette 12 [0 0 0]', 'palette 12'):
            with self.subTest(source=source), self.assertRaises(LogoError):
                it.eval_source(source)

    def test_transparent_stroke_has_uniform_opacity_at_brush_and_animation_joins(self):
        for render in ('braille', 'half', 'kitty'):
            for animated in (False, True):
                it, canvas, turtle, _ = self.build(render)
                with self.subTest(render=render, animated=animated):
                    if animated:
                        turtle.frame_cb = lambda: None
                        turtle.input_cb = lambda seconds: False
                    it.eval_source('setpc [255 0 0 0.5] setpensize 3 fd 24')
                    pixels = [p for row in canvas.pix for p in row if p is not None]
                    self.assertTrue(pixels)
                    self.assertLessEqual(max(p[3] for p in pixels), 0.5)
                    if render != 'kitty':
                        self.assertEqual({p[3] for p in pixels}, {0.5})

    def test_fill_requires_pendown_painting(self):
        for state in ('penup', 'penerase', 'penreverse'):
            it, canvas, _, _ = self.build()
            with self.subTest(state=state):
                it.eval_source(f'setpc "red {state} fill')
                self.assertTrue(all(p is None for row in canvas.pix for p in row))
                it.eval_source('pd fill')
                self.assertTrue(all(p == (255, 0, 0, 1) for row in canvas.pix for p in row))

    def test_fill_stops_at_closed_border(self):
        it, canvas, _, _ = self.build()
        it.eval_source('repeat 4 [fd 20 rt 90] pu setpos [7 7] pd setpc "red fill')
        px, py = canvas.to_pixel(7, 7)
        self.assertEqual(canvas.pix[py][px], (255, 0, 0, 1))
        self.assertIsNone(canvas.pix[0][0])

    def test_fill_tolerance_thresholds(self):
        from termlogo.canvas import Canvas

        for alpha, tolerance, crossed in (
            (0.25, 0, False),
            (0.25, 0.25, False),
            (0.25, 0.25001, True),
            (0.25, 0.5, True),
            (1, 0.5, False),
            (1, 1, True),
        ):
            with self.subTest(alpha=alpha, tolerance=tolerance):
                canvas = Canvas(3, 1, cell=(1, 2))
                canvas.alpha = True
                for y in range(canvas.height):
                    canvas.plot(1, y, (0, 0, 0, alpha))
                canvas.fill(0, 0, (255, 0, 0, 1), tolerance)
                self.assertEqual(canvas.pix[0][2] is not None, crossed)

    def test_filling_again_with_transparency_terminates_and_accumulates_alpha(self):
        it, canvas, _, _ = self.build(cols=4, rows=2)
        it.eval_source('setpc [255 0 0 0.5] fill fill')
        self.assertTrue(all(p == (255, 0, 0, 0.75) for row in canvas.pix for p in row))

    def test_fill_one_crosses_other_colours_even_when_start_matches_pen(self):
        it, canvas, _, _ = self.build(cols=4, rows=2)
        it.eval_source('setpc "blue dot [1 1] setpc "red dot [0 0] (fill 1)')
        self.assertTrue(all(p == (255, 0, 0, 1) for row in canvas.pix for p in row))

    def test_invalid_fill_and_alpha_values_are_errors(self):
        it, _, _, _ = self.build()
        for source in ('(fill -0.1)', '(fill 1.1)', 'setalpha -1', 'setalpha 2'):
            with self.subTest(source=source), self.assertRaises(LogoError):
                it.eval_source(source)

    def test_coloured_marker_and_all_renderers_accept_rgba(self):
        from termlogo.renderers import frame

        for render in ('braille', 'half', 'kitty'):
            it, canvas, turtle, _ = self.build(render, cols=8, rows=4)
            with self.subTest(render=render):
                it.eval_source('setpc [255 0 0 0.5] fd 2 label "test setbg [0 0 255 0.5]')
                self.assertTrue(frame(render, canvas, turtle))
                self.assertEqual(canvas._marker_colour(turtle), turtle.rgb)

    def test_resize_preserves_alpha_and_clipped_artwork(self):
        from termlogo.canvas import Canvas

        it, canvas, _, _ = self.build()
        it.eval_source('setpc [255 0 0 0.5] dot [30 0]')
        small = Canvas(4, 2)
        canvas.copy_to(small)
        restored = Canvas(canvas.cols, canvas.rows)
        small.copy_to(restored)
        self.assertTrue(restored.alpha)
        self.assertEqual(restored.bg, canvas.bg)
        self.assertEqual(restored.pix, canvas.pix)

    def test_rgba_svg_and_png_exports(self):
        it, canvas, _, _ = self.build(cols=4, rows=2)
        it.eval_source('setpc [255 0 0 0.5] dot [0 0]')
        svg = ET.fromstring(canvas.to_svg(pixel=1))
        self.assertEqual(svg[0].attrib['fill-opacity'], '0')
        self.assertEqual(svg[1].attrib['fill-opacity'], '0.5')
        png = canvas.to_png(pixel=1)
        self.assertEqual(png[25], 6)
        offset, chunks = 8, []
        while offset < len(png):
            size = struct.unpack('>I', png[offset : offset + 4])[0]
            if png[offset + 4 : offset + 8] == b'IDAT':
                chunks.append(png[offset + 8 : offset + 8 + size])
            offset += size + 12
        raw = zlib.decompress(b''.join(chunks))
        px, py = canvas.to_pixel(0, 0)
        index = py * (1 + canvas.width * 4) + 1 + px * 4
        self.assertEqual(raw[index : index + 4], bytes((255, 0, 0, 128)))

    def test_compositing_invisible_and_opaque_colours(self):
        self.assertEqual(composite((1, 2, 3, 0), (4, 5, 6, 0.5)), (4, 5, 6, 0.5))
        self.assertEqual(composite((1, 2, 3, 1), (4, 5, 6, 0.5)), (1, 2, 3, 1))
        self.assertEqual(composite((1, 2, 3, 0.5), None), (1, 2, 3, 0.5))


class ColourModeCLITests(unittest.TestCase):
    def test_terrapin_cli_and_us_option_alias(self):
        for flag in ('--colour-mode', '--color-mode'):
            output = io.StringIO()
            with self.subTest(flag=flag), contextlib.redirect_stdout(output):
                status = main([flag, 'terrapin', '--no-canvas', '-e', 'setpc "red pc count colors'])
                self.assertEqual(status, 0)
                self.assertEqual(output.getvalue(), '[255 0 0 1]\n139\n')

    def test_existing_ucblogo_colour_semantics_are_unchanged(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(['--no-canvas', '-e', 'setpc 4 show pc setbg 1 show bg']), 0)
        self.assertEqual(output.getvalue(), '4\n1\n')
        it, canvas, turtle = build(10, 5, 1, lambda text: None)
        it.eval_source('setpc [100 0 0] pe pd')
        self.assertEqual(turtle.rgb, (255, 0, 0))
        self.assertEqual(canvas.bg, (0, 0, 0))
        self.assertFalse(canvas.alpha)
        self.assertEqual(turtle.pen_mode, 'erase')
        with self.assertRaises(LogoError):
            it.eval_source('pc')

    def test_ucblogo_random_range_is_unchanged(self):
        from unittest.mock import call, patch

        it, _, _ = build(10, 5, 1, lambda text: None)
        with patch('termlogo.primitives_data.random.randrange', side_effect=(0, 138)) as draw:
            it.eval_source('make "first random 139 make "last random 139')
            self.assertEqual(it.lookup('first'), 0)
            self.assertEqual(it.lookup('last'), 138)
            self.assertEqual(draw.call_args_list, [call(139), call(139)])

    def test_interactive_continuation_retains_terrapin_mode(self):
        from unittest.mock import patch

        with patch('termlogo.__main__.repl', return_value=0) as enter_repl:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(
                    main(['--colour-mode', 'terrapin', '--no-canvas', '-e', 'setpc "red', '-i']),
                    0,
                )
        turtle = enter_repl.call_args.kwargs['interpreter'].turtle
        self.assertEqual(turtle.colour_mode, 'terrapin')
        self.assertEqual(turtle.rgb, (255, 0, 0, 1))
