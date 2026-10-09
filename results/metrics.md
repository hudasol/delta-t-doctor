# Evaluation results (simulated buildings)

All numbers come from the physics simulator in `deltat_doctor.sim`. They measure how well the tool recovers *simulated* faults. They are not field accuracy.

## A. Held-out buildings (5-fold grouped CV)

| setting | n | macro AUROC | any-fault AUROC | macro F1 | exact match | fix #1 gain captured | fix #1 saving captured |
|---|---|---|---|---|---|---|---|
| ours_gbdt | 4000 | 0.974 | 0.998 | 0.862 | 0.804 | 0.973 | 0.986 |
| logistic | 4000 | 0.945 | 0.991 | 0.791 | 0.701 | 0.921 | 0.969 |
| expert_rules | 4000 | 0.601 | 0.685 | 0.363 | 0.304 | 0.389 | 0.393 |
| prior | 4000 | 0.479 | 0.482 | 0.000 | 0.292 | 0.536 | 0.707 |

Per-cause detail for the tool (held-out buildings):

| cause | prevalence | AUROC | F1@0.5 | Brier | delta-T gain MAE (C) |
|---|---|---|---|---|---|
| fouling | 0.25 | 0.992 | 0.923 | 0.027 | 0.11 |
| passing_valves | 0.23 | 0.956 | 0.788 | 0.067 | 0.13 |
| constant_flow | 0.27 | 0.996 | 0.965 | 0.015 | 0.23 |
| overflow | 0.23 | 0.953 | 0.774 | 0.068 | 0.15 |

## B. Distribution shift (model trained on the main set; fresh buildings)

| setting | n | macro AUROC | any-fault AUROC | macro F1 | exact match | fix #1 gain captured | fix #1 saving captured |
|---|---|---|---|---|---|---|---|
| fresh | 480 | 0.982 | 0.999 | 0.877 | 0.844 | 0.975 | 0.986 |
| noise_x3 | 480 | 0.955 | 0.982 | 0.758 | 0.665 | 0.929 | 0.979 |
| res_2h | 480 | 0.947 | 0.969 | 0.806 | 0.702 | 0.939 | 0.967 |
| climate_p3 | 480 | 0.976 | 0.995 | 0.873 | 0.829 | 0.982 | 0.991 |
| climate_m3 | 480 | 0.982 | 0.999 | 0.884 | 0.850 | 0.977 | 0.981 |
| severity_x05 | 480 | 0.952 | 0.996 | 0.796 | 0.765 | 0.961 | 0.994 |
| severity_x15 | 480 | 0.970 | 1.000 | 0.848 | 0.775 | 0.967 | 0.983 |
| no_outdoor | 480 | 0.952 | 0.993 | 0.795 | 0.738 | 0.926 | 0.977 |
| window_21d | 480 | 0.970 | 1.000 | 0.844 | 0.802 | 0.972 | 0.991 |
| energy_only | 480 | 0.971 | 0.999 | 0.846 | 0.798 | 0.963 | 0.990 |

## C. Leave one building type out

| setting | n | macro AUROC | any-fault AUROC | macro F1 | exact match | fix #1 gain captured | fix #1 saving captured |
|---|---|---|---|---|---|---|---|
| held out: hotel | 1040 | 0.931 | 0.992 | 0.747 | 0.676 | 0.907 | 0.967 |
| held out: mall | 1160 | 0.974 | 0.993 | 0.862 | 0.784 | 0.928 | 0.939 |
| held out: office | 970 | 0.971 | 0.992 | 0.855 | 0.752 | 0.980 | 0.980 |
| held out: residential | 830 | 0.948 | 0.999 | 0.760 | 0.687 | 0.937 | 0.981 |

## D. Held-out seasons

| setting | n | macro AUROC | any-fault AUROC | macro F1 | exact match | fix #1 gain captured | fix #1 saving captured |
|---|---|---|---|---|---|---|---|
| summer_JJA | 995 | 0.959 | 0.991 | 0.812 | 0.712 | 0.953 | 0.971 |
| winter_DJF | 1019 | 0.971 | 0.999 | 0.854 | 0.796 | 0.959 | 0.972 |

## Constant-flow subtypes (recall at 0.5, held-out buildings)

| subtype | n | mean prob | recall |
|---|---|---|---|
| three_way | 161 | 0.95 | 0.96 |
| stuck_open | 132 | 0.87 | 0.90 |
| mixed | 776 | 0.95 | 0.97 |
