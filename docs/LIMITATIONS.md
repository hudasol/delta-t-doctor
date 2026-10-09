# Limitations

Read this before trusting any number from the tool.

1. **Not validated on real UAE building data.** The model is trained and scored on a physics simulator I
   wrote. Results show how well it recovers faults *that the simulator can produce*. They do not show
   how often it is right on a real building. The only outside check (LBNL, see
   [EXTERNAL_CHECK.md](EXTERNAL_CHECK.md)) has no building-side labels, and one of its three
   predictions failed.
2. **Only variable-flow building loops of the kind simulated.** On the LBNL plant (flow barely follows load, and
   delta-T is about 2.6 C with no fault) the model reports a fault with near-certainty, even when told the design
   delta-T. The tool now counts how many of its 42 measurements fall outside the training range and says "not
   reliable" when too many do. That guard was built after seeing this failure, so it is untested on real ETS data.
   See [EXTERNAL_CHECK.md](EXTERNAL_CHECK.md) sections 4 and 6.
3. **Four causes only.** Fouling, passing valves, constant-flow valves and excess pressure. Control
   problems, sensor errors, bad set-points, pump staging and the plant side are not modelled.
   A fifth cause in a real building will be forced into the closest of the four.
4. **Passing valves and constant-flow valves overlap.** Both leave flow high when load is low. The
   tool says so when both rank highly. Telling them apart needs a site check (close the valves, watch the flow).
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
