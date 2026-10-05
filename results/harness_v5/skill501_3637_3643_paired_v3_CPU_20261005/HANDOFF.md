# Codex3 original-skill audit and private-frame handoff

2026-10-05. This receipt covers completed original-task jobs only. No PRO,
sealed or human instruction files were read. No new Slurm job, physical
trial, model call or training row was created by these CPU audits.

## Implemented probe changes

- `36eee2e`: explicit `contact_approach_fallback="measured_bounds_centre"`
  when measured handle geometry is absent. The registered approach records
  original rejection, actual measured bounds and fallback. Without the
  flag it remains an unmeasured, unexecuted attempt.
- The independent-view flag replaces the final verdict after the RPent
  helper, retaining its original stable-measure evidence and legacy
  aperture/trial-lift/hold controls. This does not claim to replace those
  old controls. Macro witnesses use a read-only nullable single frame,
  without a new hold or early stopping the complete subtask.
- `b12b9b9`: `condition.private_frame_sync=True` records the existing
  pregrasp measured cache and every existing `scene.refresh` return.
  No extra capture, perception refresh, movement, hold, stop or toolkit
  step rollback is inserted. False and null frames are saved as well.
  Unmeasured chunks are not presented as measured frames.
- `contact_evidence.private_frame_sync.samples` contains each capture
  identity/source step, per-view raw measured NPZ point files and SHA256,
  current robot joint/EEF/body-quaternion observation, and synchronous
  private contact/clearance instant. Private values are diagnostic labels
  only; they never override receipts or decide control. A same-frame instant
  is distinct from the later sustained-hold measurement.

Probe source SHA256:
`fe6b75f80a49546f5f05009471ba0024d64c2136d56c9988c627249eaad7b2ff`.
Focused command: `.venv/bin/python -m pytest tests/unit_tests/robots/libero/test_v5_skill501_original.py -q`.
Result: 49 passed. Compile, scoped diff check and undefined-name Ruff check
passed. No new GPU validation of the private-sync flag is claimed here.

## Completed results

| Job(s) | Coverage and actual result | Verifier / limitation |
|---|---|---|
| 3620 | Moka reset 63/100, overhead 40/100, handle 17/100; all 300 choices SHA matched | Agreement 93%, 75%, 90%. Handle has 34 unexecuted missing-handle trials; actual-contact success 17/66. Each arm repeats 50 states twice; exploration only. |
| 3637 → 3643 | Same 20 registered cases and all 40 choices SHA matched. New fixture counts: newly satisfied 4, prior-satisfied preserved 3, prior-satisfied regressed 2, physical failure 2, missing binding 1 | Only actual placement tools are counted: TP2/TN1/FP0/FN1, null2. Macro stove-off is a saved public FP; private predicate false is retained. Pi0.5 noise was not fixed. |
| 3619_2 + 3636 | Original 47 known + continuation 52 known, all 99 sustained grasps true; one original executed unknown remains | TP98/FN1/FP0/TN0, agreement 98/99. Wilson 96.26–100% over 99 known. 100 unique tuples/state SHA; all 100 choices hashes matched, including original empty failed trace. Not a complete 100-known confirmation. |
| 3631 + 3642 | Original 20 known + continuation 79 known; 93/99 sustained grasps true. Original executed unknown retained | TP92/TN5/FP1/FN1, agreement 97/99. Wilson 87.40–97.19%; FP1/6 true negatives, FN1/93 positives. 100 unique tuples/state SHA, all choices hashes matched. No unknown replacement. |
| 3648 | All four macro smokes executed 800 Pi0.5 contact actions each; no infrastructure or execution errors. Pan centre/handle: sustained grasp then release, target true. Moka centre: no sustained grasp, target false. Moka handle: sustained grasp then release, target false | Five saved per-view verdicts contradict false lift/support conditions. NumPy Boolean identity bug reproduced on CPU and sent to root; root fixes `6ae0e71`/`dda7974` are separate new source. Original evidence not relabeled. |
| 3655 | 12/12 fixture actions executed, no missing bindings or execution errors. Newly satisfied 5, prior-satisfied preserved 2, prior-satisfied regressed 2, physical failure 3 | Measured: TP3/TN1; null8. Two microwave-open attempts really regress a prior-satisfied predicate. Two microwave-close attempts start already satisfied. No qualification claim. |

Full-transfer release never changes a prior sustained grasp into a grasp
failure. Task/subgoal completion and grasp-phase success remain separate.
All thresholds and the six-class independent-confirmation requirement remain
unchanged. Unknown metrology outcomes were neither replayed nor filled from
later observations. Current qualification remains NO-GO.

## Remote reports

All paths below are under `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/`.

| Report | SHA256 |
|---|---|
| `moka514_full3620_CPU_20261005/audit/report.json` | `76a6adedf195e33c5d12b75c8dc3e56e3878db4708369be9198859e3225b81f2` |
| `skill501_3637_3643_paired_v3_CPU_20261005/paired_smokes.json` | `d4f7e8d50814c3b525fe2daf9b6621935c8c0961b8fbcda929ca5267011b0e46` |
| `skill501_3637_3643_paired_v3_CPU_20261005/box_confirmation.json` | `975357f7e9c5e9be4148d1a9540476d4f6c01d4a4ab98941b1f655779798f1e4` |
| `mug512_3642_closed_CPU_20261005/report.json` | `d96826d45b4573ab215bf6d3c7aa24968f44377a7b21c69bbe6975032868349b` |
| `skill516_3648_closed_CPU_20261005/report.json` | `40d0e2026bfdea47b50e5e251a3f3a37becac5b2ac8aadb913e5dd6fef3d611c` |
| `skill517_3655_closed_CPU_20261005/report.json` | `8242d8a7c43dd3436fc22335a90d09e933103ee1c752a2689570a286ecb383f3` |

The paired v3 summary used the explicit source directory
`skill501_closed_audit_sources_v2_CPU_20261005/scripts/` and its absolute
entry script. The 3648/3655 reports used
`skill501_closed_audit_sources_v3_CPU_20261005/scripts/summarize_v5_skill501_smoke_closed.py`;
the cup report used the explicit v4 audit function. Each report carries the
actual summary source path/SHA, manifests, ledgers, original run source hashes
and per-case raw paths. Earlier report versions remain on the server.

Parent owns push and the shared COORDINATION update. Calibration job 3662 and
the repaired Boolean smoke 3658 are assigned to the calibration agent, so this
audit does not duplicate their read or modify their outputs.
