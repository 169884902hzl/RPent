# 3670 closed-prefix intermediate statistics

Closed 183/400. No confirmation/qualification claim. Eight ledgers were explicitly listed; immutable closed snapshots retained.

| Class/arm | Closed / planned | Sustained during | Sustained at end | Final target | Place TP/TN/FP/FN/unknown | Unique / repeat states |
|---|---|---|---|---|---|---|
| frypan/centre_full_subtask160 | 100/100 | {'True': 96, 'False': 4} | {'False': 100} | {'False': 9, 'True': 91} | 0/9/0/91/0 | 50/50 |
| frypan/handle_full_subtask160 | 72/100 | {'True': 50, 'False': 22} | {'False': 69, 'True': 3} | {'True': 42, 'False': 30} | 1/29/0/41/1 | 50/22 |
| moka pot/centre_full_subtask160 | 11/100 | {'True': 6, 'False': 5} | {'False': 10, 'True': 1} | {'True': 5, 'False': 6} | 2/2/0/0/7 | 11/0 |

Confusion is placement verification versus final private target. This complete-subtask protocol does not supply a comparable first-grasp verdict. Grasp-during and grasp-at-end stay separate.

Failure categories:
- frypan/centre_full_subtask160: {'sustained_grasp_then_released_target_not_satisfied': 5, 'target_satisfied': 91, 'no_sustained_grasp_during_subtask': 4}; stop={'chunk_budget': 100}
- frypan/handle_full_subtask160: {'target_satisfied': 42, 'held_at_end_target_not_satisfied': 3, 'no_sustained_grasp_during_subtask': 22, 'sustained_grasp_then_released_target_not_satisfied': 5}; stop={'chunk_budget': 72}
- moka pot/centre_full_subtask160: {'target_satisfied': 5, 'no_sustained_grasp_during_subtask': 5, 'sustained_grasp_then_released_target_not_satisfied': 1}; stop={'chunk_budget': 11}

## Wilson 95% intervals

Nominal repeated rows are descriptive only. Repetition0 retains the first explicit occurrence of each scene; unknown is separate and excluded from known-label denominators. Neither cohort establishes qualification.

| Class/arm | Cohort | Metric | Success / known | Unknown | Wilson95% |
|---|---|---|---|---|---|
| frypan/centre_full_subtask160 | nominal (descriptive) | sustained_during | 96/100 | 0 | 90.16–98.43% |
| frypan/centre_full_subtask160 | nominal (descriptive) | sustained_at_end | 0/100 | 0 | 0.00–3.70% |
| frypan/centre_full_subtask160 | nominal (descriptive) | target_truth | 91/100 | 0 | 83.77–95.19% |
| frypan/centre_full_subtask160 | rep0 unique scene | sustained_during | 47/50 | 0 | 83.78–97.94% |
| frypan/centre_full_subtask160 | rep0 unique scene | sustained_at_end | 0/50 | 0 | 0.00–7.13% |
| frypan/centre_full_subtask160 | rep0 unique scene | target_truth | 44/50 | 0 | 76.20–94.38% |
| frypan/handle_full_subtask160 | nominal (descriptive) | sustained_during | 50/72 | 0 | 58.05–78.87% |
| frypan/handle_full_subtask160 | nominal (descriptive) | sustained_at_end | 3/72 | 0 | 1.43–11.55% |
| frypan/handle_full_subtask160 | nominal (descriptive) | target_truth | 42/72 | 0 | 46.81–69.01% |
| frypan/handle_full_subtask160 | rep0 unique scene | sustained_during | 31/50 | 0 | 48.15–74.14% |
| frypan/handle_full_subtask160 | rep0 unique scene | sustained_at_end | 2/50 | 0 | 1.10–13.46% |
| frypan/handle_full_subtask160 | rep0 unique scene | target_truth | 27/50 | 0 | 40.40–67.03% |
| moka pot/centre_full_subtask160 | nominal (descriptive) | sustained_during | 6/11 | 0 | 28.01–78.73% |
| moka pot/centre_full_subtask160 | nominal (descriptive) | sustained_at_end | 1/11 | 0 | 1.62–37.74% |
| moka pot/centre_full_subtask160 | nominal (descriptive) | target_truth | 5/11 | 0 | 21.27–71.99% |
| moka pot/centre_full_subtask160 | rep0 unique scene | sustained_during | 6/11 | 0 | 28.01–78.73% |
| moka pot/centre_full_subtask160 | rep0 unique scene | sustained_at_end | 1/11 | 0 | 1.62–37.74% |
| moka pot/centre_full_subtask160 | rep0 unique scene | target_truth | 5/11 | 0 | 21.27–71.99% |

Report SHA256: e68c05c992ad4c493473fa585eae58a3e14a799f59e03fd3c50ce5eb7bc85667
