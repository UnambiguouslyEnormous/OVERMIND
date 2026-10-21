import unittest
from overmind.science import failures, wilson

class ScienceTests(unittest.TestCase):
    def test_failure_groups_preserve_paired_examples(self):
        rows=[{'input':str(i),'target':'yes','prediction':'yes' if correct else 'no','correct':correct} for i,correct in enumerate((True,False,False,True))]
        later=[{**row,'prediction':'yes' if correct else 'no','correct':correct} for row,correct in zip(rows,(False,True,False,True))]
        result=failures({'results':rows},{'results':later})
        self.assertEqual([r['input'] for r in result['regressions']],['0'])
        self.assertEqual([r['input'] for r in result['improvements']],['1'])
        self.assertEqual([r['input'] for r in result['persistent_failures']],['2'])
        later[0]['input']='different'
        with self.assertRaisesRegex(ValueError,'align'):failures({'results':rows},{'results':later})

    def test_small_sample_uncertainty_is_visible(self):
        low,high=wilson(40,40)
        self.assertLess(low,.92);self.assertAlmostEqual(high,1)
        low,high=wilson(0,40)
        self.assertAlmostEqual(low,0);self.assertGreater(high,.08)
