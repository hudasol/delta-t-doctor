# Changelog

Versions are git tags. All accuracy figures are simulator results unless stated.

## v1.1.0

Rounds 1 to 6 of the multi-reviewer upgrade (Google, Edge, TII, ADEO, ATRC, final Google check). Figures quoted in the older entries below were
measured at the time and some are superseded by `results/metrics.json`.

### Round 6 (final review)

- Report no longer prints a ranking when the result is flagged unreliable; abstained results say so.
- Heavy routes (including demos and CSV exports) share the concurrency limit; POST bodies over 25 MB (+1 MB) are rejected from Content-Length. Chunked uploads without Content-Length are still bounded only by the read cap, so put a body limit on the reverse proxy.
- Docs corrected: the conformal margin is 0.0 (intervals are raw quantiles; coverage 55% to 76% when a cause is truly present), both guards run, API schema updated.
- Confidence label renamed "model probability band (simulated)". Per-window series and trend now shown in the UI and the report.

### Round 5 (ATRC review)

- Open-set guard (Mahalanobis, `openset.py`) replaces the per-feature box as the abstention rule; ranking is withheld (`abstained`, empty `findings`) when it trips. Benchmark: `scripts/openset_eval.py`, `results/openset.json`.
- Evidence against healthy buildings per finding (`evidence.py`), data-driven from simulated single-cause windows; tiers (likely / possible / weak / unsupported); weak-signature causes capped at "possible"; worst-world AUROC stored in the model card.
- Per-window `series` and a Kendall / Theil-Sen `trend` on high-load delta-T.
- Savings capped at the annual surcharge (per finding and in the portfolio total); ties broken by delta-T gain.
- Models retrained (guard, healthy reference, evidence spec). Tests: tests/test_round5_openset_evidence.py.

### Round 4 (ADEO review)

- Arabic and English UI and report (RTL, bundled IBM Plex Sans Arabic); `lang` parameter on report endpoints, `--lang` on the CLI. See docs/I18N.md (machine-drafted, needs native review).
- Provenance block on every result: report ID, input SHA-256, model identity, parameters, quality flags.
- Web UI rebuilt: executive summary with delta-T gauge, saving range and confidence word, reliability banner, dark mode, skip link, chart data table, collapsed negligible causes, portfolio heat-map and ranges.
- Owner report rewritten (summary first, ranges, provenance, `@page` print).
- Demo portfolio frame cached (about 8 s to 1.5 s).
- Tests: tests/test_round4_i18n_report.py.

## Unreleased: engineering round 1 (Google ML review)
Measured before and after are in `results/metrics.md`. Changes:
* Evaluation: building-level bootstrap 95% intervals and paired differences; season hold-out now also holds out the test buildings (macro AUROC 0.941 summer, 0.960 winter); feature-group ablation (`results/ablation.json`); calibration folds are grouped by building. README table is generated from `results/metrics.json` by `scripts/update_readme.py`. The previous README stress range (0.947 to 0.982) was from an older dataset; the current one is 0.902 to 0.978.
* Input handling: NaN rows are dropped and reported, swapped supply/return, implausible temperatures and ΔT above 25 C are rejected, day-first dates and latin-1 files parse correctly, windows need 80% coverage, informed mode validates the design ΔT range, data-quality `reliable` flag and seasonal-annualisation note.
* Service: the `.csv` demo route was shadowed by the `{name}` route (fixed, tested); uploads parsed in worker threads with a concurrency limit and a 25 MB read cap (v1.1 adds a Content-Length check); NaN/inf parameters rejected (422).
* Reproducibility: bundled model hash checked against the model card; model card records git commit, data hash and sklearn version; lock file; one specific-heat constant; ruff and coverage in CI.
* Docs: corrected the claim that the two valve faults overlap (measured confusion is 2 to 5%; overflow is the hard cause).

