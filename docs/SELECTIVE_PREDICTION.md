# Selective prediction: can the system tell when its own ranking is unreliable?

Status: **definitions, protocol and predictions written 2026-10-18, before `scripts/selective_prediction.py` was written or run.**
Results are appended below the line marked "Results"; the predictions are not edited afterwards.

## Why

On world D the open set guard withheld 92% of buildings, yet the windows it let through scored worse (macro AUROC 0.618) than the windows
it withheld (0.756) ([WORLD_D.md](WORLD_D.md), prediction D7). The guard answers "is this building unlike the training data?", not "is this
answer wrong?". A reviewer will ask the second question. This experiment measures whether any signal available at diagnosis time, without
labels, can answer it.

## Unit and definition of "wrong" (fixed now)

* **Unit:** one analysis window (30 days of hourly data), which is what the model scores. Windows from the same building are kept together in
  every split and every bootstrap.
* **The product's decision for a window:** "no material cause" if the any fault probability `p_any` is below 0.5; otherwise the top ranked
  cause (highest of the four cause probabilities).
* **Wrong** if the decision is "no material cause" while at least one cause is truly present, or if the top ranked cause is not truly present.
  "Truly present" is the simulator's counterfactual label (fixing it recovers at least 0.20 C).
* Secondary loss, continuous: the Brier score of the four cause probabilities against the four labels, per window.

## Signals (all computed without labels, at diagnosis time)

| # | Signal | Higher means |
|---|---|---|
| S1 | Open set guard score of the model in use (`openset.py`, rank of Mahalanobis plus nearest neighbour distance) | more unfamiliar |
| S2 | Predictive entropy: sum of the binary entropies of the four cause probabilities and `p_any` | more uncertain |
| S3 | Decision margin: minus the smaller of abs(`p_any` minus 0.5) and abs(top cause probability minus 0.5) | closer to a threshold |
| S4 | Ensemble disagreement: mean, over the four causes, of the standard deviation of the probability across 5 boosted classifiers trained on building bootstrap resamples of the training set (uncalibrated, 120 iterations, seeds 0 to 4) | members disagree more |
| S5 | Combination: logistic regression on the training rank of S1 to S4, fitted to predict "wrong" on simulator A and B data only (rows from settings 1 to 4 below), never on D | more likely wrong, as learned on A and B |

## Settings

1. In world A: 3 fold building grouped CV inside the regenerated A pool (`results/data/main.npz`); the model and S1 to S4 come from the training folds.
2. In world B: the same inside the committed B pool (`results/data_b/main.npz`).
3. A to B: model, guard and ensemble trained on A, scored on B.
4. B to A: trained on B, scored on A.
5. **World D, held out:** the shipped model and its own guard; the ensemble trained on A + B; S5 fitted on settings 1 to 4. D is never used to
   choose or tune anything.

The model in settings 1 to 4 is the product's calibrated classifier set (`Diagnoser._calibrated`, seed 0). Setting 5 uses the bundled model.

## Measures

* **AUROC of each signal for "wrong"** (how well it ranks wrong windows above right ones).
* **Risk coverage:** keep the windows with the lowest signal, from 100% coverage down to 10%; risk is the share of wrong decisions among the
  kept windows. **AURC** is the mean risk over coverages 10% to 100% (lower is better). Also the risk at 50% coverage. An oracle (sorting by the
  truth) and the base error rate are reported for scale.
* 95% building bootstrap intervals (500 resamples) on D for AUROC and AURC.

## Shipping rule for `--abstain-on uncertainty` (fixed now)

An optional second abstention, off by default, using S5 with its threshold at the 95th percentile of S5 on the A and B rows (the guard's
convention), ships only if **all** hold:

* (a) on world D, S5 has a higher AUROC for "wrong" than S1 (the guard), with the building bootstrap interval of the difference above 0;
* (b) on world D, S5's AURC is lower than S1's;
* (c) in world A and in world B, S5's AURC is not higher than S1's by more than 0.005.

Otherwise the default is kept and this is recorded as a negative result. Either way README, LIMITATIONS, MODEL_CARD and ASSURANCE_CASE are
updated to describe the guard exactly as measured.

## Predictions

| # | Prediction | Failure if |
|---|---|---|
| Q1 | In world (settings 1 and 2), the guard S1 is a weak error signal: AUROC for "wrong" below 0.60 in both | 0.60 or above in either |
| Q2 | On world D the guard is no better than chance at finding wrong windows: AUROC at most 0.50 | above 0.50 |
| Q3 | In world, entropy S2 is a useful error signal: AUROC at least 0.65 in both A and B | below 0.65 in either |
| Q4 | On world D, entropy S2 still beats chance (AUROC at least 0.55) but loses at least 0.05 against its in world average | below 0.55, or a loss under 0.05 |
| Q5 | On world D, ensemble disagreement S4 has an AUROC for "wrong" at least as high as entropy S2 | lower than S2 |
| Q6 | Margin S3 and entropy S2 are within 0.03 AUROC of each other in every setting | a gap above 0.03 anywhere |
| Q7 | On world D, the combination S5 reaches AUROC at least 0.60 and a lower AURC than the guard S1 | either part fails |
| Q8 | On world D, keeping the 50% of windows with the lowest S5 lowers the error rate by at least 5 percentage points against keeping all | under 5 points |
| Q9 | Across simulators (settings 3 and 4), S5 has AUROC at least 0.60 in both directions | below 0.60 in either |
| Q10 | The shipping rule passes | it fails |

What I expect overall: model confidence signals carry real information in world, less across worlds, and on world D the model is often
confidently wrong (98% of healthy windows are called faulty with high probability), which will limit every confidence signal. Q4 and Q8 are
the predictions I hold least firmly.

## Implementation details decided before the run

* **S5 inputs.** S1 is already a training rank in [0, 1]; S2 to S4 are on probability scales. A training rank for S2 to S4 would need out of
  fold scores on the training rows, so S5 uses the raw values of S1 to S4, standardised with the mean and spread of the A and B rows.
* **S5 is never scored on rows it was fitted on.** For settings 1 to 4 it is fitted on the other three settings (leave one setting out); for
  world D it is fitted on all four. This is stricter than the sentence above ("fitted on settings 1 to 4") for the A and B figures, and
  identical for D.

## Results

(appended after the run)
