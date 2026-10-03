import json
import os
from pathlib import Path
import queue
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid
from .security import secret_get,redact

ROOT=Path(__file__).resolve().parents[1]

class Jobs:
    def __init__(self,store):
        self.store=store;self.root=store.root/'runs';self.root.mkdir(exist_ok=True)
        self.queue=queue.Queue(maxsize=20);self.lock=threading.Lock();self.process=None;self.active=None;self.cancelled=set()
        with store.db() as db:db.execute("UPDATE jobs SET status='INTERRUPTED',ended=? WHERE status IN ('QUEUED','RUNNING')",(time.time(),))
        threading.Thread(target=self.worker,daemon=True).start()
    def submit(self,user,pid,kind,actions=False,wid=None):
        project=self.store.project(user,pid,True)
        if kind not in ('scan','thorough','record','setup','benchmark'):raise ValueError('Unknown job type')
        if kind=='setup' and user['role']!='admin':raise PermissionError('Admin role required for installation')
        if kind=='record' and not actions:raise ValueError('Confirm authorized interaction before recording')
        if self.queue.full():raise ValueError('Job queue full')
        jid=uuid.uuid4().hex;out=self.root/jid;out.mkdir(mode=0o700)
        cfg=None
        if wid:
            with self.store.db() as db:row=db.execute('SELECT config FROM workflows WHERE id=? AND project=?',(wid,pid)).fetchone()
            if not row:raise ValueError('Workflow not in project')
            cfg=json.loads(row['config']);(out/'rules.json').write_text(json.dumps(cfg),encoding='utf-8')
        env={};needed=set()
        for journey in (cfg or {}).get('journeys',[]):
            for step in journey['steps']:
                if 'value_env' in step:needed.add(step['value_env'])
        for name in needed:env[name]=secret_get(self.store.vault_id(pid),name)
        cmd=[sys.executable]
        if kind=='record':cmd+=['-m','product.recorder',project['target'],str(out/'recording.json')]
        elif kind=='setup':cmd+=['-m','product.setup',str(out/'setup.log')]
        elif kind=='benchmark':cmd+=['-m','product.benchmark','--output',str(out/'benchmark')]
        else:
            cmd += [str(ROOT/('thorough.py' if kind=='thorough' else 'tester.py')),project['target'],'--output',str(out/'scan')]
            if kind=='scan':cmd+=['--max-pages','8','--repeats','3','--max-seconds','600']
            if actions:cmd+=['--allow-actions','--auto-fields','--explore-actions']
            if cfg:cmd+=['--config',str(out/'rules.json')]
        with self.store.db() as db:db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?)',(jid,pid,user['id'],kind,'QUEUED',time.time(),None,None,json.dumps(cmd)))
        self.store.audit(user['id'],'job-created',jid)
        self.queue.put_nowait((jid,cmd,env));return jid
    def get(self,user,jid,write=False):
        with self.store.db() as db:row=db.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone()
        if not row:raise ValueError('Unknown run')
        self.store.project(user,row['project'],write);result=dict(row);result.pop('command');return result
    def stop(self,user,jid):
        self.get(user,jid,True)
        with self.lock:
            self.cancelled.add(jid)
            if self.active==jid and self.process:self.terminate(self.process)
        self.store.audit(user['id'],'job-cancelled',jid)
    @staticmethod
    def terminate(process):
        if process.poll() is not None:return
        if os.name=='nt':subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=15)
        else:
            try:os.killpg(process.pid,signal.SIGTERM)
            except ProcessLookupError:pass
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            if os.name!='nt':
                try:os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:pass
            else:process.kill()
    def worker(self):
        while True:
            jid,cmd,private=self.queue.get();out=self.root/jid;code=None;status='ERROR'
            try:
                if jid in self.cancelled:status='CANCELLED';continue
                with self.store.db() as db:db.execute("UPDATE jobs SET status='RUNNING' WHERE id=?",(jid,))
                env=os.environ.copy();env.update(private);env['PYTHONUNBUFFERED']='1'
                process=subprocess.Popen(cmd,cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,errors='replace',start_new_session=os.name!='nt')
                with self.lock:
                    self.active=jid;self.process=process
                    if jid in self.cancelled:self.terminate(process)
                timer=threading.Timer(2100,lambda:self.terminate(process));timer.daemon=True;timer.start()
                with (out/'run.log').open('w',encoding='utf-8') as log:
                    for line in process.stdout:log.write(redact(line,private.values()));log.flush()
                code=process.wait();timer.cancel()
                status='CANCELLED' if jid in self.cancelled else 'COMPLETED' if code==0 else 'INCOMPLETE' if code in (1,2,3) else 'ERROR'
                # Text artifacts are sanitized before dashboard downloads are enabled. Binary traces may still contain credentials.
                def scrub(value):
                    if isinstance(value,dict):return {k:scrub(v) for k,v in value.items()}
                    if isinstance(value,list):return [scrub(v) for v in value]
                    if isinstance(value,str):
                        for secret in private.values():
                            if not secret:continue
                            if value==secret:return '[REDACTED]'
                            if len(secret)>=4:value=value.replace(secret,'[REDACTED]')
                        return value
                    return value
                for path in out.rglob('*.json'):
                    if path.stat().st_size<10_000_000:
                        try:data=scrub(json.loads(path.read_text(encoding='utf-8')))
                        except (ValueError,OSError):continue
                        path.write_text(json.dumps(data,indent=2),encoding='utf-8')
                        if path.name=='report.json' and 'score' in data and 'results' in data:
                            from qa.reporting import render
                            class SanitizedReport:
                                results=data['results']
                                def export(self):return data
                            render(SanitizedReport(),path.parent)
                        elif path.name=='completion.json':
                            from qa.completeness import save
                            save(data,path.parent)
                for path in out.rglob('*.log'):
                    if path.stat().st_size<10_000_000:path.write_text(redact(path.read_text(encoding='utf-8',errors='replace'),private.values()),encoding='utf-8')
            except Exception as exc:
                (out/'run.log').write_text('Execution error: '+type(exc).__name__+'; check Setup and dependencies.',encoding='utf-8')
            finally:
                private.clear()
                with self.lock:self.process=None;self.active=None
                with self.store.db() as db:db.execute('UPDATE jobs SET status=?,ended=?,exit_code=? WHERE id=?',(status,time.time(),code,jid))
                self.queue.task_done()
    def files(self,user,jid):
        job=self.get(user,jid)
        if job['status'] in ('QUEUED','RUNNING'):return []
        root=self.root/jid
        return [str(p.relative_to(root)).replace('\\','/') for p in root.rglob('*') if p.is_file() and p.name not in ('rules.json',) and (user['role']!='viewer' or p.suffix in ('.json','.log'))]
    def purge(self,user,days):
        if user['role']!='admin':raise PermissionError('Admin required')
        if not isinstance(days,int) or days<1:raise ValueError('Retention must be at least one day')
        with self.store.db() as db:rows=db.execute("SELECT id FROM jobs WHERE ended<? AND status NOT IN ('QUEUED','RUNNING','PURGED')",(time.time()-days*86400,)).fetchall()
        for row in rows:
            jid=row['id']
            if not re.fullmatch('[0-9a-f]{32}',jid):continue
            shutil.rmtree(self.root/jid,ignore_errors=False)
            with self.store.db() as db:db.execute("UPDATE jobs SET status='PURGED' WHERE id=?",(jid,))
        self.store.audit(user['id'],'retention-purge',str(len(rows)));return len(rows)
