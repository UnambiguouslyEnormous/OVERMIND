"""Bounded protocol/integration fixtures. No paid calls or real LLM gains are implied."""
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

from overmind.cloud import CloudProvider, ProviderError, BudgetExceeded, cloud_limits
from overmind.data import benchmark
from overmind.lab import Experiment, config_checked, DEFAULTS
from overmind.providers import LocalProvider
from overmind.security import register, worker_environment
from overmind.store import Store
from overmind.ollama import discover
from overmind.retrieval import augment

LIMITS={'authorized':True,'data_sharing':True,'budget_usd':'1','input_usd_per_million':'10','output_usd_per_million':'30','max_output_tokens':2048}

def small_data():
    data=benchmark()
    for split in ('train','validation','test'):
        data[split]=[r for label in data['labels'] for r in [x for x in data[split] if x['target']==label][:2]]
    return data

class Response:
    def __init__(self,payload):self.payload=payload
    def __enter__(self):return self
    def __exit__(self,*a):pass
    def read(self,n):return json.dumps(self.payload).encode()

class Phase2Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=Store(self.tmp.name)
        self.addCleanup(lambda:register('openai',''));self.addCleanup(lambda:register('anthropic',''))
        self.env=patch.dict(os.environ,{'OPENAI_API_KEY':'private-openai-fixture','ANTHROPIC_API_KEY':'private-anthropic-fixture'},clear=True)
        self.env.start();self.addCleanup(self.env.stop)

    def run_id(self,kind='openai',**overrides):
        c=config_checked({'mentor':{'kind':kind,'model':'mentor-fixture'},'student':{'kind':'ollama','url':'http://127.0.0.1:11434','model':'student-fixture'},'attempts':2,'cloud':LIMITS,**overrides})
        return self.store.create(c,small_data())

    def test_authorization_data_consent_rates_and_role_required(self):
        for field,value in [('authorized',False),('authorized','true'),('data_sharing',False),('budget_usd','0'),('budget_usd','NaN'),('input_usd_per_million','0'),('output_usd_per_million','inf'),('max_output_tokens',True)]:
            with self.subTest(field=field),self.assertRaises(ValueError):cloud_limits({**LIMITS,field:value})
        with self.assertRaises(ValueError):config_checked({'mentor':{'kind':'openai','model':'fixture'}})
        with self.assertRaises(ValueError):config_checked({'student':{'kind':'anthropic','model':'fixture'}})
        with self.assertRaises(ValueError):config_checked({'mentor':{'kind':'openai','model':'fixture','api_key':'secret'}})

    def test_direct_cloud_generation_cannot_bypass_ledger(self):
        for kind in ('openai','anthropic'):
            p=CloudProvider(kind,'fixture')
            with patch.object(p,'request') as request:
                with self.assertRaises(ProviderError):p.generate('s','p')
                request.assert_not_called()
            with self.assertRaises(ProviderError):p.request('/v1/messages',{'model':'fixture'})

    def test_metadata_discovery_has_no_generation(self):
        for kind in ('openai','anthropic'):
            p=CloudProvider(kind,'fixture')
            with patch.object(p,'request',return_value={'data':[{'id':'fixture'}]}) as request:
                self.assertEqual(p.inspect()['authenticated'],True)
                request.assert_called_once_with('/v1/models')

    def test_anthropic_model_discovery_paginates(self):
        p=CloudProvider('anthropic','fixture')
        with patch.object(p,'request',side_effect=[{'data':[{'id':'a'}],'has_more':True,'last_id':'a/b'},{'data':[{'id':'b'}],'has_more':False}]) as req:
            self.assertEqual(p.models(),['a','b'])
            self.assertEqual(req.call_args.args[0],'/v1/models?after_id=a%2Fb')

    def test_official_https_headers_payload_and_usage(self):
        for kind in ('openai','anthropic'):
            with self.subTest(kind=kind):
                p=CloudProvider(kind,'fixture');p.reservation='fixture-ledger-receipt'
                reply={'status':'completed','output':[{'type':'reasoning'},{'type':'message','content':[{'type':'output_text','text':'{"reason":"ok"}'}]}],
                    'usage':{'input_tokens':11,'output_tokens':7}} if kind=='openai' else {'content':[{'type':'text','text':'{"reason":"ok"}'}],
                    'stop_reason':'end_turn','usage':{'input_tokens':11,'output_tokens':7}}
                class Opener:
                    def open(self_,req,timeout):
                        self.assertEqual(timeout,30);self.assertTrue(req.full_url.startswith('https://api.'+('openai.com' if kind=='openai' else 'anthropic.com')))
                        self.assertIn('Authorization' if kind=='openai' else 'X-api-key',req.headers)
                        body=json.loads(req.data)
                        self.assertEqual(body['max_output_tokens' if kind=='openai' else 'max_tokens'],512)
                        if kind=='openai':self.assertFalse(body['store'])
                        else:self.assertEqual(req.headers['Anthropic-version'],'2023-06-01')
                        return Response(reply)
                with patch('urllib.request.build_opener',return_value=Opener()) as factory:
                    self.assertEqual(json.loads(p.generate('s','p'))['reason'],'ok')
                    with self.assertRaises(ProviderError):factory.call_args.args[1].redirect_request(None,None,None,None,None,None)
                self.assertEqual(p.last_usage,{'input_tokens':11,'output_tokens':7})
                self.assertIsNone(p.reservation)

    def test_cloud_errors_do_not_echo_provider_bodies_or_keys(self):
        p=CloudProvider('openai','fixture')
        for status in (400,401,403,404,429,500):
            class Opener:
                def open(self_,*a,**kw):raise urllib.error.HTTPError('https://api.openai.com/v1/models',status,'private-openai-fixture',{},io.BytesIO(b'private-openai-fixture'))
            with patch('urllib.request.build_opener',return_value=Opener()):
                with self.assertRaises(ProviderError) as error:p.models()
                self.assertNotIn('private-openai-fixture',str(error.exception));self.assertIn(str(status),str(error.exception))

    def test_reservation_reconciliation_and_budget_block_before_call(self):
        rid=self.run_id();limits=cloud_limits(LIMITS)
        receipt=self.store.reserve_cloud(rid,'openai','fixture',limits,100,20)
        self.assertEqual(self.store.billing(rid)['charged_or_reserved_usd'],.0016)
        self.store.settle_cloud(receipt,limits,{'input_tokens':10,'output_tokens':2})
        self.assertEqual(self.store.billing(rid)['charged_or_reserved_usd'],.00016)
        with self.assertRaises(ValueError):self.store.settle_cloud(receipt,limits,{'input_tokens':10,'output_tokens':2})
        rid=self.run_id(cloud={**LIMITS,'budget_usd':'.000001'})
        exp=Experiment(self.store,rid);p=CloudProvider('openai','fixture')
        with patch.object(p,'generate') as generate:
            with self.assertRaises(BudgetExceeded):exp.call(p,'s','p')
            generate.assert_not_called()
        self.assertFalse(self.store.billing(rid)['calls'])

    def test_timeout_keeps_full_reservation_after_reopening_store(self):
        rid=self.run_id();exp=Experiment(self.store,rid);p=CloudProvider('openai','fixture')
        with patch.object(p,'request',side_effect=ProviderError('fixture timeout')):
            with self.assertRaises(ProviderError):exp.call(p,'s','p')
        bill=Store(self.tmp.name).billing(rid)
        self.assertEqual(bill['uncertain_calls'],1)
        self.assertEqual(bill['calls'][0]['reserved_microusd'],bill['calls'][0]['charged_microusd'])
        self.assertTrue((self.store.root/rid/'billing.json').exists())

    def test_token_overrun_latches_cloud_dispatch_closed(self):
        rid=self.run_id();limits=cloud_limits(LIMITS)
        receipt=self.store.reserve_cloud(rid,'openai','fixture',limits,100,20)
        with self.assertRaises(BudgetExceeded):self.store.settle_cloud(receipt,limits,{'input_tokens':101,'output_tokens':1})
        with self.assertRaises(BudgetExceeded):self.store.reserve_cloud(rid,'openai','fixture',limits,1,1)

    def test_missing_usage_and_truncated_output_never_fake_success(self):
        p=CloudProvider('openai','fixture')
        for reply in ({'status':'completed','output':[]},{'status':'incomplete','usage':{'input_tokens':5,'output_tokens':512}}):
            p.reservation='fixture'
            with patch.object(p,'request',return_value=reply):
                with self.assertRaises(ProviderError):p.generate('s','p')

    def test_session_credentials_only_selected_provider_in_child(self):
        register('openai','session-openai-fixture')
        env=worker_environment('openai')
        self.assertEqual(env['OVERMIND_OPENAI_API_KEY'],'session-openai-fixture')
        self.assertNotIn('OPENAI_API_KEY',env);self.assertNotIn('ANTHROPIC_API_KEY',env)
        self.assertNotIn('OVERMIND_OPENAI_API_KEY',os.environ)
        rid=self.run_id();self.store.event(rid,'test','session-openai-fixture private-openai-fixture private-anthropic-fixture')
        self.store.artifact(rid,'redaction.json',{'text':'session-openai-fixture'})
        for path in Path(self.tmp.name).rglob('*'):
            if path.is_file():
                raw=path.read_bytes()
                for key in (b'session-openai-fixture',b'private-openai-fixture',b'private-anthropic-fixture'):self.assertNotIn(key,raw)

    def test_ollama_discovery_and_missing_dependencies(self):
        with patch('shutil.which',return_value=None),patch.object(LocalProvider,'request',side_effect=OSError('not available')):
            info=discover();self.assertFalse(info['installed']);self.assertFalse(info['running']);self.assertIn('https://docs.ollama.com/linux',info['guidance'])
        with patch('shutil.which',return_value='/usr/bin/ollama'),patch.object(LocalProvider,'request',return_value={'models':[{'name':'fixture','digest':'abc','size':1}]}):
            info=discover();self.assertTrue(info['running']);self.assertEqual(info['models'][0]['digest'],'abc')

    def test_retrieval_uses_only_frozen_training_examples(self):
        rows=[{'input':'card refund duplicate','target':'billing'},{'input':'change account name','target':'account'}]
        result=augment(rows,'refund my card',1)
        self.assertIn('card refund duplicate',result);self.assertNotIn('change account name',result)

    def test_both_cloud_mentors_control_actual_pipeline_with_protocol_fixtures(self):
        # Explicit fixtures exercise full parsing, bounded dispatch, ledger, retrieval, and verification.
        # Constant student outputs deliberately produce no improvement or promotion.
        for kind in ('openai','anthropic'):
            rid=self.run_id(kind);prompts=[];count=[0]
            def cloud_request(p,route,body=None):
                if body is None:return {'data':[{'id':'mentor-fixture'}]}
                prompts.append(body['input'] if kind=='openai' else body['messages'][0]['content'])
                count[0]+=1
                plan={'technique':'prompt_optimization' if count[0]==1 else 'retrieval_augmentation','system_prompt':'Return an exact support label.','retrieval_k':2,
                      'reason':'Fixture decision based on prior validation outcomes.'}
                text=json.dumps(plan);usage={'input_tokens':120,'output_tokens':80}
                return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':text}]}],'usage':usage} if kind=='openai' else {'stop_reason':'end_turn','content':[{'type':'text','text':text}],'usage':usage}
            with patch.object(CloudProvider,'request',cloud_request),patch.object(LocalProvider,'inspect',return_value={'architecture':'fixture'}),patch.object(LocalProvider,'generate',return_value='account'):
                Experiment(self.store,rid).run()
            self.assertEqual(self.store.get(rid)['status'],'completed')
            self.assertEqual(self.store.read(rid,'candidate-2.json')['technique'],'retrieval_augmentation')
            self.assertEqual(self.store.read(rid,'candidate-2.json')['retrieval_rows'],small_data()['train'])
            self.assertFalse(self.store.read(rid,'report.json')['promoted'])
            bill=self.store.billing(rid);self.assertEqual(len(bill['calls']),2)
            self.assertEqual(bill['input_tokens'],240);self.assertEqual(bill['output_tokens'],160)
            for row in small_data()['test']:self.assertNotIn(row['input'],''.join(prompts))
            second=json.loads(prompts[1]);self.assertEqual(second['previous_candidates'][0]['accuracy'],.25)
            self.assertEqual(second['previous_experiments'],[])
            self.assertEqual(self.store.read(rid,'candidate.json')['technique'],'prompt_optimization')

    def test_schema_migration_preserves_existing_run_rows(self):
        root=Path(self.tmp.name)/'legacy';root.mkdir()
        with sqlite3.connect(root/'lab.sqlite3') as c:
            c.execute('CREATE TABLE runs(id TEXT PRIMARY KEY, created REAL, updated REAL, status TEXT, config TEXT, state TEXT)')
            c.execute('CREATE TABLE events(seq INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, time REAL, kind TEXT, message TEXT)')
            c.execute('INSERT INTO runs VALUES(?,?,?,?,?,?)',('legacy',1,1,'completed',json.dumps(DEFAULTS),json.dumps({'phase':'done'})))
        store=Store(root)
        self.assertEqual(store.get('legacy')['status'],'completed');self.assertEqual(store.billing('legacy')['calls'],[])


    def test_manual_prompt_inference_is_local_only_and_explicit(self):
        from overmind.inference import predict_artifact
        artifact={'format':'overmind.prompt.v1','provider':{'kind':'ollama','url':'http://127.0.0.1:11434','model':'fixture'},
                  'system_prompt':'Classify.','technique':'retrieval_augmentation','retrieval_rows':small_data()['train'],'retrieval_k':2}
        with self.assertRaises(ValueError):predict_artifact(artifact,'request')
        with patch.object(LocalProvider,'generate',return_value='billing') as gen:
            self.assertEqual(predict_artifact(artifact,'request',True),'billing')
            self.assertIn('Reference labeled examples',gen.call_args.args[1])
        artifact['provider']={'kind':'openai','url':'https://api.openai.com','model':'fixture'}
        with self.assertRaises(ValueError):predict_artifact(artifact,'request',True)

    def test_digest_change_aborts_final_comparison(self):
        rid=self.run_id();exp=Experiment(self.store,rid)
        exp.s['student_info']={'identity':{'digest':'original'}}
        with patch.object(LocalProvider,'inspect',return_value={'identity':{'digest':'changed'}}):
            with self.assertRaisesRegex(ValueError,'digest changed'):exp.check_student_identity()
        self.assertFalse((self.store.root/rid/'promoted.json').exists())

    def test_large_validation_context_is_bounded(self):
        rid=self.run_id();exp=Experiment(self.store,rid)
        rows=[{'input':'x'*4000,'target':'account','prediction':'y'*16000,'correct':False} for _ in range(5000)]
        result=exp.validation_summary({'accuracy':0,'count':5000,'results':rows})
        self.assertEqual(len(result['sample_failures']),6)
        self.assertLess(len(json.dumps(result)),6000)

    def test_reserved_cost_survives_interruption_and_blocks_new_dispatch(self):
        rid=self.run_id(cloud={**LIMITS,'budget_usd':'.0016'})
        limits=cloud_limits({**LIMITS,'budget_usd':'.0016'})
        self.store.reserve_cloud(rid,'openai','fixture',limits,100,20)
        recovered=Store(self.tmp.name)
        with self.assertRaises(BudgetExceeded):recovered.reserve_cloud(rid,'openai','fixture',limits,1,1)
        self.assertEqual(recovered.billing(rid)['uncertain_calls'],1)

if __name__=='__main__':unittest.main()
