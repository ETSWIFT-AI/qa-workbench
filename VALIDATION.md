# Version 3 validation

## Executed checks

- 26 non-browser unit/adapter tests passed, covering the revised score, 354-pass/1-skip regression, null quality when unassessed, release blockers, report escaping, configuration validation, guided recipes, hash-route handling, history comparisons, CrUX origin matching, CSP/HSTS analysis and ZAP subprocess/report handling.
- Original local-demo Chromium integration passed: known broken-page/JavaScript/API-authorization failures, two configured journeys and nine field cases.
- New Chromium matrix/state integration passed: desktop/mobile workflows and field checks both run; a desktop-only element passes the desktop assertion and fails the mobile assertion; a two-step JavaScript-only route reaches `#/step3`; inferred native-field cases execute.
- Python compilation passed, including desktop launcher and guided builders.
- ZAP adapter tests verified warning/finding exit codes are accepted when a fresh report exists, and a stale report cannot make a failed/missing scan appear successful. These are mocked adapter tests, not a live ZAP vulnerability assessment.

- Two full local-demo runs completed with zero execution errors; the bundled report contains 199 passes and 15 deliberately detected failures, with 89.9 tested quality and 69.2% coverage. The two-run history was generated successfully.
- The generated HTML report was opened in Chromium and its desktop screenshot visually checked.

## Limits of validation

- Browser tests used Python 3.12, Playwright 1.51.0 and its Chromium headless shell in this environment.
- Firefox was downloaded and attempted, but its runtime could not open a page here. Its successful workflow execution is unverified. Browser startup is now bounded and unavailable matrix cells explicitly become ERROR.
- WebKit was not installed/executed in this environment.
- Tkinter imports and GUI code compile; guided builder logic is tested. The native window was not visually exercised because no display server is available. Windows batch files were inspected but not run on Windows.
- Live Docker/ZAP execution and Google CrUX API access require external installations/credentials and were not run here. ZAP/CrUX parsing and failure paths were tested with fixtures.
- Optional AI models were not retrained or live-tested for this update; their interfaces are unchanged. No new model accuracy claim is made.
- This is regression evidence for this project, not proof that every website or platform is covered.
