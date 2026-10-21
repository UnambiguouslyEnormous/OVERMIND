import copy
import tempfile
import unittest
from unittest.mock import patch
from overmind.data import benchmark
from overmind.integrity import training_evidence
from overmind.lab import DEFAULTS, Experiment, config_checked
from overmind.model import TextStudent
from overmind.store import Store

class TrainingIntegrityTests(unittest.TestCase):
    def test_real_steps_hash_changes_and_reload_predictions(self):
        with tempfile.TemporaryDirectory() as root:
            store=Store(root);rid=store.create(config_checked({**DEFAULTS,'epochs':2}),benchmark())
            Experiment(store,rid).run()
            evidence=store.read(rid,'training-integrity.json')
            self.assertTrue(evidence['verified'])
            self.assertTrue(evidence['checkpoint_reload_matches_validation'])
            self.assertGreater(evidence['optimizer_steps'],0)
            self.assertNotEqual(evidence['base_parameters_sha256'],evidence['candidate_parameters_sha256'])
            metrics=store.read(rid,'training-metrics.json')
            self.assertEqual([m['epoch'] for m in metrics],[1,2])
            self.assertGreater(metrics[0]['mean_gradient_l2'],0)
            self.assertGreater(metrics[0]['examples_per_second'],0)

    def test_zero_update_training_is_rejected_even_with_claimed_steps(self):
        def fake_epoch(model,rows,rate,seed,guard):
            model.optimizer_steps+=len(rows)
            model.last_epoch={'examples':len(rows),'learning_rate':rate,'mean_gradient_l2':0}
            return 0.0
        with tempfile.TemporaryDirectory() as root:
            store=Store(root);rid=store.create(config_checked({**DEFAULTS,'epochs':1}),benchmark())
            with patch.object(TextStudent,'epoch',fake_epoch):
                with self.assertRaisesRegex(ValueError,'zero parameter updates'):Experiment(store,rid).run()
            self.assertFalse(store.read(rid,'training-integrity.json')['verified'])
            self.assertFalse((store.root/rid/'promoted.json').exists())

    def test_steps_survive_checkpoint_reload_and_legacy_is_supported(self):
        model=TextStudent(['a','b'],16)
        before=copy.deepcopy(model.export())
        model.epoch([{'input':'alpha','target':'a'}],.1,42,lambda:None)
        restored=TextStudent.restore(model.export())
        self.assertEqual(restored.optimizer_steps,1)
        self.assertTrue(training_evidence(before,restored.export())['verified'])
        legacy=restored.export();legacy.pop('optimizer_steps')
        self.assertEqual(TextStudent.restore(legacy).predict('alpha'),restored.predict('alpha'))
        self.assertIsNone(training_evidence(before,legacy)['optimizer_steps'])
