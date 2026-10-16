# World D: a third, independent physics

Status: **design and predictions written 2026-10-16, before world D had produced a single dataset and before any evaluation code
was run.** This document and the simulator (`src/deltat_doctor/sim/world_d.py`) are committed first; results are appended below
the line marked "Results" and the predictions are not edited afterwards.

## Why a third world

Every transfer and guard figure in this repository comes from two simulators, A and B, both written by the same author. The shipped
model is trained on both, so its behaviour on either says nothing about a building it has not seen. A third world that was not
designed by looking at A and B, and that has a different model structure, is the closest available stand in for "a building the
model has not seen" until real labelled data exist. It is still simulation and still written by the same author, so it reduces the
circularity; it does not remove it.

## Design

World D is **time stepped and closed loop** where A and B are quasi steady (each hour solved on its own). The meter sees the
result of control dynamics, not a fault formula.

| Part | World A | World B | World D |
|---|---|---|---|
| Time | each hour independent | each hour independent | 5 minute steps with state, 48 hour warm up, averaged to the hourly meter |
| Demand | prescribed load fraction from weather and schedule | air enthalpy, VAV fan, start up | zone thermal mass (time constant 1 to 6 h); demand is whatever the coil removes while control holds the set point |
| Valve control | ideal: flow that exactly meets demand | ideal on an equal percentage valve with a floor | cascade: zone reset (1 to 3 K per K) sets a discharge air set point; a digital PI with a 5 minute scan (gain 0.03 to 0.12 per K, integral time 3 to 15 min) drives the valve through a sensor lag (1 to 4 min), an actuator lag (1 to 8 min) and a deadband (0.5% to 4%); 40% linear valves, 60% equal percentage |
| Coil | effectiveness NTU, sensible | effectiveness NTU on enthalpy (wet coil) | characteristic curve: capacity proportional to (flow / design flow) to a power 0.35 to 0.6 and to the entering temperature difference |
| Pressure | none (overflow is a flow term) | set point ratio moves valve floor | variable speed pump holding a DP set point; at minimum speed (30% to 55%) the pump curve sets the pressure, so pressure rises at low flow; valve flow scales with the square root of pressure |
| ETS | fixed loss on delta T | load dependent approach | counterflow plate exchanger (NTU 2.5 to 6); primary flow set so the secondary leaves at its set point; meter on the primary side |
| Building types | office, hotel, residential, mall | adds hospital, data centre, school | office, hotel, residential, mall, school, clinic, with its own schedules |

Faults, each acting on a component rather than added as a flow term:

* **fouling**: coil capacity divided by (1 + f), f from 0.2 to 1.5 on 30% to 100% of coils. The controller opens further to compensate.
* **passing valves**: a shut valve still passes 3% to 20% of its capacity, scaled by the square root of the pressure. On an idle coil
  (fan off) that water exchanges almost no heat.
* **constant flow**: a 3-way valve (the branch passes design flow at design pressure; coil flow is modulated and the bypass returns
  supply water) or an actuator stuck at 40% to 100%.
* **overflow**: the DP set point is 1.4 to 2.6 times what the index branch needs, and in half the cases some valves are also oversized by
  a factor 1.2 to 1.8. Higher pressure raises the valve's flow gain, which can push the PI loop into a limit cycle (hunting) at low load,
  and raises the minimum controllable flow. Whether a given building hunts is not set by hand; it follows from its gains, lags,
  deadband and pressure.

Labels are counterfactual as in A and B: the window is simulated again with one cause removed and the same drivers, and a cause is
"present" when removing it recovers at least 0.20 C of flow weighted delta T. Shared with A and B: the synthetic Dubai like outdoor
temperature, the counterflow effectiveness formula (used here only for the plate exchanger), the 0.20 C threshold and the record format.

Generated through the same interface: `generate(..., sim="D")` and `python scripts/generate_data.py --sim D`.

## Mechanism check before commit (no model involved)

