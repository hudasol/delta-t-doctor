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
