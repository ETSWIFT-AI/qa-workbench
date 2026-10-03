import html
import json
from pathlib import Path
import xml.etree.ElementTree as ET

def save(report, output):
    out = Path(output); out.mkdir(parents=True, exist_ok=True)
    (out / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    rows = report.get('results', [{'name': report['kind'], 'status': report.get('status', 'PASS' if report.get('passed') else 'ERROR')}])
    xml = ET.Element('testsuite', name=report['kind'], tests=str(len(rows)), failures=str(sum(r['status'] == 'FAIL' for r in rows)), errors=str(sum(r['status'] == 'ERROR' for r in rows)), skipped=str(sum(r['status'] in ('SKIP', 'REVIEW') for r in rows)))
    for row in rows:
        case = ET.SubElement(xml, 'testcase', name=row.get('name', report['kind']), classname='/'.join(str(row.get(k, '')) for k in ('browser', 'viewport')), time=str(row.get('seconds', 0)))
        status = row['status']
        if status != 'PASS':
            ET.SubElement(case, 'failure' if status == 'FAIL' else 'error' if status == 'ERROR' else 'skipped').text = json.dumps(row)
    ET.ElementTree(xml).write(out / 'junit.xml', encoding='utf-8', xml_declaration=True)
    content = html.escape(json.dumps(report, indent=2))
    (out / 'report.html').write_text('<!doctype html><meta charset="utf-8"><title>Company QA report</title><style>body{font:16px system-ui;max-width:1100px;margin:40px auto;padding:20px}pre{white-space:pre-wrap;background:#f2f5f8;padding:24px}</style><h1>Company QA — ' + html.escape(report['kind']) + '</h1><p>Result: ' + ('PASS' if report.get('passed') else 'NOT PASSED / INCOMPLETE') + '</p><pre>' + content + '</pre>', encoding='utf-8')
