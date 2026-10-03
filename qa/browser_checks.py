import json
import asyncio
import statistics
from pathlib import Path
from .security import analyse_headers

OBSERVER = r'''() => {
window.__qaMetrics = {lcp:null, cls:0, longTasks:[], supported:[]};
for (const type of ['largest-contentful-paint','layout-shift','longtask']) {
 try { new PerformanceObserver(list => { for (const e of list.getEntries()) {
  if(type==='largest-contentful-paint') window.__qaMetrics.lcp=e.startTime;
  if(type==='layout-shift' && !e.hadRecentInput) window.__qaMetrics.cls+=e.value;
  if(type==='longtask') window.__qaMetrics.longTasks.push(e.duration);
 }}).observe({type,buffered:true}); window.__qaMetrics.supported.push(type); } catch(e) {}
}
}'''

INVENTORY = r'''() => ({
 title:document.title, lang:document.documentElement.lang,
 text:(document.body?.innerText || '').slice(0,16000),
 links:[...document.querySelectorAll('a[href]')].map(e=>e.href).slice(0,1000),
 forms:[...document.querySelectorAll('input,select,textarea')].slice(0,100).map(e=>({
  tag:e.tagName,type:e.type,id:e.id,name:e.name,label:e.labels?.[0]?.innerText || e.getAttribute('aria-label') || '',
  required:e.required,min:e.min,max:e.max,step:e.step,minLength:e.minLength,maxLength:e.maxLength,
  pattern:e.pattern,disabled:e.disabled})),
 buttons:[...document.querySelectorAll('button,[role=button],input[type=submit]')].slice(0,100).map(e=>({text:(e.innerText||e.value||e.getAttribute('aria-label')||'').slice(0,100),id:e.id,disabled:e.disabled})),
 missingAlt:[...document.images].filter(e=>!e.hasAttribute('alt')).length,
 brokenImages:[...document.images].filter(e=>e.complete && e.naturalWidth===0 && e.currentSrc).map(e=>e.currentSrc).slice(0,20),
 overflow:document.documentElement.scrollWidth>innerWidth+2,
 insecureResources:[...document.querySelectorAll('script[src],link[href],img[src],iframe[src]')].map(e=>e.src||e.href).filter(s=>s.startsWith('http:')).slice(0,20)
})'''


