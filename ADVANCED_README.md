> **Bundled real UI dataset:** for one-command screenshot-only training, read `UI_TRAINING_README.md` and run `setup_ui_and_train.bat`. The multimodal training instructions below are separate.

# Advanced add-on — from-scratch website learning research

The attached v3.1 tester remains byte-for-byte unchanged. Keep using `tester.py`, `gui.py`, and their existing commands. This optional package adds a separate `advanced.py`, `advanced_gui.py` and `advanced/` directory. No trained expertise is bundled. It is a working training/observation framework, not a perfect autonomous QA engineer.

## Start on Windows

Open PowerShell in the folder containing `tester.py`:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe advanced.py scan "https://badssl.com/" --output reports\advanced_run
Start-Process .\reports\advanced_run\advanced\advanced-report.html
```

The existing deterministic scan runs first, followed by bounded read-only UI collection, a visible client structure map and test priorities. Without a qualified checkpoint the model explicitly says **NOT_TRAINED**, not a fabricated neural rating. Standard testing works without installing PyTorch. For a simple launcher, run `start_advanced.bat` after setup; the scan opens in a separate console. Original `start_gui.bat` still runs the original GUI.

The new wrapper rejects spaces inside URLs. It does not silently widen the original tester's origin restriction or bypass TLS failures. Enter the final canonical HTTPS hostname when a site redirects to another origin. This URL validation change applies to the new command only; the original runner is preserved.

Approved business tests can run without interactive prompts:

```powershell
.\.venv\Scripts\python.exe advanced.py scan "http://127.0.0.1:8765/" --config examples\demo-rules.json --allow-actions --auto-fields --explore-actions --output reports\demo_advanced
```

Run the included demo server in another terminal first: `.\.venv\Scripts\python.exe examples\demo_site.py`. Actions need a disposable authorized environment. The subsequent advanced collector is always read-only; it has its own Chromium session and does not inherit login state, original engine, or completed workflow state. Scripts/GET requests can still have side effects. It visits at most 8 recorded page/viewport entries and has a 150-second overall collection limit.

## What the new layer actually contains

| Component | Implementation | Limit |
|---|---|---|
| CNN | Three randomly initialized convolution stages over 128×128 screenshots | Downsampling loses fine layout/text details; requires human visual labels |
| RNN | GRU over up to 32 response/error/timing observations, six values per event | Observed network sequence, not hidden application reasoning |
| Transformer / NLP | Two-layer encoder, learned position embeddings, fixed UTF-8 byte vocabulary | Only first 256 text bytes; no pretrained language understanding |
| Dense neural network | MLP over 16 structural/layout/runtime features | Features are correlated indicators, not business-rule proof |
| Fusion | Joint UI-score regression and defect-label classification | Experimental supervised predictions; not all-defect detection |
| Technical UI rating | Six explicit DOM checks, with small-text/target review counts | Not beauty, full WCAG, contrast compliance, or usability certification |
| Autonomous control | Run existing approved tests, collect evidence, prioritize missing checks, list only unresolved business questions | No unsupervised execution of invented business mutations |
| Client structure discovery | Visible links, script URLs and declared form constraints | Does not recover server source or infer intended rules |
| Optional source inspection | Bounded Python AST and JS/HTML sink-pattern inventory | Review candidates, not a full SAST engine or proven root cause |

PyTorch is the numerical/autograd framework, not a pretrained model. There is no downloaded tokenizer, pretrained embedding, CNN backbone, language-model checkpoint, Ollama call, or external AI API in the new layer. The original optional AI features remain available separately through the old tester. The wrapper rejects old pretrained model flags; those are not part of scratch mode.

## Train your own model

Install optional dependencies (Python 3.12 recommended for reproducible setup):

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-advanced.txt
```

For CPU-only PyTorch, install it from the official CPU index first, then install the requirements file:

```powershell
.\.venv\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cpu
```

1. Scan multiple independent applications you can test. Each advanced run produces screenshots and `dataset-unlabelled.jsonl`.
2. A human reviews each screenshot and its workflow evidence. Label visual quality using a consistent rubric and mark whether a genuine defect was confirmed. Do not copy the tool's checklist score into the label: that would train it to repeat its own assumptions.
3. Keep all screenshots/versions/viewports of one application in the same `group`. Domains alone may not be independent: staging/production/subdomains of one app need the same group. Include multiple technologies, languages, layouts and accessibility needs.
4. Combine reviewed datasets and train. No unreviewed labels are accepted.

Example label (replace `RECORD_ID` with an ID from your dataset):

```powershell
.\.venv\Scripts\python.exe advanced.py label reports\advanced_run\advanced\dataset-unlabelled.jsonl --id RECORD_ID --ui-score 75 --defect yes --reviewer Emesh --group my-application
```

