# Changelog

Versions are git tags. All accuracy figures are simulator results unless stated.

## Unreleased: engineering round 1 (Google ML review)
Measured before and after are in . Changes:
* Evaluation: building-level bootstrap 95% intervals and paired differences; season hold-out now also holds out the test buildings (macro AUROC 0.941 summer, 0.960 winter); feature-group ablation (); calibration folds are grouped by building. README table is generated from  by . The previous README stress range (0.947 to 0.982) was from an older dataset; the current one is 0.902 to 0.978.
* Input handling: NaN rows are dropped and reported, swapped supply/return, implausible temperatures and ΔT above 25 C are rejected, day-first dates and latin-1 files parse correctly, windows need 80% coverage, informed mode validates the design ΔT range, data-quality  flag and seasonal-annualisation note.
* Service:  demo route was shadowed by the  route (fixed, tested); uploads parsed in worker threads with a concurrency limit and streaming size cap; NaN/inf parameters rejected (422).
* Reproducibility: bundled model hash checked against the model card; model card records git commit, data hash and sklearn version; lock file; one specific-heat constant; ruff and coverage in CI.
* Docs: corrected the claim that the two valve faults overlap (measured confusion is 2 to 5%; overflow is the hard cause).

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
