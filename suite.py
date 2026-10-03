"""Bounded parallel, shardable external test runner. Runs trusted local commands only."""
import argparse
import concurrent.futures
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import xml.etree.ElementTree as ET


def run_job(job,root,out):
    name=job['name']; log=out/(name+'.log'); started=time.monotonic(); started_wall=time.time()
    env=os.environ.copy(); env.update({k:str(v) for k,v in job.get('env',{}).items()})
    for key in job.get('required_env',[]):
        if key not in env: return {'name':name,'status':'ERROR','detail':'Missing environment variable '+key}
    cwd=(root/job.get('cwd','.')).resolve()
    if not cwd.is_relative_to(root): raise ValueError('Job cwd outside suite directory')
    try:
        with log.open('w',encoding='utf-8') as stream:
            proc=subprocess.Popen(job['command'],cwd=cwd,env=env,stdout=stream,stderr=subprocess.STDOUT,start_new_session=os.name!='nt')
            try: code=proc.wait(timeout=job.get('timeout_seconds',600))
            except subprocess.TimeoutExpired:
                if os.name=='nt': subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                else:
                    try: os.killpg(proc.pid,signal.SIGKILL)
                    except ProcessLookupError: pass
                proc.wait(); return {'name':name,'status':'ERROR','detail':'Timeout; process tree terminated','log':log.name}
        # Optional JUnit verifies that a command actually executed tests.
        count=failures=errors=skipped=0
        if job.get('junit'):
            files=list(cwd.glob(job['junit']))
            if not files: raise ValueError('Configured JUnit reports were not produced')
            for file in files:
                if file.stat().st_mtime<started_wall: raise ValueError('Stale JUnit report: '+str(file))
                tree=ET.parse(file)
                for case in tree.iter('testcase'):
                    count+=1; failures+=case.find('failure') is not None; errors+=case.find('error') is not None; skipped+=case.find('skipped') is not None
            if not count or count==skipped: raise ValueError('No completed JUnit test cases')
        status='ERROR' if errors else 'FAIL' if code or failures else 'PASS'
        return {'name':name,'status':status,'exit_code':code,'seconds':round(time.monotonic()-started,2),'tests':count,'skipped':skipped,'log':log.name,'basis':'JUnit and process exit' if job.get('junit') else 'Process exit only; no test coverage inferred'}
    except Exception as exc: return {'name':name,'status':'ERROR','detail':str(exc),'log':log.name}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('manifest'); p.add_argument('--workers',type=int,default=2); p.add_argument('--shard-index',type=int,default=0); p.add_argument('--shard-count',type=int,default=1); p.add_argument('--output',default='reports/suite'); p.add_argument('--allow-commands',action='store_true'); a=p.parse_args(argv)
    if not a.allow_commands: p.error('Review the manifest, then use --allow-commands to execute its local programs')
    if not 1<=a.workers<=32 or not 0<=a.shard_index<a.shard_count: p.error('Invalid workers or shard')
    manifest=Path(a.manifest).resolve(); jobs=json.loads(manifest.read_text())['jobs']; names=set()
    import re
    for job in jobs:
        name=job.get('name','')
        if not re.fullmatch(r'[A-Za-z0-9_-]+',name) or name in names: p.error('Job names must be unique safe filenames')
        names.add(name)
        if not isinstance(job.get('command'),list) or not job['command'] or any(not isinstance(x,str) for x in job['command']): p.error('command must be a nonempty string array')
        if not 1<=job.get('timeout_seconds',600)<=86400: p.error('Invalid timeout')
    selected=[job for i,job in enumerate(jobs) if i%a.shard_count==a.shard_index]
    if not selected: p.error('Shard has no jobs')
    out=Path(a.output).resolve(); out.mkdir(parents=True,exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
        rows=list(pool.map(lambda job:run_job(job,manifest.parent,out),selected))
    (out/'suite.json').write_text(json.dumps({'shard':a.shard_index,'shards':a.shard_count,'results':rows},indent=2))
    xml=ET.Element('testsuite',name='External suites',tests=str(len(rows)),failures=str(sum(r['status']=='FAIL' for r in rows)),errors=str(sum(r['status']=='ERROR' for r in rows)))
    for row in rows:
        case=ET.SubElement(xml,'testcase',name=row['name'])
        if row['status']!='PASS': ET.SubElement(case,'error' if row['status']=='ERROR' else 'failure').text=json.dumps(row)
    ET.ElementTree(xml).write(out/'junit.xml',encoding='utf-8',xml_declaration=True)
    print(json.dumps(rows,indent=2)); return int(any(r['status']!='PASS' for r in rows))
if __name__=='__main__': raise SystemExit(main())
