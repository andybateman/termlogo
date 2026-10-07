import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from termlogo import __version__

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == 'posix', 'the build script needs a POSIX shell')
class PyzBuildTests(unittest.TestCase):
    def test_single_file_build_runs_a_program_without_the_source_tree(self):
        with tempfile.TemporaryDirectory() as work:
            pyz = Path(work) / 'termlogo.pyz'
            built = subprocess.run(
                ['sh', str(ROOT / 'tools' / 'build_pyz.sh'), str(pyz)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(built.returncode, 0, built.stderr)
            self.assertTrue(os.access(pyz, os.X_OK))
            # Run from another directory with a clean path, so only the archive is used.
            env = {k: v for k, v in os.environ.items() if k != 'PYTHONPATH'}
            version = subprocess.run(
                [sys.executable, str(pyz), '--version'],
                capture_output=True,
                text=True,
                cwd=work,
                env=env,
                check=False,
            )
            self.assertIn(__version__, version.stdout)
            shown = subprocess.run(
                [sys.executable, str(pyz), '--no-canvas', '-e', 'print 2 + 3'],
                capture_output=True,
                text=True,
                cwd=work,
                env=env,
                check=False,
            )
            self.assertEqual(shown.stdout, '5\n')


class WebBuildTests(unittest.TestCase):
    def build(self, out):
        return subprocess.run(
            [sys.executable, str(ROOT / 'tools' / 'build_web.py'), '--out', str(out)],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_the_page_records_which_version_it_was_built_from(self):
        with tempfile.TemporaryDirectory() as work:
            out = Path(work) / 'site'
            result = self.build(out)
            self.assertEqual(result.returncode, 0, result.stderr)
            config = json.loads((out / 'config.json').read_text())
            self.assertEqual(config['version'], __version__)
            self.assertFalse(config['bundled'])
            for name in (
                'index.html',
                'app.js',
                'worker.js',
                'coi-sw.js',
                'termlogo.zip',
                'examples.json',
                'help.json',
            ):
                self.assertTrue((out / name).is_file(), name)

    def test_every_file_the_page_loads_is_requested_with_a_content_stamp(self):
        with tempfile.TemporaryDirectory() as work:
            out = Path(work) / 'site'
            self.assertEqual(self.build(out).returncode, 0)
            stamp = json.loads((out / 'config.json').read_text())['build']
            self.assertRegex(stamp, r'^[0-9a-f]{10}$')
            for name, needle in (
                ('index.html', f'app.js?v={stamp}'),
                ('index.html', f'style.css?v={stamp}'),
                ('app.js', f'worker.js?v={stamp}'),
                ('app.js', f'examples.json?v={stamp}'),
                ('app.js', f'help.json?v={stamp}'),
                ('worker.js', f'termlogo.zip?v={stamp}'),
            ):
                self.assertIn(needle, (out / name).read_text(), f'{name}: {needle}')
            for name in ('index.html', 'app.js', 'worker.js'):
                self.assertNotIn('__BUILD__', (out / name).read_text())

    def test_the_stamp_changes_when_the_content_does(self):
        import importlib.util
        import shutil

        spec = importlib.util.spec_from_file_location('build_web', ROOT / 'tools' / 'build_web.py')
        build_web = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(build_web)

        def stamp(folder, extra=b''):
            folder.mkdir()
            for page in (ROOT / 'web').iterdir():
                shutil.copy(page, folder / page.name)
            build_web.build_package(folder / 'termlogo.zip')
            build_web.build_examples(folder / 'examples.json')
            build_web.build_help(folder / 'help.json')
            with open(folder / 'examples.json', 'ab') as f:
                f.write(extra)
            return build_web.stamp_files(folder)

        with tempfile.TemporaryDirectory() as work:
            same = stamp(Path(work) / 'a'), stamp(Path(work) / 'b')
            changed = stamp(Path(work) / 'c', extra=b' ')
        self.assertEqual(same[0], same[1])
        self.assertNotEqual(changed, same[0])

    def test_building_twice_gives_identical_files(self):
        with tempfile.TemporaryDirectory() as work:
            first, second = Path(work) / 'a', Path(work) / 'b'
            self.assertEqual(self.build(first).returncode, 0)
            self.assertEqual(self.build(second).returncode, 0)
            for name in ('termlogo.zip', 'config.json', 'app.js'):
                self.assertEqual((first / name).read_bytes(), (second / name).read_bytes(), name)

    def test_it_will_not_replace_a_folder_it_did_not_make(self):
        with tempfile.TemporaryDirectory() as work:
            precious = Path(work) / 'precious'
            precious.mkdir()
            (precious / 'notes.txt').write_text('keep me')
            result = self.build(precious)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((precious / 'notes.txt').read_text(), 'keep me')


@unittest.skipUnless(os.name == 'posix', 'the publish script needs a POSIX shell')
class PublishSiteTests(unittest.TestCase):
    def git(self, folder, *args):
        env = dict(
            os.environ,
            GIT_AUTHOR_NAME='t',
            GIT_AUTHOR_EMAIL='t@example.com',
            GIT_COMMITTER_NAME='t',
            GIT_COMMITTER_EMAIL='t@example.com',
        )
        return subprocess.run(
            ['git', '-C', str(folder), *args], capture_output=True, text=True, env=env, check=True
        ).stdout

    def publish(self, site, *args):
        return subprocess.run(
            ['sh', str(ROOT / 'tools' / 'publish_site.sh'), str(site), *args],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_it_commits_the_build_once_and_then_has_nothing_to_do(self):
        with tempfile.TemporaryDirectory() as work:
            site = Path(work) / 'site'
            site.mkdir()
            self.git(site, 'init', '-q')
            (site / 'index.html').write_text('home')
            self.git(site, 'add', '.')
            self.git(site, 'commit', '-q', '-m', 'start')
            first = self.publish(site, '--no-push')
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertIn('Committed: Update /termlogo/ to v' + __version__, first.stdout)
            self.assertIn('Update /termlogo/ to', self.git(site, 'log', '-1', '--format=%s'))
            self.assertTrue((site / 'termlogo' / 'index.html').is_file())
            self.assertEqual((site / 'index.html').read_text(), 'home')
            again = self.publish(site, '--no-push')
            self.assertEqual(again.returncode, 0, again.stderr)
            self.assertIn('Nothing to publish', again.stdout)
            self.assertEqual(self.git(site, 'rev-list', '--count', 'HEAD').strip(), '2')

    def test_it_refuses_a_site_with_other_changes_or_that_is_not_a_checkout(self):
        with tempfile.TemporaryDirectory() as work:
            self.assertNotEqual(self.publish(Path(work) / 'missing').returncode, 0)
            site = Path(work) / 'site'
            site.mkdir()
            self.git(site, 'init', '-q')
            (site / 'draft.txt').write_text('unsaved work')
            result = self.publish(site, '--no-push')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('uncommitted changes', result.stderr)
            self.assertFalse((site / 'termlogo').exists())


if __name__ == '__main__':
    unittest.main()
