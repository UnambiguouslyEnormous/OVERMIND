"""Native GTK desktop. All experiment work happens in a separate bounded process."""
import json
from pathlib import Path
import threading
import time
import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk, Gdk, GLib, GdkPixbuf

from . import DISPLAY_VERSION
from .data import load
from .hardware import inspect
from .lab import Manager, DEFAULTS, config_checked
from .model import TextStudent
from .providers import provider, inspection_summary
from .security import register, redact, clear_credentials, harden_process
from .ollama import discover
from .skins import SkinLibrary, PreparedSkin, export_package


def label(text,style=None,wrap=False):
    w=Gtk.Label(label=text,xalign=0)
    if style: w.get_style_context().add_class(style)
    if wrap: w.set_line_wrap(True);w.set_max_width_chars(95)
    return w

def box(spacing=12,horizontal=False):
    return Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL if horizontal else Gtk.Orientation.VERTICAL,spacing=spacing)

def button(text,callback,style=None):
    w=Gtk.Button(label=text);w.connect('clicked',lambda _:callback())
    if style: w.get_style_context().add_class(style)
    return w

def scroll(child):
    s=Gtk.ScrolledWindow();s.set_policy(Gtk.PolicyType.AUTOMATIC,Gtk.PolicyType.AUTOMATIC);s.add(child);return s

def entry(text=''):
    w=Gtk.Entry();w.set_text(text);return w

