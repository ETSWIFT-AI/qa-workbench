import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from product.store import Store,verify
from product.security import redact,secret_set
from product.issues import drafts,jira_csv
from product.server import Application,make_server

class ProductTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.store=Store(self.root)
        self.admin_id=self.store.create_user('admin','Strong-admin-123','admin')
        self.tester_id=self.store.create_user('tester','Strong-tester-123','tester')
        self.viewer_id=self.store.create_user('viewer','Strong-viewer-123','viewer')
        self.admin={'id':self.admin_id,'name':'admin','role':'admin'}
        self.tester={'id':self.tester_id,'name':'tester','role':'tester'}
        self.viewer={'id':self.viewer_id,'name':'viewer','role':'viewer'}
    def tearDown(self):self.temp.cleanup()
    def test_passwords_hashed_and_sessions_expire(self):
        with self.store.db() as db:row=db.execute('SELECT password FROM users WHERE id=?',(self.admin_id,)).fetchone()
        self.assertNotIn('Strong-admin-123',row['password']);self.assertTrue(verify('Strong-admin-123',row['password']))
        token,csrf=self.store.login('admin','Strong-admin-123');self.assertEqual(self.store.session(token)['id'],self.admin_id)
        with self.store.db() as db:db.execute('UPDATE sessions SET expires=0')
        self.assertIsNone(self.store.session(token))
    def test_project_isolation_and_read_only_role(self):
        pid=self.store.add_project(self.admin,'Private','https://example.test/')
        with self.assertRaises(PermissionError):self.store.project(self.tester,pid)
        self.store.grant(self.admin,pid,'viewer');self.assertEqual(self.store.project(self.viewer,pid)['name'],'Private')
        with self.assertRaises(PermissionError):self.store.project(self.viewer,pid,True)
        with self.assertRaises(PermissionError):self.store.add_project(self.viewer,'No','https://example.test')
    def test_revocation_and_password_reset(self):
        pid=self.store.add_project(self.admin,'Private','https://example.test/')
        self.store.grant(self.admin,pid,'tester');self.store.project(self.tester,pid)
        self.store.revoke(self.admin,pid,'tester')
        with self.assertRaises(PermissionError):self.store.project(self.tester,pid)
        token,_=self.store.login('tester','Strong-tester-123')
        self.store.reset_password(self.admin,'tester','New-password-123')
        self.assertIsNone(self.store.session(token))
        self.store.login('tester','New-password-123')
    def test_multiline_secrets_redacted(self):
        self.assertNotIn('private-line',redact('private-line-one\nprivate-line-two',['private-line-one\nprivate-line-two']))
    def test_workflow_needs_assertion_and_private_inputs(self):
        pid=self.store.add_project(self.admin,'App','https://example.test/')
        config={'journeys':[{'name':'Login','path':'/','steps':[{'action':'fill','selector':'#password','value':'secret'},{'action':'visible','selector':'#welcome'}]}]}
        with self.assertRaises(ValueError):self.store.workflow(self.admin,pid,'bad',config)
        config['journeys'][0]['steps'][0]={'action':'fill','selector':'#password','value_env':'QA_PASSWORD'}
        self.assertGreater(self.store.workflow(self.admin,pid,'Good',config),0)
        config['journeys'][0]['steps'].pop()
        with self.assertRaises(ValueError):self.store.workflow(self.admin,pid,'No assertion',config)
    def test_redaction_and_export_verification(self):
        text=redact('Authorization: Bearer abc\npassword=def\nhttps://u:p@example.test/?token=123\nmy-private-value',['my-private-value'])
        for secret in ('Bearer abc','password=def','u:p','token=123','my-private-value'):self.assertNotIn(secret,text)
        r={'target':'https://example.test','results':[{'id':'x','check':'=formula','status':'ERROR','detail':'timeout'}]}
        rows=drafts(r);self.assertIn('not a confirmed',rows[0]['classification']);self.assertIn('UNVERIFIED',rows[0]['verification'])
        self.assertIn("'=formula",jira_csv(rows))
    def test_no_plaintext_credential_fallback(self):
        with patch('product.security.keyring_api',side_effect=RuntimeError('Unavailable')):
            with self.assertRaises(RuntimeError):secret_set(1,'QA_PASSWORD','secret')
        self.assertEqual(list(self.root.glob('*secret*')),[])

