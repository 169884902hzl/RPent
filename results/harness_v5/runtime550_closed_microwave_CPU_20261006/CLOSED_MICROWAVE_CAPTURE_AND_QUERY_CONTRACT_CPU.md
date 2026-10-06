# Closed microwave capture and query contract

This is a read-only diagnosis of eight explicit SOURCE544 setup chains from
job4128's captured 419-case prefix. It does not modify prior scores, rerun SAM
or physics, submit jobs, or admit a recipe. Private joint/predicate values are
not supplied to any geometry computation.

## What the original records establish

- All eight prior microwave IDs remain in the public entity list after close.
  Each becomes `visible=false` with the original `source_step=0`; no new
  microwave ID replaces it. This is not alias retirement or a lost ID mapping.
- The setup receipt is `unmeasured`, with `no_distinct_after_measurement`.
  The old cached cloud correctly cannot certify current door/handle state.
- All eight states registries have frames 0 and 1, and **zero saved SAM masks
  or query-instance records**. The original failure cannot be divided into
  semantic zero recall versus geometric rejection from these records alone.
- At frame1, all prior clouds still project 100% inside the main camera.
  Its old-bounds depth support is 14,905–37,239 points. These points are not
  semantic proof of a microwave instance; its previously open door moved.
- In all eight wrist frame1 captures, prior-cloud in-view fraction and current
  old-bounds depth support are both zero. The image montage shows the arm
  obscuring the main-camera door region and the wrist left at close contact.
  These observations support a view-recovery diagnosis, not a detector label.

## SOURCE549's actual condition

Snapshot: `/public/home/sunyihan/rpent_libero_eval/source_v5_runtime549_20261006`;
commit `8b45399594355c79c2abe6c76a8badab010b8de4`;
archive SHA `9e5992db560397557ddce8c4c3836dfde8530097399be54e9da86f1e50d8bf5c`.
The registered smoke manifest SHA is
`8db78a69313c4b85468887a60cc103506119313c16a73940070d051e86eb43c6`.

The offline query trace used the exact pinned base configuration plus condition
overrides and the original public frame1 RGB-D. SAM replies were deliberately
empty fakes. This establishes calls and missing-evidence behavior; it is not a
detector test or evidence that SOURCE549 fixes the original eight failures.

| Camera | Empty-reply query chain in SOURCE549 |
| --- | --- |
| main | microwave door -> black rectangular frame -> appliance -> open microwave door |
| wrist | microwave door |

`microwave_recall_geometry_v3`, instance geometry, support crop, independent
door measurement and dual-view fusion are enabled. However,
**`instruction_queries_v1=false` and `wrist_recall_v1=false` by default** in the
submitted condition. It has no noun-query expansion or full wrist retry chain.
The eight empty-reply traces promote **0/8** cached parents to visible.
Effective recovery flags are `articulate_view_retreat_v1=true`,
`view_retreat_v2=true`, and `retreat_clearance_v1=false`. These current flags
must not be inferred to have operated in the historical SOURCE544 captures.

SOURCE549/job4178 remains a registered focused development smoke. The parent's
next complete selection manifest will explicitly pin both missing query flags;
the submitted SOURCE549 snapshot and its manifest remain unchanged. No new
runtime patch is justified from unavailable historical mask evidence.

## Full harness default and consumers

Current code pointers, checked without scanning artifacts:

| File | Lines | Actual behavior |
| --- | --- | --- |
| robots/libero/v5_runtime.py | 160 | Both constructor flags default false. |
| harness_v5_eval.py | 340, 341 | Missing Namespace fields fall back to false. |
| harness_v5_eval.py | 994, 996 | Both CLI switches use store_true, so omission is false. |
| v5_batch_eval.py | 163, 173 | Namespace receives the manifest budget as supplied; absent keys are not added. |
| scripts/probe_v5_skill501_original.py | 893, 895 | Only keys present in merged config are passed to the constructor. |
| scripts/prepare_v5_skill536_runtime_smoke.py | 23–25 | Runtime536 preparation pins other features but does not pin these two. |
| scripts/prepare_v5_fixture540_handle_selection.py | 21, 34 | Parent's new preparation now pins both flags true for future manifests. |

No full-harness defaults were changed in this evidence-only subtask.

## Reproduction and hashes

```bash
cd /public/home/sunyihan/rpent_libero_eval
.venv/bin/python results/harness_v5/runtime550_closed_microwave_CPU_20261006/audit_closed_microwave8_CPU.py
PYTHONPATH=/public/home/sunyihan/rpent_libero_eval/source_v5_runtime549_20261006 \
  .venv/bin/python results/harness_v5/runtime550_closed_microwave_CPU_20261006/trace_source549_microwave_queries_CPU.py
```

- `explicit8_public_cases.json` SHA:
  `5528816f1762a32296071b7522384296c4494aba042aa9cb1f6da3ba7e120919`.
- `closed_microwave8_capture_audit_CPU.json` SHA:
  `4d48660d6231f7330a42badb714b1f869ac93200d569142fd10e81471287639b`.
- `source549_microwave_query_contract_CPU.json` SHA:
  `f8acddb3656a4919cdefd334b8463000ef2f47bc969a4e6f03ecb83db23d4eb4`.

Each report records the exact registered image/world/metadata paths and hashes.
The image index is `closed_microwave8_public_views.png` in this same directory.
