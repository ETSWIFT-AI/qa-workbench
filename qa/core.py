import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, urljoin

FAMILIES = {
 'functional': (25, ['http', 'actions', 'journeys']),
 'validation': (15, ['native_forms', 'boundary_rules', 'api_contracts']),
 'reliability': (10, ['js_errors', 'network_errors', 'repeatability']),
 'performance': (10, ['load_budget', 'rendering_budget']),
 'accessibility': (10, ['axe', 'keyboard']),
 'security': (15, ['transport_headers', 'cookies', 'authorization', 'external_scan']),
 'compatibility': (10, ['responsive', 'browser_matrix', 'visual_regression']),
 'lifecycle': (5, ['source_scan', 'requirements', 'operations', 'self_healing']),
}
STATUSES = {'PASS', 'FAIL', 'REVIEW', 'SKIP', 'ERROR'}
SEVERITIES = {'critical', 'high', 'medium', 'low', 'info'}


def canonical(url):
    p = urlsplit(url)
    if p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password:
        raise ValueError('Expected an HTTP(S) URL without embedded credentials')
    _ = p.port
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path or '/', p.query, p.fragment if p.fragment.startswith(('/', '!')) else ''))


def origin(url):
    p = urlsplit(canonical(url))
    return p.scheme, p.hostname, p.port or (443 if p.scheme == 'https' else 80)


def scoped(base, url):
    target = canonical(urljoin(base, url))
    if origin(target) != origin(base):
        raise ValueError('URL outside configured origin')
    return target


def display_url(url):
    """Avoid leaking query values and URL fragments into reports."""
    try:
        p = urlsplit(url)
        fragment = p.fragment.split('?')[0] if p.fragment.startswith(('/', '!')) else ''
        return urlunsplit((p.scheme, p.netloc, p.path, 'REDACTED' if p.query else '', fragment))
    except ValueError:
        return '[invalid URL]'


def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')


def validate_config(cfg, base):
    if not isinstance(cfg, dict):
        raise ValueError('Configuration must be a JSON object')
    allowed = {'journeys','fields','api_tests','evidence','exclude_paths','session_cookie_names'}
    if set(cfg) - allowed:
        raise ValueError(f'Unknown configuration keys: {set(cfg)-allowed}')
    for group in ('journeys','fields','api_tests','evidence'):
        if not isinstance(cfg.get(group, []), list):
            raise ValueError(f'{group} must be an array')
    names = set()
    for group in ('journeys','fields','api_tests'):
        for rule in cfg.get(group, []):
            if not isinstance(rule,dict) or not isinstance(rule.get('name'),str) or not rule['name']:
                raise ValueError(f'{group}: each rule needs a unique name')
            if rule['name'] in names: raise ValueError('Duplicate test name: '+rule['name'])
            names.add(rule['name'])
            scoped(base, rule['path'])
    actions = {'click','fill','press','select','check','uncheck','goto'}
    assertions = {'url','visible','hidden','text','value','enabled','disabled','count'}
    for rule in cfg.get('journeys', []):
        if not rule.get('steps') or not isinstance(rule['steps'],list): raise ValueError('Journey needs steps')
        if not any(s.get('action') in assertions for s in rule['steps']): raise ValueError('Journey needs an assertion')
        for s in rule['steps']:
            if s.get('action') not in actions | assertions: raise ValueError('Unsupported journey action')
            if s['action'] in ('url','goto'): scoped(base,s['value'])
            elif not isinstance(s.get('selector'),str): raise ValueError('Step needs selector')
    for rule in cfg.get('fields',[]):
        if not isinstance(rule.get('selector'),str) or not rule.get('cases'): raise ValueError('Field needs selector and cases')
        for case in rule['cases']:
            if not isinstance(case.get('accepted'),bool) or 'value' not in case: raise ValueError('Field case needs value and accepted boolean')
    for rule in cfg.get('api_tests',[]):
        if rule.get('method','GET').upper() not in {'GET','HEAD','POST','PUT','PATCH','DELETE','OPTIONS'}: raise ValueError('Unsupported API method')
        if not isinstance(rule.get('expected_status'),int): raise ValueError('API test needs expected_status')
        if rule.get('authorization_test') and not rule.get('role'): raise ValueError('Authorization test needs an explicit role label')
    for evidence in cfg.get('evidence',[]):
        if evidence.get('family') not in ('requirements','operations'): raise ValueError('Evidence family must be requirements or operations')
    return cfg


