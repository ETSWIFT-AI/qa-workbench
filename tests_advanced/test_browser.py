import asyncio
import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path

@unittest.skipUnless(os.environ.get('QA_BROWSER_TESTS')=='1','Explicit local Chromium test')
class ObservationTests(unittest.IsolatedAsyncioTestCase):
    async def test_ui_collection_and_no_mutations(self):
        from advanced.observe import collect
        class Handler(BaseHTTPRequestHandler):
            posts=0
            def log_message(self,*a):pass
            def do_GET(self):
                self.send_response(200);self.send_header('Content-type','text/html');self.end_headers();self.wfile.write(b'<html lang="en"><title>Fixture</title><body><h1>Demo</h1><input id="age" type="number" min="18" max="60"><div style="width:2000px">overflow</div><script>fetch("/write",{method:"POST"}).catch(()=>{})</script></body></html>')
            def do_POST(self):Handler.posts+=1;self.send_response(200);self.end_headers()
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with tempfile.TemporaryDirectory() as temp:
                root=Path(temp);url=f'http://127.0.0.1:{server.server_port}/';report=root/'report.json';report.write_text(json.dumps({'target':url,'pages':[{'url':url,'variant':'chromium/mobile'}]}))
                result=await collect(report,root/'advanced');self.assertEqual(result['errors'],[]);self.assertEqual(Handler.posts,0);self.assertEqual(len(result['rows']),1)
                checks=result['ui'][0]['checks'];self.assertFalse(checks[0]['pass']);self.assertFalse(checks[3]['pass']);self.assertTrue((root/'advanced/dataset-unlabelled.jsonl').exists())
        finally:server.shutdown();server.server_close()
