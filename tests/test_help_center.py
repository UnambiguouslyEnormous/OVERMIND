"""Deterministic guide/context/preferences checks. Status records below are fixtures, not training."""
import json
from pathlib import Path
import tempfile
import unittest
from overmind.help_content import TOPICS, SHORT_HELP
from overmind.help_guide import (ARTICLES, SHORT_ROUTES, TUTORIALS, STEPS, Context,
                                 article_key, search, reaction, verified_report)
from overmind.help_preferences import Preferences, Navigation, checked


class GuideTests(unittest.TestCase):
    def test_all_contextual_topics_and_shortcuts_have_real_articles(self):
        self.assertTrue(set(TOPICS)<=set(ARTICLES))
        self.assertEqual(set(SHORT_HELP),set(SHORT_ROUTES))
        for key in TOPICS.keys()|SHORT_HELP.keys():self.assertIn(article_key(key),ARTICLES)
        for _,steps in TUTORIALS.values():
            for key in steps:
                step=STEPS[key];self.assertIn(step.topic,ARTICLES);self.assertTrue(step.target);self.assertIn(step.page,range(7))

    def test_search_is_offline_case_insensitive_and_uses_shared_content(self):
        self.assertIn('lora.rank',[a.key for a in search('LORA rank')])
        self.assertIn('guide.local-llm',[a.key for a in search('1080')])
        self.assertEqual(search('no-such-zoological-model'),[])
        self.assertEqual(ARTICLES['lora.rank'].paragraphs,TOPICS['lora.rank'].paragraphs)

    def test_context_priority_and_stale_context(self):
        c=Context();c.location(0,'run-a');c.status='laboratory';c.focus('lora.learning_rate')
        self.assertEqual(c.resolve(),'lora.learning_rate')
        self.assertEqual(c.resolve('lora.rank'),'lora.rank')
        c.location(0,'run-a');self.assertEqual(c.resolve(),'lora.learning_rate')
        c.location(3,'run-a');self.assertIsNone(c.field);self.assertEqual(c.resolve(),'workshop')
        c.focus('dataset.seed');c.location(3,'run-b');self.assertIsNone(c.field)
        c.focus('unknown-control');self.assertEqual(c.resolve(),'workshop')
        c.status='evidence';self.assertEqual(c.resolve(),'evidence')

    def test_navigation_back_does_not_duplicate_current_article(self):
        n=Navigation();n.visit('lora.rank');n.visit('lora.rank');n.visit('evidence')
        self.assertEqual(n.back(),'lora.rank');self.assertEqual(n.back(),'guide.start')
        with self.assertRaises(KeyError):n.visit('missing')

    def test_reactions_require_actual_integrity_fields_and_do_not_claim_quality(self):
        for method,reload_key in (('weight_training','checkpoint_reload_matches_validation'),('sft_lora','checkpoint_reload_verified')):
            report={'method':method,'training_integrity':{'verified':True,'optimizer_steps':2,'parameters_changed':4,reload_key:True}}
            self.assertTrue(verified_report(report));self.assertEqual(reaction('completed',report)[1],'verified')
            report['training_integrity']['optimizer_steps']=0;self.assertFalse(verified_report(report))
            self.assertEqual(reaction('completed',report)[1],'completed')
        self.assertIsNone(reaction('running',{}));self.assertEqual(reaction('failed',{})[1],'failed')

    def test_preferences_are_allowlisted_bounded_and_private(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'help.local.json';p=Preferences(path)
            p.data.update(stanley=False,sarcasm=False,reduced_motion=True,unrecognized_field='not-to-be-saved')
            p.data['guide'].update(width=999999,height=-3,x=999999,ontop=True)
            p.data['tutorials']={'quick-start':{'step':999,'completed':False,'skipped':[0,999]}}
            self.assertTrue(p.save());saved=Preferences(path).data
            self.assertFalse(saved['stanley']);self.assertTrue(saved['guide']['ontop'])
            self.assertEqual(saved['guide']['width'],2400);self.assertEqual(saved['guide']['height'],320)
            self.assertEqual(saved['tutorials']['quick-start']['skipped'],[0]);self.assertNotIn('unrecognized_field',json.loads(path.read_text()))
            self.assertEqual(path.stat().st_mode&0o777,0o600)
            target=Path(root)/'other';target.write_text('unchanged');path.unlink();path.symlink_to(target)
            bad=Preferences(path);self.assertIsNotNone(bad.error);self.assertFalse(bad.save());self.assertEqual(target.read_text(),'unchanged')

    def test_malformed_preferences_preserve_defaults(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/'help.local.json';p.write_text('{bad json')
            self.assertTrue(Preferences(p).data['stanley'])
        self.assertTrue(checked({'stanley':'false'})['stanley'])
        self.assertEqual(checked({'tutorials':{'interface':{'step':False,'skipped':'bad'}}})['tutorials']['interface']['skipped'],[])
