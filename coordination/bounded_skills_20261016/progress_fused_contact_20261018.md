# Measured rim membership and saved-state lift replay

Runtime commit: `8e491524af107c82f2951882e25a9d25b205cdb4`, pushed to `user-fork/harness-v5`.
Specification: [SKILL_PACKAGE_SPEC.md](../../SKILL_PACKAGE_SPEC.md).
The shared schema, execution limits, 4 mm swept collision margin and private/public boundary are unchanged.

## Fix and CPU checks

The original-can init1 run `8147_21` closed both fingers on the can, but four recorded scene pixels blocked its first lift. Exact saved RGB-D reconstruction reproduces 155,644 obstacle voxels and 2,703 target voxels. Both camera crops were inspected. The wrist mask omitted the rim; one main-view rim pixel was originally segmented but discarded as a small disconnected component after robot filtering.

The adapter now bounds each camera's depth-connected instance by the combined extents of both current clean masks. Original semantic fragments need eight opposite-view current instance samples within 3 mm, a two-dimensional surface patch and at most 1 mm plane residual. Unlabelled proximity alone adds nothing. Public robot filtering and depth-gap checks remain active. This is generic instance perception, with no object-class or task-goal control branch.

|Saved-public reconstruction|Scene voxels|Target voxels|Missing recorded blocker pixels|10 cm lift route|
|---|---:|---:|---:|---|
|Old|155644|2703|4|Collision rejection|
|Combined current extent only|155522|2949|1|Collision rejection|
|Combined extent plus semantic fragment support|155521|2950|0|Pass, minimum clearance 5.999 mm|

The intermediate unsuccessful version is retained. Route comparison starts both methods from the same recorded public sensor state; it is separate from the original runtime's sampled trajectory. Raw and derived evidence: `reports/can8147_contact_membership_CPU_20261018{,_dev}.json`, `reports/can8147_contact_membership_extent_only_CPU_20261018.json`, and `reports/can8147_crossview_pair_summary_CPU_20261018.json`.

217 related CPU tests pass (`/tmp/bounded_fused_extent_tests_20261018.log`); the adjusted degenerate-plane cases were also rerun in the 23-test geometry file. These counts overlap. Tests cover the rim behind opposite-view occlusion, nearby depth-gap obstacles, unlabelled pixels, offset planes and degenerate support. Focused Ruff excluding pre-existing copyright notices and `git diff --check` pass.

## CPU physics branch, not a task score

Both arms restore the same hashed private development snapshot, with zero flat-state restoration residual. The controller reads saved public RGB-D and current proprioception. Private contacts and object pose are sampled only for diagnosis. Rendering and GPU use are disabled.

|Arm|Controls|Stop|Object COM rise|Final EEF error|Last 0.5 s dual-finger contacts|Last-window non-gripper contacts|Relative COM drift|
|---|---:|---|---:|---:|---:|---:|---:|
|Old screen|0|Collision rejection|0|—|One initial supported sample only|1|0|
|New screen|32|Endpoint|99.857 mm|0.470 mm|11/11|0/11|0.045 mm|

The new arm's minimum lower-extent clearance over its original support in that window is79.657 mm. This establishes a real saved-state lift under unchanged execution limits. It is neither a complete task success nor a registered v3 confirmation score; the isolated support intervention was not run. Exact controls, public sensors, private samples, snapshot and script hashes are in `reports/can8147_lift_physics_pair_CPU_20261018.json`.

## Deployment and pending full episodes

5880 source: `/public/home/sunyihan/rpent_libero_eval/source_bounded_8e49152_20261018`.
Archive SHA256: `fbd253fed0a60c3243d1bea68bb488460b7ba4e53829dede758d54a449971365`.
Manifest: `results/bounded_skills/feasibility_20261017/preparation/original20_manifest_8e49152_fused_contact.json`, SHA256 `f42735eaef2d23ca30976b7139b952c73e041847548d50d283e6e4a33dc99541`.
All220 registered original states and absolute input paths pass CPU preflight.
Entry: `scripts.probe_bounded_feasibility:episode`; interpreter `/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`.

Same-source/same-launcher startup8154_21 waits behind the running8147_23. Only unstarted8147_24–39 were replaced; their cancellation identities and reasons are saved in `reports/fused_contact_submission_20261018.json`. Full new-source episodes remain gated on an actual startup physical request and clean exit.

Resource policy remains node02 only, Nice500, three serial lanes with aggregate<=3 GPUs; node01, protected jobs and historical held jobs remain untouched. No model training or PRO reading occurred. All confirmation exclusions remain permanent.

Source9368299 full closed results now include can2/3(Wilson95%20.8–93.9%), bowl1/1(20.7–100%) and container1/1(20.7–100%). The can failure is the blocked lift above and is retained. A cup representative has physically placed its first cup on the correct plate and is still executing its second goal; it is not yet counted as full success. No category has20 completed current-source oracle trials.

Plate8117_160 CPU snapshots show brief single-finger grazing followed by loss of contact during y nudges. Its body moves less than1 mm over the diagnosed prefix. The top-rim contact is insufficient for sustained pushing; no plate repair is claimed. Drawer moving-surface ownership and microwave arc-following also remain open. Startup8151_140 for the preceding7e2e869 handle correction is queued separately.
