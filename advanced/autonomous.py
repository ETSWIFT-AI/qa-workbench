"""Bounded, evidence-driven browser exploration. Rule-based planning, no LLM claims."""
import asyncio
import hashlib
import json
import re
from collections import deque
from pathlib import Path
from urllib.parse import urljoin,urlsplit,unquote
from qa.core import canonical,origin,display_url

RISK=re.compile(r'\b(delete|remove|save|confirm|approve|invite|purchase|pay|payment|checkout|buy|order|send|publish|post|transfer|withdraw|subscribe|unsubscribe|logout|signout|sign out|log out|register|registration|signup|sign up|reset|forgot|upload|download)\b',re.I)
LOGIN=re.compile(r'\b(log\s*in|sign\s*in|login|signin|authenticate)\b',re.I)
SAFE_BUTTON=re.compile(r'^(menu|open menu|close menu|navigation|next|previous|back|show more|show less|expand|collapse|details|close|cancel|search|log in|sign in|login|signin)$',re.I)
class BudgetReached(Exception):pass

CONTROLS='a[href],button,[role=button],[role=tab],[role=menuitem],summary,input[type=submit]'

INVENTORY=r'''() => {
 const visible=e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return !!r.width&&!!r.height&&s.display!=='none'&&s.visibility!=='hidden'};
 const name=e=>(e.getAttribute('aria-label')||e.labels?.[0]?.innerText||e.innerText||e.value||e.name||'').trim().slice(0,100);
 const inputs=[...document.querySelectorAll('input,textarea,select')];
 const controls=[...document.querySelectorAll('a[href],button,[role=button],[role=tab],[role=menuitem],summary,input[type=submit]')];
 return {title:document.title,url:location.href,text:(document.body?.innerText||'').slice(0,18000),
 fields:inputs.map((e,i)=>({index:i,type:e.type||e.tagName.toLowerCase(),name:name(e),id:e.id,autocomplete:e.autocomplete,visible:visible(e),disabled:e.disabled,form:e.form?[...document.forms].indexOf(e.form):-1,min:e.min,max:e.max,required:e.required})),
 controls:controls.map((e,i)=>({index:i,tag:e.tagName.toLowerCase(),role:e.getAttribute('role')||'',name:name(e),href:e.href||'',type:e.type||'',visible:visible(e),disabled:!!e.disabled,form:e.form?[...document.forms].indexOf(e.form):-1,expanded:e.getAttribute('aria-expanded'),selected:e.getAttribute('aria-selected')})),
 forms:[...document.forms].map((e,i)=>({index:i,action:e.action,method:e.method})),
 challenge:!!document.querySelector('input[autocomplete="one-time-code"],iframe[src*="recaptcha"],iframe[src*="hcaptcha"]')||/captcha|verification code|one.time password/i.test((document.body?.innerText||'').slice(0,10000)),
 signedIn:/sign out|log out|logout/i.test(document.body?.innerText||''),
 loginError:/invalid (password|credentials|username)|incorrect (password|credentials)|login failed|sign.in failed/i.test(document.body?.innerText||'')};
}'''

def same_origin(base,url):
    try:return origin(base)==origin(url)
    except (ValueError,TypeError):return False

def safe_url(base,url):
    try:
        dest=canonical(urljoin(base,url));p=urlsplit(dest)
        return dest if same_origin(base,dest) and not RISK.search(unquote(p.path+' '+p.query).replace('_',' ').replace('-',' ')) else None
    except (ValueError,TypeError):return None

def login_form(view,base):
    passwords=[f for f in view['fields'] if f['type']=='password' and f['visible'] and not f['disabled']]
    if len(passwords)!=1:return None
    password=passwords[0]
    if password.get('autocomplete')=='new-password':return None
    users=[f for f in view['fields'] if f['type'] in ('text','email') and f['visible'] and not f['disabled'] and f['form']==password['form']]
    semantic=[f for f in users if re.search(r'user|email|login',f['name']+' '+f['id']+' '+f.get('autocomplete',''),re.I)]
    users=semantic or users
    buttons=[c for c in view['controls'] if c['visible'] and not c['disabled'] and c['form']==password['form'] and LOGIN.search(c['name']) and not RISK.search(c['name'])]
    if len(users)!=1 or len(buttons)!=1:return None
    form=next((f for f in view['forms'] if f['index']==password['form']),None)
    if form and not same_origin(base,form['action']):return None
    return {'username':users[0],'password':password,'submit':buttons[0],'action':form['action'] if form else view['url'],'policy_confidence':'high','basis':'One visible password field, one identifiable username/email field, and one explicitly labelled sign-in control in the same form'}

