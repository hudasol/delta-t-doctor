# Changelog

Versions are git tags. All accuracy figures are simulator results unless stated.

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
