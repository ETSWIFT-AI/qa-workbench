# Thorough testing with explicit completion gaps

Use `thorough.py` instead of the basic `tester.py` command when you want the broader scan. This adds actual execution defaults and dependency checks; it does not erase SKIP records, fabricate failures or promise exhaustive testing of an arbitrary website.

## Windows quick start

Open PowerShell in the folder containing `thorough.py`:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe thorough.py "https://demo.guru99.com/test/" --setup --allow-actions
```

Node.js/npm must be installed for axe. `--setup` installs the Python browser package, the project's pinned axe dependency, and Chromium/Firefox/WebKit. It uses `npm ci --ignore-scripts`; it does not install Node.js itself or bypass OS permissions. Subsequent runs can omit `--setup`. Linux may need Playwright's OS dependencies installed by the system administrator.

Use `--allow-actions` only on a site/test environment where you may interact with forms and test data. It enables declared-HTML boundary tests and bounded interaction exploration automatically. It also permits configured API mutations. It does not invent login credentials, complete arbitrary purchases or automatically approve destructive routes. For business submissions, supply approved `--config` journeys with assertions. Without `--allow-actions`, read-only checks run and action gaps remain explicit.

## What actually changes

- Requires axe and working Chromium, Firefox and WebKit before starting. Missing dependencies stop the scan with a setup report instead of producing ten missing-axe skips later.
- Uses desktop/mobile/tablet viewport sizes.
- Collects at least three performance samples and two configured journey repetitions.
- Raises default limits to 50 pages, 500 controls per page, 100 explored states, depth 3, and 30 minutes. These are finite bounds, not exhaustive coverage claims. Overrides are accepted; incomplete limits remain visible.
- Automatically enables existing HTML-boundary checks and selected interaction exploration with `--allow-actions`.
- Retains all raw findings and the existing measured quality score.
- Generates `completion.html`, `completion.json` and `completion-junit.xml`. Every recorded SKIP, REVIEW, ERROR, empty test family and noted route exclusion becomes an explicit completion gap with a next action.
- Exit status is unsuccessful when checks remain unresolved, the configured gate is unmet or any test failed. The completion JUnit fails the **test-completeness gate**, not the application under test.
- Uses a new timestamped folder on every invocation so a failed setup cannot accidentally show an old successful report.

Results are printed as an absolute path under `reports/thorough/run-.../completion.html`. The original detailed report is in the same run folder after a scan completes. Open the path printed in your terminal.

## Required context cannot be guessed

Use the existing tester options to supply additional information:

```powershell
.\.venv\Scripts\python.exe thorough.py "https://your-staging-site.example/" --allow-actions --config rules.json --storage-state login-state.json --baselines approved-screenshots --zap-report zap.json --sarif source.sarif --resolutions reviewed-findings.json
```

Only include options for real files you have prepared. This example is not a ready-made configuration for Guru99. A login state is sensitive; use test accounts. Traces and reports can contain private information.

The first screenshot cannot establish the correct visual design. A number input's HTML `min` cannot establish the business's intended age policy. An external website cannot provide private server source or deployment evidence. Some browsers do not expose every performance metric. These remain explicit gaps; no neural model or renamed status can turn them into executed tests.

Generated field drafts remain in `suggested-fields.json`. They describe checks against declared HTML constraints. Review them before treating them as approved business requirements. Use `company_qa.py` for the previously added backend, dataset and load scenarios; this launcher does not automatically infer those scenarios from a URL.

## Analyze an existing report without rerunning the site

```powershell
.\.venv\Scripts\python.exe thorough.py --review-report reports\guru99\report.json
```

This produces a completion-gap report only. It does not rerun skipped checks or claim to have fixed coverage.

## Validation for this update

Seven automated unit tests passed for completion classification, no mutation of raw findings, omitted-family detection, excluded routes, empty runs, HTML escaping and CI failure output. The supplied Guru99 report was processed successfully: its 72 SKIP findings and 65 REVIEW findings remain explicit gaps, with their original statuses retained. No live website rescan or browser/dependency installation was possible in this session because execution-network access was blocked. Earlier validation results in COMPANY_VALIDATION.md apply to the earlier release, not a fresh live test of this launcher.
