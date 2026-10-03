import asyncio
import json
import os
from pathlib import Path
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import pytest
from company.data import expand, rows, substitute
from company.evidence import assess
from company.management import execute
from company.workflows import check, run, scoped
from company.load import run as load_run
from examples.company_demo import make_server
ROOT=Path(__file__).resolve().parents[1]
BROWSER=pytest.mark.skipif(os.environ.get('QA_COMPANY_BROWSER_TESTS')!='1',reason='Opt in to browser tests')
def config(url):
    cfg=json.loads((ROOT/'examples/company-workflows.json').read_text());cfg['base_url']=url
    cfg['viewports']={'desktop':{'width':1000,'height':700}}
    cfg['browsers']=os.environ.get('QA_TEST_BROWSERS','chromium').split(',')
    return cfg
@pytest.fixture
def demo():
    servers=[]
    def create(broken=False):
        server=make_server(0,broken);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();servers.append((server,thread))
        return server,f'http://127.0.0.1:{server.server_port}'
    yield create
    for server,thread in servers:server.shutdown();server.server_close();thread.join()
def test_typed_substitution_and_blocks(tmp_path):
    assert substitute({'n':'${n}','x':'row-${n}'},{'n':2})=={'n':2,'x':'row-2'}
    cfg={'datasets':{'a':[{'n':1},{'n':2}]},'blocks':{'b':[{'action':'assert','actual':'${n}','expected':1}]},'tests':[{'name':'case','dataset':'a','steps':[{'use':'b'}]}]}
    assert len(expand(cfg,tmp_path))==2
    cfg['blocks']['b']=[{'use':'b'}]
    with pytest.raises(ValueError,match='Recursive'):expand(cfg,tmp_path)
def test_dataset_scope_and_assertion_requirement(tmp_path):
    with pytest.raises(ValueError):rows('../outside.csv',tmp_path)
    with pytest.raises(ValueError):expand({'tests':[{'name':'empty','steps':[{'action':'goto','url':'/'}]}]},tmp_path)
    with pytest.raises(ValueError):scoped('https://example.org','https://other.org')
    with pytest.raises(AssertionError):check([1,2],'count',1)
def test_excel_dataset(tmp_path):
    openpyxl=pytest.importorskip('openpyxl');book=openpyxl.Workbook();book.active.append(['age']);book.active.append([18]);book.save(tmp_path/'ages.xlsx');book.close()
    assert rows('ages.xlsx',tmp_path)==[{'age':18}]
def test_management_audit_and_reviews(tmp_path):
    path=tmp_path/'qa.db';execute(path,'case',{'id':'1','name':'Order','owner':'A','priority':'critical','requirement':'exactly one'})
    execute(path,'review',{'case_id':'1','reviewer':'A','state':'open','note':'Check backend'})
    result=execute(path,'review',{'case_id':'1','reviewer':'B','state':'retest','note':'Fix ready'})
    assert len(result['reviews'])==2
    with pytest.raises(ValueError):execute(path,'review',{'case_id':'missing','reviewer':'B','state':'fixed','note':'x'})
    assert not assess({})['passed']
    with pytest.raises(ValueError):assess({'checks':{'keyboard':{'status':'PASS'}}})
@BROWSER
def test_backend_exact_once_and_cleanup(demo,tmp_path):
    server,url=demo();report=asyncio.run(run(config(url),ROOT/'examples',tmp_path,True,2))
    assert report['passed'],report
    assert not server.orders
    assert all((tmp_path/r['trace']).exists() for r in report['results'])
@BROWSER
def test_duplicate_bug_detected_and_cleanup_still_runs(demo,tmp_path):
    server,url=demo(True);report=asyncio.run(run(config(url),ROOT/'examples',tmp_path,True,2))
    assert not report['passed']
    orders=[r for r in report['results'] if r['name'].startswith('Order')]
    assert all(r['status']=='FAIL' for r in orders),report
    assert all(r['cleanup'] and all(c['status']=='PASS' for c in r['cleanup']) for r in orders)
    assert not server.orders
@BROWSER
def test_mutation_requires_opt_in(demo,tmp_path):
    server,url=demo();report=asyncio.run(run(config(url),ROOT/'examples',tmp_path,False,2))
    assert not report['passed'] and not server.orders
    assert any(r.get('error',{}).get('type')=='PermissionError' for r in report['results'])
