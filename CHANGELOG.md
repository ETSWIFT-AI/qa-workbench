# 3.1.0

- Added self-healing locators for journeys/fields: when a configured selector stops matching, cached element attributes (data-testid, id, ARIA role + accessible name, form `name`, placeholder, visible text) are tried in priority order as fallback identification strategies.
- Confidence-scored healing: only matches at/above 0.85 confidence are applied automatically (logged PASS under the new `self_healing` family); matches between 0.60-0.85 are flagged REVIEW rather than silently substituted; below 0.60 is logged FAIL. This keeps healing from masking real regressions.
- Element profiles are cached to `locator-cache.json` in each run's output directory so healing has something to recover from even on a selector's first-ever failure in a later run.
- `self_healing` results are scored (low weight, under `lifecycle`) and reported separately from `journeys`/`boundary_rules` — a healed selector proves the test kept running, not that the workflow itself is correct.

# 3.0.0

- Replaced worst-case family scoring with completed-check weighted quality and independent coverage.
- Unknown and unexecuted evidence no longer masquerades as defective software; no completed tests returns null quality.
- Kept high/critical failure and execution-error gate blockers independent of averages.
- Executed configured journeys/fields for every requested engine/viewport; explicit unavailable-cell errors.
- Added native structural checks and opt-in HTML-derived boundary execution without manual JSON.
- Added desktop GUI, navigation/age/API recipe builder, CLI wizard and location-independent Windows setup/launchers.
- Added bounded multi-step state exploration with hash-route support and replay target checks.
- Added SQLite snapshots, compatible-profile trend comparisons and stable finding fingerprints.
- Added CSP/HSTS/framing analysis and optional managed Docker ZAP baseline execution.
- Added optional CrUX field-data query/import alongside retained lab samples.
- Added regression fixtures and tests; updated report wording, partial-assessment labels, counts and gate reasons.

This changes the meaning of the numeric score. Do not compare a v2 score directly with v3 tested quality.
