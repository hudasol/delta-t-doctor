# Model card

**Task.** For a district cooled building's ETS meter data, estimate for each of four causes (fouling, passing valves,
constant flow valves, excess pressure) the probability it is materially present (recovering at least 0.20 C of
delta T if fixed) and the delta T it would recover.

**Model.** Calibrated gradient-boosted classifiers and regressors on 42 scale free shape features, one set per cause,
plus an any fault classifier. Two variants: blind, and informed (adds the building's design delta T and the shortfall
against it). Trained with a fixed seed in about a minute. The simulator A pool regenerates to the same numbers; the seed of the committed
simulator B pool was not recorded, so that pool is committed rather than regenerable (`results/regeneration_check.json`).

**Training data.** 6,500 simulated 30-day windows from 650 simulated buildings, from two different simulators: A (5,000 windows;
office, hotel, residential, mall; coil-level physics with injected faults) and B (1,500 windows; seven building classes with
humidity-driven load, equal-percentage valves, 3-way mixing and a plate exchanger ETS, where faults emerge from the hydraulics).
Design delta T 4.7-12.8 C. Each label comes from a counterfactual re-simulation with the cause removed. No real data.
See [CROSS_SIMULATOR.md](research/CROSS_SIMULATOR.md).

**Uncertainty.** Besides the expected gain, each cause has a 10th, 50th and 90th percentile of recoverable delta T (quantile
boosting, with a conformal margin fitted on held out buildings; it came out 0.0 for every cause, so the intervals are the raw quantiles). Savings in AED are computed from those percentiles, so
the report shows a range as well as a number. On held out simulated buildings the 10-90 range covered the true gain 82% to 85% of
the time where it mattered (nominal 80%; `results/uncertainty.json`). Among windows where the cause is
truly present, coverage was lower (55% to 76%). Ranges assume the windows of one building move together, so they are wide; they
do not include error in scaling a partial year to a full year.

**Evaluation.** On held out simulated buildings from simulator A, for models trained and tested on A only (not the shipped A + B model): macro AUROC 0.966 (blind, 95% interval 0.963 to 0.969) and
0.971 (informed); across 4 regenerated datasets the spread is 0.959 +/- 0.003. Calibration, stress, leave one building type out and
held out-season results are in [results/metrics.md](../results/metrics.md). Across simulators the picture is much weaker: trained on A
and tested on B it scores 0.683, trained on B and tested on A 0.770 ([CROSS_SIMULATOR.md](research/CROSS_SIMULATOR.md)); on four regenerated B
pools (three with recorded seeds and generator identity, one with seed 11) these are 0.670 to 0.697 and 0.741 to 0.757 ([REPRODUCIBILITY.md](research/REPRODUCIBILITY.md)). Reproduce with
`python scripts/evaluate.py` and `python scripts/cross_simulator.py`.

**Intended use.** Ranking what to inspect first in a variable flow building loop fed by district cooling, with the owner
or an engineer checking on site.

**Not for.** Billing disputes, automatic control, plants or chiller loops, constant flow systems, anything where a wrong
ranking has safety consequences, or buildings the tool marks "not reliable".

**Known failures.**
* On the LBNL chiller-plant benchmark (a different kind of system) it reports a fault with near certainty, in blind
  and informed modes. See [EXTERNAL_CHECK.md](research/EXTERNAL_CHECK.md).
* Overflow is the weakest cause (AUROC 0.92 in simulation, chance level across simulators). Weak faults (true gain 0.2 to 0.4 C) are
  missed often: recall at p >= 0.5 for gains of 0.2 to 0.4 C is 0.28 (overflow), 0.41 (passing valves), 0.57 (fouling) and 0.69
  (constant flow) (`results/error_analysis.json`).
* Across simulators it calls most healthy buildings faulty (88% of simulator B's healthy windows when trained on A only).
* Passing valves and constant flow valves are rarely confused inside a simulator (2% to 4%), but the simulator gives them different
  signatures by construction. Whether real valves separate so cleanly is unknown, so the report still warns when both rank highly.
* Unmodelled causes (controls, sensors, set-points, pump staging) are forced into the nearest of the four.

**Open set guard (v1.1).** Two guards run and the ranking is withheld if either fires. The first is the per feature range check described below. The second averages the training-rank of a Mahalanobis distance and a mean 10-nearest neighbour distance over all 42 features (median across windows against the 95th percentile of training scores) and decides abstention; when it trips the ranking is withheld. Leave-one-world-out estimate in `results/openset.json`: 64% of B's windows flagged when fit on A, 29% of A's when fit on B (v1.1.0 Mahalanobis-only: 71% and 25%).

**Out of range guard.** The model stores the 1st-99th percentile range of each feature. A window with more out of range
features than 95% of training windows (4 of 42) is reported as "not reliable". On the simulator-A stress sets (fresh buildings,
3x noise, climate shifts, no outdoor temperature) it fires for 1% to 5% of windows (`results/identifiability.json`). On simulator B,
for a model trained only on A, it fired for 36%, which is too few: most of B's windows were diagnosed wrongly and not flagged.

**Field validation.** None yet. A pilot protocol is in [PILOT.md](PILOT.md).

**World D and fleet calibration (v1.2.0).** On a third, time stepped simulator the shipped model was never trained on, macro AUROC is
0.705 [0.685, 0.724], any fault 0.648, and 98% of healthy windows are called faulty; the combined guards withhold the ranking for 92% of
those buildings, but the windows they let through score lower (0.618) than the ones they flag (0.756) (`results/world_d.json`,
[WORLD_D.md](research/WORLD_D.md)). New buildings from the training worlds are flagged at 0% (A) and 14% (B) of buildings. A fleet calibrated model
(`deltat-doctor calibrate`) is a separate file with its own card; the bundled model described here is unchanged.

**Knowing when it is wrong (v1.2.1).** Measured per window in [SELECTIVE_PREDICTION.md](research/SELECTIVE_PREDICTION.md): the decision margin (distance
of `p_any` or the top cause probability to 0.5) ranks wrong decisions first at AUROC 0.905 in simulator A and 0.733 in B, but no label free
signal exceeds 0.61 on world D, where the model's entropy is below chance (0.457). As an error signal the open set guard is below chance in world
(0.40 and 0.44) and weak on D (0.583). The model's probabilities are therefore not a reliability measure on an unfamiliar fleet.
