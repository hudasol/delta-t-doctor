# Cross simulator test: does it work on a world it was not trained in?

Status: **predictions written 2026-10-10, before the second simulator was built or run.**

## Why

Every earlier "shift" test (3x noise, other climate, other building type, held out season) changes parameters of the same
generator. The labels, the fault mechanisms and the healthy baseline all come from one author's model, so a high score
shows the classifier recovers that model's functions. A research methodology review pass (see `docs/research/ENGINEERING_PLAN.md`) asked for a
structurally different simulator. Simulator B (`src/deltat_doctor/sim/hydraulic.py`) differs from simulator A in these ways:

1. Flow comes from a valve and pump network (equal-percentage valves, valve authority, a differential-pressure set point, a
   minimum controllable valve position). Overflow and passing valves are not injected as flows; they follow from the
   hydraulics.
2. The coil is a wet coil driven by air enthalpy, so humidity (latent load) drives demand, not just dry-bulb temperature.
3. Constant flow coils are a 3-way mixing valve: the bypass water returns unheated and mixes into the branch return.
4. The ETS plate heat exchanger has a load dependent approach, so the meter sees the primary side.
5. Extra building classes (hospital, data centre, school), a thermal-mass start-up pulse, a weaker link between load and
   outdoor temperature, and faults that begin part-way through the window.
6. Sensor offsets (supply and return sensors biased by up to 0.25 C each), dropped hours, and a healthy part load delta T
   that falls below design as a result of the hydraulics, not a clipped ceiling.

Labels use the same counterfactual rule as A (remove one cause, re-run, gain of 0.20 C or more counts as present).

## Predictions (written first)

| # | Prediction | Would count as a failure of my expectation if |
|---|---|---|
| X1 | Model trained on A, tested on B: macro AUROC at most 0.85, at least 0.12 below its in-A score (0.967) | A to B macro AUROC above 0.85 |
| X2 | Any fault AUROC A to B stays at or above 0.80 | below 0.80 |
| X3 | On A to B, overflow has the lowest per cause AUROC and constant flow the highest | otherwise |
| X4 | The out of range guard fires on at least 25% of B windows (against about 5% on A by construction) | below 25% |
| X5 | Trained on B, tested on A: macro AUROC at most 0.85 | above 0.85 |
| X6 | Training on A+B and testing on held out buildings of each simulator beats A to B by at least 0.05 | smaller gain |
| X7 | Healthy buildings of B are falsely flagged (any fault probability at or above 0.5) at least 15% of the time by the A model (A's own rate is 3.5%) | below 15% |
| X8 | After randomising A's healthy ceiling to sit below design, the informed model's AUROC gain over blind falls from +0.012 to at most +0.008 | gain stays above +0.008 |

Results are in the section below once run, with every failed prediction reported.

## Results (run after the predictions above; raw tables in `results/cross_simulator.md`)

Simulator A: 5,000 windows from 500 buildings. Simulator B: 1,500 windows from 150 buildings. Macro AUROC with a building level
bootstrap interval where computed.

| setting | macro AUROC | any fault AUROC | fouling | passing valves | constant flow | overflow |
|---|---|---|---|---|---|---|
| within A (grouped CV) | 0.966 | 0.990 | 0.988 | 0.964 | 0.995 | 0.919 |
| within B (grouped CV) | 0.884 | 0.935 | 0.675 | 0.965 | 0.970 | 0.924 |
| **train A, test B** | **0.683** [0.655, 0.710] | 0.704 | 0.633 | 0.740 | 0.858 | 0.502 |
| **train B, test A** | **0.770** [0.760, 0.778] | 0.870 | 0.889 | 0.678 | 0.966 | 0.545 |
| train A+B, test A (grouped CV) | 0.965 | 0.989 | 0.986 | 0.962 | 0.995 | 0.915 |
| train A+B, test B (grouped CV) | 0.877 | 0.931 | 0.697 | 0.958 | 0.965 | 0.887 |

| transfer | calibration error (ECE) | windows flagged out of range | healthy buildings falsely flagged (p>=0.5) | logistic baseline macro AUROC |
|---|---|---|---|---|
| A to B | 0.159 | 36% | 88% (of 628) | 0.658 |
| B to A | 0.072 | 7% | 25% (of 1,633) | 0.749 |

### Scorecard against the predictions

| # | Outcome |
|---|---|
| X1 | **Held, by a wide margin.** A to B macro AUROC 0.683, 0.28 below within-A |
| X2 | **Failed.** I expected any fault AUROC to stay at or above 0.80; it fell to 0.704. The model cannot reliably tell a faulty B building from a healthy one |
| X3 | **Held.** Overflow is the lowest (0.502, chance) and constant flow the highest (0.858) |
| X4 | **Held.** The guard flagged 36% of B windows (against 1-5% on simulator A's stress sets) |
| X5 | **Held.** B to A macro AUROC 0.770 |
| X6 | **Held, with a caveat.** Pooled training scores 0.877 on held out B buildings against 0.683 for A alone, but the pooled model has seen B-style buildings, so this is not another unseen world |
| X7 | **Held, far worse than I predicted.** 88% of B's healthy windows were flagged as faulty by the A-trained model |
| X8 | **Held.** Once healthy buildings may run below design, the informed model's gain over blind fell from +0.012 to +0.005 macro AUROC (0.971 against 0.966) |

### What this means

* The headline 0.966 is a within-simulator number. On a structurally different simulator the same model gets 0.68 and calls most
  healthy buildings faulty. Real buildings are a third, different world, so expect the unseen-world numbers, not the headline.
* The out of range guard caught only about a third of the B windows that the model got wrong. It is useful, not sufficient.
* Both directions fail on overflow (0.50 and 0.55). In B a passing valve only costs delta T in a building that is idle part of
  the time, because a leak through a running coil exchanges heat; in A it always does. The two simulators encode different
  physics for the same fault, and meter data cannot decide which a real building follows.
* Fouling is hard inside B too (0.675): its effect there shows up mainly at high load, so it is easy to confuse with healthy part load behaviour.
* Training on both simulators removes most of the gap on the simulators it has seen, so the shipped model is trained on both. That makes the
  reported within-simulator numbers look slightly better than they would for a stranger and does nothing to show how it will do on a field site.
  The honest estimate for an unseen world remains the 0.68 to 0.77 above (0.67 to 0.76 on four regenerated B pools, `docs/research/REPRODUCIBILITY.md`).
* Nearest-neighbour test (`results/identifiability.json`): even inside a simulator, windows with exactly one cause have a nearest
  neighbour with a different cause 16% of the time for passing valves against overflow in A, and 18% to 21% for overflow against
  fouling or constant flow in B. Overflow is the cause that meter data alone separates least well.
* The pooled model still marks the LBNL chiller plant as not reliable (10.75 of 42 features out of range against a limit of 4) and still
  calls it faulty with probability 0.998, so the LBNL failure stands.

### What would change this

Labelled field data from the pilot (docs/PILOT.md). A third simulator written by a different person. Valve-position or differential-pressure
channels, which would separate overflow and passing valves directly.
