# delta-t-doctor: proposal for an offline, vendor neutral delta T diagnostic

Prepared by Huda Mueen. Status of the evidence: **validated in simulation only.** No real UAE building data has been used, and no
field accuracy is claimed anywhere in this document or the repository.

## 1. The operational problem

District cooling plants in the UAE are sized for chilled water returning warm. When buildings return it too cool (low delta T), the
plant pumps more water for the same cooling, and operators pass the cost on: one published tariff adds 10% to the consumption charge
for each degree C below 8.9 C ([Emicool FAQ](https://www.emicool.com/en/faq)). The owner sees the surcharge but not the cause. Finding it today means a consultant site survey per
building. The four common fixable causes are fouled coils, passing valves on idle air handlers, constant flow (3-way or stuck) valves
and excess differential pressure.

## 2. Why a vendor neutral, software only diagnostic

* It reads only the energy transfer station meter data the operator already holds (flow, supply and return temperature or energy,
  optionally outdoor temperature). No sensors, no retrofit, no access to building controls.
* It is not tied to any controls, valve or meter vendor, so it can rank a mixed portfolio on one basis.
* Its output is a ranked inspection list with an AED estimate per cause, which sends the right engineer to the right building first.

## 3. Offline and sovereign deployment

* Runs entirely inside the operator's network: a Python package, a command line tool or a container. The product makes **no network
  calls at runtime** (fonts and scripts are bundled; a test runs a full diagnosis with outbound sockets disabled).
* The container image is assembled from hash checked wheels in a build stage with networking disabled and runs as a non root user. With
  the run flags in [SECURITY.md](SECURITY.md) it runs on a read only filesystem with all capabilities dropped; the CI smoke test runs it that way. A generated lock file (with hashes) and a CycloneDX software bill of materials list
  every component.
* Uploaded files are processed in memory and not stored. There is no telemetry and no account system.

## 4. Abstention by design

The system refuses rather than guesses. Two guards (a per feature range check and an open set distance guard) withhold the cause
ranking when a building does not resemble anything the model was trained on. Files that are not chilled water data are refused at
parsing with a plain message. Overflow (excess pressure) is never rated above "possible", because its signature does not carry
across physics.

A measured limit: the guards are novelty detectors, not error detectors. On a simulated physics the model was not trained on they withheld
92% of buildings, but the windows they let through were scored worse (0.618 macro AUROC) than those they withheld (0.756). An answer for a
building from an unfamiliar fleet is therefore not more trustworthy because it was not withheld. A follow up measured five label free
confidence signals: inside a familiar simulator the model's decision margin finds wrong answers well (AUROC 0.905), but on the unseen physics
none exceeds 0.61 and the model is confidently wrong ([SELECTIVE_PREDICTION.md](SELECTIVE_PREDICTION.md)). Fleet calibration on inspected
buildings is what addresses that.

## 5. Traceability

Every result carries a provenance block: the SHA-256 of the input file, the identity and hash of the model, the contract parameters,
the data window and the quality flags. Bundled models are loaded only if their bytes match the recorded hash (fail closed). A fleet
calibrated model carries its own card with the base model hash, the manifest hash, the hash of every building file, the date and the
parameters, and is never used unless asked for explicitly.

## 6. Bilingual support

English and Arabic user interface and owner report (right to left layout, bundled Arabic font). The Arabic text is a machine draft
with a glossary and a 181 string reviewer sheet; **it has not been reviewed by a native speaking engineer**, which is a precondition
for customer use.

## 7. The honest evidence state

All figures below are simulation results. Scripts and result files are listed in [ASSURANCE_CASE.md](ASSURANCE_CASE.md).

| Question | Measured answer (simulation unless stated) | Source |
|---|---|---|
| Accuracy on held out buildings of the training simulator | macro AUROC 0.966 [0.963, 0.969] | `results/metrics.json` |
| Accuracy on a differently built simulator | 0.683 (A to B), 0.770 (B to A) | `results/cross_simulator.json` |
| Accuracy on a third, dynamic simulator never trained on | 0.705 [0.685, 0.724]; 98% of healthy windows called faulty | `results/world_d.json` |
| After calibrating on 20 labelled buildings of that world | 0.825; healthy false alarms 26% | `results/world_d.json` |
| Fleet calibration command, 40 building pretend fleet, 12 held out | macro AUROC 0.782 to 0.833; overflow worse (0.81 to 0.66) | `results/calibrate_check.json` |
| Buildings from an unseen physics withheld by the guards | 92% | `results/world_d.json` |
| New buildings from the training worlds wrongly withheld | 0% (A), 14% (B) | `results/world_d.json` |
| Overflow across physics | chance (0.53 to 0.56; 0.547 on world D) | `results/overflow_analysis.json`, `results/world_d.json` |
| Real data (district heating, no labels): files refused or abstained | 45 of 45 refused at parsing; no crash | `results/real_data_contact.json` |
| Accuracy on real UAE buildings | **not measured; no real UAE data has been used** | none |

## 8. A 90 day pilot

Taken from [PILOT.md](PILOT.md); thresholds are a starting proposal for the partner to adjust.

* **Scope.** One operator or owner, 10 to 20 penalised buildings, 12 months of hourly ETS data each, contract terms, and where the BMS
  has it, loop differential pressure or pump speed.
* **Method.** Run the tool blind on every building and record the ranking before any visit. An engineer inspects each building without
  seeing the output. Score with `scripts/evaluate_real.py`; then calibrate on the fleet with `deltat-doctor calibrate` and read the
  holdout report.
* **Success criteria, set before the pilot.** Top 2 agreement with inspection of at least 70% on buildings with a single dominant
  cause; no more than 1 in 10 buildings where the tool is confidently wrong (probability above 0.8 on a cause the inspection rules out);
  the first inspection target is the dominant cause in at least half of the buildings. The abstention rate is reported first.
* **What the partner receives.** A ranked inspection list and AED business case per building, a portfolio view, a calibrated model for
  their fleet if 10 or more buildings are inspected, and a written account of where the tool was wrong.

Nothing in this proposal assumes any programme, requirement or contact on the Edge side; those are for the partner to define.
