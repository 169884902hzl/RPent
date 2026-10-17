# Held transport alignment: CPU evidence and physical development

This is original-scene simulation development, with the private oracle selecting existing public options and pi0.5 disabled. Startup and saved-data CPU checks are excluded from full-task denominators. All historical failures and permanent confirmation-state training exclusions remain unchanged.

## Implementation and exact saved-data check

Pushed source: `845a720e6c8e77b98de765593046877fbd4fcee6` on `user-fork/harness-v5`. Snapshot: `/public/home/sunyihan/rpent_libero_eval/source_bounded_845a720_20261017`. Code archive SHA256: `dfa1cb2ffea5c9048811b517ad818a88a21f9849719bc4decd90d0f354b792a5`. Entrypoint: `scripts.probe_bounded_feasibility:episode`; interpreter: `/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`.

The box8065_20 row7 hand was tilted 0.779rad. Its current-orientation carry had no accepted numerical IK solution under the existing thresholds. Multiple starts, fixed wrist-yaw variants and small height variants did not produce an accepted solution; numerical failure is not proof of physical unreachability. The object suite's measured table is near z=0, so this waypoint is not inside a z=0.9 table.

The existing public `align(anchor_id=held)` can now retain the projected finger-closing direction while aligning the approach axis to a measured support-plane normal. The plane comes from public RGB-D, with centroid and P95 plane-fit residual recorded. Alignment changes orientation at the measured EEF position. The same observed hand/payload collision and numerical IK screens apply. No force, budget, collision margin or servo threshold changed. No per-category execution rule or private coordinate is introduced.

Replay using the production `_route` alignment and carry methods on the saved public RGB-D/proprioception passed: 212 route samples, 36 IK checks, minimum clearance 7.4756mm. Normal P95 residual was 0.0198mm. This screens the observed hand/payload and robot numerical IK; unseen space and future full-arm collisions are not certified. It is not physical task-success evidence. Replaying production SmoothMotion.prepare with the four saved consecutive public sensor samples also passes the alignment trajectory: 4.57849s, 152 screened samples and 16 IK checks; see [smooth production CPU replay](reports/box8065_measured_plane_align_smooth_production_CPU_20261018.json). Report: [production CPU replay](reports/box8065_measured_plane_align_production_CPU_20261018.json). The earlier same-formula prototype report is retained separately.

Affected CPU validation from this implementation: 138 passed in 57.46s across bounded_skills and work_surface_geometry; the two new behavior cases reran successfully after an import-only edit. Scoped lint found no new findings, and diff checking passed. These overlapping checks are not added together.

Spec semantics updated for held alignment; spec SHA256 `bd36dc86ad1a36eca4341ab15c301d9129ce73c753f6cb684a0e90b329d4ca8e`. Shared schema bytes are unchanged: SHA256 `0da29ae7727d35c91083f3d0d2971cfbc8d91da6214b519c1202f388874d1de5`.

## Complete representative results

|Source/job|Category/state|Native success|Decisions|Simulation steps|Wall seconds|Failure|
|---|---|---:|---:|---:|---:|---|
|d6c768c / 8065_20|box / object task0 init0|0/1|19|689|878.620|Carry numerical IK rejection, then collision after scanning|
|6ddc6a1 / 8061_60|cup / libero_10 task4 init0|1/1|15|1,883|1,177.935|None; native success on release|
|1da79f2 / 8069_0|bowl / spatial task0 init0|1/1|6|279|459.804|None; native success on release|

The box's first lift failed; the second lift publicly verified holding before the carry rejection. The cup task contains two mugs and used two lifts/carries; no pi0.5 call occurred. The bowl passed carry, lower and release; the same original state failed under6ddc6a1, so this is one paired improvement after the moving-silhouette repair. Each 0/1 has Wilson95% 0–79.3%, and each 1/1 has Wilson95% 20.7–100%. These representatives are not 20/category qualification. Source-specific closed rows are kept in [closed progress](reports/oracle_closed_progress_20261018.json).

## Active validation and resources

Same-source/launcher startup8070_20 completed0:0 with280 actual controls: move_to226,align7,descend47,all successful receipts. Its initial dependency on8069_0 was removed only after a live queue query showed two running Codex3 jobs, because cup8061_60 had completed. The full same-source box8071_20 and representative array8072 then submitted. Array8072 has indices0,40,60,80,100,120,140,160,180,200 and throttle1, replacing the completed8069 lane. Startup never enters the task denominator.

The older plate8036_160 remains running with repeated contact/reapproach attempts and no final result yet. No running task, old held job or protected c5/c6/rf job was cancelled or released. Resources follow the10/17 override: node02 only, aggregate Codex3 cap3, Nice500. Queue evidence: [JSON](reports/resource_latest_node02_cap3_20261018.json) and [screenshot](reports/resource_latest_node02_cap3_20261018.png). Codex1/Codex2 were notified through shared COORDINATION appends at bytes6901164029–6901166263 and6901166263–6901167134.

There is no latest-source 20/category upper bound yet. Further oracle checks precede new comparator, K1/K4 task and fork runs. Real model HTTP/async evidence is pending a caller-owned service; VLA history remains n=0/null until eligible development/exclusion provenance is available.