class Desktop(Gtk.Window):
    def __init__(self,root,skin_root=None):
        super().__init__(title='GAFAW — The Free, Open-Source AI Laboratory')
        self.set_default_size(1280,900);self.set_size_request(980,700)
        self.manager=Manager(root);self.store=self.manager.store
        self.selected=None;self.prepared_dataset=None;self.dataset_path=None;self.checkpoint_path=None;self.history_signature=None;self.last_events=None;self.last_hardware=0
        self.connect('delete-event',self.close)
        self.skin_library=SkinLibrary(skin_root or Path(__file__).resolve().parent.parent/'skin-library')
        self.skin_provider=None;self.prepared_skin=None;self.skin_id=None
        self.connect('destroy',lambda *_:self.release_skin())
        self.skin_startup_error=None
        try:self.activate_skin(self.skin_library.selected(),persist=False)
        except Exception as error:
            self.skin_startup_error=redact(str(error));self.activate_skin('black-titanium',persist=False)
        header=Gtk.HeaderBar();header.set_show_close_button(True);header.set_title('GAFAW')
        header.set_subtitle(f'The Free, Open-Source AI Laboratory  /  {DISPLAY_VERSION}')
        self.hardware_label=label('Detecting hardware…','subtitle');header.pack_end(self.hardware_label)
        terminal_button=button('Open Terminal Here',self.open_terminal)
        terminal_button.set_tooltip_text('Open the selected experiment directory · Ctrl+Shift+T')
        header.pack_start(terminal_button)
        accelerators=Gtk.AccelGroup();self.add_accel_group(accelerators)
        key,mods=Gtk.accelerator_parse('<Control><Shift>t')
        accelerators.connect(key,mods,Gtk.AccelFlags.VISIBLE,lambda *_:self.open_terminal() or True)
        self.set_titlebar(header)
        self.set_icon_from_file(str(Path(__file__).with_name('assets')/'gafaw-mark.svg'))
        layout=box(0,True);self.add(layout)
        side=box(18);side.set_size_request(248,-1);side.get_style_context().add_class('sidebar');layout.pack_start(side,False,False,0)
        side.pack_start(Gtk.Image.new_from_file(str(Path(__file__).with_name('assets')/'gafaw-mark.svg')),False,False,0)
        side.pack_start(label('GAFAW','brand'),False,False,0)
        side.pack_start(label('Teach. Test. Verify. Evolve.','subtitle'),False,False,0)
        side.pack_start(button('+  New experiment',self.new,'primary'),False,False,4)
        side.pack_start(label('EXPERIMENT MEMORY','eyebrow'),False,False,8)
        self.history=Gtk.ListBox();self.history.set_selection_mode(Gtk.SelectionMode.SINGLE);self.history.connect('row-selected',self.history_selected)
        side.pack_start(scroll(self.history),True,True,0)
        side.pack_start(label('LOCAL STUDENT\nCloud mentor requires consent\nNo automatic file uploads','subtitle'),False,False,0)
        side.pack_start(label(str(self.store.root),'subtitle',True),False,False,0)
        self.sidebar_status=label('','subtitle',True);self.sidebar_status.set_max_width_chars(30)
        side.pack_start(self.sidebar_status,False,False,0)
        self.tabs=Gtk.Notebook();self.tabs.set_scrollable(True);layout.pack_start(self.tabs,True,True,0)
        self.setup_tab();self.live_tab();self.evidence_tab();self.workshop_tab();self.system_tab();self.notebook_tab();self.skins_tab()
        self.status=label('Ready. The built-in experiment needs no downloads.','subtitle',True)
        self.setup_content.pack_end(self.status,False,False,0)
        if self.skin_startup_error:self.message('Using Black Titanium: '+self.skin_startup_error)
        self.tick();GLib.timeout_add(500,self.tick)

    def activate_skin(self,identifier,persist=True):
        skin=self.skin_library.get(identifier)
        prepared=PreparedSkin(skin)
        try:
            candidate=Gtk.CssProvider();candidate.load_from_data(prepared.css)
            if persist:self.skin_library.select(identifier)
        except Exception:
            prepared.close();raise
        previous_provider,previous_skin=self.skin_provider,self.prepared_skin
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(),candidate,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.skin_provider=candidate;self.prepared_skin=prepared;self.skin_id=identifier
        if previous_provider:Gtk.StyleContext.remove_provider_for_screen(Gdk.Screen.get_default(),previous_provider)
        if previous_skin:previous_skin.close()
        return skin

    def release_skin(self):
        if self.skin_provider:
            Gtk.StyleContext.remove_provider_for_screen(Gdk.Screen.get_default(),self.skin_provider);self.skin_provider=None
        if self.prepared_skin:self.prepared_skin.close();self.prepared_skin=None

    def skins_tab(self):
        c=self.page('07   Skin Library')
        c.pack_start(label('Dress the laboratory. Keep the science.','title'),False,False,0)
        c.pack_start(label('Switch skins live. Local .gafawskin packages contain validated JSON and static SVG/PNG assets. No code, raw CSS, external resources or downloads.','subtitle',True),False,False,0)
        self.skin_choice=Gtk.ComboBoxText();self.skin_choice.connect('changed',lambda *_:self.skin_details())
        c.pack_start(self.skin_choice,False,False,0)
        self.skin_info=label('','subtitle',True);self.skin_info.set_selectable(True);c.pack_start(self.skin_info,False,False,0)
        row=box(8,True)
        row.pack_start(button('Apply selected skin',self.apply_selected_skin,'primary'),False,False,0)
        row.pack_start(button('Restore Black Titanium',self.restore_skin),False,False,0)
        c.pack_start(row,False,False,0)
        row=box(8,True)
        row.pack_start(button('Import .gafawskin…',self.import_skin),False,False,0)
        row.pack_start(button('Export selected skin…',self.export_skin),False,False,0)
        row.pack_start(button('Refresh library',self.refresh_skins),False,False,0)
        c.pack_start(row,False,False,0)
        self.skin_status=label('','subtitle',True);self.skin_status.set_selectable(True);c.pack_start(self.skin_status,False,False,0)
        c.pack_start(label('Community authors can export a skin as a starting point, edit manifest.json, give it a new id and repackage it. Font files and arbitrary widget/layout overrides are intentionally unsupported. Contrast remains the author’s responsibility; the engine preserves focus rings and native controls.','subtitle',True),False,False,0)
        self.refresh_skins()

    def refresh_skins(self,selected=None):
        try:
            skins,errors=self.skin_library.list()
            current=selected or self.skin_choice.get_active_id() or self.skin_id
            self.skin_choice.remove_all()
            for skin in skins:self.skin_choice.append(skin.id,skin.manifest['name']+(' · built-in' if skin.builtin else ' · installed'))
            self.skin_choice.set_active_id(current)
            self.skin_status.set_text('Active: '+self.skin_id+' · Library: '+str(self.skin_library.root)+('\nRejected packages: '+'; '.join(errors) if errors else ''))
        except Exception as error:self.skin_status.set_text(redact(str(error)))

    def skin_details(self):
        identifier=self.skin_choice.get_active_id()
        if not identifier:return
        try:
            skin=self.skin_library.get(identifier);m=skin.manifest
            self.skin_info.set_text(f"{m['name']} · v{m['version']} · {m['author']} · {m['license']}\n{m.get('description','')}\n{len(skin.assets)} static assets · "+('Built-in' if skin.builtin else 'Installed locally'))
        except Exception as error:self.skin_info.set_text(redact(str(error)))

    def apply_selected_skin(self):
        try:
            identifier=self.skin_choice.get_active_id()
            if not identifier:raise ValueError('Select a skin first.')
            self.activate_skin(identifier)
            self.skin_status.set_text('Active: '+identifier+' · saved for next launch. No experiment or data changed.')
        except Exception as error:self.skin_status.set_text('Previous skin retained: '+redact(str(error)))

    def restore_skin(self):
        self.skin_choice.set_active_id('black-titanium');self.apply_selected_skin()

    def import_skin(self):
        dialog=Gtk.FileChooserDialog(title='Import validated .gafawskin package',parent=self,action=Gtk.FileChooserAction.OPEN)
        dialog.add_buttons('Cancel',Gtk.ResponseType.CANCEL,'Import',Gtk.ResponseType.OK)
        filter=Gtk.FileFilter();filter.set_name('GAFAW skins');filter.add_pattern('*.gafawskin');dialog.add_filter(filter)
        if dialog.run()==Gtk.ResponseType.OK:
            try:
                skin=self.skin_library.install(dialog.get_filename());self.refresh_skins(skin.id)
                self.skin_status.set_text('Installed '+skin.manifest['name']+'. Choose Apply selected skin to activate it.')
            except Exception as error:self.skin_status.set_text('Import rejected: '+redact(str(error)))
        dialog.destroy()

    def export_skin(self):
        try:skin=self.skin_library.get(self.skin_choice.get_active_id())
        except Exception as error:self.skin_status.set_text(redact(str(error)));return
        dialog=Gtk.FileChooserDialog(title='Export skin package (new filename)',parent=self,action=Gtk.FileChooserAction.SAVE)
        dialog.add_buttons('Cancel',Gtk.ResponseType.CANCEL,'Export',Gtk.ResponseType.OK)
        dialog.set_current_name(skin.id+'.gafawskin')
        if dialog.run()==Gtk.ResponseType.OK:
            try:
                export_package(skin,dialog.get_filename());self.skin_status.set_text('Skin exported. Custom forks need a new manifest id before import.')
            except Exception as error:self.skin_status.set_text(redact(str(error)))
        dialog.destroy()

    def page(self,title):
        content=box(18);content.set_border_width(26)
        self.tabs.append_page(scroll(content),label(title))
        return content

    def card(self,title,subtitle=None):
        w=box(12);w.get_style_context().add_class('card')
        w.pack_start(label(title,'eyebrow'),False,False,0)
        if subtitle:w.pack_start(label(subtitle,'subtitle',True),False,False,0)
        return w

    def setup_tab(self):
        c=self.setup_content=self.page('01   Configure')
        c.pack_start(label('A laboratory for learning.','title'),False,False,0)
        c.pack_start(label('Connect a teacher, choose a student, and measure what actually changes.','subtitle',True),False,False,0)
        roles=box(16,True);c.pack_start(roles,False,False,0)
        self.role_widgets={}
        for role in ('mentor','student'):
            card=self.card(role.upper(),'Directs experiments' if role=='mentor' else 'The model being improved')
            roles.pack_start(card,True,True,0)
            combo=Gtk.ComboBoxText()
            combo.append('controller' if role=='mentor' else 'linear','Curriculum controller · deterministic' if role=='mentor' else 'CPU text classifier · real weight training')
            if role=='mentor':
                combo.append('openai','OpenAI · cloud mentor');combo.append('anthropic','Anthropic · cloud mentor')
            combo.append('ollama','Ollama · local LLM');combo.append('compatible','Compatible API · local LLM');combo.set_active(0)
            card.pack_start(combo,False,False,0)
            url=entry('http://127.0.0.1:11434');model=Gtk.ComboBoxText.new_with_entry();model.get_child().set_placeholder_text('Discover models or enter an exact ID')
            card.pack_start(url,False,False,0);card.pack_start(model,False,False,0)
            if role=='mentor':
                self.api_key=entry();self.api_key.set_visibility(False);self.api_key.set_placeholder_text('Session API key; blank uses provider environment variable')
                self.api_key.set_input_purpose(Gtk.InputPurpose.PASSWORD)
                self.api_key.set_no_show_all(True);card.pack_start(self.api_key,False,False,0)
                card.pack_start(button('Clear session keys',self.clear_session_keys),False,False,0)
            card.pack_start(button('Discover models',lambda r=role:self.discover_models(r)),False,False,0)
            if role=='student':card.pack_start(button('Test local inference',self.test_student),False,False,0)
            check=button('Inspect connection',lambda r=role:self.check_connection(r));card.pack_start(check,False,False,0)
            info=label('Built-in; no external server required.','subtitle',True);card.pack_start(info,False,False,0)
            self.role_widgets[role]=(combo,url,model,info,check)
            def changed(w,r=role):
                combo,url,model,info,check=self.role_widgets[r]
                if r=='mentor':self.invalidate_cloud_authorization()
                external=combo.get_active_id() not in ('controller','linear')
                cloud=combo.get_active_id() in ('openai','anthropic')
                url.set_sensitive(external and not cloud);model.set_sensitive(external);check.set_sensitive(external)
                if r=='mentor':
                    self.api_key.set_visible(cloud);self.api_key.set_text('')
                if cloud:
                    info.set_text('Official HTTPS endpoint. Discover/inspect checks metadata only; paid generation requires the authorization below.');return
                info.set_text('Loopback only. Server and model must already be installed.' if external else
                    'Bounded algorithm; this is not an LLM mentor.' if r=='mentor' else '8,192 trainable weights · text classification only.')
            if role=='mentor':model.get_child().connect('changed',lambda _:self.invalidate_cloud_authorization())
            combo.connect('changed',changed);changed(combo)
        checkpoint_row=box(8,True)
        checkpoint_row.pack_start(button('Use saved student weights…',self.choose_checkpoint),False,False,0)
        checkpoint_row.pack_start(button('Use a fresh student',self.reset_checkpoint),False,False,0)
        self.checkpoint_label=label('Fresh CPU classifier · no pretrained knowledge','subtitle',True)
        checkpoint_row.pack_start(self.checkpoint_label,True,True,0);c.pack_start(checkpoint_row,False,False,0)
        goal=self.card('LEARNING OBJECTIVE','For this slice, capabilities are measured as exact-label text classification. For other domains, supply your own licensed labeled dataset.')
        self.objective=entry(DEFAULTS['objective']);goal.pack_start(self.objective,False,False,0)
        self.dataset_label=label('Support routing v1 · CC0 · 80 training / 24 validation / 40 held-out examples','subtitle',True)
        goal.pack_start(self.dataset_label,False,False,0)
        row=box(8,True);row.pack_start(button('Choose dataset JSON…',self.choose_dataset),False,False,0)
        row.pack_start(button('Use built-in benchmark',self.reset_dataset),False,False,0);goal.pack_start(row,False,False,0)
        c.pack_start(goal,False,False,0)
        limits=self.card('RESOURCE ENVELOPE','The laboratory worker is memory- and time-bounded. Limits do not control memory used by a separately running inference server.')
        grid=Gtk.Grid(column_spacing=18,row_spacing=8);limits.pack_start(grid,False,False,0);self.spins={}
        for col,(key,title,low,high) in enumerate([('epochs','Training epochs',1,60),('minutes','Wall minutes',1,120),('max_calls','LLM call limit',1,2000),('memory_mb','Worker RAM · MB',128,16384)]):
            spin=Gtk.SpinButton.new_with_range(low,high,1);spin.set_value(DEFAULTS[key]);spin.set_hexpand(True)
            grid.attach(label(title,'subtitle'),col,0,1,1);grid.attach(spin,col,1,1,1);self.spins[key]=spin
        limits.pack_start(label('LLM mode: bounded mentor candidates choose prompt or retrieval improvements. Student inference remains local.','subtitle',True),False,False,0)
        c.pack_start(limits,False,False,0)
        attempts_row=box(10,True);attempts_row.pack_start(label('Maximum mentor candidates','subtitle'),False,False,0)
        self.attempts=Gtk.SpinButton.new_with_range(1,8,1);self.attempts.set_value(3);attempts_row.pack_start(self.attempts,False,False,0);limits.pack_start(attempts_row,False,False,0)
        cloud_card=self.card('CLOUD MENTOR SPENDING','Enter upper-bound rates from your provider’s current pricing for the exact model. Zero defaults block paid usage. Uncertain requests retain their full reservation.')
        cloud_grid=Gtk.Grid(column_spacing=12,row_spacing=8);self.cloud_fields={}
        for col,(key,title,default) in enumerate([('budget_usd','Run budget · USD','0'),('input_usd_per_million','Input · USD / 1M','0'),('output_usd_per_million','Output · USD / 1M','0'),('max_output_tokens','Output token cap','2048')]):
            w=entry(default);w.set_width_chars(10);w.set_hexpand(True);self.cloud_fields[key]=w
            cloud_grid.attach(label(title,'subtitle'),col,0,1,1);cloud_grid.attach(w,col,1,1,1)
        cloud_card.pack_start(cloud_grid,False,False,0)
        self.cloud_authorized=Gtk.CheckButton(label='Authorize paid mentor calls for this run within the configured budget.')
        self.cloud_sharing=Gtk.CheckButton(label='Allow this objective, hardware/model details, and training/validation data to be sent to the cloud mentor.')
        cloud_card.pack_start(self.cloud_authorized,False,False,0);cloud_card.pack_start(self.cloud_sharing,False,False,0);c.pack_start(cloud_card,False,False,0)
        self.consent=Gtk.CheckButton(label='Allow the selected dataset’s training and validation text to be sent to my local model server.')
        self.consent.set_active(False);c.pack_start(self.consent,False,False,0)
        row=box(12,True);self.run_button=button('RUN EXPERIMENT  →',self.run_new,'primary');row.pack_start(self.run_button,False,False,0)
        row.pack_start(label('Original models stay intact. Every candidate gets an evidence report.','subtitle',True),True,True,0);c.pack_start(row,False,False,0)

    def live_tab(self):
        c=self.live_content=self.page('02   Laboratory')
        self.run_title=label('No experiment selected','title');c.pack_start(self.run_title,False,False,0)
        self.run_detail=label('Start an experiment to follow its decisions and measurements.','subtitle',True);c.pack_start(self.run_detail,False,False,0)
        row=box(14,True);self.metrics={}
        for key,title in [('status','STATE'),('baseline','BASELINE'),('candidate','CANDIDATE')]:
            card=self.card(title);value=label('—','metric');card.pack_start(value,False,False,0);row.pack_start(card,True,True,0);self.metrics[key]=value
        c.pack_start(row,False,False,0)
        self.progress=Gtk.ProgressBar();self.progress.set_show_text(True);c.pack_start(self.progress,False,False,0)
        controls=box(10,True)
        self.pause_button=button('Pause',self.pause);controls.pack_start(self.pause_button,False,False,0)
        self.resume_button=button('Resume / Recover',self.resume);controls.pack_start(self.resume_button,False,False,0)
        self.stop_button=button('Emergency stop',self.stop,'danger');controls.pack_start(self.stop_button,False,False,0)
        c.pack_start(controls,False,False,0)
        self.loss_image=Gtk.Image();self.loss_image.set_halign(Gtk.Align.START);c.pack_start(self.loss_image,False,False,0)
        c.pack_start(label('DECISIONS & MEASUREMENTS','eyebrow'),False,False,0)
        self.journal=Gtk.TextView();self.journal.set_editable(False);self.journal.set_cursor_visible(False);self.journal.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        sc=scroll(self.journal);sc.set_size_request(-1,300);c.pack_start(sc,True,True,0)

    def evidence_tab(self):
        c=self.page('03   Evidence & artifacts')
        c.pack_start(label('Proof before promotion.','title'),False,False,0)
        self.verification=label('No completed comparison yet. Improvement is never assumed.','subtitle',True);c.pack_start(self.verification,False,False,0)
        self.artifact_label=label('Candidates, dataset snapshots, raw predictions and reports are saved locally.','subtitle',True);c.pack_start(self.artifact_label,False,False,0)
        c.pack_start(button('Export private evidence bundle…',self.export_evidence_bundle),False,False,0)
        self.artifact_choice=Gtk.ComboBoxText()
        for name in ('report.json','training-integrity.json','training-metrics.json','candidate-validation.json','candidate.json','baseline-validation.json','latest-validation.json','baseline-test.json','candidate-test.json','promoted.json','billing.json'):
            self.artifact_choice.append_text(name)
        self.artifact_choice.set_active(0);self.artifact_choice.connect('changed',lambda _:self.show_artifact())
        c.pack_start(self.artifact_choice,False,False,0)
        self.artifact_text=Gtk.TextView();self.artifact_text.set_editable(False);self.artifact_text.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        sc=scroll(self.artifact_text);sc.set_size_request(-1,260);c.pack_start(sc,True,True,0)
        trial=self.card('TRY THE FROZEN STUDENT','Loads the selected artifact. This input is not added to training data or the benchmark.')
        self.try_input=entry('I need a refund for a duplicate charge');trial.pack_start(self.try_input,False,False,0)
        trial.pack_start(button('Classify with candidate',self.try_candidate),False,False,0)
        self.try_result=label('—','subtitle',True);trial.pack_start(self.try_result,False,False,0);c.pack_start(trial,False,False,0)

    def workshop_tab(self):
        c=self.page('04   Dataset Workshop')
        c.pack_start(label('Good science starts with clean data.','title'),False,False,0)
        c.pack_start(label('Import labeled JSONL, CSV, TSV or tab-separated TXT (input,target columns; optional split). JSON retains authored splits. Review the editable JSONL before use.','subtitle',True),False,False,0)
        row=box(8,True)
        self.workshop_license=entry('');self.workshop_license.set_placeholder_text('License / permission statement (required for new imports)')
        row.pack_start(self.workshop_license,True,True,0)
        self.split_seed=Gtk.SpinButton.new_with_range(0,4294967295,1);self.split_seed.set_value(42)
        row.pack_start(label('Split seed','subtitle'),False,False,0);row.pack_start(self.split_seed,False,False,0)
        c.pack_start(row,False,False,0)
        actions=box(8,True)
        actions.pack_start(button('Import labeled file…',self.import_dataset),False,False,0)
        actions.pack_start(button('Load benchmark into editor',self.edit_benchmark),False,False,0)
        c.pack_start(actions,False,False,0)
        self.dataset_editor=Gtk.TextView();self.dataset_editor.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.dataset_editor.set_monospace(True)
        sc=scroll(self.dataset_editor);sc.set_size_request(-1,280);c.pack_start(sc,True,True,0)
        actions=box(8,True)
        actions.pack_start(button('Validate & use reviewed data',self.use_workshop,'primary'),False,False,0)
        actions.pack_start(button('Export new dataset version…',self.export_dataset),False,False,0)
        c.pack_start(actions,False,False,0)
        self.workshop_result=label('No file imported. Unassigned rows are deduplicated, then stratified 70/15/15. Every split must contain ≥8 rows and every label. Exact overlap is blocked; review paraphrases manually.','subtitle',True)
        self.workshop_result.set_selectable(True);c.pack_start(self.workshop_result,False,False,0)
        self.workshop_data=None

    def edit_benchmark(self):
        self.populate_workshop(load())

    def populate_workshop(self,data):
        from .workshop import editable_jsonl,summary
        self.workshop_data=data
        self.workshop_license.set_text(data['license'])
        self.dataset_editor.get_buffer().set_text(editable_jsonl(data))
        self.workshop_result.set_text(json.dumps(summary(data),indent=2,ensure_ascii=False))

    def import_dataset(self):
        from .workshop import import_file
        dialog=Gtk.FileChooserDialog(title='Import labeled dataset',parent=self,action=Gtk.FileChooserAction.OPEN)
        dialog.add_buttons('Cancel',Gtk.ResponseType.CANCEL,'Import',Gtk.ResponseType.OK)
        if dialog.run()==Gtk.ResponseType.OK:
            path=dialog.get_filename();license=self.workshop_license.get_text().strip();seed=self.split_seed.get_value_as_int()
            self.workshop_result.set_text('Validating source, duplicates and split isolation…')
            def done(data,error):
                if error:self.workshop_result.set_text(error)
                else:self.populate_workshop(data)
            self.background(lambda:import_file(path,license,seed),done)
        dialog.destroy()

    def reviewed_dataset(self):
        from .workshop import rows_from_text,prepare
        buffer=self.dataset_editor.get_buffer()
        text=buffer.get_text(buffer.get_start_iter(),buffer.get_end_iter(),True)
        previous=self.workshop_data
        data=prepare(rows_from_text(text,'jsonl'),self.workshop_license.get_text().strip(),
                     previous.get('name','Reviewed dataset') if previous else 'Reviewed dataset',self.split_seed.get_value_as_int())
        if previous:
            from .data import digest
            data['provenance']['parent_sha256']=digest(previous)
        return data

    def use_workshop(self):
        try:
            from .workshop import summary
            data=self.reviewed_dataset();self.prepared_dataset=data;self.dataset_path=None
            self.dataset_label.set_text(f"Reviewed {data['name']} · "+' / '.join(f'{len(data[k])} {k}' for k in ('train','validation','test')))
            self.workshop_result.set_text('ACTIVE FOR NEXT EXPERIMENT · '+json.dumps(summary(data),indent=2))
            self.message('Reviewed dataset selected. Configure the next experiment or export this version.')
        except Exception as e:self.workshop_result.set_text(redact(str(e)))

    def export_dataset(self):
        from .workshop import export_version
        try:data=self.reviewed_dataset()
        except Exception as e:self.workshop_result.set_text(redact(str(e)));return
        dialog=Gtk.FileChooserDialog(title='Export immutable dataset version (new filename)',parent=self,action=Gtk.FileChooserAction.SAVE)
        dialog.add_buttons('Cancel',Gtk.ResponseType.CANCEL,'Export',Gtk.ResponseType.OK)
        dialog.set_current_name('dataset-v1.json')
        if dialog.run()==Gtk.ResponseType.OK:
            try:self.workshop_result.set_text('Private dataset version saved: '+export_version(data,dialog.get_filename()))
            except Exception as e:self.workshop_result.set_text(redact(str(e)))
        dialog.destroy()

    def system_tab(self):
        c=self.page('05   Hardware & Models')
        c.pack_start(label('Hardware reality checker.','title'),False,False,0)
        c.pack_start(label('Live diagnostics; inference access and trainable checkpoints are separate capabilities. No model downloads or code execution.','subtitle',True),False,False,0)
        c.pack_start(button('Refresh hardware diagnostics',self.refresh_hardware),False,False,0)
        self.hardware_details=Gtk.TextView();self.hardware_details.set_editable(False);self.hardware_details.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        sc=scroll(self.hardware_details);sc.set_size_request(-1,260);c.pack_start(sc,True,True,0)
        c.pack_start(button('Inspect local HF checkpoint directory…',self.inspect_local_model),False,False,0)
        self.local_model_info=label('Select an existing HF-compatible directory to inspect architecture, tokenizer presence, safe weight files, storage, adapter metadata and license evidence. Use Configure for Ollama/API model discovery.','subtitle',True)
        self.local_model_info.set_selectable(True);c.pack_start(self.local_model_info,False,False,0)

    def refresh_hardware(self):
        def done(h,error):
            if error:self.hardware_details.get_buffer().set_text(error);return
            self.hardware_details.get_buffer().set_text(json.dumps(h,indent=2))
            if h.get('ram_mb'):self.hardware_label.set_text(f'{h["ram_mb"]/1024:.1f} GiB RAM · '+('NVIDIA driver detected' if h['gpu'] else 'CPU laboratory'))
        self.background(lambda:inspect(self.store.root),done)

    def inspect_local_model(self):
        from .inventory import inspect_local
        dialog=Gtk.FileChooserDialog(title='Inspect local model metadata',parent=self,action=Gtk.FileChooserAction.SELECT_FOLDER)
        dialog.add_buttons('Cancel',Gtk.ResponseType.CANCEL,'Inspect',Gtk.ResponseType.OK)
        if dialog.run()==Gtk.ResponseType.OK:
            path=dialog.get_filename()
            self.background(lambda:inspect_local(path),lambda result,error:self.local_model_info.set_text(error or json.dumps(result,indent=2)))
        dialog.destroy()

    def notebook_tab(self):
        c=self.page('06   Notebook & Compare')
        c.pack_start(label('Keep the evidence. Question the result.','title'),False,False,0)
        c.pack_start(label('Markdown notes belong to the selected experiment. Comparisons read saved predictions; they make no new model calls. Repeated holdout use is exploratory.','subtitle',True),False,False,0)
        self.note_editor=Gtk.TextView();self.note_editor.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        sc=scroll(self.note_editor);sc.set_size_request(-1,140);c.pack_start(sc,False,False,0)
        c.pack_start(button('Save experiment notes',self.save_notes),False,False,0)
        row=box(8,True);self.compare_left=Gtk.ComboBoxText();self.compare_right=Gtk.ComboBoxText()
        row.pack_start(self.compare_left,True,True,0);row.pack_start(self.compare_right,True,True,0)
        row.pack_start(button('Compare recorded results',self.compare_runs),False,False,0);c.pack_start(row,False,False,0)
        c.pack_start(button('Inspect selected experiment failures',self.inspect_failures),False,False,0)
        self.science_result=Gtk.TextView();self.science_result.set_editable(False);self.science_result.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        sc=scroll(self.science_result);sc.set_size_request(-1,240);c.pack_start(sc,True,True,0)
        self.science_result.get_buffer().set_text('Select a completed experiment to inspect failures, or choose two completed runs to compare recorded accuracy and Wilson intervals. No measurements are available before a run completes.')
        self.note_run=None;self.note_drafts={}

    def load_notes(self):
        if self.note_run==self.selected:return
        if self.note_run:
            buffer=self.note_editor.get_buffer()
            self.note_drafts[self.note_run]=buffer.get_text(buffer.get_start_iter(),buffer.get_end_iter(),True)
        self.note_run=self.selected
        try:note=self.store.read(self.selected,'notebook.json')['markdown']
        except FileNotFoundError:note=''
        self.note_editor.get_buffer().set_text(self.note_drafts.get(self.selected,note))

    def save_notes(self):
        try:
            if not self.selected:raise ValueError('Select an experiment first.')
            buffer=self.note_editor.get_buffer();text=buffer.get_text(buffer.get_start_iter(),buffer.get_end_iter(),True)
            if len(text)>100000:raise ValueError('Notes are limited to 100,000 characters.')
            self.store.artifact(self.selected,'notebook.json',{'markdown':text,'updated':time.time()})
            self.science_result.get_buffer().set_text('Notes saved privately for '+self.selected)
        except Exception as e:self.science_result.get_buffer().set_text(redact(str(e)))

    def compare_runs(self):
        from .science import compare
        try:
            left,right=self.compare_left.get_active_id(),self.compare_right.get_active_id()
            if not left or not right:raise ValueError('Choose two completed experiments.')
            if left==right:raise ValueError('Choose distinct experiments.')
            result=compare(self.store,left,right)
            self.science_result.get_buffer().set_text(json.dumps(result,indent=2))
        except Exception as e:self.science_result.get_buffer().set_text(redact(str(e)))

    def inspect_failures(self):
        from .science import failures
        try:
            if not self.selected:raise ValueError('Select a completed experiment first.')
            result=failures(self.store.read(self.selected,'baseline-test.json'),self.store.read(self.selected,'candidate-test.json'))
            self.science_result.get_buffer().set_text(json.dumps(result,indent=2,ensure_ascii=False))
        except Exception as e:self.science_result.get_buffer().set_text(redact(str(e)))

    def open_terminal(self):
        from .terminal import open_terminal
        try:
            directory=self.store.root/self.selected if self.selected else self.store.root
            self.message('Terminal opened in '+open_terminal(directory))
        except (OSError,ValueError,RuntimeError) as e:self.message(redact(str(e)))

    def clear_session_keys(self):
        self.manager.stop()
        clear_credentials()
        self.api_key.set_text('')
        self.invalidate_cloud_authorization()
        self.role_widgets['mentor'][3].set_text('Session keys cleared and the active worker stopped. Enter a key again or restart to use environment credentials. An already accepted provider request may finish.')

    def invalidate_cloud_authorization(self):
        if hasattr(self,'cloud_authorized'):
            self.cloud_authorized.set_active(False);self.cloud_sharing.set_active(False)
            for field in ('input_usd_per_million','output_usd_per_million'):self.cloud_fields[field].set_text('0')

    def role_config(self,role):
        combo,url,model,_,_=self.role_widgets[role]
        kind=combo.get_active_id()
        if kind in ('openai','anthropic'):
            if self.api_key.get_text():register(kind,self.api_key.get_text())
            return {'kind':kind,'model':model.get_child().get_text().strip()}
        return ({'kind':kind,**({'checkpoint':self.checkpoint_path} if kind=='linear' and self.checkpoint_path else {})}) if kind in ('linear','controller') else {'kind':kind,'url':url.get_text().strip(),'model':model.get_child().get_text().strip()}

    def message(self,text):
        self.status.set_text(text)
        self.sidebar_status.set_text(text)

    def background(self,work,done):
        def task():
            try: result=work();error=None
            except Exception as e:result=None;error=redact(redact(str(e)))
            GLib.idle_add(done,redact(result),error)
        threading.Thread(target=task,daemon=True).start()

    def check_connection(self,role):
        try:
            config=self.role_config(role);p=provider(config)
        except Exception as e:self.role_widgets[role][3].set_text(redact(str(e)));return
        self.role_widgets[role][3].set_text('Inspecting real server metadata…')
        def done(result,error):
            self.role_widgets[role][3].set_text(error or (inspection_summary(config,result) if config['kind'] in ('ollama','compatible') else f"{config['kind']} · {config['model']} · connected (metadata only; inference not tested)"))
        self.background(p.inspect,done)

    def discover_models(self,role):
        combo,url,model,info,_=self.role_widgets[role];kind=combo.get_active_id()
        if kind in ('linear','controller'):info.set_text('Built-in role; no discovery required.');return
        if kind in ('openai','anthropic'):
            if self.api_key.get_text():register(kind,self.api_key.get_text())
            from .cloud import CloudProvider
            work=CloudProvider(kind,'discovery').models
        elif kind=='ollama':work=lambda:discover(url.get_text().strip())
        else:
            try:work=provider({'kind':kind,'url':url.get_text().strip(),'model':'discovery'}).models
            except Exception as e:info.set_text(redact(str(e)));return
        info.set_text('Discovering models…')
        def done(result,error):
            if error:info.set_text(error);return
            if combo.get_active_id()!=kind:return
            current=model.get_child().get_text();model.remove_all()
            ids=[x['name'] for x in result.get('models',[]) if 'name' in x] if isinstance(result,dict) else result
            for name in ids:model.append_text(name)
            if current:model.get_child().set_text(current)
            elif ids:model.set_active(0)
            info.set_text(result['guidance'] if isinstance(result,dict) else f'{len(ids)} models accessible. Select a text-generation model; metadata discovery does not test generation.')
        self.background(work,done)

    def test_student(self):
        try:
            cfg=self.role_config('student')
            if cfg['kind'] not in ('ollama','compatible'):raise ValueError('Select a local LLM first.')
            p=provider(cfg)
        except Exception as e:self.role_widgets['student'][3].set_text(redact(str(e)));return
        self.role_widgets['student'][3].set_text('Testing local generation…')
        self.background(lambda:p.generate('Reply briefly.','Say ready.',16),lambda r,e:self.role_widgets['student'][3].set_text(e or 'Local inference succeeded: '+r[:160]))

    def choose_dataset(self):
        dialog=Gtk.FileChooserDialog(title='Select licensed dataset JSON',parent=self,action=Gtk.FileChooserAction.OPEN)
        dialog.add_buttons('Cancel',Gtk.ResponseType.CANCEL,'Select',Gtk.ResponseType.OK)
        if dialog.run()==Gtk.ResponseType.OK:
            path=dialog.get_filename()
            try:
                data=load(path);self.dataset_path=path;self.prepared_dataset=None
                self.dataset_label.set_text(f'{Path(path).name} · {data["license"]} · '+ ' / '.join(f'{len(data[k])} {k}' for k in ('train','validation','test')))
            except Exception as e:self.message(redact(str(e)))
        dialog.destroy()

    def choose_checkpoint(self):
        dialog=Gtk.FileChooserDialog(title='Select GAFAW / legacy OVERMIND classifier weights JSON',parent=self,action=Gtk.FileChooserAction.OPEN)
        dialog.add_buttons('Cancel',Gtk.ResponseType.CANCEL,'Select',Gtk.ResponseType.OK)
        if dialog.run()==Gtk.ResponseType.OK:
            path=dialog.get_filename()
            try:
                if Path(path).stat().st_size>4_000_000:raise ValueError('Checkpoint exceeds 4 MB.')
                TextStudent.restore(json.loads(Path(path).read_text()))
                self.checkpoint_path=path;self.checkpoint_label.set_text('Base checkpoint: '+Path(path).name)
            except Exception as e:self.message(redact(str(e)))
        dialog.destroy()

    def reset_checkpoint(self):
        self.checkpoint_path=None;self.checkpoint_label.set_text('Fresh CPU classifier · no pretrained knowledge')

    def reset_dataset(self):
        self.prepared_dataset=None;self.dataset_path=None;self.dataset_label.set_text('Support routing v1 · CC0 · 80 training / 24 validation / 40 held-out examples')

    def run_new(self):
        try:
            if self.manager.process and self.manager.process.poll() is None: raise ValueError('An experiment is active. Pause or stop it before creating another.')
            c={**DEFAULTS,'objective':self.objective.get_text().strip(),'mentor':self.role_config('mentor'),'student':self.role_config('student'),
                'attempts':self.attempts.get_value_as_int(),
                **{key:spin.get_value_as_int() for key,spin in self.spins.items()}}
            if c['mentor']['kind'] in ('openai','anthropic'):
                c['cloud']={key:w.get_text().strip() for key,w in self.cloud_fields.items()}
                c['cloud']['max_output_tokens']=int(c['cloud']['max_output_tokens'])
                c['cloud'].update(authorized=self.cloud_authorized.get_active(),data_sharing=self.cloud_sharing.get_active())
            if (c['mentor']['kind']!='controller' or c['student']['kind']!='linear') and not self.consent.get_active():
                raise ValueError('Enable the local dataset-sharing permission before connecting an external model server.')
            c=config_checked(c);dataset=self.prepared_dataset or load(self.dataset_path)
            rid=self.store.create(c,dataset);self.selected=rid;self.load_notes();self.manager.start(rid)
            self.tabs.set_current_page(1);self.message('Experiment started.');self.tick()
        except Exception as e:self.message(redact(str(e)))

    def new(self):self.tabs.set_current_page(0)
    def history_selected(self,_,row):
        if row:self.selected=row.rid;self.last_events=None;self.refresh_run();self.show_artifact();self.load_notes()
    def pause(self):self.manager.pause();self.tick()
    def resume(self):
        try:
            if self.selected:
                if self.manager.rid==self.selected and self.manager.process and self.manager.process.poll() is None:self.manager.resume()
                else:self.manager.start(self.selected)
            self.tick()
        except Exception as e:self.run_detail.set_text(redact(str(e)))
    def stop(self):self.manager.stop();self.tick()

    def tick(self):
        self.manager.poll()
        runs=self.store.list();signature=[(r['id'],r['status']) for r in runs]
        if signature!=self.history_signature:
            self.history_signature=signature
            for child in self.history.get_children():self.history.remove(child)
            for r in runs:
                row=Gtk.ListBoxRow();row.rid=r['id'];b=box(4);b.set_border_width(10)
                b.pack_start(label(r['id']),False,False,0);b.pack_start(label(r['status'].upper(),'subtitle'),False,False,0);row.add(b);self.history.add(row)
            self.history.show_all()
            for choice in (self.compare_left,self.compare_right):
                current=choice.get_active_id();choice.remove_all()
                for r in runs:
                    if r['status']=='completed':choice.append(r['id'],r['id'])
                if current:choice.set_active_id(current)
        self.refresh_run()
        if time.monotonic()-self.last_hardware>30:
            self.last_hardware=time.monotonic()
            self.refresh_hardware()
        return True

    def refresh_run(self):
        if not self.selected:return
        run=self.store.get(self.selected);s=run['state'];cfg=run['config'];report=s.get('report')
        self.run_title.set_text('Experiment '+self.selected)
        method='Weight training · CPU softmax classifier' if cfg['student']['kind']=='linear' else 'Prompt / retrieval optimization · base weights unchanged'
        bill=self.store.billing(self.selected)
        spending=(f' · cloud ${bill["charged_or_reserved_usd"]:.6f} / ${cfg["cloud"]["budget_usd"]} · tokens {bill["input_tokens"]} in / {bill["output_tokens"]} out · uncertain {bill["uncertain_calls"]}') if cfg.get('cloud') else ''
        self.run_detail.set_text(f'{cfg["objective"]}\n{method}  ·  phase: {s["phase"]}  ·  calls reserved: {s["calls"]}/{cfg["max_calls"]}'+spending)
        self.metrics['status'].set_text(run['status'].capitalize())
        self.metrics['baseline'].set_text(f'{report["baseline_accuracy"]:.1%}' if report else f'{s["baseline_validation"]:.1%} val' if 'baseline_validation' in s else '—')
        self.metrics['candidate'].set_text(f'{report["candidate_accuracy"]:.1%}' if report else f'{s["best_validation"]:.1%} val' if s.get('best_validation',-1)>=0 else '—')
        fraction=1 if run['status']=='completed' else min(.85,s.get('epoch',0)/cfg['epochs']*.8) if cfg['student']['kind']=='linear' else min(.85,s.get('attempt',0)/cfg['attempts']*.8)
        self.progress.set_fraction(fraction);self.progress.set_text(f'{s["phase"].capitalize()} · epoch {s.get("epoch",0)}/{cfg["epochs"]}' if cfg['student']['kind']=='linear' else f'{s["phase"].capitalize()} · prompt candidate {s.get("attempt",0)}/{cfg["attempts"]}')
        own=self.manager.rid==self.selected and self.manager.process and self.manager.process.poll() is None
        self.pause_button.set_sensitive(bool(own and run['status']=='running'));self.stop_button.set_sensitive(bool(own))
        self.resume_button.set_sensitive(bool(run['status']=='interrupted' or (own and run['status']=='paused')))
        events=self.store.events(self.selected);sig=(self.selected,events[-1]['seq'] if events else 0)
        if sig!=self.last_events:
            self.last_events=sig
            self.journal.get_buffer().set_text('\n\n'.join(f'{time.strftime("%H:%M:%S",time.localtime(e["time"]))}  {e["kind"].upper()}\n{inspection_summary(cfg['student'],s.get('student_info',{})) if e['kind']=='inspection' else e['message']}' for e in events))
            self.show_artifact()
            from .science import loss_chart
            try:chart=loss_chart(self.store.read(self.selected,'training-metrics.json'))
            except FileNotFoundError:chart=None
            if chart:
                loader=GdkPixbuf.PixbufLoader.new_with_type('svg');loader.write(chart.encode());loader.close()
                self.loss_image.set_from_pixbuf(loader.get_pixbuf())
            else:self.loss_image.clear()
        if report:
            self.verification.set_text(('PROMOTED' if report['promoted'] else 'NOT PROMOTED')+f' · {report["baseline_accuracy"]:.1%} → {report["candidate_accuracy"]:.1%} · paired p = {report["p_one_sided"]:.5f}\n'+report['policy']+'\n'+report['scope'])
        else:self.verification.set_text('No final evidence yet. Validation measurements are used for selection; held-out results decide promotion.')
        self.artifact_label.set_text('Artifact directory: '+str(self.store.root/self.selected))

    def export_evidence_bundle(self):
        from .bundle import export_bundle
        if not self.selected:self.message('Select a completed experiment first.');return
        if self.store.get(self.selected)['status']!='completed':self.message('Wait for the experiment to finish before exporting evidence.');return
        dialog=Gtk.FileChooserDialog(title='Export evidence ZIP (dataset text and weights excluded; review notes before sharing)',parent=self,action=Gtk.FileChooserAction.SAVE)
        dialog.add_buttons('Cancel',Gtk.ResponseType.CANCEL,'Export',Gtk.ResponseType.OK)
        dialog.set_current_name('gafaw-'+self.selected+'.zip')
        if dialog.run()==Gtk.ResponseType.OK:
            try:
                export_bundle(self.store,self.selected,dialog.get_filename())
                self.message('Private evidence exported. Inspect notes and configuration before sharing.')
            except Exception as e:self.message(redact(str(e)))
        dialog.destroy()

    def show_artifact(self):
        if not self.selected:return
        name=self.artifact_choice.get_active_text()
        try:
            data=self.store.read(self.selected,name)
            if name=='candidate.json' and data.get('weights'):
                data={**data,'weights':f'{len(data["weights"])} × {data["dimensions"]} real float weights; inspect full JSON on disk.'}
            self.artifact_text.get_buffer().set_text(json.dumps(data,indent=2,ensure_ascii=False))
        except FileNotFoundError:self.artifact_text.get_buffer().set_text('This artifact has not been produced yet.')

    def try_candidate(self):
        try:
            if not self.selected:raise ValueError('Select an experiment first.')
            artifact=self.store.read(self.selected,'candidate.json');text=self.try_input.get_text()
            if not 0<len(text)<=4000:raise ValueError('Enter 1–4000 characters.')
            if artifact['format']=='overmind.softmax.v1':self.try_result.set_text(TextStudent.restore(artifact).predict(text))
            else:
                from .inference import predict_artifact
                self.try_result.set_text('Running one local inference; this manual trial does not affect evaluation scores…')
                self.background(lambda:predict_artifact(artifact,text,allow_local=True),lambda result,error:self.try_result.set_text(error or result))
        except Exception as e:self.try_result.set_text(redact(str(e)))

    def close(self,*_):
        self.manager.stop();Gtk.main_quit();return False

def launch(root):
    harden_process()
    app=Desktop(root);app.show_all();Gtk.main()
