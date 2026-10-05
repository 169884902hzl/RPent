# Original-skill development smoke 3648

Complete: True. Recorded: 4. Infrastructure/execution errors: 0.
No new physical trials, training rows, or qualification.

| Case | Official target before → after | True sustained grasp during / at end | Public verdict | Actual first actions |
|---|---|---|---|---|
| pan_handle_full_libero_10_t2_s0_r0_centre_full_subtask160 | False → True | True / False | False (failed) | 857 |
| pan_handle_full_libero_10_t2_s0_r0_handle_full_subtask160 | False → True | True / False | False (failed) | 845 |
| moka_handle_full_libero_10_t2_s0_r0_centre_full_subtask160 | False → False | False / False | False (failed) | 848 |
| moka_handle_full_libero_10_t2_s0_r0_handle_full_subtask160 | False → False | True / False | None (unmeasured) | 847 |

| Case | Saved independent frames | Saved-condition contradictions | Same-frame private samples |
|---|---|---|---|
| pan_handle_full_libero_10_t2_s0_r0_centre_full_subtask160 | 1 | 2 | 0 |
| pan_handle_full_libero_10_t2_s0_r0_handle_full_subtask160 | 4 | 1 | 0 |
| moka_handle_full_libero_10_t2_s0_r0_centre_full_subtask160 | 31 | 1 | 0 |
| moka_handle_full_libero_10_t2_s0_r0_handle_full_subtask160 | 15 | 1 | 0 |

Single-frame witnesses are distinct from runtime two-frame grasp verdicts. A later successful release does not undo a prior sustained grasp.
Saved false/null evidence is retained. Contradictions expose the old verifier logic; these records are not silently relabeled.
Report SHA256: 40d0e2026bfdea47b50e5e251a3f3a37becac5b2ac8aadb913e5dd6fef3d611c. Exact raw paths, hashes, conditions and requested-mode audit are in report.json.
