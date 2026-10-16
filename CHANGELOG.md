# Changelog

All accuracy figures are simulator results unless stated. Tags exist from v1.1.1 onward; earlier versions were not tagged.

## v1.2.0

New evidence and new product capability. All accuracy figures are simulation results; the only real data used have no labels. The bundled
models are unchanged (not retrained). Predictions were committed before every experiment; failures are listed.

- **World D, a third physics** (`src/deltat_doctor/sim/world_d.py`, `docs/WORLD_D.md`): time stepped, closed loop (zone thermal mass,
  discharge air PI cascade with actuator lag and deadband, pump curve with a DP set point, plate exchanger ETS). Zero shot macro AUROC 0.705,
  98% healthy false alarm; guards withhold 92% of D buildings. Few shot: 20 D buildings give 0.825 and 40 give 0.850, healthy false alarms 99% to 21%; overflow stays near 0.61. 13 predictions: 9 held, 3 failed (D6, D7, D10), 1 not run (D11).
- **Correction: the guard is a novelty detector, not an error detector.** On world D the windows it lets through score 0.618, lower than the
  0.756 of those it flags (prediction D7 failed). It also flags 14% of new simulator B buildings (D6 failed). README, LIMITATIONS, MODEL_CARD
  and the proposals now say so.
- **Temporal features (negative result):** six hourly flow features do not help overflow in an unseen world and reduce other causes, so they
  fail the preregistered shipping rule and are not used by the product (`src/deltat_doctor/temporal.py` stays as an unused module).
- **Fleet calibration** (`deltat-doctor calibrate`, `diagnose --model`): refuses below 10 inspected buildings, marks 10 to 19 as weak in the
  card and every report, keeps a holdout report, verifies the calibrated file's sha256, never replaces the default model. Simulation check on
  a world D fleet: held out macro AUROC 0.782 to 0.833, overflow worse (`results/calibrate_check.json`).
- **Real data contact** (`docs/REAL_DATA_CONTACT.md`): 40 Danish smart heat meters and 5 Nis substations (CC BY 4.0) all refused at parsing
  with a plain message; no crash. Fixed a silent issue: UTC timestamps shifted the hour of day features without warning; a note now says so.
- **Why fouling transfers badly** (`docs/TRANSFER_V2.md` addendum): B's fouling signature is weak (in world 0.675); H1 and H4 held, H2 and H3
  failed.
- **Assurance:** generated `requirements.lock` with every published hash (replaces the hand written 12 line lock, which left transitive
  dependencies open); two stage Docker build whose install step runs with networking disabled; CycloneDX SBOM; `scripts/reproduce.py`;
  CI actions pinned to SHAs; read only smoke test with an upload; a test that runs a diagnosis with network sockets disabled; threat model
  in `docs/SECURITY.md` (intended standards mapping, not certified); `docs/ASSURANCE_CASE.md`; `docs/EDGE_PROPOSAL.md`.
- **CI was red from Round 4 through v1.1.1.** The Python 3.10 job could only install scikit-learn 1.7, so the bundled model refused to load,
  and fail fast cancelled the 3.12 job. Fixed: Python 3.11 or newer, scikit-learn pinned to 1.9.x, fail fast off. Earlier docs said CI was green.
- **Reproducibility:** the simulator A pool regenerates to the same numbers (stored training percentiles match to 4e-15) but not the same
  file hash; the seed of the committed simulator B pool was never recorded, so it cannot be regenerated. Commit 69d7706 removed the old lock
  file before the Docker change landed, so the Docker build fails on 69d7706 to 218e0f3.
- **Corrections from an adversarial review:** the external check is 3 of 5 predictions failed and 1 not supported (README said one failed);
  LBNL is simulated plant data; the README results table described 6500 samples across 650 buildings but shows simulator A only; valve
  confusion is 3% and 4% (was 2% and 5%); 40 target buildings give 0.836, not 0.84, and F1 failed; F5 was not tested as stated; guard false
  flags under 2 hourly data (42% of windows) and noise are now reported; round names no longer carry organisation names (they were review
  personas, not reviews by those organisations); three tests that could pass vacuously are fixed.
