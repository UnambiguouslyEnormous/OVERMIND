"""Non-modal offline guide, tutorial highlighting and field-aware Stanley companion."""
import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk, Gdk, Pango
from .context_help import contextual, short_help, with_help
from .help_content import TOPICS, SHORT_HELP, tooltip_text
from .help_guide import (ARTICLES, ARTICLE_ORDER, TAB_TOPICS, TUTORIALS, STEPS, QUIPS,
                         Context, article_key, search, reaction, verified_report)
from .help_preferences import Preferences, Navigation
from .stanley import StanleyActor


def column(spacing=10):return Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=spacing)
def row(spacing=8):return Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,spacing=spacing)
def text(value='',heading=False):
    w=Gtk.Label(label=value,xalign=0);w.set_line_wrap(True);w.set_max_width_chars(70);w.set_selectable(True)
    if heading:w.get_style_context().add_class('help-heading')
    return w

def action(title,callback):
    w=Gtk.Button(label=title);w.connect('clicked',lambda *_:callback());return w


def walk(widget):
    yield widget
    if isinstance(widget,Gtk.Container):
        for child in widget.get_children():yield from walk(child)


class HelpWindow(Gtk.Window):
    """Shared geometry/persistence without modal or permanent stacking assumptions."""
    def __init__(self,hub,title,pref):
        super().__init__(title=title);self.hub=hub;self.pref=pref
        self._gafaw_help_controller=hub
        self.get_style_context().add_class('gafaw-guide')
        self.set_transient_for(hub.app);self.set_destroy_with_parent(True);self.set_modal(False)
        saved=hub.prefs.data[pref]
        display=Gdk.Display.get_default();monitor=display.get_primary_monitor() or display.get_monitor(0)
        area=monitor.get_workarea() if monitor else None
        self.resize(min(saved['width'],area.width) if area else saved['width'],min(saved['height'],area.height) if area else saved['height'])
        if saved['x'] is not None and saved['y'] is not None:
            self.move(max(area.x,min(saved['x'],area.x+area.width-100)) if area else saved['x'],
                      max(area.y,min(saved['y'],area.y+area.height-100)) if area else saved['y'])
        self.set_keep_above(saved['ontop'])
        self.connect('delete-event',self.close_window)
        self.connect('key-press-event',self.keys)
        self.ontop=Gtk.CheckButton(label='Always on Top');self.ontop.set_active(saved['ontop'])
        short_help(self.ontop,'help.ontop');self.ontop.connect('toggled',self.top_changed)

    def top_changed(self,widget):
        self.set_keep_above(widget.get_active());self.hub.prefs.data[self.pref]['ontop']=widget.get_active();self.hub.save()

    def remember(self):
        if not self.get_realized():return
        width,height=self.get_size();x,y=self.get_position()
        self.hub.prefs.data[self.pref].update(width=width,height=height,x=x,y=y);self.hub.save()

    def close_window(self,*_):self.remember();self.hide();return True

    def keys(self,_,event):
        if event.keyval==Gdk.KEY_Escape:self.close_window();return True
        if event.keyval==Gdk.KEY_F1:
            if event.state&Gdk.ModifierType.SHIFT_MASK:self.hub.ask()
            else:self.hub.open_guide(self.hub.context.resolve())
            return True
        return False


