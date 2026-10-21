"""Offline guide, walkthroughs and context routing. No GTK, model or network imports."""
from dataclasses import dataclass
from .help_content import TOPICS, SHORT_HELP

TAB_TOPICS=('configure','laboratory','evidence','workshop','hardware','notebook','skins')


@dataclass(frozen=True)
class Article:
    key: str
    title: str
    category: str
    paragraphs: tuple[str,...]


GUIDES=(
    Article('guide.start','Quick Start: your first real experiment','Start here',(
        'Use the included support-routing dataset with the curriculum controller and CPU classifier. This trains a small text classifier, not a conversational language model, and needs no account or model download.',
        'In Configure, review the mentor, student, dataset and resource limits. Factory defaults are shown there. Reset to Defaults changes the next run, so use it only if you want to replace your unsaved configuration.',
        'Choose RUN EXPERIMENT yourself. The tutorial never starts a job or changes a setting. In Laboratory, follow the recorded loss, validation measurements and journal; the worker is bounded by your configured limits.',
        'After completion, open Evidence & artifacts. Check training-integrity.json for actual optimizer steps, changed parameters and reload verification, then read report.json and held-out predictions. Completion and falling loss do not guarantee promotion.',
        'Choose a walkthrough below for step-by-step navigation and highlighted controls. Next records a reviewed step; prerequisites are checked where indicated. Skipping is allowed and does not certify a completed experiment.')),
    Article('guide.interface','Find your way around GAFAW','Start here',(
        'Configure prepares the next run. Laboratory follows the selected run. Evidence & artifacts inspects its saved reports and provides the manual Personality Playground.',
        'Dataset Workshop reviews the next dataset. Hardware & Models inspects capabilities and local checkpoint metadata. Notebook & Compare stores notes and compares recorded results. Skin Library changes appearance.',
        'The sidebar selects saved experiments; it does not change the next configuration. Hover unfamiliar actions for a short explanation, use ? for a focused concept, and press F1 for the related guide.',
        'Shift+F1 opens What’s This with Stanley, or the guide if Stanley is disabled. Field help takes priority over the current tab; changing tabs or experiments clears old field context.')),
    Article('guide.datasets','Prepare and review a dataset','Workflows',(
        'For your first experiment, keep the built-in CC0 support-routing dataset. To inspect it, open Dataset Workshop and choose Load benchmark into editor.',
        'The labeled importer reads JSONL, CSV, TSV and tab-separated TXT with input/target columns and an optional split. Supply a license or permission statement. Automatic classification splits are deduplicated and stratified with the chosen seed; authored splits are retained.',
        'For LoRA, load the instruction seed to enter instruction-data editing mode, then review instruction/response JSONL with explicit train, validation and test assignments. Alternatively choose a complete compatible instruction JSON file in Configure.',
        'Validate & use reviewed data selects a snapshot for the next run. Editing afterward does not update that selection until you validate again. Export new dataset version saves a new private file and refuses overwrites.',
        'Exact-overlap checks do not detect every paraphrase. Keep evaluation examples independent and review the examples yourself before training.')),
    Article('guide.cpu','Configure a small CPU experiment','Workflows',(
        'Choose Curriculum controller as mentor and CPU text classifier as student. Keep the built-in support-routing data, or select a compatible licensed classification dataset.',
        'The learning objective records your hypothesis; it does not implement a new evaluator. Epochs bound passes through training data; wall minutes and worker RAM bound the worker. The external call limit is not a count of optimizer steps.',
        'Use factory defaults for a first run. Cloud spending and model-server sharing are unnecessary for this entirely local combination. Existing models and saved experiments are preserved.',
        'Click RUN EXPERIMENT only when you are ready. Every run gets a saved configuration and dataset snapshot, baseline, candidate measurements and evidence.')),
    Article('guide.running','Run, pause and stop safely','Workflows',(
        'RUN EXPERIMENT creates and starts a bounded worker from the current configuration and selected dataset. It can fail validation before starting; read the status message rather than assuming a job is running.',
        'Laboratory shows the selected run. Pause waits for an operation boundary, and the wall-time clock continues. Emergency stop terminates that worker; a separate inference server may finish an accepted request.',
        'Resume / Recover works only where the UI enables it. Interrupted LoRA runs preserve completed adapter artifacts but do not resume optimizer state; create a fresh experiment instead.',
        'Open Terminal Here uses the selected experiment directory, or the lab root when none is selected. It does not execute experiment files automatically.')),
    Article('guide.progress','Read real training measurements','Workflows',(
        'The loss curve and journal come from recorded worker measurements. No run means no measurements. A lower training loss means better fit to training examples, not necessarily better performance on unseen inputs.',
        'Validation tracks progress and guides candidate selection in supported workflows. The held-out split is reserved for the frozen final comparison. Repeatedly choosing experiments using that same holdout makes later comparisons exploratory.',
        'LoRA records optimizer steps, response loss, validation negative log likelihood, gradient norms, throughput and available memory diagnostics in its artifacts. Some measurements arrive at epoch boundaries, so the display need not move continuously.',
        'A stopped, limited or failed run is not a completed verification. Check the journal and saved artifacts to understand what finished.')),
    Article('guide.verification','Verify updates, reload and independent results','Workflows',(
        'Start with training-integrity.json: real optimizer steps, changed parameter evidence and a successful checkpoint reload establish that training mechanics worked.',
        'Then inspect report.json and baseline/candidate held-out predictions. Classifier promotion additionally requires improved held-out accuracy, the fixed paired test and no per-label regression.',
        'Generative LoRA does not automatically promote. Reference-response loss and exact matches do not certify reasoning, factual correctness or personality; review responses and regressions separately.',
        'Export private evidence bundle omits dataset text and weights by default, but notes and configuration can still contain private information. Inspect exports before sharing.')),
    Article('guide.local-llm','Local Qwen SFT + LoRA: prerequisites','Workflows',(
        'Select Local HF Qwen as student and the curriculum controller as mentor. Choose an existing supported HF safetensors checkpoint folder, record the model license you reviewed and select reviewed instruction data. Ollama/GGUF inference artifacts are not directly trainable HF checkpoints.',
        'Optional PyTorch, Transformers and PEFT dependencies belong in the isolated training interpreter; normal GTK and classifier use do not need them. This guide installs and downloads nothing. See docs/local-lora.md in the checkout for the explicit installation procedure.',
        'Choose the intended device and precision, then Check actual training compatibility. CUDA must actually initialize and pass its precision/kernel test; no silent CPU fallback occurs. A GPU name or fit estimate alone is not proof of compatibility.',
        'GTX 1080 Ti is Pascal with 11 GB VRAM and no BF16. A compatible CUDA/PyTorch build is required. FP32 uses more memory; FP16 support and stability must be verified. This backend does not enable FlashAttention, QLoRA, automatic offloading or distributed training.',
        'Start with short examples, one epoch, a small rank and a tiny optimizer-step cap for a mechanics smoke. Leave time for baseline evaluation, saving and fresh-base reload. A mechanical smoke verifies updates, not useful learned behavior.')),
    Article('guide.playground','Stock, prompted and adapter comparisons','Workflows',(
        'Personality Forge’s style/system prompt changes input context immediately. It changes no weights by itself. Reviewed LoRA training examples can produce persistent adapter updates on a supported local checkpoint.',
        'In Evidence & artifacts, select a completed LoRA experiment and enter one manual prompt in Personality Playground. Compare selected LoRA checkpoint generates matched stock, prompted and reloaded-adapter responses locally.',
        'For a prompt-only baseline, configure an existing Ollama or compatible local endpoint plus a style prompt, select an experiment to attach the trial, and use the prompt-only comparison action. It sends two explicit requests and trains no adapter.',
        'Rate style, instruction following, technical correctness and consistency separately. Zero means unrated; feedback is your judgment about the customized response, not an automatic intelligence score. Trials remain separate from the held-out benchmark.',
        'The guide never runs these comparisons for you. Model loading and generation use real resources; choose the relevant action only when your hardware and time budget permit.')),
    Article('guide.privacy','Offline help and private data','Reference',(
        'The guide, search, tutorials and Stanley use bundled deterministic text. No account, model, network request, telemetry or chat upload is involved.',
        'Context uses declared help IDs, current tab and non-sensitive workflow/status categories. It never reads field text, API keys, dataset contents, model responses or journal text to generate help.',
        'Help preferences contain only window geometry, toggles and tutorial progress in a private local JSON file next to the Skin Library directory. Experiment files and credentials are unchanged.',
        'Help cannot diagnose arbitrary error text. Use the real journal and compatibility report for details; Stanley’s reactions describe verified status categories, not an invented diagnosis.')),
    Article('guide.stanley','Stanley: Chief Executive Office Supply','Reference',(
        'Stanley is an original procedural SVG stapler, with animated eyes and a hinged jaw. He offers deterministic explanations of the current control or workspace; he is not a conversational language model.',
        'Click the sidebar stapler or press Shift+F1. The compact companion is a separate non-modal window with optional Always on Top. Its search looks up guide words; there is no model answering arbitrary questions.',
        'Use Help preferences below to disable Stanley completely, mute sarcasm or reduce motion. Hidden assistants have no animation timer; reduced motion also respects GTK’s system animation preference.',
        'Reactions are subtle and never open windows on their own. A completed run may fail promotion, and an adapter reload proves checkpoint integrity rather than improved intelligence.',
        'Window size, position and Always on Top are remembered on close. Some Linux desktops, especially Wayland compositors, may ignore requested position or stacking; normal window management still works.')),
)


