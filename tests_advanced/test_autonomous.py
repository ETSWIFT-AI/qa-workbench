import asyncio
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from advanced.autonomous import safe_url,choose_actions,login_form

class PolicyTests(unittest.TestCase):
    def test_scope_and_risk(self):
        base='https://example.com/'
        self.assertIsNone(safe_url(base,'https://other.example/login'))
        self.assertIsNone(safe_url(base,'/delete-account'))
        self.assertIsNone(safe_url(base,'/logout'))
        self.assertEqual(safe_url(base,'/login'),'https://example.com/login')
    def test_risky_buttons_not_selected(self):
        def control(name):return {'visible':True,'disabled':False,'name':name,'href':'','tag':'button','form':-1,'type':'submit','role':'','expanded':None,'index':0}
        out=choose_actions({'controls':[control('Delete'),control('Send'),control('Menu')]},'https://example.com',True)
        self.assertEqual([x['name'] for x in out],['Menu'])

@unittest.skipUnless(os.environ.get('QA_BROWSER_TESTS')=='1','Opt-in local browser tests')
class AgentBrowserTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        class Handler(BaseHTTPRequestHandler):
            posts=[];risky=0
            def log_message(self,*a):pass
            def do_GET(self):
                if self.path.startswith('/delete') or self.path.startswith('/logout'):Handler.risky+=1
                pages={
                 '/':'<a href="/login">Login</a><button onclick="document.querySelector(\'#panel\').hidden=false">Menu</button><div id="panel" hidden>Details panel</div><button onclick="fetch(\'/delete\',{method:\'POST\'})">Delete</button><a href="/logout">Logout</a>',
                 '/login':'<form method="post" action="/login"><label>Email<input name="email" type="email"></label><label>Password<input name="password" type="password"></label><button>Sign in</button></form>',
                 '/dashboard':'<h1>Dashboard</h1><a href="/logout">Log out</a><button aria-expanded="false" onclick="this.setAttribute(\'aria-expanded\',\'true\');document.querySelector(\'#details\').hidden=false">Details</button><p id="details" hidden>Private test information</p>',
                 '/mfa':'<h1>Verification code</h1><input autocomplete="one-time-code">',
                 '/search':'<form method="get" action="/results"><input type="search" name="q"><button>Search</button></form>'}
                body=pages.get(self.path,'<h1>Search results</h1>');self.send_response(200);self.send_header('Content-Type','text/html');self.end_headers();self.wfile.write(('<html lang="en"><title>Agent fixture</title>'+body+'</html>').encode())
            def do_POST(self):
                body=self.rfile.read(int(self.headers.get('Content-Length',0))).decode();Handler.posts.append((self.path,body))
                if self.path=='/login':self.send_response(303);self.send_header('Location','/dashboard');self.send_header('Set-Cookie','session=fixture; HttpOnly; SameSite=Lax');self.end_headers()
                else:Handler.risky+=1;self.send_response(200);self.end_headers()
        self.handler=Handler;self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=self.server.serve_forever,daemon=True).start();self.temp=tempfile.TemporaryDirectory();self.base=f'http://127.0.0.1:{self.server.server_port}'
    async def asyncTearDown(self):self.server.shutdown();self.server.server_close();self.temp.cleanup()
    async def test_login_discovery_and_risk_blocking(self):
        from advanced.autonomous import explore_site
        out=Path(self.temp.name)
        result=await explore_site(self.base+'/',out,True,'tester@example.com','Secret-fixture-91',max_states=8,max_actions=10,max_seconds=30)
        self.assertTrue(any(a['kind']=='login' and a['outcome']=='LIKELY_AUTHENTICATED' for a in result['actions']),result)
        self.assertEqual(len(self.handler.posts),1);self.assertEqual(self.handler.risky,0)
        self.assertTrue(any(a['kind']=='click' for a in result['actions']))
        serialized=(out/'autonomous.json').read_text();self.assertNotIn('Secret-fixture-91',serialized);self.assertNotIn('tester@example.com',serialized)
        self.assertLessEqual(len(result['actions']),10)
    async def test_missing_credentials_no_submission(self):
        from advanced.autonomous import explore_site
        result=await explore_site(self.base+'/login',Path(self.temp.name),True,max_states=3,max_actions=3,max_seconds=15)
        self.assertEqual(self.handler.posts,[]);self.assertTrue(any('test username' in q for q in result['questions']))
    async def test_mfa_does_not_submit(self):
        from advanced.autonomous import explore_site
        result=await explore_site(self.base+'/mfa',Path(self.temp.name),True,'tester@example.com','Secret-fixture-91',max_seconds=15)
        self.assertEqual(self.handler.posts,[]);self.assertTrue(any('MFA' in q for q in result['questions']))
    async def test_read_only_does_not_click(self):
        from advanced.autonomous import explore_site
        result=await explore_site(self.base+'/',Path(self.temp.name),False,max_states=3,max_seconds=15)
        self.assertEqual(result['actions'],[]);self.assertEqual(self.handler.posts,[])
    async def test_get_search(self):
        from advanced.autonomous import explore_site
        result=await explore_site(self.base+'/search',Path(self.temp.name),True,max_states=3,max_actions=3,max_seconds=15)
        self.assertTrue(any(a['kind']=='search' for a in result['actions']),result)
        self.assertEqual(self.handler.posts,[])
