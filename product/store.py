import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time

ROLES={'viewer':0,'tester':1,'admin':2}

def password_hash(password, salt=None):
    if len(password)<12: raise ValueError('Use a password of at least 12 characters')
    salt=salt or secrets.token_hex(16)
    digest=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),300000).hex()
    return salt+':'+digest

def verify(password, stored):
    try:
        salt,digest=stored.split(':')
        actual=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),300000).hex()
        return hmac.compare_digest(digest,actual)
    except (ValueError,TypeError): return False

class Store:
    def __init__(self,root):
        self.root=Path(root).resolve();self.root.mkdir(parents=True,exist_ok=True)
        try:self.root.chmod(0o700)
        except OSError:pass
        identity=self.root/'instance-id'
        if not identity.exists():identity.write_text(secrets.token_hex(16),encoding='ascii')
        self.namespace=identity.read_text(encoding='ascii').strip()
        self.path=self.root/'product.sqlite3'
        with self.db() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT UNIQUE, password TEXT, role TEXT);
            CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id INTEGER,csrf TEXT,expires REAL);
            CREATE TABLE IF NOT EXISTS projects(id INTEGER PRIMARY KEY,name TEXT,target TEXT,owner INTEGER);
            CREATE TABLE IF NOT EXISTS members(project INTEGER,user_id INTEGER,PRIMARY KEY(project,user_id));
            CREATE TABLE IF NOT EXISTS workflows(id INTEGER PRIMARY KEY,project INTEGER,name TEXT,config TEXT,updated REAL);
            CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,project INTEGER,owner INTEGER,kind TEXT,status TEXT,created REAL,ended REAL,exit_code INTEGER,command TEXT);
            CREATE TABLE IF NOT EXISTS reviews(id INTEGER PRIMARY KEY,job TEXT,finding TEXT,owner TEXT,state TEXT,note TEXT,reviewer INTEGER,created REAL);
            CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,user_id INTEGER,action TEXT,detail TEXT,created REAL);
            ''')
        try:self.path.chmod(0o600)
        except OSError:pass
    def vault_id(self,pid):return self.namespace+':'+str(pid)
    def db(self):
        db=sqlite3.connect(self.path,timeout=15);db.row_factory=sqlite3.Row;return db
    def audit(self,user,action,detail=''):
        with self.db() as db:db.execute('INSERT INTO audit(user_id,action,detail,created) VALUES(?,?,?,?)',(user,action,detail,time.time()))
    def create_user(self,name,password,role='viewer'):
        if not re.fullmatch(r'[A-Za-z0-9_.-]{2,40}',name) or role not in ROLES:raise ValueError('Invalid username or role')
        encoded=password_hash(password)
        with self.db() as db:return db.execute('INSERT INTO users(name,password,role) VALUES(?,?,?)',(name,encoded,role)).lastrowid
    def login(self,name,password):
        with self.db() as db:
            row=db.execute('SELECT * FROM users WHERE name=?',(name,)).fetchone()
            valid=verify(password,row['password'] if row else '00'*16+':'+'00'*32)
            if not row or not valid:raise PermissionError('Invalid login')
            token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32)
            db.execute('DELETE FROM sessions WHERE expires<?',(time.time(),))
            db.execute('INSERT INTO sessions VALUES(?,?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),row['id'],csrf,time.time()+8*3600))
        self.audit(row['id'],'login');return token,csrf
    def session(self,token):
        digest=hashlib.sha256(token.encode()).hexdigest()
        with self.db() as db:
            row=db.execute('SELECT users.id,users.name,users.role,sessions.csrf FROM sessions JOIN users ON users.id=sessions.user_id WHERE token=? AND expires>?',(digest,time.time())).fetchone()
        return dict(row) if row else None
    def logout(self,token):
        with self.db() as db:db.execute('DELETE FROM sessions WHERE token=?',(hashlib.sha256(token.encode()).hexdigest(),))
    def project(self,user,pid,write=False):
        if write and ROLES[user['role']]<1:raise PermissionError('Tester role required')
        with self.db() as db:
            row=db.execute('SELECT * FROM projects WHERE id=?',(pid,)).fetchone()
            if row and (user['role']=='admin' or row['owner']==user['id'] or db.execute('SELECT 1 FROM members WHERE project=? AND user_id=?',(pid,user['id'])).fetchone()):return dict(row)
        raise PermissionError('Project not accessible')
    def projects(self,user):
        with self.db() as db:
            if user['role']=='admin':rows=db.execute('SELECT * FROM projects').fetchall()
            else:rows=db.execute('SELECT DISTINCT p.* FROM projects p LEFT JOIN members m ON p.id=m.project WHERE p.owner=? OR m.user_id=?',(user['id'],user['id'])).fetchall()
        return [dict(r) for r in rows]
    def add_project(self,user,name,target):
        if ROLES[user['role']]<1:raise PermissionError('Tester role required')
        from qa.core import canonical
        target=canonical(target)
        if not 1<=len(name)<=100:raise ValueError('Project name needs 1–100 characters')
        with self.db() as db:pid=db.execute('INSERT INTO projects(name,target,owner) VALUES(?,?,?)',(name,target,user['id'])).lastrowid
        self.audit(user['id'],'project-created',str(pid));return pid
    def grant(self,user,pid,username):
        project=self.project(user,pid,True)
        if user['role']!='admin' and project['owner']!=user['id']:raise PermissionError('Project owner required')
        with self.db() as db:
            member=db.execute('SELECT id FROM users WHERE name=?',(username,)).fetchone()
            if not member:raise ValueError('Unknown user')
            db.execute('INSERT OR IGNORE INTO members VALUES(?,?)',(pid,member['id']))
        self.audit(user['id'],'member-added',str(pid)+':'+username)
    def revoke(self,user,pid,username):
        project=self.project(user,pid,True)
        if user['role']!='admin' and project['owner']!=user['id']:raise PermissionError('Project owner required')
        with self.db() as db:
            member=db.execute('SELECT id FROM users WHERE name=?',(username,)).fetchone()
            if not member:raise ValueError('Unknown user')
            if member['id']==project['owner']:raise ValueError('Project owner retains access')
            db.execute('DELETE FROM members WHERE project=? AND user_id=?',(pid,member['id']))
        self.audit(user['id'],'member-removed',str(pid)+':'+username)
    def reset_password(self,user,username,password):
        if user['role']!='admin':raise PermissionError('Admin role required')
        hashed=password_hash(password)
        with self.db() as db:
            row=db.execute('SELECT id FROM users WHERE name=?',(username,)).fetchone()
            if not row:raise ValueError('Unknown user')
            db.execute('UPDATE users SET password=? WHERE id=?',(hashed,row['id']))
            db.execute('DELETE FROM sessions WHERE user_id=?',(row['id'],))
        self.audit(user['id'],'password-reset',username)
    def workflow(self,user,pid,name,config):
        project=self.project(user,pid,True)
        from qa.core import validate_config
        if not isinstance(name,str) or not 1<=len(name)<=100:raise ValueError('Workflow name required')
        validate_config(config,project['target'])
        if not config.get('journeys'):raise ValueError('Add a journey with at least one assertion')
        for journey in config['journeys']:
            if 'storage_state' in journey:raise ValueError('Dashboard does not accept arbitrary storage-state paths')
            for step in journey['steps']:
                if step.get('action')=='fill' and 'value_env' not in step:raise ValueError('Fill values must use value_env; store private values in the OS keyring')
        # Dashboard authoring scope is UI journeys. API secrets/state files require reviewed CLI setup.
        if set(config)-{'journeys','fields','exclude_paths','session_cookie_names'}:raise ValueError('Dashboard supports UI journey/field configurations; use CLI for external evidence/API configuration')
        for field in config.get('fields',[]):
            if 'storage_state' in field:raise ValueError('Storage-state paths are not accepted here')
        with self.db() as db:wid=db.execute('INSERT INTO workflows(project,name,config,updated) VALUES(?,?,?,?)',(pid,name,json.dumps(config),time.time())).lastrowid
        self.audit(user['id'],'workflow-created',str(wid));return wid
