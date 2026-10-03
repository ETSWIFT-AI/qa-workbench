"""Bounded state-aware exploration; business outcomes still need independent oracles."""
import hashlib
import json
import re
from .core import scoped,display_url

CONTROL_SELECTOR='button,[role=button],[role=tab],a[href]'
BLOCKED=re.compile(r'delete|remove|purchase|pay|checkout|send|submit|save|confirm|logout|sign.?out|unsubscribe',re.I)

async def controls(page,limit):
    nodes=page.locator(CONTROL_SELECTOR)
    result=[]
    for i in range(min(await nodes.count(),limit)):
        e=nodes.nth(i)
        if not await e.is_visible() or not await e.is_enabled(): continue
        desc=await e.evaluate("e=>({text:(e.innerText||e.getAttribute('aria-label')||'').slice(0,120),inForm:!!e.closest('form'),href:e.getAttribute('href')||''})")
        if desc['inForm'] or BLOCKED.search(desc['text']+' '+desc['href']): continue
        result.append({'index':i,'text':desc['text']})
    return result

async def state(page):
    d=await page.evaluate("() => ({url:location.href,text:(document.body?.innerText||'').slice(0,12000)})")
    return hashlib.sha256(json.dumps(d,sort_keys=True).encode()).hexdigest()[:20],d

async def explore(browser,context_factory,urls,base,report,limit,max_depth=2,max_states=20,viewport='desktop',variant='chromium/desktop'):
    frontier=[(u,[]) for u in urls]; visited=set(); discovered=set(); explored=0
    while frontier and explored<max_states:
        start,sequence=frontier.pop(0)
        ctx=await context_factory(browser,viewport=viewport);page=await ctx.new_page()
        try:
            await page.goto(start)
            for action in sequence:
                loc=page.locator(CONTROL_SELECTOR).nth(action['index'])
                actual=(await loc.inner_text()).strip()[:120]
                if action['text'] and actual!=action['text']:
                    raise ValueError('Replay target changed; refusing an ambiguous click')
                await loc.click(); await page.wait_for_timeout(250)
            key,view=await state(page)
            if key in visited: continue
            visited.add(key);explored+=1
            report.discovery.append({'variant':variant,'url':display_url(view['url']),'state':key,'depth':len(sequence),'steps':sequence})
            if sequence:
                report.add('actions',variant+': state '+key,'REVIEW','State reached by '+json.dumps(sequence)+'; expected business outcome still requires an assertion',view['url'])
            try: discovered.add(scoped(base,view['url']))
            except ValueError: pass
            for link in await page.locator('a[href]').evaluate_all('(es)=>es.map(e=>e.href)'):
                try:
                    link=scoped(base,link)
                    if not BLOCKED.search(link): discovered.add(link)
                except ValueError: pass
            if len(sequence)<max_depth:
                for action in await controls(page,limit):
                    if len(frontier)>=max_states*limit: break
                    frontier.append((start,sequence+[action]))
        except Exception as exc:
            report.add('actions',variant+': exploration','REVIEW',str(exc),start)
        finally: await ctx.close()
    if frontier: report.add('actions',variant+': exploration limit','SKIP',f'Budget {max_states} states/depth {max_depth}; {len(frontier)} pending paths')
    report.notes.append(f'{variant}: explored {explored} distinct DOM/URL states. State hashing and positional replay are bounded heuristics, not exhaustive SPA coverage.')
    return sorted(discovered)

def suggest_fields(pages):
    """Infer draft boundary cases from HTML attributes, not from invented domain rules."""
    drafts=[]; seen=set()
    for page in pages:
        for f in page['inventory']['forms']:
            ident=f.get('id') or f.get('name')
            if not ident or f.get('disabled') or f.get('type') not in ('number','email','text'): continue
            key=(page['url'],ident)
            if key in seen: continue
            seen.add(key)
            # JSON string quoting provides a quoted CSS attribute string for normal IDs.
            import json
            selector='['+('id' if f.get('id') else 'name')+'='+json.dumps(ident)+']'
            cases=[{'value':'','accepted':not f.get('required',False)}]
            if f.get('type')=='number':
                cases.append({'value':'abc','accepted':False})
                try:
                    low=float(f['min']); high=float(f['max'])
                    if low.is_integer() and high.is_integer() and f.get('step') in ('','1'):
                        for n in (int(low)-1,int(low),int(high),int(high)+1): cases.append({'value':str(n),'accepted':low<=n<=high})
                except (KeyError,TypeError,ValueError): pass
            elif f.get('type')=='email': cases.append({'value':'not-an-email','accepted':False})
            drafts.append({'name':f'Draft: {page["url"]} {ident}','path':page['url'],'selector':selector,'cases':cases})
    return {'warning':'Draft cases inferred from current HTML. A broken implementation can contain wrong limits: verify against independent requirements. Redacted query URLs must be restored locally. Review before copying fields into your configuration.','fields':drafts}
