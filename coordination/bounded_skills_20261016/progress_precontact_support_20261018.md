# Measured support-plane correction

1. Source ec89f741b4b729b0ac854b7510ec74105a5a13e9 removes measured support-plane pixels from target contact surfaces while retaining the original scene as collision obstacles. CPU adapter/payload/offline-label checks pass 252/252.
2. Six saved-state CPU replays change four lift routes from rejected to passed. Independent CPU identity checks find 78/78 newly associated pixels belong to the target and zero belong to its support. These are geometry checks, not physical successes.
3. Can init6/8 remain rejected: their residual blockers are target pixels 5.39/6.99 mm from the current segmented instance. Their geometry is still under investigation; no collision or truth criterion is relaxed.
4. Startup 9242_22 uses the final snapshot. Its predecessor 9240_22 was cancelled before starting, with zero controls. The startup must produce actual controls before the same launcher admits the four-state new/legacy comparison.
5. The five 10:05 questions are answered in progress_1005_offline_labels_20261018.md. Codex1/Codex2 receive this source-pinned update through COORDINATION; no training, confirmation admission, or freeze is claimed.

## Supported cause and correction

Additional current-view segmentation masks contain support-plane pixels. In the preceding 68573bc saved-state checks, can init6/8/19 acquired 30/15/25 support pixels. The old stationary-scene veto cannot identify pixels which were not observed in its reference frame. Reciprocal registration fixes the occlusion-induced rigid-fit error but does not correct this mask contamination.

The adapter reuses `measured_work_surface` on current public RGB-D and visible measured anchors. The fitted plane is cached for its capture step. Only a fit with p95 residual at most 1 mm excludes pixels within 1 mm of that plane from the instance/contact surface. The unmodified scene cloud retains them as collision obstacles. Fresh-view evidence is required: no new-frame operation is applied to stale cached targets or source-step-less instance arrays. No simulator pose or private identity enters runtime.

| Saved original state | Baseline CPU lift route | Final CPU lift route | Added / removed surface pixels |
| --- | --- | --- | ---: |
| Bowl init17 / 9026_17 | rejected | passed | 31 / 0 |
| Can init2 / 9026_22 | rejected | passed | 10 / 15553 |
| Can init5 / 9026_25 | rejected | passed | 33 / 17494 |
| Can init6 / 9026_26 | rejected | rejected | 0 / 16419 |
| Can init8 / 9026_28 | rejected | rejected | 3 / 17806 |
| Can init19 / 9026_39 | rejected | passed | 1 / 18648 |

The removals are differences from the old completed target surface; they must not all be described as support pixels or erroneous pixels. Every final adapter SHA is `b4367c8e74ca7c3b2fc502b7f75394c32fa35ebdf89c55947887458b265f1ea9`. Final membership deltas match the independently audited predecessor arrays byte-for-byte. Restored-state error is zero. Private identities are used only in the independent diagnostic audit, outside runtime and model requests.

Two remaining blockers are not stationary-scene matches: their distances to that cloud are 24.94/32.70 mm. Both lie inside the registered reference bounds. Removing the plane and recomputing principal axes or testing all three cylindrical axes did not repair them. Those negative results are retained; they do not justify expanding a collision exemption.

## Validation and physical source

The first implementation failed three freshness/evidence regressions (3 failed, 249 passed, 124.64 s) and was not admitted to a GPU. After correction, the same suite passes 252 tests in 122.13 s. Six focused freshness tests overlap that suite. An existing pytest timeout-configuration warning and seven pre-existing Ruff findings remain. The new diagnostic scripts pass scoped Ruff.

Commit: `ec89f741b4b729b0ac854b7510ec74105a5a13e9`, pushed to `user-fork/harness-v5`.

Snapshot: `/public/home/sunyihan/rpent_libero_eval/source_bounded_chunk_v3_support_plane_20261018_ec89f74`.

Archive SHA256: `68aa74bc9188156b3bde2147bd2455d4fa658a9ab1bfea772cffe36486bacf68`.

Entry: `scripts.probe_bounded_feasibility:episode`. Interpreter: `/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`.

All 220 registered original states pass the existing CPU preflight. Startup 9242_22 is pending normal node02 capacity at this update. After a successful actual-control startup, the same snapshot and launcher run indices 17,22,25,39 under both chunk rules. Source c1bc859 pair 9239_17 continues separately. Old-source ff00387 array 9026 keeps its own source and denominator. Neither result is evidence for ec89f74.

The previous resource controller was terminated after its last pair was running; only `monitor_v3_timing_20261018.py --tag chunk_v3_support_plane_20261018` now controls admission. No running GPU task was cancelled. Node02 only, nice=500, at most three slots while Codex2 has GPU work; rf/c5/c6 and old held jobs remain untouched.

Public `bounded-skills/3` schema SHA `df17c6c49e4992247ab8ff37ebf528f893ac6887ea8cf946e25668aca110b4aa` and `public-request-legal/2` contract SHA `7e898e3bd4e8f4c7a4e9951d897cc1fe682037ee35ee4d6d5cc1f52606e2f49c` are unchanged.

## Evidence

- `reports/support_plane_exclusion_validation_CPU_20261018.json` and its named test log.
- `reports/9026_{17,22,25,26,28,39}_support_final_CPU_20261018.json`.
- `reports/support_exclusion_identity_CPU_20261018.json`.
- `reports/precontact_component_remaining_identity_CPU_20261018.json`.
- `reports/9026_{26,28}_precontact_stages_CPU_20261018.json` and `9026_{26,28}_support_plane_diagnosis_CPU_20261018.json`.
- `reports/chunk_v3_support_plane_20261018_preparation.json`, `chunk_v3_support_plane_20261018_startup_submission.json`, and `chunk_v3_precontact_component_20261018_superseded.json`.

These supersede the queued-source statements in progress_precontact_reciprocal_20261018.md and progress_precontact_stationary_20261018.md; their historical evidence remains unchanged.
