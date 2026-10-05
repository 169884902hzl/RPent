# 3670 closed-prefix intermediate statistics

Closed 25/400. No confirmation/qualification claim. Eight ledgers were explicitly listed; immutable closed snapshots retained.

| Class/arm | Closed / planned | Sustained during | Sustained at end | Final target | Place TP/TN/FP/FN/unknown | Unique / repeat states |
|---|---|---|---|---|---|---|
| frypan/centre_full_subtask160 | 16/100 | {'True': 16} | {'False': 16} | {'False': 2, 'True': 14} | 0/2/0/14/0 | 16/0 |
| frypan/handle_full_subtask160 | 9/100 | {'True': 8, 'False': 1} | {'False': 7, 'True': 2} | {'True': 5, 'False': 4} | 0/4/0/5/0 | 9/0 |

Confusion is placement verification versus final private target. This complete-subtask protocol does not supply a comparable first-grasp verdict. Grasp-during and grasp-at-end stay separate.

Failure categories:
- frypan/centre_full_subtask160: {'sustained_grasp_then_released_target_not_satisfied': 2, 'target_satisfied': 14}; stop={'chunk_budget': 16}
- frypan/handle_full_subtask160: {'target_satisfied': 5, 'held_at_end_target_not_satisfied': 2, 'no_sustained_grasp_during_subtask': 1, 'sustained_grasp_then_released_target_not_satisfied': 1}; stop={'chunk_budget': 9}

Report SHA256: 21111430cb6a066477dd5c5d147c4c2fc478cca46ce84b5589980d438b615914
