import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

@unittest.skipUnless(importlib.util.find_spec('torch'),'Optional torch dependency')
class UITrainingTests(unittest.TestCase):
    def test_real_dataset_integrity_and_labels(self):
        from advanced.ui_learning import load_dataset
        root=Path(__file__).parents[1];rows=load_dataset(root/'data/calista_ui/dataset.json')
        self.assertEqual(len(rows),100)
        for row in rows:self.assertAlmostEqual(row['ui_score'],(row['original_score']-1)/9*100)
    def test_unhelpful_model_abstains(self):
        from advanced.ui_learning import predict
        with tempfile.TemporaryDirectory() as temp:
            Path(temp,'ui-model.json').write_text(json.dumps({'architecture':'UICNN-v1','pretrained':False,'beats_constant_baseline_on_test':False,'metrics':{}}))
            self.assertEqual(predict([],'.',temp)['status'],'ABSTAIN')
