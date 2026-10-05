# grasp520: original public-point / private-frame diagnostic pilot

Accepted parent: prepare and launcher only, no Slurm/source/runtime/module/probe edits. Uses one explicit parent, skill516 full400 SHA `a493a63045abc7b79ea6e351ed40d75c2b70736679edbf94cf05508056a13175`. No confirmation data, PRO configuration, artifact glob/scandir or outcome-based case selection.

CPU prepare exited 0. Registered pilot32: first eight parent trial indices per pan/moka × centre/handle arm. Eight unique original scene states, 32 nominal requests; smoke4 is one request per type/arm on the first parent state. This is a capture-contract pilot, not threshold fitting or independent qualification. All original budgets, prompts and methods remain unchanged (160 chunks, same approach/fallback). Point-count threshold stays null, not an invented 5.

Only canonical new probe key is `condition.private_frame_sync=True` (default false); `condition.overrides.record_sam_masks_v6=True` is enabled alongside skill516's existing independent-view/calibration dictionary. No old provisional alias is generated. The final source must actually implement this key before parent launches; CPU prepare does not prove GPU/runtime support.

Probe owner interface, finalized in commit `b12b9b9` (probe501 SHA `fe6b75f80a49546f5f05009471ba0024d64c2136d56c9988c627249eaad7b2ff`, 49 CPU tests passed): no inserted refresh/capture or new robot actions; read at returns of existing `scene.refresh`. Store `contact_evidence.private_frame_sync`, with version `original-private-frame-sync/1`, pregrasp_reference/samples/new_robot_actions=0/selection_calibration_only=true. Each sample: phase/source_step/capture_id/chunk_index, per_view measurement and points descriptors (path/SHA/point_array_SHA/shape/dtype/src/source_step/object_id/current), same-frame raw robot observation, private_contact_before_read/private_contact/sim_time/same_physics_time/private_clearance_m/private_contact_clear_instant, plus metadata.path/SHA. NPZ points use key `array`. The private label is instantaneous, not sustained-hold truth. Missing views remain explicitly missing; an unmeasured chunk is not a captured frame. Entry records existing pre-π0.5 public cache and original private support reference. Public scene caches, stop rules, receipts, budgets and motion route are preserved. Toolkit state steps are never fake-rolled back. Final GPU source must include the owner commit; CPU tests alone do not prove live frame alignment.

The private contact/clearance is a label-side snapshot at the public frame; never substitute the later final hold. Actual first-pass TP/TN/wide-aperture coverage may be insufficient, especially when an old selective witness skipped a wide opening. Report that shortfall and preregister further original trials/methods without outcome filtering. Do not infer coverage merely from flag presence or use confirmation states to tune a threshold. This pilot cannot satisfy the final 95/90/95 gates.

Remote directory:
`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp520_original_frame_calibration_20261005/preparation/`

| Artifact | SHA-256 |
| --- | --- |
| pilot.json | 415671130e33ac4101e371308b47ffdde44bf25dbfd3ca85400108cd8fd32679 |
| smoke4.json | 76961c5906489d856f63819177a4a00b496f3907c48dd1a14d2a29dd80dd3987 |
| registration.json | 0fe8765a768ae9e50e850f96bfbbf956a9907a5098f69eb137655db862d47100 |

Case/seed records SHA: `b9744015bf660fa3c769c85658b78fc97f54640264e4d940d72fd05aed137eef`. This case registration is fixed before outcome inspection. No training rows produced, source created or jobs submitted by child.

Actual completed command:

```bash
python3 /public/home/sunyihan/rpent_libero_eval/scripts/prepare_v5_grasp520_frame_calibration.py \
  --parent-manifest /public/home/sunyihan/rpent_libero_eval/results/harness_v5/skill516_safe_subtask_exploration_20261005/preparation/full.json \
  --parent-sha256 a493a63045abc7b79ea6e351ed40d75c2b70736679edbf94cf05508056a13175 \
  --trials-per-arm 8 \
  --output /public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp520_original_frame_calibration_20261005/preparation
```

Launcher `scripts/run_v5_grasp520_frame_calibration.sbatch`: array0–3%8, four actual parts, one GPU / eight CPUs per part, no node binding or dependency. Parent supplies exact `GRASP520_SOURCE`, `GRASP520_MANIFEST_SHA`; optional `GRASP520_MANIFEST` selects smoke4 instead of default pilot. Outputs will be `.../grasp520_original_frame_calibration_20261005/diagnostic_job<array-job>/part<index>/`. Source identity/job number awaits parent; no nonexistent job reported.

Source SHA: prepare `0962db97120a00713ac3b40a0cb12e5f2469419fe3ca5c84e42ab40ac61ee8ec`, launcher `a47a6f3a9066799fa231b35932c4cf65ebf740e6a33207eb61b93ecff4ed5615`. Launcher `bash -n` exit0. Actual frame labels/raw point synchronization remain to be checked after parent smoke, not claimed passed here.
