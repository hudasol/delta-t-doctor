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

### Independent review of this run (02:50 to 03:10)

* A separate review pass, given only the repository and the constraints, returned 25 findings on the changes since v1.2.0. Acted on:
  * **AURC broke ties by file order** (high). Isotonic probabilities and the capped guard score tie often, so the first run's AURC and risk at
    50% coverage depended on row order; AUROC did not. Fixed with a tie aware AURC and a test (a5922d1); F1 is rerun after F2, and the results
    section will report the corrected figures.
  * The retraining rule in REPRODUCIBILITY.md used an undefined "outlier"; defined before any replicate pool was scored (d2a844a).
  * Overstated calibration claim, inconsistent guard wording, the C7b claim, LIMITATIONS numbering, links, the inspection form row, help text,
    remaining hyphens and PowerShell environment variable syntax (9e79b7c).
  * Pilot dry run outputs not all labelled synthetic (the evaluator writes `real_eval.json`), and a test that would pass if `--model` were
    ignored: fixed in the script and test, committed after the test reruns.
  * Still to do in the F1 rerun write up: S5's window overlap between settings (a stricter leave target world out variant is added as a
    sensitivity check), the preregistered Brier loss, an interval for the margin, Q6 rounding, the proxy nature of the window decision, the
    timeline of the preregistration.

### F2 reproducible B data (02:38 to 03:53)

* Preregistered (56c3d6a; "outlier" defined at 02:58 before any pool was scored, d2a844a). Three pools with recorded seeds (2101 to 2103), each
  16 to 19 minutes with `n_jobs=1`, plus the seed 11 pool from v1.2.0. The same code reproduces the committed pool's figures exactly.
* 4 of 5 held; R1 failed (in world B 0.908 on seed 2101). **Correction:** B to A is 0.741 to 0.757 on regenerated pools, below the committed
  0.770; README, MODEL_CARD, LIMITATIONS, PROPOSAL and EDGE_PROPOSAL now add "0.67 to 0.76 on regenerated data". Not an outlier by the rule,
  so the bundled model is not retrained.

### F1 rerun (03:54 to 04:04)

* Tie aware AURC moved nothing by more than 0.001. Results section rewritten with the review's points (1f55404). Verdicts unchanged, 2 of 10.

### F3 cut experiments (04:05 to 04:20)

* Few shot on D at k = 5, 10, 70: 0.762, 0.798, 0.869; E1 to E4 held. Temporal in world A and B: overflow +0.002 and +0.004, D11 held; E5
  failed narrowly in B (fouling +0.013, passing valves -0.010). The leave one world out figures reproduced exactly.

### Second review pass (04:25 to 04:35) and full local suite

* Full local suite: **124 passed** in 8 min 29 s (Windows, Python 3.13). Lint clean.
* A second independent review of the F2 and F3 write ups confirmed every number and every verdict, and found wording that went too far.
  Corrected in the documents (this log is append only, so two earlier entries above stay as written and are corrected here):
  * "the same code reproduces the committed pool's figures exactly" is wrong: A to B is 0.684 against 0.683 published; **to within 0.001**.
  * "temporal features do not help overflow in all three worlds" overstated it: with A held out the gain is +0.020, exactly the preregistered
    threshold; the block was rejected because other causes fell. All documents now say this.
  * C15b is "partly supported": B to A is lower on all four regenerated pools, a systematic shift. The seed 11 pool has no `generator.json`.
  * The regenerated range is quoted with one phrase everywhere ("0.67 to 0.76 on four regenerated B pools"), including LIMITATIONS item 2,
    CROSS_SIMULATOR and WORLD_D, which had been missed. The default regenerable B pool is chosen by a stated rule (closest to the replicate
    means: seed 2102), not the pool that failed R1.
  * The dry run summary now states that B is a training world of the bundled model, prints the real `interpretable` flag, and writes valid
    JSON without absolute paths.
