"""Website QA: browser checks, business rules, evidence scoring and optional AI."""
import argparse
import asyncio
import sys
from pathlib import Path
from qa.runner import run,VIEWPORTS


def parse_args(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('url')
    p.add_argument('--config',help='Approved journey, field and API rules in JSON')
    p.add_argument('--output',help='Output folder; omitted creates a unique timestamped run')
    p.add_argument('--history',default='reports/history.sqlite3')
    p.add_argument('--no-history',action='store_true')
    p.add_argument('--auto-fields',action='store_true',help='Test declared HTML boundaries automatically, with --allow-actions; not business-rule approval')
    p.add_argument('--exploration-depth',type=int,default=2)
    p.add_argument('--max-states',type=int,default=20)
    p.add_argument('--zap-baseline',action='store_true',help='Run Docker ZAP baseline spider/passive scan; requires --allow-actions')
    p.add_argument('--zap-timeout',type=int,default=240)
    p.add_argument('--crux-file',help='Existing CrUX API JSON record')
    p.add_argument('--crux-key-env',help='Opt in to CrUX lookup using API key in this environment variable')
    p.add_argument('--browsers',default='chromium',help='Comma-separated chromium,firefox,webkit')
    p.add_argument('--viewports',default='desktop,mobile',help='Comma-separated desktop,mobile,tablet')
    p.add_argument('--max-pages',type=int,default=8)
    p.add_argument('--repeats',type=int,default=3,help='Fresh-context load samples per page/viewport/engine')
    p.add_argument('--journey-repeats',type=int,default=1)
    p.add_argument('--timeout-ms',type=int,default=10000)
    p.add_argument('--max-seconds',type=int,default=600)
    p.add_argument('--settle-ms',type=int,default=500)
    p.add_argument('--delay-ms',type=int,default=400)
    p.add_argument('--action-limit',type=int,default=40)
    p.add_argument('--load-ms',type=int,default=3000)
    p.add_argument('--lcp-ms',type=int,default=2500)
    p.add_argument('--blocking-ms',type=int,default=200)
    p.add_argument('--cls',type=float,default=.1,help='Window-limited observed layout-shift budget')
    p.add_argument('--allow-actions',action='store_true',help='Enable configured clicks/field events/API mutations and non-read-only requests; use staging')
    p.add_argument('--explore-actions',action='store_true',help='Heuristically click selected non-form buttons in fresh sessions; requires --allow-actions')
    p.add_argument('--storage-state',help='Sensitive Playwright login state file')
    p.add_argument('--axe',help='Local axe.min.js path')
    p.add_argument('--baselines',help='Approved screenshot directory')
    p.add_argument('--visual-threshold',type=float,default=.01)
    p.add_argument('--zap-report',help='ZAP JSON export; candidates require human review')
    p.add_argument('--sarif',help='Source/dependency scanner SARIF 2.1.0 export')
    p.add_argument('--resolutions',help='Human dispositions for REVIEW IDs from a prior run')
    p.add_argument('--group-findings',action='store_true',help='Group similar issues with TF-IDF and DBSCAN')
    p.add_argument('--embedding-model',help='Optional local sentence-transformer model directory')
    p.add_argument('--triage-model',help='Explicitly trusted local joblib model from train_triage.py')
    p.add_argument('--ai-model',help='Installed local Ollama text model name')
    p.add_argument('--vision-model',help='Installed local Ollama image-input model name')
    p.add_argument('--vision-limit',type=int,default=2)
    p.add_argument('--ollama-url',default='http://127.0.0.1:11434')
    p.add_argument('--enforce-gate',action='store_true',help='Exit 3 if the 90-point/90%% coverage gate is not met')
    p.add_argument('--executable',help='Optional local Chromium executable path')
    a=p.parse_args(argv)
    a.browsers=list(dict.fromkeys(a.browsers.split(','))); a.viewports=list(dict.fromkeys(a.viewports.split(',')))
    if not set(a.browsers)<= {'chromium','firefox','webkit'}: p.error('Invalid browser list')
    if not set(a.viewports)<=set(VIEWPORTS): p.error('Invalid viewport list')
    positive=('max_pages','repeats','journey_repeats','timeout_ms','max_seconds','action_limit','load_ms','lcp_ms','blocking_ms','vision_limit','max_states','exploration_depth','zap_timeout')
    if any(getattr(a,key)<1 for key in positive) or min(a.settle_ms,a.delay_ms,a.cls)<0: p.error('Invalid negative/zero limits')
    if not 0<=a.visual_threshold<=1: p.error('visual-threshold must be between 0 and 1')
    if (a.explore_actions or a.auto_fields or a.zap_baseline) and not a.allow_actions: p.error('Exploration, automatic field events and ZAP crawling require --allow-actions on an authorized target')
    if not a.axe and Path('node_modules/axe-core/axe.min.js').is_file(): a.axe='node_modules/axe-core/axe.min.js'
    if a.axe and not Path(a.axe).is_file(): p.error('axe file does not exist')
    return a

if __name__=='__main__':
    if '--wizard' in sys.argv:
        from qa.guided import wizard
        raise SystemExit(wizard())
    try: raise SystemExit(asyncio.run(run(parse_args())))
    except (ValueError,FileNotFoundError) as exc: raise SystemExit('Configuration error: '+str(exc))
