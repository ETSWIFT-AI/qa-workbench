"""Self-healing locators.

When a configured journey/field selector no longer matches an element (it moved,
was renamed, or restructured), this module tries a small, ordered set of fallback
identification strategies built from the last-known element profile instead of
just failing outright:

  1. data-testid / data-test-id (most stable, if the app sets one)
  2. element id
  3. semantic role + accessible name (ARIA role, aria-label/label text)
  4. form "name" attribute
  5. placeholder text
  6. visible text content (loosest, last resort)

Each candidate gets a confidence score. Only a high-confidence match is applied
automatically; a merely plausible one is flagged for human review rather than
silently substituted (silent auto-healing can mask a real regression). Either
way, the outcome is recorded in the report under the 'self_healing' family --
healing keeps a test *running*, it does not by itself confirm the app is right.

Profiles are cached to disk per run-output directory (locator-cache.json) so a
selector that is currently working still has a profile available the next time
it breaks.
"""
import difflib
import hashlib
import json
from pathlib import Path

AUTO_APPLY_THRESHOLD = 0.85
REVIEW_THRESHOLD = 0.60

DESCRIBE_JS = r'''(el) => {
  if (!el) return null;
  const label = (el.labels && el.labels[0] && el.labels[0].innerText) || el.getAttribute('aria-label') || '';
  return {
    tag: el.tagName.toLowerCase(),
    id: el.id || '',
    name: el.getAttribute('name') || '',
    role: el.getAttribute('role') || '',
    text: (el.innerText || el.value || '').trim().slice(0, 120),
    placeholder: el.getAttribute('placeholder') || '',
    ariaLabel: label,
    testId: el.getAttribute('data-testid') || el.getAttribute('data-test-id') || '',
  };
}'''


def cache_path(out_dir):
    return Path(out_dir) / 'locator-cache.json'


def load_cache(out_dir):
    p = cache_path(out_dir)
    if p.is_file():
        try:
            return json.loads(p.read_text(encoding='utf-8'))
        except Exception:
            return {}
    return {}


def save_cache(out_dir, cache):
    try:
        cache_path(out_dir).write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding='utf-8')
    except Exception:
        pass


def _key(scope, step_index, selector):
    return hashlib.sha256(f'{scope}|{step_index}|{selector}'.encode()).hexdigest()[:16]


def _similarity(a, b):
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


async def _describe(locator):
    try:
        return await locator.evaluate(DESCRIBE_JS)
    except Exception:
        return None


def _candidate_strategies(page, profile):
    """(strategy_name, base_confidence, builder) in priority order, highest-confidence first."""
    strategies = []
    if profile.get('testId'):
        tid = profile['testId']
        strategies.append(('data-testid', 0.97, lambda: page.locator(f"[data-testid='{tid}'],[data-test-id='{tid}']")))
    if profile.get('id'):
        strategies.append(('stable id', 0.90, lambda: page.locator(f"#{profile['id']}")))
    if profile.get('role') and profile.get('ariaLabel'):
        strategies.append(('semantic role+aria-label', 0.87, lambda: page.get_by_role(profile['role'], name=profile['ariaLabel'])))
    elif profile.get('ariaLabel'):
        strategies.append(('semantic aria-label', 0.85, lambda: page.get_by_label(profile['ariaLabel'], exact=False)))
    if profile.get('role') and profile.get('text'):
        strategies.append(('semantic role+text', 0.83, lambda: page.get_by_role(profile['role'], name=profile['text'])))
    if profile.get('name'):
        strategies.append(('form name attribute', 0.75, lambda: page.locator(f"[name='{profile['name']}']")))
    if profile.get('placeholder'):
        strategies.append(('placeholder text', 0.70, lambda: page.get_by_placeholder(profile['placeholder'], exact=False)))
    if profile.get('text'):
        strategies.append(('visible text content', 0.55, lambda: page.get_by_text(profile['text'], exact=False)))
    return strategies


async def resolve(page, scope, step_index, step, cache, report=None, url='', variant=''):
    """Resolve a step's locator, self-healing from a cached element profile on failure.

    Returns (locator, healed: bool, strategy_name: str).
    """
    selector = step['selector']
    key = _key(scope, step_index, selector)
    primary = page.locator(selector)
    try:
        await primary.first.wait_for(state='attached', timeout=1500)
        profile = await _describe(primary.first)
        if profile:
            cache[key] = profile
        return primary, False, ''
    except Exception:
        pass

    label = f'{variant}: {scope} step {step_index + 1} ({selector})'
    profile = cache.get(key)
    if not profile:
        if report is not None:
            report.add('self_healing', label, 'SKIP',
                        'Selector did not match, and no prior element profile is cached to heal from yet (first observed run against this selector).',
                        url)
        return primary, False, ''

    ranked = []
    for name, base_confidence, build in _candidate_strategies(page, profile):
        try:
            candidate = build()
            if await candidate.count() == 0:
                continue
            found = await _describe(candidate.first)
            similarity = _similarity((found or {}).get('text', ''), profile.get('text', ''))
            score = round(base_confidence * (0.5 + 0.5 * similarity), 2)
            ranked.append((name, score, candidate, found))
        except Exception:
            continue
    ranked.sort(key=lambda t: t[1], reverse=True)

    if ranked and ranked[0][1] >= AUTO_APPLY_THRESHOLD:
        name, score, candidate, found = ranked[0]
        cache[key] = found or profile
        if report is not None:
            report.add('self_healing', label, 'PASS',
                        f"Original selector no longer matched (element likely moved/renamed); auto-recovered via {name} (confidence {score}). "
                        'This confirms the test could keep running, not that the workflow behaved correctly -- see the journeys result for that.',
                        url, 'low')
        return candidate, True, name

    if ranked and ranked[0][1] >= REVIEW_THRESHOLD:
        name, score, candidate, found = ranked[0]
        if report is not None:
            report.add('self_healing', label, 'REVIEW',
                        f"Original selector failed. A possible replacement was found via {name} (confidence {score}), below the "
                        f'{AUTO_APPLY_THRESHOLD} auto-heal threshold, so it was NOT applied automatically. Update the selector or confirm by hand.',
                        url, 'medium')
        return primary, False, ''

    if report is not None:
        tried = [(n, s) for n, s, _c, _f in ranked] or 'none of the fallback strategies matched any element'
        report.add('self_healing', label, 'FAIL',
                    f'Original selector failed and no fallback reached the {REVIEW_THRESHOLD} confidence floor. Candidates tried: {tried}.',
                    url, 'medium')
    return primary, False, ''
