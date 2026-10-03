# Local beta validation — 2026-10-03

Environment: Linux, Python 3.12, Playwright 1.51.0, Chromium headless shell 134, pytest 8.4.2.

## Results

- Combined regression suite: **75 passed in 44.49 seconds**, including existing tester, company scenarios, autonomous checks, completeness checks and product tests.
- After the final JSON redaction improvement: **14 product tests passed in 11.09 seconds**. These include running the existing scanner through the dashboard's job queue and loading its actual report.
- Three additional issue-publication adapter tests passed. They verify exact-preview approval, GitHub request payload/response handling, Jira ADF structure and rejected foreign destinations/redirects. No issue was published to an external service.
- Known-bug benchmark: healthy order fixture passed, duplicate-order defect detected, no intermittent outcomes, cleanup completed for both fixtures. Zero false-positive, missed-defect and inconclusive **fixture counts across these two fixtures only**.
- Dashboard screenshot captured and visually inspected at 1400 × 1100. No uncaught browser errors in the tested login/project/workflow/account flows.
- JavaScript syntax and Python compilation checks passed.

## What the tests exercised

Account login, salted password storage, session expiration, password-reset session invalidation, project grant/revoke, viewer restrictions, cross-project denial, CSRF/Origin/Host checks, login rate limiting, confined artifact downloads, private-input redaction, numeric JSON preservation, missing-keyring rejection, required workflow assertions and UI editing/saving.

Real browser checks exercised the dashboard and recorder's DOM listeners, including typing, button clicks and Alt-click assertions. Typed values did not appear in recorded event payloads. The interactive recorder's complete desktop window lifecycle has not been tested on Windows; the event engine was tested in headless Chromium.

## Remaining deployment validation

Windows batch launchers and Windows Credential Locker need validation on the user's machine. No real OS keyring round-trip, hosted CI run, Firefox/WebKit product UI test, live Jira/GitHub publication, remote multi-user deployment or broad security audit was completed here. The server is loopback-only by design.

The default package permits newer Playwright releases; only the version above was used for these local browser tests. The newest browser download attempted in this environment failed, so the previously tested version was used for verification. Dependency/setup failures are reported explicitly.

This is a local beta, not a production SaaS readiness certificate. Screenshots, trace archives and other raw artifacts can retain sensitive data. Review privacy, dependency/data licensing and deployment controls before commercial distribution.
