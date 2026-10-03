"""UI/API workflows with isolated contexts, outcome assertions and finally cleanup."""
import asyncio
import json
import os
import time
import uuid
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from .data import expand, substitute


def origin(url):
    p = urlsplit(url)
    if p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password:
        raise ValueError('Expected HTTP(S) URL without credentials')
    return p.scheme, p.hostname.lower(), p.port or (443 if p.scheme == 'https' else 80)

def scoped(base, path):
    url = urljoin(base, path)
    if origin(url) != origin(base):
        raise ValueError('URL outside configured target origin')
    return url

def pick(value, path):
    if path in ('', '$'):
        return value
    for part in path.removeprefix('$.').split('.'):
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value

def check(actual, operator, expected):
    operators = {'eq': lambda: actual == expected, 'ne': lambda: actual != expected,
                 'count': lambda: len(actual) == expected, 'contains': lambda: expected in actual,
                 'lte': lambda: actual <= expected, 'gte': lambda: actual >= expected}
    if operator not in operators:
        raise ValueError('Unknown assertion operator')
    if not operators[operator]():
        raise AssertionError('Expected outcome not met (' + operator + '); values omitted to protect test data')

async def run(config, directory, output, allow_actions=False, workers=2, repeats=1):
    from playwright.async_api import async_playwright, expect
    if not 1 <= workers <= 8 or not 1 <= repeats <= 10:
        raise ValueError('Workers must be 1–8; repeats 1–10')
    base = config['base_url']; origin(base)
    tests = expand(config, directory)
    browsers = config.get('browsers', ['chromium'])
    viewports = config.get('viewports', {'desktop': {'width': 1280, 'height': 800}})
    if not browsers or any(b not in ('chromium', 'firefox', 'webkit') for b in browsers) or not viewports:
        raise ValueError('Invalid browser/viewport matrix')
    if len(tests) * len(browsers) * len(viewports) * repeats > 2000:
        raise ValueError('Matrix exceeds 2000 cases')
    out = Path(output); out.mkdir(parents=True, exist_ok=True)
    semaphore = asyncio.Semaphore(workers)
    results = []
    async with async_playwright() as pw:
        async def case(test, engine, viewport_name, viewport, repetition):
            async with semaphore:
                run_id = uuid.uuid4().hex
                variables = {**test['variables'], 'run_id': run_id, 'base_url': base}
                row = {'name': test['name'], 'browser': engine, 'viewport': viewport_name,
                       'case_id': test.get('case_id'), 'repeat': repetition, 'run_id': run_id, 'status': 'PASS', 'steps': [], 'cleanup': []}
                browser = context = page = None
                started = time.monotonic()
                blocked = []
                async def step(raw):
                    s = substitute(raw, variables); action = s['action']
                    if action in ('click', 'fill', 'press', 'select', 'check') and not allow_actions:
                        raise PermissionError('Workflow actions require --allow-actions')
                    if action == 'goto':
                        await page.goto(scoped(base, s['url']), wait_until='domcontentloaded')
                    elif action == 'fill':
                        value = os.environ[s['value_env']] if 'value_env' in s else str(s['value'])
                        await page.locator(s['selector']).fill(value)
                    elif action == 'click': await page.locator(s['selector']).click()
                    elif action == 'press': await page.locator(s['selector']).press(s['key'])
                    elif action == 'select': await page.locator(s['selector']).select_option(str(s['value']))
                    elif action == 'check': await page.locator(s['selector']).set_checked(s.get('checked', True))
                    elif action == 'reload': await page.reload(wait_until='domcontentloaded')
                    elif action == 'expect_text': await expect(page.locator(s['selector'])).to_have_text(str(s['value']))
                    elif action == 'expect_count': await expect(page.locator(s['selector'])).to_have_count(int(s['value']))
                    elif action == 'expect_url': await expect(page).to_have_url(scoped(base, s['value']))
                    elif action == 'assert': check(s['actual'], s.get('operator', 'eq'), s['expected'])
                    elif action in ('request', 'parallel_requests'):
                        method = s.get('method', 'GET').upper()
                        if method not in ('GET', 'HEAD', 'OPTIONS') and not allow_actions:
                            raise PermissionError('API mutations require --allow-actions')
                        headers = dict(s.get('headers', {}))
                        if 'role' in s and s['role'] not in config.get('roles', {}): raise ValueError('Unknown configured role')
                        role = config.get('roles', {}).get(s.get('role'), {})
                        headers.update({k: os.environ[v] for k, v in role.get('headers_env', {}).items()})
                        async def request():
                            response = await context.request.fetch(scoped(base, s['url']), method=method,
                                headers=headers, data=s.get('json'), timeout=15000, max_redirects=0)
                            try:
                                if 'expect_status' in s: check(response.status, 'eq', s['expect_status'])
                                body = await response.json() if 'expect_json' in s or 'capture' in s else None
                                for assertion in s.get('expect_json', []):
                                    check(pick(body, assertion.get('path', '$')), assertion.get('operator', 'eq'), assertion['expected'])
                                return body
                            finally:
                                await response.dispose()
                        if action == 'parallel_requests':
                            count = int(s.get('count', 2))
                            if not 2 <= count <= 10: raise ValueError('Parallel requests must be 2–10')
                            bodies = await asyncio.gather(*(request() for _ in range(count)), return_exceptions=True)
                            for body in bodies:
                                if isinstance(body, BaseException): raise body
                            if 'capture' in s: raise ValueError('Capture from parallel requests is ambiguous')
                        else:
                            body = await request()
                            for name, path in s.get('capture', {}).items(): variables[name] = pick(body, path)
                    else: raise ValueError('Unsupported action: ' + action)
                try:
                    browser = await getattr(pw, engine).launch(timeout=15000)
                    context = await browser.new_context(viewport=viewport)
                    context.set_default_timeout(8000)
                    async def guard(route):
                        request = route.request
                        # External resources allowed; credential-bearing API calls are always scoped above.
                        if (request.is_navigation_request() or request.method not in ('GET', 'HEAD', 'OPTIONS')) and origin(request.url) != origin(base):
                            blocked.append('Cross-origin navigation'); await route.abort(); return
                        if not allow_actions and request.method not in ('GET', 'HEAD', 'OPTIONS'):
                            blocked.append('Mutation blocked'); await route.abort(); return
                        await route.continue_()
                    await context.route('**/*', guard)
                    await context.tracing.start(screenshots=True, snapshots=True, sources=True)
                    page = await context.new_page()
                    row['diagnostics'] = {'js_errors': [], 'http_errors': [], 'request_failures': []}
                    page.on('pageerror', lambda error: row['diagnostics']['js_errors'].append({'type': type(error).__name__, 'detail': 'See trace for exception text'}))
                    page.on('response', lambda response: row['diagnostics']['http_errors'].append({'status': response.status, 'resource_type': response.request.resource_type}) if response.status >= 400 else None)
                    page.on('requestfailed', lambda request: row['diagnostics']['request_failures'].append({'method': request.method, 'resource_type': request.resource_type}))
                    for stage in ('setup', 'steps'):
                        for index, s in enumerate(test[stage]):
                            await step(s)
                            row['steps'].append({'stage': stage, 'index': index, 'action': s['action'], 'status': 'PASS'})
                except Exception as exc:
                    from playwright.async_api import TimeoutError as PWTimeout
                    row['status'] = 'FAIL' if isinstance(exc, AssertionError) or (isinstance(exc, PWTimeout) and 's' in locals() and s['action'].startswith('expect_')) else 'ERROR'
                    row['error'] = {'type': type(exc).__name__, 'detail': 'Step failed; inspect local trace. Values are omitted.', 'step_index': len(row['steps'])}
                    if page:
                        try: await page.screenshot(path=str(out / (run_id + '.png')), mask=[page.locator('input,textarea')])
                        except Exception: pass
                finally:
                    if context:
                        for index, s in enumerate(test['cleanup']):
                            try:
                                await step(s); row['cleanup'].append({'index': index, 'status': 'PASS'})
                            except Exception as exc:
                                row['cleanup'].append({'index': index, 'status': 'ERROR', 'type': type(exc).__name__})
                                row['status'] = 'ERROR'
                        try:
                            await context.tracing.stop(path=str(out / (run_id + '.zip')))
                            row['trace'] = run_id + '.zip'
                        except Exception: row['trace_error'] = True
                        try: await context.close()
                        except Exception: row['status'] = 'ERROR'; row['context_cleanup_error'] = True
                    if browser:
                        try: await browser.close()
                        except Exception: row['status'] = 'ERROR'; row['browser_cleanup_error'] = True
                row['blocked_requests'] = blocked
                row['seconds'] = round(time.monotonic() - started, 3)
                return row
        results = await asyncio.gather(*(case(t, b, n, v, r + 1) for t in tests for b in browsers for n, v in viewports.items() for r in range(repeats)))
    groups = {}
    for row in results:
        key = (row['name'], row['browser'], row['viewport'])
        groups.setdefault(key, set()).add(row['status'])
    flaky = [list(k) for k, statuses in groups.items() if 'PASS' in statuses and len(statuses) > 1]
    return {'kind': 'workflows', 'results': results, 'flaky': flaky,
            'passed': all(r['status'] == 'PASS' for r in results) and not flaky,
            'limitation': 'Expected outcomes are supplied requirements; these checks do not infer complete business correctness.'}
