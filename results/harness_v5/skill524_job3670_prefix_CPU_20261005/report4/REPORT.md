# 3670 closed-prefix intermediate statistics

Closed 122/400. No confirmation/qualification claim. Eight ledgers were explicitly listed; immutable closed snapshots retained.

| Class/arm | Closed / planned | Sustained during | Sustained at end | Final target | Place TP/TN/FP/FN/unknown | Unique / repeat states |
|---|---|---|---|---|---|---|
| frypan/centre_full_subtask160 | 80/100 | {'True': 77, 'False': 3} | {'False': 80} | {'False': 8, 'True': 72} | 0/8/0/72/0 | 50/30 |
| frypan/handle_full_subtask160 | 42/100 | {'True': 29, 'False': 13} | {'False': 40, 'True': 2} | {'True': 25, 'False': 17} | 0/17/0/25/0 | 39/3 |

Confusion is placement verification versus final private target. This complete-subtask protocol does not supply a comparable first-grasp verdict. Grasp-during and grasp-at-end stay separate.

Failure categories:
- frypan/centre_full_subtask160: {'sustained_grasp_then_released_target_not_satisfied': 5, 'target_satisfied': 72, 'no_sustained_grasp_during_subtask': 3}; stop={'chunk_budget': 80}
- frypan/handle_full_subtask160: {'target_satisfied': 25, 'held_at_end_target_not_satisfied': 2, 'no_sustained_grasp_during_subtask': 13, 'sustained_grasp_then_released_target_not_satisfied': 2}; stop={'chunk_budget': 42}

Report SHA256: dcbee1e01e484fe8441aeb2af30e80f84e46de98a0bdf7557da7d4f4896ce70b
