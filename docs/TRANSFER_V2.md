# Transfer v2: can the transfer gap be closed, and what does not work?

Status: **predictions written 2026-10-11, before any of the code below was run.**

## The question

Trained on simulator A and tested on simulator B the model scores 0.683 macro AUROC; B to A is 0.770 (`docs/CROSS_SIMULATOR.md`).
Shipping a model trained on both closes the gap for those two worlds only, and says nothing about a third, which is the position a real
building is in. This round tests four candidate fixes with a protocol that never trains on the world it is tested on.

## Worlds

* **A** and **B**: the existing simulators (`results/data`, `results/data_b`).
* **C-A**: simulator A physics with a much wider randomisation envelope (sensor offsets, supply temperature, ETS loss, flow bias,
  noise, fault severity, climate shift, window length, dropped hours). Never contains B physics.
* **C-B**: simulator B physics with a wider envelope (valve oversize, minimum valve position, exchanger approach, offsets,
  noise, severity, climate shift, window length). Never contains A physics.

C-A and C-B are domain randomisation inside one physics. Whether that helps across physics is exactly what is tested. The honest limit: it
cannot show transfer to a *structurally* new world, only to the two we have.

## Protocol

Train-on / test-on pairs, always whole buildings, never the test physics in training:

* T1: train A, test B (baseline 0.683). T1+: train A + C-A, test B.
* T2: train B, test A (baseline 0.770). T2+: train B + C-B, test A.

Candidate fixes, each scored on T1 and T2 and on in world grouped CV (to see what it costs):

1. **Wide randomisation**: add C-A / C-B to training (T1+, T2+).
2. **Invariant features**: drop shape features whose distribution differs most between worlds (selected using the *training* worlds only:
   A vs C-A for T1, B vs C-B for T2), keep the rest.
3. **Target-batch standardisation**: standardise features by the unlabelled target batch's own median and spread (what a deployment could do
   with a customer's portfolio). Reported with its known cost: it also removes real prevalence differences.
4. **Combined**: 1 + 2.

## Predictions

| # | Prediction | Counts as failure of my expectation if |
|---|---|---|
| V1 | T1+ lifts A to B macro AUROC from 0.683 to between 0.70 and 0.76 | below 0.70 (no help) or above 0.76 |
| V2 | T2+ lifts B to A from 0.770 to between 0.78 and 0.84 | below 0.78 or above 0.84 |
| V3 | Invariant features alone give at most +0.03 on T1 and T2 | more than +0.03 |
| V4 | Target-batch standardisation helps T1 by at least 0.03 but hurts in world AUROC by no more than 0.02 | otherwise |
| V5 | Overflow stays below 0.65 AUROC on both transfers whatever the fix | any transfer above 0.65 |
| V6 | Healthy false-alarm rate on T1 (88% baseline) falls below 60% with the best fix | stays above 60% |
| V7 | No fix gets either transfer above 0.85 macro AUROC | a fix does |
| V8 | In world AUROC cost of wide randomisation is at most 0.02 | more than 0.02 |

Results are appended below, with every failed prediction reported.

## Results of the four fixes (run after the predictions above; `results/transfer_v2.json`, `scripts/transfer_v2.py`)

Macro AUROC on the held out physics, building-bootstrap 95% interval in brackets. Training never contains the test physics.

| fix | T1: train A, test B | T2: train B, test A |
|---|---|---|
| baseline | 0.683 [0.656, 0.706] | 0.770 [0.758, 0.778] |
| wide randomisation (adds C-A or C-B) | 0.682 [0.654, 0.702] | 0.752 [0.742, 0.760] |
| invariant features (drop 13 of 42) | 0.680 [0.658, 0.701] | 0.784 [0.776, 0.792] |
| target batch standardisation | 0.715 [0.688, 0.736] | 0.736 [0.728, 0.744] |
| wide + invariant | 0.689 [0.664, 0.710] | 0.763 [0.755, 0.771] |

Healthy-building false alarms on T1 (baseline 88%): wide 76%, invariant 84%, batch standardisation 48%, combined 77%.
In world cost (one building grouped fold): A 0.968 baseline, 0.969 wide, 0.964 invariant, 0.959 batch; B 0.867 baseline, 0.884 wide, 0.870 invariant, 0.874 batch.

**Against my predictions.**

* V1 failed: wide randomisation did nothing for A to B (0.682 against a predicted 0.70 to 0.76).
* V2 failed, in the wrong direction: B to A *fell* to 0.752 with C-B added.
* V3 held: invariant features moved the result by -0.003 and +0.014.
* V4 held for T1 (+0.032, in world cost at most 0.009) but I did not predict that it would hurt T2 (-0.034).
* V5 failed narrowly: batch standardisation took overflow on A to B to 0.65.
* V6 held: false alarms fell to 48% with batch standardisation.
* V7 held: nothing exceeds 0.79.
* V8 held: wide randomisation costs nothing in world (+0.001 on A, +0.016 on B).

