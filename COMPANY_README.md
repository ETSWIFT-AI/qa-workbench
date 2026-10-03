# Company QA add-on

The existing `tester.py`, GUI, autonomous scanner and scratch-model training remain usable. This add-on supplies explicit business-outcome tests and optional engineering integrations. It does not claim that arbitrary websites can be completely tested without requirements, credentials or backend access. No pretrained model or fabricated trained checkpoint was added.

## Start on Windows

Extract the ZIP. Open PowerShell **in the folder containing `company_qa.py`**. For the first local demo:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-company.txt
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe run_company_demo.py
Start-Process .\reports\company-demo\report.html
```

The demo starts and stops its own disposable local server, tests two products at desktop and mobile viewport sizes, verifies order persistence and concurrent retry idempotency, deletes its test orders, and runs a small HTTP load test. It does not place real orders. `setup_company.bat` additionally installs all three browser engines. Python 3.12 is recommended. Start with two workers on a 16 GB laptop. No GPU is required for this add-on.

## What was added

| Previously incomplete capability | Implementation | Remaining boundary |
|---|---|---|
| Critical end-to-end workflows | UI actions plus cookie-sharing API requests, captures and assertions in one scenario | Expected outcomes and permitted test actions still need requirements |
| Backend correctness | Check persisted fields/counts, authorized/denied requests, concurrent identical submissions, reload, and finally cleanup | Use your own authorized API; arbitrary database schemas are not inferred |
| Data-driven regression | CSV, JSON, Excel XLSX; typed variables; reusable step blocks | Max 1,000 dataset rows, 500 expanded steps per stage, 2,000 matrix executions |
| Cross-browser/device sizes | Chromium, Firefox, WebKit × configured viewport × repeat, with isolated browser sessions | Viewport sizes are not physical devices; see validation file for local results |
| Flaky behavior | Repeated runs retain every outcome and flag mixed PASS/non-PASS | Repeats do not guarantee detection of intermittent defects |
| Performance/load | Concurrent HTTP GET workers, global request-rate cap, latency percentiles, error-rate budget | One machine, not distributed load or real-user performance |
| Security depth | npm and pinned Python dependency advisory scans, role-aware API assertions; existing ZAP/SARIF retained | No claim of complete vulnerabilities or penetration testing; active attacks not added |
| Accessibility | Existing axe retained, plus dated manual keyboard/screen-reader/reflow/state/error evidence | Manual checklist is not a full WCAG audit |
| CI/CD | New automatic push/PR GitHub Actions matrix for Ubuntu/Windows and three browser engines | Workflow must be placed at repository root; no hosted run was performed here |
| Test management | SQLite case ownership, priority, requirement, append-only review history, report import/export, local dashboard | No team authentication, SaaS hosting or built-in Jira/TestRail sync |
| Multiple languages and scaling | `suite.py` runs trusted argv commands in parallel and supports CI sharding; JUnit ingestion | Install each language/runtime; no cloud autoscaling provisioning |
| Native/real-device execution | `mobile.py` Appium session adapter for Android/iOS and cloud Appium URLs | Requires Appium drivers, app, device or provider credentials; real hardware not bundled |
| Failure investigation | Playwright traces, masked-input failure screenshot, JS/HTTP/request diagnostic counts | Evidence aids diagnosis; it does not prove a root cause or identify a code commit |

## Run your workflows

Use `examples/company-workflows.json` as the schema example. Set `base_url`, selectors, API paths and expected results for your staging app. Each test needs at least one explicit outcome assertion. Change browsers to `["chromium", "firefox", "webkit"]` when installed. The fixture treats `run_id` as the idempotency key; adapt to your API's actual idempotency header/key contract.

```powershell
.\.venv\Scripts\python.exe company_qa.py workflow .\examples\company-workflows.json --allow-actions --workers 2 --repeats 2
```

For that example command, first run `python examples/company_demo.py` in a separate terminal, or simply use `run_company_demo.py` above.

Workflow actions: `goto`, `reload`, `fill`, `click`, `press`, `select`, `check`, `expect_text`, `expect_count`, `expect_url`, `request`, `parallel_requests`, `assert`.

- `${run_id}` is a fresh UUID per scenario/browser/viewport/repeat. `${base_url}` is also supplied.
- `variables` and each `dataset` row supply additional `${column}` variables. A whole-value token preserves JSON number/boolean/list types; CSV cells remain strings. Excel numeric cells and JSON values retain types.
- `datasets` maps names to rows or relative `.csv`, `.json`, `.xlsx` files inside the configuration folder. `blocks` defines steps referenced with `{"use":"name"}`.
- `setup`, `steps`, `cleanup` are ordered step arrays. Cleanup runs in `finally` when a context was established; every cleanup failure is reported as ERROR. A killed process or unavailable backend cannot guarantee cleanup.
- `request` takes `url`, optional `method`, `headers`, `json`, `expect_status`, `expect_json`, and `capture`. JSON paths use dot keys and numeric array indexes, e.g. `orders.0.id`; `$` means root. A capture such as `{"order_id":"id"}` creates `${order_id}` for later steps.
- `expect_json` entries use `path`, `operator` (default `eq`), `expected`. Operators: `eq`, `ne`, `count`, `contains`, `lte`, `gte`. `assert` uses `actual`, `operator`, `expected`.
- `parallel_requests` executes 2–10 identical scoped API calls, waiting for all calls before cleanup. Follow it with a backend count assertion. It cannot capture a single ambiguous response.
- Role configuration: `"roles":{"admin":{"headers_env":{"Authorization":"QA_ADMIN_AUTH"}}}`; add `"role":"admin"` to a request. Set the environment variable to the complete authorization value. UI credentials can use `fill` with `value_env`. No credentials are guessed.
- API requests and top-level navigations must stay on the configured origin. API redirects are not automatically followed. Browser external GET resources may load. External mutation requests are blocked. Cross-origin identity providers require a different reviewed integration; no silent bypass.
- `--allow-actions` permits form actions and API mutations. Without it, these operations return ERROR, never PASS. Even GET requests may have side effects; use disposable staging data.
- Failures do not become passes on retries. `--repeats` records each attempt, flags mixed results, and keeps the overall run unsuccessful.

Reports are JSON, HTML and JUnit in the output folder. Exit 0 means all executed configured checks passed; 1 means failure/incomplete; 2 means configuration/setup error. These reports do not alter the legacy headline score or infer universal coverage.

**Artifacts can contain secrets:** traces contain DOM and network data, including credential requests. Input masking applies to failure PNGs, not the trace archive. Keep reports private, use test accounts, and review before sharing or uploading CI artifacts.

## HTTP load

Edit `examples/company-load.json`, then:

```powershell
.\.venv\Scripts\python.exe company_qa.py load .\examples\company-load.json --allow-load
```

Only run against a target authorized for load testing. Limits: 50 users, 50 requests/second globally, 5,000 total requests, 300 seconds. Default is 2 users, 20 requests, 5 RPS. Deadline truncation is ERROR. Redirects are not followed. Performance budgets use p95 for all completed attempts and the expected HTTP status/error rate. Existing page LCP/CLS/load checks remain separate.

## Security and accessibility

```powershell
.\.venv\Scripts\python.exe company_qa.py security C:\your-app --ecosystems npm
.\.venv\Scripts\python.exe company_qa.py security C:\pinned-python-dependencies --ecosystems python
.\.venv\Scripts\python.exe company_qa.py accessibility .\examples\company-accessibility.json
```

npm requires Node/npm and a lockfile. Python requires a separate fully pinned **transitive** `requirements.txt` containing `name==version` lines: no package builds or dependency resolution is performed by this scanner. Audit results depend on advisory services and network availability; execution errors are not a clean scan. No fixes are applied. Scanner results may need exploitability review. Existing `tester.py --help` lists the ZAP and imported SARIF options.

Manual accessibility evidence starts REVIEW. A completed entry requires `status` PASS/FAIL, `reviewer`, `tested_at`, and `evidence`. Do not mark it PASS without doing the manual check. Completed attestations never silently overwrite automated results.

## Case ownership, reviews and dashboard

```powershell
.\.venv\Scripts\python.exe company_qa.py manage case --file .\examples\company-case.json
.\.venv\Scripts\python.exe company_qa.py manage review --file .\examples\company-review.json
.\.venv\Scripts\python.exe company_qa.py manage import --file .\reports\company-demo\report.json
.\.venv\Scripts\python.exe company_qa.py manage serve
```

Open http://127.0.0.1:8780. The dashboard is read-only and loopback-only. CLI changes persist in `reports/company.db`. Each review is a new audit row; human names are attestations, not authenticated identities. `manage export` writes cases, runs and reviews to JSON. Tests can supply `case_id` to associate results with a managed case. This is a local workbench, not a multi-tenant test-management platform.

## External suites / language adapters

```powershell
.\.venv\Scripts\python.exe suite.py .\suite.company.example.json --workers 2 --allow-commands
```

Review manifests before execution. Commands are argv arrays without a shell. Use installed executables to run your Java/Maven, C#/dotnet, JavaScript or Python suites; supply their JUnit glob. Set executable paths explicitly if they are not on PATH (the example uses `python`). `--shard-count N --shard-index K` partitions jobs across CI machines. Without JUnit, only the command's exit status is assessed, not coverage. Logs can contain secrets. Timed-out jobs are terminated with their process tree.

## Android/iOS and real devices

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-mobile.txt
$env:APPIUM_SERVER_URL = "http://127.0.0.1:4723"
.\.venv\Scripts\python.exe mobile.py .\examples\company-mobile.json --allow-actions
```

Replace the example app, capabilities and locators first. For iOS use the appropriate XCUITest capabilities and a macOS/Appium host or cloud provider. For cloud devices use the provider's Appium endpoint/capabilities and keep credentials in the environment. Actions supported: click, fill, visible, text, context. Device kind is user/provider evidence, not automatically certified by our client. A screenshot/XML snapshot may contain sensitive app content. Missing sessions produce ERROR.

## Regression verification

```powershell
$env:QA_COMPANY_BROWSER_TESTS = "1"
$env:QA_BROWSER_TESTS = "1"
.\.venv\Scripts\python.exe -m pytest tests tests_company tests_advanced/test_autonomous.py -q
```

Set `QA_TEST_BROWSERS` to `chromium,firefox,webkit` for the company and legacy matrix fixtures after installing those engines. The new GitHub workflow checks one engine per job on two operating systems; it uses local demo data, not production credentials.

Official integration references: [Appium Python](https://appium.io/docs/en/latest/quickstart/test-py/), [Playwright API requests](https://playwright.dev/python/docs/api/class-apirequestcontext), [npm audit](https://docs.npmjs.com/cli/v11/commands/npm-audit/).