The brief requires that overflow in D can produce hunting. Before committing I ran a mechanism check on 8 buildings (one January week each,
healthy against a DP set point 2.4 times need, flow only; no model, no labels). My first design put the PI loop on zone temperature;
it produced **no** oscillation at any scale (relative step to step flow change 0.02 to 0.04 in both variants), because a loop on slow zone
temperature is well damped. I replaced it with the standard AHU cascade above (fast discharge air loop under a slow zone reset, some linear
valves), with gains and lags chosen from typical commissioning ranges, not adjusted afterwards. The check then showed hunting appear with excess pressure in 2 of 8
buildings (relative 5 minute flow change from 0.03 to 0.13 and from 0.02 to 0.14), one healthy building that already hunted (0.10) and got
worse (0.15), and a smaller rise in two more (about 0.02 to 0.035). Where hunting appeared, flow weighted delta T was 0.4 to 0.6 C lower. **At the hourly meter the same buildings show no change in hour to hour flow movement** (0.094 against
0.085, 0.163 against 0.161): the oscillation period is around ten minutes and the hourly average removes it. I saw this before committing the
predictions below; I did not change them. It bears directly on D10.

## Datasets and protocol

* **D**: 150 buildings x 10 windows = 1500 windows, seed 21, with the optional temporal block (`temporal=True`).
* **A** and **B**: the existing training pools (A: 500 x 10, seed 11; B: 150 x 10), regenerated with the temporal block. The 42 shape
  features must come out identical to the stored ones, which is checked before use.
* **Fresh in world sets** for the guard's false flag rate: fresh A (80 x 6, seed 1000, the existing `stress_fresh` recipe) and fresh B
  (80 x 6, seed 2000).
* Intervals are 95% building grouped bootstrap intervals (1000 resamples of whole buildings).

Evaluation order, written to `results/world_d.json` by `scripts/world_d_eval.py`:

1. The shipped model on D, zero shot: macro AUROC, per cause AUROC, any fault AUROC, healthy false alarm (p_any at least 0.5 on windows with
   no present cause).
2. The shipped guard on D: share of windows flagged and share of buildings flagged by the open set guard, the per feature box and the
   combination the product uses (abstain if either fires; building level uses the median window score as in `diagnose.py`). The same on
   the fresh in world sets gives the false flag rate.
3. Few shot on D: train on A + B (the shipped recipe) plus k whole D buildings repeated 5 times, k in {0, 5, 10, 20, 40}, three draws of the
   k buildings, 70 fixed D test buildings. This copies the logic of `scripts/transfer_fewshot.py` without changing that script.
4. Temporal features (`src/deltat_doctor/temporal.py`, six features from the hourly flow series, written before any D data existed):
   * in world, building grouped 5 fold CV in each of A, B and D, 42 features against 42 + 6;
   * leave one world out in all three directions (A + B to D, A + D to B, B + D to A), 42 against 42 + 6.

**Shipping rule for the temporal block, fixed now.** It ships as an optional feature block only if (a) in at least one leave one world out
direction it raises overflow AUROC on the held out world by at least 0.02, and (b) in no leave one world out direction does any other
cause's AUROC fall by more than 0.01. Otherwise it stays in `scripts/` and `temporal.py` as a documented negative result and the product
does not use it.

## Predictions

| # | Prediction | Failure condition |
|---|---|---|
| D1 | Zero shot macro AUROC of the shipped model on D is between 0.60 and 0.80 | outside that range |
| D2 | Zero shot healthy false alarm on D is at least 30% | below 30% |
| D3 | Zero shot overflow AUROC on D is at most 0.65 | above 0.65 |
| D4 | Zero shot any fault AUROC on D is below 0.80 | 0.80 or above |
| D5 | The shipped guard (box or open set, as the product combines them) flags at least 30% of D buildings | below 30% |
| D6 | The shipped guard flags at most 10% of fresh in world buildings (A and B, each) | above 10% in either |
| D7 | On D, windows the shipped open set guard does not flag have a macro AUROC at least 0.03 higher than windows it flags | difference below 0.03 |
| D8 | Few shot: with 20 D buildings macro AUROC is at least 0.80, with 40 at least 0.84 | below either |
| D9 | Few shot: healthy false alarm on D falls below 30% at 20 D buildings | 30% or above |
| D10 | In world on D, the temporal block raises overflow AUROC by at least 0.02 | gain below 0.02 |
| D11 | In world on A and on B, the temporal block changes overflow AUROC by less than 0.01 (neither has dynamics) | change of 0.01 or more in either |
| D12 | Leave one world out A + B to D, the temporal block raises overflow AUROC on D by less than 0.02 | gain of 0.02 or more |
| D13 | The temporal block fails the shipping rule | it passes |

D10 to D13 together say what I expect: the temporal features see hunting where hunting exists, but a model cannot learn that signature
from worlds that do not contain it, so the block cannot help a world it was not trained on. If D12 fails, that would be the more
interesting result.

## Results

(appended after the run)
