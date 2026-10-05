# Closed original-skill development audit

No replay, qualification, freeze, or new training rows.

| Case | 3637 physical class / predicate | 3643 physical class / predicate | 3643 public verification |
|---|---|---|---|
| drawer_close_libero_10_t3_s0_r0_current160 | newly_satisfied: False -> True | already_satisfied_preserved: True -> True | None (unmeasured) |
| drawer_close_libero_10_t3_s0_r0_vla_subtask160 | not_executed: None -> None | already_satisfied_preserved: True -> True | None (unmeasured) |
| drawer_open_libero_goal_t0_s0_r0_current160 | not_executed: None -> None | newly_satisfied: False -> True | None (unmeasured) |
| drawer_open_libero_goal_t0_s0_r0_vla_subtask160 | not_executed: None -> None | not_executed: None -> None | None (None) |
| microwave_close_libero_10_t9_s0_r0_current160 | already_satisfied_preserved: True -> True | already_satisfied_preserved: True -> True | None (unmeasured) |
| microwave_close_libero_10_t9_s0_r0_vla_subtask160 | already_satisfied_preserved: True -> True | physical_failure: False -> False | None (unmeasured) |
| microwave_open_libero_10_t9_s0_r0_current160 | already_satisfied_regressed: True -> False | already_satisfied_regressed: True -> False | None (unmeasured) |
| microwave_open_libero_10_t9_s0_r0_vla_subtask160 | already_satisfied_regressed: True -> False | already_satisfied_regressed: True -> False | None (unmeasured) |
| moka_handle_full_libero_10_t2_s0_r0_handle_full_subtask160 | newly_satisfied: False -> True | newly_satisfied: False -> True | None (unmeasured) |
| moka_handle_full_libero_10_t2_s0_r0_handle_short160 | physical_failure: False -> False | physical_failure: False -> False | True (verified) |
| pan_handle_full_libero_10_t2_s0_r0_handle_full_subtask160 | newly_satisfied: False -> True | newly_satisfied: False -> True | False (failed) |
| pan_handle_full_libero_10_t2_s0_r0_handle_short160 | physical_failure: False -> False | physical_failure: False -> False | True (verified) |
| place_in_libero_object_t1_s0_r0_current160 | newly_satisfied: False -> True | newly_satisfied: False -> True | None (unmeasured) |
| place_in_libero_object_t1_s0_r0_vla_subtask160 | newly_satisfied: False -> True | newly_satisfied: False -> True | True (verified) |
| place_on_libero_goal_t8_s0_r0_current160 | physical_failure: False -> False | physical_failure: False -> False | False (failed) |
| place_on_libero_goal_t8_s0_r0_vla_subtask160 | newly_satisfied: False -> True | newly_satisfied: False -> True | True (verified) |
| stove_turn_off_libero_goal_t7_s0_r0_current160 | physical_failure: False -> False | newly_satisfied: False -> True | None (unmeasured) |
| stove_turn_off_libero_goal_t7_s0_r0_vla_subtask160 | physical_failure: False -> False | physical_failure: False -> False | True (verified) |
| stove_turn_on_libero_goal_t7_s0_r0_current160 | newly_satisfied: False -> True | newly_satisfied: False -> True | None (unmeasured) |
| stove_turn_on_libero_goal_t7_s0_r0_vla_subtask160 | newly_satisfied: False -> True | newly_satisfied: False -> True | True (verified) |

Fixture classes: {"already_satisfied_preserved": 3, "already_satisfied_regressed": 2, "newly_satisfied": 4, "not_executed": 1, "physical_failure": 2}.
Placement-only confusion: {"fn": 1, "tn": 1, "tp": 2, "unmeasured_private_positive": 2}.
Public null stays unmeasured. Macro final release does not negate an earlier sustained grasp.

Box: original 47 known + continuation 52 known + one preserved executed unknown.
Known truth: {"confusion": {"FN": 1, "FP": 0, "TN": 0, "TP": 98, "unknown_truth": 1}, "contact_execution_counts": {"executed": 100}, "error_rows": 1, "failure_reason_counts": {}, "false_negative": {"all_known_rate": 0.010101010101010102, "conditional_rate": 0.010101010101010102, "count": 1, "true_positive_denominator": 99}, "false_positive": {"all_known_rate": 0.0, "conditional_rate": null, "count": 0, "true_negative_denominator": 0}, "known_truth": 99, "maximum_init_tuple_repetitions": 1, "repeated_original_init_rows": 0, "repeated_state_sha_rows": 0, "rows": 100, "state_sha_rows": 100, "truth_success": 99, "truth_success_over_planned_lower_bound": 0.99, "truth_success_over_planned_upper_bound": 1.0, "truth_success_rate": 1.0, "truth_success_wilson95": [0.9626467879321726, 1.0], "unique_original_init_tuples": 100, "unique_state_sha": 100, "verifier_agreement": 0.98989898989899, "verifier_agreement_wilson95": [0.9449846853541274, 0.9982146927208301], "visual_verified": 98}.
No unknown replacement and no complete-confirmation claim. Per-case raw paths, original/new receipts and SHA256 are in the JSON reports.
