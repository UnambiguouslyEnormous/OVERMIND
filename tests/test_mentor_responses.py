"""Mentor-response regressions. Every cloud response is mocked; never spends credits."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from overmind.cloud import CloudProvider, ProviderError, BudgetExceeded, TruncatedResponse
from overmind.lab import Experiment, Halt, Limit, config_checked
from overmind.mentor import parse_proposal, proposal_schema, ProposalError
from overmind.providers import LocalProvider, inspection_summary
from overmind.store import Store
from test_phase2 import LIMITS, small_data

PLAN={'technique':'retrieval_augmentation','system_prompt':'Classify the request using exactly one allowed label.',
      'retrieval_k':2,'reason':'Use licensed examples to address baseline classification mistakes.'}


def cloud_reply(text,kind='openai',truncated=False):
    usage={'input_tokens':100,'output_tokens':50}
    if kind=='openai':
        return {'status':'incomplete' if truncated else 'completed',
            'incomplete_details':{'reason':'max_output_tokens'} if truncated else None,
            'usage':usage,'output':[{'type':'message','content':[{'type':'output_text','text':text}]}]}
    return {'stop_reason':'max_tokens' if truncated else 'end_turn','usage':usage,'content':[{'type':'text','text':text}]}

class ProposalValidationTests(unittest.TestCase):
    def test_exact_live_failure_shape_is_normalized_without_inventing_fields(self):
        # Original run returned experiment.{name,technique,description,system_prompt,retrieval_k,reason}.
        wrapped={'experiment':{'name':'Fixture experiment','description':'Fixture description',**PLAN}}
        with self.assertRaisesRegex(ValueError,'system_prompt'):
            # Reproduce the old top-level-only test, before asserting its replacement.
            if not isinstance(wrapped.get('system_prompt'),str):
                raise ValueError('Mentor must return a system_prompt of 1–3000 characters.')
        plan,normalized=parse_proposal(json.dumps(wrapped))
        self.assertEqual(plan,PLAN);self.assertTrue(normalized)
        self.assertNotIn('name',plan);self.assertNotIn('description',plan)

    def test_flat_fenced_and_linear_proposals_remain_compatible(self):
        self.assertEqual(parse_proposal(json.dumps(PLAN)),(PLAN,False))
        self.assertEqual(parse_proposal('```json\n'+json.dumps(PLAN)+'\n```')[0],PLAN)
        self.assertEqual(parse_proposal('{"system_prompt":"Classify.","reason":"Use validation."}')[0]['technique'],'prompt_optimization')
        self.assertEqual(parse_proposal('{"learning_rate":0.3,"reason":"Train."}',True)[0]['learning_rate'],.3)

    def test_missing_empty_oversized_wrong_type_and_unsupported_proposals(self):
        for change,category in [({'system_prompt':None},'invalid_type'),({'system_prompt':''},'empty_prompt'),
                ({'system_prompt':'  \n '},'empty_prompt'),({'system_prompt':'x'*3001},'oversized_prompt'),
                ({'technique':'execute_shell'},'unsupported_strategy'),({'technique':[]},'invalid_type'),
                ({'retrieval_k':True},'invalid_type'),({'retrieval_k':5},'invalid_range'),
                ({'reason':[]},'invalid_type'),({'reason':''},'invalid_reason')]:
            with self.subTest(change=list(change),category=category):
                with self.assertRaises(ProposalError) as error:parse_proposal(json.dumps({**PLAN,**change}))
                self.assertEqual(error.exception.category,category)
        plan=dict(PLAN);del plan['system_prompt']
        with self.assertRaises(ProposalError) as error:parse_proposal(json.dumps(plan))
        self.assertEqual(error.exception.category,'missing_field');self.assertIn('system_prompt',str(error.exception))
        self.assertEqual(len(parse_proposal(json.dumps({**PLAN,'system_prompt':'x'*3000}))[0]['system_prompt']),3000)

    def test_malformed_ambiguous_and_invalid_json_are_distinct(self):
        cases=[('{"system_prompt":','malformed_json'),('[]','invalid_type'),
               ('{"experiment":[]}','invalid_type'),('{"reason":"a","reason":"b"}','ambiguous_structure'),
               (json.dumps({**PLAN,'experiment':PLAN}),'ambiguous_structure'),
               ('{"learning_rate":NaN,"reason":"bad"}','invalid_type')]
        for reply,category in cases:
            with self.subTest(category=category),self.assertRaises(ProposalError) as error:parse_proposal(reply)
            self.assertEqual(error.exception.category,category)

    def test_schemas_define_required_fields_and_closed_strategy_set(self):
        for linear in (False,True):
            schema=proposal_schema(linear)
            self.assertFalse(schema['additionalProperties'])
            self.assertEqual(set(schema['required']),set(schema['properties']))
        self.assertIn('system_prompt',proposal_schema()['required'])
        self.assertEqual(proposal_schema()['properties']['technique']['enum'],['prompt_optimization','retrieval_augmentation'])

class ProposalRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=Store(self.temp.name)

    def experiment(self,kind='openai',**overrides):
        c=config_checked({'mentor':{'kind':kind,'model':'mentor-fixture'},'student':{'kind':'ollama','url':'http://127.0.0.1:11434','model':'student-fixture'},'attempts':1,'cloud':LIMITS,**overrides})
        rid=self.store.create(c,small_data());exp=Experiment(self.store,rid)
        exp.s['hardware']={};return exp

    def mocked(self,replies,kind='openai',callback=None):
        responses=iter(replies);seen=[]
        def request(p,route,body=None):
            if body is None:return {'data':[{'id':'mentor-fixture'}]}
            seen.append(body)
            reply=next(responses)
            if isinstance(reply,Exception):raise reply
            if callback:callback(len(seen))
            return reply
        return patch.object(CloudProvider,'request',request),seen

    def test_successful_retry_for_both_providers_uses_same_cap_and_paid_ledger(self):
        for kind in ('openai','anthropic'):
            exp=self.experiment(kind)
            mock,seen=self.mocked([cloud_reply(json.dumps({k:v for k,v in PLAN.items() if k!='system_prompt'}),kind),cloud_reply(json.dumps(PLAN),kind)])
            with mock:plan=exp.mentor_plan()
            self.assertEqual(plan,PLAN);self.assertEqual(len(seen),2)
            for body in seen:
                if kind=='openai':
                    self.assertTrue(body['text']['format']['strict']);schema=body['text']['format']['schema']
                else:schema=body['output_config']['format']['schema']
                self.assertEqual(schema,proposal_schema())
                self.assertEqual(body.get('max_output_tokens',body.get('max_tokens')),2048)
            context=json.loads(seen[1]['input'] if kind=='openai' else seen[1]['messages'][0]['content'])
            self.assertEqual(context['response_correction']['category'],'missing_field')
            self.assertIn('system_prompt',context['response_correction']['instruction'])
            bill=self.store.billing(exp.rid);self.assertEqual(len(bill['calls']),2)
            self.assertEqual(bill['input_tokens'],200);self.assertEqual(bill['output_tokens'],100)
            self.assertEqual(exp.s['calls'],2)
            events=self.store.events(exp.rid);self.assertEqual(sum(x['kind']=='mentor_retry' for x in events),1)
            self.assertEqual(self.store.read(exp.rid,'mentor-0-response-2.json')['category'],'valid')

    def test_truncation_is_classified_retried_and_accounted_for_both_providers(self):
        for kind in ('openai','anthropic'):
            exp=self.experiment(kind)
            mock,_=self.mocked([cloud_reply('{',kind,True),cloud_reply(json.dumps(PLAN),kind)])
            with mock:self.assertEqual(exp.mentor_plan(),PLAN)
            self.assertEqual(self.store.read(exp.rid,'mentor-0-response-1.json')['category'],'truncated_response')
            self.assertEqual(self.store.billing(exp.rid)['input_tokens'],200)
            self.assertEqual(self.store.billing(exp.rid)['calls'][0]['status'],'error_usage')

    def test_provider_error_is_not_retried_and_reservation_is_preserved(self):
        exp=self.experiment();mock,seen=self.mocked([ProviderError('Mock HTTP 401 authentication failure.')])
        with mock,self.assertRaises(ProviderError):exp.mentor_plan()
        self.assertEqual(len(seen),1);self.assertEqual(self.store.billing(exp.rid)['uncertain_calls'],1)
        self.assertEqual(self.store.read(exp.rid,'mentor-0-response-1.json')['category'],'provider_api_error')

    def test_retries_exhaust_at_three_dispatches_including_after_recovery(self):
        exp=self.experiment();mock,seen=self.mocked([cloud_reply('{}')]*3)
        with mock,self.assertRaises(ProposalError) as error:exp.mentor_plan()
        self.assertEqual(error.exception.category,'retry_exhausted')
        self.assertEqual(len(seen),3);self.assertEqual(exp.s['calls'],3)
        self.assertEqual(len(self.store.billing(exp.rid)['calls']),3)
        recovered=Experiment(self.store,exp.rid)
        with patch.object(CloudProvider,'request') as req,self.assertRaises(ProposalError):recovered.mentor_plan()
        req.assert_not_called()

    def test_call_budget_prevents_correction_dispatch(self):
        exp=self.experiment(max_calls=1);mock,seen=self.mocked([cloud_reply('{}')])
        with mock,self.assertRaises(Limit):exp.mentor_plan()
        self.assertEqual(len(seen),1);self.assertEqual(exp.s['calls'],1)

    def test_spending_budget_prevents_corrective_request(self):
        exp=self.experiment(cloud={**LIMITS,'budget_usd':'.20'})
        # Long prompt makes a second conservative reservation exceed the remaining grant.
        exp.c['objective']='x'*2000
        reply=cloud_reply('{}');reply['usage']={'input_tokens':5000,'output_tokens':1000}
        mock,seen=self.mocked([reply])
        with mock,self.assertRaises(BudgetExceeded):exp.mentor_plan()
        self.assertEqual(len(seen),1)
        self.assertEqual(len(self.store.billing(exp.rid)['calls']),1)

    def test_cancellation_between_invalid_response_and_retry(self):
        exp=self.experiment();mock,seen=self.mocked([cloud_reply('{}')])
        original=exp.proposal_diagnostic
        def diagnostic(*args,**kwargs):
            original(*args,**kwargs);self.store.update(exp.rid,status='stopped')
        with mock,patch.object(exp,'proposal_diagnostic',diagnostic),self.assertRaises(Halt):exp.mentor_plan()
        self.assertEqual(len(seen),1);self.assertEqual(len(self.store.billing(exp.rid)['calls']),1)

    def test_diagnostics_never_echo_user_text_or_raw_mentor_output(self):
        exp=self.experiment();secret_text='private customer contact details'
        invalid=json.dumps({'reason':secret_text,'system_prompt':[]})
        mock,_=self.mocked([cloud_reply(invalid),cloud_reply(json.dumps(PLAN))])
        with mock:exp.mentor_plan()
        diagnostics=''.join(f.read_text() for f in (self.store.root/exp.rid).glob('mentor-*-response-*.json'))
        events=''.join(e['message'] for e in self.store.events(exp.rid))
        self.assertNotIn(secret_text,diagnostics+events)
        self.assertNotIn(PLAN['system_prompt'],diagnostics+events)
        d=self.store.read(exp.rid,'mentor-0-response-1.json')
        for field in ('provider','model','outcome','category','corrective_retry','usage','charged_or_reserved_usd'):self.assertIn(field,d)

    def test_wrapped_proposal_reaches_candidate_evaluation_end_to_end(self):
        exp=self.experiment();mock,_=self.mocked([cloud_reply(json.dumps({'experiment':{'name':'Fixture','description':'Fixture',**PLAN}}))])
        with mock,patch.object(LocalProvider,'inspect',return_value={'architecture':'fixture'}),patch.object(LocalProvider,'generate',return_value='account'):
            exp.run()
        self.assertEqual(self.store.get(exp.rid)['status'],'completed')
        self.assertEqual(self.store.read(exp.rid,'candidate.json')['system_prompt'],PLAN['system_prompt'])
        self.assertEqual(self.store.read(exp.rid,'latest-validation.json')['count'],8)
        self.assertFalse(self.store.read(exp.rid,'report.json')['promoted'])
        self.assertTrue(self.store.read(exp.rid,'mentor-0-response-1.json')['normalized_experiment_wrapper'])

    def test_worker_exhaustion_fails_gracefully_preserving_baseline(self):
        exp=self.experiment()
        script='''
import sys
from unittest.mock import patch
sys.path.insert(0,'tests')
from test_mentor_responses import cloud_reply
from overmind.cloud import CloudProvider
from overmind.providers import LocalProvider
from overmind.lab import worker

def request(p,route,body=None):
    return {'data':[{'id':'mentor-fixture'}]} if body is None else cloud_reply('{}')
with patch.object(CloudProvider,'request',request),patch.object(LocalProvider,'inspect',return_value={'architecture':'fixture'}),patch.object(LocalProvider,'generate',return_value='account'):
    sys.exit(worker(sys.argv[1],sys.argv[2]))
'''
        result=subprocess.run([sys.executable,'-c',script,str(self.store.root),exp.rid],capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,1,result.stderr)
        self.assertEqual(self.store.get(exp.rid)['status'],'failed')
        self.assertEqual(self.store.read(exp.rid,'baseline-validation.json')['count'],8)
        self.assertFalse((self.store.root/exp.rid/'candidate.json').exists())
        self.assertEqual(len(self.store.billing(exp.rid)['calls']),3)
        self.assertTrue((self.store.root/exp.rid/'mentor-0-response-3.json').exists())


    def test_cloud_required_fields_are_not_silently_defaulted(self):
        for key in proposal_schema()['required']:
            plan=dict(PLAN);del plan[key]
            with self.subTest(field=key),self.assertRaises(ProposalError) as error:
                parse_proposal(json.dumps(plan),require_all=True)
            self.assertEqual(error.exception.category,'missing_field')

    def test_empty_response_can_be_corrected(self):
        exp=self.experiment();mock,seen=self.mocked([cloud_reply(''),cloud_reply(json.dumps(PLAN))])
        with mock:self.assertEqual(exp.mentor_plan(),PLAN)
        self.assertEqual(len(seen),2)
        self.assertEqual(self.store.read(exp.rid,'mentor-0-response-1.json')['category'],'empty_response')

    def test_second_corrective_retry_succeeds_at_ceiling(self):
        exp=self.experiment();mock,seen=self.mocked([cloud_reply('{'),cloud_reply('{}'),cloud_reply(json.dumps(PLAN))])
        with mock:self.assertEqual(exp.mentor_plan(),PLAN)
        self.assertEqual(len(seen),3)
        self.assertEqual(self.store.read(exp.rid,'mentor-0-response-3.json')['outcome'],'accepted')

    def test_inspection_summary_excludes_license_dump(self):
        metadata={'details':{'parameter_size':'1.5B','quantization_level':'Q4_K_M'},
            'model_info':{'qwen2.context_length':32768},'identity':{'size':1024**3},'license':'APACHE LICENSE\n'+'secret license prose'*5000}
        summary=inspection_summary({'kind':'ollama','model':'qwen2.5:1.5b'},metadata)
        for text in ('qwen2.5:1.5b','1.5B','Q4_K_M','32768','connected'):self.assertIn(text,summary)
        self.assertNotIn('APACHE',summary);self.assertLess(len(summary),350)

if __name__=='__main__':unittest.main()
