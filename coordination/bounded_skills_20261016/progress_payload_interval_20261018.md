# Held-payload interval correction

1. Source87ef92e preserves the existing measured4mm surface interval through guided and cross-view completion; the previous sampled extrema discarded current bowl pixels.
2. Saved-public CPU comparisons recover3pixels in9026_10,row5 and1pixel in9026_14,row2. All34recorded rejected-pose checks then pass. Full nudge routes still reject other measured blockers.
3. All4added pixels are bowl pixels in a separate CPU sensor diagnostic; private identity is used only for diagnosis. Runtime uses RGB-D, static geometry and proprioception.
4. CPU tests:241passed; no new Ruff findings,7preexisting. The same-source220-state preflight passed. Startup9210_10 passed with196controls. Matched physical checks9211_10/14 are running or queued; no task success claimed.
5. Existing9026sourceff00387 remains a retained development cohort, not relabeled as87ef92e. Its bowl result is15/20, below the stage diagnostic threshold; these failures still require repair.

## Evidence and limits

The first post-guided completion and the final3D component pass both replaced a noisy measured interval with exact sampled minimum/maximum coordinates. The init10 blocker was0.067mm beyond the sampled z minimum; init14 was0.451mm beyond the sampled x minimum. The correction carries the existing surface association residual into both extents. It does not widen the3mm depth connection,4mm stationary-scene veto, sweep clearance, robot limits, or success criterion. An extent alone never grants ownership.

Saved-state report: `reports/9026_payload_extent_CPU_20261018.json`. Baseline and candidate full screens/point arrays remain on5880 at the hash-pinned paths listed in that report. The comparison reuses accepted saved public guided membership; it does not reconstruct the complete raw SAM response or reproduce live execution. All17recorded rejected-pose checks per state change to pass. Full nudge routes retain4rejections ininit10 and2ininit14 because additional points block those routes; they are not cleared by this patch.

Private diagnostic: `reports/9026_extent_added_pixels_CPU_20261018.json`. The software renderer restores the saved simulator state with zero flat-state error and issues zero controls. Each new point maps to `akita_black_bowl_1_g0` in the main camera. Wrist diagnostic IDs can include transparent visualization sites and are not treated as reliable object labels. No private identity is read by the runtime correction.

Regression: `test_held_payload_interval_recovers_connected_edge_without_owning_neighbours` exercises an image-occluded3D edge; disconnected, known-static and beyond-interval points remain obstacles. Full changed adapter/payload suites:241passed in104.72s. Existing pytest timeout-configuration warning remains. Ruff's code/message findings match HEAD before the patch:5in adapter,2in its tests; this is not an all-clean lint claim. Receipt: `reports/payload_interval_CPU_tests_20261018.json`.

Source snapshot: `/public/home/sunyihan/rpent_libero_eval/source_bounded_chunk_v3_payload_interval_20261018_87ef92e`.
Archive SHA: `4d3a530fd1d1897f8116dac4c527805b0cdf751a5d40afa1330cd367025bbeeb`.
Entry: `scripts.probe_bounded_feasibility:episode`.
Interpreter: `/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`.
Manifest SHA: `25d3556cd74e25914333347923d5c40154a567b97f0fcb519bd1c9246d2349c9`.
Public schema remains bounded-skills/3, SHA `df17c6c49e4992247ab8ff37ebf528f893ac6887ea8cf946e25668aca110b4aa`.

The same-snapshot/launcher startup9210_10 completed0:0 with196controls in178.203s. The gated10/14new-versus-legacy chunk pairs are submitted as9211. Verified9026shards fill the remaining capacity while the startup or pairs run; pending replacements give priority to the paired diagnostic. All jobs are development diagnostics, pi0.5 disabled, node02only, nice500. No confirmation-state reuse or training.

The three other bowl failures remain separate:16/19after lift and17before lift have7retained blockers, all bowl pixels in a CPU diagnostic with transparent sites disabled for identity only. Disabling the sites changes none of these depth values (all seven residuals are0); robot debug sites are not the measurement cause. The interval patch does not clear these saved blockers. No sensor or self-filter change was made from this rejected hypothesis. Evidence: `reports/9026_contact_blocker_sites_CPU_20261018.json`.
