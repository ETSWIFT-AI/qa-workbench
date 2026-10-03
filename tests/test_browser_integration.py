"""Opt-in integration against our deliberately broken local site. Never an external target."""
import asyncio
import json
import os
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from examples.demo_site import Handler
from tester import parse_args
from qa.runner import run

@unittest.skipUnless(os.environ.get('QA_BROWSER_TESTS')=='1','Set QA_BROWSER_TESTS=1 after installing Chromium')
class BrowserIntegration(unittest.TestCase):
    def test_detects_known_defects_and_validates_rules(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with tempfile.TemporaryDirectory() as d:
                args=parse_args([f'http://127.0.0.1:{server.server_port}','--config','examples/demo-rules.json','--output',d,'--allow-actions','--max-pages','4','--repeats','1','--viewports','desktop','--settle-ms','100','--timeout-ms','3000','--no-history'])
                code=asyncio.run(run(args))
                data=json.loads((Path(d)/'report.json').read_text())
                results=data['results']
                self.assertEqual(code,1)
                self.assertTrue(any(r['family']=='http' and r['status']=='FAIL' for r in results))
                self.assertTrue(any(r['family']=='js_errors' and r['status']=='FAIL' for r in results))
                self.assertTrue(any(r['family']=='authorization' and r['status']=='FAIL' for r in results))
                self.assertEqual(len([r for r in results if r['family']=='boundary_rules' and r['status']=='PASS']),9)
                self.assertEqual(len([r for r in results if r['family']=='journeys' and r['status']=='PASS']),2)
                self.assertEqual(data['score']['gate'],'NOT_QUALIFIED')
        finally: server.shutdown(); server.server_close()

if __name__=='__main__': unittest.main()
