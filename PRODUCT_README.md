# QA Workbench — local beta

This release connects the existing tester to a local browser dashboard. It adds projects, accounts, recording, editable assertions, issue drafts, installation diagnostics and a small known-bug benchmark. It is a beta product shell, not a hosted multi-tenant SaaS or a guarantee of exhaustive testing.

## Start on Windows

Extract the ZIP. Open the `website_tester` folder containing **product_app.py**, then double-click **setup_product.bat**.

Or use PowerShell in that folder:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-product.txt
.\.venv\Scripts\python.exe product_app.py
```

On first launch, create an administrator in the terminal. Use a password of at least 12 characters. Password characters are not displayed while typing. The app opens at http://127.0.0.1:8790. Keep the terminal open.

For later launches, double-click **start_product.bat** or run the last command again.

## First scan

1. Sign in and create a project with the website URL.
2. Open **Setup → Check installation**.
3. Install Node.js/npm if reported missing, reopen the terminal, then choose **Install browser & axe dependencies**. This admin action downloads the project's dependencies and three browser engines. It does not install Node.js or bypass OS permissions.
4. Return to **Overview**, choose Standard or Thorough and start a run.
5. Open the run under **Runs & findings** for live logs, findings and report downloads.

Standard uses the existing tester with eight pages, desktop/mobile sizes and three samples. Thorough uses its existing preflight and stricter completeness rules. Execution status COMPLETED is a process result, not release approval. Always inspect actual quality, coverage and unresolved checks. No percent-complete estimate is invented for unknown crawl scope.

Checking the action authorization box permits test interactions and configured mutations. Use approved test environments and disposable data. Public read-only scans need no stored credentials.

## Record and replay

1. Select a project and open **Workflows**.
2. Confirm permission to interact and select **Open recorder**.
3. A local Chromium window opens. Perform the workflow yourself.
4. **Alt+click** an element to supply its expected text. This records an assertion. Expected outcomes must come from your requirements.
5. Close the recording window. Open that run and choose **Load recording into editor**.
6. Review selectors and steps, add/edit assertions, then save a workflow version.
7. Save private inputs such as `QA_INPUT_1` under **Team & privacy**.
8. Select the saved workflow under Overview, authorize actions and run it.

The recorder does not collect typed text or select values. It stores private input names. The editor shows their selectors so you can enter the correct replay values. Select values should match the option's HTML value. The recorder's draft is not automatically approved or run.

The visual editor supports one journey per saved version: click, fill, select, check/uncheck, press, goto, URL/text/value/count/visibility/enabled assertions. Workflows export to the existing tester JSON. Multi-journey, API and advanced evidence configurations remain available through the CLI. Recording cannot capture every canvas widget, cross-origin login flow, popup, iframe or file upload. It requires a desktop display; a headless cloud server cannot open the interactive recording window.

## Reports, assignments and issue exports

Open **Load findings** after a completed run. Select a finding, assign its owner, record reproduction evidence and choose a review state. Reviews are append-only and do not change measured findings.

Jira CSV and GitHub Markdown exports include the named check, expected/actual information, reproduction guidance, evidence reference and latest human review. Unknown reproduction details are labeled, not invented. Generic crawler findings need manual reproduction; the tool cannot certify that every reported exception is a product defect.

**No issues are sent automatically.** Dashboard exports are reviewable files. An optional CLI can create GitHub or Jira Cloud issues after you confirm a digest of the exact destination and content. Account linking, background synchronization and publication directly from the dashboard are not implemented.

Preview a selected finding:

```powershell
.\.venv\Scripts\python.exe publish_issue.py path\to\report.json --finding FINDING_ID --provider github --repository OWNER/REPOSITORY
```

Review the printed preview. Set `QA_ISSUE_TOKEN` in your process environment using your credential-management method, then repeat with `--publish --confirm-digest THE_PRINTED_DIGEST`. Never paste a token into the command itself. Jira Cloud uses `--provider jira --server https://YOURTEAM.atlassian.net --project PROJECTKEY --email YOUR_ACCOUNT_EMAIL`; its token is read from the same environment variable. The project must allow the selected issue type and supplied fields; additional mandatory custom fields are not supported by this minimal adapter.

