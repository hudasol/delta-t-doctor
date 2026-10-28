# Baseline suite

Status: **run complete; predictions were committed before any baseline was run** (the existing logistic, hand rule and prior baselines were run before,
on simulator A only; their numbers are in the README and are not re-predicted here).

## Why

The README compares the model with three baselines on one simulator. The hand written rules are weak enough to be a strawman, and nothing is
compared outside simulator A. A reviewer will ask the simple questions: does a decision tree do as well, does a random forest, does a
threshold fitted to the data, does the plain delta T number, and does any of it survive a change of world? This document fixes the
protocol and the predictions first.

## Protocol

* Features: the same 42 shape features for every model. No model-specific feature work.
* Splits: building grouped 5 fold CV (same fold assignment for every model) inside simulators A, B and D. Zero shot transfer: A to B, B to A,
  and A+B to D (the shipped training set). Whole buildings never straddle train and test.
* Hyperparameters are fixed here, before running, and are not tuned on any test fold.
* Intervals: building level bootstrap, 200 resamples, 95%, paired differences against the shipped model on the same resamples.
* Metrics: macro AUROC over the four causes; any fault AUROC; mean Brier; expected calibration error (10 bins); healthy false alarm rate
  (p_any ≥ 0.5 on windows with no cause present); gain MAE when a cause is present (the quantity behind the AED estimate); and **top 1 precision**,
  meaning the share of faulty windows whose first recommendation (largest probability × predicted gain) is a cause that is really present.

| id | model | definition |
|---|---|---|
| prior | class prior | training prevalence for every window |
| rules_v1 | hand written rules | the existing `ExpertRules` heuristics, no training |
| delta_t_only | plain KPI | logistic regression on the flow weighted delta T alone (what a billing dashboard already knows) |
| stumps | fitted thresholds | per cause, the single feature and threshold with the best training AUROC (200 candidate thresholds), a fitted version of "rules of thumb" |
| tree3 | decision tree | depth 3, `min_samples_leaf` 20, per cause (readable rules) |
| logistic | logistic regression | the existing `LogisticBaseline` (C = 0.5, standardised) |
| rf | random forest | 300 trees, `min_samples_leaf` 3, `max_features` sqrt, per cause |
| hgb | boosting without calibration | `HistGradientBoosting`, 200 iterations, learning rate 0.06, 15 leaves, no calibration, no quantile models |
| shipped | delta-t-doctor | the `Diagnoser` as released |

Gain regressors: each baseline uses its own family (ridge for delta_t_only and logistic, a depth 3 tree, a forest, boosting). The prior uses the
mean training gain per cause. Stumps use the mean gain of training windows above the threshold.

## Predictions

| # | Prediction | Failure if |
|---|---|---|
| B1 | In world A the shipped model has the highest macro AUROC and leads the best other baseline by at least 0.02 | lead under 0.02, or any baseline higher |
| B2 | In world B, the same: highest, lead of at least 0.02 | lead under 0.02, or any baseline higher |
| B3 | In world D (CV inside D) the shipped model has the highest macro AUROC | any baseline higher |
| B4 | The best of rf and hgb is within 0.02 macro AUROC of the shipped model in A and in B (a generic ensemble gets most of the way) | gap above 0.02 in either |
| B5 | The shipped model has lower ECE than both rf and hgb in all three worlds | higher than either in any world |
| B6 | Fitted stumps beat the hand written rules_v1 by at least 0.10 macro AUROC in A | gap under 0.10 |
| B7 | delta_t_only scores at most 0.70 macro AUROC in every world | above 0.70 in any world |
| B8 | Zero shot A+B to D: every model scores at most 0.75 macro AUROC | any model above 0.75 |
| B9 | Zero shot A+B to D: the shipped model does not beat the best baseline by more than 0.02 (no robustness advantage under shift) | lead above 0.02 |
| B10 | Zero shot A to B and B to A: the shipped lead over the best baseline is under 0.03 in both | lead of 0.03 or more in either |
| B11 | Top 1 precision in A (CV): shipped at least 0.90, rules_v1 at most 0.60, prior at most 0.40 | any of the three missed |
| B12 | Gain MAE when present in A (CV): shipped at least 30% lower than the prior | reduction under 30% |
| B13 | Healthy false alarm rate in A (CV): shipped at most 10% | above 10% |

B9 and B10 are written so that the honest outcome "the shipped model has no special robustness" counts as a pass for the prediction, because
that is what I expect from the earlier transfer results.

## Results

### Macro AUROC

