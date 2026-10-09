# Cross-simulator test: does it work on a world it was not trained in?

Status: **predictions written 2026-10-10, before the second simulator was built or run.**

## Why

Every earlier "shift" test (3x noise, other climate, other building type, held-out season) changes parameters of the same
generator. The labels, the fault mechanisms and the healthy baseline all come from one author's model, so a high score
shows the classifier recovers that model's functions. A TII-style review (see `docs/ENGINEERING_PLAN.md`) asked for a
structurally different simulator. Simulator B (`src/deltat_doctor/sim/hydraulic.py`) differs from simulator A in these ways:

1. Flow comes from a valve and pump network (equal-percentage valves, valve authority, a differential-pressure set point, a
   minimum controllable valve position). Overflow and passing valves are not injected as flows; they follow from the
   hydraulics.
2. The coil is a wet coil driven by air enthalpy, so humidity (latent load) drives demand, not just dry-bulb temperature.
3. Constant-flow coils are a 3-way mixing valve: the bypass water returns unheated and mixes into the branch return.
4. The ETS plate heat exchanger has a load-dependent approach, so the meter sees the primary side.
5. Extra building classes (hospital, data centre, school), a thermal-mass start-up pulse, a weaker link between load and
   outdoor temperature, and faults that begin part-way through the window.
6. Sensor offsets (supply and return sensors biased by up to 0.25 C each), dropped hours, and a healthy part-load delta-T
   that falls below design as a result of the hydraulics, not a clipped ceiling.

Labels use the same counterfactual rule as A (remove one cause, re-run, gain of 0.20 C or more counts as present).

## Predictions (written first)

| # | Prediction | Would count as a failure of my expectation if |
|---|---|---|
| X1 | Model trained on A, tested on B: macro AUROC at most 0.85, at least 0.12 below its in-A score (0.967) | A to B macro AUROC above 0.85 |
| X2 | Any-fault AUROC A to B stays at or above 0.80 | below 0.80 |
| X3 | On A to B, overflow has the lowest per-cause AUROC and constant-flow the highest | otherwise |
| X4 | The out-of-range guard fires on at least 25% of B windows (against about 5% on A by construction) | below 25% |
| X5 | Trained on B, tested on A: macro AUROC at most 0.85 | above 0.85 |
| X6 | Training on A+B and testing on held-out buildings of each simulator beats A to B by at least 0.05 | smaller gain |
| X7 | Healthy buildings of B are falsely flagged (any-fault probability at or above 0.5) at least 15% of the time by the A model (A's own rate is 3.5%) | below 15% |
| X8 | After randomising A's healthy ceiling to sit below design, the informed model's AUROC gain over blind falls from +0.012 to at most +0.008 | gain stays above +0.008 |

Results are in the section below once run, with every failed prediction reported.
