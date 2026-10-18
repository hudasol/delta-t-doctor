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

## Deviations from the protocol (written before the results below)

The machine this ran on was shared and heavily loaded (CPU at 100% and memory paging for hours; generating the 1500 D windows took 3.6 hours).
To finish inside the night I changed three things, all before seeing the results they affect:

1. **Few shot curve narrowed** to k in {0, 20, 40} (three draws each) instead of {0, 5, 10, 20, 40}. D8 and D9 only need k = 20 and 40.
2. **In world temporal comparison run on D only.** D11 (in world A and B) was not run and is scored "not run".
3. **The B pool for the temporal comparison** is a pool regenerated with the temporal block (seed 11, `results/data_b_t`). It is not identical
   to the committed B pool: the seed of the committed pool was never recorded, which this check exposed (`results/regeneration_check.json`).
   The design section above said the regenerated pools "must come out identical"; for A they do numerically (training percentiles match to
   4e-15), for B they do not. Both arms of every temporal comparison use the same rows, so the comparison is still fair; it is not a
   comparison on the shipped model's own B rows.

Everything else follows the protocol: zero shot and guard use the shipped model and the committed D set; few shot trains on the committed A and
B pools plus D buildings, exactly as `scripts/transfer_fewshot.py` does for A and B.

## Results

Data: 1500 D windows from 150 buildings; 42% of windows have no material cause; flow weighted delta T 4.1, 8.5 and 14.4 C at the 5th, 50th
and 95th percentile; cause prevalence fouling 26%, passing valves 10%, constant flow 25%, overflow 18% (`results/world_d.json`, `data`).

**1. Shipped model, zero shot** (`scripts/world_d_eval.py zeroshot`; building bootstrap, 1000 resamples):

| measure | value [95% interval] |
|---|---|
| macro AUROC | 0.705 [0.685, 0.724] |
| any fault AUROC | 0.648 [0.609, 0.686] |
| fouling / passing valves / constant flow / overflow | 0.577 [0.536, 0.618] / 0.833 [0.802, 0.860] / 0.865 [0.840, 0.888] / 0.547 [0.510, 0.586] |
| healthy false alarm (p_any at least 0.5, 635 healthy windows) | 98% |

**2. Shipped guards** (`guard`): world D 73% of windows and **92% of buildings** withheld (open set 79%, box 78% of buildings). Fresh in world
sets: simulator A 2.7% of windows and 0% of 80 buildings; simulator B 24% of windows and **14% of 80 buildings**. On D, the windows the open set
guard lets through score macro AUROC **0.618**, the windows it flags **0.756**.

**3. Few shot** (`fewshot`; macro AUROC on 70 held out D buildings, mean of 3 draws):

| k D buildings | macro AUROC | healthy false alarm | fouling | passing valves | constant flow | overflow |
|---|---|---|---|---|---|---|
| 0 | 0.709 | 99% | 0.573 | 0.850 | 0.869 | 0.544 |
| 20 | 0.825 (sd 0.002) | 26% | 0.869 | 0.883 | 0.949 | 0.599 |
| 40 | 0.850 (sd 0.007) | 21% | 0.915 | 0.904 | 0.965 | 0.614 |

**4. Temporal block** (`temporal`, `results/world_d_temporal.json`). Leave one world out, AUROC without and with the six temporal features:

| held out world (trained on) | fouling | passing valves | constant flow | overflow | macro |
|---|---|---|---|---|---|
| D (A + B) | 0.544 to 0.515 | 0.804 to 0.815 | 0.853 to 0.878 | 0.553 to 0.558 | 0.689 to 0.692 |
| B (A + D) | 0.577 to 0.577 | 0.673 to 0.653 | 0.874 to 0.896 | 0.493 to 0.509 | 0.654 to 0.659 |
| A (B + D) | 0.708 to 0.717 | 0.724 to 0.664 | 0.980 to 0.981 | 0.503 to 0.523 | 0.729 to 0.721 |

In world on D (building grouped 5 fold CV, 42 features against 42 + 6): 0.968 to 0.968 | 0.934 to 0.932 | 0.974 to 0.976 | 0.703 to 0.714 (fouling, passing valves, constant flow, overflow); macro 0.895 to 0.897. Even inside the world that contains hunting, the hourly features add only +0.010 to overflow.

Shipping rule: part (a) is met once (overflow +0.020 when A is held out), part (b) fails (passing valves fall by 0.060 on A and 0.019 on B,
fouling by 0.029 on D). **The temporal block is not shipped**; `src/deltat_doctor/temporal.py` stays as an optional, unused module and this is
recorded as a negative result.

### Predictions scored

