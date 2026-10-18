# Measured handle surface and current oracle diagnostics

Runtime source: `3d71f446c846f0e7bc2b1ae2816f6aab6d3ed461`, pushed to `user-fork/harness-v5`. Only original LIBERO development states, no training or PRO inputs. All confirmation exclusions remain permanent. Schema stays `bounded-skills/1`.

The drawer regression is retained: old `9368299` completed the same drawer-open state; `cbffa78` in job8161_100 failed after two measured 18–20 mm pulls because an exposed curved handle pixel remained a right-finger obstacle. Rebuilding the old contact cache alone did not fix it. The new perception adapter fits local circular cross-sections along the measured handle tangent, requiring 20 points, 25% support and a 90-degree observed arc. It associates only actual current self-filtered RGB-D pixels within the measured axial range and 1 mm residual. No predicted-point removal, collision-clearance change, force increase or budget change.

Validation: 206 focused adapter/geometry/route-screen tests passed in 85.00 s, including five new curved-surface tests. Existing unknown pytest timeout-option warning remains. Scoped Ruff excluding existing CPY001 notices and diff checks passed. Test log: `/tmp/bounded_curved_handle_adapter_tests_20261018.log`.

Immutable snapshot: `/public/home/sunyihan/rpent_libero_eval/source_bounded_3d71f44_20261018`. Archive SHA256 `6f5f2e3c499e169755f1449ed0ef404817b56f000519364bd4694f64dcebcb82`. Manifest: `results/bounded_skills/feasibility_20261017/preparation/original20_manifest_curved_handle_20261018.json`, SHA256 `82ee08998a0b8b8ed6dbb9803d96dea7086e62bcd7a06badadf82f8e9ebcef43`. All 220 original states passed CPU path/state preflight. Entry `scripts.probe_bounded_feasibility:episode`; interpreter `/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`.

Same-source/launcher startup8169_100 completed 0:0, with 437 actual simulation controls, 1 decision and 153.329 s episode wall time. It is excluded from full-episode success denominators. Full paired drawer8170_100 is running; fixture representatives8171_80/120/180/200 follow serially. Only unstarted8162_120/180/200 were replaced. Details and exact arguments: `reports/curved_handle_submission_20261018.json` and `reports/curved_handle_full_submission_20261018.json`.

The committed-source saved-frame screen independently reproduces prototype evidence: old screen rejects; new screen passes the full 2 cm route, with the old blocking point now an exact measured handle pixel. Observed minimum clearance3.8229 mm uses the existing positive-initial-clearance/non-intrusion rule, not a relaxed 4 mm threshold. `reports/drawer8161_curved_committed_pair_CPU_20261018.json` pins both deployed module hashes. A separate paired saved-physics prefix executes old0/new18 controls and moves the middle drawer by old0/new−19.143 mm; both branches remain native_success=false. Physics restore residual0; public FK residual33.856 µm and quaternion residual4.579e-6 are disclosed. This one-prefix result is not a complete-task success. Its r1 sensor assertion failure remains in the original log; r2 separates exact physics restoration from cached sensor recomputation.

Full physical results at this update:

| Source/job | Original category/state | Task success | Decisions | Sim steps | Episode wall seconds |
|---|---|---:|---:|---:|---:|
|bc160ff /8159_0|bowl,init0|1|5|270|430.070|
|bc160ff /8159_1|bowl,init1|1|6|287|496.647|
|bc160ff /8159_2|bowl,init2|0|8|209|576.658|
|bc160ff /8158_60|two-cup transfer,init0|0|24|2094|1786.306|
|cbffa78 /8161_100|drawer open,init0|0|10|549|687.523|
|cbffa78 /8162_80|drawer close,init0|0|13|590|1002.978|

The bowl cohort is2/3, Wilson95%20.8–93.9%; each one-case failure has0–79.3%. These tiny original development samples do not qualify any category. Current-source20-case completion remains pending. Machine summaries retain source cohorts and duplicate-state identities separately in `reports/oracle_closed_progress_20261018.json`.

Cup8158 placed the first cup, then failed second-cup transport. The unowned visible cup-wall point is29.6 mm from the static gripper visual shell, so expanding robot self filtering is unsupported. A 3 mm fused component, measured circular-section hypotheses, and recent public payload references did not recover it. The rolling-reference CPU diagnosis leaves5.660 mm nearest owned-surface distance for all five tested reference captures; it is not deployed. Its first diagnostic run failed because the reused loader attempted NumPy loading of PNG; r2 uses the image loader and completed, with zero physical controls. A saved-public SAM text/point identity diagnosis8172 follows running8159_2 in lane3. Point guidance comes from the existing mask, independent of the blocker. It introduces no new model. Remaining unstarted8159_3–59 were replaced by8173_3–59 using the already physically startup-checked3d71f44 snapshot, after8172; originals and replacement reasons remain in `reports/sam_and_current_oracle_submission_20261018.json`.

SAM8172 subsequently completed0:0 in18 s. Its measured interior-pixel wrist prompt recovers the first raw blocker exactly, score0.96094, original-mask recall93.95% and precision99.66%. Generic cup/mug text alone did not recover it. The first full CPU route pair with the guided-mask union still rejects the same obstacle because geometric component cleanup drops the newly segmented fragment. The runtime is not changed on the basis of a raw-mask improvement. Follow-up CPU diagnosis isolates that cleanup; original and all unsuccessful hypotheses remain recorded. SAM report `reports/cup8158_sam_identity_GPU_job8172/report.json`, paired screen `reports/cup8158_guided_membership_pair_CPU_20261018.json`.

Resource policy: node02 only, Nice500, aggregate maximum3 GPUs in three serial lanes. Running8117_160 and8159_2 remain untouched; historical JobHeldUser and c5/c6/rf jobs unchanged. The queue screenshot and JSON are `reports/resource_latest_node02_cap3_20261018.*`. COORDINATION curved-handle notice occupies bytes6901211199–6901214743 and its append SHA256 is5dd16fa937114c92be7e1c90293183e09afefacfbed4706cb734342fcdc0dbc5; exact slice was read back and verified.

Continue oracle category feasibility first. Diagnose retained cup/plate/fixture failures; then run the historical no-vla_task expert and pi05-only controls, K1/K4 and fork records in that order. No new freeze claim.
