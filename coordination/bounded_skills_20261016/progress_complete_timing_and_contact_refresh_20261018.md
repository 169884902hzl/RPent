# Codex3 | complete timing pairs and measured-contact regression repair

All six physical arms of 8822 completed (0:0). These are three original development states, no confirmation or training. Source d2ab0c2; new measured-receipt boundary rule versus legacy static-contact rule. Native task success is reported independently of job exit code.

| State / rule | Native success | Decisions | Sim steps | Wall s | Perception s | Planning s | Sim/render s | Oracle exclusive s | pi05 s | Other+IO+residual s |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| bowl_transfer_libero_spatial_t0_s0 / oracle_k4 | True | 3 | 265 | 526.804 | 183.707 | 322.588 | 7.467 | 3.437 | 0.000 | 9.604 |
| bowl_transfer_libero_spatial_t0_s0 / oracle_k4_legacy | True | 5 | 265 | 574.819 | 201.382 | 346.852 | 7.244 | 8.164 | 0.000 | 11.177 |
| box_transfer_libero_object_t0_s4 / oracle_k4 | False | 5 | 175 | 224.248 | 91.445 | 115.469 | 5.515 | 0.103 | 0.000 | 11.715 |
| box_transfer_libero_object_t0_s4 / oracle_k4_legacy | True | 5 | 410 | 350.218 | 179.104 | 147.979 | 8.422 | 0.084 | 0.000 | 14.629 |
| container_libero_object_t2_s0 / oracle_k4 | False | 5 | 316 | 236.714 | 92.758 | 125.658 | 7.320 | 0.123 | 0.000 | 10.854 |
| container_libero_object_t2_s0 / oracle_k4_legacy | True | 4 | 584 | 297.879 | 140.593 | 134.098 | 10.302 | 0.073 | 0.000 | 12.813 |

The bowl succeeds in both arms with the same 265 ticks: wall 574.819 -> 526.804 s (-8.35%), decisions 5 -> 3. The box and container regressions are NOT speed improvements: both stop early in the new arm. Do not average short failures as throughput improvements. Full additive main-thread-exclusive timing/root detail: reports/wall_time_8822_20261018.json and .md; raw ledgers remain under results/bounded_skills/feasibility_20261017/job8822_{0,24,40}.

Planning is the largest bucket in five of the six arms; perception is also substantial. In the successful bowl new arm, 126.799 s of perception occurs under execution (24.1% of wall), while planning totals 322.588 s (61.2%). This does not support attributing most wall time solely to per-step sensing. Full RGB-D refresh has not been removed. A CPU-only saved-observation profile is now measuring nested geometry/prefix-planning costs before any performance change.

Supported regression: after move_to -> descend -> close, a passive observe(refresh) unconditionally cleared committed_grasps. The hand and closed gripper had not moved. An occluded patch could not be refitted; lift disappeared, followed by blocked scans/no_public_option. Box matched close aperture is 0.06231897179131023 m in both arms. Container shows the same close->refresh->no-lift pattern.

Repair 4524f81 (pushed user-fork/harness-v5): passive refresh or unexecuted wrist scan retains the measured contact; a scan actually withdrawing beyond the endpoint tolerance still clears it. Opening and motion failures retain their prior invalidation rules. No limit, collision clearance, budget, success predicate, state identity, training boundary or confirmation score changed. CPU: 206 passed in 114.82 s; one pre-existing pytest timeout-option warning. Receipt: reports/contact_refresh_CPU_20261018.json.

New immutable source: /public/home/sunyihan/rpent_libero_eval/source_bounded_chunk_v3_refresh_20261018_4524f81. Archive SHA256 8de696ee3d3e626521f1f4f2f393661a08afb2fdf48fbf37f6aa716c5301944a. Spec SHA256 2369e5c9d538384e68e014a0b72f27f007d56ebbf4941780af42d30a92708b62 (supersedes 842a097 spec hash). Schema remains bounded-skills/3, SHA256 7082085b2c59e592e92bfdfedb85e82e3197c3f366d3f0e9e2959435fb415cb3. Entry scripts.probe_bounded_feasibility:episode; interpreter /public/home/sunyihan/rpent_libero_eval/.venv/bin/python. C1/C2: behavior change is contact-plan retention only, no added model-visible fields.

220-state CPU preflight passed. Same-source/same-launcher real startup 8826_24 is running; formal replay of indices 0,24,40 is gated on its actual first physical request and COMPLETED 0:0. New repair has no completed physical result yet. Old paired results and sources are preserved. Resource monitor keeps our ordinary pending behind this replay, protects running and held jobs, uses node02/nice500 and aggregate cap4 only while C2 has no GPU queue. Current running: 8826_24,8600_4,8600_5,8262_160 on node02; C2 idle.
