import asyncio
import hashlib
import json
import time
from datetime import datetime,timezone
import uuid
from pathlib import Path
from urllib.parse import urlsplit
from .core import Report,canonical,origin,scoped,display_url,validate_config,load_json
from .browser_checks import OBSERVER,inspect,performance
from .rules import journeys,fields,api_tests,evidence
from .integrations import visual_compare,import_zap,import_sarif
from .reporting import resolutions,render
from .ai import analyse
from .exploration import explore,suggest_fields
from .core import write_json
from .history import save_run
from .security import zap_baseline
from .field_metrics import field_metrics

VIEWPORTS={'desktop':{'width':1440,'height':900},'mobile':{'width':390,'height':844},'tablet':{'width':768,'height':1024}}


async def run(args):
    from playwright.async_api import async_playwright
    base=canonical(args.url)
    cfg=validate_config(load_json(args.config) if args.config else {},base)
    out=Path(args.output or ('reports/run-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6]))
    out.mkdir(parents=True,exist_ok=True)
    settings={k:getattr(args,k) for k in ('max_pages','browsers','viewports','repeats','allow_actions','timeout_ms','max_seconds','auto_fields','explore_actions','exploration_depth','max_states','load_ms','lcp_ms','cls','blocking_ms','journey_repeats','settle_ms','delay_ms','action_limit','zap_baseline','visual_threshold')}
    settings['config_digest']=hashlib.sha256(json.dumps(cfg,sort_keys=True).encode()).hexdigest()
    for key in ('storage_state','axe','baselines','zap_report','sarif','resolutions','executable'):
        value=getattr(args,key)
        settings[key+'_configured']=bool(value)
        if value and Path(value).is_file(): settings[key+'_digest']=hashlib.sha256(Path(value).read_bytes()).hexdigest()
    report=Report(base,settings)
    report.notes.extend([
      'Tested quality excludes unknown checks. Coverage is separate: high quality with low coverage is a partial assessment, not proof of complete software quality.',
      'Default mode does not click or fill controls, and blocks non-GET/HEAD/OPTIONS requests. Site scripts and GET requests can still have side effects. Use staging.',
      'AI suggestions never alter deterministic results. Imported scanner alerts need confirmation.',
      'Reports, screenshots, traces and inventories can contain private information. Query values are redacted in displayed URLs, but artifacts and error messages may contain sensitive data.',
      'Cross-origin navigations are blocked; external subresources may load. Login states, if configured, contain sensitive credentials.',
      'Keyboard focus order, native form requirements and scanner completeness need human review. Reviews cannot be silently counted as passes.',
      'No active exploit scan or load/stress test is performed. Optional ZAP baseline spiders and passively analyses responses. Performance lab and CrUX field observations remain separate.',
      'Self-healing locators: when a configured selector stops matching, cached element attributes (id/testid/role/label/text) are used to try alternative fallback strategies. Only high-confidence matches are applied automatically (logged under "self_healing"); lower-confidence candidates are flagged for review, not silently substituted. Healing keeps a journey/field test executable; it does not by itself confirm the workflow behaves correctly \u2014 see the journeys/boundary_rules result for that. Profiles are cached in locator-cache.json under the report output directory.',
    ])
    exclude=cfg.get('exclude_paths',['logout','signout','delete','remove','checkout'])
    report.notes.append('ACTION MODE: approved workflow actions enabled.' if args.allow_actions else 'READ-ONLY MODE: submissions, checkouts and state-changing workflows were NOT tested. This is not a clean bill of health.')
    blocked=set()
    discovery_pages=[]
    async def guard(route):
        req=route.request
        try:
            off=req.is_navigation_request() and origin(req.url)!=origin(base)
        except ValueError: off=True
        mutating=not args.allow_actions and req.method not in ('GET','HEAD','OPTIONS')
        if off or mutating:
            key=(display_url(req.url),req.method)
            if key not in blocked:
                blocked.add(key)
                report.add('network_errors','Request excluded','SKIP',f'{req.method}; '+('outside target origin' if off else 'read-only mode'),req.url)
            await route.abort()
        else: await route.continue_()

    async def context_factory(browser,state=None,viewport='desktop'):
        ctx=await browser.new_context(storage_state=state or args.storage_state,viewport=VIEWPORTS[viewport],service_workers='block',ignore_https_errors=False,reduced_motion='reduce')
        ctx.set_default_timeout(args.timeout_ms)
        await ctx.route('**/*',guard)
        await ctx.add_init_script('('+OBSERVER+')()')
        return ctx

    async def work():
        async with async_playwright() as pw:
            engines={}
            for name in args.browsers:
                candidate=None
                try:
                    kwargs={'headless':True}
                    if args.executable and name=='chromium': kwargs['executable_path']=args.executable
                    candidate=await asyncio.wait_for(getattr(pw,name).launch(**kwargs),timeout=20)
                    probe=await asyncio.wait_for(candidate.new_page(),timeout=10)
                    await asyncio.wait_for(probe.close(),timeout=5)
                    engines[name]=candidate
                except Exception as exc:
                    report.add('browser_matrix',name,'ERROR',str(exc) or 'Browser startup/blank-page health check timed out','','high')
                    if candidate:
                        try: await asyncio.wait_for(candidate.close(),timeout=5)
                        except Exception: pass
            if len(args.browsers)<2: report.add('browser_matrix','Engine coverage','SKIP','Only one engine requested; add firefox and/or webkit')
            if len(args.viewports)<2: report.add('responsive','Viewport coverage','SKIP','Only one viewport requested')
            queue=[base]; seen={base}; processed=[]
            try:
                while queue and len(processed)<args.max_pages and engines:
                    url=queue.pop(0); processed.append(url)
                    print(f'Inspecting {display_url(url)}',flush=True)
                    for engine,browser in engines.items():
                        for viewport in args.viewports:
                            variant=engine+'/'+viewport
                            print('Page checks: '+variant,flush=True)
                            samples=[]
                            for sample in range(args.repeats):
                                ctx=await context_factory(browser,viewport=viewport)
                                page=await ctx.new_page()
                                errors=[]; failures=[]; statuses=[]
                                page.on('pageerror',lambda e:errors.append(str(e)))
                                page.on('requestfailed',lambda r:failures.append({'url':display_url(r.url),'reason':r.failure}))
                                page.on('response',lambda r:statuses.append({'url':display_url(r.url),'status':r.status}) if r.status>=400 else None)
                                try:
                                    start=time.perf_counter()
                                    response=await page.goto(url,wait_until='load')
                                    load=(time.perf_counter()-start)*1000
                                    await page.wait_for_timeout(args.settle_ms)
                                    metrics=await page.evaluate('window.__qaMetrics')
                                    samples.append({'load_ms':round(load),'metrics':metrics})
                                    if sample==0:
                                        report.add('browser_matrix',variant,'PASS','Page loaded in this engine/viewport; configured workflows are separately tested across the matrix',url)
                                        inventory=await asyncio.wait_for(inspect(page,response,report,url,variant,out,args.axe,cfg.get('session_cookie_names',[]),args.action_limit),timeout=max(30,args.timeout_ms/1000*4))
                                        key=hashlib.sha256(url.encode()).hexdigest()[:12]
                                        shot=out/f'page-{key}-{engine}-{viewport}.png'
                                        # Return to top after actionability/tab tests; baseline has a stable viewport.
                                        await page.evaluate('window.scrollTo(0,0)')
                                        await page.screenshot(path=str(shot),animations='disabled')
                                        visual_compare(shot,args.baselines,report,url,variant,args.visual_threshold)
                                        public_inventory={k:v for k,v in inventory.items() if k not in ('links','insecureResources','brokenImages')}
                                        report.pages.append({'url':display_url(url),'variant':variant,'screenshot':shot.name,'inventory':public_inventory})
                                        discovery_pages.append({'url':url,'variant':variant,'inventory':public_inventory})
                                        if engine==next(iter(engines)) and viewport==args.viewports[0]:
                                            for link in inventory['links']:
                                                try: link=scoped(base,link)
                                                except (ValueError,TypeError): continue
                                                if any(str(word).lower() in urlsplit(link).path.lower() for word in exclude):
                                                    report.notes.append('Excluded route: '+display_url(link)); continue
                                                if link not in seen:
                                                    seen.add(link)
                                                    if len(seen)<=args.max_pages*20: queue.append(link)
                                                    else: report.add('http','Discovery limit','SKIP','Link discovery cap reached',base)
                                    label=f'{variant} sample {sample+1}'
                                    report.add('js_errors',label,'FAIL' if errors else 'PASS',json.dumps(errors) if errors else 'No uncaught page errors observed in sampling window',url,'high')
                                    network=failures+statuses
                                    report.add('network_errors',label,'REVIEW' if network else 'PASS',json.dumps(network) if network else 'No failed requests observed in sampling window',url)
                                except Exception as exc:
                                    report.add('http',variant,'ERROR',str(exc),url,'high')
                                finally: await ctx.close()
                            performance(report,url,variant,samples,args.load_ms,args.lcp_ms,args.cls,args.blocking_ms)
                    await asyncio.sleep(args.delay_ms/1000)
                if queue: report.add('http','Crawl coverage','SKIP',f'{len(queue)} discovered pages untested; max_pages={args.max_pages}',base)
                if engines:
                    # Every available requested engine × viewport runs the configured workflows.
                    for engine,browser in engines.items():
                        for viewport in args.viewports:
                            variant=engine+'/'+viewport
                            print('Workflow matrix: '+variant,flush=True)
                            await journeys(browser,context_factory,cfg,base,report,out,args.allow_actions,args.journey_repeats,variant,viewport)
                            await fields(browser,context_factory,cfg,base,report,args.allow_actions,out,variant,viewport)
                            if args.auto_fields:
                                drafts=suggest_fields([p for p in discovery_pages if p['variant']==variant])['fields']
                                # Draft cases verify consistency with declared HTML, not domain correctness.
                                await fields(browser,context_factory,{'fields':drafts},base,report,args.allow_actions,out,variant,viewport,family='native_forms')
                            if args.explore_actions:
                                discovered=await explore(browser,context_factory,processed,base,report,args.action_limit,args.exploration_depth,args.max_states,viewport,variant)
                                for route in discovered:
                                    if route not in seen:
                                        report.notes.append('Exploration discovered route for follow-up: '+display_url(route))
                    # Missing browser engines must also leave explicit missing workflow coverage.
                    for engine in set(args.browsers)-set(engines):
                        for viewport in args.viewports:
                            report.add('journeys',engine+'/'+viewport,'ERROR','Requested workflow matrix cell unavailable',severity='high')
                            report.add('boundary_rules',engine+'/'+viewport,'ERROR','Requested field matrix cell unavailable',severity='high')
                else:
                    report.add('journeys','Browser unavailable','ERROR','No browser engine could start',severity='high')
                    report.add('boundary_rules','Browser unavailable','ERROR','No browser engine could start',severity='high')
                await api_tests(pw,cfg,base,report,args.allow_actions,args.timeout_ms)
            finally:
                for browser in engines.values():
                    try: await asyncio.wait_for(browser.close(),timeout=5)
                    except Exception: pass

    try: await asyncio.wait_for(work(),timeout=args.max_seconds)
    except asyncio.TimeoutError: report.add('http','Run time limit','ERROR','Run was incomplete; increase --max-seconds or reduce scope',base,'high')
    except Exception as exc: report.add('http','Runner interruption','ERROR',str(exc),base,'high')
    zap_path=args.zap_report
    if args.zap_baseline: zap_path=await zap_baseline(base,out,report,timeout=args.zap_timeout)
    import_zap(zap_path,report,base)
    import_sarif(args.sarif,report)
    evidence(cfg,report)
    if args.resolutions:
        try: resolutions(report,args.resolutions)
        except Exception as exc: report.add('requirements','Review resolutions','ERROR',str(exc))
    if args.ai_model or args.vision_model or args.group_findings or args.triage_model or args.embedding_model:
        await asyncio.to_thread(analyse,report,args,out)
    write_json(out/'suggested-fields.json',suggest_fields(report.pages))
    report.field_data=await asyncio.to_thread(field_metrics,args,base)
    if not args.no_history:
        try: save_run(report,args.history)
        except Exception as exc: report.notes.append('History could not be saved: '+str(exc))
    render(report,out)
    print(json.dumps(report.score(),indent=2),flush=True)
    print('Report:',(out/'report.html').resolve())
    if any(r['status']=='ERROR' for r in report.results): return 2
    if args.enforce_gate and report.score()['gate']!='MEETS_CONFIGURED_GATE': return 3
    return 1 if any(r['status']=='FAIL' for r in report.results) else 0
