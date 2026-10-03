"""Read-only DOM/layout observations. These are technical checks, not aesthetic truth."""
import asyncio
import hashlib
from pathlib import Path
from urllib.parse import urlsplit
from qa.core import origin,display_url
from .data import FEATURE_NAMES

OBSERVE=r'''() => {
 const visible=e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none'};
 const controls=[...document.querySelectorAll('button,a[href],input:not([type=hidden]),select,textarea,[role=button]')].filter(visible).slice(0,300);
 const forms=controls.filter(e=>['INPUT','SELECT','TEXTAREA'].includes(e.tagName));
 const small=controls.filter(e=>{const r=e.getBoundingClientRect();return r.width<24||r.height<24});
 const unlabelled=forms.filter(e=>!e.labels?.length&&!e.getAttribute('aria-label')&&!e.getAttribute('aria-labelledby'));
 const textNodes=[...document.querySelectorAll('p,span,label,button,a,h1,h2,h3')].filter(e=>visible(e)&&e.innerText?.trim()).slice(0,300);
 const smallText=textNodes.filter(e=>parseFloat(getComputedStyle(e).fontSize)<12);
 return {width:innerWidth,height:innerHeight,title:document.title,lang:document.documentElement.lang,text:(document.body?.innerText||'').slice(0,12000),
 controls:controls.length,fields:forms.length,images:document.images.length,missing_alt:[...document.images].filter(e=>!e.hasAttribute('alt')).length,
 broken_images:[...document.images].filter(e=>e.complete&&e.naturalWidth===0&&e.currentSrc).length,
 small_targets:small.length,unlabelled:unlabelled.length,overflow:document.documentElement.scrollWidth>innerWidth+2,
 contrast_candidates:0,small_text:smallText.length,heading_count:document.querySelectorAll('h1,h2,h3,h4,h5,h6').length,
 links:[...document.querySelectorAll('a[href]')].map(e=>e.href).slice(0,200),
 forms_spec:forms.map(e=>({id:e.id,name:e.name,type:e.type,min:e.min,max:e.max,required:e.required,pattern:e.pattern})),
 scripts:[...document.scripts].map(e=>e.src).filter(Boolean).slice(0,100)}
}'''

def ui_checks(d):
    checks=[{'name':'No horizontal overflow','pass':not d['overflow']},
            {'name':'Images load','pass':d['broken_images']==0},
            {'name':'Images declare alternative text','pass':d['missing_alt']==0},
            {'name':'Fields declare label references','pass':d['unlabelled']==0},
            {'name':'Page has a title','pass':bool(d['title'].strip())},
            {'name':'Page declares language','pass':bool(d['lang'].strip())}]
    return {'technical_ui_score':round(100*sum(x['pass'] for x in checks)/len(checks),1),'checks':checks,
     'review':{'targets_under_24_css_pixels':d['small_targets'],'text_under_12_css_pixels':d['small_text']},
     'scope':'Six DOM-based checks only. Not visual aesthetics, full accessibility, or WCAG conformance. Label references/alt content may be wrong. Size observations need context. Contrast is not measured by this collector; use the existing axe audit.'}

async def collect(report_path,out,max_pages=8,timeout=10000):
    import json
    from playwright.async_api import async_playwright
    report=json.loads(Path(report_path).read_text());out=Path(out);out.mkdir(parents=True,exist_ok=True)
    rows=[];ui=[];errors=[];graph=[];base=report['target']
    pages=report.get('pages',[])[:max_pages]
    async with async_playwright() as pw:
        browser=await pw.chromium.launch()
        try:
            for entry in pages:
                url=entry['url'];variant=entry['variant']; viewport={'width':390,'height':844} if 'mobile' in variant else {'width':768,'height':1024} if 'tablet' in variant else {'width':1440,'height':900}
                if 'REDACTED' in url:errors.append({'url':url,'reason':'Redacted query cannot be replayed; use source report screenshot with an approved dataset record'});continue
                context=await browser.new_context(viewport=viewport,service_workers='block');context.set_default_timeout(timeout)
                async def guard(route):
                    r=route.request
                    try:outside=r.is_navigation_request() and origin(r.url)!=origin(base)
                    except ValueError:outside=True
                    if outside or r.method not in ('GET','HEAD','OPTIONS'):await route.abort()
                    else:await route.continue_()
                await context.route('**/*',guard);page=await context.new_page();js=[];failed=[];events=[]
                page.on('pageerror',lambda e:js.append(str(e)))
                page.on('requestfailed',lambda r:failed.append(display_url(r.url)))
                page.on('response',lambda r:events.append([int(r.request.is_navigation_request()),r.status/600,0,0,0,0]) if len(events)<30 else None)
                try:
                    import time
                    start=time.perf_counter();await page.goto(url,wait_until='domcontentloaded');await page.wait_for_timeout(300);ms=(time.perf_counter()-start)*1000
                    d=await page.evaluate(OBSERVE);key=hashlib.sha256((url+variant).encode()).hexdigest()[:16];image='image-'+key+'.png'
                    await page.screenshot(path=str(out/image),animations='disabled')
                    values={**d,'text_length':len(d['text']),'links':len(d['links']),'js_errors':len(js),'failed_requests':len(failed),'load_ms':ms}
                    features=[float(values[k]) for k in FEATURE_NAMES];events.append([1,0,float(bool(failed)),float(bool(js)),min(ms/10000,10),0])
                    row={'schema':1,'id':key,'group':urlsplit(base).netloc,'url':display_url(url),'variant':variant,'image':image,'text':d['text'],'features':features,'events':events[:32],'labels':None,'reviewer':None}
                    rows.append(row);ui.append({'id':key,'url':display_url(url),'variant':variant,'image':image,**ui_checks(d)})
                    graph.append({'page':display_url(url),'links':[display_url(u) for u in d['links']],'scripts':[display_url(u) for u in d['scripts']],'declared_fields':d['forms_spec'],'interpretation':'Observed client-visible structure; constraints describe implementation, not approved business requirements.'})
                except Exception as exc:errors.append({'url':display_url(url),'variant':variant,'reason':str(exc)[:1000]})
                finally:await context.close()
        finally:await browser.close()
    (out/'dataset-unlabelled.jsonl').write_text('\n'.join(json.dumps(r) for r in rows)+'\n',encoding='utf-8')
    return {'rows':rows,'ui':ui,'client_map':graph,'errors':errors,'note':'Independent read-only Chromium revisit with no login state. Does not inherit original engine/authenticated session. Limited pages, controls and sampling window.'}
