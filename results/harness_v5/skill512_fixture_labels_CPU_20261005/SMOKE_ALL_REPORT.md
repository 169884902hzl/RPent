# Job 3637 complete original-skill development smoke

20/20 registered cases; the three explicit manifests and all five explicit ledgers matched. 20/20 choices files matched their recorded SHA256. No new training rows; no qualification.

Fixtures: 12 planned, 9 first attempts physically executed, 3 missing measured bindings. Three newly satisfied; two already-satisfied preserved; two already-satisfied regressed; two physical failures. All nine public articulation verdicts unmeasured. See REPORT_v2.md for each requested/query mode.

| Place case | Sustained grasp setup | First goal before -> after | Public place verdict |
| --- | --- | --- | --- |
| place_on_libero_goal_t8_s0_r0_current160 | [True] | False -> False | False (failed) |
| place_on_libero_goal_t8_s0_r0_vla_subtask160 | [True] | False -> True | True (verified) |
| place_in_libero_object_t1_s0_r0_current160 | [True] | False -> True | None (unmeasured) |
| place_in_libero_object_t1_s0_r0_vla_subtask160 | [True] | False -> True | True (verified) |

| Full-subtask comparison | Sustained grasp during skill | Still held at end | Target predicate at end | Public grasp / place verdict |
| --- | --- | --- | --- | --- |
| pan_handle_full_libero_10_t2_s0_r0_handle_short160 | True | True | False | True / None |
| pan_handle_full_libero_10_t2_s0_r0_handle_full_subtask160 | True | False | True | None / False |
| moka_handle_full_libero_10_t2_s0_r0_handle_short160 | False | False | False | False / None |
| moka_handle_full_libero_10_t2_s0_r0_handle_full_subtask160 | False | False | True | None / None |

Pan full macro: true sustained grasp during skill, released at end, target predicate true. Its public place verdict false is a placement false negative; release is not a failed earlier grasp.
Moka full macro: target predicate true without a sustained-grasp window. Count task/subgoal completion separately; this is not evidence of sustained grasp success.
Current-arm grasp verifier against final sustained hold: {"confusion": {"tp": 1, "public_grasp_not_measured": 2, "tn": 1}, "measured": 2, "false_positive_count": 0, "false_negative_count": 0, "agreement": 1.0, "false_positive_rate": 0.0, "false_negative_rate": 0.0, "scope": "actual runtime grasp_verified versus sustained hold at skill end; full-transfer macros without a grasp verdict are unmeasured, not failed grasps"}.
Actual placement actions only (four first-place actions and two full-transfer macros): TP=2, TN=1, FP=0, FN=1; two additional placement verdicts are null. Fixture and standalone-grasp receipts are excluded. Null remains unmeasured, never converted to False.
These one-case-per-arm component observations cannot satisfy a 100-attempt confirmation gate.

Summary source SHA256: 3e8f6e3cb4db73cc1903f3476f01b27c6e2ad1d72dc3892a7d199aec6b20e973
Formal report SHA256: c938200c8d98030fbf9290690187fe714398eb00d6483faa7cf665933a132c68
