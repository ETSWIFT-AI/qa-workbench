# Autonomous exploration validation

- Original v3.1 test suite: 32 passed, 2 browser tests skipped in this invocation.
- Autonomous policy/browser tests: seven passed using local Chromium fixtures. Covered single supplied-credential login, runtime DOM discovery, disclosure clicks, GET search, missing-credential questions without submission, MFA questions without bypass, read-only no-click behaviour, same-origin/risky-route filtering, credential redaction, and action budget.
- End-to-end wrapper tested with the included loopback demo: baseline report + advanced report + login, account disclosure and search exploration; zero advanced execution errors. The first end-to-end run revealed that clicking a disclosure could postpone link discovery; all eligible links are now enqueued before selecting a click, and the corrected run was retested.
- All 55 original non-cache files are byte-compared with the uploaded v3.1 archive before packaging and remain unchanged.
- Python compilation and generated report browser rendering checked.

Environment: Python 3.12, Playwright 1.51.0, Chromium headless shell on Linux. No neural model or pretrained service is involved in these autonomy tests.

Not verified: arbitrary real-site authentication, multi-step/passwordless/SSO login, iframe/shadow DOM flows, mobile devices, Firefox/WebKit autonomy, production side-effect safety, human-level reasoning, or correctness of business logic. Native Windows launcher interaction/batch execution was not run on Windows. The existing model training features retain their earlier validation; they were not retrained for this change.

The example demo credentials are deliberately public, local-only fixture values. Reports do not contain the credentials used during its browser run. Screenshots can still include other private page content.