@BROWSER
def test_cleanup_failure_is_error(demo,tmp_path):
    server,url=demo();cfg=config(url);cfg['tests']=[{'name':'cleanup failure','steps':[{'action':'assert','actual':1,'expected':1}],'cleanup':[{'action':'request','url':'/missing','expect_status':200}]}]
    report=asyncio.run(run(cfg,ROOT/'examples',tmp_path,True))
    assert all(r['status']=='ERROR' and r['cleanup'][0]['status']=='ERROR' for r in report['results'])
@BROWSER
def test_load_is_concurrent_and_budget_failures_are_reported():
    lock=threading.Lock();state={'active':0,'peak':0}
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            with lock:state['active']+=1;state['peak']=max(state['peak'],state['active'])
            time.sleep(.15)
            with lock:state['active']-=1
            self.send_response(200);self.end_headers();self.wfile.write(b'ok')
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        cfg={'base_url':f'http://127.0.0.1:{server.server_port}','users':3,'requests':9,'rps':30,'max_p95_ms':1}
        report=asyncio.run(load_run(cfg,True))
        assert report['completed']==9 and report['status']=='FAIL' and state['peak']>=2
        with pytest.raises(PermissionError):asyncio.run(load_run(cfg,False))
    finally:server.shutdown();server.server_close();thread.join()
def test_mobile_adapter_asserts():
    from mobile import execute as mobile_execute
    class Element:
        text='Ready'
        def is_displayed(self):return True
    class Driver:
        def find_element(self,*args):return Element()
    mobile_execute(Driver(),[{'action':'visible','by':'id','selector':'heading'},{'action':'text','by':'id','selector':'heading','value':'Ready'}])
    with pytest.raises(AssertionError):mobile_execute(Driver(),[{'action':'text','by':'id','selector':'heading','value':'Wrong'}])

def test_security_failure_and_execution_error(tmp_path,monkeypatch):
    import company.security as sec
    from types import SimpleNamespace
    (tmp_path/'package-lock.json').write_text('{}')
    monkeypatch.setattr(sec.shutil,'which',lambda name:'npm')
    monkeypatch.setattr(sec.subprocess,'run',lambda *a,**k:SimpleNamespace(returncode=1,stdout='{"metadata":{"vulnerabilities":{"total":2}}}'))
    report=sec.dependency_scan(tmp_path,['npm'],tmp_path/'out')
    assert report['results'][0]['status']=='FAIL'
    monkeypatch.setattr(sec.subprocess,'run',lambda *a,**k:SimpleNamespace(returncode=1,stdout='{"error":{"message":"offline"}}'))
    assert sec.dependency_scan(tmp_path,['npm'],tmp_path/'out')['results'][0]['status']=='ERROR'

def test_external_runner_detects_junit_failure_and_stale_report(tmp_path):
    import sys
    from suite import run_job
    job={'name':'fail','command':[sys.executable,'-c',"from pathlib import Path;Path('test.xml').write_text('<testsuite><testcase name=\"bad\"><failure/></testcase></testsuite>')"],'junit':'test.xml'}
    result=run_job(job,tmp_path,tmp_path)
    assert result['status']=='FAIL' and result['tests']==1
    job['command']=[sys.executable,'-c','pass']
    result=run_job(job,tmp_path,tmp_path)
    assert result['status']=='ERROR' and 'Stale' in result['detail']

@BROWSER
def test_repeated_mixed_results_are_flaky(demo,tmp_path):
    server,url=demo();cfg=config(url)
    cfg['tests']=[{'name':'flaky','steps':[{'action':'request','url':'/api/admin','headers':{'X-Role':'${role}'},'expect_status':200}], 'variables':{'role':'admin'}}]
    # A request endpoint with a deterministic alternating outcome verifies repeat classification.
    old=server.RequestHandlerClass.do_GET
    counter={'n':0}
    def alternating(handler):
        if handler.path=='/api/admin':
            counter['n']+=1;handler.send(200 if counter['n']%2 else 403,{});return
        old(handler)
    server.RequestHandlerClass.do_GET=alternating
    report=asyncio.run(run(cfg,ROOT/'examples',tmp_path,True,1,2))
    assert report['flaky'] and not report['passed']
