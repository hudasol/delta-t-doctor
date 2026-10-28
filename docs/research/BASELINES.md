# Baseline suite

Status: **predictions committed before any baseline was run** (the existing logistic, hand rule and prior baselines were run before,
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

Not run yet.
