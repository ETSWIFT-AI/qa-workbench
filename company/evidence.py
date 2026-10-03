"""Manual accessibility evidence, separated from automated conformance claims."""
REQUIRED = ('keyboard', 'focus_order', 'screen_reader', 'zoom_reflow', 'contrast_states', 'errors_labels')

def assess(config):
    items = config.get('checks', {})
    rows = []
    for name in REQUIRED:
        item = items.get(name, {})
        status = item.get('status', 'REVIEW')
        if status not in ('PASS', 'FAIL', 'REVIEW'): raise ValueError('Invalid manual status')
        if status != 'REVIEW' and not all(item.get(k) for k in ('reviewer', 'evidence', 'tested_at')):
            raise ValueError('Completed manual checks require reviewer, dated evidence')
        rows.append({'name': name, 'status': status, 'basis': 'Human attestation', **{k: item[k] for k in ('reviewer', 'evidence', 'tested_at') if k in item}})
    return {'kind': 'accessibility-review', 'results': rows, 'passed': all(r['status'] == 'PASS' for r in rows), 'limitation': 'A focused review checklist, not a full WCAG conformance audit. Run existing axe checks too.'}
