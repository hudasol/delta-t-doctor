# Follow up log, v1.2.0 to v1.2.1

Started 2026-10-18 02:14 (UAE time). Plan and time budget first, then an append only log. Every number quoted here comes from a script in
`scripts/` and a file in `results/`; the log names both. Previous run: [OVERNIGHT_LOG.md](OVERNIGHT_LOG.md).

## Plan and time budget (about 4 hours)

| Task | What | Budget |
|---|---|---|
| F0 | Pull, lint, full local test suite, local Docker build | 30 min |
| F1 | Selective prediction: can the system tell when its own ranking is unreliable? (preregistered) | 90 min |
| F4 | Pilot dry run end to end, inspection form, Arabic review brief | 40 min |
| F2 | Reproducible simulator B pool with a recorded seed, replication of the B results | 35 min |
| F3 | Few shot on D at k = 5, 10, 70; temporal comparison in A and B (preregistered) | 45 min |
| F5 | Housekeeping from the review | 20 min |
| F6 | Review, full tests, clean install, release v1.2.1 | 25 min |

Order: F0, F1, F4, F2, F3, F5, F6. F4 is moved ahead of F2 and F3 because it needs little compute and commits value early; F3 is the first
to cut if time or memory runs short (the brief's own order of protection is F6, F1, F4).

Machine at the start: 1.5 GB of 14 GB free, CPU 41%. Rules kept from the brief: check free memory before each heavy job, one heavy job at a
time, `n_jobs=1`, never touch processes I did not start.

## Log

### F0 orientation (02:14)

* Pulled: already at b67898b (v1.2.0). Read OVERNIGHT_LOG, README, LIMITATIONS, MODEL_CARD, ASSURANCE_CASE, PILOT, WORLD_D, CHANGELOG.
* Lint passed. Full local test suite on Windows (Python 3.13, OMP_NUM_THREADS=2): every test passed except one,
  `test_ui_has_language_and_a11y_hooks`, which read the bundled UI with the platform default encoding (cp1252 on Windows) and could not decode
  the Arabic text. CI runs on Linux, so it had never shown. Fixed with an explicit UTF-8 read; the test now passes. Slowest setup: the
  calibration fixtures (114 s).
* Docker: the CLI is installed but the Docker Desktop engine is not running. Starting it would take about 2 GB of memory with about 1.3 GB
  free, so the local build is skipped and the image is verified by the CI `docker` job, as before.
* Decision: F4 documents and the pilot dry run were written while the suite ran, because they need little compute. The pilot dry run test
  (20 synthetic B buildings, one month each) passes.
