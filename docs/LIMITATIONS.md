# Limitations

Read this before trusting any number from the tool.

1. **Not validated on real UAE building data.** The model is trained and scored on a physics simulator I
   wrote. Results show how well it recovers faults *that the simulator can produce*. They do not show
   how often it is right on a real building. The only outside check (LBNL simulated plant data, see
   [EXTERNAL_CHECK.md](EXTERNAL_CHECK.md)) has no building-side labels; 3 of its 5 predictions failed, 1 was not supported and 1 passed only
   on a technicality. The only contact with real meter data (district heating, no labels, [REAL_DATA_CONTACT.md](REAL_DATA_CONTACT.md))
   measures refusal and abstention, not accuracy.
2. **Across structurally different simulators it fails, and the fixes I tried do not close the gap.** Trained on one simulator and tested on a second one with different
   hydraulics, macro AUROC is 0.68 (A to B) and 0.77 (B to A), and the A-trained model flags 88% of B's healthy windows. The shipped
   model is trained on both, which helps on those two worlds and says nothing about a third. See [CROSS_SIMULATOR.md](CROSS_SIMULATOR.md).
   Domain randomised training worlds, invariant feature selection and target batch standardisation were tested: best 0.715 and 0.784, not a fix
   ([TRANSFER_V2.md](TRANSFER_V2.md)). What does work is calibrating on surveyed target buildings: about 20 lift the weak direction to 0.800 and
   40 to 0.836 (the preregistered target of 0.84 was missed narrowly; simulator to simulator; real fleets may differ). On a third, dynamic
   simulator (world D, [WORLD_D.md](WORLD_D.md)) the shipped model scores 0.705 zero shot and calls 98% of healthy windows faulty.
3. **Only variable-flow building loops of the kind simulated.** On the LBNL plant (flow barely follows load, and
   delta-T is about 2.6 C with no fault) the model reports a fault with near-certainty, even when told the design
   delta-T. The tool now counts how many of its 42 measurements fall outside the training range and says "not
   reliable" when too many do. That guard was built after seeing this failure, so it is untested on real ETS data. Since v1.1 a second, joint-distribution guard also runs (item 11).
   See [EXTERNAL_CHECK.md](EXTERNAL_CHECK.md) sections 4 and 6.
4. **Four causes only.** Fouling, passing valves, constant-flow valves and excess pressure. Control
   problems, sensor errors, bad set-points, pump staging and the plant side are not modelled.
   A fifth cause in a real building will be forced into the closest of the four.
5. **Overflow is the hard cause; the two valve faults are not confused with each other.** In held-out
   buildings with exactly one fault, passing valves are called constant-flow in 3% of cases and the reverse in
   4% (`results/error_analysis.json`). The weak spot is overflow: its recall at p>=0.5 is 0.28, 0.45, 0.67 and 0.80 for true gains of
   0.2 to 0.4, 0.4 to 0.8, 0.8 to 1.6 and above 1.6 C, because it shares a high low-load flow signature with the valve faults. Within one physics it is found at about 0.92 AUROC;
   the real problem is transfer, where it falls to 0.53 to 0.56 (chance; 0.547 on world D), so it stays capped at "possible" ([OVERFLOW.md](OVERFLOW.md)).
   World D can produce valve hunting, but at a period of about ten minutes the hourly meter averages it out, and hourly temporal features did not
   help overflow in an unseen world ([WORLD_D.md](WORLD_D.md)). Weak faults
   (true gain 0.2-0.4 C) are missed about half the time or more. Telling these apart on site needs a valve
   position or differential-pressure reading.
6. **The tariff is a parameter, not a fact.** The 10% per degC below 8.9 C surcharge comes from one operator's
   published FAQ. Contracts differ. The AED rate in the demo (0.40 per RT-hr) is illustrative. Use your
   own contract values before quoting any AED figure.
7. **Savings are model estimates.** They come from a counterfactual run of the simulator and the
   contract terms, not from measured before-and-after data.
8. **Synthetic weather.** Dubai-like monthly means with a daily cycle and noise, not measured data.
9. **Data needs.** At least 14 days of hourly (or finer) supply and return temperature, flow
   (or energy) and ideally outdoor temperature; 30+ days is better. Without outdoor temperature,
   accuracy drops (see the stress results).
10. **Not a substitute for a site survey.** The output is a ranked list of where to look first.
11. **Open-set guard is a simulator-measured estimate.** Since v1.1.1 it averages a Mahalanobis score and a nearest-neighbour score. Fit on A it flags 64% of
    B's windows; fit on B it flags 29% of A's (`results/openset.json`; v1.1.0's Mahalanobis-only guard gave 71% and 25%). The asymmetry is partly structural:
    B's wider envelope contains much of A's behaviour, so A looks "in range". I tried six detectors (`results/openset_v2.json`); none is strong in both directions.
    In-world false-flag rate is 5.5% to 6% on clean held out windows, so about one in fifteen normal windows is flagged (the building-level test uses the
    median window, which is stricter). It is much higher under degraded input: 42% of windows with 2 hourly data, 22% with 3x sensor noise, 16%
    without outdoor temperature (`results/openset.json`), and 24% of windows (14% of buildings) from freshly generated simulator B buildings
    (`results/world_d.json`), so "hourly or 2 hourly is enough" holds for the parser, not for the guard. **The guard detects unfamiliar
    buildings; it does not pick out the model's mistakes**: on world D the windows it lets through score 0.618 macro AUROC, lower than the 0.756
    of the windows it flags. On real chilled water buildings the rates are unknown.
12. **Evidence is a physics-consistency flag, not proof.** The features and directions are chosen from simulated single-cause
    windows. When two faults are present they can mask each other (the mixed demo shows fouling as "unconfirmed" for this reason).
13. **Trend is confounded by season.** The test uses delta-T at 60-100% load, which is roughly load-matched, but a half-year file
    cannot separate a fault developing from a seasonal shift. It is reported only when it passes a significance and size threshold.
14. **Savings are capped at the surcharge being paid.** Overlapping causes cannot add up to more than the building pays, but the
    per-cause figures are still marginal counterfactuals and are not additive.
15. **Tariff shape.** Only the linear surcharge is modelled (no tiers, deadbands, caps or demand charges).
16. **Reproducibility of the training data is partial.** The simulator A pool regenerates to the same numbers (the shipped model's stored
    training percentiles match to 4e-15; `results/regeneration_check.json`) but not to the same file hash. The seed used for the committed
    simulator B pool was not recorded, so that pool cannot be regenerated from the repository; it is committed as is.
17. **Fleet calibration is measured in simulation only**, on 12 held out buildings of a pretend fleet (`results/calibrate_check.json`): macro
    AUROC rose from 0.782 to 0.833 but overflow fell (0.81 to 0.66) and abstention stayed at 58%. Small holdouts give noisy figures.