class GuideWindow(HelpWindow):
    def __init__(self,hub):
        super().__init__(hub,'GAFAW · Offline Help Center','guide');self.set_size_request(640,440)
        self.navigation=Navigation();self.tutorial=None;self.step=0;self.skipped=set();self.rebuilding=False
        outer=column(10);outer.set_border_width(14);self.add(outer)
        toolbar=row()
        self.back_button=action('Back',self.back);self.previous=action('Previous',lambda:self.advance(-1));self.next_button=action('Next',lambda:self.advance(1))
        for w in (self.back_button,self.previous,self.next_button):toolbar.pack_start(w,False,False,0)
        toolbar.pack_start(action('Quick Start',lambda:self.start_tutorial('quick-start')),False,False,0)
        toolbar.pack_end(self.ontop,False,False,0);outer.pack_start(toolbar,False,False,0)
        pane=Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL);pane.set_position(240);outer.pack_start(pane,True,True,0)
        left=column();left.set_size_request(185,-1);pane.pack1(left,False,False)
        self.search=Gtk.SearchEntry();self.search.set_placeholder_text('Search offline help…');self.search.set_max_length(200)
        self.search.get_accessible().set_name('Search offline help');contextual(self.search,'help.center')
        self.search.connect('search-changed',lambda *_:self.results());left.pack_start(self.search,False,False,0)
        self.result_count=text();left.pack_start(self.result_count,False,False,0)
        self.topics=Gtk.ListBox();self.topics.set_selection_mode(Gtk.SelectionMode.SINGLE);self.topics.connect('row-selected',self.select_topic)
        self.topics.get_accessible().set_name('Help search results')
        sc=Gtk.ScrolledWindow();sc.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC);sc.add(self.topics);left.pack_start(sc,True,True,0)
        right=column();right.set_border_width(10);pane.pack2(right,True,False)
        chooser=row();self.tutorial_choice=Gtk.ComboBoxText()
        for key,(title,_) in TUTORIALS.items():self.tutorial_choice.append(key,title)
        self.tutorial_choice.set_active_id('quick-start');short_help(self.tutorial_choice,'help.tutorial')
        chooser.pack_start(self.tutorial_choice,True,True,0)
        chooser.pack_start(action('Start / Restart',lambda:self.start_tutorial(self.tutorial_choice.get_active_id())),False,False,0)
        right.pack_start(chooser,False,False,0)
        self.tutorial_status=text();right.pack_start(self.tutorial_status,False,False,0)
        self.resume_button=action('Resume saved walkthrough',self.resume_tutorial);right.pack_start(self.resume_button,False,False,0)
        self.tutorial_choice.connect('changed',lambda *_:self.update_tutorial_status())
        self.article=Gtk.TextView();self.article.set_editable(False);self.article.set_cursor_visible(True);self.article.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.article.set_left_margin(10);self.article.set_right_margin(10);self.article.set_pixels_above_lines(5);self.article.set_pixels_below_lines(5)
        self.article.get_accessible().set_name('Help article and walkthrough instructions')
        self.article.get_buffer().create_tag('guide-title',weight=Pango.Weight.BOLD,size_points=18,foreground='#c4f4ce')
        sc=Gtk.ScrolledWindow();sc.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC);sc.add(self.article);right.pack_start(sc,True,True,0)
        self.tour_actions=row()
        self.show_control=action('Show Control',lambda:self.hub.highlight(self.current_step(),present=True))
        self.skip=action('Skip step',self.skip_step);self.exit_tour=action('Leave walkthrough',self.leave_tutorial)
        for w in (self.show_control,self.skip,self.exit_tour):self.tour_actions.pack_start(w,False,False,0)
        right.pack_start(self.tour_actions,False,False,0)
        self.notice=text();right.pack_start(self.notice,False,False,0)
        preferences=Gtk.Expander(label='Help preferences · Stanley, humor and motion');outer.pack_start(preferences,False,False,0)
        options=column(8);preferences.add(options)
        self.enabled=Gtk.CheckButton(label='Enable Stanley the Stapler');self.enabled.set_active(hub.prefs.data['stanley']);short_help(self.enabled,'help.stanley')
        self.sarcasm=Gtk.CheckButton(label='Allow Stanley’s dry office humor');self.sarcasm.set_active(hub.prefs.data['sarcasm'])
        self.motion=Gtk.CheckButton(label='Reduce animation');self.motion.set_active(hub.prefs.data['reduced_motion'])
        options.pack_start(with_help(self.enabled,'help.stanley'),False,False,0)
        options.pack_start(with_help(self.sarcasm,'help.humor'),False,False,0)
        options.pack_start(with_help(self.motion,'help.motion'),False,False,0)
        self.enabled.connect('toggled',lambda w:hub.preference('stanley',w.get_active()))
        self.sarcasm.connect('toggled',lambda w:hub.preference('sarcasm',w.get_active()))
        self.motion.connect('toggled',lambda w:hub.preference('reduced_motion',w.get_active()))
        self.results();self.render()
        accel=Gtk.AccelGroup();self.add_accel_group(accel)
        key,mods=Gtk.accelerator_parse('<Control>f');accel.connect(key,mods,Gtk.AccelFlags.VISIBLE,lambda *_:self.search.grab_focus() or True)

    def set_article(self,value):
        buffer=self.article.get_buffer();buffer.set_text(value)
        start=buffer.get_start_iter();end=start.copy();end.forward_to_line_end()
        buffer.apply_tag_by_name('guide-title',start,end)

    def results(self):
        self.rebuilding=True
        for child in self.topics.get_children():self.topics.remove(child)
        results=search(self.search.get_text());self.result_count.set_text(f'{len(results)} offline topics')
        for article in results:
            item=Gtk.ListBoxRow();item.article_key=article.key
            caption=Gtk.Label(label=article.title+'\n'+article.category,xalign=0);caption.set_line_wrap(True);caption.set_max_width_chars(25);caption.set_margin_top(7);caption.set_margin_bottom(7)
            item.add(caption);self.topics.add(item)
        self.topics.show_all();self.rebuilding=False

    def select_topic(self,_,item):
        if item and not self.rebuilding:self.open(item.article_key)

    def open(self,key):
        self.leave_tutorial(render=False);self.navigation.visit(article_key(key));self.render()

    def render(self):
        article=ARTICLES[self.navigation.current]
        self.set_article(article.title+'\n\n'+ '\n\n'.join(article.paragraphs))
        self.article.get_accessible().set_name(article.title)
        self.tour_actions.set_no_show_all(True);self.tour_actions.hide()
        self.back_button.set_sensitive(bool(self.navigation.history))
        index=ARTICLE_ORDER.index(self.navigation.current)
        self.previous.set_sensitive(index>0);self.next_button.set_sensitive(index<len(ARTICLE_ORDER)-1);self.next_button.set_label('Next')
        self.notice.set_text(self.hub.prefs.error or 'Offline documentation · no model calls · F1 context help · Ctrl+F search')
        self.update_tutorial_status()

    def update_tutorial_status(self):
        key=self.tutorial_choice.get_active_id();saved=self.hub.prefs.data['tutorials'].get(key)
        if saved:
            self.tutorial_status.set_text('Completed · reviewed steps, not a model-quality certificate' if saved['completed'] else f"Saved at step {saved['step']+1} · {len(saved['skipped'])} skipped")
        else:self.tutorial_status.set_text('Not started · you can leave or skip at any time')
        self.resume_button.set_sensitive(bool(saved))

    def back(self):
        self.leave_tutorial(render=False);self.navigation.back();self.render()

    def current_step(self):return STEPS[TUTORIALS[self.tutorial][1][self.step]] if self.tutorial else None

    def start_tutorial(self,key,resume=False):
        if key not in TUTORIALS:return
        self.tutorial=key;self.tutorial_choice.set_active_id(key);saved=self.hub.prefs.data['tutorials'].get(key,{}) if resume else {}
        self.step=saved.get('step',0);self.skipped=set(saved.get('skipped',[]));self.render_step()

    def resume_tutorial(self):
        key=self.tutorial_choice.get_active_id()
        if key in self.hub.prefs.data['tutorials']:self.start_tutorial(key,resume=True)
        else:self.notice.set_text('No saved steps for this walkthrough. Choose Start / Restart.')

    def render_step(self):
        step=self.current_step();title,steps=TUTORIALS[self.tutorial]
        self.set_article(f'{title}\nStep {self.step+1} of {len(steps)} · {step.title}\n\n{step.text}\n\n'+ '\n\n'.join(ARTICLES[article_key(step.topic)].paragraphs))
        self.article.get_accessible().set_name(step.title)
        self.tour_actions.set_no_show_all(False);self.tour_actions.show_all()
        self.previous.set_sensitive(self.step>0);self.back_button.set_sensitive(True)
        self.next_button.set_label('Finish' if self.step==len(steps)-1 else 'Next')
        self.hub.highlight(step);self.update_gate()
        self.save_progress(False)

    def update_gate(self):
        if not self.tutorial:return
        allowed,message=self.hub.prerequisite(self.current_step().requires)
        self.next_button.set_sensitive(allowed)
        self.notice.set_text(message or 'Review this step, then choose Next. Show Control focuses the outlined field; settings remain yours.')

    def save_progress(self,completed):
        self.hub.prefs.data['tutorials'][self.tutorial]={'step':self.step,'completed':completed,'skipped':sorted(self.skipped)};self.hub.save();self.update_tutorial_status()

    def advance(self,direction):
        if not self.tutorial:
            i=ARTICLE_ORDER.index(self.navigation.current)+direction
            if 0<=i<len(ARTICLE_ORDER):self.open(ARTICLE_ORDER[i])
            return
        if direction>0 and not self.hub.prerequisite(self.current_step().requires)[0]:return
        count=len(TUTORIALS[self.tutorial][1]);next_step=self.step+direction
        if next_step>=count:
            completed=not self.skipped;self.save_progress(completed);self.leave_tutorial()
            self.notice.set_text('Walkthrough completed. This records reviewed steps, not a claim of model improvement.' if completed else 'Walkthrough ended with skipped steps. Restart to review them; completion is not certified.')
            if completed:self.hub.react('celebrate','tutorial','You finished the walkthrough. Review experiment evidence separately from tutorial progress.')
        elif next_step>=0:self.step=next_step;self.render_step()

    def skip_step(self):
        if not self.tutorial:return
        self.skipped.add(self.step)
        # Skipping is explicit and never bypasses a scientific verification claim.
        if self.step+1<len(TUTORIALS[self.tutorial][1]):self.step+=1;self.render_step()
        else:self.save_progress(False);self.leave_tutorial();self.notice.set_text('Walkthrough ended with skipped steps; it is not marked completed.')

    def leave_tutorial(self,render=True):
        self.tutorial=None;self.hub.clear_highlight()
        if render:self.render()

    def close_window(self,*args):
        self.hub.clear_highlight();return super().close_window(*args)


