# Original-skill development smoke 3655

Complete: True. Recorded: 12. Infrastructure/execution errors: 0.
No new physical trials, training rows, or qualification.

| Case | Official target before → after | True sustained grasp during / at end | Public verdict | Actual first actions |
|---|---|---|---|---|
| drawer_open_libero_goal_t0_s0_r0_current160 | False → True | None / None | True (verified) | 300 |
| drawer_close_libero_10_t3_s0_r0_vla_subtask160 | False → True | None / None | None (unmeasured) | 800 |
| microwave_close_libero_10_t9_s0_r0_current160 | True → True | None / None | None (unmeasured) | 800 |
| stove_turn_on_libero_goal_t7_s0_r0_vla_subtask160 | False → True | None / None | True (verified) | 223 |
| drawer_open_libero_goal_t0_s0_r0_vla_subtask160 | False → False | None / None | None (unmeasured) | 800 |
| microwave_open_libero_10_t9_s0_r0_current160 | True → False | None / None | None (unmeasured) | 800 |
| microwave_close_libero_10_t9_s0_r0_vla_subtask160 | True → True | None / None | None (unmeasured) | 800 |
| stove_turn_off_libero_goal_t7_s0_r0_current160 | False → False | None / None | None (unmeasured) | 542 |
| drawer_close_libero_10_t3_s0_r0_current160 | False → False | None / None | False (failed) | 800 |
| microwave_open_libero_10_t9_s0_r0_vla_subtask160 | True → False | None / None | None (unmeasured) | 800 |
| stove_turn_on_libero_goal_t7_s0_r0_current160 | False → True | None / None | None (unmeasured) | 220 |
| stove_turn_off_libero_goal_t7_s0_r0_vla_subtask160 | False → True | None / None | True (verified) | 508 |

| Case | Saved independent frames | Saved-condition contradictions | Same-frame private samples |
|---|---|---|---|
| drawer_open_libero_goal_t0_s0_r0_current160 | 0 | 0 | 0 |
| drawer_close_libero_10_t3_s0_r0_vla_subtask160 | 0 | 0 | 0 |
| microwave_close_libero_10_t9_s0_r0_current160 | 0 | 0 | 0 |
| stove_turn_on_libero_goal_t7_s0_r0_vla_subtask160 | 0 | 0 | 0 |
| drawer_open_libero_goal_t0_s0_r0_vla_subtask160 | 0 | 0 | 0 |
| microwave_open_libero_10_t9_s0_r0_current160 | 0 | 0 | 0 |
| microwave_close_libero_10_t9_s0_r0_vla_subtask160 | 0 | 0 | 0 |
| stove_turn_off_libero_goal_t7_s0_r0_current160 | 0 | 0 | 0 |
| drawer_close_libero_10_t3_s0_r0_current160 | 0 | 0 | 0 |
| microwave_open_libero_10_t9_s0_r0_vla_subtask160 | 0 | 0 | 0 |
| stove_turn_on_libero_goal_t7_s0_r0_current160 | 0 | 0 | 0 |
| stove_turn_off_libero_goal_t7_s0_r0_vla_subtask160 | 0 | 0 | 0 |

Single-frame witnesses are distinct from runtime two-frame grasp verdicts. A later successful release does not undo a prior sustained grasp.
Saved false/null evidence is retained. Contradictions expose the old verifier logic; these records are not silently relabeled.
Report SHA256: 8242d8a7c43dd3436fc22335a90d09e933103ee1c752a2689570a286ecb383f3. Exact raw paths, hashes, conditions and requested-mode audit are in report.json.
