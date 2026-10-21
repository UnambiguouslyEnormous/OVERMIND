"""Launch a terminal in a validated directory without invoking a shell."""
from pathlib import Path
import shutil
import subprocess
from .security import subprocess_environment


def open_terminal(directory):
    path = Path(directory).resolve(strict=True)
    if not path.is_dir():
        raise ValueError('Terminal location must be a directory.')
    candidates = (
        ('x-terminal-emulator', []),
        ('gnome-terminal', ['--working-directory', str(path)]),
        ('konsole', ['--workdir', str(path)]),
        ('xfce4-terminal', ['--working-directory', str(path)]),
        ('kitty', ['--directory', str(path)]),
        ('xterm', []),
    )
    for name, arguments in candidates:
        executable = shutil.which(name)
        if executable:
            subprocess.Popen([executable, *arguments], cwd=path,
                             env=subprocess_environment(), start_new_session=True,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
            return str(path)
    raise RuntimeError(f'No supported terminal installed. Open a terminal manually in: {path}')
