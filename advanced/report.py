import html
import json
from pathlib import Path

def render(data,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    (out/'advanced-report.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
    esc=lambda x:html.escape(str(x),quote=True)
    cards=[]
    for row in data.get('ui',[]):
        checks=''.join('<li>'+('PASS' if c['pass'] else 'FAIL')+' — '+esc(c['name'])+'</li>' for c in row['checks'])
        image=row.get('image','')
        preview=f'<a href="{esc(image)}"><img src="{esc(image)}" alt="Captured test page"></a>' if image and Path(image).name==image else ''
        cards.append('<article><h3>'+esc(row['variant'])+'</h3><p class="url">'+esc(row['url'])+'</p><strong>'+esc(row['technical_ui_score'])+'/100</strong><p>Technical UI checklist · 6 checks</p>'+preview+'<ul>'+checks+'</ul><p>'+esc(row['scope'])+'</p><p>Review: '+esc(row['review']['targets_under_24_css_pixels'])+' small targets; '+esc(row['review']['text_under_12_css_pixels'])+' small-text elements.</p></article>')
    sections=[]
    for name,key in [('Autonomous exploration decisions and evidence','autonomous'),('Screenshot aesthetic model','ui_model'),('From-scratch model details','model'),('Next test priorities','plan'),('Observed client structure','client_map'),('Local source review','source'),('Collection errors','errors')]:
        sections.append('<details><summary>'+name+'</summary><pre>'+esc(json.dumps(data.get(key),indent=2,ensure_ascii=False))+'</pre></details>')
    content='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Advanced website assessment</title><style>body{font:16px/1.5 system-ui;background:#f3f6fa;color:#142135;max-width:1100px;margin:auto;padding:30px}header{padding:24px;background:#142135;color:white;border-radius:12px}details,article{background:white;padding:18px;margin-top:15px;border-radius:8px;border:1px solid #dce3ec}summary{font-weight:bold}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}a{color:#1263a3}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}.url{overflow-wrap:anywhere;font-size:13px}strong{font-size:30px}img{width:100%;height:160px;object-fit:contain;background:#f4f6f8}article p,li{font-size:13px}.status{background:#fef4ce;padding:18px;border-radius:8px}</style><header><h1>Advanced website assessment</h1><p>Measured evidence and experimental predictions are separate.</p></header>'''
    if data.get('ui_model'):
        content+='<div class="status"><b>Screenshot CNN: '+esc(data['ui_model']['status'])+'</b><p>Trained on human aesthetic preferences. Separate from the untrained multimodal model below.</p></div>'
    agent=data.get('autonomous')
    if agent:
        content+='<div class="status"><b>Autonomous explorer: '+esc(agent['mode'])+'</b><p>'+str(len(agent['states']))+' observed states · '+str(len(agent['actions']))+' action records · '+str(len(agent['questions']))+' questions requiring input</p><p>'+esc(agent['planner'])+'</p></div>'
        content+='<h2>Needs your input</h2><ul>'+(''.join('<li>'+esc(q)+'</li>' for q in agent['questions']) or '<li>No additional input requested in this run.</li>')+'</ul>'
        content+='<h2>Exploration evidence</h2><div class="grid">'
        for state in agent['states']:
            shot=state.get('screenshot')
            preview=('<a href="autonomous/'+esc(shot)+'"><img src="autonomous/'+esc(shot)+'" alt="Observed page state"></a>') if shot and Path(shot).name==shot else ''
            content+='<article><h3>'+esc(state['title'])+'</h3><p class="url">'+esc(state['url'])+'</p>'+preview+'</article>'
        content+='</div><h2>Action log</h2><div style="overflow:auto"><table><tr><th>Action</th><th>Outcome</th><th>Evidence</th></tr>'
        for action in agent['actions']:
            links=[]
            for key in ('before','after'):
                path=action.get(key)
                if path and Path(path).name==path:links.append('<a href="autonomous/'+esc(path)+'">'+key+'</a>')
            content+='<tr><td>'+esc(action['kind']+': '+action.get('control',''))+'</td><td>'+esc(action.get('outcome') or action.get('note',''))+'</td><td>'+' / '.join(links)+'</td></tr>'
        content+='</table></div>'
    model_label='Not configured — optional; exploration still works' if data['model']['status']=='NOT_TRAINED' else data['model']['status']
    content+='<p>'+esc(data['scope'])+'</p><div class="status"><b>Optional multimodal research model: '+esc(model_label)+'</b><p>'+esc(data['model'].get('reason') or data['model'].get('note') or 'Predictions are advisory; inspect held-out metrics and uncertainty.')+'</p></div><p><a href="../report.html">Open original tester report</a></p><div class="grid">'+''.join(cards)+'</div>'+''.join(sections)+'</html>'
    (out/'advanced-report.html').write_text(content,encoding='utf-8')