def category(key):
    if key.startswith(('lora.','model.')) or key in ('lora','hardware'):return 'Local models & training'
    if key.startswith(('dataset.','experiment.','cloud.')):return 'Settings & safeguards'
    return 'Concepts & controls'


ARTICLES={a.key:a for a in GUIDES}
ARTICLES.update({key:Article(key,t.title,category(key),t.paragraphs) for key,t in TOPICS.items()})
ARTICLE_ORDER=tuple(ARTICLES)
SHORT_ROUTES={
    'terminal':'guide.running','endpoint':'student','model.identity':'student','credentials.input':'credentials',
    'discover':'student','inspect':'hardware','inference.test':'student','checkpoint.fresh':'checkpoint',
    'dataset.choose':'dataset','dataset.builtin':'dataset','run':'guide.running','pause':'guide.running',
    'resume':'guide.running','stop':'guide.running','artifact':'evidence','candidate.try':'evidence',
    'playground.prompt':'playground','feedback.notes':'feedback','feedback.save':'feedback',
    'workshop.import':'guide.datasets','workshop.benchmark':'guide.datasets','workshop.instructions':'guide.datasets',
    'workshop.use':'guide.datasets','workshop.editor':'guide.datasets','hardware.refresh':'hardware',
    'notes.save':'notebook','notes.editor':'notebook','compare.left':'comparison','compare.right':'comparison',
    'failures':'comparison','skin.select':'skins','skin.apply':'skins','skin.restore':'skins',
    'skin.import':'skins','skin.export':'skins','skin.refresh':'skins',
}
SHORT_ROUTES.update({f'feedback.{axis}':'feedback' for axis in ('style','instruction','technical','consistency')})


