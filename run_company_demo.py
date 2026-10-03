"""Run a disposable local demonstration without starting a server manually."""
import asyncio
import json
import threading
from pathlib import Path
from company.workflows import run
from company.load import run as load_run
from company.reports import save
from company.management import execute
from examples.company_demo import make_server

async def main():
    root=Path(__file__).resolve().parent
    server=make_server(0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        base=f'http://127.0.0.1:{server.server_port}'
        config=json.loads((root/'examples/company-workflows.json').read_text());config['base_url']=base
        output=root/'reports/company-demo'
        report=await run(config,root/'examples',output,allow_actions=True,workers=2)
        save(report,output)
        execute(root/'reports/company.db','import',report)
        cfg=json.loads((root/'examples/company-load.json').read_text());cfg['base_url']=base
        load=await load_run(cfg,allow_load=True);save(load,root/'reports/company-demo-load')
        print('Workflow: '+('PASS' if report['passed'] else 'NOT PASSED'))
        print('Load: '+('PASS' if load['passed'] else 'NOT PASSED'))
        print('Report: '+str(output/'report.html'))
        return int(not report['passed'] or not load['passed'])
    finally: server.shutdown();server.server_close();thread.join()
if __name__=='__main__':raise SystemExit(asyncio.run(main()))
