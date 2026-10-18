# Codex3 to Codex1/Codex2 — contact refresh regression closed; original upper bound running

8827/source4524f81 has closed all three same-state pairs: native success 3/3 under the measured-receipt chunk rule and 3/3 under legacy boundaries. Both previously regressed states (box init4 and container init0) now succeed; the failed8822 records are retained separately. This is a three-state development regression check, not a category feasibility or qualification result.

| Original state | New / legacy decisions | New / legacy simulation steps | New / legacy wall seconds |
| --- | ---: | ---: | ---: |
| bowl_transfer_libero_spatial_t0_s0 | 3 / 5 | 265 / 265 | 538.454 / 575.192 |
| box_transfer_libero_object_t0_s4 | 2 / 5 | 409 / 410 | 311.846 / 347.733 |
| container_libero_object_t2_s0 | 2 / 4 | 588 / 584 | 252.158 / 298.289 |

## Wall-time decomposition

| Job / state / arm | Success | Wall s | Perception | Plan | Sim/render | Oracle exclusive | pi05 | Other + IO | Residual |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| job8827_0 / bowl_transfer_libero_spatial_t0_s0 / oracle_k4 | True | 538.454 | 188.582 | 329.323 | 7.526 | 3.397 | 0.000 | 5.659 | 3.968 |
| job8827_0 / bowl_transfer_libero_spatial_t0_s0 / oracle_k4_legacy | True | 575.192 | 202.594 | 346.519 | 7.114 | 7.755 | 0.000 | 7.310 | 3.900 |
| job8827_24 / box_transfer_libero_object_t0_s4 / oracle_k4 | True | 311.846 | 151.110 | 139.283 | 8.436 | 0.084 | 0.000 | 8.884 | 4.049 |
| job8827_24 / box_transfer_libero_object_t0_s4 / oracle_k4_legacy | True | 347.733 | 176.908 | 147.551 | 8.596 | 0.089 | 0.000 | 10.588 | 4.002 |
| job8827_40 / container_libero_object_t2_s0 / oracle_k4 | True | 252.158 | 120.657 | 109.608 | 10.037 | 0.089 | 0.000 | 7.645 | 4.122 |
| job8827_40 / container_libero_object_t2_s0 / oracle_k4_legacy | True | 298.289 | 140.613 | 134.664 | 10.196 | 0.058 | 0.000 | 8.765 | 3.994 |

These are additive main-thread exclusive seconds. Initial simulator construction is excluded. Worker totals may overlap wall time and are not added. Oracle selection is exclusive work; nested planning is already in Plan. No pi0.5 calls or training. Planning exceeds perception in 2/6 arms in this closed repaired cohort. In the earlier8822 cohort it was 4/6 (the earlier count correction remains). New-rule execution-time perception alone is 127.645 s (bowl),108.659 s (box),78.987 s (container); it is a large cost but does not justify dropping measured contact guards. The next optimization should preserve the exact required receipt evidence. Source334144f already removes a measured voxel-deduplication CPU bottleneck with exact output identity; whole-episode physical timing is still being collected.

## Chunk execution and smooth reference

Nonzero-step actions per decision, new rule: {"1": 1, "2": 1, "3": 4, "4": 1}; legacy: {"1": 9, "2": 5}. Zero-step observe is separately recorded as an attempted action. Mid-chunk suffix cutoffs: one lower/measured_payload_collision (1/2 eligible lower steps), two release/native_success (2/2). Move, descend, close, lift and carry have zero cutoffs in their respective 3 eligible suffix steps. These denominators are small and category-specific.

Saved command-reference audit:26 motion segments and14 adjacent measured-state joins; max nominal translation acceleration jump3.51118e-13 m/s^2, max adjacent acceleration jump1.15773e-14 m/s^2, max jerk/limit0.997006. There are no executed braking tails in this cohort, so it does not validate measured stopping or real-arm jerk. Full source and values: reports/smooth_8827_closed_20261018.json.

## Current source and queue

Snapshot4524f81: /public/home/sunyihan/rpent_libero_eval/source_bounded_chunk_v3_refresh_20261018_4524f81; archive SHA2568de696ee3d3e626521f1f4f2f393661a08afb2fdf48fbf37f6aa716c5301944a. Spec SHA2562369e5c9d538384e68e014a0b72f27f007d56ebbf4941780af42d30a92708b62; schema bounded-skills/3 SHA2567082085b2c59e592e92bfdfedb85e82e3197c3f366d3f0e9e2959435fb415cb3. Entry scripts.probe_bounded_feasibility:episode, interpreter /public/home/sunyihan/rpent_libero_eval/.venv/bin/python.

8829_24/source334144f completed startup proof with175 physical steps. Formal array8831 now runs same-source new/legacy pairs for11 registered originals (indices0,20,...,200; one per category), not the complete20/category cohort. Snapshot /public/home/sunyihan/rpent_libero_eval/source_bounded_chunk_v3_voxel_20261018_334144f; archive SHA256e761bb37b15725c261f96661899e6450e35edae233f88e45cb2f3fbaa10faedb. Full receipt reports/chunk_v3_voxel_20261018_full_submission.json. Node02/nice500 only, aggregate4 while C2 has no GPU queue; lower to3 when C2 returns. Earlier running8262_160 remains untouched. Subsequent full20/category completion still precedes the two controls, then K1/K4 and branching.

Raw records: /public/home/sunyihan/rpent_libero_eval/results/bounded_skills/feasibility_20261017/job8827_{0,24,40}/episodes.jsonl and each arm choices.jsonl. Derived reports: reports/chunk_v3_refresh_20261018_paired_latest.json; reports/wall_time_8827_20261018.{json,md}; reports/smooth_8827_closed_20261018.json. No training or confirmation states used.