def choose_actions(view,base,allow_actions):
    chosen=[]
    for c in view['controls']:
        if not c['visible'] or c['disabled']:continue
        text=c['name']+' '+unquote(c['href'])
        if RISK.search(text.replace('_',' ').replace('-',' ')):continue
        if c['tag']=='a' and c['href']:
            dest=safe_url(base,c['href'])
            if dest:chosen.append({'kind':'navigate','target':dest,'name':c['name'],'priority':0 if LOGIN.search(c['name']) else 2})
        elif allow_actions and c['form']==-1:
            if c['role']=='tab' or c['tag']=='summary' or c['expanded'] is not None or SAFE_BUTTON.fullmatch(c['name']):
                if sum(x['visible'] and x['name']==c['name'] and x['role']==c['role'] for x in view['controls'])!=1:continue
                chosen.append({'kind':'click','index':c['index'],'name':c['name'],'role':c['role'],'priority':1,'basis':'Recognized navigation/disclosure control, outside a form'})
    return sorted(chosen,key=lambda a:a['priority'])

async def explore_site(url,out,allow_actions=False,username=None,password=None,max_actions=20,max_states=12,max_seconds=120,timeout_ms=6000):
    from playwright.async_api import async_playwright
    base=canonical(url);out=Path(out);out.mkdir(parents=True,exist_ok=True)
    result={'mode':'ACTIONS_ENABLED' if allow_actions else 'READ_ONLY','planner':'Deterministic semantic heuristics, not a trained neural agent','target':display_url(base),'states':[],'actions':[],'findings':[],'questions':[],'blocked':[],'limits':{'actions':max_actions,'states':max_states,'seconds':max_seconds},'scope':'Observed behaviour only. No credential guessing, arbitrary form submission, purchase/delete/send actions, cross-origin login or CAPTCHA bypass. GETs and site scripts may still have side effects.'}
    secrets=[v for v in (username,password) if v];pending=deque([(base,[])]);seen=set();attempted=set();queued_navigations={base};login_attempted=False;search_attempted=False;permit_login=False;login_destination=None
    def ask(text):
        if text not in result['questions']:result['questions'].append(text)
    def finding(kind,detail,status='REVIEW'):
        result['findings'].append({'status':status,'kind':kind,'detail':detail})
    async def snapshot(page):
        view=await page.evaluate(INVENTORY)
        digest=hashlib.sha256(json.dumps({'url':view['url'],'text':view['text'],'controls':view['controls']},sort_keys=True).encode()).hexdigest()[:16]
        return view,digest
    async def shot(page,name):
        try:
            # Mask field values and literal test credentials wherever Playwright can locate them.
            masks=[page.locator('input,textarea,select')]+[page.get_by_text(s,exact=False) for s in secrets]
            await page.screenshot(path=str(out/name),mask=masks,animations='disabled',timeout=timeout_ms)
            return name
        except Exception:return None
    async def work():
        nonlocal login_attempted,search_attempted,permit_login,login_destination
        async with async_playwright() as pw:
            browser=await pw.chromium.launch()
            context=await browser.new_context(service_workers='block',ignore_https_errors=False)
            context.set_default_timeout(timeout_ms)
            async def guard(route):
                req=route.request
                bad_origin=not same_origin(base,req.url)
                dangerous=RISK.search(unquote(urlsplit(req.url).path+' '+urlsplit(req.url).query).replace('_',' ').replace('-',' '))
                mutation=req.method not in ('GET','HEAD','OPTIONS')
                login_path=urlsplit(login_destination).path if login_destination else None
                auth_endpoint=urlsplit(req.url).path==login_path or bool(re.search(r'/(login|signin|sign-in|auth|session|token)(/|$)',urlsplit(req.url).path,re.I))
                blocked=((req.is_navigation_request() or login_attempted) and bad_origin) or bool(dangerous) or (mutation and (not permit_login or bad_origin or req.method!='POST' or not auth_endpoint))
                if blocked:
                    if len(result['blocked'])<50:result['blocked'].append({'url':display_url(req.url),'method':req.method,'reason':'outside origin, blocked action, or mutation outside sign-in window'})
                    await route.abort()
                else:await route.continue_()
            await context.route('**/*',guard)
            page=await context.new_page();events=[]
            def record(kind,value):
                if len(events)<100:events.append({'kind':kind,'detail':str(value)[:500]})
            page.on('pageerror',lambda e:record('javascript',e))
            page.on('response',lambda r:record('http',str(r.status)+' '+display_url(r.url)) if r.status>=400 else None)
            page.on('dialog',lambda d:asyncio.create_task(d.dismiss()))
            page.on('popup',lambda p:asyncio.create_task(p.close()))
            try:
                while pending and len(seen)<max_states and len(result['actions'])<max_actions:
                    start,sequence=pending.popleft();events.clear()
                    try:
                        response=await page.goto(start,wait_until='domcontentloaded');await page.wait_for_timeout(250)
                        if response and response.status>=400:finding('Document HTTP error',{'url':display_url(start),'status':response.status},'FAIL')
                        for action in sequence:
                            nodes=page.locator(CONTROLS);node=nodes.nth(action['index'])
                            current=await page.evaluate(INVENTORY)
                            actual=next((x for x in current['controls'] if x['index']==action['index']),None)
                            if not actual or actual['name']!=action['name'] or actual['role']!=action['role']:raise ValueError('Control changed during replay; ambiguous action refused')
                            if len(result['actions'])>=max_actions:raise BudgetReached()
                            await node.click();await page.wait_for_timeout(200)
                            result['actions'].append({'kind':'click','control':action['name'],'replay':True,'status':'REVIEW','note':'Replayed recognized control to explore this path; effects are observed in the resulting state.'})
                        view,key=await snapshot(page)
                        if key in seen:continue
                        seen.add(key);before=await shot(page,'state-'+key+'.png')
                        result['states'].append({'id':key,'url':display_url(view['url']),'title':view['title'],'screenshot':before,'controls_seen':len(view['controls']),'fields_seen':len(view['fields']),'events':events.copy()})
                        if events:
                            finding('Runtime/network observations',events.copy(),'FAIL' if any(e['kind']=='javascript' for e in events) else 'REVIEW')
                        login=login_form(view,base)
                        if view['challenge']:ask('This flow needs CAPTCHA/MFA or a verification code. Complete it manually; no bypass is attempted.')
                        if login and not login_attempted and not view['challenge']:
                            if not allow_actions:ask('A login form was found. Enable autonomous actions on a test environment to exercise it.')
                            elif not username or not password:ask('A login form was found. Supply a test username and password to authenticate; selectors are detected automatically.')
                            elif urlsplit(base).scheme!='https' and urlsplit(base).hostname not in ('localhost','127.0.0.1','::1'):ask('Credentials require HTTPS, except for a local development server.')
                            else:
                                login_attempted=True
                                fields=page.locator('input,textarea,select')
                                # The form must still have the same unique interpretation just before filling.
                                fresh=await page.evaluate(INVENTORY)
                                if login_form(fresh,base)!=login:raise ValueError('Login controls changed before action')
                                login_destination=login['action'];permit_login=True
                                try:
                                    await fields.nth(login['username']['index']).fill(username)
                                    await fields.nth(login['password']['index']).fill(password)
                                    await page.locator(CONTROLS).nth(login['submit']['index']).click()
                                    await page.wait_for_timeout(800)
                                finally:permit_login=False
                                after,after_key=await snapshot(page);image=await shot(page,'login-after-'+after_key+'.png')
                                outcome='CHALLENGE' if after['challenge'] else 'CREDENTIALS_REJECTED' if after['loginError'] else 'LIKELY_AUTHENTICATED' if after['signedIn'] and not login_form(after,base) else 'UNCONFIRMED'
                                result['actions'].append({'kind':'login','before':before,'after':image,'outcome':outcome,'status':'REVIEW','basis':login['basis'],'note':'One supplied-credential attempt only. Sign-out UI is evidence, not proof of server authorization or role correctness.'})
                                if outcome=='UNCONFIRMED':ask('What should appear after a successful login? The observed page does not establish the expected outcome.')
                                if outcome=='CHALLENGE':ask('Login requires a verification step; complete it manually.')
                                if outcome=='CREDENTIALS_REJECTED':ask('The site rejected the supplied credentials. Check the test account; no retry or password guessing was performed.')
                                # Continue from current authenticated page; cookies remain in memory only.
                                view=after;key=after_key
                                result['states'].append({'id':key,'url':display_url(view['url']),'title':view['title'],'screenshot':image,'controls_seen':len(view['controls']),'fields_seen':len(view['fields']),'events':events.copy()})
                                start=view['url'];sequence=[];before=image
                        if allow_actions and not search_attempted and len(result['actions'])<max_actions:
                            searches=[f for f in view['fields'] if f['type']=='search' and f['visible'] and not f['disabled']]
                            if len(searches)==1:
                                field=searches[0];form=next((f for f in view['forms'] if f['index']==field['form']),None)
                                if form and form['method'].lower()=='get' and safe_url(base,form['action']):
                                    search_attempted=True
                                    loc=page.locator('input,textarea,select').nth(field['index'])
                                    await loc.fill('test');await loc.press('Enter');await page.wait_for_timeout(300)
                                    view,key=await snapshot(page);image=await shot(page,'search-after-'+key+'.png')
                                    result['actions'].append({'kind':'search','query':'test','before':before,'after':image,'status':'REVIEW','note':'One identified GET search exercised. Result relevance and expected count need independent requirements.'})
                                    start=view['url'];sequence=[];before=image
                        if allow_actions:
                            # Probe native constraints on detached clones: no events, no application writes.
                            checks=await page.locator('input[type=number],input[type=email]').evaluate_all(r'''es=>es.slice(0,20).map(e=>{const c=e.cloneNode(true);const cases=[];const probe=v=>{c.value=v;cases.push({input:v,value:c.value,valid:c.checkValidity()})};probe('');if(e.type==='email')probe('not-an-email');if(e.type==='number'){if(e.min!=='')probe(String(Number(e.min)-1));if(e.max!=='')probe(String(Number(e.max)+1))}return {id:e.id,name:e.name,type:e.type,min:e.min,max:e.max,required:e.required,cases}})''')
                            if checks:finding('Declared native constraints',{'checks':checks,'note':'Detached DOM clones only. Business limits, custom validation and submission were not tested.'})
                        planned=choose_actions(view,base,allow_actions)
                        for navigation in [a for a in planned if a['kind']=='navigate']:
                            if navigation['target'] not in queued_navigations and len(pending)<max_states*3:
                                queued_navigations.add(navigation['target'])
                                if navigation['priority']==0:pending.appendleft((navigation['target'],[]))
                                else:pending.append((navigation['target'],[]))
                        for action in [a for a in planned if a['kind']=='click']:
                            token=(key,json.dumps(action,sort_keys=True))
                            if token in attempted:continue
                            attempted.add(token)
                            if action['kind']=='navigate':
                                if len(pending)<max_states*3:pending.append((action['target'],[]))
                            elif len(sequence)<3 and len(result['actions'])<max_actions:
                                before_view=await page.evaluate(INVENTORY)
                                actual=next((c for c in before_view['controls'] if c['index']==action['index']),None)
                                if not actual or actual['name']!=action['name']:continue
                                try:
                                    event_start=len(events)
                                    await page.locator(CONTROLS).nth(action['index']).click();await page.wait_for_timeout(250)
                                    after,after_key=await snapshot(page);image=await shot(page,'action-'+str(len(result['actions']))+'.png')
                                    changed=key!=after_key
                                    if any(e['kind']=='javascript' for e in events[event_start:]):finding('JavaScript error observed after action',{'control':action['name'],'events':events[event_start:]},'FAIL')
                                    result['actions'].append({'kind':'click','control':action['name'],'reason':action['basis'],'before':before,'after':image,'changed':changed,'status':'REVIEW','note':'Change observed; intended outcome not assumed.' if changed else 'No sampled DOM/URL change; may be a no-op, delayed effect or unobserved behaviour.'})
                                    if changed and len(pending)<max_states*3:pending.appendleft((start,sequence+[action]))
                                except Exception as exc:finding('Control action error',type(exc).__name__+': '+str(exc)[:300],'ERROR')
                                # One action from a state; revisit/replay before trying siblings.
                                for sibling in choose_actions(view,base,allow_actions):
                                    if sibling['kind']=='click' and sibling!=action and len(pending)<max_states*3:
                                        pending.append((start,sequence+[sibling]))
                                break
                    except BudgetReached:
                        pending.appendleft((start,sequence));break
                    except Exception as exc:finding('Exploration interrupted',type(exc).__name__+': '+str(exc)[:500],'ERROR')
                result['remaining_paths']=len(pending)
                result['stopped_by_budget']=bool(pending)
            finally:await context.close();await browser.close()
    try:await asyncio.wait_for(work(),timeout=max_seconds)
    except asyncio.TimeoutError:finding('Time budget','Partial exploration; time budget reached','ERROR')
    except Exception as exc:finding('Browser startup/execution',type(exc).__name__+': '+str(exc)[:500],'ERROR')
    def redact(value):
        if isinstance(value,str):
            for secret in secrets:value=value.replace(secret,'[REDACTED]')
            return value
        if isinstance(value,list):return [redact(v) for v in value]
        if isinstance(value,dict):return {k:redact(v) for k,v in value.items()}
        return value
    result=redact(result)
    (out/'autonomous.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result
