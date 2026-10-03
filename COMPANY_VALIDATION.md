# Validation — 2026-09-28

## Executed locally

Linux, Python 3.12, Playwright 1.51, headless Chromium:

```
QA_BROWSER_TESTS=1 QA_COMPANY_BROWSER_TESTS=1 python -m pytest tests tests_company tests_advanced/test_autonomous.py -q
54 passed in 40.50s
```

This includes:

- Existing tester, self-healing, browser/viewport and autonomous-agent tests.
- Healthy backend order persistence with concurrent retries.
- Deliberately broken duplicate-order backend: test correctly FAILS; cleanup still runs.
- Mutation opt-in enforcement and cleanup-error reporting.
- Real overlapping HTTP requests, with a deliberately exceeded latency budget correctly failing.
- Repeated mixed pass/fail results flagged flaky without converting them into success.
- Dataset expansion, typed variables, XLSX loading, recursive block/path protections.
- Manual evidence validation, case ownership and append-only review records.
- External JUnit failure and stale-report rejection.
- Dependency scanner parsing with failing/error fixtures.
- Appium action assertions with a fake driver (not hardware validation).

`run_company_demo.py` was executed: workflow PASS, load PASS. A real npm audit of this project's package lock completed with zero reported known vulnerabilities at the time of the run. This is not a whole-website security score.

## Not verified here

- Firefox was downloaded, but its local workflow run did not complete; it was stopped. Browser startup now has a 15-second timeout.
- WebKit downloaded, but required system libraries were missing. OS permission restrictions blocked installing those libraries. No WebKit pass is claimed.
- New GitHub Actions configuration has not run on hosted Windows/Ubuntu runners in this session.
- Windows batch launchers have not run on Windows here.
- Appium/Android/iOS and cloud providers require real sessions and have not been exercised here.
- Live Python advisory service was not exercised. Its failure handling is tested; npm service was exercised.
- Full WCAG conformance, active penetration testing, distributed cloud load and business correctness outside supplied expectations are not provided.

Original uploaded source files remain unchanged; functionality is added alongside the existing project. The old trainer and included UI training data are retained, but this release does not add a newly trained neural model.
