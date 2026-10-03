import hmac
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import re
import threading
import time
from urllib.parse import urlsplit,parse_qs
from .store import Store,ROLES
from .jobs import Jobs
from .doctor import diagnose
from .issues import drafts,markdown,jira_csv
from .security import secret_set,secret_delete,redact

UI=Path(__file__).with_name('ui.html')

class Application:
    def __init__(self,root):
        self.store=Store(root);self.jobs=Jobs(self.store);self.attempts={};self.auth_lock=threading.Lock()
    def login(self,name,password):
        key=str(name)[:40]
        with self.auth_lock:
            now=time.time();self.attempts={k:[t for t in v if now-t<300] for k,v in self.attempts.items() if any(now-t<300 for t in v)}
            if len(self.attempts.get(key,[]))>=5 or sum(map(len,self.attempts.values()))>=50:raise PermissionError('Too many login attempts; wait five minutes')
            self.attempts.setdefault(key,[]).append(now)
        result=self.store.login(name,password)
        with self.auth_lock:self.attempts.pop(key,None)
        return result
    def snapshot(self,user,pid=None):
        result={'user':user,'projects':self.store.projects(user)}
        if pid:
            result['project']=self.store.project(user,pid)
            with self.store.db() as db:
                result['workflows']=[dict(r) for r in db.execute('SELECT id,name,config,updated FROM workflows WHERE project=? ORDER BY updated DESC',(pid,))]
                result['jobs']=[dict(r) for r in db.execute('SELECT id,kind,status,created,ended,exit_code FROM jobs WHERE project=? ORDER BY created DESC LIMIT 100',(pid,))]
                result['reviews']=[dict(r) for r in db.execute('SELECT r.*,u.name AS reviewer_name FROM reviews r JOIN jobs j ON j.id=r.job JOIN users u ON u.id=r.reviewer WHERE j.project=? ORDER BY r.created DESC LIMIT 200',(pid,))]
        return result
    def run_report(self,user,jid):
        job=self.jobs.get(user,jid)
        if job['status'] in ('RUNNING','QUEUED'):raise ValueError('Wait for the run to finish')
        root=self.jobs.root/jid
        reports=sorted(root.rglob('report.json'))
        if not reports:raise ValueError('No scan report available')
        data=json.loads(reports[0].read_text(encoding='utf-8'))
        return data

