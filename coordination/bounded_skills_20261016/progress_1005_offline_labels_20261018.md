# 10/18 10:05 follow-up

1. Bowl spatial0/init2 is repaired: the same-command 9022 pair succeeds in both arms, at 260 simulation steps; the lower-silhouette mask omission affected both chunk rules.
2. The CPU arbitrary-prefix interface is implemented and tested. Captured measured contexts can fill model-prefix rule labels; historical simulator pickles alone cannot reconstruct every missing label faithfully.
3. Representative microwave function profiles identify route search, cloud/IK preparation, sweep screening, and repeated segmentation/measurement as the main costs. The client profile does not isolate SAM server kernels.
4. Candidate array order is explicitly nonsemantic. Source detailed history remains the last three receipts. Public schema/contract bytes are unchanged.
5. Actual launcher9046 and CPU reannotation now agree at all four oracle positions; a nonoracle nudge prefix is also labeled. Codex2 can use matching new private capture contexts, with substantial CPU cost. Physical microwave recovery continues. No training or freeze admission.

## Bowl cause and matched rerun

Both old and new rules encountered current public depth pixels along the bowl's lower silhouette which SAM omitted from the held-instance mask. Those pixels remained stationary obstacles and blocked transport. Source a5efcd2 applies the existing 3 mm connected-depth completion to the guided held surface; it does not remove unrelated obstacles or relax the 4 mm sweep clearance.

Job9022_2, same registered state and launcher, pi0.5 disabled:

| Arm | Native success | Decisions | Simulation steps | Wall seconds |
| --- | --- | ---: | ---: | ---: |
| New receipt-based chunk | true | 3 | 260 | 356.706 |
| Legacy chunk | true | 5 | 260 | 435.904 |

References: `reports/chunk_v3_connected_payload_20261018_paired_latest.json`, `reports/wall_time_connected_payload_pair_20261018.json`, `reports/public_legal_v2_physical9022_CPU_20261018.json`. The last report independently checks eight actual requests and sixteen label positions: zero legal/selected/acceptable violations, zero planner calls for legal.

## Where request time goes

Saved-state original microwave startup9024_120, source ff00387. It generated a real request and executed305 controls; it is not a task-success result. Raw pstats paths, hashes, calls and both overall/project top15 functions are in `reports/profile_saved9024_120_CPU_20261018.json`. Inclusive cumulative times below overlap and must not be added.

| Function | Calls | Cumulative seconds |
| --- | ---: | ---: |
| MeasuredSkillAdapter.request | 1 | 46.782 |
| _surface_contact_plan | 3 | 18.913 |
| _cloud_and_ik | 48 | 17.987 |
| _candidate | 58 | 15.691 |
| SmoothMotion.prepare | 54 | 14.917 |
| grasp_geometry | 1 | 14.563 |
| PublicRouteScreen.__call__ | 54 | 12.737 |
| measure_fixture_handle_pose | 2 | 11.223 |
| PublicPoseScreen.check | 900 | 6.711 |
| measure_fixture_endpoint | 4 | 5.648 |
| _contact_pixels / _instance_pixels | 6 / 8 | 5.331 / 5.331 |
| remove_visual_robot | 5 | 5.003 |

Each full scene.refresh in this startup takes5.821–7.481s. The initial refresh has11RPC calls totaling5.356s; three receipt refreshes add another17.979s. The whole startup's exclusive perception buckets are segmentation27.617s, entity measurement20.892s, depth0.259s, capture/transport3.626s. Thus the large per-decision perception total includes repeated captures plus measurement work nested in request construction and execution; it is not a single35–40s scene.refresh. The previous box profile has planning26.124s; microwave has more fixture contact searches and900IK checks.

Caching decisions:

- Same-capture raw pixels, self-filtered world images, target subtraction, and exact-pose mesh checks can be reused. The existing exact-output fixes use these boundaries, mesh broad phases and a seeded connected graph. Startup request/choice bytes and saved geometry arrays were checked against their original versions, as documented in `progress_0750_followup_20261018.md`.
- Per-candidate process parallelism is not independent with the present code: numerical IK warm starts/last_solution, plans and caches are shared in candidate order. Forking each candidate from a different seed can change reachability evidence. It has not been enabled under the requirement to preserve candidate/consequence values.
- Per-view geometric transforms/fits are candidates for parallel work after freezing input arrays and assembling results in the existing order. The client RPC trace currently groups SAM/server computation with transport waiting; it does not justify a claim about separate SAM kernels or a measured speedup from parallel SAM calls.
- Skipping full scene measurements inside a chunk could miss a moved obstacle. Receipt-target-only measurement has not been enabled without paired evidence that later candidates and collision inputs remain correct.

## CPU interface for Codex2

`robots.libero.bounded_offline_labels` exports:

```python
state = capture_annotation_state(oracle, request)
reference = save_annotation_state(path, state)
state = load_annotation_state(reference['path'], reference['sha256'])
label = annotate_prefix(state, request, model_selected_prefix_ids)
```

