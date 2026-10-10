# Evaluation results (simulated buildings)

All numbers come from the physics simulator in `deltat_doctor.sim`. They measure how well the tool recovers *simulated* faults. They are not field accuracy.

## A. Held-out buildings (5-fold grouped CV)

| setting | n | macro AUROC | any-fault AUROC | macro F1 | exact match | fix #1 gain captured | fix #1 saving captured |
|---|---|---|---|---|---|---|---|
| ours_gbdt | 5000 | 0.966 | 0.990 | 0.818 | 0.786 | 0.970 | 0.975 |
| logistic | 5000 | 0.915 | 0.967 | 0.642 | 0.670 | 0.906 | 0.934 |
| expert_rules | 5000 | 0.581 | 0.656 | 0.324 | 0.298 | 0.379 | 0.382 |
| prior | 5000 | 0.478 | 0.483 | 0.000 | 0.327 | 0.543 | 0.598 |
| ours_informed | 5000 | 0.971 | 0.994 | 0.841 | 0.804 | 0.969 | 0.975 |

Per-cause detail for the tool (held-out buildings):

| cause | prevalence | AUROC | F1@0.5 | Brier | delta-T gain MAE (C) |
|---|---|---|---|---|---|
| fouling | 0.24 | 0.988 | 0.911 | 0.032 | 0.09 |
| passing_valves | 0.20 | 0.964 | 0.796 | 0.057 | 0.09 |
| constant_flow | 0.25 | 0.995 | 0.950 | 0.019 | 0.18 |
| overflow | 0.18 | 0.919 | 0.614 | 0.079 | 0.12 |

Building-level bootstrap, 95% intervals (200 resamples of whole buildings):

| model | macro AUROC | any-fault AUROC | macro AUROC, difference of ours minus this model |
|---|---|---|---|
| ours_gbdt | 0.966 [0.963, 0.969] | 0.990 [0.987, 0.992] | reference |
| logistic | 0.914 [0.908, 0.920] | 0.967 [0.960, 0.971] | +0.052 [+0.047, +0.056] |
| expert_rules | 0.581 [0.572, 0.589] | 0.655 [0.637, 0.674] | +0.386 [+0.376, +0.395] |
| prior | 0.478 [0.468, 0.487] | 0.482 [0.466, 0.499] | +0.489 [+0.478, +0.499] |
| ours_informed | 0.971 [0.968, 0.974] | 0.994 [0.992, 0.996] | reference |

## B. Distribution shift (model trained on the main set; fresh buildings)

| setting | n | macro AUROC | any-fault AUROC | macro F1 | exact match | fix #1 gain captured | fix #1 saving captured |
|---|---|---|---|---|---|---|---|
| fresh | 480 | 0.976 | 0.988 | 0.834 | 0.817 | 0.961 | 0.965 |
| noise_x3 | 480 | 0.910 | 0.884 | 0.623 | 0.517 | 0.929 | 0.934 |
| res_2h | 480 | 0.925 | 0.964 | 0.716 | 0.690 | 0.916 | 0.925 |
| climate_p3 | 480 | 0.964 | 0.986 | 0.811 | 0.792 | 0.956 | 0.959 |
| climate_m3 | 480 | 0.970 | 0.994 | 0.848 | 0.835 | 0.975 | 0.979 |
| severity_x05 | 480 | 0.961 | 0.977 | 0.790 | 0.792 | 0.961 | 0.976 |
| severity_x15 | 480 | 0.961 | 0.993 | 0.788 | 0.727 | 0.949 | 0.950 |
| no_outdoor | 480 | 0.907 | 0.975 | 0.630 | 0.650 | 0.921 | 0.936 |
| window_21d | 480 | 0.964 | 0.989 | 0.795 | 0.777 | 0.958 | 0.967 |
| energy_only | 480 | 0.966 | 0.994 | 0.820 | 0.792 | 0.971 | 0.977 |

## B2. Same stress sets, informed model (design delta-T supplied)

| setting | n | macro AUROC | any-fault AUROC | macro F1 | exact match | fix #1 gain captured | fix #1 saving captured |
|---|---|---|---|---|---|---|---|
| fresh | 480 | 0.980 | 0.991 | 0.858 | 0.829 | 0.960 | 0.964 |
| noise_x3 | 480 | 0.938 | 0.921 | 0.686 | 0.671 | 0.943 | 0.948 |
| res_2h | 480 | 0.932 | 0.970 | 0.742 | 0.710 | 0.920 | 0.932 |
| climate_p3 | 480 | 0.971 | 0.990 | 0.838 | 0.817 | 0.965 | 0.967 |
| climate_m3 | 480 | 0.975 | 0.995 | 0.860 | 0.833 | 0.969 | 0.973 |
| severity_x05 | 480 | 0.965 | 0.977 | 0.798 | 0.804 | 0.960 | 0.974 |
| severity_x15 | 480 | 0.967 | 0.994 | 0.811 | 0.742 | 0.951 | 0.954 |
| no_outdoor | 480 | 0.916 | 0.979 | 0.681 | 0.673 | 0.924 | 0.940 |
| window_21d | 480 | 0.967 | 0.991 | 0.810 | 0.794 | 0.967 | 0.972 |
| energy_only | 480 | 0.969 | 0.996 | 0.840 | 0.808 | 0.964 | 0.970 |

## E. Healthy buildings by design delta-T band (held-out buildings)

False alarm = any-cause probability of 0.5 or more on a building with no fault.

| design delta-T (C) | n | healthy | blind: mean p(any) | blind: false alarms | informed: mean p(any) | informed: false alarms | blind any-fault AUROC | informed any-fault AUROC |
|---|---|---|---|---|---|---|---|---|
| 5-7 | 1530 | 562 | 0.15 | 13% | 0.13 | 11% | 0.977 | 0.982 |
| 7-9 | 1260 | 396 | 0.08 | 7% | 0.06 | 6% | 0.988 | 0.993 |
| 9-11 | 1310 | 391 | 0.05 | 3% | 0.04 | 3% | 0.997 | 0.999 |
| 11-13 | 860 | 270 | 0.03 | 2% | 0.04 | 2% | 0.998 | 0.999 |

## C. Leave one building type out

| setting | n | macro AUROC | any-fault AUROC | macro F1 | exact match | fix #1 gain captured | fix #1 saving captured |
|---|---|---|---|---|---|---|---|
| held out: hotel | 1290 | 0.934 | 0.979 | 0.706 | 0.670 | 0.911 | 0.931 |
| held out: mall | 1450 | 0.952 | 0.986 | 0.778 | 0.754 | 0.940 | 0.939 |
| held out: office | 1210 | 0.971 | 0.990 | 0.845 | 0.793 | 0.971 | 0.973 |
| held out: residential | 1050 | 0.938 | 0.973 | 0.723 | 0.694 | 0.930 | 0.948 |

## D. Held-out seasons

| setting | n | macro AUROC | any-fault AUROC | macro F1 | exact match | fix #1 gain captured | fix #1 saving captured |
|---|---|---|---|---|---|---|---|
| summer_JJA | 1242 | 0.952 | 0.972 | 0.764 | 0.717 | 0.946 | 0.955 |
| winter_DJF | 1283 | 0.957 | 0.994 | 0.776 | 0.765 | 0.937 | 0.953 |

## Constant-flow subtypes (recall at 0.5, held-out buildings)

| subtype | n | mean prob | recall |
|---|---|---|---|
| three_way | 201 | 0.92 | 0.95 |
| stuck_open | 140 | 0.86 | 0.91 |
| mixed | 918 | 0.93 | 0.96 |
