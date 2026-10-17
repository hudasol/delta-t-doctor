# Reproducibility of the training data and the headline numbers

## What can be regenerated, and what cannot

| Data | Committed? | Regenerable from the repository? | Evidence |
|---|---|---|---|
| Simulator A pool (`results/data/main.npz`, 500 buildings x 10 windows, seed 11) | no (gitignored, regenerated) | **yes, numerically**: the shipped model's stored training percentiles match to 4e-15 and label prevalence is identical; the file hash differs in the last float bits | `scripts/check_regenerated.py`, `results/regeneration_check.json` |
| Simulator B pool (`results/data_b/main.npz`, 150 x 10) | yes | **no**: the seed used to make it was never recorded; seed 11 gives a different pool | same |
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

## Results

(appended after the run)
