# delta-t-doctor

**Find out why a district cooled building returns water that is too cool, and which fix to try first, using only the utility meter data it already has.**

![The diagnosis screen for a simulated building with fouled coils](docs/img/ui_fouled.png)

> **Status: a research prototype, validated in simulation only.** Trained and tested on physics simulators.
> It has **not** been validated on real UAE building data and no field accuracy is claimed. In the external check 3 of 5 predictions
> failed and 1 was not supported, and on simulators it was not trained on it scores 0.68 to 0.77 macro AUROC (0.67 to 0.76 on four regenerated B pools) (see [Results](#results) and
> [Limitations](docs/LIMITATIONS.md)). Treat its output as a ranked inspection list.

Product plan, market research and roadmap: [plan.md](plan.md). Draft pilot protocol: [docs/PILOT.md](docs/PILOT.md), with a blind
[inspection form](docs/INSPECTION_FORM.md). Reproducibility of the data: [docs/REPRODUCIBILITY.md](docs/REPRODUCIBILITY.md).

## The problem

District cooling supplies chilled water to buildings through an energy transfer station (ETS). The
plant is sized for the water coming back warm. When a building returns it too cool, the plant moves more water for
the same cooling. This is called low delta T syndrome. Operators put the burden on the building owner: for
example, Emicool's published FAQ says the owner must maintain a delta T of 8.9 C, with a surcharge of **10% on the
consumption charge for each degree Celsius below it** ([source](https://www.emicool.com/en/faq)). Contracts
vary.

The owner sees the surcharge on a bill but not the cause. Typical causes are fouled coils, leaking valves on
idle air handlers, 3-way valves that pass full flow, and excess differential pressure. Finding which one applies
is a consultant led site survey. I found no self serve tool that does this from meter data.

## What it does

Upload a CSV from the ETS meter (timestamp, flow, supply and return temperature or energy, optionally outdoor
temperature). You get:

1. **Penalty calculator**: delta T against your contract minimum, month by month, and an annual surcharge estimate.
2. **Fault-signature classifier**: the probability that each of four causes is materially present.
3. **Savings ranking**: causes ordered by expected AED per year recovered, with what to check on site.
4. **Open benchmark**: the simulator, labels and evaluation scripts, so the approach can be tested and criticised.

Also: **portfolio mode** (one file, many buildings, ranked by saving), a **printable owner report**, an optional
**design delta T** input that gives a slightly better diagnosis in simulation (about +0.005 AUROC), and a **"not reliable" warning** when a building looks
unlike anything the model was trained on. Accepts messy real world exports (any delimiter, degF, L/s, RT, MW, cumulative
kWh registers, .xlsx).

## How it works

```
meter CSV -> hourly canonical frame -> 42 scale free shape features -> calibrated gradient boosting -> ranked report
```

Real buildings come without root-cause labels, so training data come from two simulators (A: effectiveness-NTU coil
model, four building types; B: hydraulic and wet coil model, seven building types; four fault families). Ground truth is a **counterfactual**: remove one cause,
simulate again, and the delta T difference is that cause's gain. Details: [docs/METHODOLOGY.md](docs/METHODOLOGY.md).

## Results

<!--results:start-->
All simulated, simulator A only: 5000 windows across 500 buildings, models trained and tested on A with 5-fold CV grouped by building (the shipped model is trained on A and B; on B it scores 0.877 in the same protocol, results/cross_simulator.md). Intervals resample whole buildings.

| model | macro AUROC (95% CI) | any fault AUROC | macro F1 | fix #1 gain captured* |
|---|---|---|---|---|
| **delta-t-doctor (blind)** | 0.966 [0.963, 0.969] | 0.990 | 0.818 | 0.970 |
| delta-t-doctor (informed, design delta T given) | 0.971 [0.968, 0.974] | 0.994 | 0.841 | 0.969 |
| logistic regression | 0.915 [0.908, 0.920] | 0.967 | 0.642 | 0.906 |
| hand written expert rules | 0.581 [0.572, 0.589] | 0.656 | 0.324 | 0.379 |
| class prior | 0.478 [0.468, 0.487] | 0.483 | 0.000 | 0.543 |
<!--results:end-->

\*Share of the achievable delta T gain recovered by fixing the tool's top ranked cause, without access to the true fault list.

Under stress (3x sensor noise, 2-hour data, +/-3 C climate, no outdoor temperature, energy-only meter,
21-day window, half and 1.5x fault severity) macro AUROC ranges from 0.91 (3x sensor noise, no outdoor temperature) to 0.98 (fresh
buildings, no shift). Holding out a whole building type costs 0.00 to 0.03 (hotel held out: 0.934). Holding out a season as well as
the test buildings gives 0.952 (June-August) and 0.957 (December-February). Regenerating the data and retraining under 4 different
seeds (smaller 2,000-window sets) gives 0.959 +/- 0.003. A feature ablation shows delta T shape (18 features) and flow shape each carry most of the signal; the
single average delta T feature scores 0.64 ([results/ablation.json](results/ablation.json)).

**Those numbers are all inside one simulator, and they are the optimistic ones.** I wrote a second, structurally different simulator
(valves and pressure, a humidity-driven wet coil, a plate exchanger ETS; [docs/CROSS_SIMULATOR.md](docs/CROSS_SIMULATOR.md)) and wrote
predictions before running it. A model trained on the first and tested on the second scores **0.68** macro AUROC and flags 88% of
healthy buildings as faulty; the reverse direction scores 0.77. One prediction failed (any fault AUROC fell to 0.70, I expected 0.80).
The shipped model is trained on both simulators, which closes the gap for those two worlds and proves nothing about a real building.
Expect the unseen-world numbers until the pilot shows otherwise.

Savings carry ranges: each cause has 10th/50th/90th percentile gains from quantile boosting, and the report shows an AED range next to the point estimate. A conformal margin is fitted but came out 0.0 on simulated data, so the ranges are the raw quantiles. Coverage of the true gain on held out simulated buildings is 82% to 85% among windows where a cause is predicted active, but only 55% to 76% among windows where the cause is truly present (`results/uncertainty.json`), so treat the lower end as optimistic.

**External check (LBNL chiller plant benchmark, CC-BY; simulated plant data from a different team).** I wrote predictions before running it
and again before the follow-up ([docs/EXTERNAL_CHECK.md](docs/EXTERNAL_CHECK.md)). Outcome:

* **It failed.** A fault free plant was flagged as faulty with near certainty, in v0.1 and again in v0.2, even when
  told its design delta T. My first explanation (low design delta T) was only part of it: the plant's flow barely
  follows load, unlike every simulated building. The model is a four cause classifier for variable flow building
  loops, not a general anomaly detector.
* **What changed.** The tool now measures how far a building's behaviour is from the training range and reports
  "not reliable" when it is far. That guard was built after the failure and is untested on real data.
* I also found and fixed a supply/return mapping bug in my own first run (described in EXTERNAL_CHECK.md; the discarded log is not kept in the repository).

That dataset has no building-side labels, so it cannot measure accuracy.

**Open set guard (v1.1).** The first guard checked each feature against its own range and missed combinations it had never seen.
It is joined by a Mahalanobis distance guard over all 42 shape features (the building is withheld if either fires), and when a guard trips the tool **withholds the cause ranking**
instead of printing it with a warning. Measured as a leave one world out estimate (`results/openset.json`): fit on simulator A, it
flags 64% of simulator B's windows (the old box: 37%) at a 5.5% false flag rate on held out A buildings. Fit on B, it flags 29% of A
(old box: 7%), so the guard is weaker when the training world is small. (v1.1.0 used Mahalanobis alone: 71% and 25%; v1.1.1 adds a nearest neighbour score for a more balanced result.) It is built and tested on simulated data only.
In world false flags are higher under degraded input: 42% of windows with 2 hourly data, 22% with 3x sensor noise, 16% without outdoor temperature
(`results/openset.json`), and 24% of windows (14% of buildings) from freshly generated simulator B buildings (`results/world_d.json`).

Every finding now carries evidence against healthy buildings (measured value next to the healthy 5th to 95th percentile), a tier
(likely / possible / weak / unsupported), and the report shows per window delta T with a trend test. Overflow is found at about 0.92 AUROC
inside one simulator but at chance (0.53 to 0.56) across simulators (`results/overflow_analysis.json`), so it is never rated above "possible".

**v1.2.0: a third physics, real data contact, fleet calibration, assurance.** All simulation unless stated.

* **World D** ([docs/WORLD_D.md](docs/WORLD_D.md)), a time stepped closed loop simulator written to test the claims above, with predictions
  committed first. The shipped model scores **0.705** macro AUROC on it zero shot and calls 98% of healthy windows faulty; the guards withhold
  the ranking for 92% of D buildings. **But the windows the guard lets through score lower (0.618) than those it flags (0.756)**: the guard
  detects unfamiliar buildings, it does not pick out the model's mistakes. Hourly temporal features did not help overflow in an unseen world
  and are not shipped.
* **When does it know it is probably wrong?** ([docs/SELECTIVE_PREDICTION.md](docs/SELECTIVE_PREDICTION.md), v1.2.1, simulation.) Inside a
  familiar simulator, its own decision margin finds wrong rankings well (AUROC 0.905 in A, 0.733 in B; keeping the more confident half cuts the
  error rate from 7.0% to 0.3% in A). On the unseen world D, **no label free signal works**: the best reaches 0.608, the model's entropy is below
  chance (0.457) because it is confidently wrong, and as an error signal the guard is below chance in world (0.40, 0.44) and weak on D (0.583).
  No extra abstention flag is shipped. Calibration on inspected buildings is the only adaptation measured to raise accuracy on an unfamiliar
  fleet (few shot on world D: 0.71 to 0.83 with 20 buildings); whether it also restores error detection has not been tested.
* **Real data contact** ([docs/REAL_DATA_CONTACT.md](docs/REAL_DATA_CONTACT.md)): two openly licensed real district heating datasets (no labels).
  The product refused all 45 buildings at parsing with a plain message and did not crash; one silent issue (UTC timestamps) was fixed.
* **Fleet calibration** (`deltat-doctor calibrate`, [docs/API.md](docs/API.md)): adapts the cause classifiers to a fleet from 10 or more
  inspected buildings, refuses below 10, marks 10 to 19 as weak, keeps a holdout report and never replaces the default model.
* **Assurance** ([docs/ASSURANCE_CASE.md](docs/ASSURANCE_CASE.md), [docs/SECURITY.md](docs/SECURITY.md)): hashed lock file, Docker install
  stage with networking disabled, SBOM, a test that runs a diagnosis with network sockets disabled, `scripts/reproduce.py`.

## Quick start

Python 3.11 or newer. One command per line (works in Windows PowerShell 5 as well as bash):

```bash
pip install -e ".[api,dev,xlsx]"
deltat-doctor serve
deltat-doctor simulate --causes fouling --out demo_ets.csv
deltat-doctor diagnose demo_ets.csv --rate 0.40
deltat-doctor diagnose demo_ets.csv --design-dt 9.0 --html report.html
deltat-doctor portfolio examples/portfolio_6_towers.csv --out ranked.csv
pytest
docker build -t delta-t-doctor .
docker run --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --cap-drop ALL --security-opt no-new-privileges -p 8000:8000 delta-t-doctor
```

`deltat-doctor serve` starts the web app on http://127.0.0.1:8000. Reproduce the data, model and evaluation (the data step is slow):

```bash
python scripts/generate_data.py
python scripts/train.py
python scripts/evaluate.py
python scripts/reproduce.py
```

The external check needs the LBNL zip placed under `external/`: `python scripts/lbnl_check.py`.

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

Short version: simulator-only validation, four causes, designed low delta T plants out of range, the demo
rate is a placeholder. Full list: [docs/LIMITATIONS.md](docs/LIMITATIONS.md).

## Sources

* Emicool FAQ, delta T surcharge: https://www.emicool.com/en/faq
* Granderson et al., LBNL FDD datasets, chiller plant: https://fdddata.lbl.gov (CC-BY)
* Background on low delta T syndrome: Grundfos and ACR Latinoamerica explainers; PolyU fault-diagnosis paper.

## Licence

MIT.
