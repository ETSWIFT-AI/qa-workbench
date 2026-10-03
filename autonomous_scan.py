"""Config-free launcher; asks for credentials only after a login form is detected."""
import asyncio
import getpass
import json
from pathlib import Path
import runpy
import subprocess
import sys
from datetime import datetime
import uuid

ROOT=Path(__file__).resolve().parent
if __name__=='__main__':
    print('Autonomous test exploration: recognized navigation/disclosure actions and GET searches.')
    print('Use a website you are authorized to test. Purchases/deletion/message sending are excluded.')
    url=input('Website URL: ').strip()
    out=ROOT/'reports'/('autonomous-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6])
    ui=ROOT/'models/calista_ui' if (ROOT/'models/calista_ui/ui-model.json').is_file() else None
    command=[sys.executable,str(ROOT/'advanced.py'),'scan',url,'--autonomous-actions','--output',str(out)]
    if ui:command+=['--ui-model',str(ui)]
    code=subprocess.call(command,cwd=ROOT)
    report=out/'advanced/advanced-report.json'
    if report.exists():
        data=json.loads(report.read_text(encoding='utf-8'))
        questions=data.get('autonomous',{}).get('questions',[])
        if any('Supply a test username' in q for q in questions):
            print('A login form was detected. Credentials are needed only for that flow.')
            username=input('Test username (Enter skips authentication): ').strip()
            if username:
                password=getpass.getpass('Test password (hidden): ')
                if password:
                    cli=runpy.run_path(str(ROOT/'advanced.py'),run_name='advanced_cli')
                    asyncio.run(cli['assess'](out/'report.json',out/'advanced',observe=False,ui_model=str(ui) if ui else None,autonomous={'url':cli['validate_url'](url),'options':{'allow_actions':True,'username':username,'password':password}}))
                    password=None
        print('Open:',out/'advanced/advanced-report.html')
    raise SystemExit(code)
