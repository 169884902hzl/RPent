# grasp518: wide-opening point evidence audit

CPU audit completed for all 700 explicitly registered original-task episodes: pan3616 four arms ×100 and moka3620 three arms ×100. Every closed choices SHA matches. No glob/scandir, PRO configuration, sealed text, new simulation, policy call, old verdict edit, runtime/module/probe edit or Slurm submission.

| Evidence | Full 700-episode result |
| --- | ---: |
| Saved robot pose steps (EEF xyz/body quat/jaw qpos) | 2538 |
| Declared whole-scene per-camera world cloud files present | 5076 |
| Public verification frames | 1138 |
| Frames with same-step robot pose and camera whole-scene cloud | 1138 |
| Episodes enabling record_sam_masks_v6 | 0 |
| Declared target instance SAM mask artifacts | 0 |
| Episodes saving per-view target raw point payloads | 0 |
| Episodes with private snapshots synchronized to visual frames | 0 |

Result: **cannot calibrate `minimum_points_per_finger` from these saved records**. Whole-scene depth/XYZ plus measured boxes do not recover the original target-only segmentation: bounding-box crops can include fingers, support, furniture and neighbouring objects. Fused points must not be relabelled as camera-specific raw evidence. The later sustained-hold truth is not a synchronized label for an earlier public frame.

Both fixed runtimes have SHA `0b129a8747516ca591d49265881dc7d394538e122edbf8863404521bffb8bd09` and have no independent per-view point cache. Their mask-saving capability exists but is disabled in all 700 configs. The state manifests retain the same-step public body quaternion needed with calibration513's fixed robot transform; the target-mask/phase-label gaps remain.

Using the **new empty-open calibration boundary** `0.07815118134021759 - 0.000853613018989563 = 0.07729756832122803 m`, thirteen π0.5-return samples are wide: later hold truth 1 positive /12 negative. This descriptive count is neither per-frame TP/TN nor a changed verdict; the old 0.07 threshold and all original results remain intact. Keep the point threshold null.

Artifact directory on gpu5880-ts:
`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp518_wide_points_evidence_CPU_20261005/report_v2/`

- report.json SHA: `137c8692484f94d5835c0015ca9511470effe4955f15dc4811b6f984a618c095`
- evidence_rows.jsonl SHA: `9a9bbb64813be5a77d6bc5d1eee64abfdf2282f47014a20dad90bf4adeebef45`
- audit script SHA: `384aa497535cd9d9f0b597d419c62fb95d8e39c0ba814c6b7f6075a7a2393e28`

The original report directory is preserved. v2 only clarifies the proposed point-count formula to match the current public verifier and records the fixed capture identity; all 700 evidence rows are byte-identical. NPZ file presence and manifest step alignment were checked; no array-content or new SAM-mask reconstruction was claimed.

Smallest useful new original development pilot: pan and moka, each ≥30 synchronized wide-opening true-positive episodes and ≥30 true-negative episodes. Distinct task/init units must exclude preselected confirmation states; repeated conditions and frames stay grouped. Start with an outcome-unfiltered measurement smoke, then preregister additional original methods/states if natural TP/TN coverage is insufficient. The 30/30 pilot supports separability checks, not independent ≥95% qualification.

True-positive labels come from synchronous private clearance/finger support at each captured public frame plus sustained hold. True negatives include empty fingers near a target, target still on support, one-finger/briefly lifted then dropped targets and non-target contamination near the gripper. These private labels never enter state, candidates, stop criteria or public receipts.

Save each frame's immutable camera RGB/depth/world cloud, exact SAM instance mask and camera metadata, pre-fusion object points with object_id/source_step/src, synchronized public EEF/body-quat/jaw qpos, measured pregrasp support, phase/capture time and immediate private diagnostic snapshot. Freeze camera/SAM/dtype/selector versions. Reproduce the module's exact count slabs `abs(x-side*opening/2)<=measured_tolerance` inside calibrated pad depth/height boxes; do not silently move slabs using the asset's separate inner-pad-gap offset, widen opening, pool fused pixels or fit per-task geometric margins.

Choose an integer point threshold only on grouped development data, report both errors and unknown coverage, and keep null if positive/negative point counts overlap or target association is missing. Freeze the threshold and SHA before independent original holdout/confirmation. Unknown is not counted as correct agreement. Final gates remain ≥100 new states per class, ≥95% overall true first-grasp success, ≥90% each class and ≥95% verifier agreement, with bidirectional errors and Wilson intervals.

Actual remote audit used `python3 scripts/audit_v5_grasp518_wide_points_evidence.py` with explicit calibration513 JSON, pan490/moka493 full manifests, the seven named `full_job3616/part0–3` and `full_job3620/part0–2/episodes.jsonl`, and both fixed runtime files. Complete exact input paths and SHA are in report.json; reads followed only ledger output_dir plus states.json declarations. Exit 0; no GPU used.