## Unreleased: engineering round 3 (TII review)
* **Second simulator** (`sim/hydraulic.py`) with different hydraulics, psychrometrics, ETS and sensor effects, and a cross-simulator experiment with predictions written first ([docs/CROSS_SIMULATOR.md](docs/CROSS_SIMULATOR.md)). Result: A to B macro AUROC 0.683, B to A 0.770, 88% of B's healthy windows falsely flagged by the A-trained model; 7 of 8 predictions held, one failed. The shipped model is now trained on both simulators.
* **Healthy baseline realism:** simulator A's healthy part-load ceiling may sit below design (it was always above). Effect on A: macro AUROC 0.967 to 0.966; informed-mode gain over blind +0.012 to +0.005; healthy false alarms at design 5-7 C 8% to 13%.
* **Uncertainty:** quantile gain models and conformal margins; findings carry 10-90 ranges for delta-T gain and AED saving; the mean saving no longer applies the tariff hinge after averaging; the report notes when the top two fixes' ranges overlap. Coverage of the true gain on held-out buildings: 82% to 85% where it matters.
* **Evaluation:** 4-seed replication, identifiability (nearest-neighbour) analysis, guard fire rates, `scripts/cross_simulator.py`, `scripts/uncertainty_eval.py`, `scripts/identifiability.py`.
* Ingestion: supply/return are called swapped only if the median delta-T is below -0.75 C (sensor offsets alone could trip the old threshold on very low delta-T plants).
* Docs corrected: stale design range, overflow AUROC, false-alarm figures, and the LBNL result re-checked with the new model (still fails; the guard still flags it).

## Unreleased: engineering round 2 (Edge review)
* Quality gate: flow spikes (above 6x the running 90th percentile), sensor codes, impossible temperatures and delta-T above 30 C, text and formulas in numeric cells, unreadable timestamps and frozen meters are removed or flagged and counted; `reliable` goes false above 2% (48 repeated flow readings for a frozen meter). Verified: a file with 1% of flow readings at 1e9 changed the annual surcharge estimate from 2.1e10 to within 0.1% of the clean value.
* Model loading fails closed: bundled models must match their recorded sha256 and sklearn minor version; the hashed bytes are the unpickled bytes.
* Parsing bounds: row, column and unzipped-size caps, zip magic and zip-bomb check, `.xls` refused, C CSV parser with a sniffed delimiter. The CLI portfolio command uses the same reader.
* Portfolio: null building ids are grouped and reported; inconsistent design delta-T within a building is reported; CSV output neutralises formulas.
* Operations: JSON audit lines and `X-Request-ID`; Docker image installs from the lock file, no home directory, read-only run documented; benchmark script and measured budget.
* Not done, listed in docs/SECURITY.md: CSP nonce, SHA-pinned Actions, SBOM and image scan, authentication.

## v1.0.0
Examples, one-page proposal, docs checked against a green CI run. 1.0 means the product surface is complete and documented. It does not mean validated on field data; that is what the pilot is for.

## v0.5.0
Real-world file import (any delimiter, degF, L/s, RT, MW, cumulative kWh, .xlsx, dd/mm dates), data-quality notes, security headers, bundled fonts (no external requests), API, security, deployment and model-card docs. Docker image and CI smoke test (built and smoke-tested in GitHub Actions).

## v0.4.0 (v0.2.0 to v0.4.0 landed in one commit)
Printable owner report (HTML, Print to PDF), `/api/report`, `--html` in the CLI.

## v0.3.0
Portfolio mode: one file with many buildings, ranked by saving. `/api/portfolio`, `deltat-doctor portfolio`.

## v0.2.0
Design-delta-T aware diagnosis. Training range widened from 9-13 C to 5-12 C design delta-T. Optional informed model
that takes the design delta-T. Out-of-range guard (reports "not reliable" for buildings unlike the training data). Follow-up check on the LBNL benchmark: predictions P4 and P5 were written first and both failed, see docs/EXTERNAL_CHECK.md section 6.

## v0.1.0
Prototype: simulator, four-cause classifier, penalty calculator, web app, CLI, tests, pre-registered external check
(P1 failed).