class CompanionWindow(HelpWindow):
    def __init__(self,hub):
        super().__init__(hub,'Stanley · GAFAW laboratory assistant','companion');self.set_size_request(350,380)
        outer=column();outer.set_border_width(16);self.add(outer)
        head=row();self.actor=StanleyActor(145,100);head.pack_start(self.actor,False,False,0)
        heading=column(4);heading.pack_start(text('STANLEY',True),False,False,0);heading.pack_start(text('Chief Executive Office Supply\nGAFAW Laboratories'),False,False,0);head.pack_start(heading,True,True,0)
        outer.pack_start(head,False,False,0)
        self.title=text('',True);outer.pack_start(self.title,False,False,0)
        self.location=text();outer.pack_start(self.location,False,False,0)
        self.explanation=text();self.explanation.set_max_width_chars(44)
        sc=Gtk.ScrolledWindow();sc.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC);sc.add(self.explanation);outer.pack_start(sc,True,True,0)
        self.quip=text();self.quip.set_max_width_chars(44);self.quip.get_style_context().add_class('stanley-quip');outer.pack_start(self.quip,False,False,0)
        line=row();line.pack_start(action('What’s This?',lambda:hub.ask()),False,False,0);line.pack_start(action('Explain More',self.explain_more),False,False,0);outer.pack_start(line,False,False,0)
        self.query=Gtk.SearchEntry();self.query.set_max_length(200);self.query.set_placeholder_text('Search topics, e.g. rank or dataset');self.query.get_accessible().set_name('Stanley offline help search')
        self.query.connect('activate',lambda *_:hub.open_guide(query=self.query.get_text()));contextual(self.query,'help.center');outer.pack_start(self.query,False,False,0)
        line=row();line.pack_start(action('Quick Start',lambda:hub.start_tutorial('quick-start')),False,False,0)
        line.pack_start(action('Search Help',lambda:hub.open_guide(query=self.query.get_text())),False,False,0)
        line.pack_start(action('Open Guide',lambda:hub.open_guide(self.topic)),False,False,0);outer.pack_start(line,False,False,0)
        outer.pack_start(self.ontop,False,False,0)
        outer.pack_start(text('Offline guide lookup · no AI model required'),False,False,0)
        self.topic='guide.start'

    def explain(self,key):
        self.topic=article_key(key);article=ARTICLES[self.topic]
        self.title.set_text(article.title);self.location.set_text(self.hub.context_caption())
        self.explanation.set_text(tooltip_text(key) if key in TOPICS or key in SHORT_HELP else article.paragraphs[0])
        self.quip.set_text(QUIPS.get(key,QUIPS.get(self.topic,QUIPS['default'])) if self.hub.prefs.data['sarcasm'] else '')
        self.actor.play('sideeye' if key=='lora.rank' and self.hub.prefs.data['sarcasm'] else 'confused' if key not in ARTICLES and key not in SHORT_HELP else 'speaking')

    def explain_more(self):
        self.explanation.set_text('\n\n'.join(ARTICLES[self.topic].paragraphs));self.actor.play('speaking')


