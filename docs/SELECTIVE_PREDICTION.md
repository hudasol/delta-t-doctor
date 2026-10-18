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

Run on 2026-10-18 (`scripts/selective_prediction.py`, `results/selective_prediction.json`, per window values in
`results/selective_prediction_windows.npz`; about 10 minutes, single process).

**Timeline, stated plainly.** The protocol and predictions were committed at 02:15 (dca7f70). The script was drafted in the same minutes and
committed 75 seconds later (745ac0d) together with the "Implementation details" section above; neither had been run. The first run (02:28 to
02:38) broke ties in the risk coverage figures by file order. A review found this; AURC was made tie aware (a5922d1) and the experiment was
rerun at 03:54. The rerun moved no AUROC, and no AURC or 50% coverage figure by more than 0.001; the first run's file is kept as
`results/selective_prediction_firstrun_tie_order.json`. All figures below are from the rerun.

**Deviations and limits, listed here as well as above.** (1) S5 uses standardised raw signal values, not training ranks (decided before the run,
after the preregistration). (2) "Never scored on rows it was fitted on" holds by row but not by window: in world A and B to A score the same A
windows, so S5 for one is fitted on the other's windows under a different model. A stricter variant that leaves the whole target world out
(S5b, not preregistered) gives 0.756 (in world A), 0.683 (B), 0.570 (A to B) and
0.728 (B to A); D is unaffected. (3) The per window decision is a **proxy** for the product's report, which works per building,
averages windows, uses tiers and caps overflow at "possible"; these results do not directly measure the shipped report.

**AUROC of each signal for "wrong"** (0.5 is chance; below 0.5 means the signal is higher on right answers than on wrong ones):

| Setting | windows, base error rate | S1 guard | S2 entropy | S3 margin | S4 disagreement | S5 combination |
|---|---|---|---|---|---|---|
| In world A | 5000 windows, 7.0% wrong | 0.399 | 0.865 | 0.905 | 0.818 | 0.849 |
| In world B | 1500 windows, 21.5% wrong | 0.442 | 0.730 | 0.733 | 0.687 | 0.666 |
| A to B | 1500 windows, 63.1% wrong | 0.417 | 0.569 | 0.553 | 0.478 | 0.566 |
| B to A | 5000 windows, 38.7% wrong | 0.519 | 0.744 | 0.711 | 0.559 | 0.737 |
| World D (held out) | 1500 windows, 68.0% wrong | 0.583 | 0.457 | 0.608 | 0.434 | 0.513 |

**AURC**, tie aware (mean error rate over coverages 10% to 100%, lower is better; the oracle sorts by the truth):

| Setting | oracle AURC | S1 guard | S2 entropy | S3 margin | S4 disagreement | S5 combination |
|---|---|---|---|---|---|---|
| In world A | 0.003 | 0.087 | 0.015 | 0.011 | 0.020 | 0.017 |
| In world B | 0.029 | 0.234 | 0.116 | 0.116 | 0.132 | 0.143 |
| A to B | 0.293 | 0.691 | 0.591 | 0.589 | 0.650 | 0.587 |
| B to A | 0.098 | 0.381 | 0.231 | 0.244 | 0.348 | 0.235 |
| World D (held out) | 0.350 | 0.620 | 0.720 | 0.606 | 0.734 | 0.680 |

**Error rate when only the 50% of windows with the lowest signal are kept:**

| Setting | all windows | S1 guard | S2 entropy | S3 margin | S4 disagreement | S5 combination |
|---|---|---|---|---|---|---|
| In world A | 7.0% | 8.9% | 0.4% | 0.3% | 1.1% | 0.4% |
| In world B | 21.5% | 25.1% | 9.5% | 10.0% | 11.3% | 12.8% |
| A to B | 63.1% | 66.0% | 56.1% | 59.7% | 64.5% | 58.7% |
| B to A | 38.7% | 36.7% | 20.9% | 24.5% | 34.5% | 22.2% |
| World D (held out) | 68.0% | 63.3% | 70.8% | 60.8% | 71.6% | 68.1% |

**Preregistered secondary loss: mean Brier score** of the four cause probabilities, all windows against the kept 50%:

