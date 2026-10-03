import html
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from .core import write_json, load_json


def resolutions(report,path):
    if not path: return
    data=load_json(path)
    lookup={r['id']:r for r in report.results}
    for decision in data:
        key=decision['id']
        if key not in lookup:
            report.notes.append('Resolution did not match this run: '+str(key)); continue
        row=lookup[key]
        if row['status']!='REVIEW': raise ValueError('Only REVIEW findings can be resolved; skipped/error tests must be rerun')
        if decision.get('status') not in ('PASS','FAIL') or not decision.get('reviewer') or not decision.get('reason'):
            raise ValueError('Resolution needs PASS/FAIL, reviewer and reason')
        row['original_status']='REVIEW'; row['status']=decision['status']
        row['human_resolution']={k:decision[k] for k in ('reviewer','reason')}


def render(report,out):
    data=report.export()
    write_json(out/'report.json',data)
    esc=lambda v:html.escape(str(v),quote=True)
    score=data['score']
    cards=''.join(f'<article><b>{esc(name.title())}</b><p>{v["quality"] if v["quality"] is not None else "N/A"}</p><small>Coverage {v["coverage"]}%</small></article>' for name,v in score['categories'].items())
    rows=''
    order={'ERROR':0,'FAIL':1,'REVIEW':2,'SKIP':3,'PASS':4}
    for r in sorted(data['results'],key=lambda x:order[x['status']]):
        evidence=''
        if r['evidence'] and Path(r['evidence']).name==r['evidence']:
            evidence=f'<a href="{esc(r["evidence"])}">Evidence</a>'
        rows+=f'<tr data-status="{r["status"]}"><td class="{r["status"]}">{r["status"]}<br>{esc(r["severity"])}</td><td>{esc(r["family"])}<br><strong>{esc(r["check"])}</strong><br><small>{esc(r["id"])}</small></td><td>{esc(r["url"])}</td><td>{esc(r["detail"])}<br>{evidence}</td></tr>'
    notes=''.join('<li>'+esc(n)+'</li>' for n in data['notes'])
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Website QA report</title>
<style>:root{color-scheme:light}body{font:15px/1.5 system-ui;background:#f5f7fb;color:#142135;margin:0;padding:32px}main{max-width:1400px;margin:auto}h1{font-size:32px;margin-bottom:8px}.muted{color:#526078}.hero{background:#12223c;color:white;padding:28px;border-radius:16px}.hero b{font-size:38px}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:20px 0}article{background:white;padding:16px;border:1px solid #d8dfeb;border-radius:10px}article p{font-size:22px;margin:8px 0}table{width:100%;border-collapse:collapse;background:white}td,th{padding:12px;border-bottom:1px solid #d8dfeb;text-align:left;vertical-align:top;overflow-wrap:anywhere}td:last-child{max-width:600px}.FAIL,.ERROR{color:#a01528;font-weight:bold}.PASS{color:#17653b}.REVIEW{color:#805400}.SKIP{color:#58657b}select{padding:9px;margin:16px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere}details{background:white;padding:16px;margin:15px 0}.scroll{overflow:auto}small{font-size:11px}</style><main>'''
    quality=str(score['score'])+'/100' if score['score'] is not None else 'Not assessed'
    counts=data['counts']
    gate_reasons=''.join('<li>'+esc(x)+'</li>' for x in score['gate_reasons'])
    mode='Action-enabled test run' if data['settings'].get('allow_actions') else 'READ-ONLY — state-changing workflows not tested'
    history=data.get('history',{})
    trend=''.join(f"<tr><td>{esc(t['started'])}</td><td>{esc(t['quality'])}</td><td>{t['coverage']}%</td><td>{esc(t['gate'])}</td></tr>" for t in history.get('trend',[]))
    page+=f'<h1>Website testing report</h1><p class="muted">{esc(data["target"])} · {esc(data["started"])}</p><section class="hero"><h2>{esc(score["assessment"].replace("_"," "))}</h2><b>{quality}</b><p>Tested quality — completed checks only</p><h2>{score["coverage"]}% coverage</h2><p>{esc(mode)}</p></section><p>{esc(score["explanation"])}</p><p><strong>{counts.get("FAIL",0)} failed · {counts.get("REVIEW",0)} need review · {counts.get("SKIP",0)} skipped · {counts.get("ERROR",0)} execution errors</strong></p><details open><summary>Release gate: {esc(score["gate"])}</summary><ul>{gate_reasons}</ul></details><div class="cards">{cards}</div><details><summary>Coverage, limitations and run notes</summary><ul>{notes}</ul><pre>{esc(json.dumps(score["categories"],indent=2))}</pre></details><details><summary>Run history and regressions</summary><p>{esc(history.get("note","History disabled or unavailable"))}</p><table><tr><th>Run</th><th>Tested quality</th><th>Coverage</th><th>Gate</th></tr>{trend}</table><pre>{esc(json.dumps(history.get("comparison"),indent=2))}</pre></details><details><summary>Field performance — separate from lab timing</summary><pre>{esc(json.dumps(data.get("field_data",{}),indent=2))}</pre></details><details><summary>AI suggestions — unverified, excluded from score</summary><pre>{esc(json.dumps(data["ai"],indent=2))}</pre></details>'
    page+='<label for="filter">Show results: </label><select id="filter"><option value="ALL">All</option>'+''.join(f'<option>{s}</option>' for s in ('FAIL','ERROR','REVIEW','SKIP','PASS'))+'</select><div class="scroll"><table><thead><tr><th>Status</th><th>Test</th><th>Page</th><th>Evidence / explanation</th></tr></thead><tbody>'+rows+'</tbody></table></div><script>document.getElementById("filter").addEventListener("change",e=>document.querySelectorAll("tr[data-status]").forEach(r=>r.hidden=e.target.value!=="ALL"&&r.dataset.status!==e.target.value));</script></main></html>'
    (out/'report.html').write_text(page,encoding='utf-8')
    suite=ET.Element('testsuite',name='Website QA',tests=str(len(report.results)))
    for r in report.results:
        case=ET.SubElement(suite,'testcase',name=r['check'],classname=r['family'])
        tag={'FAIL':'failure','ERROR':'error','SKIP':'skipped','REVIEW':'skipped'}.get(r['status'])
        if tag: ET.SubElement(case,tag,message=r['status']).text=r['detail']
    suite.set('failures',str(sum(r['status']=='FAIL' for r in report.results)))
    suite.set('errors',str(sum(r['status']=='ERROR' for r in report.results)))
    suite.set('skipped',str(sum(r['status'] in ('SKIP','REVIEW') for r in report.results)))
    ET.ElementTree(suite).write(out/'junit.xml',encoding='utf-8',xml_declaration=True)
