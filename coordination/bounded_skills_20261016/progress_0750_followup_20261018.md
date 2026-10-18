# 10/18 07:50 follow-up: measured boundary failures, public legality and profiles

8822 first-chunk control sequences and flattened MuJoCo state hashes are identical at equal ticks (bowl190 / box175 / container316; max state error0). Model/data/controller/gripper snapshots also match. RNG snapshots differ and are retained separately. The failing box/container refresh clears the old committed contact identity: 15 grasp-related candidates, including lift, disappear. These states have no verified held payload yet. Do not describe this as losing an already-held payload.

Passive refresh and zero-motion failed scans now retain the committed measured grasp. The private upper-bound selector also stops an already nonempty prefix before a redundant observe; the executor already performs each receipt measurement. Wrist scanning still undergoes full sweep collision screening; zero physical ticks on an obstructed scan are valid. Repeated no-change refresh remains no_effect under the existing loop rule.

Fixed-source4335578 paired development run9001 closed5/5 states. User-requested three pairs all succeeded in both arms; two extra bowl states retain one both-success and one both-failed result. No successful state regressed in this focused comparison. These are original-task oracle upper bounds with pi0.5 disabled, not model or confirmation scores.

| State | Old success | New success | Decisions old→new | Sim steps old→new | Wall s old→new |
| --- | --- | --- | ---: | ---: | ---: |
| bowl_transfer_libero_spatial_t0_s0 | True | True | 5→3 | 265→265 | 465.08→387.75 |
| bowl_transfer_libero_spatial_t0_s2 | False | False | 8→7 | 203→203 | 587.15→630.79 |
| bowl_transfer_libero_spatial_t0_s3 | True | True | 5→2 | 302→302 | 489.33→352.97 |
| box_transfer_libero_object_t0_s4 | True | True | 5→2 | 410→409 | 279.60→245.60 |
| container_libero_object_t2_s0 | True | True | 4→2 | 584→588 | 243.80→197.64 |

The failed bowl init2 still has a public boundary pixel that is not associated with its held instance and blocks19 routes. Saved RGB-D places the pixel on the visible lower silhouette; the current SAM mask omits it. This observation does not authorize deleting an obstacle or loosening clearance. No new private truth coordinate enters the runtime.

Public sequence legality is now `public-request-legal/2` (`bounded-skills/3`, judge/6). `legal_after(request,prefix)` uses only frozen public fields, known collision/IK flags and published held prerequisites. It does not call the planner. 268 integrated CPU tests, Codex2 bridge25 tests/20subtests and823 saved positions pass; selected/acceptable out-of-legal and illegal-prefix counts are0. Source commit79d1d59 is pushed. Schema SHA `df17c6c49e4992247ab8ff37ebf528f893ac6887ea8cf946e25668aca110b4aa`; contract SHA `7e898e3bd4e8f4c7a4e9951d897cc1fe682037ee35ee4d6d5cc1f52606e2f49c`. New paired run9008 uses this exact version and is closed3/3, all success in both arms. Do not relabel9001 with the newer contract. An independent source validator recounts9008 actual21requests/43label positions: exact legal denominators and selected/acceptable memberships all pass, zero violations.

Whole-episode exclusive wall buckets for all10 arms are in `reports/wall_time_current_plane_pairs_20261018.{json,md}`. For bowl init0 new/old: perception153.44/164.60s; consequence/planning213.67/272.56s; simulation/render7.25/7.69s; oracle exclusive3.48/8.14s; pi0.5=0. The failed init2 new arm is43.64s slower than old and remains in the report.

Function-level profiles (top15, cumulative times and calls) are in `reports/visual_profile_startup_pair_20261018.json` and `progress_function_profile_20261018.md`. In the improved box startup: planning26.124s, grasp_geometry16.604s/2calls, _cloud_and_ik13.218s/48, prepare11.810s/59, route screen8.963s/59. Actual initial scene.refresh6.752s includes9RPC calls totaling4.930s. These cumulative times overlap. Recursive wrist-refresh child profiles cannot be added to the parent.

Per-candidate process parallelism is deferred: shared IK continuation/warm starts and mutable plans/caches are order-dependent. Exact geometry changes instead preserve outputs. The self-filter optimization preserves8/8 saved-view arrays/evidence and startup request30709bytes/oracle choice. The route AABB optimization preserves9saved screen evidence dictionaries and29CPU tests. Its real startup pair9007_24/9012_24 has identical request/choice bytes; first planning25.95→24.42s. Each is one pair, not stable episode throughput.