class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.app=Application(self.temp.name)
        self.app.store.create_user('admin','Strong-admin-123','admin')
        self.server=make_server(self.app,0);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.cookie='';self.csrf=''
    def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join();self.temp.cleanup()
    def request(self,path,data=None,csrf=True,headers=None):
        c=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=10)
        h={'Cookie':self.cookie}
        if data is not None:h['Content-Type']='application/json'
        if csrf:h['X-QA-CSRF']=self.csrf
        h.update(headers or {});c.request('POST' if data is not None else 'GET',path,json.dumps(data) if data is not None else None,h)
        r=c.getresponse();body=r.read();result=(r.status,dict(r.getheaders()),body);c.close();return result
    def login(self):
        status,headers,body=self.request('/api/login',{'name':'admin','password':'Strong-admin-123'})
        self.assertEqual(status,200);self.cookie=headers['Set-Cookie'].split(';')[0];self.csrf=json.loads(body)['csrf']
    def test_auth_csrf_origin_and_host(self):
        self.assertEqual(self.request('/api/state')[0],403);self.login()
        self.assertEqual(self.request('/api/state')[0],200)
        self.assertEqual(self.request('/api/project',{'name':'x','target':'https://example.test'},csrf=False)[0],403)
        self.assertEqual(self.request('/api/project',{'name':'x','target':'https://example.test'},headers={'Origin':'https://evil.test'})[0],403)
        self.assertEqual(self.request('/api/state',headers={'Host':'evil.test'})[0],403)
    def test_account_role_enforcement_via_http(self):
        self.login();status,_,body=self.request('/api/project',{'name':'Private','target':'https://example.test/'})
        self.assertEqual(status,200);pid=json.loads(body)['id']
        self.assertEqual(self.request('/api/user',{'name':'viewer','password':'Strong-viewer-123','role':'viewer'})[0],200)
        self.request('/api/logout',{});status,headers,body=self.request('/api/login',{'name':'viewer','password':'Strong-viewer-123'});self.cookie=headers['Set-Cookie'].split(';')[0];self.csrf=json.loads(body)['csrf']
        self.assertEqual(self.request('/api/state?project='+str(pid))[0],403)
        self.assertEqual(self.request('/api/run',{'project':pid,'kind':'setup'})[0],403)
    def test_login_rate_limit(self):
        for _ in range(5):self.assertEqual(self.request('/api/login',{'name':'admin','password':'wrong'})[0],403)
        status,_,body=self.request('/api/login',{'name':'admin','password':'Strong-admin-123'})
        self.assertEqual(status,403);self.assertIn(b'wait five minutes',body)
    def test_job_output_redacted_and_artifact_path_confined(self):
        self.login();uid=1;pid=self.app.store.add_project({'id':uid,'role':'admin'},'Demo','http://127.0.0.1/')
        jid='a'*32;out=self.app.jobs.root/jid;out.mkdir()
        with self.app.store.db() as db:db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?)',(jid,pid,uid,'scan','QUEUED',time.time(),None,None,'[]'))
        code="import os,json;from pathlib import Path;v=os.environ['QA_TEST'];print(v);Path("+repr(str(out/'report.json'))+").write_text(json.dumps({'secret':v,'numeric':1,'short':'1'}))"
        self.app.jobs.queue.put((jid,[sys.executable,'-c',code],{'QA_TEST':'private-value-123','QA_SHORT':'1'}))
        self.app.jobs.queue.join()
        self.assertNotIn('private-value-123',(out/'run.log').read_text());self.assertNotIn('private-value-123',(out/'report.json').read_text())
        self.assertEqual(self.request('/api/file?id='+jid+'&path=../../product.sqlite3')[0],403)
        self.assertEqual(self.request('/api/file?id='+jid+'&path=report.json')[0],200)
        cleaned=json.loads((out/'report.json').read_text());self.assertEqual(cleaned['numeric'],1);self.assertEqual(cleaned['short'],'[REDACTED]')

if __name__=='__main__':unittest.main()
