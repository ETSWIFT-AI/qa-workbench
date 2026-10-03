"""Thorough scan with dependency preflight and strict incomplete-run reporting."""
import argparse
import asyncio
from datetime import datetime, timezone
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
import uuid
from qa.completeness import summarize, save

ROOT=Path(__file__).resolve().parent


def build_args(url, forwarded, output):
    from tester import parse_args
    defaults=[url,'--browsers','chromium,firefox,webkit','--viewports','desktop,mobile,tablet',
        '--repeats','3','--journey-repeats','2','--max-pages','50','--action-limit','500',
        '--max-states','100','--exploration-depth','3','--max-seconds','1800',
        '--axe',str(ROOT/'node_modules/axe-core/axe.min.js')]
    args=parse_args(defaults+forwarded+['--output',str(output)])
    if args.repeats < 3: raise ValueError('Thorough mode needs at least 3 repetitions')
    if set(args.browsers)!={'chromium','firefox','webkit'}: raise ValueError('Thorough mode requires all three browser engines')
    if len(args.viewports)<2: raise ValueError('Thorough mode requires at least two viewport sizes')
    if args.allow_actions:
        args.auto_fields=True
        args.explore_actions=True
    return args


def setup(log):
    """Explicit --setup installs documented project dependencies; never disables protections."""
    npm=shutil.which('npm')
    commands=[[sys.executable,'-m','pip','install','-r',str(ROOT/'requirements.txt')]]
    if npm: commands.append([npm,'ci','--ignore-scripts'])
    commands.append([sys.executable,'-m','playwright','install','chromium','firefox','webkit'])
    errors=[]
    with log.open('w',encoding='utf-8') as stream:
        for cmd in commands:
            print('Installing '+('accessibility engine' if cmd[0]==npm else 'browser dependencies')+'...',flush=True)
            try:
                r=subprocess.run(cmd,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,timeout=600)
                if r.returncode: errors.append('Dependency installer failed; see setup.log')
            except (OSError,subprocess.TimeoutExpired): errors.append('Dependency installer failed or timed out; see setup.log')
    if not npm: errors.append('Node.js/npm is missing. Install Node.js, then rerun --setup.')
    return errors

async def browser_preflight(args):
    from playwright.async_api import async_playwright
    problems=[]
    async with async_playwright() as pw:
        for name in args.browsers:
            browser=None
            try:
                browser=await getattr(pw,name).launch(timeout=15000)
                page=await asyncio.wait_for(browser.new_page(),10)
                await asyncio.wait_for(page.close(),5)
            except Exception as exc:
                problems.append(name+': startup failed ('+type(exc).__name__+'). Install this engine and its OS dependencies; see --setup.')
            finally:
                if browser:
                    try: await asyncio.wait_for(browser.close(),5)
                    except Exception: problems.append(name+': browser cleanup failed')
    return problems

def blocked(target, problems, output):
    gaps=[{'family':'setup','status':'BLOCKED','count':1,'finding_ids':[], 'reason':reason,
           'next_action':'Resolve setup, then rerun the same command. On Linux, Playwright may require OS packages; on Windows use --setup.'} for reason in problems]
    save({'target':target,'status':'BLOCKED_BEFORE_SCAN','passed':False,'counts':{},'gaps':gaps,
          'note':'No website assessment was made. Required checks could not start; no skips or passes are fabricated.'},output)
    print('BLOCKED: '+str(output/'completion.html'),flush=True)
    for problem in problems: print(problem,flush=True)
    return 2

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__,epilog='Additional tester.py options are accepted, including --config and --allow-actions.')
    p.add_argument('url',nargs='?');p.add_argument('--setup',action='store_true')
    p.add_argument('--output',default='reports/thorough');p.add_argument('--review-report',help='Analyze an existing report without running browsers')
    a,forwarded=p.parse_known_args(argv)
    # Unique directory prevents a failed setup from presenting an old result as a new scan.
    out=Path(a.output).resolve()/('run-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6])
    out.mkdir(parents=True,exist_ok=True)
    if a.review_report:
        if a.setup or forwarded: p.error('--review-report cannot be combined with setup or scan options')
        data=json.loads(Path(a.review_report).read_text(encoding='utf-8'))
        summary=summarize(data);save(summary,out)
        print(summary['status']+': '+str(out/'completion.html'));return 0 if summary['passed'] else 3
    if not a.url:p.error('Provide a target URL')
    from qa.core import canonical, display_url
    target=display_url(canonical(a.url))
    problems=setup(out/'setup.log') if a.setup else []
    if importlib.util.find_spec('playwright') is None: problems.append('Python Playwright is missing. Rerun with --setup.')
    # The explicit axe override, when supplied, is validated by tester.py.
    if not any(x=='--axe' or x.startswith('--axe=') for x in forwarded) and not (ROOT/'node_modules/axe-core/axe.min.js').is_file(): problems.append('axe-core is missing. Rerun with --setup (Node.js/npm required).')
    if problems:return blocked(target,problems,out)
    try:
        args=build_args(a.url,forwarded,out)
        from qa.core import validate_config,load_json
        validate_config(load_json(args.config) if args.config else {},canonical(a.url))
        problems=asyncio.run(browser_preflight(args))
        if problems:return blocked(target,problems,out)
        print('Thorough scan: 3 engines, '+str(len(args.viewports))+' viewports, '+str(args.repeats)+' samples. Limits remain bounded; any remaining gaps block completion.',flush=True)
        if not args.allow_actions: print('Action tests need --allow-actions and authorized test data. They remain unassessed in read-only mode.',flush=True)
        from qa.runner import run
        code=asyncio.run(run(args))
        data=json.loads((out/'report.json').read_text(encoding='utf-8'))
        summary=summarize(data);save(summary,out)
        print(summary['status']+': '+str(out/'completion.html'))
        return code if code else (0 if summary['passed'] else 3)
    except (ValueError,OSError,ImportError,KeyError) as exc:
        return blocked(target,[type(exc).__name__+': '+str(exc)],out)

if __name__=='__main__':raise SystemExit(main())
