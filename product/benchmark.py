"""Known-good and deliberately broken local order fixtures; no universal accuracy claim."""
import argparse
import asyncio
import json
from pathlib import Path
import threading
from company.workflows import run
from company.reports import save
from examples.company_demo import make_server

async def evaluate(output):
    root=Path(__file__).resolve().parents[1];out=Path(output);out.mkdir(parents=True,exist_ok=True);cases=[]
    for broken in (False,True):
        server=make_server(0,broken);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            cfg=json.loads((root/'examples/company-workflows.json').read_text());cfg['base_url']=f'http://127.0.0.1:{server.server_port}'
            cfg['viewports']={'desktop':{'width':1200,'height':800}}
            cfg['tests']=[cfg['tests'][0]]
            report=await run(cfg,root/'examples',out/('broken' if broken else 'healthy'),True,1,2)
            save(report,out/('broken' if broken else 'healthy'))
            statuses=[r['status'] for r in report['results']]
            detected=any(s=='FAIL' for s in statuses);execution_ok=all(s in ('PASS','FAIL') for s in statuses)
            cases.append({'fixture':'duplicate-order bug' if broken else 'healthy order service','known_defect':broken,'detected_failure':detected,'execution_ok':execution_ok,'cleaned_up':not server.orders,'flaky':report['flaky'], 'matched_expectation':execution_ok and all(s==('FAIL' if broken else 'PASS') for s in statuses) and not report['flaky'] and not server.orders})
        finally:server.shutdown();server.server_close();thread.join()
    result={'cases':cases,'passed':all(c['matched_expectation'] for c in cases),'false_positive_fixtures':sum(c['detected_failure'] and not c['known_defect'] for c in cases if c['execution_ok']), 'missed_defect_fixtures':sum(not c['detected_failure'] and c['known_defect'] for c in cases if c['execution_ok']), 'inconclusive_fixtures':sum(not c['execution_ok'] for c in cases),'limitation':'Two local order fixtures only; not an industry accuracy benchmark or security/accessibility coverage estimate.'}
    (out/'benchmark.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2));return 0 if result['passed'] else 1
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',default='reports/benchmark');a=p.parse_args();raise SystemExit(asyncio.run(evaluate(a.output)))
