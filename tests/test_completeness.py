import copy
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
from qa.completeness import summarize,save

class CompletionTests(unittest.TestCase):
    def report(self):
        return {'target':'https://example.test/','results':[{'id':'a','family':'http','status':'PASS','detail':'HTTP 200'}], 'score':{'gate':'MEETS_CONFIGURED_GATE','categories':{'functional':{'families':{'http':{'planned':1}}}}}}
    def test_preserves_unknown_without_inventing_defect(self):
        d=self.report();d['results'].append({'id':'b','family':'axe','status':'SKIP','detail':'Missing axe'})
        before=copy.deepcopy(d);s=summarize(d)
        self.assertEqual(d,before);self.assertFalse(s['passed']);self.assertEqual(s['status'],'INCOMPLETE');self.assertIn('npm',s['gaps'][0]['next_action'])
    def test_each_unknown_status_blocks_success(self):
        for status in ('REVIEW','ERROR','SKIP'):
            d=self.report();d['results'][0]['status']=status
            self.assertFalse(summarize(d)['passed'])
    def test_failure_stays_failure(self):
        d=self.report();d['results'][0]['status']='FAIL'
        self.assertEqual(summarize(d)['status'],'FAILED')
    def test_missing_family_and_excluded_route_block(self):
        d=self.report();d['score']['categories']['functional']['families']['journeys']={'planned':0}
        d['notes']=['Excluded route: https://example.test/delete']
        s=summarize(d);self.assertEqual(len(s['gaps']),2);self.assertFalse(s['passed'])
    def test_empty_run_is_not_pass(self):
        self.assertFalse(summarize({})['passed'])
    def test_only_completed_configured_scope_can_pass(self):
        self.assertTrue(summarize(self.report())['passed'])
        d=self.report();d['score']['gate']='NOT_QUALIFIED'
        self.assertFalse(summarize(d)['passed'])
    def test_export_escapes_html_and_fails_ci(self):
        d=self.report();d['results'][0].update(status='REVIEW',detail='<script>alert(1)</script>')
        with tempfile.TemporaryDirectory() as td:
            save(summarize(d),td);p=Path(td)
            self.assertNotIn('<script>',(p/'completion.html').read_text())
            self.assertIsNotNone(ET.parse(p/'completion-junit.xml').find('.//failure'))
            self.assertFalse(json.loads((p/'completion.json').read_text())['passed'])

if __name__=='__main__':unittest.main()
