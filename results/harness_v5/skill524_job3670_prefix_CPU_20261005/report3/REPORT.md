# 3670 closed-prefix intermediate statistics

Closed 106/400. No confirmation/qualification claim. Eight ledgers were explicitly listed; immutable closed snapshots retained.

| Class/arm | Closed / planned | Sustained during | Sustained at end | Final target | Place TP/TN/FP/FN/unknown | Unique / repeat states |
|---|---|---|---|---|---|---|
| frypan/centre_full_subtask160 | 68/100 | {'True': 65, 'False': 3} | {'False': 68} | {'False': 7, 'True': 61} | 0/7/0/61/0 | 49/19 |
| frypan/handle_full_subtask160 | 38/100 | {'True': 27, 'False': 11} | {'False': 36, 'True': 2} | {'True': 24, 'False': 14} | 0/14/0/24/0 | 36/2 |

Confusion is placement verification versus final private target. This complete-subtask protocol does not supply a comparable first-grasp verdict. Grasp-during and grasp-at-end stay separate.

Failure categories:
- frypan/centre_full_subtask160: {'sustained_grasp_then_released_target_not_satisfied': 4, 'target_satisfied': 61, 'no_sustained_grasp_during_subtask': 3}; stop={'chunk_budget': 68}
- frypan/handle_full_subtask160: {'target_satisfied': 24, 'held_at_end_target_not_satisfied': 2, 'no_sustained_grasp_during_subtask': 11, 'sustained_grasp_then_released_target_not_satisfied': 1}; stop={'chunk_budget': 38}

Report SHA256: f4a013a4cf119f5d356351b87c7b668340099ad1475645f4c4586bcd5ac5530e
