# Config-free autonomous exploration

## Run

Keep your old tester and optional trained UI model. For a fresh extraction run `setup_windows.bat` once. Then double-click **`start_autonomous.bat`** and enter an authorized test website URL.

No selector JSON is required for the recognized actions. If a conventional login form is found and credentials are missing, the launcher asks for a test username and masked password **after discovery**. Press Enter to skip authentication. It then reruns the bounded explorer with that test account; it does not rerun the entire original scan. MFA/CAPTCHA and unknown expected outcomes are reported as questions, not guessed. Credentials are not written to config files, command-line arguments or reports.

The new mode runs without neural training. If `models/calista_ui/` contains your trained screenshot CNN, it adds that separate experimental aesthetic estimate. To move an earlier trained model into a fresh extraction, copy only your `models` folder; create a new `.venv` with setup rather than moving an old virtual environment.

PowerShell alternative:

```powershell
.\.venv\Scripts\python.exe advanced.py scan "https://YOUR-TEST-SITE/" --autonomous-actions --output reports\autonomous
Start-Process .\reports\autonomous\advanced\advanced-report.html
```

For unattended login, supply test credentials as `QA_TEST_USERNAME` and `QA_TEST_PASSWORD` environment variables in your local process. They are never guessed. Avoid real personal/admin accounts; stateful tests belong on your disposable test environment.

Without UI clicks or authentication:

```powershell
.\.venv\Scripts\python.exe advanced.py scan "https://YOUR-TEST-SITE/" --autonomous
```

This still follows selected same-origin links with GETs. It is read-only at the HTTP-method level, not a guarantee of zero side effects on a poorly designed website.

## What it does

- Observes visible controls, fields, semantic labels, form association, page text and screenshots.
- Prioritizes a discovered login link. Recognizes a unique visible password field, username/email field and explicitly named sign-in control. Uses one supplied-credential attempt per exploration run.
- Keeps cookies in memory to explore authenticated states. Does not export login storage state.
- Selects same-origin links, named navigation/disclosure buttons, tabs, menu controls and summaries. Uses bounded path replay for JavaScript state exploration and refuses changed/ambiguous targets.
- Exercises a uniquely detected native `type=search` GET form with the query `test`. Result relevance is left for independent assessment.
- Samples native number/email constraints using detached DOM clones. This does not trigger application events or prove business validation/submission correctness.
- Records before/after screenshots, decisions, changes, runtime errors, observed HTTP errors, remaining paths and focused questions.
- Masks input fields and known credential text in screenshots; redacts supplied credential strings from the JSON report. Other private page content may remain in screenshots, so treat artifacts as sensitive.

The decision engine is **deterministic semantic heuristics**, not a newly trained neural agent or a human-equivalent brain. The CNN judges screenshot aesthetics only. No pretrained AI service is introduced. Merely adding CNN/RNN/Transformer layers cannot establish an application's intended business rules.

## Verdicts and boundaries

A successful click is not automatically a successful test. Page/state changes and sign-out UI are REVIEW evidence. `LIKELY_AUTHENTICATED` means relevant UI evidence appeared; it does not prove server authorization, roles or object ownership. Bad credentials are not automatically an application defect. Uncaught JavaScript errors and document HTTP errors are recorded as observed failures; causality or product intent still needs investigation. Navigation/runtime interruption is an execution ERROR.

Purchase, delete, send, publish, registration, password-reset and similar controls/routes are excluded by conservative name/path rules. Generic form submissions are not attempted. Non-read-only requests are blocked except same-origin POSTs to the detected login destination or recognizable auth/session endpoints during the narrow sign-in window. All cross-origin requests are blocked after the sign-in attempt begins. Names and routes are imperfect clues, so these rules do not make arbitrary production interaction risk-free.

No SSO across origins, credential guessing, CAPTCHA bypass, MFA completion, browser downloads/popups, arbitrary code execution, private backend reconstruction, payment, messaging or deletion is implemented. Complex multi-step/passwordless/localized login, iframe/shadow DOM controls, custom POST search, and domain-specific forms may remain untested. The tool cannot know correct prices, permissions, age limits or business outcomes without an independent specification.

Default budgets: 20 action records (including replay clicks/login/search), 12 distinct visited states, path depth up to three recognized clicks, 120 seconds. Navigation and filling are additional operations within those state/time budgets. Change them with `--agent-actions`, `--agent-states`, `--agent-seconds`. Reports show when paths remain. Budget exhaustion is incomplete coverage, not a clean bill of health. Screenshots from an additional post-login state can make the recorded state count exceed the unique-visited-state budget by one.

The original `tester.py`, `gui.py`, configurations and v3.1 self-healing code remain unchanged. The autonomous section supplements that report; its exploratory REVIEW results do not silently raise the original quality score. Its authenticated session is separate from the baseline scan and the advanced read-only collector.

## Try the included local demo

In terminal one:

```powershell
.\.venv\Scripts\python.exe examples\autonomous_demo.py
```

Run `start_autonomous.bat` and use `http://127.0.0.1:8766/`. When asked, use the disposable demo account `demo@example.com` / `Demo-only-123`. This demo binds to loopback and is not production authentication code.

See `AUTONOMOUS_VALIDATION.md` for actual tests and limitations.
