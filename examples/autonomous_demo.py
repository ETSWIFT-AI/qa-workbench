"""Loopback-only demo for selector-free login/search/navigation. Not a production auth implementation."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import parse_qs,urlsplit

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*a):pass
    def send(self,body,status=200):
        self.send_response(status);self.send_header('Content-Type','text/html; charset=utf-8');self.end_headers();self.wfile.write(('<!doctype html><html lang="en"><title>Autonomous QA demo</title><style>body{font:18px system-ui;max-width:800px;margin:50px auto}button,input{padding:12px;margin:8px}nav a{margin-right:20px}</style><body>'+body+'</body></html>').encode())
    def do_GET(self):
        path=urlsplit(self.path).path
        if path=='/':self.send('<h1>Autonomous QA demo</h1><nav><a href="/login">Login</a><a href="/search">Search</a></nav><button aria-expanded="false" onclick="this.setAttribute(\'aria-expanded\',\'true\');document.getElementById(\'details\').hidden=false">Details</button><p id="details" hidden>Exploration discovered this panel.</p>')
        elif path=='/login':self.send('<h1>Sign in</h1><form action="/login" method="post"><label>Email <input type="email" name="email" autocomplete="username"></label><label>Password <input type="password" name="password" autocomplete="current-password"></label><button>Sign in</button></form>')
        elif path=='/dashboard':
            if 'demo_session=yes' not in self.headers.get('Cookie',''):self.send('<h1>Authentication required</h1>',401);return
            self.send('<h1>Dashboard</h1><a href="/logout">Log out</a><button role="tab" onclick="document.getElementById(\'account\').hidden=false">Account</button><p id="account" hidden>Account panel reached.</p>')
        elif path=='/search':self.send('<h1>Search</h1><form action="/results" method="get"><label>Search <input type="search" name="q"></label><button>Search</button></form>')
        elif path=='/results':self.send('<h1>Search results</h1><p>Demo result. Relevance is not automatically verified.</p>')
        else:self.send('<h1>Not found</h1>',404)
    def do_POST(self):
        body=parse_qs(self.rfile.read(int(self.headers.get('Content-Length','0'))).decode())
        if self.path=='/login' and body.get('email')==['demo@example.com'] and body.get('password')==['Demo-only-123']:
            self.send_response(303);self.send_header('Location','/dashboard');self.send_header('Set-Cookie','demo_session=yes; HttpOnly; SameSite=Lax');self.end_headers()
        else:self.send('<h1>Invalid credentials</h1>',200)
if __name__=='__main__':
    print('Demo: http://127.0.0.1:8766/ | test user demo@example.com | password Demo-only-123',flush=True)
    ThreadingHTTPServer(('127.0.0.1',8766),Handler).serve_forever()
