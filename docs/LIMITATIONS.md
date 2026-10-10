# Limitations

Read this before trusting any number from the tool.

1. **Not validated on real UAE building data.** The model is trained and scored on a physics simulator I
   wrote. Results show how well it recovers faults *that the simulator can produce*. They do not show
   how often it is right on a real building. The only outside check (LBNL, see
   [EXTERNAL_CHECK.md](EXTERNAL_CHECK.md)) has no building-side labels, and one of its three
   predictions failed.
1b. **Across structurally different simulators it fails.** Trained on one simulator and tested on a second one with different
   hydraulics, macro AUROC is 0.68 (A to B) and 0.77 (B to A), and the A-trained model flags 88% of B's healthy windows. The shipped
   model is trained on both, which helps on those two worlds and says nothing about a third. See [CROSS_SIMULATOR.md](CROSS_SIMULATOR.md).
2. **Only variable-flow building loops of the kind simulated.** On the LBNL plant (flow barely follows load, and
   delta-T is about 2.6 C with no fault) the model reports a fault with near-certainty, even when told the design
   delta-T. The tool now counts how many of its 42 measurements fall outside the training range and says "not
   reliable" when too many do. That guard was built after seeing this failure, so it is untested on real ETS data. Since v1.1 a second, joint-distribution guard also runs (item 10).
   See [EXTERNAL_CHECK.md](EXTERNAL_CHECK.md) sections 4 and 6.
3. **Four causes only.** Fouling, passing valves, constant-flow valves and excess pressure. Control
   problems, sensor errors, bad set-points, pump staging and the plant side are not modelled.
   A fifth cause in a real building will be forced into the closest of the four.
4. **Overflow is the hard cause; the two valve faults are not confused with each other.** In held-out
   buildings with exactly one fault, passing valves are called constant-flow in 2% of cases and the reverse in
   5% (`results/error_analysis.json`). The weak spot is overflow: even for large true gains its recall at p>=0.5
   plateaus near 0.77, because it shares a high low-load flow signature with the valve faults. Weak faults
   (true gain 0.2-0.4 C) are missed about half the time or more. Telling these apart on site needs a valve
   position or differential-pressure reading.
5. **The tariff is a parameter, not a fact.** The 10% per degC below 8.9 C surcharge comes from one operator's
   published FAQ. Contracts differ. The AED rate in the demo (0.40 per RT-hr) is illustrative. Use your
   own contract values before quoting any AED figure.
6. **Savings are model estimates.** They come from a counterfactual run of the simulator and the
   contract terms, not from measured before-and-after data.
7. **Synthetic weather.** Dubai-like monthly means with a daily cycle and noise, not measured data.
8. **Data needs.** At least 14 days of hourly (or finer) supply and return temperature, flow
   (or energy) and ideally outdoor temperature; 30+ days is better. Without outdoor temperature,
   accuracy drops (see the stress results).
9. **Not a substitute for a site survey.** The output is a ranked list of where to look first.
10. **Open-set guard is a simulator-measured estimate.** Fit on A it flags 71% of B; fit on B it flags 25% of A (`results/openset.json`).
    In-world false-flag rate is 6.6% to 7%, so about one in fifteen normal windows is flagged (the building-level test uses the
    median window, which is stricter). On real buildings the rates are unknown.
11. **Evidence is a physics-consistency flag, not proof.** The features and directions are chosen from simulated single-cause
    windows. When two faults are present they can mask each other (the mixed demo shows fouling as "unconfirmed" for this reason).
12. **Trend is confounded by season.** The test uses delta-T at 60-100% load, which is roughly load-matched, but a half-year file
    cannot separate a fault developing from a seasonal shift. It is reported only when it passes a significance and size threshold.
13. **Savings are capped at the surcharge being paid.** Overlapping causes cannot add up to more than the building pays, but the
    per-cause figures are still marginal counterfactuals and are not additive.
14. **Tariff shape.** Only the linear surcharge is modelled (no tiers, deadbands, caps or demand charges).
