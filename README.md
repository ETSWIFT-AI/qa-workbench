QA Workbench

A local web dashboard for scanning websites, recording browser workflows, and turning findings into reviewable issues.

Most test tools hand you one score and call it a day. QA Workbench reports two numbers, tested quality and coverage, so a site with a single passing check is never mistaken for a site that is ready to ship.



Status: local beta. Runs on your own machine (loopback only). It is not a hosted SaaS and does not guarantee exhaustive testing. See Limitations.

Features
Cross-browser scans. Chromium, Firefox and WebKit across desktop, mobile and tablet viewports.
Record and replay. Perform a workflow in a real browser, Alt+click to add assertions, then edit and re-run it as a saved test.
Broad checks. Functionality, form validation, accessibility (axe-core), security headers (CSP, HSTS, framing), performance and reliability.
Honest scoring. Quality and coverage are reported separately. Skipped or errored checks count as unknown evidence, not as product failures.
Issue export. Assign findings, record reproduction notes, and export to Jira CSV or GitHub Markdown. Nothing is sent automatically.
Accounts and privacy. Admin / Tester / Viewer roles, per-project access, salted password hashes, CSRF and Origin checks, and redaction of private inputs in logs and reports.
Run history. Trends, new failures and fixes compared across runs of the same target.
Quick start

Windows: extract the folder and double-click setup_product.bat, then use start_product.bat for later launches.

Any OS:

bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-product.txt
python product_app.py

On first launch, create an administrator in the terminal (password of at least 12 characters). The app opens at http://127.0.0.1:8790.

Then:

Create a project with your site's URL.
Open Setup → Check installation and install the browser and axe dependencies if prompted (requires Node.js/npm).
Choose Standard or Thorough and start a run.
Open the run under Runs & findings for live logs, findings and report downloads.
Record and replay a workflow
Open Workflows in a project and select Open recorder.
Perform the workflow in the Chromium window that opens.
Alt+click an element to record an assertion with its expected text.
Close the window, load the recording into the editor, review the steps, and save a version.
Run the saved workflow from the Overview page.

The recorder never stores typed text. It stores the names of private inputs, and you provide the values under Team & privacy (kept in your OS keyring).

Understanding the two numbers
Metric	Question it answers
Tested quality	Of the checks that actually completed, how well did the site do?
Coverage	How much of the configured or recorded evidence actually completed?
Quality is a severity-weighted pass rate (critical = 5, high = 3, medium = 2, low = 1) across completed PASS/FAIL checks.
SKIP, REVIEW and ERROR results lower coverage only. They never count against quality.
One passing check can give high quality but very low coverage. The report labels this PARTIAL ASSESSMENT and will not approve a release.
Release approval requires quality of at least 90, coverage of at least 90%, no high or critical failures, no execution errors, and every declared critical journey passing.

These weights are project policy, not an industry certification or a bug-detection probability.

Command line

The scanner behind the dashboard can also be run directly:

bash
# Read-only scan
python tester.py "https://your-staging-site.example" --max-pages 10

# Full workflows across the browser matrix (staging only)
python tester.py "https://your-staging-site.example" \
  --config my-rules.json --allow-actions --auto-fields \
  --browsers chromium,firefox,webkit --viewports desktop,mobile,tablet

Read-only mode blocks state-changing requests. Use --allow-actions only on environments you own, with disposable data.

Create GitHub or Jira issues from a report (preview first, then publish with a confirmation digest):

bash
python publish_issue.py path/to/report.json --finding FINDING_ID \
  --provider github --repository OWNER/REPOSITORY

Set QA_ISSUE_TOKEN in your environment. Never put a token on the command line.

Safety and privacy
The server binds to 127.0.0.1 only. Do not expose it to the internet. Remote hosting would need HTTPS, SSO/MFA, worker isolation and a separate security review.
Only scan sites you own or are authorized to test.
Screenshots, traces and the data folder can contain credentials or personal data and are not encrypted. Keep product-data/ private and review evidence before sharing.
Redaction covers known private inputs and common secret patterns. It is not a guarantee that every sensitive value is removed.
Limitations
Benchmarks cover two fixtures (a healthy backend and one with a known duplicate-order bug). They are not a measure of detection accuracy.
Security checks are passive analysis, not penetration testing.
A tool cannot know your product's intended behavior. Business-rule coverage depends on assertions you write.
Not yet tested: Windows launchers and keyring, live Jira/GitHub publishing, Firefox/WebKit dashboard UI, multi-user remote deployment.
The recorder needs a desktop display and cannot capture every canvas widget, popup, iframe, file upload or cross-origin login.
Development
bash
pip install -r requirements-product.txt
pytest tests tests_product

Browser integration tests run in Chromium. Details of what has and has not been validated are in docs/VALIDATION.md. Release notes are in CHANGELOG.md.
