# Codex3 | exact voxel optimization after full-episode timing evidence

Full six-arm timing and the two contact-plan regressions were delivered first. No scene refresh, SAM query, depth frame, collision tolerance, IK criterion or candidate is removed by this optimization.

Source 334144f (pushed user-fork/harness-v5) replaces multi-column integer-cell uniqueness with fixed-width integer-record equality. It still selects the same first original depth pixel and preserves input order. 228 related CPU tests passed (157.01 s); receipt reports/voxel_record_CPU_tests_20261018.json.

Saved-pixel comparison: three original states (bowl init0, box init4, container init0), main+wrist, fixed first three captures, 2 mm and 4 mm voxels: 18 images / 36 comparisons, all output arrays point-for-point and in the same order. Three alternating-order repetitions per input; median paired per-input speed ratio 3.3667, range 2.2389–4.2777. Sum of per-input medians 24.7152 -> 7.2266 s. Report reports/voxel_record_pixels_CPU_20261018.json includes each input/output SHA and raw timings. These are microbenchmarks, not full-episode throughput.

| Same-state CPU profile | Before4524 | After334 |
| --- | ---: | ---: |
| Total profiled seconds | 148.728852 | 101.449004 |
| Voxel calls | 156 | 156 |
| Nested voxel seconds | 64.907800 | 17.983687 |

Both full and blocker-compact requests were independently passed through BoundedOracle.choose in each source from the same saved original8288 public RGB-D. Exact decisions, complete labels and public screen checks match before/after. No controls or GPU. cProfile adds overhead; nested voxel time must not be added to total time. Historical step4 lift remains explicitly unreproduced; both current sources choose observe. Report reports/voxel_oracle_identity_and_profile_CPU_20261018.json; raw profile and independent oracle request/label files remain on 5880.

Snapshot: /public/home/sunyihan/rpent_libero_eval/source_bounded_chunk_v3_voxel_20261018_334144f. Archive SHA256 e761bb37b15725c261f96661899e6450e35edae233f88e45cb2f3fbaa10faedb. Schema and spec unchanged from4524 (schema v3 SHA7082085b2c59e592e92bfdfedb85e82e3197c3f366d3f0e9e2959435fb415cb3; spec SHA2369e5c9d538384e68e014a0b72f27f007d56ebbf4941780af42d30a92708b62). Entry scripts.probe_bounded_feasibility:episode; /public/home/sunyihan/rpent_libero_eval/.venv/bin/python. 220-state CPU preflight passed.

Physical state: contact-repair cohort8827/source4524 is still running. Bowl/new is native success,3 decisions,265 sim steps,538.454443 s. Box/container and remaining legacy arms are not yet complete. Optimization334 has no complete physical-episode speed result. Same-launcher startup8829_24 queued afterany8827; first physical proof is required before the new upper-bound array is admitted.

214 ordinary unstarted8600 elements from the superseded schema2 source were cancelled and will be replaced by the new original-state cohort. The live8600_4/5 runs were preserved; their raw results and old cohort receipts remain. Exact cancellation IDs and queue-before proof: reports/old8600_pending_replaced_by334_20261018.json. No protected or held job was changed. This prevents starting stale source after the current three-state regression replay. Resource caps remain node02/nice500,3 cards normally /4 only while C2 has no GPU queue.