**Reading.** Randomising parameters inside one physics does not teach the model another physics. The gap is structural, so no feature trick closes
it with these two simulators. Batch standardisation is the only fix that moves A to B, and it hurts B to A, so it is not shipped. The honest
position is: transfer to an unseen world is about 0.68 to 0.78, the guard has to catch the worst cases, and the model must be calibrated on
a few surveyed buildings from the real fleet. The next section measures how few.

## Few shot adaptation: how many surveyed buildings does a pilot need?

Status: **predictions written before this ran.** Train on the source physics plus *k* whole buildings of the target physics (target rows repeated 5x),
test on target buildings never seen. Three random draws of the *k* buildings; fixed test buildings (B: 70 of 150; A: 150 of 500).

| # | Prediction | Failure if |
|---|---|---|
| F1 | A to B: with 10 target buildings macro AUROC is at least 0.78; with 40, at least 0.84 | below either |
| F2 | B to A: with 20 target buildings macro AUROC is at least 0.88 | below |
| F3 | Overflow remains the weakest cause at every k up to 40 | any other cause is weaker |
| F4 | Healthy false alarms on A to B fall below 30% at 20 target buildings (88% at 0) | stay above 30% |
| F5 | The curve flattens: going from 40 to 80 target buildings adds under 0.03 | adds more |

### Few shot results (`scripts/transfer_fewshot.py`, `results/transfer_fewshot.json`)

Macro AUROC on held out target buildings (mean of 3 draws; sd of the draws 0.001 to 0.017). "Healthy FA" is the share of healthy
buildings called faulty at p ≥ 0.5.

| k target buildings | A to B macro | A to B healthy FA | A to B overflow | B to A macro | B to A healthy FA | B to A overflow |
|---|---|---|---|---|---|---|
| 0 | 0.689 | 82% | 0.555 | 0.767 | 23% | 0.532 |
| 5 | 0.727 | 66% | 0.630 | 0.809 | 19% | 0.591 |
| 10 | 0.759 | 43% | 0.682 | 0.866 | 11% | 0.657 |
| 20 | 0.800 | 24% | 0.764 | 0.903 | 10% | 0.779 |
| 40 / 50 | 0.836 | 19% | 0.834 | 0.935 | 8% | 0.855 |
| 70 / 100 | 0.859 | 12% | 0.875 | 0.951 | 7% | 0.891 |
| – / 200 | – | – | – | 0.959 | 7% | 0.907 |

| # | Outcome | Verdict |
|---|---|---|
| F1 | 10 buildings: 0.759 (needed 0.78); 40 buildings: 0.836 (needed 0.84) | **Failed**, narrowly on both |
| F2 | 20 buildings: 0.903 (needed 0.88) | Held |
| F3 | B to A: overflow is the weakest cause at every k up to 200 (0.907 at k=200); A to B: fouling is the weakest cause from k=5 on (overflow 0.83 at k=40 versus fouling 0.66) | **Failed** as stated (A to B); held for B to A |
| F4 | 24% at 20 buildings (needed under 30%); at k=0 the measured figure was 82%, not the 88% written in the prediction | Held (the "88%" in the prediction was a misquote; the correct baseline is 82%) |
| F5 | A to B 40 to 70 buildings adds 0.023; the 80 building point was not run | Not tested as stated (corrected in v1.2.0 from "Held, approximately") |

Reading, plainly:

* A pilot does not need a large labelled fleet to leave the weak region. Roughly 20 surveyed buildings lift the weaker direction from
  0.69 to 0.80 and cut healthy false alarms from 82% to 24%; 40 gets 0.836, just under the preregistered 0.84 (F1 failed). These are simulator to simulator numbers; the
  point is the shape of the curve, not the values, and real buildings may need more or fewer.
* Fouling is the cause that adapts worst in A to B (0.66 at k=40 while the others reach 0.83 to 0.96). I have not yet tested why; a
  plausible but unverified reading is that B's valve and mixing physics hide the fouling signature.
* The two predictions I got wrong were both over-optimistic about small k. The product therefore states the requirement as "calibrate on
  about 20 to 40 surveyed buildings before trusting the probabilities", not "a handful".
* None of this is real-data evidence. It says how fast a model adapts when the target data are labelled and drawn from a simulator.

## Addendum (v1.2.0): why does fouling transfer worst from A to B?

Status: **hypotheses and predictions written 2026-10-16, before `scripts/fouling_transfer.py` was written or run.**