def make_server(app,port=8790):
    class Handler(BaseHTTPRequestHandler):
        def reply(self,status,data,extra=None,mime='application/json; charset=utf-8'):
            body=data if isinstance(data,bytes) else json.dumps(data).encode()
            self.send_response(status);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('X-Frame-Options','DENY')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            for k,v in (extra or {}).items():self.send_header(k,v)
            self.end_headers();self.wfile.write(body)
        def token(self):
            try:
                cookies=SimpleCookie(self.headers.get('Cookie',''));return cookies['qa_session'].value if 'qa_session' in cookies else ''
            except Exception:return ''
        def user(self):
            user=app.store.session(self.token())
            if not user:raise PermissionError('Sign in required')
            return user
        def host_ok(self):
            allowed={'127.0.0.1:'+str(self.server.server_port),'localhost:'+str(self.server.server_port)}
            if self.headers.get('Host') not in allowed:raise PermissionError('Invalid host')
            origin=self.headers.get('Origin')
            if origin and origin not in {'http://'+h for h in allowed}:raise PermissionError('Cross-origin request denied')
        def do_GET(self):
            try:
                self.host_ok();path=urlsplit(self.path).path;q=parse_qs(urlsplit(self.path).query)
                if path=='/':self.reply(200,UI.read_bytes(),mime='text/html; charset=utf-8');return
                if path=='/app.js':self.reply(200,UI.with_name('app.js').read_bytes(),mime='text/javascript; charset=utf-8');return
                user=self.user()
                if path=='/api/state':self.reply(200,app.snapshot(user,int(q['project'][0]) if q.get('project') else None))
                elif path=='/api/doctor':self.reply(200,{'checks':diagnose()})
                elif path=='/api/job':
                    jid=q['id'][0];job=app.jobs.get(user,jid);root=app.jobs.root/jid
                    job['files']=app.jobs.files(user,jid)
                    log=root/'run.log';job['log']=''
                    if log.exists():
                        with log.open('rb') as stream:
                            stream.seek(max(0,log.stat().st_size-20000));job['log']=redact(stream.read().decode('utf-8',errors='replace'))
                    rec=root/'recording.json'
                    if rec.exists() and job['status'] not in ('RUNNING','QUEUED'):job['recording']=json.loads(rec.read_text())
                    self.reply(200,job)
                elif path=='/api/findings':
                    report=app.run_report(user,q['id'][0]);self.reply(200,{'score':report.get('score'), 'target':report.get('target'),'findings':report.get('results',[])})
                elif path=='/api/issues':
                    jid=q['id'][0];report=app.run_report(user,jid);cfgpath=app.jobs.root/jid/'rules.json';cfg=json.loads(cfgpath.read_text()) if cfgpath.exists() else None
                    rows=drafts(report,cfg)
                    with app.store.db() as db:reviews=db.execute('SELECT r.*,u.name AS reviewer_name FROM reviews r JOIN users u ON u.id=r.reviewer WHERE job=? ORDER BY created',(jid,)).fetchall()
                    latest={r['finding']:r for r in reviews}
                    for row in rows:
                        review=latest.get(row['id'])
                        if review:
                            row['verification']='Human review: '+review['state']+' by '+review['reviewer_name']+'; '+redact(review['note'])
                    format=q.get('format',['json'])[0]
                    if format=='jira':self.reply(200,jira_csv(rows).encode(),{'Content-Disposition':'attachment; filename="jira-drafts.csv"'},'text/csv; charset=utf-8')
                    elif format=='markdown':self.reply(200,markdown(rows).encode(),{'Content-Disposition':'attachment; filename="github-issue-drafts.md"'},'text/markdown; charset=utf-8')
                    else:self.reply(200,{'drafts':rows})
                elif path=='/api/file':
                    jid=q['id'][0];relative=q['path'][0]
                    if relative not in app.jobs.files(user,jid):raise PermissionError('Artifact not available')
                    root=(app.jobs.root/jid).resolve();file=(root/relative).resolve()
                    if not file.is_relative_to(root):raise PermissionError('Invalid artifact path')
                    if file.stat().st_size>50_000_000:raise ValueError('Artifact exceeds dashboard download limit; use local files')
                    safe=re.sub(r'[^A-Za-z0-9_.-]','_',file.name)
                    self.reply(200,file.read_bytes(),{'Content-Disposition':'attachment; filename="'+safe+'"'},'application/octet-stream')
                else:self.reply(404,{'error':'Not found'})
            except PermissionError as exc:self.reply(403,{'error':str(exc)})
            except (ValueError,KeyError,FileNotFoundError,json.JSONDecodeError) as exc:self.reply(400,{'error':str(exc)})
            except Exception:self.reply(500,{'error':'Request failed; check local setup'})
        def do_POST(self):
            try:
                self.host_ok()
                if self.headers.get_content_type()!='application/json':raise ValueError('JSON body required')
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=1_000_000:raise ValueError('Invalid request size')
                d=json.loads(self.rfile.read(size));path=urlsplit(self.path).path
                if not isinstance(d,dict):raise ValueError('JSON object required')
                if path=='/api/login':
                    token,csrf=app.login(d.get('name',''),d.get('password',''));self.reply(200,{'csrf':csrf},{'Set-Cookie':'qa_session='+token+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800'});return
                user=self.user()
                if not hmac.compare_digest(self.headers.get('X-QA-CSRF',''),user['csrf']):raise PermissionError('Invalid request token')
                if path=='/api/logout':app.store.logout(self.token());self.reply(200,{'ok':True},{'Set-Cookie':'qa_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'});return
                if path=='/api/project':result={'id':app.store.add_project(user,d['name'],d['target'])}
                elif path=='/api/member':app.store.grant(user,int(d['project']),d['username']);result={'ok':True}
                elif path=='/api/member-remove':app.store.revoke(user,int(d['project']),d['username']);result={'ok':True}
                elif path=='/api/password':app.store.reset_password(user,d['name'],d['password']);result={'ok':True}
                elif path=='/api/user':
                    if user['role']!='admin':raise PermissionError('Admin role required')
                    result={'id':app.store.create_user(d['name'],d['password'],d['role'])};app.store.audit(user['id'],'user-created',d['name'])
                elif path=='/api/workflow':result={'id':app.store.workflow(user,int(d['project']),d['name'],d['config'])}
                elif path in ('/api/secret','/api/secret-delete'):
                    pid=int(d['project']);app.store.project(user,pid,True)
                    if path.endswith('delete'):secret_delete(app.store.vault_id(pid),d['name'])
                    else:secret_set(app.store.vault_id(pid),d['name'],d['value'])
                    app.store.audit(user['id'],'secret-updated',str(pid)+':'+d['name']);result={'ok':True}
                elif path=='/api/run':result={'id':app.jobs.submit(user,int(d['project']),d['kind'],d.get('actions') is True,d.get('workflow'))}
                elif path=='/api/cancel':app.jobs.stop(user,d['id']);result={'ok':True}
                elif path=='/api/retention':result={'purged':app.jobs.purge(user,d['days'])}
                elif path=='/api/review':
                    job=app.jobs.get(user,d['job'],True)
                    report=app.run_report(user,d['job'])
                    if not any(r.get('id')==d['finding'] for r in report.get('results',[])):raise ValueError('Unknown finding')
                    if d['state'] not in ('open','reproduced','not-reproduced','fixed-awaiting-retest','accepted-risk') or not d.get('note'):raise ValueError('Review state and note required')
                    with app.store.db() as db:db.execute('INSERT INTO reviews(job,finding,owner,state,note,reviewer,created) VALUES(?,?,?,?,?,?,?,?)',(d['job'],d['finding'],str(d.get('owner',''))[:100],d['state'],str(d['note'])[:4000],user['id'],time.time()))
                    app.store.audit(user['id'],'finding-reviewed',d['job']+':'+d['finding']);result={'ok':True}
                else:self.reply(404,{'error':'Not found'});return
                self.reply(200,result)
            except PermissionError as exc:self.reply(403,{'error':str(exc)})
            except (ValueError,KeyError,FileNotFoundError,RuntimeError) as exc:self.reply(400,{'error':str(exc)})
            except Exception:self.reply(500,{'error':'Operation failed; check setup, unique names and supplied fields'})
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler);server.daemon_threads=True;return server
