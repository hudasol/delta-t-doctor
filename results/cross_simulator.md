# Cross-simulator results

Simulator A: 5000 windows. Simulator B: structurally different (see docs/CROSS_SIMULATOR.md).

| setting | macro AUROC | any-fault AUROC | fouling | passing_valves | constant_flow | overflow |
|---|---|---|---|---|---|---|
| within A (grouped CV) | 0.966 | 0.990 | 0.988 | 0.964 | 0.995 | 0.919 |
| within B (grouped CV) | 0.884 | 0.935 | 0.675 | 0.965 | 0.970 | 0.924 |
| train A, test B | 0.683 | 0.704 | 0.633 | 0.740 | 0.858 | 0.502 |
| train B, test A | 0.770 | 0.870 | 0.889 | 0.678 | 0.966 | 0.545 |
| train A+B, test A (grouped CV) | 0.965 | 0.989 | 0.986 | 0.962 | 0.995 | 0.915 |
| train A+B, test B (grouped CV) | 0.877 | 0.931 | 0.697 | 0.958 | 0.965 | 0.887 |

| transfer | macro AUROC 95% CI | ECE | out-of-range windows | healthy false alarms (p>=0.5) | logistic macro AUROC |
|---|---|---|---|---|---|
| A to B | 0.683 [0.655, 0.710] | 0.159 | 36% | 88% (n=628) | 0.658 |
| B to A | 0.770 [0.760, 0.778] | 0.072 | 7% | 25% (n=1633) | 0.749 |

Prevalence of each cause (share of windows with the cause present):

| | fouling | passing_valves | constant_flow | overflow |
|---|---|---|---|---|
| A | 0.24 | 0.20 | 0.25 | 0.18 |
| B | 0.19 | 0.05 | 0.26 | 0.20 |