def article_key(key):
    return key if key in ARTICLES else SHORT_ROUTES.get(key,'guide.start')


def search(query):
    words=query.casefold().split()[:20]
    return [a for a in ARTICLES.values() if all(w in (' '.join((a.key,a.title,a.category,*a.paragraphs))).casefold() for w in words)]


class Context:
    """Only stable IDs and public status categories; never field values or experiment text."""
    def __init__(self):self.page=0;self.experiment=None;self.field=None;self.status=None;self.kind=None;self.stage=None

    def location(self,page,experiment):
        if (page,experiment)!=(self.page,self.experiment):self.field=None;self.status=None;self.kind=None;self.stage=None
        self.page=page if 0<=page<len(TAB_TOPICS) else 0;self.experiment=experiment

    def focus(self,key):self.field=key if key in TOPICS or key in SHORT_HELP else None

    def resolve(self,explicit=None):
        if explicit in ARTICLES or explicit in SHORT_HELP:return explicit
        return self.field or self.status or TAB_TOPICS[self.page]


@dataclass(frozen=True)
class Step:
    title: str
    text: str
    page: int
    target: str
    topic: str
    requires: str = ''


STEPS={
    'interface':Step('Meet the workbench','The seven tabs share one experiment history. This guide stays open while you use GAFAW. Show Control outlines the real next-run configuration without changing it.',0,'objective','guide.interface'),
    'dataset':Step('Review the examples','Load benchmark into editor to inspect the included examples, or import your licensed classification data. Preserve independent train, validation and test examples.',3,'dataset_editor','guide.datasets'),
    'select-data':Step('Select reviewed data','Validate & use reviewed data makes a snapshot for the next run. For a first experiment, you may instead keep Configure’s built-in benchmark; no import is required.',3,'workshop.use','workshop'),
    'configure':Step('Choose a CPU student','In Configure choose Curriculum controller and CPU text classifier. Keep built-in data and review limits. The tutorial never resets or edits your settings.',0,'student','guide.cpu'),
    'limits':Step('Understand your limits','Review epochs, wall minutes and RAM. Defaults are shown above. The CPU classifier needs no cloud spending or model-server sharing permission.',0,'epochs','experiment.epochs'),
    'run':Step('Start when you are ready','Choose RUN EXPERIMENT yourself after reviewing configuration. Next becomes available when a CPU-classifier experiment is selected; it does not start a job.',0,'run_button','guide.running','cpu-run'),
    'progress':Step('Observe recorded progress','Laboratory displays actual worker state, validation values, loss and journal entries. The wall-time budget includes pauses. Completion alone is not evidence of improvement.',1,'progress','guide.progress'),
    'evidence':Step('Verify the saved work','After the selected CPU experiment completes, inspect training-integrity.json and report.json. Next requires real update/reload evidence; promotion is a separate question.',2,'artifact_choice','guide.verification','cpu-verified'),
    'reports':Step('Interpret independent results','Choose saved artifacts to compare held-out results with baseline. Exact-match scores and loss have limits. Exported notes/configuration can still contain private information.',2,'artifact_choice','evidence'),
    'hardware':Step('Check hardware reality','Review actual diagnostics. A detected GPU is not a guarantee that a model fits or CUDA kernels work. The guide starts no benchmark, installation or download.',4,'hardware_details','hardware'),
    'lora':Step('Choose a trainable checkpoint','Read the local-model prerequisites. Select Local HF Qwen yourself before inspecting its settings; a local Ollama/GGUF inference artifact cannot replace HF base weights.',0,'student','guide.local-llm'),
    'preflight':Step('Review device and compatibility','After selecting the LoRA student, review device, precision, license and instruction data, then run its compatibility check yourself. Hidden LoRA controls are never enabled by this tutorial.',0,'lora_device','lora.device'),
    'style':Step('Try a style baseline','The optional style/system prompt changes context without updating weights. Configure a supported local inference endpoint for prompt-only comparisons, or train a compatible LoRA adapter separately.',0,'style_prompt','personality'),
    'playground':Step('Compare matched prompts','Open Personality Playground. A completed LoRA run supports stock/prompted/adapter comparison; a configured local endpoint supports the prompt-only path. Explicit actions use real model resources.',2,'playground_prompt','guide.playground'),
    'feedback':Step('Rate separate qualities','Rate the customized response by style, instruction following, technical correctness and consistency, then save feedback. A funny answer is not automatically a correct one.',2,'feedback_notes','feedback'),
}
TUTORIALS={
    'quick-start':('Quick Start · real CPU experiment',('interface','configure','limits','run','progress','evidence','reports')),
    'interface':('1 · Find your way around',('interface',)),
    'datasets':('2 · Prepare or import data',('dataset','select-data')),
    'cpu':('3 · Configure CPU training',('configure','limits')),
    'running':('4 · Run an experiment',('run','progress')),
    'progress':('5 · Understand measurements',('progress','reports')),
    'evidence':('6 · Verify learning evidence',('evidence','reports')),
    'local-llm':('7 · Local LLM prerequisites',('hardware','lora','preflight')),
    'playground':('8 · Compare model variants',('style','playground','feedback')),
}

