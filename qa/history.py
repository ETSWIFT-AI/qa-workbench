"""Persistent run snapshots, comparable profiles and honest finding diffs."""
import hashlib
import html
import json
import sqlite3
from pathlib import Path
from .core import origin


def profile_key(settings):
    return hashlib.sha256(json.dumps(settings,sort_keys=True,default=str).encode()).hexdigest()[:20]


def compare(previous,current):
    old={r['fingerprint']:r for r in previous['results']}
    new={r['fingerprint']:r for r in current['results']}
    return {
      'new_failures':[k for k,v in new.items() if v['status']=='FAIL' and (k not in old or old[k]['status']!='FAIL')],
      'resolved_failures':[k for k,v in old.items() if v['status']=='FAIL' and k in new and new[k]['status']=='PASS'],
      'unobserved_previous_failures':[k for k,v in old.items() if v['status']=='FAIL' and k not in new],
      'unresolved_or_unknown':[k for k,v in old.items() if v['status']=='FAIL' and k in new and new[k]['status'] not in ('PASS','FAIL')],
    }


def save_run(report,path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    target=json.dumps(origin(report.target)); profile=profile_key(report.settings)
    current=report.export()
    with sqlite3.connect(path,timeout=20) as db:
        db.execute('CREATE TABLE IF NOT EXISTS runs (id INTEGER PRIMARY KEY, target TEXT, profile TEXT, started TEXT, report TEXT)')
        row=db.execute('SELECT report FROM runs WHERE target=? AND profile=? ORDER BY id DESC LIMIT 1',(target,profile)).fetchone()
        report.history={'profile':profile,'comparison':compare(json.loads(row[0]),current) if row else None,'note':'Only matching scan profiles/configurations are compared. Disappearing checks are not called fixed.'}
        db.execute('INSERT INTO runs(target,profile,started,report) VALUES(?,?,?,?)',(target,profile,report.started,json.dumps(report.export())))
        rows=db.execute('SELECT report FROM runs WHERE target=? AND profile=? ORDER BY id DESC LIMIT 20',(target,profile)).fetchall()
        report.history['trend']=[{'started':d['started'],'quality':d['score']['score'],'coverage':d['score']['coverage'],'gate':d['score']['gate']} for d in (json.loads(r[0]) for r in reversed(rows))]
    return report.history


def dashboard(path,output):
    esc=lambda x:html.escape(str(x),quote=True)
    with sqlite3.connect(path) as db: rows=db.execute('SELECT started,target,profile,report FROM runs ORDER BY id DESC LIMIT 200').fetchall()
    body=''
    for started,target,profile,raw in rows:
        d=json.loads(raw);s=d['score']
        body+=f'<tr><td>{esc(started)}</td><td>{esc(d["target"])}</td><td>{esc(profile)}</td><td>{esc(s["score"] if s["score"] is not None else "N/A")}</td><td>{s["coverage"]}%</td><td>{esc(s["gate"])}</td></tr>'
    Path(output).write_text('<!doctype html><meta charset="utf-8"><title>QA history</title><style>body{font:16px system-ui;padding:25px}table{border-collapse:collapse}td,th{padding:12px;border:1px solid #ddd}</style><h1>Run history</h1><p>Compare matching profile IDs only. Quality and coverage are independent.</p><table><tr><th>Run</th><th>Target</th><th>Profile</th><th>Tested quality</th><th>Coverage</th><th>Gate</th></tr>'+body+'</table>',encoding='utf-8')
