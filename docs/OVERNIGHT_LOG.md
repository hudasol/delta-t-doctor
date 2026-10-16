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
* Known issue, recorded and not rewritten: the v1.1.1 commit (409fc66) has an AI tool listed as author and carries a co author trailer and
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

* Two openly licensed real datasets were opened, licences read and checksums verified (`docs/REAL_DATA_SEARCH.md`): Danish smart heat
  meters (Zenodo 6563114, CC BY 4.0; 40 meters read by HTTP range requests because the archive is 3.3 GB and the link ran at about 100 KB/s)
  and the XAI4HEAT Nis substations (Mendeley, CC BY 4.0, sha256 matched). Dryad hydronic data (CC0) was not reachable without an account
  token; OpenEI chilled water records returned "No data found". No real district cooling ETS data was found.

### T2 world D (06:00 onwards)

* Design and 13 predictions committed before any D data existed (b457e83). A pre-commit mechanism check found that my first controller
  (PI on zone temperature) could not hunt; it was replaced by a discharge air cascade before the commit, and the check and its hourly
  result are written into `docs/WORLD_D.md`.
* Zero shot on D (`scripts/world_d_eval.py zeroshot`, `results/world_d.json`): macro AUROC 0.705 [0.685, 0.724], any fault 0.648, healthy
  false alarm 98%, overflow 0.547, fouling 0.577.
* Regenerating the simulator A pool on this Windows machine gave a file whose sha256 differs from the one in the model card (fa77ca41...
  against 680dca73...). Being checked at array level next.
