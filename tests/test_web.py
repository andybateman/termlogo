import unittest

from termlogo.web import Session


class Recorder:
    def __init__(self):
        self.events = []

    def __call__(self, kind, *args):
        self.events.append((kind, *args))

    def of(self, kind):
        return [e[1:] for e in self.events if e[0] == kind]

    def text(self):
        return ''.join(args[0] for args in self.of('out'))


def session(**kwargs):
    post = Recorder()
    return Session(post, width=200, height=120, **kwargs), post


class WebSessionTests(unittest.TestCase):
    def test_a_run_prints_draws_and_reports_done(self):
        s, post = session()
        self.assertEqual(s.run('print 2 + 3 repeat 4 [fd 30 rt 90]', speed=0), '')
        self.assertEqual(post.text(), '5\n')
        self.assertEqual(post.of('done'), [('',)])
        png, labels = post.of('frame')[-1]
        self.assertTrue(bytes(png).startswith(b'\x89PNG'))
        self.assertEqual(labels, [])
        self.assertEqual(len(s.turtle.strokes), 4)

    def test_errors_are_reported_not_raised(self):
        for source, message in (
            ('fd', 'Not enough inputs to fd'),
            ('repeat 2 [fd 10', 'Unfinished list or TO definition'),
            ('print :nothing', 'nothing has no value'),
            ('goto "nowhere', "Can't find tag nowhere"),
            ('output 1', 'OUTPUT can only be used inside a procedure'),
            ('stop', 'STOP can only be used inside a procedure'),
            ('throw "x', "Can't find catch tag for x"),
            ('to f f f end f', 'Stack overflow'),
        ):
            with self.subTest(source=source):
                s, post = session()
                self.assertEqual(s.run(source, speed=0), message)
                self.assertEqual(post.of('done'), [(message,)])

    def test_bye_ends_the_run_quietly(self):
        s, post = session()
        self.assertEqual(s.run('print 1 bye print 2', speed=0), '')
        self.assertEqual(post.text(), '1\n')

    def test_the_workspace_lasts_between_runs_until_reset(self):
        s, post = session()
        s.run('to sq fd 20 end make "n 7', speed=0)
        s.run('sq print :n', speed=0)
        self.assertEqual(post.text(), '7\n')
        s.reset()
        self.assertEqual(s.run('print :n', speed=0), 'n has no value')
        self.assertEqual(s.turtle.strokes, [])

    def test_reset_keeps_the_speed_and_can_change_the_colour_mode(self):
        s, post = session()
        s.run('', speed=3)
        s.reset('terrapin')
        self.assertEqual(s.turtle.speed, 3)
        self.assertEqual(s.turtle.colour_mode, 'terrapin')

    def test_labels_travel_with_the_picture(self):
        s, post = session()
        s.run('setpc 4 pu setxy 10 20 label "hi', speed=0)
        _, labels = post.of('frame')[-1]
        self.assertEqual(len(labels), 1)
        x, y, text, r, g, b = labels[0]
        self.assertEqual((text, (r, g, b)), ('hi', (255, 0, 0)))
        self.assertAlmostEqual(x, s.canvas.to_pixel(10, 20)[0], delta=2)

    def test_animation_sends_pictures_while_running_but_not_for_every_step(self):
        s, post = session()
        s.turtle.sleep = lambda seconds: None
        s.run('repeat 200 [fd 1]', speed=10)
        frames = len(post.of('frame'))
        self.assertGreaterEqual(frames, 1)
        self.assertLess(frames, 200)

    def test_input_commands_see_the_end_of_input(self):
        s, post = session()
        s.run('print readword print readlist print readchar print keyp', speed=0)
        self.assertEqual(post.text(), '\n\n\nfalse\n')

    def test_cleartext_tells_the_page(self):
        s, post = session()
        s.run('print 1 cleartext', speed=0)
        self.assertEqual(post.of('clear'), [()])

    def test_exports(self):
        s, post = session()
        s.run('setpensize 2 repeat 4 [fd 30 rt 90]', speed=0)
        for kind, magic in (('png', b'\x89PNG'), ('svg', b'<svg'), ('stl', b'')):
            with self.subTest(kind=kind):
                s.export(kind)
                name, mime, data, notes = post.of('file')[-1]
                self.assertTrue(name.endswith(kind))
                self.assertTrue(bytes(data).startswith(magic))
        self.assertIn('triangles', ' '.join(notes))
        with self.assertRaises(ValueError):
            s.export('gif')

    def test_an_empty_drawing_cannot_be_a_stencil(self):
        s, post = session()
        s.export('stl')
        self.assertEqual(len(post.of('file-error')), 1)
        self.assertEqual(post.of('file'), [])


if __name__ == '__main__':
    unittest.main()
