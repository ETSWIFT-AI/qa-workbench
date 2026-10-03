"""Opt-in real browser tests: catch viewport-specific failures and SPA routes."""
import asyncio
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from tester import parse_args
from qa.runner import run

HTML='''<!doctype html><html lang="en"><head><title>Matrix fixture</title><style>@media(max-width:500px){#ok{display:none}}</style></head><body>
<h1>State root</h1><p id="ok">Desktop-only feature</p>
<label for="age">Age</label><input id="age" type="number" required min="18" max="120">
<button id="next" onclick="history.pushState({},'', '#/step2'); document.querySelector('h1').textContent='State two'; document.getElementById('last').hidden=false;">Next</button>
<button id="last" hidden onclick="history.pushState({},'', '#/step3'); document.querySelector('h1').textContent='State three'">Last</button>
</body></html>'''
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200);self.send_header('Content-Type','text/html');self.end_headers();self.wfile.write(HTML.encode())
    def log_message(self,*args):pass

@unittest.skipUnless(os.environ.get('QA_BROWSER_TESTS')=='1','Opt-in real browsers')
class MatrixTests(unittest.TestCase):
    def test_mobile_failure_and_two_step_spa(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with tempfile.TemporaryDirectory() as d:
                root=Path(d);config=root/'rules.json'
                config.write_text(json.dumps({'journeys':[{'name':'Visible feature','path':'/','critical':True,'steps':[{'action':'visible','selector':'#ok'}]}],'fields':[{'name':'Age','path':'/','selector':'#age','cases':[{'value':'18','accepted':True}]}]}))
                args=parse_args([f'http://127.0.0.1:{server.server_port}','--config',str(config),'--browsers',os.environ.get('QA_TEST_BROWSERS','chromium'),'--viewports','desktop,mobile','--output',str(root/'out'),'--max-pages','1','--repeats','1','--allow-actions','--auto-fields','--explore-actions','--max-states','8','--exploration-depth','2','--timeout-ms','2000','--settle-ms','50','--no-history'])
                args.axe=None  # This fixture targets the matrix/state engine, not the external axe adapter.
                code=asyncio.run(run(args));r=json.loads((root/'out/report.json').read_text())
                self.assertEqual(code,1)
                js=[x for x in r['results'] if x['family']=='journeys']
                for engine in args.browsers:
                    self.assertTrue(any(x['check'].startswith(engine+'/desktop') and x['status']=='PASS' for x in js))
                    self.assertTrue(any(x['check'].startswith(engine+'/mobile') and x['status']=='FAIL' for x in js))
                    for viewport in args.viewports:
                        self.assertTrue(any(x['family']=='boundary_rules' and x['check'].startswith(engine+'/'+viewport) and x['status']=='PASS' for x in r['results']))
                self.assertTrue(any(x['url'].endswith('#/step3') and x['depth']==2 for x in r['discovery']))
                self.assertTrue(any('Draft:' in x['check'] and x['family']=='native_forms' for x in r['results']))
        finally:server.shutdown();server.server_close()

if __name__=='__main__':unittest.main()
