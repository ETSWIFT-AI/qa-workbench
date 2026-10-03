import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from advanced.data import byte_tokens,load_records,safe_image
from advanced.learning import split_groups,predict
from advanced.observe import ui_checks
from advanced.source import inspect_source
from advanced.planner import plan

class CoreTests(unittest.TestCase):
    def test_tokenizer_no_external_vocabulary(self):
        self.assertEqual(len(byte_tokens('')),256);self.assertEqual(byte_tokens('A')[0],66)
    def test_group_separation(self):
        rows=[{'group':str(i//4)} for i in range(40)];parts=split_groups(rows,42);groups=[{r['group'] for r in x} for x in parts]
        self.assertFalse(groups[0]&groups[1]);self.assertFalse(groups[0]&groups[2]);self.assertFalse(groups[1]&groups[2])
        with self.assertRaises(ValueError):split_groups(rows[:4],42)
    def test_missing_model_abstains(self):self.assertEqual(predict([],'.',None)['status'],'NOT_TRAINED')
    def test_ui_scope(self):
        x={'overflow':True,'broken_images':0,'missing_alt':0,'unlabelled':0,'title':'Hi','lang':'en','small_targets':4,'small_text':2}
        result=ui_checks(x);self.assertEqual(result['technical_ui_score'],83.3);self.assertIn('Not visual aesthetics',result['scope'])
    def test_image_escape(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):safe_image(root,'../private.png')
    def test_source_does_not_execute(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'app.py').write_text('def f(x):\n return eval(x)\n');(root/'.env').write_text('secret=abc')
            out=inspect_source(root);self.assertEqual(len(out['files']),1);self.assertEqual(out['files'][0]['review'][0]['line'],2)
    def test_no_oracle_invented(self):
        out=plan({'results':[]},{'client_map':[]});self.assertTrue(out['questions_if_business_assessment_required'])

@unittest.skipUnless(importlib.util.find_spec('torch'),'Optional torch not installed')
class LearningTests(unittest.TestCase):
    def test_all_branches_have_gradients(self):
        import torch
        from advanced.models import WebsiteNet
        torch.set_num_threads(2);m=WebsiteNet();p=m(torch.rand(2,3,128,128),torch.ones(2,256,dtype=torch.long),torch.rand(2,32,6),torch.tensor([5,7]),torch.rand(2,16));p.sum().backward()
        for branch in ('cnn','rnn','tokens','transformer','mlp','fusion'):
            self.assertTrue(any(p.grad is not None and float(p.grad.abs().sum())>0 for p in getattr(m,branch).parameters()),branch)
    def test_train_and_serialization_abstention(self):
        from advanced.synthetic import generate
        from advanced.learning import train
        import torch
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);generate(root/'data');meta=train(root/'data/dataset.jsonl',root/'model',epochs=2,batch_size=8)
            self.assertFalse(meta['pretrained']);self.assertFalse(meta['eligible_for_advisory']);self.assertTrue(meta['synthetic'])
            self.assertEqual(predict([],root/'data',root/'model')['status'],'ABSTAIN')
            self.assertTrue(torch.load(root/'model/weights.pt',weights_only=True))
