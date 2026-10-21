#!/usr/bin/env python3
"""Focused real-display help check. Temporary stores only; no training, downloads or provider calls."""
from pathlib import Path
import sys
import tempfile
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from overmind.desktop import Desktop
from overmind.context_help import missing_parameter_help, short_help, no_help
from overmind.help_content import TOPICS
from overmind.skins import load_builtin, export_package
from gi.repository import Gtk, Gdk


def pump(seconds=0):
    end=time.monotonic()+seconds
    while True:
        while Gtk.events_pending():Gtk.main_iteration_do(False)
        if time.monotonic()>=end:return
        time.sleep(.01)


def widgets(root):
    yield root
    if isinstance(root,Gtk.Container):
        for child in root.get_children():yield from widgets(child)


def escape(popover):
    event=Gdk.Event.new(Gdk.EventType.KEY_PRESS)
    event.window=popover.get_window();event.keyval=Gdk.KEY_Escape
    event.set_device(Gdk.Display.get_default().get_default_seat().get_keyboard())
    assert popover.emit('key-press-event',event)
    pump(.2)
    assert not popover.get_visible()


with tempfile.TemporaryDirectory() as temporary:
    app=Desktop(Path(temporary)/'lab',skin_root=Path(temporary)/'skins')
    try:
        app.show_all();pump(.2)
        app.role_widgets['student'][0].set_active_id('local_lora');pump()
        assert not missing_parameter_help(app), 'A parameter control needs an explicit explanation or exemption'
        before={key:w.get_value() for key,w in app.spins.items()}
        covered=set();count=0
        for page in range(app.tabs.get_n_pages()):
            app.tabs.set_current_page(page);pump()
            triggers=[w for w in widgets(app.tabs.get_nth_page(page)) if w.get_style_context().has_class('gafaw-help-trigger')]
            assert triggers, f'Workspace {page} has no contextual explanations'
            for trigger in triggers:
                assert trigger.get_mapped(), (page,trigger.get_accessible().get_name())
                assert trigger.get_can_focus() and trigger.get_accessible().get_name().startswith('Help: ')
                assert len(trigger.get_tooltip_text())<=120
                assert trigger._gafaw_help_popover is None, 'Explanation should be lazy'
                trigger.grab_focus()
                # Send a real GDK key event to the focused GTK widget.
                event=Gdk.Event.new(Gdk.EventType.KEY_PRESS)
                event.window=trigger.get_window();event.keyval=Gdk.KEY_space if count%2 else Gdk.KEY_Return
                event.set_device(Gdk.Display.get_default().get_default_seat().get_keyboard())
                assert trigger.emit('key-press-event',event)
                pump(.3)
                popover=trigger._gafaw_help_popover
                assert popover and popover.get_visible(),trigger._gafaw_help_key
                assert popover.get_accessible().get_name()==TOPICS[trigger._gafaw_help_key].title
                rendered=[w.get_text() for w in widgets(popover) if isinstance(w,Gtk.Label)]
                assert all(p in rendered for p in TOPICS[trigger._gafaw_help_key].paragraphs)
                assert app.get_focus()==popover._gafaw_close, 'Opening help should focus its Close action'
                escape(popover)
                assert trigger.has_focus(), 'Escape should return focus to the help button'
                trigger.clicked();pump(.2)
                assert popover.get_visible(), 'Mouse click must reopen the same explanation'
                popover._gafaw_close.clicked();pump(.2)
                assert not popover.get_visible() and trigger.has_focus()
                covered.add(trigger._gafaw_help_key);count+=1
        assert set(TOPICS)==covered, sorted(set(TOPICS)-covered)
        # Check explanatory text independently of community skin colors and live replacement.
        app.tabs.set_current_page(6);pump()
        trigger=next(w for w in widgets(app.tabs.get_nth_page(6)) if hasattr(w,'_gafaw_help_popover'))
        custom=load_builtin('black-titanium');custom.manifest['id']='help-contrast';custom.manifest['name']='Help Contrast'
        for key in custom.manifest['colors']:custom.manifest['colors'][key]='#ffffff'
        custom.manifest['font']['size']=24
        package=Path(temporary)/'contrast.gafawskin';export_package(custom,package);app.skin_library.install(package)
        trigger.clicked();pump(.2)
        for skin in ('black-titanium','phosphor-night','help-contrast'):
            app.activate_skin(skin);pump(.15)
            popover=trigger._gafaw_help_popover
            assert popover.get_visible(), 'Switching skins should keep help open'
            for widget in widgets(popover):
                if isinstance(widget,Gtk.Label):
                    color=widget.get_style_context().get_color(Gtk.StateFlags.NORMAL)
                    assert color.red>.9 and color.green>.9 and color.blue>.9, (skin,color)
        escape(trigger._gafaw_help_popover)
        # The audit must flag future unexplained parameters rather than fabricate help.
        new=Gtk.SpinButton.new_with_range(1,10,1);app.setup_content.pack_start(new,False,False,0)
        assert new in missing_parameter_help(app)
        short_help(new,'experiment.epochs');assert not missing_parameter_help(app)
        other=Gtk.ComboBoxText();app.setup_content.pack_start(other,False,False,0)
        assert other in missing_parameter_help(app)
        no_help(other,'Fixture control with an obvious label');assert not missing_parameter_help(app)
        assert before=={key:w.get_value() for key,w in app.spins.items()}
        assert not app.store.list(), 'Exploring help must not create experiments'
    finally:
        app.manager.stop();app.destroy();pump()
print(f'GTK help smoke passed: {count} explanations across 7 workspaces; keyboard/mouse, focus, 3 skins and missing-help audit.')
