# Initial lift: public measurement repair

Runtime commit `11a73af4e967883ac1a5494811e0f43f56f83918` is pushed to `user-fork/harness-v5`. Snapshot: `/public/home/sunyihan/rpent_libero_eval/source_bounded_11a73af_20261017`; code archive SHA256 `86c59556b635f82fe7de983c7211b2bf2b8de17b6b5a7df5327140c9157605a1`. Spec SHA256 `3786f6df51a36891c19300cca72db807211a328721a5a04abae380f99ae4c396`. Schema bytes are unchanged: `0da29ae7727d35c91083f3d0d2971cfbc8d91da6214b519c1202f388874d1de5`.

## Evidence

Original-scene bowl `libero_spatial/task0/init2`, source96679ad/job8087_2, returned two `public_hold_not_verified` failures. Public lower-bound rise was81.23/81.85mm and gripper opening3.44/4.08mm,above its calibrated empty-closed bound2.70mm. Visible-centre displacement relative to EEF was16.88/17.35mm,just outside the old15mm centre check.

CPU-only private saved-control replay8099 completed without a renderer or GPU. At each rejected lift's final sample,both fingers contacted the bowl,there was no non-gripper contact,and true lower clearance was38.16/39.64mm. In the last0.45/0.50s,dual contact was10/10 and11/11;maximum relative COM drift was7.60mm and0.0047mm. The first window includes part of the rise and is shorter than the registered0.5s scoring window; these diagnostics do not declare a new sustained-grasp score. Flat snapshot restore error was0,but maximum EEF control-replay error was0.823/1.371mm. This is approximate replay,not full trajectory identity. The original failure receipts and task result remain unchanged.

The third lift was publicly accepted; the whole original run still failed after16 decisions/661 controls because carry/scan options were blocked. The preceding source closed2/3 bowl episodes; it has not completed20/category. Box8095_20 also remains a task failure after21 decisions/1239 controls:the lift passed,then transport lost the object and correctly returned `public_hold_lost`.

## Code and checks

Lift now uses the same fresh public RGB-D bounds transported by measured EEF rotation/translation as transport validation. The reference stores the complete measured post-close robot pose. It still requires3cm lower-bound rise,calibrated nonempty opening,and a bounds gap no greater than15mm. Centre displacement remains diagnostic. Missing/stale paired motion gives `unmeasured`. These endpoint checks do not establish continuous holding at every intermediate instant. No truth pose,task goal,request field or schema field is introduced.

`pytest tests/unit_tests/robots/libero/test_bounded_skills.py -q`:145 passed in72.87s,one existing unknown-timeout-option warning. Scoped Ruff with `--ignore CPY001` and `git diff --check` passed. New cases cover a changed visible centre,stationary object,separated surface,empty closed gripper,and stale evidence. Private replay code and a compact hashed ledger are in `scripts/bowl8087_lift_replay_CPU_20261018.py` and `reports/lift_bounds_11a73af_delivery_20261018.json`.

## Physical admission and resources

All220 explicit original-state hashes and absolute paths passed CPU preflight. Same-source/launcher startup8101_2 waits for running8087_3;no new-source physical outcome yet. Only unstarted8087_4–19 were cancelled to replace this known old verification path. Existing8072_100,8087_3 and8095_140 continue naturally. Contact startup8098_80 remains queued after8072. Subsequent arrays must retain aggregateGPU<=3 on node02,Nice500. No node01,protected or historical held job was changed. Confirmation exclusions remain permanent;all new records are development,training=false.
