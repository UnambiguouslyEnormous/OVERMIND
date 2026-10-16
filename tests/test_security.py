"""Credential hardening regressions. Synthetic values only; all network use is mocked."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import resource
import sqlite3
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch, Mock

from overmind import security
from overmind.__main__ import main
from overmind.data import benchmark
from overmind.lab import DEFAULTS, Manager
from overmind.store import Store

ROOT=Path(__file__).resolve().parents[1]

def fake_key(letter='A'):return 'sk-proj-'+letter*48

class SecurityTests(unittest.TestCase):
    def setUp(self):
        for name,value in [('_session',{}),('_redaction_keys',set()),('_blocked',set())]:
            p=patch.object(security,name,value);p.start();self.addCleanup(p.stop)
        env=patch.dict(os.environ,{'PATH':os.environ.get('PATH','/usr/bin:/bin')},clear=True);env.start();self.addCleanup(env.stop)
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)

    def test_replaced_cleared_and_rotated_environment_keys_stay_redacted(self):
        first,second=fake_key('A'),fake_key('B')
        security.register('openai',first);security.register('openai',second);security.clear_credentials('openai')
        self.assertNotIn(first,security.redact(first+second));self.assertNotIn(second,security.redact(first+second))
        os.environ['ANTHROPIC_API_KEY']='fixture-environment-original'
        self.assertEqual(security.credential('anthropic'),'fixture-environment-original')
        os.environ['ANTHROPIC_API_KEY']='fixture-environment-replacement'
        result=security.redact('fixture-environment-original fixture-environment-replacement')
        self.assertNotIn('fixture-environment-original',result);self.assertNotIn('fixture-environment-replacement',result)

    def test_clear_disables_fallback_without_changing_user_environment(self):
        os.environ['OPENAI_API_KEY']='fixture-external-key'
        security.register('openai','fixture-session-key');security.clear_credentials()
        self.assertEqual(os.environ['OPENAI_API_KEY'],'fixture-external-key')
        with self.assertRaisesRegex(ValueError,'cleared'):security.credential('openai')
        security.register('openai','fixture-new-session')
        self.assertEqual(security.credential('openai'),'fixture-new-session')

    def test_arbitrary_retired_session_values_not_only_provider_patterns(self):
        security.register('openai','fixture-old-unusual-key');security.register('openai','fixture-new-unusual-key')
        self.assertEqual(security.redact('fixture-old-unusual-key'),'[REDACTED]')

    def test_unknown_provider_and_bearer_tokens_are_redacted(self):
        self.assertNotIn(fake_key(),security.redact('unexpected '+fake_key()))
        self.assertEqual(security.redact('Bearer fixture-unregistered-token'),'Bearer [REDACTED]')
        self.assertEqual(security.redact({'API-Key':'unknown','nested':[{'client_secret':'unknown'}]}),{'API-Key':'[REDACTED]','nested':[{'client_secret':'[REDACTED]'}]})

    def test_recursive_field_rejection_in_dicts_lists_and_tuples(self):
        for value in ({'api_key':'fixture'},{'nested':[{'client-secret':'fixture'}]},({'nested':({'OPENAI_API_KEY':'fixture'},)},)):
            with self.subTest(kind=type(value).__name__),self.assertRaises(ValueError):security.reject_secrets(value)
        security.reject_secrets({'input_tokens':12,'rows':[{'input':'reset my password','target':'account'}]})

    def test_cli_output_and_exception_redaction(self):
        for error in (False,True):
            key='fixture-CLI-canary-key';security.register('openai',key)
            out,err=io.StringIO(),io.StringIO()
            kwargs={'side_effect':ValueError(key)} if error else {'return_value':key}
            with patch.object(sys,'argv',['overmind','predict','unused.json','input']),patch('pathlib.Path.stat',return_value=SimpleNamespace(st_size=2)),patch('pathlib.Path.read_text',return_value='{}'),patch('overmind.inference.predict_artifact',**kwargs),patch('overmind.__main__.harden_process'),contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):
                main()
            self.assertNotIn(key,out.getvalue()+err.getvalue());self.assertIn('[REDACTED]',out.getvalue()+err.getvalue())

    def test_cli_unexpected_exception_no_raw_traceback(self):
        key='fixture-unexpected-error';security.register('openai',key)
        out=io.StringIO()
        with patch.object(sys,'argv',['overmind','hardware']),patch('overmind.__main__.inspect',side_effect=TypeError(key)),patch('overmind.__main__.harden_process'),contextlib.redirect_stderr(out):
            self.assertEqual(main(),1)
        self.assertNotIn(key,out.getvalue());self.assertNotIn('Traceback',out.getvalue())

    def test_output_stream_redacts_split_writes_and_flushes_partial_line(self):
        key='fixture-split-secret';security.register('openai',key)
        result=io.StringIO()
        with contextlib.redirect_stdout(result),security.redacted_output():
            sys.stdout.write(key[:9]);sys.stdout.write(key[9:]+'\n');sys.stdout.write(key)
        self.assertNotIn(key,result.getvalue());self.assertEqual(result.getvalue(),'[REDACTED]\n[REDACTED]')

    def test_worker_and_auxiliary_environments_are_allowlisted(self):
        os.environ.update({'HOME':self.tmp.name,'LANG':'C.UTF-8','AWS_SECRET_ACCESS_KEY':'fixture-aws',
            'DATABASE_PASSWORD':'fixture-db','OPENAI_API_KEY':'fixture-openai','ANTHROPIC_API_KEY':'fixture-anthropic',
            'UNRELATED_KEY':'fixture-other','LD_PRELOAD':'fixture-injection','PYTHONPATH':'fixture-injection'})
        env=security.worker_environment('openai')
        self.assertEqual(env['OVERMIND_OPENAI_API_KEY'],'fixture-openai')
        self.assertEqual(env['HOME'],self.tmp.name)
        for name in ('AWS_SECRET_ACCESS_KEY','DATABASE_PASSWORD','OPENAI_API_KEY','ANTHROPIC_API_KEY','UNRELATED_KEY','LD_PRELOAD','PYTHONPATH'):self.assertNotIn(name,env)
        self.assertFalse(any('KEY' in name or 'PASSWORD' in name for name in security.subprocess_environment()))
        self.assertFalse(any('KEY' in name for name in security.worker_environment('controller')))
        self.assertEqual(security.worker_environment('anthropic')['OVERMIND_ANTHROPIC_API_KEY'],'fixture-anthropic')

    def test_hardware_subprocess_never_receives_cloud_keys(self):
        from overmind.hardware import inspect
        os.environ['OVERMIND_OPENAI_API_KEY']='fixture-worker-key'
        with patch('overmind.hardware.subprocess.run',return_value=SimpleNamespace(returncode=1)) as run:inspect()
        self.assertNotIn('OVERMIND_OPENAI_API_KEY',run.call_args.kwargs['env'])

    def test_process_disables_core_dumps_and_linux_dumpability(self):
        code='from overmind.security import harden_process;import resource,ctypes,os;harden_process();assert resource.getrlimit(resource.RLIMIT_CORE)==(0,0);assert ctypes.CDLL(None).prctl(3,0,0,0,0)==0;assert os.umask(0o077)==0o077'
        result=subprocess.run([sys.executable,'-B','-c',code],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,'Process hardening subprocess failed (output withheld).')

    def test_private_files_with_permissive_umask_and_existing_data(self):
        root=Path(self.tmp.name)/'custom-lab';root.mkdir(mode=0o755)
        old=root/'legacy';old.mkdir(mode=0o755)
        evidence=old/'baseline.json';evidence.write_text('{"evidence":true}');evidence.chmod(0o664)
        before=evidence.read_bytes();previous=os.umask(0)
        try:
            store=Store(root);rid=store.create(DEFAULTS,benchmark());store.artifact(rid,'sample.json',{'value':'safe'})
        finally:os.umask(previous)
        self.assertEqual(evidence.read_bytes(),before)
        for path in [root,*root.rglob('*')]:
            self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o700 if path.is_dir() else 0o600,str(path.relative_to(root)))
        self.assertIn('*\n',(root/'.gitignore').read_text())

    def test_permission_migration_preserves_database_run_and_artifact(self):
        store=Store(Path(self.tmp.name)/'lab');rid=store.create(DEFAULTS,benchmark())
        store.update(rid,status='failed',state={'phase':'improve','calls':25})
        path=store.root/rid/'baseline.json';store.artifact(rid,'baseline.json',{'score':.792});before=path.read_bytes()
        path.chmod(0o644);store.root.chmod(0o755)
        reopened=Store(store.root)
        self.assertEqual(reopened.get(rid)['state'],{'phase':'improve','calls':25})
        self.assertEqual(reopened.get(rid)['status'],'failed');self.assertEqual(path.read_bytes(),before)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o600)

    def test_artifacts_dataset_and_state_reject_nested_credential_fields(self):
        store=Store(self.tmp.name);rid=store.create(DEFAULTS,benchmark())
        with self.assertRaises(ValueError):store.artifact(rid,'unsafe.json',{'nested':[{'api_key':'fixture'}]})
        self.assertFalse((store.root/rid/'unsafe.json').exists())
        with self.assertRaises(ValueError):store.update(rid,state={'nested':[{'API_KEY':'fixture'}]})
        data=benchmark();data['extra']=[{'credentials':{'api_key':'fixture'}}]
        with self.assertRaises(ValueError):store.create(DEFAULTS,data)

    def test_known_credentials_redacted_across_persistence_boundaries(self):
        key='fixture-storage-canary';security.register('openai',key)
        store=Store(self.tmp.name);rid=store.create({**DEFAULTS,'objective':key},benchmark())
        store.event(rid,key,key);store.update(rid,state={'note':key});store.artifact(rid,'safe.json',{'text':key})
        limits={'budget_usd':'1','input_usd_per_million':'1','output_usd_per_million':'1'}
        store.reserve_cloud(rid,'openai',key,limits,1,1)
        for path in store.root.rglob('*'):
            if path.is_file():self.assertNotIn(key.encode(),path.read_bytes())

    def test_symlinks_and_source_data_roots_are_rejected(self):
        root=Path(self.tmp.name)/'lab';root.mkdir();outside=Path(self.tmp.name)/'outside';outside.write_text('unchanged');outside.chmod(0o644)
        (root/'link').symlink_to(outside)
        with self.assertRaises(ValueError):Store(root)
        self.assertEqual(stat.S_IMODE(outside.stat().st_mode),0o644);self.assertEqual(outside.read_text(),'unchanged')
        with self.assertRaises(ValueError):Store(ROOT)

    def test_artifact_path_traversal_is_rejected(self):
        store=Store(self.tmp.name)
        for rid,name in [('..','unsafe.json'),('ok','../unsafe.json')]:
            with self.assertRaises(ValueError):store.artifact(rid,name,{})


    def test_clear_session_ui_stops_worker_and_removes_key_entry(self):
        from overmind.desktop import Desktop
        security.register('openai','fixture-ui-key')
        view=SimpleNamespace(manager=SimpleNamespace(stop=Mock()),api_key=SimpleNamespace(set_text=Mock()),
            invalidate_cloud_authorization=Mock(),role_widgets={'mentor':[None,None,None,SimpleNamespace(set_text=Mock())]})
        Desktop.clear_session_keys(view)
        view.manager.stop.assert_called_once();view.api_key.set_text.assert_called_once_with('')
        view.invalidate_cloud_authorization.assert_called_once()
        with self.assertRaises(ValueError):security.credential('openai')

    def test_lock_file_is_private_even_without_main_entrypoint(self):
        previous=os.umask(0)
        try:
            store=Store(self.tmp.name)
            with store.lock():pass
        finally:os.umask(previous)
        self.assertEqual(stat.S_IMODE((store.root/'worker.lock').stat().st_mode),0o600)

class GitSecretCheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.git('init','-q')

    def git(self,*args,env=None):
        return subprocess.run(['git',*args],cwd=self.root,capture_output=True,check=True,env=env).stdout

    def stage(self,name,content):
        path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content)
        self.git('add','-f','--',name)

    def scan(self,*args,env=None):
        settings={**os.environ,'PYTHONPATH':str(ROOT),**(env or {})}
        return subprocess.run([sys.executable,'-B','-m','overmind.secret_scan',*args],cwd=self.root,capture_output=True,text=True,env=settings)

    def test_realistic_fake_secret_blocks_without_echoing_value(self):
        key=fake_key();self.stage('settings.py','api_key = '+repr(key))
        result=self.scan('--staged')
        self.assertEqual(result.returncode,1);self.assertIn('settings.py',result.stdout)
        self.assertNotIn(key,result.stdout+result.stderr)

    def test_staged_snapshot_not_clean_working_file_is_scanned(self):
        self.stage('settings.py','x='+repr(fake_key()))
        (self.root/'settings.py').write_text('x="safe"')
        self.assertEqual(self.scan('--staged').returncode,1)

    def test_unstaged_secret_is_not_misrepresented_as_committed(self):
        self.stage('settings.py','x="safe"');(self.root/'settings.py').write_text('x='+repr(fake_key()))
        self.assertEqual(self.scan('--staged').returncode,0)

    def test_force_added_private_file_is_blocked_even_without_key_pattern(self):
        self.stage('.env.local','setting=private')
        result=self.scan('--staged');self.assertEqual(result.returncode,1);self.assertNotIn('setting=private',result.stdout)

    def test_private_key_and_unknown_credential_assignment(self):
        self.stage('sample.txt','-----BEGIN '+'PRIVATE KEY-----\nfixture')
        self.assertEqual(self.scan('--tracked').returncode,1)
        self.stage('sample.txt','api_key = "'+'Z'*40+'"')
        result=self.scan('--tracked');self.assertEqual(result.returncode,1);self.assertNotIn('Z'*40,result.stdout)

    def test_examples_and_source_remain_visible_and_pass_scan(self):
        (self.root/'.gitignore').write_bytes((ROOT/'.gitignore').read_bytes())
        for name in ('examples/cloud-mentor.json','.env.example','credentials.example.json','overmind/security.py','overmind/credentials.py','overmind/secrets.py'):
            self.stage(name,'{}' if name.endswith('.json') else '# safe example\n')
            result=subprocess.run(['git','check-ignore','--no-index','-q',name],cwd=self.root)
            self.assertEqual(result.returncode,1,name)
        self.assertEqual(self.scan('--tracked').returncode,0)

    def test_ignore_rules_cover_secret_config_logs_and_known_lab_files(self):
        (self.root/'.gitignore').write_bytes((ROOT/'.gitignore').read_bytes())
        for name in ('.env','.env.local','config.json','config.local.json','credentials.json','secrets.json','error.log','x.tmp','other/lab.sqlite3','other/worker.lock','.aws/credentials','.codex/auth.json'):
            result=subprocess.run(['git','check-ignore','--no-index','-q',name],cwd=self.root)
            self.assertEqual(result.returncode,0,name)

    def test_alternate_lab_marker_protects_all_artifacts_and_force_add_is_blocked(self):
        store=Store(self.root/'arbitrary-custom-directory');rid=store.create(DEFAULTS,benchmark())
        name=str((store.root/rid/'dataset.json').relative_to(self.root))
        result=subprocess.run(['git','check-ignore','--no-index','-q',name],cwd=self.root)
        self.assertEqual(result.returncode,0)
        self.git('add','-f','--',name)
        self.assertEqual(self.scan('--staged').returncode,1)

    def test_alternate_git_index_is_respected(self):
        self.stage('safe.py','# safe\n')
        alternate=self.root/'alternate-index'
        alternate.write_bytes((self.root/'.git/index').read_bytes())
        self.stage('bad.py','x='+repr(fake_key()))
        self.assertEqual(self.scan('--staged').returncode,1)
        self.assertEqual(self.scan('--staged',env={'GIT_INDEX_FILE':str(alternate)}).returncode,0)

    def test_not_a_git_repository_fails_closed(self):
        elsewhere=Path(self.tmp.name)/'not-repo';elsewhere.mkdir()
        from overmind import secret_scan
        with patch.object(secret_scan,'git',side_effect=ValueError('fixture')):
            out=io.StringIO()
            with contextlib.redirect_stderr(out):self.assertEqual(secret_scan.main(['--staged']),2)
        self.assertNotIn('fixture',out.getvalue())

if __name__=='__main__':unittest.main()
