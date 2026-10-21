#!/usr/bin/env python3
"""Opt-in tiny actual Qwen2/PEFT CPU run. No model download or mocked training success."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
missing=[name for name in ('torch','transformers','peft','safetensors','tokenizers') if importlib.util.find_spec(name) is None]
if missing:
    print('UNAVAILABLE: '+', '.join(missing)+'. No LoRA optimizer step or checkpoint reload was executed. See docs/local-lora.md.')
    raise SystemExit(2)
import torch
from tokenizers import Tokenizer
from tokenizers.models import WordLevel
from tokenizers.pre_tokenizers import Whitespace
from transformers import Qwen2Config,Qwen2ForCausalLM,PreTrainedTokenizerFast
from overmind.lab import DEFAULTS,Manager,config_checked,Experiment
from overmind.sft_data import example
from overmind.lora import playground
from unittest.mock import patch

torch.set_num_threads(2)
with tempfile.TemporaryDirectory() as temporary:
    root=Path(temporary);model=root/'tiny-qwen';model.mkdir();data=example()
    words=sorted({word for split in ('train','validation','test') for row in data[split] for word in (row['input']+' '+row['target']).split()})
    vocabulary={word:i for i,word in enumerate(['[UNK]','[PAD]','[EOS]','user','assistant','system',':',*words])}
    # Whitespace pretokenization can produce unknown punctuation; this remains an actual causal LM.
    backend=Tokenizer(WordLevel(vocabulary,unk_token='[UNK]'));backend.pre_tokenizer=Whitespace()
    tokenizer=PreTrainedTokenizerFast(tokenizer_object=backend,unk_token='[UNK]',pad_token='[PAD]',eos_token='[EOS]')
    tokenizer.chat_template="{% for message in messages %}{{ message['role'] + ': ' + message['content'] + '\n' }}{% endfor %}{% if add_generation_prompt %}{{ 'assistant: ' }}{% endif %}"
    tokenizer.save_pretrained(model)
    tiny=Qwen2ForCausalLM(Qwen2Config(vocab_size=max(vocabulary.values())+1,hidden_size=32,intermediate_size=64,num_hidden_layers=1,
                                   num_attention_heads=4,num_key_value_heads=2,max_position_embeddings=256,eos_token_id=2,pad_token_id=1))
    tiny.save_pretrained(model,safe_serialization=True);del tiny
    config=config_checked({**DEFAULTS,'student':{'kind':'local_lora','model':str(model)},'epochs':1,'memory_mb':4096,'minutes':2,
                           'lora':{'model_license':'CC0 synthetic random fixture','max_length':128,'max_new_tokens':4,'max_steps':2,'rank':2,'alpha':4}})
    manager=Manager(root/'lab');rid=manager.store.create(config,data);manager.start(rid);start=time.monotonic()
    try:
        while manager.process.poll() is None:
            manager.poll()
            if time.monotonic()-start>90:raise RuntimeError('Tiny LoRA smoke exceeded 90-second budget')
            time.sleep(.1)
        manager.poll()
        if manager.store.get(rid)['status']!='completed':raise RuntimeError(json.dumps(manager.store.events(rid),indent=2))
        evidence=manager.store.read(rid,'training-integrity.json')
        assert evidence['verified'] and evidence['checkpoint_reload_verified'] and evidence['optimizer_steps']==2
        assert evidence['before_sha256']!=evidence['after_sha256'] and evidence['parameters_changed']>0
        trial=playground(manager.store,rid,'Explain a fuse.')
        assert all(isinstance(trial[key],str) for key in ('stock','prompted','adapter'))
        from overmind.bundle import export_bundle,validate_bundle
        bundle=root/'evidence.zip';export_bundle(manager.store,rid,bundle,include_weights=True);validate_bundle(bundle)
        # Negative control intentionally sabotages optimizer updates after real forward/backward work.
        negative=manager.store.create(config,data)
        with patch.object(torch.optim.AdamW,'step',return_value=None):
            try:Experiment(manager.store,negative).run()
            except ValueError as error:assert 'unchanged adapter' in str(error)
            else:raise AssertionError('Zero-update backend must be rejected')
        print(json.dumps({'actual_tiny_qwen_cpu_run':rid,'integrity':evidence,'zero_update_negative_control':'rejected',
                          'notice':'Random tiny Qwen architecture, not pretrained Qwen capability evidence; no physical GPU tested.'},indent=2))
    finally:manager.stop()
