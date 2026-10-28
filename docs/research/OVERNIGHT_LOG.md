# Overnight log, v1.1.1 to v1.2.0

Started 2026-10-16 05:10 (UAE time). This file is the plan, then an append only log. Every number quoted here comes from a
script in `scripts/` and a file in `results/`; the log names both.

## Plan and time budget

| Task | What | Budget |
|---|---|---|
| T0 | Orientation, baseline lint and tests, tag v1.1.1 | 20 min |
| T1 | Real data contact without labels: search, loaders, guard behaviour | 45 min |
| T2 | World D (third, independent physics), zero shot, guard, few shot, temporal features | 90 min |
| T3 | `deltat-doctor calibrate` fleet calibration mode | 45 min |
| T4 | Why fouling transfers badly (preregistered hypotheses) | 30 min |
| T5 | Assurance and deployability (lock, Docker, reproduce, SBOM, CI, threat model) | 40 min |
| T6 | Edge proposal and assurance case | 25 min |
| T7 | Adversarial self review, regression, release v1.2.0 | 40 min |

If time runs short: T7 first, then T6 cut to the assurance case table, then T5 cut to the lock file and CI.

## Environment

* Windows 11, Python 3.13 in a local virtual environment, 16 logical cores (previous sessions had 2).
* Working copy: a fresh clone of `hudasol/delta-t-doctor` at 409fc66. The zip extract in the parent folder
  (`delta-t-doctor-main`) is an older snapshot (version 1.1.0, no TRANSFER_V2.md) and was not used.

## Log

### T0 orientation (05:10)

* Read README, LIMITATIONS, MODEL_CARD, TRANSFER_V2, OVERFLOW, PILOT, EXTERNAL_CHECK, SECURITY, CHANGELOG, `scripts/evaluate_real.py`,
  `src/deltat_doctor/diagnose.py`, both simulators and the model code.
* Annotated tag `v1.1.1` created on 409fc66 and pushed. Before this push the remote had no tags at all, although CHANGELOG.md says
  "Versions are git tags". Older versions are not tagged; I did not create tags for them because I cannot verify which commit each
  version corresponds to.
* Known issue, recorded and not rewritten: the v1.1.1 commit (409fc66) lists a different author and carries a co author trailer and
  a session link in its message. History is not rewritten. No later commit carries such lines; commits from here on are authored by
  Huda Mueen as configured in git.
* `results/data/` (the simulator A training pool) is not in the repository (gitignored). It must be regenerated with
  `python scripts/generate_data.py`; its sha256 is recorded in the model card, which gives a free reproducibility check.
* Baseline: `ruff check src tests scripts` passed at 409fc66. The baseline test run did not finish (see machine conditions below); the
  full suite is run again before the release instead.

### Machine conditions (recorded because they shaped every later decision)

* The machine is shared with several other projects' jobs (other test suites, an install that kept one core busy for hours, a local
  model server, browsers). CPU was at 100% from about 05:40, and from about 06:40 free memory fell to a few hundred MB with heavy paging
  (about 9000 pages per second measured at 09:55). Between 06:36 and 09:44 my session itself stalled and background jobs made almost no
  progress: world D generation (1500 windows) took 12,980 s and the A pool regeneration 12,845 s, against minutes on an idle machine.
* Decision (two options written down): (a) stop other projects' processes to get CPU back, or (b) leave them alone, lower the priority of
  my own less urgent jobs and cut scope. I chose (b): those processes are not mine to stop.

### T1 real data contact (05:30 to 06:40, analysis finished later)

* Two openly licensed real datasets were opened, licences read and checksums verified (`docs/research/REAL_DATA_SEARCH.md`): Danish smart heat
  meters (Zenodo 6563114, CC BY 4.0; 40 meters read by HTTP range requests because the archive is 3.3 GB and the link ran at about 100 KB/s)
  and the XAI4HEAT Nis substations (Mendeley, CC BY 4.0, sha256 matched). Dryad hydronic data (CC0) was not reachable without an account
  token; OpenEI chilled water records returned "No data found". No real district cooling ETS data was found.

### T2 world D (06:00 onwards)

* Design and 13 predictions committed before any D data existed (b457e83). A pre-commit mechanism check found that my first controller
  (PI on zone temperature) could not hunt; it was replaced by a discharge air cascade before the commit, and the check and its hourly
  result are written into `docs/research/WORLD_D.md`.
* Zero shot on D (`scripts/world_d_eval.py zeroshot`, `results/world_d.json`): macro AUROC 0.705 [0.685, 0.724], any fault 0.648, healthy
  false alarm 98%, overflow 0.547, fouling 0.577.
* Regenerating the simulator A pool on this Windows machine gave a file whose sha256 differs from the one in the model card (fa77ca41...
  against 680dca73...). Being checked at array level next.

### T3 fleet calibration (06:20 to 07:15 written; tests and commit 11:13)

