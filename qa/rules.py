import asyncio
import os
import time
from pathlib import Path
from .core import scoped, load_json
from .healing import load_cache, save_cache, resolve as resolve_locator


def resolve_value(step):
    if 'value_env' in step:
        name=step['value_env']
        if name not in os.environ: raise ValueError('Missing environment variable: '+name)
        return os.environ[name]
    return str(step.get('value',''))


async def journeys(browser, context_factory, cfg, base, report, out, allowed, repeats, variant="chromium/desktop", viewport="desktop"):
    from playwright.async_api import expect
    locator_cache=load_cache(out)
    if not cfg.get('journeys'):
        report.add('journeys','Business journeys','SKIP','No expected journeys configured')
    for test in cfg.get('journeys',[]):
        severity='critical' if test.get('critical') else 'high'
        if not allowed:
            report.add('journeys',variant+': '+test['name'],'SKIP','Use --allow-actions on a disposable test environment',severity=severity)
            continue
        for repetition in range(repeats):
            ctx=await context_factory(browser, test.get('storage_state'),viewport=viewport)
            page=await ctx.new_page()
            label=f"{variant}: {test['name']} [run {repetition+1}]"
            url=scoped(base,test['path'])
            trace=out/f'journey-{len(report.results)}.zip'
            healed_steps=[]
            await ctx.tracing.start(screenshots=True,snapshots=True,sources=False)
            try:
                await page.goto(url,wait_until='domcontentloaded')
                for step_index,step in enumerate(test['steps']):
                    action=step['action']
                    if action=='goto': await page.goto(scoped(base,step['value'])); continue
                    if action=='url': await expect(page).to_have_url(scoped(base,step['value'])); continue
                    loc,healed,strategy=await resolve_locator(page,test['name'],step_index,step,locator_cache,report,url,variant)
                    if healed: healed_steps.append(f'step {step_index+1} via {strategy}')
                    if action=='click': await loc.click()
                    elif action=='fill': await loc.fill(resolve_value(step))
                    elif action=='press': await loc.press(resolve_value(step))
                    elif action=='select': await loc.select_option(resolve_value(step))
                    elif action=='check': await loc.check()
                    elif action=='uncheck': await loc.uncheck()
                    elif action=='visible': await expect(loc).to_be_visible()
                    elif action=='hidden': await expect(loc).to_be_hidden()
                    elif action=='enabled': await expect(loc).to_be_enabled()
                    elif action=='disabled': await expect(loc).to_be_disabled()
                    elif action=='text': await expect(loc).to_have_text(resolve_value(step))
                    elif action=='value': await expect(loc).to_have_value(resolve_value(step))
                    elif action=='count': await expect(loc).to_have_count(int(step['value']))
                detail='All configured steps/assertions passed'+((' (self-healed: '+'; '.join(healed_steps)+')') if healed_steps else '')
                report.add('journeys',label,'PASS',detail,url,severity,evidence=trace.name,requirement=test.get('requirement',''))
            except AssertionError as exc:
                report.add('journeys',label,'FAIL',str(exc),url,severity,trace.name,test.get('requirement',''))
            except Exception as exc:
                # Selector timeouts and infrastructure failures need diagnosis, not automatic defect claims.
                report.add('journeys',label,'ERROR',str(exc),url,severity,trace.name,test.get('requirement',''))
            finally:
                await ctx.tracing.stop(path=str(trace))
                await ctx.close()
    save_cache(out,locator_cache)


