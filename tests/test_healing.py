import json
from qa.healing import _key, _similarity, _candidate_strategies, load_cache, save_cache, AUTO_APPLY_THRESHOLD, REVIEW_THRESHOLD


def test_key_is_stable_and_scoped():
    a = _key('login journey', 0, '#submit')
    b = _key('login journey', 0, '#submit')
    c = _key('signup journey', 0, '#submit')
    assert a == b
    assert a != c


def test_similarity_bounds():
    assert _similarity('', 'x') == 0.0
    assert _similarity('Sign in', 'Sign in') == 1.0
    assert 0 < _similarity('Sign in', 'Log in') < 1


def test_candidate_strategies_priority_order():
    profile = {'testId': 't1', 'id': 'submit', 'role': 'button', 'ariaLabel': 'Submit',
               'text': 'Submit', 'name': '', 'placeholder': ''}
    names = [name for name, _conf, _build in _candidate_strategies(page=None, profile=profile)]
    assert names[0] == 'data-testid'
    assert 'stable id' in names
    assert names.index('stable id') < names.index('semantic role+aria-label')


def test_thresholds_are_ordered():
    assert 0 < REVIEW_THRESHOLD < AUTO_APPLY_THRESHOLD <= 1


def test_cache_roundtrip(tmp_path):
    cache = {'abc': {'id': 'x'}}
    save_cache(tmp_path, cache)
    assert load_cache(tmp_path) == cache
    assert json.loads((tmp_path / 'locator-cache.json').read_text())['abc']['id'] == 'x'


def test_missing_cache_returns_empty(tmp_path):
    assert load_cache(tmp_path / 'does-not-exist') == {}
