import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from overmind.terminal import open_terminal

class TerminalTests(unittest.TestCase):
    def test_directory_is_literal_and_environment_is_sanitized(self):
        with tempfile.TemporaryDirectory(prefix='gafaw ; $(literal) ') as root:
            with patch('overmind.terminal.shutil.which', side_effect=lambda n:'/usr/bin/xterm' if n=='xterm' else None), patch('overmind.terminal.subprocess.Popen') as launch:
                self.assertEqual(open_terminal(root),str(Path(root).resolve()))
                args, kwargs=launch.call_args
                self.assertEqual(args[0],['/usr/bin/xterm'])
                self.assertEqual(kwargs['cwd'],Path(root).resolve())
                self.assertNotIn('shell',kwargs)
                self.assertNotIn('OPENAI_API_KEY',kwargs['env'])

    def test_missing_terminal_provides_directory(self):
        with tempfile.TemporaryDirectory() as root, patch('overmind.terminal.shutil.which',return_value=None):
            with self.assertRaisesRegex(RuntimeError,root):open_terminal(root)