# Quips never carry the instructions or claim unobserved outcomes.
QUIPS={
    'default':'I’m just trying to hold things together.',
    'lora.learning_rate':'Small adjustments. A revolutionary alternative to turning everything up to eleven.',
    'lora.rank':'Bigger is not automatically better. A difficult memo for the hardware department.',
    'workshop':'Garbage in, garbage out. Office supplies have known this for years.',
    'evidence':'Evidence. Finally, something we can staple to a claim.',
    'welcome':'Ah, documentation. The thing everyone ignores until something catches fire.',
    'tutorial':'Congratulations. You can now press buttons with slightly more confidence.',
    'failed':'Something broke. Fortunately, we kept the paperwork.',
    'completed':'The worker has finished. Let’s read the evidence before ordering a cake.',
    'verified':'Actual parameter updates and a reload. The paperwork checks out; quality is a separate meeting.',
    'incompatible':'This setup has declined to participate. Consult the compatibility report.',
}


def verified_report(report):
    if not isinstance(report,dict):return False
    integrity=report.get('training_integrity',{})
    if not isinstance(integrity,dict):return False
    reload_key='checkpoint_reload_verified' if (report or {}).get('method')=='sft_lora' else 'checkpoint_reload_matches_validation'
    return (integrity.get('verified') is True and type(integrity.get('optimizer_steps')) is int and integrity['optimizer_steps']>0
            and type(integrity.get('parameters_changed')) is int and integrity['parameters_changed']>0 and integrity.get(reload_key) is True)


def reaction(status,report):
    if status=='failed':return ('concerned','failed','The selected experiment failed. Inspect the recorded journal and artifacts for the actual cause.')
    if status!='completed':return None
    if verified_report(report):
        return ('celebrate','verified','The saved report verifies parameter updates and checkpoint reload. Review independent results before claiming an improvement.')
    return ('greeting','completed','The worker completed. Inspect its report; completion alone does not verify learning or promotion.')
