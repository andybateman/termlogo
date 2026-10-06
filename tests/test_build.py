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


if __name__ == '__main__':
    unittest.main()
