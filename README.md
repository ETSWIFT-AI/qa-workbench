# Website QA 3.0 — tested quality, coverage and history

Version 3 corrects the misleading headline score, expands workflow testing across the browser/viewport matrix, and adds a desktop launcher, guided rule builder, automatic HTML-boundary checks, bounded SPA exploration, persistent history, integrated ZAP baseline execution and optional real-user performance data.

## Easiest Windows setup

1. Extract the ZIP. Open the folder containing `tester.py` and `gui.py`.
2. Double-click **setup_windows.bat**. It creates a virtual environment in that same folder and installs Chromium.
3. Double-click **start_gui.bat**.
4. Enter your URL, choose a profile, and click **Start scan**.
5. Use **Open report** or **Run history** afterward.

Python must be installed with the Windows `py` launcher. The desktop interface uses standard-library Tkinter; no PyQt installation is needed. Run the batch files from the extracted project; they locate their own folder, avoiding the previous Downloads/nested-folder problem.

To update an existing `C:\website_tester` installation, back up your custom rules, reports, approved baselines and login state; extract the new project into a separate folder and run its setup. Do not overwrite your custom rules or use an old sample report as a new scan.

### Optional components

From a terminal inside the project:

```powershell
.\.venv\Scripts\python.exe -m playwright install firefox webkit
npm ci --ignore-scripts
.\.venv\Scripts\python.exe -m pip install -r requirements-ai.txt
```

The full browser matrix needs all three engines installed. `npm ci` installs axe-core; the scanner automatically uses it when present. Optional AI/visual-comparison packages are separate. Docker is needed only for integrated ZAP. CrUX requires a Google API key or an existing CrUX JSON record. Missing components are shown as gaps/errors, not fabricated passes.

## What changed for each feedback item

| Feedback | Correction in version 3 |
|---|---|
| Worst single result zeroed an entire family | Quality is a severity-weighted mean over completed PASS/FAIL checks. Coverage is separate. SKIP/REVIEW/ERROR do not count as product failures. No completed checks means **Not assessed**, not 0/100. |
| Too much hand-written JSON | Desktop test builder and CLI wizard generate navigation, integer-age boundary and API-status recipes. Optional automatic field checks use declared HTML constraints. Structural checks run without config. Business correctness still needs an independent expected outcome. |
| Workflows only on the first desktop engine | Configured journeys and field tests run in **every requested available browser × viewport**. Missing engines produce explicit workflow coverage errors. |
| Default run never tests mutations | Read-only mode remains deliberate. Reports prominently say state-changing workflows were not tested. Staging mode makes opt-in visible in the GUI and enables approved actions. |
| Shallow security | Added CSP-source/base-uri/frame-ancestor analysis, HSTS duration and framing-value analysis, plus a command that executes and imports ZAP baseline automatically. This is passive security analysis, not comprehensive penetration testing. |
| Lab-only performance | Raw repeated lab samples are retained; optional CrUX real-user LCP/CLS/INP is shown separately with its period and availability. Lab timing is never relabelled as field data. |
| REVIEW crushed scores | Reviews appear in a separate queue and lower coverage only. Their existence does not lower tested quality. |
| Shallow JS exploration | Bounded breadth-first exploration replays multi-step button/tab/link paths in fresh contexts, tracks DOM/URL states, and preserves hash routes. Discovered states and follow-up routes are reported. |
| No history | SQLite stores snapshots by target and scan profile. Reports show trends, new failures, explicit fixes and previously failing checks no longer observed. |
| CLI-only | Native desktop GUI, presets, no-JSON recipe builder, Windows launchers and CLI wizard. Advanced CLI remains available. |

## The two numbers

**Tested quality** answers: “Of the deterministic checks completed, how well did the site do?”

Within each family, calculate weighted PASS / weighted (PASS + FAIL), using critical=5, high=3, medium=2, low=1, info=1. Average the available family scores using the category weights below, split equally across the category's families. Untested families are excluded from this quality denominator.

**Coverage** answers: “How much of the framework's configured/recorded evidence is complete?”

For each fixed family, use completed PASS/FAIL cases divided by all recorded cases; unconfigured families have zero coverage. Combine using the fixed family weights. REVIEW, SKIP and ERROR are unknown evidence, not product failures. This is not a percentage of every possible path in the website.

