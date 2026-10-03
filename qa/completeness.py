"""Expose incomplete coverage without inventing product failures or hiding skips."""
from collections import Counter
import html
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ACTIONS = {
 'axe': 'Install axe with npm ci --ignore-scripts; supply --axe node_modules/axe-core/axe.min.js.',
 'repeatability': 'Run at least three samples with --repeats 3.',
 'browser_matrix': 'Install and launch Chromium, Firefox and WebKit; resolve browser startup errors.',
 'responsive': 'Test all requested viewports; review overflow screenshots against the intended layout.',
 'visual_regression': 'Review reference screenshots, then supply their folder with --baselines. A first screenshot is not automatically correct.',
 'cookies': 'Supply actual session_cookie_names and an authenticated --storage-state. Do not guess the session cookie.',
 'journeys': 'Configure critical use cases with actions and expected outcomes; use authorized test credentials and --allow-actions.',
 'boundary_rules': 'Supply expected valid/invalid field cases. Automatic HTML constraints do not establish business limits.',
 'api_contracts': 'Supply API endpoints and expected responses in --config.',
 'authorization': 'Supply role/owner access cases, credentials and expected allowed/denied responses.',
 'external_scan': 'Supply a ZAP JSON report, or use the existing authorized ZAP baseline integration.',
 'source_scan': 'Supply a source/dependency SARIF report; a website URL cannot expose its server code.',
 'requirements': 'Supply reviewed requirements evidence and expected outcomes.',
 'operations': 'Supply reviewed deployment, rollback and monitoring evidence.',
 'keyboard': 'Review keyboard focus, traps and screen-reader behavior; record reviewed dispositions with --resolutions.',
 'transport_headers': 'Review policy applicability and values, then record supported PASS/FAIL dispositions.',
 'network_errors': 'Inspect failed requests. Read-only POST blocks are not website defects; actions need authorized test scope.',
 'actions': 'Raise --action-limit/--max-states if a limit was reached. Supply expected outcomes for interactions and review hidden/disabled controls.',
 'http': 'Resolve navigation errors or increase page/time limits. Review excluded routes before enabling them.',
 'rendering_budget': 'Check browser metric support and collect supported measurements; never substitute a missing metric with zero.',
 'load_budget': 'Resolve page-load errors, then collect completed timing samples.',
 'js_errors': 'Inspect browser traces and reproduce the JavaScript exception.',
}

def summarize(data):
    grouped = {}
    for row in data.get('results', []):
        if row.get('status') not in ('SKIP', 'REVIEW', 'ERROR'): continue
        key = (row['family'], row['status'], row.get('detail', ''))
        entry = grouped.setdefault(key, {'family': row['family'], 'status': row['status'],
            'reason': row.get('detail', ''), 'count': 0, 'finding_ids': [],
            'next_action': ACTIONS.get(row['family'], 'Inspect evidence and supply the missing requirement or dependency.')})
        entry['count'] += 1
        entry['finding_ids'].append(row.get('id'))
    # An omitted family must not disappear from a strict assessment.
    for category in data.get('score', {}).get('categories', {}).values():
        for name, family in category.get('families', {}).items():
            if family.get('planned', 0) == 0 and name != 'self_healing':
                grouped[(name, 'UNASSESSED', '')] = {'family': name, 'status': 'UNASSESSED',
                    'reason': 'No cases recorded for this family', 'count': 1, 'finding_ids': [],
                    'next_action': ACTIONS.get(name, 'Define the applicable test cases and expected outcomes.')}
    for note in data.get('notes', []):
        if note.startswith('Excluded route:') or note.startswith('Exploration discovered route for follow-up:'):
            grouped[('http', 'EXCLUDED', note)] = {'family':'http','status':'EXCLUDED','reason':note,'count':1,'finding_ids':[], 'next_action':'Review this route and provide an authorized explicit workflow or follow-up scan. Excluded routes are not tested.'}
    counts = Counter(r.get('status') for r in data.get('results', []))
    gaps = list(grouped.values())
    if not data.get('results'):
        gaps.append({'family':'execution','status':'UNASSESSED','reason':'No test results recorded','count':1,'finding_ids':[], 'next_action':'Fix setup and rerun.'})
    gate = data.get('score', {}).get('gate')
    passed = not gaps and counts['FAIL'] == 0 and gate == 'MEETS_CONFIGURED_GATE'
    return {'target': data.get('target'), 'status': 'CONFIGURED_SCOPE_PASSED' if passed else 'INCOMPLETE' if gaps else 'FAILED',
        'passed': passed, 'counts': dict(counts), 'gaps': gaps,
        'gate_reasons': data.get('score', {}).get('gate_reasons', []),
        'note': 'Strict completion covers configured and recorded checks only. It cannot prove that every possible use case was discovered. Original findings and scores are preserved.'}

def save(summary, directory):
    out = Path(directory); out.mkdir(parents=True, exist_ok=True)
    (out/'completion.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    esc=lambda x:html.escape(str(x), quote=True)
    report_link='<p><a href="report.html">Detailed scan report</a></p>' if (out/'report.html').exists() else ''
    rows=''.join('<tr><td>'+esc(g['family'])+'</td><td>'+esc(g['status'])+'</td><td>'+str(g['count'])+'</td><td>'+esc(g['reason'])+'</td><td>'+esc(g['next_action'])+'</td></tr>' for g in summary['gaps'])
    (out/'completion.html').write_text('<!doctype html><meta charset="utf-8"><title>Test completion</title><style>body{font:16px system-ui;margin:32px;color:#172535}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccd4df;padding:12px;text-align:left;vertical-align:top;overflow-wrap:anywhere}h1{color:#9c2632}</style><h1>'+esc(summary['status'])+'</h1><p>'+esc(summary.get('target',''))+'</p><p>'+esc(summary['note'])+'</p><p>Counts: '+esc(summary['counts'])+'</p>'+report_link+'<table><tr><th>Area</th><th>Status</th><th>Entries</th><th>Reason</th><th>Next action</th></tr>'+rows+'</table>',encoding='utf-8')
    suite=ET.Element('testsuite', name='Strict completeness', tests='1', failures='0' if summary['passed'] else '1')
    case=ET.SubElement(suite,'testcase',name='All configured checks complete and passing')
    if not summary['passed']:
        ET.SubElement(case,'failure',message='Testing incomplete or failing; not a fabricated application defect').text=json.dumps(summary)
    ET.ElementTree(suite).write(out/'completion-junit.xml',encoding='utf-8',xml_declaration=True)
