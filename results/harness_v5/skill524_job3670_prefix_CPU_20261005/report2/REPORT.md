# 3670 closed-prefix intermediate statistics

Closed 62/400. No confirmation/qualification claim. Eight ledgers were explicitly listed; immutable closed snapshots retained.

| Class/arm | Closed / planned | Sustained during | Sustained at end | Final target | Place TP/TN/FP/FN/unknown | Unique / repeat states |
|---|---|---|---|---|---|---|
| frypan/centre_full_subtask160 | 38/100 | {'True': 37, 'False': 1} | {'False': 38} | {'False': 4, 'True': 34} | 0/4/0/34/0 | 38/0 |
| frypan/handle_full_subtask160 | 24/100 | {'True': 18, 'False': 6} | {'False': 22, 'True': 2} | {'True': 15, 'False': 9} | 0/9/0/15/0 | 24/0 |

Confusion is placement verification versus final private target. This complete-subtask protocol does not supply a comparable first-grasp verdict. Grasp-during and grasp-at-end stay separate.

Failure categories:
- frypan/centre_full_subtask160: {'sustained_grasp_then_released_target_not_satisfied': 3, 'target_satisfied': 34, 'no_sustained_grasp_during_subtask': 1}; stop={'chunk_budget': 38}
- frypan/handle_full_subtask160: {'target_satisfied': 15, 'held_at_end_target_not_satisfied': 2, 'no_sustained_grasp_during_subtask': 6, 'sustained_grasp_then_released_target_not_satisfied': 1}; stop={'chunk_budget': 24}

Report SHA256: a7429dd96767b3bc83c98ef4ac5aaa3e2b67a7bdb5923f9c3f694ab815ba04eb
