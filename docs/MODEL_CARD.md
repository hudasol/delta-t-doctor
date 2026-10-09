# Model card

**Task.** For a district-cooled building's ETS meter data, estimate for each of four causes (fouling, passing valves,
constant-flow valves, excess pressure) the probability it is materially present (recovering at least 0.20 C of
delta-T if fixed) and the delta-T it would recover.

**Model.** Calibrated gradient-boosted classifiers and regressors on 42 scale-free shape features, one set per cause,
plus an any-fault classifier. Two variants: blind, and informed (adds the building's design delta-T and the shortfall
against it). Trained with a fixed seed in under a minute.

**Training data.** 5,000 simulated 30-day windows from 500 simulated buildings (office, hotel, residential, mall;
design delta-T 5.0-12.2 C; 6-30 air handlers each). Faults are injected by a coil-level physics simulator, and each
label comes from a counterfactual re-simulation with the cause removed. No real data.

**Evaluation.** On held-out simulated buildings: macro AUROC 0.967 (blind) and 0.979 (informed); calibration, stress and
leave-one-building-type-out results in [results/metrics.md](../results/metrics.md). Reproduce with
`python scripts/evaluate.py`.

**Intended use.** Ranking what to inspect first in a variable-flow building loop fed by district cooling, with the owner
or an engineer checking on site.

**Not for.** Billing disputes, automatic control, plants or chiller loops, constant-flow systems, anything where a wrong
ranking has safety consequences, or buildings the tool marks "not reliable".

**Known failures.**
* On the LBNL chiller-plant benchmark (a different kind of system) it reports a fault with near-certainty, in blind
  and informed modes. See [EXTERNAL_CHECK.md](EXTERNAL_CHECK.md).
* Passing valves and constant-flow valves look alike in meter data.
* Unmodelled causes (controls, sensors, set-points, pump staging) are forced into the nearest of the four.

**Out-of-range guard.** The model stores the 1st-99th percentile range of each feature. A window with more out-of-range
features than 95% of training windows (4 of 42) is reported as "not reliable". On held-out simulated buildings this fires
for 2.5-6% of windows.

**Field validation.** None yet. A pilot protocol is in [PILOT.md](PILOT.md).
