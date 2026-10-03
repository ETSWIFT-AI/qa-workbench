"""Optional autonomous observation + from-scratch ML research layer. Old tester.py remains unchanged."""
import argparse
import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime
import uuid


def validate_url(value):
    from urllib.parse import urlsplit,unquote
    value=value.strip()
    if any(c.isspace() for c in value) or any(c.isspace() for c in unquote(urlsplit(value).netloc)):
        raise ValueError('URL contains spaces. Example: https://badssl.com/')
    from qa.core import canonical
    return canonical(value)

async def assess(report_file,output,model=None,source=None,observe=True,ui_model=None,autonomous=None):
    from advanced.report import render
    from advanced.planner import plan
    from advanced.source import inspect_source
    report=json.loads(Path(report_file).read_text(encoding='utf-8'));out=Path(output);out.mkdir(parents=True,exist_ok=True)
    observed={'rows':[],'ui':[],'client_map':[],'errors':[]}
    if observe:
        from advanced.observe import collect
        try:observed=await asyncio.wait_for(collect(report_file,out),timeout=150)
        except Exception as exc:observed['errors'].append({'reason':type(exc).__name__+': '+str(exc)[:1000]})
        (out/'observations.json').write_text(json.dumps(observed,indent=2),encoding='utf-8')
    elif (out/'observations.json').is_file():observed=json.loads((out/'observations.json').read_text())
    if not observed['rows']:
        prediction={'status':'NOT_ASSESSED','reason':'No complete multimodal observations; no neural or UI score fabricated'}
    else:
        from advanced.learning import predict
        try:prediction=await asyncio.to_thread(predict,observed['rows'],out,model)
        except Exception as exc:prediction={'status':'UNAVAILABLE','reason':str(exc)}
    data={'version':'advanced-0.1.0','scope':'Research add-on to the unchanged v3.1 tester. Technical UI checklist is not a beauty rating. Neural outputs never change deterministic test results or the release gate. No pretrained models used by this layer.','ui':observed['ui'],'model':prediction,'plan':plan(report,observed),'client_map':observed['client_map'],'errors':observed['errors'],'source':inspect_source(source) if source else {'status':'NOT_SUPPLIED','note':'Backend logic cannot be reconstructed from a public URL alone.'}}
    if ui_model:
        try:
            from advanced.ui_learning import predict as predict_ui
            data['ui_model']=await asyncio.to_thread(predict_ui,observed['rows'],out,ui_model) if observed['rows'] else {'status':'NOT_ASSESSED','reason':'No screenshots'}
        except Exception as exc:data['ui_model']={'status':'UNAVAILABLE','reason':str(exc)}
    if autonomous is not None:
        from advanced.autonomous import explore_site
        data['autonomous']=await explore_site(autonomous['url'],out/'autonomous',**autonomous['options'])
        for finding in data['autonomous']['findings']:
            if finding['status']=='ERROR':data['errors'].append({'autonomous':finding['kind'],'reason':finding['detail']})
    render(data,out);print('Advanced report:',(out/'advanced-report.html').resolve());return data


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    scan=sub.add_parser('scan');scan.add_argument('url');scan.add_argument('--output');scan.add_argument('--model');scan.add_argument('--ui-model');scan.add_argument('--source-dir')
    scan.add_argument('--autonomous',action='store_true')
    scan.add_argument('--autonomous-actions',action='store_true',help='Recognized UI clicks and supplied-credential login on an authorized test target')
    scan.add_argument('--agent-actions',type=int,default=20)
    scan.add_argument('--agent-states',type=int,default=12)
    scan.add_argument('--agent-seconds',type=int,default=120)
    ana=sub.add_parser('analyse');ana.add_argument('report');ana.add_argument('--model');ana.add_argument('--ui-model');ana.add_argument('--source-dir');ana.add_argument('--collect-ui',action='store_true')
    tr=sub.add_parser('train');tr.add_argument('dataset');tr.add_argument('--output',required=True);tr.add_argument('--epochs',type=int,default=30);tr.add_argument('--seed',type=int,default=42);tr.add_argument('--batch-size',type=int,default=16)
    label=sub.add_parser('label');label.add_argument('dataset');label.add_argument('--id',required=True);label.add_argument('--ui-score',type=float,required=True);label.add_argument('--defect',choices=['yes','no'],required=True);label.add_argument('--reviewer',required=True);label.add_argument('--group',help='Independent site/project identity; same site must always keep the same group')
    merge=sub.add_parser('combine');merge.add_argument('datasets',nargs='+');merge.add_argument('--output',required=True)
    demo=sub.add_parser('smoke-data');demo.add_argument('--output',required=True)
    args,extra=p.parse_known_args(argv)
    if extra and args.command!='scan':p.error('Unknown arguments: '+' '.join(extra))
    if args.command=='scan':
        from tester import parse_args
        from qa.runner import run
        url=validate_url(args.url);out=Path(args.output or ('reports/advanced-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6]))
        old=parse_args([url,'--output',str(out)]+extra)
        if any(getattr(old,k) for k in ('ai_model','vision_model','embedding_model','triage_model')):p.error('Advanced scratch mode does not invoke pretrained/external models. Use the original tester separately for those optional features.')
        if min(args.agent_actions,args.agent_states,args.agent_seconds)<1:p.error('Agent budgets must be positive')
        import os
        agent={'url':url,'options':{'allow_actions':args.autonomous_actions,'username':os.environ.get('QA_TEST_USERNAME'),'password':os.environ.get('QA_TEST_PASSWORD'),'max_actions':args.agent_actions,'max_states':args.agent_states,'max_seconds':args.agent_seconds}} if args.autonomous or args.autonomous_actions else None
        result=asyncio.run(run(old));data=asyncio.run(assess(out/'report.json',out/'advanced',args.model,args.source_dir,ui_model=args.ui_model,autonomous=agent));return result or (2 if data['errors'] else 0)
    if args.command=='analyse':asyncio.run(assess(args.report,Path(args.report).parent/'advanced',args.model,args.source_dir,args.collect_ui,args.ui_model));return 0
    if args.command=='train':
        from advanced.learning import train
        metadata=train(args.dataset,args.output,args.epochs,args.seed,args.batch_size);print(json.dumps(metadata['metrics'],indent=2));print('Eligible for advisory:',metadata['eligible_for_advisory']);return 0
    if args.command=='label':
        if not 0<=args.ui_score<=100 or not args.reviewer.strip():p.error('UI score must be 0–100; reviewer required')
        path=Path(args.dataset);rows=[json.loads(line) for line in path.read_text().splitlines() if line.strip()];matched=False
        for row in rows:
            if row['id']==args.id:
                row['labels']={'ui_score':args.ui_score,'defect':args.defect=='yes'};row['reviewer']=args.reviewer
                if args.group:row['group']=args.group
                matched=True
        if not matched:p.error('Record ID not found')
        path.write_text('\n'.join(json.dumps(r) for r in rows)+'\n',encoding='utf-8');print('Saved reviewed labels');return 0
    if args.command=='combine':
        from advanced.data import load_records,safe_image
        import shutil,hashlib
        out=Path(args.output);out.mkdir(parents=True,exist_ok=True);rows=[];seen=set()
        for source in args.datasets:
            path=Path(source)
            for row in load_records(path):
                image=safe_image(path.parent,row['image']);digest=hashlib.sha256(image.read_bytes()).hexdigest()
                if digest in seen:raise ValueError('Duplicate screenshot across input datasets; remove duplicates before training')
                seen.add(digest);name=digest+image.suffix;shutil.copy2(image,out/name);row['image']=name;rows.append(row)
        (out/'dataset.jsonl').write_text('\n'.join(json.dumps(r) for r in rows)+'\n');print(out/'dataset.jsonl');return 0
    if args.command=='smoke-data':
        from advanced.synthetic import generate
        generate(args.output);print('Synthetic plumbing data only; resulting model is barred from assessment');return 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except (ValueError,KeyError,FileNotFoundError,ModuleNotFoundError) as exc:raise SystemExit('Advanced setup/data error: '+str(exc))
