#!/usr/bin/env python3
"""Real GTK event/adjustment check; no hardware/input mocks and no persistent data."""
from pathlib import Path
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from overmind.desktop import Desktop,CLOUD_FORM_DEFAULTS
from overmind.lab import DEFAULTS
from gi.repository import Gtk,Gdk


def pump():
    while Gtk.events_pending():Gtk.main_iteration_do(False)


def controls(root):
    result=[]
    if isinstance(root,(Gtk.SpinButton,Gtk.ComboBox,Gtk.Range)):result.append(root)
    if isinstance(root,Gtk.Container):
        for child in root.get_children():result.extend(controls(child))
    return result


def value(w):
    return w.get_value() if isinstance(w,(Gtk.SpinButton,Gtk.Range)) else (w.get_active(),w.get_child().get_text() if w.get_has_entry() else None)

with tempfile.TemporaryDirectory() as temporary:
    app=Desktop(Path(temporary)/'lab',skin_root=Path(temporary)/'skins');app.show_all();pump()
    app.role_widgets['student'][0].set_active_id('local_lora');pump()
    assert app.lora_card.get_visible() and app.lora_device.get_mapped(),'Optional training controls must be visible'
    tested=0;scrolled=0
    for page in range(app.tabs.get_n_pages()):
        app.tabs.set_current_page(page);pump()
        for control in controls(app.tabs.get_nth_page(page)):
            control.grab_focus();pump();before=value(control)
            ancestor=control.get_parent()
            while ancestor and not isinstance(ancestor,Gtk.ScrolledWindow):ancestor=ancestor.get_parent()
            if ancestor:
                adjustment=ancestor.get_vadjustment();adjustment.set_value(adjustment.get_lower());pump()
                old_scroll=adjustment.get_value()
            for direction in (Gdk.ScrollDirection.DOWN,Gdk.ScrollDirection.SMOOTH):
                event=Gdk.Event.new(Gdk.EventType.SCROLL);event.window=control.get_window();event.send_event=True
                event.set_device(Gdk.Display.get_default().get_default_seat().get_pointer())
                event.direction=direction;event.delta_y=1;event.delta_x=0
                control.emit('scroll-event',event)
                pump();assert value(control)==before,(page,type(control).__name__,before,value(control))
            if ancestor and control.get_mapped() and control.get_sensitive() and adjustment.get_upper()>adjustment.get_page_size():
                assert adjustment.get_value()>old_scroll,f'Containing page did not scroll: page {page}, {type(control).__name__}'
                scrolled+=1
            tested+=1
    app.reset_configuration()
    app.tabs.set_current_page(0);pump()
    spin=app.spins['epochs'];spin.grab_focus()
    Gtk.bindings_activate(spin,Gdk.KEY_Up,Gdk.ModifierType(0));assert spin.get_value_as_int()==19
    spin.spin(Gtk.SpinType.STEP_FORWARD,1);assert spin.get_value_as_int()==20
    spin.set_text('7');spin.update();assert spin.get_value_as_int()==7
    app.role_widgets['student'][0].set_active_id('ollama');assert app.role_widgets['student'][0].get_active_id()=='ollama'
    app.role_widgets['mentor'][0].set_active_id('openai');app.api_key.set_text('fixture-reset-preserved')
    app.prepared_dataset={'fixture':'unsaved'};app.dataset_path='fixture.json';app.checkpoint_path='fixture.json'
    app.objective.set_text('Changed');app.attempts.set_value(7)
    for key,w in app.spins.items():w.set_value(w.get_adjustment().get_upper())
    for w in app.cloud_fields.values():w.set_text('99')
    app.cloud_authorized.set_active(True);app.cloud_sharing.set_active(True);app.consent.set_active(True)
    app.lora_spins['rank'].set_value(32);app.lora_license.set_text('fixture permission');app.style_prompt.set_text('fixture style')
    skin=app.skin_id;app.reset_configuration()
    assert app.api_key.get_text()=='fixture-reset-preserved'
    assert app.skin_id==skin and app.selected is None and not app.store.list()
    assert not app.prepared_dataset and not app.dataset_path and not app.checkpoint_path
    assert app.objective.get_text()==DEFAULTS['objective']
    assert app.attempts.get_value_as_int()==DEFAULTS['attempts']
    for key,w in app.spins.items():assert w.get_value_as_int()==DEFAULTS[key]
    for role,(combo,url,model,_,_) in app.role_widgets.items():
        assert combo.get_active_id()==DEFAULTS[role]['kind'] and not model.get_child().get_text()
        assert url.get_text()=='http://127.0.0.1:11434'
    for key,w in app.cloud_fields.items():assert w.get_text()==CLOUD_FORM_DEFAULTS[key]
    from overmind.lora import OPTIONS
    for key,w in app.lora_spins.items():assert w.get_value_as_int()==OPTIONS[key]
    assert app.lora_device.get_active_id()=='cpu' and app.lora_precision.get_active_id()=='fp32'
    assert not app.lora_license.get_text() and not app.style_prompt.get_text()
    assert not any(w.get_active() for w in (app.cloud_authorized,app.cloud_sharing,app.consent))
    app.manager.stop();app.destroy()
print(f'GTK parameter smoke passed: {tested} controls, {scrolled} scrolling contexts; deliberate edits and complete reset verified.')