Publication writes an attempt record before sending, rejects redirects, and never retries automatically. After a timeout or error, inspect the provider and the attempt record before any manual retry to avoid duplicates. Evidence files are referenced locally, not uploaded. Live publication was not performed during development; requests and approval behavior were tested with simulated responses.

Official API references: [GitHub issues](https://docs.github.com/en/rest/issues/issues#create-an-issue), [Jira Cloud issues](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issues/).

## Accounts and privacy

- Admin: create accounts, reset passwords, install dependencies, access all projects, purge expired artifacts.
- Tester: create projects and run/edit projects they own or are granted access to.
- Viewer: inspect accessible projects, JSON reports and logs; cannot run, edit or download HTML, XML or binary artifacts.
- Project owners/admins can grant or revoke membership. Admins retain global access. Password resets invalidate that account's sessions.
- Passwords use salted PBKDF2 hashes. Sessions expire after eight hours. Mutations require a session-bound token; foreign browser origins and invalid Host headers are rejected. Login attempts are rate limited.
- Private inputs use supported OS keyrings (Windows, macOS, Linux Secret Service). Unsupported/plaintext keyring backends are rejected. Values are never returned through a browser API.
- Known private inputs are redacted from logs and JSON string values; standard scan HTML/JUnit reports are regenerated from that sanitized JSON. Numeric measurements are preserved. Short private values are masked when they occupy an entire JSON string, to avoid corrupting unrelated text. Exported issue text also redacts common secret patterns and URL query values. This is not guaranteed removal of every unknown sensitive value.
- **Raw traces, screenshots and other non-regenerated artifacts can contain credentials or personal data.** They remain restricted to project testers/admins, but are not encrypted by this application. Keep `product-data` private and use OS disk protection. Review evidence before sharing.
- OS keyring values are scoped to the retained `instance-id` and project. Back up the entire data folder for updates. Moving machines may require re-entering private inputs because OS vaults do not move with the folder.
- Artifact retention is an explicit admin purge, minimum one day. Run metadata/review audit records remain. Pending and active runs are not purged.

The server binds **127.0.0.1 only**. Accounts and project permissions can be exercised on one workstation. Remote team hosting, HTTPS termination, SSO/MFA and multi-tenant isolation require a separate deployment design and validation; do not expose this development server to the internet.

## Benchmarks and CI

Choose **Local benchmark** to test the included healthy order backend and an intentionally broken duplicate-order backend. It repeats each case, checks cleanup and reports false-positive, missed-defect and inconclusive **fixture counts**. Infrastructure errors are inconclusive, not successful detection.

These are two fixtures, not a representative accuracy dataset. They do not measure all UI, security, accessibility or business logic bugs. Extend the labeled fixture suite before claiming detection accuracy.

The GitHub workflow includes product tests. Browser integration tests run in Chromium jobs; company tests retain their browser matrix. Hosted CI itself has not been executed in this session.

## Updates and recovery

Updates are manual: stop the app, back up `product-data`, extract the reviewed new version, install its requirements and start with your retained data directory:

```powershell
.\.venv\Scripts\python.exe product_app.py --data-dir "D:\QA-Data"
```

There is no unauthenticated auto-update channel. Browser setup checks required tools and logs installer failures. Jobs are queued one at a time (up to 20 waiting) to keep laptop resource usage bounded. Stop cancels the process tree. After an interrupted restart, unfinished runs are marked INTERRUPTED; they are not silently called successful or automatically replayed.

Original CLI tools, company workflows, autonomous exploration and scratch-model training remain available. This release does not train a new model or remove the need for requirements, credentials and human judgment.
