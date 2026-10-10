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