It uses the same PublicPrefixPrediction and private task-progress rules. Public `legal` is exactly `legal_after(request,prefix)` and never invokes the planner. `rule_acceptable` uses the prefix's conditional predicted state; it is not physical branch success. A model prefix need not follow the oracle-selected path. Explicit terminal/infeasible/no-option statuses are retained, rather than turning them into positive labels. No environment, rendering, control or RPC method exists in the frozen sensor interface. CPU route and IK screening still incur computation time.

CLI: `python -m scripts.label_bounded_prefix --state STATE.pkl.gz --state-sha256 SHA --request REQUEST.json --prefix PREFIX.json --output LABEL.json`.

The probe records `private_prefix_annotation_state` separately from its public request. Snapshots include private goal status/bindings and must remain outside model-visible state. They contain captured depth/geometry and routes missing from the existing raw simulator pickle. Old records without this information remain explicitly unsupported; they must not be labeled by substituting another state or oracle path. Prefetched requests need their capture-time context and are not exported from a later execution state.

Private interface `libero-offline-prefix-label/1`; public `bounded-skills/3` and `public-request-legal/2` unchanged. Schema SHA `df17c6c49e4992247ab8ff37ebf528f893ac6887ea8cf946e25668aca110b4aa`; contract SHA `7e898e3bd4e8f4c7a4e9951d897cc1fe682037ee35ee4d6d5cc1f52606e2f49c`.

CPU validation:243tests passed in129.34s (adapter, payload, offline labels), and53tests passed in51.49s (offline labels, screen, probe resilience, chunk; overlapping sets). New interface tests check canonical oracle-path agreement, a nonoracle nudge prefix, save/load, no live IO, repeated annotation without mutation, mismatched request, invalid prefix, terminal prefix and corrupt snapshot. CLI help, scoped Ruff and diff whitespace checks pass. One pytest configuration warning remains (`timeout` is not registered in this local environment).

Actual-capture validation: startup9046_120 executes305controls and saves the initial canonical microwave-close request with its private context. Offline CPU labels match online legal/rule_acceptable/selected at all four positions, with zero mismatches. A different legal nudge prefix returns33legal IDs and5acceptable IDs. No simulator, RPC or GPU is used by the annotation audit. This validates the captured-state path; it does not establish physical branch success or support incomplete historical contexts.

| Prefix | CPU seconds | Legal | Acceptable |
| --- | ---: | ---: | ---: |
| Oracle position0 | 8.955 | 34 | 5 |
| Oracle position1 | 30.475 | 33 | 1 |
| Oracle position2 | 42.834 | 32 | 1 |
| Oracle position3 | 51.006 | 31 | 1 |
| Nonoracle nudge | 28.669 | 33 | 5 |

The compressed context is101,610,674bytes. Capture and serialization add7.616s to the startup ledger. Bulk offline labeling remains expensive; the interface currently prioritizes matching the existing conditional oracle over throughput. Evidence: `reports/offline_prefix_9046_120_CPU_20261018.json`; script `scripts/audit_offline_prefix_state_CPU_20261018.py`. Runtime source remains c916ab1. The actual result has been appended and byte-verified in shared COORDINATION for Codex1/Codex2.

The later contact/binding context at9209_120,row3 also matches all three online oracle positions in legal/rule_acceptable/selected, with zero mismatches. A nonoracle nudge prefix is labeled as well. CPU times are1.619/12.349/16.210s for the oracle prefixes and9.398s for the alternative. Its compressed context is170,703,093bytes. Across the two independently captured contexts, all seven checked oracle positions match; two nonoracle prefixes return labels. These are conditional oracle rules, not measured physical branch outcomes. Evidence: `reports/offline_prefix_9209_120_row3_CPU_20261018.json`. Codex2 can fill unknown positions when the matching private measured context exists; no claim is made for missing historical contexts or unsaved prefetched requests.

## Additional microwave evidence

9025 new arm is a retained development failure:16decisions/772controls, no public option; the legacy arm is still being measured. Saved row7 has30target/finger hits at positive2.37–3.98mm clearance, zero mesh-interior hits. Scene geometry already allowed leaving an occupied positive margin without moving closer; the target cloud used a separate path without that rule. The correction applies the same rule to both clouds. Real interiors, new obstacles and deeper incursion are still blocked. Saved-public CPU geometry changes three1cm escape routes from rejected to passed, while all three inward routes remain rejected. This is geometry-only evidence with a stub IK, not physical reachability or task success. Report: `reports/microwave9025_target_margin_CPU_20261018.json`.

The registered180-state source ff00387 cohort continues separately and is never silently relabeled as the newer source. Interim bowl13/14, Wilson95%[0.6853,0.9873]; one collision failure is retained for diagnosis. Remaining categories are incomplete. This is oracle development with pi0.5 disabled, not confirmation or learned-model performance.