| Setting | all windows | S1 guard | S2 entropy | S3 margin | S4 disagreement | S5 combination |
|---|---|---|---|---|---|---|
| In world A | 0.048 | 0.044 | 0.009 | 0.027 | 0.011 | 0.010 |
| In world B | 0.078 | 0.077 | 0.036 | 0.045 | 0.038 | 0.054 |
| A to B | 0.189 | 0.170 | 0.197 | 0.216 | 0.191 | 0.216 |
| B to A | 0.135 | 0.117 | 0.083 | 0.094 | 0.117 | 0.087 |
| World D (held out) | 0.244 | 0.273 | 0.226 | 0.250 | 0.210 | 0.247 |

**Intervals** (building bootstrap, 500 resamples, seed 0). In world, guard AUROC [0.370, 0.428] (A) and [0.407, 0.479] (B); margin
[0.892, 0.917] (A) and [0.696, 0.767] (B). World D: guard [0.548, 0.619], margin [0.571, 0.640], S5 [0.477, 0.553];
margin minus guard [-0.029, 0.081]; S5 minus guard [-0.130, -0.006]; AURC guard [0.582, 0.656], S5
[0.643, 0.714], S5 minus guard [0.019, 0.097]. S5 weights (standardised, fitted on A and B): guard +0.44,
entropy +1.05, margin +0.52, disagreement -0.41.

### Predictions scored

| # | Outcome | Verdict |
|---|---|---|
| Q1 | guard 0.399 (A) and 0.442 (B) | Held |
| Q2 | guard on D 0.583 [0.548, 0.619] | **Failed**: weakly informative on D, not chance |
| Q3 | entropy 0.865 (A) and 0.730 (B) | Held |
| Q4 | entropy on D 0.457 | **Failed**: below chance |
| Q5 | disagreement on D 0.434, entropy 0.457 | **Failed** |
| Q6 | margin minus entropy: +0.041 (A), +0.004 (B), -0.016 (A to B), -0.0330 (B to A, just past 0.03), +0.151 (D) | **Failed** (A, B to A and D) |
| Q7 | S5 on D 0.513, AURC 0.680 against the guard's 0.620 | **Failed** |
| Q8 | S5 keeps the error rate at 68.1% at 50% coverage (68.0% for all windows) | **Failed** |
| Q9 | S5 0.566 (A to B) and 0.737 (B to A) | **Failed** (A to B) |
| Q10 | (a) fails, S5 minus guard AUROC [-0.130, -0.006]; (b) fails; (c) holds | **Failed**: not shipped |

2 of 10 held. `--abstain-on uncertainty` is **not** added; the default is unchanged.

### The measured answer to "when does the system know it is probably wrong?"

* **Inside a familiar simulator, its own confidence carries the information.** The decision margin ranks wrong windows above right ones at 0.905
  AUROC in A and 0.733 in B; keeping the more confident half cuts the error rate from 7.0% to 0.3% (A) and from 21.5% to 10.0% (B).
* **Across physics, only weakly**, and unevenly: 0.55 to 0.57 from A to B, 0.71 to 0.74 from B to A.
* **On a physics it has never seen (world D), it does not.** No label free signal exceeds 0.61 AUROC. The model's own entropy is below chance
  (0.457): on D its wrong windows tend to carry confident probabilities (98% of healthy D windows are called faulty, `results/world_d.json`).
  The margin (0.608) and the guard (0.583) cannot be told apart (difference [-0.029, 0.081]); keeping the more confident half
  still leaves 61% (margin) or 63% (guard) of decisions wrong, against 68%.
* **The open set guard is a novelty detector, not an error detector.** In world it is below chance as an error signal (intervals above, both
  below 0.5): it flags unusual windows that the model handles correctly. On D it is weakly informative (0.583). This complements D7: on D the
  windows it flags are somewhat more often wrongly decided, yet within them the cause probabilities rank better (macro AUROC 0.756 against 0.618).
* **What this means for the product.** On a new fleet no confidence number from the model or the guard should be read as reliability.
  Calibration on inspected buildings is the only adaptation measured to raise accuracy on an unfamiliar physics (few shot on world D, all k
  buildings used for fitting: 0.71 to 0.83 with 20 buildings, `results/world_d.json`); whether it also restores error detection has **not**
  been tested. The decision margin looked best on D, but it was not the preregistered signal and D was used to notice it, so it is not shipped;
  it is a candidate to preregister against a future world.
