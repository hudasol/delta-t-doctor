# delta-t-doctor

**Find out why a district-cooled building returns water that is too cool, and which fix to try first, using only the utility meter data it already has.**

![The diagnosis screen for a simulated building with fouled coils](docs/img/ui_fouled.png)

> **Status: a research prototype validated in simulation.** Trained and tested on a physics simulator.
> It has **not** been validated on real UAE building data, one prediction in the external check failed, and a cross-simulator
> test showed it generalises poorly to a differently built simulator (see [Results](#results) and [Limitations](docs/LIMITATIONS.md)). Treat its output as a ranked inspection list.

Product plan, market research and roadmap: [plan.md](plan.md). Draft pilot protocol: [docs/PILOT.md](docs/PILOT.md).

## The problem

District cooling supplies chilled water to buildings through an energy transfer station (ETS). The
plant is sized for the water coming back warm. When a building returns it too cool, the plant moves more water for
the same cooling. This is called low delta-T syndrome. Operators put the burden on the building owner: for
example, Emicool's published FAQ says the owner must maintain a delta-T of 8.9 C, with a surcharge of **10% on the
consumption charge for each degree Celsius below it** ([source](https://www.emicool.com/en/faq)). Contracts
vary.

The owner sees the surcharge on a bill but not the cause. Typical causes are fouled coils, leaking valves on
idle air handlers, 3-way valves that pass full flow, and excess differential pressure. Finding which one applies
is a consultant-led site survey. I found no self-serve tool that does this from meter data.

## What it does

Upload a CSV from the ETS meter (timestamp, flow, supply and return temperature or energy, optionally outdoor
temperature). You get:

1. **Penalty calculator**: delta-T against your contract minimum, month by month, and an annual surcharge estimate.
2. **Fault-signature classifier**: the probability that each of four causes is materially present.
3. **Savings ranking**: causes ordered by expected AED per year recovered, with what to check on site.
4. **Open benchmark**: the simulator, labels and evaluation scripts, so the approach can be tested and criticised.

Also: **portfolio mode** (one file, many buildings, ranked by saving), a **printable owner report**, an optional
**design delta-T** input that gives a more reliable diagnosis, and a **"not reliable" warning** when a building looks
unlike anything the model was trained on. Accepts messy real-world exports (any delimiter, degF, L/s, RT, MW, cumulative
kWh registers, .xlsx).

## How it works

```
meter CSV -> hourly canonical frame -> 42 scale-free shape features -> calibrated gradient boosting -> ranked report
```

Real buildings come without root-cause labels, so training data come from a simulator (effectiveness-NTU coil
model, four fault families, four building types). Ground truth is a **counterfactual**: remove one cause,
simulate again, and the delta-T difference is that cause's gain. Details: [docs/METHODOLOGY.md](docs/METHODOLOGY.md).

## Results

<!--results:start-->
All simulated, 6500 samples across 650 buildings, 5-fold CV grouped by building. Intervals resample whole buildings.

| model | macro AUROC (95% CI) | any-fault AUROC | macro F1 | fix #1 gain captured* |
|---|---|---|---|---|
| **delta-t-doctor (blind)** | 0.966 [0.963, 0.969] | 0.990 | 0.818 | 0.970 |
| delta-t-doctor (informed, design delta-T given) | 0.971 [0.968, 0.974] | 0.994 | 0.841 | 0.969 |
| logistic regression | 0.915 [0.908, 0.920] | 0.967 | 0.642 | 0.906 |
| hand-written expert rules | 0.581 [0.572, 0.589] | 0.656 | 0.324 | 0.379 |
| class prior | 0.478 [0.468, 0.487] | 0.483 | 0.000 | 0.543 |
<!--results:end-->

\*Share of the achievable delta-T gain recovered by fixing the tool's top-ranked cause, without access to the true fault list.

Under stress (3x sensor noise, 2-hour data, +/-3 C climate, no outdoor temperature, energy-only meter,
21-day window, half and 1.5x fault severity) macro AUROC ranges from 0.91 (3x sensor noise, no outdoor temperature) to 0.98 (fresh
buildings, no shift). Holding out a whole building type costs 0.00 to 0.03 (hotel held out: 0.934). Holding out a season as well as
the test buildings gives 0.952 (June-August) and 0.957 (December-February). Regenerating the data and retraining under 4 different
seeds (smaller 2,000-window sets) gives 0.959 +/- 0.003. A feature ablation shows delta-T shape (18 features) and flow shape each carry most of the signal; the
single average delta-T feature scores 0.64 ([results/ablation.json](results/ablation.json)).

**Those numbers are all inside one simulator, and they are the optimistic ones.** I wrote a second, structurally different simulator
(valves and pressure, a humidity-driven wet coil, a plate-exchanger ETS; [docs/CROSS_SIMULATOR.md](docs/CROSS_SIMULATOR.md)) and wrote
predictions before running it. A model trained on the first and tested on the second scores **0.68** macro AUROC and flags 88% of
healthy buildings as faulty; the reverse direction scores 0.77. One prediction failed (any-fault AUROC fell to 0.70, I expected 0.80).
The shipped model is trained on both simulators, which closes the gap for those two worlds and proves nothing about a real building.
Expect the unseen-world numbers until the pilot shows otherwise.

Savings carry ranges: each cause has 10th/50th/90th percentile gains (conformal-widened; 82% to 85% coverage of the true gain on
held-out simulated buildings, nominal 80%), and the report shows an AED range next to the point estimate.

**External check (LBNL chiller-plant benchmark, CC-BY).** I wrote predictions before running it and again before
the follow-up ([docs/EXTERNAL_CHECK.md](docs/EXTERNAL_CHECK.md)). Outcome:

* **It failed.** A fault-free plant was flagged as faulty with near-certainty, in v0.1 and again in v0.2, even when
  told its design delta-T. My first explanation (low design delta-T) was only part of it: the plant's flow barely
  follows load, unlike every simulated building. The model is a four-cause classifier for variable-flow building
  loops, not a general anomaly detector.
* **What changed.** The tool now measures how far a building's behaviour is from the training range and reports
  "not reliable" when it is far. That guard was built after the failure and is untested on real data.
* I also found and fixed a supply/return mapping bug in my own first run and kept the discarded log.

That dataset has no building-side labels, so it cannot measure accuracy.

## Quick start

```bash
pip install -e ".[api,dev]"
deltat-doctor serve                         # web app on http://127.0.0.1:8000
deltat-doctor simulate --causes fouling --out demo_ets.csv
deltat-doctor diagnose demo_ets.csv --rate 0.40
pytest                                      # 82 tests
deltat-doctor portfolio fleet.csv --out ranked.csv
deltat-doctor diagnose demo_ets.csv --design-dt 9.0 --html report.html
docker build -t delta-t-doctor . && docker run -p 8000:8000 delta-t-doctor
```

Reproduce the data, model and evaluation: `make data train evaluate` (the data step takes several minutes).
The external check needs the LBNL zip placed under `external/`: `make lbnl`.

## Examples

`examples/` holds a simulated six-month building, its printable report (open the HTML file), and a six-tower portfolio with its ranked output.

## Repository layout

```
src/deltat_doctor/   sim/ (simulator), features, models, penalty, diagnose, io, api, cli, web/
scripts/             generate_data, train, evaluate, lbnl_check
tests/               unit and API tests
docs/                METHODOLOGY, LIMITATIONS, EXTERNAL_CHECK, MODEL_CARD, PILOT, API, SECURITY, DEPLOYMENT
results/             metrics.md/json, figures, logs
```

## Limitations

Short version: simulator-only validation, four causes, designed-low-delta-T plants out of range, the demo
rate is a placeholder. Full list: [docs/LIMITATIONS.md](docs/LIMITATIONS.md).

## Sources

* Emicool FAQ, delta-T surcharge: https://www.emicool.com/en/faq
* Granderson et al., LBNL FDD datasets, chiller plant: https://fdddata.lbl.gov (CC-BY)
* Background on low delta-T syndrome: Grundfos and ACR Latinoamerica explainers; PolyU fault-diagnosis paper.

## Licence

MIT.
