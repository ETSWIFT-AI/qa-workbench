"""Optional CrUX field data. Never blend field data with lab observations."""
import json
import os
import urllib.request
import urllib.error
import urllib.parse
from .core import origin,load_json


def validate_record(data,base):
    record=data.get('record',{})
    key=record.get('key',{})
    target=key.get('url') or key.get('origin')
    if not target or origin(target)!=origin(base): raise ValueError('CrUX record does not match target origin')
    metrics=record.get('metrics',{})
    if not isinstance(metrics,dict) or not metrics: raise ValueError('CrUX record has no metrics')
    return {'status':'available','source':'Chrome UX Report (real-user field data)','key':key,'collectionPeriod':record.get('collectionPeriod'),
       'metrics':metrics,'note':'Aggregated Chrome population over the returned collection period; not this run, not all users, and not a substitute for application-specific testing.'}


def field_metrics(args,base):
    try:
        if args.crux_file: return validate_record(load_json(args.crux_file),base)
        if not args.crux_key_env: return {'status':'not_requested','note':'No field-performance data; reported browser timings are local lab samples only.'}
        key=os.environ.get(args.crux_key_env)
        if not key: raise ValueError('Configured CrUX key environment variable is missing')
        scheme,host,port=origin(base)
        authority=('['+host+']') if ':' in host else host
        target=f'{scheme}://{authority}'+('' if port==(443 if scheme=='https' else 80) else f':{port}')
        url='https://chromeuxreport.googleapis.com/v1/records:queryRecord?'+urllib.parse.urlencode({'key':key})
        req=urllib.request.Request(url,data=json.dumps({'origin':target,'metrics':['largest_contentful_paint','cumulative_layout_shift','interaction_to_next_paint']}).encode(),headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=30) as response: data=json.load(response)
        return validate_record(data,base)
    except urllib.error.HTTPError as exc:
        return {'status':'unavailable','reason':f'CrUX HTTP {exc.code}; target may lack eligible field data or API access. Not a website failure.'}
    except Exception as exc: return {'status':'unavailable','reason':str(exc)}
