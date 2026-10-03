"""Policy analysis and opt-in ZAP baseline orchestration; not an exploit scanner."""
import asyncio
import re
import uuid
from pathlib import Path


def analyse_headers(headers):
    rows=[]
    csp=headers.get('content-security-policy','')
    directives={}
    for part in csp.split(';'):
        tokens=part.strip().split()
        if tokens: directives.setdefault(tokens[0].lower(),tokens[1:])
    if csp:
        script=directives.get('script-src',directives.get('default-src',[]))
        weak=[v for v in script if v in ("'unsafe-eval'","'unsafe-inline'",'*','http:')]
        rows.append(('CSP script sources','REVIEW' if weak or not script else 'PASS',f'Potentially permissive sources: {weak}; manually assess nonce/hash/strict-dynamic semantics' if weak else 'Script/default sources specified; not proof against XSS'))
        rows.append(('CSP base-uri','PASS' if directives.get('base-uri') else 'REVIEW','Restrict base-uri to reduce injected base-tag risk; assess applicability'))
        rows.append(('CSP framing sources','PASS' if directives.get('frame-ancestors') else 'REVIEW','frame-ancestors policy present' if directives.get('frame-ancestors') else 'No CSP frame-ancestors; X-Frame-Options may provide fallback'))
    if 'strict-transport-security' in headers:
        m=re.search(r'(?:^|;)\s*max-age\s*=\s*(\d+)',headers['strict-transport-security'],re.I)
        rows.append(('HSTS duration','PASS' if m and int(m[1])>=15552000 else 'REVIEW','Check max-age >= 180 days; rollout requirements may differ'))
    xfo=headers.get('x-frame-options')
    if xfo: rows.append(('X-Frame-Options value','PASS' if xfo.upper() in ('DENY','SAMEORIGIN') else 'REVIEW','Accepted values DENY or SAMEORIGIN; deprecated/invalid alternatives need review'))
    return rows


async def zap_baseline(base,out,report,image='ghcr.io/zaproxy/zaproxy:stable',timeout=240):
    """Run the maintained packaged scanner. No shell interpolation or active attack scan."""
    name='website-qa-'+uuid.uuid4().hex[:12]
    dest=Path(out).resolve()/'zap';dest.mkdir(parents=True,exist_ok=True)
    # ZAP's container user needs write access to this task-specific output directory.
    try: dest.chmod(0o777)
    except OSError: pass
    cmd=['docker','run','--rm','--name',name,'-v',str(dest)+':/zap/wrk/:rw',image,
         'zap-baseline.py','-t',base,'-m','1','-T','2','-J','zap.json','-r','zap.html']
    (dest/'zap.json').unlink(missing_ok=True)
    process=None
    try:
        with (dest/'scanner.log').open('wb') as log:
            process=await asyncio.create_subprocess_exec(*cmd,stdout=log,stderr=asyncio.subprocess.STDOUT)
            code=await asyncio.wait_for(process.wait(),timeout)
        # ZAP uses 1/2 for findings/warnings. These are not execution failures.
        if code not in (0,1,2) or not (dest/'zap.json').is_file():
            raise RuntimeError(f'ZAP did not produce a valid report (exit {code}); see zap/scanner.log')
        report.notes.append('ZAP baseline executed: spider plus passive rules, no active exploit scan. Authenticated business flows are not automatically covered.')
        return dest/'zap.json'
    except asyncio.TimeoutError:
        report.add('external_scan','ZAP baseline','ERROR','Scanner timed out; no clean result inferred')
    except Exception as exc:
        report.add('external_scan','ZAP baseline','ERROR',str(exc))
    finally:
        if process and process.returncode is None:
            process.kill();await process.wait()
            try:
                cleanup=await asyncio.create_subprocess_exec('docker','rm','-f',name,stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL)
                await asyncio.wait_for(cleanup.wait(),10)
            except (OSError,asyncio.TimeoutError): pass
    return None
