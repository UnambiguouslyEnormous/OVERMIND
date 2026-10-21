#!/usr/bin/env python3
"""Render the real GTK window on an available desktop; no persistent data used."""
import sys
from pathlib import Path
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from overmind.desktop import Desktop
from gi.repository import Gtk, Gdk, GLib

with tempfile.TemporaryDirectory() as root:
    app = Desktop(root)
    app.show_all()
    def capture():
        image = Gdk.pixbuf_get_from_window(app.get_window(), 0, 0,
                                         app.get_allocated_width(), app.get_allocated_height())
        image.savev('/tmp/gafaw-desktop.png', 'png', [], [])
        app.manager.stop()
        app.destroy()
        Gtk.main_quit()
        return False
    GLib.timeout_add(1200, capture)
    Gtk.main()
print('Real GTK smoke passed; screenshot: /tmp/gafaw-desktop.png')
