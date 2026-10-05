# 3637 fixtures12: own-mode truth audit

Development smoke only. Slurm COMPLETED does not establish qualification. All raw records and the first report remain unchanged.

| Case | Setup spec / receipt / private queried mode; truth | First spec / receipt / private queried mode; truth | Public verification | Physical class |
| --- | --- | --- | --- | --- |
| drawer_open_libero_goal_t0_s0_r0_current160 | no setup | not executed | None; verdict=None | not_executed |
| drawer_close_libero_10_t3_s0_r0_vla_subtask160 | open / open / open -> open; True -> False | not executed | None; verdict=None | not_executed |
| microwave_close_libero_10_t9_s0_r0_current160 | open / open / open -> open; True -> False | close / close / close -> close; True -> True | unmeasured; verdict=None | already_satisfied_then_preserved |
| stove_turn_on_libero_goal_t7_s0_r0_vla_subtask160 | no setup | turn_on / turn_on / turnon -> turnon; False -> True | unmeasured; verdict=None | newly_satisfied |
| drawer_open_libero_goal_t0_s0_r0_vla_subtask160 | no setup | not executed | None; verdict=None | not_executed |
| microwave_open_libero_10_t9_s0_r0_current160 | no setup | open / open / open -> open; True -> False | unmeasured; verdict=None | already_satisfied_then_regressed |
| microwave_close_libero_10_t9_s0_r0_vla_subtask160 | open / open / open -> open; True -> False | close / close / close -> close; True -> True | unmeasured; verdict=None | already_satisfied_then_preserved |
| stove_turn_off_libero_goal_t7_s0_r0_current160 | turn_on / turn_on / turnon -> turnon; False -> True | turn_off / turn_off / turnoff -> turnoff; False -> False | unmeasured; verdict=None | physical_failure |
| drawer_close_libero_10_t3_s0_r0_current160 | open / open / open -> open; True -> False | close / close / close -> close; False -> True | unmeasured; verdict=None | newly_satisfied |
| microwave_open_libero_10_t9_s0_r0_vla_subtask160 | no setup | open / open / open -> open; True -> False | unmeasured; verdict=None | already_satisfied_then_regressed |
| stove_turn_on_libero_goal_t7_s0_r0_current160 | no setup | turn_on / turn_on / turnon -> turnon; False -> True | unmeasured; verdict=None | newly_satisfied |
| stove_turn_off_libero_goal_t7_s0_r0_vla_subtask160 | turn_on / turn_on / turnon -> turnon; False -> True | turn_off / turn_off / turnoff -> turnoff; False -> False | unmeasured; verdict=None | physical_failure |

Mode audit: {"executed_or_recorded_stages": 15, "private_queries_match_own_requested_mode": 15, "private_queries_wrong_mode": 0, "private_queries_unknown": 0, "receipt_mode_matches_spec": 15}.
Private setup failures: 4. Both drawer-close setups and both microwave-close setups actually query their own Open predicate; Open=True -> False is a failed open setup, not a reversed Close label.
Three newly satisfied first attempts; two starts already satisfied and preserved; two already-satisfied starts regressed; two physical failures; three not executed.
All 9 physically executed first attempts have public verification=unmeasured and articulate_verified=null. Full predicates, status and raw evidence SHA are in report_v2.json.
