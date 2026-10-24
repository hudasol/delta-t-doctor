# Roadmap: open limitations

Status as of v1.2.1. Everything in this repository is validated in simulation only; no field accuracy is claimed. Each row names one planned fix and one measurable success criterion.

| Limitation | Status | Planned fix | Success criterion |
|---|---|---|---|
| Validation in simulation only | Open | Pilot with one operator: 10 to 20 buildings, blind inspections using `docs/INSPECTION_FORM.md`, scored with `scripts/evaluate_real.py` | At least 10 inspected buildings scored, with top 2 agreement of at least 70% and at most 1 in 10 confidently wrong, as set in `docs/PILOT.md` |
| The guard detects unfamiliar buildings, not model mistakes | Measured, not solved (`docs/SELECTIVE_PREDICTION.md`) | Calibrate on labelled buildings from the target fleet, then re-test an error signal on that fleet | An error signal with risk coverage area below the no abstention baseline on a held out fleet |
| Simulator B data not regenerable (seed never recorded) | Mitigated: regenerable B pools with recorded seeds (`docs/REPRODUCIBILITY.md`) | Report all headline B figures on the regenerable pools and keep the legacy pool labelled | No headline B figure rests only on the legacy pool |
| Few shot on world D only at k = 0, 20, 40 | Closed in v1.2.1 (k = 5, 10, 70 added) | None | Done |
| Temporal features tested only in world D | Closed in v1.2.1 (all three worlds); block not shipped | Re-test on real data if hourly meters allow it | Overflow AUROC gain of at least 0.02 with no other cause falling by more than 0.01 |
| Arabic text awaiting native review | Open, needs a person | Native speaking engineer completes `docs/i18n_review_sheet.csv` using `docs/ARABIC_REVIEW_BRIEF.md` | Every string marked accepted or corrected, corrections merged and tested |
| Docker build failing on commits 69d7706 to 218e0f3 | Noted, history not rewritten | Keep CI building and smoke testing the image on every commit from the fix onward | CI Docker job green on every commit after the fix |
