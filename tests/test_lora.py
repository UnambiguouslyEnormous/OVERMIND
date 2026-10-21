"""Trust-boundary tests only. Fake weight files are metadata fixtures, never training evidence."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from overmind.data import benchmark,load
from overmind.lab import config_checked,DEFAULTS,Experiment
from overmind.lora import checked,checkpoint_files,preflight
from overmind.sft_data import example,validate,reviewed_jsonl,editable_jsonl
from overmind.store import Store
from overmind.workshop import export_version

class LoraTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.model=self.root/'model';self.model.mkdir()
        (self.model/'config.json').write_text(json.dumps({'model_type':'qwen2'}))
        (self.model/'tokenizer.json').write_text('{}')
        (self.model/'model.safetensors').write_bytes(b'not actual model weights; metadata fixture only')
        self.config={**DEFAULTS,'student':{'kind':'local_lora','model':str(self.model)},'epochs':1,'memory_mb':4096,
                     'lora':{'model_license':'fixture permission'}}

    def test_instruction_split_roundtrip_and_leakage_rejection(self):
        data=example();reviewed=reviewed_jsonl(editable_jsonl(data),data['license'],data['name'],data)
        for split in ('train','validation','test'):self.assertEqual(reviewed[split],data[split])
        bad=copy.deepcopy(data);bad['test'][0]['input']='  '+bad['train'][0]['input'].upper()+' '
        with self.assertRaisesRegex(ValueError,'Duplicate'):validate(bad)
        with self.assertRaisesRegex(ValueError,'explicit'):reviewed_jsonl('{"input":"i","target":"t"}','CC0')
        path=self.root/'version.json';export_version(reviewed,path);self.assertEqual(load(path),reviewed)

    def test_sft_and_classification_cannot_be_silently_mixed(self):
        store=Store(self.root/'lab');cfg=config_checked(self.config)
        with self.assertRaisesRegex(ValueError,'requires'):store.create(cfg,benchmark())
        with self.assertRaisesRegex(ValueError,'requires'):store.create(config_checked(DEFAULTS),example())
        rid=store.create(cfg,example());self.assertEqual(store.get(rid)['config']['student']['kind'],'local_lora')

    def test_no_cloud_custom_code_quantization_or_pickle(self):
        for options in ({'device':'cpu','precision':'fp16'},{'precision':'bf16'},{'learning_rate':float('nan')},{'python':'/arbitrary/code'}):
            with self.subTest(options=options),self.assertRaises(ValueError):checked({'model_license':'fixture',**options})
        with self.assertRaisesRegex(ValueError,'controller'):config_checked({**self.config,'mentor':{'kind':'openai','model':'fixture'}})
        for field in ('auto_map','quantization_config'):
            (self.model/'config.json').write_text(json.dumps({'model_type':'qwen2',field:{'fixture':True}}))
            with self.assertRaises(ValueError):checkpoint_files(self.model)
        (self.model/'config.json').write_text('{"model_type":"qwen2"}')
        (self.model/'pytorch_model.bin').write_bytes(b'never deserialized')
        with self.assertRaisesRegex(ValueError,'Pickle'):checkpoint_files(self.model)

    def test_shard_traversal_is_rejected(self):
        (self.model/'model.safetensors.index.json').write_text(json.dumps({'weight_map':{'w':'../outside.safetensors'}}))
        with self.assertRaisesRegex(ValueError,'shard'):checkpoint_files(self.model)

    def test_missing_dependencies_are_reported_without_training_claims(self):
        with patch('overmind.lora.importlib.util.find_spec',return_value=None):
            report=preflight(self.model,{'model_license':'fixture permission'},4096,runtime=True)
        self.assertFalse(report['ready']);self.assertIn('Missing optional',' '.join(report['blockers']))
        self.assertIsNone(report['runtime_device'])
        self.assertNotIn('optimizer_steps',report)
