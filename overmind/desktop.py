"""Native GTK desktop. All experiment work happens in a separate bounded process."""
import json
from pathlib import Path
import threading
import time
import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk, Gdk, GLib

from .data import load
from .hardware import inspect
from .lab import Manager, DEFAULTS, config_checked
from .model import TextStudent
from .providers import provider, inspection_summary
from .security import register, redact, clear_credentials, harden_process
from .ollama import discover

CSS = b'''
* { font-family: "Inter", "DejaVu Sans", sans-serif; font-size: 13px; }
window { background: #11151e; color: #e5eaf4; }
headerbar { background: #171c28; border: 0; padding: 12px; }
headerbar .title { color: #f4f6fc; font-weight: bold; }
.sidebar { background: #151a25; border-right: 1px solid #2a3243; padding: 20px; }
.title { font-size: 28px; font-weight: bold; color: #f4f7fd; }
.subtitle { color: #9caac0; font-size: 13px; }
.brand { font-size: 21px; letter-spacing: 3px; font-weight: bold; color: #b8c5ff; }
.eyebrow { font-size: 11px; font-weight: bold; color: #9aacc8; letter-spacing: 1px; }
.card { background: #1b2230; border: 1px solid #303b50; border-radius: 12px; padding: 20px; }
.metric { font-size: 30px; font-weight: bold; color: #c4d0ff; }
button { background: #273247; border: 1px solid #3a4861; color: #eaf0ff; border-radius: 7px; padding: 9px 14px; }
button:hover { background: #354766; }
button:disabled { opacity: 0.4; }
button.primary { background: #a8bbff; border-color: #a8bbff; color: #10182b; font-weight: bold; }
button.danger { background: #512c39; border-color: #855064; color: #ffccda; }
entry, spinbutton, combobox button, textview text { background: #121925; color: #e4ebf8; border-color: #39455c; }
entry, spinbutton { border-radius: 6px; padding: 8px; }
textview { background: #121925; padding: 14px; }
textview text { font-family: "DejaVu Sans Mono", monospace; font-size: 12px; }
notebook header { background: #151b27; border-bottom: 1px solid #303b50; }
notebook tab { padding: 12px 18px; }
notebook tab:checked { color: #b8c8ff; border-bottom: 2px solid #b8c8ff; }
list, list row { background: transparent; color: #dce4f2; }
list row:selected { background: #2a3650; border-radius: 7px; }
progressbar trough { background: #293449; border: 0; border-radius: 4px; min-height: 6px; }
progressbar progress { background: #9bb3ff; border: 0; border-radius: 4px; }
separator { background: #303b50; }
'''

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
    def __init__(self,root):
        super().__init__(title='OVERMIND — AI Apprenticeship Laboratory')
        self.set_default_size(1280,900);self.set_size_request(980,700)
        self.manager=Manager(root);self.store=self.manager.store
        self.selected=None;self.dataset_path=None;self.checkpoint_path=None;self.history_signature=None;self.last_events=None;self.last_hardware=0
        self.connect('delete-event',self.close)
        css=Gtk.CssProvider();css.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(),css,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        header=Gtk.HeaderBar();header.set_show_close_button(True);header.set_title('OVERMIND')
        header.set_subtitle('AI APPRENTICESHIP LABORATORY  /  0.2')
        self.hardware_label=label('Detecting hardware…','subtitle');header.pack_end(self.hardware_label)
        self.set_titlebar(header)
        layout=box(0,True);self.add(layout)
        side=box(18);side.set_size_request(248,-1);side.get_style_context().add_class('sidebar');layout.pack_start(side,False,False,0)
        side.pack_start(label('OVERMIND','brand'),False,False,0)
        side.pack_start(label('Teach. Test. Verify.','subtitle'),False,False,0)
        side.pack_start(button('+  New experiment',self.new,'primary'),False,False,4)
        side.pack_start(label('EXPERIMENT MEMORY','eyebrow'),False,False,8)
        self.history=Gtk.ListBox();self.history.set_selection_mode(Gtk.SelectionMode.SINGLE);self.history.connect('row-selected',self.history_selected)
        side.pack_start(scroll(self.history),True,True,0)
        side.pack_start(label('LOCAL STUDENT\nCloud mentor requires consent\nNo automatic file uploads','subtitle'),False,False,0)
        side.pack_start(label(str(self.store.root),'subtitle',True),False,False,0)
        self.tabs=Gtk.Notebook();layout.pack_start(self.tabs,True,True,0)
        self.setup_tab();self.live_tab();self.evidence_tab()
        self.status=label('Ready. The built-in experiment needs no downloads.','subtitle',True)
        self.setup_content.pack_end(self.status,False,False,0)
        self.tick();GLib.timeout_add(500,self.tick)

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
        c.pack_start(label('DECISIONS & MEASUREMENTS','eyebrow'),False,False,0)
        self.journal=Gtk.TextView();self.journal.set_editable(False);self.journal.set_cursor_visible(False);self.journal.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        sc=scroll(self.journal);sc.set_size_request(-1,300);c.pack_start(sc,True,True,0)

    def evidence_tab(self):
        c=self.page('03   Evidence & artifacts')
        c.pack_start(label('Proof before promotion.','title'),False,False,0)
        self.verification=label('No completed comparison yet. Improvement is never assumed.','subtitle',True);c.pack_start(self.verification,False,False,0)
        self.artifact_label=label('Candidates, dataset snapshots, raw predictions and reports are saved locally.','subtitle',True);c.pack_start(self.artifact_label,False,False,0)
        self.artifact_choice=Gtk.ComboBoxText()
        for name in ('report.json','candidate.json','baseline-validation.json','latest-validation.json','baseline-test.json','candidate-test.json','promoted.json','billing.json'):
            self.artifact_choice.append_text(name)
        self.artifact_choice.set_active(0);self.artifact_choice.connect('changed',lambda _:self.show_artifact())
        c.pack_start(self.artifact_choice,False,False,0)
        self.artifact_text=Gtk.TextView();self.artifact_text.set_editable(False);self.artifact_text.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        sc=scroll(self.artifact_text);sc.set_size_request(-1,260);c.pack_start(sc,True,True,0)
        trial=self.card('TRY THE FROZEN STUDENT','Loads the selected artifact. This input is not added to training data or the benchmark.')
        self.try_input=entry('I need a refund for a duplicate charge');trial.pack_start(self.try_input,False,False,0)
        trial.pack_start(button('Classify with candidate',self.try_candidate),False,False,0)
        self.try_result=label('—','subtitle',True);trial.pack_start(self.try_result,False,False,0);c.pack_start(trial,False,False,0)

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
                data=load(path);self.dataset_path=path
                self.dataset_label.set_text(f'{Path(path).name} · {data["license"]} · '+ ' / '.join(f'{len(data[k])} {k}' for k in ('train','validation','test')))
            except Exception as e:self.message(redact(str(e)))
        dialog.destroy()

    def choose_checkpoint(self):
        dialog=Gtk.FileChooserDialog(title='Select OVERMIND classifier weights JSON',parent=self,action=Gtk.FileChooserAction.OPEN)
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
        self.dataset_path=None;self.dataset_label.set_text('Support routing v1 · CC0 · 80 training / 24 validation / 40 held-out examples')

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
            c=config_checked(c);dataset=load(self.dataset_path)
            rid=self.store.create(c,dataset);self.selected=rid;self.manager.start(rid)
            self.tabs.set_current_page(1);self.message('Experiment started.');self.tick()
        except Exception as e:self.message(redact(str(e)))

    def new(self):self.tabs.set_current_page(0)
    def history_selected(self,_,row):
        if row:self.selected=row.rid;self.last_events=None;self.refresh_run();self.show_artifact()
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
        self.refresh_run()
        if time.monotonic()-self.last_hardware>8:
            self.last_hardware=time.monotonic()
            self.background(inspect,lambda h,e:self.hardware_label.set_text(f'{h["ram_mb"]//1024} GB RAM  ·  '+('NVIDIA available' if h['gpu'] else 'CPU · NVIDIA unavailable')) if h and h.get('ram_mb') else None)
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
        if report:
            self.verification.set_text(('PROMOTED' if report['promoted'] else 'NOT PROMOTED')+f' · {report["baseline_accuracy"]:.1%} → {report["candidate_accuracy"]:.1%} · paired p = {report["p_one_sided"]:.5f}\n'+report['policy']+'\n'+report['scope'])
        else:self.verification.set_text('No final evidence yet. Validation measurements are used for selection; held-out results decide promotion.')
        self.artifact_label.set_text('Artifact directory: '+str(self.store.root/self.selected))

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
