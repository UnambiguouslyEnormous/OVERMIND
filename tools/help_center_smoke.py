#!/usr/bin/env python3
"""Real GTK help interactions with temporary data. No training, inference or network calls.
The status-transition records are explicitly synthetic fixtures, not measured runs.
"""
from pathlib import Path
import sys
import tempfile
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from overmind.desktop import Desktop
from overmind.context_help import missing_parameter_help
from overmind.help_guide import TUTORIALS, TOPICS
from overmind.help_preferences import Preferences
from overmind.help_center import walk
from overmind.skins import load_builtin, export_package
from overmind.stanley import STATES
from gi.repository import Gtk, Gdk


def pump(seconds=.03):
    until=time.monotonic()+seconds
    while True:
        while Gtk.events_pending():Gtk.main_iteration_do(False)
        if time.monotonic()>=until:return
        time.sleep(.005)


def buffer_text(view):return view.get_buffer().get_text(*view.get_buffer().get_bounds(),True)


with tempfile.TemporaryDirectory() as temporary:
    root=Path(temporary);app=Desktop(root/'lab',skin_root=root/'skins')
    try:
        app.show_all();pump();hub=app.help_system
        assert hub.actor.get_mapped() and hub.actor.source, 'Visible Stanley should animate when system motion is enabled'
        # Control-level context is preserved when the launcher takes focus.
        app.role_widgets['student'][0].set_active_id('local_lora');pump()
        app.lora_rate.set_text('0.0002');app.lora_rate.grab_focus();pump()
        assert hub.context.resolve()=='lora.learning_rate'
        hub.launcher.grab_focus();pump();assert hub.context.resolve()=='lora.learning_rate'
        hub.launcher.clicked();pump();companion=hub.companion
        assert companion.get_visible() and companion.title.get_text()==TOPICS['lora.learning_rate'].title
        companion.explain_more();assert TOPICS['lora.learning_rate'].paragraphs[1] in companion.explanation.get_text()
        # Context switches must discard old fields, then fall back to tab explanations.
        app.tabs.set_current_page(3);pump();assert hub.context.field is None and hub.context.resolve()=='workshop'
        app.split_seed.grab_focus();pump();assert hub.context.resolve()=='dataset.seed'
        hub.ask('lora.rank');pump();assert companion.title.get_text()==TOPICS['lora.rank'].title
        app.tabs.set_current_page(2);pump();assert hub.context.resolve()=='evidence'
        assert Gtk.accel_groups_activate(app,Gdk.KEY_F1,Gdk.ModifierType(0));pump();guide=hub.guide
        assert not guide.get_modal() and guide.get_resizable() and guide.navigation.current=='evidence'
        assert not missing_parameter_help(guide) and not missing_parameter_help(companion)
        # Search and ordered/history navigation, including empty results.
        guide.search.set_text('1080');guide.results();assert guide.topics.get_children()
        guide.search.set_text('not-a-real-topic-012345');guide.results();assert not guide.topics.get_children()
        guide.open('lora.rank');guide.open('evidence');guide.back();assert guide.navigation.current=='lora.rank'
        guide.advance(1);assert guide.navigation.current=='lora.alpha'
        guide.advance(-1);assert guide.navigation.current=='lora.rank'
        guide.search.set_text('');guide.results()
        # Every tutorial resolves real controls, without editing configuration or starting workers.
        baseline={key:w.get_value() for key,w in app.spins.items()};style=app.style_prompt.get_text()
        for key in TUTORIALS:
            guide.start_tutorial(key);pump();assert guide.tutorial==key
            for index in range(len(TUTORIALS[key][1])):
                guide.step=index;guide.render_step();pump()
                assert hub.target(guide.current_step().target) is not None
            guide.leave_tutorial()
        guide.start_tutorial('datasets');guide.advance(1);guide.leave_tutorial();guide.resume_tutorial()
        assert guide.tutorial=='datasets' and guide.step==1
        hub.register_target('fixture.target',app.objective);assert hub.target('fixture.target') is app.objective
        guide.start_tutorial('quick-start');guide.step=3;guide.render_step()
        assert not guide.next_button.get_sensitive(), 'A tutorial must not certify a nonexistent run'
        guide.skip_step();assert 3 in guide.skipped
        guide.leave_tutorial();assert hub.highlighted is None
        guide.start_tutorial('interface');guide.advance(1)
        assert hub.prefs.data['tutorials']['interface']['completed']
        guide.start_tutorial('interface');assert not hub.prefs.data['tutorials']['interface']['completed']
        guide.skip_step();assert not hub.prefs.data['tutorials']['interface']['completed']
        assert baseline=={key:w.get_value() for key,w in app.spins.items()} and style==app.style_prompt.get_text()
        assert app.manager.process is None and not app.store.list(), 'Help must not create or start experiments'
        # Real ? popovers route both optional links to the same catalog topic.
        app.tabs.set_current_page(0);app.present();pump()
        trigger=next(w for w in walk(app) if isinstance(w,Gtk.Button) and getattr(w,'_gafaw_help_key',None)=='lora.rank')
        trigger.clicked();pump();popover=trigger._gafaw_help_popover
        next(w for w in walk(popover) if isinstance(w,Gtk.Button) and w.get_label()=='Learn More').clicked();pump()
        assert guide.navigation.current=='lora.rank'
        trigger.clicked();pump()
        next(w for w in walk(popover) if isinstance(w,Gtk.Button) and w.get_label()=='Ask Stanley').clicked();pump()
        assert companion.title.get_text()==TOPICS['lora.rank'].title
        # Context never leaks secret/private field contents into guide or assistant output.
        app.role_widgets['mentor'][0].set_active_id('openai');app.api_key.set_text('fixture-private-do-not-display');app.api_key.grab_focus();pump();hub.ask();pump()
        assert 'fixture-private-do-not-display' not in (companion.explanation.get_text()+buffer_text(guide.article)+companion.quip.get_text())
        # Original gestures, hidden/reduced-motion lifecycle, and system animation preference.
        for state in STATES:hub.actor.play(state,.02)
        hub.preference('reduced_motion',True);assert hub.actor.source is None and companion.actor.source is None
        hub.preference('reduced_motion',False);pump();assert hub.actor.source
        settings=hub.actor.settings;animations=settings.get_property('gtk-enable-animations')
        settings.set_property('gtk-enable-animations',False);assert hub.actor.source is None and companion.actor.source is None
        settings.set_property('gtk-enable-animations',animations)
        # Exercise lifecycle routing with synthetic window-state events; no claim about every compositor.
        event=Gdk.Event.new(Gdk.EventType.WINDOW_STATE);event.new_window_state=Gdk.WindowState.ICONIFIED
        hub.actor.window_state(app,event);assert hub.actor.source is None
        event.new_window_state=Gdk.WindowState(0);hub.actor.window_state(app,event);assert hub.actor.source
        companion.close_window();pump();assert companion.actor.source is None
        hub.preference('sarcasm',False);hub.ask('lora.rank');assert not companion.quip.get_text()
        # Synthetic records test transition routing; no historical-run celebration.
        record={'id':'fixture-only','status':'completed','state':{'report':{}}}
        hub.last_reaction=None;hub.observe(record);assert hub.last_reaction is None
        record['status']='running';hub.observe(record)
        record['status']='failed';hub.observe(record);assert hub.last_reaction[1]=='failed'
        previous=hub.last_reaction;hub.observe(record);assert hub.last_reaction==previous
        hub.compatibility('{"ready": false, "blockers": ["fixture"]}');assert hub.last_reaction[1]=='incompatible'
        # Deliberately poor-contrast skin cannot obscure either help surface.
        custom=load_builtin('black-titanium');custom.manifest['id']='help-reader';custom.manifest['name']='Reader fixture'
        for key in custom.manifest['colors']:custom.manifest['colors'][key]='#ffffff'
        custom.manifest['font']['size']=24
        package=root/'contrast.gafawskin';export_package(custom,package);app.skin_library.install(package)
        for skin in ('black-titanium','phosphor-night','help-reader'):
            app.activate_skin(skin);pump()
            for window in (guide,companion):
                color=window.get_style_context().get_color(Gtk.StateFlags.NORMAL)
                assert min(color.red,color.green,color.blue)>.9
            assert guide.article.get_style_context().get_color(Gtk.StateFlags.NORMAL).red>.9
        app.activate_skin('black-titanium')
        # Preference persistence, complete disabling, and F1 guide fallback.
        guide.resize(1000,730);guide.ontop.set_active(True);companion.ontop.set_active(True);pump(.1)
        guide.close_window();saved=Preferences(hub.prefs.path).data
        assert saved['guide']['ontop'] and saved['companion']['ontop'] and saved['guide']['width']>=640
        hub.preference('stanley',False);pump();app.show_all();pump()
        assert not hub.launcher.get_visible() and not companion.get_visible() and hub.actor.source is None and companion.actor.source is None
        hub.ask('lora.rank');pump();assert guide.get_visible() and guide.navigation.current=='lora.rank' and not companion.get_visible()
        assert not Preferences(hub.prefs.path).data['stanley']
        assert not popover._gafaw_stanley_link.get_visible()
        assert Gtk.accel_groups_activate(app,Gdk.KEY_F1,Gdk.ModifierType.SHIFT_MASK);assert not companion.get_visible()
        # Re-enabling also reveals descendants when the app started with Stanley hidden.
        hub.launcher.get_child().hide();hub.preference('stanley',True);pump()
        assert hub.actor.get_mapped() and hub.actor.source
        hub.preference('stanley',False);assert hub.actor.source is None
        # Capture the real guide using the same widgets on a non-composited surface.
        guide.close_window();guide.open('guide.start')
        surface=Gtk.OffscreenWindow();surface.set_size_request(980,740);surface.get_style_context().add_class('gafaw-guide')
        content=guide.get_child();guide.remove(content);surface.add(content);surface.show_all();pump(.15)
        surface.get_pixbuf().savev('/tmp/gafaw-help-center.png','png',[],[])
        surface.remove(content);guide.add(content);surface.destroy()
        assert not app.store.list()
    finally:
        app.manager.stop();app.destroy();pump()
print('GTK Help Center passed: field/tab context, links, 9 walkthroughs, navigation, private preferences, 3 skins, gestures and complete disable. Status reactions used fixtures; no training/inference ran.')
