# API

Interactive docs are served at `/docs` (OpenAPI) when the app is running. All endpoints take contract terms as
`min_dt` (default 8.9), `pct` (default 0.10, a fraction per degree C below the minimum) and `rate`
(AED per RT-hr, default 0.40, **illustrative only**). `design_dt` (degrees C) is optional and switches on the informed model.

| Method and path | Purpose |
|---|---|
| `GET /api/health` | status, version, cause list. `status` is `model-missing` if no model is installed |
| `POST /api/diagnose` | multipart `file` (CSV or .xlsx) plus the terms; returns the diagnosis JSON |
| `POST /api/portfolio` | multipart `file` with a `building_id` column (optional `design_delta_t_c` column); returns ranked buildings |
| `POST /api/report` | same inputs as diagnose plus `name`; returns a printable HTML report |
| `GET /api/demos`, `GET /api/demo/{name}` | list and run a simulated demo building |
| `GET /api/demo/{name}/report`, `GET /api/demo/{name}.csv` | demo report and demo data |
| `GET /api/demo-portfolio`, `GET /api/demo-portfolio.csv` | a simulated 12-building portfolio |

## Input file

One row per reading, any common delimiter. Headers are matched loosely (`CHW Supply Temp (degF)`, `Flow [L/s]`,
`Cooling Load (RT)`, `OA Temp`). Needed: a timestamp, a flow, and either supply and return temperatures or a cooling
power or energy column. Cumulative kWh registers are differenced. Outdoor temperature is optional and helps.
At least 14 days; a full year is best.

## Diagnosis response (abridged)

```json
{
  "delta_t_c": 7.52, "min_delta_t_c": 8.9, "below_minimum": true,
  "annual_surcharge_aed_estimate": 230952.0, "p_any_cause": 1.0,
  "mode": "blind", "design_delta_t_c": null,
  "findings": [{"cause": "fouling", "probability": 1.0, "expected_dt_gain_c": 2.9,
                "expected_saving_aed_per_year": 230952.0, "checks": ["..."]}],
  "monthly": [], "notes": [], "data_quality": {"reliable": true, "features_out_of_range": 0.4, "coverage": 0.99}
}
```

`data_quality.reliable` is `false` when the building's behaviour is outside the trained range (per-feature box or the open-set Mahalanobis guard), or when input quality is poor (dropped rows, outliers, a flatlined meter, low coverage). When a guard trips, `abstained` is `true` and `findings` is empty.

New in v1.1 on every result: `abstained`, `guard` (open-set score, threshold, box count), `series` (per-window delta-T and cause probabilities), `trend` (Kendall / Theil-Sen on delta-T at 60-100% load), `provenance`, `is_demo`, `notes_ar`, `disclaimer_ar`. Each finding adds `tier` (likely / possible / weak / unsupported), `evidence` (measured features against the healthy 5th-95th percentile, `weak_signature`), `label_ar`, `checks_ar`, and `saving_low/high_aed_per_year`. Savings are capped at the annual surcharge.
Show that to users: the ranking should not be trusted in that case.

## Errors

`422` with a plain-language `detail` for unreadable files, missing columns, too little data or invalid terms.
`413` above 25 MB. `404` for an unknown demo. `503` if the informed model is not installed.

## Fleet calibration (command line only, new in v1.2.0)

The web API always uses the bundled model. Calibration is a separate, explicit step on the command line:

```
deltat-doctor calibrate manifest.csv --out fleet_model.joblib
deltat-doctor diagnose building.csv --model fleet_model.joblib
```

* **Input.** A manifest in the format of `examples/real_manifest_template.csv`: `building_id`, `file` (meter export, relative to the
  manifest), `causes` (semicolon list of `fouling`, `passing_valves`, `constant_flow`, `overflow`, `other`, `none`), `complete` (`yes` when
  the inspection ruled out every cause not listed). Only buildings with `complete = yes` are used; the others are listed as skipped.
* **What changes.** The four cause classifiers and the any fault classifier are refitted on the base model's training rows plus every
  window of the labelled buildings, repeated 5 times (`--repeat`), the weighting measured in `scripts/transfer_fewshot.py`. The open set guard
  and the per feature range are refitted on base plus fleet windows. Delta T gains and AED savings still come from the base model's
  regressors, because inspections give causes, not recoverable delta T.
* **Refusals and warnings.** Fewer than 10 usable labelled buildings: refused, no file written. 10 to 19: written, but marked
  `weakly_calibrated` in the model card and in every report that uses it (`calibration` field, a "WEAKLY CALIBRATED" note in English and
  Arabic, and the provenance block). Calibrated models are blind only (no `--design-dt`). The output may not be written into the package
  assets, so it can never replace the default model.
* **Holdout report.** 30% of the labelled buildings (at least 3, `--holdout`, fixed `--seed`) are never used for fitting. The model card
  (`fleet_model.joblib.card.json`) records, for the base and the calibrated model on those buildings: abstention rate, per cause and macro
  AUROC, top 1 and top 2 agreement on single cause buildings, and healthy false alarm rate.
* **Provenance.** The card records the base model's sha256, the manifest's sha256, the sha256 of every building file, the number of
  buildings, the date, the parameters and the calibrated model's own sha256, which is verified before the model is loaded (fail closed).
* **Evidence.** In simulation only: `scripts/calibrate_check.py` and `results/calibrate_check.json`, and `tests/test_calibrate.py`.
