import unittest
from unittest.mock import patch
from overmind.hardware import inspect

class HardwareTests(unittest.TestCase):
    def test_pascal_never_claims_bf16_or_verified_training(self):
        with patch('overmind.hardware._query',side_effect=['GTX 1080 Ti, 11264, 100, 0','GTX 1080 Ti, 550.1, 11264, 11164, 6.1']):
            result=inspect()
        gpu=result['nvidia_devices'][0]
        self.assertFalse(gpu['bf16_hardware_candidate'])
        self.assertIn('no BF16',gpu['precision_guidance'])
        self.assertEqual(result['training_device'],'CPU')
        self.assertEqual(result['cuda_runtime'],'unverified')

    def test_missing_driver_still_provides_cpu_and_storage_guidance(self):
        with patch('overmind.hardware._query',return_value=None):result=inspect()
        self.assertIsNone(result['gpu'])
        self.assertEqual(result['nvidia_devices'],[])
        self.assertGreater(result['disk']['free_mb'],0)
        self.assertIn('inference only',' '.join(result['recommendations']))