async def fields(browser,context_factory,cfg,base,report,allowed,out,variant="chromium/desktop",viewport="desktop",family="boundary_rules"):
    locator_cache=load_cache(out)
    if not cfg.get('fields'): report.add(family,'Boundary tests','SKIP','No approved input requirements configured')
    for test in cfg.get('fields',[]):
        if not allowed:
            report.add(family,variant+': '+test['name'],'SKIP','Field events may save data; use --allow-actions')
            continue
        for i,case in enumerate(test['cases']):
            ctx=await context_factory(browser,test.get('storage_state'),viewport=viewport)
            page=await ctx.new_page()
            url=scoped(base,test['path'])
            try:
                await page.goto(url)
                field,_healed,_strategy=await resolve_locator(page,'field:'+test['name'],0,{'selector':test['selector']},locator_cache,report,url,variant)
                raw=str(case['value'])
                await field.fill('')
                await field.press_sequentially(raw)
                await field.press('Tab')
                if test.get('submit_selector'): await page.locator(test['submit_selector']).click()
                error_selector=case.get('error_selector')
                if error_selector:
                    from playwright.async_api import expect
                    if case['accepted']: await expect(page.locator(error_selector)).to_be_hidden()
                    else: await expect(page.locator(error_selector)).to_be_visible()
                    matched=True
                    detail='Configured custom error visibility assertion passed; does not verify persistence'
                else:
                    value=await field.input_value()
                    valid=await field.evaluate('(e)=>e.checkValidity()')
                    matched=((value==raw and valid)==case['accepted'])
                    detail=f"Input {raw!r}; observed {value!r}; native validity {valid}; expected accepted {case['accepted']}"
                report.add(family,f"{variant}: {test['name']} case {i+1}",'PASS' if matched else 'FAIL',detail,url,'high',requirement=test.get('requirement',''))
            except AssertionError as exc:
                report.add(family,f"{variant}: {test['name']} case {i+1}",'FAIL',str(exc),url,'high')
            except Exception as exc:
                report.add(family,f"{variant}: {test['name']} case {i+1}",'ERROR',str(exc),url,'high')
            finally: await ctx.close()
    save_cache(out,locator_cache)


def json_value(data,path):
    current=data
    for key in path.split('.'):
        current=current[int(key)] if isinstance(current,list) else current[key]
    return current


async def api_tests(pw,cfg,base,report,allowed,timeout):
    if not cfg.get('api_tests'): report.add('api_contracts','API contracts','SKIP','No endpoint expectations configured')
    if not any(t.get('authorization_test') for t in cfg.get('api_tests',[])):
        report.add('authorization','Role-based access','SKIP','Configure allowed/denied cases for each role and object owner')
    for test in cfg.get('api_tests',[]):
        family='authorization' if test.get('authorization_test') else 'api_contracts'
        method=test.get('method','GET').upper()
        url=scoped(base,test['path'])
        if method not in ('GET','HEAD','OPTIONS') and not allowed:
            report.add(family,test['name'],'SKIP','Mutation requires --allow-actions',url,'high'); continue
        ctx=None
        try:
            headers=dict(test.get('headers',{}))
            for key,env_name in test.get('headers_env',{}).items(): headers[key]=os.environ[env_name]
            ctx=await pw.request.new_context(extra_http_headers=headers,storage_state=test.get('storage_state'),timeout=timeout,ignore_https_errors=False)
            start=time.perf_counter()
            response=await ctx.fetch(url,method=method,data=test.get('json'),max_redirects=0)
            duration=(time.perf_counter()-start)*1000
            errors=[]
            if response.status != test['expected_status']: errors.append(f"Expected HTTP {test['expected_status']}, received {response.status}")
            if test.get('max_ms') is not None and duration>test['max_ms']: errors.append(f'Response {duration:.0f} ms exceeds budget')
            for key,value in test.get('expected_headers',{}).items():
                if response.headers.get(key.lower()) != value: errors.append(f'Header mismatch: {key}')
            if test.get('json_equals'):
                try:
                    body=await response.json()
                    for path,value in test['json_equals'].items():
                        if json_value(body,path)!=value: errors.append(f'JSON mismatch at {path}')
                except (ValueError,KeyError,IndexError,TypeError): errors.append('Missing or invalid expected JSON')
            report.add(family,test['name'],'FAIL' if errors else 'PASS','; '.join(errors) if errors else f'Configured assertions passed; {duration:.0f} ms; role={test.get("role","unspecified")}',url,'critical' if family=='authorization' else 'high',requirement=test.get('requirement',''))
        except Exception as exc: report.add(family,test['name'],'ERROR',str(exc),url,'high')
        finally:
            if ctx: await ctx.dispose()


def evidence(cfg,report):
    for family in ('requirements','operations'):
        rows=[e for e in cfg.get('evidence',[]) if e['family']==family]
        if not rows: report.add(family,'Lifecycle evidence','SKIP','Supply reviewed requirement traceability or deployment/rollback/monitoring evidence')
        for e in rows:
            path=Path(e.get('path',''))
            ok=path.is_file() and bool(e.get('reviewer')) and e.get('approved') is True
            report.add(family,e.get('name','Manual evidence'),'PASS' if ok else 'REVIEW',f"User-attested review by {e.get('reviewer','missing')}; file {path.name}. Contents/approval authenticity not independently verified.")
