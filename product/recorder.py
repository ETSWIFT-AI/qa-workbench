"""Visible local browser recorder. Never records input values or login state."""
import argparse
import asyncio
import json
from pathlib import Path
from urllib.parse import urlsplit
from qa.core import canonical,origin

SCRIPT=r'''(() => {
function selector(e){
 if(e.id) return '#'+CSS.escape(e.id);
 for(const k of ['data-testid','name']) if(e.getAttribute(k)){
  const s=e.tagName.toLowerCase()+'['+k+'='+JSON.stringify(e.getAttribute(k))+']';
  if(document.querySelectorAll(s).length===1)return s;
 }
 const a=[];while(e&&e.nodeType===1&&e!==document.documentElement){
  let s=e.tagName.toLowerCase(),n=1,p=e;while((p=p.previousElementSibling))if(p.tagName===e.tagName)n++;
  a.unshift(s+':nth-of-type('+n+')');e=e.parentElement;
 }return a.join(' > ');
}
addEventListener('click',e=>{
 if(e.altKey){e.preventDefault();e.stopImmediatePropagation();
  const value=prompt('Expected text (your requirement, not an automatic approval):');
  if(value!==null)window.qaRecord({action:'text',selector:selector(e.target),value});return;
 }
 const el=e.target.closest('button,a,input[type=submit],[role=button]');
 if(el)window.qaRecord({action:'click',selector:selector(el)});
},true);
const changed=e=>{
 const el=e.target;if(!el.matches('input,textarea,select')||el.type==='file')return;
 if(['checkbox','radio'].includes(el.type))window.qaRecord({action:el.checked?'check':'uncheck',selector:selector(el)});
 else window.qaRecord({action:el.tagName==='SELECT'?'select':'fill',selector:selector(el),privateInput:true});
};
addEventListener('input',changed,true);addEventListener('change',changed,true);
addEventListener('keydown',e=>{if(e.key==='Enter'&&e.target.matches('input,textarea'))window.qaRecord({action:'press',selector:selector(e.target),value:'Enter'});},true);
})();'''

async def record(url,path,max_seconds=900):
    from playwright.async_api import async_playwright
    base=canonical(url);steps=[];variables={};path=Path(path)
    def write():
        draft={'journeys':[{'name':'Recorded workflow — review expected outcomes','path':(urlsplit(base).path or '/')+('?' + urlsplit(base).query if urlsplit(base).query else ''), 'critical':True,'steps':steps}]}
        path.write_text(json.dumps({'draft':draft,'required_inputs':list(variables.values()),'review_required':True,'note':'Input values were not recorded. Add an assertion and review the workflow before saving.'},indent=2),encoding='utf-8')
    write()
    async with async_playwright() as pw:
        browser=await pw.chromium.launch(headless=False,timeout=15000)
        context=await browser.new_context()
        async def guard(route):
            if route.request.is_navigation_request():
                try:allowed=origin(route.request.url)==origin(base)
                except ValueError:allowed=False
                if not allowed:await route.abort();return
            await route.continue_()
        await context.route('**/*',guard)
        async def capture(source,event):
            try:
                if origin(source['frame'].url)!=origin(base):return
            except ValueError:return
            if len(steps)>=500:return
            action=event.get('action');selector=event.get('selector','')
            if action not in ('click','fill','select','check','uncheck','text','press') or not selector or len(selector)>2000:return
            step={'action':action,'selector':selector}
            if action in ('fill','select'):
                if selector not in variables:variables[selector]='QA_INPUT_'+str(len(variables)+1)
                step['value_env']=variables[selector]
            elif action in ('text','press'):step['value']=str(event.get('value',''))[:2000]
            if steps and action=='fill' and steps[-1].get('selector')==selector and steps[-1]['action']=='fill':steps[-1]=step
            else:steps.append(step)
            write()
        await context.expose_binding('qaRecord',capture)
        await context.add_init_script(SCRIPT)
        page=await context.new_page()
        done=asyncio.Event();browser.on('disconnected',lambda:done.set());page.on('close',lambda:done.set())
        try:
            await page.goto(base,wait_until='domcontentloaded',timeout=30000)
            print('Recording. Alt+click an element to add an expected-text assertion. Close the browser when finished.',flush=True)
            try:await asyncio.wait_for(done.wait(),max_seconds)
            except asyncio.TimeoutError:print('Recording time limit reached.',flush=True)
        finally:
            write();await browser.close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('url');p.add_argument('output');a=p.parse_args()
    asyncio.run(record(a.url,a.output))
