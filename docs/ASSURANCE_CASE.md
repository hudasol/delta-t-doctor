# Assurance case

Each claim the repository makes, the evidence behind it, and its status. **Every evidence item is from simulation or from the code itself;
none is field evidence.** "Supported" means supported in simulation or by a test, never more. Section 2 lists what is not supported.

## 1. Claims and their evidence

| # | Claim | Status | Script | Results file | Test |
|---|---|---|---|---|---|
| C1 | Inside simulator A, held out buildings: macro AUROC 0.966 [0.963, 0.969] | Supported (simulation) | `scripts/evaluate.py` | `results/metrics.json` | `tests/test_sim.py` (simulator behaviour) |
| C2 | Across simulators the model transfers poorly: 0.683 (A to B), 0.770 (B to A) | Supported (simulation) | `scripts/cross_simulator.py` | `results/cross_simulator.json` | none (experiment) |
| C3 | On a third, dynamic physics (world D) the shipped model scores macro AUROC 0.705 [0.685, 0.724] zero shot and calls 98% of healthy windows faulty | Supported (simulation) | `scripts/world_d_eval.py zeroshot` | `results/world_d.json` (`zero_shot`) | `tests/test_world_d.py` (simulator) |
| C4 | Labelled target buildings lift transfer: about 20 give 0.80 and 40 give 0.84 (A to B) | Supported (simulation) | `scripts/transfer_fewshot.py` | `results/transfer_fewshot.json` | none (experiment) |
| C4D | The same on world D | Supported (simulation): 20 D buildings give 0.825 and 40 give 0.850; healthy false alarms 99% to 21%; overflow stays near 0.61 | `scripts/world_d_eval.py fewshot` | `results/world_d.json` (`few_shot`) | none |
| C5 | The guards withhold the ranking for most buildings from an unseen physics: 92% of world D buildings | Supported (simulation) | `scripts/world_d_eval.py guard` | `results/world_d.json` (`guard`) | `tests/test_round5_openset_evidence.py::test_guard_flags_joint_shift_not_seen_by_per_feature_box` |
| C6 | The guards rarely flag new buildings from the training worlds: 0% of fresh A buildings, 13.8% of fresh B buildings | Partly supported: the B figure is above the 10% I predicted | `scripts/world_d_eval.py guard` | `results/world_d.json` | none |
| C7 | The guard removes the windows where the model is wrong | **Not supported**: on world D the windows it lets through score lower (0.618) than those it flags (0.756) | `scripts/world_d_eval.py guard` | `results/world_d.json` | none |
| C8 | Overflow is not identifiable across physics (0.53 to 0.56) and is capped at "possible" | Supported (simulation); world D gives 0.547 | `scripts/overflow_analysis.py`, `scripts/world_d_eval.py` | `results/overflow_analysis.json`, `results/world_d.json` | `tests/test_round5_openset_evidence.py::test_weak_signature_cause_is_never_likely` |
| C9 | Hourly temporal features do not recover overflow in an unseen world, so they are not shipped | Supported (simulation) | `scripts/world_d_eval.py temporal` | `results/world_d_temporal.json` | `tests/test_world_d.py` (feature block computed) |
| C10 | Out of scope real files are refused with a plain message: 40 of 40 Danish heat meters, 5 of 5 Nis substations, no crash | Supported (real data, no labels) | `scripts/real_contact.py` | `results/real_data_contact.json` | `tests/test_real_loaders.py` |
| C11 | No network calls at runtime | Supported (test) | none | none | `tests/test_assurance.py::test_diagnosis_runs_with_outbound_network_disabled`, `tests/test_v02_portfolio_report.py` |
| C12 | A tampered model file is refused before it is unpickled (bundled and fleet calibrated) | Supported (test) | none | none | `tests/test_edge_robustness.py::test_tampered_bundled_model_refused`, `tests/test_calibrate.py::test_tampered_calibrated_model_is_refused` |
| C13 | Fleet calibration refuses below 10 inspected buildings, marks 10 to 19 as weak in the card and every report, never replaces the default model | Supported (test) | none | none | `tests/test_calibrate.py` |
| C14 | Fleet calibration improves held out discrimination on a fleet from an unseen world | Partly supported (simulation): on 12 held out buildings of a world D fleet macro AUROC rose from 0.782 to 0.833, but overflow fell (0.81 to 0.66) and abstention stayed at 58%; the unit test with a B fleet also shows a rise | `scripts/calibrate_check.py` | `results/calibrate_check.json` | `tests/test_calibrate.py::test_calibration_improves_held_out_agreement_on_unseen_world` |
| C15 | The training pool can be regenerated from the repository | Partly supported: the A pool matches the shipped model's stored training percentiles to 4e-15 (not bitwise); the seed of the committed B pool was not recorded | `scripts/check_regenerated.py`, `scripts/reproduce.py` | `results/regeneration_check.json` | none |
| C16 | Dependencies are pinned with hashes and the image installs offline from hash checked wheels | Supported (CI) | `scripts/make_lock.py` | `requirements.lock`, `sbom.cdx.json` | `tests/test_assurance.py`, CI `docker` job |
| C17 | The image runs as a non root user on a read only filesystem with all capabilities dropped, and accepts an upload | Supported (CI) | none | none | CI `docker` job smoke test |
| C18 | Every result carries input hash, model identity and parameters | Supported (test) | none | none | `tests/test_round4_i18n_report.py`, `tests/test_calibrate.py` |
| C19 | Why fouling transfers worst from A to B | Answered (simulation): B's fouling signature is weak (in world 0.675; A's top features move about a tenth as much in B); no reversal (H2 and H3 failed, H1 and H4 held) | `scripts/fouling_transfer.py` | `results/fouling_transfer.json` | none |

## 2. Claims that are NOT supported

* **Any accuracy on real buildings.** No labelled real data has been used; no UAE data at all.
* **Guard behaviour on real chilled water buildings.** The only real contact is district heating, which the guard rejects trivially.
* **Savings in AED.** They come from simulated counterfactuals and an illustrative tariff, not measured before and after data.
* **Overflow detection across physics**, with or without the temporal features; a measured DP channel is untested on real data.
* **Arabic text quality.** Machine draft; no native speaking engineer has reviewed it.
* **Calibration on a real fleet.** Measured only with simulated fleets.
* **Certification or compliance** with any standard. `docs/SECURITY.md` gives an intended mapping only.
