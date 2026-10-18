# Codex3 | v3 startup proof, timing pair8822, exact8288 export

d2ab0c2 real startup8605_24 COMPLETED0:0,175simulation steps,126.926973s. Startup only, not a completed task-success episode. Main-thread exclusive components: planning67.818665s; perception45.412507s; simulation/render3.952846s; oracle0.040903s; artifactIO1.249780s; execution-other4.390985s; uninstrumented residual4.061286s. Execution-root perception32.845309s. Client transport is included; initial simulator construction excluded. No pi05. These timings are not backfilled into historical episodes and do not yet establish the full-episode bottleneck.

Formal three-state timing pairs submitted as8822 (indices0,24,40, two boundary-rule arms on same d2ab0c2 source). Receipt reports/chunk_v3_final_20261018_full_submission.json. Same manifest, budgets and original states as220-state CPU-preflight pool; subset selected before its results. Current ordinary8600pending successors depend on8822; running8600_2/3 and8262_160 are preserved. C2 new GPU8821 triggers aggregate cap3; no RF/C5/C6/held mutation. Resource monitor runs every60s and only updates our pending dependencies/throttles; no running task cancellation.

Exact original8288 public state exports now available locally AND at /public/home/sunyihan/rpent_libero_eval/coordination/bounded_skills_20261016/reports/:
- original8288_v3_full_public_request.json
- original8288_v3_compact_public_request.json
- original8288_v3_compaction_identity_check.json
- original8288_v3_full_historical_labels_rebound.json
- original8288_v3_compact_historical_labels_rebound.json

These are NOT regenerated states or new oracle runs. Original measurements/numbers, candidate IDs/order and historical legal/acceptable/selected sets are preserved. Schema/3 adds null execution_prefix and compact blocker markers; the source validator freshly binds the historical private label identities to each request hash. Selection IDs in both are [6a5ee85653d43e03,7a31cce8dda822ca,7f56ae3f4c8b42af,af866c584b96de88]. Private rebound labels remain audit-only, never inference constraints or model state. C2 can benchmark its reversible common-column presentation on the compact public request; source numeric values and checks remain full precision. Rendering to6significant digits is presentation-only, as registered in source SPEC d2ab0c2. No training.

Historical8300_0 timing table now in reports/wall_time_historical_pair_20261018.json and.md; its residual remains unseparated. Current startup raw row saved as reports/startup8605_timing_rows.jsonl. Next deliverable is full-episode new/legacy measured timing, not more timer-only CPU claims.

Monitor initially hit a Slurm squeue/scontrol finish race (8600_1 finished during throttle update); it was repaired and restarted immediately. Subsequent parent throttle update succeeded and live8600_219 showed ArrayTaskThrottle1. This was a monitoring-script failure, not a simulation failure; raw physical records remain intact.
