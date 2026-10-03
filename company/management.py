"""Local case ownership and review audit trail. No invented shared SaaS integration."""
import datetime
import html
import json
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def connect(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.executescript('''CREATE TABLE IF NOT EXISTS cases(id TEXT PRIMARY KEY,name TEXT NOT NULL,owner TEXT NOT NULL,priority TEXT NOT NULL,requirement TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY,created TEXT NOT NULL,report TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS reviews(id INTEGER PRIMARY KEY,case_id TEXT NOT NULL,reviewer TEXT NOT NULL,state TEXT NOT NULL,note TEXT NOT NULL,created TEXT NOT NULL);''')
    return db

def execute(path, action, data=None):
    data = data or {}
    with connect(path) as db:
        if action == 'case':
            if not all(data.get(k) for k in ('id', 'name', 'owner', 'priority', 'requirement')):
                raise ValueError('Case needs id, name, owner, priority and requirement')
            db.execute('INSERT INTO cases VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,owner=excluded.owner,priority=excluded.priority,requirement=excluded.requirement', tuple(data[k] for k in ('id','name','owner','priority','requirement')))
        elif action == 'review':
            if data.get('state') not in ('open', 'accepted', 'fixed', 'retest') or not data.get('reviewer') or not data.get('note'):
                raise ValueError('Review needs reviewer, note, state open/accepted/fixed/retest')
            if not db.execute('SELECT id FROM cases WHERE id=?', (data['case_id'],)).fetchone():
                raise ValueError('Unknown case')
            db.execute('INSERT INTO reviews(case_id,reviewer,state,note,created) VALUES(?,?,?,?,?)', tuple(data[k] for k in ('case_id','reviewer','state','note')) + (datetime.datetime.now(datetime.timezone.utc).isoformat(),))
        elif action == 'import':
            if not isinstance(data.get('results'), list) and 'kind' not in data:
                raise ValueError('Expected a QA report')
            db.execute('INSERT INTO runs(created,report) VALUES(?,?)', (datetime.datetime.now(datetime.timezone.utc).isoformat(), json.dumps(data)))
        elif action != 'export': raise ValueError('Unknown management action')
        return {table: [dict(row) for row in db.execute('SELECT * FROM ' + table)] for table in ('cases', 'runs', 'reviews')}

def serve(path, port=8780):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path not in ('/', '/api/export'):
                self.send_error(404); return
            data = execute(path, 'export')
            if self.path == '/api/export':
                body = json.dumps(data, indent=2).encode(); content_type = 'application/json'
            else:
                body = ('<!doctype html><meta charset="utf-8"><title>QA case dashboard</title><style>body{font:16px system-ui;max-width:1000px;margin:40px auto}pre{white-space:pre-wrap}</style><h1>QA case dashboard</h1><p>Local, read-only dashboard. Reviews are human attestations and never change automated results.</p><a href="/api/export">Export JSON</a><pre>' + html.escape(json.dumps(data, indent=2)) + '</pre>').encode(); content_type = 'text/html; charset=utf-8'
            self.send_response(200); self.send_header('Content-Type', content_type); self.send_header('Content-Length', str(len(body))); self.send_header('Cache-Control', 'no-store'); self.end_headers(); self.wfile.write(body)
        def log_message(self, *args): pass
    print(f'Dashboard: http://127.0.0.1:{port} (Ctrl+C to stop)', flush=True)
    ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()
