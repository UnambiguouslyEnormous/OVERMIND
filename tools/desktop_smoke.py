#!/usr/bin/env python3
"""Exercise the real GTK widgets on an available display; use only temporary data."""
import argparse
import sys
from pathlib import Path
import tempfile
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from overmind.desktop import Desktop
from overmind.skins import load_builtin, export_package, load_package
from gi.repository import Gtk, GLib

parser=argparse.ArgumentParser()
parser.add_argument('--skins',action='store_true',help='Exercise skin export/import, live switching and saved selection')
parser.add_argument('--experiment',action='store_true',help='Also run a real bounded classifier worker and inspect evidence')
args=parser.parse_args()
errors=[]
with tempfile.TemporaryDirectory() as temporary:
    root=Path(temporary)/'lab'
    app=Desktop(root,skin_root=Path(temporary)/'library')
    # The compositor can obscure window captures; offscreen renders the same native widgets.
    surface=Gtk.OffscreenWindow();surface.set_default_size(1280,900)
    content=app.get_child();app.remove(content);surface.add(content);surface.show_all()
    start=time.monotonic()
    def finish():
        try:
            surface.get_pixbuf().savev('/tmp/gafaw-desktop.png','png',[],[])
        finally:
            app.manager.stop();surface.destroy();app.destroy();Gtk.main_quit()
        return False
    def check():
        try:
            if not args.experiment:
                if args.skins:app.tabs.set_current_page(6);GLib.timeout_add(300,finish);return False
                return finish()
            if not app.selected:
                raise RuntimeError(app.status.get_text())
            run=app.store.get(app.selected)
            if run['status']=='completed':
                app.tick()
                assert app.store.read(app.selected,'training-integrity.json')['verified']
                assert app.loss_image.get_pixbuf() is not None
                app.inspect_failures()
                assert 'persistent_failures' in app.science_result.get_buffer().get_text(*app.science_result.get_buffer().get_bounds(),True)
                app.note_editor.get_buffer().set_text('# Smoke experiment\nReal CPU worker, independent held-out evaluation.')
                app.save_notes()
                assert app.store.read(app.selected,'notebook.json')['markdown'].startswith('# Smoke')
                app.tabs.set_current_page(1)
                GLib.timeout_add(300,finish)
                return False
            if run['status'] not in ('running','ready'):raise RuntimeError('Worker status: '+run['status'])
            if time.monotonic()-start>45:raise RuntimeError('GUI experiment exceeded 45-second smoke budget')
            return True
        except Exception as error:
            errors.append(error);finish();return False
    if args.skins:
        assert app.skin_id=='black-titanium'
        skin=load_builtin('phosphor-night');skin.manifest['id']='smoke-community';skin.manifest['name']='Smoke Community'
        package=Path(temporary)/'community.gafawskin';export_package(skin,package)
        app.skin_library.install(package);app.refresh_skins('smoke-community')
        previous=app.skin_provider
        app.apply_selected_skin()
        assert app.skin_id=='smoke-community' and app.skin_provider is not previous
        assert app.skin_library.selected()=='smoke-community'
        color=app.metrics['baseline'].get_style_context().get_color(Gtk.StateFlags.NORMAL)
        assert color.red>.9 and color.green>.7 and color.blue<.7, 'Expected the applied amber metric color'
        assert app.run_button.get_sensitive()
        assert load_package(package).id=='smoke-community'
        app.restore_skin();assert app.skin_id=='black-titanium'
        assert app.skin_library.selected()=='black-titanium'
    if args.experiment:
        app.edit_benchmark();app.use_workshop()
        assert app.prepared_dataset and app.prepared_dataset['provenance']['split_policy']=='preserved'
        app.spins['epochs'].set_value(2);app.run_new()
    GLib.timeout_add(1200,check);Gtk.main()
if errors:raise errors[0]
print('Real GTK smoke passed'+(' including package import/export, live skin switching and saved preference' if args.skins else '')+(' including dataset review, CPU worker, integrity, graph, failures and notes' if args.experiment else '')+'; screenshot: /tmp/gafaw-desktop.png')
