# Measured held-object recovery, 2026-10-18

Runtime commit: `bc160fff5d434e72ee0a44585552727256f662c8`, including oracle commit `6c4c015`. Both pushed to `user-fork/harness-v5`. No merge or force push. Shared specification: [SKILL_PACKAGE_SPEC.md](../../SKILL_PACKAGE_SPEC.md); the schema is unchanged.

## Supported root cause and changes

Original cup run8145_60(source9368299) fails after17decisions/1973controls/1335.33s. The first cup reaches its official destination; the second lift succeeds but transport is collision-blocked. At row11, the public request contains two clear upward nudges(1and2cm),both collision=false and IK reachable=true. Carry routes and the longer wrist scan are blocked. The old private oracle only falls back to observation.

The oracle now tries an already available screened2cm,then1cm upward nudge when carry and alignment are both unavailable. The same public candidate filters and failure memory still apply. It supplies no additional coordinates and does not change the model's options.

A separate receipt bug would incorrectly mark such a held nudge unmeasured: stationary `screen.target` is deliberately empty for a held object, but the old contact validator used it as its pre-action reference. The adapter now transforms the already measured `screen.payload` from hand-local into world coordinates for that reference. The existing measured axis-registration rule and5mm progress requirement are unchanged.

## Verification

Full adapter CPU file:158passed in79.17s, `/tmp/bounded_held_nudge_tests_20261018.log`. This includes the27selected nudge/oracle checks;counts overlap. Regression cases preserve blocked options, prefer alignment when available, test the smaller nudge fallback, and verify actual payload-motion evidence with an empty stationary target. Focused Ruff excluding pre-existing CPY001 and diff checks pass. No extra dependency or shared environment change.

Actual same-state CPU MuJoCo branch(no renderer/GPU):

|Arm|Controls|Stop|Cup COM vertical displacement|Dual-finger samples|
|---|---:|---|---:|---:|
|Original wrist scan(all5directions)|0|All routes collision-rejected|0|1/1initial sample|
|Existing2cm upward nudge|18|endpoint|19.101mm|19/19|

Both restored physics flat states have zero residual. The recorded public request pose and restored current proprioception differ by15.928micrometres(max XYZ component)and3.392e-6(max quaternion component);this discrepancy is recorded,not hidden by loosening restoration checks. The first diagnostic script wrongly demanded exact request/current equality;its failure log remains `/tmp/cup8145_bounded_lift_pair_CPU_20261018_initial.log`. Controls use current proprioception and the captured public screen. No post-action RGB-D is rendered in this branch,so it establishes physical recovery movement only. It is neither a complete task nor a registeredv3 confirmation score.

Reports/scripts: `reports/cup8145_bounded_lift_pair_CPU_20261018.json`, `scripts/cup8145_bounded_lift_pair_CPU_20261018.py`. Public blocker crops show a thin wrist-view surface beside the hand; current semantic membership alone still misses both tested blockers in old9368299 and new8e49152. This membership diagnosis deliberately omits temporal payload reconstruction;it is not an exact full-screen comparison. See `reports/cup8145_current_membership_{old,new}_CPU_20261018.json` and `reports/cup8145_lift_blocker_public_CPU_20261018.json`.

## Plate diagnostic, no deployed repair

Same saved plate state:recorded upper rim contact yields0.357mm planar body motion;an actually observed lower rim point yields15.421mm(9.451mm along the tested y push)after three2cm nudges. The lower point is selected from current public target pixels within1cm of the original patch;no private pose supplies it. Both restore residuals0. This does not achieve sustained directed transport and is not deployed. Report:`reports/plate8117_rim_contact_pair_CPU_20261018.json`.

## Snapshot and queue

5880 source:`/public/home/sunyihan/rpent_libero_eval/source_bounded_bc160ff_20261018`.
Archive SHA256:`1e2759b4b4b412babfbb723a71961f015ddd02e4194295e1e7f90018f1434362`.
Entry:`scripts.probe_bounded_feasibility:episode`;interpreter:`/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`.
Deployment receipt:`reports/held_nudge_submission_20261018.json`. Same-source/same-launcher cup startup8157_60 completed564physical controls and cleanly exited0:0. Full8158_60 then started;original20per-category bowl/can/container cohort8159(60states)follows in the same serial lane. See reports/held_nudge_full_submission_20261018.json. All lanes are node02,Nice500,serial%1,aggregate<=3;protected jobs,node01and historical held jobs untouched.

All runs are original-scene development,not training/confirmation. Confirmation-state exclusions remain permanent. No category currently has20completed current-source oracle episodes. Source8e49152 can init1 full8156_21 succeeds natively6decisions/561controls/265.86s;the old9368299 failure9/396/475.30s shares its exact registered case/state identity. This is1improved development state,not category qualification. Earlier9368299 can init3 completed natively(31decisions/2966steps/1291.60s),bringing that unchanged source cohort to3/4(Wilson95%30.1–95.4%);its init1failure remains retained.