* `deltat-doctor calibrate` and `diagnose --model` (commit 218e0f3). Tests: refusal below 10, incomplete inspections not counted, CLI
  message, no writing into assets, weak marking in card, report notes (English and Arabic) and provenance, tamper refusal, blind only, default
  model untouched, improvement on an unseen B fleet against an A only base. All pass.
* Decision: the calibrated model keeps the base model's gain regressors (inspections give causes, not recoverable delta T). Alternative was to
  drop savings for calibrated models; keeping them with the card saying so is more useful and reversible.
* Simulation check (`results/calibrate_check.json`): 40 building world D fleet, 12 held out: macro AUROC 0.782 to 0.833, top 1 agreement 0.6
  to 0.8 on 5 single cause buildings, overflow 0.81 to 0.66, abstention unchanged at 58%. The holdout is small; reported as partly supported.

### T4 fouling transfer (preregistered 06:22, run 10:47 to 11:35)

* H1 held, H2 failed, H3 failed, H4 held. Answer: B's fouling signature is weak (0.675 in world), not reversed.

### T5 assurance (06:25 onwards)

* pip-compile with hashes downloads every wheel to hash it; at about 100 KB/s that was impractical, so `scripts/make_lock.py` resolves with pip
  and takes PyPI's published digests. Constrained to the versions the bundled model was trained with.
* Found: the old `requirements-lock.txt` pinned 12 top level packages only. Its deletion was staged early and slipped into commit 69d7706, so the
  Docker build fails on 69d7706 to 218e0f3; fixed by 0221350. Not rewritten.
* Found: CI had been red on every commit since Round 4 (bc40e83), including v1.1.0 and v1.1.1, because Python 3.10 cannot install scikit-learn
  1.9 and the bundled model refuses other versions; fail fast then cancelled 3.12. Fixed in def4d91; CI green on 3.11, 3.12, 3.13 and Docker.
* Docker was not built locally (network); the CI job builds it with the offline install stage and passes the read only smoke test with an upload.

### T6 and T7 (11:20 onwards)

* An independent review pass (given only the repository and the constraints) returned 40 findings. Fixed: the high ones and most medium ones
  (see commit d13e76d and the CHANGELOG). Rejected, with reason: `tests/test_upload_cap.py` accepting 400 for a declared but absent body is
  test plumbing (the client cannot send the declared length), not a weak assertion; benchmark timings without a results file are labelled
  in DEPLOYMENT.md rather than rerun, because timings on this loaded machine would be meaningless. Not done: hyphenation clean up of older docs,
  plan.md refresh, a `_simulated` marker in example file names.
* The full test suite was not run locally under these machine conditions; it runs in CI on three Python versions for every push, and the
  tests touched tonight were run locally.
* Clean install check: a fresh virtual environment with `pip install .[api]` serves `/api/health` (status ok, version 1.2.0) and the
  fouled coils demo. `scripts/reproduce.py` quick checks all match (`results/reproduce_report.json`). CI green at def4d91 on Python 3.11,
  3.12, 3.13 and the Docker job.

## Final report (12:20)

**Predictions across the night**

| Set | Held | Failed | Not run |
|---|---|---|---|
| World D (D1 to D13, `docs/research/WORLD_D.md`) | D1, D2, D3, D4, D5, D8, D9, D12, D13 | D6 (guard flags 14% of new B buildings), D7 (guard passes the windows the model handles worse), D10 (hourly temporal features add 0.010 to overflow inside D) | D11 (machine load) |
| Fouling transfer (H1 to H4, `docs/research/TRANSFER_V2.md`) | H1, H4 | H2, H3 | none |
| Temporal block shipping rule (preregistered) | | fails part (b): not shipped | |

**Claims added:** world D zero shot 0.705 and few shot 0.825 / 0.850; guard withholds 92% of unseen world buildings; fleet calibration
command with refusal and weak marking; real district heating files refused at parsing (45 of 45); fouling transfers badly because B's
signature is weak; hashed lock, offline Docker install stage, SBOM, reproduce script.

**Claims corrected:** the guard is a novelty detector, not an error detector; guard false flags are much higher under degraded input and on
new B buildings; external check is 3 of 5 failed (not "one"); LBNL is simulated; README results table is simulator A only; valve confusion
3% and 4%; 0.836 not 0.84 (F1 failed); F5 not tested; CI was red since Round 4 (now fixed); round names no longer carry organisation names;
the B pool's seed was never recorded.

**Only a human can do:** native speaker review of the Arabic text; a real data partner with blind inspections (and sub hourly data and loop DP
where available); deciding whether to run the deferred few shot points (k = 5, 10) and in world A and B temporal runs on a free machine;
reviewing the remaining low findings in the overnight review (hyphenation in older docs, plan.md refresh, example file naming).

**Single most important next step:** a pilot with 10 to 20 buildings of one operator, inspected blind, scored with
`scripts/evaluate_real.py` and then calibrated with `deltat-doctor calibrate`; every figure in this repository is still simulation.
