# Pilot proposal (draft)

**Goal:** measure, on real buildings, how often delta-t-doctor's top ranked cause matches what a site inspection finds.

## Scope
* One operator or one property owner. 10-20 penalised buildings. 90 days.
* Data: 12 months of ETS meter data per building (timestamp, flow, supply and return temperature or energy, outdoor
  temperature if available). Hourly data are needed for full reliability: 2 hourly data parse, but the open set guard flags 42% of such windows in simulation (`results/openset.json`).
* Contract terms per building (minimum delta T, surcharge rule, rate).

## Method
1. Run the tool blind on every building. Record the ranked causes before anyone visits.
2. An engineer inspects each building without seeing the output and records the dominant cause(s) among: fouling,
   passing valves, constant flow (3-way or stuck open) valves, excess pressure, other.
3. Compare. Report top-1 agreement, top-2 agreement, and where "other" occurred.
4. For buildings that are fixed, compare delta T and surcharge before and after.

## Success criteria (set before the pilot)
* Top-2 agreement with inspection of at least 70% on buildings with a single dominant cause.
* No building where the tool is confidently wrong (probability above 0.8) on a cause the inspection rules out,
  in more than 1 of 10.
* Fix-order value: the first inspection target is the dominant cause in at least half of the buildings.

These thresholds are my starting proposal, and the pilot partner should adjust them.

## What the partner gets
A ranked inspection list and an AED business case per building, plus a written account of where the tool was wrong.

## Data handling
Files are analysed in memory by the web app and are not stored. A pilot would run the tool inside the partner's own
environment (Docker) so that no data leaves it.

## Real-data validation: where it stands (v1.1.1)

No real UAE data has been used. Everything in this repository is simulator-validated. This section records what was looked for, what
the partner needs to supply, and how the result will be scored.

### Search for public real data (no ETS-level labelled set found)

The full record (every candidate opened, with licence, reason and checksums) is now [REAL_DATA_SEARCH.md](REAL_DATA_SEARCH.md), and the
first contact of the pipeline with real, unlabelled district heating meter data is in [REAL_DATA_CONTACT.md](REAL_DATA_CONTACT.md). The
table below is the v1.1.1 summary and is kept for history.

| Candidate | What it is | Why it does not settle the question |
|---|---|---|
| LBNL building-side plant data (already used, `docs/EXTERNAL_CHECK.md`) | Simulated plant data (EnergyPlus and Modelica, different team), no building-side fault labels | Gave a failed prediction; useful for the guard, not for accuracy |
| Vanderbilt ESB chiller dataset (reported) | Real campus chiller data | Plant side, not building ETS; I have not verified labels |
| LBNL FDD datasets | Mostly simulated or lab AHU/RTU faults | Different equipment and fault classes |
| Recent labelled AHU datasets (Scientific Data, 2025) | Air-handler faults | Existence and labels not confirmed by me; AHU, not ETS |

So a pilot is the only route to field evidence. The data are held by operators and owners, which is the point of proposing one.

### Data request pack (per building)

1. 12 months of hourly (or 2-hourly) ETS data: timestamp, flow, supply and return temperature (or energy), outdoor temperature if available.
2. Contract terms: minimum delta T, surcharge rule, rate.
3. Design delta T of the secondary loop, if known.
4. Optional, and the reason overflow is capped today: loop differential pressure or pump speed, and valve positions where the BMS records them.
5. An inspection record made **without seeing the tool's output**: dominant cause(s) from fouling, passing valves, constant flow valves, excess pressure, other, none; and whether the inspector ruled out the others.

### Scoring

`python scripts/evaluate_real.py manifest.csv` (template: `examples/real_manifest_template.csv`). It reports abstention rate, top-1 and top-2
agreement on single cause buildings, per cause AUROC, Brier score and reliability bins, healthy false alarms, the number of buildings where
the tool was confidently wrong (p > 0.8 on a cause the inspection ruled out), and 95% building-bootstrap intervals. With fewer than 10 buildings
it prints a warning and no intervals, and the numbers must not be quoted. The success criteria above are checked by the same script.

### Inspection form and dry run (v1.2.1)

Inspectors use the blind form in [INSPECTION_FORM.md](INSPECTION_FORM.md). `scripts/pilot_dry_run.py` rehearses the whole path (manifest,
`evaluate_real.py`, `calibrate`, rescoring) on synthetic buildings before a partner exists.

### Fleet calibration in the pilot (v1.2.0)

`deltat-doctor calibrate manifest.csv --out fleet_model.joblib` turns the labelled pilot buildings into a calibrated model for that fleet
([API.md](API.md), section "Fleet calibration"). It refuses below 10 inspected buildings, marks 10 to 19 as weakly calibrated, and holds out
30% of the buildings for a holdout report stored with the model. A suggested split for a 20 building pilot: inspect all 20 blind, score the
bundled model on all 20 with `scripts/evaluate_real.py`, then calibrate and read the holdout report. The default model is never replaced; a
calibrated model is used only with `--model`.

### What the pilot also tells us

* **Fleet calibration.** The few shot curve (`docs/TRANSFER_V2.md`) says about 20 to 40 labelled buildings from the target fleet are what move
  cross-physics performance from 0.69 to 0.80 (20 buildings) and 0.836 (40) in simulation. A 10 to 20 building pilot is therefore a calibration set as well as a test; keep a
  held out half for scoring.
* **Guard behaviour.** Even unlabelled real files show how often the tool abstains. Report that rate before accuracy.
* **Overflow.** If DP or pump speed is supplied, check whether it separates overflow from the valve faults; this is the only path to lifting its "possible" cap.
