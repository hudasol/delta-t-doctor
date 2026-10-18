# Reproducibility of the training data and the headline numbers

## What can be regenerated, and what cannot

| Data | Committed? | Regenerable from the repository? | Evidence |
|---|---|---|---|
| Simulator A pool (`results/data/main.npz`, 500 buildings x 10 windows, seed 11) | no (gitignored, regenerated) | **yes, numerically**: the shipped model's stored training percentiles match to 4e-15 and label prevalence is identical; the file hash differs in the last float bits | `scripts/check_regenerated.py`, `results/regeneration_check.json` |
| Simulator B pool (`results/data_b/main.npz`, 150 x 10) | yes | **no**: the seed used to make it was never recorded; seed 11 gives a different pool | same |
| Replicate B pools (`results/data_b_r2101`, `_r2102`, `_r2103`, 150 x 10 each) | yes | yes: seed, call and versions in each `generator.json` (the seed 11 pool in `results/data_b_t` from v1.2.0 has the seed in its folder history only, no `generator.json`) | `results/replication_b.json` |
| World D (`results/data_d/main.npz`, 150 x 10, seed 21) | yes | yes (`scripts/reproduce.py --full`) | `results/reproduce_report.json` |
| Domain randomised worlds C-A and C-B (`results/data_ca`, `results/data_cb`) | yes | not checked | none |

Headline numbers that rest on the non regenerable B pool: the shipped model itself (trained on A + the committed B), in world B 0.884,
A to B 0.683, B to A 0.770 (`results/cross_simulator.json`), the guard rates fit on or tested against B (`results/openset.json`), the B side
of the few shot and transfer experiments (`results/transfer_fewshot.json`, `results/transfer_v2.json`), the overflow analysis in B, and the
fouling transfer analysis (`results/fouling_transfer.json`).

## Replication with recorded seeds (F2, 2026-10-18)

Status: **predictions written before `scripts/replicate_b.py` was run.**

New B pools are generated with recorded seeds and a recorded generator identity (package version, git commit, Python, numpy, pandas and
scikit-learn versions, arguments), each as a new folder `results/data_b_r<seed>/` with a `generator.json`; the committed pool is not replaced.
Seeds: **2101, 2102, 2103** (150 buildings x 10 windows each, `n_jobs=1`). The pool regenerated last night with seed 11
(`results/data_b_t`, used in the temporal experiment) is included as a fourth replicate.

On each pool, with the protocol of `scripts/cross_simulator.py` (the product's calibrated classifiers, seed 0, building grouped):

* in world B: 5 fold building grouped CV macro AUROC;
* A to B: trained on the regenerated A pool, tested on the replicate B pool;
* B to A: trained on the replicate B pool, tested on the A pool;
* healthy false alarm rate of the A to B model on B (p_any at least 0.5).

| # | Prediction | Failure if |
|---|---|---|
| R1 | In world B macro AUROC is within 0.02 of 0.884 on every replicate | any replicate outside 0.864 to 0.904 |
| R2 | A to B macro AUROC is within 0.03 of 0.683 on every replicate | any outside 0.653 to 0.713 |
| R3 | B to A macro AUROC is within 0.03 of 0.770 on every replicate | any outside 0.740 to 0.800 |
| R4 | Across the replicates, the spread (largest minus smallest) of each of the three figures is at most 0.03 | any spread above 0.03 |
| R5 | A to B healthy false alarm stays above 70% on every replicate (88% on the committed pool) | any replicate at 70% or below |

Decision rule, fixed now: the bundled model is retrained only if a replicate moves a headline figure by more than the tolerances above **and**
the committed pool turns out to be the outlier among the five pools (committed plus four replicates). Otherwise the committed pool stays,
documented as non regenerable but replicated.

Definitions added at 02:58, before any replicate pool was evaluated (the first pool had been generated; none had been scored), after a review
pointed out that "outlier" was undefined:

* "The replicates" in R1 to R5 are the four regenerated pools (seeds 11, 2101, 2102, 2103); the committed pool is not one of them.
* The committed pool is "the outlier" for a figure when its value lies outside the replicates' minimum to maximum by more than that figure's
  tolerance (0.02 for in world B, 0.03 for the two transfers).

## Results

Run 2026-10-18 02:38 to 03:53 (`scripts/replicate_b.py`, `results/replication_b.json`; each pool's `generator.json` records the seed, call,
package version, git commit and library versions). Generating one pool took 16 to 19 minutes on this machine with `n_jobs=1`.

| Pool | in world B | A to B | B to A | A to B healthy false alarm |
|---|---|---|---|---|
| committed | 0.884 | 0.684 | 0.770 | 88% |
| seed 11 | 0.896 | 0.697 | 0.741 | 87% |
| seed 2101 | 0.908 | 0.689 | 0.749 | 86% |
| seed 2102 | 0.889 | 0.676 | 0.757 | 90% |
| seed 2103 | 0.888 | 0.670 | 0.746 | 84% |

Replicate means: in world B 0.895, A to B 0.683, B to A 0.748, healthy false alarm
87%. Spread over the four replicates (largest minus smallest): in world B 0.021, A to B 0.026, B to A 0.016 (these three are R4); healthy false alarm 0.056.

The protocol reproduces the committed pool's own published figures to within 0.001 (0.884, 0.684 against 0.683 published, 0.770, 88%), so
the differences below come mainly from the pools.

| # | Outcome | Verdict |
|---|---|---|
| R1 | in world B 0.896, 0.908, 0.889, 0.888 (allowed 0.864 to 0.904) | **Failed** (seed 2101, 0.908, is higher) |
| R2 | A to B 0.697, 0.689, 0.676, 0.670 | Held |
| R3 | B to A 0.741, 0.749, 0.757, 0.746 | Held, all near the lower bound |
| R4 | spreads 0.021, 0.026, 0.016 | Held |
| R5 | 87%, 86%, 90%, 84% | Held |

Decision rule: the committed pool is not an outlier on any figure (in world B 0.884 is 0.004 below the replicate range, B to A 0.770 is 0.013
above it; both inside the tolerances), so the bundled model is **not** retrained.

**What moves.** The headline transfer figures hold on regenerable data. The one honest correction: **B to A is 0.741 to 0.757 on regenerated
pools (mean 0.748), so the committed pool's 0.770 sits at the favourable end.** The range quoted in README and LIMITATIONS,
"0.68 to 0.77", becomes "0.68 to 0.77 (0.67 to 0.76 on four regenerated B pools)". In world B on regenerated pools is slightly higher
(0.888 to 0.908) than the committed 0.884. The A to B healthy false alarm stays between 84% and 90%.

From now on any new B result should use a regenerable pool. By a rule fixed here, the default is the pool closest to the replicate means on
all three figures, `results/data_b_r2102/main.npz` (0.889, 0.676, 0.757); results that depend on B should also be checked on the other two.
The committed pool is kept because the shipped model was trained on it.
