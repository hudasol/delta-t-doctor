# delta-t-doctor: product plan

Last updated: 2026-10-09. Owner: Huda Mueen.

## 1. One-line pitch

A vendor-neutral, software-only tool that tells a district cooled building owner (or the utility) **why** the building
returns water that is too cool and **which fix to try first**, using only the ETS meter data that already exists.

## 2. The problem, with evidence

**Mechanism.** District cooling plants are sized for chilled water returning warm. A building that returns it
cool (low delta T) makes the plant move more water for the same cooling. Utilities pass that cost to the owner.

**The money.** One operator's public FAQ states the owner must maintain a delta T of 8.9 C and that the surcharge is
"an increase by 10% on consumption charge for each degree Celsius" below it ([Emicool FAQ](https://www.emicool.com/en/faq)).
A building at 7.5 C is 1.4 C short, so it pays roughly 14% on top of its consumption charge. Contracts differ and
my modelled AED figures use an illustrative rate until a real tariff is supplied.

**The scale.** Empower alone reports about 1.7 million RT of connected capacity at the end of 2025
([GDMO, Jan 2026](https://www.mediaoffice.ae/en/news/2026/january/20-01/empower-connected-capacity)).
The Business Bay network alone serves 201 buildings. A metering rollout at Empower covers about 70,000 BTU
sub-meters across roughly 300 buildings, read every 2 hours
([Diehl case study](https://www.diehl.com/metering/en/customer-cases/dubai-fixed-network/)). The data this tool needs exists.

**The gap.** Vendors and trade bodies say low delta T is a "silent cost driver"
([Danfoss at District Energy, Nov 2025](https://www.districtenergy.org/blogs/district-energy/2025/11/11/event-emphasizes-importance-of-energy-efficiency-a)).
The common causes are valve leakage, coil fouling, setpoint drift and hydraulic short-circuiting
([Oxmaint recovery plan](https://oxmaint.com/industries/hvac/chilled-water-delta-t-recovery-plan-for-large-campuses),
a vendor article, no stated assumptions). Finding which one applies in a given building is a site survey.
I found no self serve tool that does it from meter data.

## 3. Competitive landscape (honest)

| Player | What they offer | Where this differs |
|---|---|---|
| Johnson Controls, Balanced Cooling (launched 27 Apr 2026) | Smart-valve retrofits plus monitoring, AI diagnostics and control; claims up to 100% surcharge elimination and up to 40% pumping energy saving in initial testing ([release](https://me.johnsoncontrols.com/media-center/news/press-release/2026/04/27/johnson-controls-launches-balanced-cooling-to-resolve-low-delta-t-performance)) | Hardware-led and vendor-tied. This tool needs no retrofit, works from the meter alone, and can sit in front of a retrofit decision (is it worth it, and which fix?) |
| Danfoss HydronicS | Balancing, flow control, intelligent BTU metering | Same: it sells equipment. This tool is the neutral diagnosis |
| Grundfos | A penalty-savings calculator for its pump solutions ([page](https://www.grundfos.com/ae/learn/ecademy/all-courses/air-conditioning/the-potential-saved-penalty-from-improved-delta-t-in-buildings-w)) | It prices a penalty. It does not diagnose a cause |
| Consultants / site surveys | Real diagnosis, slow and per-building | This tool ranks where to look first, so surveys are targeted |
| Generic building analytics (PropTech OS and similar) | Portfolio energy dashboards | Not specific to ETS delta T root cause |

Position: **neutral triage that makes every retrofit, survey and tariff dispute better informed.** It complements the
hardware players rather than competing with their products, and it is the credible way to verify their claims.

## 4. Who would buy, and why

1. **Utilities and operators** (Empower, Tabreed, Emicool and others): they already hold the ETS data. A triage
   tool lets them tell each penalised customer *what to fix*, which reduces disputes and improves plant return
   temperature. Pilot target.
2. **Facility managers and property owners with several towers:** portfolio view ranked by AED.
3. **FM and MEP contractors:** a faster first visit and a quantified business case for a retrofit.

The first proposal is a **90-day pilot** on 10-20 buildings at one operator, with site inspections used as ground truth.
See [docs/PILOT.md](docs/PILOT.md).

## 5. Where this stands (honest)

Built and tested on a physics simulator. **Not yet validated on real UAE data.** A preregistered external check
on the public LBNL chiller-plant data failed its first prediction: a fault free plant was flagged
as faulty. Results: [docs/EXTERNAL_CHECK.md](docs/EXTERNAL_CHECK.md).

The v0.2 follow-up did not fix it: the benchmark plant's flow does not follow load, which no simulated building does. The tool now reports "not reliable" for buildings that far from its training data. The first job of the pilot is to find out how often real ETS data passes that guard.

## 6. Roadmap

| Version | Goal | Done when |
|---|---|---|
| v0.1.0 | Prototype: simulator, 4-cause classifier, penalty calculator, web app, CLI, tests | Done |
| v0.2.0 | **Design-delta T aware diagnosis (done; the LBNL follow-up failed, see EXTERNAL_CHECK section 6).** Train over a design range of 5-12 C, take an optional design delta T input, add an out of range guard | Re-run LBNL fault free year: false-alarm rate reported against a hypothesis written before the run |
| v0.3.0 | **Portfolio mode (done).** One file with many buildings, ranked by AED/yr; batch CLI; JSON and CSV export | Test on a 30-building synthetic portfolio |
| v0.4.0 | **Reports (done).** Printable one page owner report (HTML to PDF) and a plain-language "what to tell the contractor" checklist | Report renders for all demo cases |
| v0.5.0 | **Deployable (written; first real Docker build happens in CI).** Dockerfile, health and version endpoints, request limits, CI on every push, release workflow | `docker build` and smoke test pass in CI |
| v1.0.0 | **Pilot-ready.** Pilot protocol, data-sharing and privacy note, evidence pack, model card | Documents complete; limits stated |

Beyond 1.0 (needs real data): a feedback loop where inspection results update the model, tariff presets per operator
(only with the operator's confirmed terms), a fifth "design deficit" cause, and connectors to BMS and utility portals.

## 7. Principles

* Never claim field accuracy that has not been measured.
* Write the prediction before running the check. Report failures.
* Rates and tariffs are inputs. Never present an illustrative number as a contract fact.
* Privacy by default: files are analysed in memory and not stored.
* Neutral on vendors. The tool recommends what to inspect, not what to buy.

## 8. Risks

| Risk | Mitigation |
|---|---|
| Real buildings behave unlike the simulator | The pilot; the out of range guard; honest confidence; invite labelled data |
| Overflow looks like the valve faults in meter data | Reported with lower confidence; the report names the site reading that separates them |
| Operators will not share data | The tool runs on an owner's own export; the operator pilot is a second step |
| Incumbent hardware vendors | Neutral positioning; complement, not compete |
| Tariff differences | Contract terms are inputs; operator presets only when confirmed |

## 9. Sources

* [Emicool FAQ, delta T surcharge](https://www.emicool.com/en/faq)
* [GDMO: Empower connected capacity, Jan 2026](https://www.mediaoffice.ae/en/news/2026/january/20-01/empower-connected-capacity)
* [Diehl Metering: Empower fixed network](https://www.diehl.com/metering/en/customer-cases/dubai-fixed-network/)
* [Johnson Controls: Balanced Cooling, Apr 2026](https://me.johnsoncontrols.com/media-center/news/press-release/2026/04/27/johnson-controls-launches-balanced-cooling-to-resolve-low-delta-t-performance)
* [District Energy: Danfoss event, Nov 2025](https://www.districtenergy.org/blogs/district-energy/2025/11/11/event-emphasizes-importance-of-energy-efficiency-a)
* [Grundfos: saved penalty from improved delta T](https://www.grundfos.com/ae/learn/ecademy/all-courses/air-conditioning/the-potential-saved-penalty-from-improved-delta-t-in-buildings-w)
* [Oxmaint: delta T recovery plan](https://oxmaint.com/industries/hvac/chilled-water-delta-t-recovery-plan-for-large-campuses)
* [LBNL FDD datasets](https://fdddata.lbl.gov) (CC-BY)
