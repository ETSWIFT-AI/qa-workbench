import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from qa.core import Report,canonical,validate_config
from qa.history import save_run,compare
from qa.security import analyse_headers,zap_baseline
from qa.field_metrics import validate_record
from qa.guided import age_rule,navigation_rule
from tester import parse_args

class V3Tests(unittest.TestCase):
    def test_354_passes_one_skip_does_not_zero_quality(self):
        r=Report('https://example.com',{})
        for i in range(354):r.add('actions',str(i),'PASS')
        r.add('actions','unconfigured','SKIP')
        self.assertEqual(r.score()['score'],100)
        f=r.score()['categories']['functional']['families']['actions']
        self.assertEqual(f['completed'],354);self.assertGreater(f['coverage'],99)
        self.assertEqual(r.score()['assessment'],'PARTIAL_ASSESSMENT')
        self.assertEqual(r.score()['gate'],'NOT_QUALIFIED')

    def test_review_only_has_no_quality(self):
        r=Report('https://example.com',{});r.add('keyboard','focus','REVIEW')
        self.assertIsNone(r.score()['score'])

    def test_history_resolves_only_explicit_pass(self):
        with tempfile.TemporaryDirectory() as d:
            db=Path(d)/'history.db'
            a=Report('https://example.com',{'profile':'x'});a.add('http','response','FAIL','old duration 200')
            save_run(a,db)
            b=Report('https://example.com',{'profile':'x'});b.add('http','response','PASS','new duration 100')
            save_run(b,db)
            self.assertEqual(len(b.history['comparison']['resolved_failures']),1)
            c=Report('https://example.com',{'profile':'different'});save_run(c,db)
            self.assertIsNone(c.history['comparison'])

    def test_disappearing_failure_is_not_fixed(self):
        a=Report('https://example.com',{});a.add('http','response','FAIL')
        b=Report('https://example.com',{})
        delta=compare(a.export(),b.export())
        self.assertFalse(delta['resolved_failures']);self.assertEqual(len(delta['unobserved_previous_failures']),1)

    def test_csp_presence_is_not_enough(self):
        rows=analyse_headers({'content-security-policy':"script-src * 'unsafe-eval'",'strict-transport-security':'max-age=0'})
        self.assertTrue(any(r[0]=='CSP script sources' and r[1]=='REVIEW' for r in rows))
        self.assertTrue(any(r[0]=='HSTS duration' and r[1]=='REVIEW' for r in rows))

    def test_crux_origin_guard(self):
        with self.assertRaises(ValueError):validate_record({'record':{'key':{'origin':'https://other.example'},'metrics':{'lcp':{}}}},'https://example.com')
        data=validate_record({'record':{'key':{'origin':'https://example.com'},'metrics':{'largest_contentful_paint':{'percentiles':{'p75':2500}}}}},'https://example.com')
        self.assertEqual(data['status'],'available')

    def test_hash_routes_preserved(self):
        self.assertNotEqual(canonical('https://example.com/#/one'),canonical('https://example.com/#/two'))
        self.assertEqual(canonical('https://example.com/#google_vignette'),'https://example.com/')

    def test_guided_recipes_validate(self):
        cfg={'journeys':[navigation_rule('about','/','#about','/about')],'fields':[age_rule('age','/register','#age',21,65)]}
        validate_config(cfg,'https://example.com')
        self.assertIn({'value':'20','accepted':False},cfg['fields'][0]['cases'])

    def test_actions_remain_explicit(self):
        with self.assertRaises(SystemExit):parse_args(['https://example.com','--auto-fields'])
        a=parse_args(['https://example.com','--allow-actions','--auto-fields'])
        self.assertTrue(a.auto_fields)

if __name__=='__main__':unittest.main()
