import hashlib
import json
from pathlib import Path
from .core import load_json, origin


def visual_compare(screenshot,baseline_dir,report,url,variant,threshold):
    name=Path(screenshot).name
    if not baseline_dir:
        report.add('visual_regression',variant,'SKIP','No approved screenshot baseline',url); return
    baseline=Path(baseline_dir)/name
    if not baseline.is_file():
        report.add('visual_regression',variant,'SKIP','Baseline missing: '+name,url); return
    try:
        from PIL import Image, ImageChops
        import numpy as np
        a,b=Image.open(baseline).convert('RGB'),Image.open(screenshot).convert('RGB')
        if a.size!=b.size:
            report.add('visual_regression',variant,'REVIEW',f'Size changed {a.size} -> {b.size}',url); return
        pixels=np.asarray(ImageChops.difference(a,b))
        fraction=float((pixels.max(axis=2)>25).mean())
        changed=fraction>threshold
        diff=Path(screenshot).with_name(Path(screenshot).stem+'-diff.png')
        Image.fromarray(pixels).save(diff)
        report.add('visual_regression',variant,'REVIEW' if changed else 'PASS',f'Changed pixels {fraction:.2%}; limit {threshold:.2%}. Rendering differences require human review.',url,evidence=diff.name)
    except Exception as exc: report.add('visual_regression',variant,'ERROR',str(exc),url)


def import_zap(path,report,base):
    if not path:
        report.add('external_scan','ZAP report','SKIP','No ZAP JSON report supplied'); return
    try:
        data=load_json(path)
        sites=data['site']
        if isinstance(sites,dict): sites=[sites]
        matched=[s for s in sites if origin(s['@name'])==origin(base)]
        if not matched: raise ValueError('No ZAP site matches target origin')
        alerts=[a for s in matched for a in s.get('alerts',[])]
        if not alerts:
            # An empty alert list is not proof a scan completed or covered the application.
            report.add('external_scan','ZAP imported','REVIEW','No alerts in supplied report; scan completion, date and coverage require verification',base)
        for alert in alerts:
            severity={'0':'info','1':'low','2':'medium','3':'high'}.get(str(alert.get('riskcode','1')),'medium')
            report.add('external_scan',str(alert.get('alert','ZAP alert')),'REVIEW',f"Imported scanner candidate; confidence={alert.get('confidence','unknown')}; CWE={alert.get('cweid','unknown')}; verify exploitability and report freshness",base,severity)
    except Exception as exc: report.add('external_scan','ZAP import','ERROR',str(exc),base)


def import_sarif(path,report):
    if not path:
        report.add('source_scan','Source/dependency scan','SKIP','No SARIF report supplied; website access cannot inspect backend code or dependencies'); return
    try:
        data=load_json(path)
        if data.get('version')!='2.1.0' or not isinstance(data.get('runs'),list) or not data['runs']: raise ValueError('Expected SARIF 2.1.0 with nonempty runs')
        total=0
        for run in data['runs']:
            name=run.get('tool',{}).get('driver',{}).get('name','scanner')
            for result in run.get('results',[]):
                total+=1
                severity={'error':'high','warning':'medium','note':'low','none':'info'}.get(result.get('level','warning'),'medium')
                report.add('source_scan',name+': '+str(result.get('ruleId','finding')),'REVIEW',result.get('message',{}).get('text','Imported candidate'),severity=severity)
        if not total: report.add('source_scan','SARIF imported','REVIEW','No findings reported; verify successful execution, source revision, enabled rules and dependency coverage')
    except Exception as exc: report.add('source_scan','SARIF import','ERROR',str(exc))