Example: **354 PASS + 1 SKIP** in a family gives **100% tested quality** and **99.7% coverage in that family**. It does not produce zero. If other families have not been configured, overall coverage remains low.

A single passing check can yield high *tested quality* but very low coverage. The report labels this **PARTIAL ASSESSMENT** and does not approve release. A scan that cannot load anything displays **NO ASSESSMENT**.

| Category | Weight |
|---|---:|
| Functionality | 25 |
| Validation | 15 |
| Reliability | 10 |
| Performance | 10 |
| Accessibility | 10 |
| Security | 15 |
| Compatibility | 10 |
| Lifecycle evidence | 5 |

Release approval still requires quality >= 90, coverage >= 90%, no high/critical confirmed failure, no execution error, and at least one passing critical business journey with every declared critical journey passing. Lots of passes cannot override this blocker. These weights are project policy, not an industry certification or bug-detection probability.

## Modes and profiles

- **Read-only:** browse, inspect DOM/headers, observe errors/performance, trial clicks and accessibility checks. Non-GET/HEAD/OPTIONS requests are blocked. This may also block legitimate read APIs that use POST; the report records that gap.
- **Staging/actions:** permits approved workflow actions, field events and configured API mutations. Optional exploration and ZAP crawling require explicit action authorization.
- **Quick:** few pages, one timing sample, desktop Chromium. Good for a quick diagnosis, not high-confidence coverage.
- **Standard:** desktop and mobile viewports with repeated samples.
- **Full matrix:** Chromium, Firefox and WebKit × desktop, mobile and tablet, including configured journeys/fields.

Use owned/authorized targets and disposable data for staging actions. Browser context isolation does not undo backend changes. Even GET requests or page scripts can change server state. Exploration's label exclusions are heuristics, not a guarantee of harmlessness. It does not submit form controls intentionally.

## Local demo

In terminal 1:

```powershell
.\.venv\Scripts\python.exe examples/demo_site.py
```

In terminal 2:

```powershell
.\.venv\Scripts\python.exe tester.py http://127.0.0.1:8765 --config examples/demo-rules.json --allow-actions --auto-fields --output reports/demo
```

Then:

```powershell
Start-Process .\reports\demo\report.html
```

Or click **Start local demo** in the GUI, select staging mode and tick the authorization box. The deliberately faulty demo should fail the gate. It is not representative of a production site's expected score.

## Build tests without writing JSON

Open the GUI's **Build tests without JSON** tab:

- Navigation recipe: starting page, control selector, expected destination.
- Integer-age recipe: page, field selector and independently specified minimum/maximum.
- API recipe: endpoint and expected HTTP status.

Save the rules and they are selected for the next scan. Use IDs shown by your browser's Inspect tool or the report's input inventory as selectors (for example `#age`). The builder reduces configuration syntax; it cannot infer your product's intended requirements.

The terminal alternative is:

```powershell
.\.venv\Scripts\python.exe tester.py --wizard
```

`--auto-fields --allow-actions` generates and runs boundary cases from declared HTML limits without a rules file. These results belong to **native_forms**, not business-rule coverage. A field declaring the wrong age limit still requires independent requirements to catch that mistake. No automatic submission is performed by these inferred cases; client-side events can nevertheless save data.

## CLI examples

Read-only:

```powershell
.\.venv\Scripts\python.exe tester.py "https://your-staging-site.example" --max-pages 10
```

Full workflows:

```powershell
.\.venv\Scripts\python.exe tester.py "https://your-staging-site.example" --config my-rules.json --allow-actions --auto-fields --browsers chromium,firefox,webkit --viewports desktop,mobile,tablet --max-seconds 1800
```

State discovery:

```powershell
.\.venv\Scripts\python.exe tester.py "https://your-staging-site.example" --allow-actions --explore-actions --exploration-depth 2 --max-states 20
```

Each engine/viewport explores within the selected bounds. Client-side states are captured even when no anchor points to them; new routes found during exploration are listed for follow-up. This is not an exhaustive model of all SPA state, shadow DOM, nested frames or role combinations. Replay stops on changed/ambiguous control text rather than knowingly clicking a different target.

A unique timestamped report directory is created by default. `--output` selects a fixed directory. History still preserves snapshots if that directory is reused. `--no-history` disables persistence; `--history` chooses the SQLite file.

