# delta-t-doctor v1.2.0

Validated in simulation only. No field accuracy is claimed. The bundled models are the v1.1.1 models, unchanged.

## What is new

* **Fleet calibration.** `deltat-doctor calibrate manifest.csv --out fleet_model.joblib` adapts the cause classifiers to one fleet from
  inspected buildings; `deltat-doctor diagnose file.csv --model fleet_model.joblib` uses it. Refuses below 10 inspected buildings, marks 10 to
  19 as weakly calibrated in the model card and in every report, keeps a building level holdout report, verifies the file's sha256 before
  loading, and never replaces the default model. See `docs/API.md`.
* **World D**, a third, time stepped simulator (`src/deltat_doctor/sim/world_d.py`, `python scripts/generate_data.py --sim D`).
* **UTC timestamp note.** Exports with UTC timestamps now get a data quality note, because the hour of day measurements assume local time.
* **Assurance.** Generated, fully hashed `requirements.lock`; Docker image installed from hash checked wheels in a stage with networking
  disabled; CycloneDX SBOM (`sbom.cdx.json`); `scripts/reproduce.py`; CI actions pinned to commit SHAs; threat model in `docs/SECURITY.md`;
  claim by claim evidence in `docs/ASSURANCE_CASE.md`; a two page proposal in `docs/EDGE_PROPOSAL.md`.
* **Python 3.11 or newer** is now required, and scikit-learn is pinned to 1.9.x, the version the bundled model loads with.

## What was measured

| Experiment | Result | Source |
|---|---|---|
| Shipped model on world D, zero shot | macro AUROC 0.705 [0.685, 0.724]; 98% of healthy windows called faulty | `results/world_d.json` |
| Guards on world D | 92% of buildings withheld | `results/world_d.json` |
| Guards on new buildings of the training worlds | 0% (A), 14% (B) of buildings withheld | `results/world_d.json` |
| Few shot on world D | 20 buildings: 0.825, healthy false alarm 26%; 40 buildings: 0.850, 21%; overflow stays near 0.61 | `results/world_d.json` |
| Temporal features | no gain on overflow in an unseen world; other causes fall; not shipped | `results/world_d_temporal.json` |
| Fleet calibration, world D pretend fleet, 12 held out buildings | macro AUROC 0.782 to 0.833; overflow 0.81 to 0.66 | `results/calibrate_check.json` |
| Real district heating data (45 buildings, no labels) | all refused at parsing with a plain message; no crash | `results/real_data_contact.json` |
| Why fouling transfers badly from A to B | B's fouling signature is weak (in world 0.675) | `results/fouling_transfer.json` |
| Regenerating the A training pool | same numbers (4e-15), not the same file hash | `results/regeneration_check.json` |

## What failed

* World D predictions D6 (guard flags 14% of new simulator B buildings, limit 10%), D10 (hourly temporal features add only 0.010 to
  overflow even inside world D) and D7 (the guard lets through the windows the model
  handles worse, not better). D7 changes a claim: the guard detects unfamiliar buildings, not model errors.
* Fouling hypotheses H2 and H3.
* The temporal feature block failed its shipping rule.
* CI had been failing on Python 3.10 since Round 4, including v1.1.0 and v1.1.1; fixed here.
* The seed of the committed simulator B pool was never recorded.

## What is still open

* Real labelled data from a pilot partner; no UAE data has been used.
* Native speaker review of the Arabic text.
* Guard behaviour on real chilled water buildings.
* Sub hourly data to see valve hunting, which the hourly meter averages out.
* A container image vulnerability scan; a CSP nonce in place of `'unsafe-inline'`.
