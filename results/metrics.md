# Evaluation results (simulated buildings)

All numbers come from the physics simulator in `deltat_doctor.sim`. They measure how well the tool recovers *simulated* faults. They are not field accuracy.

## A. Held-out buildings (5-fold grouped CV)

| setting | n | macro AUROC | any-fault AUROC | macro F1 | exact match | fix #1 gain captured | fix #1 saving captured |
|---|---|---|---|---|---|---|---|
| ours_gbdt | 5000 | 0.967 | 0.995 | 0.833 | 0.786 | 0.970 | 0.976 |
| logistic | 5000 | 0.922 | 0.985 | 0.690 | 0.670 | 0.910 | 0.941 |
| expert_rules | 5000 | 0.601 | 0.675 | 0.362 | 0.312 | 0.410 | 0.415 |
| prior | 5000 | 0.478 | 0.480 | 0.000 | 0.298 | 0.530 | 0.597 |
| ours_informed | 5000 | 0.979 | 0.998 | 0.873 | 0.826 | 0.975 | 0.980 |

Per-cause detail for the tool (held-out buildings):

| cause | prevalence | AUROC | F1@0.5 | Brier | delta-T gain MAE (C) |
|---|---|---|---|---|---|
| fouling | 0.25 | 0.991 | 0.917 | 0.030 | 0.11 |
| passing_valves | 0.21 | 0.957 | 0.778 | 0.063 | 0.11 |
| constant_flow | 0.26 | 0.997 | 0.967 | 0.014 | 0.19 |
| overflow | 0.20 | 0.922 | 0.669 | 0.082 | 0.14 |

Building-level bootstrap, 95% intervals (200 resamples of whole buildings):

| model | macro AUROC | any-fault AUROC | macro AUROC, difference of ours minus this model |
|---|---|---|---|
| ours_gbdt | 0.967 [0.963, 0.969] | 0.995 [0.993, 0.997] | reference |
| logistic | 0.922 [0.916, 0.927] | 0.985 [0.982, 0.988] | +0.045 [+0.041, +0.048] |
| expert_rules | 0.601 [0.593, 0.609] | 0.675 [0.652, 0.697] | +0.366 [+0.357, +0.375] |
| prior | 0.478 [0.468, 0.486] | 0.479 [0.464, 0.495] | +0.489 [+0.480, +0.498] |
| ours_informed | 0.979 [0.976, 0.981] | 0.998 [0.996, 0.999] | reference |

## B. Distribution shift (model trained on the main set; fresh buildings)

| setting | n | macro AUROC | any-fault AUROC | macro F1 | exact match | fix #1 gain captured | fix #1 saving captured |
|---|---|---|---|---|---|---|---|
| fresh | 480 | 0.978 | 0.999 | 0.860 | 0.833 | 0.969 | 0.975 |
| noise_x3 | 480 | 0.902 | 0.970 | 0.652 | 0.467 | 0.916 | 0.919 |
| res_2h | 480 | 0.931 | 0.958 | 0.765 | 0.644 | 0.921 | 0.944 |
| climate_p3 | 480 | 0.969 | 0.993 | 0.836 | 0.798 | 0.973 | 0.979 |
| climate_m3 | 480 | 0.971 | 0.995 | 0.845 | 0.808 | 0.976 | 0.984 |
| severity_x05 | 480 | 0.952 | 0.986 | 0.813 | 0.798 | 0.965 | 0.982 |
| severity_x15 | 480 | 0.964 | 1.000 | 0.828 | 0.758 | 0.949 | 0.952 |
| no_outdoor | 480 | 0.912 | 0.985 | 0.693 | 0.633 | 0.928 | 0.957 |
| window_21d | 480 | 0.964 | 0.998 | 0.813 | 0.796 | 0.968 | 0.979 |
| energy_only | 480 | 0.965 | 1.000 | 0.827 | 0.796 | 0.959 | 0.972 |

## B2. Same stress sets, informed model (design delta-T supplied)

| setting | n | macro AUROC | any-fault AUROC | macro F1 | exact match | fix #1 gain captured | fix #1 saving captured |
|---|---|---|---|---|---|---|---|
| fresh | 480 | 0.987 | 0.999 | 0.895 | 0.871 | 0.972 | 0.980 |
| noise_x3 | 480 | 0.968 | 0.997 | 0.745 | 0.742 | 0.915 | 0.926 |
| res_2h | 480 | 0.958 | 0.988 | 0.824 | 0.729 | 0.910 | 0.934 |
| climate_p3 | 480 | 0.982 | 0.999 | 0.868 | 0.829 | 0.980 | 0.983 |
| climate_m3 | 480 | 0.983 | 1.000 | 0.896 | 0.865 | 0.967 | 0.980 |
| severity_x05 | 480 | 0.972 | 0.995 | 0.835 | 0.810 | 0.975 | 0.989 |
| severity_x15 | 480 | 0.976 | 1.000 | 0.866 | 0.802 | 0.951 | 0.957 |
| no_outdoor | 480 | 0.966 | 0.997 | 0.822 | 0.760 | 0.964 | 0.977 |
| window_21d | 480 | 0.976 | 0.999 | 0.860 | 0.835 | 0.977 | 0.983 |
| energy_only | 480 | 0.977 | 0.999 | 0.855 | 0.819 | 0.970 | 0.988 |

## E. Healthy buildings by design delta-T band (held-out buildings)

False alarm = any-cause probability of 0.5 or more on a building with no fault.

| design delta-T (C) | n | healthy | blind: mean p(any) | blind: false alarms | informed: mean p(any) | informed: false alarms | blind any-fault AUROC | informed any-fault AUROC |
|---|---|---|---|---|---|---|---|---|
| 5-7 | 1530 | 461 | 0.12 | 8% | 0.09 | 6% | 0.991 | 0.994 |
| 7-9 | 1260 | 375 | 0.06 | 2% | 0.03 | 2% | 0.995 | 0.999 |
| 9-11 | 1310 | 381 | 0.04 | 2% | 0.03 | 2% | 0.997 | 0.997 |
| 11-13 | 860 | 265 | 0.02 | 0% | 0.02 | 1% | 1.000 | 1.000 |

## C. Leave one building type out

| setting | n | macro AUROC | any-fault AUROC | macro F1 | exact match | fix #1 gain captured | fix #1 saving captured |
|---|---|---|---|---|---|---|---|
| held out: hotel | 1290 | 0.930 | 0.988 | 0.730 | 0.677 | 0.906 | 0.936 |
| held out: mall | 1450 | 0.958 | 0.989 | 0.820 | 0.769 | 0.922 | 0.921 |
| held out: office | 1210 | 0.965 | 0.958 | 0.815 | 0.689 | 0.969 | 0.964 |
| held out: residential | 1050 | 0.939 | 0.994 | 0.726 | 0.688 | 0.930 | 0.964 |

## D. Held-out seasons

| setting | n | macro AUROC | any-fault AUROC | macro F1 | exact match | fix #1 gain captured | fix #1 saving captured |
|---|---|---|---|---|---|---|---|
| summer_JJA | 1242 | 0.941 | 0.973 | 0.747 | 0.647 | 0.941 | 0.952 |
| winter_DJF | 1283 | 0.960 | 0.996 | 0.810 | 0.776 | 0.958 | 0.969 |

## Constant-flow subtypes (recall at 0.5, held-out buildings)

| subtype | n | mean prob | recall |
|---|---|---|---|
| three_way | 202 | 0.95 | 0.97 |
| stuck_open | 155 | 0.90 | 0.93 |
| mixed | 953 | 0.96 | 0.97 |