class HelpController:
    def __init__(self,app,side,header,accelerators):
        self.app=app;app._gafaw_help_controller=self
        self.prefs=Preferences(app.skin_library.root.with_name(app.skin_library.root.name+'.help.local.json'))
        self.context=Context();self.guide=None;self.companion=None;self.highlighted=None;self.seen={};self.last_reaction=None;self.targets={}
        self.actor=StanleyActor(88,60)
        self.launcher=Gtk.Button();content=row(4);content.pack_start(self.actor,False,False,0);content.pack_start(text('Ask Stanley\nWhat’s This?'),True,True,0);self.launcher.add(content)
        self.launcher.get_accessible().set_name('Ask Stanley about this control or workspace')
        self.launcher._gafaw_context_utility=True;short_help(self.launcher,'help.stanley');self.launcher.connect('clicked',lambda *_:self.ask())
        side.pack_end(self.launcher,False,False,0)
        self.reaction_label=Gtk.Label(xalign=0);self.reaction_label.set_line_wrap(True);self.reaction_label.set_max_width_chars(28)
        self.reaction_label.get_style_context().add_class('subtitle');side.pack_end(self.reaction_label,False,False,0)
        guide=action('Help / User Guide',lambda:self.open_guide());short_help(guide,'help.center');guide._gafaw_context_utility=True;header.pack_start(guide)
        for shortcut,callback in (('F1',self.open_guide),('<Shift>F1',self.ask)):
            key,mods=Gtk.accelerator_parse(shortcut);accelerators.connect(key,mods,Gtk.AccelFlags.VISIBLE,lambda *_,cb=callback:cb() or True)
        app.connect('set-focus',self.focus_changed);app.tabs.connect('switch-page',self.tab_changed)
        app.connect('destroy',self.destroy)
        self.apply_preferences()

    def save(self):
        self.prefs.save()
        if self.guide and self.prefs.error:self.guide.notice.set_text(self.prefs.error)

    def preference(self,key,value):
        self.prefs.data[key]=value;self.apply_preferences();self.save()

    def apply_preferences(self):
        enabled=self.prefs.data['stanley']
        self.launcher.set_no_show_all(not enabled)
        if enabled:self.launcher.show_all()
        else:self.launcher.hide()
        self.reaction_label.set_no_show_all(not enabled);self.reaction_label.set_visible(enabled)
        self.actor.motion(self.prefs.data['reduced_motion'])
        for widget in walk(self.app):
            popover=getattr(widget,'_gafaw_help_popover',None)
            if popover and hasattr(popover,'_gafaw_stanley_link'):
                link=popover._gafaw_stanley_link;link.set_no_show_all(not enabled);link.set_visible(enabled)
        if self.companion:
            self.companion.actor.motion(self.prefs.data['reduced_motion'])
            if not enabled:self.companion.close_window()
            if not self.prefs.data['sarcasm']:self.companion.quip.set_text('')

    def sync_context(self):
        self.context.location(self.app.tabs.get_current_page(),self.app.selected)
        if self.context.page==0:
            self.context.kind=self.app.role_widgets['student'][0].get_active_id();self.context.stage='next run'

    def context_caption(self):
        names=('Configure','Laboratory','Evidence & artifacts','Dataset Workshop','Hardware & Models','Notebook & Compare','Skin Library')
        kinds={'linear':'CPU classifier','local_lora':'local SFT + LoRA','ollama':'Ollama inference','compatible':'compatible inference'}
        return ' · '.join(part for part in (names[self.context.page],kinds.get(self.context.kind),self.context.stage) if part)

    def tab_changed(self,_,page,index):
        self.context.location(index,self.app.selected)
        if index==0:self.context.kind=self.app.role_widgets['student'][0].get_active_id();self.context.stage='next run'
        self.refresh_companion()

    def focus_changed(self,_,widget):
        self.sync_context()
        if widget is None:return
        current=widget;key=None
        while current is not None and current is not self.app:
            if getattr(current,'_gafaw_context_utility',False):return
            if key is None:key=getattr(current,'_gafaw_help_key',None)
            current=current.get_parent()
        self.context.focus(key)
        self.refresh_companion()

    def refresh_companion(self):
        if self.companion and self.companion.get_visible():self.companion.explain(self.context.resolve())

    def ask(self,key=None):
        self.sync_context()
        if not self.prefs.data['stanley']:self.open_guide(key or self.context.resolve());return
        if self.companion is None:
            self.companion=CompanionWindow(self);self.companion.actor.motion(self.prefs.data['reduced_motion'])
        self.companion.explain(key or self.context.resolve());self.companion.show_all();self.companion.present();self.actor.play('greeting')

    def open_guide(self,key=None,query=None):
        self.sync_context()
        if self.guide is None:self.guide=GuideWindow(self)
        self.guide.open(key or self.context.resolve());self.guide.show_all()
        self.guide.tour_actions.set_visible(bool(self.guide.tutorial))
        if query is not None:self.guide.search.set_text(query);self.guide.results();self.guide.search.grab_focus()
        self.guide.present()

    def start_tutorial(self,key):
        self.open_guide('guide.start');self.guide.start_tutorial(key)

    def register_target(self,name,widget):
        """Register a stable application-owned tutorial target; help never executes imported definitions."""
        self.targets[name]=widget

    def target(self,name):
        if name in self.targets:return self.targets[name]
        if name=='student':return self.app.role_widgets['student'][0]
        if name=='epochs':return self.app.spins['epochs']
        if name=='workshop.use':
            return next((w for w in walk(self.app.tabs.get_nth_page(3)) if isinstance(w,Gtk.Button) and getattr(w,'_gafaw_help_key',None)=='workshop.use'),None)
        return getattr(self.app,name,None)

    def clear_highlight(self):
        if self.highlighted:self.highlighted.get_style_context().remove_class('gafaw-tour-target');self.highlighted=None

    def highlight(self,step,present=False):
        if not step:return
        self.clear_highlight();self.app.tabs.set_current_page(step.page)
        target=self.target(step.target)
        if not target:return
        if not target.get_mapped():
            if self.guide:self.guide.notice.set_text('This control is hidden in the current configuration. Select the relevant student yourself; the guide does not change settings.')
            return
        self.highlighted=target;target.get_style_context().add_class('gafaw-tour-target')
        # Bring the control into view using GTK coordinates, without pointer polling.
        ancestor=target.get_parent()
        while ancestor and not isinstance(ancestor,Gtk.ScrolledWindow):ancestor=ancestor.get_parent()
        if ancestor:
            content=ancestor.get_child();xy=target.translate_coordinates(content,0,0)
            if xy:
                adjustment=ancestor.get_vadjustment();adjustment.clamp_page(xy[1],xy[1]+target.get_allocated_height())
        if present:self.app.present();target.grab_focus()

    def prerequisite(self,kind):
        if not kind:return True,''
        if not self.app.selected:return False,'Select a real CPU-classifier experiment to continue, or Skip this step.'
        run=self.app.store.get(self.app.selected)
        if run['config']['student']['kind']!='linear':return False,'This step needs a CPU-classifier run; another workflow is selected. You can Skip.'
        if kind=='cpu-run':return True,''
        if run['status']!='completed':return False,'Wait for a completed CPU run, or Skip. A failed or stopped run is not verified completion.'
        report=run['state'].get('report',{})
        if not verified_report(report):
            return False,'The report does not verify updates and reload. Inspect the real evidence, or Skip.'
        return True,'Update and reload evidence is verified. Review held-out results separately; promotion is not assumed.'

    def observe(self,run):
        self.context.location(self.app.tabs.get_current_page(),run['id'])
        kind=run.get('config',{}).get('student',{}).get('kind')
        if self.context.page!=0:
            self.context.kind=kind if kind in ('linear','local_lora','ollama','compatible') else None
            stage=run.get('state',{}).get('phase')
            self.context.stage=stage if stage in ('inspect','baseline','plan','train','verify','done') else None
        self.context.status='evidence' if run['status']=='completed' else 'laboratory' if run['status'] in ('running','paused','failed','limited') else None
        previous=self.seen.get(run['id']);self.seen[run['id']]=run['status']
        if len(self.seen)>256:del self.seen[next(iter(self.seen))]
        # Opening historical runs is not a newly completed experiment.
        if previous and previous!=run['status']:
            event=reaction(run['status'],run['state'].get('report'))
            if event:self.react(*event)
        if self.guide:self.guide.update_gate()

    def compatibility(self,result,error=None):
        # A parsed preflight result is the only source; never infer diagnosis from arbitrary error text.
        if error:return
        import json
        try:data=json.loads(result)
        except (ValueError,TypeError):return
        if isinstance(data,dict) and data.get('ready') is False:
            self.react('concerned','incompatible','Compatibility preflight reported blockers. Read its actual report before starting training.')

    def react(self,state,key,message):
        if not self.prefs.data['stanley']:return
        self.last_reaction=(state,key,message)
        self.actor.play(state)
        self.reaction_label.set_text(message)
        if self.companion and self.companion.get_visible():
            self.companion.actor.play(state);self.companion.title.set_text('Recorded status')
            self.companion.explanation.set_text(message);self.companion.quip.set_text(QUIPS.get(key,'') if self.prefs.data['sarcasm'] else '')

    def remember_all(self):
        for window in (self.guide,self.companion):
            if window:window.remember()

    def destroy(self,*_):
        self.clear_highlight()
        for window in (self.guide,self.companion):
            if window:window.remember();window.destroy()
        self.actor.stop()
