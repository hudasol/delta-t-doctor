# Pilot dry run summary (SYNTHETIC)

**Simulated buildings only (simulator B, seed 5); the labels are simulator ground truth, not inspections. Nothing here is evidence about real buildings.** Produced by `scripts/pilot_dry_run.py`.

Simulator B is one of the bundled model's training worlds, so high scores are expected and say nothing about accuracy; the dry run tests the path, not the model.

Fleet: 24 buildings, 2 months each. Calibration half: 12; scoring half: 12.

| Measure | All buildings, bundled model | Scoring half, bundled | Scoring half, calibrated |
|---|---|---|---|
| n_buildings | 24 | 12 | 12 |
| abstention_rate | 0.17 | 0.08 | 0.08 |
| top1 | 1.00 | 1.00 | 1.00 |
| top2 | 1.00 | 1.00 | 1.00 |
| healthy_false_alarm | 0.12 | 0.17 | 0.17 |
| confidently_wrong_buildings | 1 | 1 | 1 |
| brier | 0.09 | 0.10 | 0.10 |
| interpretable | True | True | True |

Calibration card: **weakly calibrated** on 12 buildings (8 fitted, 4 held out inside the calibration half).

`interpretable` is false when `evaluate_real.py` was given fewer than 10 buildings.
