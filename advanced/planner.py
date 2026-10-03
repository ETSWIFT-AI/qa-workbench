"""Deterministic next-test priorities; observed implementation is not its own oracle."""
def plan(report,observations):
    tasks=[]
    if any(r['status']=='ERROR' for r in report.get('results',[])):
        tasks.append({'priority':1,'task':'Resolve execution errors and rerun affected checks','reason':'Incomplete execution cannot establish product quality'})
    for page in observations.get('client_map',[]):
        for field in page.get('declared_fields',[]):
            if field.get('type') in ('number','email'):
                tasks.append({'priority':2,'task':'Verify blank, malformed and boundary inputs','page':page['page'],'field':field.get('id') or field.get('name'),'declared_min':field.get('min'),'declared_max':field.get('max'),'needs_requirement':True})
    failures=[r for r in report.get('results',[]) if r['status']=='FAIL']
    if failures:tasks.append({'priority':1,'task':'Reproduce confirmed failures with the same environment','finding_ids':[r['id'] for r in failures[:20]]})
    if not any(r.get('family')=='journeys' and r['status'] in ('PASS','FAIL') for r in report.get('results',[])):
        tasks.append({'priority':2,'task':'Add one critical business journey with independent expected outcomes','needs_requirement':True})
    questions=[]
    if any(x.get('needs_requirement') for x in tasks):questions.append('Which critical flow and valid input limits should the site implement? Provide existing rules/specification if available.')
    return {'tasks':tasks[:30],'questions_if_business_assessment_required':questions,'autonomy':'Runs bounded observation and existing approved tests without prompts. Missing business oracles remain explicit; recommendations are not auto-executed mutations.'}
