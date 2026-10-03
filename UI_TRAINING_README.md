# Real dataset included — laptop UI training

## Easiest Windows use

Extract the ZIP fully. Open the `website_tester` folder.

1. Double-click **`setup_ui_and_train.bat`**. It creates `.venv` if needed, installs CPU PyTorch and training dependencies, trains the bundled dataset, then installs the original browser dependencies/Chromium. Python must already be installed. It tries Python 3.12 first, then your default Python. Internet is needed for dependency/browser installation, but **the training data is already inside the ZIP**.
2. When it finishes, double-click **`scan_with_ui.bat`** and paste your website URL. The console prints the report paths. Scans use read-only mode by default.

The training subscript pauses after training; press a key to let browser setup continue. Existing original setup/GUI commands continue to work.

If you already have dependencies, the complete training command is:

```powershell
.\.venv\Scripts\python.exe train_ui.py
```

To scan directly:

```powershell
.\.venv\Scripts\python.exe advanced.py scan "https://badssl.com/" --ui-model models\calista_ui --output reports\ui_scan
Start-Process .\reports\ui_scan\advanced\advanced-report.html
```

The screenshot CNN appears separately from the older multimodal network. Seeing `NOT_TRAINED` for that multimodal network does not mean the screenshot CNN failed. Look for **Screenshot CNN** and **Screenshot aesthetic model** in the report.

## Included real data

`data/calista_ui/` contains all **100** images from Calista's **comparison-based** subset, published aesthetic scores, original site mapping, the upstream MIT notice and provenance. Source commit: `b45fb864e819425f5dbf43023c7c2000484b8822` from https://github.com/calista-ai/website-aesthetics-datasets.

The labels were derived by the dataset authors from human pairwise preferences using a Bradley–Terry model. They are not functional defect labels. Original scores from 1–10 are linearly mapped to 0–100 using `(score - 1) / 9 * 100`. Screenshots were converted into aspect-preserving JPEGs with longest dimension at most 512 pixels; original and bundled image hashes are recorded. The bundled data is about 3.2 MB. Full original high-resolution images and the separate rating-based dataset are not included.

Attribution: Alexandros Delitzas, Kyriakos C. Chatzidimitriou, Andreas L. Symeonidis, *Calista: A deep learning-based system for understanding and evaluating website aesthetics*, International Journal of Human-Computer Studies 175 (2023), DOI 10.1016/j.ijhcs.2023.103019. Original webpages may contain third-party copyrighted material and trademarks; the repository notice does not imply ownership of those assets.

No manual labels are required for this screenshot-only task. No missing text/events or defect labels are fabricated to satisfy the original multimodal trainer. Use `train_ui.py`, **not** `advanced.py train`, for this bundled dataset.

## Laptop defaults

For your 16 GB RAM laptop with about 184 GB free disk space:

- CPU execution; no graphics card required.
- 128×128 letterboxed network input, batch size 8, two CPU threads.
- Maximum 40 epochs; early stopping after ten epochs without validation improvement.
- Small CNN initialized randomly. No pretrained model or embeddings.
- Dataset tensors occupy about 20 MB; Python/PyTorch add memory overhead. Leave several GB free for dependencies/browser installation and other running applications. Exact installation size and training speed depend on your Python/CPU/platform.

Use fewer epochs for a quick execution check:

```powershell
.\.venv\Scripts\python.exe train_ui.py --epochs 5
```

To retrain into a separate folder rather than replace your default model:

```powershell
.\.venv\Scripts\python.exe train_ui.py --output models\ui_experiment2
```

## What the result means

Training keeps website groups separate: 70 training, 15 validation and 15 test websites in the bundled split. Validation selects the checkpoint; the held-out test split is used for reporting. `models/calista_ui/ui-model.json` records splits, seed, loss history and mean absolute error. Compare against the included constant training-mean baseline. Do not repeatedly tune against this small test split and then describe it as an independent final evaluation.

If the model does not beat that baseline on the test split, scan-time prediction returns **ABSTAIN**. Otherwise estimates are still **experimental review items** with a validation-derived error range. That range is not a guaranteed confidence interval on new websites. Historical aesthetic preferences are subjective and may not transfer to modern designs, languages or mobile layouts. The global published ranking labels predate our train/test split and include pairwise relationships across its groups; this is an exploratory regression benchmark, not a clean independent judgement study.

This trains **visual aesthetics only**. It does not train the GRU, transformer, functional defect detector, security scanner, or backend reasoning. Those require their own appropriate labelled data. The original deterministic tester continues to provide functional and other checks; neural predictions do not change its results or release score.

## Validation performed while packaging

The full default CPU training run completed. On this environment/seed, held-out test MAE was 11.36/100 versus 12.36/100 for the constant-score baseline, on only 15 test websites. These figures are limited experimental measurements, not expected accuracy on your sites. No weights are bundled: your machine trains from random initialization. See `data/calista_ui/validation-example.json` for the model card from our validation run (metadata only).

Additional verification: dataset checksums and score conversion passed; the abstention guard was tested; real saved UI weights were loaded and produced advisory predictions for the packaged demo observations. New suite: 11 passed, 1 browser test skipped in this run. Windows batch scripts were inspected but not executed on Windows.