- The v1.1.1 transfer entry below counts the few shot predictions only (2 of 5 failed); the transfer fixes had 3 of 8 failed (V1, V2, V5).

## v1.1.1

Round 7: turning the six open limitations into measured results. Predictions were written before each experiment; failures are recorded.

- **Chunked uploads capped in the app.** `BodyLimit` ASGI middleware counts bytes as they arrive and answers 413 past 26 MB even without Content-Length (`tests/test_upload_cap.py`). A proxy limit is still advised (`docs/DEPLOYMENT.md`).
- **Cross-simulator transfer.** New domain-randomised worlds (`sim/worlds.py`, `--sim CA|CB`) and four fixes compared (`scripts/transfer_v2.py`, `docs/TRANSFER_V2.md`): none closes the gap (best 0.715 / 0.784). Few-shot adaptation curve (`scripts/transfer_fewshot.py`): about 20 surveyed buildings lift the weak direction to 0.80, 40 to 0.84; healthy false alarms 82% to 24%. Two of five predictions failed.
- **Open-set guard.** Six detectors compared in both directions (`scripts/openset_v2.py`); shipped guard is now Mahalanobis plus nearest-neighbour (windows flagged: A to B 64%, B to A 29%, was 71% and 25%; in-world 5.5% to 6%). Asymmetry is partly structural and is documented, not removed. Models retrained.
- **Overflow.** `docs/OVERFLOW.md`: found at about 0.91 AUROC within one physics, chance across physics. The earlier "barely shows up" wording is corrected; the "possible" cap stays. Two of five predictions failed. DP ceiling test is circular and labelled so.
- **Arabic.** Terminology normalised to UAE operator usage; `docs/i18n_glossary.csv` and `docs/i18n_review_sheet.csv` (178 strings) prepared for the native-speaker review, which has not happened.
- **Real data.** `scripts/evaluate_real.py` scores the tool against site-inspection labels (agreement, AUROC, calibration, false alarms, confidently-wrong count, bootstrap intervals, refuses under 10 buildings). `docs/PILOT.md` now has a data-request pack and the dataset search record. No real-data accuracy is claimed.

## v1.1.0

Rounds 1 to 6 of the multi-viewpoint upgrade (review personas written by the author; no organisation reviewed or endorsed this work). Figures quoted in the older entries below were
measured at the time and some are superseded by `results/metrics.json`.

### Round 6 (final review)

- Report no longer prints a ranking when the result is flagged unreliable; abstained results say so.
- Heavy routes (including demos and CSV exports) share the concurrency limit; POST bodies over 25 MB (+1 MB) are rejected from Content-Length. Chunked uploads without Content-Length are still bounded only by the read cap, so put a body limit on the reverse proxy.
- Docs corrected: the conformal margin is 0.0 (intervals are raw quantiles; coverage 55% to 76% when a cause is truly present), both guards run, API schema updated.
- Confidence label renamed "model probability band (simulated)". Per-window series and trend now shown in the UI and the report.

### Round 5 (abstention and evidence)

- Open-set guard (Mahalanobis, `openset.py`) replaces the per-feature box as the abstention rule; ranking is withheld (`abstained`, empty `findings`) when it trips. Benchmark: `scripts/openset_eval.py`, `results/openset.json`.
- Evidence against healthy buildings per finding (`evidence.py`), data-driven from simulated single-cause windows; tiers (likely / possible / weak / unsupported); weak-signature causes capped at "possible"; worst-world AUROC stored in the model card.
- Per-window `series` and a Kendall / Theil-Sen `trend` on high-load delta-T.
- Savings capped at the annual surcharge (per finding and in the portfolio total); ties broken by delta-T gain.
- Models retrained (guard, healthy reference, evidence spec). Tests: tests/test_round5_openset_evidence.py.

