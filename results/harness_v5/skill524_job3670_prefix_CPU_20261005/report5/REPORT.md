# 3670 closed-prefix intermediate statistics

Closed 162/400. No confirmation/qualification claim. Eight ledgers were explicitly listed; immutable closed snapshots retained.

| Class/arm | Closed / planned | Sustained during | Sustained at end | Final target | Place TP/TN/FP/FN/unknown | Unique / repeat states |
|---|---|---|---|---|---|---|
| frypan/centre_full_subtask160 | 100/100 | {'True': 96, 'False': 4} | {'False': 100} | {'False': 9, 'True': 91} | 0/9/0/91/0 | 50/50 |
| frypan/handle_full_subtask160 | 58/100 | {'True': 38, 'False': 20} | {'False': 56, 'True': 2} | {'True': 33, 'False': 25} | 0/25/0/33/0 | 49/9 |
| moka pot/centre_full_subtask160 | 4/100 | {'True': 2, 'False': 2} | {'False': 4} | {'True': 2, 'False': 2} | 1/1/0/0/2 | 4/0 |

Confusion is placement verification versus final private target. This complete-subtask protocol does not supply a comparable first-grasp verdict. Grasp-during and grasp-at-end stay separate.

Failure categories:
- frypan/centre_full_subtask160: {'sustained_grasp_then_released_target_not_satisfied': 5, 'target_satisfied': 91, 'no_sustained_grasp_during_subtask': 4}; stop={'chunk_budget': 100}
- frypan/handle_full_subtask160: {'target_satisfied': 33, 'held_at_end_target_not_satisfied': 2, 'no_sustained_grasp_during_subtask': 20, 'sustained_grasp_then_released_target_not_satisfied': 3}; stop={'chunk_budget': 58}
- moka pot/centre_full_subtask160: {'target_satisfied': 2, 'no_sustained_grasp_during_subtask': 2}; stop={'chunk_budget': 4}

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
| frypan/handle_full_subtask160 | nominal (descriptive) | sustained_during | 38/58 | 0 | 52.67–76.44% |
| frypan/handle_full_subtask160 | nominal (descriptive) | sustained_at_end | 2/58 | 0 | 0.95–11.73% |
| frypan/handle_full_subtask160 | nominal (descriptive) | target_truth | 33/58 | 0 | 44.12–68.82% |
| frypan/handle_full_subtask160 | rep0 unique scene | sustained_during | 31/49 | 0 | 49.27–75.33% |
| frypan/handle_full_subtask160 | rep0 unique scene | sustained_at_end | 2/49 | 0 | 1.13–13.71% |
| frypan/handle_full_subtask160 | rep0 unique scene | target_truth | 27/49 | 0 | 41.32–68.15% |
| moka pot/centre_full_subtask160 | nominal (descriptive) | sustained_during | 2/4 | 0 | 15.00–85.00% |
| moka pot/centre_full_subtask160 | nominal (descriptive) | sustained_at_end | 0/4 | 0 | 0.00–48.99% |
| moka pot/centre_full_subtask160 | nominal (descriptive) | target_truth | 2/4 | 0 | 15.00–85.00% |
| moka pot/centre_full_subtask160 | rep0 unique scene | sustained_during | 2/4 | 0 | 15.00–85.00% |
| moka pot/centre_full_subtask160 | rep0 unique scene | sustained_at_end | 0/4 | 0 | 0.00–48.99% |
| moka pot/centre_full_subtask160 | rep0 unique scene | target_truth | 2/4 | 0 | 15.00–85.00% |

Report SHA256: 90e7f227b6fa699242277699ab1ffdcc99c5da70dc7d1f4620c5f60666febc60