| # | Outcome | Verdict |
|---|---|---|
| D1 | 0.705 | Held |
| D2 | 98% | Held |
| D3 | 0.547 | Held |
| D4 | 0.648 | Held |
| D5 | 92% of buildings | Held |
| D6 | A 0%, B 14% of buildings (limit 10%) | **Failed** (B) |
| D7 | unflagged 0.618 against flagged 0.756: the opposite direction | **Failed** |
| D8 | k = 20: 0.825 (needed 0.80); k = 40: 0.850 (needed 0.84) | Held |
| D9 | 26% at k = 20 (needed below 30%) | Held |
| D10 | overflow 0.703 to 0.714 (+0.010; needed +0.02) | **Failed** |
| D11 | not run (deviation 2) | Not run |
| D12 | overflow +0.005 on D | Held |
| D13 | rule fails on part (b) | Held |

### What this changes

* **The transfer claim holds on a third physics.** An unseen world gives 0.705, inside the 0.68 to 0.77 seen between A and B, with almost every
  healthy building called faulty. The product's honest position does not change: zero shot probabilities on a new fleet are not trustworthy.
* **The guard claim needs a correction.** The guards do withhold most unseen world buildings (92%). But they are novelty detectors, not error
  detectors: on D they pass the windows the model handles worse. So "the system refuses rather than guesses" is true for unfamiliar buildings,
  and **an answered building from an unfamiliar fleet is not more likely to be right**. README, LIMITATIONS and the Edge proposal now say so.
  The guard also flags 14% of new buildings from simulator B, its own training world, so the in world false flag figure of 5.5% to 6% holds only
  for windows like the training ones.
* **Few shot adaptation transfers to D**: 20 labelled D buildings lift macro AUROC from 0.71 to 0.83 and 40 to 0.85, and
  cut healthy false alarms from 99% to 26% and 21%, slightly above the A to B curve. Overflow is the exception: 0.60 at 20 and 0.61 at 40. This supports fleet calibration as a product step.
* **Hourly temporal features do not rescue overflow.** World D's hunting has a period of about ten minutes; the hourly meter averages it out.
  Detecting hunting would need sub hourly data, which is a data request for the pilot, not a model change.

## Follow up (v1.2.1): the cut experiments

Status: **predictions written 2026-10-18, before these runs.** Same scripts and protocol as above: `scripts/world_d_eval.py fewshot` with the
environment variable `DTD_KS` set to `5,10,70` (in PowerShell: `$env:DTD_KS="5,10,70"`; same 70 test buildings, same three draws per k, seeds 100 to 102), written to `results/world_d_fewshot_followup.json`; and
`scripts/world_d_eval.py temporal` in world A and B (`DTD_TEMPORAL_INWORLD` set to `A,B`), written to `results/world_d_temporal_followup.json`, which
scores the already preregistered D11. The B pool for the temporal comparison is again the seed 11 pool (deviation 3 above).

| # | Prediction | Failure if |
|---|---|---|
| E1 | k = 5: macro AUROC at least 0.74 | below 0.74 |
| E2 | k = 10: macro AUROC between 0.76 and 0.82 | outside |
| E3 | k = 70: macro AUROC at least 0.86, and the gain from k = 40 (0.850) to k = 70 is at most 0.03 | either part fails |
| E4 | Overflow stays below 0.70 at every k up to 70 | 0.70 or above at any k |
| E5 | In world A and B the temporal block changes no other cause by more than 0.01 | a change above 0.01 for any of fouling, passing valves, constant flow |

D11 (written before the v1.2.0 run, unchanged): "In world on A and on B, the temporal block changes overflow AUROC by less than 0.01".

### Follow up results: few shot (`results/world_d_fewshot_followup.json`, run 2026-10-18 04:05 to 04:10)

Macro AUROC on the same 70 held out D buildings, mean of three draws, joined with the v1.2.0 points:

| k D buildings | macro AUROC | healthy false alarm | fouling | passing valves | constant flow | overflow |
|---|---|---|---|---|---|---|
| 0 | 0.709 | 99% | 0.573 | 0.850 | 0.869 | 0.544 |
| 5 | 0.762 (sd 0.002) | 50% | 0.732 | 0.849 | 0.912 | 0.555 |
| 10 | 0.798 (sd 0.001) | 35% | 0.807 | 0.868 | 0.940 | 0.576 |
| 20 | 0.825 | 26% | 0.869 | 0.883 | 0.949 | 0.599 |
| 40 | 0.850 | 21% | 0.915 | 0.904 | 0.965 | 0.614 |
| 70 | 0.869 (sd 0.003) | 16% | 0.942 | 0.918 | 0.968 | 0.646 |

| # | Outcome | Verdict |
|---|---|---|
| E1 | k = 5: 0.762 | Held |
| E2 | k = 10: 0.798 | Held |
| E3 | k = 70: 0.869; gain from k = 40 is 0.019 | Held |
| E4 | overflow at most 0.646 (k = 70) | Held |

The curve is smooth and flattens after about 40 buildings. Healthy false alarms fall fastest: from 99% to 35% with 10 labelled buildings.
Overflow barely moves (0.54 to 0.65 over the whole curve), so even a calibrated fleet model should keep overflow at "possible".
