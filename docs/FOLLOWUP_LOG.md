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

### F1 selective prediction (02:25 to 02:38)

* Preregistered (dca7f70, two implementation details fixed before the run in 745ac0d), run in about 10 minutes (`scripts/selective_prediction.py`,
  `results/selective_prediction.json`). 2 of 10 predictions held (Q1, Q3); Q2 and Q4 to Q10 failed.
* Answer: inside a familiar simulator the model's own decision margin finds wrong rankings well (AUROC 0.905 in A, 0.733 in B); on world D no
  label free signal exceeds 0.61, the model's entropy is below chance (0.457, confidently wrong), and the A and B fitted combination gives 0.513.
  The guard is below chance as an error signal in world (0.40, 0.44) and weak on D (0.583).
* Shipping rule failed on (a) and (b), so `--abstain-on uncertainty` was not added. Decision recorded: the decision margin looks best on D
  (0.608), but it was not the preregistered signal and D was used to see that, so shipping it now would be tuning on D. It is listed as a
  candidate to preregister against a future world.
* README, LIMITATIONS (new item 18), MODEL_CARD, ASSURANCE_CASE (C7, new C7b) and EDGE_PROPOSAL updated in the same commit (edfc9bb).

### F4 pilot dry run and documents (02:20 to 02:30)

* `scripts/pilot_dry_run.py` (synthetic fleet, manifest, evaluate_real, calibrate on one half, rescore the other half with both models, one
  page summary) with a reduced test that passes; `evaluate_real.py` gained an optional `--model` flag. `docs/INSPECTION_FORM.md` and
  `docs/ARABIC_REVIEW_BRIEF.md` written. The full size dry run is queued after F2 (one heavy job at a time).

### F5 housekeeping, done early (02:30 to 02:35)

* The Arabic review sheet was stale (178 strings; three notes added in v1.2.0 were missing) and its generator failed on Windows with the same
  code page bug as the test above. Fixed and regenerated: 181 strings, glossary check clean (32d1c27).
* Unneeded hyphens removed from older published docs (269 occurrences of a fixed list of compounds, 1c2f2e9); the README table generator uses
  the same wording. The note that Docker builds fail on commits 69d7706 to 218e0f3 is already in OVERNIGHT_LOG.md (T5), so it was not repeated.
