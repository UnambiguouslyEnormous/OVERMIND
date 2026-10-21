#!/usr/bin/env python3
"""Actual GTK -> worker diagnostic when ML dependencies are absent; never trains fixtures."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from overmind.desktop import Desktop
from gi.repository import Gtk
if all(importlib.util.find_spec(name) for name in ('torch','transformers','peft','safetensors')):
    raise SystemExit('This check is for an environment without ML dependencies. Use tools/lora_smoke.py instead.')
with tempfile.TemporaryDirectory() as temporary:
    root=Path(temporary);model=root/'model';model.mkdir()
    (model/'config.json').write_text('{"model_type":"qwen2"}')
    (model/'tokenizer.json').write_text('{}')
    (model/'model.safetensors').write_bytes(b'metadata-only fixture, must never be trained')
    app=Desktop(root/'lab',skin_root=root/'skins');app.show_all()
    app.role_widgets['student'][0].set_active_id('local_lora')
    app.role_widgets['student'][2].get_child().set_text(str(model));app.lora_license.set_text('fixture permission')
    app.edit_instructions();app.use_workshop();assert app.prepared_dataset['format']=='gafaw.sft.v1'
    app.run_new();assert app.selected,app.status.get_text()
    deadline=time.monotonic()+15
    try:
        while time.monotonic()<deadline:
            while Gtk.events_pending():Gtk.main_iteration_do(False)
            app.tick();run=app.store.get(app.selected)
            if run['status']=='failed':break
            if run['status'] not in ('ready','running'):raise AssertionError(run['status'])
            time.sleep(.05)
        else:raise AssertionError('Missing-dependency worker did not terminate promptly')
        diagnostic=app.store.read(app.selected,'preflight.json')
        assert not diagnostic['ready'] and 'Missing optional' in ' '.join(diagnostic['blockers'])
        assert not (app.store.root/app.selected/'training-integrity.json').exists()
        assert 'No LoRA' not in app.verification.get_text() or run['status']=='failed'
    finally:app.manager.stop();app.destroy()
print('GTK instruction review -> real worker -> truthful missing-dependency failure passed. No LoRA update or reload claimed.')