| Model | A | B | D | A to B | B to A | A+B to D |
|---|---|---|---|---|---|---|
| Prior | 0.478 | 0.451 | 0.462 | 0.500 | 0.500 | 0.500 |
| Hand rules (rules_v1) | 0.581 | 0.609 | 0.580 | 0.609 | 0.581 | 0.580 |
| Delta T only | 0.625 | 0.604 | 0.679 | 0.557 | 0.566 | 0.623 |
| Fitted stumps | 0.775 | 0.722 | 0.759 | 0.603 | 0.612 | 0.623 |
| Depth 3 tree | 0.910 | 0.815 | 0.824 | 0.701 | 0.662 | 0.683 |
| Logistic | 0.915 | 0.841 | 0.870 | 0.658 | 0.749 | 0.694 |
| Random forest | 0.963 | 0.887 | 0.898 | 0.702 | 0.750 | 0.688 |
| Plain boosting | 0.967 | 0.889 | 0.892 | 0.672 | 0.769 | 0.707 |
| Shipped | 0.966 | 0.884 | 0.895 | 0.683 | 0.770 | 0.705 |

A, B, D are grouped 5 fold CV inside each simulator; the other columns are zero shot transfer. Building level bootstrap intervals and paired differences are in `results/baselines.json`.

### Calibration and decision quality in simulator A (grouped CV)

| Model | Brier | ECE | Healthy false alarm | Top 1 precision | Gain MAE when present (C) |
|---|---|---|---|---|---|
| Prior | 0.170 | 0.002 | 1.00 | 0.37 | 1.07 |
| Hand rules (rules_v1) | 0.267 | 0.267 | 0.48 | 0.42 | 1.52 |
| Delta T only | 0.159 | 0.012 | 0.68 | 0.43 | 0.99 |
| Fitted stumps | 0.117 | 0.006 | 0.18 | 0.80 | 0.81 |
| Depth 3 tree | 0.074 | 0.009 | 0.13 | 0.89 | 0.57 |
| Logistic | 0.071 | 0.016 | 0.08 | 0.92 | 0.50 |
| Random forest | 0.051 | 0.018 | 0.08 | 0.94 | 0.39 |
| Plain boosting | 0.047 | 0.010 | 0.07 | 0.95 | 0.38 |
| Shipped | 0.047 | 0.005 | 0.08 | 0.95 | 0.38 |

### Healthy false alarm rate (p_any at or above 0.5), shipped model

| A | B | D | A to B | B to A | A+B to D |
|---|---|---|---|---|---|
| 0.08 | 0.07 | 0.08 | 0.88 | 0.25 | 0.98 |

### Scoring of the predictions

| ID | Outcome | Evidence |
|---|---|---|
| B1 | failed | A: boosting 0.967, shipped 0.966; no lead |
| B2 | failed | B: boosting 0.889 and forest 0.887 above shipped 0.884 |
| B3 | failed | D: forest 0.898 above shipped 0.895 |
| B4 | held | best generic ensemble is within 0.001 (A) and 0.005 (B) of shipped |
| B5 | held | shipped ECE 0.005, 0.009, 0.009 against forest 0.018, 0.018, 0.017 and boosting 0.010, 0.042, 0.043 |
| B6 | held | stumps 0.775 against rules_v1 0.581 in A, a gap of 0.194 |
| B7 | held | delta_t_only at most 0.679 in every setting |
| B8 | held | highest zero shot score on D is 0.707 (plain boosting) |
| B9 | held | shipped 0.705, below plain boosting 0.707 |
| B10 | held | A to B: shipped below forest and tree; B to A: lead 0.001 |
| B11 | held | top 1 precision shipped 0.95, rules_v1 0.42, prior 0.37 |
| B12 | held | gain MAE 0.38 against 1.07 for the prior (64% lower) |
| B13 | held | healthy false alarm 0.08 in A |

Ten of thirteen predictions held; B1, B2 and B3 failed.

### Reading

* The shipped model does not beat a plain gradient boosting or random forest on the same features in discrimination. The three failed predictions were the ones claiming that it would. Differences from plain boosting are within the bootstrap noise in A, B and D.
* What the shipped model adds over a generic ensemble is calibration (lowest ECE in every world, B5), the gain intervals, the abstention and the evidence statements. Those are product properties, not AUROC gains, and are described as such.
* Hand written rules and a fitted single threshold are far behind (0.58 and 0.78 in A), and the plain delta T number alone reaches only 0.60 to 0.68. Cause level diagnosis needs the shape features.
* A depth 3 tree reaches 0.91 in A, and logistic regression 0.915: much of the simulated signal is easy. This is a statement about the simulators, not about field data.
* Zero shot, no model passes 0.77, and the healthy false alarm rate of every model on A+B to D is 0.94 to 1.00 except the hand rules (0.30) and delta T only (0.20), which are also the least discriminating. No model, shipped or not, solves transfer to an unseen world; the shipped model has no special robustness (B9, B10).
* The fitted stump rules on A are: fouling `flow_bin5 < 0.694`; passing valves `dt_night_minus_day < -0.0642`; constant flow `dt_hi_minus_mid > 0.867`; overflow `dt_period > 5.03`.

Source: `scripts/baselines.py`, `results/baselines.json`, `results/baselines.log`. Protocol, hyperparameters and seeds are fixed as stated above.
