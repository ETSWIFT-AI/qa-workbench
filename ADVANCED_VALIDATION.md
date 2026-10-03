# Advanced add-on validation

## Executed

- Compared all 55 original non-cache files against `website_tester_v3.1_self_healing.zip`: no original file modified. Existing commands, original reports and optional legacy AI modules remain present.
- Original pytest suite: **32 passed, 2 skipped**. The two skipped cases require opt-in browser integration. Existing self-healing unit tests were included by pytest.
- New non-browser suite: **9 passed**, one browser test skipped in that invocation.
- New browser collector integration: **1 passed** using a loopback-only fixture. It detected horizontal overflow and a missing field label and confirmed that a scripted POST did not reach the server.
- Actual two-epoch training smoke test: random initialization, forward/backward through CNN, GRU, Transformer and MLP, nonzero gradients verified in every branch, validation checkpoint selection, parameter save/reload, and explicit abstention for synthetic/insufficiently supported models.
- Full advanced scan CLI executed on the supplied deliberately buggy local demo: original scan plus four independent advanced observations (two pages × desktop/mobile), generated screenshot-backed HTML/JSON reports and unlabelled dataset, zero advanced collection errors. Model status was NOT_TRAINED. Original exit code 1 for known demo failures was preserved.
- Generated report opened in Chromium and desktop screenshot visually inspected.
- New Python modules compiled successfully.

## Environment

Python 3.12, CPU PyTorch 2.14.0, NumPy 2.5.3, Pillow 12.3.0, Playwright 1.51.0 and its Chromium headless shell. The latest Playwright browser download failed in this environment; validation used the successfully installed 1.51.0 version allowed by the existing dependency range.

## Not established

- No complete multimodal human-labelled multi-site training corpus was supplied. The later bundled screenshot-only Calista subset is evaluated separately in UI_TRAINING_README.md. There is **no validated trained model**, no real-world accuracy estimate, and no demonstration of cross-site reasoning/generalization. Synthetic training success proves execution only.
- The eligibility-approved prediction path is implemented but has not been evaluated with a genuinely qualified real-data checkpoint. No production inference certification is claimed.
- GUI windows and batch files were not executed on Windows; GUI syntax compiled. No display server was available for native GUI visual verification.
- Firefox, WebKit, native mobile devices, remote grids, and cloud-scale execution were not tested for this add-on. The advanced collector specifically uses Chromium even if the original scan requested other engines.
- Real-site logins, anti-bot systems, stateful transactions, private backend logic, aesthetic judgement, reverse engineering of binaries, and full SDLC coverage remain outside the validated scope.
- The technical UI score is six measured DOM checks only. A page can get 100 on this checklist and still have poor design, inaccessible content, or serious application defects.
- Original v3.1 behaviour/limitations, including its locator recovery implementation and scoring policy, are inherited unchanged.

The packaged `advanced-sample` is evidence from the deliberately buggy loopback demo. It is not a rating of badssl.com or any external website. No model weights or synthetic accuracy claims are bundled.