class Report:
    def __init__(self, target, settings):
        self.target = display_url(target)
        self.settings = settings
        self.started = datetime.now(timezone.utc).isoformat()
        self.results, self.pages, self.notes = [], [], []
        self.ai = {}
        self.history = {}
        self.field_data = {}
        self.performance_samples = []
        self.discovery = []

    def add(self, family, check, status, detail='', url='', severity='medium', evidence='', requirement=''):
        if family not in {f for _, fs in FAMILIES.values() for f in fs}: raise ValueError('Unknown family')
        if status not in STATUSES or severity not in SEVERITIES: raise ValueError('Bad result status/severity')
        row = dict(family=family,check=check,status=status,severity=severity,detail=str(detail)[:4000],url=display_url(url),evidence=evidence,requirement=requirement)
        stable = '|'.join(str(row[k]) for k in ('family','check','url','detail'))
        row['id'] = hashlib.sha256(stable.encode()).hexdigest()[:16]
        key = '|'.join(str(row[k]) for k in ('family','check','url','requirement'))
        row['fingerprint'] = hashlib.sha256(key.encode()).hexdigest()[:20]
        # Exact duplicates do not artificially inflate the score.
        if not any(x['id']==row['id'] and x['status']==status for x in self.results): self.results.append(row)
        return row

    def score(self):
        # Unknown results are not defects. Quality and evidence coverage are independent.
        categories, quality_sum, assessed_weight, coverage = {}, 0.0, 0.0, 0.0
        risk = {'critical':5,'high':3,'medium':2,'low':1,'info':1}
        for category,(weight,families) in FAMILIES.items():
            details = {}; cat_sum = cat_assessed = cat_coverage = 0.0
            for family in families:
                rows = [r for r in self.results if r['family']==family]
                tested = [r for r in rows if r['status'] in ('PASS','FAIL')]
                denominator = sum(risk[r['severity']] for r in tested)
                quality = (100*sum(risk[r['severity']] for r in tested if r['status']=='PASS')/denominator) if denominator else None
                fraction = len(tested)/len(rows) if rows else 0
                family_weight = weight/len(families)
                if quality is not None:
                    quality_sum += family_weight*quality; assessed_weight += family_weight
                    cat_sum += family_weight*quality; cat_assessed += family_weight
                coverage += family_weight*fraction; cat_coverage += family_weight*fraction
                details[family] = {'quality':round(quality,1) if quality is not None else None,
                    'coverage':round(fraction*100,1),'completed':len(tested),'planned':len(rows),
                    'counts':dict(Counter(r['status'] for r in rows))}
            categories[category] = {'weight':weight,'quality':round(cat_sum/cat_assessed,1) if cat_assessed else None,
                'coverage':round(100*cat_coverage/weight,1),'families':details}
        quality = round(quality_sum/assessed_weight,1) if assessed_weight else None
        blockers = [r['id'] for r in self.results if (r['status']=='FAIL' and r['severity'] in ('critical','high')) or r['status']=='ERROR']
        critical = [r for r in self.results if r['family']=='journeys' and r['severity']=='critical']
        gate = quality is not None and quality>=90 and coverage>=90 and not blockers and bool(critical) and all(r['status']=='PASS' for r in critical)
        reasons=[]
        if quality is None: reasons.append('No completed checks; website quality cannot be assessed')
        elif quality<90: reasons.append('Tested quality is below 90')
        if coverage<90: reasons.append('Coverage is below 90%')
        if blockers: reasons.append('High/critical failures or execution errors remain')
        if not critical or not all(r['status']=='PASS' for r in critical): reasons.append('Passing critical business journeys are required')
        label = 'NO_ASSESSMENT' if quality is None else 'PARTIAL_ASSESSMENT' if coverage<90 else 'ASSESSED_CONFIGURED_SCOPE'
        return dict(score=quality,coverage=round(coverage,1),assessment=label,
            gate='MEETS_CONFIGURED_GATE' if gate else 'NOT_QUALIFIED',gate_reasons=reasons,
            blockers=blockers,categories=categories,
            explanation='Tested quality: severity-weighted PASS rate within each tested family, averaged using fixed family weights. SKIP/REVIEW/ERROR never count as failed product tests. Coverage: weighted completed/recorded cases in each fixed family; unconfigured families have zero coverage. Neither metric estimates all possible website behavior. A high score with low coverage is a partial assessment, not release approval.')

    def export(self):
        return dict(version='3.0.0',target=self.target,started=self.started,settings=self.settings,score=self.score(),counts=dict(Counter(r['status'] for r in self.results)),pages=self.pages,notes=self.notes,ai=self.ai,history=self.history,field_data=self.field_data,performance_samples=self.performance_samples,discovery=self.discovery,results=self.results)
