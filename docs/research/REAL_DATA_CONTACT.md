# First contact with real meter data (no labels)

**No cause accuracy is claimed or measured here.** Neither dataset has labels for the four causes, and both are district heating, not
district cooling. The question is narrower: what does the pipeline do when it meets real, messy meter files, and does it refuse or abstain
where it should?

Sources, licences and checksums: [REAL_DATA_SEARCH.md](REAL_DATA_SEARCH.md). Reproduce:

```
python scripts/fetch_real_data.py
python scripts/real_contact.py
```

Output: `results/real_data_contact.json` (per building and summary). Loaders: `scripts/real_loaders.py`, tested on synthetic fixtures in
`tests/test_real_loaders.py`.

## Two paths

* **Product path.** Each building is written out the way a user would upload it (flow and temperatures under the product's column names,
  supply = inlet, return = back, timestamps as the source gives them) and passed unchanged to `read_table` and `diagnose_frame`.
* **Research path, not the product.** The loader builds the canonical hourly frame directly, skipping the chilled water plausibility checks,
  so the 42 shape features and both guards can be looked at on real hydraulics. It answers: if a heating file got past the unit checks, would
  the open set guard still stop it?

## Results

| | Danish smart heat meters (Zenodo 6563114) | Nis substations (XAI4HEAT) |
|---|---|---|
| Buildings | 40 (seeded random choice of 3021), about 26,000 hourly rows each (3 years) | 5, 10,877 to 18,137 hourly rows each |
| Loader | 40 of 40 read; no negative register steps, no irregular steps; hours with zero volume: median 50 (0 to 10,667); hours with a delta T outside -1 to 80 C set aside: median 1,272 (41 to 6,513); heat from flow and temperatures against the energy register: median ratio 1.02 (0.87 to 1.05) | 5 of 5 read; no flow column exists |
| Product path | **40 of 40 refused at parsing**, with the message that the supply temperature median (61 to 75 C) is not a plausible chilled water temperature | **5 of 5 refused**: "No flow column found" |
| Crashes or silent failures | none crashed; one silent issue found (below) | none |
| Research path: open set guard | flags 40 of 40 buildings (99.8% of windows) | not run (no flow) |
| Research path: per feature box | flags 40 of 40 buildings (100% of windows) | not run |
| Research path: combined abstention | **40 of 40 buildings** | not run |
| Flow weighted delta T (5th, 25th, 50th, 75th, 95th percentile across buildings) | 27.7, 34.3, 36.5, 40.0, 42.7 C | median primary supply minus return per substation: 32.1 to 35.0 C (no flow, so not flow weighted) |
| Model output if the guard were ignored | median probability of "some cause" 0.99 | not run |

Reading:

* Both datasets are outside the product's scope, and the product says so at the first step with a plain message. That is the correct and
  useful outcome, not a failure.
* Even when the unit checks are bypassed, both guards withhold the ranking on every Danish building. Without the guards the model would call
  almost every one faulty (median 0.99), which is the same failure mode as the LBNL check in [EXTERNAL_CHECK.md](EXTERNAL_CHECK.md). The
  guard's 100% abstention here is easy: a 36 C delta T is far outside anything simulated. It says nothing about how the guard behaves on real
  chilled water buildings that look nearly normal, which is the case that matters.
* Real hydraulics in these houses do follow load (median correlation of flow with load 0.74, against 0.18 for the LBNL plant), so the guard
  fired on delta T level and shape rather than on flow behaviour.

## Product issue found and fixed

The Danish files carry UTC timestamps (`2018-01-02T23:00:00Z`). The parser handles them, but the hour of day features (night against day,
weekend against week) assume local wall time, so a UAE export written in UTC would shift them by four hours **with no warning**. v1.2.0
adds a data quality note when timestamps are in UTC, in English and Arabic (`src/deltat_doctor/io.py`, test in `tests/test_real_loaders.py`).
The timestamps are not converted, because the local zone of an upload is not known.

## What this does not show

No accuracy, no false alarm rate on real chilled water buildings, and nothing about UAE buildings. Those need a pilot partner's ETS data and
blind inspections ([PILOT.md](../PILOT.md)).
