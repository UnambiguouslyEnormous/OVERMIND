"""Tests use explicit fixtures for provider replies; no fixture scores are product evidence."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from overmind.data import benchmark, validate, digest
from overmind.lab import Experiment, DEFAULTS, Manager, config_checked, score, verdict, Limit, Halt
from overmind.model import TextStudent
from overmind.providers import LocalProvider, json_reply
from overmind.store import Store

class LabTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=Store(self.temp.name)

    def create(self,**overrides):
        return self.store.create(config_checked({**DEFAULTS,**overrides}),benchmark())

    def test_real_weights_and_independent_final_evidence(self):
        rid=self.create(epochs=8)
        Experiment(self.store,rid).run()
        run=self.store.get(rid);report=self.store.read(rid,'report.json')
        self.assertEqual(run['status'],'completed')
        self.assertEqual(report['method'],'weight_training')
        self.assertGreater(report['candidate_accuracy'],report['baseline_accuracy'])
        self.assertTrue(report['promoted'])
        self.assertEqual(report['test_count'],40)
        candidate=self.store.read(rid,'candidate.json')
        self.assertTrue(any(w!=0 for row in candidate['weights'] for w in row))
        model=TextStudent.restore(candidate)
        final=score(benchmark()['test'],model.predict)
        self.assertEqual(final,self.store.read(rid,'candidate-test.json'))
        self.assertEqual(report['dataset_sha256'],digest(benchmark()))
        import hashlib
        self.assertEqual(report['candidate_sha256'],hashlib.sha256((self.store.root/rid/'candidate.json').read_bytes()).hexdigest())

    def test_test_answers_never_enter_mentor_context(self):
        rid=self.create(epochs=1,mentor={'kind':'ollama','url':'http://127.0.0.1:11434','model':'fixture'})
        prompts=[]
        def generate(_,system,prompt,max_tokens=512):
            prompts.append(system+prompt)
            return json.dumps({'learning_rate':.5,'reason':'Fixture curriculum for integration testing.'})
        with patch.object(LocalProvider,'inspect',return_value={'architecture':'fixture'}),patch.object(LocalProvider,'generate',generate):
            Experiment(self.store,rid).run()
        self.assertTrue(prompts)
        for row in benchmark()['test']:
            self.assertNotIn(row['input'],''.join(prompts))
        self.assertEqual(self.store.get(rid)['state']['calls'],1)

    def test_prompt_pipeline_is_separate_from_weight_training(self):
        cfg={'student':{'kind':'compatible','url':'http://127.0.0.1:9000','model':'student-fixture'},
             'mentor':{'kind':'ollama','url':'http://127.0.0.1:11434','model':'mentor-fixture'},'attempts':1}
        rid=self.create(**cfg)
        def generate(p,system,prompt,max_tokens=512):
            if p.model=='mentor-fixture':return json.dumps({'system_prompt':'fixture classifier','reason':'Explicit test fixture.'})
            # Deliberately weak, constant-output fixture: no fabricated gain should be promoted.
            return 'account'
        with patch.object(LocalProvider,'inspect',return_value={'architecture':'fixture'}),patch.object(LocalProvider,'generate',generate):
            Experiment(self.store,rid).run()
        report=self.store.read(rid,'report.json')
        self.assertEqual(report['method'],'prompt_optimization')
        self.assertFalse(report['promoted'])
        self.assertEqual(self.store.read(rid,'candidate.json')['format'],'overmind.prompt.v1')
        self.assertFalse((self.store.root/rid/'promoted.json').exists())

    def test_data_leakage_and_license_validation(self):
        b=benchmark();b['test'][0]=dict(b['train'][0])
        with self.assertRaisesRegex(ValueError,'Duplicate'):validate(b)
        b=benchmark();b.pop('license')
        with self.assertRaisesRegex(ValueError,'license'):validate(b)

    def test_no_remote_redirects_or_paid_access(self):
        for url in ['https://api.example.com','http://192.168.1.10:11434','http://example.com','http://127.0.0.1@evil.test', 'http://127.0.0.1?key=secret']:
            with self.subTest(url=url), self.assertRaises(ValueError):LocalProvider('ollama',url,'model')
        p=LocalProvider('ollama','http://localhost:11434','student')
        self.assertEqual(p.url,'http://127.0.0.1:11434')
        self.assertEqual(LocalProvider('compatible','http://[::1]:9000','student').url,'http://[::1]:9000')

    def test_mentor_commands_are_validated_never_executed(self):
        rid=self.create(mentor={'kind':'ollama','url':'http://127.0.0.1:11434','model':'fixture'})
        exp=Experiment(self.store,rid);exp.s['hardware']={}
        for rate in [100,-1,'execute shell',float('nan')]:
            with patch.object(LocalProvider,'generate',return_value=json.dumps({'learning_rate':rate,'reason':'invalid'})):
                with self.assertRaises(ValueError):exp.mentor_plan()
        self.assertFalse(Path(self.temp.name,'unsafe').exists())

    def test_call_budget_is_reserved_before_dispatch(self):
        rid=self.create(max_calls=1);exp=Experiment(self.store,rid)
        p=LocalProvider('ollama','http://127.0.0.1:11434','fixture')
        with patch.object(p,'generate',side_effect=TimeoutError('provider timeout')):
            with self.assertRaises(TimeoutError):exp.call(p,'system','input')
            with self.assertRaises(Limit):exp.call(p,'system','input')
        self.assertEqual(self.store.get(rid)['state']['calls'],1)

    def test_wall_budget_and_stop_guard(self):
        rid=self.create(minutes=1);exp=Experiment(self.store,rid)
        exp.elapsed=61
        with self.assertRaises(Limit):exp.guard()
        exp.elapsed=0;self.store.update(rid,status='stopped')
        with self.assertRaises(Halt):exp.guard()

    def test_promotion_rejects_ties_regressions_and_small_evidence(self):
        rows=[{'input':str(i),'target':'a' if i<2 else 'b'} for i in range(4)]
        base=score(rows,lambda _: 'a')
        tie=score(rows,lambda _: 'a')
        self.assertFalse(verdict(base,tie,['a','b'])['promoted'])
        better=score(rows,lambda x:'a' if int(x)<2 else 'b')
        self.assertFalse(verdict(base,better,['a','b'])['promoted'])
        regression=score(rows,lambda _: 'b')
        self.assertFalse(verdict(base,regression,['a','b'])['promoted'])

    def test_validation_selected_candidate_frozen_on_recovery(self):
        rid=self.create(epochs=2);exp=Experiment(self.store,rid)
        # Stop at verification boundary to emulate a crash after model selection.
        with patch.object(exp,'verify',side_effect=RuntimeError('interruption')):
            with self.assertRaises(RuntimeError):exp.run()
        frozen=(self.store.root/rid/'candidate.json').read_bytes()
        self.store.update(rid,status='interrupted')
        with patch.object(Experiment,'train_weights',side_effect=AssertionError('must not retrain')):
            Experiment(self.store,rid).run()
        self.assertEqual(frozen,(self.store.root/rid/'candidate.json').read_bytes())
        self.assertEqual(self.store.get(rid)['status'],'completed')

    def test_config_limits(self):
        for field,value in [('epochs',0),('memory_mb',16),('minutes',999),('max_calls',True),('allow_synthetic',True)]:
            with self.subTest(field=field),self.assertRaises(ValueError):config_checked({field:value})
        with self.assertRaises(ValueError):config_checked({'student':{'kind':'ollama','url':'http://127.0.0.1:11434','model':'a'}})

    def test_artifact_load_rejects_nonfinite_or_wrong_weights(self):
        m=TextStudent(['a','b'],16);a=m.export();a['weights'][0][0]=float('nan')
        with self.assertRaises(ValueError):TextStudent.restore(a)
        with self.assertRaises(ValueError):json_reply('__import__("os").system("true")')

    def test_worker_subprocess_real_memory_bounded_run(self):
        out=subprocess.run([sys.executable,'-m','overmind','--data',self.temp.name,'run','--epochs','2'],capture_output=True,text=True,timeout=30)
        self.assertEqual(out.returncode,0,out.stdout+out.stderr)
        self.assertIn('Status: completed',out.stdout)

    def test_pause_resume_stop_worker(self):
        rid=self.create(epochs=60);manager=Manager(self.temp.name);manager.start(rid)
        self.addCleanup(manager.stop)
        deadline=time.monotonic()+8
        while time.monotonic()<deadline and self.store.get(rid)['state']['epoch']<1:time.sleep(.03)
        manager.pause();time.sleep(.3)
        self.assertEqual(self.store.get(rid)['status'],'paused')
        epoch=self.store.get(rid)['state']['epoch'];time.sleep(.2)
        self.assertEqual(self.store.get(rid)['state']['epoch'],epoch)
        manager.resume();time.sleep(.1)
        self.assertEqual(self.store.get(rid)['status'],'running')
        manager.stop()
        self.assertEqual(self.store.get(rid)['status'],'stopped')
        self.assertIsNotNone(manager.process.poll())


    def test_existing_checkpoint_is_snapshotted_and_used_for_baseline(self):
        data=benchmark();base=TextStudent(data['labels'])
        for epoch in range(3):base.epoch(data['train'],.6,epoch,lambda:None)
        path=Path(self.temp.name)/'base.json';raw=json.dumps(base.export());path.write_text(raw)
        rid=self.create(epochs=1,student={'kind':'linear','checkpoint':str(path)})
        expected=score(data['validation'],base.predict)
        Experiment(self.store,rid).run()
        self.assertEqual(self.store.read(rid,'baseline-validation.json'),expected)
        self.assertEqual(path.read_text(),raw)
        self.assertEqual(self.store.read(rid,'original-student.json'),base.export())

    def test_provider_wire_formats_and_no_redirects(self):
        class Response:
            def __init__(self,payload):self.payload=payload
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,n):return json.dumps(self.payload).encode()
        class Opener:
            def __init__(self,payload):self.payload=payload;self.requests=[]
            def open(self,req,timeout):self.requests.append(req);return Response(self.payload)
        op=Opener({'response':'billing'})
        p=LocalProvider('ollama','http://127.0.0.1:11434','fixture')
        with patch('urllib.request.build_opener',return_value=op) as factory:
            self.assertEqual(p.generate('system','request',32),'billing')
            handlers=factory.call_args.args
            with self.assertRaises(ValueError):handlers[1].redirect_request(None,None,None,None,None,None)
        req=op.requests[0];body=json.loads(req.data)
        self.assertTrue(req.full_url.endswith('/api/generate'))
        self.assertFalse(body['stream']);self.assertEqual(body['options']['num_predict'],32)
        op=Opener({'choices':[{'message':{'content':'security'}}]})
        p=LocalProvider('compatible','http://127.0.0.1:9000','fixture')
        with patch('urllib.request.build_opener',return_value=op):self.assertEqual(p.generate('system','request'),'security')
        self.assertTrue(op.requests[0].full_url.endswith('/v1/chat/completions'))

    def test_epoch_checkpoint_cursor_recovers_consistently(self):
        rid=self.create(epochs=2);exp=Experiment(self.store,rid)
        with patch.object(exp,'verify',side_effect=RuntimeError('interrupt')):
            with self.assertRaises(RuntimeError):exp.run()
        checkpoint=self.store.read(rid,'working.json')
        self.assertEqual(checkpoint['epoch'],2)
        # SQLite state lagging behind the atomically persisted weights must not cause extra SGD epochs.
        state=self.store.get(rid)['state'];state['epoch']=0;state['phase']='improve'
        self.store.update(rid,state=state,status='interrupted')
        with patch.object(TextStudent,'epoch',side_effect=AssertionError('already trained')):
            Experiment(self.store,rid).run()
        self.assertEqual(self.store.get(rid)['state']['epoch'],2)

if __name__=='__main__':unittest.main()
