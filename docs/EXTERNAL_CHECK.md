# External check on the LBNL chiller-plant benchmark

**Status of this document:** the predictions in section 2 were written *before* the check
was run. Section 4 (results) is appended afterwards, unedited by hindsight.

## 1. What this check is, and is not

The public LBNL FDD chiller-plant dataset (Granderson et al., DOE, CC-BY, EnergyPlus-Modelica
simulation of a 12-storey Chicago office, 1-minute data, 21+ faulted years and one fault-free year)
contains no building-side low-delta-T root-cause labels: its faults sit on the plant side (sensor
biases, condenser-loop valve, cooling-tower fouling, chiller fouling, secondary pressure-sensor bias).

So it **cannot measure the accuracy** of this tool's four-way diagnosis. What it can do is act as an
independent, physics-simulated building the classifier has never seen, from a different team,
climate and code base:

* Does a healthy building read as healthy (few false alarms)?
* Do faults that do not touch the building loop leave the verdict unchanged?
* What does the tool say about the secondary-loop pressure-sensor faults, which do change hydraulics?

The data are mapped as: secondary-loop supply/return temperature, secondary-loop flow and outdoor
dry-bulb temperature (deg F and GPM converted to SI). Chicago winter months have almost no cooling, so
results are reported for the cooling season (June-September) and for the full year.

## 2. Predictions (written before running)

* **P1.** On the fault-free year, the mean probability of "any material cause" over cooling-season
  windows is below 0.35.
* **P2.** For plant-side faults that should not alter the building loop (cooling-tower fouling 95%,
  cooling-tower PI tuning, chiller sensor bias +2 C, condenser three-way valve stuck 75% and leaking
  75%), the cooling-season mean "any cause" probability stays within 0.15 of the fault-free value.
* **P3.** For the secondary pressure-sensor bias of -20% (controller believes pressure is lower than
  it is and drives the pumps harder) I expect the "overflow" probability to rise relative to the
  fault-free year. I hold this prediction weakly: whether the fault is visible in delta-T at all is
  unknown to me.
* **Out-of-distribution caveat.** The classifier was trained on Dubai-like simulated buildings. A
  Chicago office with a different design delta-T is out of distribution, so a failed P1 would more
  likely mean "domain shift" than "bad classifier", and I will say so only if the evidence supports it.

## 3. Method

`scripts/lbnl_check.py` extracts selected CSVs from the LBNL zip, builds the same canonical hourly
frame the tool uses for real meter exports, splits it into 30-day windows and runs the trained
diagnoser. No retraining or threshold tuning on this data.

## 4. Results

Run on the dataset's cooling season (June-September), no retraining, no threshold changes.
Raw output: `results/lbnl_check.json`, `results/lbnl.log`.

**A mistake worth recording.** The first run mapped supply and return temperature the wrong way round
(measured delta-T of exactly 0.00). I found it from that implausible number, fixed the mapping in
`scripts/lbnl_check.py`, and discarded the first run's output (kept as
`results/lbnl_first_run_discarded.log`). The numbers below are from the corrected run only. The
predictions above were not edited.

| Case | cooling-season delta-T (C) | any cause | fouling | passing valves | constant flow | overflow |
|---|---|---|---|---|---|---|
| fault-free | 2.62 | 1.00 | 0.98 | 0.06 | 0.67 | 0.04 |
| secondary pressure bias -20% | 2.61 | 1.00 | 0.98 | 0.06 | 0.68 | 0.03 |
| secondary pressure bias -10% | 2.61 | 1.00 | 0.98 | 0.06 | 0.66 | 0.04 |
| secondary pressure bias +10% | 2.79 | 1.00 | 0.98 | 0.06 | 0.66 | 0.04 |
| secondary pressure bias +20% | 2.95 | 1.00 | 0.98 | 0.06 | 0.67 | 0.05 |
| cooling tower fouling 95% | 2.62 | 1.00 | 0.98 | 0.06 | 0.67 | 0.04 |
| cooling tower PI tuning | 2.62 | 1.00 | 0.98 | 0.06 | 0.67 | 0.03 |
| chiller sensor bias +2 C | 4.43 | 1.00 | 1.00 | 0.19 | 0.15 | 0.23 |
| condenser 3-way stuck 75% | 0.13 | 0.99 | 0.07 | 0.00 | 0.41 | 0.02 |
| condenser 3-way leak 75% | 0.13 | 0.99 | 0.07 | 0.00 | 0.41 | 0.02 |

### Verdicts against the predictions

* **P1 failed, clearly.** The fault-free year scores 1.00 "any cause", against a prediction of below 0.35.
  The tool raised a false alarm on a healthy building.
* **Why (interpretation, not proven).** This plant's secondary loop runs at a delta-T of about 2.6 C
  even with no fault. The classifier was trained on buildings designed for 9-13 C, in which a delta-T
  that low can only come from a fault. A building that is *designed* low-delta-T is outside what the
  model has seen, and it reads such a building as a badly fouled one. This is a domain-shift limit of
  the model, and it is the main limitation of the tool. I did not tune anything to hide it. The tool
  now prints a warning when average delta-T is below 4 C (added after seeing this result, so it is a
  response to the finding and not evidence for it).
* **P2 passes only on a technicality.** Every case scores 0.99-1.00 on "any cause", so all are within
  0.15 of the fault-free value. But the prediction has no power here because the score is saturated.
  The per-cause probabilities do move for two cases: the chiller sensor bias (constant flow 0.67 to
  0.15) and the condenser 3-way valve (fouling 0.98 to 0.07). Both change the measured delta-T a lot,
  so a change is not unreasonable, but I cannot call it correct either, since this data has no
  building-side labels.
* **P3 not supported.** With the pressure bias at -20%, overflow stayed at 0.03 against 0.04 fault-free.
  Delta-T barely moved either (2.61 vs 2.62), so this fault is probably not visible in delta-T at
  all. I held this prediction weakly.

### What this check does and does not show

Tower fouling and PI tuning leave the building loop untouched and give identical outputs to the
fault-free year, which is the only well-behaved result here. It is a consistency check, not an accuracy
measurement. Accuracy claims in this repo rest on the simulated evaluation (`results/metrics.md`), and
the model has not been validated on real UAE meter data.

