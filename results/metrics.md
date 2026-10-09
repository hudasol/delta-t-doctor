# Evaluation results (simulated buildings)

All numbers come from the physics simulator in `deltat_doctor.sim`. They measure how well the tool recovers *simulated* faults. They are not field accuracy.

## A. Held-out buildings (5-fold grouped CV)

| setting | n | macro AUROC | any-fault AUROC | macro F1 | exact match | fix #1 gain captured | fix #1 saving captured |
|---|---|---|---|---|---|---|---|
| ours_gbdt | 5000 | 0.967 | 0.995 | 0.835 | 0.787 | 0.970 | 0.976 |
| logistic | 5000 | 0.922 | 0.985 | 0.690 | 0.670 | 0.910 | 0.941 |
| expert_rules | 5000 | 0.601 | 0.675 | 0.362 | 0.312 | 0.410 | 0.415 |
| prior | 5000 | 0.478 | 0.480 | 0.000 | 0.298 | 0.530 | 0.597 |
| ours_informed | 5000 | 0.979 | 0.998 | 0.875 | 0.830 | 0.975 | 0.980 |

Per-cause detail for the tool (held-out buildings):

| cause | prevalence | AUROC | F1@0.5 | Brier | delta-T gain MAE (C) |
|---|---|---|---|---|---|
| fouling | 0.25 | 0.991 | 0.918 | 0.029 | 0.11 |
| passing_valves | 0.21 | 0.957 | 0.780 | 0.063 | 0.11 |
| constant_flow | 0.26 | 0.997 | 0.963 | 0.014 | 0.19 |
| overflow | 0.20 | 0.924 | 0.681 | 0.081 | 0.14 |

## B. Distribution shift (model trained on the main set; fresh buildings)

| setting | n | macro AUROC | any-fault AUROC | macro F1 | exact match | fix #1 gain captured | fix #1 saving captured |
|---|---|---|---|---|---|---|---|
| fresh | 480 | 0.979 | 0.999 | 0.863 | 0.831 | 0.969 | 0.975 |
| noise_x3 | 480 | 0.902 | 0.946 | 0.642 | 0.463 | 0.916 | 0.919 |
| res_2h | 480 | 0.932 | 0.940 | 0.761 | 0.648 | 0.921 | 0.944 |
| climate_p3 | 480 | 0.969 | 0.994 | 0.838 | 0.798 | 0.973 | 0.979 |
| climate_m3 | 480 | 0.972 | 0.997 | 0.855 | 0.819 | 0.976 | 0.984 |
| severity_x05 | 480 | 0.951 | 0.986 | 0.811 | 0.790 | 0.965 | 0.982 |
| severity_x15 | 480 | 0.962 | 1.000 | 0.828 | 0.754 | 0.949 | 0.952 |
| no_outdoor | 480 | 0.911 | 0.986 | 0.689 | 0.635 | 0.928 | 0.957 |
| window_21d | 480 | 0.964 | 0.999 | 0.818 | 0.802 | 0.968 | 0.979 |
| energy_only | 480 | 0.966 | 1.000 | 0.834 | 0.800 | 0.959 | 0.972 |

## B2. Same stress sets, informed model (design delta-T supplied)

| setting | n | macro AUROC | any-fault AUROC | macro F1 | exact match | fix #1 gain captured | fix #1 saving captured |
|---|---|---|---|---|---|---|---|
| fresh | 480 | 0.987 | 0.999 | 0.897 | 0.869 | 0.972 | 0.980 |
| noise_x3 | 480 | 0.972 | 0.996 | 0.744 | 0.731 | 0.915 | 0.926 |
| res_2h | 480 | 0.957 | 0.976 | 0.824 | 0.735 | 0.910 | 0.934 |
| climate_p3 | 480 | 0.982 | 1.000 | 0.869 | 0.829 | 0.980 | 0.983 |
| climate_m3 | 480 | 0.982 | 0.999 | 0.893 | 0.860 | 0.967 | 0.980 |
| severity_x05 | 480 | 0.971 | 0.995 | 0.833 | 0.808 | 0.975 | 0.989 |
| severity_x15 | 480 | 0.975 | 1.000 | 0.863 | 0.796 | 0.951 | 0.957 |
| no_outdoor | 480 | 0.963 | 0.996 | 0.820 | 0.762 | 0.964 | 0.977 |
| window_21d | 480 | 0.976 | 1.000 | 0.857 | 0.829 | 0.977 | 0.983 |
| energy_only | 480 | 0.977 | 1.000 | 0.850 | 0.812 | 0.970 | 0.988 |

## E. Healthy buildings by design delta-T band (held-out buildings)

False alarm = any-cause probability of 0.5 or more on a building with no fault.

| design delta-T (C) | n | healthy | blind: mean p(any) | blind: false alarms | informed: mean p(any) | informed: false alarms | blind any-fault AUROC | informed any-fault AUROC |
|---|---|---|---|---|---|---|---|---|
| 5-7 | 1530 | 461 | 0.11 | 7% | 0.09 | 5% | 0.991 | 0.995 |
| 7-9 | 1260 | 375 | 0.05 | 3% | 0.04 | 2% | 0.996 | 0.999 |
| 9-11 | 1310 | 381 | 0.03 | 1% | 0.03 | 2% | 0.997 | 0.997 |
| 11-13 | 860 | 265 | 0.02 | 1% | 0.03 | 1% | 1.000 | 1.000 |

## C. Leave one building type out

| setting | n | macro AUROC | any-fault AUROC | macro F1 | exact match | fix #1 gain captured | fix #1 saving captured |
|---|---|---|---|---|---|---|---|
| held out: hotel | 1290 | 0.933 | 0.987 | 0.738 | 0.688 | 0.906 | 0.936 |
| held out: mall | 1450 | 0.955 | 0.987 | 0.808 | 0.750 | 0.922 | 0.921 |
| held out: office | 1210 | 0.964 | 0.967 | 0.822 | 0.717 | 0.969 | 0.964 |
| held out: residential | 1050 | 0.938 | 0.995 | 0.723 | 0.673 | 0.930 | 0.964 |

## D. Held-out seasons

| setting | n | macro AUROC | any-fault AUROC | macro F1 | exact match | fix #1 gain captured | fix #1 saving captured |
|---|---|---|---|---|---|---|---|
| summer_JJA | 1242 | 0.948 | 0.977 | 0.771 | 0.681 | 0.942 | 0.958 |
| winter_DJF | 1283 | 0.963 | 0.996 | 0.821 | 0.793 | 0.960 | 0.973 |

## Constant-flow subtypes (recall at 0.5, held-out buildings)

| subtype | n | mean prob | recall |
|---|---|---|---|
| three_way | 202 | 0.95 | 0.97 |
| stuck_open | 155 | 0.89 | 0.92 |
| mixed | 953 | 0.95 | 0.97 |
