"""Preview a selected finding and publish only after an explicit digest confirmation."""
import argparse
import json
import os
from pathlib import Path
from product.issues import drafts,markdown
from product.integrations import prepare,digest,publish

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('report');p.add_argument('--finding',required=True);p.add_argument('--provider',choices=['github','jira'],required=True)
    p.add_argument('--repository',default='');p.add_argument('--server',default='');p.add_argument('--project',default='');p.add_argument('--email',default='');p.add_argument('--issue-type',default='Bug')
    p.add_argument('--token-env',default='QA_ISSUE_TOKEN');p.add_argument('--publish',action='store_true');p.add_argument('--confirm-digest');a=p.parse_args()
    report_path=Path(a.report).resolve();report=json.loads(report_path.read_text(encoding='utf-8'))
    row=next((r for r in drafts(report) if r['id']==a.finding),None)
    if row is None:p.error('Select a FAIL or ERROR finding ID in this report')
    preview=prepare(a.provider,row['title'][:250],markdown([row]),a.repository,a.server,a.project,a.email,a.issue_type)
    approved=digest(preview)
    if not a.publish:
        print(json.dumps(preview,indent=2));print('\nReview this exact destination and content. To publish, repeat with --publish --confirm-digest '+approved);return 0
    if a.confirm_digest!=approved:p.error('Exact preview digest confirmation required')
    token=os.environ.get(a.token_env)
    if not token:p.error('Missing token environment variable '+a.token_env)
    # Durable reservation before networking prevents accidental duplicate retries, including after timeouts.
    ledger=report_path.parent/('issue-publication-'+approved+'.json')
    try:
        with ledger.open('x',encoding='utf-8') as f:json.dump({'state':'ATTEMPTED','destination':preview['identity'],'finding':a.finding},f)
    except FileExistsError:p.error('Publication already attempted. Inspect the saved record and provider before any manual retry.')
    try:
        url=publish(preview,token,a.confirm_digest)
        ledger.write_text(json.dumps({'state':'CREATED','url':url,'finding':a.finding},indent=2));print('Created: '+url);return 0
    except Exception as exc:
        ledger.write_text(json.dumps({'state':'UNKNOWN_OR_FAILED','error_type':type(exc).__name__,'finding':a.finding},indent=2))
        print('Publication not confirmed. Check the provider before retrying. '+str(exc) if isinstance(exc,(ValueError,RuntimeError)) else 'Publication not confirmed; check the provider before retrying.')
        return 1
if __name__=='__main__':raise SystemExit(main())
