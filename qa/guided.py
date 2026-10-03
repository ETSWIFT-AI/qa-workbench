"""Small no-JSON recipe builders shared by the CLI wizard and desktop GUI."""
import json
from pathlib import Path
from .core import validate_config


def age_rule(name,path,selector,minimum,maximum,required=True):
    low,high=int(minimum),int(maximum)
    if low>high: raise ValueError('Minimum cannot exceed maximum')
    values=[('',not required),('abc',False),(str(low-1),False),(str(low),True),(str(high),True),(str(high+1),False),(str(low)+'.5',False)]
    return {'name':name,'path':path,'selector':selector,'cases':[{'value':v,'accepted':a} for v,a in values]}


def navigation_rule(name,path,selector,destination,critical=True):
    return {'name':name,'path':path,'critical':critical,'steps':[{'action':'click','selector':selector},{'action':'url','value':destination}]}


def api_rule(name,path,status,authorization=False,role='anonymous'):
    rule={'name':name,'path':path,'expected_status':int(status)}
    if authorization: rule.update(authorization_test=True,role=role)
    return rule


def save_config(path,cfg,base):
    validate_config(cfg,base)
    Path(path).write_text(json.dumps(cfg,indent=2),encoding='utf-8')


def wizard():
    from tester import parse_args
    import asyncio
    from .runner import run
    url=input('Website URL: ').strip()
    mode=input('Mode: 1 = read-only, 2 = authorized staging actions [1]: ').strip()
    cfg={}; output=input('Save rules to [my-rules.json]: ').strip() or 'my-rules.json'
    while True:
        choice=input('Add test: 1 navigation, 2 integer age range, 3 API status, Enter to finish: ').strip()
        if not choice: break
        name=input('Test name: ').strip();path=input('Starting path [/]: ').strip() or '/'
        if choice=='1': cfg.setdefault('journeys',[]).append(navigation_rule(name,path,input('Button/link CSS selector: ').strip(),input('Expected destination path: ').strip()))
        elif choice=='2': cfg.setdefault('fields',[]).append(age_rule(name,path,input('Age field CSS selector: ').strip(),input('Minimum age: '),input('Maximum age: ')))
        elif choice=='3': cfg.setdefault('api_tests',[]).append(api_rule(name,path,input('Expected HTTP status: ')))
        else: print('Unknown choice')
    save_config(output,cfg,url)
    argv=[url,'--config',output]
    if mode=='2': argv+=['--allow-actions','--auto-fields','--explore-actions']
    return asyncio.run(run(parse_args(argv)))
