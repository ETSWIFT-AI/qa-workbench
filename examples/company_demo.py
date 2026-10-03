"""Disposable loopback order service: exact-once persistence and cleanup fixture."""
import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs

PAGE = '''<!doctype html><meta charset="utf-8"><title>Order test fixture</title>
<h1>Test order</h1><label>Run ID <input id="run"></label><label>Item <input id="item"></label>
<button id="place">Place Order</button><p id="status">Ready</p>
<script>document.querySelector('#place').onclick=async()=>{const r=await fetch('/api/orders',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({run_id:document.querySelector('#run').value,item:document.querySelector('#item').value})});document.querySelector('#status').textContent=r.ok?'Confirmed':'Error';};</script>'''

def make_server(port=8770, broken=False):
    orders = []; lock = threading.Lock()
    class Handler(BaseHTTPRequestHandler):
        def send(self, status, value, mime='application/json'):
            data = value.encode() if isinstance(value, str) else json.dumps(value).encode()
            self.send_response(status); self.send_header('Content-Type', mime); self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)
        def do_GET(self):
            parsed = urlsplit(self.path)
            if parsed.path == '/': self.send(200, PAGE, 'text/html'); return
            if parsed.path == '/api/admin': self.send(200 if self.headers.get('X-Role') == 'admin' else 403, {'ok': self.headers.get('X-Role') == 'admin'}); return
            if parsed.path == '/api/orders':
                run_id = parse_qs(parsed.query).get('run_id', [''])[0]
                with lock: selected = [dict(x) for x in orders if x['run_id'] == run_id]
                self.send(200, {'orders': selected}); return
            self.send(404, {'error': 'Not found'})
        def do_POST(self):
            if self.path != '/api/orders': self.send(404, {}); return
            data = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))))
            if not data.get('run_id') or not data.get('item'): self.send(400, {}); return
            with lock:
                existing = next((x for x in orders if x['run_id'] == data['run_id']), None)
                if not existing or broken:
                    existing = {'id': len(orders) + 1, 'run_id': data['run_id'], 'item': data['item']}; orders.append(existing)
            self.send(201, existing)
        def do_DELETE(self):
            parsed = urlsplit(self.path)
            if parsed.path != '/api/orders': self.send(404, {}); return
            run_id = parse_qs(parsed.query).get('run_id', [''])[0]
            if not run_id: self.send(400, {}); return
            with lock: orders[:] = [o for o in orders if o['run_id'] != run_id]
            self.send(200, {'deleted': True})
        def log_message(self, *args): pass
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.orders = orders
    return server

if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--port', type=int, default=8770); p.add_argument('--broken', action='store_true'); a = p.parse_args()
    print(f'Disposable demo: http://127.0.0.1:{a.port}', flush=True)
    make_server(a.port, a.broken).serve_forever()