async def inspect(page, response, report, url, variant, out, axe_path, session_names, action_limit):
    inventory = await page.evaluate(INVENTORY)
    check = lambda family,name,status,detail='',severity='medium': report.add(family,f'{variant}: {name}',status,detail,url,severity)
    status = response.status if response else None
    check('http','Document response','PASS' if status and status<400 else 'FAIL',f'HTTP {status}','high')
    check('http','Image loading','FAIL' if inventory['brokenImages'] else 'PASS',inventory['brokenImages'])
    check('responsive','Horizontal overflow','REVIEW' if inventory['overflow'] else 'PASS','Overflow can be intentional; review screenshot')
    headers = await response.all_headers() if response else {}
    if not url.startswith('https:'):
        check('transport_headers','HTTPS','REVIEW','HTTP target; localhost development may be intentional','high')
    else: check('transport_headers','HTTPS','PASS','TLS verified by browser','high')
    for header in ('content-security-policy','x-content-type-options','referrer-policy'):
        good = bool(headers.get(header))
        if header=='x-content-type-options': good = headers.get(header,'').lower()=='nosniff'
        check('transport_headers',header,'PASS' if good else 'REVIEW','Present/basic value checked; not a full policy audit' if good else 'Missing or unexpected header')
    if url.startswith('https:'):
        check('transport_headers','HSTS','PASS' if 'strict-transport-security' in headers else 'REVIEW','Presence check only')
        check('transport_headers','Mixed-content references','REVIEW' if inventory['insecureResources'] else 'PASS',inventory['insecureResources'])
    csp=headers.get('content-security-policy','')
    frame=bool(headers.get('x-frame-options')) or 'frame-ancestors' in csp
    check('transport_headers','Framing policy','PASS' if frame else 'REVIEW','Presence check only; applicability and policy strength require review')
    for name,status,detail in analyse_headers(headers): check('transport_headers',name,status,detail)
    cookies=await page.context.cookies(url)
    if not session_names: check('cookies','Session cookie policy','SKIP','Configure session_cookie_names; cannot infer which cookies are security-sensitive')
    for name in session_names:
        found=[c for c in cookies if c['name']==name]
        if not found: check('cookies',name,'SKIP','Named session cookie absent in current session')
        for c in found:
            ok=c['secure'] and c['httpOnly'] and c['sameSite'] in ('Lax','Strict')
            check('cookies',name,'PASS' if ok else 'REVIEW','Secure/HttpOnly/SameSite checked; cross-site session use may need SameSite=None','high')
    controls=page.locator('button,a[href],input[type=submit],[role=button]')
    n=await controls.count()
    if not n: report.notes.append(variant+': no supported controls on '+url)
    if n>action_limit: check('actions','Control limit','SKIP',f'{n-action_limit} controls not tested')
    for i in range(min(n,action_limit)):
        c=controls.nth(i)
        label=(await c.get_attribute('aria-label') or await c.inner_text() or await c.get_attribute('value') or f'#{i}')[:100]
        if not await c.is_visible() or not await c.is_enabled():
            # Hidden/disabled controls may be intentional; do not assert a defect.
            continue
        try:
            await c.click(trial=True,timeout=1200)
            check('actions',f'Clickable {i}','PASS',label+'; action effects NOT tested')
        except Exception as exc:
            check('actions',f'Clickable {i}','REVIEW',label+'; '+str(exc)[:250])
    # Independent structural invariants can be checked without guessing domain requirements.
    structure = await page.evaluate("""() => {
      const all=[...document.querySelectorAll('[id]')]; const seen=new Set(); const duplicates=[];
      for(const e of all){if(seen.has(e.id))duplicates.push(e.id);seen.add(e.id)}
      const fields=[...document.querySelectorAll('input:not([type=hidden]),select,textarea')];
      return {duplicates:[...new Set(duplicates)],unlabelled:fields.filter(e=>!e.labels?.length&&!e.getAttribute('aria-label')&&!e.getAttribute('aria-labelledby')).map(e=>e.id||e.name||e.tagName),
      impossible:fields.filter(e=>e.min!==undefined&&e.min!==''&&e.max!==''&&Number(e.min)>Number(e.max)).map(e=>e.id||e.name)};
    }""")
    check('native_forms','Duplicate element IDs','FAIL' if structure['duplicates'] else 'PASS',structure['duplicates'])
    if inventory['forms']:
        check('native_forms','Declared numeric bounds','FAIL' if structure['impossible'] else 'PASS',structure['impossible'] or 'No contradictory min/max bounds; intended business limits not inferred')
        check('native_forms','Field labels','FAIL' if structure['unlabelled'] else 'PASS',structure['unlabelled'] or 'All inventoried fields have a label reference; semantic correctness not established')
        report.notes.append(variant+': native constraints inventoried; automatic structural checks do not prove business validation on '+url)
    # Automated Tab traversal is an observation, not WCAG conformance.
    focus=[]
    for _ in range(min(n+2,12)):
        await page.keyboard.press('Tab')
        focus.append(await page.evaluate('() => ({tag:document.activeElement.tagName,id:document.activeElement.id})'))
    check('keyboard','Tab sequence','REVIEW',json.dumps(focus)+'; manual focus order, visible focus and keyboard traps still need assessment')
    if not axe_path:
        check('axe','axe-core audit','SKIP','Supply --axe node_modules/axe-core/axe.min.js')
    else:
        try:
            await page.add_script_tag(path=str(axe_path))
            result=await asyncio.wait_for(page.evaluate("async () => await axe.run(document, {runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}})"),timeout=20)
            for passed in result['passes']: check('axe',passed['id'],'PASS',passed['help']+'; automated rule only')
            for v in result['violations']:
                severity={'critical':'high','serious':'high','moderate':'medium','minor':'low'}.get(v['impact'],'medium')
                check('axe',v['id'],'FAIL',v['help']+'; selectors: '+json.dumps([node['target'] for node in v['nodes'][:10]]),severity)
            for v in result['incomplete']: check('axe',v['id']+' incomplete','REVIEW',v['help'])
        except Exception as exc: check('axe','axe-core audit','ERROR',str(exc))
    return inventory


def performance(report,url,variant,samples,load_budget,lcp_budget,cls_budget,blocking_budget):
    if not samples:
        report.add('load_budget',variant,'ERROR','No completed samples',url)
        return
    report.performance_samples.append({'url':url,'variant':variant,'source':'local-lab','samples':samples})
    loads=[s['load_ms'] for s in samples]
    median=statistics.median(loads)
    report.add('load_budget',variant,'PASS' if median<=load_budget else 'FAIL',f'Median load {median:.0f} ms; budget {load_budget}; samples {loads}. Local lab conditions.',url)
    available=[s['metrics'] for s in samples if s.get('metrics')]
    lcps=[m['lcp'] for m in available if m['lcp'] is not None]
    if lcps:
        report.add('rendering_budget',variant+' LCP','PASS' if statistics.median(lcps)<=lcp_budget else 'FAIL',f'Lab LCP samples {lcps}; budget {lcp_budget} ms',url)
    else: report.add('rendering_budget',variant+' LCP','SKIP','LCP not observed in this engine/page',url)
    cls=[m['cls'] for m in available if 'layout-shift' in m['supported']]
    if cls: report.add('rendering_budget',variant+' layout shifts','PASS' if max(cls)<=cls_budget else 'FAIL',f'Observed cumulative shifts {cls}; budget {cls_budget}. Window-limited sum, not field Core Web Vitals CLS.',url)
    else: report.add('rendering_budget',variant+' layout shifts','SKIP','Layout-shift observer unsupported',url)
    blocking=[sum(max(0,d-50) for d in m['longTasks']) for m in available if 'longtask' in m['supported']]
    if blocking: report.add('rendering_budget',variant+' observed blocking','PASS' if max(blocking)<=blocking_budget else 'FAIL',f'Long-task excess over 50 ms per sample: {blocking}; budget {blocking_budget} ms. Sampling-window proxy, not Lighthouse TBT.',url)
    if len(loads)>=3:
        spread=(max(loads)-min(loads))/max(median,1)
        report.add('repeatability',variant,'REVIEW' if spread>1 else 'PASS',f'Load range/median={spread:.2f}; timing consistency only, not journey flakiness',url)
    else: report.add('repeatability',variant,'SKIP','Need at least 3 repetitions',url)