A suggested human UI rubric is 0–25 each for readability, layout/coherence, interaction clarity and responsive usability. Check more than a screenshot before marking a functional defect. Keep an annotation guide and use a second reviewer on a sample to measure agreement. The UI label is subjective; it is not the original release score.

```powershell
.\.venv\Scripts\python.exe advanced.py combine data\app1\dataset.jsonl data\app2\dataset.jsonl data\app3\dataset.jsonl --output data\reviewed
.\.venv\Scripts\python.exe advanced.py train data\reviewed\dataset.jsonl --output models\my_scratch_model --epochs 30
.\.venv\Scripts\python.exe advanced.py scan "https://your-site.example/" --model models\my_scratch_model
```

The combine command accepts any number of datasets; the three paths above are syntax examples, not sufficient training support. At least **5 independent groups** are required to run an experimental split. Advisory eligibility is stricter: every train/validation/test split must have **at least 20 samples, 5 independent groups, and both defect classes**, plus held-out UI MAE ≤15 and balanced defect accuracy ≥0.70. With the 60/20/20 split, plan on at least 25 independent application groups and substantially more data for useful generalization. These thresholds are engineering safeguards, not a statistical guarantee of accuracy.

Splits are by group, not random screenshots. Identical screenshots across groups are rejected. Feature normalization uses training data only. Checkpoint selection and scalar probability-temperature fitting use validation data only. The test split is reported after model selection. Repeated experiments against the same test set invalidate its independence—retain a separate final evaluation dataset. A model card records the groups, seed, data fingerprint and metrics.

Inference abstains for missing/unqualified weights, synthetic training data, or structural features far outside training support. Predictions remain REVIEW/advisory. The empirical UI range is based on validation residuals and is not a guaranteed interval for arbitrary websites. Confidence is not correctness; new defects and domains may be missed even with extreme probabilities. The old test outcomes and release score are never overwritten by neural output.

Use only trusted locally produced model files. Loading uses `torch.load(weights_only=True)` and a size limit, but this is not a sandbox for hostile model files. The model eligibility metadata is local research metadata, not signed certification.

## Exercise the pipeline without claiming a trained website tester

```powershell
.\.venv\Scripts\python.exe advanced.py smoke-data --output data\synthetic
.\.venv\Scripts\python.exe advanced.py train data\synthetic\dataset.jsonl --output models\smoke --epochs 2
```

This makes 30 artificial screenshots and runs actual backpropagation through all four branches. It tests plumbing, not real visual reasoning. Synthetic checkpoints are explicitly barred from advisory use. No research accuracy result on these fixtures should be marketed as website-testing accuracy.

## Source / reverse-engineering boundary

For code you own or are authorized to inspect:

```powershell
.\.venv\Scripts\python.exe advanced.py scan "http://localhost:3000/" --source-dir C:\your-app\src
```

Only local source is inspected; it is not executed or uploaded. Python function/branch inventory and dynamic HTML/code sink candidates are recorded with filenames/line numbers. Browser-visible script URLs are mapped, not downloaded/decompiled. No access-control bypass, hidden backend reconstruction, firmware/binary reverse engineering, exploit generation or automatic source patching is implemented. A URL alone cannot expose private database constraints, server logic, requirements or all execution paths.

Reports, text inventories, DOM observations and screenshots can contain personal information. Keep data local and curate/redact it before training or sharing. Source inspection skips common hidden/dependency folders but cannot prove every file is nonsensitive; point it at a deliberately scoped source folder.

## Output and validation

- `report.html`: original v3.1 deterministic findings and score.
- `advanced/advanced-report.html` and `.json`: measured UI checklist, scratch model status/predictions, priorities, visible client map and source review.
- `advanced/dataset-unlabelled.jsonl`: observations awaiting human labels.
- `model.json` and `weights.pt`: locally trained parameters and evaluation metadata.

Existing report analysis without refetching: `python advanced.py analyse reports\advanced_run\report.json`. Add `--collect-ui` to explicitly revisit its public page URLs. Query-redacted URLs are not replayed. Authenticated journeys must be assessed from independently prepared data; the advanced collector does not silently load your credentials.

Test commands:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests_advanced -v
$env:QA_BROWSER_TESTS="1"
.\.venv\Scripts\python.exe -m unittest discover -s tests_advanced -v
```

See `ADVANCED_VALIDATION.md` for what was actually executed. No claim of perfect software, complete SDLC coverage, trained natural-language reasoning, or production-grade model accuracy is made.

Reference APIs: [PyTorch TransformerEncoder](https://docs.pytorch.org/docs/stable/generated/torch.nn.TransformerEncoder.html), [PyTorch GRU](https://docs.pytorch.org/docs/stable/generated/torch.nn.GRU.html), [PyTorch weight loading](https://docs.pytorch.org/docs/stable/generated/torch.load.html), [Playwright Python](https://playwright.dev/python/).
