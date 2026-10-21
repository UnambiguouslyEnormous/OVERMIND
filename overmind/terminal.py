"""Launch a terminal in a validated directory without invoking a shell."""
from pathlib import Path
import os
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
    environment = subprocess_environment()
    for key in ('DISPLAY', 'WAYLAND_DISPLAY', 'XAUTHORITY', 'XDG_RUNTIME_DIR',
                'DBUS_SESSION_BUS_ADDRESS', 'XDG_SESSION_TYPE'):
        if key in os.environ:environment[key] = os.environ[key]
    for name, arguments in candidates:
        executable = shutil.which(name)
        if executable:
            subprocess.Popen([executable, *arguments], cwd=path,
                             env=environment, start_new_session=True,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
            return str(path)
    raise RuntimeError(f'No supported terminal installed. Open a terminal manually in: {path}')
