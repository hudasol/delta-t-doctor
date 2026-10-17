# Methodology

## Pipeline

```
meter CSV -> canonicalise (hourly, SI units) -> 30-day windows -> 42 features -> models -> ranked report
```

1. **Canonicalise** (`io.py`). Accepts common column names, flow in m3/h, L/s or GPM, and either
   supply/return temperatures or energy. Resamples to hourly. Needs at least 14 days.
2. **Features** (`features.py`). 42 shape-based, scale-invariant numbers: delta T per load band, flow
   per load band, flow load correlation, share of flow at low load, day/night and weekend structure, delta T
   against outdoor temperature. They describe the *shape* of how the building behaves, so a large and a small
   building with the same fault look alike.
3. **Models** (`models.py`). For each of four causes, a calibrated gradient-boosted classifier
   (is this cause materially present?) and a regressor (how many degC of delta T would fixing it recover?).
   Plus an "any fault" classifier.
4. **Penalty and savings** (`penalty.py`). Contract terms (minimum delta T, surcharge per degC, rate) turn
   delta T into dirhams. A cause's expected saving is its predicted delta T gain priced through the same
   surcharge formula. Causes are ranked by expected AED per year.

## Simulator (ground truth)

Real buildings do not come with root-cause labels, so the training data are simulated (`sim/`).

* **Coil:** effectiveness-NTU counterflow model. Water-side resistance scales with flow^0.8. A
  healthy part load delta T ceiling stops the idealised coil from returning unrealistically warm water.
* **Faults:** fouling (extra thermal resistance), passing valves (leak flow at low delta T through idle
  coils), constant flow (3-way valve or stuck open actuator), overflow (extra flow at part load from excess
  differential pressure). Causes can combine (30% healthy, 40% one, 22% two, 8% three).
* **Buildings:** office, hotel, residential and mall schedules; design delta T drawn from 5.0-12.2 C (simulator A) and 4.5-13 C (simulator B); the healthy part load ceiling on coil delta T may sit below design (from v1.1).
* **Weather:** Dubai-like monthly means with a daily cycle and correlated noise. Synthetic, not measured.
* **Labels by counterfactual.** For each simulated sample, each cause is removed in turn and the building is
  simulated again. The delta T improvement is that cause's ground-truth gain. A cause is "present" if
  its gain is at least 0.20 degC. This is how the models learn "what would fixing this recover?".

## Evaluation protocol (`scripts/evaluate.py`)

* **Held out buildings:** 5-fold CV grouped by building, so the same building never appears in train and test.
* **Baselines:** logistic regression, hand-written expert rules, and a class-prior guess.
* **Stress shifts:** 3x sensor noise, 2-hour data, climate +/-3 C, half and 1.5x fault severity, no outdoor
  temperature, 21-day window, energy-only meter.
* **Leave one building type out** and **held out seasons.**
* **Metrics:** AUROC, F1, Brier score, gain error, and a decision metric: of the available delta T
  gain, how much does fixing the tool's top-ranked cause capture.

All results are in [results/metrics.md](../results/metrics.md) and are simulator results.

## Honest scope

Simulator-only validation means the numbers measure self-consistency under a physical model I chose. The
external check ([EXTERNAL_CHECK.md](EXTERNAL_CHECK.md)) was designed in advance, and it showed a real
weakness, documented there. See [LIMITATIONS.md](LIMITATIONS.md).


## Simulator B and the gain intervals (v1.1)

A second generator, `sim/hydraulic.py`, models valves, differential pressure, a wet coil and a plate exchanger ETS so that fault
signatures emerge instead of being injected. It exists to test generalisation, not to replace simulator A. Both are written by the same
author. See [CROSS_SIMULATOR.md](CROSS_SIMULATOR.md).

Each cause also has quantile gain models (10th, 50th, 90th percentile). Because the saving is a monotone function of the gain, its
10th and 90th percentiles are the saving at those gain percentiles; its mean is taken over the gain distribution so that the
tariff's hinge (no saving above the contract minimum) does not bias it upward. The 10-90 range is with a conformal margin (fitted; 0.0 on the shipped data, so effectively raw quantiles),
computed separately for "active" intervals (upper end of 0.2 C or more) and the rest, using out-of-fold predictions from held out buildings.
