"""Small, rate-capped HTTP load test. Not a distributed stress-testing service."""
import asyncio
import math
import time
from .workflows import scoped

def percentile(values, fraction):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)] if ordered else None

async def run(config, allow_load=False):
    from playwright.async_api import async_playwright
    if not allow_load:
        raise PermissionError('Use --allow-load only for a target you are authorized to load test')
    vus, count, rps = int(config.get('users', 2)), int(config.get('requests', 20)), float(config.get('rps', 5))
    duration = float(config.get('max_seconds', 60))
    if not 1 <= vus <= 50 or not 1 <= count <= 5000 or not 0 < rps <= 50 or not 1 <= duration <= 300:
        raise ValueError('Limits: users 1–50, requests 1–5000, RPS (0,50], duration 1–300s')
    url = scoped(config['base_url'], config.get('path', '/'))
    expected = config.get('expected_status', 200)
    samples, cursor, next_start = [], 0, 0.0
    lock = asyncio.Lock()
    started = time.monotonic(); deadline = started + duration
    async with async_playwright() as pw:
        async def worker():
            nonlocal cursor, next_start
            ctx = await pw.request.new_context()
            try:
                while True:
                    async with lock:
                        if cursor >= count: break
                        slot = max(next_start, time.monotonic()); next_start = slot + 1 / rps
                        if slot >= deadline: break
                        cursor += 1
                    await asyncio.sleep(max(0, slot - time.monotonic()))
                    begin = time.monotonic(); status = None; error = None
                    try:
                        response = await ctx.get(url, timeout=max(1, min(15000, (deadline - begin) * 1000)), max_redirects=0)
                        status = response.status
                        await response.body()
                        await response.dispose()
                    except Exception as exc:
                        error = type(exc).__name__
                    samples.append({'ms': round((time.monotonic() - begin) * 1000, 2), 'status': status, 'error': error})
            finally: await ctx.dispose()
        await asyncio.gather(*(worker() for _ in range(vus)))
    elapsed = time.monotonic() - started
    failures = sum(s['status'] != expected or s['error'] is not None for s in samples)
    error_rate = failures / len(samples) if samples else 1
    p95 = percentile([s['ms'] for s in samples], .95)
    complete = len(samples) == count
    passed = complete and error_rate <= config.get('max_error_rate', 0) and p95 <= config.get('max_p95_ms', 1000)
    return {'kind': 'load', 'passed': passed, 'status': 'PASS' if passed else 'FAIL' if complete else 'ERROR',
            'requested': count, 'completed': len(samples), 'users': vus, 'rps_cap': rps,
            'throughput_rps': round(len(samples) / elapsed, 2), 'p50_ms': percentile([s['ms'] for s in samples], .5),
            'p95_ms': p95, 'error_rate': error_rate, 'seconds': round(elapsed, 2), 'samples': samples,
            'limitation': 'HTTP GET load from one machine; no browser render timing, real-user field data or distributed capacity claim.'}