The few shot table above shows fouling as the cause that adapts worst in A to B (0.66 at 40 target buildings, the others 0.83 to 0.96).
One fact was already known before this addendum and must not be counted as a test: `docs/OVERFLOW.md` reports that inside world B alone,
fouling is the weakest cause (0.700 AUROC on one building grouped fold). So part of the answer may be that fouling is simply hard to see in B,
whatever the training world.

Feature groups used below (42 shape features): **delta T shape** (`dt_period`, `dt_p10`, `dt_p90`, `dt_std_loaded`, `dt_lowload`,
`dt_night_minus_day`, `dt_weekend_minus_week`, `dt_hi_minus_mid`, `dt_bin0` to `dt_bin7`), **flow shape** (`zero_flow_frac`,
`flow_lowload_share`, `flow_intercept_ratio`, `flow_load_corr`, `flow_cv_loaded`, `flow_p10_over_p95`, `flow_p50_over_p95`, `flow_bin0` to
`flow_bin7`), **load distribution** (`duty_factor`, `load_p10_over_p98`, `frac_bin0` to `frac_bin7`), **weather** (`dt_vs_oat_slope`).

| # | Hypothesis | Prediction | Failure if |
|---|---|---|---|
| H1 | Masking: B's valve, mixing and exchanger physics shrink the fouling signature | For the 5 features whose single fault fouling effect (median shift in healthy spread units, as in `scripts/transfer_v2.py`) is largest in A, the median of the absolute effect in B is less than half the median in A | it is half or more |
| H2 | Direction: the features that identify fouling in A point the other way, or are not monotone, in B | At least 2 of those 5 features have a univariate fouling AUROC on opposite sides of 0.5 in A and in B | fewer than 2 |
| H3 | The delta T shape features learned in A mislead in B | Leave one group out, trained on A and tested on B: removing the delta T shape group raises fouling AUROC on B by at least 0.02; trained on B and tested on A, removing it lowers fouling AUROC on A by at least 0.02 | either part fails |
| H4 | Identifiability ceiling (partly post hoc, see above) | Building grouped 5 fold CV inside B gives fouling AUROC at most 0.75, and the A to B fouling AUROC at 40 target buildings (0.66) is within 0.10 of it | in world B fouling above 0.75, or the gap is larger than 0.10 |

Also reported, without a prediction: permutation importance of the A trained fouling classifier measured on held out A and on B, and
partial dependence of that classifier on its two most important features, with the B and A feature ranges marked.

The answer is written below whichever way it goes, including "undetermined".

### Results (`scripts/fouling_transfer.py`, `results/fouling_transfer.json`)

| # | Measured | Verdict |
|---|---|---|
| H1 | A's five strongest fouling features (`dt_std_loaded`, `flow_load_corr`, `flow_bin5`, `dt_hi_minus_mid`, `dt_vs_oat_slope`) shift by a median of 3.63 healthy spreads in A and 0.38 in B, about a tenth | Held |
| H2 | Only `dt_std_loaded` has a univariate fouling AUROC on opposite sides of 0.5 (0.78 in A, 0.46 in B); the other four point the same way in both worlds, only much more weakly in B (0.15 to 0.21 in A, 0.36 to 0.48 in B) | **Failed** |
| H3 | Removing the delta T shape group lowers fouling AUROC in both directions: A to B 0.630 to 0.614 (I predicted a rise), B to A 0.889 to 0.870 (a fall of 0.020, just under the 0.02 I required) | **Failed** |
| H4 | Building grouped 5 fold CV inside B gives fouling AUROC 0.675, and the A to B few shot value at 40 buildings is 0.66, within 0.02 | Held |

Descriptive: the A trained fouling classifier relies mostly on `dt_std_loaded` and `flow_load_corr` (permutation importance on held out A:
0.103 and 0.060 AUROC). On B, `dt_std_loaded` is worth almost nothing (0.008) and `flow_load_corr` remains the main feature (0.068). Partial
dependence shows why the second one cannot carry over: in A, `flow_load_corr` lies between 0.91 and 1.00 (5th to 95th percentile), in B
between 0.27 and 1.00, and over most of B's range the A model's output is flat at about 0.52, which is extrapolation, not information.

**Answer.** Fouling transfers worst from A to B mainly because B's fouling signature is weak, not because it points the wrong way. Inside B
alone fouling is found at only 0.675 AUROC, the few shot curve reaches the same level, and A's strongest fouling features move about a tenth as
much in B. The delta T shape features are not misleading in B (H3 failed), and only one feature reverses (H2 failed). In B's physics a fouled
coil is compensated by the valve and the plate exchanger approach, so the meter sees little. The practical consequence is the same as for
overflow: in a fleet whose hydraulics resemble B, fouling will be hard to confirm from meter data alone, and calibration cannot lift it above
what the meter data contain. This is a simulation result about two simulators written by the same author.
