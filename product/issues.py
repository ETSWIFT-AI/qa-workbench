"""Reviewable issue drafts; no external messages or issues are sent automatically."""
import csv
import io
import json
from .security import redact

def drafts(report,config=None):
    rows=[]
    for finding in report.get('results',[]):
        if finding.get('status') not in ('FAIL','ERROR'):continue
        journey=None
        for j in (config or {}).get('journeys',[]):
            if j['name'] in finding.get('check',''):journey=j;break
        reproduction=[]
        if journey:
            reproduction.append('Open '+journey['path'])
            for step in journey['steps']:
                description=step['action']+' '+step.get('selector','')
                if step.get('value_env'):description+=' using private input '+step['value_env']
                elif 'value' in step:description+=' '+str(step['value'])
                reproduction.append(redact(description))
        else:
            reproduction=['Open '+redact(finding.get('url') or report.get('target','')),
                'Repeat check: '+finding.get('check','Unknown check'),
                'Use the recorded browser/viewport and inspect the attached local evidence.']
        rows.append({'id':finding.get('id'), 'title':redact(finding.get('check','Finding')),
            'classification':'Product finding requiring reproduction' if finding['status']=='FAIL' else 'Execution problem; not a confirmed product defect',
            'severity':finding.get('severity','medium'),'expected': 'Configured assertions must hold' if journey else 'The named check should meet its configured requirement; confirm intended behavior during triage.',
            'actual':redact(finding.get('detail','')), 'steps':reproduction,'evidence':finding.get('evidence',''),
            'verification':'UNVERIFIED — manual reproduction required'})
    return rows

def markdown(rows):
    return '\n\n'.join('## '+r['title']+'\n\n'+r['classification']+'\n\n**Verification:** '+r['verification']+'\n\n**Expected:** '+r['expected']+'\n\n**Actual:** '+r['actual']+'\n\n**Steps:**\n'+ '\n'.join(str(i+1)+'. '+s for i,s in enumerate(r['steps']))+'\n\n**Evidence:** '+r['evidence'] for r in rows)

def jira_csv(rows):
    stream=io.StringIO();w=csv.writer(stream);w.writerow(['Summary','Description','Issue Type'])
    for row in rows:w.writerow([safe_cell(row['title']),safe_cell(markdown([row])),'Bug'])
    return stream.getvalue()

def safe_cell(value):return "'"+value if value[:1] in ('=','+','-','@','\t','\r') else value
