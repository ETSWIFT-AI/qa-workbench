"""Intentionally buggy local target. Binds only to loopback."""
import json
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer

HOME='''<!doctype html><html lang="en"><head><title>QA demo shop</title></head><body><h1>QA demo shop</h1>
<a href="/about">About</a> <a href="/register">Register</a> <a href="/missing">Broken page</a>
<button id="noop">This button does nothing</button><button disabled>Intentionally disabled</button>
<img src="/missing-image.png"><div style="width:1800px">This causes overflow on mobile</div>
<script>setTimeout(()=>{throw new Error('Deliberate demo error')},50)</script></body></html>'''
REGISTER='''<!doctype html><html lang="en"><head><title>Register</title></head><body><h1>Register</h1>
<form onsubmit="event.preventDefault();document.querySelector('#result').textContent='Saved'">
<label for="age">Age</label><input id="age" name="age" type="number" min="18" max="120" step="1" required>
<button id="submit">Save</button></form><p id="result"></p><a href="/">Home</a></body></html>'''
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path=='/api/profile':
            # Deliberate authorization flaw: unauthenticated request returns private profile.
            payload={'name':'Demo private profile'}
            self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers(); self.wfile.write(json.dumps(payload).encode()); return
        pages={'/':HOME,'/register':REGISTER,'/about':'<!doctype html><html lang="en"><title>About</title><h1>About</h1></html>'}
        body=pages.get(self.path,'<h1>Not found</h1>')
        self.send_response(200 if self.path in pages else 404)
        self.send_header('Content-Type','text/html; charset=utf-8'); self.end_headers(); self.wfile.write(body.encode())
    def log_message(self,*args): pass

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(); p.add_argument('--port',type=int,default=8765); a=p.parse_args()
    print(f'Deliberately faulty demo running at http://127.0.0.1:{a.port}',flush=True)
    ThreadingHTTPServer(('127.0.0.1',a.port),Handler).serve_forever()