### Round 4 (Arabic, provenance and UI)

- Arabic and English UI and report (RTL, bundled IBM Plex Sans Arabic); `lang` parameter on report endpoints, `--lang` on the CLI. See docs/I18N.md (machine-drafted, needs native review).
- Provenance block on every result: report ID, input SHA-256, model identity, parameters, quality flags.
- Web UI rebuilt: executive summary with delta-T gauge, saving range and confidence word, reliability banner, dark mode, skip link, chart data table, collapsed negligible causes, portfolio heat-map and ranges.
- Owner report rewritten (summary first, ranges, provenance, `@page` print).
- Demo portfolio frame cached (about 8 s to 1.5 s).
- Tests: tests/test_round4_i18n_report.py.

## Engineering round 1 (evaluation rigour; shipped in v1.1.0)
Measured before and after are in `results/metrics.md`. Changes:
* Evaluation: building-level bootstrap 95% intervals and paired differences; season hold-out now also holds out the test buildings (macro AUROC 0.941 summer, 0.960 winter); feature-group ablation (`results/ablation.json`); calibration folds are grouped by building. README table is generated from `results/metrics.json` by `scripts/update_readme.py`. The previous README stress range (0.947 to 0.982) was from an older dataset; the current one is 0.902 to 0.978.
* Input handling: NaN rows are dropped and reported, swapped supply/return, implausible temperatures and ΔT above 25 C are rejected, day-first dates and latin-1 files parse correctly, windows need 80% coverage, informed mode validates the design ΔT range, data-quality `reliable` flag and seasonal-annualisation note.
* Service: the `.csv` demo route was shadowed by the `{name}` route (fixed, tested); uploads parsed in worker threads with a concurrency limit and a 25 MB read cap (v1.1 adds a Content-Length check); NaN/inf parameters rejected (422).
* Reproducibility: bundled model hash checked against the model card; model card records git commit, data hash and sklearn version; lock file; one specific-heat constant; ruff and coverage in CI.
* Docs: corrected the claim that the two valve faults overlap (measured confusion is 2 to 5%; overflow is the hard cause).

## Engineering round 3 (second simulator and uncertainty; shipped in v1.1.0)
* **Second simulator** (`sim/hydraulic.py`) with different hydraulics, psychrometrics, ETS and sensor effects, and a cross-simulator experiment with predictions written first ([docs/CROSS_SIMULATOR.md](docs/CROSS_SIMULATOR.md)). Result: A to B macro AUROC 0.683, B to A 0.770, 88% of B's healthy windows falsely flagged by the A-trained model; 7 of 8 predictions held, one failed. The shipped model is now trained on both simulators.
* **Healthy baseline realism:** simulator A's healthy part-load ceiling may sit below design (it was always above). Effect on A: macro AUROC 0.967 to 0.966; informed-mode gain over blind +0.012 to +0.005; healthy false alarms at design 5-7 C 8% to 13%.
* **Uncertainty:** quantile gain models and conformal margins; findings carry 10-90 ranges for delta-T gain and AED saving; the mean saving no longer applies the tariff hinge after averaging; the report notes when the top two fixes' ranges overlap. Coverage of the true gain on held-out buildings: 82% to 85% where it matters.
* **Evaluation:** 4-seed replication, identifiability (nearest-neighbour) analysis, guard fire rates, `scripts/cross_simulator.py`, `scripts/uncertainty_eval.py`, `scripts/identifiability.py`.
* Ingestion: supply/return are called swapped only if the median delta-T is below -0.75 C (sensor offsets alone could trip the old threshold on very low delta-T plants).
* Docs corrected: stale design range, overflow AUROC, false-alarm figures, and the LBNL result re-checked with the new model (still fails; the guard still flags it).

## Engineering round 2 (robustness and deployment; shipped in v1.1.0)
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
