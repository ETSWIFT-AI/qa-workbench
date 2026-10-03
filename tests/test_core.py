import json
import tempfile
import unittest
from pathlib import Path
from qa.core import Report,FAMILIES,canonical,origin,scoped,validate_config
from qa.reporting import render,resolutions
from qa.integrations import import_zap,import_sarif
from qa.ai import ollama_json,group_findings

class CoreTests(unittest.TestCase):
    def test_url_scope(self):
        self.assertEqual(canonical('https://example.com#x'),'https://example.com/')
        self.assertEqual(origin('https://example.com'),origin('https://example.com:443/'))
        for url in ('https://attacker.example/path','http://example.com/','file:///tmp/x','https://a:b@example.com/'):
            with self.assertRaises(ValueError): scoped('https://example.com/',url)

    def full_report(self):
        r=Report('https://example.com',{})
        for _,families in FAMILIES.values():
            for family in families: r.add(family,'baseline','PASS',severity='critical' if family=='journeys' else 'medium')
        return r

    def test_empty_report_has_no_quality(self):
        r=Report('https://example.com',{})
        self.assertIsNone(r.score()['score'])
        self.assertEqual(r.score()['coverage'],0)
        self.assertEqual(r.score()['gate'],'NOT_QUALIFIED')

    def test_fully_assessed_configured_scope_passes(self):
        self.assertEqual(self.full_report().score()['gate'],'MEETS_CONFIGURED_GATE')

    def test_critical_failure_cannot_be_diluted(self):
        r=self.full_report()
        r.add('authorization','Critical flaw','FAIL','private data exposed',severity='critical')
        before=r.score()['score']
        for i in range(100): r.add('authorization',str(i),'PASS')
        self.assertGreaterEqual(r.score()['score'],before)
        self.assertTrue(r.score()['blockers'])
        self.assertEqual(r.score()['gate'],'NOT_QUALIFIED')

    def test_skipped_and_errors_reduce_coverage(self):
        for status in ('SKIP','ERROR','REVIEW'):
            r=self.full_report(); r.add('api_contracts','missing',status)
            self.assertEqual(r.score()['score'],100)
            self.assertLess(r.score()['coverage'],100)

    def test_missing_critical_journey_blocks_gate(self):
        r=self.full_report()
        for row in r.results: row['severity']='medium'
        self.assertEqual(r.score()['gate'],'NOT_QUALIFIED')

    def test_bad_config_rejected(self):
        with self.assertRaises(ValueError): validate_config({'journeys_typo':[]},'https://example.com')
        with self.assertRaises(ValueError): validate_config({'journeys':[{'name':'x','path':'/','steps':[{'action':'click','selector':'button'}]}]},'https://example.com')
        with self.assertRaises(ValueError): validate_config({'api_tests':[{'name':'bad','path':'https://attacker.example','expected_status':200}]},'https://example.com')

    def test_report_escapes_target_and_finding(self):
        r=Report('https://example.com',{}); r.add('http','<script>alert(1)</script>','FAIL','<img src=x onerror=alert(1)>')
        with tempfile.TemporaryDirectory() as d:
            render(r,Path(d)); text=(Path(d)/'report.html').read_text()
            self.assertNotIn('<img src=x',text)
            self.assertIn('&lt;img',text)
            self.assertTrue((Path(d)/'junit.xml').exists())

    def test_reviews_need_traceable_resolution(self):
        r=Report('https://example.com',{}); row=r.add('axe','contrast','REVIEW')
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'review.json'; p.write_text(json.dumps([{'id':row['id'],'status':'PASS','reviewer':'Tester','reason':'Manually measured compliant contrast'}]))
            resolutions(r,p)
        self.assertEqual(row['original_status'],'REVIEW'); self.assertEqual(row['status'],'PASS')

    def test_empty_scanner_reports_do_not_pass(self):
        r=Report('https://example.com',{})
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'zap.json'; p.write_text(json.dumps({'site':[{'@name':'https://example.com','alerts':[]}]}))
            import_zap(p,r,'https://example.com')
            p.write_text(json.dumps({'version':'2.1.0','runs':[{'results':[]}]})); import_sarif(p,r)
        self.assertTrue(all(x['status']=='REVIEW' for x in r.results))

    def test_ai_endpoint_must_be_local(self):
        with self.assertRaises(ValueError): ollama_json('model','prompt','https://example.com')

    def test_query_values_redacted(self):
        r=Report('https://example.com/?token=private',{})
        row=r.add('http','status','PASS',url='https://example.com/?key=private')
        self.assertNotIn('private',r.target); self.assertNotIn('private',row['url'])

if __name__=='__main__': unittest.main()