Seeded spatial graph optimization353113c preserves the complete saved mask and evidence (including46629149edges) while reducing helper CPU4.35→2.04s. 90affected tests and120literal old/new cases pass. Snapshot `/public/home/sunyihan/rpent_libero_eval/source_bounded_chunk_v3_seed_graph_20261018_353113cb50ab3d86bca70e05c71bbe6c18be961c`; archive SHA `a0b09c5ec5d8830363faffcc5993dca016059217106a05fc1226543a62dc326b`. Entry `scripts.probe_bounded_feasibility:episode`, runtime `/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`. CPU preflight220states passed; same-launcher startup9013 completed0:0 with175 physical ticks. Its request/decision bytes equal9012 exactly. Full latest-source three-pair check9014 is now closed: all six arms succeeded. Startup alone is not task-success evidence.

Candidate compaction remains goal-independent:56→56 candidates,5 compact blockers; exact Qwen tokenizer source evidence13181→12558tokens (623 fewer), from `reports/candidate_compaction_tokens_CPU_20261018.json`. The in-flight `execution_prefix` fields remain covered by the integrated tests. No task-goal filtering or model training.

132 stale ordinary pending shards were cancelled before physical requests (8870:112,8987:20). Running and held/protected work were not changed. Codex2 queued9011 at08:27PDT; automatic future cap changed to3, and Codex2 began running after the borrowed card became free. New job arguments remain node02/nice500. This note is development status, not behavior freeze or admission.

## Final performance-source check9014

These are the user-requested original-task three-state pairs, using source353113c for both arms. The only arm difference is the static chunk boundary rule. pi0.5 is disabled. All six physical results and native terminal signals are preserved.

| Original state | Old/new success | Decisions old→new | Sim steps old→new | Wall s old→new |
| --- | --- | ---: | ---: | ---: |
| bowl spatial0/init0 | both success | 5→3 | 265→265 | 401.207→336.390 |
| historical box_transfer object0/init4 | both success | 5→2 | 410→409 | 253.872→221.668 |
| container object2/init0 | both success | 4→2 | 584→588 | 228.458→183.728 |

The historical box_transfer case is alphabet-soup can, not the separate cream-cheese-box category. This three-state check does not establish a category success rate or a general throughput improvement.

Actual physically executed actions per decision: new {1:1,2:1,3:4,4:1}; old {1:9,2:5}. One lower suffix was interrupted by measured_payload_collision (1/2 eligible lower steps); two release suffixes ended at native_success (2/2). Move_to, descend, lift and carry_to had no intermediate interruptions in their three eligible occurrences each. Native-success stops are not execution failures.

Independent exact-request validation of9014:21requests/43label positions, zero legal denominator/selected/acceptable mismatches and zero planner calls. See `reports/public_legal_v2_physical9014_CPU_20261018.json` and `reports/chunk_v3_seed_graph_20261018_paired_latest.json`. Schema/contract hashes above are unchanged.

| New-rule arm | Perception s | Consequence/planning s | Sim/render s | Oracle exclusive s | Total wall s |
| --- | ---: | ---: | ---: | ---: | ---: |
| bowl | 143.105 | 173.028 | 6.941 | 3.454 | 336.390 |
| historical box_transfer | 116.927 | 83.716 | 8.088 | 0.065 | 221.668 |
| container | 94.948 | 67.320 | 9.705 | 0.060 | 183.728 |

The complete old/new disjoint wall buckets, including IO and residual, are in `reports/wall_time_seed_graph_pairs_20261018.{json,md}`. The top15 function table in the profile report remains source85107ca evidence; its earlier /1 legality note is historical, superseded by /2 above.

## Contacted-panel follow-up

Microwave8993 close used the original contact normal even as current public panel captures rotated. The first CPU-only patch incorrectly reused the initial fingertip-contact 2cm slab restriction and consequently updated none of the four saved captures. No physical run used that patch. The revised fit requires two broad measured tangents with the existing 4:1 extent separation; it does not require the parallel recessed faces to fit within that initial contact slab. Saved public captures now update all4 normals, by9.65°,17.30°,21.06°,28.51° relative to the old normal. These are normal estimates, not measured door endpoint labels.

Source9f11e41 keeps original contact pixels for collision association and updates only a current visible surface's normal; stale, occluded and thin-handle measurements cannot update it. CPU tests:201full adapter cases passed before the one-line fit correction;5affected current-fit cases passed afterward (197deselected). The saved-capture CPU report contains all input hashes and no controls. Live fixture success and a complete post-change category cohort remain pending; neither the /2 schema nor its contract changed.