## Security and performance integrations

### ZAP baseline in one command

Install/start Docker, then:

```powershell
.\.venv\Scripts\python.exe tester.py "https://your-staging-site.example" --allow-actions --zap-baseline
```

The maintained ZAP container spiders the target and runs passive rules. Its JSON/HTML/log output is saved under the run's `zap/` folder and imported automatically. There is no active attack scan. Findings remain candidates until confirmed; an empty report is not proof that all vulnerabilities were tested. Container networking must be able to reach the target: Docker's localhost is not your host's localhost. This adapter does not silently rewrite target origins or authentication.

You can still import `--zap-report zap.json` and `--sarif scan.sarif`. SARIF imports source/dependency findings; the program does not itself scan backend source or resolve dependencies. Cookie checks need `session_cookie_names` for security-sensitive cookies.

### Real-user performance

```powershell
$env:CRUX_API_KEY="your-api-key"
.\.venv\Scripts\python.exe tester.py "https://your-site.example" --crux-key-env CRUX_API_KEY
```

Or pass `--crux-file crux.json` from an existing CrUX API response. Origin matching is checked. Field metrics, collection dates and unavailability appear separately from lab results; they do not silently alter the local test score. Low-traffic/unlisted sites may have no CrUX record, and CrUX reflects eligible Chrome users, not every user. API errors/unavailability do not become website defects.

## Advanced rules, review and privacy

Existing v2 rule files remain supported. Journeys accept click, fill, press, select, check/uncheck, goto and assertions for URL, visible/hidden, text/value, enabled/disabled and count. Environment-backed values use `value_env`; API credentials can use `headers_env`. Store tokens/passwords in environment variables or protected Playwright storage-state files, never committed rules. A field case with `error_selector` checks custom error visibility; add journey/API assertions to prove persistence.

Role-based APIs use `authorization_test: true` with an explicit `role` and expected status/body. Write both allowed and denied/ownership cases. Login state can be passed globally or per test; each browser/viewport uses a fresh context. Repeated mutation flows must use idempotent fixtures or unique data and cleanup you provide. The program cannot reset your database automatically.

`--resolutions reviewed.json` resolves REVIEW IDs with PASS/FAIL, reviewer and reason. The original status and attribution remain visible. Skips/errors must be rerun, not signed off as passes. Lifecycle `evidence` files record user-attested requirements/operations review, not independent certification.

Reports, screenshots, traces and the history database can hold sensitive data. Displayed query values are redacted, but screenshots, error messages, input values and stored snapshots may still expose secrets. Protect artifacts and restrict access. This local CLI/desktop tool must not be deployed as a public URL-scanning service without worker isolation, authentication, resource limits, egress/DNS/redirect controls and artifact access policies.

## Optional AI

Existing v2 features remain: TF-IDF/DBSCAN grouping, local sentence-transformer embeddings, local Ollama text/vision suggestions and `train_triage.py` for a logistic-regression + neural MLP ensemble. Install `requirements-ai.txt`; sentence-transformers and model weights are additional. AI is advisory and never sets scores or test outcomes. Training requires genuine labelled examples and held-out projects. Only load trusted joblib files.

## Tests, CI and limits

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
$env:QA_BROWSER_TESTS="1"
$env:QA_TEST_BROWSERS="chromium,firefox"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tests include scoring regressions, missing evidence, release blockers, history matching, field-data origin validation, guided recipes, browser/viewport-specific workflow failures and a two-step SPA fixture. See `VALIDATION.md` for what was actually run in the delivery environment.

Exit codes: 0 = no FAIL/ERROR (gaps may remain); 1 = observed failed checks; 2 = execution error; 3 = `--enforce-gate` was requested and not met. The example GitHub workflow is still available.

Remaining boundaries: no all-vulnerabilities guarantee, automatic business oracle, real-device lab, source-level SDLC certification, full stress/soak testing, database cleanup or cross-browser equivalence proof beyond the configured tests. The GUI makes setup easier; it does not remove the need for well-defined requirements.

References: [Playwright browsers](https://playwright.dev/python/docs/browsers), [ZAP baseline](https://www.zaproxy.org/docs/docker/baseline-scan/), [CrUX API](https://developer.chrome.com/docs/crux/guides/crux-api).
