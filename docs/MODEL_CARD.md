# Model card

**Task.** For a district-cooled building's ETS meter data, estimate for each of four causes (fouling, passing valves,
constant-flow valves, excess pressure) the probability it is materially present (recovering at least 0.20 C of
delta-T if fixed) and the delta-T it would recover.

**Model.** Calibrated gradient-boosted classifiers and regressors on 42 scale-free shape features, one set per cause,
plus an any-fault classifier. Two variants: blind, and informed (adds the building's design delta-T and the shortfall
against it). Trained with a fixed seed in under a minute.

**Training data.** 6,500 simulated 30-day windows from 650 simulated buildings, from two different simulators: A (5,000 windows;
office, hotel, residential, mall; coil-level physics with injected faults) and B (1,500 windows; seven building classes with
humidity-driven load, equal-percentage valves, 3-way mixing and a plate-exchanger ETS, where faults emerge from the hydraulics).
Design delta-T 4.7-12.8 C. Each label comes from a counterfactual re-simulation with the cause removed. No real data.
See [CROSS_SIMULATOR.md](CROSS_SIMULATOR.md).

**Uncertainty.** Besides the expected gain, each cause has a 10th, 50th and 90th percentile of recoverable delta-T (quantile
boosting, widened by a conformal margin fitted on held-out buildings). Savings in AED are computed from those percentiles, so
the report shows a range as well as a number. On held-out simulated buildings the 10-90 range covered the true gain 82% to 85% of
the time where it mattered (nominal 80%; `results/uncertainty.json`). Where a cause was truly present but the model had predicted
almost no gain, coverage was lower (55% to 76%). Ranges assume the windows of one building move together, so they are wide; they
do not include error in scaling a partial year to a full year.

**Evaluation.** On held-out simulated buildings from simulator A: macro AUROC 0.966 (blind, 95% interval 0.963 to 0.969) and
0.971 (informed); across 4 regenerated datasets the spread is 0.959 +/- 0.003. Calibration, stress, leave-one-building-type-out and
held-out-season results are in [results/metrics.md](../results/metrics.md). Across simulators the picture is much weaker: trained on A
and tested on B it scores 0.683, trained on B and tested on A 0.770 ([CROSS_SIMULATOR.md](CROSS_SIMULATOR.md)). Reproduce with
`python scripts/evaluate.py` and `python scripts/cross_simulator.py`.

**Intended use.** Ranking what to inspect first in a variable-flow building loop fed by district cooling, with the owner
or an engineer checking on site.

**Not for.** Billing disputes, automatic control, plants or chiller loops, constant-flow systems, anything where a wrong
ranking has safety consequences, or buildings the tool marks "not reliable".

**Known failures.**
* On the LBNL chiller-plant benchmark (a different kind of system) it reports a fault with near-certainty, in blind
  and informed modes. See [EXTERNAL_CHECK.md](EXTERNAL_CHECK.md).
* Overflow is the weakest cause (AUROC 0.92 in simulation, chance level across simulators). Weak faults (true gain 0.2 to 0.4 C) are
  missed about half the time or more.
* Across simulators it calls most healthy buildings faulty (88% of simulator B's healthy windows when trained on A only).
* Passing valves and constant-flow valves are rarely confused inside a simulator (2% to 4%), but the simulator gives them different
  signatures by construction. Whether real valves separate so cleanly is unknown, so the report still warns when both rank highly.
* Unmodelled causes (controls, sensors, set-points, pump staging) are forced into the nearest of the four.

**Open-set guard (v1.1).** In addition to the per-feature range check below, a Mahalanobis-distance score over all 42 features (median across windows against the 95th percentile of training scores) decides abstention; when it trips the ranking is withheld. Leave-one-world-out estimate in `results/openset.json`: 71% of B flagged when fit on A, 25% of A when fit on B.

**Out-of-range guard.** The model stores the 1st-99th percentile range of each feature. A window with more out-of-range
features than 95% of training windows (4 of 42) is reported as "not reliable". On the simulator-A stress sets (fresh buildings,
3x noise, climate shifts, no outdoor temperature) it fires for 1% to 5% of windows (`results/identifiability.json`). On simulator B,
for a model trained only on A, it fired for 36%, which is too few: most of B's windows were diagnosed wrongly and not flagged.

**Field validation.** None yet. A pilot protocol is in [PILOT.md](PILOT.md).
