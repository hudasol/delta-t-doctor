# Why overflow is capped at "possible", and what would lift the cap

Status: **predictions written before the analysis ran.** Script: `scripts/overflow_analysis.py`, output `results/overflow_analysis.json`.

Overflow (a loop pressure set point above need, or oversized valves) adds flow at part load at a low ΔT. From ETS meter data alone
(flow, heat, ΔT, outdoor temperature) that looks like passing valves (extra flow with little heat) and constant flow (valve stuck open).
This note measures how separable it is, rather than asserting it.

## Predictions

| # | Prediction | Failure if |
|---|---|---|
| W1 | In world, overflow is the weakest or second weakest cause (AUROC vs all others) in both simulators | it ranks first or second best |
| W2 | Among single-fault windows, overflow versus passing valves is the hardest pair (lowest AUROC of overflow's three pairings) in both worlds | another pair is lower in either world |
| W3 | Overflow in single-fault windows scores at least 0.05 AUROC higher than in windows where it co-occurs with another fault | gap is under 0.05 in either world |
| W4 | Adding a *measured* loop differential pressure (a simulated, noisy channel, 10% error) lifts in world overflow AUROC above 0.95 in both worlds | stays below 0.95 in either |
| W5 | The same DP-aware model, trained in one world and tested in the other, reaches overflow AUROC above 0.85 (the meter-only model gets 0.53 to 0.56) | stays below 0.85 |

W4 and W5 are a ceiling test, not a product claim: the simulator's DP channel is generated from the same variable that defines the
fault, so a high value shows the information is sufficient, not that real DP data will behave. It tells us whether collecting DP is worth
asking for in a pilot.

## Results (`results/overflow_analysis.json`)

Held out buildings, first of five building grouped folds, one gradient-boosted detector per cause on the meter-derived shape features.

| Measure | World A | World B |
|---|---|---|
| Overflow vs everything else, in world AUROC | 0.918 | 0.914 |
| Weakest cause in world | overflow (others 0.97 to 0.99) | fouling 0.700, then overflow |
| Overflow alone (single fault) vs negatives | 0.979 | 0.929 |
| Overflow co-occurring with another fault vs negatives | 0.852 | 0.885 |
| Overflow vs fouling / passing valves / constant flow (single-fault windows) | 0.955 / 0.960 / 0.990 | 0.940 / 0.903 / 0.823 |
| Ceiling with a simulated DP channel: in world | 0.998 | 0.995 |
| Ceiling with a simulated DP channel: trained in the other world | 0.998 (B to A: 0.989) | |
| Meter-only, trained in the other world (from `docs/TRANSFER_V2.md`) | 0.555 (A to B) | 0.532 (B to A) |

| # | Outcome | Verdict |
|---|---|---|
| W1 | Weakest in A, second weakest in B | Held |
| W2 | Hardest pair is fouling in A, constant flow in B; passing valves is not the hardest in either | **Failed** |
| W3 | Gap 0.126 in A, 0.044 in B (needed 0.05 in both) | **Failed** narrowly in B |
| W4 | 0.998 and 0.995 | Held (by construction, see below) |
| W5 | 0.998 and 0.989 | Held (by construction, see below) |

### What this changes in the product's position

1. **The cap is not because overflow is invisible.** Inside one physics it is found at about 0.91 AUROC, comparable to the other causes.
   The weakness is that the learned signature **does not carry across physics** (0.53 to 0.56, which is chance). The earlier wording, "overflow
   barely shows up in meter data", was too strong and is corrected in `docs/LIMITATIONS.md`.
2. **Why the cap stays.** A pilot building is a third physics. Until the model has been calibrated on that fleet it is in the 0.53 to 0.56
   regime for overflow, so "possible" is the right tier. The few shot curve (`docs/TRANSFER_V2.md`) shows overflow reaches 0.76 to 0.78 with
   20 surveyed buildings and 0.83 to 0.86 with 40 to 50.
3. **The DP ceiling is circular and I am not claiming it.** The DP channel in this test is generated from the fault label, so near-1.0 AUROC only
   shows that a measured loop pressure would be sufficient information, not what real DP data will do. It does justify one concrete ask in the pilot data
   request: loop differential pressure (or pump speed) at the building, where the BMS has it.
4. **Hunting features were not tested.** Both simulators produce overflow as a steady extra part load flow, with no oscillation dynamics. A
   high-frequency "hunting" feature could only be validated on data I would have to invent, so I did not build one. It remains a candidate for the
   real data pilot.

Product decision: keep overflow at "possible" (no behaviour change). Record what would lift it: local calibration on about 20 to 40 labelled buildings
(`scripts/evaluate_real.py` measures when that is met) or a measured DP channel confirmed on real data.
