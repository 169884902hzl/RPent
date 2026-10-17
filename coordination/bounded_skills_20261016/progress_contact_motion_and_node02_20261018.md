# Codex3 bounded-skill development: contact receipts and node02

Source: `776e900c4a9886fc57011cb17e474fe38436276b`, pushed to `user-fork/harness-v5`. Original LIBERO development and CPU checks only. No training, PRO input, confirmation rescoring or real robot use.

## Resource receipt

Pacific time 2026-10-17 11:03:07: three running jobs on node02 (`8025_101`, `8028_60`, `8030_160`), zero on node01. Queue image and JSON: `reports/resource_latest_node02_cap3_20261018.{png,json}`. Arrays use throttle1; dependencies preserve three concurrent channels. All submitted launchers pin node02 and Nice500. c5/c6/rf jobs and historical held jobs were untouched.

`8023_60` completed its exact-source/launcher startup with463 controls. Full cup run `8028_60` uses78c7c46. `8027_160` completed startup with336 controls; full plate run8030_160 usesddecd79. Neither startup is counted as a completed-task trial.

## Changes and checks

- `2da8248`: an anchored contact nudge requires a new visible RGB-D entity measurement after the action. Less than5mm measured object displacement is `no_effect`; missing/stale measurement is `unmeasured`. Free-space nudges retain motion-arrival semantics; native benchmark success remains success. Audit of the unchanged8020 plate record found28/28 nudges labelled success despite object displacement below5mm (EEF moved15.3–19.8mm). Evidence: `reports/plate_contact_motion_CPU_20261018.json`. This audit is not a physical rerun or rescoring of confirmation data.117 adapter/payload CPU tests passed in43.99s; scoped Ruff and diff checks passed. Startup8031_160 is queued after8030, so it adds no fourth running channel.
- `776e900`: `rpent.skill_package.contract.is_boundary(candidate)` makes anchored `nudge` and `rotate_wrist` observation boundaries. Selection rejects a hidden suffix; execution excludes contact from blending and asynchronous lookahead. Unanchored motions still blend.110 adapter/async/schema CPU tests passed in49.98s; scoped Ruff and diff checks passed. Startup8032_180 (stove off) is queued after8028, preserving the same channel.
- Shared schema SHA256 remains `0da29ae7727d35c91083f3d0d2971cfbc8d91da6214b519c1202f388874d1de5`. Current specification SHA256 is `d8478e7d29da148e9bcbc373575c080e93a57014c5cc36df84bf378829d18b8a`. Codex2 should use the shared boundary helper as well as the schema when validating K=4 decisions.

Snapshots on5880:

| Source | Snapshot | archive SHA256 |
|---|---|---|
|2da8248|`/public/home/sunyihan/rpent_libero_eval/source_bounded_2da8248_20261017`|`3d478ba00dd173aa5ca242f70ebc20b26bf07724c5463a77e6aed149eb6e42e6`|
|776e900|`/public/home/sunyihan/rpent_libero_eval/source_bounded_776e900_20261017`|`4d582520bfeec42c09ee25d47d9bf1b20b58fa109d6331792604612835134e85`|

The temporary deployment helper previously retained inherited `source_snapshot` metadata. It is now fixed, and8027's manifest was corrected while it was still pending. Both new manifests pin actual commit, snapshot and archive. Already-running and completed old manifests were not rewritten; their actual launcher SOURCE/SOURCE_COMMIT remains recorded separately. This corrects the earlier progress note's premature statement that the helper had already updated those fields.

## Completed physical results, source-specific

| Job/source | Original case | Official result | Decisions | Sim controls | Wall seconds |
|---|---|---:|---:|---:|---:|
|8016_100 / b045b98|drawer open,init0|1/1|10|586|938.2|
|8016_60 / b045b98|two-cup transfer,init0|0/1|18|1806|1267.7|
|8010_120 / 2d50b76|microwave close,init0|0/1|6|355|473.7|
|8010_160 / 2d50b76|plate push,init0|0/1|66|1640|3780.1|
|8020_160 / 8c43651|plate push,init0|0/1|36|878|2021.7|
|8025_100 / ca4ce83|drawer open,init0|1/1|10|586|937.0|

All have pi05_calls=0 and rgbd_dual_view/1. Source-specific single-case Wilson95% intervals:1/1 is20.7–100%;0/1 is0–79.3%. Repeated init0 across revisions is not an independent sample. No current-source20/category cohort is complete, so there is no100/category expansion or freeze claim. Full rows and identities: `reports/oracle_closed_progress_20261018.json`.

## Microwave diagnostics not promoted

Current/old-reference boundary completion still leaves the same leftfinger blocker. A new CPU-only search across8 measured vertical-panel contact patches also finds no passing route; it is retained as diagnostic evidence, not added to runtime. `reports/microwave_vertical_patches_CPU_20261018.json`.

CPU prefix replay matches EEF/joints within1e-8 and camera origin exactly, but the saved depth blocker does not match a replay visual mesh closely enough: nearest reported door mesh is9.4mm away and exact/neighbour rays miss the near surface. Robot replay agreement alone does not establish matching furniture geometry. Its body identity remains unconfirmed; this private replay is not used for control or runtime ownership. `reports/microwave_blocker_body_private_CPU_replay_r4_20261018.json`. Next diagnostic must preserve/verify fixture state and compare rendered depth with the same saved public capture before assigning a collision body.

## Common motion residual

CPU recomputation of all240 unchanged7754 raw trajectories (20 states x3 routes x4 methods), with raw file hashes: `reports/motion_20261017/common_command_residual_CPU_20261018.json`. Same definition for every method: norm(before XYZ + action XYZ x0.05m - after XYZ). This is one-control commanded-position residual, not timed-trajectory tracking error or task success.

| Executor | n | Median per-route maximum residual(mm) | p90(mm) |
|---|---:|---:|---:|
|legacy_move_to|60|35.319|36.413|
|legacy_move|60|35.727|36.931|
|smooth K=1|60|25.025|32.279|
|smooth K=4|60|20.416|22.313|

Earlier jerk/path/stops measurements remain in `progress_motion_vla_20261017.md`; their previous legacy/timed residual definitions must not be directly compared. Task-level K=1/K=4 and branch experiments remain after oracle category feasibility, per resource priority.
